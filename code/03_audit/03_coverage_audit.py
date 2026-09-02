#!/usr/bin/env python3
"""03_coverage_audit.py — FIX-03: coverage audit (runs before any panel).

Two-sentence summary: for every operator nation x year we measure what
share of T-100's own reported passenger segment-months actually carry a
usable (>0) airborne-time number, because a nation-year cell where the
field is mostly blank would manufacture "disruptions" out of a reporting
hole rather than a real change in flying; any cell below 50% coverage
(G6) is excluded from the headline panel and listed, never silently
averaged in or imputed.

FIX-02 (operator-nation mapping) is BLOCKED-NEEDS-HUMAN with a
DEGENERATE-GATE flag: G7 has a coverage reading (0.9021, PASS) and a
route-endpoint precision reading (0.8631, FAIL) for foreign carriers, and
neither has been chosen by a human. Per the overseer's ruling
(REVIEW_REPORT.md section L), THIS task MAY PROCEED on matched carriers
only (match_method in {iata, icao, name_exact, us_by_construction}), with
the excluded population logged (coverage_matching_exclusions.csv), and
must carry FIX-02's own per-code precision diagnostic
(carrier_nation_precision_audit.csv's flag_home_share_zero) forward as a
departures-weighted `share_dep_home0` column on every nation x year cell,
so a nation whose cells rest mostly on mismapped carrier codes is visible
before FIX-04 consumes this table. Mapped nations RU and IR are
MATCH-SENSITIVE wherever they appear (see that CSV) and are labelled as
such (`match_sensitive` column, and a table/figure footnote) in every
output here.

Column-naming note (overseer cycle-2 required action 4): the row-count column in
coverage_audit.csv / coverage_by_corridor.csv is named `n_rows` and counts raw
carrier x segment x month x aircraft-type x class rows (post service-class/
departures>0 filtering), NOT distinct (origin, dest, month) segment-months --
T-100 has one row per aircraft type flown on a segment-month, so `n_rows` runs
about 1.70x the distinct-segment-month count (1,745,448 raw rows vs 1,027,021
distinct (ORIGIN, DEST, MONTH) combinations in the matched sample). FIX-04 is the
task that aggregates aircraft types to the cell; this task deliberately does not.

Reads data/interim/t100_raw.parquet (FIX-01),
data/interim/carrier_nation.parquet (FIX-02), and
rounds/round-1-t100-panel/carrier_nation_precision_audit.csv (FIX-02).
Never modifies any of them, and never modifies data/raw/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from utils import setup_logger, log_merge  # noqa: E402

# --- Inputs ---------------------------------------------------------------
PARQUET_T100 = ROOT / "data" / "interim" / "t100_raw.parquet"
PARQUET_NATION = ROOT / "data" / "interim" / "carrier_nation.parquet"

OUT_DIR = ROOT / "rounds" / "round-1-t100-panel"
PRECISION_AUDIT_CSV_IN = OUT_DIR / "carrier_nation_precision_audit.csv"

# --- Outputs ----------------------------------------------------------------
COVERAGE_AUDIT_CSV = OUT_DIR / "coverage_audit.csv"
COVERAGE_CORRIDOR_CSV = OUT_DIR / "coverage_by_corridor.csv"
COVERAGE_EXCLUDED_CSV = OUT_DIR / "coverage_excluded_cells.csv"
MATCHING_EXCLUSIONS_CSV = OUT_DIR / "coverage_matching_exclusions.csv"
TABLE_TEX = OUT_DIR / "tables" / "tab_coverage_audit.tex"
HEATMAP_PNG = OUT_DIR / "figures" / "fig_coverage_heatmap.png"
LOG_FILE = ROOT / "logs" / "03_coverage_audit.log"

# --- Constants --------------------------------------------------------------
G6_MIN = 0.50
COVID_YEARS = {2020, 2021}  # window is 2020-03..2021-12; both years overlap it
MATCH_SENSITIVE_NATIONS = {"RU", "IR"}
MATCHED_METHODS = ["iata", "icao", "name_exact", "us_by_construction"]
SAMPLE_LABEL = "US-touching international segments"

# NEW-06 anchor corridors: US airports <-> these foreign airports, both
# directions, passenger service. Airport lists are disjoint by construction
# (checked in code below).
CORRIDORS = {
    "useastasia": ["PEK", "PVG", "CAN", "HKG", "NRT", "HND", "ICN", "TPE"],
    "usindia": ["DEL", "BOM", "BLR", "HYD"],
    "usmideast": ["DXB", "DOH", "AUH", "TLV", "IST"],
    "useurope_placebo": ["LHR", "CDG", "FRA", "AMS", "MAD"],
}


def _cell_stats(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """Aggregate a matched, passenger, departures>0 sample to group_cols.

    Reporting-gap distinction (Part 0): AIR_TIME == 0 and AIR_TIME null are
    counted separately from each other and from AIR_TIME > 0 — never lumped,
    never imputed. Same for RAMP_TO_RAMP.
    """
    g = df.groupby(group_cols, dropna=False)

    def _shares(col: str, prefix: str) -> pd.DataFrame:
        valid = g.apply(lambda d, c=col: int((d[c] > 0).sum()), include_groups=False)
        zero = g.apply(lambda d, c=col: int((d[c] == 0).sum()), include_groups=False)
        null = g.apply(lambda d, c=col: int(d[c].isna().sum()), include_groups=False)
        out = pd.DataFrame({f"n_{prefix}_valid": valid,
                             f"n_{prefix}_zero": zero,
                             f"n_{prefix}_null": null})
        return out

    n_cells = g.size().rename("n_rows")
    air = _shares("AIR_TIME", "air_time")
    ramp = _shares("RAMP_TO_RAMP", "ramp")
    dep_total = g["DEPARTURES_PERFORMED"].sum().rename("dep_total")
    median_dep = g["DEPARTURES_PERFORMED"].median().rename("median_departures")
    dep_home0 = g.apply(lambda d: float(d.loc[d["flag_home_share_zero"], "DEPARTURES_PERFORMED"].sum()),
                         include_groups=False).rename("dep_home0")

    out = pd.concat([n_cells, air, ramp, dep_total, median_dep, dep_home0], axis=1).reset_index()
    for prefix in ("air_time", "ramp"):
        for kind in ("valid", "zero", "null"):
            out[f"share_{prefix}_{kind}"] = out[f"n_{prefix}_{kind}"] / out["n_rows"]
    out["share_dep_home0"] = out["dep_home0"] / out["dep_total"]
    return out


def main() -> int:
    logger = setup_logger("03_coverage_audit", str(LOG_FILE))

    if not PARQUET_T100.exists():
        logger.error("BLOCKED: %s not found — FIX-01 must run first.", PARQUET_T100)
        return 1
    if not PARQUET_NATION.exists():
        logger.error("BLOCKED: %s not found — FIX-02 must run first (even if it "
                      "ends BLOCKED-NEEDS-HUMAN, it must produce this parquet).", PARQUET_NATION)
        return 1
    if not PRECISION_AUDIT_CSV_IN.exists():
        logger.error("BLOCKED: %s not found — FIX-02's precision diagnostic is required "
                      "for the share_dep_home0 column commissioned by the overseer's ruling.",
                      PRECISION_AUDIT_CSV_IN)
        return 1

    # Corridor airport lists must be disjoint, or a row could be double-counted.
    all_airports = [a for lst in CORRIDORS.values() for a in lst]
    assert len(all_airports) == len(set(all_airports)), "corridor airport lists overlap"

    (OUT_DIR / "tables").mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "figures").mkdir(parents=True, exist_ok=True)

    # --- Load ---------------------------------------------------------------
    cols = ["UNIQUE_CARRIER", "YEAR", "MONTH", "ORIGIN", "DEST",
            "ORIGIN_COUNTRY", "DEST_COUNTRY", "DEPARTURES_PERFORMED",
            "AIR_TIME", "RAMP_TO_RAMP", "SERVICE_CLASS", "is_passenger", "CARRIER_GROUP"]
    t100 = pd.read_parquet(PARQUET_T100, columns=cols)
    logger.info("Loaded t100_raw.parquet: %d rows.", len(t100))

    nation = pd.read_parquet(PARQUET_NATION)
    logger.info("Loaded carrier_nation.parquet: %d (UNIQUE_CARRIER, year) rows.", len(nation))

    precision = pd.read_csv(PRECISION_AUDIT_CSV_IN)
    logger.info("Loaded carrier_nation_precision_audit.csv: %d matched-foreign codes.", len(precision))

    # --- Step 1: passenger service, departures > 0 (round file step 1) -----
    n_before = len(t100)
    sample = t100.loc[t100["is_passenger"] & (t100["DEPARTURES_PERFORMED"] > 0)].copy()
    logger.info("Filter passenger service (is_passenger==True) & DEPARTURES_PERFORMED>0: "
                "%d -> %d rows.", n_before, len(sample))

    # US-touching sanity check (Part 0): every international-segment row has
    # exactly one US endpoint. This is what lets a single "foreign airport"
    # be read off each row for the corridor assignment below.
    neither_us = sample.loc[(sample["ORIGIN_COUNTRY"] != "US") & (sample["DEST_COUNTRY"] != "US")]
    both_us = sample.loc[(sample["ORIGIN_COUNTRY"] == "US") & (sample["DEST_COUNTRY"] == "US")]
    if len(neither_us) or len(both_us):
        logger.warning("US-touching assumption violated: %d rows with neither end US, "
                        "%d rows with both ends US.", len(neither_us), len(both_us))
    else:
        logger.info("US-touching check: every sampled row has exactly one US endpoint (verified).")

    # --- Merge operator nation, keyed (UNIQUE_CARRIER, year) ----------------
    merged = sample.merge(nation, left_on=["UNIQUE_CARRIER", "YEAR"],
                           right_on=["UNIQUE_CARRIER", "year"], how="left", indicator=True)
    log_merge(logger, sample, nation, merged, on="(UNIQUE_CARRIER, YEAR)", how="left")

    # --- Classify and log the excluded population (overseer's condition) ---
    null_carrier = merged["UNIQUE_CARRIER"].isna()
    match_method = merged["match_method"]
    unmatched_code = match_method.eq("unmatched")
    refused = match_method.eq("refused_suffix_collision")
    matched = match_method.isin(MATCHED_METHODS)

    unexpected = ~(null_carrier | unmatched_code | refused | matched)
    if unexpected.any():
        logger.error("Unexpected match_method values found for %d rows: %s",
                      int(unexpected.sum()), merged.loc[unexpected, "match_method"].unique())
        return 1
    assert (null_carrier | unmatched_code | refused | matched).all(), \
        "every row must fall into exactly one of the four match categories"

    category = pd.Series("matched", index=merged.index)
    category.loc[null_carrier] = "null_carrier_code"
    category.loc[unmatched_code] = "unmatched_code"
    category.loc[refused] = "refused_suffix_collision"
    merged["exclusion_category"] = category

    excluded_mask = category != "matched"
    excl = merged.loc[excluded_mask].copy()
    # Overseer cycle-2 required action 3: the excluded population's own AIR_TIME
    # coverage, split by CARRIER_GROUP, so "no exceptions" (foreign carriers never
    # report AIR_TIME, matched or not) is citable from this CSV directly.
    excl_summary = (excl.groupby(["exclusion_category", "UNIQUE_CARRIER", "CARRIER_GROUP"],
                                  dropna=False)
                     .agg(n_rows=("DEPARTURES_PERFORMED", "size"),
                          departures=("DEPARTURES_PERFORMED", "sum"),
                          n_air_gt0=("AIR_TIME", lambda s: int((s > 0).sum())))
                     .reset_index()
                     .sort_values(["exclusion_category", "departures"], ascending=[True, False]))
    excl_summary["share_air_gt0"] = excl_summary["n_air_gt0"] / excl_summary["n_rows"]
    excl_summary.to_csv(MATCHING_EXCLUSIONS_CSV, index=False)
    n_excl_codes = excl_summary["UNIQUE_CARRIER"].nunique()
    n_excl_rows = int(excluded_mask.sum())
    excl_departures = float(excl["DEPARTURES_PERFORMED"].sum())
    logger.info("Excluded population (FIX-02 mapping): %d codes / %d segment-month rows / "
                "%.0f departures logged to %s.",
                n_excl_codes, n_excl_rows, excl_departures, MATCHING_EXCLUSIONS_CSV)
    for cat, d in excl.groupby("exclusion_category"):
        logger.info("  %s: %d codes, %d rows, %.0f departures.",
                    cat, d["UNIQUE_CARRIER"].nunique(dropna=False), len(d),
                    float(d["DEPARTURES_PERFORMED"].sum()))
    excl_is_us = excl["CARRIER_GROUP"].isin([1, 2, 3, 7])
    for is_us_flag, label in ((False, "foreign-group"), (True, "US-group")):
        d = excl.loc[excl_is_us == is_us_flag]
        if len(d):
            logger.info("  excluded population AIR_TIME coverage, %s: %d rows, "
                        "%d with AIR_TIME>0 (share %.6f).",
                        label, len(d), int((d["AIR_TIME"] > 0).sum()),
                        float((d["AIR_TIME"] > 0).mean()))

    matched_sample = merged.loc[matched].copy()
    logger.info("Matched sample for coverage audit: %d / %d rows (%.4f of segment-months, "
                "%.4f of departures).",
                len(matched_sample), len(merged), len(matched_sample) / len(merged),
                matched_sample["DEPARTURES_PERFORMED"].sum() / merged["DEPARTURES_PERFORMED"].sum())

    # --- Attach FIX-02's per-code precision flag (overseer's condition) ----
    # us_by_construction codes are not in the precision audit — their nation
    # is verified independently via BTS's own CARRIER_GROUP field, not from
    # route geography (same rationale FIX-02 states for excluding them from
    # the cross-border drift test) — so they get flag_home_share_zero=False
    # by construction, not by omission.
    prec = precision[["unique_carrier", "flag_home_share_zero"]].rename(
        columns={"unique_carrier": "UNIQUE_CARRIER"})
    matched_sample = matched_sample.merge(prec, on="UNIQUE_CARRIER", how="left")
    n_unflagged = matched_sample["flag_home_share_zero"].isna().sum()
    us_construction_rows = (matched_sample["match_method"] == "us_by_construction").sum()
    logger.info("Precision-flag merge: %d rows unmatched to precision_audit "
                "(expect ~= us_by_construction rows = %d).", n_unflagged, us_construction_rows)
    matched_sample["flag_home_share_zero"] = matched_sample["flag_home_share_zero"].fillna(False)

    # --- coverage_audit.csv: nation x year -----------------------------
    cell = _cell_stats(matched_sample, ["nation_iso2", "YEAR"])
    cell = cell.rename(columns={"nation_iso2": "nation", "YEAR": "year"})
    cell["covid_flag"] = cell["year"].isin(COVID_YEARS)
    cell["match_sensitive"] = cell["nation"].isin(MATCH_SENSITIVE_NATIONS)
    cell["gate_g6_pass"] = cell["share_air_time_valid"] >= G6_MIN
    cell = cell.sort_values(["nation", "year"]).reset_index(drop=True)
    cell.to_csv(COVERAGE_AUDIT_CSV, index=False)
    logger.info("Wrote %s: %d nation x year cells.", COVERAGE_AUDIT_CSV, len(cell))

    # --- G1-G5 sanity: share columns in [0,1]; internal consistency --------
    share_cols = [c for c in cell.columns if "share" in c]
    for c in share_cols:
        bad = cell[c].dropna()
        bad = bad[(bad < -1e-9) | (bad > 1 + 1e-9)]
        if len(bad):
            logger.error("G5 FAIL: column %s outside [0,1] in %d rows.", c, len(bad))
            return 1
    consistency = (cell["share_air_time_valid"] + cell["share_air_time_zero"]
                   + cell["share_air_time_null"] - 1.0).abs()
    if (consistency > 1e-9).any():
        logger.error("Internal consistency FAIL: air-time shares don't sum to 1 in %d cells.",
                     int((consistency > 1e-9).sum()))
        return 1
    logger.info("G5 pass: all %d share columns within [0,1]; air-time shares sum to 1 in every cell.",
                len(share_cols))

    # --- G6: exclude cells below 0.50 airborne-time coverage ----------------
    excluded_cells = cell.loc[~cell["gate_g6_pass"],
                               ["nation", "year", "share_air_time_valid", "dep_total",
                                "n_rows", "covid_flag", "match_sensitive"]].copy()
    excluded_cells["reason"] = "share_air_time_valid < " + str(G6_MIN)
    excluded_cells.to_csv(COVERAGE_EXCLUDED_CSV, index=False)
    n_fail_g6 = len(excluded_cells)
    dep_fail_g6 = float(excluded_cells["dep_total"].sum())
    dep_total_all = float(cell["dep_total"].sum())
    logger.info("G6: %d / %d nation x year cells fail (share_air_time_valid < %.2f), "
                "carrying %.0f / %.0f departures (%.4f share). Written to %s.",
                n_fail_g6, len(cell), G6_MIN, dep_fail_g6, dep_total_all,
                dep_fail_g6 / dep_total_all if dep_total_all else float("nan"),
                COVERAGE_EXCLUDED_CSV)

    # VERIFY: exact set equality between the <0.50 cells in coverage_audit.csv
    # and the rows of coverage_excluded_cells.csv (round file's VERIFY item).
    set_from_audit = set(map(tuple, cell.loc[~cell["gate_g6_pass"], ["nation", "year"]].values))
    set_from_excluded = set(map(tuple, excluded_cells[["nation", "year"]].values))
    assert set_from_audit == set_from_excluded, \
        "G6 VERIFY failed: excluded-cells set does not match <0.50 cells in coverage_audit.csv"
    logger.info("G6 VERIFY: excluded-cells set matches <0.50 cells in coverage_audit.csv exactly "
                "(%d cells).", len(set_from_audit))

    # --- coverage_by_corridor.csv: restrict to NEW-06 anchor corridors -----
    airport_to_corridor = {a: name for name, lst in CORRIDORS.items() for a in lst}
    foreign_airport = np.where(matched_sample["DEST_COUNTRY"] == "US", matched_sample["ORIGIN"],
                                np.where(matched_sample["ORIGIN_COUNTRY"] == "US",
                                         matched_sample["DEST"], pd.NA))
    matched_sample["foreign_airport"] = foreign_airport
    matched_sample["corridor"] = matched_sample["foreign_airport"].map(airport_to_corridor)
    corridor_sample = matched_sample.loc[matched_sample["corridor"].notna()].copy()
    logger.info("Corridor sample (rows touching a NEW-06 anchor airport): %d / %d rows.",
                len(corridor_sample), len(matched_sample))

    corr = _cell_stats(corridor_sample, ["corridor", "nation_iso2", "YEAR"])
    corr = corr.rename(columns={"nation_iso2": "nation", "YEAR": "year"})
    corr["covid_flag"] = corr["year"].isin(COVID_YEARS)
    corr["match_sensitive"] = corr["nation"].isin(MATCH_SENSITIVE_NATIONS)
    corr["gate_g6_pass"] = corr["share_air_time_valid"] >= G6_MIN
    # Overseer cycle-2 required action 6 (Part 0's direction rule): rows are already
    # directed in T-100 (ORIGIN->DEST) and this cell is pooled over BOTH directions
    # (US-origin outbound legs and US-destination inbound legs) without ever
    # symmetrizing individual rows first -- state that pooling explicitly rather than
    # leaving it implicit.
    corr["directions"] = "both (US-origin outbound + US-destination inbound pooled)"
    corr = corr.sort_values(["corridor", "nation", "year"]).reset_index(drop=True)
    corr.to_csv(COVERAGE_CORRIDOR_CSV, index=False)
    logger.info("Wrote %s: %d corridor x nation x year cells.", COVERAGE_CORRIDOR_CSV, len(corr))

    corr_share_cols = [c for c in corr.columns if "share" in c]
    for c in corr_share_cols:
        bad = corr[c].dropna()
        bad = bad[(bad < -1e-9) | (bad > 1 + 1e-9)]
        if len(bad):
            logger.error("G5 FAIL (corridor): column %s outside [0,1] in %d rows.", c, len(bad))
            return 1

    # Ex-ante rationale check: anchor corridors' FOREIGN operators below 0.50.
    corr_foreign = corr.loc[corr["nation"] != "US"]
    corr_fail = corr_foreign.loc[~corr_foreign["gate_g6_pass"]]
    if len(corr_fail):
        logger.warning("Anchor-corridor foreign-operator cells below G6 (0.50): %d "
                        "(counts against proceeding, per round file ex-ante rationale). "
                        "corridors affected: %s",
                        len(corr_fail), sorted(corr_fail["corridor"].unique()))
    else:
        logger.info("No anchor-corridor foreign-operator nation x year cell falls below "
                     "the 0.50 airborne-time coverage bound.")

    # --- tables/tab_coverage_audit.tex: nation x decade, from the CSV only -
    cell["decade"] = (cell["year"] // 10) * 10
    dep_w = cell["dep_total"].clip(lower=0)
    cell["_w_air"] = cell["share_air_time_valid"] * dep_w
    cell["_w_home0"] = cell["share_dep_home0"] * dep_w

    by_nation_decade = (cell.groupby(["nation", "decade"])
                        .agg(w_air=("_w_air", "sum"), w_home0=("_w_home0", "sum"),
                             dep=("dep_total", "sum"))
                        .reset_index())
    by_nation_decade["cov"] = by_nation_decade["w_air"] / by_nation_decade["dep"]
    decades = sorted(cell["decade"].unique())

    pivot_cov = by_nation_decade.pivot(index="nation", columns="decade", values="cov")
    pivot_dep = by_nation_decade.pivot(index="nation", columns="decade", values="dep")

    nation_totals = (cell.groupby("nation")
                     .agg(dep_total=("dep_total", "sum"), w_air=("_w_air", "sum"),
                          w_home0=("_w_home0", "sum"), n_cells=("year", "size"),
                          n_fail_g6=("gate_g6_pass", lambda s: int((~s).sum())))
                     .reset_index())
    nation_totals["overall_coverage"] = nation_totals["w_air"] / nation_totals["dep_total"]
    nation_totals["overall_home0"] = nation_totals["w_home0"] / nation_totals["dep_total"]
    nation_totals = nation_totals.sort_values("dep_total", ascending=False).reset_index(drop=True)

    def fmt_pct(x):
        return "--" if pd.isna(x) else f"{100 * x:.1f}"

    lines = []
    lines.append("% Auto-generated by code/03_audit/03_coverage_audit.py -- do not hand-edit.")
    lines.append("% Every number is read from rounds/round-1-t100-panel/coverage_audit.csv.")
    lines.append("\\begin{table}[htbp]")
    lines.append("\\centering")
    col_spec = "l" + "r" * len(decades) + "rrr"
    lines.append(f"\\begin{{tabular}}{{{col_spec}}}")
    lines.append("\\toprule")
    header = ["Nation"] + [f"{d}s cov.\\ \\%" for d in decades] + \
        ["Total dep.", "Overall cov.\\ \\%", "home0 \\%"]
    lines.append(" & ".join(header) + " \\\\")
    lines.append("\\midrule")
    for _, row in nation_totals.iterrows():
        nat = row["nation"]
        label = nat + ("$^{\\dagger}$" if nat in MATCH_SENSITIVE_NATIONS else "")
        cells = [label]
        for d in decades:
            v = pivot_cov.loc[nat, d] if (nat in pivot_cov.index and d in pivot_cov.columns) else np.nan
            cells.append(fmt_pct(v))
        cells.append(f"{row['dep_total']:,.0f}")
        cells.append(fmt_pct(row["overall_coverage"]))
        cells.append(fmt_pct(row["overall_home0"]))
        lines.append(" & ".join(cells) + " \\\\")
    lines.append("\\bottomrule")
    lines.append("\\end{tabular}")
    lines.append(f"\\caption{{Airborne-time reporting coverage by operator nation and decade, "
                 f"{SAMPLE_LABEL}. ``cov.'' = share of passenger segment-months with "
                 f"\\texttt{{AIR\\_TIME}} $>0$; ``home0'' = departures-weighted share of the "
                 f"nation's segment-months resting on a carrier code whose mapped home country "
                 f"never appears as one of its own T-100 endpoints (FIX-02 precision "
                 f"diagnostic). $^{{\\dagger}}$RU and IR are MATCH-SENSITIVE: FIX-02's "
                 f"carrier--nation mapping is BLOCKED-NEEDS-HUMAN on a DEGENERATE-GATE and "
                 f"these two nations' precision readings are the worst in the sample.}}")
    lines.append("\\label{tab:coverage_audit}")
    lines.append("\\end{table}")
    TABLE_TEX.write_text("\n".join(lines) + "\n")
    logger.info("Wrote %s: %d nation rows x %d decade columns.", TABLE_TEX,
                len(nation_totals), len(decades))

    # --- figures/fig_coverage_heatmap.png -----------------------------------
    heat = cell.pivot(index="nation", columns="year", values="share_air_time_valid")
    heat = heat.reindex(nation_totals["nation"])  # sorted by total departures, descending
    years = sorted(cell["year"].unique())
    heat = heat.reindex(columns=years)

    fig_h = max(6.0, 0.16 * len(heat.index))
    fig_w = max(8.0, 0.22 * len(years))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(heat.values, aspect="auto", vmin=0.0, vmax=1.0, cmap="RdYlGn",
                    interpolation="nearest")
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels([str(y) for y in years], rotation=90, fontsize=6)
    ylabels = [n + ("*" if n in MATCH_SENSITIVE_NATIONS else "") for n in heat.index]
    ax.set_yticks(range(len(heat.index)))
    ax.set_yticklabels(ylabels, fontsize=5)
    ax.set_xlabel("Year")
    ax.set_ylabel("Operator nation (ISO2), sorted by total departures")
    ax.set_title("Airborne-time coverage share by operator nation x year\n"
                f"{SAMPLE_LABEL}\n"
                "(* = MATCH-SENSITIVE: RU, IR -- FIX-02 DEGENERATE-GATE)",
                fontsize=10)
    covid_year_idx = [i for i, y in enumerate(years) if y in COVID_YEARS]
    if covid_year_idx:
        ax.axvspan(min(covid_year_idx) - 0.5, max(covid_year_idx) + 0.5,
                   fill=False, edgecolor="black", linestyle="--", linewidth=1.0)
    cbar = fig.colorbar(im, ax=ax, fraction=0.02, pad=0.02)
    cbar.set_label("Share with AIR_TIME > 0")
    fig.tight_layout()
    # Overseer cycle-2 required action 5: bbox_inches="tight" re-measures the actual
    # rendered artists (title included) before saving, so the mandatory
    # "US-touching international segments" sample label is never clipped regardless
    # of how tight_layout alone sized the canvas.
    fig.savefig(HEATMAP_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    logger.info("Wrote %s (%d nations x %d years).", HEATMAP_PNG, len(heat.index), len(years))

    logger.info("03_coverage_audit DONE. %d nation x year cells; %d fail G6 (%.4f of departures).",
               len(cell), n_fail_g6, dep_fail_g6 / dep_total_all if dep_total_all else float("nan"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
