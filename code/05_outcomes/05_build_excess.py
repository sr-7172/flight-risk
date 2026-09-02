#!/usr/bin/env python3
"""05_build_excess.py — FIX-05: baseline, excess airborne time, bidirectional sum.

Two-sentence summary: for every "clean" US-carrier cell (passes FIX-04's
cell_ok gate: nation-year coverage >= 0.50 and >= 4 departures in the month,
per Part 0/G6) we take its mean airborne minutes per departure and subtract
the median of that same directed route in the same calendar month over the
trailing three years (COVID months never counted), so "excess" means "how
many minutes longer or shorter than this route normally flies in this
month of the year"; the bidirectional sum then adds the excess on the return
leg so a jet-stream tailwind on one direction cannot be mistaken for a
system-wide slowdown.

REGENERATION NOTICE. This script was first run concurrently with FIX-04's
review, which then FAILED FIX-04 (cycle 1) on columns this script reads.
Per the overseer's ruling, that first run's artifacts were VOID and have
been overwritten in place by this corrected run against FIX-04's PASSED
(cycle 2) panel_monthly.parquet -- no mixture of old/new outputs is left in
the round folder. Two substantive changes from the void run are folded in
below: (1) panel_monthly's airborne_min_mean now divides by the recovered
airborne-reporting-eligible denominator (departures_time_eligible) rather
than departures_performed, and within-US reporting gaps (time-eligible
departures with AIR_TIME==0) are NaN rather than imputed as 0.00 -- this
script consumes airborne_min_mean as FIX-04 computed it and does not
re-derive it; (2) the extreme-value screen below is now an implied-speed
screen (see DATA-QUALITY SCREEN), replacing an absolute-minutes threshold.

GOVERNING SCOPE (binding, per the overseer's instruction for this task).
FIX-03 established and FIX-04 independently re-verified from CARRIER_GROUP
that foreign carriers (CARRIER_GROUP == 0) NEVER report AIR_TIME/RAMP_TO_RAMP
-- every one of 1,133,545 foreign-carrier segment-months is a literal 0.00,
not a null, in all 36 years. Consequently airborne_min_mean is non-null ONLY
on nation == 'US' cells (asserted below), and coverage_ok (G6, nation x year
airborne coverage >= 0.50) is empirically True only for nation == 'US' --
confirmed at runtime, not assumed. Every deliverable in this script is
therefore an explicitly ALL-US computation: "US carriers' airborne time on
US-touching international segments," never "the carrier-nation wedge." No
cross-national comparison is attempted or implied here.

DATA-QUALITY SCREEN (this task's own diagnostic, investigated below; revised
per the overseer's ruling on the void run). The void run treated the single
raw value 9999.0 as a sentinel; the overseer's re-audit of the raw t100_raw
rows found 47 raw (pre-aggregation) rows hit 9999.0 in AIR_TIME, and 46 of
them are unremarkable MONTHLY TOTALS that divide down to an ordinary
per-departure mean once aggregated (e.g. NW BOS-AMS 1990-10: total 9999 min
across many departures = 357 min/departure = a physically ordinary ~581 mph
implied speed) -- a magnitude- or round-number-based screen on the raw field
would have deleted 46 good cells, so no such screen is used here. Only ONE
cell-level row is genuinely impossible: M5 YGE->LKE 2025-10 (1 departure,
207 raw miles, airborne_min_mean == 9999.0, already cell_ok == False on the
>=4-departures gate alone; RAMP_TO_RAMP == 10004 suggests the corrupted raw
field is actually DEPARTURES_PERFORMED, not AIR_TIME). The correct,
physically-motivated screen is on IMPLIED SPEED (distance in miles / airborne
hours), not on raw minutes: no scheduled passenger aircraft in this dataset
cruises below 50 mph, so airborne_min_mean values implying less are flagged
as raw reporting errors and excluded from every baseline/excess computation
(never imputed, airborne_min_mean itself left untouched in
panel_monthly.parquet / panel_excess.parquet). distance == 0 (50 rows total,
2 with cell_ok == True, e.g. SWL<->WFB, a genuine Puget Sound seaplane hop
where BTS's whole-mile DISTANCE field rounds to 0) makes implied speed
degenerate (0 / positive-time = 0 mph, which would wrongly satisfy "< 50"
and misclassify a real short hop as an error) -- these rows are handled
EXPLICITLY, carved out of the speed test before it runs, and logged as KEPT,
not excluded. A supplementary >1000-min/departure diagnostic (not used for
exclusion; 80 cell_ok cells, worst NSB->FLL at 2,433 min / 59 mi) is also
logged in outcome_data_quality_exclusions.csv for scale.

BASELINE / EXCESS DEFINITION. "Valid" cell = cell_ok (FIX-04's G6 + >=4
departures gate) AND airborne_min_mean not null AND implied speed >= 50 mph
(not implausible; distance==0 cells are exempt from this test and remain
eligible). For a valid target cell (route, nation, year, month), the
baseline candidate pool is up to 3 values: the SAME valid cell at (year-1,
month), (year-2, month), (year-3, month) -- i.e. the same calendar month in
each of the trailing three years (PROJECT.md Outcome 1; ROUND_01 FIX-05
step 1's "trailing 36 months" and PROJECT.md's "trailing 3 years, same
calendar month" are the same window, since 36 months contains exactly 3
instances of any calendar month). A candidate is dropped from the pool (not
counted, not imputed) if its (year, month) falls inside the COVID window
2020-03..2021-12, per Part 0 and G8. baseline_med/baseline_mad are computed
only when >= 2 candidates survive (G8); otherwise both are NaN and
excess_min/excess_min_w/excess_z are NaN for that cell (the ">= 2 obs"
failure is never relaxed -- baseline_failures.csv reports the share).

Reads data/interim/panel_monthly.parquet (FIX-04, PASSED cycle 2). Never
modifies it, never touches data/raw/.
"""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from utils import setup_logger  # noqa: E402

# --- Inputs ------------------------------------------------------------
PANEL_MONTHLY_PARQUET = ROOT / "data" / "interim" / "panel_monthly.parquet"

# --- Outputs -------------------------------------------------------------
OUT_DIR = ROOT / "rounds" / "round-1-t100-panel"
PANEL_EXCESS_PARQUET = ROOT / "data" / "interim" / "panel_excess.parquet"
DESC_OUTCOMES_CSV = OUT_DIR / "desc_outcomes.csv"
BASELINE_FAILURES_CSV = OUT_DIR / "baseline_failures.csv"
DQ_EXCLUSIONS_CSV = OUT_DIR / "outcome_data_quality_exclusions.csv"
WINSOR_CUTOFFS_CSV = OUT_DIR / "excess_winsorization_cutoffs.csv"
CONSTRUCTION_DIAG_CSV = OUT_DIR / "excess_construction_diagnostics.csv"
SPEED_SENSITIVITY_CSV = OUT_DIR / "excess_speed_screen_sensitivity.csv"
FIG_PNG = OUT_DIR / "figures" / "fig_excess_distribution.png"
LOG_FILE = ROOT / "logs" / "05_build_excess.log"

# --- Constants -------------------------------------------------------------
COVID_START = (2020, 3)   # inclusive
COVID_END = (2021, 12)    # inclusive
IMPLIED_SPEED_MPH_MIN = 50.0  # no scheduled passenger aircraft cruises below this
DIAGNOSTIC_ONLY_MIN_PER_DEP = 1000.0  # reported, not used for exclusion
SPEED_SENSITIVITY_THRESHOLDS_MPH = (50.0, 100.0, 150.0, 200.0)  # sensitivity grid, NOT a change
UPPER_SPEED_DIAG_MPH = 700.0  # symmetric diagnostic only; no exclusion applied at either end
BASELINE_LAG_YEARS = (1, 2, 3)
WINSOR_LO, WINSOR_HI = 0.01, 0.99
SAMPLE_LABEL = "US carriers' airborne time on US-touching international segments"


def _covid_flag(year, month):
    year = np.asarray(year)
    month = np.asarray(month)
    lo = (year > COVID_START[0]) | ((year == COVID_START[0]) & (month >= COVID_START[1]))
    hi = (year < COVID_END[0]) | ((year == COVID_END[0]) & (month <= COVID_END[1]))
    return lo & hi


def _recompute_excess_min_w(panel: pd.DataFrame, valid_mask: pd.Series) -> np.ndarray:
    """Re-run the SAME baseline/excess/winsorize algorithm as the headline
    computation in main(), for an arbitrary validity mask. Used ONLY for the
    speed-screen sensitivity analysis (overseer cycle-2 blocking item 2) --
    never to alter the headline valid mask or any shipped column. At
    IMPLIED_SPEED_MPH_MIN (the shipped threshold) this function is not
    called; the sensitivity block reuses the actual shipped excess_min_w
    column instead, so the shipped 50-mph row can never drift from this
    re-implementation.
    """
    valid_df = panel.loc[valid_mask, ["origin", "dest", "nation", "year", "month",
                                       "airborne_min_mean"]].rename(
        columns={"airborne_min_mean": "value"})
    key_cols = ["origin", "dest", "nation", "month"]
    cand = {}
    for k in BASELINE_LAG_YEARS:
        lookup = panel[key_cols].copy()
        lookup["year"] = panel["year"] - k
        merged = lookup.merge(valid_df, on=["origin", "dest", "nation", "year", "month"],
                               how="left")
        cflag = _covid_flag(lookup["year"].to_numpy(), lookup["month"].to_numpy())
        value = np.where(cflag, np.nan, merged["value"].to_numpy())
        cand[k] = value
    cand_arr = np.column_stack([cand[k] for k in BASELINE_LAG_YEARS])
    baseline_n = np.sum(~np.isnan(cand_arr), axis=1)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        baseline_med_raw = np.nanmedian(cand_arr, axis=1)
    ok2 = baseline_n >= 2
    baseline_med = np.where(ok2, baseline_med_raw, np.nan)
    target_ok = valid_mask.to_numpy() & ok2
    excess_min = np.where(target_ok, panel["airborne_min_mean"].to_numpy() - baseline_med, np.nan)

    tmp = panel[["origin", "dest", "nation"]].copy()
    tmp["excess_min"] = excess_min
    grp = tmp.groupby(["origin", "dest", "nation"])["excess_min"]
    q_lo = grp.transform(lambda s: s.quantile(WINSOR_LO))
    q_hi = grp.transform(lambda s: s.quantile(WINSOR_HI))
    excess_min_w = tmp["excess_min"].clip(lower=q_lo, upper=q_hi)
    return excess_min_w.to_numpy()


def main() -> int:
    logger = setup_logger("05_build_excess", str(LOG_FILE))

    if not PANEL_MONTHLY_PARQUET.exists():
        logger.error("BLOCKED: required input %s not found.", PANEL_MONTHLY_PARQUET)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "figures").mkdir(parents=True, exist_ok=True)

    panel = pd.read_parquet(PANEL_MONTHLY_PARQUET)
    logger.info("Loaded panel_monthly.parquet: %d rows.", len(panel))

    # =====================================================================
    # Governing-fact re-check: airborne_min_mean is non-null only on US cells.
    # =====================================================================
    non_us_nonnull = panel.loc[(panel["nation"] != "US") & panel["airborne_min_mean"].notna()]
    if len(non_us_nonnull):
        logger.error("SCOPE VIOLATION: %d non-US cells carry a non-null airborne_min_mean -- "
                      "the all-US scope assumption this script rests on is false. Refusing "
                      "to proceed.", len(non_us_nonnull))
        return 1
    non_us_coverage_ok = panel.loc[(panel["nation"] != "US") & panel["coverage_ok"]]
    if len(non_us_coverage_ok):
        logger.error("SCOPE VIOLATION: %d non-US cells have coverage_ok == True. Refusing "
                      "to proceed.", len(non_us_coverage_ok))
        return 1
    logger.info("Governing-fact re-check holds: airborne_min_mean and coverage_ok are both "
                "empirically all-US in this panel (0 non-US exceptions). Every deliverable "
                "below is labelled '%s'.", SAMPLE_LABEL)

    # =====================================================================
    # Data-quality screen: implied-speed screen (distance / airborne hours),
    # replacing the void run's absolute-minutes threshold per the overseer's
    # ruling (see DATA-QUALITY SCREEN in the docstring).
    # =====================================================================
    dq_rows = []

    distance_zero = panel["distance"] == 0
    has_air = panel["airborne_min_mean"].notna()
    # Explicit handling of distance == 0 (per the coordinator's instruction:
    # do not let it "fall through" the speed formula, where 0 / positive-time
    # would evaluate to a finite 0 mph and wrongly satisfy "< 50 mph"). These
    # rows are carved OUT of the speed test entirely -- speed is undefined,
    # not "implausibly slow" -- and handled as their own KEPT category.
    implied_speed_mph = pd.Series(np.nan, index=panel.index)
    finite_mask = has_air & (~distance_zero)
    implied_speed_mph[finite_mask] = (panel.loc[finite_mask, "distance"]
                                       / (panel.loc[finite_mask, "airborne_min_mean"] / 60.0))

    implausible_speed = finite_mask & (implied_speed_mph < IMPLIED_SPEED_MPH_MIN)
    n_implausible = int(implausible_speed.sum())
    n_implausible_cellok = int((implausible_speed & panel["cell_ok"]).sum())
    logger.info("Implied-speed screen (< %.0f mph = distance / airborne hours; no scheduled "
                "passenger aircraft cruises this slow): %d rows total, %d with cell_ok == "
                "True. Nulled out of every baseline/excess computation below.",
                IMPLIED_SPEED_MPH_MIN, n_implausible, n_implausible_cellok)
    for idx, r in panel.loc[implausible_speed].iterrows():
        dq_rows.append({
            "check": "implied_speed_below_50mph", "value": float(implied_speed_mph[idx]),
            "n_airborne_min_mean": 1, "n_ramp_min_mean": 0,
            "example_origin": r["origin"], "example_dest": r["dest"],
            "example_year": int(r["year"]), "example_month": int(r["month"]),
            "example_departures": float(r["departures_performed"]),
            "example_distance": float(r["distance"]),
            "example_airborne_min_mean": float(r["airborne_min_mean"]),
            "decision": "EXCLUDED from baseline/excess (airborne_min_mean left untouched "
                        "in panel_monthly/panel_excess)",
        })

    dist0 = panel.loc[distance_zero]
    dist0_cellok = dist0.loc[dist0["cell_ok"]]
    logger.info("distance == 0 rows: %d total, %d with cell_ok == True (kept, carved out of "
                "the implied-speed test explicitly -- genuine very-short routes where BTS's "
                "whole-mile DISTANCE field rounds to 0; distance is a covariate here, not an "
                "outcome input).", len(dist0), len(dist0_cellok))
    for _, r in dist0_cellok.iterrows():
        dq_rows.append({
            "check": "distance_zero_cell_ok", "value": 0.0,
            "n_airborne_min_mean": np.nan, "n_ramp_min_mean": np.nan,
            "example_origin": r["origin"], "example_dest": r["dest"],
            "example_year": int(r["year"]), "example_month": int(r["month"]),
            "example_departures": float(r["departures_performed"]),
            "example_distance": 0.0,
            "example_airborne_min_mean": float(r["airborne_min_mean"]),
            "decision": "KEPT (short-route rounding artifact; implied speed undefined, "
                        "not excluded from outcomes)",
        })

    # Supplementary diagnostic (NOT used for exclusion): raw magnitude alone,
    # reported for scale/cross-reference against the overseer's own audit.
    diag_gt1000 = has_air & (panel["airborne_min_mean"] > DIAGNOSTIC_ONLY_MIN_PER_DEP)
    n_diag_gt1000 = int(diag_gt1000.sum())
    n_diag_gt1000_cellok = int((diag_gt1000 & panel["cell_ok"]).sum())
    logger.info("Diagnostic only (NOT an exclusion criterion): airborne_min_mean > %.0f "
                "min/departure: %d rows total, %d with cell_ok == True (worst cases overlap "
                "with the implied-speed exclusion above, e.g. NSB<->FLL).",
                DIAGNOSTIC_ONLY_MIN_PER_DEP, n_diag_gt1000, n_diag_gt1000_cellok)
    for idx, r in panel.loc[diag_gt1000 & panel["cell_ok"]].iterrows():
        dq_rows.append({
            "check": "diagnostic_only_gt_1000min_per_dep", "value": float(r["airborne_min_mean"]),
            "n_airborne_min_mean": 1, "n_ramp_min_mean": 0,
            "example_origin": r["origin"], "example_dest": r["dest"],
            "example_year": int(r["year"]), "example_month": int(r["month"]),
            "example_departures": float(r["departures_performed"]),
            "example_distance": float(r["distance"]),
            "example_airborne_min_mean": float(r["airborne_min_mean"]),
            "decision": "NOT EXCLUDED on its own (diagnostic only; see implied_speed_below_50mph "
                        "for the exclusion actually applied to this row, if any)",
        })

    # NOTE: outcome_data_quality_exclusions.csv is NOT written here. Per the
    # overseer's cycle-2 required action, a write-before-assert bug meant this
    # CSV could survive on disk even if the G8 RuntimeError below aborted the
    # run. dq_rows is held in memory and flushed to disk only after G8's
    # assertions pass (see "Write outcome_data_quality_exclusions.csv" below).

    # =====================================================================
    # Validity mask and baseline candidate pool.
    # =====================================================================
    panel = panel.reset_index(drop=True)
    panel["time_implausible_flag"] = implausible_speed
    valid = panel["cell_ok"] & panel["airborne_min_mean"].notna() & (~implausible_speed)
    logger.info("Valid measurement (cell_ok & airborne notna & implied speed >= %.0f mph or "
                "distance == 0): %d / %d rows (%.4f).", IMPLIED_SPEED_MPH_MIN,
                int(valid.sum()), len(panel), valid.sum() / len(panel))

    valid_df = panel.loc[valid, ["origin", "dest", "nation", "year", "month",
                                  "airborne_min_mean"]].rename(
        columns={"airborne_min_mean": "value"})
    dup_key = valid_df.duplicated(subset=["origin", "dest", "nation", "year", "month"]).sum()
    if dup_key:
        logger.error("G1 FAIL: %d duplicate (origin,dest,nation,year,month) keys among valid "
                      "cells -- panel_monthly's own key uniqueness must be broken.", dup_key)
        return 1

    key_cols = ["origin", "dest", "nation", "month"]
    cand = {}
    cand_covid = {}
    for k in BASELINE_LAG_YEARS:
        lookup = panel[key_cols].copy()
        lookup["year"] = panel["year"] - k
        merged = lookup.merge(valid_df, on=["origin", "dest", "nation", "year", "month"],
                               how="left")
        if len(merged) != len(panel):
            logger.error("G1 FAIL: baseline lookup merge for lag %d changed row count "
                          "(%d -> %d) -- a duplicate key crept into valid_df.",
                          k, len(panel), len(merged))
            return 1
        cflag = _covid_flag(lookup["year"].to_numpy(), lookup["month"].to_numpy())
        value = merged["value"].to_numpy()
        # G8: a COVID-window candidate month is never counted, regardless of validity.
        value = np.where(cflag, np.nan, value)
        cand[k] = value
        cand_covid[k] = cflag

    cand_arr = np.column_stack([cand[k] for k in BASELINE_LAG_YEARS])
    baseline_n = np.sum(~np.isnan(cand_arr), axis=1)
    with np.errstate(invalid="ignore"), warnings.catch_warnings():
        # All-NaN rows (no baseline candidates at all) correctly produce NaN via
        # nanmedian; numpy's "All-NaN slice encountered" RuntimeWarning for those
        # rows is expected here (there is no data to silently mask), not suppressed
        # elsewhere in this script.
        warnings.filterwarnings("ignore", message="All-NaN slice encountered")
        baseline_med_raw = np.nanmedian(cand_arr, axis=1)
        dev = np.abs(cand_arr - baseline_med_raw[:, None])
        baseline_mad_raw = np.nanmedian(dev, axis=1)
    ok2 = baseline_n >= 2
    baseline_med = np.where(ok2, baseline_med_raw, np.nan)
    baseline_mad = np.where(ok2, baseline_mad_raw, np.nan)

    # --- G8, asserted in code (raise on violation) --------------------------
    if np.any((baseline_n < 2) & ~np.isnan(baseline_med)):
        raise RuntimeError("G8 VIOLATED: a baseline_med was computed with < 2 observations.")
    for k in BASELINE_LAG_YEARS:
        bad = cand_covid[k] & ~np.isnan(cand[k])
        if np.any(bad):
            raise RuntimeError(
                f"G8 VIOLATED: {int(bad.sum())} baseline candidates at lag {k} years fall "
                f"inside the COVID window ({COVID_START}..{COVID_END}) and were not excluded.")
    logger.info("G8 holds (asserted in code): no baseline_med uses a COVID-window candidate; "
                "every computed baseline_med has >= 2 observations.")

    # --- Write outcome_data_quality_exclusions.csv (deferred until after G8 --
    # passes, per the overseer's write-before-assert finding; sample label
    # column added per the overseer's advisory).
    dq_df = pd.DataFrame(dq_rows)
    if len(dq_df):
        dq_df["sample"] = SAMPLE_LABEL
    dq_df.to_csv(DQ_EXCLUSIONS_CSV, index=False)
    logger.info("Wrote %s: %d rows.", DQ_EXCLUSIONS_CSV, len(dq_df))

    n_baseline_fail = int(np.sum(valid.to_numpy() & (baseline_n < 2)))
    n_valid = int(valid.sum())
    logger.info("Baseline failure (valid target cell, but baseline_n < 2): %d / %d valid "
                "cells (%.4f) -- reported as-is, not relaxed, in %s.",
                n_baseline_fail, n_valid,
                n_baseline_fail / n_valid if n_valid else float("nan"),
                BASELINE_FAILURES_CSV.name)

    panel["baseline_n"] = baseline_n
    panel["baseline_med"] = baseline_med
    panel["baseline_mad"] = baseline_mad

    # =====================================================================
    # Excess (raw), winsorized excess, z-score.
    # =====================================================================
    target_ok = valid.to_numpy() & ok2
    excess_min = np.where(target_ok, panel["airborne_min_mean"].to_numpy() - baseline_med, np.nan)
    panel["excess_min"] = excess_min

    grp = panel.groupby(["origin", "dest", "nation"])["excess_min"]
    q_lo = grp.transform(lambda s: s.quantile(WINSOR_LO))
    q_hi = grp.transform(lambda s: s.quantile(WINSOR_HI))
    panel["excess_min_w"] = panel["excess_min"].clip(lower=q_lo, upper=q_hi)
    n_winsorized = int(((panel["excess_min"] != panel["excess_min_w"])
                         & panel["excess_min"].notna()).sum())
    logger.info("Winsorized excess_min at [%.2f, %.2f] within (origin, dest, nation): "
                "%d / %d non-null rows moved.", WINSOR_LO, WINSOR_HI, n_winsorized,
                int(panel["excess_min"].notna().sum()))

    # --- excess_winsorization_cutoffs.csv (overseer cycle-2 blocking item 3: --
    # the round file's VERIFY says the cutoffs must be checkable against a
    # deliverable, not just recomputable from the log). One row per
    # (origin, dest, nation) directed route with a non-null excess_min: n,
    # p1, p99 (the actual clip boundaries applied), and n_clipped (rows
    # where excess_min_w != excess_min among that route's non-null cells).
    # Per the overseer's advisory, the note below is explicit that these
    # cutoffs are computed on the FULL 1990-2025 sample per route -- a 2022
    # cell's clip boundary can depend on that same route's 2025 data, since
    # winsorization is not done separately by year.
    cutoff_src = panel.loc[panel["excess_min"].notna(),
                            ["origin", "dest", "nation", "excess_min", "excess_min_w"]]
    winsor_cutoffs = (cutoff_src.groupby(["origin", "dest", "nation"])["excess_min"]
                       .agg(n="size", p1=lambda s: s.quantile(WINSOR_LO),
                            p99=lambda s: s.quantile(WINSOR_HI))
                       .reset_index())
    n_clipped_by_route = (cutoff_src.assign(
        clipped=cutoff_src["excess_min"] != cutoff_src["excess_min_w"])
        .groupby(["origin", "dest", "nation"])["clipped"].sum().reset_index()
        .rename(columns={"clipped": "n_clipped"}))
    winsor_cutoffs = winsor_cutoffs.merge(n_clipped_by_route, on=["origin", "dest", "nation"],
                                           how="left")
    winsor_cutoffs["cutoff_computed_on"] = "full 1990-2025 sample for this route (not by-year)"
    winsor_cutoffs["sample"] = SAMPLE_LABEL
    winsor_cutoffs = winsor_cutoffs.sort_values(["origin", "dest", "nation"]).reset_index(drop=True)
    winsor_cutoffs.to_csv(WINSOR_CUTOFFS_CSV, index=False)
    logger.info("Wrote %s: %d (origin, dest, nation) routes.", WINSOR_CUTOFFS_CSV,
                len(winsor_cutoffs))
    assert int(winsor_cutoffs["n_clipped"].sum()) == n_winsorized, (
        "excess_winsorization_cutoffs.csv's own n_clipped sum must reconcile with "
        "n_winsorized -- both count the same clipped rows two different ways.")

    zero_mad = target_ok & (baseline_mad == 0)
    n_zero_mad = int(zero_mad.sum())
    with np.errstate(divide="ignore", invalid="ignore"):
        excess_z = np.where(target_ok, excess_min / baseline_mad, np.nan)
    excess_z = np.where(zero_mad, np.nan, excess_z)
    panel["excess_z"] = excess_z
    logger.info("excess_z: %d rows had baseline_mad == 0 (set to NaN rather than +-inf); "
                "%d rows are non-null.", n_zero_mad, int(panel["excess_z"].notna().sum()))

    # --- Bidirectional sum: excess_min_w(A->B) + excess_min_w(B->A) --------
    rev = panel[["origin", "dest", "nation", "year", "month", "excess_min_w"]].rename(
        columns={"origin": "dest", "dest": "origin", "excess_min_w": "excess_min_w_rev"})
    merged_bidir = panel[["origin", "dest", "nation", "year", "month"]].merge(
        rev, on=["origin", "dest", "nation", "year", "month"], how="left")
    if len(merged_bidir) != len(panel):
        logger.error("G1 FAIL: bidirectional self-merge changed row count (%d -> %d).",
                      len(panel), len(merged_bidir))
        return 1
    panel["bidir_sum"] = panel["excess_min_w"].to_numpy() + merged_bidir["excess_min_w_rev"].to_numpy()
    n_bidir = int(panel["bidir_sum"].notna().sum())
    logger.info("bidir_sum non-null (both directed legs present): %d / %d rows (%.4f).",
                n_bidir, len(panel), n_bidir / len(panel))

    # =====================================================================
    # excess_construction_diagnostics.csv -- overseer cycle-2 required
    # actions: (3) n_winsorized/n_zero_mad were log-only (G9: not citable);
    # (4) excess_z's MAD comes from at most 3 candidates, making it a
    # near-degenerate statistic -- |z| > 100 and |z| > 1000 counts go here
    # rather than only in the formula-text caveat; advisory: report the
    # panel's own "baseline_n >= 2" denominator both unconditionally (every
    # row for which SOME cell's baseline succeeded, whether or not that row
    # is itself a valid target) and restricted to valid targets (the subset
    # that actually gets a non-null excess_min) -- these are two different
    # numbers and conflating them is a citation error.
    # =====================================================================
    abs_z = panel["excess_z"].abs()
    n_z_gt_100 = int((abs_z > 100).sum())
    n_z_gt_1000 = int((abs_z > 1000).sum())
    n_baseline_ge2_any_row = int((panel["baseline_n"] >= 2).sum())
    n_baseline_ge2_valid_target = int(panel.loc[valid, "baseline_n"].ge(2).sum())
    assert n_baseline_ge2_valid_target == int(panel["excess_min"].notna().sum()), (
        "baseline_n>=2 among valid targets must equal the non-null excess_min count "
        "by construction -- these are two ways of counting the same rows.")

    construction_diag = pd.DataFrame([{
        "metric": "n_valid_measurement", "value": int(valid.sum()),
        "note": "cell_ok & airborne_min_mean notna & implied speed >= "
                f"{IMPLIED_SPEED_MPH_MIN:.0f} mph or distance == 0",
    }, {
        "metric": "n_baseline_ge2_any_row", "value": n_baseline_ge2_any_row,
        "note": "rows where SOME cell's 3-year same-month baseline had >= 2 candidates, "
                "regardless of whether this row's OWN measurement is a valid target",
    }, {
        "metric": "n_baseline_ge2_valid_target", "value": n_baseline_ge2_valid_target,
        "note": "subset of the above that is ALSO a valid target -- equals n_obs for "
                "excess_min in desc_outcomes.csv; this is the correct denominator for "
                "'cells with a computed excess value'",
    }, {
        "metric": "n_winsorized_rows", "value": n_winsorized,
        "note": "non-null excess_min rows where excess_min_w != excess_min "
                "(1st/99th percentile clip, within route x nation, applied)",
    }, {
        "metric": "n_zero_mad_rows", "value": n_zero_mad,
        "note": "valid-target rows with baseline_mad == 0 -- excess_z set to NaN here "
                "rather than a fabricated +-inf",
    }, {
        "metric": "n_bidir_sum_nonnull", "value": n_bidir,
        "note": "both directed legs (A->B and B->A) present in the same nation/year/month",
    }, {
        "metric": "n_excess_z_abs_gt_100", "value": n_z_gt_100,
        "note": "excess_z magnitude > 100 -- see the excess_z formula-text caveat: MAD is "
                "computed from at most 3 baseline candidates and can be near-zero by chance, "
                "making excess_z read as an enormous anomaly for an ordinary excess_min value",
    }, {
        "metric": "n_excess_z_abs_gt_1000", "value": n_z_gt_1000,
        "note": "excess_z magnitude > 1000 -- same caveat, more extreme",
    }, {
        "metric": "n_implied_speed_below_50mph", "value": n_implausible,
        "note": "flagged by the implied-speed screen (panel-wide, not just cell_ok)",
    }, {
        "metric": "n_implied_speed_below_50mph_cell_ok", "value": n_implausible_cellok,
        "note": "same, restricted to cell_ok cells",
    }, {
        "metric": "n_distance_zero_cell_ok", "value": len(dist0_cellok),
        "note": "kept, not excluded -- implied speed undefined, see DATA-QUALITY SCREEN",
    }, {
        "metric": "n_diagnostic_gt_1000min_per_dep_cell_ok", "value": n_diag_gt1000_cellok,
        "note": "NOT an exclusion criterion on its own -- see outcome_data_quality_exclusions.csv",
    }])
    construction_diag["sample"] = SAMPLE_LABEL
    construction_diag.to_csv(CONSTRUCTION_DIAG_CSV, index=False)
    logger.info("Wrote %s: %d rows.", CONSTRUCTION_DIAG_CSV, len(construction_diag))

    # =====================================================================
    # excess_speed_screen_sensitivity.csv -- overseer cycle-2 blocking item 2:
    # winsorization does not remove the measurement contamination from
    # implied-speed values just above the shipped 50 mph floor (1,171
    # surviving cells imply < 150 mph, carrying 58.7% of sum(excess_min_w)
    # despite being 0.30% of the sample). The threshold is NOT changed here
    # (that would be an unauthorized re-specification) -- this is additive
    # sensitivity reporting only, for the director/human to rule on. The 50
    # mph row reuses the ACTUAL shipped excess_min_w column (not a
    # recomputation), so it cannot drift from what was shipped; 100/150/200
    # mph rows use _recompute_excess_min_w with a stricter valid mask. A
    # symmetric upper-speed diagnostic (implied speed > 700 mph, an
    # under-reported AIR_TIME reading as a spurious speed-up) is reported
    # alongside -- constant across rows because a stricter LOWER bound never
    # removes a HIGH-speed cell.
    # =====================================================================
    decade_arr = (panel["year"] // 10 * 10).astype(int)

    def _stats_rows(threshold_mph, valid_t, excess_w_arr):
        rows = []
        n_speed_gt_upper = int((valid_t.to_numpy() & finite_mask.to_numpy()
                                 & (implied_speed_mph.to_numpy() > UPPER_SPEED_DIAG_MPH)).sum())
        s_full = pd.Series(excess_w_arr, index=panel.index)
        for dec_label, mask in [("all", pd.Series(True, index=panel.index))] + [
                (int(d), decade_arr == d) for d in sorted(decade_arr.unique())]:
            vals = s_full.loc[mask].dropna()
            row = {
                "screen_mph": threshold_mph, "decade": dec_label,
                "n_valid_measurement": int((valid_t & mask).sum()),
                "n_excess_computed": int(len(vals)),
                "n_speed_gt_%dmph_diagnostic" % int(UPPER_SPEED_DIAG_MPH): n_speed_gt_upper,
            }
            if len(vals):
                qs = vals.quantile([0.01, 0.50, 0.99])
                row.update({"mean": vals.mean(), "sd": vals.std(),
                            "p1": qs.loc[0.01], "p50": qs.loc[0.50], "p99": qs.loc[0.99],
                            "sum_excess_min_w": vals.sum()})
            else:
                row.update({"mean": np.nan, "sd": np.nan, "p1": np.nan, "p50": np.nan,
                            "p99": np.nan, "sum_excess_min_w": np.nan})
            rows.append(row)
        return rows

    sensitivity_rows = []
    for t in SPEED_SENSITIVITY_THRESHOLDS_MPH:
        if t == IMPLIED_SPEED_MPH_MIN:
            valid_t = valid  # reuse the ACTUAL shipped mask/column -- no recomputation
            excess_w_t = panel["excess_min_w"].to_numpy()
        else:
            implausible_t = finite_mask & (implied_speed_mph < t)
            valid_t = panel["cell_ok"] & has_air & (~implausible_t)
            excess_w_t = _recompute_excess_min_w(panel, valid_t)
        for row in _stats_rows(t, valid_t, excess_w_t):
            row["method"] = "full_recompute_stricter_valid_mask"
            sensitivity_rows.append(row)

    # --- Second method: NAIVE filter of the ACTUAL SHIPPED excess_min_w -----
    # series (drop cells implying < t mph, do NOT re-run baselines/winsorize).
    # This reproduces the overseer's own cycle-2 diagnostic exactly (1,171
    # cells < 150 mph / -59% mean shift / 58.7% of sum(excess_min_w)) --
    # included alongside the full-recompute method above because the two
    # answer different questions ("how much does just discarding the
    # contaminated tail change the CURRENT estimate" vs "what would a
    # properly re-estimated system look like under a stricter screen") and
    # a reader checking this CSV against the review should be able to find
    # both without doing the arithmetic themselves.
    shipped_w = panel["excess_min_w"]
    for t in SPEED_SENSITIVITY_THRESHOLDS_MPH:
        contaminated = shipped_w.notna() & finite_mask & (implied_speed_mph < t)
        kept_series = shipped_w.where(~contaminated)
        n_speed_gt_upper = int((shipped_w.notna() & finite_mask
                                 & (implied_speed_mph > UPPER_SPEED_DIAG_MPH)).sum())
        for dec_label, mask in [("all", pd.Series(True, index=panel.index))] + [
                (int(d), decade_arr == d) for d in sorted(decade_arr.unique())]:
            vals = kept_series.loc[mask].dropna()
            row = {
                "screen_mph": t, "decade": dec_label, "method": "naive_filter_shipped_series",
                "n_valid_measurement": pd.NA,
                "n_excess_computed": int(len(vals)),
                "n_speed_gt_%dmph_diagnostic" % int(UPPER_SPEED_DIAG_MPH): n_speed_gt_upper,
                "n_removed_from_shipped_series": int((contaminated & mask).sum()),
            }
            if len(vals):
                qs = vals.quantile([0.01, 0.50, 0.99])
                row.update({"mean": vals.mean(), "sd": vals.std(),
                            "p1": qs.loc[0.01], "p50": qs.loc[0.50], "p99": qs.loc[0.99],
                            "sum_excess_min_w": vals.sum()})
            else:
                row.update({"mean": np.nan, "sd": np.nan, "p1": np.nan, "p50": np.nan,
                            "p99": np.nan, "sum_excess_min_w": np.nan})
            sensitivity_rows.append(row)

    sensitivity_df = pd.DataFrame(sensitivity_rows)
    sensitivity_df["sample"] = SAMPLE_LABEL
    sensitivity_df["note"] = ("distance == 0 cells remain exempt from the speed test at "
                               "every threshold shown (unchanged decision, see "
                               "DATA-QUALITY SCREEN); threshold NOT changed from the "
                               f"shipped {IMPLIED_SPEED_MPH_MIN:.0f} mph -- for sensitivity "
                               "reporting only. method == 'full_recompute_stricter_valid_mask' "
                               "re-runs the entire baseline/excess/winsorize pipeline with a "
                               "stricter validity gate (also cleans contaminated candidates "
                               "out of OTHER cells' baselines); method == "
                               "'naive_filter_shipped_series' instead just drops the flagged "
                               "cells from the ACTUAL SHIPPED excess_min_w series with no "
                               "recomputation -- this is the version that reproduces the "
                               "overseer's cycle-2 diagnostic numbers exactly.")
    sensitivity_df.to_csv(SPEED_SENSITIVITY_CSV, index=False)
    logger.info("Wrote %s: %d rows (%d thresholds x pooled+by-decade x 2 methods).",
                SPEED_SENSITIVITY_CSV, len(sensitivity_df),
                len(SPEED_SENSITIVITY_THRESHOLDS_MPH))

    shipped_row = sensitivity_df.loc[
        (sensitivity_df["method"] == "full_recompute_stricter_valid_mask")
        & (sensitivity_df["screen_mph"] == IMPLIED_SPEED_MPH_MIN)
        & (sensitivity_df["decade"] == "all")].iloc[0]
    assert shipped_row["n_excess_computed"] == int(panel["excess_min"].notna().sum()), (
        "the sensitivity CSV's shipped-threshold pooled row must reconcile exactly with "
        "the actual shipped excess_min non-null count.")
    logger.info("Sensitivity-CSV shipped-threshold (%.0f mph) pooled row reconciles "
                "exactly with the shipped excess_min/excess_min_w columns (n=%d, "
                "mean=%.5f).", IMPLIED_SPEED_MPH_MIN, int(shipped_row["n_excess_computed"]),
                float(shipped_row["mean"]))

    naive_check = sensitivity_df.loc[(sensitivity_df["method"] == "naive_filter_shipped_series")
                                      & (sensitivity_df["screen_mph"] == 150.0)
                                      & (sensitivity_df["decade"] == "all")].iloc[0]
    assert int(naive_check["n_removed_from_shipped_series"]) == 1171, (
        "naive-filter <150mph removed-row count must reconcile with the overseer's cycle-2 "
        "cited figure (1,171) -- it does not.")
    logger.info("Naive-filter sensitivity (method=naive_filter_shipped_series, 150 mph, "
                "pooled) reconciles with the overseer's cycle-2 diagnostic: n_removed=%d, "
                "mean after removal=%.5f (was %.5f shipped).",
                int(naive_check["n_removed_from_shipped_series"]), float(naive_check["mean"]),
                float(shipped_row["mean"]))

    # =====================================================================
    # G1/G5 sanity + write panel_excess.parquet
    # =====================================================================
    if panel[["origin", "dest", "nation", "year", "month"]].isna().any().any():
        logger.error("G1 FAIL: null values in the cell key.")
        return 1
    if panel.duplicated(subset=["origin", "dest", "nation", "year", "month"]).sum():
        logger.error("G1 FAIL: duplicate cell keys in panel_excess.")
        return 1
    logger.info("G1 pass: no null/duplicate cell keys.")

    panel.to_parquet(PANEL_EXCESS_PARQUET, index=False)
    logger.info("Wrote %s: %d rows.", PANEL_EXCESS_PARQUET, len(panel))

    # =====================================================================
    # baseline_failures.csv — cells with baseline_n < 2, by nation x year
    # (restricted to cells with a valid target measurement, i.e. cells for
    # which we would otherwise have computed an excess value).
    #
    # Overseer cycle-2 required action (blocking item 1b): the round's most
    # consequential fact -- WHICH months have zero computable excess cells,
    # not just which YEARS have a high failure share -- has no trace at
    # annual resolution (2022 and 2023 both show ~87% failure, which reads as
    # "mostly missing" rather than "entirely missing in 20 of 24 months,
    # recovering only in Jan/Feb of each year"). Month-resolution rows are
    # added below (granularity == 'month') alongside the original
    # nation x year rows (granularity == 'year'), both restricted to the
    # same valid-target population, so "0 computable excess cells in month
    # X" is a citable (file.csv, row) trace under G9. n_excess_computed is
    # added explicitly (= n_valid_cells - n_baseline_fail) so a zero is
    # visible without subtracting two other columns by hand.
    # =====================================================================
    fail_mask = valid & (panel["baseline_n"] < 2)
    by_ny = (panel.loc[valid].assign(fail=fail_mask.loc[valid])
             .groupby(["nation", "year"])
             .agg(n_valid_cells=("fail", "size"), n_baseline_fail=("fail", "sum"))
             .reset_index())
    by_ny["baseline_fail_share"] = by_ny["n_baseline_fail"] / by_ny["n_valid_cells"]
    by_ny["n_excess_computed"] = by_ny["n_valid_cells"] - by_ny["n_baseline_fail"]
    by_ny["granularity"] = "year"
    by_ny["month"] = pd.NA

    by_nym = (panel.loc[valid].assign(fail=fail_mask.loc[valid])
              .groupby(["nation", "year", "month"])
              .agg(n_valid_cells=("fail", "size"), n_baseline_fail=("fail", "sum"))
              .reset_index())
    by_nym["baseline_fail_share"] = by_nym["n_baseline_fail"] / by_nym["n_valid_cells"]
    by_nym["n_excess_computed"] = by_nym["n_valid_cells"] - by_nym["n_baseline_fail"]
    by_nym["granularity"] = "month"

    col_order = ["granularity", "nation", "year", "month", "n_valid_cells",
                 "n_baseline_fail", "baseline_fail_share", "n_excess_computed"]
    baseline_failures = pd.concat([by_ny[col_order], by_nym[col_order]],
                                   ignore_index=True)
    baseline_failures["sample"] = SAMPLE_LABEL

    # Sanity cross-check: for every (nation, year), the sum of n_valid_cells
    # across that year's 'month' rows must equal the 'year' row's own value
    # (both are drawn from the identical `valid` mask, just grouped
    # differently) -- an actual assertion, not a claim.
    year_check = (by_nym.groupby(["nation", "year"])["n_valid_cells"].sum()
                  .reset_index().rename(columns={"n_valid_cells": "n_from_months"}))
    check = by_ny.merge(year_check, on=["nation", "year"], how="left")
    mismatch = check.loc[check["n_valid_cells"] != check["n_from_months"]]
    if len(mismatch):
        logger.error("G1 FAIL: %d nation x year rows in baseline_failures.csv don't "
                      "reconcile with the sum of their own month-level rows.", len(mismatch))
        return 1
    logger.info("baseline_failures.csv month/year reconciliation holds (%d nation x year "
                "groups checked).", len(check))

    zero_months = by_nym.loc[by_nym["n_excess_computed"] == 0]
    logger.info("Month-resolution zero-computable-excess cells (US, valid-target "
                "population): %d of %d (nation, year, month) rows have "
                "n_excess_computed == 0; see %s for the exact list (this is what "
                "'baseline failure share' looks like at the resolution the design "
                "actually needs).", len(zero_months), len(by_nym), BASELINE_FAILURES_CSV.name)

    baseline_failures.to_csv(BASELINE_FAILURES_CSV, index=False)
    logger.info("Wrote %s: %d rows (%d nation x year + %d nation x year x month).",
                BASELINE_FAILURES_CSV, len(baseline_failures), len(by_ny), len(by_nym))

    # =====================================================================
    # desc_outcomes.csv — formulas as text + distribution moments by decade
    # =====================================================================
    formulas = {
        "excess_min": (
            "airborne_min_mean(cell) - baseline_med(cell). baseline_med = median of "
            "airborne_min_mean for the SAME (origin, dest, nation) directed route in the "
            "SAME calendar month, at year-1/year-2/year-3 (trailing 3 years = trailing 36 "
            "months), among cells passing cell_ok (FIX-04 G6 nation-year coverage >= 0.50 "
            "AND departures_performed >= 4) with an implied speed (distance / airborne "
            "hours) >= 50 mph, or distance == 0 (exempt from the speed test); a "
            "candidate month inside the COVID window 2020-03..2021-12 is "
            "never counted; requires >= 2 surviving candidates, else NaN (G8)."
        ),
        "excess_min_w": (
            "excess_min, winsorized (clipped) at the 1st/99th percentile computed within "
            "each (origin, dest, nation) directed-route group, using ALL non-null "
            "excess_min for that route across the full 1990-2025 sample (not separately "
            "by year) -- a 2022 cell's clip boundary can therefore depend on that same "
            "route's 2025 data. See excess_winsorization_cutoffs.csv for the per-route "
            "n/p1/p99/n_clipped actually applied, and "
            "excess_speed_screen_sensitivity.csv for how much the pooled mean/p1/p99 "
            "move if the implied-speed screen is tightened beyond the shipped 50 mph "
            "(winsorization alone does not remove the measurement contamination just "
            "above 50 mph: cells implying < 150 mph are 0.30% of the sample but a "
            "majority of sum(excess_min_w) -- see that CSV)."
        ),
        "excess_z": (
            "excess_min / baseline_mad, where baseline_mad = median absolute deviation "
            "(around baseline_med) of the same up-to-3 baseline candidates used for "
            "baseline_med. NaN when baseline_mad == 0 (never divided, to avoid a "
            "fabricated +-inf). CAVEAT (overseer cycle-2 finding): with at most 3 "
            "candidates, baseline_mad is itself a near-degenerate statistic that can be "
            "small by chance, so excess_z routinely reads as an enormous anomaly (p99 "
            "roughly 84, some cells beyond |z|=1000) for an excess_min value that is "
            "itself unremarkable. This column should NOT be read as a conventional "
            "z-score / cited as evidence of anomaly magnitude without first checking "
            "excess_min and baseline_mad directly; see "
            "excess_construction_diagnostics.csv for |z|>100 and |z|>1000 counts. "
            "Treat as NOT-FOR-USE pending a director-commissioned dispersion measure "
            "with a larger candidate pool."
        ),
        "bidir_sum": (
            "excess_min_w(origin->dest, nation, year, month) + "
            "excess_min_w(dest->origin, nation, year, month) for the SAME nation/year/month; "
            "NaN if either directed leg is missing (never imputed)."
        ),
    }
    decade = (panel["year"] // 10 * 10).astype(int)
    panel["_decade"] = decade
    moment_cols = ["p1", "p5", "p50", "p95", "p99", "mean", "sd"]
    desc_rows = []
    for outcome in ["excess_min", "excess_min_w", "excess_z", "bidir_sum"]:
        for dec, sub in panel.groupby("_decade"):
            vals = sub[outcome].dropna()
            row = {"outcome": outcome, "formula": formulas[outcome], "sample": SAMPLE_LABEL,
                   "decade": int(dec), "n_obs": int(len(vals))}
            if len(vals):
                qs = vals.quantile([0.01, 0.05, 0.50, 0.95, 0.99])
                row.update({
                    "p1": qs.loc[0.01], "p5": qs.loc[0.05], "p50": qs.loc[0.50],
                    "p95": qs.loc[0.95], "p99": qs.loc[0.99],
                    "mean": vals.mean(), "sd": vals.std(),
                })
            else:
                row.update({c: np.nan for c in moment_cols})
            desc_rows.append(row)
        vals_all = panel[outcome].dropna()
        row = {"outcome": outcome, "formula": formulas[outcome], "sample": SAMPLE_LABEL,
               "decade": "all", "n_obs": int(len(vals_all))}
        if len(vals_all):
            qs = vals_all.quantile([0.01, 0.05, 0.50, 0.95, 0.99])
            row.update({
                "p1": qs.loc[0.01], "p5": qs.loc[0.05], "p50": qs.loc[0.50],
                "p95": qs.loc[0.95], "p99": qs.loc[0.99],
                "mean": vals_all.mean(), "sd": vals_all.std(),
            })
        else:
            row.update({c: np.nan for c in moment_cols})
        desc_rows.append(row)
    panel = panel.drop(columns=["_decade"])
    desc_df = pd.DataFrame(desc_rows, columns=["outcome", "formula", "sample", "decade",
                                                "n_obs"] + moment_cols)
    desc_df.to_csv(DESC_OUTCOMES_CSV, index=False)
    logger.info("Wrote %s: %d rows.", DESC_OUTCOMES_CSV, len(desc_df))

    # --- G1/G5 sanity on desc_outcomes.csv (no coef column, but check n_obs) --
    if (desc_df["n_obs"] < 0).any():
        logger.error("G1 FAIL: negative n_obs in desc_outcomes.csv.")
        return 1

    # =====================================================================
    # figures/fig_excess_distribution.png
    # =====================================================================
    pooled = panel["excess_min_w"].dropna()
    y2022_mask = panel["year"] == 2022
    y2022 = panel.loc[y2022_mask, "excess_min_w"].dropna()
    pooled_q = pooled.quantile([WINSOR_LO, WINSOR_HI]) if len(pooled) else None

    # Overseer cycle-2 blocking item 1a: this panel's cells are NOT a random
    # or full-year sample of 2022 -- the 1/2/3-year lag structure plus the
    # 22-month COVID bar (2020-03..2021-12) means 2022-03 onward has ZERO
    # computable excess_min cells (see baseline_failures.csv, granularity ==
    # 'month', n_excess_computed == 0 for those rows) -- i.e. every cell in
    # this panel is from BEFORE the February 2022 event this paper studies.
    # Determine which months are actually present (rather than hardcoding
    # "Jan-Feb") so the title cannot silently go stale if that changes.
    months_present = sorted(panel.loc[y2022_mask & panel["excess_min_w"].notna(),
                                       "month"].unique().tolist())
    if months_present == list(range(min(months_present), max(months_present) + 1)) and months_present:
        month_names = {1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
                        7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec"}
        span = (f"{month_names[months_present[0]]}"
                if len(months_present) == 1
                else f"{month_names[months_present[0]]}-{month_names[months_present[-1]]}")
    else:
        span = ",".join(str(m) for m in months_present) if months_present else "none"
    # Describe the zero-computable-month pattern from the data itself (do
    # not hand-type a date range): most of 2022-03..2023-12 has 0 computable
    # excess_min cells, but Jan/Feb of each year briefly recover (their
    # year-3 lag reaches back to Jan/Feb 2020, which sits just outside the
    # COVID window) before March again loses both the year-2 AND year-3
    # candidate to the window. See baseline_failures.csv (granularity ==
    # 'month') for the exact by-month counts this describes.
    window_months = panel.loc[panel["year"].isin([2022, 2023]), ["year", "month"]].drop_duplicates()
    zero_ym = []
    nonzero_ym = []
    for _, r in window_months.sort_values(["year", "month"]).iterrows():
        n_nonnull = int(panel.loc[(panel["year"] == r["year"]) & (panel["month"] == r["month"]),
                                   "excess_min"].notna().sum())
        (zero_ym if n_nonnull == 0 else nonzero_ym).append(f"{int(r['year'])}-{int(r['month']):02d}")
    # Keep the ax title SHORT (matplotlib does not wrap ax titles, and a long
    # one overflows into the neighboring subplot -- exactly the clipping
    # defect flagged in a prior round); the full month-by-month accounting
    # (which specific months are zero vs. non-zero) is logged and lives in
    # baseline_failures.csv (granularity == 'month'), not crammed into the
    # figure.
    right_title = (
        f"2022, {span} ONLY (n={len(y2022):,}) -- entirely BEFORE the Feb-2022 event\n"
        f"2022-03..2023-12 mostly unobservable: only {len(nonzero_ym)}/24 months in "
        "2022-2023 have any computable excess_min (see baseline_failures.csv)"
    )
    logger.info("Right-panel month accounting: non-zero months = %s; zero months (%d) = %s.",
                nonzero_ym, len(zero_ym), zero_ym)

    fig, axes = plt.subplots(1, 2, figsize=(14, 7))
    titles = (f"Pooled, all years (n={len(pooled):,})", right_title)
    title_sizes = (10, 9)
    for ax, data, title, tsize in zip(axes, (pooled, y2022), titles, title_sizes):
        if len(data):
            ax.hist(data, bins=80, color="#4c72b0", edgecolor="none")
            if pooled_q is not None:
                ax.axvline(pooled_q.loc[WINSOR_LO], color="firebrick", linestyle="--",
                            linewidth=1.2, label=f"pooled p1={pooled_q.loc[WINSOR_LO]:.1f}")
                ax.axvline(pooled_q.loc[WINSOR_HI], color="firebrick", linestyle="--",
                            linewidth=1.2, label=f"pooled p99={pooled_q.loc[WINSOR_HI]:.1f}")
            ax.legend(fontsize=8, loc="upper right")
        ax.set_title(title, fontsize=tsize, wrap=True)
        ax.set_xlabel("excess_min_w (minutes)")
        ax.set_ylabel("count of cells")
    fig.suptitle(
        f"Excess airborne minutes (winsorized 1/99 within route x nation) -- {SAMPLE_LABEL}\n"
        "Dashed lines mark the POOLED p1/p99 for visual reference only -- winsorization "
        "itself is applied per (origin, dest, nation) directed route, not pooled.",
        fontsize=10, y=0.99)
    fig.tight_layout(rect=(0, 0, 1, 0.80))
    fig.subplots_adjust(top=0.78, wspace=0.28)
    fig.savefig(FIG_PNG, dpi=150)
    plt.close(fig)
    logger.info("Wrote %s.", FIG_PNG)

    logger.info("DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
