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
FIG_PNG = OUT_DIR / "figures" / "fig_excess_distribution.png"
LOG_FILE = ROOT / "logs" / "05_build_excess.log"

# --- Constants -------------------------------------------------------------
COVID_START = (2020, 3)   # inclusive
COVID_END = (2021, 12)    # inclusive
IMPLIED_SPEED_MPH_MIN = 50.0  # no scheduled passenger aircraft cruises below this
DIAGNOSTIC_ONLY_MIN_PER_DEP = 1000.0  # reported, not used for exclusion
BASELINE_LAG_YEARS = (1, 2, 3)
WINSOR_LO, WINSOR_HI = 0.01, 0.99
SAMPLE_LABEL = "US carriers' airborne time on US-touching international segments"


def _covid_flag(year, month):
    year = np.asarray(year)
    month = np.asarray(month)
    lo = (year > COVID_START[0]) | ((year == COVID_START[0]) & (month >= COVID_START[1]))
    hi = (year < COVID_END[0]) | ((year == COVID_END[0]) & (month <= COVID_END[1]))
    return lo & hi


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

    pd.DataFrame(dq_rows).to_csv(DQ_EXCLUSIONS_CSV, index=False)
    logger.info("Wrote %s: %d rows.", DQ_EXCLUSIONS_CSV, len(dq_rows))

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
    # =====================================================================
    fail_mask = valid & (panel["baseline_n"] < 2)
    by_ny = (panel.loc[valid].assign(fail=fail_mask.loc[valid])
             .groupby(["nation", "year"])
             .agg(n_valid_cells=("fail", "size"), n_baseline_fail=("fail", "sum"))
             .reset_index())
    by_ny["baseline_fail_share"] = by_ny["n_baseline_fail"] / by_ny["n_valid_cells"]
    by_ny["sample"] = SAMPLE_LABEL
    by_ny.to_csv(BASELINE_FAILURES_CSV, index=False)
    logger.info("Wrote %s: %d nation x year rows.", BASELINE_FAILURES_CSV, len(by_ny))

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
            "each (origin, dest, nation) directed-route group."
        ),
        "excess_z": (
            "excess_min / baseline_mad, where baseline_mad = median absolute deviation "
            "(around baseline_med) of the same up-to-3 baseline candidates used for "
            "baseline_med. NaN when baseline_mad == 0 (never divided, to avoid a "
            "fabricated +-inf)."
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
    y2022 = panel.loc[panel["year"] == 2022, "excess_min_w"].dropna()
    pooled_q = pooled.quantile([WINSOR_LO, WINSOR_HI]) if len(pooled) else None

    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    for ax, data, title in ((axes[0], pooled, f"Pooled, all years (n={len(pooled):,})"),
                             (axes[1], y2022, f"2022 only (n={len(y2022):,})")):
        if len(data):
            ax.hist(data, bins=80, color="#4c72b0", edgecolor="none")
            if pooled_q is not None:
                ax.axvline(pooled_q.loc[WINSOR_LO], color="firebrick", linestyle="--",
                            linewidth=1.2, label=f"pooled p1={pooled_q.loc[WINSOR_LO]:.1f}")
                ax.axvline(pooled_q.loc[WINSOR_HI], color="firebrick", linestyle="--",
                            linewidth=1.2, label=f"pooled p99={pooled_q.loc[WINSOR_HI]:.1f}")
            ax.legend(fontsize=8, loc="upper right")
        ax.set_title(title, fontsize=10)
        ax.set_xlabel("excess_min_w (minutes)")
        ax.set_ylabel("count of cells")
    fig.suptitle(
        f"Excess airborne minutes (winsorized 1/99 within route x nation) -- {SAMPLE_LABEL}\n"
        "Dashed lines mark the POOLED p1/p99 for visual reference only -- winsorization "
        "itself is applied per (origin, dest, nation) directed route, not pooled.",
        fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(FIG_PNG, dpi=150)
    plt.close(fig)
    logger.info("Wrote %s.", FIG_PNG)

    logger.info("DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
