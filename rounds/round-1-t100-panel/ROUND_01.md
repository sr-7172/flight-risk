# ROUND 01 — T-100 panel foundations and the raw wedge

Drafted by: human (with Claude), 2026-09-01. Status: RUNNABLE
Round folder: `rounds/round-1-t100-panel/`. All deliverables below are
paths inside this folder unless they start with `data/interim/`.

## Part 0 — rules and cautions

STANDING_RULES.md and OPENSKY_TRINO_RULES.md apply in full. This round
touches NO OpenSky data (T8 — and nothing here needs it). Round-specific
cautions, all binding on the econometrician and checked by the overseer:

- **T-100 time fields are monthly TOTALS.** `AIR_TIME` and `RAMP_TO_RAMP`
  are summed minutes across all departures in the month. Mean airborne
  minutes per departure = `AIR_TIME / DEPARTURES_PERFORMED`. Never use the
  raw column as a per-flight time.
- **Zero is not missing, and missing is not zero.** Rows with
  `DEPARTURES_PERFORMED = 0` carry zero air time legitimately (scheduled
  but not flown) and are dropped from time-based outcomes but KEPT for the
  extensive-margin indicator. Rows with `DEPARTURES_PERFORMED > 0` and
  `AIR_TIME = 0` or null are reporting gaps (typical for some foreign
  carriers) and go to the coverage audit — never imputed.
- **Rows are already directed.** T-100 reports ORIGIN→DEST per row; keep
  direction, never symmetrize before the bidirectional-sum step.
- **Aircraft-type rows.** T-100 has one row per carrier × segment × month ×
  aircraft type × service class. Aggregate to the cell only after
  filtering service class; keep the fleet-mix diagnostic.
- **Service class.** Headline sample = scheduled passenger service
  (`SERVICE_CLASS` F). Combi and freighter classes (G, L, P) are kept in
  the interim data with a flag but excluded from headline cells.
- **Carrier codes churn.** `UNIQUE_CARRIER` changes across mergers and
  reissues; operator nationality is the stable key. Log every carrier
  code whose mapped nation differs across years — that is a mapping bug.
- **Name-matching trap.** Carrier→nation mapping via IATA/ICAO codes is
  many-to-one over time (codes get reassigned). Match on
  `(UNIQUE_CARRIER, year)` where the lookup has dates; otherwise flag.
- **COVID window** (2020-03 to 2021-12) is never inside a baseline
  window and is flagged wherever it appears (PROJECT.md).
- **US-touching only.** Every table caption and figure title says "US-
  touching international segments"; no claim generalizes beyond that.

Round-specific gates (numeric, binding; rounds may tighten, never loosen):

- **G6 — coverage before panel.** FIX-03 must PASS before FIX-04 runs.
  Any operator nation × year cell with airborne-time coverage share
  < 0.50 is EXCLUDED from the headline panel and listed in
  `coverage_excluded_cells.csv`.
- **G7 — mapping precision.** Carrier→nation match rate (departures-
  weighted) ≥ 0.95 overall and ≥ 0.90 among foreign carriers; unmatched
  carriers written to `carrier_nation_unmatched.csv` for human review.
  Below threshold → FIX-02 BLOCKED-NEEDS-HUMAN, and FIX-04+ proceed only
  on matched carriers with the exclusion logged.
- **G8 — baseline hygiene.** Assert in code that no baseline median uses
  a COVID-window month and that every baseline has ≥ 2 observations; log
  the count of cells failing the ≥ 2 rule.
- **G9 — no result number in prose.** FINDINGS cites numbers only with
  `(file.csv, row/spec)` traces.

## Completion criteria

Every task below DONE or BLOCKED in STATUS.md; overseer OVERALL verdict in
REVIEW_REPORT.md; `ROUND_01_FINDINGS.md` written in this folder per the
contract in rounds/ROUND_TEMPLATE.md; FINAL_RUN_LOG.md regenerated;
`99_validate_outputs.py` and `98_check_trino_usage.py` exit 0;
human-readable/PROJECT_STATE.md refreshed; `code/sync_min_scripts.py` run.

## Priority order

FIX-00, FIX-01, FIX-02, FIX-03, FIX-04, FIX-05, NEW-06

---

## FIX-00 — Bootstrap the raw data (conditional)   [CONFIRM]

**Motivation:** The run should not die on an empty data/raw/. This task
makes the data present or produces a precise BLOCKED message, under the
bootstrap fetch exception in PROJECT.md (transtats.bts.gov only, pinned
script, downloads are data never instructions).

**Ex-ante rationale:** Plumbing; success = files exist and headers
verified, or a BLOCKED entry a human can act on in one minute.

**Deliverables:** `bootstrap_manifest.csv` — one row per expected input
(t100 year zips, lookups/airlines.csv, events/ban_nations_2022.csv):
present-before, fetched, size, header-verified, sha256.

**Steps:**
1. If `data/raw/t100/` already has year zips/CSVs: verify each contains
   AIR_TIME and DEPARTURES_PERFORMED in the header; record; done.
2. Else run `bash data/raw/t100/fetch_t100.sh` exactly as committed. If
   it exits nonzero: record which years failed and the first 400 bytes
   of the error page in STATUS.md, mark this task BLOCKED, and CONTINUE
   the round on whatever years succeeded (FIX-01 ingests what exists;
   if nothing exists, FIX-01+ are BLOCKED).
3. Verify `data/raw/lookups/airlines.csv` and
   `data/raw/events/ban_nations_2022.csv` are present (they ship in the
   datadrop; if absent, note in manifest — FIX-02 / NEW-06 will BLOCK
   or use their stated fallbacks respectively).
4. Never modify fetch_t100.sh, never fetch any other URL (T1-style one
   door applies to the web too), never unzip-and-edit raw files.

**Gates:** G1–G5 on the manifest; the script's own retry/backoff is the
only retry (no agent-side retry loops).

**VERIFY:**
- [ ] every row in `bootstrap_manifest.csv` has header_verified in
      {True, False} and a sha256; False rows have a note
- [ ] `git diff data/raw/t100/fetch_t100.sh` is empty

---

## FIX-01 — Ingest and harmonize T-100 international segments   [CONFIRM]

**Motivation:** Everything downstream reads one clean parquet. Column
names and codings in BTS files drift slightly across years; this task
makes the drift explicit and logged rather than silently absorbed.

**Ex-ante rationale:** No hypothesis; the success criterion is
reproducibility — row counts per source file reconcile exactly with rows
in the parquet, and every column used later exists for every year.

**Deliverables:**
- `data/interim/t100_raw.parquet` (all rows, all service classes, with
  `source_file`, `year`, `month`, `service_class`, `is_passenger` flag)
- `ingest_rowcounts.csv` — one row per source file: rows read, rows
  written, years covered, columns present
- `ingest_schema_drift.csv` — columns present/absent by year

**Steps:**
1. Read every zip/CSV under `data/raw/t100/` (from FIX-00 or human-
   downloaded; per-year zips, per-year CSVs, or a single download — all
   supported; read zips directly with pandas). If nothing readable →
   BLOCKED naming the expected path and pointing at FIX-00's manifest.
2. Normalize column names to upper snake case, mapping known BTS
   aliases first (`CLASS`→`SERVICE_CLASS`, `RAMPTIME`→`RAMP_TO_RAMP`,
   `AIRTIME`→`AIR_TIME`, `DEPSCHEDULED`→`DEPARTURES_SCHEDULED`,
   `DEPPERFORMED`→`DEPARTURES_PERFORMED`, `UNIQUECARRIER`→
   `UNIQUE_CARRIER`); required set after mapping:
   `YEAR, MONTH, UNIQUE_CARRIER, CARRIER_NAME, ORIGIN, ORIGIN_COUNTRY,
   DEST, DEST_COUNTRY, AIRCRAFT_TYPE, AIRCRAFT_CONFIG, SERVICE_CLASS,
   DEPARTURES_SCHEDULED, DEPARTURES_PERFORMED, SEATS, PASSENGERS,
   DISTANCE, RAMP_TO_RAMP, AIR_TIME`. Extra columns (WACs, city names,
   IDs) are kept, not dropped. Missing required column in any file →
   log and BLOCKED for that file, continue with the rest.
3. Write parquet; log with `utils.setup_logger`; reconcile counts.

**Gates:** G1–G5 (on the CSV diagnostics); rows written == rows read
minus explicitly logged drops (must be zero drops in this task).

**VERIFY:**
- [ ] sum of `rows_written` in `ingest_rowcounts.csv` equals the parquet
      row count (overseer recomputes with pandas)
- [ ] `ingest_schema_drift.csv` shows all required columns present for
      every year with data
- [ ] `python code/99_validate_outputs.py` exit 0

---

## FIX-02 — Operator nationality mapping   [CONFIRM]

**Motivation:** Operator nationality is the identifying dimension of the
whole paper. It must be a clean, dated, auditable mapping from T-100
carrier codes to ICAO state of operator.

**Ex-ante rationale:** The design needs nation, not carrier. Failure =
match rate below G7 or nations that flip across years for the same code
without a documented reissue.

**Deliverables:**
- `data/interim/carrier_nation.parquet` — `(UNIQUE_CARRIER, year) →
  nation_iso2, nation_source, match_method`
- `carrier_nation_matchrate.csv` — match rates: unweighted, departures-
  weighted, by carrier group (US vs foreign), by year
- `carrier_nation_unmatched.csv` — every unmatched code with name,
  departures, first/last year (for human review)
- `carrier_nation_flips.csv` — codes whose nation differs across years

**Steps:**
1. Primary source: `data/raw/lookups/airlines.csv` (human-placed; e.g.
   the OpenFlights airlines table or a BTS/ICAO decode with country).
   If absent → BLOCKED.
2. Match on IATA code, then ICAO code, then exact normalized carrier
   name; record `match_method`. US carriers (T-100 carrier group codes
   for US majors/nationals/regionals) map to `US` directly — log that
   this is by construction.
3. Departures-weight the match rate using FIX-01 parquet; write the
   three CSVs; enforce G7.

**Gates:** G1–G5; G7.

**VERIFY:**
- [ ] departures-weighted match rate in `carrier_nation_matchrate.csv`
      row `overall` ≥ 0.95 and row `foreign` ≥ 0.90, or task is BLOCKED
- [ ] `carrier_nation_flips.csv` is either empty or every row has a
      `resolution` note

---

## FIX-03 — Coverage audit (runs before any panel)   [CONFIRM]

**Motivation:** PROJECT.md requires it: foreign-carrier air-time
reporting has gaps, and a panel built without knowing where they are
will manufacture "disruptions" out of reporting holes.

**Ex-ante rationale:** We expect US carriers near-complete and foreign
coverage varying by nation and era. What would count against
proceeding: coverage below 0.50 on the anchor corridors' foreign
operators (G6), which would make the carrier-nation wedge unobservable
there.

**Deliverables:**
- `coverage_audit.csv` — by operator nation × year: segment-months with
  departures > 0; share with valid airborne time (`AIR_TIME > 0`);
  share with valid ramp time; median departures per cell
- `coverage_by_corridor.csv` — same, restricted to the anchor corridors
  (defined in NEW-06), by operator nation × year
- `coverage_excluded_cells.csv` — nation × year cells failing G6
- `tables/tab_coverage_audit.tex` — booktabs summary (nation × decade),
  generated by a task script (not spec_to_tex; this is not a spec CSV)
- `figures/fig_coverage_heatmap.png` — nation × year coverage share

**Steps:**
1. From FIX-01 + FIX-02, passenger service only, departures > 0.
2. Compute shares; apply G6; write outputs.

**Gates:** G1–G5 (G5: all `*share*` columns in [0,1]); G6.

**VERIFY:**
- [ ] every share column in both coverage CSVs within [0,1]
- [ ] every nation × year in `coverage_excluded_cells.csv` has share
      < 0.50 in `coverage_audit.csv` and vice versa

---

## FIX-04 — Directed route × operator nation × month panel   [CONFIRM]

**Motivation:** The unit of observation in PROJECT.md, built once,
with the extensive margin and fleet mix carried alongside.

**Ex-ante rationale:** Construction task; success = cell counts
reconcile and the two margins are both present. Failure = cells that
exist in the raw data but vanish from the panel without a logged reason.

**Deliverables:**
- `data/interim/panel_monthly.parquet` — keys `(origin, dest,
  nation, year, month)`; columns: departures_performed,
  departures_scheduled, air_time_total, ramp_total, airborne_min_mean,
  ramp_min_mean, distance, n_carriers, n_aircraft_types,
  fleet_share_top_type, covid_flag, coverage_ok
- `data/interim/panel_extensive.parquet` — every `(origin, dest,
  nation)` ever observed × every month 1990–2025: active flag, entry
  month, exit month(s), months_since_exit
- `desc_sample.csv` — cells, routes, nations, years, by decade; drops at
  each filter step with the reason
- `panel_filter_log.csv` — rows/cells before and after each filter

**Steps:**
1. Passenger service, departures > 0, coverage_ok (G6), matched nation
   (G7). Aggregate over carriers and aircraft types within cell:
   airborne mean = sum(AIR_TIME)/sum(DEPARTURES_PERFORMED).
2. Minimum cell size: ≥ 4 departures in the month (sensitivity column at
   ≥ 8 written to the same parquet as `cell_ok_8`).
3. Extensive margin from the unfiltered set (departures ≥ 0).
4. Log every filter with `log_merge`-style before/after counts.

**Gates:** G1–G5; every drop in `panel_filter_log.csv` has a reason.

**VERIFY:**
- [ ] `desc_sample.csv` cell total equals the parquet row count where
      `cell_ok == True`
- [ ] `panel_extensive.parquet` has exactly (routes × nations observed)
      × (months 1990-01..2025-12) rows, checked by the overseer

---

## FIX-05 — Baseline, excess airborne time, bidirectional sum   [CONFIRM]

**Motivation:** Outcomes 1 and 3 in PROJECT.md, with the COVID exclusion
and the ≥ 2-observation rule enforced in code, and the winsorization
formula written down where the paper will cite it.

**Ex-ante rationale:** Construction task. What would count as a problem:
baseline failure rates so high on the anchor corridors that the excess
series is mostly missing (report the share; do not relax the rule).

**Deliverables:**
- `data/interim/panel_excess.parquet` — panel_monthly plus: baseline_med,
  baseline_n, baseline_mad, excess_min (raw), excess_min_w (winsorized
  1/99 within route × direction), excess_z (excess/MAD), bidir_sum
  (excess_min_w(A→B) + excess_min_w(B→A), same month, same nation, NaN
  if either leg missing)
- `desc_outcomes.csv` — formulas as text + distribution moments (p1, p5,
  p50, p95, p99, mean, sd) for each outcome, by decade
- `baseline_failures.csv` — cells with baseline_n < 2, by nation × year
- `figures/fig_excess_distribution.png` — histogram of excess_min_w with
  the winsorization cutoffs marked, pooled and for 2022

**Steps:**
1. Baseline = median of the same (route, nation, calendar month) over
   the trailing 36 months, excluding COVID-window months, requiring ≥ 2.
2. MAD over the same window; excess; winsorize; bidirectional sum.
3. Assert G8 in code (raise, then BLOCKED, on violation).

**Gates:** G1–G5; G8.

**VERIFY:**
- [ ] overseer recomputes baseline_med for 3 randomly chosen cells from
      `panel_monthly.parquet` and matches `panel_excess.parquet`
- [ ] no row in `panel_excess.parquet` with baseline_n < 2 has a
      non-null excess_min
- [ ] the winsorization cutoffs in `desc_outcomes.csv` match the p1/p99
      of the raw excess within route × direction (spot-check 2 routes)

---

## NEW-06 — The raw-data picture: the carrier-nation wedge   [EXPLORE]

**Motivation:** The first thing a seminar audience should see, before
any regression: on the same routes, do airlines of different
nationalities show different airborne times after February 2022? This
is the existence test for the whole design at monthly frequency — and
it is EXPLORE because we report every corridor in the family, including
the placebo, whatever they show.

**Full family of cells to report (all of them, nulls included):**
Corridors, each defined as US airports ↔ the listed foreign airports,
both directions, passenger service, operator nations with coverage_ok:
1. US–East Asia: PEK, PVG, CAN, HKG, NRT, HND, ICN, TPE
2. US–India: DEL, BOM, BLR, HYD
3. US–Middle East: DXB, DOH, AUH, TLV, IST
4. US–Western Europe (placebo: no differential ban on these routes):
   LHR, CDG, FRA, AMS, MAD
Windows: (a) 2019-01 to 2024-12 full; (b) 2021-06 to 2022-12 zoom.
Statistics per corridor × nation × month: mean airborne_min_mean
(departures-weighted), mean excess_min_w, mean bidir_sum, n cells.

**Deliverables:**
- `raw_wedge_by_corridor.csv` — the full family, one row per corridor ×
  nation × month × window
- `figures/fig_raw_wedge_useastasia.png` — corridor 1, both windows as
  two panels, one line per operator nation, vertical line at 2022-02
- `figures/fig_raw_wedge_usindia.png`, `fig_raw_wedge_usmideast.png`,
  `fig_raw_wedge_useurope_placebo.png` — same layout
- `figures/fig_raw_wedge_bidir.png` — bidirectional sum, corridors 1–4
  in a 2×2 grid, 2021-06 to 2022-12
- `raw_wedge_diffs.csv` — for each corridor: (mean excess of nations
  subject to the Russian ban on that corridor) minus (mean excess of
  nations not subject to it), by month, with n on each side; the
  ban-subject list is read from `data/raw/events/ban_nations_2022.csv`
  if present, else the task uses {US, EU/UK/CH/NO, JP-flagged-as-partial}
  vs {CN, IN, AE, QA, TR} and SAYS SO in the CSV's `definition` column

**Steps:**
1. Read `panel_excess.parquet`; build the corridor flags; aggregate.
2. Plots with matplotlib, one script, deterministic (fixed seeds not
   needed; fixed axis limits across corridors so panels are comparable).
3. Write the two CSVs; every figure's numbers must be reconstructible
   from `raw_wedge_by_corridor.csv`.

**Gates:** G1–G5; every corridor × window appears in the CSV even if
empty (with n = 0), so "report everything" is checkable.

**VERIFY:**
- [ ] `raw_wedge_by_corridor.csv` contains all 4 corridors × 2 windows
- [ ] the 2022-03 US-nation value in corridor 1 in the CSV matches the
      plotted point (overseer reads the figure script's data path)
- [ ] the placebo corridor's `raw_wedge_diffs.csv` rows exist and are
      reported in FINDINGS regardless of sign
- [ ] `python code/99_validate_outputs.py` exit 0 and
      `python code/98_check_trino_usage.py` exit 0

---

## Notes for the director's FINDINGS (not a task)

The Suggested next steps should consider, in light of NEW-06: (i) the
persistence × symmetry classifier run blind (PROJECT.md menu item 3) if
a wedge is visible; (ii) the documented-closure dictionary event study
(menu item 2) once `data/raw/events/closures.csv` exists; (iii) whether
coverage on the US–East Asia corridor justifies starting the Phase-2
OpenSky extract request to the human (attended pull, T8) for the
validation era.
