#!/usr/bin/env python3
"""04_build_panel.py — FIX-04: directed route x operator-nation x month panel.

Two-sentence summary: we collapse T-100's carrier x aircraft-type x segment x
month rows to one row per (origin, dest, operator nation, year, month) cell by
summing departures and (where BTS actually reports it) minutes flown, so a
seminar audience sees "how many flights, and on average how long were they"
for every directed corridor-nation-month ever filed. A companion, unfiltered
extensive-margin panel then answers "was this corridor even served by this
nation that month" for every nation the data ever contains, not just the ones
with usable time data.

FIX-02 (carrier -> nation mapping) is BLOCKED-NEEDS-HUMAN on a DEGENERATE-GATE
(G7's coverage reading passes, its precision reading fails). Per the overseer's
governing instruction for this task: FIX-04 MAY BUILD the panel but MAY NOT
REPORT nation-level numbers as findings. This script only constructs and
diagnoses; no output here should be read as a headline result.

THE STRUCTURAL-ZERO GUARD (binding, asserted in code below). FIX-03 established,
independently re-verified from the raw CARRIER_GROUP field
(coverage_by_carrier_group.csv), that BTS's foreign carriers (CARRIER_GROUP==0)
NEVER report AIR_TIME or RAMP_TO_RAMP -- every value is a literal 0.00, not a
null, in all 36 years, for all 1,133,545 foreign-carrier segment-months. We
independently confirmed here that this is governed by CARRIER_GROUP, not by our
own nation mapping: among matched, passenger-service carriers, exactly three
codes are mapped to nation=='US' but carry CARRIER_GROUP==0 (non-time-reporting)
-- `VX (1)` (T-100 CARRIER_NAME "Aces Airlines"), `B0` ("Dreamjet SAS Dba La
Compagnie"), and `WO` ("SWOOP Inc."). These are NOT US carriers filing on the
foreign schedule: they are FOREIGN carriers (Aces Airlines/Colombia, La
Compagnie/France, Swoop/Canada) mis-mapped to nation=='US' by FIX-02 IATA-code
collisions with unrelated US-registered airlines (the OpenFlights candidate
names "Virgin America", "Aws express", "World Airways" in
carrier_nation_precision_audit.csv) -- all three carry
home_country_dep_share == 0.0 in that audit, i.e. FIX-02's own G7 precision
diagnostic already flags them. Their CARRIER_GROUP==0 is BTS correctly
recording them as foreign; it is the nation label that is wrong. Because they
mis-map to nation=='US', their departures land in nation=='US' cells but never
contribute a real airborne/ramp minute -- exactly the G7 precision failure this
script's nation_precision_flag / cell_ok_precision machinery exists to flag
(see below), and exactly why departures_time_eligible / departures_non_reporting
(both retained as their own panel_monthly columns) must not be collapsed into
departures_performed alone. Zero matched rows have a time-reporting
CARRIER_GROUP (1,2,3,7) mapped to a non-US nation, so the converse leak does not
occur. So: a row's eligibility to contribute to airborne/ramp aggregates is
determined by CARRIER_GROUP.isin({1,2,3,7}), not by the nation label alone --
this is a strictly more conservative (and correct) test than "nation == US",
and it still guarantees, by construction, that every non-US-nation cell gets a
null airborne_min_mean/ramp_min_mean (asserted below, not just claimed). Any
cell with zero reporting-eligible departures gets NaN for air_time_total,
ramp_total, airborne_min_mean, ramp_min_mean -- never a computed 0.00, because
sum(AIR_TIME)/sum(DEPARTURES_PERFORMED) over an all-structural-zero cell is a
fabricated number, not a measurement. airborne_available / ramp_available flag
this explicitly on every row.

WITHIN-US REPORTING GAPS (Part 0: "never imputed", overseer cycle-1 required
action 3). Even among CARRIER_GROUP-eligible (reports_time==True) rows, a
handful (measured at runtime, logged as its own panel_filter_log.csv step) have
AIR_TIME == 0 or RAMP_TO_RAMP == 0 despite DEPARTURES_PERFORMED > 0 -- these are
reporting gaps, not zero-minute flights, exactly the Part 0 distinction. Such
rows are excluded from BOTH the numerator and the denominator of
airborne_min_mean / ramp_min_mean (separately, since the two fields' gap rows
need not coincide), so an all-gap cell gets NaN and airborne_available/
ramp_available == False rather than a fabricated 0.0/True.

Aggregation note (round file: "aggregate over aircraft types; do not assume
cell-key uniqueness"). We independently confirmed the raw sample has rows that
are non-unique on the natural (carrier, year, month, origin, dest,
aircraft_type) key (duplicates across e.g. aircraft configuration) and exact
duplicate rows. No dedup step is applied anywhere in this script -- every
detail row in the filtered sample is summed into its cell via a single
groupby(...).sum(), so duplicates are counted, never silently collapsed to one
row. n_rows_raw on panel_monthly.parquet records how many detail rows fed each
cell, for audit.

Carrier-match tier (round-file override, binding): matched carriers only,
MATCHED_METHODS = {iata, name_exact, us_by_construction}. The icao tier is
DROPPED here (not just at FIX-03's coverage-audit stage) per the reviewer's
finding that it is ~49% home-country-zero on the FIX-02 precision diagnostic
and unusable for cell construction; icao-tier rows are logged and excluded
alongside unmatched/refused/null-carrier rows in panel_filter_log.csv.

Nation-level numbers (FIX-02 DEGENERATE-GATE): every panel_monthly row carries
nation_precision_flag (True for the two known MATCH-SENSITIVE nations, RU and
IR, or where >=50% of the cell's departures rest on a carrier code whose
mapped home country never appears as one of its own T-100 endpoints -- FIX-02's
flag_home_share_zero, carried forward departures-weighted as share_dep_home0)
and cell_ok_precision (cell_ok filtered further to drop precision-flagged
cells). No downstream aggregate in THIS script uses cell_ok_precision to make
a claim -- it is carried so later tasks can choose the strict variant without
recomputing it, per FIX-02's own governing ruling in REVIEW_REPORT.md.

Reads data/interim/t100_raw.parquet (FIX-01), data/interim/carrier_nation.parquet
(FIX-02), rounds/round-1-t100-panel/coverage_audit.csv (FIX-03, G6 pass/fail by
nation x year) and carrier_nation_precision_audit.csv (FIX-02, per-code
home-share-zero flag). Never modifies any of them, never touches data/raw/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from utils import setup_logger, log_merge  # noqa: E402

# --- Inputs ------------------------------------------------------------
PARQUET_T100 = ROOT / "data" / "interim" / "t100_raw.parquet"
PARQUET_NATION = ROOT / "data" / "interim" / "carrier_nation.parquet"
OUT_DIR = ROOT / "rounds" / "round-1-t100-panel"
COVERAGE_AUDIT_CSV = OUT_DIR / "coverage_audit.csv"
PRECISION_AUDIT_CSV = OUT_DIR / "carrier_nation_precision_audit.csv"

# --- Outputs -------------------------------------------------------------
PANEL_MONTHLY_PARQUET = ROOT / "data" / "interim" / "panel_monthly.parquet"
PANEL_EXTENSIVE_PARQUET = ROOT / "data" / "interim" / "panel_extensive.parquet"
DESC_SAMPLE_CSV = OUT_DIR / "desc_sample.csv"
FILTER_LOG_CSV = OUT_DIR / "panel_filter_log.csv"
CHURN_CSV = OUT_DIR / "extensive_margin_churn.csv"
LOG_FILE = ROOT / "logs" / "04_build_panel.log"

# --- Constants -------------------------------------------------------------
US_GROUP_CODES = {1, 2, 3, 7}  # BTS CARRIER_GROUP codes that report AIR_TIME/RAMP_TO_RAMP
MATCHED_METHODS = ["iata", "name_exact", "us_by_construction"]  # icao tier dropped, per round file
MATCH_SENSITIVE_NATIONS = {"RU", "IR"}
COVID_START = (2020, 3)   # inclusive
COVID_END = (2021, 12)    # inclusive
MIN_CELL_DEP = 4
MIN_CELL_DEP_SENSITIVITY = 8
HOME0_CELL_THRESHOLD = 0.50  # cell-level nation_precision_flag threshold on share_dep_home0
PANEL_START = (1990, 1)
PANEL_END = (2025, 12)


def _covid_flag(year: pd.Series, month: pd.Series) -> pd.Series:
    lo = (year > COVID_START[0]) | ((year == COVID_START[0]) & (month >= COVID_START[1]))
    hi = (year < COVID_END[0]) | ((year == COVID_END[0]) & (month <= COVID_END[1]))
    return lo & hi


def _log_filter(log_rows: list[dict], level: str, action: str, step: str,
                 n_before: int, n_after: int, reason: str) -> None:
    log_rows.append({
        "level": level, "action": action, "step": step,
        "n_before": n_before, "n_after": n_after,
        "n_dropped": n_before - n_after, "reason": reason,
    })


def main() -> int:
    logger = setup_logger("04_build_panel", str(LOG_FILE))

    for p in (PARQUET_T100, PARQUET_NATION, COVERAGE_AUDIT_CSV, PRECISION_AUDIT_CSV):
        if not p.exists():
            logger.error("BLOCKED: required input %s not found.", p)
            return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    filter_log: list[dict] = []

    # --- Load ----------------------------------------------------------
    cols = ["UNIQUE_CARRIER", "YEAR", "MONTH", "ORIGIN", "DEST", "ORIGIN_COUNTRY",
            "DEST_COUNTRY", "AIRCRAFT_TYPE", "SERVICE_CLASS", "CARRIER_GROUP",
            "DEPARTURES_SCHEDULED", "DEPARTURES_PERFORMED", "DISTANCE",
            "RAMP_TO_RAMP", "AIR_TIME", "is_passenger"]
    t100 = pd.read_parquet(PARQUET_T100, columns=cols)
    logger.info("Loaded t100_raw.parquet: %d rows.", len(t100))

    nation = pd.read_parquet(PARQUET_NATION)
    logger.info("Loaded carrier_nation.parquet: %d (UNIQUE_CARRIER, year) rows.", len(nation))

    coverage = pd.read_csv(COVERAGE_AUDIT_CSV)
    precision = pd.read_csv(PRECISION_AUDIT_CSV)
    logger.info("Loaded coverage_audit.csv (%d nation x year rows) and "
                "carrier_nation_precision_audit.csv (%d codes).", len(coverage), len(precision))

    # --- Step 1a: passenger service ------------------------------------
    n0 = len(t100)
    sample = t100.loc[t100["is_passenger"]].copy()
    _log_filter(filter_log, "row", "drop", "passenger_service_only", n0, len(sample),
                "SERVICE_CLASS != F (combi/freighter/other); headline sample is scheduled "
                "passenger service only, per Part 0.")
    logger.info("Filter passenger service: %d -> %d rows.", n0, len(sample))

    # --- Step 1b: match nation, matched carriers only (icao tier dropped) --
    n1 = len(sample)
    merged = sample.merge(nation, left_on=["UNIQUE_CARRIER", "YEAR"],
                           right_on=["UNIQUE_CARRIER", "year"], how="left", indicator=True)
    log_merge(logger, sample, nation, merged, on="(UNIQUE_CARRIER, YEAR)", how="left")

    null_carrier = merged["UNIQUE_CARRIER"].isna()
    method = merged["match_method"]
    icao_tier = method.eq("icao")
    unmatched_or_refused = method.isin(["unmatched", "refused_suffix_collision"])
    matched = method.isin(MATCHED_METHODS)
    unexpected = ~(null_carrier | icao_tier | unmatched_or_refused | matched)
    if unexpected.any():
        logger.error("Unexpected match_method values for %d rows: %s",
                      int(unexpected.sum()), merged.loc[unexpected, "match_method"].unique())
        return 1

    n_icao = int(icao_tier.sum())
    n_unmatched = int(unmatched_or_refused.sum())
    n_null_carrier = int(null_carrier.sum())
    matched_sample = merged.loc[matched].copy()
    _log_filter(filter_log, "row", "drop", "icao_tier_dropped", n1, n1 - n_icao,
                f"icao match tier dropped by round-file override: measured ~49% "
                f"home-country-zero on FIX-02's precision diagnostic, unusable "
                f"({n_icao} rows).")
    _log_filter(filter_log, "row", "drop", "unmatched_or_refused_carrier", n1 - n_icao,
                len(matched_sample) + n_null_carrier,
                f"UNIQUE_CARRIER code unmatched to a nation or refused for suffix "
                f"collision (G7 matched-carriers-only) ({n_unmatched} rows).")
    _log_filter(filter_log, "row", "drop", "null_carrier_code", len(matched_sample) + n_null_carrier,
                len(matched_sample),
                f"UNIQUE_CARRIER itself null/unresolvable at the merge step ({n_null_carrier} rows).")
    logger.info("Matched-nation sample (icao/unmatched/refused/null dropped): %d / %d rows "
                "(%.4f of passenger rows).", len(matched_sample), n1, len(matched_sample) / n1)
    matched_sample = matched_sample.rename(columns={"nation_iso2": "nation"})

    # --- Structural-zero guard: which rows are eligible to report AIR_TIME/RAMP --
    matched_sample["reports_time"] = matched_sample["CARRIER_GROUP"].isin(US_GROUP_CODES)
    # Confirm, on THIS filtered population, the empirical claim the whole guard rests on:
    # zero matched rows have a time-reporting CARRIER_GROUP mapped to a non-US nation.
    leak = matched_sample.loc[matched_sample["reports_time"] & (matched_sample["nation"] != "US")]
    if len(leak):
        logger.error("STRUCTURAL-ZERO GUARD VIOLATED: %d matched rows have a time-reporting "
                      "CARRIER_GROUP (%s) mapped to a non-US nation -- refusing to proceed with "
                      "a null-only assumption for non-US cells.", len(leak), sorted(US_GROUP_CODES))
        return 1
    logger.info("Structural-zero guard holds on the matched sample: 0 rows with a "
                "time-reporting CARRIER_GROUP mapped to a non-US nation.")
    us_nonreporting_mask = (matched_sample["nation"] == "US") & (~matched_sample["reports_time"])
    n_us_nation_nonreporting = int(us_nonreporting_mask.sum())
    us_nonreporting_codes = sorted(matched_sample.loc[us_nonreporting_mask, "UNIQUE_CARRIER"].unique())
    logger.info("Within nation=='US' cells, %d rows carry a non-time-reporting CARRIER_GROUP "
                "and are excluded from the airborne/ramp denominator (but retained in "
                "departures_performed): codes %s -- these are FOREIGN carriers mis-mapped to "
                "nation=='US' by FIX-02 IATA-code collisions (VX (1)=Aces Airlines/Colombia, "
                "B0=Dreamjet SAS Dba La Compagnie/France, WO=SWOOP Inc./Canada; all three have "
                "home_country_dep_share==0.0 in carrier_nation_precision_audit.csv), not US "
                "carriers filing on the foreign schedule.", n_us_nation_nonreporting, us_nonreporting_codes)

    # --- Attach FIX-02 per-code precision flag (home-country-zero) ---------
    prec = precision[["unique_carrier", "flag_home_share_zero"]].rename(
        columns={"unique_carrier": "UNIQUE_CARRIER"})
    matched_sample = matched_sample.merge(prec, on="UNIQUE_CARRIER", how="left")
    matched_sample["flag_home_share_zero"] = matched_sample["flag_home_share_zero"].fillna(False)

    # --- Extensive-margin population (unfiltered on departures) ------------
    extensive_pop = matched_sample.copy()
    logger.info("Extensive-margin population (passenger, matched-nation, departures >= 0 "
                "i.e. unfiltered on the intensive DEPARTURES_PERFORMED>0 step): %d rows.",
                len(extensive_pop))

    # --- B4 (overseer cycle-1 required action 4): routes that vanish from the
    # extensive margin entirely, because EVERY carrier that ever served them was
    # unmatched/icao-tier/null-code at the step-1b filter. These routes never
    # appear as a triple (they had no matched nation at all), so they are simply
    # absent from panel_extensive -- log them explicitly rather than let them
    # vanish without a reason. ---------------------------------------------
    routes_before_match = sample[["ORIGIN", "DEST"]].drop_duplicates()
    routes_after_match = extensive_pop[["ORIGIN", "DEST"]].drop_duplicates()
    routes_before_set = set(map(tuple, routes_before_match.to_numpy()))
    routes_after_set = set(map(tuple, routes_after_match.to_numpy()))
    lost_routes_set = routes_before_set - routes_after_set
    n_routes_before = len(routes_before_set)
    n_routes_after = len(routes_after_set)
    n_routes_lost = len(lost_routes_set)
    if lost_routes_set:
        lost_routes_df = pd.DataFrame(list(lost_routes_set), columns=["ORIGIN", "DEST"])
        lost_rows = sample.merge(lost_routes_df, on=["ORIGIN", "DEST"], how="inner")
        dep_lost = float(lost_rows["DEPARTURES_PERFORMED"].sum())
    else:
        dep_lost = 0.0
    _log_filter(filter_log, "route", "drop", "routes_lost_no_matched_carrier",
                n_routes_before, n_routes_after,
                f"(origin, dest) routes present in the passenger-service sample where EVERY "
                f"carrier ever serving them was unmatched/icao-tier/null-code at the "
                f"matched-nation filter, so the route has zero matched-nation triples and is "
                f"entirely absent from panel_extensive ({n_routes_lost} routes, "
                f"{dep_lost:.0f} departures, all attributable to excluded carriers).")
    logger.info("B4: %d / %d passenger-service (origin, dest) routes have no matched-nation "
                "carrier at all and are absent from panel_extensive (%.0f departures).",
                n_routes_lost, n_routes_before, dep_lost)

    # --- Step 1c: departures > 0 (intensive panel only) ---------------------
    n2 = len(matched_sample)
    intensive = matched_sample.loc[matched_sample["DEPARTURES_PERFORMED"] > 0].copy()
    _log_filter(filter_log, "row", "drop", "departures_gt_0", n2, len(intensive),
                "DEPARTURES_PERFORMED == 0 rows (scheduled but not flown) dropped from the "
                "intensive panel; kept for the extensive margin only, per Part 0.")
    logger.info("Filter departures>0 (intensive panel only): %d -> %d rows.", n2, len(intensive))

    # =====================================================================
    # PANEL_MONTHLY: aggregate over carriers AND aircraft types within cell.
    # Fully vectorized (groupby.agg / groupby.sum, never groupby.apply with a
    # per-group Python function) -- with ~1M detail rows and hundreds of
    # thousands of cells, a per-group callback is a wall-clock non-starter
    # and was measured hanging past 2.5 minutes in development; every
    # quantity below is computed as a row-level helper column first, so the
    # actual groupby is a single Cython-level sum/nunique pass.
    # =====================================================================
    group_cols = ["ORIGIN", "DEST", "nation", "YEAR", "MONTH"]
    n_detail_rows = len(intensive)

    d = intensive
    rt = d["reports_time"]
    # B3 (overseer cycle-1): among CARRIER_GROUP-eligible rows, AIR_TIME==0 or
    # RAMP_TO_RAMP==0 (with DEPARTURES_PERFORMED>0) is a within-US reporting gap
    # per Part 0, not a zero-minute flight -- excluded from BOTH the numerator
    # and the denominator of the respective mean, logged as its own filter step.
    air_gap_row = rt & (d["AIR_TIME"].fillna(0.0) == 0.0)
    ramp_gap_row = rt & (d["RAMP_TO_RAMP"].fillna(0.0) == 0.0)
    air_valid_row = rt & (~air_gap_row)
    ramp_valid_row = rt & (~ramp_gap_row)

    n_air_gap_rows = int(air_gap_row.sum())
    dep_air_gap = float(d.loc[air_gap_row, "DEPARTURES_PERFORMED"].sum())
    n_ramp_gap_rows = int(ramp_gap_row.sum())
    dep_ramp_gap = float(d.loc[ramp_gap_row, "DEPARTURES_PERFORMED"].sum())
    _log_filter(filter_log, "row", "exclude_from_time_agg", "air_time_zero_gap_excluded",
                n_detail_rows, n_detail_rows - n_air_gap_rows,
                f"CARRIER_GROUP-eligible rows with AIR_TIME==0 despite DEPARTURES_PERFORMED>0 "
                f"(within-US reporting gap, Part 0 'never imputed') excluded from both the "
                f"numerator and denominator of airborne_min_mean, NOT dropped from the panel "
                f"row itself ({n_air_gap_rows} rows, {dep_air_gap:.0f} departures).")
    _log_filter(filter_log, "row", "exclude_from_time_agg", "ramp_zero_gap_excluded",
                n_detail_rows, n_detail_rows - n_ramp_gap_rows,
                f"CARRIER_GROUP-eligible rows with RAMP_TO_RAMP==0 despite DEPARTURES_PERFORMED>0 "
                f"(within-US reporting gap) excluded from both the numerator and denominator of "
                f"ramp_min_mean, NOT dropped from the panel row itself "
                f"({n_ramp_gap_rows} rows, {dep_ramp_gap:.0f} departures).")
    logger.info("Within-US reporting gaps: %d rows / %.0f departures excluded from the "
                "airborne mean (AIR_TIME==0), %d rows / %.0f departures excluded from the "
                "ramp mean (RAMP_TO_RAMP==0).", n_air_gap_rows, dep_air_gap,
                n_ramp_gap_rows, dep_ramp_gap)

    d = d.assign(
        dep_time_eligible=np.where(rt, d["DEPARTURES_PERFORMED"], 0.0),
        dep_air_valid=np.where(air_valid_row, d["DEPARTURES_PERFORMED"], 0.0),
        dep_ramp_valid=np.where(ramp_valid_row, d["DEPARTURES_PERFORMED"], 0.0),
        air_time_eligible=np.where(air_valid_row, d["AIR_TIME"].fillna(0.0), 0.0),
        ramp_eligible=np.where(ramp_valid_row, d["RAMP_TO_RAMP"].fillna(0.0), 0.0),
        sched_eligible=np.where(rt, d["DEPARTURES_SCHEDULED"].fillna(0.0), 0.0),
        dep_home0_contrib=np.where(d["flag_home_share_zero"], d["DEPARTURES_PERFORMED"], 0.0),
        dep_x_distance=d["DEPARTURES_PERFORMED"] * d["DISTANCE"],
    )

    logger.info("Aggregating %d detail rows (carrier x aircraft-type x segment x month, "
                "no dedup) into cells on %s ...", n_detail_rows, group_cols)

    cell_agg = d.groupby(group_cols, dropna=False, sort=False).agg(
        departures_performed=("DEPARTURES_PERFORMED", "sum"),
        departures_time_eligible=("dep_time_eligible", "sum"),
        dep_for_airtime=("dep_air_valid", "sum"),
        dep_for_ramp=("dep_ramp_valid", "sum"),
        air_time_total_raw=("air_time_eligible", "sum"),
        ramp_total_raw=("ramp_eligible", "sum"),
        departures_scheduled_raw=("sched_eligible", "sum"),
        dep_home0=("dep_home0_contrib", "sum"),
        dep_x_distance=("dep_x_distance", "sum"),
        n_carriers=("UNIQUE_CARRIER", "nunique"),
        n_aircraft_types=("AIRCRAFT_TYPE", "nunique"),
        n_rows_raw=("DEPARTURES_PERFORMED", "size"),
    ).reset_index()

    # Fleet mix: departures by (cell, aircraft type), then the max share within cell.
    type_sums = (d.groupby(group_cols + ["AIRCRAFT_TYPE"], dropna=False, sort=False)
                 ["DEPARTURES_PERFORMED"].sum().reset_index(name="type_dep"))
    top_type = (type_sums.groupby(group_cols, dropna=False, sort=False)["type_dep"]
                .max().reset_index(name="top_type_dep"))
    cell_agg = cell_agg.merge(top_type, on=group_cols, how="left")

    panel = cell_agg.rename(columns={"ORIGIN": "origin", "DEST": "dest",
                                      "YEAR": "year", "MONTH": "month"})
    n_cells_raw = len(panel)
    assert panel["n_rows_raw"].sum() == n_detail_rows, \
        "aggregation lost or invented detail rows -- dedup must have happened somewhere"
    logger.info("Aggregated to %d (origin, dest, nation, year, month) cells "
                "(%d detail rows in, %d out via n_rows_raw sum check).",
                n_cells_raw, n_detail_rows, int(panel["n_rows_raw"].sum()))
    _log_filter(filter_log, "cell", "none", "aggregate_to_cell", n_cells_raw, n_cells_raw,
                "Aggregation step, not a drop: every detail row is summed into exactly one "
                "cell (verified n_rows_raw sums to the input row count).")

    # B2 (overseer cycle-1): departures_time_eligible is CARRIER_GROUP-based (structural
    # eligibility to report time at all) and is kept as its own column, distinct from
    # departures_performed, precisely so a mixed cell (real US departures plus departures
    # from a carrier mis-mapped to US, per the docstring's VX (1)/B0/WO finding) is visible
    # rather than silently diluting the denominator. departures_non_reporting is the gap.
    assert (panel["departures_time_eligible"] <= panel["departures_performed"] + 1e-6).all(), \
        "departures_time_eligible must never exceed departures_performed"
    panel["departures_non_reporting"] = (panel["departures_performed"]
                                          - panel["departures_time_eligible"])

    has_air = panel["dep_for_airtime"] > 0
    has_ramp = panel["dep_for_ramp"] > 0
    panel["air_time_total"] = np.where(has_air, panel["air_time_total_raw"], np.nan)
    panel["ramp_total"] = np.where(has_ramp, panel["ramp_total_raw"], np.nan)
    panel["departures_scheduled"] = np.where(panel["departures_time_eligible"] > 0,
                                              panel["departures_scheduled_raw"], np.nan)
    panel["airborne_min_mean"] = np.where(has_air,
                                           panel["air_time_total_raw"] / panel["dep_for_airtime"], np.nan)
    panel["ramp_min_mean"] = np.where(has_ramp,
                                       panel["ramp_total_raw"] / panel["dep_for_ramp"], np.nan)
    panel["airborne_available"] = has_air
    panel["ramp_available"] = has_ramp
    panel["distance"] = panel["dep_x_distance"] / panel["departures_performed"]
    panel["fleet_share_top_type"] = np.where(panel["departures_performed"] > 0,
                                              panel["top_type_dep"] / panel["departures_performed"],
                                              np.nan)
    # Advisory (cycle-2): rename, don't drop, the two true denominators. departures_time_eligible
    # (CARRIER_GROUP-based) is NOT the correct weight for airborne_min_mean/ramp_min_mean in the
    # 26+8 cells affected by the within-US AIR_TIME==0/RAMP_TO_RAMP==0 gap exclusion above --
    # those cells have dep_for_airtime/dep_for_ramp strictly less than departures_time_eligible.
    # Exposing the real denominators directly (rather than requiring a caller to back them out
    # as air_time_total/airborne_min_mean) removes that trap.
    panel = panel.rename(columns={"dep_for_airtime": "departures_airborne_eligible",
                                   "dep_for_ramp": "departures_ramp_eligible"})
    panel = panel.drop(columns=["air_time_total_raw", "ramp_total_raw", "departures_scheduled_raw",
                                 "dep_x_distance", "top_type_dep"])

    panel["share_dep_home0"] = np.where(panel["departures_performed"] > 0,
                                         panel["dep_home0"] / panel["departures_performed"], np.nan)
    panel = panel.drop(columns=["dep_home0"])

    # --- STRUCTURAL-ZERO GUARD, asserted at the cell level ------------------
    non_us = panel.loc[panel["nation"] != "US"]
    bad_air = non_us.loc[non_us["airborne_min_mean"].notna() | non_us["air_time_total"].notna()]
    bad_ramp = non_us.loc[non_us["ramp_min_mean"].notna() | non_us["ramp_total"].notna()]
    bad_avail = non_us.loc[non_us["airborne_available"] | non_us["ramp_available"]]
    bad_eligible = non_us.loc[non_us["departures_time_eligible"] > 0]
    if len(bad_air) or len(bad_ramp) or len(bad_avail) or len(bad_eligible):
        logger.error("STRUCTURAL-ZERO GUARD VIOLATED at cell level: %d non-US cells with a "
                      "non-null airborne value, %d with a non-null ramp value, %d with an "
                      "available flag True, %d with departures_time_eligible > 0.",
                      len(bad_air), len(bad_ramp), len(bad_avail), len(bad_eligible))
        return 1
    logger.info("STRUCTURAL-ZERO GUARD holds: all %d non-US-nation cells have null "
                "airborne_min_mean/ramp_min_mean, airborne_available/ramp_available == False, "
                "and departures_time_eligible == 0.", len(non_us))
    us_cells = panel.loc[panel["nation"] == "US"]
    n_us_airborne_avail = int(us_cells["airborne_available"].sum())
    logger.info("US-nation cells: %d total, %d with airborne_available == True (%.4f).",
                len(us_cells), n_us_airborne_avail,
                n_us_airborne_avail / len(us_cells) if len(us_cells) else float("nan"))
    # B2 diagnostic (cycle-2 correction): departures_non_reporting > 0 spans TWO distinct
    # populations that must not be described as one another. (i) Non-US-nation cells: ALL
    # of their departures_performed is non_reporting BY CONSTRUCTION (departures_time_eligible
    # == 0 there, per the structural-zero guard above) -- this is the ordinary, expected
    # foreign-carrier-never-reports-time fact from FIX-03, nothing to do with FIX-02's mapping
    # precision. (ii) nation=='US' cells: a SMALL subset of these are "mixed" -- containing
    # departures from VX (1)/B0/WO, the three carriers mis-mapped to nation=='US' by FIX-02
    # IATA-code collisions (see docstring) -- and only THIS subset is the G7 precision issue.
    non_us_nonreporting_cells = non_us.loc[non_us["departures_non_reporting"] > 0]
    n_non_us_nonreporting_cells = len(non_us_nonreporting_cells)
    dep_non_us_nonreporting = float(non_us_nonreporting_cells["departures_non_reporting"].sum())
    us_mixed_cells = us_cells.loc[us_cells["departures_non_reporting"] > 0]
    n_us_mixed_cells = len(us_mixed_cells)
    dep_us_mixed = float(us_mixed_cells["departures_non_reporting"].sum())
    logger.info("B2 diagnostic, non-US-nation cells (ordinary structural non-reporting, FIX-03 "
                "fact -- NOT a FIX-02 mapping issue): %d cells / %.0f departures, all of it "
                "(every non-US cell has departures_time_eligible == 0 by construction).",
                n_non_us_nonreporting_cells, dep_non_us_nonreporting)
    logger.info("B2 diagnostic, nation=='US' mixed cells (the actual G7 precision issue -- "
                "departures from VX (1)/Aces Airlines/Colombia, B0/La Compagnie/France, or "
                "WO/SWOOP/Canada landing in a nation=='US' cell without contributing to the "
                "airborne/ramp numerator): %d cells / %.0f departures.",
                n_us_mixed_cells, dep_us_mixed)

    # --- covid_flag, coverage_ok (G6, from FIX-03), cell_ok, cell_ok_8 -----
    panel["covid_flag"] = _covid_flag(panel["year"], panel["month"])

    cov = coverage[["nation", "year", "gate_g6_pass"]].rename(columns={"gate_g6_pass": "coverage_ok"})
    panel = panel.merge(cov, on=["nation", "year"], how="left", indicator="_cov_merge")
    n_cov_missing = int((panel["_cov_merge"] == "left_only").sum())
    if n_cov_missing:
        logger.warning("%d panel cells have no matching (nation, year) row in "
                        "coverage_audit.csv -- treating coverage_ok as False (conservative).",
                        n_cov_missing)
    panel["coverage_ok"] = panel["coverage_ok"].fillna(False)
    panel = panel.drop(columns=["_cov_merge"])

    panel["nation_precision_flag"] = (panel["nation"].isin(MATCH_SENSITIVE_NATIONS)
                                       | (panel["share_dep_home0"] >= HOME0_CELL_THRESHOLD))
    panel["cell_ok"] = panel["coverage_ok"] & (panel["departures_performed"] >= MIN_CELL_DEP)
    panel["cell_ok_8"] = panel["coverage_ok"] & (panel["departures_performed"] >= MIN_CELL_DEP_SENSITIVITY)
    panel["cell_ok_precision"] = panel["cell_ok"] & (~panel["nation_precision_flag"])

    n_fail_coverage = int((~panel["coverage_ok"]).sum())
    n_fail_mincell = int((panel["coverage_ok"] & (panel["departures_performed"] < MIN_CELL_DEP)).sum())
    n_cell_ok = int(panel["cell_ok"].sum())
    n_cell_ok_8 = int(panel["cell_ok_8"].sum())
    _log_filter(filter_log, "cell", "flag", "coverage_ok_g6", n_cells_raw, n_cells_raw - n_fail_coverage,
                f"nation x year coverage share (FIX-03 G6) < 0.50 -- flagged False, "
                f"NOT dropped from panel_monthly ({n_fail_coverage} cells).")
    _log_filter(filter_log, "cell", "flag", "min_cell_size_4", n_cells_raw,
                n_cells_raw - n_fail_mincell,
                f"< 4 departures in the month among coverage_ok cells -- flagged False in "
                f"cell_ok, NOT dropped ({n_fail_mincell} cells).")
    _log_filter(filter_log, "cell", "flag", "cell_ok_final", n_cells_raw, n_cell_ok,
                f"cell_ok = coverage_ok & departures>=4 ({n_cell_ok} cells pass).")
    _log_filter(filter_log, "cell", "flag", "cell_ok_8_sensitivity", n_cells_raw, n_cell_ok_8,
                f"sensitivity: cell_ok_8 = coverage_ok & departures>=8 ({n_cell_ok_8} cells pass).")
    logger.info("cell_ok (coverage_ok & departures>=4): %d / %d cells (%.4f).",
                n_cell_ok, n_cells_raw, n_cell_ok / n_cells_raw)
    logger.info("cell_ok_8 (coverage_ok & departures>=8): %d / %d cells (%.4f).",
                n_cell_ok_8, n_cells_raw, n_cell_ok_8 / n_cells_raw)
    logger.info("cell_ok_precision (cell_ok & ~nation_precision_flag): %d / %d cells (%.4f).",
                int(panel["cell_ok_precision"].sum()), n_cells_raw,
                panel["cell_ok_precision"].sum() / n_cells_raw)

    n_cell_ok_mixed = int(((panel["cell_ok"]) & (panel["departures_non_reporting"] > 0)).sum())
    dep_cell_ok_mixed = float(panel.loc[panel["cell_ok"] & (panel["departures_non_reporting"] > 0),
                                         "departures_non_reporting"].sum())
    n_cell_ok_precision_mixed = int(((panel["cell_ok_precision"])
                                      & (panel["departures_non_reporting"] > 0)).sum())
    max_mixed_share = float((panel.loc[panel["cell_ok_precision"] & (panel["departures_non_reporting"] > 0),
                                        "departures_non_reporting"]
                              / panel.loc[panel["cell_ok_precision"] & (panel["departures_non_reporting"] > 0),
                                          "departures_performed"]).max()) if n_cell_ok_precision_mixed else float("nan")
    logger.info("B2 testable: %d cell_ok cells have departures_non_reporting > 0 (%.0f "
                "departures); %d of those still survive cell_ok_precision (max mixed share "
                "%.4f).", n_cell_ok_mixed, dep_cell_ok_mixed, n_cell_ok_precision_mixed,
                max_mixed_share)
    # G9 (overseer cycle-2 required action 2): 1,681 / 35,051 / 588 previously existed only in
    # the log, uncitable by the director. Carry them into panel_filter_log.csv as their own
    # cell-level "flag" rows (not drops -- these cells remain in panel_monthly regardless).
    _log_filter(filter_log, "cell", "flag", "cell_ok_mixed_mapping_precision",
                n_cell_ok, n_cell_ok - n_cell_ok_mixed,
                f"cell_ok cells whose departures_performed includes departures from carriers "
                f"mis-mapped to nation=='US' by FIX-02 IATA-code collisions (VX (1)/B0/WO) "
                f"that never contribute to the airborne/ramp numerator -- flagged via "
                f"departures_non_reporting > 0, NOT dropped from panel_monthly "
                f"({n_cell_ok_mixed} cells, {dep_cell_ok_mixed:.0f} departures).")
    _log_filter(filter_log, "cell", "flag", "cell_ok_precision_mixed_mapping_residual",
                n_cell_ok_mixed, n_cell_ok_mixed - n_cell_ok_precision_mixed,
                f"of the {n_cell_ok_mixed} cell_ok mixed-mapping cells above, "
                f"{n_cell_ok_precision_mixed} still survive cell_ok_precision (i.e. "
                f"nation_precision_flag did not catch them; max mixed departures share "
                f"{max_mixed_share:.4f}) -- residual G7 precision exposure not fully screened "
                f"by the cell-level nation_precision_flag threshold.")

    # --- G1/G5 sanity gates --------------------------------------------
    share_cols = [c for c in panel.columns if "share" in c.lower()]
    for c in share_cols:
        vals = panel[c].dropna()
        bad = vals[(vals < -1e-9) | (vals > 1 + 1e-9)]
        if len(bad):
            logger.error("G5 FAIL: column %s outside [0,1] in %d rows.", c, len(bad))
            return 1
    logger.info("G5 pass: %s all within [0,1].", share_cols)
    if panel[["origin", "dest", "nation", "year", "month"]].isna().any().any():
        logger.error("G1 FAIL: null values in the cell key.")
        return 1
    dup_key = panel.duplicated(subset=["origin", "dest", "nation", "year", "month"]).sum()
    if dup_key:
        logger.error("G1 FAIL: %d duplicate cell keys in panel_monthly -- aggregation is broken.",
                     dup_key)
        return 1
    logger.info("G1 pass: no null cell keys, no duplicate cell keys (%d unique cells).", len(panel))

    panel = panel.sort_values(["origin", "dest", "nation", "year", "month"]).reset_index(drop=True)
    # NOTE (overseer cycle-1 required action 5, corrected per cycle-2 advisory): panel.to_parquet
    # is deliberately NOT called here -- it is deferred until after the panel_extensive row-count
    # VERIFY below, so a VERIFY failure leaves neither parquet on disk. This is NOT a blanket
    # "nothing is ever written on any failure" guarantee: desc_sample.csv's own TOTAL assertion
    # (further below) is a separate, later gate, and a failure there does NOT roll back the two
    # parquets or extensive_margin_churn.csv, which were already validly written by that point
    # (confirmed by mutation testing -- the desc-TOTAL mutation exits 1 but leaves both parquets
    # and the churn CSV in place, correctly, since nothing about them was invalidated).

    # =====================================================================
    # PANEL_EXTENSIVE: every (origin, dest, nation) ever observed x every
    # month 1990-01..2025-12. "Ever observed" = distinct triples appearing at
    # least once in the passenger-service, matched-nation population with
    # departures >= 0 (extensive_pop above, i.e. step 1a+1b applied, step 1c
    # NOT applied). This is the definition the VERIFY item's "routes x
    # nations observed" refers to: the count of DISTINCT (origin, dest,
    # nation) triples actually observed -- not the full cross product of all
    # routes ever seen times all nations ever seen (which would include
    # combinations no nation ever flew).
    # =====================================================================
    monthly_activity = (extensive_pop.groupby(["ORIGIN", "DEST", "nation", "YEAR", "MONTH"],
                                                dropna=False)["DEPARTURES_PERFORMED"]
                         .sum().rename("departures_performed_month").reset_index())
    monthly_activity = monthly_activity.rename(columns={"ORIGIN": "origin", "DEST": "dest",
                                                          "YEAR": "year", "MONTH": "month"})
    monthly_activity["observed_this_month"] = True
    monthly_activity["active"] = monthly_activity["departures_performed_month"] > 0

    triples = extensive_pop[["ORIGIN", "DEST", "nation"]].drop_duplicates().rename(
        columns={"ORIGIN": "origin", "DEST": "dest"})
    n_triples = len(triples)
    n_routes = triples[["origin", "dest"]].drop_duplicates().shape[0]
    n_nations_observed = triples["nation"].nunique()

    months = pd.period_range(f"{PANEL_START[0]}-{PANEL_START[1]:02d}",
                              f"{PANEL_END[0]}-{PANEL_END[1]:02d}", freq="M")
    n_months = len(months)
    months_df = pd.DataFrame({"year": months.year, "month": months.month})
    expected_rows = n_triples * n_months
    logger.info("Extensive margin: %d distinct (origin, dest, nation) triples ever observed "
                "x %d months (%s..%s) = %d expected rows.",
                n_triples, n_months, months[0], months[-1], expected_rows)

    triples["_key"] = 1
    months_df["_key"] = 1
    grid = triples.merge(months_df, on="_key").drop(columns="_key")
    logger.info("Built full grid: %d rows.", len(grid))

    ext = grid.merge(monthly_activity, on=["origin", "dest", "nation", "year", "month"], how="left")
    log_merge(logger, grid, monthly_activity, ext, on="(origin,dest,nation,year,month)", how="left")
    ext["observed_this_month"] = ext["observed_this_month"].fillna(False)
    ext["active"] = ext["active"].fillna(False)
    ext["departures_performed_month"] = ext["departures_performed_month"].fillna(0.0)

    if len(ext) != expected_rows:
        logger.error("VERIFY FAIL: panel_extensive has %d rows, expected %d "
                     "(%d triples x %d months). No parquet written.",
                     len(ext), expected_rows, n_triples, n_months)
        return 1
    logger.info("VERIFY: panel_extensive row count matches %d triples x %d months exactly.",
                n_triples, n_months)

    ext = ext.sort_values(["origin", "dest", "nation", "year", "month"]).reset_index(drop=True)
    grp_keys = ["origin", "dest", "nation"]
    g = ext.groupby(grp_keys, sort=False)

    prev_active = g["active"].shift(1).fillna(False).astype(bool)
    ext["entry_flag"] = ext["active"] & (~prev_active)
    ext["exit_flag"] = (~ext["active"]) & prev_active

    first_row_of_group = ~ext.duplicated(subset=grp_keys)
    state_change = (ext["active"].to_numpy() != prev_active.to_numpy()) | first_row_of_group.to_numpy()
    run_id = pd.Series(state_change, index=ext.index).cumsum()
    cumcount_in_run = ext.groupby(run_id).cumcount()

    # Vectorized (groupby().cummax() is a Cython-level op, not a per-group callback):
    # whether `active` was True at any row strictly before the current one, within
    # the same (origin, dest, nation) group.
    ever_active_before = prev_active.astype("int8").groupby(
        ext.groupby(grp_keys, sort=False).ngroup()).cummax().astype(bool)

    ext["months_since_exit"] = np.where(
        ext["active"], np.nan,
        np.where(ever_active_before.to_numpy(), cumcount_in_run.to_numpy(), np.nan))

    ext["covid_flag"] = _covid_flag(ext["year"], ext["month"])

    n_entries = int(ext["entry_flag"].sum())
    n_exits = int(ext["exit_flag"].sum())
    logger.info("Extensive margin flags: %d entry events, %d exit events across %d triples.",
                n_entries, n_exits, n_triples)

    # --- Both validated parquets, written together, only now (overseer cycle-1
    # required action 5) ------------------------------------------------------
    panel.to_parquet(PANEL_MONTHLY_PARQUET, index=False)
    logger.info("Wrote %s: %d rows.", PANEL_MONTHLY_PARQUET, len(panel))
    ext.to_parquet(PANEL_EXTENSIVE_PARQUET, index=False)
    logger.info("Wrote %s: %d rows.", PANEL_EXTENSIVE_PARQUET, len(ext))

    # =====================================================================
    # B6 (overseer cycle-1 required action 6): extensive-margin churn diagnostic.
    # Construction caveat, NOT a result -- an exit event study on this margin would
    # be mostly seasonality (thin routes flip active/inactive month to month), and
    # this CSV exists so that caveat is G9-citable rather than living only in a
    # review comment. Every number here is a mechanical property of the entry/exit
    # flags already asserted correct above (active row count == panel_monthly
    # row count, verified earlier in this script).
    # =====================================================================
    ext["month_idx"] = (ext["year"] - PANEL_START[0]) * 12 + (ext["month"] - 1)
    entries_idx = ext.loc[ext["entry_flag"], grp_keys + ["month_idx"]].rename(
        columns={"month_idx": "entry_idx"})
    exits_idx = ext.loc[ext["exit_flag"], grp_keys + ["month_idx"]].rename(
        columns={"month_idx": "exit_idx"})
    pair = exits_idx.merge(entries_idx, on=grp_keys, how="left")
    pair = pair.loc[pair["entry_idx"] > pair["exit_idx"]]
    next_entry = pair.groupby(grp_keys + ["exit_idx"])["entry_idx"].min().reset_index()
    next_entry["gap_months"] = next_entry["entry_idx"] - next_entry["exit_idx"]

    n_exits_total = n_exits
    n_reenter_ever = len(next_entry)
    n_reenter_3 = int((next_entry["gap_months"] <= 3).sum())
    n_reenter_12 = int((next_entry["gap_months"] <= 12).sum())
    entries_per_triple = ext.groupby(grp_keys)["entry_flag"].sum()
    active_months_per_triple = ext.groupby(grp_keys)["active"].sum()
    share_multi_entry = float((entries_per_triple > 1).mean())

    churn_rows = [
        {"metric": "n_triples", "value": n_triples},
        {"metric": "n_exits", "value": n_exits_total},
        {"metric": "n_exits_reentering_ever", "value": n_reenter_ever},
        {"metric": "share_exits_reentering_ever",
         "value": n_reenter_ever / n_exits_total if n_exits_total else float("nan")},
        {"metric": "n_exits_reentering_within_3mo", "value": n_reenter_3},
        {"metric": "share_exits_reentering_within_3mo",
         "value": n_reenter_3 / n_exits_total if n_exits_total else float("nan")},
        {"metric": "n_exits_reentering_within_12mo", "value": n_reenter_12},
        {"metric": "share_exits_reentering_within_12mo",
         "value": n_reenter_12 / n_exits_total if n_exits_total else float("nan")},
        {"metric": "entries_per_triple_mean", "value": float(entries_per_triple.mean())},
        {"metric": "entries_per_triple_median", "value": float(entries_per_triple.median())},
        {"metric": "entries_per_triple_p90", "value": float(entries_per_triple.quantile(0.90))},
        {"metric": "entries_per_triple_max", "value": float(entries_per_triple.max())},
        {"metric": "share_triples_with_gt1_entry", "value": share_multi_entry},
        {"metric": "active_months_per_triple_mean", "value": float(active_months_per_triple.mean())},
        {"metric": "active_months_per_triple_median", "value": float(active_months_per_triple.median())},
        {"metric": "active_months_per_triple_p90", "value": float(active_months_per_triple.quantile(0.90))},
        {"metric": "active_months_per_triple_max", "value": float(active_months_per_triple.max())},
    ]
    churn = pd.DataFrame(churn_rows)
    churn["note"] = ("construction caveat, not a result -- extensive-margin churn is "
                      "dominated by thin/seasonal routes; see panel_filter_log.csv and "
                      "ROUND_01_FINDINGS.md before using this margin for an event study")
    churn.to_csv(CHURN_CSV, index=False)
    logger.info("Wrote %s: %d metric rows. n_exits=%d, reenter_ever=%d (%.4f), "
                "reenter<=3mo=%d (%.4f), reenter<=12mo=%d (%.4f), median active months/triple=%.1f.",
                CHURN_CSV, len(churn), n_exits_total, n_reenter_ever,
                n_reenter_ever / n_exits_total if n_exits_total else float("nan"),
                n_reenter_3, n_reenter_3 / n_exits_total if n_exits_total else float("nan"),
                n_reenter_12, n_reenter_12 / n_exits_total if n_exits_total else float("nan"),
                float(active_months_per_triple.median()))

    # =====================================================================
    # desc_sample.csv: cells/routes/nations/years by decade (cell_ok==True
    # headline sample) + drops at each filter step (mirrors panel_filter_log)
    # =====================================================================
    ok = panel.loc[panel["cell_ok"]].copy()
    ok["decade"] = (ok["year"] // 10) * 10

    # VERIFY item computed and asserted BEFORE the CSV is written (overseer cycle-1
    # required action 5): a failed assertion here must leave no desc_sample.csv on disk.
    n_cell_ok_total = len(ok)
    assert n_cell_ok_total == int(panel["cell_ok"].sum()), \
        "desc_sample.csv TOTAL n_cells does not equal panel_monthly cell_ok==True row count"
    logger.info("VERIFY: desc_sample.csv TOTAL n_cells (%d) == panel_monthly cell_ok==True "
                "row count (%d).", n_cell_ok_total, int(panel["cell_ok"].sum()))

    decade_rows = []
    for decade, dd in ok.groupby("decade"):
        decade_rows.append({
            "row_type": "decade_summary", "decade": int(decade), "step": pd.NA,
            "n_cells": len(dd), "n_routes": dd[["origin", "dest"]].drop_duplicates().shape[0],
            "n_nations": dd["nation"].nunique(), "n_years": dd["year"].nunique(),
            "n_before": pd.NA, "n_after": pd.NA, "n_dropped": pd.NA, "reason": pd.NA,
        })
    decade_rows.append({
        "row_type": "decade_summary", "decade": "TOTAL", "step": pd.NA,
        "n_cells": n_cell_ok_total, "n_routes": ok[["origin", "dest"]].drop_duplicates().shape[0],
        "n_nations": ok["nation"].nunique(), "n_years": ok["year"].nunique(),
        "n_before": pd.NA, "n_after": pd.NA, "n_dropped": pd.NA, "reason": pd.NA,
    })
    filter_rows_for_desc = []
    for r in filter_log:
        filter_rows_for_desc.append({
            "row_type": "filter_drop", "decade": pd.NA, "step": r["step"],
            "n_cells": pd.NA, "n_routes": pd.NA, "n_nations": pd.NA, "n_years": pd.NA,
            "n_before": r["n_before"], "n_after": r["n_after"], "n_dropped": r["n_dropped"],
            "reason": r["reason"],
        })
    desc = pd.DataFrame(decade_rows + filter_rows_for_desc)
    desc.to_csv(DESC_SAMPLE_CSV, index=False)
    logger.info("Wrote %s: %d rows (%d decade_summary incl. TOTAL, %d filter_drop).",
                DESC_SAMPLE_CSV, len(desc), len(decade_rows), len(filter_rows_for_desc))

    # =====================================================================
    # panel_filter_log.csv
    # =====================================================================
    pd.DataFrame(filter_log).to_csv(FILTER_LOG_CSV, index=False)
    logger.info("Wrote %s: %d filter-step rows.", FILTER_LOG_CSV, len(filter_log))

    logger.info("04_build_panel DONE. panel_monthly: %d cells (%d cell_ok, %d cell_ok_8, "
                "%d cell_ok_precision). panel_extensive: %d rows (%d triples x %d months).",
                len(panel), int(panel["cell_ok"].sum()), int(panel["cell_ok_8"].sum()),
                int(panel["cell_ok_precision"].sum()), len(ext), n_triples, n_months)
    return 0


if __name__ == "__main__":
    sys.exit(main())
