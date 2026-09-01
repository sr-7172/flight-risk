# STATUS

[2026-09-01 21:02 UTC] RUN START — active round: rounds/round-1-t100-panel/ROUND_01.md (unattended, auto 1)

[2026-09-01 21:05 UTC] ENV REPAIR (orchestrator, pre-task):
  - Restored 17 files that were deleted-but-uncommitted in the working tree
    (code/utils.py, code/99_validate_outputs.py, code/build_run_log.py,
    code/sync_min_scripts.py, code/spec_to_tex.py, rounds/ROUND_TEMPLATE.md,
    .claude agents/commands/hooks/skills, data/*/.gitkeep) via `git checkout --`
    from HEAD 8221a6c. Without these the round contract cannot execute.
  - Data drop had landed at ./raw/ ; moved raw/{t100,lookups,events} to
    data/raw/ (contents unmodified; move only). 36 T-100 year CSVs
    (1990-2025, uncompressed), lookups/airlines.csv, events/ban_nations_2022.csv.
  - Env OK: pandas 3.0.5, pyarrow 25.0.1; validator exit 0; trino check exit 0.

[2026-09-01 21:06 UTC] FIX-00 DONE. data/raw/t100/ already had all 36 year
  CSVs (step 1 of FIX-00 applied — no fetch attempted, fetch_t100.sh not
  present and not needed). code/01_ingest/00_bootstrap_manifest.py wrote
  rounds/round-1-t100-panel/bootstrap_manifest.csv, one row per expected
  input file (36 t100 + 1 lookup + 1 event = 38 rows), with
  present_before/fetched/size_bytes/header_verified/sha256/note per row.
  All rows header_verified True. 99_validate_outputs.py and
  98_check_trino_usage.py both exit 0. data/raw/ untouched (git status
  clean under data/raw/); no fetch_t100.sh exists so its diff is
  trivially empty.
[2026-09-01 21:12 UTC] FIX-00 DONE — overseer VERDICT: PASS (REVIEW_REPORT.md). Bootstrap manifest written; all expected inputs present and header-verified; no fetch needed, data/raw/ unmodified. Carried-forward advisories: widen t100 glob to zips in FIX-01; NEW-06 must caveat the agent-drafted ban_nations_2022.csv.
[2026-09-01 21:15 UTC] FIX-01 DONE. code/01_ingest/01_ingest_t100.py reads
  every CSV/zip under data/raw/t100/ (glob widened to both extensions per
  FIX-00 advisory), normalizes column names to upper snake case with the
  BTS alias map (CLASS->SERVICE_CLASS etc.), verifies the required column
  set per file, and writes data/interim/t100_raw.parquet with source_file,
  year, month, service_class, is_passenger provenance columns added. All
  36 source files matched the single canonical T-100 header (schema-drift
  check found zero drift in this drop); sum(rows_written) in
  ingest_rowcounts.csv reconciles exactly against the parquet row count
  and against rows_read, with rows_dropped == 0 for every file (verified
  independently with pandas). String/code columns (UNIQUE_CARRIER, ORIGIN,
  DEST, country codes, SERVICE_CLASS, AIRCRAFT_TYPE, AIRCRAFT_CONFIG) kept
  as strings [SUPERSEDED — see cycle-2 entry below: this was false as
  written for UNIQUE_CARRIER, CARRIER, ORIGIN_COUNTRY, DEST_COUNTRY, whose
  observed 'NA' values were being read as null under keep_default_na=True].
  No file BLOCKED. 99_validate_outputs.py and 98_check_trino_usage.py both
  exit 0. data/raw/ sha256s re-verified against FIX-00's
  bootstrap_manifest.csv — unchanged.
[2026-09-01 21:22 UTC] FIX-01 cycle 1 — overseer VERDICT: FAIL (blocking). Ingest read T-100 with pandas default NA strings, converting the observed code 'NA' (North American Airlines; Namibia country code) into nulls and conflating it with genuinely blank cells. Required actions 1-7 returned to the econometrician; cycle 2 of 3 in progress. Row reconciliation, calendar completeness and raw-file integrity were verified correct and are being preserved.
[2026-09-01 21:25 UTC] FIX-01 cycle 2 — required actions addressed.
  code/01_ingest/01_ingest_t100.py now reads each file with
  keep_default_na=False plus a per-column na_values map: STR_TARGET_COLS
  (UNIQUE_CARRIER, CARRIER, ORIGIN/DEST, country codes, SERVICE_CLASS,
  AIRCRAFT_TYPE, AIRCRAFT_CONFIG, name/region fields) treat ONLY the empty
  string as missing; numeric/ID columns keep pandas' full default NA-string
  list. Observed codes (carrier 'NA' = North American Airlines, country
  'NA' = Namibia) are now preserved as literal strings, separated from
  genuinely blank cells. All eight reviewer-specified value-level
  assertions (UNIQUE_CARRIER/CARRIER/ORIGIN_COUNTRY/DEST_COUNTRY =='NA'
  counts and .isna() counts) are computed and logged in code against exact
  expected values and pass. Parquet re-written: still 2,662,470 rows,
  rows_dropped == 0 on all 36 files, 432 distinct year-months, single
  canonical header across all 36 files, raw sha256s unchanged — all
  previously-verified invariants preserved and re-checked independently
  with pandas. Added rounds/round-1-t100-panel/ingest_value_drift.csv (one
  row per year x SERVICE_CLASS with row count, DEPARTURES_PERFORMED sum,
  and documented_in_round_file — False only for class Q, which Part 0 does
  not name). Added a standing per-file NA-string guard: a lightweight
  second read of only the code/string columns under naive
  keep_default_na=True, logged (not silent) wherever its null count would
  differ from the corrected read, so this bug class cannot recur silently
  on a future data drop. is_passenger kept as name (per task's stated
  option) with a docstring/comment clarifying it flags SERVICE_CLASS=='F'
  only, not a full passenger-carrying indicator (class L is passenger
  charter and is excluded by design). 99_validate_outputs.py now scans 4
  CSVs, exit 0; 98_check_trino_usage.py exit 0.
[2026-09-01 21:30 UTC] FIX-01 DONE (cycle 2) — overseer VERDICT: PASS. NA-nulling bug fixed at the read layer with in-code assertions (reviewer confirmed they raise: flipped-constant test exits 1) and a standing NA-string guard; parquet rewritten and deterministic. Advisories carried to FINDINGS: (1) parquet is still written before the assertion exit-1 return; (2) the eight expected counts are drop-specific literals, the durable check is the guard; (3) undocumented SERVICE_CLASS Q must be disclosed; (4) exact-duplicate rows and cell-key non-uniqueness — FIX-04 must aggregate, not assume uniqueness; (5) FIX-02 must run on the NEW parquet only, any cycle-1 G7 figure is void.
[2026-09-01 21:45 UTC] FIX-02 cycle 1 — overseer VERDICT: FAIL. Coverage figures verified honest and reproducible, but G7 ("mapping precision") was measured as coverage only; a route-endpoint precision audit shows many ambiguous IATA-code collisions resolved to the wrong carrier nation, so the two readings of G7 disagree by far more than the pass margin. DEGENERATE-GATE expected. Required actions 1-9 returned to the econometrician; cycle 2 of 3 in progress. Rate-raising changes are prohibited without a written director commission (rules 4 and 10).
[2026-09-01 22:10 UTC] FIX-02 cycle 2 — required actions 1-9 addressed in code/02_build/02_carrier_nation.py. Structural fix (action 4): reissue-suffix families that would silently collapse two BTS-distinct carriers onto one shared nation are now detected and refused rather than guessed, logged to carrier_nation_flips.csv with a resolution note (file is no longer vacuously empty). New diagnostics added, changing no mapping: carrier_nation_precision_audit.csv (one row per matched-foreign code: observed home-country departure share, top observed endpoint, OpenFlights candidate(s)), carrier_nation_audit_sample.csv (40 largest + random 40 for human tier scoring), carrier_nation_corridor_coverage.csv (matched-departure share by NEW-06 anchor airport x window), and carrier_nation_flips.csv's name-churn-under-fixed-nation diagnostic (replacing the mechanically-vacuous cross-year check). carrier_nation_matchrate.csv gained foreign x year and foreign x service_class rows plus both G7 readings side by side (coverage and precision-adjusted); carrier_nation_unmatched.csv gained modal foreign-endpoint country and recent-window departures.
  G7 has two defensible readings on this drop that disagree on pass/fail: a coverage reading (does the code resolve to some OpenFlights candidate) and a precision-adjusted reading (does the matched code's own T-100 traffic ever touch its mapped home country). Per STANDING_RULES rule 4, neither reading is chosen. **DEGENERATE-GATE flag set. FIX-02 is BLOCKED-NEEDS-HUMAN** pending a human decision on which reading of G7 governs (or a director-commissioned change to the matching rules, which would need to be justified and reported both ways per action 8, not picked by the agent). All requested numbers are in the round-folder CSVs named above (carrier_nation_matchrate.csv rows `overall`/`foreign`/`foreign_by_year`/`foreign_by_service_class`; carrier_nation_precision_audit.csv; carrier_nation_flips.csv; carrier_nation_corridor_coverage.csv); none are typed here. Re-run confirmed byte-identical. 99_validate_outputs.py and 98_check_trino_usage.py both exit 0.
[2026-09-01 22:25 UTC] FIX-02 cycle 2 — overseer VERDICT: FAIL (diagnostics incomplete; DEGENERATE-GATE declaration itself endorsed). All cycle-2 numbers reproduced exactly by independent reconstruction. Five additive gaps: gate sensitivity to the weakest match tier not on the record; per-tier precision only in a log, uncitable under G9; no precision reading on the class-F headline sample; corridor table pools US carriers unlabelled; unmatched CSV lacks candidate columns. Cycle 3 of 3 in progress — additive diagnostics only, no mapping change. Terminal state will be BLOCKED-NEEDS-HUMAN either way.
[2026-09-01 22:40 UTC] FIX-02 cycle 3 (final — max cycles reached) — required actions 1-6 addressed additively in code/02_build/02_carrier_nation.py; no mapping changed (action 4's suffix-collision refusal from cycle 2 stands unmodified; action 7 left code/02_build/ for the coordinator to commit). New round-folder deliverables, all sensitivities/diagnostics, none preferred over another: carrier_nation_gate_sensitivity.csv (the coverage reading's margin over G7_FOREIGN_MIN stated in departures, set beside the icao tier's departures and its own home0 rate, plus an excl-icao-tier coverage recomputation for both scopes); carrier_nation_tier_precision.csv (per-tier n_codes/departures/home0 share/<0.01 share/implausible-pairs list, now citable under G9 instead of log-only); carrier_nation_matchrate.csv gained overall_classF/foreign_classF/us_classF rows plus both precision-adjusted variants (home0 and <0.01 thresholds) on both the all-classes and class-F cuts; carrier_nation_corridor_coverage.csv now reports all-carrier, foreign-only, and foreign-precision-adjusted match rates side by side per anchor x window (previously only the all-carrier figure, which pools in trivially-matched US carriers), plus covid_flag/covid_month_share per window; carrier_nation_unmatched.csv gained n_openflights_candidates and candidate_names so a human can see AV/OZ/etc.'s specific failure mode without re-deriving it from airlines.csv. Also fixed a stale hardcoded row-count literal in the null_carrier_code note (now interpolated from n_null_rows).
  Every new figure is reported as a sensitivity or diagnostic; the DEGENERATE-GATE framing is unchanged from cycle 2 and neither reading of G7 is presented as the answer. **Final state: BLOCKED-NEEDS-HUMAN, DEGENERATE-GATE.** All numbers live in the round-folder CSVs named above; none are typed here. Re-run confirmed byte-identical across all carrier_nation_*.csv and the parquet. 99_validate_outputs.py and 98_check_trino_usage.py both exit 0 (the pipeline script itself correctly exits 1, reflecting BLOCKED).
[2026-09-01 22:40 UTC] FIX-02 BLOCKED-NEEDS-HUMAN (DEGENERATE-GATE) — cycle 3 of 3 complete; per STANDING_RULES rule 7 the task is recorded BLOCKED and the round continues. The two readings of G7 are both on the record and neither is chosen: coverage clears the bound, precision-adjusted does not. Decision-grade diagnostics now in the round folder (gate sensitivity, per-tier precision, class-F headline-sample readings, corridor coverage with foreign/precision splits, unmatched carriers with OpenFlights candidates). The human must rule on whether G7 governs coverage or precision, and whether a dated carrier-nationality source should replace the OpenFlights extract.
  Overseer ruling on downstream tasks (Part 0 G7 clause): FIX-03 MAY PROCEED with the excluded codes logged; FIX-04 MAY BUILD with precision flags and the icao tier dropped, but no nation-level number may be REPORTED until FIX-02 unblocks; FIX-05 MAY PROCEED under the same embargo; NEW-06 MAY BUILD but not as a headline, must ship a precision-excluded version alongside, and corridor 1 / ICN may be computed but NOT reported.
