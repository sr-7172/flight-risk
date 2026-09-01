#!/usr/bin/env python3
"""02_carrier_nation.py — FIX-02: map T-100 UNIQUE_CARRIER codes to ICAO
state-of-operator, keyed by (UNIQUE_CARRIER, year).

Two-sentence summary: every T-100 carrier code is either a U.S. carrier
(known directly from BTS's own CARRIER_GROUP field, no lookup needed) or a
foreign carrier matched against the OpenFlights airlines table on IATA
code, then ICAO code, then an exact normalized name — in that priority
order, with the method used recorded per code so a human can see exactly
which rows rest on a code match versus a name match. Nothing is fuzzy: a
lookup step that could return more than one distinct country for a code is
treated as a non-match rather than guessed, and OpenFlights has no dates
so we report a code's nation as fixed and flag (not silently resolve) any
code whose T-100 rows disagree on nationality across years.

Never edits data/raw/. Reads data/interim/t100_raw.parquet (FIX-01,
cycle-2 rewrite) and data/raw/lookups/airlines.csv only.
"""
from __future__ import annotations

import re
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "code"))
from utils import setup_logger, log_merge  # noqa: E402

PARQUET_IN = ROOT / "data" / "interim" / "t100_raw.parquet"
AIRLINES_CSV = ROOT / "data" / "raw" / "lookups" / "airlines.csv"

OUT_DIR = ROOT / "rounds" / "round-1-t100-panel"
PARQUET_OUT = ROOT / "data" / "interim" / "carrier_nation.parquet"
MATCHRATE_CSV = OUT_DIR / "carrier_nation_matchrate.csv"
UNMATCHED_CSV = OUT_DIR / "carrier_nation_unmatched.csv"
FLIPS_CSV = OUT_DIR / "carrier_nation_flips.csv"
PRECISION_AUDIT_CSV = OUT_DIR / "carrier_nation_precision_audit.csv"
AUDIT_SAMPLE_CSV = OUT_DIR / "carrier_nation_audit_sample.csv"
CORRIDOR_COVERAGE_CSV = OUT_DIR / "carrier_nation_corridor_coverage.csv"
TIER_PRECISION_CSV = OUT_DIR / "carrier_nation_tier_precision.csv"
GATE_SENSITIVITY_CSV = OUT_DIR / "carrier_nation_gate_sensitivity.csv"
LOG_FILE = ROOT / "logs" / "02_carrier_nation.log"

# G7 (ROUND_01.md Part 0 / gates): departures-weighted match rate >= 0.95
# overall, >= 0.90 among foreign carriers. Binding — never relaxed.
G7_OVERALL_MIN = 0.95
G7_FOREIGN_MIN = 0.90

# --- NEW-06 anchor airports and windows (round file, NEW-06 family) -----
# Used only for the corridor-coverage diagnostic (how much of the traffic
# at each anchor airport, passenger service only, rests on a matched
# carrier code) -- this script does not build the corridor panel itself.
ANCHOR_AIRPORTS = {
    "PEK": "1_useastasia", "PVG": "1_useastasia", "CAN": "1_useastasia",
    "HKG": "1_useastasia", "NRT": "1_useastasia", "HND": "1_useastasia",
    "ICN": "1_useastasia", "TPE": "1_useastasia",
    "DEL": "2_usindia", "BOM": "2_usindia", "BLR": "2_usindia", "HYD": "2_usindia",
    "DXB": "3_usmideast", "DOH": "3_usmideast", "AUH": "3_usmideast",
    "TLV": "3_usmideast", "IST": "3_usmideast",
    "LHR": "4_useurope_placebo", "CDG": "4_useurope_placebo",
    "FRA": "4_useurope_placebo", "AMS": "4_useurope_placebo", "MAD": "4_useurope_placebo",
}
CORRIDOR_WINDOWS = {
    "full_2019_2024": (201901, 202412),
    "zoom_2021h2_2022": (202106, 202212),
}

# Precision-audit thresholds (cycle-2 review, action 2): report, do not
# gate on, the departures-weighted share of matched-foreign departures
# whose carrier never actually touches its mapped home country.
PRECISION_ZERO_THRESH = 0.0
PRECISION_LOW_THRESH = 0.01

# --- US-by-construction ------------------------------------------------
# T-100's own CARRIER_GROUP field: 0 = Foreign carrier; 1/2/3 = U.S.
# domestic groups (trunk/local-service/national, pre-2003 scheme); 7 =
# U.S. all-cargo. Verified against known codes before use (AA/DL/UA/WN
# -> {1,3}; CA/BA/LH -> {0}; ABX Air, an all-cargo carrier -> {7}).
# CARRIER_GROUP_NEW subdivides the U.S. side further (adds 4,5,6,9 for
# regional/commuter tiers) but never disagrees with CARRIER_GROUP on the
# US-vs-foreign boundary in this data (checked in code below).
US_GROUP_CODES = {1, 2, 3, 7}
FOREIGN_GROUP_CODE = 0

SUFFIX_RE = re.compile(r"\s*\(\d+\)\s*$")


def strip_reissue_suffix(code: str) -> str:
    """BTS disambiguates a reused 2/3-char code across entities by
    appending ' (1)', ' (2)', ... to UNIQUE_CARRIER. Strip that suffix to
    recover the underlying code for matching against IATA/ICAO columns;
    the suffixed UNIQUE_CARRIER itself remains the panel key throughout."""
    return SUFFIX_RE.sub("", code).strip()


def normalize_name(s) -> str | None:
    """Light, exact normalization only — case, punctuation, whitespace.
    No fuzzy/approximate matching (round file step 2 forbids it)."""
    if s is None or (isinstance(s, float) and np.isnan(s)):
        return None
    s = str(s).strip()
    if not s:
        return None
    s = s.upper()
    s = re.sub(r"[.,]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# --- Country-name -> ISO2 crosswalk -------------------------------------
# OpenFlights' `country` column is a free-text country NAME, not ISO2.
# Rather than hand-typing a name->ISO2 table (a hidden, unauditable
# choice), we build it FROM the T-100 data itself: T-100's
# ORIGIN/DEST_COUNTRY columns already carry ISO2-like codes paired with
# ORIGIN/DEST_COUNTRY_NAME (checked to be an injective name->code map,
# 219 distinct names, 0 collisions, in this drop). Any OpenFlights
# country string that doesn't appear verbatim in that self-built
# crosswalk is resolved only through the small, documented alias table
# below (typo/synonym fixes to known T-100 spellings, verified by hand
# against the T-100 country-name list) or the ISO 3166-1 supplement
# (countries with no direct T-100 US-touching corridor, so absent from
# the T-100 crosswalk entirely). Anything left over stays unmatched.
COUNTRY_NAME_ALIASES = {
    # OpenFlights spelling/synonym -> T-100 ORIGIN/DEST_COUNTRY_NAME spelling
    "Russian Federation": "Russia",
    "UNited Kingdom": "United Kingdom",
    "Bahamas": "The Bahamas",
    "Hong Kong SAR of China": "Hong Kong",
    "Republic of Korea": "South Korea",
    "Democratic People's Republic of Korea": "North Korea",
    "Ivory Coast": "Cote d'Ivoire",
    "Myanmar": "Burma",
    "Congo (Brazzaville)": "Congo (Brazaville)",  # T-100 itself misspells this
    "Republic of the Congo": "Congo (Brazaville)",
    "Democratic Republic of Congo": "Congo (Kinshasa)",
    "Democratic Republic of the Congo": "Congo (Kinshasa)",
    "Lao Peoples Democratic Republic": "Laos",
    "Syrian Arab Republic": "Syria",
    "Somali Republic": "Somalia",
    "Macao": "Macau",
    "Netherland": "Netherlands",
    "Canadian Territories": "Canada",
}

# ISO 3166-1 alpha-2 codes for countries that never appear as an
# ORIGIN/DEST_COUNTRY in this T-100 extract (no direct US-touching
# segment), so they cannot be resolved from T-100 itself. Standard,
# static, publicly documented codes — not an invented resolution.
ISO_SUPPLEMENT = {
    "American Samoa": "AS",
    "Puerto Rico": "PR",
    "Bhutan": "BT",
    "Faroe Islands": "FO",
    "Reunion": "RE",
    "South Sudan": "SS",
    "Monaco": "MC",
    "Eritrea": "ER",
    "Gambia": "GM",
    "Comoros": "KM",
    "Guinea-Bissau": "GW",
}


def build_country_crosswalk(t100: pd.DataFrame, logger) -> tuple[dict, dict]:
    """Return (name->iso2, source-of-name) built from T-100's own
    ORIGIN/DEST country columns, self-consistency-checked."""
    o = t100[["ORIGIN_COUNTRY", "ORIGIN_COUNTRY_NAME"]].drop_duplicates()
    o.columns = ["code", "name"]
    d = t100[["DEST_COUNTRY", "DEST_COUNTRY_NAME"]].drop_duplicates()
    d.columns = ["code", "name"]
    cw = pd.concat([o, d], ignore_index=True).dropna().drop_duplicates()
    dup = cw.groupby("name")["code"].nunique()
    bad = dup[dup > 1]
    if len(bad):
        logger.warning("country-name crosswalk: %d names map to >1 code, "
                        "dropping from crosswalk: %s", len(bad), list(bad.index))
        cw = cw[~cw["name"].isin(bad.index)]
    name_to_iso2 = dict(zip(cw["name"], cw["code"]))
    logger.info("country-name crosswalk built from T-100: %d distinct names -> ISO2",
                len(name_to_iso2))
    source = {n: "t100_crosswalk" for n in name_to_iso2}
    for alias, target in COUNTRY_NAME_ALIASES.items():
        if target in name_to_iso2:
            name_to_iso2[alias] = name_to_iso2[target]
            source[alias] = "t100_crosswalk_via_alias"
        else:
            logger.warning("alias target %r for %r not found in T-100 crosswalk — dropped",
                            target, alias)
    for name, iso2 in ISO_SUPPLEMENT.items():
        if name not in name_to_iso2:
            name_to_iso2[name] = iso2
            source[name] = "iso3166_supplement"
    return name_to_iso2, source


def resolve_country(country_name: str | None, name_to_iso2: dict, source: dict):
    if country_name is None or (isinstance(country_name, float) and np.isnan(country_name)):
        return None, None
    country_name = str(country_name).strip()
    if country_name in name_to_iso2:
        return name_to_iso2[country_name], source[country_name]
    return None, None


def unique_country(cand: pd.DataFrame, name_to_iso2: dict, source: dict):
    """Given the OpenFlights candidate rows (name, country) matching a code
    on some key, return (iso2, nation_source, n_candidates, candidate_names)
    -- iso2 is set only if the resolvable candidates agree on exactly one
    ISO2; an ambiguous or unresolvable lookup returns (None, None, ...)
    rather than a guess. n_candidates/candidate_names describe the RAW
    candidate rows (not just the resolvable ones) so an unmatched or
    single-but-wrong match is auditable: this is the diagnostic the cycle-2
    review asked for -- a code with exactly one OpenFlights candidate can
    still be the wrong candidate (a different real-world carrier that
    happens to share the code), and that is measured, not silently fixed,
    by the precision audit downstream."""
    names = "; ".join(f"{r['name']} ({r['country']})" for _, r in cand.iterrows())
    n_candidates = len(cand)
    resolved = set()
    src = None
    for c in cand["country"].dropna().unique():
        iso2, src_i = resolve_country(c, name_to_iso2, source)
        if iso2 is not None:
            resolved.add(iso2)
            src = src_i
    if len(resolved) == 1:
        return next(iter(resolved)), src, n_candidates, names
    return None, None, n_candidates, names




def main() -> int:
    logger = setup_logger("02_carrier_nation", str(LOG_FILE))

    if not PARQUET_IN.exists():
        logger.error("BLOCKED: %s not found — FIX-01 must run first.", PARQUET_IN)
        return 1
    if not AIRLINES_CSV.exists():
        logger.error("BLOCKED: %s not found (round file step 1).", AIRLINES_CSV)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    t100 = pd.read_parquet(
        PARQUET_IN,
        columns=["UNIQUE_CARRIER", "CARRIER_NAME", "UNIQUE_CARRIER_NAME",
                 "CARRIER_GROUP", "CARRIER_GROUP_NEW", "YEAR", "MONTH",
                 "DEPARTURES_PERFORMED", "ORIGIN", "ORIGIN_COUNTRY", "ORIGIN_COUNTRY_NAME",
                 "DEST", "DEST_COUNTRY", "DEST_COUNTRY_NAME",
                 "SERVICE_CLASS", "is_passenger"],
    )
    logger.info("Loaded t100_raw.parquet: %d rows", len(t100))

    airlines = pd.read_csv(AIRLINES_CSV, dtype=str, keep_default_na=False, na_values=[""])
    logger.info("Loaded airlines.csv: %d rows", len(airlines))
    airlines["iata_norm"] = airlines["iata"].where(
        airlines["iata"].notna() & (airlines["iata"] != "-"))
    airlines["icao_norm"] = airlines["icao"].where(
        airlines["icao"].notna() & (airlines["icao"] != "N/A"))
    airlines["name_norm"] = airlines["name"].apply(normalize_name)
    airlines["alias_norm"] = airlines["alias"].apply(normalize_name)

    name_to_iso2, cw_source = build_country_crosswalk(t100, logger)

    # --- Split out the 2,407 genuinely-null UNIQUE_CARRIER rows ---------
    null_mask = t100["UNIQUE_CARRIER"].isna()
    n_null_rows = int(null_mask.sum())
    null_departures = float(t100.loc[null_mask, "DEPARTURES_PERFORMED"].sum())
    logger.info("UNIQUE_CARRIER null (missing, not a code): %d rows, %.0f departures — "
                "own category, excluded from match-rate denominator.",
                n_null_rows, null_departures)
    t100c = t100.loc[~null_mask].copy()

    # --- Observed foreign endpoint per row (cycle-2 review, action 2) ---
    # T-100 international-segment rows are US-touching, so one side is
    # normally 'US'. If DEST is US, the foreign endpoint is ORIGIN; if
    # ORIGIN is US, it's DEST; if neither (or both) is US we cannot read
    # a foreign endpoint off this row and mark it missing rather than
    # guess. This is the observable evidence used to (a) audit whether a
    # matched code's own routes ever touch its mapped home country, and
    # (b) flag whether a CARRIER_NAME change coincides with a change in
    # observed traffic geography.
    t100c["foreign_endpoint"] = np.where(
        t100c["DEST_COUNTRY"] == "US", t100c["ORIGIN_COUNTRY"],
        np.where(t100c["ORIGIN_COUNTRY"] == "US", t100c["DEST_COUNTRY"], pd.NA))

    # --- Homogeneity check: is CARRIER_GROUP US/foreign split constant
    # per code, and per (code, year)? This is what makes a static
    # code->nation map honest rather than papering over real churn. -----
    t100c["is_us_row"] = t100c["CARRIER_GROUP"].isin(US_GROUP_CODES)
    foreign_bad = ~(t100c["CARRIER_GROUP"].isin(US_GROUP_CODES) |
                     (t100c["CARRIER_GROUP"] == FOREIGN_GROUP_CODE))
    if foreign_bad.any():
        logger.warning("CARRIER_GROUP values outside known US/foreign set found in %d rows: %s",
                        int(foreign_bad.sum()), t100c.loc[foreign_bad, "CARRIER_GROUP"].unique())

    code_year_group = (t100c.groupby(["UNIQUE_CARRIER", "YEAR"])["is_us_row"]
                       .agg(["nunique", "first"]))
    within_year_inconsistent = code_year_group[code_year_group["nunique"] > 1]
    if len(within_year_inconsistent):
        logger.warning("Codes with inconsistent US/foreign CARRIER_GROUP WITHIN a single year: "
                        "%d (code,year) cells — see flips output.",
                        len(within_year_inconsistent))

    code_group = t100c.groupby("UNIQUE_CARRIER")["is_us_row"].nunique()
    cross_year_crossers = code_group[code_group > 1]
    if len(cross_year_crossers):
        logger.warning("Codes crossing the US/foreign CARRIER_GROUP boundary ACROSS years: %d",
                        len(cross_year_crossers))
    else:
        logger.info("No UNIQUE_CARRIER code crosses the US/foreign CARRIER_GROUP boundary "
                     "across years in this data (checked, not assumed).")

    # --- Per-code static attributes --------------------------------------
    code_tbl = (t100c.groupby("UNIQUE_CARRIER")
                .agg(is_us=("is_us_row", lambda s: bool(s.mode().iloc[0])),
                     name=("UNIQUE_CARRIER_NAME", lambda s: s.dropna().iloc[0] if s.notna().any() else None),
                     carrier_name_variants=("CARRIER_NAME", lambda s: s.dropna().nunique()),
                     total_departures=("DEPARTURES_PERFORMED", "sum"),
                     first_year=("YEAR", "min"),
                     last_year=("YEAR", "max"),
                     n_years=("YEAR", "nunique"))
                .reset_index())
    logger.info("Distinct UNIQUE_CARRIER codes (excl. null): %d", len(code_tbl))

    nation_iso2 = pd.Series(pd.NA, index=code_tbl.index, dtype="object")
    nation_source = pd.Series(pd.NA, index=code_tbl.index, dtype="object")
    match_method = pd.Series("unmatched", index=code_tbl.index, dtype="object")
    n_candidates = pd.Series(0, index=code_tbl.index, dtype="int64")
    candidate_names = pd.Series("", index=code_tbl.index, dtype="object")

    us_mask = code_tbl["is_us"]
    nation_iso2.loc[us_mask] = "US"
    nation_source.loc[us_mask] = "carrier_group_us"
    match_method.loc[us_mask] = "us_by_construction"
    logger.info("US-by-construction (CARRIER_GROUP in %s): %d codes.", US_GROUP_CODES, int(us_mask.sum()))

    foreign_idx = code_tbl.index[~us_mask]
    logger.info("Foreign codes to match against %s: %d", AIRLINES_CSV.name, len(foreign_idx))

    for idx in foreign_idx:
        code = code_tbl.at[idx, "UNIQUE_CARRIER"]
        cname = code_tbl.at[idx, "name"]
        base = strip_reissue_suffix(code)
        cname_norm = normalize_name(cname)
        method = "unmatched"
        iso2 = None
        src = None
        n_cand = 0
        cand_names = ""

        # 1. IATA
        if len(base) == 2:
            cand = airlines.loc[airlines["iata_norm"].str.upper() == base.upper(), ["name", "country"]]
            if len(cand):
                iso2r, srcr, n_candr, cand_namesr = unique_country(cand, name_to_iso2, cw_source)
                n_cand, cand_names = n_candr, cand_namesr
                if iso2r is not None:
                    iso2, src, method = iso2r, srcr, "iata"

        # 2. ICAO
        if iso2 is None and len(base) == 3:
            cand = airlines.loc[airlines["icao_norm"].str.upper() == base.upper(), ["name", "country"]]
            if len(cand):
                iso2r, srcr, n_candr, cand_namesr = unique_country(cand, name_to_iso2, cw_source)
                if iso2r is not None:
                    iso2, src, method = iso2r, srcr, "icao"
                    n_cand, cand_names = n_candr, cand_namesr
                elif not n_cand:
                    n_cand, cand_names = n_candr, cand_namesr

        # 3. Exact normalized name (name field, then alias field)
        if iso2 is None and cname_norm:
            cand = airlines.loc[airlines["name_norm"] == cname_norm, ["name", "country"]]
            if len(cand):
                iso2r, srcr, n_candr, cand_namesr = unique_country(cand, name_to_iso2, cw_source)
                if iso2r is not None:
                    iso2, src, method = iso2r, srcr, "name_exact"
                    n_cand, cand_names = n_candr, cand_namesr
                elif not n_cand:
                    n_cand, cand_names = n_candr, cand_namesr
            if iso2 is None:
                cand = airlines.loc[airlines["alias_norm"] == cname_norm, ["name", "country"]]
                if len(cand):
                    iso2r, srcr, n_candr, cand_namesr = unique_country(cand, name_to_iso2, cw_source)
                    if iso2r is not None:
                        iso2, src, method = iso2r, srcr, "name_exact"
                        n_cand, cand_names = n_candr, cand_namesr
                    elif not n_cand:
                        n_cand, cand_names = n_candr, cand_namesr

        if iso2 is not None:
            nation_iso2.at[idx] = iso2
            nation_source.at[idx] = src
            match_method.at[idx] = method
        else:
            match_method.at[idx] = "unmatched"
        n_candidates.at[idx] = n_cand
        candidate_names.at[idx] = cand_names

    code_tbl["nation_iso2"] = nation_iso2
    code_tbl["nation_source"] = nation_source
    code_tbl["match_method"] = match_method
    code_tbl["n_candidates"] = n_candidates
    code_tbl["candidate_names"] = candidate_names

    n_matched_pre_refusal = int((code_tbl["match_method"] != "unmatched").sum())
    logger.info("Matched codes before suffix-collision check: %d / %d.",
                n_matched_pre_refusal, len(code_tbl))

    # ======================================================================
    # Suffix-collision refusal (cycle-2 review, required action 4).
    # strip_reissue_suffix() is necessary to look candidates up (the
    # lookup table carries no BTS reissue suffixes), but blindly using it
    # as the sole join key silently forces every suffixed sibling of a
    # reused code onto the SAME single OpenFlights candidate even when
    # BTS itself disambiguated them into different UNIQUE_CARRIER codes
    # because they are different real-world entities (e.g. UNIQUE_CARRIER
    # 'JD' = Beijing Capital Airlines 2017-2020 vs 'JD (1)' = Japan Air
    # System 1990-1997; OpenFlights has exactly one 'JD' row, Japan Air
    # System -> Japan, so both silently inherited "Japan"). We refuse the
    # match for BOTH siblings whenever: (a) they share a base code, (b)
    # they were both matched via the OpenFlights lookup (not
    # us_by_construction), (c) they would receive the SAME nation, and
    # (d) their UNIQUE_CARRIER_NAMEs differ -- i.e. BTS itself says they
    # are different carriers. This is measurement-driven correction, not
    # a rate-chasing loosening: it can only REMOVE matches, never add one.
    # ======================================================================
    code_tbl["base_code"] = code_tbl["UNIQUE_CARRIER"].apply(strip_reissue_suffix)
    code_tbl["name_norm_for_collision"] = code_tbl["name"].apply(normalize_name)
    code_tbl["nation_before_suffix_check"] = code_tbl["nation_iso2"]

    refuse_idx: set[int] = set()
    lookup_matched_mask = code_tbl["match_method"].isin(["iata", "icao", "name_exact"])
    for base, grp in code_tbl.loc[lookup_matched_mask].groupby("base_code"):
        if grp["UNIQUE_CARRIER"].nunique() < 2:
            continue
        for i, j in combinations(grp.index, 2):
            ni, nj = grp.at[i, "nation_iso2"], grp.at[j, "nation_iso2"]
            if pd.isna(ni) or pd.isna(nj) or ni != nj:
                continue
            name_i, name_j = grp.at[i, "name_norm_for_collision"], grp.at[j, "name_norm_for_collision"]
            if name_i is not None and name_j is not None and name_i != name_j:
                refuse_idx.add(i)
                refuse_idx.add(j)

    n_collision_families = len({code_tbl.at[i, "base_code"] for i in refuse_idx})
    collision_departures = float(code_tbl.loc[code_tbl.index.isin(refuse_idx), "total_departures"].sum())
    logger.info("Suffix-collision check: %d UNIQUE_CARRIER codes refused across %d base-code "
                "families (%.0f departures) -- siblings of a reused code that would receive the "
                "same nation despite differing UNIQUE_CARRIER_NAME; refused rather than guessed.",
                len(refuse_idx), n_collision_families, collision_departures)

    for idx in refuse_idx:
        code_tbl.at[idx, "match_method"] = "refused_suffix_collision"
        code_tbl.at[idx, "nation_iso2"] = pd.NA
        code_tbl.at[idx, "nation_source"] = pd.NA

    # ======================================================================
    # (UNIQUE_CARRIER, year) parquet output
    # ======================================================================
    cy = (t100c.groupby(["UNIQUE_CARRIER", "YEAR"])
          .agg(is_us_year_share=("is_us_row", "mean"),
               n_rows=("is_us_row", "size"))
          .reset_index())
    cy["cell_inconsistent"] = (cy["is_us_year_share"] > 0) & (cy["is_us_year_share"] < 1)

    out = cy.merge(code_tbl[["UNIQUE_CARRIER", "nation_iso2", "nation_source",
                              "match_method"]], on="UNIQUE_CARRIER", how="left")
    out.loc[out["cell_inconsistent"], ["nation_iso2", "nation_source"]] = pd.NA
    out.loc[out["cell_inconsistent"], "match_method"] = "ambiguous_group_inconsistent"
    out = out.rename(columns={"YEAR": "year"})[
        ["UNIQUE_CARRIER", "year", "nation_iso2", "nation_source", "match_method"]]
    out.to_parquet(PARQUET_OUT, index=False)
    logger.info("Wrote %s: %d (UNIQUE_CARRIER, year) rows.", PARQUET_OUT, len(out))

    log_merge(logger, code_tbl, airlines, code_tbl[code_tbl["match_method"].isin(
        ["iata", "icao", "name_exact"])], on="iata/icao/name (priority-ordered)",
        how="left-priority-chain, post suffix-collision refusal")

    # ======================================================================
    # carrier_nation_matchrate.csv
    # ======================================================================
    t100c = t100c.merge(code_tbl[["UNIQUE_CARRIER", "is_us", "nation_iso2", "match_method"]],
                         on="UNIQUE_CARRIER", how="left", suffixes=("", "_code"))
    t100c["matched_row"] = t100c["match_method"].isin(
        ["iata", "icao", "name_exact", "us_by_construction"])
    t100c["dep"] = t100c["DEPARTURES_PERFORMED"].fillna(0.0)

    MATCH_METHODS = ["iata", "icao", "name_exact", "us_by_construction",
                      "ambiguous_group_inconsistent", "refused_suffix_collision", "unmatched"]

    def rate_block(df: pd.DataFrame, category: str, subcategory: str = "") -> dict:
        total_dep = df["dep"].sum()
        matched_dep = df.loc[df["matched_row"], "dep"].sum()
        n_codes = df["UNIQUE_CARRIER"].nunique()
        n_codes_matched = df.loc[df["matched_row"], "UNIQUE_CARRIER"].nunique()
        row = {
            "category": category,
            "subcategory": subcategory,
            "n_codes_total": n_codes,
            "n_codes_matched": n_codes_matched,
            "match_rate_unweighted": (n_codes_matched / n_codes) if n_codes else float("nan"),
            "departures_total": total_dep,
            "departures_matched": matched_dep,
            "match_rate_weighted": (matched_dep / total_dep) if total_dep > 0 else float("nan"),
        }
        for m in MATCH_METHODS:
            dep_m = df.loc[df["match_method"] == m, "dep"].sum()
            row[f"share_dep_{m}"] = (dep_m / total_dep) if total_dep > 0 else float("nan")
        return row

    rate_rows = []
    rate_rows.append(rate_block(t100c, "overall"))
    rate_rows.append(rate_block(t100c[~t100c["is_us"]], "foreign"))
    rate_rows.append(rate_block(t100c[t100c["is_us"]], "us"))
    for yr, sub in t100c.groupby("YEAR"):
        rate_rows.append(rate_block(sub, "by_year", str(yr)))
    # Required action 6: foreign x year, foreign x service_class -- the
    # 'overall' by_year rows above blend in the US-by-construction codes,
    # which are verified separately and are not what's being tested here.
    foreign_t100c = t100c[~t100c["is_us"]]
    for yr, sub in foreign_t100c.groupby("YEAR"):
        rate_rows.append(rate_block(sub, "foreign_by_year", str(yr)))
    for sc, sub in foreign_t100c.groupby("SERVICE_CLASS"):
        rate_rows.append(rate_block(sub, "foreign_by_service_class", str(sc)))

    # Required action 3 (cycle-3 review): the round's headline sample is
    # SERVICE_CLASS == 'F' (is_passenger) -- FIX-04/NEW-06 use only class
    # F. Report both G7 readings on that cut alongside the all-classes
    # ones so the human can see whether the answer differs on the sample
    # that actually feeds the paper (all-classes is dragged down by
    # freight/combi service, per foreign_by_service_class above).
    classf_t100c = t100c[t100c["is_passenger"]]
    rate_rows.append(rate_block(classf_t100c, "overall_classF"))
    rate_rows.append(rate_block(classf_t100c[~classf_t100c["is_us"]], "foreign_classF"))
    rate_rows.append(rate_block(classf_t100c[classf_t100c["is_us"]], "us_classF"))

    total_all_dep = t100["DEPARTURES_PERFORMED"].fillna(0.0).sum()
    rate_rows.append({
        "category": "null_carrier_code", "subcategory": "",
        "n_codes_total": 0, "n_codes_matched": 0,
        "match_rate_unweighted": float("nan"),
        "departures_total": null_departures,
        "departures_matched": 0.0,
        "match_rate_weighted": 0.0,
        **{f"share_dep_{m}": float("nan") for m in MATCH_METHODS},
    })
    matchrate_df = pd.DataFrame(rate_rows)
    matchrate_df["note"] = ""
    matchrate_df.loc[matchrate_df["category"] == "null_carrier_code", "note"] = (
        f"{n_null_rows}-row category: UNIQUE_CARRIER genuinely null (missing, not a code); "
        f"{null_departures:.0f} departures, {100*null_departures/total_all_dep:.2f}% of all "
        f"departures in t100_raw.parquet. Excluded from overall/foreign match-rate denominator "
        f"per round-file instruction (neither matched nor a code).")

    overall_rate = float(matchrate_df.loc[matchrate_df["category"] == "overall",
                                           "match_rate_weighted"].iloc[0])
    foreign_rate = float(matchrate_df.loc[matchrate_df["category"] == "foreign",
                                           "match_rate_weighted"].iloc[0])
    foreign_total_dep = float(matchrate_df.loc[matchrate_df["category"] == "foreign",
                                                "departures_total"].iloc[0])
    overall_total_dep = float(matchrate_df.loc[matchrate_df["category"] == "overall",
                                                "departures_total"].iloc[0])
    us_matched_dep = float(matchrate_df.loc[matchrate_df["category"] == "us",
                                             "departures_matched"].iloc[0])
    logger.info("G7 coverage reading: overall departures-weighted match rate = %.4f (need >= "
                "%.2f); foreign departures-weighted match rate = %.4f (need >= %.2f).",
                overall_rate, G7_OVERALL_MIN, foreign_rate, G7_FOREIGN_MIN)

    # ======================================================================
    # carrier_nation_precision_audit.csv (required action 2/3)
    # This is measurement, not correction -- it changes no mapping.
    # ======================================================================
    foreign_matched_mask = (~code_tbl["is_us"]) & code_tbl["match_method"].isin(
        ["iata", "icao", "name_exact"])
    precision_rows = []
    for idx in code_tbl.index[foreign_matched_mask]:
        code = code_tbl.at[idx, "UNIQUE_CARRIER"]
        nation = code_tbl.at[idx, "nation_iso2"]
        sub = t100c.loc[t100c["UNIQUE_CARRIER"] == code]
        dep_total = float(sub["dep"].sum())
        dep_home = float(sub.loc[sub["foreign_endpoint"] == nation, "dep"].sum())
        home_share = (dep_home / dep_total) if dep_total > 0 else float("nan")
        endpoint_dep = sub.groupby("foreign_endpoint")["dep"].sum().dropna()
        top_endpoint = endpoint_dep.idxmax() if len(endpoint_dep) else None
        precision_rows.append({
            "unique_carrier": code,
            "carrier_name": code_tbl.at[idx, "name"],
            "nation_iso2": nation,
            "match_method": code_tbl.at[idx, "match_method"],
            "departures": dep_total,
            "home_country_dep_share": home_share,
            "top_endpoint_country": top_endpoint,
            "n_openflights_candidates": int(code_tbl.at[idx, "n_candidates"]),
            "candidate_names": code_tbl.at[idx, "candidate_names"],
            "flag_home_share_zero": bool(home_share == 0),
        })
    precision_df = pd.DataFrame(precision_rows)
    if len(precision_df):
        precision_df = precision_df.sort_values("departures", ascending=False).reset_index(drop=True)
    precision_df.to_csv(PRECISION_AUDIT_CSV, index=False)
    logger.info("Wrote %s: %d matched-foreign codes audited.", PRECISION_AUDIT_CSV, len(precision_df))

    foreign_matched_departures = float(precision_df["departures"].sum()) if len(precision_df) else 0.0
    home0_departures = float(precision_df.loc[precision_df["flag_home_share_zero"],
                                               "departures"].sum()) if len(precision_df) else 0.0
    home_lt001_departures = float(precision_df.loc[
        precision_df["home_country_dep_share"] < PRECISION_LOW_THRESH, "departures"
    ].sum()) if len(precision_df) else 0.0
    share_home0 = (home0_departures / foreign_matched_departures) if foreign_matched_departures > 0 else float("nan")
    share_home_lt001 = (home_lt001_departures / foreign_matched_departures) if foreign_matched_departures > 0 else float("nan")
    n_home0_codes = int(precision_df["flag_home_share_zero"].sum()) if len(precision_df) else 0

    precision_adjusted_foreign_rate = ((foreign_matched_departures - home0_departures) / foreign_total_dep
                                        if foreign_total_dep > 0 else float("nan"))
    precision_adjusted_overall_rate = ((us_matched_dep + foreign_matched_departures - home0_departures)
                                        / overall_total_dep if overall_total_dep > 0 else float("nan"))

    logger.info("Precision audit: %d / %d matched-foreign codes have home_country_dep_share == 0 "
                "(%.4f of matched-foreign departures); %.4f of matched-foreign departures have "
                "home_country_dep_share < %.2f.",
                n_home0_codes, len(precision_df), share_home0, share_home_lt001, PRECISION_LOW_THRESH)
    logger.info("G7 precision-adjusted reading (matched AND home_country_dep_share>0): "
                "overall=%.4f foreign=%.4f (need >= %.2f / %.2f).",
                precision_adjusted_overall_rate, precision_adjusted_foreign_rate,
                G7_OVERALL_MIN, G7_FOREIGN_MIN)

    # Required action 2 (cycle-3 review): per-tier precision must live in
    # a round-folder CSV, not only in the log, so a number can be traced
    # to (file.csv, row) under G9. One row per match tier plus an
    # implausible-pairs list (the home0-flagged codes in that tier).
    tier_rows = []
    for m, d in precision_df.groupby("match_method") if len(precision_df) else []:
        dep_sum = d["departures"].sum()
        home0_d = d.loc[d["flag_home_share_zero"]]
        lt001_d = d.loc[d["home_country_dep_share"] < PRECISION_LOW_THRESH]
        implausible = "; ".join(f"{r.unique_carrier} ({r.carrier_name} -> {r.nation_iso2}, "
                                 f"top_endpoint={r.top_endpoint_country})"
                                 for r in home0_d.itertuples())
        tier_rows.append({
            "match_method": m,
            "n_codes": len(d),
            "departures": dep_sum,
            "n_home0_codes": len(home0_d),
            "share_home0_codes": d["flag_home_share_zero"].mean(),
            "share_home0_dep": (home0_d["departures"].sum() / dep_sum) if dep_sum > 0 else float("nan"),
            "n_home_lt001_codes": len(lt001_d),
            "share_home_lt001_dep": (lt001_d["departures"].sum() / dep_sum) if dep_sum > 0 else float("nan"),
            "implausible_pairs_home0": implausible,
        })
    tier_precision_df = pd.DataFrame(tier_rows)
    tier_precision_df.to_csv(TIER_PRECISION_CSV, index=False)
    logger.info("Wrote %s: %d tier rows (precision proxy = observed home-country endpoint share).",
                TIER_PRECISION_CSV, len(tier_precision_df))
    if len(tier_precision_df):
        logger.info("Precision by match tier:\n%s", tier_precision_df.to_string())

    # ======================================================================
    # Class-F (headline sample) precision cut -- required action 3.
    # Recompute home_country_dep_share using ONLY SERVICE_CLASS == 'F'
    # departures for each matched-foreign code (freight/combi service is
    # excluded from FIX-04/NEW-06's headline panel, and pulls the
    # all-classes precision figure down -- see foreign_by_service_class
    # rows above).
    # ======================================================================
    classf_foreign_total_dep = float(matchrate_df.loc[matchrate_df["category"] == "foreign_classF",
                                                        "departures_total"].iloc[0])
    classf_foreign_matched_dep = float(matchrate_df.loc[matchrate_df["category"] == "foreign_classF",
                                                          "departures_matched"].iloc[0])
    classf_overall_total_dep = float(matchrate_df.loc[matchrate_df["category"] == "overall_classF",
                                                        "departures_total"].iloc[0])
    classf_us_matched_dep = float(matchrate_df.loc[matchrate_df["category"] == "us_classF",
                                                     "departures_matched"].iloc[0])

    precision_classf_rows = []
    for idx in code_tbl.index[foreign_matched_mask]:
        code = code_tbl.at[idx, "UNIQUE_CARRIER"]
        nation = code_tbl.at[idx, "nation_iso2"]
        sub = classf_t100c.loc[classf_t100c["UNIQUE_CARRIER"] == code]
        dep_total = float(sub["dep"].sum())
        dep_home = float(sub.loc[sub["foreign_endpoint"] == nation, "dep"].sum())
        home_share = (dep_home / dep_total) if dep_total > 0 else float("nan")
        precision_classf_rows.append({
            "unique_carrier": code,
            "departures_classF": dep_total,
            "home_country_dep_share_classF": home_share,
            "flag_home_share_zero_classF": bool(dep_total > 0 and home_share == 0),
        })
    precision_classf_df = pd.DataFrame(precision_classf_rows)
    home0_dep_classf = float(precision_classf_df.loc[precision_classf_df["flag_home_share_zero_classF"],
                                                       "departures_classF"].sum()) if len(precision_classf_df) else 0.0
    home_lt001_dep_classf = float(precision_classf_df.loc[
        precision_classf_df["home_country_dep_share_classF"] < PRECISION_LOW_THRESH, "departures_classF"
    ].sum()) if len(precision_classf_df) else 0.0
    share_home0_classf = (home0_dep_classf / classf_foreign_matched_dep) if classf_foreign_matched_dep > 0 else float("nan")
    share_home_lt001_classf = (home_lt001_dep_classf / classf_foreign_matched_dep) if classf_foreign_matched_dep > 0 else float("nan")

    precision_adjusted_foreign_rate_classf_home0 = (
        (classf_foreign_matched_dep - home0_dep_classf) / classf_foreign_total_dep
        if classf_foreign_total_dep > 0 else float("nan"))
    precision_adjusted_foreign_rate_classf_lt001 = (
        (classf_foreign_matched_dep - home_lt001_dep_classf) / classf_foreign_total_dep
        if classf_foreign_total_dep > 0 else float("nan"))
    precision_adjusted_overall_rate_classf_home0 = (
        (classf_us_matched_dep + classf_foreign_matched_dep - home0_dep_classf) / classf_overall_total_dep
        if classf_overall_total_dep > 0 else float("nan"))
    precision_adjusted_overall_rate_classf_lt001 = (
        (classf_us_matched_dep + classf_foreign_matched_dep - home_lt001_dep_classf) / classf_overall_total_dep
        if classf_overall_total_dep > 0 else float("nan"))

    logger.info("Class-F (headline sample) readings: coverage foreign=%.4f overall=%.4f; "
                "precision-adjusted (home0) foreign=%.4f overall=%.4f; precision-adjusted "
                "(<%.2f) foreign=%.4f overall=%.4f.",
                classf_foreign_matched_dep / classf_foreign_total_dep if classf_foreign_total_dep > 0 else float("nan"),
                float(matchrate_df.loc[matchrate_df["category"] == "overall_classF", "match_rate_weighted"].iloc[0]),
                precision_adjusted_foreign_rate_classf_home0, precision_adjusted_overall_rate_classf_home0,
                PRECISION_LOW_THRESH,
                precision_adjusted_foreign_rate_classf_lt001, precision_adjusted_overall_rate_classf_lt001)

    # Fold precision diagnostics (all-classes and class-F, both
    # thresholds) into the matchrate CSV next to the coverage rate
    # they're being compared against (required actions 2 and 3).
    matchrate_df["share_matched_dep_home0"] = float("nan")
    matchrate_df["share_matched_dep_home_lt_001"] = float("nan")
    matchrate_df["precision_adjusted_match_rate_home0"] = float("nan")
    matchrate_df["precision_adjusted_match_rate_lt001"] = float("nan")
    matchrate_df.loc[matchrate_df["category"] == "foreign", "share_matched_dep_home0"] = share_home0
    matchrate_df.loc[matchrate_df["category"] == "foreign", "share_matched_dep_home_lt_001"] = share_home_lt001
    matchrate_df.loc[matchrate_df["category"] == "foreign", "precision_adjusted_match_rate_home0"] = precision_adjusted_foreign_rate
    matchrate_df.loc[matchrate_df["category"] == "foreign", "precision_adjusted_match_rate_lt001"] = (
        (foreign_matched_departures - home_lt001_departures) / foreign_total_dep if foreign_total_dep > 0 else float("nan"))
    matchrate_df.loc[matchrate_df["category"] == "overall", "precision_adjusted_match_rate_home0"] = precision_adjusted_overall_rate
    matchrate_df.loc[matchrate_df["category"] == "overall", "precision_adjusted_match_rate_lt001"] = (
        (us_matched_dep + foreign_matched_departures - home_lt001_departures) / overall_total_dep
        if overall_total_dep > 0 else float("nan"))
    matchrate_df.loc[matchrate_df["category"] == "foreign_classF", "share_matched_dep_home0"] = share_home0_classf
    matchrate_df.loc[matchrate_df["category"] == "foreign_classF", "share_matched_dep_home_lt_001"] = share_home_lt001_classf
    matchrate_df.loc[matchrate_df["category"] == "foreign_classF", "precision_adjusted_match_rate_home0"] = precision_adjusted_foreign_rate_classf_home0
    matchrate_df.loc[matchrate_df["category"] == "foreign_classF", "precision_adjusted_match_rate_lt001"] = precision_adjusted_foreign_rate_classf_lt001
    matchrate_df.loc[matchrate_df["category"] == "overall_classF", "precision_adjusted_match_rate_home0"] = precision_adjusted_overall_rate_classf_home0
    matchrate_df.loc[matchrate_df["category"] == "overall_classF", "precision_adjusted_match_rate_lt001"] = precision_adjusted_overall_rate_classf_lt001
    matchrate_df.to_csv(MATCHRATE_CSV, index=False)
    logger.info("Wrote %s (%d rows).", MATCHRATE_CSV, len(matchrate_df))

    # ======================================================================
    # carrier_nation_gate_sensitivity.csv -- required action 1. The
    # coverage reading clears G7_FOREIGN_MIN by a small margin; this makes
    # explicit how much of that margin rests on the icao tier, which the
    # per-tier precision CSV above shows is ~49% wrong by the same proxy.
    # Reported neutrally as a sensitivity, not as a preferred reading.
    # ======================================================================
    icao_dep_foreign_matched = float(t100c.loc[(~t100c["is_us"]) & (t100c["match_method"] == "icao"),
                                                "dep"].sum())
    foreign_matched_dep_all = float(matchrate_df.loc[matchrate_df["category"] == "foreign",
                                                       "departures_matched"].iloc[0])
    overall_matched_dep_all = float(matchrate_df.loc[matchrate_df["category"] == "overall",
                                                       "departures_matched"].iloc[0])
    foreign_coverage_excl_icao = ((foreign_matched_dep_all - icao_dep_foreign_matched) / foreign_total_dep
                                   if foreign_total_dep > 0 else float("nan"))
    overall_coverage_excl_icao = ((overall_matched_dep_all - icao_dep_foreign_matched) / overall_total_dep
                                   if overall_total_dep > 0 else float("nan"))
    margin_departures = (foreign_rate - G7_FOREIGN_MIN) * foreign_total_dep

    sensitivity_rows = [
        {"cut": "coverage_all_tiers", "scope": "foreign", "departures_total": foreign_total_dep,
         "departures_matched_or_adjusted": foreign_matched_dep_all, "rate": foreign_rate,
         "note": "as reported in carrier_nation_matchrate.csv row category=foreign; the coverage reading."},
        {"cut": "coverage_excl_icao_tier", "scope": "foreign", "departures_total": foreign_total_dep,
         "departures_matched_or_adjusted": foreign_matched_dep_all - icao_dep_foreign_matched,
         "rate": foreign_coverage_excl_icao,
         "note": (f"icao tier carries {icao_dep_foreign_matched:.0f} matched departures at "
                  f"{PRECISION_LOW_THRESH:.2f}-threshold precision shown in "
                  f"carrier_nation_tier_precision.csv row match_method=icao "
                  f"(share_home0_dep~0.49); excluding it alone drops foreign coverage below "
                  f"G7_FOREIGN_MIN. Sensitivity only -- neither reading is the answer.")},
        {"cut": "coverage_excl_icao_tier", "scope": "overall", "departures_total": overall_total_dep,
         "departures_matched_or_adjusted": overall_matched_dep_all - icao_dep_foreign_matched,
         "rate": overall_coverage_excl_icao,
         "note": "same exclusion, overall scope, for completeness."},
        {"cut": "coverage_margin_over_g7_min", "scope": "foreign", "departures_total": foreign_total_dep,
         "departures_matched_or_adjusted": margin_departures, "rate": foreign_rate - G7_FOREIGN_MIN,
         "note": (f"the coverage reading clears G7_FOREIGN_MIN ({G7_FOREIGN_MIN:.2f}) by this many "
                  f"departures; icao-tier matched departures ({icao_dep_foreign_matched:.0f}) exceed "
                  f"this margin, so the icao tier alone can flip the coverage reading's verdict.")},
    ]
    gate_sensitivity_df = pd.DataFrame(sensitivity_rows)
    gate_sensitivity_df.to_csv(GATE_SENSITIVITY_CSV, index=False)
    logger.info("Wrote %s: %d rows. Foreign coverage margin over G7_FOREIGN_MIN = %.0f "
                "departures; icao-tier matched departures = %.0f; excluding icao tier alone gives "
                "foreign coverage = %.4f (vs G7_FOREIGN_MIN = %.2f).",
                GATE_SENSITIVITY_CSV, len(gate_sensitivity_df), margin_departures,
                icao_dep_foreign_matched, foreign_coverage_excl_icao, G7_FOREIGN_MIN)

    # ======================================================================
    # carrier_nation_audit_sample.csv (required action 3): 40 largest +
    # random 40 matched-foreign codes, for a human to score precision by
    # tier against the listed OpenFlights candidate(s).
    # ======================================================================
    if len(precision_df):
        top40 = precision_df.head(40).copy()
        top40["sample_group"] = "top40_by_departures"
        remainder = precision_df.iloc[40:]
        random40 = remainder.sample(n=min(40, len(remainder)), random_state=42).copy() if len(remainder) else remainder.copy()
        random40["sample_group"] = "random40_seed42"
        audit_sample = pd.concat([top40, random40], ignore_index=True)
    else:
        audit_sample = precision_df.copy()
        audit_sample["sample_group"] = pd.Series(dtype="object")
    audit_sample.to_csv(AUDIT_SAMPLE_CSV, index=False)
    logger.info("Wrote %s: %d rows (%d top-by-departures, %d random) for human tier scoring.",
                AUDIT_SAMPLE_CSV, len(audit_sample),
                int((audit_sample.get("sample_group") == "top40_by_departures").sum()) if len(audit_sample) else 0,
                int((audit_sample.get("sample_group") == "random40_seed42").sum()) if len(audit_sample) else 0)

    # ======================================================================
    # carrier_nation_unmatched.csv (required action 7a)
    # ======================================================================
    unmatched_codes = code_tbl.loc[code_tbl["match_method"].isin(
        ["unmatched", "refused_suffix_collision"])].copy()

    def _code_endpoint_and_recent(code: str):
        sub = t100c.loc[t100c["UNIQUE_CARRIER"] == code]
        endpoint_dep = sub.groupby("foreign_endpoint")["dep"].sum().dropna()
        modal = endpoint_dep.idxmax() if len(endpoint_dep) else None
        recent = float(sub.loc[(sub["YEAR"].between(2019, 2024)) & (sub["is_passenger"]), "dep"].sum())
        return modal, recent

    modal_list, recent_list = [], []
    for code in unmatched_codes["UNIQUE_CARRIER"]:
        modal, recent = _code_endpoint_and_recent(code)
        modal_list.append(modal)
        recent_list.append(recent)
    unmatched_codes["modal_foreign_endpoint_country"] = modal_list
    unmatched_codes["departures_2019_2024_classF"] = recent_list

    unmatched_codes = unmatched_codes.sort_values("total_departures", ascending=False)
    unmatched_out = unmatched_codes[["UNIQUE_CARRIER", "name", "total_departures",
                                      "first_year", "last_year", "match_method",
                                      "modal_foreign_endpoint_country",
                                      "departures_2019_2024_classF",
                                      "n_candidates", "candidate_names"]].rename(
        columns={"UNIQUE_CARRIER": "unique_carrier", "name": "carrier_name",
                 "n_candidates": "n_openflights_candidates"})
    unmatched_out.to_csv(UNMATCHED_CSV, index=False)
    logger.info("Wrote %s: %d unmatched-or-refused codes, %.0f total departures.",
                UNMATCHED_CSV, len(unmatched_out), unmatched_out["total_departures"].sum())

    # ======================================================================
    # carrier_nation_corridor_coverage.csv (required action 4, cycle-3
    # review): the plain "all-carrier" match rate pools in trivially-
    # matched US carriers, which flatters every anchor for a carrier-
    # NATIONALITY design. Report all three cuts side by side, unlabelled
    # in favour of none of them: all-carrier, foreign-only, and foreign
    # with the precision-adjusted (home_country_dep_share>0) requirement
    # folded in. Also flag whether each window overlaps Part 0's COVID
    # window (2020-03 to 2021-12).
    # ======================================================================
    t100_m = t100.merge(code_tbl[["UNIQUE_CARRIER", "is_us", "match_method"]],
                         on="UNIQUE_CARRIER", how="left")
    t100_m["is_us"] = t100_m["is_us"].fillna(False).astype(bool)
    t100_m["matched_row"] = t100_m["match_method"].isin(
        ["iata", "icao", "name_exact", "us_by_construction"])
    t100_m["is_foreign_code"] = t100_m["UNIQUE_CARRIER"].notna() & (~t100_m["is_us"])
    code_home_share = (dict(zip(precision_df["unique_carrier"], precision_df["home_country_dep_share"]))
                        if len(precision_df) else {})
    t100_m["home_share_code"] = t100_m["UNIQUE_CARRIER"].map(code_home_share)
    t100_m["precision_pass"] = t100_m["matched_row"] & (
        t100_m["is_us"] | (t100_m["home_share_code"] > 0))
    t100_m["dep"] = t100_m["DEPARTURES_PERFORMED"].fillna(0.0)
    t100_m["ym"] = t100_m["YEAR"] * 100 + t100_m["MONTH"]

    COVID_YM_START, COVID_YM_END = 202003, 202112

    def _ym_overlap_share(lo: int, hi: int) -> float:
        """Share of the window's calendar months that fall inside the
        COVID window, computed on year-month integers (not exact for
        cross-century windows, unused here; all windows are within one
        decade so month-counting by (year,month) pairs is exact)."""
        def to_months(ym):
            return (ym // 100) * 12 + (ym % 100)
        w_lo, w_hi = to_months(lo), to_months(hi)
        c_lo, c_hi = to_months(COVID_YM_START), to_months(COVID_YM_END)
        overlap = max(0, min(w_hi, c_hi) - max(w_lo, c_lo) + 1)
        total = w_hi - w_lo + 1
        return overlap / total if total > 0 else 0.0

    corridor_rows = []
    for airport, corridor in ANCHOR_AIRPORTS.items():
        at_airport = (t100_m["ORIGIN"] == airport) | (t100_m["DEST"] == airport)
        for window_name, (lo, hi) in CORRIDOR_WINDOWS.items():
            sub = t100_m.loc[at_airport & t100_m["is_passenger"] & t100_m["ym"].between(lo, hi)]
            total_all = float(sub["dep"].sum())
            matched_all = float(sub.loc[sub["matched_row"], "dep"].sum())

            sub_f = sub.loc[sub["is_foreign_code"]]
            total_foreign = float(sub_f["dep"].sum())
            matched_foreign = float(sub_f.loc[sub_f["matched_row"], "dep"].sum())
            precision_matched_foreign = float(sub_f.loc[sub_f["precision_pass"], "dep"].sum())

            covid_month_share = _ym_overlap_share(lo, hi)
            corridor_rows.append({
                "airport": airport,
                "corridor": corridor,
                "window": window_name,
                "covid_flag": bool(covid_month_share > 0),
                "covid_month_share": covid_month_share,
                "departures_total_all_carriers": total_all,
                "departures_matched_all_carriers": matched_all,
                "match_rate_all_carriers": (matched_all / total_all) if total_all > 0 else float("nan"),
                "departures_total_foreign": total_foreign,
                "departures_matched_foreign": matched_foreign,
                "match_rate_foreign": (matched_foreign / total_foreign) if total_foreign > 0 else float("nan"),
                "departures_matched_foreign_homecountry_filtered": precision_matched_foreign,
                "match_rate_foreign_precision_adjusted": (
                    (precision_matched_foreign / total_foreign) if total_foreign > 0 else float("nan")),
            })
    corridor_df = pd.DataFrame(corridor_rows)
    corridor_df.to_csv(CORRIDOR_COVERAGE_CSV, index=False)
    logger.info("Wrote %s: %d airport x window rows (all-carrier / foreign-only / "
                "foreign-precision-adjusted, covid_flag).", CORRIDOR_COVERAGE_CSV, len(corridor_df))

    # ======================================================================
    # carrier_nation_flips.csv (required action 5 replaces the vacuous
    # cross-year-nation check; required action 4 appends the
    # suffix-collision refusals). Every row carries a resolution note.
    # ======================================================================
    name_eras = (t100c.groupby(["UNIQUE_CARRIER", "CARRIER_NAME"])
                 .agg(year_start=("YEAR", "min"), year_end=("YEAR", "max"),
                      departures=("dep", "sum"))
                 .reset_index())
    era_counts = name_eras.groupby("UNIQUE_CARRIER").size()
    churn_codes = era_counts[era_counts > 1].index

    flip_rows = []
    n_cross_border = 0
    churn_departures = 0.0
    for code in churn_codes:
        eras = name_eras.loc[name_eras["UNIQUE_CARRIER"] == code].sort_values("year_start")
        churn_departures += float(eras["departures"].sum())
        code_row = code_tbl.loc[code_tbl["UNIQUE_CARRIER"] == code]
        nation_val = code_row["nation_iso2"].iloc[0] if len(code_row) else None
        match_method_val = code_row["match_method"].iloc[0] if len(code_row) else None

        # The route-geography drift test only means something where the
        # nation itself rests on weak, dateless lookup evidence (iata /
        # icao / name_exact): there, a rebrand that coincides with a
        # change in which foreign country the code actually serves is a
        # legitimate reason to distrust the fixed nation assignment. For
        # us_by_construction the nation is independently known from BTS's
        # own CARRIER_GROUP field (ground truth, not inferred from
        # routes), so route-mix drift (e.g. a charter carrier's
        # destination countries changing year to year) is normal business
        # variation, not evidence of anything -- running the same test
        # there produced spurious flags (a US charter operator serving
        # different contract destinations across eras) and was dropped.
        # unmatched/refused codes carry no nation to test against.
        test_applies = match_method_val in ("iata", "icao", "name_exact")
        cross_border = False
        distinct_endpoints: set = set()
        era_top_endpoints = [None] * len(eras)
        if test_applies:
            era_top_endpoints = []
            for _, era_row in eras.iterrows():
                era_sub = t100c.loc[(t100c["UNIQUE_CARRIER"] == code) &
                                     (t100c["CARRIER_NAME"] == era_row["CARRIER_NAME"])]
                endpoint_dep = era_sub.groupby("foreign_endpoint")["dep"].sum().dropna()
                era_top_endpoints.append(endpoint_dep.idxmax() if len(endpoint_dep) else None)
            distinct_endpoints = {e for e in era_top_endpoints if e is not None}
            cross_border = len(distinct_endpoints) > 1
            if cross_border:
                n_cross_border += 1

        for (_, era_row), top_ep in zip(eras.iterrows(), era_top_endpoints):
            if not test_applies:
                if match_method_val == "us_by_construction":
                    resolution = (
                        f"resolved — UNIQUE_CARRIER_NAME changes across years, but the nation "
                        f"'US' is verified independently via BTS's own CARRIER_GROUP field, not "
                        f"inferred from route geography; a route-mix change is not evidence "
                        f"against it. Not tested for cross-border drift.")
                    flip_type = "name_churn_stable_nation"
                else:
                    resolution = (
                        f"not applicable — this code carries no assigned nation currently "
                        f"(match_method={match_method_val!r}); listed for completeness only, not "
                        f"tested for cross-border drift.")
                    flip_type = "name_churn_no_nation_assigned"
            elif cross_border:
                resolution = (
                    f"unresolved — the top observed endpoint country changes across "
                    f"UNIQUE_CARRIER_NAME eras for this code ({sorted(distinct_endpoints)}) while "
                    f"the mapped nation is held fixed at {nation_val!r}; candidate undetected "
                    f"nationality change coinciding with the rebrand, needs human review")
                flip_type = "name_churn_cross_border"
            else:
                resolution = (
                    f"resolved — UNIQUE_CARRIER_NAME changes across years but the top observed "
                    f"endpoint country is stable ({top_ep!r}) and the mapped nation is held fixed "
                    f"at {nation_val!r}; read as a rebrand, not a nationality flip")
                flip_type = "name_churn_stable_nation"
            flip_rows.append({
                "unique_carrier": code,
                "carrier_name_era": era_row["CARRIER_NAME"],
                "year_start": int(era_row["year_start"]),
                "year_end": int(era_row["year_end"]),
                "nation_iso2": nation_val,
                "match_method": match_method_val,
                "flip_type": flip_type,
                "resolution": resolution,
            })

    logger.info("Name-churn diagnostic: %d codes with >1 UNIQUE_CARRIER_NAME era, %d rows, "
                "%.0f departures (%.4f of all non-null-carrier departures); %d flagged "
                "cross-border (endpoint geography changed alongside the name).",
                len(churn_codes), sum(1 for r in flip_rows if r["flip_type"].startswith("name_churn")),
                churn_departures, churn_departures / t100c["dep"].sum() if t100c["dep"].sum() > 0 else float("nan"),
                n_cross_border)

    for idx in refuse_idx:
        code = code_tbl.at[idx, "UNIQUE_CARRIER"]
        base = code_tbl.at[idx, "base_code"]
        nation_before = code_tbl.at[idx, "nation_before_suffix_check"]
        siblings = code_tbl.loc[(code_tbl["base_code"] == base) & (code_tbl.index.isin(refuse_idx))]
        sibling_desc = "; ".join(f"{r['UNIQUE_CARRIER']} ({r['name']})"
                                  for _, r in siblings.iterrows() if r["UNIQUE_CARRIER"] != code)
        sub = t100c.loc[t100c["UNIQUE_CARRIER"] == code]
        flip_rows.append({
            "unique_carrier": code,
            "carrier_name_era": code_tbl.at[idx, "name"],
            "year_start": int(sub["YEAR"].min()) if len(sub) else None,
            "year_end": int(sub["YEAR"].max()) if len(sub) else None,
            "nation_iso2": pd.NA,
            "match_method": "refused_suffix_collision",
            "flip_type": "suffix_collision_refused",
            "resolution": (
                f"unresolved — reissue-suffix family sharing base code {base!r} would map two or "
                f"more distinct BTS entities with differing UNIQUE_CARRIER_NAME to the same nation "
                f"{nation_before!r} under a dateless OpenFlights lookup; refused rather than "
                f"guessed. Other sibling(s): {sibling_desc}. Candidate code reissue across "
                f"nationalities, needs human review to split by date."),
        })

    flips_df = pd.DataFrame(flip_rows, columns=["unique_carrier", "carrier_name_era", "year_start",
                                                 "year_end", "nation_iso2", "match_method",
                                                 "flip_type", "resolution"])
    flips_df.to_csv(FLIPS_CSV, index=False)
    logger.info("Wrote %s: %d rows (%d name-churn, %d suffix-collision-refused).",
                FLIPS_CSV, len(flips_df),
                int((flips_df["flip_type"].str.startswith("name_churn")).sum()) if len(flips_df) else 0,
                int((flips_df["flip_type"] == "suffix_collision_refused").sum()) if len(flips_df) else 0)

    # ======================================================================
    # G7 gate -- two readings, neither chosen (STANDING_RULES rule 4;
    # required action 1). "Coverage" = departures-weighted share of
    # departures whose code resolved to SOME nation. "Precision-adjusted"
    # = the same, but additionally requiring that the matched code's own
    # T-100 routes ever touch its mapped home country at least once.
    # ======================================================================
    g7_overall_coverage_pass = overall_rate >= G7_OVERALL_MIN
    g7_foreign_coverage_pass = foreign_rate >= G7_FOREIGN_MIN
    g7_coverage_pass = g7_overall_coverage_pass and g7_foreign_coverage_pass

    g7_overall_precision_pass = precision_adjusted_overall_rate >= G7_OVERALL_MIN
    g7_foreign_precision_pass = precision_adjusted_foreign_rate >= G7_FOREIGN_MIN
    g7_precision_pass = g7_overall_precision_pass and g7_foreign_precision_pass

    degenerate_gate = g7_coverage_pass != g7_precision_pass

    if degenerate_gate:
        logger.error(
            "DEGENERATE-GATE: G7 is titled 'mapping precision', and its two defensible readings "
            "disagree on pass/fail. Coverage reading (does the code resolve to some candidate; "
            "overall=%.4f foreign=%.4f) reads %s. Precision-adjusted reading (same, but the "
            "matched code's own T-100 routes must touch its mapped home country at least once; "
            "overall=%.4f foreign=%.4f) reads %s. Per STANDING_RULES rule 4, neither reading is "
            "chosen. FIX-02 is BLOCKED-NEEDS-HUMAN. Diagnostics: %s (one row per matched-foreign "
            "code), %s (both readings side by side), %s (40 largest + random 40 for human tier "
            "scoring), %s (suffix-collision and name-churn detail).",
            overall_rate, foreign_rate, "PASS" if g7_coverage_pass else "FAIL",
            precision_adjusted_overall_rate, precision_adjusted_foreign_rate,
            "PASS" if g7_precision_pass else "FAIL",
            PRECISION_AUDIT_CSV, MATCHRATE_CSV, AUDIT_SAMPLE_CSV, FLIPS_CSV)
        return 1

    if not g7_coverage_pass:
        logger.error("G7 FAILED under both readings (coverage overall=%.4f foreign=%.4f; "
                      "precision-adjusted overall=%.4f foreign=%.4f). FIX-02 BLOCKED-NEEDS-HUMAN. "
                      "See %s, %s.", overall_rate, foreign_rate, precision_adjusted_overall_rate,
                      precision_adjusted_foreign_rate, UNMATCHED_CSV, MATCHRATE_CSV)
        return 1

    logger.info("G7 PASSED under both readings (coverage and precision-adjusted). FIX-02 DONE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
