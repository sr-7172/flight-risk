#!/usr/bin/env python3
"""01_ingest_t100.py — FIX-01: ingest and harmonize T-100 international
segment files into one clean parquet.

Two-sentence summary: this script reads every T-100 year file under
data/raw/t100/ (csv or zip), maps known BTS column-name aliases onto a
single canonical schema, and stacks all years into one parquet with zero
row drops, so every later script reads one clean panel instead of 36
slightly-different CSVs. It never filters by service class, aircraft
type, or anything else — that happens downstream; this task only proves
the raw rows made it across intact and logs any column drift it finds.

Never modifies data/raw/. Read-only over data/raw/.
"""
from __future__ import annotations

import csv
import hashlib
import io
import re
import sys
import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from utils import setup_logger  # noqa: E402

RAW = ROOT / "data" / "raw"
T100_DIR = RAW / "t100"

OUT_DIR = ROOT / "rounds" / "round-1-t100-panel"
PARQUET_PATH = ROOT / "data" / "interim" / "t100_raw.parquet"
ROWCOUNTS_CSV = OUT_DIR / "ingest_rowcounts.csv"
DRIFT_CSV = OUT_DIR / "ingest_schema_drift.csv"
VALUE_DRIFT_CSV = OUT_DIR / "ingest_value_drift.csv"
LOG_FILE = ROOT / "logs" / "01_ingest_t100.log"

# pandas' documented default NA-string list (read_csv `na_values` default).
# Hardcoded rather than imported from pandas._libs (private API) so it stays
# stable across pandas versions; restored ONLY for genuinely numeric columns.
DEFAULT_NA_VALUES = [
    "", "#N/A", "#N/A N/A", "#NA", "-1.#IND", "-1.#QNAN", "-NaN", "-nan",
    "1.#IND", "1.#QNAN", "<NA>", "N/A", "NA", "NULL", "NaN", "None",
    "n/a", "nan", "null",
]

# Service classes the round file (Part 0) documents and headline/interim
# handling covers explicitly: F = scheduled passenger, G/L/P = combi/
# freighter/charter kept with the is_passenger flag. Anything else (e.g. Q)
# is real data but undocumented in Part 0 — ingest_value_drift.csv flags it.
DOCUMENTED_SERVICE_CLASSES = {"F", "G", "L", "P"}

# --- known BTS column-name aliases, applied AFTER upper-snake normalization ---
ALIASES = {
    "CLASS": "SERVICE_CLASS",
    "RAMPTIME": "RAMP_TO_RAMP",
    "AIRTIME": "AIR_TIME",
    "DEPSCHEDULED": "DEPARTURES_SCHEDULED",
    "DEPPERFORMED": "DEPARTURES_PERFORMED",
    "UNIQUECARRIER": "UNIQUE_CARRIER",
}

REQUIRED = [
    "YEAR", "MONTH", "UNIQUE_CARRIER", "CARRIER_NAME", "ORIGIN", "ORIGIN_COUNTRY",
    "DEST", "DEST_COUNTRY", "AIRCRAFT_TYPE", "AIRCRAFT_CONFIG", "SERVICE_CLASS",
    "DEPARTURES_SCHEDULED", "DEPARTURES_PERFORMED", "SEATS", "PASSENGERS",
    "DISTANCE", "RAMP_TO_RAMP", "AIR_TIME",
]

# Columns that must be read/kept as strings/categoricals — never coerced to
# numbers, never allowed to lose leading characters. Matched on the MAPPED
# (post-alias) name.
STR_TARGET_COLS = {
    "UNIQUE_CARRIER", "UNIQUE_CARRIER_NAME", "UNIQUE_CARRIER_ENTITY", "REGION",
    "CARRIER", "CARRIER_NAME",
    "ORIGIN", "ORIGIN_CITY_NAME", "ORIGIN_COUNTRY", "ORIGIN_COUNTRY_NAME",
    "DEST", "DEST_CITY_NAME", "DEST_COUNTRY", "DEST_COUNTRY_NAME",
    "SERVICE_CLASS", "AIRCRAFT_TYPE", "AIRCRAFT_CONFIG",
}

YEAR_RE = re.compile(r"(19|20)\d{2}")


def normalize(col: str) -> str:
    return col.strip().upper().replace(" ", "_")


def discover_files() -> list[Path]:
    if not T100_DIR.is_dir():
        return []
    files = list(T100_DIR.glob("*.csv")) + list(T100_DIR.glob("*.zip"))
    # Drop obvious non-data artifacts (hidden files, fetch script, macOS cruft)
    files = [f for f in files if not f.name.startswith(".") and f.suffix.lower() in (".csv", ".zip")]

    def sort_key(p: Path):
        m = YEAR_RE.search(p.name)
        return (int(m.group(0)) if m else 9999, p.name)

    return sorted(files, key=sort_key)


def filename_year(path: Path) -> int | None:
    m = YEAR_RE.search(path.name)
    return int(m.group(0)) if m else None


def read_header_and_hash(path: Path) -> tuple[list[str], str]:
    """Return (raw header columns, md5 of the raw header line) for csv or zip."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as zf:
            inner = [n for n in zf.namelist() if n.lower().endswith(".csv")]
            if not inner:
                return [], ""
            with zf.open(inner[0]) as fh:
                header_line = io.TextIOWrapper(fh, encoding="utf-8", errors="replace").readline()
    else:
        with open(path, "r", newline="", encoding="utf-8", errors="replace") as f:
            header_line = f.readline()
    cols = next(csv.reader([header_line]))
    h = hashlib.md5(header_line.encode("utf-8", errors="replace")).hexdigest()
    return cols, h


def build_dtype_map(raw_cols: list[str], rename_map: dict[str, str]) -> dict[str, type]:
    dtype_map = {}
    for raw_col in raw_cols:
        mapped = rename_map.get(raw_col, raw_col)
        if mapped in STR_TARGET_COLS:
            dtype_map[raw_col] = str
    return dtype_map


def build_na_map(raw_cols: list[str], rename_map: dict[str, str]) -> dict[str, list[str]]:
    """Per-column na_values: STR_TARGET_COLS treat ONLY "" as missing (so an
    observed code like 'NA' — North American Airlines, or the country code
    for Namibia — is never conflated with a genuinely blank cell); every
    other (numeric/ID) column keeps pandas' full default NA-string list.
    Must be paired with keep_default_na=False so pandas does not ALSO apply
    its global default list on top of this per-column map.
    """
    na_map = {}
    for raw_col in raw_cols:
        mapped = rename_map.get(raw_col, raw_col)
        na_map[raw_col] = [""] if mapped in STR_TARGET_COLS else list(DEFAULT_NA_VALUES)
    return na_map


def read_one(path: Path, logger) -> tuple[pd.DataFrame | None, dict]:
    """Read one source file, normalize+alias-map columns, add provenance.

    Returns (df or None, diagnostics dict). df is None only if the file is
    unreadable or missing a required column after mapping (BLOCKED for
    that file, per FIX-01 step 2).
    """
    rel = str(path.relative_to(ROOT))
    diag = {
        "source_file": rel,
        "rows_read": 0,
        "rows_written": 0,
        "rows_dropped": 0,
        "years_covered": "",
        "n_columns_raw": 0,
        "missing_required_columns": "",
        "blocked": False,
        "note": "",
    }

    raw_cols, header_hash = read_header_and_hash(path)
    if not raw_cols:
        diag["blocked"] = True
        diag["note"] = "could not read header (empty/unreadable file)"
        logger.error("%s: %s", rel, diag["note"])
        return None, diag
    diag["n_columns_raw"] = len(raw_cols)

    normalized = [normalize(c) for c in raw_cols]
    mapped = [ALIASES.get(n, n) for n in normalized]
    rename_map = dict(zip(raw_cols, mapped))

    missing = [c for c in REQUIRED if c not in mapped]
    if missing:
        diag["blocked"] = True
        diag["missing_required_columns"] = ";".join(missing)
        diag["note"] = f"missing required columns after alias mapping: {missing}"
        logger.error("%s BLOCKED: %s", rel, diag["note"])
        return None, diag

    dtype_map = build_dtype_map(raw_cols, rename_map)
    na_map = build_na_map(raw_cols, rename_map)
    try:
        df = pd.read_csv(path, dtype=dtype_map, keep_default_na=False,
                          na_values=na_map, low_memory=False)
    except Exception as exc:  # noqa: BLE001
        diag["blocked"] = True
        diag["note"] = f"read_csv failed: {exc}"
        logger.error("%s BLOCKED: %s", rel, diag["note"])
        return None, diag

    diag["rows_read"] = len(df)
    df = df.rename(columns=rename_map)

    # --- standing guard: prove the na_values scheme above actually matters,
    # so a future data drop cannot silently regress into the keep_default_na
    # =True bug (observed codes like 'NA' getting swallowed as null). Do a
    # cheap second read of ONLY the code/string columns under the naive
    # (buggy) default-NA behavior and log any column whose null count would
    # have differed.
    str_raw_cols = [rc for rc in raw_cols if rename_map.get(rc, rc) in STR_TARGET_COLS]
    if str_raw_cols:
        naive = pd.read_csv(path, usecols=str_raw_cols, dtype=str,
                             keep_default_na=True, low_memory=False)
        naive = naive.rename(columns=rename_map)
        for col in naive.columns:
            naive_null = int(naive[col].isna().sum())
            correct_null = int(df[col].isna().sum())
            if naive_null != correct_null:
                logger.warning(
                    "%s: NA-string guard — column %s null count under naive "
                    "keep_default_na=True would be %d vs %d under the correct "
                    "empty-string-only scheme (delta %d values would have been "
                    "silently swallowed as missing)",
                    rel, col, naive_null, correct_null, naive_null - correct_null)
        del naive

    # Duplicate-named columns after mapping would silently merge — guard it.
    dup = df.columns[df.columns.duplicated()].tolist()
    if dup:
        diag["blocked"] = True
        diag["note"] = f"duplicate columns after alias mapping: {dup}"
        logger.error("%s BLOCKED: %s", rel, diag["note"])
        return None, diag

    # Cross-check filename year against data YEAR (log only, never blocks).
    fy = filename_year(path)
    data_years = sorted(pd.unique(pd.to_numeric(df["YEAR"], errors="coerce").dropna()).astype(int).tolist())
    diag["years_covered"] = ";".join(str(y) for y in data_years)
    if fy is not None and data_years and (len(data_years) != 1 or data_years[0] != fy):
        logger.warning("%s: filename year=%s but YEAR column has %s", rel, fy, data_years)

    # --- provenance columns ---
    df["source_file"] = rel
    df["year"] = pd.to_numeric(df["YEAR"], errors="coerce").astype("Int64")
    df["month"] = pd.to_numeric(df["MONTH"], errors="coerce").astype("Int64")
    df["service_class"] = df["SERVICE_CLASS"]
    # is_passenger flags ONLY SERVICE_CLASS == 'F' (scheduled passenger
    # service, the headline sample). It is not a full passenger-carrying
    # indicator: class L (passenger charter) and combi classes G/P can also
    # carry passengers but are excluded from this flag by design — headline
    # vs. non-headline service-class handling is a downstream decision
    # (Part 0), not decided by this ingest task.
    df["is_passenger"] = df["service_class"] == "F"

    diag["rows_written"] = len(df)
    diag["rows_dropped"] = diag["rows_read"] - diag["rows_written"]
    diag["_header_hash"] = header_hash
    diag["_raw_cols"] = raw_cols
    diag["_mapped_cols"] = mapped
    diag["_fy"] = fy
    return df, diag


def main() -> int:
    logger = setup_logger("01_ingest_t100", str(LOG_FILE))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    PARQUET_PATH.parent.mkdir(parents=True, exist_ok=True)

    files = discover_files()
    if not files:
        logger.error(
            "No readable T-100 files found under %s (looked for *.csv and *.zip). "
            "BLOCKED — see rounds/round-1-t100-panel/bootstrap_manifest.csv (FIX-00) "
            "for what was expected to be present.", T100_DIR)
        return 1

    logger.info("Found %d T-100 source file(s) under %s", len(files), T100_DIR)

    frames: list[pd.DataFrame] = []
    rowcount_rows: list[dict] = []
    drift_rows: list[dict] = []
    any_blocked = False

    for path in files:
        df, diag = read_one(path, logger)
        rowcount_rows.append({k: v for k, v in diag.items() if not k.startswith("_")})

        drift_row = {
            "year": diag.get("_fy", ""),
            "source_file": diag["source_file"],
            "raw_header_md5": diag.get("_header_hash", ""),
        }
        mapped_cols = diag.get("_mapped_cols", [])
        for req in REQUIRED:
            drift_row[req] = req in mapped_cols
        extra = sorted(set(mapped_cols) - set(REQUIRED)) if mapped_cols else []
        drift_row["extra_columns"] = ";".join(extra)
        drift_rows.append(drift_row)

        if df is None:
            any_blocked = True
            continue
        frames.append(df)
        logger.info("%s: read=%d written=%d years=%s", diag["source_file"],
                     diag["rows_read"], diag["rows_written"], diag["years_covered"])

    if not frames:
        logger.error("Every source file was BLOCKED — nothing to write. See ingest_rowcounts.csv.")
        _write_csv(ROWCOUNTS_CSV, rowcount_rows)
        _write_csv(DRIFT_CSV, drift_rows)
        return 1

    logger.info("Concatenating %d frame(s)...", len(frames))
    full = pd.concat(frames, ignore_index=True, sort=False)
    del frames

    total_read = sum(r["rows_read"] for r in rowcount_rows)
    total_written = sum(r["rows_written"] for r in rowcount_rows)
    total_dropped = sum(r["rows_dropped"] for r in rowcount_rows)

    logger.info("Total rows_read=%d rows_written=%d rows_dropped=%d parquet_rows=%d",
                total_read, total_written, total_dropped, len(full))

    if total_dropped != 0:
        logger.error("Non-zero rows_dropped (%d) — FIX-01 requires zero drops. BLOCKED.", total_dropped)
        any_blocked = True

    if len(full) != total_written:
        logger.error("Parquet row count (%d) != sum(rows_written) (%d). BLOCKED.",
                      len(full), total_written)
        any_blocked = True

    # --- value-level correctness assertions (in code, not just observed) ---
    # These pin down the reviewer-caught NA/blank conflation bug so a
    # regression trips the run rather than passing silently.
    assertions = [
        ("UNIQUE_CARRIER == 'NA'", int((full["UNIQUE_CARRIER"] == "NA").sum()), 8612),
        ("CARRIER == 'NA'", int((full["CARRIER"] == "NA").sum()), 7731),
        ("ORIGIN_COUNTRY == 'NA'", int((full["ORIGIN_COUNTRY"] == "NA").sum()), 3),
        ("DEST_COUNTRY == 'NA'", int((full["DEST_COUNTRY"] == "NA").sum()), 3),
        ("UNIQUE_CARRIER.isna()", int(full["UNIQUE_CARRIER"].isna().sum()), 2407),
        ("CARRIER.isna()", int(full["CARRIER"].isna().sum()), 0),
        ("ORIGIN_COUNTRY.isna()", int(full["ORIGIN_COUNTRY"].isna().sum()), 38),
        ("DEST_COUNTRY.isna()", int(full["DEST_COUNTRY"].isna().sum()), 41),
    ]
    for label, actual, expected in assertions:
        status = "OK" if actual == expected else "MISMATCH"
        logger.info("assertion %s: actual=%d expected=%d [%s]", label, actual, expected, status)
        if actual != expected:
            any_blocked = True
    if any_blocked:
        logger.error("One or more value-level assertions failed — BLOCKED before parquet write "
                      "would still occur below for inspection, but the run is marked failed.")

    full.to_parquet(PARQUET_PATH, index=False, engine="pyarrow")
    size_mb = PARQUET_PATH.stat().st_size / (1024 * 1024)
    logger.info("Wrote %s: %d rows, %d cols, %.1f MB", PARQUET_PATH, len(full), full.shape[1], size_mb)

    _write_csv(ROWCOUNTS_CSV, rowcount_rows)
    _write_csv(DRIFT_CSV, drift_rows)
    logger.info("Wrote %s (%d rows)", ROWCOUNTS_CSV, len(rowcount_rows))
    logger.info("Wrote %s (%d rows)", DRIFT_CSV, len(drift_rows))

    # --- ingest_value_drift.csv: one row per (year, SERVICE_CLASS) ---
    vd = (full.groupby(["year", "service_class"], dropna=False)
              .agg(n_rows=("service_class", "size"),
                   departures_performed_sum=("DEPARTURES_PERFORMED", "sum"))
              .reset_index())
    vd["documented_in_round_file"] = vd["service_class"].isin(DOCUMENTED_SERVICE_CLASSES)
    vd = vd.sort_values(["year", "service_class"]).reset_index(drop=True)
    vd.to_csv(VALUE_DRIFT_CSV, index=False)
    logger.info("Wrote %s (%d rows)", VALUE_DRIFT_CSV, len(vd))
    undocumented = vd[~vd["documented_in_round_file"]]
    if len(undocumented):
        logger.warning("SERVICE_CLASS values outside Part 0's documented {F,G,L,P} set found: %s "
                        "(see %s)", sorted(undocumented["service_class"].unique().tolist()), VALUE_DRIFT_CSV)

    # --- reporting aids for the human/reviewer ---
    ym = full[["year", "month"]].dropna().astype(int)
    if len(ym):
        earliest = ym.sort_values(["year", "month"]).iloc[0]
        latest = ym.sort_values(["year", "month"]).iloc[-1]
        logger.info("Coverage: earliest=(%d,%d) latest=(%d,%d)",
                    earliest["year"], earliest["month"], latest["year"], latest["month"])
    sc_counts = full["service_class"].value_counts(dropna=False)
    logger.info("SERVICE_CLASS distribution:\n%s", sc_counts.to_string())

    if any_blocked:
        logger.error("FIX-01 completed with one or more file-level or reconciliation BLOCKs "
                      "(see log lines above / ingest_rowcounts.csv notes).")
        return 1

    logger.info("FIX-01 DONE.")
    return 0


def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        Path(path).write_text("")
        return
    fieldnames = list(rows[0].keys())
    for r in rows[1:]:
        for k in r.keys():
            if k not in fieldnames:
                fieldnames.append(k)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


if __name__ == "__main__":
    sys.exit(main())
