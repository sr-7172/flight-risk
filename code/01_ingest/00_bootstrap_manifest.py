#!/usr/bin/env python3
"""00_bootstrap_manifest.py — FIX-00: verify data/raw/ is present and
usable, or produce a precise BLOCKED record.

Two-sentence summary: this script checks that every file the T-100 panel
needs (36 year CSVs, the OpenFlights airline lookup, the ban-nations event
dictionary) is on disk and has the columns downstream steps rely on. It
never downloads anything itself except through the pinned, committed
`data/raw/t100/fetch_t100.sh` (only if `data/raw/t100/` is empty), and it
writes one manifest row per file so a human can see present/fetched/
header-verified/sha256 at a glance.

Never modifies data/raw/ or fetch_t100.sh. Read-only over data/raw/.
"""
from __future__ import annotations

import csv
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from utils import setup_logger  # noqa: E402

RAW = ROOT / "data" / "raw"
T100_DIR = RAW / "t100"
LOOKUPS_DIR = RAW / "lookups"
EVENTS_DIR = RAW / "events"
FETCH_SCRIPT = T100_DIR / "fetch_t100.sh"

OUT_DIR = ROOT / "rounds" / "round-1-t100-panel"
OUT_CSV = OUT_DIR / "bootstrap_manifest.csv"
LOG_FILE = ROOT / "logs" / "00_bootstrap_manifest.log"

T100_REQUIRED_COLS = {"AIR_TIME", "DEPARTURES_PERFORMED"}
LOOKUP_REQUIRED_COLS = {"airline_id", "name", "alias", "iata", "icao",
                         "callsign", "country", "active"}
EVENTS_REQUIRED_COLS = {"nation_iso2", "status", "effective_date", "notes"}

FIELDNAMES = ["path", "kind", "present_before", "fetched", "size_bytes",
              "header_verified", "sha256", "note"]


def sha256_of(path: Path) -> str:
    """Stream sha256 in 1 MiB chunks so a ~15-30MB CSV never loads whole."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_header_cols(path: Path) -> list[str]:
    with open(path, "r", newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.reader(f)
        try:
            return next(reader)
        except StopIteration:
            return []


def manifest_row(path: Path, kind: str, present_before: bool, fetched: bool,
                  required_cols: set[str] | None, note_if_missing: str) -> dict:
    row = {
        "path": str(path.relative_to(ROOT)),
        "kind": kind,
        "present_before": present_before,
        "fetched": fetched,
        "size_bytes": "",
        "header_verified": False,
        "sha256": "",
        "note": "",
    }
    if not present_before and not fetched:
        row["note"] = note_if_missing
        return row

    row["size_bytes"] = path.stat().st_size
    row["sha256"] = sha256_of(path)
    if required_cols is None:
        row["header_verified"] = False
        row["note"] = "no required-column set defined for this kind"
        return row

    header_cols = set(read_header_cols(path))
    missing = required_cols - header_cols
    if missing:
        row["header_verified"] = False
        row["note"] = f"missing expected header columns: {sorted(missing)}"
    else:
        row["header_verified"] = True
        row["note"] = f"verified columns present: {sorted(required_cols)}"
    return row


def main() -> int:
    logger = setup_logger("00_bootstrap_manifest", str(LOG_FILE))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    blocked = False
    blocked_notes: list[str] = []

    # --- Step 1/2: T-100 year files ------------------------------------
    t100_files = sorted(T100_DIR.glob("T_T100I_SEGMENT_ALL_CARRIER_*.csv")) if T100_DIR.is_dir() else []
    if t100_files:
        logger.info("data/raw/t100/ has %d CSV(s) already present — skipping fetch (step 1 applies).",
                     len(t100_files))
        for fp in t100_files:
            row = manifest_row(fp, "t100", present_before=True, fetched=False,
                                required_cols=T100_REQUIRED_COLS,
                                note_if_missing="unexpected: listed but not found")
            rows.append(row)
            if not row["header_verified"]:
                logger.warning("HEADER CHECK FAILED for %s: %s", row["path"], row["note"])
    else:
        logger.warning("data/raw/t100/ has no year CSVs — step 2 applies.")
        if FETCH_SCRIPT.exists():
            logger.info("Running pinned fetch script exactly as committed: %s", FETCH_SCRIPT)
            proc = subprocess.run(["bash", str(FETCH_SCRIPT)], cwd=str(ROOT),
                                   capture_output=True, text=True)
            if proc.returncode != 0:
                err_excerpt = (proc.stderr or proc.stdout or "")[:400]
                logger.error("fetch_t100.sh exited %d. First 400 bytes of error: %s",
                              proc.returncode, err_excerpt)
                blocked = True
                blocked_notes.append(
                    f"fetch_t100.sh exited {proc.returncode}; error excerpt: {err_excerpt!r}")
                rows.append({
                    "path": "data/raw/t100/fetch_t100.sh",
                    "kind": "t100",
                    "present_before": False,
                    "fetched": False,
                    "size_bytes": "",
                    "header_verified": False,
                    "sha256": "",
                    "note": f"fetch failed, exit {proc.returncode}: {err_excerpt!r}",
                })
            else:
                # Re-scan for whatever the script produced.
                fetched_files = sorted(T100_DIR.glob("T_T100I_SEGMENT_ALL_CARRIER_*.csv"))
                for fp in fetched_files:
                    row = manifest_row(fp, "t100", present_before=False, fetched=True,
                                        required_cols=T100_REQUIRED_COLS,
                                        note_if_missing="unexpected: listed but not found")
                    rows.append(row)
                if not fetched_files:
                    blocked = True
                    blocked_notes.append("fetch_t100.sh exited 0 but produced no year CSVs")
        else:
            logger.error("No T-100 CSVs present AND data/raw/t100/fetch_t100.sh does not exist. "
                          "BLOCKED per FIX-00 step 2 — nothing to fetch, no fetch script to run.")
            blocked = True
            blocked_notes.append(
                "data/raw/t100/ is empty and fetch_t100.sh is not present; "
                "no bootstrap path available")
            rows.append({
                "path": "data/raw/t100/",
                "kind": "t100",
                "present_before": False,
                "fetched": False,
                "size_bytes": "",
                "header_verified": False,
                "sha256": "",
                "note": "no year CSVs and no fetch_t100.sh to run",
            })

    # --- Step 3: lookups/airlines.csv -----------------------------------
    airlines_path = LOOKUPS_DIR / "airlines.csv"
    row = manifest_row(
        airlines_path, "lookup", present_before=airlines_path.exists(), fetched=False,
        required_cols=LOOKUP_REQUIRED_COLS,
        note_if_missing="data/raw/lookups/airlines.csv absent — FIX-02 will BLOCK or use stated fallback")
    rows.append(row)
    if not airlines_path.exists():
        logger.warning("lookups/airlines.csv missing.")

    # --- Step 3: events/ban_nations_2022.csv -----------------------------
    ban_path = EVENTS_DIR / "ban_nations_2022.csv"
    row = manifest_row(
        ban_path, "event", present_before=ban_path.exists(), fetched=False,
        required_cols=EVENTS_REQUIRED_COLS,
        note_if_missing="data/raw/events/ban_nations_2022.csv absent — NEW-06 uses stated fallback")
    rows.append(row)
    if not ban_path.exists():
        logger.warning("events/ban_nations_2022.csv missing.")

    # --- Write manifest ---------------------------------------------------
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)
    logger.info("Wrote %d rows to %s", len(rows), OUT_CSV)

    n_true = sum(1 for r in rows if r["header_verified"] is True)
    n_false = sum(1 for r in rows if r["header_verified"] is False)
    logger.info("header_verified: %d True, %d False (of %d rows)", n_true, n_false, len(rows))

    if blocked:
        logger.error("FIX-00 BLOCKED: %s", "; ".join(blocked_notes))
        return 1

    logger.info("FIX-00 DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
