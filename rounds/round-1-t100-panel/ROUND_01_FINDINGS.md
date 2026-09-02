# ROUND 01 FINDINGS — T-100 panel foundations and the raw wedge

Written by the director at round close, 2026-09-02. Audience: a coauthor
with zero context. Every number below is transcribed from a CSV in this
folder, with the file and row named inline. Nothing is quoted from logs,
reviews, or memory.

---

## The headline, up front

**The project's primary outcome — airborne time by operator nationality —
is not observable in T-100 for the population the design needs. Foreign
carriers never report airborne time. Not sparsely: never.**

Across all 36 raw year files, 1990–2025, rows filed by foreign carriers
(BTS's own `CARRIER_GROUP == 0` field, read straight from the raw CSVs,
with no dependence on anything this project built) number **1,133,545 —
and 0 of them have `AIR_TIME > 0`, 0 have `RAMP_TO_RAMP > 0`, and 0 are
null in either field: every value is a literal zero**
(coverage_by_carrier_group.csv, the 36 rows with `carrier_group == 0`,
columns `n_rows`, `n_air_gt0`, `n_ramp_gt0`, `n_air_null`, `n_ramp_null`,
summed). Foreign carriers report volume but never time: the share of
foreign rows with a positive value is **1.0 for departures, 1.0 for
distance, 0.8404 for seats, 0.8355 for passengers — and 0.0 for airborne
time, 0.0 for ramp-to-ramp, 0.0 for scheduled departures**
(coverage_column_availability.csv, rows `(foreign, <column>)`, column
`share_gt0`). US carriers in the very same files report airborne time in
**0.9964** of rows (1,523,392 of 1,528,925)
(coverage_column_availability.csv, row `(us, AIR_TIME)`).

The *pattern* is established beyond doubt and is not a defect of our
download: the columns exist in every file's header, they are full for
US carriers in those same files, the export writes zeros rather than
blanks, and the pattern holds for 36 consecutive years without a single
exception — a different download would return the same zeros. Our
*inference* is that this reflects BTS's foreign-carrier reporting
schedule (the T-100(f) form collecting volume but not block/airborne
time); the form's published data-element list has not yet been sourced,
so that attribution awaits an attended web session (scheduled in the
next steps) and is stated here as inference, not fact.

**This blocker is independent of, and larger than, the FIX-02 mapping
problem described below: a perfect carrier-nation mapping would change
nothing, because there is no airborne time to attribute to any non-US
nation.** The round therefore did not produce the finding it set out to
test — the carrier-nation flight-time wedge at monthly frequency — and it
did produce a solid, fully evidenced reason why, plus a clean US-side
panel, a verified extensive margin, and a decision-grade package for the
human. The wedge thread is PARKED, not dead: ADS-B tracking data (the
Phase-2 OpenSky source) observes every operator's actual airborne time
regardless of what BTS collects.

---

## 1. What we were trying to find out this round, and why

The project's idea: when countries clash, airlines reveal it — flights
between certain country pairs get longer (detours around closed airspace)
or disappear, and crucially this happens *asymmetrically*: after Russia
banned EU/US/UK airlines from Siberian airspace in February 2022, a
US airline's Chicago→Tokyo flight had to detour, while a Chinese
airline's flight on the same route did not. If we can measure "excess
airborne time" (this month's flight time on a route minus that route's
own normal) separately by the airline's home country, the *gap between
nationalities on the same route* is a language-free, bilateral index of
geopolitical disruption.

Round 1 was the foundation round on the free monthly US data (BTS T-100,
every nonstop international segment touching the US, 1990–2025): ingest
the raw files, map each carrier code to its home country, audit how well
airborne time is actually reported (the project brief explicitly warned
foreign reporting had "gaps"), build the route × operator-nation × month
panel, construct the excess-time outcome, and draw the first raw picture:
do US and foreign airlines' flight times split apart on US–East Asia
routes after February 2022, with US–Western Europe (where no differential
ban applies) as the placebo that should show nothing?

## 2. What we did

Seven tasks, in pipeline order. Plain-words versions:

- **FIX-00 (bootstrap):** checked that all the raw files are present and
  intact before anything runs. All 38 expected inputs (36 T-100 year
  files + an airline lookup + a 2022 ban-list) present, every header
  verified (bootstrap_manifest.csv, 38 rows, `header_verified` all True).
- **FIX-01 (ingest):** read all 36 raw year files into one clean table,
  standardizing column names that drift across years. 2,662,470 rows
  read, 2,662,470 written, 0 dropped (ingest_rowcounts.csv, sums of
  `rows_read`/`rows_written`/`rows_dropped`). One real bug was caught and
  fixed in review: the literal code "NA" (a real airline code, and the
  country code for Namibia) was silently being turned into "missing" by
  the default reader settings; the fix preserves it and adds a standing
  guard so this bug class cannot recur silently on a new data drop.
- **FIX-02 (nationality mapping):** mapped each carrier code (e.g. "AF")
  to its home country using the human-supplied OpenFlights airline table.
  This is where the round's second problem lives — see §3. Terminal
  state: **BLOCKED-NEEDS-HUMAN with a DEGENERATE-GATE flag** (two
  defensible readings of the quality gate disagree; neither was chosen).
- **FIX-03 (coverage audit):** before building anything, measured *who
  actually reports airborne time*, by nation and year — and, decisively,
  by BTS's own US/foreign carrier-group field straight from the raw
  files. This produced the headline finding above.
- **FIX-04 (panel):** built the unit of observation — one row per
  directed route (e.g. ORD→NRT, direction kept) × operator nation ×
  month — plus an "extensive margin" table recording when route service
  starts and stops (exits during disruptions are data, not gaps). Per
  the overseer's conservative FIX-02 ruling, the panel is built on
  matched carriers only and drops the low-precision `icao` match tier
  (347 rows; panel_filter_log.csv, row `icao_tier_dropped`) — a
  conservative default, not a resolution of the blocked gate.
- **FIX-05 (outcomes):** built "excess airborne time": each cell's mean
  minutes per departure minus that same route's median in the same
  calendar month over the trailing 3 years (same-calendar-month because
  winds are seasonal), COVID months (2020-03…2021-12) never allowed into
  the normal, at least 2 prior observations required, extreme values
  clipped at each route's own 1st/99th percentile ("winsorizing"), plus
  the wind-cancelling bidirectional sum (outbound + return excess, same
  month). Necessarily **US carriers only**, per FIX-03.
- **NEW-06 (the raw picture), reduced form:** the commissioned wedge
  figures are not computable — the foreign side of every corridor is
  structurally empty — so, under a binding overseer ruling, the task
  shipped a *documented null*: a complete corridor × nation × month
  availability record with a reason attached to every empty cell, plus a
  US-only series clearly labelled as not a cross-national comparison.

## 3. What we found

### 3a. The primary outcome does not exist for foreign operators (the headline)

Details and traces at the top of this file. Downstream consequences, each
verified in this round's own outputs:

- In the headline analysis sample (scheduled passenger service,
  departures > 0, matched carriers), **2,213 of 2,249 operator-nation ×
  year cells fail the coverage gate G6 (share of cells with valid
  airborne time < 0.50) — every failing cell at a share of exactly 0.0 —
  and the 36 passing cells are all `nation == US`** (0.9923–1.0)
  (coverage_audit.csv, columns `share_air_time_valid`, `gate_g6_pass`;
  coverage_excluded_cells.csv, 2,213 rows). Departures-weighted, the
  failing cells carry **0.3976** of all departures (coverage_audit.csv,
  `dep_total` summed over `gate_g6_pass == False` rows ÷ all rows).
- On the four anchor corridors, **0 of 908 non-US corridor cells pass
  G6 — identically on the three treated corridors and on the European
  placebo** (coverage_by_corridor.csv, rows with `nation != "US"`,
  column `gate_g6_pass`).
- It is not an artifact of our carrier-matching exclusions either: the
  rows excluded from matching show the same split — every foreign-group
  exclusion row has `share_air_gt0` 0.0, every US-group row 1.0
  (coverage_matching_exclusions.csv, grouped by `CARRIER_GROUP`).

**The placebo is as empty as the treated corridors.** That symmetry is
itself the informative fact (standing rule 6: nulls are deliverables): it
tells us the emptiness is about *the data source*, not about the world.
A real behavioral null would have looked like "foreign series present and
flat"; what we have is "foreign series absent everywhere, treated and
placebo alike."

### 3b. FIX-02: the nationality gate split down the middle — unresolved, by design

The mapping quality gate G7 required a departures-weighted match rate
≥ 0.95 overall and ≥ 0.90 among foreign carriers. Two defensible readings
of "match rate" disagree, and per standing rule 4 **neither was chosen;
both are reported, and the human must rule**:

- **Coverage reading** (did the code resolve to *some* candidate):
  overall **0.9592**, foreign **0.9021** — clears the bound
  (carrier_nation_matchrate.csv, rows `category == overall` / `foreign`,
  column `match_rate_weighted`).
- **Precision-adjusted reading** (does the matched code's own T-100
  traffic ever touch its mapped home country): foreign **0.8631** (or
  **0.8440** at a stricter < 0.01 threshold) — fails the bound (same row,
  columns `precision_adjusted_match_rate_home0` /
  `precision_adjusted_match_rate_lt001`). On the class-F headline sample:
  coverage **0.9303**, precision-adjusted **0.8911**
  (carrier_nation_matchrate.csv, row `foreign_classF`).
- **The decisive sensitivity: the coverage pass is knife-edge and rests
  on the weakest match tier.** It clears the 0.90 bound by **41,643
  departures** (carrier_nation_gate_sensitivity.csv, row
  `coverage_margin_over_g7_min`), while the `icao` match tier alone
  carries **47,345 matched departures** at a home-country-zero departure
  share of **0.4938** — i.e. roughly half of that tier's traffic is on
  codes mapped to a country the carrier never flies to
  (carrier_nation_tier_precision.csv, row `match_method == icao`).
  Excluding just that tier drops foreign coverage to **0.8997**, below
  the bound (carrier_nation_gate_sensitivity.csv, row
  `coverage_excl_icao_tier`, scope `foreign`). So the gate's verdict
  flips on its least trustworthy stratum.

Concrete mis-mappings now on the record for the human's packet, all from
carrier_nation_precision_audit.csv (columns `departures`,
`home_country_dep_share`):

- `KV` Sky Regional Airlines (a Canadian carrier) → mapped **RU**,
  222,939 departures, home-country share 0.0; `RV` Air Canada rouge →
  mapped **IR**, 191,266 departures, share 0.0. These two codes are most
  of what "Russia" and "Iran" would have meant in any nation-level table.
- `TA` Taca International (El Salvador) → mapped **CR**, 347,572
  departures, share 0.0038 — a vendor error both G7 readings let through.
- `VX (1)` Aces Airlines (Colombia), `B0` La Compagnie (France), `WO`
  Swoop (Canada) → all mapped **US** (19,410 + 10,871 + 4,887
  departures, all at share 0.0), contaminating 1,681 otherwise-clean US
  panel cells (panel_filter_log.csv, row
  `cell_ok_mixed_mapping_precision`).
- Found late, on the placebo corridor: `N0` Norse Atlantic Airways →
  mapped **AR** (Argentina!), 7,272 departures, share 0.0, and `Z0` Norse
  Atlantic UK → **AR**, 5,630 departures, share 0.0; `WPT` World2Fly
  Portugal → **CA**, 2 departures (carrier_nation_precision_audit.csv,
  rows `N0`, `Z0`, `WPT`).
- 244 carrier codes never matched at all, carrying 1,931,914 departures
  (carrier_nation_unmatched.csv, 244 rows, `total_departures` summed);
  the two largest are Avianca `AV` (254,450) and **Asiana `OZ` (204,972;
  22,793 in the 2019–2024 class-F window)** (same file, rows `AV`, `OZ`).
  Asiana's absence makes Seoul/Incheon the one dirty anchor airport:
  foreign match rate at ICN **0.6753** (precision-adjusted **0.6572**)
  versus **0.9562** at Taipei and ≥ 0.9995 at the other 20 anchors
  (carrier_nation_corridor_coverage.csv, rows `ICN` / `TPE`, window
  `full_2019_2024`). **Corridor 1 (US–East Asia) numbers may be computed
  but not reported until the human rules.**
- A reassuring null: of 80 carrier codes whose *name* churns across years
  (173 eras), zero verified cross-border code reissues; the 2 flagged
  candidates (`AI`, `K8`) are marked unresolved for human review
  (carrier_nation_flips.csv, `flip_type` counts; rows
  `name_churn_cross_border`). 22 codes with BTS reissue suffixes were
  *refused* rather than guessed (same file, `suffix_collision_refused`
  rows); in the class-F audit sample those refusals cover 178,674
  departures (coverage_matching_exclusions.csv, `refused_suffix_collision`
  rows, `departures` summed).

The root cause of all of this is the lookup itself:
`data/raw/lookups/airlines.csv` is a 2014-vintage OpenFlights extract,
undated, with corrupted `country` values on dozens of rows. Whether to
replace it with a dated source (ICAO Doc 8585, a BTS carrier decode) is
the second half of the human's FIX-02 decision. **Neither reading of G7
is presented as the answer anywhere in this round.**

### 3c. The US-only panel and outcomes are built, clean, and guarded

- **Panel:** 1,026,729 directed route × nation × month cells; 517,076
  pass `cell_ok` (coverage + ≥ 4 departures) (panel_filter_log.csv, rows
  `aggregate_to_cell`, `cell_ok_final`). The headline sample is **100%
  US on the face of the output**: `n_nations == 1` in every decade row,
  across 4,133 routes and 36 years (desc_sample.csv, `decade_summary`
  rows). The 457,018 cells whose nation fails G6 carry **null** airborne
  time, never a fabricated zero (panel_filter_log.csv, row
  `coverage_ok_g6`) — this "structural-zero guard" matters because the
  raw source *zero-fills*, so any naive mean would report foreign
  flights as taking zero minutes. The guard was mutation-tested by the
  overseer (it aborts rather than ships). **Disclosure: the shipped
  panel drops the `icao` match tier entirely** — 347 detail rows
  (panel_filter_log.csv, row `icao_tier_dropped`) — under the overseer's
  conservative FIX-02 ruling. That exclusion is materially option (a3)
  of the very gate decision the human is being asked to make in D-01,
  already partly in force as a conservative default; it is **not** a
  resolution of the gate.
- **Within-US reporting gaps excluded, never imputed:** 60 detail rows /
  483 departures with positive departures but zero air time were removed
  from both numerator and denominator of the airborne mean (8 rows / 9
  departures for ramp time) (panel_filter_log.csv, rows
  `air_time_zero_gap_excluded`, `ramp_zero_gap_excluded`).
- **311 routes (41,348 departures) drop out entirely** because every
  carrier ever serving them was unmatched/refused (panel_filter_log.csv,
  row `routes_lost_no_matched_carrier`).
- **Excess time behaves like a correctly centred measure:** 393,148 cells
  have an excess value; winsorized excess has median **0.011** minutes,
  mean **0.035**, sd **8.20** (desc_outcomes.csv, row `excess_min_w`,
  `decade == all`); the bidirectional sum exists for 389,446 cells (mean
  0.070, sd 12.60) (same file, row `bidir_sum`). A median of essentially
  zero is what a correct baseline should give. **Do not headline the
  pooled mean:** 0.035 minutes is two seconds, and it is a
  near-cancellation of decade means −0.111 (1990s), +0.752 (2000s),
  −0.412 (2010s), −0.053 (2020s)
  (excess_speed_screen_sensitivity.csv, `screen_mph == 50`, decade rows).
- **The two hard baseline rules (no COVID months, ≥ 2 observations) are
  asserted in code and were mutation-tested** — both abort the run if
  violated.

### 3d. The round's principal limitation: two ten-month blackouts in the event window

The trailing-3-year, COVID-excluded, ≥ 2-observation baseline rule
mechanically wipes out the excess outcome exactly where the paper's
motivating event lives. **The blackout is two ten-month blocks, not one
continuous gap: no month in 2022-03…2022-12 and no month in
2023-03…2023-12 has a single computable excess cell
(`n_excess_computed == 0` on all 20 monthly rows), while January and
February of both years survive** — 1,156 cells in 2022-01, 1,162 in
2022-02, 1,169 in 2023-01, 1,170 in 2023-02 (baseline_failures.csv,
`granularity == 'month'`, rows `US,2022,1` … `US,2023,12`). The reason is
mechanical: a January/February target can still reach its
three-years-back month (Jan/Feb 2020), just outside the COVID bar, so it
keeps two baseline observations; from March onward only one candidate
survives. Every surviving 2022 cell is therefore *in or before* the
event month (the 1,162 surviving 2022-02 cells are contemporaneous with
the late-February 2022 ban, not pre-event). The outcome recovers in 2024 (15,712 cells) and 2025
(17,253) (baseline_failures.csv, `granularity == 'year'`, rows `US,2024`,
`US,2025`, column `n_excess_computed`). Overall, 122,727 of 515,875 valid
cells (23.8%) have no usable baseline (excess_construction_diagnostics.csv,
rows `n_valid_measurement`, and baseline_failures.csv year rows summed);
1990–91 fail 100% because no prior history exists.

**The ≥ 2-observation and COVID-exclusion rules were NOT relaxed and must
not be relaxed by any agent** — changing the baseline definition is a
change to a headline outcome after results are known, i.e. a rule-11
DECISION-PENDING for the human (recorded in DECISIONS.md). Any 2022 event
design on T-100 must use the raw airborne level (which exists in 72 of 72
months on the East Asia and Europe corridors — see 3f), a different
baseline agreed with the human, or the 2024–25 recovery window.

### 3e. Known imperfections, on the record

- **Speed screen fragility:** cells implying a ground speed below 50 mph
  are excluded (328 panel-wide, 141 otherwise clean; 2 zero-distance
  seaplane cells deliberately kept)
  (outcome_data_quality_exclusions.csv / excess_construction_diagnostics.csv).
  But the threshold matters a lot: simply dropping cells implying under
  150 mph removes **1,171 cells (0.30% of 393,148) and moves the pooled
  mean from 0.0347 to 0.0144** — the removed cells carry 8,012 of the
  13,660 total excess minutes, i.e. **58.7% of the outcome's sum sits on
  0.30% of cells** (excess_speed_screen_sensitivity.csv, rows
  `method == naive_filter_shipped_series`, `screen_mph` 50 vs 150,
  columns `n_removed_from_shipped_series`, `mean`, `sum_excess_min_w`).
  A full pipeline re-run at 150 mph gives mean 0.0209 (same file, row
  `full_recompute_stricter_valid_mask`, `screen_mph == 150`). The screen
  is also one-sided: 117 valid cells imply over 700 mph (under-reported
  airborne time, reading as spurious speed-ups) and nothing screens them
  (same file, `screen_mph == 50` full-recompute row,
  `n_speed_gt_700mph_diagnostic`). The threshold is the human's decision;
  no agent changed it.
- **`excess_z` is NOT-FOR-USE.** The z-score divides by a spread measure
  (MAD) built from at most 3 numbers, which can be tiny by chance: 5,904
  cells exceed |z| = 100 and 429 exceed |z| = 1,000
  (excess_construction_diagnostics.csv, rows `n_excess_z_abs_gt_100`,
  `n_excess_z_abs_gt_1000`); 1,629 zero-MAD cells are NaN rather than
  divided (row `n_zero_mad_rows`). The column ships with the caveat in
  its own formula text (desc_outcomes.csv, row `excess_z`) and is parked
  pending a commissioned dispersion measure with a larger pool.
- **The extensive margin is mostly seasonality, not market exit.** Of
  80,260 recorded exits, **78.8% are followed by later re-entry on the
  same route-nation** (50.9% within twelve months, 23.1% within three);
  58.8% of the 20,395 route-nation pairs have more than one entry (max
  88), and the median pair is active in only 5 of 432 months
  (extensive_margin_churn.csv, rows `n_exits`,
  `share_exits_reentering_ever`, `share_exits_reentering_within_12mo`,
  `share_exits_reentering_within_3mo`, `share_triples_with_gt1_entry`,
  `entries_per_triple_max`, `active_months_per_triple_median`). Any exit
  event study needs a spell-based definition (exit = k consecutive
  inactive months) first. This is a construction caveat, not a result.
- **Winsorization documented per route:** 11,040 of 393,148 rows clipped
  across 2,910 routes; 55 thin routes have p1 == p99, where the clip does
  nothing (excess_winsorization_cutoffs.csv, columns `n_clipped`, `p1`,
  `p99`; excess_construction_diagnostics.csv, row `n_winsorized_rows`).
  Note the clip boundary is computed over the full 1990–2025 sample, so a
  2022 cell's boundary can depend on 2025 data.
- **Undocumented service class `Q`:** 721 rows in 1990–1998 carry a
  service class the round file does not name; disclosed, excluded from
  the headline (class-F) sample (ingest_value_drift.csv, the 9 rows with
  `documented_in_round_file == False`, `n_rows` summed).
- **Carrier-group oddity:** `CARRIER_GROUP` takes values {0, 1, 2, 3, 7};
  group 7 appears only in 2002–2004, 382 rows
  (coverage_by_carrier_group.csv, columns `carrier_group`, `year`,
  `n_rows`). Note the `us` label in coverage_column_availability.csv
  pools group 7 with groups 1–3 — its US status is asserted by
  convention, not verified.

### 3f. NEW-06: what the raw picture honestly is — a documented null about the data

The full commissioned family was reported, nulls included: 5,824
corridor × nation × month rows across 4 corridors × 2 windows
(raw_wedge_by_corridor.csv). Airborne time is computable in **358** of
them, and every one is `nation == 'US'`; excess in **226**, again all US
(raw_wedge_by_corridor.csv, non-null `airborne_min_mean_wtd` /
`excess_min_w_wtd` rows). All **5,460 non-US rows carry no outcome value
at all** — an empty side, not a small one. Every empty cell carries its
reason: **3,780** rows had no departures at all that month; **1,685** are
foreign carriers that flew but structurally report no airborne time;
**120** are US months inside the two baseline blackouts; **12** fail the
baseline for other reasons; **1** was too small to measure (same file,
`reason_missing` counts). The treated-vs-control difference table exists
as a completeness record only: 364 rows, `diff_banned_minus_not_banned`
NaN in all 364 **including every placebo-corridor row**, because the
non-banned side is entirely non-US and never has data
(raw_wedge_diffs.csv, `status` column: "NOT A RESULT — COMPLETENESS
RECORD ONLY"). The raw *level* of US airborne time, by contrast, is
nearly complete: 72 of 72 months on US–East Asia and the Europe placebo,
71/72 on US–Middle East, 67/72 on US–India (raw_wedge_by_corridor.csv,
window `full_2019_2024`, US rows, non-null `airborne_min_mean_wtd`) — so
a US-only event design has raw material even where the excess series is
dark. Route-activity and departure counts are populated for all operator
nations (23 nations ever observed on US–East Asia, 30 on the Europe
placebo, 9 on US–Middle East, 2 on US–India — raw_wedge_by_corridor.csv,
distinct `nation` per corridor), with the seasonality caveat above
attached in the file itself. **These nation counts are mapping-derived
and MATCH-SENSITIVE quantities: they are mapped labels, not verified
nationalities** (FIX-02 is blocked, and the counts inherit its known
errors — the placebo corridor's "AR" row is actually `N0`/`Z0` Norse
Atlantic mis-mapped to Argentina, and its "CA" row carries the
2-departure `WPT` false zero; carrier_nation_precision_audit.csv, rows
`N0`, `Z0`, `WPT`). The same caveat applies to the nation labels printed
on `figures/fig_data_availability.png`, which currently carries no
caveat on its face. The 2022 ban list used for the grouping is
agent-drafted and human-unreviewed (`data/raw/events/ban_nations_2022.csv`);
it is caveated in the CSV and grouped nothing that had data anyway.

The five prohibited wedge figures were not produced (the script asserts
their absence at the end of its own run); the shipped figures are a
3-state availability grid and two US-only series explicitly titled "US
carriers only — not a cross-national comparison", with both blackout
blocks shaded.

## 4. Complete list of code scripts created or edited this round

Reconciled against `git log` (commits 69280bc, 355b63e, dfa64fe, f18d712,
57d3fd8, feabab9, 14dfeb3). All are new this round:

- `code/01_ingest/00_bootstrap_manifest.py` — verifies/inventories the 38
  raw inputs, writes bootstrap_manifest.csv (FIX-00, commit 69280bc).
- `code/01_ingest/01_ingest_t100.py` — reads the 36 raw T-100 files,
  harmonizes columns, preserves observed 'NA' codes, writes
  `data/interim/t100_raw.parquet` + ingest diagnostics (FIX-01, 355b63e).
- `code/02_build/02_carrier_nation.py` — carrier→nation mapping with the
  full precision/coverage/sensitivity diagnostic suite (FIX-02, dfa64fe).
- `code/03_audit/03_coverage_audit.py` — nation × year airborne-time
  coverage audit, G6 enforcement, heatmap + TeX table (FIX-03, f18d712).
- `code/03_audit/03b_carrier_group_coverage.py` — the standalone proof of
  the headline: reads the 36 raw CSVs directly (no parquet, no mapping),
  writes coverage_by_carrier_group.csv and
  coverage_column_availability.csv with in-code assertions (FIX-03,
  f18d712).
- `code/04_panel/04_build_panel.py` — the directed route × nation × month
  panel with the structural-zero guard, precision flags, and the
  extensive-margin parquet (FIX-04, 57d3fd8).
- `code/05_outcomes/05_build_excess.py` — baselines, excess, winsorizing,
  bidirectional sum, G8 assertions, screen/winsorization/blackout
  diagnostics (FIX-05, feabab9; note this file was also swept prematurely
  into the FIX-04 commit 57d3fd8 before its own review — a sequencing
  error the orchestrator owned in STATUS.md; the reviewed version is the
  one in feabab9).
- `code/06_wedge/06_wedge_availability.py` — the reduced-form NEW-06:
  availability grid, completeness record, US-only series, with runtime
  guards against producing any wedge figure (NEW-06, 14dfeb3).

Commit 8694d59 ("ENV: restore deleted pipeline infrastructure") added
under `code/` exactly two files, both pre-existing infrastructure
recommitted rather than authored this round: `code/98_check_trino_usage.py`
and `code/opensky_query.py`. The other deleted-but-uncommitted
infrastructure files (`code/utils.py`, `code/99_validate_outputs.py`,
`code/build_run_log.py`, `code/sync_min_scripts.py`, `code/spec_to_tex.py`,
templates, hooks) were restored in the working tree via `git checkout --`
from HEAD 8221a6c and appear in no round-1 commit (STATUS.md, 21:05 UTC
entry); their last commit remains 8221a6c.

## 5. Open problems and flags

Verbatim states from STATUS.md / REVIEW_REPORT.md:

- **FIX-02: BLOCKED-NEEDS-HUMAN, DEGENERATE-GATE** (cycle 3 of 3,
  maximum reached). "The two readings of G7 are both on the record and
  neither is chosen: coverage clears the bound, precision-adjusted does
  not. … The human must rule on whether G7 governs coverage or precision,
  and whether a dated carrier-nationality source should replace the
  OpenFlights extract."
- **Reporting embargo (overseer ruling, still in force):** no
  nation-level number from FIX-04/FIX-05 may be reported until FIX-02
  unblocks; corridor 1 / ICN may be computed but not reported; mapped RU
  and IR are labelled MATCH-SENSITIVE in every output; nothing from
  FIX-02 outputs enters paper/ or slides/.
- **The two ten-month blackouts** (2022-03…2022-12, 2023-03…2023-12) —
  the round's principal limitation for any 2022 event design; the rules
  producing them are not to be relaxed by an agent (rule-11
  DECISION-PENDING, see DECISIONS.md).
- **`excess_z` NOT-FOR-USE** pending a commissioned dispersion measure.
- **Carried advisories (none blocking):** write-before-assert persists
  for some CSVs (several artifacts are written before their in-code
  assertions would abort); one production assert hard-codes a
  reviewer-diagnostic count and will raise on a future data vintage;
  `tables/tab_coverage_audit.tex` caption still says "segment-months" and
  must be fixed before entering paper/;
  `fig_us_only_corridor_series_airborne.png` has a squeezed y-axis (an
  inherited zero line) and its subtitle describes the blackout as a
  single block rather than the correct two blocks (the econometrician is
  regenerating the caption); both must be fixed before paper/slides use;
  the US-only figures carry no "not a headline" note on their face; a
  wording fix is owed on `departures_scope_note` ("matched and retained
  (icao tier dropped)"); one known third false zero (`WPT`/CA, 2 departures)
  is documented but unnamed in the file's own note; the
  `n_speed_gt_700mph_diagnostic` column differs by method row (117 on the
  full-recompute rows vs 48 on the naive-filter rows of
  excess_speed_screen_sensitivity.csv — different conditioning sets, both
  correct; NEW-06 advisory B4); STATUS.md contains
  two early entries with untraced counts, superseded by later entries.
- **`data/raw/events/ban_nations_2022.csv` is agent-drafted and
  human-unreviewed**; flagged wherever used.

## 6. Suggested next steps

Prioritized. Items 1–2 are the human's; the rest are plannable now.

1. **Human decision packet (blocks the paper's core design).** Rule on:
   (a) which reading of G7 governs — coverage, precision, or coverage
   with named low-precision strata excluded — and whether a dated
   carrier-nationality source replaces the OpenFlights lookup; (b) the
   Phase-1 re-scope forced by the missing foreign air time — see
   DECISIONS.md D-02 for the four options with evidence; (c) the
   baseline-window rule for the 2022–23 blackouts; (d) the speed-screen
   threshold. All evidence is in this folder; nothing further is needed
   from agents to decide.
2. **Start the Phase-2 OpenSky extract request now (attended session,
   T1–T9).** This is far more pressing than when the round was planned:
   ADS-B observes *every* operator's airborne time regardless of what
   BTS collects, so it is currently the only path to the carrier-nation
   wedge — the project's central object. Scope per PROJECT.md Phase 2:
   daily, 2019-01-01…2022-12-31, US/Europe–East Asia and US–Middle East
   corridors first. Success = an extract in `data/raw/opensky/` that
   yields per-operator airborne times on the 2022 corridors; the T-100
   round shows exactly which comparisons it must support.
3. **Spell-based extensive-margin measure (EXPLORE, conservative — does
   not pre-commit the human's re-scope choice).** Define exit as k
   consecutive inactive months (grid k ∈ {3, 6, 12}), report the full
   family of resulting churn statistics against the raw flags, and
   re-draw the corridor availability picture on volume outcomes
   (departures, seats, passengers — which foreign carriers DO report).
   Success = a definition under which most flagged exits are not seasonal
   re-entries; failure (all definitions still churn-dominated) parks the
   margin for monthly T-100.
4. **US-only raw-level corridor pictures around 2022-02 (EXPLORE, raw
   means only, no regression).** The raw airborne level exists 72/72
   months on the key corridors. Plot departures-weighted levels by
   corridor with route-composition held fixed (balanced route set), as
   groundwork for the human's option (B) (US-only route-exposure DiD)
   without pre-committing to it. Any DiD itself waits for the human.
5. **If the human supplies a dated nationality lookup:** re-run FIX-02
   once, evaluate G7 once on the ruled reading, and re-run the FIX-03
   audit on volume fields only (time fields are settled — foreign zeros
   are a BTS property, not a mapping property).
6. **Commission a replacement dispersion measure for `excess_z`** (e.g.
   MAD pooled within route over a longer window, or a route-level
   empirical distribution), so Outcome 2's threshold grid (2× MAD etc.)
   has a usable denominator. Until then, the persistence × symmetry
   classifier (menu item 3) stays parked — it is also structurally
   impossible cross-nation on T-100 (the symmetry axis needs foreign
   times) and only a symmetric/US-only variant would be computable.
7. **Ask the human for `data/raw/events/closures.csv`** (the documented-
   closure dictionary) and a review of `ban_nations_2022.csv`; the event
   study (menu item 2) is buildable in US-only or volume form once it
   exists and the re-scope decision is made.
8. **Paper-hygiene fixes bundled into the next round's cleanup task:**
   the .tex caption, the two figure y-axis items, the airborne figure's
   single-block subtitle, the `departures_scope_note` wording, the
   write-before-assert pattern in the two named CSV writers, and
   `build_run_log.py`'s "Active round" header line (it currently picks
   up STATUS.md's first line instead of the round path — cosmetic).
9. **Attended web check (one item):** source BTS's published T-100(f)
   data-element list and check it against the observed foreign schedule
   (volume-only). The observed pattern is established; whether the
   reporting-schedule attribution is the right explanation is what this
   check settles. Belongs in any lit/data appendix.
