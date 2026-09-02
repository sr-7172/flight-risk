#!/usr/bin/env python3
"""03b_carrier_group_coverage.py — FIX-03 cycle-2 required action 1-2: make the
round's headline fact directly citable.

Two-sentence summary: this script reads BTS's own CARRIER_GROUP field straight
from the 36 raw T-100 international-segment CSVs (US groups {1,2,3,7} vs the
single foreign group {0}) and counts, for every year x group, how many rows
report a positive AIR_TIME / RAMP_TO_RAMP / other field, with no dependence on
FIX-01's parquet or FIX-02's carrier-nation mapping at all -- so "foreign
carriers never report airborne time in this extract" is provable from raw BTS
text, independent of any pipeline choice this project made.

Deliberately duplicates the read step FIX-01 already did (rather than reading
the parquet) so this script's numbers cannot be an artifact of FIX-01's
ingest or FIX-02's BLOCKED-NEEDS-HUMAN mapping. Reads data/raw/t100/*.csv
only, all service classes, all rows (no is_passenger / departures>0 filter --
that filter belongs to 03_coverage_audit.py's headline sample, not to this
raw-CARRIER_GROUP proof). Never modifies data/raw/.

Never modifies data/interim/ or any FIX-02 output.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from utils import setup_logger  # noqa: E402

RAW_DIR = ROOT / "data" / "raw" / "t100"
OUT_DIR = ROOT / "rounds" / "round-1-t100-panel"
GROUP_COVERAGE_CSV = OUT_DIR / "coverage_by_carrier_group.csv"
COLUMN_AVAILABILITY_CSV = OUT_DIR / "coverage_column_availability.csv"
LOG_FILE = ROOT / "logs" / "03b_carrier_group_coverage.log"

US_GROUP_CODES = {1, 2, 3, 7}  # same convention as code/02_build/02_carrier_nation.py

# Columns whose availability (share of rows with value > 0) is reported, both
# for the per-year-x-group table's *_gt0 counts and for the pooled US/foreign
# column-availability table (overseer required action 2).
NUMERIC_COLS = ["DEPARTURES_PERFORMED", "AIR_TIME", "RAMP_TO_RAMP",
                "DEPARTURES_SCHEDULED", "MAIL", "SEATS", "PASSENGERS",
                "PAYLOAD", "FREIGHT", "DISTANCE"]


def _read_raw_file(path: Path) -> pd.DataFrame:
    usecols = ["YEAR", "CARRIER_GROUP"] + NUMERIC_COLS
    df = pd.read_csv(path, usecols=usecols)
    for c in NUMERIC_COLS + ["CARRIER_GROUP", "YEAR"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def main() -> int:
    logger = setup_logger("03b_carrier_group_coverage", str(LOG_FILE))

    if not RAW_DIR.exists():
        logger.error("BLOCKED: %s not found.", RAW_DIR)
        return 1
    files = sorted(RAW_DIR.glob("*.csv")) + sorted(RAW_DIR.glob("*.zip"))
    if not files:
        logger.error("BLOCKED: no CSV/zip files under %s.", RAW_DIR)
        return 1
    if any(f.suffix == ".zip" for f in files):
        logger.error("BLOCKED: zip files present under %s but this script only "
                      "implements the plain-CSV read path used by this data drop "
                      "(FIX-00's bootstrap_manifest.csv shows 36 CSVs, no zips).", RAW_DIR)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    frames = []
    for f in files:
        df = _read_raw_file(f)
        df["source_file"] = f.name
        frames.append(df)
        logger.info("Read %s: %d rows.", f.name, len(df))
    t100 = pd.concat(frames, ignore_index=True)
    logger.info("Concatenated %d raw files: %d rows total.", len(files), len(t100))

    group_values = sorted(t100["CARRIER_GROUP"].dropna().unique())
    logger.info("CARRIER_GROUP value set observed: %s", group_values)
    unexpected_groups = [g for g in group_values if g not in (US_GROUP_CODES | {0})]
    if unexpected_groups:
        logger.error("Unexpected CARRIER_GROUP values found: %s — refusing to guess "
                      "US/foreign for them.", unexpected_groups)
        return 1

    # --- coverage_by_carrier_group.csv: one row per year x CARRIER_GROUP -------
    rows = []
    for (year, grp), d in t100.groupby(["YEAR", "CARRIER_GROUP"], dropna=False):
        row = {
            "year": int(year),
            "carrier_group": int(grp),
            "is_us_carrier_group": bool(int(grp) in US_GROUP_CODES),
            "n_rows": len(d),
            "n_dep_gt0": int((d["DEPARTURES_PERFORMED"] > 0).sum()),
            "n_air_gt0": int((d["AIR_TIME"] > 0).sum()),
            "n_air_zero": int((d["AIR_TIME"] == 0).sum()),
            "n_air_null": int(d["AIR_TIME"].isna().sum()),
            "n_ramp_gt0": int((d["RAMP_TO_RAMP"] > 0).sum()),
            "n_ramp_zero": int((d["RAMP_TO_RAMP"] == 0).sum()),
            "n_ramp_null": int(d["RAMP_TO_RAMP"].isna().sum()),
            "n_depsched_gt0": int((d["DEPARTURES_SCHEDULED"] > 0).sum()),
            "n_mail_gt0": int((d["MAIL"] > 0).sum()),
            "n_seats_gt0": int((d["SEATS"] > 0).sum()),
            "n_pax_gt0": int((d["PASSENGERS"] > 0).sum()),
            "n_dist_gt0": int((d["DISTANCE"] > 0).sum()),
            "departures": float(d["DEPARTURES_PERFORMED"].sum()),
        }
        rows.append(row)
    group_cov = pd.DataFrame(rows).sort_values(["year", "carrier_group"]).reset_index(drop=True)
    group_cov.to_csv(GROUP_COVERAGE_CSV, index=False)
    logger.info("Wrote %s: %d year x carrier_group rows.", GROUP_COVERAGE_CSV, len(group_cov))

    # --- Binding assertion: CARRIER_GROUP == 0 NEVER reports AIR_TIME/RAMP -----
    grp0 = group_cov.loc[group_cov["carrier_group"] == 0]
    bad_air = grp0.loc[grp0["n_air_gt0"] != 0]
    bad_ramp = grp0.loc[grp0["n_ramp_gt0"] != 0]
    if len(bad_air) or len(bad_ramp):
        logger.error("ASSERTION FAILED: CARRIER_GROUP==0 has nonzero AIR_TIME>0 in %d "
                      "year-rows and nonzero RAMP_TO_RAMP>0 in %d year-rows — the "
                      "'foreign carriers never report time' claim does NOT hold as "
                      "stated; see %s for the offending years.",
                      len(bad_air), len(bad_ramp), GROUP_COVERAGE_CSV)
        return 1
    assert (grp0["n_air_gt0"] == 0).all() and (grp0["n_ramp_gt0"] == 0).all()
    n_grp0_rows = int(grp0["n_rows"].sum())
    n_grp0_air_gt0 = int(grp0["n_air_gt0"].sum())
    n_grp0_air_null = int(grp0["n_air_null"].sum())
    n_grp0_ramp_null = int(grp0["n_ramp_null"].sum())
    logger.info("ASSERTION HOLDS across all %d years with CARRIER_GROUP==0 data: "
                "%d rows, %d with AIR_TIME>0, %d AIR_TIME null, %d RAMP_TO_RAMP null.",
                len(grp0), n_grp0_rows, n_grp0_air_gt0, n_grp0_air_null, n_grp0_ramp_null)

    grp7_years = sorted(int(y) for y in t100.loc[t100["CARRIER_GROUP"] == 7, "YEAR"].dropna().unique())
    logger.info("CARRIER_GROUP==7 years: %s", grp7_years)

    us = group_cov.loc[group_cov["is_us_carrier_group"]]
    us_dep_gt0 = int(us["n_dep_gt0"].sum())
    us_air_gt0_among_dep_gt0 = None  # computed below at the row level (n_dep_gt0 != n_air_gt0's own base)

    # The overseer's cited "US groups AIR_TIME>0 of departures>0" figure needs the
    # row-level AND (dep>0, air>0) count, which n_air_gt0 alone does not give (it's
    # unconditional on dep>0). Compute that intersection directly and log both.
    us_mask = t100["CARRIER_GROUP"].isin(US_GROUP_CODES)
    us_dep_gt0_rows = t100.loc[us_mask & (t100["DEPARTURES_PERFORMED"] > 0)]
    us_air_gt0_and_dep_gt0 = int((us_dep_gt0_rows["AIR_TIME"] > 0).sum())
    logger.info("US-group (CARRIER_GROUP in %s) rows with DEPARTURES_PERFORMED>0: %d; "
                "of those, AIR_TIME>0: %d (share %.6f). Independently reproduced from "
                "the 36 raw CSVs directly (not the parquet).",
                sorted(US_GROUP_CODES), len(us_dep_gt0_rows), us_air_gt0_and_dep_gt0,
                us_air_gt0_and_dep_gt0 / len(us_dep_gt0_rows) if len(us_dep_gt0_rows) else float("nan"))

    # --- coverage_column_availability.csv: share of rows > 0, US vs foreign ----
    t100["is_us_carrier_group"] = t100["CARRIER_GROUP"].isin(US_GROUP_CODES)
    avail_rows = []
    for is_us, label in ((True, "us"), (False, "foreign")):
        d = t100.loc[t100["is_us_carrier_group"] == is_us]
        for c in NUMERIC_COLS:
            avail_rows.append({
                "carrier_group_label": label,
                "column": c,
                "n_rows": len(d),
                "n_gt0": int((d[c] > 0).sum()),
                "share_gt0": float((d[c] > 0).mean()) if len(d) else float("nan"),
            })
    avail_df = pd.DataFrame(avail_rows)
    avail_df.to_csv(COLUMN_AVAILABILITY_CSV, index=False)
    logger.info("Wrote %s: %d rows (2 groups x %d columns).",
                COLUMN_AVAILABILITY_CSV, len(avail_df), len(NUMERIC_COLS))

    foreign_avail = avail_df.loc[avail_df["carrier_group_label"] == "foreign"]
    logger.info("Foreign-group column availability (share of ALL rows with value>0):\n%s",
                foreign_avail[["column", "share_gt0"]].to_string(index=False))

    # --- G1/G5 sanity ---------------------------------------------------------
    for c in ["share_gt0"]:
        bad = avail_df[c].dropna()
        bad = bad[(bad < -1e-9) | (bad > 1 + 1e-9)]
        if len(bad):
            logger.error("G5 FAIL: column %s outside [0,1] in %d rows.", c, len(bad))
            return 1
    logger.info("G5 pass: share_gt0 within [0,1] in all rows.")

    logger.info("03b_carrier_group_coverage DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
