"""opensky_query.py — the ONLY sanctioned path to OpenSky Trino (OPENSKY_TRINO_RULES.md, T1).

Enforces, in code, the guidelines at https://opensky-network.org/data/trino
so that no agent or script can accidentally trigger a ban:

  T2  every referenced table has a predicate on its partition column
      (`hour`, or `day` for flights_data4/5); `time` alone is rejected
  T3  partition span caps: <= MAX_HOURS_PER_QUERY hours (hour tables),
      <= MAX_DAYS_PER_QUERY days (day tables); longer -> run_chunked()
  T4  state-vector queries need a row bound (icao24/callsign/lat-lon box)
      unless allow_unbounded=True (round-file instruction required)
  T5  one query at a time (process lock), polite pause between chunks,
      bounded backoff retries (2), then raise
  T6  soft warning at 5 min, hard stop at 25 min wall clock
  T7  parquet cache keyed by SQL hash under data/raw/opensky/; cache hit
      never touches Trino
  T9  lost-data periods skipped by the chunker; every query logged to
      logs/opensky_queries.log

DO NOT EDIT THE GUARDS. If the guard rejects your SQL, the SQL is wrong.
Raising a cap is a DECISION-PENDING memo for the human, never a code edit.

Usage (attended sessions only — T8):

    from opensky_query import OpenSkyClient
    osk = OpenSkyClient()
    df = osk.query("SELECT ... FROM flights_data4 WHERE day = 1645660800 AND ...")
    df = osk.run_chunked(
        "SELECT ... FROM state_vectors_data4 WHERE hour BETWEEN {h0} AND {h1} "
        "AND icao24 IN ('3c6444') AND time BETWEEN {h0} AND {h1}",
        start="2022-02-24", end="2022-02-26", table="state_vectors_data4")
"""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import threading
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "data" / "raw" / "opensky"
LOGFILE = ROOT / "logs" / "opensky_queries.log"

# ---- caps (T3). Changing these requires human approval via DECISIONS.md ----
MAX_HOURS_PER_QUERY = 6
MAX_DAYS_PER_QUERY = 7
SOFT_LIMIT_S = 5 * 60
HARD_LIMIT_S = 25 * 60
PAUSE_BETWEEN_CHUNKS_S = 3.0
BACKOFFS_S = (60, 300)

DAY_TABLES = {"flights_data4", "flights_data5"}
KNOWN_TABLES = DAY_TABLES | {
    "state_vectors_data4", "position_data4", "velocity_data4",
    "identification_data4", "operational_status_data4", "acas_data4",
    "allcall_replies_data4", "rollcall_replies_data4", "flarm_raw",
}
BOUND_TABLES = {"state_vectors_data4", "position_data4", "velocity_data4"}

# Lost-data periods (UTC), from the OpenSky Trino page (T9).
LOST_PERIODS = [
    ("2023-01-02 23:00", "2023-01-03 10:00"),
    ("2023-01-18 11:00", "2023-01-23 07:00"),
    ("2023-06-21 13:00", "2023-06-21 22:00"),
    ("2023-11-15 06:00", "2023-11-16 08:00"),
    ("2023-11-20 01:00", "2023-11-20 03:00"),
    ("2023-12-02 08:00", "2023-12-05 03:00"),
    ("2024-05-20 10:00", "2024-05-21 05:00"),
]

_LOCK = threading.Lock()  # T5: one query at a time per process


class TrinoRuleViolation(ValueError):
    """Raised before any network call when SQL violates OPENSKY_TRINO_RULES.md."""


# ----------------------------------------------------------------------------
# Guards (T2, T3, T4) — pure functions on SQL text, unit-testable offline
# ----------------------------------------------------------------------------
_TABLE_RE = re.compile(r"\b(?:from|join)\s+(?:minio\.osky\.|osky\.)?([a-z_0-9]+)", re.I)
_COMMENT_RE = re.compile(r"--[^\n]*|/\*.*?\*/", re.S)


def _strip(sql: str) -> str:
    return _COMMENT_RE.sub(" ", sql)


def tables_in(sql: str) -> list[str]:
    return sorted({t.lower() for t in _TABLE_RE.findall(_strip(sql))})


def partition_col(table: str) -> str:
    return "day" if table in DAY_TABLES else "hour"


def _partition_predicates(sql: str, col: str) -> list[tuple[str, str]]:
    """Return (kind, args) for each predicate on the partition column."""
    s = _strip(sql)
    out = []
    for m in re.finditer(rf"\b(?:\w+\.)?{col}\s*=\s*(\d+)", s, re.I):
        out.append(("eq", m.group(1)))
    for m in re.finditer(rf"\b(?:\w+\.)?{col}\s+between\s+(\d+)\s+and\s+(\d+)", s, re.I):
        out.append(("between", f"{m.group(1)},{m.group(2)}"))
    for m in re.finditer(rf"\b(?:\w+\.)?{col}\s+in\s*\(([\d\s,]+)\)", s, re.I):
        out.append(("in", m.group(1)))
    # >= ... <= pair
    lo = re.search(rf"\b(?:\w+\.)?{col}\s*>=\s*(\d+)", s, re.I)
    hi = re.search(rf"\b(?:\w+\.)?{col}\s*<=?\s*(\d+)", s, re.I)
    if lo and hi:
        out.append(("between", f"{lo.group(1)},{hi.group(1)}"))
    return out


def partition_span_seconds(sql: str, col: str) -> int:
    """Widest span implied by the partition predicates (0 for a single value)."""
    preds = _partition_predicates(sql, col)
    if not preds:
        return -1
    vals: list[int] = []
    for kind, args in preds:
        vals += [int(x) for x in args.split(",") if x.strip()]
    return max(vals) - min(vals)


def check_sql(sql: str, allow_unbounded: bool = False) -> None:
    """Raise TrinoRuleViolation if sql breaks T2/T3/T4. Silent if compliant."""
    tabs = tables_in(sql)
    if not tabs:
        raise TrinoRuleViolation("T2: no table found in SQL (need FROM <table>)")
    unknown = [t for t in tabs if t not in KNOWN_TABLES]
    if unknown:
        raise TrinoRuleViolation(f"T2: unknown table(s) {unknown}; only *_data4/5 tables are sanctioned")
    for t in tabs:
        col = partition_col(t)
        span = partition_span_seconds(sql, col)
        if span < 0:
            raise TrinoRuleViolation(
                f"T2: table {t} requires a WHERE predicate on partition column "
                f"'{col}' (=, BETWEEN, IN, or >=/<=). Filtering on 'time' alone is "
                f"a full-table scan and is banned by OpenSky.")
        cap = MAX_DAYS_PER_QUERY * 86400 if col == "day" else MAX_HOURS_PER_QUERY * 3600
        if span > cap:
            raise TrinoRuleViolation(
                f"T3: {t} partition span {span/3600:.0f}h exceeds cap "
                f"({cap/3600:.0f}h). Use run_chunked().")
        if t in BOUND_TABLES and not allow_unbounded:
            s = _strip(sql).lower()
            bounded = any(k in s for k in ("icao24", "callsign")) or (
                "lat" in s and "lon" in s)
            if not bounded:
                raise TrinoRuleViolation(
                    f"T4: {t} query has no row bound (icao24/callsign list or "
                    f"lat/lon box). Pass allow_unbounded=True only with a round-file "
                    f"instruction quoting T4.")


# ----------------------------------------------------------------------------
# Time helpers
# ----------------------------------------------------------------------------
def to_unix(x) -> int:
    if isinstance(x, (int, float)):
        return int(x)
    ts = pd.Timestamp(x)
    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    return int(ts.timestamp())


def floor_hour(u: int) -> int:
    return u - (u % 3600)


def floor_day(u: int) -> int:
    return u - (u % 86400)


def in_lost_period(u0: int, u1: int) -> str | None:
    for a, b in LOST_PERIODS:
        la, lb = to_unix(a), to_unix(b)
        if u0 < lb and u1 > la:
            return f"{a} -> {b}"
    return None


# ----------------------------------------------------------------------------
# Client
# ----------------------------------------------------------------------------
class OpenSkyClient:
    """Serial, cached, guarded Trino client. Attended sessions only (T8)."""

    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self._conn = None
        CACHE.mkdir(parents=True, exist_ok=True)
        LOGFILE.parent.mkdir(parents=True, exist_ok=True)

    # -- connection is lazy so guards/caches work without pyopensky installed
    def _connect(self):
        if self._conn is None:
            from pyopensky.trino import Trino  # the only import of pyopensky in the repo
            self._conn = Trino()
        return self._conn

    @staticmethod
    def _key(sql: str) -> str:
        norm = re.sub(r"\s+", " ", _strip(sql)).strip().lower()
        return hashlib.sha1(norm.encode()).hexdigest()[:16]

    def _log(self, msg: str) -> None:
        stamp = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        with LOGFILE.open("a", encoding="utf-8") as f:
            f.write(f"[{stamp}] {msg}\n")

    def query(self, sql: str, allow_unbounded: bool = False) -> pd.DataFrame:
        check_sql(sql, allow_unbounded=allow_unbounded)  # T2/T3/T4 — never skip
        key = self._key(sql)
        pq = CACHE / f"{key}.parquet"
        if pq.is_file():  # T7
            self._log(f"CACHE-HIT {key} {pq.name}")
            return pd.read_parquet(pq)
        (CACHE / f"{key}.sql").write_text(sql.strip() + "\n", encoding="utf-8")
        if self.dry_run:
            self._log(f"DRY-RUN {key} (guards passed, not sent)")
            return pd.DataFrame()

        with _LOCK:  # T5
            last_err: Exception | None = None
            for attempt in range(1 + len(BACKOFFS_S)):
                t0 = time.monotonic()
                self._log(f"SEND {key} attempt={attempt + 1} sql={' '.join(sql.split())[:300]}")
                try:
                    df = self._run_with_limits(sql)
                    dur = time.monotonic() - t0
                    df.to_parquet(pq, index=False)
                    self._log(f"DONE {key} rows={len(df)} secs={dur:.0f} -> {pq.name}")
                    if dur > SOFT_LIMIT_S:
                        self._log(f"WARN {key} exceeded soft limit ({SOFT_LIMIT_S}s); "
                                  f"halve chunk size before the next query (T6)")
                    return df
                except TimeoutError as exc:  # T6 hard stop
                    self._log(f"HARD-LIMIT {key}: {exc}. STOP querying; ask the human to "
                              f"KILL the query in the Trino UI.")
                    raise
                except Exception as exc:  # noqa: BLE001
                    last_err = exc
                    if attempt < len(BACKOFFS_S):
                        wait = BACKOFFS_S[attempt]
                        self._log(f"ERROR {key} {type(exc).__name__}: {exc} — backoff {wait}s")
                        time.sleep(wait)
            self._log(f"GIVE-UP {key}: {last_err}. Mark task BLOCKED.")
            raise RuntimeError(f"OpenSky query failed after retries: {last_err}")

    def _run_with_limits(self, sql: str) -> pd.DataFrame:
        conn = self._connect()
        result: dict = {}

        def target():
            try:
                result["df"] = conn.query(sql)
            except Exception as exc:  # noqa: BLE001
                result["err"] = exc

        th = threading.Thread(target=target, daemon=True)
        th.start()
        th.join(HARD_LIMIT_S)
        if th.is_alive():
            raise TimeoutError(f"query still running after {HARD_LIMIT_S}s")
        if "err" in result:
            raise result["err"]
        return result["df"]

    def run_chunked(self, template: str, start, end, table: str,
                    allow_unbounded: bool = False) -> pd.DataFrame:
        """Issue one guarded query per chunk, sequentially, skipping lost periods.

        `template` uses {h0}/{h1} (hour tables) or {d0}/{d1} (day tables) as
        inclusive unix partition bounds. Chunk = MAX_HOURS_PER_QUERY hours or
        MAX_DAYS_PER_QUERY days.
        """
        u0, u1 = to_unix(start), to_unix(end)
        col = partition_col(table)
        if col == "day":
            step, floor = MAX_DAYS_PER_QUERY * 86400, floor_day
            k0, k1 = "d0", "d1"
        else:
            step, floor = MAX_HOURS_PER_QUERY * 3600, floor_hour
            k0, k1 = "h0", "h1"
        unit = 86400 if col == "day" else 3600
        cur, frames = floor(u0), []
        while cur <= u1:
            nxt = min(cur + step - unit, floor(u1))
            lost = in_lost_period(cur, nxt + unit)
            if lost:
                self._log(f"SKIP lost-data period {lost} for chunk {cur}-{nxt} (T9)")
                cur += step
                continue
            sql = template.format(**{k0: cur, k1: nxt})
            frames.append(self.query(sql, allow_unbounded=allow_unbounded))
            cur += step
            if cur <= u1 and not self.dry_run:
                time.sleep(PAUSE_BETWEEN_CHUNKS_S)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
