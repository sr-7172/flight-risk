#!/usr/bin/env python3
"""06_wedge_availability.py — NEW-06, REDUCED FORM ordered by the overseer.

Two-sentence summary: NEW-06 was commissioned to plot mean airborne minutes
by operator nationality on four US-international corridors around the
February-2022 Russian-overflight ban, but T-100 international data shows
foreign carriers (CARRIER_GROUP == 0) report a literal zero airborne
minutes in 100% of segment-months across all 36 years on file, so the
non-US side of every corridor comparison is structurally empty rather than
noisy or small; this script therefore ships the honest substitute the
overseer specified -- a full corridor x nation x month completeness record
(nulls included), a NEVER-PLOT diff CSV that proves the wedge computation
is empty by construction, a data-availability figure showing exactly which
cells have observable airborne time, and (extensive margin only, which BTS
records for all 93 operator nations) a departures/route-count picture --
and explicitly does NOT produce any of the five prohibited cross-national
wedge figures.

GOVERNING FACTS (established independently in FIX-03/04/05, re-verified
below at runtime, never assumed):
  - CARRIER_GROUP == 0 (foreign carriers) never reports AIR_TIME > 0:
    1,133,545 raw segment-months, 0 non-zero, 0 null -- every value a
    literal 0.00 (03b_carrier_group_coverage.py). This is BTS's T-100 vs
    T-100(f) reporting schedule, not a property of this download.
  - Consequently panel_excess.parquet has airborne_min_mean non-null and
    coverage_ok == True ONLY for nation == 'US' (05_build_excess.py's own
    governing-fact re-check; re-asserted below).
  - The surviving US excess series has two ten-month blackouts,
    2022-03..2022-12 and 2023-03..2023-12 (FIX-05 cycle 2, overseer-
    corrected wording), because the trailing-3-year/COVID-excluded
    baseline needs >= 2 candidates and Jan/Feb of each year are the only
    months whose year-3 lag reaches back to Jan/Feb 2020, just outside the
    COVID bar.

PROHIBITED (per the overseer's ruling on this task; never produced here):
  figures/fig_raw_wedge_useastasia.png, _usindia.png, _usmideast.png,
  _useurope_placebo.png, _bidir.png. No foreign air time is imputed, no
  proxy outcome is substituted, no cross-national comparison is presented.

CORRIDOR 1 / ICN CAVEAT (binding while FIX-02 is BLOCKED-NEEDS-HUMAN):
  operator-nation match precision at ICN is far below every other NEW-06
  anchor (carrier_nation_corridor_coverage.csv), driven by Asiana's absence
  from the matched population. useastasia rows below carry an explicit
  fix02_caveat string and MUST NOT be read as a headline result.

CYCLE-2 FIXES (overseer FAIL, three blocking items, all additive -- no
shipped number from cycle 1 was wrong):
  B1) raw_wedge_diffs.csv's mean_excess_* columns are renamed with an
      unmistakable _NOT_A_RESULT / _US_ONLY suffix in the header itself
      (not just in the prose definition column), and a runtime assert now
      refuses to write the file if any mean_excess_* value is non-null for
      a group whose *_with_data count exceeds 1 -- the file's only content
      besides the always-null diff should ever be a single-nation (US)
      series while FIX-02 is blocked.
  B2) the diffs computation now actually weights nation-pooling by summed
      departures_airborne_eligible (matching what the definition column
      claims), not by the cell count n_cells_excess_valid as cycle 1 did --
      the two coincided only because at most one nation ever has data.
  B3) a raw-level US-only figure (departures-weighted mean
      airborne_min_mean by corridor x month, 2x2, same layout/annotations)
      is added ALONGSIDE the excess-level one, not in place of it -- the
      excess panel is blank for 20 of the 24 event-window months by
      construction (FIX-05's blackout), and the raw-level panel is the one
      outcome this round can actually observe across that window.
  Advisories also addressed: departures_performed_month_sum / route counts
  in raw_wedge_by_corridor.csv are MATCHED-CARRIER-ONLY (FIX-02 mapped);
  per-corridor unmatched shares are computed live against t100_raw.parquet
  and logged/carried as a note column. The extensive-margin seasonality
  caveat (FIX-04's extensive_margin_churn.csv) travels with the departure
  counts. Two known false-zero cells against raw T-100 (useurope_placebo
  AR and PT) are documented in a note column, per the overseer's cycle-1
  audit -- the grid itself is unchanged.

Reads data/interim/panel_excess.parquet (FIX-05), panel_extensive.parquet
(FIX-04), data/interim/t100_raw.parquet and data/interim/carrier_nation.parquet
(FIX-01/FIX-02, for the matched-vs-raw departures note only -- NOT re-used
for any nation assignment, which stays exactly panel_excess/panel_extensive's
own), carrier_nation_corridor_coverage.csv (FIX-02, for the ICN/TPE caveat
numbers), extensive_margin_churn.csv (FIX-04, for the seasonality caveat),
data/raw/events/ban_nations_2022.csv (agent-drafted, FOR HUMAN REVIEW --
see the README in that directory; used here ONLY to populate a
completeness record that is never plotted and carries no sign).
Never modifies any of them, never touches data/raw/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from utils import setup_logger  # noqa: E402

# --- Inputs ------------------------------------------------------------
PANEL_EXCESS_PARQUET = ROOT / "data" / "interim" / "panel_excess.parquet"
PANEL_EXTENSIVE_PARQUET = ROOT / "data" / "interim" / "panel_extensive.parquet"
T100_RAW_PARQUET = ROOT / "data" / "interim" / "t100_raw.parquet"
CARRIER_NATION_PARQUET = ROOT / "data" / "interim" / "carrier_nation.parquet"
OUT_DIR = ROOT / "rounds" / "round-1-t100-panel"
CORRIDOR_COVERAGE_CSV = OUT_DIR / "carrier_nation_corridor_coverage.csv"
CARRIER_GROUP_COVERAGE_CSV = OUT_DIR / "coverage_by_carrier_group.csv"
EXTENSIVE_CHURN_CSV = OUT_DIR / "extensive_margin_churn.csv"
BAN_NATIONS_CSV = ROOT / "data" / "raw" / "events" / "ban_nations_2022.csv"

# --- Outputs -------------------------------------------------------------
WEDGE_BY_CORRIDOR_CSV = OUT_DIR / "raw_wedge_by_corridor.csv"
WEDGE_DIFFS_CSV = OUT_DIR / "raw_wedge_diffs.csv"
FIG_AVAILABILITY = OUT_DIR / "figures" / "fig_data_availability.png"
FIG_US_ONLY_AIRBORNE = OUT_DIR / "figures" / "fig_us_only_corridor_series_airborne.png"
FIG_US_ONLY_EXCESS = OUT_DIR / "figures" / "fig_us_only_corridor_series_excess.png"
FIG_US_ONLY_STALE = OUT_DIR / "figures" / "fig_us_only_corridor_series.png"  # cycle-1 name, retired
LOG_FILE = ROOT / "logs" / "06_wedge_availability.log"

SAMPLE_LABEL = "US-touching international segments"

# NEW-06 anchor corridors -- kept byte-identical to code/03_audit/03_coverage_audit.py's
# CORRIDORS dict by construction; a runtime assertion below cross-checks against
# coverage_by_corridor.csv's own corridor names so this cannot silently drift.
CORRIDORS = {
    "useastasia": ["PEK", "PVG", "CAN", "HKG", "NRT", "HND", "ICN", "TPE"],
    "usindia": ["DEL", "BOM", "BLR", "HYD"],
    "usmideast": ["DXB", "DOH", "AUH", "TLV", "IST"],
    "useurope_placebo": ["LHR", "CDG", "FRA", "AMS", "MAD"],
}
AIRPORT_TO_CORRIDOR = {a: name for name, lst in CORRIDORS.items() for a in lst}

WINDOWS = {
    "full_2019_2024": [(y, m) for y in range(2019, 2025) for m in range(1, 13)],
    "zoom_2021h2_2022": (
        [(2021, m) for m in range(6, 13)] + [(2022, m) for m in range(1, 13)]
    ),
}

COVID_START, COVID_END = (2020, 3), (2021, 12)
# The two-block excess blackout established in FIX-05 (do not simplify to one span).
BLACKOUT_BLOCKS = [
    ((2022, 3), (2022, 12)),
    ((2023, 3), (2023, 12)),
]
EVENT_YM = (2022, 2)


def _ym_in(year, month, lo, hi) -> bool:
    return (year, month) >= lo and (year, month) <= hi


def _covid_flag_scalar(year: int, month: int) -> bool:
    return _ym_in(year, month, COVID_START, COVID_END)


def _in_blackout(year: int, month: int) -> bool:
    return any(_ym_in(year, month, lo, hi) for lo, hi in BLACKOUT_BLOCKS)


def _wmean(value: pd.Series, weight: pd.Series, group_keys: list[str],
           df: pd.DataFrame) -> pd.Series:
    """Departures-weighted group mean, ignoring rows where value is null
    (weight is zeroed for those rows before summing, so a null value never
    contributes to either the numerator or the denominator). Per the
    overseer's binding instruction, `weight` must be departures_airborne_eligible,
    never departures_performed.
    """
    v = value.to_numpy()
    w = weight.to_numpy()
    w_eff = np.where(np.isnan(v), 0.0, w)
    v_eff = np.where(np.isnan(v), 0.0, v)
    tmp = df[group_keys].copy()
    tmp["_num"] = v_eff * w_eff
    tmp["_den"] = w_eff
    g = tmp.groupby(group_keys, dropna=False)[["_num", "_den"]].sum()
    out = g["_num"] / g["_den"]
    out[g["_den"] <= 0] = np.nan
    return out


def main() -> int:
    logger = setup_logger("06_wedge_availability", str(LOG_FILE))

    for p in (PANEL_EXCESS_PARQUET, PANEL_EXTENSIVE_PARQUET, CORRIDOR_COVERAGE_CSV,
              CARRIER_GROUP_COVERAGE_CSV, T100_RAW_PARQUET, CARRIER_NATION_PARQUET,
              EXTENSIVE_CHURN_CSV):
        if not p.exists():
            logger.error("BLOCKED: required input %s not found.", p)
            return 1

    # Retire the cycle-1 figure name (B3: replaced by two explicitly-named
    # panels below) so a stale file cannot linger and be mistaken for current.
    if FIG_US_ONLY_STALE.exists():
        FIG_US_ONLY_STALE.unlink()
        logger.info("Removed stale cycle-1 figure %s (superseded by %s and %s).",
                    FIG_US_ONLY_STALE.name, FIG_US_ONLY_AIRBORNE.name, FIG_US_ONLY_EXCESS.name)

    (OUT_DIR / "figures").mkdir(parents=True, exist_ok=True)

    panel = pd.read_parquet(PANEL_EXCESS_PARQUET)
    ext = pd.read_parquet(PANEL_EXTENSIVE_PARQUET)
    logger.info("Loaded panel_excess.parquet: %d rows; panel_extensive.parquet: %d rows.",
                len(panel), len(ext))

    # =====================================================================
    # Governing-fact re-check (do not proceed silently if this has changed).
    # =====================================================================
    non_us_air = panel.loc[(panel["nation"] != "US") & panel["airborne_min_mean"].notna()]
    non_us_cov = panel.loc[(panel["nation"] != "US") & panel["coverage_ok"]]
    if len(non_us_air) or len(non_us_cov):
        logger.error("SCOPE VIOLATION: %d non-US cells carry non-null airborne_min_mean, "
                      "%d have coverage_ok == True. The reduced-form design this script "
                      "implements assumes both counts are zero. Refusing to proceed.",
                      len(non_us_air), len(non_us_cov))
        return 1
    logger.info("Governing-fact re-check holds: 0 non-US cells with non-null "
                "airborne_min_mean, 0 with coverage_ok == True (n=%d non-US matched cells "
                "in panel_excess.parquet).", int((panel["nation"] != "US").sum()))

    # Foreign-carrier structural non-reporting scale, read from FIX-03's own
    # standalone raw-CSV audit (never hardcoded, so this cannot drift from source).
    cg = pd.read_csv(CARRIER_GROUP_COVERAGE_CSV)
    cg0 = cg.loc[cg["carrier_group"] == 0]
    foreign_group0_rows = int(cg0["n_rows"].sum())
    foreign_group0_air_gt0 = int(cg0["n_air_gt0"].sum())
    if foreign_group0_air_gt0 != 0:
        logger.error("UNEXPECTED: CARRIER_GROUP==0 has %d rows with AIR_TIME>0 in %s -- the "
                      "'foreign carriers never report airborne time' governing fact no "
                      "longer holds on this data drop. Refusing to proceed.",
                      foreign_group0_air_gt0, CARRIER_GROUP_COVERAGE_CSV.name)
        return 1
    structural_nonreporting_note = (
        f"CARRIER_GROUP==0 carriers report AIR_TIME as a literal 0 in "
        f"{foreign_group0_air_gt0} of {foreign_group0_rows:,} segment-months 1990-2025 "
        f"({CARRIER_GROUP_COVERAGE_CSV.name}); not observable for ANY non-US operator, not "
        "specific to this cell"
    )
    logger.info("Structural non-reporting note (sourced from %s): %d / %d rows have "
                "AIR_TIME>0.", CARRIER_GROUP_COVERAGE_CSV.name, foreign_group0_air_gt0,
                foreign_group0_rows)

    # =====================================================================
    # Corridor assignment. Every row is US-touching (verified in FIX-03); the
    # foreign endpoint is whichever of origin/dest is a corridor airport.
    # =====================================================================
    panel = panel.copy()
    panel["corridor"] = panel["origin"].map(AIRPORT_TO_CORRIDOR).fillna(
        panel["dest"].map(AIRPORT_TO_CORRIDOR))
    ext = ext.copy()
    ext["corridor"] = ext["origin"].map(AIRPORT_TO_CORRIDOR).fillna(
        ext["dest"].map(AIRPORT_TO_CORRIDOR))

    corr_coverage = pd.read_csv(CORRIDOR_COVERAGE_CSV)
    corridor_names_in_coverage_file = {c.split("_", 1)[1] if c[0].isdigit() else c
                                        for c in corr_coverage["corridor"].unique()}
    assert set(CORRIDORS) <= corridor_names_in_coverage_file, (
        f"CORRIDORS dict {sorted(CORRIDORS)} has drifted from "
        f"{CORRIDOR_COVERAGE_CSV.name}'s corridor names "
        f"{sorted(corridor_names_in_coverage_file)}")
    logger.info("Corridor definitions cross-checked against %s: no drift.",
                CORRIDOR_COVERAGE_CSV.name)

    panel_c = panel.loc[panel["corridor"].notna()].copy()
    ext_c = ext.loc[ext["corridor"].notna()].copy()
    logger.info("Corridor-restricted rows: panel_excess %d / %d, panel_extensive %d / %d.",
                len(panel_c), len(panel), len(ext_c), len(ext))

    n_nonus_corridor_cells = int((panel_c["nation"] != "US").sum())
    n_nonus_corridor_air_valid = int(
        ((panel_c["nation"] != "US") & panel_c["airborne_min_mean"].notna()).sum())
    logger.info("Non-US corridor cells (matched population, all 4 corridors, panel_excess "
                "grain): %d. Of those, non-null airborne_min_mean: %d (expected 0).",
                n_nonus_corridor_cells, n_nonus_corridor_air_valid)

    # ICN / TPE match-rate caveat numbers, pulled from FIX-02's own corridor
    # coverage CSV rather than typed, so the caveat text cannot drift from source.
    # match_rate_foreign (matched foreign departures / total foreign departures) is
    # the coverage reading the overseer's ruling cites (0.6753 at ICN, 0.9562 at
    # TPE); it differs from match_rate_foreign_precision_adjusted at ICN (which
    # additionally strips home-country-share-zero codes) but the two coincide at
    # TPE. Both are carried in the CSV for transparency; the caveat text quotes
    # match_rate_foreign to match the overseer's stated figures exactly.
    icn_tpe = corr_coverage.loc[corr_coverage["airport"].isin(["ICN", "TPE"])
                                 & corr_coverage["window"].eq("full_2019_2024"),
                                 ["airport", "match_rate_foreign",
                                  "match_rate_foreign_precision_adjusted"]]
    icn_rate = icn_tpe.loc[icn_tpe["airport"] == "ICN", "match_rate_foreign"].iloc[0]
    icn_rate_prec = icn_tpe.loc[icn_tpe["airport"] == "ICN",
                                 "match_rate_foreign_precision_adjusted"].iloc[0]
    tpe_rate = icn_tpe.loc[icn_tpe["airport"] == "TPE", "match_rate_foreign"].iloc[0]
    fix02_caveat_text = (
        f"FIX-02 EMBARGO: corridor-1 (useastasia) nation-level match rate at ICN is "
        f"{icn_rate:.4f} (precision-adjusted: {icn_rate_prec:.4f}; Asiana's class-F "
        f"departures absent from the matched population); TPE is {tpe_rate:.4f}; every "
        f"other NEW-06 anchor is >= 0.956. Not reportable as a headline result until "
        f"FIX-02 unblocks (STATUS.md, FIX-02 BLOCKED-NEEDS-HUMAN)."
    )
    logger.info("fix02_caveat (useastasia rows only): %s", fix02_caveat_text)

    # =====================================================================
    # Nation universe per corridor: every (origin, dest, nation) triple ever
    # observed on that corridor's airports, from the extensive margin (Part
    # 0: "every operator nation reports departures" -- this is not
    # restricted by the coverage_ok/cell_ok QUALITY gates, so a nation that
    # flew a corridor route but failed those gates still shows up in the
    # departures/route-count picture). It IS, however, restricted to carrier
    # codes FIX-02 could assign a nation to at all -- panel_extensive is
    # keyed by (origin, dest, NATION), so an unmatched carrier code (no
    # nation) cannot appear here no matter how many departures it flew. The
    # diagnostic immediately below quantifies that gap against raw T-100.
    # =====================================================================
    triples = ext_c[["corridor", "origin", "dest", "nation"]].drop_duplicates()
    nations_per_corridor = {c: sorted(g["nation"].unique())
                             for c, g in triples.groupby("corridor")}
    for c, nats in nations_per_corridor.items():
        logger.info("Corridor %s: %d operator nations ever observed (%s).",
                    c, len(nats), ", ".join(nats))

    # =====================================================================
    # Advisory: departures_performed_month_sum (and every extensive-margin
    # count in this file) is a MATCHED-CARRIER count, never stated in cycle
    # 1. Quantify the matched-vs-raw gap per corridor directly against
    # t100_raw.parquet (2019-2024, passenger service, departures>0 -- the
    # same filter the round's own coverage audit uses), independent of
    # panel_extensive's own construction, so this note cannot silently drift
    # from what the CSV's departure counts actually cover.
    # =====================================================================
    raw_cols = ["ORIGIN", "DEST", "UNIQUE_CARRIER", "YEAR", "DEPARTURES_PERFORMED",
                "is_passenger"]
    raw = pd.read_parquet(T100_RAW_PARQUET, columns=raw_cols)
    raw_sample = raw.loc[raw["is_passenger"] & (raw["DEPARTURES_PERFORMED"] > 0)
                          & raw["YEAR"].between(2019, 2024)].copy()
    raw_sample["corridor"] = raw_sample["ORIGIN"].map(AIRPORT_TO_CORRIDOR).fillna(
        raw_sample["DEST"].map(AIRPORT_TO_CORRIDOR))
    raw_corr = raw_sample.loc[raw_sample["corridor"].notna()].copy()
    cn = pd.read_parquet(CARRIER_NATION_PARQUET)
    raw_corr = raw_corr.merge(cn, left_on=["UNIQUE_CARRIER", "YEAR"],
                               right_on=["UNIQUE_CARRIER", "year"], how="left")
    departures_scope_note = {}
    for corridor in CORRIDORS:
        d = raw_corr.loc[raw_corr["corridor"] == corridor]
        raw_total = float(d["DEPARTURES_PERFORMED"].sum())
        matched_total = float(d.loc[d["nation_iso2"].notna(), "DEPARTURES_PERFORMED"].sum())
        unmatched_total = raw_total - matched_total
        unmatched_share = (unmatched_total / raw_total) if raw_total > 0 else float("nan")
        top_unmatched = (d.loc[d["nation_iso2"].isna()]
                         .groupby("UNIQUE_CARRIER")["DEPARTURES_PERFORMED"].sum()
                         .sort_values(ascending=False).head(3))
        top_str = ", ".join(f"{c}={v:,.0f}" for c, v in top_unmatched.items())
        logger.info("Corridor %s: raw class-F passenger departures 2019-2024 = %.0f, "
                     "matched (FIX-02-mapped) = %.0f, unmatched = %.0f (%.4f share)%s.",
                     corridor, raw_total, matched_total, unmatched_total, unmatched_share,
                     f" -- top unmatched carriers: {top_str}" if top_str else "")
        departures_scope_note[corridor] = (
            f"departures_performed_month_sum / n_routes_* count MATCHED-CARRIER "
            f"(FIX-02-mapped) departures/routes ONLY. Raw class-F passenger departures "
            f"on this corridor 2019-2024 (t100_raw.parquet, all carriers): {raw_total:,.0f}; "
            f"matched: {matched_total:,.0f}; unmatched: {unmatched_total:,.0f} "
            f"({unmatched_share:.4f} share)"
            + (f", largest unmatched carriers: {top_str}" if top_str else "")
            + ". See coverage_matching_exclusions.csv / carrier_nation_unmatched.csv for "
            "the excluded population."
        )

    # Extensive-margin seasonality caveat (FIX-04's own diagnostic), pulled live
    # so the counts in this file always travel with the caveat that most churn
    # is thin/seasonal routes re-entering, not one-way exit.
    churn = pd.read_csv(EXTENSIVE_CHURN_CSV).set_index("metric")["value"]
    n_exits = int(churn.loc["n_exits"])
    n_reenter = int(churn.loc["n_exits_reentering_ever"])
    median_active_months = churn.loc["active_months_per_triple_median"]
    extensive_seasonality_note = (
        f"EXTENSIVE-MARGIN CAVEAT (extensive_margin_churn.csv): of {n_exits:,} route-exit "
        f"events across the full panel, {n_reenter:,} re-enter at some later month -- "
        f"median (origin,dest,nation) triple is active only {median_active_months:.0f} of "
        "432 months on file. n_routes_active / departures_performed_month_sum here are "
        "activity counts, NOT entry/exit events, and must not be read as an event-study "
        "outcome (per the round's own ruling on this margin)."
    )
    logger.info("Extensive-margin seasonality note: %s", extensive_seasonality_note)

    # Two known false-zero cells against raw T-100, found and quantified in the
    # overseer's cycle-1 audit -- documented here, NOT corrected in the grid
    # (per the coordinator's instruction: "document them rather than changing
    # the grid").
    known_discrepancies_note = (
        "KNOWN FALSE ZEROS (overseer cycle-1 audit, documented not corrected): "
        "useurope_placebo / AR shows a departures_performed_month_sum of 0 in at least "
        "one cell where raw T-100 has 1 departure; useurope_placebo / PT (Portugal) is "
        "absent from this corridor's nation universe entirely, where raw T-100 has 2 "
        "departures somewhere on these routes. Both are sub-single-digit-departure edge "
        "cases in the extensive-margin construction (FIX-04), not reproduced independently "
        "in this script; the grid is left as FIX-04 built it."
    )

    # =====================================================================
    # Extensive-margin aggregation: corridor x nation x year x month.
    # departures_performed_month and route-activity counts are observable
    # for ALL 93 nations (Part 0's "one genuinely informative thing").
    # =====================================================================
    ext_agg = (ext_c.groupby(["corridor", "nation", "year", "month"], dropna=False)
               .agg(n_routes_active=("active", "sum"),
                    n_routes_total=("origin", "size"),
                    departures_performed_month_sum=("departures_performed_month", "sum"))
               .reset_index())

    # =====================================================================
    # Matched-population (panel_excess) aggregation: corridor x nation x
    # year x month. Weighted means use departures_airborne_eligible per the
    # overseer's binding instruction (never departures_performed).
    # =====================================================================
    grp_keys = ["corridor", "nation", "year", "month"]
    valid_air = (panel_c["cell_ok"] & panel_c["airborne_min_mean"].notna()
                 & (~panel_c["time_implausible_flag"]))
    match_agg = (panel_c.groupby(grp_keys, dropna=False)
                 .agg(n_cells_matched=("origin", "size"),
                      n_cells_airborne_valid=("airborne_min_mean",
                                               lambda s: int(s.notna().sum())))
                 .reset_index())
    # n_cells_airborne_valid above double-counts implausible-speed rows as
    # "notna"; recompute exactly against the valid_air mask instead.
    va_counts = (panel_c.assign(_valid_air=valid_air)
                 .groupby(grp_keys, dropna=False)["_valid_air"].sum()
                 .rename("n_cells_airborne_valid").reset_index())
    match_agg = match_agg.drop(columns=["n_cells_airborne_valid"]).merge(
        va_counts, on=grp_keys, how="left")

    airborne_wtd = _wmean(panel_c["airborne_min_mean"].where(valid_air),
                           panel_c["departures_airborne_eligible"], grp_keys, panel_c)
    excess_wtd = _wmean(panel_c["excess_min_w"], panel_c["departures_airborne_eligible"],
                         grp_keys, panel_c)
    n_excess_valid = (panel_c.assign(_v=panel_c["excess_min_w"].notna())
                      .groupby(grp_keys, dropna=False)["_v"].sum()
                      .rename("n_cells_excess_valid"))
    # B2: the departures_airborne_eligible mass behind excess_min_w_wtd, i.e. the
    # SAME weight the cell-level weighted mean above already used (denominator of
    # excess_wtd). This is what raw_wedge_diffs.csv's nation-pooling step must sum
    # over nations by, per the file's own "definition" text -- never the cell count.
    dep_excess_valid_sum = (
        panel_c.assign(_w=panel_c["departures_airborne_eligible"]
                        .where(panel_c["excess_min_w"].notna(), 0.0))
        .groupby(grp_keys, dropna=False)["_w"].sum()
        .rename("departures_airborne_eligible_excess_sum"))

    # bidir_sum is stored on BOTH directed legs of a pair with the same value
    # (A->B row and B->A row both carry excess(A->B)+excess(B->A)); dedupe by
    # the unordered route pair before averaging so it is not double-weighted.
    bidir_src = panel_c.copy()
    bidir_src["_pair"] = bidir_src.apply(
        lambda r: tuple(sorted((r["origin"], r["dest"]))), axis=1)
    bidir_src = bidir_src.drop_duplicates(subset=["_pair", "nation", "year", "month"])
    bidir_wtd = _wmean(bidir_src["bidir_sum"], bidir_src["departures_airborne_eligible"],
                        grp_keys, bidir_src)
    n_bidir_valid = (bidir_src.assign(_v=bidir_src["bidir_sum"].notna())
                     .groupby(grp_keys, dropna=False)["_v"].sum()
                     .rename("n_cells_bidir_valid"))

    match_stats = match_agg.set_index(grp_keys)
    match_stats["airborne_min_mean_wtd"] = airborne_wtd
    match_stats["excess_min_w_wtd"] = excess_wtd
    match_stats["n_cells_excess_valid"] = n_excess_valid
    match_stats["departures_airborne_eligible_excess_sum"] = dep_excess_valid_sum
    match_stats["bidir_sum_wtd"] = bidir_wtd
    match_stats["n_cells_bidir_valid"] = n_bidir_valid
    match_stats = match_stats.reset_index()

    # =====================================================================
    # Build the full family: corridor x window x nation x month, cross-joined
    # so n=0 rows are present and checkable (round file's own VERIFY item,
    # carried into the reduced deliverable).
    # =====================================================================
    rows = []
    for corridor, nats in nations_per_corridor.items():
        for window_name, ym_list in WINDOWS.items():
            for nation in nats:
                for (year, month) in ym_list:
                    rows.append((corridor, window_name, nation, year, month))
    family = pd.DataFrame(rows, columns=["corridor", "window", "nation", "year", "month"])
    logger.info("Full family cross-join: %d corridor x window x nation x month rows.",
                len(family))

    family = family.merge(ext_agg, on=["corridor", "nation", "year", "month"], how="left")
    family = family.merge(match_stats, on=["corridor", "nation", "year", "month"], how="left")
    for c in ["n_routes_active", "n_routes_total", "departures_performed_month_sum",
              "n_cells_matched", "n_cells_airborne_valid", "n_cells_excess_valid",
              "departures_airborne_eligible_excess_sum", "n_cells_bidir_valid"]:
        family[c] = family[c].fillna(0)

    family["covid_flag"] = family.apply(
        lambda r: _covid_flag_scalar(int(r["year"]), int(r["month"])), axis=1)
    family["in_excess_blackout"] = family.apply(
        lambda r: _in_blackout(int(r["year"]), int(r["month"])), axis=1)

    # --- reason_missing: priority-ordered, per the reduced deliverable's
    # instruction that every empty cell traces to a stated reason. ---------
    def _reason(r) -> str:
        if r["departures_performed_month_sum"] <= 0:
            return "no_departures: n=0, this operator nation flew no corridor route this month"
        if r["nation"] != "US":
            return "foreign_structural_nonreporting: " + structural_nonreporting_note
        if r["n_cells_matched"] <= 0:
            return ("us_unmatched: departures observed but no matched passenger-service "
                    "cell this month (see panel_filter_log.csv)")
        if r["n_cells_airborne_valid"] <= 0:
            return ("us_airborne_excluded: matched cells present but excluded from airborne "
                    "measurement (cell_ok gate <4 departures/month, G6 coverage, or the "
                    "implied-speed screen; see panel_excess.parquet flags)")
        if r["n_cells_excess_valid"] <= 0:
            if r["in_excess_blackout"]:
                return ("us_baseline_blackout: airborne observed, but the trailing-3-year "
                        "COVID-excluded baseline has <2 candidates in this month (one of "
                        "the two 10-month blocks 2022-03..2022-12 / 2023-03..2023-12, "
                        "FIX-05 cycle 2)")
            return ("us_baseline_fail_other: airborne observed, baseline_n<2 for a reason "
                    "outside the two-block blackout (see baseline_failures.csv)")
        return "observable: airborne and excess computable (US carriers only)"

    family["reason_missing"] = family.apply(_reason, axis=1)
    family["fix02_caveat"] = np.where(family["corridor"] == "useastasia", fix02_caveat_text, "")
    # Advisory: departures_performed_month_sum / n_routes_* are MATCHED-CARRIER-ONLY
    # counts (FIX-02-mapped); this note states that scope, per corridor, and the raw-
    # vs-matched residual, on every row so it always travels with the counts.
    family["departures_scope_note"] = family["corridor"].map(departures_scope_note)
    # Advisory: extensive-margin churn is seasonal re-entry, not one-way exit --
    # carried with the activity counts so it is never read as an event-study outcome.
    family["extensive_margin_seasonality_note"] = extensive_seasonality_note
    # Advisory: two known false-zero cells vs raw T-100 on useurope_placebo, found in
    # the overseer's cycle-1 audit -- documented here rather than changing the grid.
    family["known_false_zero_note"] = np.where(
        family["corridor"] == "useurope_placebo", known_discrepancies_note, "")
    family["match_sensitive_nation"] = family["nation"].isin(["RU", "IR"])
    family["sample"] = SAMPLE_LABEL
    family = family.sort_values(["corridor", "window", "nation", "year", "month"]
                                 ).reset_index(drop=True)

    col_order = ["corridor", "window", "nation", "year", "month", "covid_flag",
                 "in_excess_blackout", "match_sensitive_nation",
                 "n_routes_active", "n_routes_total", "departures_performed_month_sum",
                 "n_cells_matched", "n_cells_airborne_valid", "airborne_min_mean_wtd",
                 "n_cells_excess_valid", "excess_min_w_wtd",
                 "departures_airborne_eligible_excess_sum",
                 "n_cells_bidir_valid", "bidir_sum_wtd",
                 "reason_missing", "fix02_caveat", "departures_scope_note",
                 "extensive_margin_seasonality_note", "known_false_zero_note", "sample"]
    family = family[col_order]
    family.to_csv(WEDGE_BY_CORRIDOR_CSV, index=False)
    logger.info("Wrote %s: %d rows.", WEDGE_BY_CORRIDOR_CSV, len(family))

    # --- VERIFY: all 4 corridors x 2 windows present, including n=0 rows. ---
    got = set(zip(family["corridor"], family["window"]))
    want = set((c, w) for c in CORRIDORS for w in WINDOWS)
    assert got == want, f"corridor x window coverage incomplete: missing {want - got}"
    n_zero_rows = int((family["departures_performed_month_sum"] <= 0).sum())
    logger.info("VERIFY: all %d corridor x window combinations present (%d n=0 rows among "
                "them).", len(want), n_zero_rows)

    n_nonnull_air_nonus = int(
        ((family["nation"] != "US") & (family["airborne_min_mean_wtd"].notna())).sum())
    logger.info("Non-null airborne_min_mean_wtd among non-US family rows: %d (expected 0).",
                n_nonnull_air_nonus)
    if n_nonnull_air_nonus:
        logger.error("UNEXPECTED: %d non-US family rows carry a non-null "
                      "airborne_min_mean_wtd -- governing fact violated downstream of the "
                      "re-check above.", n_nonnull_air_nonus)
        return 1

    # =====================================================================
    # raw_wedge_diffs.csv -- COMPLETENESS RECORD ONLY. Never plotted, no
    # sign to be read. Ban-nation classification from data/raw/events/
    # ban_nations_2022.csv (agent-drafted, unreviewed) purely so the
    # commissioned computation's non-existence is checkable, not because a
    # result is being reported.
    # =====================================================================
    ban = pd.read_csv(BAN_NATIONS_CSV)
    ban_status = dict(zip(ban["nation_iso2"], ban["status"]))
    ban_dictionary_note = (
        "ban_nations_2022.csv is agent-drafted (Claude, 2026-09-01) from public reporting "
        "and its own README says FOR HUMAN REVIEW before headline use (PROJECT.md requires "
        "event dictionaries to be human-curated) -- NOT human-reviewed as of this run. "
        "voluntary_avoidance is its own line per that README, never pooled with "
        "banned/not_banned."
    )

    # Column-name convention (B1): every mean_excess_* column carries an unmistakable
    # suffix in the HEADER ITSELF (not only in the prose 'definition' column) because
    # at most one nation (US) ever has data behind it -- see the assert below, which
    # refuses to write the file if that ever stops being true for any status group.
    STATUS_COLS = {
        "banned": "mean_excess_banned_side_US_ONLY_NOT_A_RESULT",
        "not_banned": "mean_excess_not_banned_side_US_ONLY_NOT_A_RESULT",
        "voluntary_avoidance": "mean_excess_voluntary_avoidance_side_US_ONLY_NOT_A_RESULT",
        "unclassified": "mean_excess_unclassified_side_US_ONLY_NOT_A_RESULT",
    }

    diff_rows = []
    for corridor, nats in nations_per_corridor.items():
        for window_name, ym_list in WINDOWS.items():
            cw = family.loc[(family["corridor"] == corridor)
                             & (family["window"] == window_name)].copy()
            cw["ban_status"] = cw["nation"].map(ban_status).fillna("unclassified")
            for (year, month) in ym_list:
                m = cw.loc[(cw["year"] == year) & (cw["month"] == month)]
                groups = {}
                for status in STATUS_COLS:
                    sub = m.loc[m["ban_status"] == status]
                    # B2: pool nations within a ban-status group weighted by summed
                    # departures_airborne_eligible (the SAME weight the cell-level
                    # excess_min_w_wtd mean above used), never by cell count -- this
                    # is what the 'definition' text below actually claims.
                    w = sub["departures_airborne_eligible_excess_sum"].where(
                        sub["excess_min_w_wtd"].notna(), 0)
                    num = (sub["excess_min_w_wtd"].fillna(0) * w).sum()
                    den = w.sum()
                    groups[status] = {
                        "mean_excess_min_w": (num / den) if den > 0 else np.nan,
                        "n_nations": int(sub["nation"].nunique()),
                        "n_nations_with_data": int(
                            sub.loc[sub["excess_min_w_wtd"].notna(), "nation"].nunique()),
                    }
                diff = groups["banned"]["mean_excess_min_w"] - groups["not_banned"]["mean_excess_min_w"]
                row = {"corridor": corridor, "window": window_name, "year": year, "month": month}
                for status, col in STATUS_COLS.items():
                    row[col] = groups[status]["mean_excess_min_w"]
                    row[f"n_nations_{status}"] = groups[status]["n_nations"]
                    row[f"n_nations_{status}_with_data"] = groups[status]["n_nations_with_data"]
                row["diff_banned_minus_not_banned"] = diff
                diff_rows.append(row)
    diffs = pd.DataFrame(diff_rows)
    diffs["status"] = "NOT A RESULT -- COMPLETENESS RECORD ONLY"

    # B1 (enforced, not just asserted-in-prose): refuse to write the file if any
    # mean_excess_* column is non-null for a group whose *_with_data count exceeds 1
    # -- i.e. if the pooled mean this run wrote down was ever pooling more than the
    # single US series while FIX-02 is blocked. A violation here means the "this
    # column is US-only, not a treatment effect" claim is no longer true and the file
    # must not ship silently.
    for status, col in STATUS_COLS.items():
        wd = f"n_nations_{status}_with_data"
        bad = diffs.loc[(diffs[wd] > 1) & diffs[col].notna()]
        if len(bad):
            logger.error("B1 VIOLATION: %d rows of %s have %s non-null with %s > 1 -- "
                          "more than one nation is contributing to this column; it can "
                          "no longer be assumed to be the US-only series. Refusing to "
                          "write the file.", len(bad), WEDGE_DIFFS_CSV.name, col, wd)
            return 1
    logger.info("B1 check passed: every mean_excess_*_US_ONLY_NOT_A_RESULT column is "
                "null whenever its status group has more than 1 nation with data.")
    diffs["definition"] = (
        "diff_banned_minus_not_banned = mean_excess_banned_side_US_ONLY_NOT_A_RESULT minus "
        "mean_excess_not_banned_side_US_ONLY_NOT_A_RESULT. Each mean_excess_*_side_US_ONLY_"
        "NOT_A_RESULT column pools nations within that ban_nations_2022.csv status on this "
        "corridor x month, weighted by each nation's SUMMED departures_airborne_eligible "
        "across its matched cells with a valid excess_min_w that month "
        "(departures_airborne_eligible_excess_sum in raw_wedge_by_corridor.csv) -- the same "
        "weight the cell-level departures-weighted mean (excess_min_w_wtd) already used one "
        "level down, so the two-level pooling is weighted consistently top to bottom; NOT "
        "by nation/cell counts. The not_banned side is nations CN/IN/AE/QA/TR/RS/IL/ET/etc "
        "-- all non-US, and "
        f"airborne_min_mean is non-null for {n_nonus_corridor_air_valid} of "
        f"{n_nonus_corridor_cells} non-US corridor cells in this dataset "
        "(structural non-reporting, verified above), so "
        "mean_excess_not_banned_side_US_ONLY_NOT_A_RESULT is NaN in EVERY row and "
        "diff_banned_minus_not_banned is therefore NaN BY CONSTRUCTION in every row, "
        "regardless of month or corridor. mean_excess_banned_side_US_ONLY_NOT_A_RESULT can "
        "be non-NaN because 'banned' pools US with EU/UK/CH/NO carriers and only the US "
        "side ever has data (enforced at runtime: the script refuses to write this file if "
        "any mean_excess_* column is non-null while its n_nations_*_with_data exceeds 1) -- "
        "that column is NOT a treatment-effect estimate on its own; it is shown, with its "
        "header naming exactly what it is, so the empty side of the subtraction is visible "
        "rather than silently missing. NEVER PLOT THIS CSV. NO SIGN MAY BE READ FROM IT. "
        + ban_dictionary_note
    )
    diffs = diffs.sort_values(["corridor", "window", "year", "month"]).reset_index(drop=True)
    diffs.to_csv(WEDGE_DIFFS_CSV, index=False)
    n_diff_nonnull = int(diffs["diff_banned_minus_not_banned"].notna().sum())
    logger.info("Wrote %s: %d rows. Non-null diff_banned_minus_not_banned: %d (expected 0).",
                WEDGE_DIFFS_CSV, len(diffs), n_diff_nonnull)
    if n_diff_nonnull:
        logger.error("UNEXPECTED: %d rows of raw_wedge_diffs.csv have a non-null diff -- "
                      "the 'not_banned side is structurally empty' claim is false for this "
                      "data drop. This would need investigation before the CSV's own "
                      "'definition' text is trustworthy.", n_diff_nonnull)
        return 1

    # =====================================================================
    # Figure 1 (required): data availability -- NOT a wedge figure.
    # 2x2 grid, one panel per corridor, y = nation, x = month (full window),
    # 3-state categorical: no departures / active but not observable /
    # observable. Fixed axis limits and a shared legend across panels so the
    # four corridors (including the placebo) are visually comparable.
    # =====================================================================
    full_ym = WINDOWS["full_2019_2024"]
    month_labels = [f"{y}-{m:02d}" for (y, m) in full_ym]
    cmap = ListedColormap(["#d9d9d9", "#c44e52", "#4c72b0"])  # gray / red / blue

    fig, axes = plt.subplots(2, 2, figsize=(20, 14))
    corridor_order = ["useastasia", "usindia", "usmideast", "useurope_placebo"]
    for ax, corridor in zip(axes.flat, corridor_order):
        nats = nations_per_corridor[corridor]
        # US first, then alphabetical, so the one nation with real data anchors row 0.
        nats_sorted = (["US"] if "US" in nats else []) + sorted(n for n in nats if n != "US")
        sub = family.loc[(family["corridor"] == corridor)
                          & (family["window"] == "full_2019_2024")]
        grid = np.zeros((len(nats_sorted), len(full_ym)), dtype=int)
        idx = {nat: i for i, nat in enumerate(nats_sorted)}
        jdx = {ym: j for j, ym in enumerate(full_ym)}
        for _, r in sub.iterrows():
            i, j = idx[r["nation"]], jdx[(int(r["year"]), int(r["month"]))]
            if r["departures_performed_month_sum"] <= 0:
                grid[i, j] = 0
            elif r["n_cells_airborne_valid"] > 0:
                grid[i, j] = 2
            else:
                grid[i, j] = 1
        ax.imshow(grid, aspect="auto", cmap=cmap, vmin=0, vmax=2, interpolation="none")
        ax.set_yticks(range(len(nats_sorted)))
        ax.set_yticklabels(nats_sorted, fontsize=6)
        tick_pos = [j for j, (y, m) in enumerate(full_ym) if m == 1]
        ax.set_xticks(tick_pos)
        ax.set_xticklabels([str(full_ym[j][0]) for j in tick_pos], fontsize=8, rotation=0)
        event_j = jdx.get(EVENT_YM)
        if event_j is not None:
            ax.axvline(event_j - 0.5, color="black", linewidth=1.2, linestyle="--")
        ax.set_title(corridor, fontsize=11)
    legend_handles = [
        Patch(facecolor="#d9d9d9", label="no departures this month (n=0)"),
        Patch(facecolor="#c44e52", label="active, airborne time NOT observable"),
        Patch(facecolor="#4c72b0", label="active, airborne time observable"),
    ]
    fig.legend(handles=legend_handles, loc="lower center", ncol=3, fontsize=10,
               bbox_to_anchor=(0.5, -0.02))
    fig.suptitle(
        f"Data availability, NOT a wedge -- {SAMPLE_LABEL}, 2019-2024\n"
        "Dashed line = 2022-02 (event month). Airborne time is observable for US carriers "
        "only, at every anchor corridor including the placebo (useurope_placebo); it is "
        "structurally absent for every foreign operator (T-100(f) reporting schedule).",
        fontsize=12, y=1.01)
    fig.tight_layout(rect=(0, 0.03, 1, 0.96))
    fig.savefig(FIG_AVAILABILITY, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s.", FIG_AVAILABILITY)

    # =====================================================================
    # Figures 2a/2b (B3, cycle-2 fix): US-only raw-level corridor series.
    # The commissioned item-4 deliverable is the RAW-level panel
    # (departures-weighted airborne_min_mean by corridor x month); it is
    # added ALONGSIDE the excess-level panel, not in place of it, because
    # the excess panel is blank for 20 of the 24 event-window months by
    # construction (FIX-05's two blackout blocks) while airborne_min_mean_wtd
    # is observed almost every month across the same window. Both panels:
    # same 2x2 layout, same corridor order, 2022-02 event line, explicitly
    # labelled "not a cross-national comparison".
    # =====================================================================
    def _plot_us_only_panel(value_col: str, ylabel: str, out_path: Path,
                             subtitle: str, shade_excess_blackout: bool) -> None:
        fig, axes = plt.subplots(2, 2, figsize=(16, 10), sharex=True)
        for ax, corridor in zip(axes.flat, corridor_order):
            us = family.loc[(family["corridor"] == corridor)
                             & (family["window"] == "full_2019_2024")
                             & (family["nation"] == "US")].sort_values(["year", "month"])
            x = np.arange(len(us))
            y = us[value_col].to_numpy()
            ax.plot(x, y, color="#4c72b0", linewidth=1.5, marker="o", markersize=2.5)
            ax.axhline(0, color="black", linewidth=0.8, linestyle=":")
            if shade_excess_blackout:
                for lo, hi in BLACKOUT_BLOCKS:
                    j_lo = full_ym.index(lo) if lo in full_ym else None
                    j_hi = full_ym.index(hi) if hi in full_ym else None
                    if j_lo is not None and j_hi is not None:
                        ax.axvspan(j_lo - 0.5, j_hi + 0.5, color="#c44e52", alpha=0.15,
                                   label=("excess baseline blackout"
                                          if lo == BLACKOUT_BLOCKS[0][0] else None))
            covid_js = [j for j, ym in enumerate(full_ym) if _covid_flag_scalar(*ym)]
            if covid_js:
                ax.axvspan(min(covid_js) - 0.5, max(covid_js) + 0.5, color="gray", alpha=0.12,
                           label="COVID window")
            event_j = full_ym.index(EVENT_YM) if EVENT_YM in full_ym else None
            if event_j is not None:
                ax.axvline(event_j, color="black", linewidth=1.0, linestyle="--",
                           label="2022-02 event")
            tick_pos = [j for j, (y_, m_) in enumerate(full_ym) if m_ == 1]
            ax.set_xticks(tick_pos)
            ax.set_xticklabels([str(full_ym[j][0]) for j in tick_pos], fontsize=8)
            ax.set_title(corridor, fontsize=11)
            ax.set_ylabel(ylabel, fontsize=8)
        axes.flat[0].legend(fontsize=7, loc="upper left")
        fig.suptitle(
            "US carriers only -- not a cross-national comparison\n" + subtitle,
            fontsize=11, y=1.03)
        fig.tight_layout(rect=(0, 0, 1, 0.94))
        fig.savefig(out_path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        logger.info("Wrote %s.", out_path)

    _plot_us_only_panel(
        value_col="airborne_min_mean_wtd",
        ylabel="airborne_min_mean (minutes)",
        out_path=FIG_US_ONLY_AIRBORNE,
        subtitle=(f"{SAMPLE_LABEL}, departures-weighted mean airborne_min_mean (raw level, "
                   "not excess) by corridor, 2019-2024. This raw-level series is observed "
                   "through the 2022-03..2023-12 event window where the excess-level series "
                   "(below) is blacked out by FIX-05's baseline construction. "
                   "Shaded: COVID window (gray)."),
        shade_excess_blackout=False,
    )
    _plot_us_only_panel(
        value_col="excess_min_w_wtd",
        ylabel="excess_min_w (minutes)",
        out_path=FIG_US_ONLY_EXCESS,
        subtitle=(f"{SAMPLE_LABEL}, departures-weighted mean excess_min_w by corridor, "
                   "2019-2024. Shaded: COVID window (gray) and the two excess-baseline "
                   "blackout blocks (red, 2022-03..2022-12 and 2023-03..2023-12)."),
        shade_excess_blackout=True,
    )

    # --- Final guard: none of the five prohibited filenames were written. ---
    prohibited = ["fig_raw_wedge_useastasia.png", "fig_raw_wedge_usindia.png",
                  "fig_raw_wedge_usmideast.png", "fig_raw_wedge_useurope_placebo.png",
                  "fig_raw_wedge_bidir.png"]
    existing_prohibited = [f for f in prohibited if (OUT_DIR / "figures" / f).exists()]
    if existing_prohibited:
        logger.error("PROHIBITED FIGURE(S) PRESENT: %s -- this script did not write them, "
                      "but their presence must be investigated before this task can be "
                      "marked DONE.", existing_prohibited)
        return 1
    logger.info("Confirmed: none of the 5 prohibited wedge figures exist in %s.",
                OUT_DIR / "figures")

    logger.info("DONE (reduced form). No cross-national wedge was computed or plotted.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
