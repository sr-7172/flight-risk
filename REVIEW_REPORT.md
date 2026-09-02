# REVIEW REPORT (overseer, append-only)

## FIX-00 review — 2026-09-01 21:08 UTC

VERDICT: PASS

Scope reviewed: `rounds/round-1-t100-panel/ROUND_01.md` Part 0 + FIX-00;
script `code/01_ingest/00_bootstrap_manifest.py`; deliverable
`rounds/round-1-t100-panel/bootstrap_manifest.csv` (38 data rows).

Checks run (all recomputed independently by the overseer, read-only):

1. Manifest shape: 38 data rows, columns
   `path,kind,present_before,fetched,size_bytes,header_verified,sha256,note`.
   Zero empty cells in any column; 38 unique paths; 38 unique sha256; all
   sha256 match `[0-9a-f]{64}`.
2. VERIFY item 1 (literal): `header_verified` ∈ {True, False} for 38/38 rows
   (all True, 0 False), and `sha256` non-empty for 38/38. No False rows
   exist, so the "False rows have a note" clause is vacuously satisfied; I
   separately exercised the code path (see check 5) and confirmed False rows
   are always written with a non-empty note.
3. sha256 spot-checks against `sha256sum` — 6 of 38 checked by hand, then all
   38 recomputed programmatically. Hand checks:
   - `data/raw/t100/T_T100I_SEGMENT_ALL_CARRIER_1990.csv`
     `da97a8cf611f44092190858620dd430d9f8f35a485b841d4d2fa4525fb6bef57` — match
   - `..._2007.csv` `324880ed63dec9d7901ba12199cf4272193b7d0712ab217089f5d86c9c7b7bf2` — match
   - `..._2020.csv` `ea08b189d1964e60cee1f287893e035bd781a57c7270d4f24cd3834f7b1ac599` — match
   - `..._2025.csv` `0449b4907608ff977bcd0ccff6b034f52d49a9a42f4176eadf35aac2d7601014` — match
   - `data/raw/lookups/airlines.csv` `de19b5c18c623c39c3d62dafb929b5afee879d324c3083bbda1037dba0072ebd` — match
   - `data/raw/events/ban_nations_2022.csv` `e4946e9fbc465faa4bc83f3e1e8c544d67381e5c833cab8af56351f250f77f3f` — match
   Programmatic sweep: 0/38 rows failed sha256, size_bytes, or
   header_verified recomputation.
4. size_bytes spot-checks against `stat -c %s` — 1990: 14335642; 2007:
   21790588; 2020: 16360343; 2025: 31747310; airlines.csv: 316849;
   ban_nations_2022.csv: 2066. All six match the manifest exactly.
5. Header verification is real, not hardcoded. (a) `head -1` on the 1990,
   2002, 2019, 2025 files shows `DEPARTURES_PERFORMED` (field 2) and
   `AIR_TIME` (field 10) literally present; `airlines.csv` header is
   `airline_id,name,alias,iata,icao,callsign,country,active`;
   `ban_nations_2022.csv` header is
   `nation_iso2,status,effective_date,notes` — matching the three
   required-column sets in the script. (b) I imported the module in a temp
   directory OUTSIDE `data/raw/` and called `manifest_row()` on synthetic
   headers: header `FOO,BAR` → header_verified False, note "missing expected
   header columns: ['AIR_TIME', 'DEPARTURES_PERFORMED']"; header
   `AIR_TIME,BAR` → False, note names only `DEPARTURES_PERFORMED`; header
   `BAR,DEPARTURES_PERFORMED,ZZZ,AIR_TIME` → True. Absent file → False with
   the caller's note and empty sha256/size. The check is a genuine set
   difference (lines 87-94), not a constant.
6. Completeness. `find data/raw -type f -name '*.csv'` returns exactly the
   38 CSVs listed in the manifest; `comm` in both directions is empty
   (nothing on disk omitted, nothing in the manifest absent from disk).
   Years present: 1990-2025 contiguous, 36 files, no gaps. Non-CSV files
   under data/raw are only `.gitkeep`, two provenance `README.md`, and a
   `.DS_Store` — none is an expected analysis input.
7. Nothing downloaded, nothing under data/raw modified. All 41 files under
   `data/raw/` carry mtimes 21:01:09-21:01:16 (the orchestrator's data-drop
   move) except `data/raw/.gitkeep` at 21:03:14 (orchestrator env repair);
   the script ran at 21:05:30, after every one of them. No file under
   `data/raw/` has an mtime newer than 21:04. `fetch_t100.sh` does not exist
   anywhere in the repo, and `logs/00_bootstrap_manifest.log` records
   "data/raw/t100/ has 36 CSV(s) already present — skipping fetch (step 1
   applies)", so the step-2 branch was never entered. Step-1 branch is the
   correct branch and the VERIFY item `git diff data/raw/t100/fetch_t100.sh`
   is vacuous.
8. Network / rules. The script imports only `csv, hashlib, subprocess, sys,
   pathlib` plus `utils.setup_logger`; no `requests`/`urllib`/`socket`/curl/
   wget. The single `subprocess.run` is the pinned-fetch call on line 121,
   unreached. No `pyopensky`/`trino`/`traffic` import.
   `python code/98_check_trino_usage.py` → "trino-usage check: 0 FAIL",
   exit 0 (re-run by me). T8 respected: no live pull in an unattended run.
9. Conventions: `sys.path.insert(0, str(ROOT / "code"))` with
   `ROOT = parents[2]` (correct from `code/01_ingest/`), `utils.setup_logger`
   used, log written to `logs/00_bootstrap_manifest.log`, output written
   inside the active round folder.
10. Determinism / re-runnability: I re-ran the script; exit 0 and the
    regenerated `bootstrap_manifest.csv` is byte-identical to the pre-run
    copy (`diff` empty). Ordering comes from `sorted(glob)`; no timestamps,
    no randomness in the CSV. Re-run touched no file under `data/raw/`.
11. Validator: `python code/99_validate_outputs.py` → "validate: 1 CSVs
    scanned, 0 FAIL, 0 WARN", exit 0 (re-run by me). The one CSV scanned IS
    `rounds/round-1-t100-panel/bootstrap_manifest.csv`, i.e. the round's new
    file sits inside the active round folder and is covered by the
    directory-wide scan. No result CSV was written outside the round folder.
12. Pathology hunt: not applicable in substance (no coef/se/pval columns, no
    inference performed), and confirmed vacuous rather than skipped — no
    column name contains share/rate/survival/precision, no numeric column
    other than size_bytes (all positive integers matching `stat`).

Gate status:
- G1 (no empty coef/se/pval; pval in [0,1]) — N/A, no inference columns;
  separately verified NO cell in ANY column is empty. PASS (vacuous).
- G2 (|coef|>100 on log/share) — N/A. PASS (vacuous).
- G3 (no p=0.0, no repeated p) — N/A. PASS (vacuous).
- G4 (SE scale) — N/A. PASS (vacuous).
- G5 (shares/rates in [0,1]; family counts) — no bounded-token column exists.
  PASS (vacuous).
- G6, G7, G8 — not in scope for FIX-00 (FIX-02/03/05).
- G9 (no result number in prose) — see finding 3 below; PASS with note.
- T1-T9 — no OpenSky/Trino access attempted; 98_check_trino_usage exit 0;
  `logs/opensky_queries.log` correctly absent (no pull). PASS.

Findings (none blocking):
1. ADVISORY — narrow glob. `00_bootstrap_manifest.py` line 106 discovers
   T-100 inputs with `T_T100I_SEGMENT_ALL_CARRIER_*.csv` only, while
   ROUND_01 FIX-00 step 1 and FIX-01 step 1 both contemplate "year zips/
   CSVs". For THIS drop the glob captures 100% of the T-100 files on disk
   (verified by set comparison in check 6), so nothing is silently omitted
   today. But a future drop delivered as `.zip`, or a differently named CSV,
   would be invisible to the manifest AND — worse — would make the script
   take the step-2 fetch branch as if `data/raw/t100/` were empty. Suggest
   widening the glob to `T_T100I_SEGMENT_ALL_CARRIER_*.{csv,zip}` (or
   `*.csv` + `*.zip`) when FIX-01 is implemented.
2. ADVISORY — absent-file rows carry an empty `sha256`. Verified by
   exercising the code path: a missing expected input produces
   header_verified=False + note but sha256="" and size_bytes="". That is
   defensible (no file, no hash), but it would violate the FIX-00 VERIFY
   sentence read literally ("every row ... has ... a sha256"). It did not
   arise in this run (38/38 files present). If any future run has a missing
   input, the implementer should write an explicit sentinel (e.g.
   `sha256 = "NA-file-absent"`) rather than an empty cell.
3. NOTE — STATUS.md's FIX-00 entry hand-types "36 t100 + 1 lookup + 1 event
   = 38 rows" and "All rows header_verified True". These are counts
   describing the state of a plumbing deliverable, not coefficients, so
   STANDING_RULES rule 5 is satisfied ("STATUS.md lines describe state").
   I recomputed both from the CSV and both are correct. Flagged only so the
   pattern does not migrate to substantive results.
4. NOTE — STATUS.md offers "data/raw/ untouched (git status clean under
   data/raw/)" as evidence. That evidence is vacuous: `data/raw/**` is
   gitignored (`.gitignore:8`, confirmed with `git check-ignore -v`), so git
   status is clean under data/raw no matter what happens there. The claim
   is nonetheless TRUE on independent evidence (mtime audit, check 7). The
   implementer should not cite git status as a data/raw integrity proof
   again.
5. FORWARD FLAG (not FIX-00, for the director/NEW-06) —
   `data/raw/events/README.md` states that `ban_nations_2022.csv` was
   "drafted by Claude 2026-09-01 from public reporting, FOR HUMAN REVIEW
   before headline use", while PROJECT.md requires event dictionaries to be
   human-curated. FIX-00 correctly only manifests the file. But NEW-06 reads
   this file to define the ban-subject nation list, i.e. an agent-authored
   treatment definition would sit under a headline figure. NEW-06 must
   either carry an explicit "agent-drafted, unreviewed" caveat in the
   `definition` column of `raw_wedge_diffs.csv` and in FINDINGS, or be
   raised as DECISION-PENDING for the human.

Required actions: none. FIX-00 is accepted.

---

## FIX-01 review — 2026-09-01 21:19 UTC

VERDICT: FAIL

Reviewed: `code/01_ingest/01_ingest_t100.py`, `data/interim/t100_raw.parquet`,
`rounds/round-1-t100-panel/ingest_rowcounts.csv`,
`rounds/round-1-t100-panel/ingest_schema_drift.csv`, `logs/01_ingest_t100.log`,
STATUS.md FIX-01 entry.

### Checks run (all recomputed independently; nothing taken from the log)

1. **Row reconciliation, three ways.** `wc -l` minus header on each of the 36
   raw CSVs equals `rows_read` in `ingest_rowcounts.csv` file-by-file (e.g.
   1990: 51160/51160; 2020: 57468/57468; 2025: 112306/112306). Column sums:
   `rows_read` = `rows_written` = 2,662,470; `rows_dropped` = 0 on all 36 rows;
   `blocked` False on all 36. `pyarrow.ParquetFile.metadata.num_rows` =
   **2,662,470** — exact match. Equality of `wc -l` with the parsed record
   count also rules out embedded newlines. CLAIM 1 CONFIRMED.
2. **Header identity.** md5 of the raw header line of all 36 files =
   `0f6f3a7185fbdac6113f4ee4925c068b`, one distinct value; identical to
   `raw_header_md5` in every row of `ingest_schema_drift.csv`. All 18 required
   columns True in all 36 rows; `extra_columns` has exactly 1 distinct value
   (25 extras); zero empty cells in either diagnostic CSV. The raw header ends
   in `CLASS`, so the `CLASS`→`SERVICE_CLASS` alias is load-bearing and works;
   the other five aliases never fire in this drop. CLAIM 2 CONFIRMED.
3. **Calendar completeness.** Distinct (year, month) in the parquet = 432 =
   36x12; min (1990,1), max (2025,12); **zero missing months**. Thinnest cells
   are 2020-05 (2,515 rows) and 2020-04 (2,784) — COVID, not a hole. 2025 is
   complete Jan-Dec (9,328 ... 9,650 rows/month). CLAIM 3 CONFIRMED.
4. **Service class.** F 1,819,635 / L 340,398 / G 292,680 / P 209,036 /
   **Q 721**; zero nulls; `service_class` == `SERVICE_CLASS` on every row;
   `is_passenger` == (`service_class`=='F') on every row, sum 1,819,635.
   CLAIM 4 CONFIRMED numerically (see Finding 2 on its surfacing).
5. **Schema/extra columns.** Parquet has 48 columns = 43 raw + 5 provenance;
   no raw column dropped. Code columns retain string dtype: `AIRCRAFT_TYPE`
   9,392 rows with a leading zero preserved ('030','033','035',...; 289
   distinct); `UNIQUE_CARRIER_ENTITY` 274,869 rows with leading zero
   ('02040','06920 (1)'); `ORIGIN`/`DEST` length 3 on 100% of rows;
   `AIRCRAFT_CONFIG` {'1','2','3','4'} as strings. CLAIM 5 CONFIRMED for
   AIRCRAFT_TYPE/ORIGIN/DEST/AIRCRAFT_CONFIG, **REFUTED for UNIQUE_CARRIER,
   CARRIER, ORIGIN_COUNTRY, DEST_COUNTRY** (Finding 1).
6. **Null preservation / no imputation.** Code contains no `fillna`,
   `interpolate`, `ffill`, `bfill`; the two `dropna()` calls (lines 185, 285)
   are diagnostic-only and touch no written data. Raw-vs-parquet for 1990 and
   2022 on AIR_TIME, RAMP_TO_RAMP, DEPARTURES_SCHEDULED/PERFORMED, SEATS,
   PASSENGERS, DISTANCE: blank counts and zero counts match exactly (1990
   AIR_TIME zeros 27,614 raw = 27,614 parquet; 2022 42,933 = 42,933). Zeros
   were not turned into nulls. CLAIM 6 CONFIRMED for numerics, **REFUTED for
   string codes in the opposite direction** — an observed value was turned
   into a null (Finding 1).
7. **data/raw integrity.** Recomputed sha256 for all 38 files listed in
   `bootstrap_manifest.csv`: 38 checked, **0 mismatches**. CLAIM 7 CONFIRMED.
8. **Rule compliance.** `utils.setup_logger` used (line 207); no `requests`/
   `urllib`/`http`/`trino`/`opensky` token anywhere in the script; no result
   number hand-typed into a CSV; discovery is a sorted glob with a
   deterministic sort key and there is no RNG or timestamp in either output,
   so re-running is deterministic (verified by inspection, not re-run, to
   avoid mutating the artifact under review).
9. **Validator / trino.** `uv run python code/99_validate_outputs.py` ->
   `validate: 3 CSVs scanned, 0 FAIL, 0 WARN`, **exit 0**. `uv run python
   code/98_check_trino_usage.py` -> `0 FAIL`, **exit 0**. Both FIX-01 CSVs are
   inside `rounds/round-1-t100-panel/` and are among the 3 scanned.

### Gate status

- G1 PASS (vacuous — no coef/se/pval columns; zero empty cells in both CSVs).
- G2 PASS (vacuous — no coefficient columns).
- G3 PASS (vacuous — no p-values).
- G4 PASS (vacuous — no SEs).
- G5 PASS (vacuous — no share/rate columns).
- Task-specific "rows written == rows read minus logged drops, drops must be
  zero": **PASS**, recomputed in check 1.
- G6/G7/G8 not applicable to FIX-01. G9 n/a (no FINDINGS yet).

### Findings

1. **BLOCKING — `data/interim/t100_raw.parquet` silently converts the literal
   carrier code `NA` into null.** `code/01_ingest/01_ingest_t100.py:163-165`
   calls `pd.read_csv(..., keep_default_na=True)`, and `'NA'` is in pandas'
   default NA-string set. Effect, recomputed from the raw CSVs with
   `keep_default_na=False, na_filter=False` and compared against the parquet:
   - `UNIQUE_CARRIER`: 8,612 raw rows carry the literal string `NA`
     (1990-2014, `UNIQUE_CARRIER_NAME` == "North American Airlines" on all of
     them, 24,530 departures performed, 1,435 of the rows in headline service
     class F carrying 6,708 departures). In the parquet those rows have
     `UNIQUE_CARRIER` null and `(UNIQUE_CARRIER=='NA').sum() == 0`.
   - `CARRIER`: 7,731 raw `NA` -> 7,731 parquet nulls (100% of that column's
     nulls are manufactured; the raw column has no genuinely blank cell).
   - `ORIGIN_COUNTRY`: 3 raw `NA` (Namibia; WDH->FLL/MCO/SJU, 2015-2016) ->
     null. `DEST_COUNTRY`: 3 raw `NA` (Namibia; TSB 2002, WDH 2008, WDH 2011)
     -> null. Both columns' `*_COUNTRY_NAME` twins still read "Namibia", which
     is how I identified them.
   This is irrecoverable inside the parquet: `UNIQUE_CARRIER` also has 2,407
   genuinely empty raw cells, so the 11,019 parquet nulls now conflate 8,612
   observed-North-American-Airlines with 2,407 truly-missing. Downstream
   consequences: FIX-02 keys the nation mapping on `UNIQUE_CARRIER` and
   enforces G7 on a departures-weighted match rate — 24,530 departures will
   enter as unmatched-null rather than as a matchable US carrier code, and
   `carrier_nation_unmatched.csv` will contain a nameless null row instead of
   "NA / North American Airlines". `ORIGIN`/`DEST` are unaffected (verified:
   0 nulls, all length 3 — note `NAN` = Nadi, Fiji survives because uppercase
   `NAN` is not in pandas' default NA list; that was luck, not design).
   This also directly contradicts Part 0's "missing is not zero" discipline in
   its mirror form, and contradicts the STATUS.md FIX-01 line "String/code
   columns (UNIQUE_CARRIER, ORIGIN, DEST, country codes, SERVICE_CLASS,
   AIRCRAFT_TYPE, AIRCRAFT_CONFIG) kept as strings; no NaNs filled" — NaNs
   were not filled, they were *created*.

2. **ADVISORY (upgrade to a FINDINGS item, not a FAIL) — undocumented
   `SERVICE_CLASS` value `Q` is surfaced only in `logs/01_ingest_t100.log`.**
   721 rows, confined to 1990-1998 (1990: 205, 1991: 103, 1992: 75, 1993: 73,
   1994: 77, 1995: 70, 1996: 74, 1997: 37, 1998: 7). ROUND_01 Part 0 names only
   F/G/L/P, so this is genuine value-level drift in the vendor coding. Neither
   `ingest_rowcounts.csv` nor `ingest_schema_drift.csv` contains any
   service-class column — grep across `rounds/round-1-t100-panel/*.csv` finds
   `SERVICE_CLASS` only as a column-presence header flag. A human reading the
   round folder cannot see that Q exists. The `is_passenger = (SERVICE_CLASS
   == 'F')` treatment is nevertheless **correct**: Q is not scheduled passenger
   service under any BTS reading, it is 0.027% of rows, it ends in 1998, and it
   is 24 years outside the 2022 event window — so no headline number moves.
   The defect is disclosure, not classification. Note also that
   `ingest_schema_drift.csv` as designed can only detect *column* drift (and
   detects none: 36 byte-identical headers); it structurally cannot detect the
   *value* drift that Q represents.

3. **ADVISORY — `is_passenger` is a misleading name for `SERVICE_CLASS == 'F'`.**
   BTS class L is non-scheduled civilian passenger/cargo, i.e. passenger
   charter; calling F-only "is_passenger" will mislead any downstream reader
   into thinking L rows carry no passengers. (ROUND_01 Part 0 makes the same
   slip, describing G/L/P as "combi and freighter".) The flag matches the round
   file's headline-sample definition, so this is naming, not logic.

4. **ADVISORY, forward to FIX-04 — duplicate rows exist in the source and are
   correctly preserved.** 2,270 parquet rows are exact duplicates across all 43
   raw columns (service_class: L 1,001, P 454, G 423, **F 380**, Q 12; by
   decade 1990s 1,137, 2000s 1,109, 2010s 24). Separately, 57,014 rows (2.141%)
   are non-unique on `(year, month, UNIQUE_CARRIER, ORIGIN, DEST,
   AIRCRAFT_TYPE, SERVICE_CLASS)`, and 40,394 remain non-unique after adding
   `AIRCRAFT_CONFIG`, `UNIQUE_CARRIER_ENTITY`, `CARRIER_GROUP`, `DISTANCE`.
   FIX-01 is right not to touch them (zero-drop contract), but FIX-04 must sum
   rather than assume a unique key, and must decide explicitly whether the
   2,270 exact duplicates are double-reported months. Record the decision.

5. **NOTE — 100% of rows are US-touching** (`ORIGIN_COUNTRY=='US'` or
   `DEST_COUNTRY=='US'` on 2,662,470 / 2,662,470 rows), so Part 0's
   "US-touching only" caption rule is satisfied by construction for this file.

6. **NOTE — FIX-00's carried-forward advisory was implemented.** `discover_files`
   globs `*.csv` and `*.zip` and filters dotfiles, so the `.DS_Store` in
   `data/raw/t100/` is correctly excluded and a future zip drop would be read.

### Required actions (blocking; execute in order)

1. In `code/01_ingest/01_ingest_t100.py`, stop pandas from interpreting data
   values as missing in code/string columns. Concretely: in `read_one`, pass
   `na_values` / `keep_default_na` such that the columns in `STR_TARGET_COLS`
   (post-alias) treat only the empty string as missing — e.g. read with
   `keep_default_na=False, na_values={col: [""] for col in <raw names mapping
   into STR_TARGET_COLS>}` plus the pandas default NA list restored for the
   numeric columns only (`DEPARTURES_*`, `SEATS`, `PASSENGERS`, `FREIGHT`,
   `MAIL`, `PAYLOAD`, `DISTANCE`, `RAMP_TO_RAMP`, `AIR_TIME`, the `*_ID`,
   `*_WAC`, `*_GROUP`, `YEAR`, `QUARTER`, `MONTH`). Do not hand-write a
   post-hoc `.replace(np.nan, 'NA')` patch — that cannot separate the 8,612
   real `NA` codes from the 2,407 genuinely empty cells.
2. Re-run the script and re-write `data/interim/t100_raw.parquet`,
   `ingest_rowcounts.csv`, `ingest_schema_drift.csv`. After the re-run these
   must hold and must be asserted in code (not just observed):
   `(UNIQUE_CARRIER == 'NA').sum() == 8612`; `(CARRIER == 'NA').sum() == 7731`;
   `(ORIGIN_COUNTRY == 'NA').sum() == 3`; `(DEST_COUNTRY == 'NA').sum() == 3`;
   `UNIQUE_CARRIER.isna().sum() == 2407`; `CARRIER.isna().sum() == 0`;
   `ORIGIN_COUNTRY.isna().sum() == 38`; `DEST_COUNTRY.isna().sum() == 41`;
   parquet rows still 2,662,470 with `rows_dropped == 0` on all 36 files.
3. Add a value-level drift diagnostic to the round folder — a new CSV
   `ingest_value_drift.csv` written by the same script, one row per
   (year, SERVICE_CLASS) with the row count and the departures-performed sum,
   plus a `documented_in_round_file` boolean that is False for any class
   outside {F, G, L, P}. This is what makes `Q` visible to a human without
   reading a log, and it is the artifact ROUND_01_FINDINGS.md should cite.
4. Add to the same script a logged (not silent) count of code columns whose
   null count changed relative to a `keep_default_na=False` read of the same
   file — i.e. a standing guard so this class of bug cannot recur silently on
   a future data drop.
5. Correct the STATUS.md FIX-01 entry: the sentence "String/code columns
   (UNIQUE_CARRIER, ORIGIN, DEST, country codes, SERVICE_CLASS, AIRCRAFT_TYPE,
   AIRCRAFT_CONFIG) kept as strings; no NaNs filled" was false as written for
   UNIQUE_CARRIER, CARRIER, ORIGIN_COUNTRY and DEST_COUNTRY. Restate it only
   after action 2's assertions pass.
6. Re-run `uv run python code/99_validate_outputs.py` (expect exit 0, now 4
   CSVs scanned) and `uv run python code/98_check_trino_usage.py` (exit 0).
7. Non-blocking but do them while the file is open: rename `is_passenger` to
   `is_sched_pax_f` (or keep the name and add a one-line docstring note that L
   is passenger charter), and carry Findings 2 and 4 into ROUND_01_FINDINGS.md
   with `(ingest_value_drift.csv, row)` traces.

Everything in checks 1-4 and 7-9 above is genuinely correct and should not be
re-done: the row reconciliation, the calendar completeness, the header
identity, the raw-file integrity and both exit-0 checks all stand. The failure
is narrow, real, and upstream of every remaining task in the round.

---

## FIX-01 review (cycle 2) — 2026-09-01 21:36 UTC

Reviewed: `code/01_ingest/01_ingest_t100.py` (rewritten read layer),
`data/interim/t100_raw.parquet` (mtime 21:23), `ingest_rowcounts.csv`,
`ingest_schema_drift.csv`, new `ingest_value_drift.csv`,
`logs/01_ingest_t100.log`, STATUS.md FIX-01 entries. Everything below was
recomputed by the overseer from the raw CSVs / parquet; nothing was taken from
the implementer's summary or the run log.

### Cycle-1 Required actions, one by one

1. **Read-layer fix — DONE, verified at the read layer, not post hoc.**
   `read_one` (lines 191-195) calls `pd.read_csv(..., dtype=dtype_map,
   keep_default_na=False, na_values=build_na_map(...))`. `build_na_map`
   (136-148) assigns `[""]` to every raw column mapping into
   `STR_TARGET_COLS` and pandas' full default list to every other column.
   The hardcoded `DEFAULT_NA_VALUES` (44-48) is **set-identical to
   `pandas.io.parsers.STR_NA_VALUES` under the installed pandas 3.0.5**
   (recomputed: 0 missing, 0 extra), so numeric/ID columns lost nothing.
   No post-hoc patch exists: grep for `fillna|.replace(|interpolate|ffill|
   bfill|.mask(|np.where` finds only the column-*name* `.replace(" ","_")`
   on line 88 and three diagnostic `dropna()` calls (238, 380, 386) that
   touch no written data.
2. **Eight assertions — all eight reproduce on the parquet, and they are
   enforced, not printed.** My independent recomputation:
   `UNIQUE_CARRIER=='NA'` **8612**; `CARRIER=='NA'` **7731**;
   `ORIGIN_COUNTRY=='NA'` **3**; `DEST_COUNTRY=='NA'` **3**;
   `UNIQUE_CARRIER.isna()` **2407**; `CARRIER.isna()` **0**;
   `ORIGIN_COUNTRY.isna()` **38**; `DEST_COUNTRY.isna()` **41** — 8/8 match.
   Semantics re-verified: the 8,612 `NA` carrier rows are 1990-2014, all
   `UNIQUE_CARRIER_NAME == "North American Airlines"`, 24,530 departures
   performed, 1,435 rows in class F; the 3+3 country `NA` rows all carry
   `*_COUNTRY_NAME == "Namibia"` (WDH 2015/2016 origin; TSB 2002, WDH 2008,
   WDH 2011 dest). Enforcement is real: I copied the script into an isolated
   sandbox root (`/tmp/rev01`, `data/raw` symlinked read-only), flipped one
   expected value 8612→8613, and the run exited **1** with
   `assertion UNIQUE_CARRIER == 'NA': actual=8612 expected=8613 [MISMATCH]`
   and an ERROR line. Unmodified, the same sandbox run exited **0** and
   reproduced all three round CSVs byte-identically (`diff` empty) and a
   parquet with sha256 `62613a6c...1fb99b`, **identical to the committed
   `data/interim/t100_raw.parquet`** — i.e. the artifact under review is
   exactly what this code produces, deterministically, with no manual step.
3. **`ingest_value_drift.csv` — DONE and it reconciles.** 153 rows, columns
   `year, service_class, n_rows, departures_performed_sum,
   documented_in_round_file`; zero empty cells; `n_rows` sums to
   **2,662,470**. Outer-merged against my own parquet groupby on
   (year, service_class): 153 both / 0 left_only / 0 right_only, max |diff|
   = 0 on `n_rows` and 0.0 on `departures_performed_sum`.
   `documented_in_round_file` is False on exactly 9 rows, all class **Q**
   (1990-1998; 721 rows; 3,054 departures performed) — Q is now visible to a
   human without opening a log, as required.
4. **Standing NA-string guard — real, logged, and it reconciles.** Lines
   211-226 do a second `usecols`-restricted read under naive
   `keep_default_na=True` and log a WARNING per column whose null count would
   differ. The current run emitted **50** guard warnings across **27** of 36
   files; parsing them, the per-column deltas sum to exactly
   UNIQUE_CARRIER 8612, CARRIER 7731, ORIGIN_COUNTRY 3, DEST_COUNTRY 3 —
   matching the raw-token census I ran independently (see check A). No delta
   is <= 0. The guard fires only where the bug would have bitten.
5. **STATUS.md — DONE.** The cycle-1 sentence now carries an inline
   `[SUPERSEDED — see cycle-2 entry below: this was false as written for
   UNIQUE_CARRIER, CARRIER, ORIGIN_COUNTRY, DEST_COUNTRY ...]` and the
   21:25 entry restates the handling correctly. No result number is
   hand-typed beyond plumbing counts (rule 5 satisfied).
6. **Exit codes — DONE.** `uv run python code/99_validate_outputs.py` →
   `validate: 4 CSVs scanned, 0 FAIL, 0 WARN`, **exit 0**;
   `uv run python code/98_check_trino_usage.py` → `0 FAIL`, **exit 0**. All
   4 scanned CSVs are inside `rounds/round-1-t100-panel/`; `find` for CSVs
   modified since 21:00 outside `data/raw/` returns those 4 and nothing else,
   so no result CSV was written outside the round folder.
7. **Non-blocking items — DONE (naming) / carried forward (FINDINGS).**
   `is_passenger` keeps its name with an explicit 6-line comment (248-253)
   stating it flags `SERVICE_CLASS=='F'` only and that class L is passenger
   charter, excluded by design. The Q and duplicate-row items are advisories
   for ROUND_01_FINDINGS.md, which does not exist yet (round not closed) —
   listed below for the director.

### Additional checks run this cycle

A. **Full-column NA census, raw vs parquet (the new-bug-in-the-opposite-
   direction hunt).** I read all 36 raw CSVs with `na_filter=False` and
   counted, per raw column, blanks and pandas-NA-token strings, then compared
   with the parquet. Results: the ONLY columns containing an NA-like token
   anywhere in 2,662,470 x 43 cells are UNIQUE_CARRIER (8612 `NA`), CARRIER
   (7731), DEST_COUNTRY (3), ORIGIN_COUNTRY (3) — so no other column could
   have gained or lost nulls, in either direction. For **all 43 columns**,
   `parquet nulls == raw blanks` exactly (max deviation 0), and
   **zero columns contain any empty string in the parquet** — the classic
   `keep_default_na=False` blanks→`''` regression did NOT happen anywhere,
   including ORIGIN, DEST, AIRCRAFT_TYPE, AIRCRAFT_CONFIG, SERVICE_CLASS,
   UNIQUE_CARRIER_NAME, CARRIER_NAME (all 0 empty strings; ORIGIN/DEST/
   AIRCRAFT_TYPE/AIRCRAFT_CONFIG/SERVICE_CLASS have 0 nulls and 0 blanks;
   UNIQUE_CARRIER_NAME and CARRIER_NAME have 2407 nulls = 2407 raw blanks).
   `''` and null cannot diverge downstream because `''` does not occur.
B. **Numeric columns kept numeric NA handling.** dtypes:
   AIR_TIME float64, DEPARTURES_PERFORMED float64, DEPARTURES_SCHEDULED
   float64, RAMP_TO_RAMP float64, SEATS float64, PASSENGERS float64,
   DISTANCE float64, FREIGHT/MAIL/PAYLOAD float64, YEAR/QUARTER/MONTH int64,
   the `*_ID`/`*_WAC`/`*_GROUP` int64 (AIRLINE_ID and CARRIER_GROUP_NEW
   float64 because they carry the 2407 genuine blanks). **No numeric column
   came back as object/string**, so no numeric field is holding a literal
   "NA" as text. Zeros preserved and distinct from nulls: AIR_TIME 1,139,078
   zeros / 0 nulls; DEPARTURES_PERFORMED 5,140 / 0; RAMP_TO_RAMP 1,138,695 / 0;
   SEATS 509,535 / 0; PASSENGERS 547,516 / 0; DISTANCE 253 / 0 (the raw files
   contain no blank in any of these six, so 0 nulls is correct, not swallowed).
C. **Cycle-1 invariants re-verified after the rewrite.** Parquet
   `metadata.num_rows` = **2,662,470** = sum(`rows_written`) = sum(`rows_read`)
   in `ingest_rowcounts.csv` (36 rows, `rows_dropped` = 0 and `blocked` False
   on all 36). Distinct (year, month) = **432**, min (1990,1), max (2025,12),
   **zero missing months**. `ingest_schema_drift.csv`: 36 rows, all 18
   required columns True in every row, **one** distinct `raw_header_md5`
   (`0f6f3a7185fbdac6113f4ee4925c068b`, unchanged from cycle 1). Leading zeros
   preserved: AIRCRAFT_TYPE 9,392 rows starting '0' (289 distinct),
   UNIQUE_CARRIER_ENTITY 274,869; ORIGIN/DEST length 3 on 100% of rows;
   AIRCRAFT_CONFIG {'1','2','3','4'} as strings. Service classes F 1,819,635 /
   L 340,398 / G 292,680 / P 209,036 / Q 721, zero nulls; `is_passenger` ==
   (`service_class`=='F') on every row (1,819,635 True). `ORIGIN=='NAN'`
   (Nadi) 1,888 rows and `DEST=='NAN'` 2,852 rows survive as strings.
   **All 38 `data/raw` sha256s recomputed against `bootstrap_manifest.csv`:
   0 mismatches**; no file under `data/raw/` has an mtime after 21:05.

### Gate status

- G1 PASS (vacuous — no coef/se/pval anywhere; the only empty cells in any
  round CSV are `note`/`missing_required_columns` on non-blocked rows of
  `ingest_rowcounts.csv`, which are correctly empty by construction).
- G2 PASS (vacuous — no coefficient columns).
- G3 PASS (vacuous — no p-values).
- G4 PASS (vacuous — no SEs).
- G5 PASS (vacuous — no share/rate/precision columns; `n_rows` and
  `departures_performed_sum` in `ingest_value_drift.csv` are non-negative
  counts, verified).
- Task gate "rows written == rows read minus logged drops, drops must be
  zero": **PASS** (2,662,470 = 2,662,470, 0 drops on 36/36 files).
- ROUND_01 FIX-01 VERIFY items: (1) sum(rows_written) == parquet rows — PASS,
  recomputed; (2) all required columns present every year in
  `ingest_schema_drift.csv` — PASS, 36/36 rows x 18/18 columns True;
  (3) validator exit 0 — PASS.
- G6/G7/G8 not applicable to FIX-01. G9 n/a (no FINDINGS file yet).
- T1-T9: no OpenSky/Trino import or access anywhere in the script;
  `98_check_trino_usage.py` exit 0; `logs/opensky_queries.log` correctly
  absent (no pull attempted in this unattended run). PASS.
- Complexity gate (STANDING_RULES rule 12): plumbing task, no estimator. N/A.

### Findings

1. **Cycle-1 blocking defect is fully repaired.** The fix is at the read
   layer, is drop-deterministic (byte-identical parquet on an independent
   re-run), enforced by in-code assertions that provably exit 1, and it did
   not introduce the mirror bug: no empty strings, no lost numeric NA
   handling, no other column's null count moved by a single cell.
2. **ADVISORY (design, not blocking) — the parquet is still written when an
   assertion fails.** In the sandbox failure run the script logged MISMATCH,
   returned exit 1, *and* wrote the parquet (line 356 executes after the
   assertion block). The orchestrator's non-zero exit is the real gate, so
   nothing silently passes, but a failed run leaves a bad
   `data/interim/t100_raw.parquet` on disk that a later script would happily
   read. Suggest `return 1` before the write (or unlink the stale parquet)
   the next time this file is touched.
3. **ADVISORY — the eight expected counts are drop-specific literals.** They
   correctly pin THIS 1990-2025 drop, but any legitimate new year file will
   trip them, and the tempting response is to bump the constants to whatever
   was observed, which would silently re-license the original bug. The
   durable protection is the NA-string guard (action 4), which is
   drop-invariant. Document that hierarchy in FINDINGS so a future
   implementer updates the literals only after reading the guard warnings.
4. **ADVISORY for ROUND_01_FINDINGS.md — SERVICE_CLASS `Q`.** 721 rows,
   3,054 departures performed, confined to 1990-1998
   (`ingest_value_drift.csv`, the 9 rows with `service_class == Q`), flagged
   `documented_in_round_file = False`. Not scheduled passenger service, 0.027%
   of rows, ends 24 years before the 2022 event window — classification is
   correct, disclosure is the point. Cite the file and rows in FINDINGS.
5. **ADVISORY, forward to FIX-04 — duplicates and cell-key non-uniqueness
   (number corrected).** Recomputed on the new parquet across the 43 raw
   columns: **2,270 rows are involved in an exact duplicate group
   (`duplicated(keep=False)`), of which 1,194 are excess copies
   (`duplicated(keep='first')`)** — split by class L 534, P 236, G 219, F 197,
   Q 8. My cycle-1 report quoted 2,270 without saying which convention; use
   both numbers with the convention named. The NA fix did not change either
   count (recomputed under the old NA→null behaviour: still 1,194). Separately,
   **57,014 rows (2.141%)** are non-unique on
   `(year, month, UNIQUE_CARRIER, ORIGIN, DEST, AIRCRAFT_TYPE, SERVICE_CLASS)`
   — unchanged from cycle 1. FIX-04 must aggregate rather than assume a unique
   cell key, and must record an explicit decision on the exact duplicates.
6. **NOTE — FIX-02 impact of the repair.** The 8,612 recovered
   `UNIQUE_CARRIER == 'NA'` rows (24,530 departures, 1,435 of them class F)
   will now enter FIX-02's departures-weighted match rate as a matchable US
   carrier code rather than as an unmatched null, and
   `carrier_nation_unmatched.csv` should no longer contain a nameless null
   row. FIX-02's G7 numbers are therefore expected to differ from anything
   computed against the cycle-1 parquet; nothing computed on the old parquet
   may be reused.

### Required actions

None. Findings 2-6 are advisories; 4 and 5 must be carried into
`ROUND_01_FINDINGS.md` with `(ingest_value_drift.csv, row)` /
`(data/interim/t100_raw.parquet)` traces, and 3 into the same file's method
notes. No analysis code change is required to close FIX-01.

VERDICT: PASS

---

## FIX-02 review — 2026-09-01 22:04 UTC

Reviewed: `code/02_build/02_carrier_nation.py`, `data/interim/carrier_nation.parquet`,
`rounds/round-1-t100-panel/carrier_nation_matchrate.csv`,
`carrier_nation_unmatched.csv`, `carrier_nation_flips.csv`,
`logs/02_carrier_nation.log`, ROUND_01 Part 0 + FIX-02 + G7.
Everything below was recomputed by me from `data/interim/t100_raw.parquet` and
`data/raw/lookups/airlines.csv`. Nothing was taken from the implementer's summary.

### Every implementer claim, checked

| Claim | Recomputed | Status |
|---|---|---|
| overall dep-weighted 0.9637 | 0.963742 | CONFIRMED |
| foreign dep-weighted 0.9130 | 0.913004 | CONFIRMED |
| composition: us_by_construction .583 / iata .3647 / name_exact .0148 / icao .0010 / unmatched .0363 | identical | CONFIRMED (but mislabelled, Finding 6) |
| foreign: iata .8751 / name_exact .0355 / icao .0024 / unmatched .0870 | identical | CONFIRMED |
| 222 unmatched codes, 1,716,907 departures | 222 / 1,716,907; all CARRIER_GROUP==0 | CONFIRMED |
| 0 flips | 0 rows | CONFIRMED but vacuous (Finding 2) |
| 2,407 null-carrier rows excluded | 2,407 rows / 15,483 dep | CONFIRMED |
| no fuzzy matching; crosswalk built from T-100 | verified line by line | CONFIRMED |

I also re-ran the script: exit 0, all three CSVs byte-identical, parquet sha256
`b8e0b09826c468a0f78bca229522d9f166b1ab61d30734a658bd67a18fd72e89` unchanged —
deterministic. All 38 `data/raw` sha256s still match `bootstrap_manifest.csv`;
nothing under `data/raw/` modified. `99_validate_outputs.py` → 7 CSVs, 0 FAIL,
1 WARN, exit 0. `98_check_trino_usage.py` → 0 FAIL, exit 0. No network/Trino
token anywhere in the script; `utils.setup_logger` and `utils.log_merge` both used.

### Priority 1 — is the 0.9130 honest? Yes. The gate it clears is the wrong gate.

I could not find a drawing of the *coverage* rate that flatters. All the
alternatives I tested move it the same way or up:

- headline service class F only (the round file's actual headline sample):
  foreign **0.9406**, overall 0.9753 — the shipped all-classes draw is the
  CONSERVATIVE one.
- F+L: foreign 0.9286. G+P (freight) only: foreign 0.7699.
- null-carrier rows put back into the denominator: overall 0.96343, foreign
  0.91258 — immaterial (15,483 dep, 0.03%).
- US/foreign split: `CARRIER_GROUP` is perfectly homogeneous — **0** codes cross
  the US/foreign boundary across years, **0** (code,year) cells disagree within a
  year, and `CARRIER_GROUP_NEW` disagrees with `CARRIER_GROUP` on the US/foreign
  boundary in **0** of 2.66M rows. The `ambiguous_group_inconsistent` branch never
  fires. Code-level mode == row-level value everywhere.
- strict resolution (refuse a match if ANY candidate country string is
  unresolvable, not just if two resolve differently): foreign **0.913004**,
  bit-identical. No match anywhere rests on partial resolution.
- dropping the ISO-3166 supplement: foreign **0.9137** — the supplement LOWERS the
  rate (it adds countries that create ambiguity). Not a rate-raising device.
- the obvious rate-raising lever was left on the table: an OpenFlights
  `active=='Y'` tie-break would give foreign **0.9368** / overall 0.9737 and was
  not used.

So: **G7 as literally written (departures-weighted match rate, pooled) is met,
0.9130 ≥ 0.90, honestly, on the conservative draw.** I say that plainly.

### Priority 2 — threshold-chasing in the tables: none found in the tables.

All 18 `COUNTRY_NAME_ALIASES` entries are genuine country-name spelling/synonym
normalisations and every one resolves to the right ISO2 (Russian Federation→RU,
Republic of Korea→KR, Myanmar→Burma→MM, Congo (Brazzaville)→CG, Macao→MO,
Canadian Territories→CA, …). **No entry assigns carrier identity; there is no
hardcoded carrier→nation pair anywhere in the script** (I grepped; `US_GROUP_CODES`
is a BTS group-code set, and the AA/DL/CA/BA/ABX names appear only in a comment).
The table is load-bearing for the gate (removing it: foreign 0.8766; removing
name_exact: 0.8775) but it is not *selective*: of the 276 OpenFlights `country`
strings, 62 remain unresolved and **every one of the 62 is a corrupted field-shift
value** (`AVIANCA`, `ALASKA`, `Russia]]`, ` S.A.`, `WATCHDOG`, …), not a country
spelling that was withheld. The alias table is exhaustive over the real country
names. The script is uncommitted (`git log -- code/02_build/02_carrier_nation.py`
empty), so I could not read its edit history; the counterfactuals above are my
substitute and they exonerate the tables.

### BLOCKING — the mapping is measured for coverage and never for correctness, and it is materially wrong

G7 is titled **"mapping precision"**. What is implemented and reported is a
*coverage* rate: the share of departures on codes that received *some* nation. No
accuracy check of any kind was run, no audit sample was produced, and the round
folder contains nothing a human could use to judge whether a mapped nation is the
right one. It is not right, often, and it is wrong in the places this project
cares about most.

Auditable test I ran (reproducible, no judgement calls): for each matched foreign
code, the departures-weighted share of its own segments that touch its mapped home
country. Every T-100 row is US-touching, so a genuine national carrier's home
country appears on its routes unless it flies only fifth-freedom sectors.

- **112 of 312 matched foreign codes have a home share of exactly 0**, carrying
  **899,410 departures = 4.99% of all matched foreign departures**. Another 6 codes
  sit in (0, 0.01), carrying 385,019 (2.14%), including `TA` at 0.0038.
- I then read the 45 largest matched foreign codes pair by pair against
  `airlines.csv`. Confirmed misclassifications among them:
  - `KV` "Sky Regional Airlines Inc." (Canada) → **RU**, 222,939 departures.
    OpenFlights row: `Kavminvodyavia,,KV,MVD,AIR MINVODY,Russia`. Pure IATA collision.
  - `RV` "Air Canada rouge LP" (Canada) → **IR**, 191,266 departures.
    OpenFlights row: `Caspian Airlines,,RV,CPN,CASPIAN,Iran`.
  - `TA` "Taca International Airlines" (El Salvador) → **CR**, 347,572 departures.
    OpenFlights row: `Grupo TACA,TACA,TA,TAT,TACA-COSTARICA,Costa Rica` (vendor's own error, uncaught).
  Beyond the top 45, the same test names `2T (1)` Canada 3000 → HT (50,096),
  `7Z` → CV (35,840), `6R` AeroUnion (MX) → RU (30,764), `VH (1)` Aeropostal (VE)
  → FJ (28,302), `K8` Dutch Caribbean → ZM (25,319), `GU (1)` Aviateca (GT) → IT
  (24,313), `FQ` Air Aruba → BE (21,332), `VX (1)` Aces (CO) → US (19,410),
  `TR (1)` Transbrasil → SG (14,679), `WW` WOW Air (IS) → GB (13,036),
  `DI` Norwegian Air UK → DE (12,426), `N3` Vuela El Salvador → RU (12,092),
  `B0` La Compagnie (FR) → US (10,871), `ZG` ZIPAIR Tokyo (JP) → **MO** (7,858),
  `D8` Norwegian Air Intl → DJ (8,248), `N0`/`Z0` Norse Atlantic → AR (12,902),
  `WO` SWOOP (CA) → US (4,887). Of the 30 largest zero-home-share codes, **29 are
  unambiguously wrong** (the exception is `9W` Jet Airways → IN, correct, US–BRU
  fifth freedom).
- The ICAO tier is the worst: of its 10 largest matches, `VJT` VistaJet (MT)→CA,
  `SEQ` Sky Service FBO (CA)→TH, `ACQ` Aeronautica de Cancun (MX)→PE, `TRA`
  Aeromexico Travel→NL (OpenFlights `TRA` = Transavia Holland), `SMQ` Serv.
  Aerolineas Mexicanas→**TJ** (Samar Air, Tajikistan), `RTQ` Aerotour Dominicano→FR
  are all wrong. Tier is small (47,345 dep) but precision there is roughly 0.3–0.4.
  The `name_exact` tier is by contrast good (~0.9+: Air Georgian→CA, Aerolitoral→MX,
  Nippon Cargo→JP, Nolinor→CA, Taca Peru→PE all correct).

**Consequence for the gate.** An upper bound on the departures-weighted *correct*-
nation rate for foreign carriers is
(18,018,666 − 899,410 − 385,019) / 19,735,573 = **0.8479 < 0.90**. So the two
defensible readings of G7 disagree: coverage 0.9130 PASS, precision ≤0.8479 FAIL.
The implementer shipped the passing one and never computed the other. STANDING_RULES
rule 4 is explicit that when two readings disagree the deliverable is the flag plus
diagnostics, not the reading that works.

**Consequence for the science.** The errors land on the treated nations of the
2022 design:
- mapped nation **RU** = 339,471 departures, of which only Aeroflot (`SU`, 57,710)
  and Volga-Dnepr (`VIQ`, 3,441) are actually Russian → **precision 0.180**. 66% of
  "Russia" is a Canadian regional (`KV`), plus a Mexican freight carrier (`6R`) and
  a Salvadoran LCC (`N3`).
- mapped nation **IR** = 193,696 departures, **precision 0.000** — it is Air Canada
  rouge and Lynx Air. There is no Iranian flying in this panel at all.
- In NEW-06's own window (2019–2024, class F, foreign carriers): 2,925,942 matched
  departures of which **262,020 (8.96%)** are on suspect codes — led by `RV`→IR
  (75,993), `TA`→CR (58,763), `KV`→RU (56,213), `ZG` ZIPAIR→MO (5,450).

### BLOCKING — the reissue-suffix strip erases BTS's own disambiguation

`strip_reissue_suffix` maps `"JD (1)"` and `"JD"` to the same base before lookup.
BTS uses that suffix precisely because the code was reissued to a different entity.
Of the 24 suffix families whose members are both foreign, **11 assign one nation to
two demonstrably different carriers**:
`JD` Beijing Capital Airlines (CN) and `JD (1)` Japan Air System (JP) → both **JP**;
`TR` Scoot (SG) and `TR (1)` Transbrasil (BR) → both **SG**;
`LC` Varig Logistica (BR) and `LC (1)` Lineas Aereas del Caribe (CO) → both **BR**;
`VH` Viva Colombia (CO) and `VH (1)` Aeropostal (VE) → both **FJ**;
`2T` BermudAir (BM) and `2T (1)` Canada 3000 (CA) → both **HT**;
`4M` LAN Argentina and `4M (1)` LAN Dominicana → both **AR**.
Part 0's "Name-matching trap" caution ("codes get reassigned … match on
(UNIQUE_CARRIER, year) where the lookup has dates; otherwise flag") is not merely
unmet — the code actively discards the only reissue information T-100 supplies, and
nothing flags it.

### Priority 3 — the flips CSV is structurally vacuous, and I want it replaced

`out.nation_iso2` is merged from a per-code static table, so `len(distinct_nations)
> 1` is **logically impossible**: that branch can never fire, whatever the data. The
only live trigger is `has_inconsistent_cell`, and I verified independently that
CARRIER_GROUP has 0 within-year US/foreign disagreements across all 8,842
(code, year) cells, so it too is empty by fact. The empty file satisfies FIX-02's
VERIFY sentence ("either empty or every row has a `resolution` note") by its letter
and satisfies Part 0's intent ("Log every carrier code whose mapped nation differs
across years — that is a mapping bug") not at all.

The honest diagnostic exists and is cheap, and I ran it so the implementer knows
what it returns: **80 of 770 codes (13.8% of all departures) have a `CARRIER_NAME`
that changes across years** while the mapped nation is held fixed — the reissue/
rebrand signature (`QK` Air Nova 1991-2000 → Air Canada Regional 2001-2010 → Jazz
2011-2025, 1,134,565 dep; `MQ` Simmons → American Eagle → Envoy; `EV` Atlantic
Southeast → ExpressJet). Resolving each historical name era separately against
OpenFlights, **0 of the 80 cross a national border**, which is a genuinely reassuring
result — and it is exactly the reassurance the round folder currently cannot offer,
because the file that was supposed to carry it is empty. The suffix-family table
above is the second half of the same diagnostic, and that one is not reassuring.

### Priority 4 — us_by_construction is clean

236 codes, 27,616,976 departures (58.32% of all departures — see Finding 6 on the
label). I read all 236 `UNIQUE_CARRIER_NAME`s: every one is a US-flag operator
(including US-territory carriers Continental Micronesia, Samoa Aviation, Freedom
Air (Guam), Air St. Thomas). No foreign carrier is swept in. The US path is
separable in the CSV (`share_dep_us_by_construction`, category `us`) and documented
in the script header, and `CARRIER_GROUP ∈ {1,2,3,7}` is corroborated by
`CARRIER_GROUP_NEW` on 100% of rows. The overall 0.9637 IS mechanically dominated
by this trivial path — `us` category rate is exactly 1.0 — which is why the foreign
figure is the only informative one, and why its precision problem is the whole
story. `NA`/North American Airlines (24,530 dep) is correctly present as US, so the
FIX-01 cycle-2 repair carried through as predicted.

### Priority 5 — the unmatched CSV: correct refusals, but not actionable, and concentrated where it hurts

222 rows, sorted by `total_departures` descending (verified monotone), 1,716,907
departures, reconciling exactly with the parquet. Spot-checks against
`data/raw/lookups/airlines.csv`, all legitimate:
- `AV` Avianca (254,450 dep) — single OpenFlights row, `country` field is the
  corrupt string `AVIANCA`. Vendor corruption, as stated. Correct refusal.
- `OZ` Asiana (204,972) — `OZ` = Asiana (Republic of Korea) **and** Ozark Air Lines
  (United States). Correct ambiguity refusal.
- `CP (1)` Canadian Airlines International (183,233) — `CP` = Canadian Airlines
  (Canada) **and** Compass Airlines (US). Correct refusal. Note BTS's own `(1)`
  suffix would have resolved it, and the code throws that away.
- `VB` VivaAerobus (89,661) — `VB` = Birmingham European (UK) and Pacific Express
  (US); **neither is VivaAerobus**. Refusal here actively prevented a wrong answer.
- `CV` Cargolux (79,517), `L7` LATAM Colombia, `M7` MasAir, `AD` Azul, `JX` STARLUX
  (absent from the 2014-vintage OpenFlights entirely) — same pattern.
The refusal rule is the right rule and it is not a matching bug.

But the residual is **not** diffuse across harmless small carriers. Foreign-carrier
match rate by foreign endpoint country in NEW-06's window (2019–2024, class F):
ICN **0.6753**, TPE 0.9562, and every other anchor airport ≥ 0.9996 (FRA 0.99998,
CDG 0.99993, MAD 0.99957, LHR/IST/NRT/HND/PEK/PVG/CAN/HKG/DEL/BOM/BLR/HYD/DXB/DOH/
AUH/TLV/AMS all 1.0000). Korea alone is the residual: `OZ` Asiana (22,793 dep in
window) and `LJ` Jin Air (3,648) are unmatched, so corridor 1's Korean series will
be Korean Air + Jeju + Air Busan and will silently omit the second flag carrier —
32% of ICN's foreign departures. Nothing in the round folder tells a human this.
`JX` STARLUX (2,065) does the same, smaller, at TPE.

The pooled foreign rate also conceals strong year variation that the round file
asked to see: **17 of 36 years have a foreign rate below 0.90**, including 2019
(0.8933), 2020 (0.8967), 2021 (0.8742), 2023 (0.8968), 2024 (0.8774), 2025 (0.8815),
with 2022 at 0.9016. `carrier_nation_matchrate.csv` has `by_year` rows, but only
pooled across US and foreign — the one cut (carrier group × year) that would show
this is missing, and the round file's deliverable line asks for "by carrier group
(US vs foreign), by year".

### Gate status

- **G1** — no empty coef/se/pval; N/A (no inference columns). Zero empty cells in
  `carrier_nation_unmatched.csv`; in `carrier_nation_matchrate.csv` the only blanks
  are `subcategory` on the 4 non-year rows and the `share_dep_*`/`match_rate_unweighted`
  cells on the `null_carrier_code` row, all empty by construction. PASS (vacuous).
- **G2** — no |coef|>100 on log/share outcomes. N/A. PASS (vacuous).
- **G3** — no p=0.0, no repeated p. N/A, no p-values. PASS (vacuous).
- **G4** — SE scale. N/A. PASS (vacuous).
- **G5** — shares/rates in [0,1]: all 6 `share_dep_*` columns and both
  `match_rate_*` columns within [0,1] on all 40 rows, 0 violations; `share_dep_*`
  sums to exactly 1.0 on all 39 real rows (max deviation 1.1e-16);
  `departures_matched/departures_total == match_rate_weighted` to 1.1e-16 on every
  row; `n_codes_matched/n_codes_total == match_rate_unweighted` exactly; `foreign`
  + `us` departures = `overall` = sum over the 36 `by_year` rows = 47,352,549.
  Family counts are complete (40 rows, every year 1990–2025 present). **PASS.**
- **G7 — mapping precision.** Coverage reading: overall 0.963742 ≥ 0.95, foreign
  0.913004 ≥ 0.90 → PASS. Precision reading (the gate's own name): foreign correct-
  nation rate ≤ **0.8479** < 0.90 → **FAIL**. Two defensible readings disagree by
  more than the margin; only the passing one was computed and reported.
  **Status: DEGENERATE-GATE / BLOCKED-NEEDS-HUMAN.**
- G6, G8 — not in scope (FIX-03, FIX-05). G9 — no FINDINGS file yet.
- **T1–T9** — no OpenSky/Trino import or access; `98_check_trino_usage.py` exit 0;
  `logs/opensky_queries.log` correctly absent. PASS.
- **Rule 12 (method discipline)** — deterministic lookup, no estimator. N/A.
- **FIX-02 VERIFY item 1** — matchrate `overall` ≥ 0.95 and `foreign` ≥ 0.90:
  met on the coverage reading. **Item 2** — flips empty or noted: met by letter,
  not by intent (Finding 2).

### Findings

**BLOCKING**

1. **No precision measurement, and the mapping is materially wrong on the
   project's treated nations.** (`data/interim/carrier_nation.parquet`, codes `KV`,
   `RV`, `TA`, `6R`, `N3`, `ZG`, `VH`, `2T`, `GU`, and 100+ others; effect visible in
   `carrier_nation_matchrate.csv` row `foreign` only as a coverage number.) 4.99% of
   matched foreign departures sit on codes whose mapped home country never appears on
   any of their routes; 29 of the 30 largest such codes are confirmed wrong by hand
   against `data/raw/lookups/airlines.csv`. Mapped nation RU has precision 0.180,
   mapped nation IR has precision 0.000. Upper bound on the foreign correct-nation
   rate is 0.8479, below G7's 0.90.
2. **`carrier_nation_flips.csv` is empty by construction, not by evidence.** The
   `len(distinct_nations) > 1` branch cannot fire under a static per-code map; the
   other branch is empirically zero (0 of 8,842 cells). Part 0's cross-year
   reissue check therefore has no diagnostic content as implemented. The real
   reissue exposure is elsewhere and is nonzero: 11 suffix families assign one
   nation to two different carriers (`JD`, `TR`, `LC`, `VH`, `2T`, `4M`, …).
3. **`strip_reissue_suffix` destroys the only dated disambiguation in the data.**
   BTS's ` (1)`/` (2)` suffixes exist because the code was reissued; stripping them
   before lookup guarantees the reissued pair receives one nation.
4. **The commissioned carrier-group × year breakdown is missing**, and its absence
   hides that the foreign rate is below 0.90 in 17 of 36 years, including 5 of the
   last 7 and every year of the NEW-06 window except 2022 (0.9016).
5. **Anchor-corridor concentration is invisible.** ICN's foreign match rate in the
   NEW-06 window is 0.6753 (Asiana + Jin Air unmatched) against ≥0.9996 at every
   other anchor airport. `carrier_nation_unmatched.csv` carries no nation, corridor,
   or window column, so a human reviewing it cannot see this.

**ADVISORY**

6. **Mislabelled composition figure.** `logs/02_carrier_nation.log` line
   "Of matched departures overall, share resting on us_by_construction alone =
   0.5832" is the share of **all** departures, not of matched (matched share =
   0.5832/0.9637 = 0.6052). The implementer's summary repeats the wrong label, as do
   the other composition percentages. The CSV column
   `share_dep_us_by_construction` is correctly defined; only the prose is wrong.
7. **Hand-typed number inside a generated CSV.** `02_carrier_nation.py:420` builds
   the `note` cell with the literal string `"2,407-row category: …"` while every
   other number in the same f-string is interpolated. It is correct today; on any
   new drop it becomes a silently stale number in a deliverable. Interpolate
   `n_null_rows`.
8. **Validator WARN on the empty flips CSV is correct and should not be suppressed.**
   `99_validate_outputs.py` → 7 CSVs, 0 FAIL, 1 WARN, exit 0. The WARN is the
   validator doing its job; the fix is a file with content (Finding 2), never an
   exemption.
9. **No STATUS.md FIX-02 entry exists yet**; the script is uncommitted, so no git
   history was available to audit for tuning. Commit before the next cycle so the
   history is reviewable.
10. **Do not "fix" this by hand-mapping carriers.** Asiana, Avianca, Canadian
    Airlines and the rest must not acquire a nation through a typed carrier→nation
    pair; that would be the exact defect I would fail next cycle.

### Required actions (blocking; execute in order)

1. **Set the DEGENERATE-GATE flag and mark FIX-02 BLOCKED-NEEDS-HUMAN in STATUS.md**
   with a neutral statement of the disagreement: coverage 0.9130 clears G7,
   precision-adjusted ≤0.8479 does not, and G7's own title says precision. Do not
   choose between them.
2. **Add a precision audit as a round-folder deliverable**, e.g.
   `carrier_nation_precision_audit.csv`: one row per matched code with
   `unique_carrier, carrier_name, nation_iso2, match_method, departures,
   home_country_dep_share, top_endpoint_country, n_openflights_candidates,
   candidate_names, flag_home_share_zero`. Report the departures-weighted share of
   matched foreign departures with `home_country_dep_share == 0` and `< 0.01` as
   explicit gate diagnostics next to the coverage rate. This is measurement, not
   correction — it changes no mapping.
3. **Add an audit sample for human review**: the 40 largest matched foreign codes
   plus a random 40, each with the T-100 name and the OpenFlights row(s) it matched,
   so a human can score precision by tier (`iata`, `icao`, `name_exact`). Report
   precision per tier with the implausible pairs listed.
4. **Stop collapsing reissue suffixes into a single lookup key**, or, if the base
   code must still be used, refuse the match whenever two suffixed siblings of the
   same base would receive the same nation and their `UNIQUE_CARRIER_NAME`s differ.
   Write those cases to `carrier_nation_flips.csv` with a `resolution` note. That
   file must stop being empty for a structural reason.
5. **Replace the vacuous flips check with the diagnostic Part 0 actually wants**:
   codes whose `CARRIER_NAME` changes materially across years under a fixed mapped
   nation, with the year ranges of each name era. It returns 80 codes / 13.8% of
   departures and 0 cross-border cases — a real, reportable, reassuring result that
   the round folder currently cannot show.
6. **Add `foreign × year` and `foreign × service_class` rows to
   `carrier_nation_matchrate.csv`** (the round file's "by carrier group … by year"),
   so the 17 sub-0.90 years are on the record rather than in my report.
7. **Add nation/corridor exposure columns to `carrier_nation_unmatched.csv`** — the
   modal foreign endpoint country and departures inside 2019–2024 class F — and add
   a small `carrier_nation_corridor_coverage.csv` giving matched-departure share by
   NEW-06 anchor airport and window, so ICN's 0.6753 is a visible artifact that
   FIX-04 and NEW-06 must reckon with.
8. **Any change that raises the match rate** (OpenFlights `active=='Y'` tie-break,
   corporate-suffix name normalisation that would recover Asiana, a second lookup
   source) must be commissioned in writing by the director in ROUND_01.md with the
   before/after rate reported both ways. The econometrician must not pick one in
   this cycle — that is the rate-chasing STANDING_RULES rule 4 and rule 10 forbid.
9. Fix advisories 6 and 7 while the file is open; re-run and confirm the outputs are
   still byte-identical apart from the intended additions; re-run
   `99_validate_outputs.py` and `98_check_trino_usage.py` (both must exit 0).

### For the director to carry into ROUND_01_FINDINGS.md

- G7 status is split and must be reported as split, with both numbers traced
  (`carrier_nation_matchrate.csv`, row `foreign` for 0.913004; the new precision
  CSV for the precision figure). Never report 0.9130 alone.
- The RU (0.180) and IR (0.000) precision figures, with named carriers — this is
  the single most damaging number in the round and it must not be discovered by a
  referee.
- ICN 0.6753 vs ≥0.9996 at every other anchor airport, and the fact that Asiana is
  absent from corridor 1 as delivered.
- The 80 name-churn codes with 0 cross-border reissues (once the diagnostic exists)
  — a real null worth reporting under rule 6.
- That `us_by_construction` carries 58.32% of all departures and is trivially
  "matched", so the overall 0.9637 is not evidence about the lookup; only the
  foreign figure is.
- The 62 corrupted `country` values in the OpenFlights extract (`AVIANCA`,
  `Russia]]`, ` S.A.`, …) as a known limitation of `data/raw/lookups/airlines.csv`,
  and a DECISION-PENDING note asking the human whether a better carrier-nationality
  source (ICAO Doc 8585, OAG, or a BTS carrier decode with country) should be
  placed in `data/raw/lookups/` before FIX-04.

VERDICT: FAIL

---

## FIX-02 review (cycle 2) — 2026-09-01 22:27 UTC

Reviewed: `code/02_build/02_carrier_nation.py` (902 lines, read in full),
`data/interim/carrier_nation.parquet`, and all six FIX-02 CSVs in
`rounds/round-1-t100-panel/`; `logs/02_carrier_nation.log`; STATUS.md 22:10 entry.
Everything below was recomputed by me from `data/interim/t100_raw.parquet` and
`data/raw/lookups/airlines.csv` with my own independent re-implementation of the
match chain (crosswalk, alias table, ISO supplement, IATA→ICAO→name priority,
suffix-collision refusal). Nothing was taken from the implementer's summary or
the run log.

### A. Every cycle-2 claim, recomputed

| Implementer claim | My independent recomputation | Status |
|---|---|---|
| refusals: 22 codes, 11 families, 215,007 dep | 22 / 11 / 215,007 | CONFIRMED |
| coverage overall 0.9592 / foreign 0.9021 | 0.959201478 / 0.902110063 | CONFIRMED |
| precision-adjusted overall 0.9429 / foreign 0.8631 | 0.942933315 / 0.863077044 | CONFIRMED |
| home0 share 0.0433 | 0.0432685775 (770,339 dep / 100 codes) | CONFIRMED |
| home<0.01 share 0.0644 | 0.0644401805 (1,147,271 dep / 105 codes) | CONFIRMED |
| tier iata n=226 0.0437 | 226 codes, 17,054,778 dep, 0.043693 | CONFIRMED |
| tier icao n=35 0.4938 | 35 codes, 47,345 dep, 0.493759 | CONFIRMED |
| tier name_exact n=29 0.0025 | 29 codes, 701,536 dep, 0.002544 | CONFIRMED |
| name-churn 173 rows / 80 codes / 13.83% | 173 / 80 / 0.138289 | CONFIRMED |
| 2 cross-border flags (AI GB/IN; K8 ZM) | AI ['GB','IN']; K8 ['AN','HT'] mapped ZM | CONFIRMED |
| 26 spurious flags if us_by_construction tested | exactly 26 of 45 US churn codes | CONFIRMED |
| flips 195 rows (173 + 22) | 195; resolution non-empty on 195/195 | CONFIRMED |
| corridor ICN 0.7634, TPE 0.9604, six others 1.0000 | 0.763413 / 0.960432 / 1.000000 | CONFIRMED |
| foreign×year: 18 of 36 below 0.90; 2019 0.888 … 2025 0.880 | 18; 0.888165, 0.894216, 0.870160, 0.899010, 0.895385, 0.875770, 0.879634 | CONFIRMED |
| all CSVs + parquet byte-identical on re-run | see check A5 | CONFIRMED |

A1. **Priority 1 — did the headline move for an honest reason? YES, exactly.**
Denominators are unchanged from cycle 1: foreign `departures_total` 19,735,573
and overall 47,352,549, identical to the cycle-1 values I recorded. Foreign
`departures_matched` fell 18,018,666 → 17,803,659, a drop of **exactly 215,007**,
which equals `share_dep_refused_suffix_collision × departures_total` on both the
`overall` and `foreign` rows to 1e-9. Nothing else touched the numerator or the
denominator. 18,018,666/19,735,573 = 0.913004 (cycle 1);
17,803,659/19,735,573 = 0.902110 (now). Full reconciliation, no residual.

A2. **The precision numbers went DOWN, not up — no flattering.** Pre-refusal I
recompute the home0 share on the 312-code matched-foreign population as
899,410/18,018,666 = **0.049915** (matching my cycle-1 0.0499). Of the 215,007
refused departures, **129,071 (60.0%, 12 of the 22 codes)** were home0. That is
the whole of the decline: (899,410 − 129,071)/(18,018,666 − 215,007) = 0.043269.
The implementer's stated explanation is correct and is not a population change
that flatters. Crucially, the precision-*adjusted rate* also fell: the cycle-1
equivalent was (18,018,666 − 899,410)/19,735,573 = 0.86741; it is now 0.86308.
Both readings of G7 moved down. A rate-chasing edit would have moved at least one up.

A3. **Priority 2 — action 8, no rate-chasing. Clean, verified three ways.**
(i) Full read of the script: no `active=='Y'` tie-break (the string `active`
appears nowhere), no fuzzy/approximate matcher (`difflib`/`rapidfuzz`/`jaro`/
`levenshtein`/`soundex` absent; `normalize_name` is case + `[.,]` + whitespace
only), no corporate-suffix normalisation, no hardcoded carrier→nation pair, and
exactly two data reads in the whole file (`read_parquet` on t100_raw,
`read_csv` on airlines.csv) — no second lookup source. `COUNTRY_NAME_ALIASES`
and `ISO_SUPPLEMENT` are unchanged from cycle 1 (18 and 11 entries, all country
names, none carrier-identifying).
(ii) Structural: the only mapping-changing rule added is the suffix-collision
refusal, which by construction can only set `match_method` to
`refused_suffix_collision` and `nation_iso2` to NA — it cannot create a match.
(iii) Numeric: matched departures fell by exactly the refused amount and by
nothing else (A1). **Action 8 satisfied.**
Caveat on method: I could not diff against cycle-1 code because
`code/02_build/` is *still untracked* (`git status` → `?? code/02_build/`),
which was cycle-1 advisory 9. The three checks above are my substitute and they
are conclusive for this cycle, but the file must be committed.

A4. **The refusal rule is conservative, and costs some correct mappings.** Of the
22 refused codes, 10 (85,936 dep) had a positive home-country share before
refusal, i.e. were probably mapped correctly: `SN (1)` Sabena (BE, hs 0.968) and
`SN` Brussels Airlines (BE, hs 0.998) — *same, correct nation*, refused only
because the names differ; `MT` Thomas Cook UK (GB, 0.984); `4M` LAN Argentina
(AR, 0.907); `JD (1)` Japan Air System (JP, 1.000); `5G` Skyservice (CA, 1.000);
`MT (1)` (GB, 1.000). The other 12 (129,071 dep) were home0. This is the right
direction of error under "refuse rather than guess", but the human should know
that a date-aware lookup recovers ≈86k departures with no guessing.

A5. **Determinism and provenance.** I rebuilt an isolated root (`/tmp/rev02`,
`data/raw` symlinked, its own `rounds/` and `logs/`) and ran the script there:
all six CSVs **byte-identical** (`cmp`) to the committed round-folder files, and
`carrier_nation.parquet` sha256 `88bc0fdf…85528b` identical to the committed
artifact. Exit code **1**, correct for a DEGENERATE-GATE/BLOCKED task. The only
stochastic element (`random40_seed42`) is seeded. All 38 `data/raw` sha256s still
match `bootstrap_manifest.csv` (0 mismatches); no file under `data/raw/` has an
mtime after 21:06.

A6. **Checkers.** `python code/99_validate_outputs.py` → `validate: 10 CSVs
scanned, 0 FAIL, 0 WARN`, **exit 0** (the cycle-1 WARN on the empty flips file is
gone because the file now has content — the correct way to clear it). `python
code/98_check_trino_usage.py` → `0 FAIL`, **exit 0**. All ten scanned CSVs are
inside `rounds/round-1-t100-panel/`; the only artifact written outside is
`data/interim/carrier_nation.parquet`, which the round file names as a FIX-02
deliverable path. No network/Trino/OpenSky token anywhere in the script;
`logs/opensky_queries.log` correctly absent (T8 respected).

### B. Priority 3 — is the cross-border scoping defensible or convenient? DEFENSIBLE, but the test is near-powerless and the scoping is under-disclosed.

I ran the test myself on all three tiers. Lookup-matched codes: 24 churn codes,
**2** flagged. `us_by_construction`: 45 churn codes, **26** flagged — I reproduce
the implementer's count exactly. Unmatched/refused: 11 codes, 4 flagged.

The exclusion is **correct on the merits**, and I say so independently. For a
`us_by_construction` code the nation is read off BTS's own `CARRIER_GROUP` field,
which is ground truth, not inferred from route geography; a change in the modal
foreign endpoint therefore carries zero information about the nation. The 26
flags are exactly what that reasoning predicts and nothing else: `MQ` American
Eagle BS→CA→MX, `US` US Airways CA→MX, `ABX` Air CA→MX, `TW` TWA DO→FR, `MG`,
`C5`, `X9`, `TCQ` all CA↔MX. There is no reading under which "American Eagle's
modal foreign destination moved from the Bahamas to Canada" is evidence that
`nation = US` is wrong. Nothing is suppressed either: all 45 US churn codes are
still written to `carrier_nation_flips.csv` as `name_churn_stable_nation` with a
resolution note saying explicitly they were not tested and why. This is **not**
the rule-10 pathology.

Two real defects around it:
1. **The test has almost no power for the thing it is named after.** Of its 2
   flags, both are route-mix noise, not nationality change: `AI` is Air India's
   BOM–LHR–JFK fifth-freedom era (nation IN is correct), and `K8`'s AN→HT shift
   is a route change — the actual defect in `K8` is that it is mapped to **ZM**
   (Zambia; it is Dutch Caribbean/ALM Antillean), which this test does not and
   cannot detect. It is the precision audit that catches `K8`. The diagnostic's
   honest characterisation is "0 detected nationality changes among 24 testable
   codes, 2 false positives", not "2 candidate flips".
2. **The scoping is disclosed only in a code comment** (lines 753–761) and in
   per-row resolution notes. The log line reports "2 flagged cross-border" with
   no denominator; STATUS.md's cycle-2 entry does not mention the exclusion at
   all. The director must carry it into FINDINGS in words.

### C. Priority 4 — the ICAO tier, and the fact that decides the human's answer

`icao` tier verified: 35 codes, 47,345 departures, **0.493759** of tier
departures on codes whose mapped country never appears on any of their routes;
0.657 of tier *codes*. My hand audit of the 9 icao rows in the audit sample says
it is worse than that: `EXC` Hapag-Lloyd Executive GmbH (DE)→SE, `PTQ` Pontair→
"Port Townsend Airways" US, `CRV` Acropolis Aviation (GB)→"Cargo Ivoire" CI,
`RTQ` Aerotour Dominicano→"Air Turquoise" FR, `SMQ` Serv. Aerolineas Mexicanas→
"Samar Air" TJ, `APQ` Alas de Transporte→"Aspen Aviation" US, `WGT` Volkswagen
AirService GmbH→"Lion Air Services" GB (hs 0.162, *not* flagged), `VJT` VistaJet
(Malta/Austria)→CA (hs 0.035, *not* flagged) are all wrong; only `NOS` Neos
S.p.A.→IT is right. **8 of 9.** The tier should be reported as unusable.

Its weight is trivial — 0.266% of matched-foreign departures, 3,607 departures in
class F ever, **952 departures (0.03%) inside NEW-06's 2019–2024 class-F window**
— so discarding it costs the analysis essentially nothing.

**And that is the finding the round folder is missing.** The coverage reading
clears its threshold by 0.902110 − 0.900000 = **0.00211, i.e. 41,643
departures**. The `icao` tier carries **47,345**. Delete the tier the
implementer's own audit shows is ~35–50% accurate and the coverage reading
becomes **0.8997 — a FAIL**. So the "coverage PASS" is knife-edge and is held
above the line by the least trustworthy tier in the mapping. A human deciding
"which reading of G7 governs" who does not know this will decide wrongly. It is
in no CSV, no log, and no STATUS entry. (For completeness: dropping `name_exact`
gives 0.8666; that tier is 0.0025 home0 and should not be dropped.)

### D. Priority 5 — is `home_country_dep_share == 0` a fair test? Yes, and it UNDERSTATES the error rate.

Both directions quantified, as asked.

**Overstatement (false positives) is negligible.** The distribution over matched-
foreign departures is bimodal and clean: hs ≥ 0.9 holds for 122 codes /
13,344,552 dep (**74.95%**); [0.5,0.9) 30 codes / 2,199,884 (12.36%); [0.1,0.5)
22 / 1,059,644 (5.95%); [0.01,0.1) 11 / 52,308 (0.29%); (0,0.01) 5 / 376,932
(2.12%); exactly 0: 100 / 770,339 (4.33%). The mid-range is populated by
carriers whose mapping is *correct* and whose home share is legitimately low —
`SQ` 0.227 (SIN–HKG/NRT–US), `SK` 0.250 (SAS, a three-country consortium mapped
SE), `LA` LATAM 0.408, `BW` 0.477, `NZ` 0.617, `MP` Martinair 0.609. The spike at
exactly 0 is a separate object. Reading all 100 home0 codes against
`airlines.csv` by hand, the only correct mappings in it are `9W` Jet Airways→IN
(10,168 dep, the BRU–EWR fifth freedom), `KM` Air Malta→MT (24 dep) and `M2` MHS
Aviation→DE (4 dep): **10,196 of 770,339 = 1.3% false positives.** 98.7% of the
flagged mass is genuine mis-mapping (KV→RU, RV→IR, 7Z→CV, 6R→RU, K8→ZM, FQ→BE,
`VX (1)`→US, WW→GB, DI→DE, N3→RU, B0→US, …).

**Understatement is the larger error, and it runs against the pipeline.** Codes
that are wrong but have a nonzero home share are invisible to the headline
precision-adjusted rate: `TA` Taca International (El Salvador) → **CR**, 347,572
dep at hs 0.0038; `VJT` VistaJet → CA, 17,409 at 0.035; `4Y` Eurowings Discover
(DE) → FR, 9,123 at 0.0001; `WGT` 308; `CAQ` 91; `ATQ` 91 — ≈374,594 departures.
Netting false positives against these, my point estimate of the true departures-
weighted foreign correct-nation rate is **≈0.8446**, essentially my cycle-1 upper
bound of 0.8479 and **below** the 0.8631 the CSV reports. The reported
precision-adjusted number is therefore *generous to the pipeline*, not inflated.
The `<0.01` variant, which the CSV supplies only as a share, corresponds to
**0.8440 foreign / 0.9350 overall**. Conclusion for the human: the choice of
threshold does not flip anything — every construction of the precision reading
lands in 0.844–0.863, all well under 0.90.

**Independent audit-sample scoring, pair by pair (all 80 rows read).**
- `top40_by_departures`: 3 implausible pairs — `KV` Sky Regional Airlines Inc.
  (Canada) ↔ *Kavminvodyavia (Russia)*, 222,939 dep; `RV` Air Canada rouge ↔
  *Caspian Airlines (Iran)*, 191,266; `TA` Taca International (El Salvador) ↔
  *Grupo TACA (Costa Rica)*, 347,572. 37/40 plausible; departures-weighted
  precision ≈ **0.94**. (`AZ` ITA↔Alitalia is a different legal entity but the
  same nation — accepted. `ZX` Air Georgian↔Air Georgian (Canada) is correct
  despite the name.)
- `random40_seed42` (drawn from the tail, i.e. ranks 41+, unweighted): **18 of 40
  implausible** — Z0↔All Argentina Express, AE Air Europe↔Mandarin Airlines,
  9T TravelspanGT↔Transwest Air, 8R Edelweiss (CH)↔TRIP Linhas (BR),
  `GW (1)` Central American↔Kuban Airlines (RU), ZS Hispaniola↔Sama (SA),
  EXC↔European Executive Express, PTQ Pontair↔Port Townsend Airways,
  CRV Acropolis↔Cargo Ivoire, RTQ Aerotour Dominicano↔Air Turquoise,
  GE Lufthansa Cargo↔TransAsia, SMQ↔Samar Air, K8 Dutch Caribbean↔Airlink
  Zambia, VJT VistaJet↔"Vistajet (Canada)", C8 Cargolux Italia↔Chicago Express,
  WGT Volkswagen AirService↔Lion Air Services, 7Z Lb Limited↔Halcyonair,
  APQ Alas de Transporte↔Aspen Aviation. Several are textbook generic-token
  collisions. Departures-weighted precision in this stratum ≈ **0.79**.
- **Estimated precision by tier (my scoring, departures-weighted):** `iata`
  ≈0.95; `name_exact` ≈0.997 (both audit-sample rows correct; exhaustive home0 is
  0.0025); `icao` ≈0.35–0.50 — **unusable**. These agree with the CSV-derived
  statistics, which is itself evidence the proxy is calibrated.

### E. Cycle-1 required actions, one by one

1. DEGENERATE-GATE set, FIX-02 BLOCKED-NEEDS-HUMAN, neither reading chosen —
   **DONE**. Script computes both, sets `degenerate_gate` on disagreement, logs
   an ERROR naming both readings, returns 1. STATUS.md 22:10 states the split
   neutrally and types **no** result number (rule 5 / G9 respected).
2. `carrier_nation_precision_audit.csv` with all ten specified columns and both
   `==0` / `<0.01` shares next to the coverage rate — **DONE**. 290 rows, zero
   empty cells, sorted by departures descending, both shares on the `foreign` row.
3. Audit sample 40 largest + random 40 with the OpenFlights row(s); **report
   precision per tier with the implausible pairs listed** — **PARTIAL / NOT MET.**
   The 80-row sample exists and carries `candidate_names`. But the per-tier
   precision (iata 0.0437 / icao 0.4938 / name_exact 0.0025) exists **only in
   `logs/02_carrier_nation.log`** — `grep '0.493' rounds/round-1-t100-panel/`
   returns nothing. Under G9 the director cannot cite the single most damaging
   number in this task to any `(file.csv, row)`. See required action 1.
4. Refuse suffix-collision siblings, write to flips with a resolution — **DONE**.
   22 codes / 11 families; every row's `resolution` names the base code, the
   nation that would have been inherited, and the sibling. `carrier_nation_flips.csv`
   is no longer empty for a structural reason.
5. Replace the vacuous flips check with the name-churn diagnostic — **DONE**
   (see section B for the two caveats).
6. `foreign_by_year` and `foreign_by_service_class` rows — **DONE**. 36 + 5 rows;
   both sum to the `foreign` denominator 19,735,573 exactly.
7. Exposure columns on the unmatched CSV + a corridor-coverage CSV — **DONE to
   the letter**, with two substantive shortfalls (findings 3 and 4 below).
8. No rate-raising change without a written commission — **DONE** (A3).
9. Fix advisories 6 and 7; re-run byte-identical; both checkers exit 0 —
   **PARTIAL.** Advisory 6 (the mislabelled "share resting on us_by_construction"
   log line) is **fixed** — it is absent from the 22:11 run block. Advisory 7 is
   **not fixed**: `02_carrier_nation.py:544` still hardcodes the string
   `"2,407-row category: …"`, and that literal is written verbatim into the `note`
   cell of the `null_carrier_code` row of `carrier_nation_matchrate.csv` while
   `15483` and `0.03%` beside it are interpolated. Re-run byte-identical and both
   checkers exit 0: confirmed.

### F. Gate status

- **G1** — no coef/se/pval columns anywhere; N/A. Separately: zero empty cells in
  `carrier_nation_precision_audit.csv`, `carrier_nation_audit_sample.csv`,
  `carrier_nation_unmatched.csv`, `carrier_nation_corridor_coverage.csv`. The
  only blanks are `nation_iso2` on 45 flips rows (22 refused + 23 no-nation, empty
  by construction) and the by-design-blank precision/note columns on the
  matchrate rows they do not apply to. **PASS (vacuous).**
- **G2** — no |coef|>100 on log/share outcomes; no coefficient columns. **PASS.**
- **G3** — no p-values anywhere; no p=0.0, no repeated p. **PASS (vacuous).**
- **G4** — no SEs. **PASS (vacuous).**
- **G5** — every `*share*`/`*rate*`/`*precision*` column in all ten round CSVs
  lies in [0,1], 0 violations. `share_dep_*` sums to 1 on all 80 real matchrate
  rows (max |dev| 3.3e-16); `departures_matched/departures_total ==
  match_rate_weighted` to 1.1e-16 on every row; `n_codes_matched/n_codes_total ==
  match_rate_unweighted` exactly; `by_year` departures sum to `overall`
  (47,352,549), `foreign_by_year` and `foreign_by_service_class` each sum to
  `foreign` (19,735,573), and `us` + `foreign` = `overall`. Family counts
  complete (36 years present in both year blocks). **PASS.**
- **G7 — mapping precision. DEGENERATE-GATE, correctly declared, correctly
  neither-chosen.** Coverage reading: overall 0.959201 ≥ 0.95, foreign 0.902110 ≥
  0.90 → PASS. Precision-adjusted (`==0`) reading: overall 0.942933 < 0.95,
  foreign 0.863077 < 0.90 → FAIL. My own construction (`<0.01`, and netting the
  false positives I hand-verified) puts the honest foreign figure at
  **0.844–0.863** under every variant. **Status: DEGENERATE-GATE /
  BLOCKED-NEEDS-HUMAN — I concur with the declaration.** But see finding 1: the
  coverage side of the split is knife-edge (0.00211 = 41,643 departures) and that
  is not on the record.
- **FIX-02 VERIFY item 1** ("rate ≥0.95/≥0.90 **or task is BLOCKED**) — satisfied
  via the BLOCKED branch. **Item 2** ("flips empty or every row has a `resolution`
  note") — 195/195 rows carry a non-empty resolution. **PASS, by content this
  time, not by vacuity.**
- G6, G8 — not in scope (FIX-03, FIX-05). G9 — no FINDINGS file yet; but see
  required action 1, which is a G9 problem in waiting.
- **T1–T9** — no OpenSky/Trino import or access; `98_check_trino_usage.py` exit 0;
  `logs/opensky_queries.log` correctly absent. **PASS.**
- **Rule 12 (method discipline)** — deterministic lookup, no estimator. N/A.
- **Rule 10 (post-hoc scope narrowing)** — the `us_by_construction` exclusion is
  substantively justified (section B) and the excluded rows are still written with
  a stated reason. **PASS with a disclosure requirement** (required action 5).

### G. Findings

**BLOCKING (all are additive diagnostics; none requires a mapping change)**

1. **The coverage reading's PASS is knife-edge and is propped up by the worst
   tier, and this is nowhere in the round folder.** `carrier_nation_matchrate.csv`,
   row `foreign`: `match_rate_weighted` 0.902110 exceeds 0.90 by 41,643
   departures. `carrier_nation_precision_audit.csv`, the 35 rows with
   `match_method == 'icao'`, carry 47,345 departures at 0.4938 home0. Excluding
   that tier alone gives foreign coverage **0.8997 → the coverage reading FAILS
   too**, and the "two defensible readings" become one. The human is being asked
   to choose between a PASS and a FAIL without being told the PASS survives on
   47,345 departures of a tier the same folder shows is ~35–50% accurate.
2. **Per-tier precision exists only in a log file** (`logs/02_carrier_nation.log`,
   22:11:05 block). `grep -rl '0.493' rounds/round-1-t100-panel/` → nothing. This
   is literal non-compliance with cycle-1 required action 3 ("Report precision per
   tier"), and it makes the number uncitable under G9 when the director writes
   ROUND_01_FINDINGS.md.
3. **No precision reading exists on the headline sample.** The round file's
   headline sample is `SERVICE_CLASS == 'F'` and FIX-04/NEW-06 use only class F,
   yet the precision audit and both G7 readings are computed over all service
   classes. I recompute on class F: foreign coverage **0.9303** (the CSV has this,
   `foreign_by_service_class` row `F`), foreign precision-adjusted (`==0`)
   **0.8911**, (`<0.01`) **0.8710**, and overall precision-adjusted **0.9547 —
   which PASSES the 0.95 leg**. So on the sample that actually feeds the paper the
   gate fails on the foreign leg alone and by only 0.0089, a materially different
   decision problem from the all-classes 0.8631. The all-classes figure is dragged
   down by freight: `foreign_by_service_class` shows L 0.4607, P 0.6710, G 0.7745.
   The human cannot answer "which reading governs" without the class-F cut.
4. **`carrier_nation_corridor_coverage.csv` reports the most flattering of three
   possible corridor numbers, unlabelled.** Its `match_rate_weighted` pools US
   carriers (trivially matched) into the denominator. At ICN: all-carrier
   **0.763413** (what the CSV shows) vs foreign-carrier-only **0.675340** vs
   foreign + precision-adjusted **0.657241**. For a carrier-*nationality* design
   the second and third are the relevant ones, and the CSV has no
   foreign/US split and no precision column. It also hides that `NRT` reads
   1.0000 coverage but **0.9228** precision-adjusted (ZIPAIR `ZG`→MO), and CDG
   0.9827. There is no `covid_flag` on the `zoom_2021h2_2022` window even though
   it overlaps Part 0's COVID window (2020-03 to 2021-12).
5. **`carrier_nation_unmatched.csv` is not actionable in one sitting.** 244 rows,
   correctly sorted descending on `total_departures` (verified monotone), named,
   with `modal_foreign_endpoint_country` and `departures_2019_2024_classF` — but
   **no `n_openflights_candidates` and no `candidate_names`**, both of which the
   script already holds in `code_tbl` for these codes. A human looking at `AV`
   Avianca (254,450 dep) or `OZ` Asiana (204,972) cannot see *why* it is unmatched
   — corrupt `country` field, two-country ambiguity, or zero candidates — without
   re-deriving it from `airlines.csv`. That is precisely the decision the human is
   being handed.

**ADVISORY**

6. **Cycle-1 advisory 7 still open.** `02_carrier_nation.py:544` hardcodes
   `"2,407-row category: …"`; the literal is written into the `note` cell of
   `carrier_nation_matchrate.csv`, row `null_carrier_code`. Correct today, silently
   stale on the next drop. Interpolate `n_null_rows`.
7. **`code/02_build/` is still untracked** (cycle-1 advisory 9, unheeded). No
   cycle-1→cycle-2 diff was possible; I verified action 8 by full read plus exact
   numeric reconciliation instead. Commit before cycle 3 so the history is auditable.
8. **The name-churn cross-border test should be reported as a null with 2 false
   positives, not as "2 flags"** (section B), and its 24-of-80 denominator must be
   stated. Both `AI` and `K8` resolve on inspection; `K8`'s real defect (→ZM) is
   caught by the precision audit, not by this test.
9. **The refusal rule's collateral cost is worth one sentence to the human**:
   85,936 of the 215,007 refused departures were on codes whose pre-refusal
   mapping was probably right, including `SN`/`SN (1)` where both siblings are
   Belgian and both would have received the correct BE (A4). A dated lookup
   recovers them without guessing; corporate-suffix normalisation must **not** be
   used for this (that is the action-8 prohibition).
10. **The round file was never amended to commission the three new deliverables**
    (`carrier_nation_precision_audit.csv`, `carrier_nation_audit_sample.csv`,
    `carrier_nation_corridor_coverage.csv`). They were commissioned by my cycle-1
    required actions, which is a legitimate route, but FINDINGS must record that
    FIX-02's deliverable list grew from 4 to 7 and why.
11. **The DEGENERATE-GATE is stated neutrally in STATUS.md and in the log, but not
    in any CSV.** `carrier_nation_matchrate.csv` presents `match_rate_weighted`
    and `precision_adjusted_match_rate` side by side with an empty `note` cell on
    both the `overall` and `foreign` rows. The artifact is not self-describing; a
    reader who opens only the CSV sees two numbers and no statement that the gate
    is split and unresolved. (Neutrality of the wording itself: I checked and it is
    even-handed. The log's "G7 is titled 'mapping precision'" leans very slightly
    toward the precision reading, but it is a true statement about the round file's
    own text and I do not object to it.)

### H. VERDICT

**VERDICT: FAIL** — cycle 2 of 3.

To be unambiguous about what is *not* wrong, because this must not be
re-litigated in cycle 3: the DEGENERATE-GATE declaration is **correct and I
endorse it**; the two readings are honest, exactly reproducible and neither is
preferred; the refusal fix is the right structural fix and moved both readings
down; there is no rate-chasing; the outputs are deterministic; the
`us_by_construction` scoping is substantively justified. A rigorous BLOCKED is a
successful outcome and this one is nearly there.

It fails because cycle-1 required action 3 is not met (per-tier precision is not
in any round-folder CSV — finding 2, testable by `grep`), and because the
evidence package is not yet *sufficient for a human to decide in one sitting*:
the decisive sensitivity (finding 1), the headline-sample cut the decision
actually turns on (finding 3), the corridor number's definition (finding 4) and
the reason-for-non-match (finding 5) are all absent. Each is an additive
diagnostic over data already in memory in the same script.

### I. Required actions for cycle 3 (all additive; change NO mapping, NO threshold, NO rate)

1. **Write per-tier precision into a CSV.** Add rows to
   `carrier_nation_precision_audit.csv` (or a `carrier_nation_precision_by_tier.csv`)
   with one row per `match_method` ∈ {iata, icao, name_exact} giving `n_codes`,
   `departures`, `share_home0_codes`, `share_home0_dep`, `share_home_lt001_dep`.
   The numbers must reproduce iata 226/17,054,778/0.043693, icao 35/47,345/0.493759,
   name_exact 29/701,536/0.002544.
2. **Add the leave-one-tier-out sensitivity of the coverage reading**, as rows or
   columns in `carrier_nation_matchrate.csv`: foreign coverage excluding `icao`
   = 0.8997, excluding `name_exact` = 0.8666, and the margin above the threshold
   in departures (41,643). One line of arithmetic; it is the single most
   decision-relevant fact in the task.
3. **Compute both G7 readings on the headline sample.** Add
   `precision_adjusted_match_rate`, `share_matched_dep_home0` and
   `share_matched_dep_home_lt_001` to the `foreign_by_service_class` rows (at
   minimum the `F` row) and to a new `overall_class_f` / `foreign_class_f` row
   pair. Expected: foreign F coverage 0.9303, precision-adjusted 0.8911
   (`<0.01`: 0.8710); overall F coverage 0.9710, precision-adjusted 0.9547.
   Also report the `<0.01` variant of `precision_adjusted_match_rate` as its own
   column for the all-classes rows (foreign 0.8440, overall 0.9350) so the
   threshold choice is visible rather than implicit.
4. **Fix the corridor CSV's definition.** Add `carrier_group` (`all` / `foreign`)
   as a row dimension and a `precision_adjusted_match_rate` column, plus a
   `covid_overlap` boolean on the window. Expected ICN full_2019_2024: all
   0.763413, foreign 0.675340, foreign precision-adjusted 0.657241; NRT foreign
   1.000000 / 0.922750.
5. **Add `n_openflights_candidates` and `candidate_names` to
   `carrier_nation_unmatched.csv`**, and a `reason` column distinguishing
   zero-candidate / ambiguous-country / unresolvable-country-string /
   refused-suffix-collision. The script already carries all of it in `code_tbl`.
6. **Disclosure, in STATUS.md and then in ROUND_01_FINDINGS.md** (words, not new
   numbers): that the cross-border drift test was applied to 24 lookup-matched
   churn codes and deliberately not to the 45 `us_by_construction` ones, with the
   reason; that its 2 flags both resolve as false positives; and that the refusal
   rule removed ~86k departures of probably-correct mapping.
7. Fix advisory 6 (interpolate `n_null_rows` at line 544), and **commit
   `code/02_build/`** so cycle 3 is diffable.
8. Re-run; confirm the six existing CSVs change only by the intended additions;
   `99_validate_outputs.py` and `98_check_trino_usage.py` exit 0; script still
   exits 1 under DEGENERATE-GATE. **Do not touch the matching rules.** Any edit
   that moves 0.902110 or 0.863077 is out of scope and will fail cycle 3.

### J. (a) The precise question the human must answer

**Does G7 govern *coverage* (did the carrier code resolve to some nation) or
*precision* (is the resolved nation the right one)?** Concretely, one of:
- **(a1)** G7 = coverage → foreign 0.9021 clears 0.90 and FIX-04+ proceed on all
  matched carriers. The human must then accept, in writing, that ≈15% of matched
  foreign departures are on a code mapped to a nation the carrier never flies to,
  that mapped **RU** is ~0.18 precise and mapped **IR** ~0.000, and that the PASS
  survives by 41,643 departures carried by a tier that is ~35–50% accurate.
- **(a2)** G7 = precision → 0.8631 (or 0.8911 on class F) fails and FIX-02 stays
  BLOCKED until the lookup source is replaced or dated.
- **(a3)** Split the difference: keep the coverage gate but exclude specified
  low-precision strata (the `icao` tier; codes with `home_country_dep_share == 0`;
  or nations whose within-nation precision is below some bar) and log the
  exclusion. This is the option the evidence actually supports and it is cheap:
  the `icao` tier is 952 departures inside NEW-06's window.

A second, independent decision is queued behind it: **may a better
carrier-nationality source be placed in `data/raw/lookups/`** (ICAO Doc 8585, OAG,
or a BTS carrier decode with country and dates)? `data/raw/lookups/airlines.csv`
is a 2014-vintage OpenFlights extract with 62 corrupted `country` values
(`AVIANCA`, `Russia]]`, ` S.A.`, `WATCHDOG`), no dates, and it is the direct cause
of every defect in this task. No agent may add one without this decision.

### K. (b) What would unblock FIX-02

Any **one** of:
- a human ruling on (a1)/(a2)/(a3) recorded in DECISIONS.md and reflected in a
  ROUND_01.md amendment restating G7 unambiguously; **or**
- a human-placed dated carrier-nationality lookup in `data/raw/lookups/`, after
  which FIX-02 re-runs and G7 is evaluated once, on one reading; **or**
- a director-written commission in ROUND_01.md for a specific matching change,
  with the before/after rate reported both ways (cycle-1 action 8).
Nothing an agent can do alone unblocks it. Completing my cycle-3 actions above
does **not** unblock FIX-02 — it makes the BLOCKED package decision-grade.

### L. (c) Ruling: what FIX-03, FIX-04, FIX-05 and NEW-06 may use now

Part 0's G7 clause — "Below threshold → FIX-02 BLOCKED-NEEDS-HUMAN, and FIX-04+
proceed only on matched carriers with the exclusion logged" — is the operative
authority, and it is written to survive exactly this situation. My ruling:

- **FIX-03 (coverage audit): MAY PROCEED**, on `match_method ∈ {iata, icao,
  name_exact, us_by_construction}` from `data/interim/carrier_nation.parquet`, with
  the exclusion logged as a row in `coverage_excluded_cells.csv`'s filter log:
  244 codes / 1,931,914 departures excluded (222 unmatched + 22 refused). FIX-03
  measures *airborne-time reporting coverage*, and its conclusions are about data
  completeness, not about nationality, so mis-mapping degrades it far less than it
  degrades FIX-04. **Condition:** FIX-03 must additionally report every nation ×
  year coverage cell's `share_dep_home0` so that a nation whose cells are built
  mostly out of mis-mapped carriers is visible before FIX-04 consumes it.
  Mandatory captions: mapped nation **RU** and **IR** must be labelled
  MATCH-SENSITIVE wherever they appear.
- **FIX-04 (panel): MAY PROCEED under a hard restriction.** Build on matched
  carriers only, with the exclusion logged in `panel_filter_log.csv` as its own
  named filter step with before/after departures. In addition, and this is not
  optional: carry a per-cell `nation_precision_flag` derived from
  `carrier_nation_precision_audit.csv` (`home_country_dep_share == 0`, and a
  second at `< 0.01`), and write a `cell_ok_precision` column. The panel may be
  **built**; no nation-level number from it may be **reported** until FIX-02 is
  unblocked. The `icao` tier (952 departures in the 2019–2024 class-F window)
  should simply be dropped in FIX-04 with the drop logged — it costs nothing and
  removes the worst stratum.
- **FIX-05 (baselines/excess): MAY PROCEED** on FIX-04's output. It is arithmetic
  on the panel and inherits FIX-04's flags; nothing in it depends on nationality
  being right. Same reporting embargo.
- **NEW-06 (the raw-data wedge figure): MAY PROCEED to build, MUST NOT be
  presented as a headline.** It is the one task where mis-mapping is fatal: its
  treated nations are exactly where precision is worst, and 8.85% of matched
  foreign class-F departures in its own 2019–2024 window sit on codes with
  `home_country_dep_share < 0.01`. Every NEW-06 artifact must carry the
  MATCH-SENSITIVE flag and a version computed with home0 codes excluded, shown
  side by side. NEW-06 also still carries the FIX-00 forward flag: its treatment
  list comes from the agent-drafted, human-unreviewed
  `data/raw/events/ban_nations_2022.csv`.
- **Corridor 1 / ICN: MAY BE COMPUTED, MUST NOT BE REPORTED as a corridor
  result in this round.** Foreign-carrier coverage at ICN in the 2019–2024
  window is **0.675340** (0.657241 precision-adjusted) against ≥0.956 at every
  other anchor; Asiana `OZ` (22,793 class-F departures 2019–2024) and Jin Air
  `LJ` are simply absent, so a "Korea" series is Korean Air + Jeju + Air Busan
  with the second flag carrier silently missing. Any ICN chart must state that
  in the caption or be dropped. `TPE` at 0.956194 (STARLUX `JX` missing) should
  carry a footnote. The other 20 anchors are clean at ≥0.9995 and may be used
  normally.
- **Nothing may be written into `paper/` or `slides/` from FIX-02 outputs.**

### M. For the director to carry into ROUND_01_FINDINGS.md

1. G7 is split and must always be reported split, both numbers traced:
   coverage `(carrier_nation_matchrate.csv, row foreign, match_rate_weighted)`
   and precision-adjusted `(same row, precision_adjusted_match_rate)`, with
   `share_matched_dep_home0` and `share_matched_dep_home_lt_001` from the same
   row. **Never report 0.9021 alone.**
2. The knife-edge: the coverage PASS clears by 41,643 departures and dies if the
   `icao` tier is removed (finding 1). Cite once required action 2 exists.
3. Per-tier precision, with `icao` reported as **unusable** and its trivial weight
   stated (952 departures in NEW-06's window). Cite once required action 1 exists.
4. Mapped **RU** precision ≈0.18 and mapped **IR** ≈0.000 — named carriers `KV`
   Sky Regional (Canada) and `RV` Air Canada rouge. The most damaging pair of
   numbers in the round; a referee will find them if we do not.
5. `TA` Taca International (El Salvador) mapped to **CR**, 347,572 departures —
   a vendor error in `airlines.csv` that both G7 readings currently let through
   (`home_country_dep_share` 0.0038 > 0).
6. ICN foreign coverage 0.675 vs ≥0.956 elsewhere; Asiana absent from corridor 1.
7. The name-churn null: 80 codes / 173 rows / 13.83% of departures churn their
   name; of the 24 testable, 0 genuine cross-border reissues (2 flags, both false
   positives). Report as a reassuring null under rule 6, with the scoping stated.
8. The suffix-collision refusal: 22 codes / 11 families / 215,007 departures now
   refused rather than guessed; it lowered both G7 readings; ~86k of those
   departures were probably correct and a dated lookup would recover them.
9. FIX-02's deliverable list grew from 4 to 7 files, commissioned by overseer
   cycle-1 required actions rather than by the round file (advisory 10).
10. DECISION-PENDING for the human: replace `data/raw/lookups/airlines.csv`
    (2014 OpenFlights, 62 corrupted `country` values, no dates) with a dated
    carrier-nationality source before FIX-04 is reported. Carried forward from
    cycle 1 and now the direct cause of the block.
11. Carried from FIX-01 and still owed in FINDINGS: SERVICE_CLASS `Q`
    (`ingest_value_drift.csv`, the 9 rows with `documented_in_round_file` False);
    the exact-duplicate / cell-key non-uniqueness warning for FIX-04; and the
    note that the eight NA-count literals are drop-specific while the NA-string
    guard is the durable check.

---

## FIX-03 review — 2026-09-02 00:32 UTC

**VERDICT: FAIL** (additive-only required actions; no result is wrong, and
nothing below asks for a re-specification. The task's own VERIFY items all
pass and every number I recomputed reproduced exactly. It fails because the
single most consequential claim of the round is supported by no committed
script and no round-folder CSV, and therefore cannot be cited under G9, and
because two deliverable-text items are not met.)

### 0. HEADLINE: the zero-foreign-air-time finding is **CONFIRMED**, and it is
### stronger and cleaner than the implementer stated.

I verified this from the raw CSVs under `data/raw/t100/` with my own code,
using only BTS's `CARRIER_GROUP` field, touching neither the FIX-01 parquet
nor the FIX-02 mapping. Not a sample of years — **all 36 files, 1990-2025**:

- `CARRIER_GROUP` values present in the drop: {0, 1, 2, 3, 7}. Group 0 is the
  foreign group (2019 top codes by departures: AC Air Canada, KV Sky Regional,
  WS Westjet, QK Jazz, BA British Airways, CM Copa, LH Lufthansa); groups
  1/2/3 are US large/national/regional (AA, UA, DL, JetBlue, Mesa, Piedmont)
  and group 7 (2002-2004 only, 382 rows) is ABX Air, a US freighter.
- **Rows in CARRIER_GROUP 0 with `AIR_TIME > 0`, all 36 files: 0 of 1,133,545.**
- **Rows in CARRIER_GROUP 0 with `RAMP_TO_RAMP > 0`, all 36 files: 0 of 1,133,545.**
- Nulls in those columns for group 0: **0**. Every value is the literal string
  `0.00`. There are **no blank cells anywhere in the 2019 file** (checked every
  column, `(df=='').sum()` is zero for all 44 columns), so `0.00` is this
  export's representation of "not reported".
- US groups: `AIR_TIME > 0` on 1,523,392 of 1,523,785 rows with
  `DEPARTURES_PERFORMED > 0` (99.97%). Per-year, per-group counts reproduce the
  implementer's 2019 figures exactly (group 0: 41,958 rows, share 0.0;
  groups 1/2/3: share 1.000 among departures>0).

So the wording should be **"never", not "essentially never"**: it is not a
pattern of gaps, not "almost all", and there is no single foreign carrier
anywhere in the 36 years that reports a nonzero airborne or ramp minute. The
distribution is perfectly binary — in `coverage_audit.csv`, exactly 28 of
2,249 cells have a share strictly between 0 and 1, all of them US; every one
of the 2,213 G6-failing cells has `share_air_time_valid` **exactly 0.0**
(`max(share_air_time_valid)` over `coverage_excluded_cells.csv` = 0.0).

Two independent corroborations the implementer did not report and should:

- The finding survives the FIX-02 exclusion. Of the 70,132 rows FIX-03 drops
  for being unmatched/refused, **70,120 are CARRIER_GROUP 0 with
  `AIR_TIME>0` share 0.0**, and the other 12 are US-group rows with share 1.0.
  So "every foreign row" is literally true over the whole class-F, departures>0
  sample, not merely over the 96.14% that FIX-02 could map.
- The mapping never assigns a US-carrier-group code to a foreign nation
  (0 rows), and 1,816 foreign-group rows are mapped to nation `US` — those
  1,816 rows are exactly why US coverage is 0.9923-1.0 rather than 1.0
  (US-mapped rows with `AIR_TIME==0`: 1,876, of which 1,816 are group 0).
  That is a FIX-02 precision leak, not an airborne-time gap.

### 1. Which columns are US-only (all 36 files, share of rows with value > 0)

| column | foreign (grp 0) | US (grp 1/2/3/7) |
|---|---|---|
| AIR_TIME | **0.000000** | 0.996381 |
| RAMP_TO_RAMP | **0.000000** | 0.996632 |
| DEPARTURES_SCHEDULED | **0.000000** | 0.716241 |
| MAIL | **0.000000** | 0.201192 |
| DEPARTURES_PERFORMED | 1.000000 | 0.996638 |
| DISTANCE | 1.000000 | 0.999835 |
| SEATS | 0.840383 | 0.785076 |
| PASSENGERS | 0.835525 | 0.763837 |
| PAYLOAD | 0.809544 | 0.996519 |
| FREIGHT | 0.651918 | 0.547579 |

Foreign operators report **volume**, never **time**: performed departures,
distance, seats, passengers, payload, freight are all present and usable;
airborne time, ramp-to-ramp time, scheduled departures and mail are uniformly
absent.

### 2. Extract artifact or BTS reporting? — **BTS reporting.**

Stated plainly, as commissioned. The evidence in hand:
(a) `AIR_TIME` and `RAMP_TO_RAMP` are **in the header of every one of the 36
files** and are fully populated for US carriers **in those same files**, so
this is not a column the download omitted; (b) the export writes no blanks at
all, so foreign rows are zero-filled, not null-filled; (c) the absent set is
not arbitrary — it is exactly `{airborne time, ramp-to-ramp, departures
scheduled, mail}`, which is the data-element difference between the US
carriers' T-100 schedule and the foreign carriers' T-100(f) schedule; (d) it
holds without a single exception for 36 consecutive years and every foreign
carrier. A different download of the same BTS table will return the same
zeros. **Consequence: the fix is a different data source, not a different
download.** The one check I cannot run unattended is BTS's own documentation
of the T-100(f) data elements (needs a web session); I record that as the
confirming step, not as doubt about the conclusion.

### 3. No imputation, zero-vs-null kept distinct — confirmed

`code/03_audit/03_coverage_audit.py` counts `>0`, `==0` and `isna()` in three
separate columns per field (`n_air_time_valid/zero/null`, `n_ramp_*`) and
writes all three shares; they sum to 1 in every cell (max deviation 2.2e-16 in
both CSVs). The only `fillna` in the script is on the boolean precision flag
`flag_home_share_zero` (defaulted False for `us_by_construction` codes, which
are absent from the precision audit by design) — no outcome column is filled,
smoothed, or interpolated anywhere. `share_air_time_null` and
`share_ramp_null` are 0.0 in all 2,249 + 1,037 cells, correctly, because the
source zero-fills. `data/raw/` is untouched (`git status` clean under it).

### 4. Checks run (recomputed independently, not reread)

- Full independent rebuild of `coverage_audit.csv` from the two parquets +
  precision CSV: 2,249 cells, outer-merge `both`=2,249, `left_only`=0,
  `right_only`=0; max abs difference **0** on `n_segment_months`,
  `n_air_time_valid`, `n_air_time_zero`, `n_air_time_null`, `n_ramp_valid`,
  `dep_total`, `median_departures`, `dep_home0`, and 1.1e-16 on
  `share_air_time_valid`.
- Independent rebuild of `coverage_by_corridor.csv`: 1,037 cells, all `both`,
  max abs difference 0 on `n_segment_months`, `n_air_time_valid`, `dep_total`,
  `median_departures`.
- G6: my count of cells with `share_air_time_valid < 0.50` = **2,213**, matching
  `coverage_excluded_cells.csv` row count exactly; departures-weighted failure
  share **0.3976470** (16,078,928 / 40,435,177).
- TeX traceability: `US` row `1990s cov.\ % = 99.7` recomputes to 0.9965,
  `2020s = 99.6` to 0.9964, `Overall = 99.8` to 0.9982, `Total dep. =
  24,356,249` exact; `RU home0 % = 80.2` to 0.8019; `GB = 1.0` to 0.0098;
  `DE = 2.4` to 0.0238; 93 nation rows = 93 nations in the CSV. All
  departures-weighted from `coverage_audit.csv` only.
- Determinism: re-ran the script; all six outputs **byte-identical** (sha256
  match on all four CSVs, the .tex and the .png).
- `python code/99_validate_outputs.py` → `16 CSVs scanned, 0 FAIL, 0 WARN`,
  **exit 0**. `python code/98_check_trino_usage.py` → `0 FAIL`, **exit 0**.
  All six new artifacts are inside `rounds/round-1-t100-panel/` and inside the
  validator's directory-wide scan. No network, no Trino, no OpenSky (T8 clean);
  the script imports only pandas/numpy/matplotlib/utils.
- Pathology sweep over **all 16** round-folder CSVs (not a manifest): no
  column with `share`/`rate`/`precision` in its name outside [0,1]; no all-null
  column except two note columns in `ingest_rowcounts.csv` (FIX-01, expected);
  no p-value columns exist this round (no regressions), so G1-G4 are vacuous.
- `utils.setup_logger` and `utils.log_merge` both used; the merge log shows
  1,815,580 left / 8,842 right / 1,815,580 merged, 515 `left_only`.
- No hand-typed number in STATUS.md's FIX-03 entry (qualitative only), none in
  the .tex (auto-generated header present), none in the figure.

### 5. VERIFY items (round file, FIX-03)

- [x] every share column in both coverage CSVs within [0,1] — all 7 share
      columns in each; min 0.0, max 1.0, zero nulls, in both files.
- [x] set equality both directions — |{cells <0.50 in `coverage_audit.csv`}| =
      2,213, |rows in `coverage_excluded_cells.csv`| = 2,213, symmetric
      difference **empty in both directions**; each excluded row's
      `share_air_time_valid` equals its `coverage_audit.csv` value. The
      assertion is in code (line 281) and it is a real assertion, not a log.
- Corridor coverage: all four corridors present (`useastasia` 373 cells,
  `useurope_placebo` 461, `usindia` 41, `usmideast` 162). Both directions are
  in the underlying sample and roughly balanced (e.g. `useastasia` 48,411
  US→foreign vs 48,694 foreign→US; `useurope_placebo` 97,390 / 100,950) — but
  see finding 4 below.
- Captions/titles carry "US-touching international segments" in the source
  string — but see finding 5 below for the rendered figure.

### 6. Gate status

- **G1-G4**: N/A (no regression output this round). No p-values anywhere.
- **G5**: PASS. All share columns in [0,1] in both coverage CSVs; the
  three-way shares sum to 1 within 2.2e-16.
- **G6**: mechanism worked exactly as designed and is **not** a FIX-03 defect:
  2,213 / 2,249 nation-year cells excluded, 39.76% of departures, all
  foreign, all at exactly 0.0 coverage; **0 of 908 non-US anchor-corridor
  cells pass**. The round file's stated ex-ante "what would count against
  proceeding" is triggered at the maximum possible scale. FIX-03 correctly
  reports and lists rather than relaxing; marking the task DONE (not BLOCKED)
  is the right call, since G6 is a filter gate on FIX-04's population, not a
  validity gate on FIX-03.
- **G7**: unchanged, still BLOCKED-NEEDS-HUMAN / DEGENERATE-GATE. FIX-03
  complied with my FIX-02 ruling: matched methods only, `share_dep_home0` on
  every cell, RU/IR labelled `match_sensitive` in both CSVs and in the table
  and figure. **However**, see finding 1: the round's headline now rests on a
  mapping-independent fact, and the round folder contains only the
  mapping-dependent version of it.
- **G8, G9**: G8 N/A (no baselines yet). **G9 is the reason for the FAIL** —
  see finding 1.

### 7. FIX-02 exclusion-population reconciliation (my 244 / 1,931,914 vs the
### implementer's 98 / 70,132 / 1,214,475) — **reconciled, no discrepancy**

Different bases, both correct. My FIX-02 ruling's figures are the whole-parquet
base (all service classes, all rows): I recompute **244 codes / 1,947,397
departures** over all rows, of which `carrier_nation_unmatched.csv`'s
`total_departures` column sums to exactly **1,931,914** — the 15,483
difference is the null-carrier-code rows, which that CSV does not carry.
FIX-03's base is its own analysis sample (class F passenger, departures > 0):
I recompute **98 codes (78 unmatched + 20 refused) / 70,132 rows / 1,214,475
departures**, matching `coverage_matching_exclusions.csv` exactly (the CSV's
99th row is the blank-carrier-code group). Recommend the director state the
base explicitly wherever either number appears.

### 8. Findings

1. **[BLOCKING] The round's headline result exists in no round-folder CSV and
   in no committed script.** The `CARRIER_GROUP` verification — the only
   evidence that is independent of the BLOCKED FIX-02 mapping, and the only
   evidence that supports the word "every" — was done ad hoc. It is not in
   `code/03_audit/03_coverage_audit.py` (which never reads `CARRIER_GROUP`),
   not in `logs/03_coverage_audit.log` (grep for `carrier_group`: no hits),
   and not in any of the four CSVs. Under G9 the director **cannot cite it in
   FINDINGS at all**, and the only citable version — `coverage_audit.csv` by
   mapped `nation` — is downstream of the one input this round has formally
   declared unreliable. That is precisely backwards: the most decision-critical
   claim of the round is the least verifiable artifact in it. It happens to be
   true (section 0), but the repository cannot demonstrate it.
2. **[BLOCKING] `n_segment_months` is not segment-months.** The deliverable
   text is "segment-months with departures > 0"; the column is a raw row count
   over carrier × segment × month × aircraft type. In the matched sample it is
   **1.70×** the number of distinct `(ORIGIN, DEST, MONTH)` pairs per cell
   (1,745,448 rows vs 1,027,021 distinct segment-months). Because coverage here
   is binary the shares are unaffected, but the column will be read as a sample
   size by anyone using this table, and Part 0 explicitly warns that T-100 rows
   are aircraft-type rows.
3. **[non-blocking] The `coverage_matching_exclusions.csv` population's own
   coverage is not reported**, so the audit as shipped cannot support "every
   foreign row" — only "every matched foreign row" (96.14% of rows). I verified
   the excluded population is also uniformly zero (70,120 group-0 rows at 0.0);
   that belongs in the CSV, not in my review.
4. **[non-blocking] `coverage_by_corridor.csv` has no `direction` column.**
   Both directions are pooled into each cell. The deliverable spec did not
   require the split and the 0/1 structure means it cannot change any
   conclusion, but Part 0 says "keep direction, never symmetrize", and a reader
   cannot tell from the CSV that both legs are inside each row.
5. **[non-blocking] The figure's mandatory Part 0 label is clipped in the
   render.** `fig_coverage_heatmap.png` renders its title as "...ouching
   international segments (* = MATCH-SENSITIVE: RU, IR — see FIX-02
   DEGENERATE-GATE" — both ends cut off by the axes box. The string is correct
   in the source; the PNG a human actually looks at does not show "US-touching"
   or the closing paren.
6. **[advisory, for the director]** The `match_sensitive` labelling is correct
   but now nearly moot: RU and IR both sit at 0.0 coverage like every other
   foreign nation, so the FIX-02 precision problem cannot change any FIX-03
   conclusion. Worth saying in FINDINGS so the human does not read two
   independent blockers as one compounding one. Conversely, the 1,816
   foreign-group rows mapped to `US` are the FIX-02 leak that *does* touch this
   table (it is why US coverage is 99.2-100% and not 100%).
7. **[advisory]** `COVID_YEARS = {2020, 2021}` flags whole calendar years while
   PROJECT.md's window is 2020-03..2021-12. Defensible at annual granularity
   and documented in a comment; carry the coarsening into FINDINGS so FIX-05
   does not inherit it silently at monthly granularity.

### 9. Required actions (all additive; no mapping change, no re-specification)

1. Add a committed script (e.g. `code/03_audit/03b_carrier_group_coverage.py`)
   writing `rounds/round-1-t100-panel/coverage_by_carrier_group.csv` **read
   straight from `data/raw/t100/*.csv`** (or from the parquet's verbatim
   `CARRIER_GROUP` column, stating which), with no dependence on
   `carrier_nation.parquet`: one row per `year × CARRIER_GROUP`, columns
   `n_rows, n_dep_gt0, n_air_gt0, n_air_zero, n_air_null, n_ramp_gt0,
   n_ramp_zero, n_ramp_null, n_depsched_gt0, n_mail_gt0, n_seats_gt0,
   n_pax_gt0, n_dist_gt0, departures, is_us_carrier_group`. Assert in code that
   `n_air_gt0 == 0` and `n_ramp_gt0 == 0` for every `CARRIER_GROUP == 0` row.
   Values it must reproduce (I computed these independently; a mismatch is a
   bug in the new script, not in my numbers): group 0 totals 1,133,545 rows
   with 0 `AIR_TIME>0`, 0 `RAMP_TO_RAMP>0` and 0 nulls in either; US groups
   total 1,523,392 `AIR_TIME>0` of 1,523,785 departures>0 rows; the
   `CARRIER_GROUP` value set is {0,1,2,3,7} with group 7 confined to 2002-2004.
2. In the same CSV or a companion, write the all-36-file column-availability
   table of section 1 (share of rows > 0 by column × US/foreign group), so the
   director can cite "foreign carriers report volume, never time" with a trace.
3. Add the excluded population's own coverage to
   `coverage_matching_exclusions.csv` (columns `n_air_gt0`, `share_air_gt0`,
   `carrier_group`), so the "no exceptions" wording is citable. Expected:
   70,120 foreign-group rows at 0.0, 12 US-group rows at 1.0.
4. Rename `n_segment_months` → `n_rows` (or add `n_distinct_segment_months`
   alongside) in both coverage CSVs, the .tex and the figure, and state the
   aircraft-type multiplicity in the script docstring.
5. Fix the figure title clipping so "US-touching international segments" is
   fully legible in the rendered PNG (shorten, wrap, or widen the figure).
   Part 0 makes this label mandatory on every figure.
6. Add a `direction` column to `coverage_by_corridor.csv`, or a `directions`
   column stating the pooling, so Part 0's direction rule is visibly honoured.
7. Re-run both checkers and confirm byte-identical re-run of the six existing
   artifacts (they are byte-identical today; keep them so).

### 10. (b) What this means for FIX-04, FIX-05 and NEW-06

**The project's headline outcome is unobservable in T-100 for every operator
except US carriers. This is not a coverage problem to be filtered around; it is
the absence of the dependent variable for the treated population.**

- **PROJECT.md Outcome 1 (excess airborne time), Outcome 2 (asymmetric vs
  symmetric disruption), Outcome 3 (bidirectional sum)** all require airborne
  minutes per departure by operator nationality. For foreign operators that
  quantity does not exist in this source, in any year, on any route.
- **FIX-04 — build, with a hollow centre.** The panel keys and the extensive
  margin are fully constructible for all 93 nations. But `air_time_total`,
  `ramp_total`, `airborne_min_mean`, `ramp_min_mean` will be non-missing only
  for `nation == US` cells: 36 of 2,249 nation-year cells, 24,356,249 of
  40,435,177 departures (60.24%). `coverage_ok` (G6) will be True only for US
  cells. `departures_performed`, `departures_scheduled` (US-only, see section
  1), `distance`, `n_carriers`, `n_aircraft_types`, `fleet_share_top_type`,
  `covid_flag` are all fine for everyone. **Recommendation: FIX-04 proceeds,
  but its time-based columns must be documented as US-operator-only, and
  `panel_extensive.parquet` becomes the round's most valuable output rather
  than a side deliverable.**
- **FIX-05 — arithmetic on an all-US sample.** Baselines, MAD, excess,
  winsorization and the bidirectional sum are all computable and correct, but
  only within US operators (both legs of every bidirectional pair will be US).
  It stops being "the carrier-nation wedge" and becomes "US carriers' airborne
  time on international routes". Worth running: it is the machinery the paper
  needs, and it is testable on the one nation that reports.
- **NEW-06 — the commissioned figure cannot exist.** Its stated question is
  "on the same routes, do airlines of different nationalities show different
  airborne times after February 2022?" Every treated foreign nation is at
  exactly 0.0 coverage: in `coverage_by_corridor.csv`, all 79 rows for
  {CN, IN, AE, QA, TR, KR, JP, GB, FR, DE, NL, ES} in 2019-2024 have
  `share_air_time_valid = 0.0`, and **0 of 908 non-US corridor cells pass G6**,
  identically on the three treated corridors and on the European placebo. Each
  of the four corridor figures would contain exactly one line (US, coverage
  1.000 in 2019-2024 on all four corridors), and `raw_wedge_diffs.csv`'s
  treated-minus-control column would be NaN in every month by construction —
  the control side is empty, not small. NEW-06 must be re-scoped or BLOCKED;
  it must not be shipped as a set of one-line charts implying a comparison
  that the data cannot make.

**What survives, concretely, and is worth doing:**
(i) the **extensive margin** for all nations — route entry/exit, frequency,
seats, passengers, load factor — which is a genuine geoeconomic-response
outcome and is fully populated for foreign carriers (`DEPARTURES_PERFORMED`
1.000000, `SEATS` 0.840383, `PASSENGERS` 0.835525 of rows > 0);
(ii) a **US-carrier-only, route-exposure design**: US carriers are themselves
subject to the 2022 Russian overflight ban, so US-operated US–East Asia
segments (141,251 departures 2019-2024, coverage 1.000) can be compared with
US-operated US–Western Europe segments (389,436 departures, coverage 0.991)
and US–Middle East (20,824) / US–India (10,791). This replaces identification
off *operator nationality* with identification off *route exposure*, keeps the
airborne-time outcome, and keeps a placebo. **It is a change to a starred
PROJECT.md section (unit of observation) and is therefore DECISION-PENDING for
the human, not a director call.**
(iii) **Phase 2 (OpenSky/ADS-B) is now the only route to the operator-nationality
wedge**, because ADS-B observes every operator's actual airborne time
regardless of who files what with BTS. The round file's own note (iii) about
"whether coverage on the US–East Asia corridor justifies starting the Phase-2
extract request" is now answered in the strongest possible terms: T-100 cannot
deliver the design at all, and the attended OpenSky pull is the project's
critical path, not an optional enrichment.

### 11. (c) What the director must put in FINDINGS, and the human's decision

FINDINGS must contain, each with a `(file.csv, row)` trace once required
action 1 lands:
1. The carrier-group fact as the round's headline, from
   `coverage_by_carrier_group.csv` — foreign carrier group, 36 years, zero rows
   with airborne or ramp minutes, zero nulls — stated as **never**, not
   "effectively never", and explicitly labelled a property of **BTS's foreign-
   carrier reporting schedule, not of our download**, with the caveat that the
   confirming documentation check needs an attended web session.
2. The column-availability split (foreign carriers report volume, never time),
   from required action 2, because it defines the entire surviving option set.
3. G6's outcome from `coverage_excluded_cells.csv` (2,213 of 2,249 cells;
   39.76% of departures; every failing cell exactly 0.0) and from
   `coverage_by_corridor.csv` (0 of 908 non-US anchor-corridor cells pass;
   all 79 anchor-nation 2019-2024 rows at 0.0, treated and placebo alike).
4. The explicit statement that **NEW-06 as commissioned is not computable** and
   why — one line per chart, empty control side, NaN differences.
5. That this blocker is **independent of, and larger than, the FIX-02
   DEGENERATE-GATE**: even a perfect carrier-nation mapping changes nothing,
   because there is no airborne time to attribute to any nation.
6. The FIX-02 exclusion base reconciliation of section 7, so the two departure
   counts in this round's record are not read as a contradiction.

**The decision the human must make (one choice, everything else waits on it):**

> The Phase-1 outcome variable does not exist in the Phase-1 data source for
> the population the design compares. Choose one:
> **(A)** Re-scope Phase 1 to the extensive margin (departures, seats,
> passengers, entry/exit) for all nations — keeps the cross-nationality
> comparison, loses "excess airborne time";
> **(B)** Re-scope Phase 1 to US-carrier-only route-exposure DiD — keeps
> airborne time and the placebo, loses operator-nationality identification;
> **(C)** Accelerate Phase 2: commission the attended OpenSky pull now and make
> ADS-B the primary source for the wedge, with T-100 demoted to a volume/
> extensive-margin companion;
> **(D)** Find a source that reports foreign-carrier block or airborne time
> (Eurocontrol, OAG/Cirium schedules-and-actuals, commercial OOOI).
>
> (A), (B) and (C) all touch starred PROJECT.md sections and belong in
> DECISIONS.md. My reading: (C) is the design the project was written for and
> (A) is the honest interim deliverable; (B) is a different paper.

No agent should proceed to FIX-04, FIX-05 or NEW-06 as currently written
without this ruling. Building FIX-04/FIX-05 in their US-only form is harmless
and useful and may continue under the existing reporting embargo; NEW-06
should be held.

**VERDICT: FAIL**

---

## FIX-03 (cycle 2) review — 2026-09-02 00:51 UTC

Focused re-review of the six required actions from the cycle-1 FAIL. Cycle-1
substantive results are not re-litigated; I re-ran them only as a determinism
and regression check, and they are unchanged (byte-identical).

### 1. Every value I specified reproduces — exactly, from the raw CSVs

I rebuilt the whole year x CARRIER_GROUP table myself from
`data/raw/t100/*.csv` (36 files, 2,662,470 rows) with my own read path, then
outer-merged against `coverage_by_carrier_group.csv`: **147 rows, all `both`,
0 left_only, 0 right_only, max abs difference 0.0 on every one of the 15
value columns** (`n_rows, n_dep_gt0, n_air_gt0, n_air_zero, n_air_null,
n_ramp_gt0, n_ramp_zero, n_ramp_null, n_depsched_gt0, n_mail_gt0,
n_seats_gt0, n_pax_gt0, n_dist_gt0, departures, is_us_carrier_group`).

Each specified value, recomputed:

- `CARRIER_GROUP` set = **{0, 1, 2, 3, 7}**, zero nulls; group 7 = **{2002,
  2003, 2004}**, 382 rows. Reproduced in the CSV exactly.
- Group 0: **1,133,545 rows; `AIR_TIME>0` = 0; `RAMP_TO_RAMP>0` = 0;
  `AIR_TIME` nulls = 0; `RAMP_TO_RAMP` nulls = 0; `n_air_zero` = 1,133,545.**
  (`coverage_by_carrier_group.csv`, the 36 rows with `carrier_group==0`.)
- Excluded population: `coverage_matching_exclusions.csv` now splits by
  `CARRIER_GROUP` — **70,120 group-0 rows (99 codes), `n_air_gt0` = 0,
  `share_air_gt0` = 0.0**; **12 US-group rows (8 in group 1, 4 in group 2),
  `share_air_gt0` = 1.0**. Exactly the values I specified. Totals still
  reconcile: 70,132 rows / 1,214,475 departures.
- Column availability, `coverage_column_availability.csv`, 20 rows: every
  `share_gt0` equals `n_gt0/n_rows` to 1.1e-16 and every value reproduces my
  independent count. Foreign (n_rows 1,133,545): AIR_TIME 0.0, RAMP_TO_RAMP
  0.0, DEPARTURES_SCHEDULED 0.0, MAIL 0.0, DEPARTURES_PERFORMED 1.0, DISTANCE
  1.0, SEATS 0.8403830461, PASSENGERS 0.8355248358, PAYLOAD 0.8095443939,
  FREIGHT 0.6519176566. US (n_rows 1,528,925): AIR_TIME 0.9963811175,
  RAMP_TO_RAMP 0.9966316203, DEPARTURES_SCHEDULED 0.7162411498, MAIL
  0.2011923410.

**The assertions are real and they raise.** Mutation-tested, in an isolated
`/tmp` root (no repo file modified):
- flipping the assertion's target group from 0 to 1 (a group that *does*
  report time) → script logs `ASSERTION FAILED ... in 36 year-rows` and
  **exits 1**;
- narrowing `US_GROUP_CODES` to {1,2,3} so group 7 becomes unknown → logs
  `Unexpected CARRIER_GROUP values found: [7] — refusing to guess` and
  **exits 1**.
Carried-forward advisory (same class as FIX-01's): the CSV is written *before*
the assertion returns 1, so a future failing run leaves a stale artifact on
disk next to an exit-1 log.

### 2. The 1,523,392 / 1,523,785 / 1,523,296 "discrepancy" — the implementer's
### account is CORRECT, and my cycle-1 phrasing was the thing that was wrong

Recomputed from the raw CSVs. All three are real, different, correct numbers
with three different denominators:

| number | what it is | where |
|---|---|---|
| 1,528,925 | US-group rows, all of them | `coverage_column_availability.csv`, rows `(us, *)`, `n_rows` |
| 1,523,785 | US-group rows with `DEPARTURES_PERFORMED>0` | `coverage_column_availability.csv`, row `(us, DEPARTURES_PERFORMED)`, `n_gt0`; also `coverage_by_carrier_group.csv`, `n_dep_gt0` summed over US rows |
| 1,523,392 | US-group rows with `AIR_TIME>0`, **unconditional** | `coverage_column_availability.csv`, row `(us, AIR_TIME)`, `n_gt0` |
| 1,523,296 | US-group rows with `AIR_TIME>0` **and** `DEPARTURES_PERFORMED>0` | log only |

My cycle-1 sentence "1,523,392 `AIR_TIME>0` of 1,523,785 departures>0 rows"
silently mixed an unconditional numerator with a conditional denominator. The
implementer was right to refuse to force a match; **no value was adjusted, and
the 96-row gap is real** (96 US-group rows carry `AIR_TIME>0` with
`DEPARTURES_PERFORMED==0`). This is correct bookkeeping, not a discrepancy,
and I record it as such.

The CSVs state their denominators unambiguously: in both files every count
column is a count over the `n_rows` in its **own row**, and no column name or
value implies a departures-conditional base. A reader cannot mistake one for
another.

One residue, non-blocking but binding on the director: **1,523,296 exists only
in `logs/03b_carrier_group_coverage.log`, in no CSV**, so under G9 it is NOT
citable and neither is "99.97% of departures>0 rows". The citable US contrast
is the unconditional 0.9963811175 from `coverage_column_availability.csv`, row
`(us, AIR_TIME)`. Use that one.

### 3. G9 is genuinely solved — `coverage_by_carrier_group.csv` stands alone

Proved, not inspected. I copied the script to an isolated root containing
**only** `data/raw/t100` (symlink), `code/utils.py`, and empty output dirs —
**no `data/interim/`, no `t100_raw.parquet`, no `carrier_nation.parquet`, no
FIX-02 CSV**. It ran to completion and wrote a `coverage_by_carrier_group.csv`
whose md5 (`81f67452c12f73458086a76be4ba69e3`) is **identical to the committed
round-folder file**. The headline is therefore provable from raw BTS text with
zero dependence on the BLOCKED FIX-02 mapping, and on FIX-01's parquet only
coincidentally. Cycle-1's blocking finding 1 is fully cured.

### 4. Actions 4, 5, 6

- **Action 4 (rename): met.** `n_segment_months` appears nowhere in `code/`,
  `rounds/`, `paper/`, `slides/`, `human-readable/` (repo-wide grep; only
  historical prose in STATUS.md / this file). `coverage_audit.csv` and
  `coverage_by_corridor.csv` both carry `n_rows`; the figure and .tex carry no
  such column. The multiplicity caveat is in `03_coverage_audit.py`'s
  docstring (lines 29-35) and its number is right: matched-sample `n_rows` sums
  to **1,745,448**, and I reproduce **1,027,021** distinct
  `(nation_iso2, YEAR, ORIGIN, DEST, MONTH)` combinations — ratio 1.6996.
  *Two wording residues, carried forward, not blocking:* (i) the docstring
  states the key as "(ORIGIN, DEST, MONTH)" without the nation-year qualifier —
  unqualified, that count is 81,413, and `(ORIGIN, DEST, YEAR, MONTH)` is
  839,612, so the stated key does not produce the stated number; (ii)
  `tables/tab_coverage_audit.tex`'s caption still defines "cov." as "share of
  passenger **segment-months** with AIR_TIME > 0" (twice, incl. the home0
  gloss), which is the exact mislabel the rename removed from the CSVs. Shares
  are unaffected (coverage is binary 0.0/99.8), so no number changes — but this
  .tex must not enter `paper/` until the caption says rows.
- **Action 5 (title clipping): met.** I inspected the rendered PNG, not the
  source string. The title now wraps to three lines and **"US-touching
  international segments" is fully legible**, as is the closing paren of
  "(* = MATCH-SENSITIVE: RU, IR -- FIX-02 DEGENERATE-GATE)". Pixel scan of the
  heatmap body finds exactly **one** green band (y 96-116 = the US row) and no
  other; consistent with `coverage_audit.csv`, where the 36 cells with
  `share_air_time_valid > 0` are all `nation == US` (min 0.9923, max 1.0).
- **Action 6 (directions): met.** `coverage_by_corridor.csv` has a
  `directions` column, single value in all 1,037 rows:
  `"both (US-origin outbound + US-destination inbound pooled)"`.

### 5. Determinism, gates, checkers

- **Determinism verified by me, not accepted from the log.** md5'd all 8
  artifacts, re-ran `03_coverage_audit.py` (exit 0) and
  `03b_carrier_group_coverage.py` (exit 0), `md5sum -c`: **8/8 OK**
  (4 pre-existing CSVs + 2 new CSVs + .tex + .png). The 03b CSV additionally
  reproduces byte-identically from a different filesystem root (section 3).
- `python code/99_validate_outputs.py` → `18 CSVs scanned, 0 FAIL, 0 WARN`,
  **exit 0**. 18 = every CSV in `rounds/round-1-t100-panel/`; both new files
  are inside the active round folder and inside the directory-wide scan. No
  result CSV was written outside the round folder.
- `python code/98_check_trino_usage.py` → `0 FAIL`, **exit 0**. No
  `logs/opensky_queries.log` and none required: no OpenSky/Trino/network access
  this round; `03b` imports only pandas and `utils`, and reads only
  `data/raw/t100/`. `data/raw/` unmodified (`git status` clean under it).
- **Gates. G1-G4:** N/A — no regression, no p-value/SE/coef column exists in
  any of the 18 CSVs (checked every file, not a manifest). No degenerate-
  inference pathology is even possible this round. **G5: PASS** — swept every
  `share*/rate*/precision*` column in all 18 CSVs; zero values outside [0,1];
  the three-way air/ramp shares sum to 1. **G6: unchanged and correct** — set
  equality re-verified, |cells with `share_air_time_valid < 0.50`| = 2,213 =
  |`coverage_excluded_cells.csv`|, **symmetric difference empty**; max
  `share_air_time_valid` among excluded = **0.0**; departures-weighted failure
  share **0.3976470290**; **0 of 908 non-US corridor cells pass**. **G7:**
  unchanged, still BLOCKED-NEEDS-HUMAN / DEGENERATE-GATE; FIX-03 complies with
  the matched-methods restriction. **G8:** N/A. **G9: NOW MET** — see
  section 3.
- No all-null columns anywhere except the two known FIX-01 note columns in
  `ingest_rowcounts.csv`. Zero empty cells in the two new CSVs; the three blank
  `UNIQUE_CARRIER` cells in `coverage_matching_exclusions.csv` are the
  `null_carrier_code` category and are meaningful, not missing.
- No fancy estimator: this task is counts and shares. Rule-12 benchmark
  requirement is not engaged.
- No hand-typed number in the .tex (auto-generated header line present), the
  figure, or the CSVs. **One violation to clean up:** STATUS.md's FIX-03
  cycle-2 entry contains the typed phrase "off by 96 rows" — a result number in
  a state file, which the conventions forbid without a CSV trace, and 96 is in
  no CSV. One-line edit; not worth a cycle, but fix it at round close.

### 6. Findings

1. **[cured]** Cycle-1 finding 1 (headline not citable under G9) is fully
   resolved and proven mapping-independent by isolated-root execution.
2. **[cured]** Cycle-1 findings 2, 3, 4, 5 — rename, excluded-population
   coverage, `directions`, figure title — all met and verified in the rendered
   artifact where relevant.
3. **[carry-forward, blocks paper use only]** `tables/tab_coverage_audit.tex`
   caption still calls the denominator "segment-months" in two places; the unit
   is rows (1.70x multiplicity). Fix before this table is copied into `paper/`.
4. **[carry-forward]** `03_coverage_audit.py` docstring states the
   distinct-segment-month key without the nation-year qualifier; the number
   1,027,021 is right, the stated key is not.
5. **[binding on the director]** 1,523,296 and any "99.97%" phrasing are
   log-only and NOT citable under G9. Cite 0.9963811175 instead.
6. **[advisory]** `code/03_audit/` and all 8 FIX-03 artifacts are still
   untracked; the coordinator must commit them (same handoff as FIX-02's
   `code/02_build/`).
7. **[advisory]** STATUS.md "off by 96 rows" — typed result number, no trace.
8. **[unchanged, for the human]** `coverage_by_carrier_group.csv` /
   `coverage_column_availability.csv` cover **all rows, all service classes**;
   `coverage_audit.csv` covers **class-F passenger, departures>0, matched
   carriers**. Both are correct; FINDINGS must name the sample beside every
   number, because the two bases differ by ~900k rows.

### 7. HEADLINE BLOCK for ROUND_01_FINDINGS.md (traced, G9-compliant)

> **Foreign carriers never report airborne time in this T-100 extract — in any
> of the 36 years, in any row.** From BTS's own `CARRIER_GROUP` field read
> straight from the 36 raw year files, with no dependence on this project's
> carrier-nation mapping (which is BLOCKED):
>
> - Foreign carrier group (`CARRIER_GROUP == 0`): **1,133,545 rows**, of which
>   **0** have `AIR_TIME > 0` and **0** have `RAMP_TO_RAMP > 0`; **0** are null
>   in either field — every value is a literal zero.
>   *(coverage_by_carrier_group.csv, the 36 rows with `carrier_group == 0`;
>   columns `n_rows`, `n_air_gt0`, `n_ramp_gt0`, `n_air_null`, `n_ramp_null`,
>   summed. All service classes, all rows.)*
> - Foreign carriers report **volume, never time**: `DEPARTURES_PERFORMED`
>   share > 0 = **1.0**, `DISTANCE` **1.0**, `SEATS` **0.8403830461**,
>   `PASSENGERS` **0.8355248358**, `PAYLOAD` **0.8095443939**, `FREIGHT`
>   **0.6519176566**; while `AIR_TIME` **0.0**, `RAMP_TO_RAMP` **0.0**,
>   `DEPARTURES_SCHEDULED` **0.0**, `MAIL` **0.0**.
>   *(coverage_column_availability.csv, rows `(foreign, <column>)`, column
>   `share_gt0`; denominator `n_rows` = 1,133,545 in every one of those rows.)*
> - US carriers, same files, same columns: `AIR_TIME` share > 0 =
>   **0.9963811175** (1,523,392 of 1,528,925 rows).
>   *(coverage_column_availability.csv, row `(us, AIR_TIME)`, columns `n_gt0`,
>   `n_rows`, `share_gt0`.)*
> - The `CARRIER_GROUP` values present are **{0, 1, 2, 3, 7}**; group 7 appears
>   only in **2002-2004** (382 rows).
>   *(coverage_by_carrier_group.csv, columns `carrier_group`, `year`,
>   `n_rows`.)*
> - It is **not** an artifact of the carrier-nation mapping's exclusions: of the
>   rows FIX-03 drops as unmatched/refused, the **70,120** foreign-group rows
>   have `share_air_gt0` = **0.0** and the **12** US-group rows have **1.0**.
>   *(coverage_matching_exclusions.csv, rows grouped by `CARRIER_GROUP`;
>   columns `n_rows`, `n_air_gt0`, `share_air_gt0`.)*
> - In the headline analysis sample (class-F passenger, departures > 0, matched
>   carriers): **2,213 of 2,249** operator-nation x year cells fail G6, every
>   one at `share_air_time_valid` **exactly 0.0**; the **36** cells with any
>   coverage are all `nation == US` (0.9923-1.0). Departures-weighted, the
>   failing cells are **0.3976470290** of all departures.
>   *(coverage_audit.csv, columns `nation`, `year`, `share_air_time_valid`,
>   `dep_total`, `gate_g6_pass`; coverage_excluded_cells.csv, 2,213 rows.)*
> - On the NEW-06 anchor corridors: **0 of 908** non-US corridor cells pass G6 —
>   identically on the three treated corridors and on the European placebo.
>   *(coverage_by_corridor.csv, rows with `nation != "US"`, column
>   `gate_g6_pass`; both directions pooled, see column `directions`.)*
>
> **Interpretation to state plainly:** this is BTS's foreign-carrier reporting
> schedule (T-100(f) collects volume, not block/airborne time), not a defect of
> our download — the columns are in every file's header and are full for US
> carriers in those same files, the export writes zeros rather than blanks, and
> the absent set is exactly {airborne time, ramp-to-ramp, scheduled departures,
> mail} for 36 consecutive years without one exception. Confirming this against
> BTS's published T-100(f) data-element list needs an attended web session; it
> is a confirmation step, not a doubt.
> **Consequence:** this blocker is independent of, and larger than, the FIX-02
> DEGENERATE-GATE. A perfect carrier-nation mapping would change nothing,
> because there is no airborne time to attribute to any nation.

### 8. Ruling for FIX-04, FIX-05, NEW-06 (restated, still binding)

Two independent constraints stack: the **FIX-02 embargo** (G7
BLOCKED-NEEDS-HUMAN — build allowed, nation-level reporting not) and the
**FIX-03 fact** (the outcome variable does not exist for any non-US operator).

- **FIX-04 — MAY BUILD, MAY NOT REPORT nation-level numbers.** Matched
  carriers only, `icao` tier dropped, precision flags carried. Panel keys and
  the extensive margin (`departures_performed`, `distance`, `seats`,
  `passengers`, `n_carriers`, `n_aircraft_types`, `covid_flag`) are valid for
  all 93 nations. **Hard requirement:** every airborne/ramp-derived column must
  be constructed as **missing** for non-US cells and must carry an explicit
  availability flag. The source zero-fills, so any mean, sum or ratio taken
  over raw `AIR_TIME` will silently report foreign flights as taking zero
  minutes — that is the single most dangerous error available in this round and
  I will look for it first. `DEPARTURES_SCHEDULED` is US-only too (share 0.0
  foreign); do not build a load/completion-factor variable on it for foreign
  cells. Must aggregate over aircraft types rather than assume cell-key
  uniqueness (FIX-01 advisory 4).
- **FIX-05 — MAY BUILD, under the same embargo, as an explicitly all-US
  computation.** Baselines, MAD, excess and the bidirectional sum are all
  computable, but every surviving cell and both legs of every bidirectional
  pair are US operators. It must be labelled "US carriers' airborne time on
  US-touching international segments", never "the carrier-nation wedge". G8
  assertions (no COVID month in any baseline; >= 2 obs per baseline) must be in
  code and must raise. Note the COVID coarsening carried from FIX-03
  (`COVID_YEARS = {2020, 2021}` vs PROJECT.md's 2020-03..2021-12) — at monthly
  granularity FIX-05 must use the true window, not inherit the annual one.
- **NEW-06 — MAY NOT SHIP AS COMMISSIONED.** The airborne-time wedge figure is
  not computable: 0 of 908 non-US corridor cells pass G6, so each corridor chart
  would carry exactly one line (US) and the treated-minus-control column would
  be NaN in every month by construction — the control side is empty, not small.
  Do not ship one-line charts implying a comparison the data cannot make.
  It **may** be re-scoped to an **extensive-margin** wedge (departures, seats,
  passengers, entry/exit), which is fully populated for foreign carriers — but
  that changes the outcome variable, so it requires a written director
  commission in the round file naming the new outcome and its ex-ante
  rationale, must ship the raw-means benchmark, must ship a
  precision-excluded version alongside, and corridor 1 / ICN may be computed
  but not reported while G7 is blocked. Any airborne-time version stays
  BLOCKED.
- **Unchanged and above all three:** the human's (A) extensive-margin re-scope
  / (B) US-only route-exposure DiD / (C) accelerate OpenSky / (D) new data
  source decision is still open. All touch starred PROJECT.md sections. No
  agent may pick one; FIX-04 and FIX-05 building in the forms above is
  compatible with every branch and does not pre-commit the choice.

**VERDICT: PASS**

---

## FIX-04 review — 2026-09-02 01:20 UTC

Scope: `code/04_panel/04_build_panel.py`, `data/interim/panel_monthly.parquet`,
`data/interim/panel_extensive.parquet`, `rounds/round-1-t100-panel/desc_sample.csv`,
`rounds/round-1-t100-panel/panel_filter_log.csv`. I rebuilt the entire panel
independently from `t100_raw.parquet` + `carrier_nation.parquet` with my own
read/merge/aggregate path and compared cell by cell.

### Checks run (recomputed, not reread)

**Full independent reconstruction of `panel_monthly.parquet`.** Outer-merged my
rebuild against the shipped parquet on `(origin, dest, nation, year, month)`:
**1,026,729 rows, all `both`, 0 left_only, 0 right_only**, and **max abs diff
0.0** with **0 null-pattern mismatches** on `airborne_min_mean`,
`air_time_total`, `distance`, `fleet_share_top_type`, `share_dep_home0`,
`departures_performed`, `n_carriers`, `n_aircraft_types`, `n_rows_raw`.
Every implementer row count reproduces: 1,026,729 cells; `cell_ok` **517,076**;
`cell_ok_8` **476,207**; `cell_ok_precision` **515,983**.

**Structural-zero guard — the item I said I would look for first. It holds.**
- `panel_monthly`, `nation != 'US'`: **457,018 cells**, and for each of
  `air_time_total`, `ramp_total`, `airborne_min_mean`, `ramp_min_mean` the
  non-null count is **0** and the `== 0` count is **0**. Not zeros dressed as
  data; genuinely absent. `airborne_available` and `ramp_available` are True on
  **0** of the 457,018. `departures_scheduled` (also US-only per my FIX-03
  ruling) is null on all 458,129 non-reporting cells.
- Row level: on the matched passenger sample (1,749,156 rows) I find **0 rows**
  with `CARRIER_GROUP ∈ {1,2,3,7}` mapped to a non-US nation. Confirmed against
  the raw field, not the mapping.
- No laundering downstream: the only columns that touch `AIR_TIME`/
  `RAMP_TO_RAMP` are the five nulled ones. `distance`, `fleet_share_top_type`,
  `share_dep_home0`, `n_carriers`, `n_aircraft_types` are volume-side and
  legitimately populated for foreign cells. No ratio, share or fleet variable
  divides by or multiplies a structural zero anywhere in either parquet.
- **Mutation tests (5), isolated root at `/tmp/fix04mut` with only the input
  parquets symlinked, all writes redirected to /tmp:** baseline exit 0 and
  identical figures; (A) `US_GROUP_CODES = {0,1,2,3,7}` → **exit 1**, logs
  "GUARD VIOLATED: 741262 matched rows"; (B) `has_time = departures_performed
  > 0` → **exit 1**, "GUARD VIOLATED at cell level: 457018 non-US cells with a
  non-null airborne value" (this is the catastrophic branch — every foreign
  cell would have shown `airborne_min_mean = 0.0`; the guard stops it before
  the parquet is written); (C) `d = intensive.drop_duplicates()` → **exit 1**
  on the `n_rows_raw` assertion; (D) `PANEL_END = (2025,11)` → **exit 1**,
  "VERIFY FAIL: panel_extensive has 8790245 rows, expected 8810640"; (E)
  `desc_sample` built on `cell_ok_8` → **exit 1** on the TOTAL assertion.
  All five assertions are real, not decorative.

**VERIFY item 1** — `desc_sample.csv` TOTAL `n_cells` = **517,076**; parquet
rows with `cell_ok == True` = **517,076**. PASS.

**VERIFY item 2** — `panel_extensive.parquet` = **8,810,640 rows**; distinct
`(origin, dest, nation)` triples = **20,395**; every triple has exactly **432**
rows; 432 distinct year-months spanning 1990-01..2025-12; 20,395 × 432 =
8,810,640. PASS. **Judgment on the reading:** the implementer's definition is
the correct one. The round file's deliverable text is unambiguous — "every
`(origin, dest, nation)` ever observed × every month 1990–2025" — and the
VERIFY checkbox's "routes × nations observed" is loose shorthand for the same
thing. The alternative reading (13,678 routes × 93 nations × 432 months) is
**549,527,328 rows**, 98.4% of them combinations no nation ever flew; it is not
a panel, it is a fabrication. Triple reading accepted.

**Filter-log reconciliation (item 3).** Recomputed from the source: passenger
2,662,470 → 1,819,635 (−842,835); `icao` 347; unmatched 57,678 + refused
11,939 = 69,617; null carrier 515; matched 1,006,123 + 725,704 + 17,329 =
1,749,156; departures>0 → 1,745,101 (−4,055). Every logged number matches
exactly, the chain closes to 2,662,470 with no residual, every row has a
`reason`, and I verified the three drop classes are mutually disjoint (a
non-null carrier with no `match_method` would trip the `unexpected` branch;
there are none). Cell-level rows are flags, not drops, and partition exactly:
457,018 + 52,635 = 509,653 = 1,026,729 − 517,076.

**Aggregation without a uniqueness assumption (item 4).** `n_rows_raw` sums to
**1,745,101**, exactly the detail-row count, asserted in code and reproduced by
me. No `drop_duplicates` anywhere. My reconstruction independently reproduces
`n_carriers`, `n_aircraft_types` and `n_rows_raw` with max diff 0, including on
cells fed by up to 60 detail rows. FIX-01 advisory 4 is discharged.

**covid_flag (item 5).** Exactly **22 months** flagged, 2020-03 through
2021-12, all-or-nothing within each month; 2020-01 and 2020-02 are 0.0,
2020-03 is 1.0, 2021-12 is 1.0, 2022-01 is 0.0. True monthly window, no annual
coarsening. PASS. Present on both parquets.

**icao tier and precision flags (item 6).** `match_method == 'icao'` appears
**0 times** in the panel population; the 347 rows are dropped and logged.
`nation_precision_flag` and `cell_ok_precision` are present and correctly
constructed (25,842 flagged cells; RU 7,659 and IR 5,003 lead, per my FIX-02
condition). `cell_ok_precision` = 515,983 = 517,076 − 1,093.

**G-gates.** G1 PASS — no null cell keys, no duplicate cell keys on
(origin,dest,nation,year,month), 1,026,729 unique; the only nulls in the file
are the 458,129 deliberately-absent time cells. G2/G3/G4 N/A (no estimation in
this task). G5 PASS — `fleet_share_top_type` ∈ [0.1741, 1.0] with 0 nulls,
`share_dep_home0` ∈ [0.0, 1.0] with 0 nulls. G6 inherited PASS and verified:
`coverage_ok` is **exactly** the indicator `nation == 'US'`; all 36 US
nation-years pass, **0 of 2,213** non-US nation-years pass; 0 panel
nation-years missing from `coverage_audit.csv`. G7 remains
BLOCKED-NEEDS-HUMAN; no nation-level number is reported out of this task.

**Standard.** `python code/99_validate_outputs.py` → **20 CSVs scanned, 0 FAIL,
0 WARN, exit 0**; both new CSVs are inside `rounds/round-1-t100-panel/` and
covered by the scan. `python code/98_check_trino_usage.py` → exit 0. No
network/Trino/OpenSky reference in the script. `setup_logger` and `log_merge`
used on both merges (the carrier merge logs 1,819,120 both / 515 left_only;
the extensive grid merge logs 8,810,640 left / 1,027,372 right). Re-run is
**byte-identical** on all four artifacts (sha256 compared before/after).
No result number is typed anywhere in the CSVs — all generated.

### BLOCKING defects

**B1. The task's own headline sub-finding is false, and it is committed to the
repo.** The docstring (lines 25–27) and the runtime log both say a handful of
US-mapped codes "`VX, B0, ASQ`" carry `CARRIER_GROUP == 0`, and the implementer
reported this to me as "a US-flag carrier filing on the foreign schedule … if
real the director should carry it". It is not real, and the truth is the
opposite. The three codes actually present are:

| code | `CARRIER_NAME` in T-100 | actual nationality | rows | departures |
|---|---|---|---|---|
| `VX (1)` | Aces Airlines | **Colombia** (Aerolíneas Centrales de Colombia) | 795 | 19,410 |
| `B0` | Dreamjet SAS Dba La Compagnie | **France** | 480 | 10,871 |
| `WO` | SWOOP Inc. | **Canada** (WestJet's ULCC) | 496 | 4,887 |

`ASQ` appears **0 times** in the matched passenger sample (6 times in all of
T-100). `VX` proper (Virgin America, 2010–2018, `us_by_construction`, groups
1/2/3) is a genuine US carrier and is not one of these. These are not US
carriers on the foreign schedule — they are **three foreign carriers that
FIX-02 mis-mapped to nation `US`** via IATA-code collisions, and BTS's own
`CARRIER_GROUP == 0` is telling us so. FIX-02 already documented the collisions
(`carrier_nation_precision_audit.csv`, rows `VX (1)`/`B0`/`WO`:
`home_country_dep_share` **0.0** on all three, `candidate_names` literally
"Virgin America (United States)", "Aws express (United States)", "World Airways
(United States)"), and their observed endpoint countries are CO/DO, FR/GB/ES/
IT/BE/IE/MA/SK/SX and CA respectively. The *code* is unaffected — the guard
keys on `CARRIER_GROUP`, not on the nation label, so it does the right thing —
but this narrative would have entered ROUND_01_FINDINGS.md as a discovered fact
about US carriers. It is a fabricated fact and it reverses a G7 precision
failure into a benign curiosity. Fix the docstring and the log line; carry the
true version.

**B2. The airborne denominator is computed and then thrown away, and
`departures_performed` silently mixes reporting and non-reporting departures.**
`dep_for_time` (line 294, the denominator of `airborne_min_mean`) is dropped at
line 308. `departures_performed` sums **all** matched rows including the
`CARRIER_GROUP == 0` ones. Consequence, recomputed: **1,681** `cell_ok` US
cells contain at least one mis-mapped foreign departure — 1,041 pure cells
(caught by `cell_ok_precision`, `share_dep_home0 == 1.0`) plus **640 mixed
cells, of which 588 survive `cell_ok_precision`** because their foreign share
sits below the 0.50 threshold (median 0.2559, **max 0.9688**). **35,051**
foreign departures sit inside `cell_ok` US cells, 14,975 of them inside mixed
cells where `airborne_min_mean` was computed on a strictly smaller denominator
than `departures_performed`. Any departures-weighted mean of `airborne_min_mean`
in FIX-05 or NEW-06 — which is exactly what NEW-06 commissions — will weight
those cells by a count that includes flights excluded from the number being
weighted, and in the worst cell 96.9% of the weight is foreign. There is no
column in the panel that lets a downstream task see this. It costs one line to
keep.

**B3. Part 0's "missing is not zero" rule is violated inside the US sample.**
Part 0: "Rows with `DEPARTURES_PERFORMED > 0` and `AIR_TIME = 0` or null are
reporting gaps … never imputed." **60** time-eligible detail rows (483
departures) report `AIR_TIME == 0` with departures > 0 and are summed into
their cells as a literal zero. Result: **32 US cells** where every eligible row
is a gap get `airborne_min_mean = 0.0` **with `airborne_available = True`** —
**19 of them are `cell_ok == True`** — plus **26 diluted cells** (25 `cell_ok`)
where real minutes are averaged against zero-minute gap departures, median
dilution 0.2105, **max 0.3867**. This is the same fabricated-zero pathology the
guard was built to stop, surviving at the US-cell level because the guard is
keyed on nation rather than on the reported value. The magnitude is tiny
(483 of 24,320,765 US-eligible departures, 0.002%) but a 0-minute mean flight
is the extreme left tail of FIX-05's `excess_min`, it will set p1 on any thin
route, and the rule is written in the round file in so many words.
(Note: the `.fillna(0.0)` calls on lines 252–254 are no-ops — the eligible
population has **0** nulls in `AIR_TIME`, `RAMP_TO_RAMP` and
`DEPARTURES_SCHEDULED`. The defect is the reported zeros, not the fill.)

### ADVISORIES (not blocking; carry them)

**A1. Extreme values — my ruling on item 7. `9999` is NOT a sentinel here, and
that matters.** I inventoried every `9999` in the raw source: 25 rows with
`AIR_TIME == 9999` and 22 with `RAMP_TO_RAMP == 9999`, 41 of them passenger
class. Because `AIR_TIME` is a **monthly total**, 46 of the 47 are entirely
unremarkable — e.g. NW BOS–AMS 1990-10, 28 departures, 9999 minutes = 357
min/departure over 3,457 miles = 581 mph. Exactly **one** row is impossible:
`M5` (Kenmore Air) `YGE→LKE` 2025-10, **1 departure**, `AIR_TIME 9999`,
`RAMP_TO_RAMP 10004`, distance 207 — 166 hours for a 207-mile seaplane hop.
The ramp value being 9999+5 suggests the corrupted field is
`DEPARTURES_PERFORMED`, not `AIR_TIME`. That cell is already `cell_ok == False`
(1 departure < 4). So: **benign raw-data passthrough for a construction task**,
and FIX-05 must **not** screen on the literal value 9999 — that would delete 46
good cells. The real screen is implied ground speed. Quantified for FIX-05:
among 516,035 `cell_ok` cells with airborne data, implied speed
(`distance / (airborne_min_mean/60)`) has median 467.3 mph, p1 176.4, p99
589.2; **162 cells (0.0313%)** are below 50 mph or non-finite, concentrated on
seaplane/short-hop routes (`KEH↔YWH` 27 cells at ~49 mph, `FRD↔YYJ`, `VIJ↔STT`,
`FXE↔SAQ/CCZ/TZN`, `NSB↔FLL`); **80 `cell_ok` cells** exceed 1,000 min/departure,
worst `NSB→FLL` 2018-02 at 2,433 min/departure over 59 miles. FIX-05's 1/99
winsorization is *within route × direction*, so a persistently-inflated route
cancels through its own baseline — but the 19 zero cells (B3) and the
non-finite-speed cells do not. **Contamination FIX-05 must handle explicitly,
by an implied-speed screen documented in `desc_outcomes.csv`, not by a 9999
rule.**

**A2. `distance == 0`.** **50 panel cells**, of which **2** are `cell_ok`
(`SWL↔WFB`, 2002-04, 24 min mean, 24 departures) — 3.9e-06 of the `cell_ok`
sample, on 2 distinct routes. 253 raw rows carry `DISTANCE == 0` (86
passenger). Benign passthrough; `distance` is never a denominator in FIX-04.
FIX-05/NEW-06 must not divide by it.

**A3. The extensive margin's entry/exit flags are mostly seasonality, not
market entry/exit.** This is the output my FIX-03 ruling called "the round's
most valuable", so it needs saying plainly. Of **80,260** exits, **63,255
(78.8%)** are followed by a later re-entry on the same triple; **50.9%** of
exits re-enter within 12 months and **23.1%** within 3 months (median gap 7
months). **58.8%** of the 20,395 triples have more than one entry (mean 4.10,
max 88), and the median triple is active in only **5** of 432 months, with
**46.2%** active in ≤3 months ever. `months_since_exit` correctly resets to 0
at each exit (verified: 80,260 zeros, exactly matching `exit_flag`; NaN on all
1,026,729 active rows and on all pre-entry rows). The mechanics are right; the
economics are not what the labels suggest. Any later event study using
`exit_flag` as "the nation stopped serving this route" would be ~79% noise. A
spell-based definition (exit requires k consecutive inactive months) is needed
before this variable carries any weight.

**A4. 311 routes vanish without a cell-level log row.** 13,989 routes appear in
the passenger population; 13,678 survive into `panel_extensive`. The 311
missing ones are served exclusively by unmatched/icao/null carriers, so they
have no nation and cannot form a triple — necessary, but it is a drop with a
reason and belongs in `panel_filter_log.csv` at the route level (41,348
departures, 0.099% of passenger departures). The round file's gate is "every
drop … has a reason"; this drop has no row.

**A5. Write-before-assert, second occurrence.** `desc_sample.csv` is written
(line 513) before its TOTAL assertion (line 519), and `panel_monthly.parquet`
is written (line 396) before the `panel_extensive` VERIFY (line 444). Under
mutations D and E the script correctly exits 1 — with a wrong CSV and a
parquet already on disk. Same pattern flagged as FIX-01 advisory 1 and still
open.

**A6. Cell-level filter-log framing.** `min_cell_size_4` reports `n_before =
1,026,729 → n_after = 974,094`, but the 52,635 dropped are counted only within
`coverage_ok` cells. The arithmetic is right and the `reason` column says so;
the `n_before` column reads as a sequential chain that it is not.

**A7. Two COVID windows exist.** FIX-04 uses PROJECT.md line 74 / Part 0's
baseline-exclusion window 2020-03..2021-12 — correct. PROJECT.md line 142 also
defines a wider *event* flag window 2020-01..2022-01. NEW-06 must not conflate
them.

**A8. Minor data-quality notes for the record.** `ramp_min_mean <
airborne_min_mean` in **4** of 568,600 cells (ramp-to-ramp must exceed air
time). `departures_scheduled == 0` with departures performed > 0 in **23,565**
cells (60,248 raw rows) — genuine in T-100 (extra sections), but a completion
factor built on it would be wrong, and in the 640 mixed cells the numerator and
denominator have different populations (B2). `n_carriers` counts reissue
suffixes as separate carriers (`VX` vs `VX (1)`).

**A9. Deliverable wording.** The round file asks `panel_extensive` for "entry
month, exit month(s)"; the implementer delivered `entry_flag`/`exit_flag`
indicators. Informationally equivalent and I accept it, but the FINDINGS should
say so rather than leave a reader hunting for a month column.

**A10. Not yet committed.** `code/04_panel/`, `logs/04_build_panel.log`,
`desc_sample.csv` and `panel_filter_log.csv` are untracked. Commit after the
required actions land.

### Required actions

1. Correct the false carrier identification (B1) in the `04_build_panel.py`
   docstring and in the runtime log line. Name the three codes as they appear
   in the data (`VX (1)`, `B0`, `WO`), give their T-100 `CARRIER_NAME`s, state
   that they are **foreign carriers mis-mapped to `US` by FIX-02 IATA
   collisions** (traceable to `carrier_nation_precision_audit.csv`,
   `home_country_dep_share == 0.0` on all three), and remove `ASQ`. Do not
   describe them as US carriers anywhere. Testable: `grep -c ASQ
   code/04_panel/04_build_panel.py` returns 0, and the log line names all three
   real codes.
2. Retain the airborne denominator on `panel_monthly.parquet` as its own
   column (`departures_time_eligible`, = the current `dep_for_time`), and add
   `departures_non_reporting = departures_performed − departures_time_eligible`
   or an equivalent. Assert in code that
   `departures_time_eligible <= departures_performed` and that it is 0 on every
   non-US cell. Testable: both columns present; the recomputed count of
   `cell_ok` cells with `departures_non_reporting > 0` equals **1,681**.
3. Honour Part 0 on within-US reporting gaps (B3): exclude time-eligible rows
   with `AIR_TIME == 0` from **both** the numerator and the denominator of
   `airborne_min_mean` (same for `RAMP_TO_RAMP == 0` and `ramp_min_mean`), so
   an all-gap cell gets `NaN` and `airborne_available == False` rather than
   0.0/True. Log the excluded rows as their own named step in
   `panel_filter_log.csv` with a reason. Testable: after the fix,
   `((airborne_min_mean == 0) & airborne_available).sum() == 0` and the count
   of `cell_ok` cells with `airborne_min_mean == 0` falls from **19** to **0**;
   the new log step shows **60** rows / **483** departures.
4. Add a route/triple-level row to `panel_filter_log.csv` for the **311**
   routes (41,348 departures) that leave `panel_extensive` because every
   carrier serving them is unmatched/icao/null, with the reason stated.
5. Move `desc.to_csv` after its TOTAL assertion and `panel.to_parquet` after
   the `panel_extensive` row-count VERIFY, so a failed run leaves no artifact
   on disk. Re-run mutations D and E to confirm no file is written.
6. Add the extensive-margin churn diagnostic (A3) to the round folder as a CSV
   — exits, share re-entering within 3/12 months, entries per triple, active
   months per triple — so the seasonality caveat is G9-citable rather than
   living in this report. It must not be reported as a result; it is a
   construction caveat.
7. Re-run; confirm byte-identical on everything except the deliberately changed
   columns, validator and trino checker exit 0, and all five mutation tests
   still exit 1.

### For the director to carry into ROUND_01_FINDINGS.md

1. **The panel is built and the structural-zero guard works.** 1,026,729 cells;
   457,018 non-US cells carry a null airborne time, never a zero; verified by
   mutation test that the guard exits 1 rather than shipping 457,018 fabricated
   zero-minute foreign cells. *(panel_filter_log.csv, rows `coverage_ok_g6`;
   desc_sample.csv, row `TOTAL`.)*
2. **The headline sample is 100% US and this is visible on the face of
   `desc_sample.csv`**: `n_nations == 1` in every decade row and in TOTAL. That
   is the FIX-03 blocker made concrete, not a coding choice.
   *(desc_sample.csv, `decade_summary` rows.)*
3. **Three foreign carriers are inside the US sample.** `VX (1)` Aces Airlines
   (Colombia), `B0` La Compagnie (France), `WO` Swoop (Canada) are mapped to
   `US`; 1,681 `cell_ok` cells contain at least one of their departures,
   35,051 departures in total, and 588 of those cells survive
   `cell_ok_precision`. Report it as a G7 precision failure, not as a US-carrier
   curiosity. *(carrier_nation_precision_audit.csv, rows `VX (1)`/`B0`/`WO`,
   column `home_country_dep_share`; panel_monthly `nation_precision_flag`.)*
4. **The extensive margin is the round's surviving asset but its entry/exit
   flags are ~79% seasonality** (A3). State the churn numbers before anyone
   designs an exit event study on them.
5. **Extreme-value inventory for FIX-05** (A1/A2): one impossible cell at 9999
   (already excluded), 80 `cell_ok` cells above 1,000 min/departure, 162 below
   50 mph implied speed, 2 `cell_ok` cells at `distance == 0`, 19 `cell_ok`
   cells at exactly 0 minutes pending required action 3. `9999` is **not** a
   sentinel in this source and must not be screened on.
6. The G6/G7 embargo is intact: no nation-level number is reported out of
   FIX-04, and `cell_ok_precision` is carried so a later task can take the
   strict sample without recomputing it.
7. Carried forward and still open: FIX-01's write-before-assert pattern (A5),
   now in its second script.

### FIX-05 permission

**FIX-05 may NOT proceed on this panel as it stands.** Required actions 2 and 3
change columns FIX-05 reads: action 2 supplies the only correct weight for a
departures-weighted mean of `airborne_min_mean`, and action 3 removes 19
zero-minute cells that would otherwise define the left tail of `excess_min` and
the p1 winsorization cutoff on thin routes. Rebuilding baselines, MAD, excess
and the bidirectional sum twice is worse than one review cycle. Once actions
2, 3 and 7 land and this task passes, **FIX-05 may proceed** on
`panel_monthly.parquet` under the unchanged terms of my FIX-03 ruling: an
explicitly all-US computation, labelled "US carriers' airborne time on
US-touching international segments", never "the carrier-nation wedge", with G8
asserted in code, the true monthly COVID window, and an implied-speed screen
documented in `desc_outcomes.csv`. Nothing else in the panel needs to change —
the keys, the aggregation, the extensive grid, the filter log and both VERIFY
items are correct.

**VERDICT: FAIL**

**Addendum (2026-09-02 01:22 UTC), process flag.** While this review was being
written, FIX-05 artifacts appeared in the working tree — `code/05_outcomes/`,
`logs/05_build_excess.log`, `desc_outcomes.csv`, `baseline_failures.csv`,
`outcome_data_quality_exclusions.csv`, `figures/fig_excess_distribution.png`.
FIX-05 therefore started against the **pre-fix** `panel_monthly.parquet`, i.e.
before the FIX-04 verdict existed and before required actions 2 and 3. Under
the permission ruling above those outputs are void and must be regenerated
after FIX-04 passes; they are not reviewed here and no number in them may be
cited. The overseer touched no file this round other than REVIEW_REPORT.md.

---

## FIX-04 (cycle 2) review — 2026-09-02 01:55 UTC

**Scope.** Focused re-review of the seven required actions from the FIX-04
cycle-1 FAIL. Only `code/04_panel/04_build_panel.py` changed. The cycle-1
substantive verifications (panel rebuild at max abs diff 0, structural-zero
guard, both VERIFY items, filter-log reconciliation to 2,662,470, covid_flag
window) were not re-litigated but were re-confirmed as undisturbed.

### Checks run (every number below independently recomputed by the overseer)

**Independent panel rebuild.** I re-derived every cell from
`data/interim/t100_raw.parquet` + `carrier_nation.parquet` with my own code
(passenger → matched tier {iata, name_exact, us_by_construction} → departures>0
→ groupby(origin,dest,nation,year,month)) and outer-merged against the shipped
`panel_monthly.parquet`: **1,026,729 vs 1,026,729 rows, 1,026,729 `both`, 0
`left_only`, 0 `right_only`**; max absolute difference **0.0** and zero NaN-pattern
mismatches on `airborne_min_mean`, `ramp_min_mean`, `departures_performed`,
`departures_time_eligible`, `air_time_total`, `n_rows_raw`.

**Action 1 (B1, carrier identity).** `grep -c ASQ code/04_panel/04_build_panel.py`
→ **0**. Runtime log line (01:35:10) names `['B0', 'VX (1)', 'WO']` with no
other codes. Identities verified against the raw source, not the prose: in
`t100_raw.parquet`, `VX (1)` = CARRIER_NAME "Aces Airlines", CARRIER_GROUP ∈ {0}
only, 1992–2003, endpoint countries {CO, DO, US}; `B0` = "Dreamjet SAS Dba La
Compagnie", group {0}, 2014–2025, endpoints {BE,ES,FR,GB,IE,IT,MA,SK}; `WO` =
"SWOOP Inc.", group {0}, 2020–2023, endpoints {CA,US}. Distinct from `VX` =
"Virgin America", groups {2,3}, 2010–2018 — the collision the docstring names.
In `carrier_nation_precision_audit.csv` rows 90/110/146: all three
`match_method == iata`, `home_country_dep_share == 0.0`, `flag_home_share_zero
== True`, `top_endpoint_country` = CO / FR / CA respectively, candidate names
"Virgin America (United States)" / "Aws express (United States)" / "World
Airways (United States)". Every clause of the new docstring and log line is
true. `ASQ` (Aerosur (1)) is confirmed icao-tier and therefore not in the panel
at all — the cycle-1 finding stands and the name is gone.

**Action 2 (B2, airborne denominator).** `departures_time_eligible` and
`departures_non_reporting` both present on `panel_monthly.parquet`.
`(departures_time_eligible <= departures_performed).all()` → **True**;
`departures_time_eligible == 0` on all **457,018** non-US cells → **True**.
`cell_ok` cells with `departures_non_reporting > 0` = **1,681** (matches),
carrying **35,051** departures; **588** survive `cell_ok_precision` (matches).

**Action 3 (B3, `AIR_TIME == 0` gaps) and the overcorrection test.**
`((airborne_min_mean == 0) & airborne_available).sum()` = **0**;
`cell_ok` cells with `airborne_min_mean == 0` = **0** (was 19);
`((ramp_min_mean == 0) & ramp_available).sum()` = **0**;
`(air_time_total == 0).sum()` = **0**. From the raw sample I recount the gap
rows: **60 rows / 483.0 departures** with `AIR_TIME == 0` and **8 rows / 9.0
departures** with `RAMP_TO_RAMP == 0` among CARRIER_GROUP-eligible,
departures>0 rows — exactly the two new `exclude_from_time_agg` rows in
`panel_filter_log.csv`.
*Overcorrection audit.* Recomputing both the old (all-eligible denominator) and
new (gap-excluded) means for all 1,026,729 cells: exactly **58** cells change,
**32** to NaN and **26** in value; among `cell_ok`, **19** → NaN (precisely the
19 zero cells) and **25** change value. Nothing else moved. Hand-recomputed
four of them from the underlying detail rows:
`DCA→YYZ 2003-10` — YV 46 dep/2,832 min plus JI (1) 29 dep/**0** air but 1,926
ramp min → new airborne 2832/46 = **61.565** (old 37.760), ramp still uses both
rows (correct: the two gap populations are handled separately, and this cell
proves it);
`CUN→DFW 2013-06` — SY 49 dep/**0** air/8,251 ramp excluded → 26046/184 =
**141.554** (old 111.785);
`FPO→FLL 2021-11` — NK 1 dep/0 air excluded → 220/7 = **31.429** (old 27.500);
`CUN→CVG 2011-11` — sole row U5, 4 dep, 0 air, 642 ramp → airborne **NaN**,
`airborne_available False`, ramp retained. No cell lost data it should have
kept: `departures_performed` is unchanged in every one of the 1,026,729 cells
(max diff 0.0), only `AIR_TIME == 0` rows leave the airborne aggregate.
*Headline counts moved only as much as the fix explains.* `cell_ok` **517,076**
(identical to cycle 1's run, log line 34 vs 167), `cell_ok_8` **476,207**,
`cell_ok_precision` **515,983**, cells **1,026,729**, non-US **457,018**,
`panel_extensive` **8,810,640 = 20,395 × 432** — all unchanged. The only moves:
`cell_ok` cells with airborne data 516,035 → **516,016** (−19), minimum
`airborne_min_mean` 0.00 → **0.61**, and cells below 50 mph implied speed or
non-finite 162 → **143** (−19). Both deltas equal 19 exactly.

**Action 4 (lost routes).** Recomputed from the raw sample: **13,989** passenger
routes before the matched-nation filter, **13,678** after, **311** lost,
**41,348.0** departures across 3,337 rows — matches the new
`routes_lost_no_matched_carrier` row in `panel_filter_log.csv` and
`desc_sample.csv`.

**Action 5 (write-after-assert).** I ran three mutations myself on a redirected
copy of the script (outputs pointed at a scratch dir; no project file touched).
*Extensive-VERIFY mutation* (`expected_rows + 1`): exit **1**, scratch dir
contains **only the log file** — no parquet, no CSV. *Structural-zero-guard
mutation* (`reports_time = True`): exit **1** at 741,262 detected leak rows,
**no artifact written**. *desc-TOTAL mutation* (`len(ok) + 1`): exit **1**,
`desc_sample.csv` and `panel_filter_log.csv` correctly absent — but
`panel_monthly.parquet` (13.8 MB), `panel_extensive.parquet` (5.4 MB) and
`extensive_margin_churn.csv` were already on disk (see finding 3).

**Action 6 (churn CSV).** `rounds/round-1-t100-panel/extensive_margin_churn.csv`,
17 metric rows + `note` column marking it a construction caveat. Recomputed
independently from `panel_extensive.parquet`: entry/exit flags reproduce
bit-for-bit (83,612 entries, **80,260** exits, stored flags identical to mine),
`n_exits_reentering_ever` **63,255** (**0.78813**), `≤3mo` **18,562**
(**0.23127**), `≤12mo` **40,877** (**0.50931**), `entries_per_triple` mean
**4.0996** / median 2 / p90 10 / max **88**, `share_triples_with_gt1_entry`
**0.58838**, `active_months_per_triple` median **5.0** / p90 191 / max 432.
Every one of the 17 values matches to full precision.

**Action 7 (determinism, validators).** I re-ran an unmutated redirected copy of
the script end to end (exit 0) and md5-compared: `panel_monthly.parquet`,
`panel_extensive.parquet`, `desc_sample.csv`, `panel_filter_log.csv`,
`extensive_margin_churn.csv` — **all five byte-identical** to the shipped
artifacts. `python code/99_validate_outputs.py` → exit **0**, "24 CSVs scanned,
0 FAIL, 0 WARN". `python code/98_check_trino_usage.py` → exit **0**.

**Preserved from cycle 1 (re-confirmed, not re-litigated).** Structural-zero
guard at cell level: of 457,018 non-US cells, 0 have a non-null
`airborne_min_mean`, 0 a non-null `ramp_min_mean`, 0 an `available` flag True,
0 `departures_time_eligible > 0`. VERIFY 1: `desc_sample.csv` TOTAL `n_cells`
**517,076** == parquet `cell_ok` count **517,076** (checked from the CSV, not
the assertion); all four decade rows reproduce exactly (1990: 89,473/1,639;
2000: 147,289/2,470; 2010: 180,194/2,621; 2020: 100,120/2,531) and `n_nations
== 1` in every row. VERIFY 2: `panel_extensive` = **8,810,640** rows = 20,395
triples × 432 months, 0 duplicate keys, active rows **1,026,729** == panel_monthly
rows. `covid_flag` covers exactly **22** months, 2020-03 … 2021-12, in both
parquets. Filter-log chain still reconciles to the ingest total 2,662,470.
Economic plausibility of the headline outcome: `cell_ok` airborne mean 276.4
min, median 203.0, p1 33.4, p99 834.6, min 0.61, max 2,433; implied speed
median 467.3 mph, p1 176.4, p99 589.2. Nothing artifactual.

### Gate status

- **G1** (no empty cells; keys) — PASS. No nulls in `(origin,dest,nation,year,
  month)`, 0 duplicate keys, no empty cells in `panel_filter_log.csv` (13×7) or
  `extensive_margin_churn.csv` (17×3); the 13/5 blank cells in `desc_sample.csv`
  are the row_type-specific schema, not missing data.
- **G2/G3/G4** — N/A (construction task; no coefficients, SEs or p-values are
  produced anywhere in FIX-04).
- **G5** — PASS. `fleet_share_top_type` ∈ [0.1741, 1.0], `share_dep_home0` ∈
  [0.0, 1.0]; asserted in code and re-verified from the parquet.
- **G6** — PASS, carried from FIX-03 by merge; 457,018 cells flagged
  `coverage_ok == False`, logged, not dropped.
- **G7** — PASS as constrained: matched tier only, icao/unmatched/refused/null
  dropped with logged reasons; the DEGENERATE-GATE remains
  BLOCKED-NEEDS-HUMAN at FIX-02 and no nation-level number is reported here.
- **G8** — N/A (FIX-05).
- **G9** — see finding 2: three numbers I directed into FINDINGS have no CSV
  trace yet.
- Round-file gate "every drop in `panel_filter_log.csv` has a reason" — PASS;
  all 13 rows carry a non-empty `reason`, including the three new steps.

### Findings

1. **(Must fix before the FIX-04 commit; text only, cannot change a number.)
   The new B2 diagnostic log line misattributes 99.6% of what it counts.**
   `logs/04_build_panel.log` line 166: "*458769 cells … have
   departures_non_reporting > 0 (16110805 departures total) -- these are mixed
   cells whose departures_performed includes carriers mis-mapped to
   nation=='US' (VX (1)/B0/WO …)*". I decomposed it: of the 458,769 cells,
   **457,018 are non-US cells** where every carrier is structurally
   non-reporting and `departures_non_reporting == departures_performed` by
   construction; only **1,751** are US cells. Of the 16,110,805 departures,
   **16,075,637** are foreign and only **35,168** come from the three
   mis-mapped codes. The counts are right; the explanatory clause is false for
   99.6% of the cells and 99.8% of the departures, and a director transcribing
   it would report a 16-million-departure contamination that does not exist.
   This is the same class of error as cycle-1's B1. Rewrite
   `04_build_panel.py` lines 445–449 to split the two populations explicitly
   (structural non-reporting in non-US cells vs the US-cell mis-mapping) and
   re-run; the artifacts must stay byte-identical (verified above that they
   will, the change is log text).
2. **(Must fix before the FIX-04 commit.) G9: `1,681` / `35,051` / `588` exist
   only in a log line, not in any round-folder CSV**, yet they are the numbers
   my cycle-1 FINDINGS block directs the director to report. Add them as rows
   to `panel_filter_log.csv` (e.g. `level=cell, action=flag, step=
   mixed_cells_non_reporting`, with the departures and the
   `cell_ok_precision`-survivor count), so the FINDINGS citation is a real
   `(file.csv, row)` trace. Until that row exists the director may cite only
   **35,168** departures, traceable as the sum of the `departures` column over
   rows `VX (1)`, `B0`, `WO` of `carrier_nation_precision_audit.csv` (19,410 +
   10,871 + 4,887).
3. **(Must fix before the FIX-04 commit.) The stale cycle-1 text is still in a
   file that will be committed.** `logs/` is not in `.gitignore`, and
   `logs/04_build_panel.log` lines 12, 27, 55, 89 and 123 (runs 01:01–01:12)
   still read "*e.g. VX/B0/ASQ-style codes*" — the exact false statement that
   failed cycle 1. Truncate the log and re-run once (40 s; artifacts proven
   byte-identical) so the committed log contains only the corrected run, or
   the reader has to know which timestamps to ignore. Note in mitigation:
   `code/build_run_log.py` reads only `rounds/round-*/**/*.csv`, so no log
   text can reach `FINAL_RUN_LOG.md`.
4. **(Advisory.) Action 5 is met in the letter, and the code comment
   overclaims.** Lines 527–531 assert "*Every write in this script (both
   parquets, desc_sample.csv, the churn CSV, panel_filter_log.csv) happens
   only after ALL validations below … have passed, so a failed run leaves no
   artifact on disk.*" My mutation D shows that is false: a failing
   `desc_sample` TOTAL assertion (line 695) leaves both parquets and the churn
   CSV (19.2 MB) on disk, because they are written at lines 618–676. The two
   writes the required action named are correctly gated, and the desc
   assertion is in practice tautological (`len(ok)` vs `panel["cell_ok"].sum()`),
   so no number is at risk — but delete or weaken the comment rather than let
   a later reader trust it. The property that matters I verified directly from
   the artifacts, not from the assertion.
5. **(Advisory, matters for FIX-05.) `departures_time_eligible` is *not* the
   denominator of `airborne_min_mean` in 26 cells.** Action 3 correctly moved
   the airborne denominator to the gap-excluded count, but the panel retains
   the pre-gap `departures_time_eligible` and drops the internal
   `dep_for_airtime`. The exact denominator is recoverable —
   `air_time_total / airborne_min_mean` is integer-valued to 1.1e-13 and
   differs from `departures_time_eligible` in exactly **26** of 516,016 cells —
   so nothing is lost, but a departures-weighted mean of `airborne_min_mean`
   weighted by `departures_time_eligible` is very slightly wrong. FIX-05 should
   weight by `air_time_total / airborne_min_mean` (or, equivalently, aggregate
   `air_time_total` and that denominator) and say so in `desc_outcomes.csv`.
6. **(Advisory, for round close.) The void FIX-05 artifacts are still in the
   round folder and the validator counts them.** `desc_outcomes.csv`,
   `baseline_failures.csv`, `outcome_data_quality_exclusions.csv` and
   `figures/fig_excess_distribution.png` (all mtime 01:17–01:18) predate the
   rebuilt `panel_monthly.parquet` (01:36) and are part of the "24 CSVs
   scanned" the validator reports green. They are void per the cycle-1
   addendum. Regenerate or move them to `legacy_quarantine/` before round
   close; a green validator over stale files is not evidence.
7. **(Advisory, unchanged.) A3 stands and A10 is still open.** The churn CSV
   now makes the seasonality caveat citable, and `code/04_panel/`,
   `logs/04_build_panel.log` and the three CSVs remain untracked — commit them
   with findings 1–3 applied.

All seven cycle-1 required actions are met on their stated testables, every
recomputation reproduces the shipped numbers exactly, and the three items in
findings 1–3 are text/row-only corrections that provably cannot alter an
analysed number.

**VERDICT: PASS**

### FIX-04 block for ROUND_01_FINDINGS.md (G9-traced; the director should carry
this and nothing else from FIX-04)

1. **The panel is built and the structural-zero guard holds.** 1,026,729
   directed route × operator-nation × month cells; 517,076 pass `cell_ok`
   (coverage_ok and ≥ 4 departures). *(panel_filter_log.csv, rows
   `aggregate_to_cell` and `cell_ok_final`; desc_sample.csv, row TOTAL.)* The
   457,018 cells whose nation fails FIX-03's coverage gate carry a null
   airborne time, never a fabricated zero. *(panel_filter_log.csv, row
   `coverage_ok_g6`.)* Verified by mutation test that the guard exits 1 rather
   than shipping fabricated zero-minute foreign cells.
2. **The headline sample is 100% US on the face of the output**: `n_nations ==
   1` in all four decade rows and in TOTAL, across 4,133 routes and 36 years.
   *(desc_sample.csv, `decade_summary` rows.)* This is FIX-03's blocker made
   concrete, not a modelling choice.
3. **Within-US reporting gaps are excluded, never imputed.** 60 detail rows /
   483 departures report `AIR_TIME == 0` alongside positive departures and are
   removed from both the numerator and the denominator of the airborne mean
   (8 rows / 9 departures likewise for ramp time), so an all-gap cell is
   missing rather than zero. *(panel_filter_log.csv, rows
   `air_time_zero_gap_excluded` and `ramp_zero_gap_excluded`.)* No cell in the
   panel now shows a zero-minute average flight.
4. **Three foreign carriers are mislabelled as US by the carrier→nation
   mapping** — `VX (1)` Aces Airlines (Colombia), `B0` La Compagnie (France),
   `WO` Swoop (Canada), 35,168 departures between them, each with a
   home-country departure share of 0.0. *(carrier_nation_precision_audit.csv,
   rows `VX (1)`, `B0`, `WO`, columns `departures` and
   `home_country_dep_share`.)* Report this as the G7 precision failure it is,
   not as a US-carrier curiosity. The cell-level counts (mixed `cell_ok` cells
   and their `cell_ok_precision` survivors) may be cited once finding 2 above
   puts them in `panel_filter_log.csv`.
5. **311 routes (41,348 departures) leave the panel** because every carrier
   that ever served them was unmatched, icao-tier or null-coded, so they form
   no nation triple. *(panel_filter_log.csv, row
   `routes_lost_no_matched_carrier`.)*
6. **The extensive margin is the round's surviving asset, but its entry/exit
   flags are mostly seasonality, not market entry and exit.** 80,260 exits, of
   which 78.8% are followed by a later re-entry on the same route-nation, 50.9%
   within twelve months and 23.1% within three; 58.8% of the 20,395 route-nation
   pairs have more than one entry (max 88) and the median pair is active in only
   5 of 432 months. *(extensive_margin_churn.csv, rows `n_exits`,
   `share_exits_reentering_ever`, `share_exits_reentering_within_12mo`,
   `share_exits_reentering_within_3mo`, `share_triples_with_gt1_entry`,
   `entries_per_triple_max`, `active_months_per_triple_median`.)* This is a
   construction caveat, not a result — the CSV says so in its own `note`
   column. Any exit event study needs a spell-based definition (exit requires k
   consecutive inactive months) first.
7. **G6/G7 embargo intact**: no nation-level number is reported out of FIX-04,
   and `cell_ok_precision` is carried on the panel so a later task can take the
   strict sample without recomputing it.
8. Carried forward: FIX-01's write-before-assert pattern is now fixed for the
   two artifacts that mattered but is not eliminated (review finding 4).

### FIX-05 permission

**FIX-05 MAY NOW PROCEED** on `data/interim/panel_monthly.parquet` as rebuilt
at 2026-09-02 01:36 UTC. Findings 1–3 above are log-text and filter-log-row
corrections that cannot change a panel value; FIX-05 does not read them and
need not wait. Terms, restated and unchanged from the FIX-03 ruling:

1. **All-US, and labelled as such.** The computation is explicitly "US
   carriers' airborne time on US-touching international segments", never "the
   carrier-nation wedge" or anything implying a foreign comparison. Every
   `cell_ok` cell has `nation == 'US'`; assert it in code.
2. **G8 asserted in code**, not merely described: no baseline median may use a
   COVID-window month, every baseline must have ≥ 2 observations, and the count
   of cells failing the ≥ 2 rule must be logged and written to a CSV.
3. **The true monthly COVID window is 2020-03 … 2021-12** (22 months, PROJECT.md
   line 74 / Part 0). Do not use the wider 2020-01 … 2022-01 *event* window from
   PROJECT.md line 142 — that one belongs to NEW-06 (advisory A7).
4. **Screen on implied ground speed, not on the sentinel value 9999.** `9999`
   is not a sentinel in this source: 46 of the 47 raw rows carrying it are
   ordinary monthly totals, and screening on the literal value would delete
   good cells. Document the implied-speed screen in `desc_outcomes.csv`. For
   calibration on the current panel: 143 `cell_ok` cells are below 50 mph or
   non-finite and 80 exceed 1,000 minutes per departure (both recomputed
   above; the counts fell from 162 and stayed at 80 after the B3 fix).
   `distance == 0` on 2 `cell_ok` cells — never divide by it.
5. **Weight by the airborne denominator, not `departures_time_eligible`**
   (review finding 5): use `air_time_total / airborne_min_mean`, which differs
   in 26 cells.
6. **The previously-built FIX-05 artifacts are void and must be regenerated.**
   `code/05_outcomes/` ran at 01:17–01:18 against the pre-fix panel, before
   this verdict existed. `data/interim/panel_excess.parquet`,
   `desc_outcomes.csv`, `baseline_failures.csv`,
   `outcome_data_quality_exclusions.csv` and
   `figures/fig_excess_distribution.png` must be rebuilt from the 01:36 panel;
   no number in the existing versions may be cited, and they should be
   quarantined rather than left to be counted green by the validator.

## FIX-05 review — 2026-09-02 02:14 UTC

**Scope.** Full adversarial review of FIX-05 (`code/05_outcomes/05_build_excess.py`
→ `data/interim/panel_excess.parquet`; `desc_outcomes.csv`,
`baseline_failures.csv`, `outcome_data_quality_exclusions.csv`,
`figures/fig_excess_distribution.png`), plus the provenance question (were the
VOID artifacts really regenerated against the cycle-2 panel), plus the final
ruling on NEW-06. No analysis code was modified by the overseer; all mutation
tests ran on redirected copies in `/tmp/f05a|b|c`.

### Provenance (independently confirmed, not taken on mtime alone)

`panel_excess.parquet` carries all 29 cycle-2 panel columns including
`departures_time_eligible`, `departures_airborne_eligible` and
`departures_non_reporting`. Sorted on the cell key, **every one of the 29
inherited columns is identical to `panel_monthly.parquet` — 0 value diffs, 0
NaN-pattern diffs, keys equal row for row** (1,026,729 rows both sides). The
seven FIX-05 columns are additive. No void artifact survives: the four
round-folder deliverables are byte-identical to a clean isolated re-run against
the 01:57:59 panel (md5 below), and `legacy_quarantine/` does not exist because
the void files were overwritten in place rather than moved. The one place the
void run does survive is `logs/05_build_excess.log` (advisory A2).

### Checks run (every number recomputed by the overseer from the parquets)

**Full independent rebuild of the outcome block.** I re-derived the screen, the
candidate pool, `baseline_n`, `baseline_med`, `baseline_mad`, `excess_min`,
`excess_min_w`, `bidir_sum` from `panel_monthly.parquet` with my own code and
compared against the shipped parquet: **max abs diff 0.0 and 0 NaN-pattern
mismatches on every one of the seven columns**. Reproduced exactly: valid
measurement **515,875 / 1,026,729 = 0.5024**; implied-speed flags **328** rows
panel-wide, **141** with `cell_ok`; `distance == 0` **50** rows, **2** with
`cell_ok` (141 + 2 = 143, reconciling with my FIX-04 count); baseline failures
**122,727 / 515,875 = 0.23789**; `excess_min` non-null **393,148**; winsorized
**11,040**; `bidir_sum` non-null **389,446 / 1,026,729 = 0.3793**;
`baseline_mad == 0` **1,629**. Every implementer claim in the hand-off is
arithmetically correct except the baseline-failure narrative (finding 1).

**VERIFY 1 — baseline_med hand-recomputed on randomly drawn cells (seed
20260902).** `MIA→SDQ 2005-05`: candidates 103.5806 / 103.2747 / 104.0968 →
median **103.5806**, shipped 103.5806, excess −0.5914 = shipped. `IAH→MTY
2007-07`: 66.7148 / 66.8669 / 66.2810 → **66.7148** = shipped, excess 3.3113.
`CDG→ORD 1992-09`: 532.0333 / 546.0690 / (1989 absent) → n=2, **539.0511** =
shipped, excess −4.7845. `UVF→MIA 2009-03`: 203.7742 / 211.3548 / 207.9355 →
**207.9355** = shipped. All four match to full precision.

**VERIFY 2.** Rows with `baseline_n < 2` and non-null `excess_min`: **0**. Rows
with `baseline_n < 2` and non-null `baseline_med`: **0**.

**VERIFY 3 (winsorization), 3 routes of my own choosing plus the implementer's
2.** `JFK→LHR` n=388 p1=−19.8241 p99=24.4623 = observed min/max of
`excess_min_w`; `MIA→GRU` n=374 −16.9332 / 12.7289; `ORD→NRT` n=348 −21.8591 /
22.2611; `LHR→JFK` n=387 **−27.0951 / 24.3269** (implementer's figure
confirmed); `PTY→MIA` n=382 **−6.8020 / 6.5811** (confirmed). Recomputing the
per-group clip over all 2,910 route groups reproduces `excess_min_w` at **max
abs diff 0.0**. Clipping is applied strictly after the screen (screened cells
carry `excess_min = NaN` and never enter a quantile). Degenerate cutoffs: **55
groups have p1 == p99, covering 75 rows (0.019% of non-null excess)**, and all
are single-observation or constant-valued groups, so the clip is a no-op there
— no group is collapsed to a point. Groups with n ≤ 5 hold **691 rows
(0.176%)**.

**Trailing window / look-ahead.** The candidate pool is built by merging
`year − k` for k ∈ {1,2,3} at the same (origin, dest, nation, calendar month).
It is strictly backward-looking; there is no centred or forward term, and the
merge is a left join on a key I verified unique among valid cells (**0
duplicates**). Confirmed on data, not on code: `2021-01` targets reach
`baseline_n == 3` (888 cells) while `2021-03` targets top out at **2** — i.e.
2020-01 is usable and 2020-03 is not.

**G8 by mutation, in an isolated root.** (a) Deleting the COVID-nulling line
→ `RuntimeError: G8 VIOLATED: 18916 baseline candidates at lag 1 years fall
inside the COVID window ((2020, 3)..(2021, 12))`, **exit 1**, no parquet, no
desc/baseline CSV, no figure written. (b) Weakening `ok2` to `baseline_n >= 1`
→ `RuntimeError: G8 VIOLATED: a baseline_med was computed with < 2
observations.`, **exit 1**, same absence of artifacts. (c) The window is
monthly, not an annual coarsening: `_covid_flag` returns True on exactly **22**
month cells, first (2020, 3), last (2021, 12); 2020-01/02 False, 2020-03 True,
2021-12 True, 2022-01 False.

**Screen applies to both roles.** Screened cells are removed from the
baseline-contributor pool, not only from the target role — e.g. `FLL→MHH
2019-02` draws its baseline from 2017 (47.8085) and 2016 (46.9423) only, with
the 2018 value of 365.72 min excluded; shipped `baseline_med` **47.375409** =
my hand median. `CUN→MCI 2007-05` and `FLL→GHC 2020-12` fall to
`baseline_n == 1` (excess NaN) for the same reason. The `distance == 0`
carve-out is correct rather than convenient: both `cell_ok` cases are
`SWL↔WFB 2002-04` (11 and 13 departures, 24 min, 0 miles) — a Puget Sound
seaplane hop where the whole-mile DISTANCE field rounds to 0, so 0 mph is
undefined, not slow. Every screened row is documented one-per-row in
`outcome_data_quality_exclusions.csv`: **328 + 2 + 80 = 410 rows**, counts
matching the panel exactly. Docstring examples verified against the panel:
`YGE→LKE 2025-10` (1 dep, 207 mi, airborne 9999.0, ramp 10004.0, `cell_ok`
False, flagged) and `NSB→FLL 2018-02` (88 dep, 59 mi, 2,433 min → 1.45 mph,
flagged and excluded).

**desc_outcomes.csv.** 20 rows = 4 outcomes × (4 decades + `all`), with
`formula` and `sample` as text and all seven moments. Every moment on all four
`decade == all` rows and on the 2020s `excess_min` row reproduces exactly from
the parquet (e.g. `excess_min` all: n 393,148, p1 −21.2319, p50 0.011360, p99
21.2533, mean 0.056855, sd 8.851467).

**Labelling.** `SAMPLE_LABEL` = "US carriers' airborne time on US-touching
international segments" appears on all 20 rows of `desc_outcomes.csv`, all 36
rows of `baseline_failures.csv` (whose `nation` column is `US` and only `US`),
and in the figure suptitle, which renders **fully unclipped** in the PNG. The
script's only occurrence of "wedge" is the docstring clause forbidding it. No
deliverable implies a cross-national comparison.

**Determinism / isolation.** A clean re-run in `/tmp/f05a` (no `data/raw/`, no
network, no Trino) exits 0 and produces `panel_excess.parquet`,
`desc_outcomes.csv`, `baseline_failures.csv`,
`outcome_data_quality_exclusions.csv` and `fig_excess_distribution.png`
**byte-identical (md5) to the shipped artifacts**.
`python code/99_validate_outputs.py` → exit **0** ("24 CSVs scanned, 0 FAIL, 0
WARN"); `python code/98_check_trino_usage.py` → exit **0**. All four
deliverables are inside `rounds/round-1-t100-panel/` and inside the validator's
directory-wide scan.

### Gate status

- **G1** — PASS. 0 null keys, 0 duplicate keys in `panel_excess.parquet`; no
  empty cells in `desc_outcomes.csv` or `baseline_failures.csv`; the 2 blank
  cells in `outcome_data_quality_exclusions.csv` are the `distance_zero`
  rows' inapplicable count columns, schema not missingness.
- **G2/G3/G4** — N/A. FIX-05 produces no coefficient, SE or p-value.
- **G5** — PASS. `baseline_fail_share` ∈ [0, 1] on all 36 rows (min 0.0965,
  max 1.0); validator's bounded-column scan clean.
- **G6** — inherited PASS (cells enter through `cell_ok`, which carries
  `coverage_ok`); the all-US consequence is asserted at runtime.
- **G7** — embargo intact: every valid cell is `nation == 'US'`, no
  nation-level or cross-national number is produced.
- **G8** — **PASS, and mutation-proven** (both assertions raise and exit 1; the
  window is the correct 22-month monthly window). The count failing the ≥ 2
  rule is written to `baseline_failures.csv`, as commissioned.
- **G9** — **PARTIAL, see finding 3.** `11,040` winsorized rows, `1,629`
  zero-MAD rows, the per-route winsorization cutoffs, and the month-resolution
  collapse of the excess series in 2022-03…2023-12 exist only in a log or only
  in the parquet — none is citable from a round-folder CSV.

### Findings — BLOCKING

1. **The excess series is empty for the entire post-event window
   2022-03 … 2023-12, and no deliverable says so.** Recomputed from
   `panel_excess.parquet`: non-null `excess_min` by month is 1,156 (2022-01),
   1,162 (2022-02), then **0 in every one of 2022-03 … 2022-12 and 0 in every
   one of 2023-01 … 2023-12**, recovering to 15,712 in 2024 and 17,253 in 2025.
   This is mechanical, not a bug — with lags of 1/2/3 years and the 22 COVID
   months barred, a 2022-05 target has only 2019-05 left and a 2023-05 target
   only 2022-05 — and the rule must NOT be relaxed (that would be a rule-11
   DECISION-PENDING for the human, not an agent fix). But the consequences are
   currently invisible and one of them is actively misleading:
   (a) `figures/fig_excess_distribution.png`, right panel, is titled **"2022
   only (n=2,318)"** when all 2,318 cells are January–February 2022, i.e.
   entirely *before* the February 2022 event this paper is about. A seminar
   reader takes that panel for the treatment year.
   (b) `baseline_failures.csv` reports this only at annual resolution (rows
   `US,2022` share **0.8684374822634656** and `US,2023` share **0.875**), so
   the "which months" — the only part that matters for the design — has no CSV
   trace and cannot enter FINDINGS under G9.
   (c) The implementer's own hand-off summary to this reviewer described the
   file as "100% failure in 1990–91 …, then ~17–26%/yr", which is contradicted
   by the two rows in that same CSV that decide whether the round's headline
   outcome exists during the treatment window. Prose-vs-CSV misdescription of
   exactly this kind is what these reviews exist to catch.
   *Required (all additive; no shipped number may change):* retitle the right
   panel to name the Jan–Feb restriction and the reason; add month-resolution
   (or window-resolution) rows to `baseline_failures.csv` so
   "0 computable excess cells, 2022-03 … 2023-12" is a `(file.csv, row)` trace;
   state the blackout in the FIX-05 FINDINGS block as the round's principal
   limitation for any 2022 event design.

2. **Winsorization does not swallow the measurement contamination, and the
   surviving cells dominate the mean.** With the screen at 50 mph, **1,171
   cells with non-null `excess_min_w` still imply a ground speed below 150 mph**
   (376 below 100 mph) — physically impossible for the scheduled jet service
   in this sample, whose implied-speed distribution is p1 195.9 / p50 467.3 /
   p99 588.8 mph. Per-route 1/99 clipping leaves them: the largest shipped
   `excess_min_w` is **+968.195** at `GCM→CVG 1999-06` (4 departures, 1,375
   miles, 1,200 min/departure = **68.75 mph**), with `CVG↔GCM` 1998–2000
   supplying six of the twelve largest values, and `excess_min_w` ranges
   **[−281.501, +968.195]**. Those 1,171 cells are 0.30% of the sample but
   carry **58.7% of the sum of `excess_min_w`**: dropping them moves the pooled
   mean from **0.03474** to **0.01441** (−59%); dropping only the sub-100 mph
   cells gives 0.01269. The screen is also one-sided — 48 valid cells imply
   **> 700 mph** (max **11,730 mph**), an under-reported AIR_TIME that reads as
   a large *negative* excess, i.e. a spurious speed-up, and nothing screens it.
   Every mean-based statistic downstream (NEW-06's corridor means, any DiD on
   `excess_min_w`) inherits this. *Required:* do NOT silently move the
   threshold (rate-changing without commission is prohibited); write the
   sensitivity to a round CSV — pooled and by-decade mean/p1/p99 of
   `excess_min_w` under screens at 50 / 100 / 150 / 200 mph with the cell
   counts, plus a symmetric upper-speed diagnostic count — so the director and
   the human can see the fragility and rule on the threshold.

3. **VERIFY item 3 is unmet in the letter, and two headline construction counts
   are log-only (G9).** The round file's VERIFY reads "the winsorization
   cutoffs **in `desc_outcomes.csv`** match the p1/p99 of the raw excess within
   route × direction". `desc_outcomes.csv` contains no cutoff column at all —
   only pooled/by-decade moments — so the stated check is not performable
   against the deliverable; I could only perform it against
   `panel_excess.parquet`. Likewise `11,040` winsorized rows and `1,629`
   zero-MAD rows appear only in `logs/05_build_excess.log`. *Required:* add the
   per-route cutoffs (a small CSV keyed by origin × dest × nation with n, p1,
   p99, n_clipped is the natural form) or at minimum a cutoffs block in
   `desc_outcomes.csv`, and put the winsorized and zero-MAD counts in a CSV.

4. **`excess_z` as shipped is a degenerate statistic and `desc_outcomes.csv`
   presents it without a caveat.** Its MAD comes from at most three candidates,
   so it is near-zero at will: over 391,519 non-null values the sd is
   **205.9477**, p1 **−71.7730**, p99 **83.9958** (`desc_outcomes.csv`,
   outcome `excess_z`, decade `all`), the range is **[−32,315.13,
   +87,010.00]**, and **5,904 cells exceed |z| = 100** (429 exceed 1,000). A
   quantity labelled a z-score whose 99th percentile is 84 will be read as
   evidence of enormous anomalies; it is an artifact of a 2–3 point MAD.
   *Required:* say so in the `formula` text for `excess_z` and add the
   |z| > 100 count to a CSV, or mark the column NOT-FOR-USE pending a
   director-commissioned dispersion measure. Do not re-specify it here.

### Findings — ADVISORY (not blocking, carry forward)

A1. `logs/05_build_excess.log` is committed (in 57d3fd8) and contains **two
    VOID runs** (01:17:22 and 01:17:50) carrying superseded numbers — 516,032
    valid cells, 122,787 failures, 393,245 non-null excess, 389,540 bidir, and
    a "> 1440 min = 24h" screen that no longer exists — with no VOID marker in
    the file. Same class as FIX-04 finding 3. Truncate and re-run once (the
    artifacts are proven byte-identical) or annotate.
A2. **Write-before-assert persists.** In the mutation runs, `RuntimeError` on
    G8 left `outcome_data_quality_exclusions.csv` (76,906 bytes) on disk in the
    scratch root because it is written at line 244, before the assertions at
    lines 302–309. The parquet, both other CSVs and the figure are correctly
    gated. Third round of this pattern (FIX-01, FIX-04, FIX-05).
A3. `outcome_data_quality_exclusions.csv` is the one FIX-05 deliverable with no
    `sample` label column; add it for consistency with the all-US labelling
    ruling.
A4. Winsorization cutoffs are computed on the **full 1990–2025 sample**, so a
    2022 cell's clip depends on 2025 data. Standard practice and small in
    effect (11,040 of 393,148 rows move), but state it in the formula text; a
    pre-period-only cutoff is the conservative alternative if the paper ever
    winsorizes inside an event window.
A5. FIX-04 review finding 5 (weight by `air_time_total / airborne_min_mean`,
    not `departures_time_eligible`) is **not triggered in FIX-05** — the script
    produces no weighted statistic. The term transfers intact to NEW-06 and to
    any future departures-weighted mean.
A6. The hand-off's "393,148 cells got `baseline_n >= 2`" is loose: **398,220**
    rows carry `baseline_n >= 2`; 393,148 is the subset that is also a valid
    target. Harmless (the extra 5,072 carry `excess_min = NaN`), but the
    FINDINGS wording should use the CSV's own denominators.
A7. Process: the FIX-05 artifacts and `code/05_outcomes/05_build_excess.py`
    were swept into the **FIX-04** commit 57d3fd8 (02:05) before FIX-05 was
    reviewed. Content is the regenerated version, so nothing is contaminated,
    but the commit-after-review discipline (standing rule 8) was not followed
    for this task.

**VERDICT: FAIL** — four blocking items, all additive and text/CSV-only. Every
computed value in FIX-05 reproduced exactly; **no shipped number needs to
change**, and the ≥2-observation and COVID-exclusion rules must not be touched
in the fix cycle.

### FIX-05 block for ROUND_01_FINDINGS.md (G9-traced; the director should carry
this and nothing else from FIX-05, after the four required actions are met)

1. **What was built.** For every clean US cell we now have "excess airborne
   minutes": the cell's mean airborne minutes per departure minus the median of
   the same directed route in the same calendar month over the trailing three
   years, COVID months never counted, at least two prior years required.
   *(desc_outcomes.csv, column `formula`, rows `excess_min` /`excess_min_w` /
   `excess_z` / `bidir_sum`.)*
2. **Scale of the outcome.** 393,148 cells have an excess value; pooled p1
   −21.23, median 0.011, p99 21.25, mean 0.057, sd 8.85 minutes; after
   winsorizing 1/99 within route, mean 0.035, sd 8.20. The bidirectional sum
   exists for 389,446 cells (mean 0.070, sd 12.60). *(desc_outcomes.csv, rows
   `excess_min`/`excess_min_w`/`bidir_sum` with `decade == all`.)* Median
   excess of essentially zero is what a correctly-centred baseline should give.
3. **One cell in four has no usable baseline.** 122,727 of 515,875 valid cells
   (23.8%) fail the ≥ 2-prior-years rule; 1990 and 1991 fail at 100% because no
   prior history exists. *(baseline_failures.csv, rows `US,1990` … `US,2025`,
   columns `n_valid_cells`, `n_baseline_fail`, `baseline_fail_share`.)*
4. **The rule empties the event window.** Baseline failure is **0.8684** in
   2022 and **0.8750** in 2023 *(baseline_failures.csv, rows `US,2022` and
   `US,2023`)*, versus 0.195 in 2024 and 0.145 in 2025 — because 2022 and 2023
   targets can only look back into the barred COVID months. The surviving 2022
   and 2023 cells are January and February only, so **the excess and
   bidirectional-sum outcomes do not exist for any month from March 2022
   through December 2023**, the whole first two years after the February 2022
   event. Any 2022 event design must use the raw airborne level, a different
   baseline window agreed with the human, or the 2024–25 recovery period. *(To
   be cited from the month-resolution rows required by review finding 1; until
   those exist, only the two annual shares above are citable.)*
5. **Data-quality screen.** Cells whose implied ground speed (miles ÷ airborne
   hours) is below 50 mph are excluded from both the target and the baseline
   roles — 328 cells panel-wide, 141 of them otherwise-clean cells — and two
   zero-distance seaplane cells (`SWL↔WFB`) are explicitly kept, since 0 miles
   makes speed undefined rather than slow. *(outcome_data_quality_exclusions.csv,
   `check` values `implied_speed_below_50mph`, `distance_zero_cell_ok`,
   `diagnostic_only_gt_1000min_per_dep`.)* The screen is deliberately
   permissive and one-sided; see the sensitivity required by review finding 2
   before any mean of excess is reported.
6. **All-US, and only that.** Every row of every FIX-05 deliverable carries the
   sample label "US carriers' airborne time on US-touching international
   segments" and `nation == 'US'` *(baseline_failures.csv, column `sample`;
   desc_outcomes.csv, column `sample`)*. Nothing here is a carrier-nation
   comparison; the G6/G7 embargo is intact.
7. **G8 holds and was proven, not asserted.** No baseline uses a COVID month
   (2020-03…2021-12) and none uses fewer than two observations; the overseer
   mutation-tested both assertions and both exit 1.

### FINAL RULING — NEW-06

**Confirmed, not revised: NEW-06 may not ship as commissioned.** Re-verified
this session from `coverage_by_corridor.csv`: **0 of 908 non-US corridor ×
nation × year cells pass G6**, and their `share_air_time_valid` is **0.0 at the
maximum**, not merely below the 0.50 bound — foreign operators report no
airborne time anywhere in the file (per corridor: useastasia 0/337,
useurope_placebo 0/425, usmideast 0/126, usindia 0/20; all 129 US cells pass).
In `panel_excess.parquet`, non-US cells on the four anchor corridors in
2019–2024 number 7,599 / 10,818 / 5,687 / 998 and **exactly 0 of them carry a
non-null `airborne_min_mean`**. Every commissioned corridor figure would be a
single US line labelled as a cross-national comparison, and every row of
`raw_wedge_diffs.csv` would be NaN with n = 0 on one side by construction.
Shipping those five figures would be the most attackable artifact this project
could produce. Compounding it, the US line itself goes dark on the excess
outcomes exactly at the event: in the zoom window 2021-06…2022-12 the corridor
cells have `excess_min_w` only through 2022-02 (finding 1).

**NEW-06 is therefore BLOCKED as specified — figures
`fig_raw_wedge_useastasia.png`, `fig_raw_wedge_usindia.png`,
`fig_raw_wedge_usmideast.png`, `fig_raw_wedge_useurope_placebo.png` and
`fig_raw_wedge_bidir.png` may not be produced in wedge form** (one line per
operator nation, read as a national comparison). The reason is a property of
the BTS extract established in FIX-03 and re-verified twice, not a modelling
choice, and no mapping fix or estimator can recover it.

**What NEW-06 MAY still legitimately produce, as a documented null (this is the
reduced deliverable, and it is the whole of it):**

1. `raw_wedge_by_corridor.csv` — the **full commissioned family**, all 4
   corridors × 2 windows × every operator nation ever observed on the corridor
   × every month in the window, so the round file's "report every corridor
   including empty cells with n = 0" gate is checkable. Statistic columns
   present and NaN where undefined, with `n_cells`, `n_cells_with_airborne`
   (0 for every non-US nation) and a `reason_missing` column naming the cause
   and its trace (`coverage_by_corridor.csv`, `gate_g6_pass` /
   `share_air_time_valid`).
2. `raw_wedge_diffs.csv` — written, with every row's `n_treated`/`n_control`
   and a NaN `diff`, plus the `definition` column the round file requires and
   an explicit "NaN by construction: no non-US operator reports airborne time"
   note. It is a completeness record only: it may not be plotted, and no sign,
   direction or placebo comparison may be read from it in FINDINGS or anywhere
   else.
3. **One figure, and it is a data-availability figure, not a wedge figure** —
   e.g. corridor × operator-nation × month count of cells with non-null
   airborne time, showing the zero band for every foreign nation against the
   populated US row, titled as coverage/availability and captioned
   "US-touching international segments". This is the honest visual form of the
   null.
4. **Optionally**, a US-only raw-level series per corridor: departures-weighted
   mean `airborne_min_mean` by corridor × month across both windows, weights
   `air_time_total / airborne_min_mean` (FIX-04 finding 5, advisory A5), with
   the 2022-02 line drawn, titled "US carriers only — not a cross-national
   comparison". If excess or bidirectional-sum panels are shown at all they
   must carry the annotated 2022-03…2023-12 gap; a line that simply stops is
   not acceptable.

Standing conditions that survive unchanged: NEW-06 is not a headline under any
circumstance; corridor 1 / ICN may be computed but not reported pending the
FIX-02 human ruling; RU and IR remain labelled MATCH-SENSITIVE; and the
agent-drafted `data/raw/events/ban_nations_2022.csv` must be caveated wherever
it is used. If the director prefers, NEW-06 may instead be recorded BLOCKED in
full with items 1–2 written as the record of the null — but items 1–2 are the
minimum: the EXPLORE contract requires the empty cells to be on the record, and
silence is not an option.

**FIX-05 VERDICT: FAIL** (blocking findings 1–4, all additive; no shipped
number changes). **NEW-06: BLOCKED as commissioned**, reduced to the four
documented-null deliverables above.

---

## FIX-05 review (cycle 2) — 2026-09-02 02:43 UTC

**Scope.** Confirm only that the four cycle-1 blocking fixes and the five
advisories landed, that nothing previously verified moved, and that both
checkers still exit 0. Cycle-1 provenance, the isolated byte-identical re-run,
the baseline hand-checks and the G8 mutation tests are NOT re-litigated. No
analysis code was modified by the overseer.

### Nothing moved (independently recomputed from `panel_excess.parquet`)

`md5(data/interim/panel_excess.parquet)` = **075189120f0cf3b7307601fbb543717c**,
as reported. Because cycle 1 recorded no md5 literal, I did not accept the hash
as proof and re-derived the substance instead. Every cycle-1 number reproduces
to the digit from the shipped parquet with my own code:

| quantity | cycle-1 | cycle-2 recompute |
|---|---|---|
| valid measurement | 515,875 / 1,026,729 = 0.5024451 | **515,875**, 0.5024451 |
| implied-speed flags (all / cell_ok) | 328 / 141 | **328 / 141** |
| distance == 0 (all / cell_ok) | 50 / 2 | **50 / 2** |
| baseline failures | 122,727 | **122,727** |
| non-null `excess_min` | 393,148 | **393,148** |
| winsorized rows | 11,040 | **11,040** |
| `baseline_mad == 0` among targets | 1,629 | **1,629** |
| non-null `bidir_sum` | 389,446 | **389,446** |
| `baseline_n >= 2` any row / valid target | 398,220 / 393,148 | **398,220 / 393,148** |
| `\|excess_z\| > 100` / `> 1000` | 5,904 / 429 | **5,904 / 429** |

`desc_outcomes.csv`: all eight numeric columns × 20 rows are **identical to the
HEAD version (max abs diff 0.0 on every column)** — only `formula` text changed.
Spot-recomputed from the parquet: `excess_min` all (n 393,148, mean 0.056855,
sd 8.851467, p1 −21.2319, p50 0.011360, p99 21.2533), `excess_min_w` all (mean
0.034744, sd 8.196160), `bidir_sum` all (n 389,446, mean 0.069697, sd
12.603801), `excess_min` 2020s (n 57,646, mean −0.061045) — all exact.
`baseline_failures.csv` annual rows: **max abs diff 0.0** vs HEAD on
`n_valid_cells`, `n_baseline_fail`, `baseline_fail_share`.
`outcome_data_quality_exclusions.csv`: **identical to HEAD on all 12 shared
columns**, 410 rows, `sample` appended.
`git diff HEAD` on `05_build_excess.py` deletes **nothing** from the screen,
baseline, COVID-bar, winsorization or G8 logic; constants unchanged
(`IMPLIED_SPEED_MPH_MIN = 50.0`, `WINSOR_LO/HI = 0.01/0.99`,
`COVID_START/END = (2020,3)/(2021,12)`, `baseline_n >= 2`). The change is
additive plus figure/text.

`python code/99_validate_outputs.py` → **exit 0** ("27 CSVs scanned, 0 FAIL, 0
WARN"; was 24, +3 new). `python code/98_check_trino_usage.py` → **exit 0**. All
27 CSVs are inside `rounds/round-1-t100-panel/`; no project CSV exists outside a
round folder.

### Blocking item 1 — LANDED, and the correction is UPHELD; my cycle-1 framing was WRONG

Recomputed non-null `excess_min` by month directly from the parquet:

- 2022: **1156, 1162, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0** (total 2,318)
- 2023: **1169, 1170, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0** (total 2,339)
- 2024: 1257 … 1376, total 15,712; 2025 total 17,253.

`bidir_sum` shows the same shape (2022: 1150, 1156, then zeros; 2023: 1164,
1168, then zeros).

**The implementer's characterization is correct and mine was not.** The zero
range is **two blocks of ten months each — 2022-03 … 2022-12 and 2023-03 …
2023-12 — not one continuous block 2022-03 … 2023-12.** January and February of
*both* 2022 and 2023 are populated. My cycle-1 sentence "0 in every one of
2023-01 … 2023-12" was false; 2023 has 2,339 computable cells, all in Jan–Feb.

Mechanism verified on the data, not inferred: `baseline_n` among valid targets
is capped at **2** in 2022-01 (1,156 cells at n=2), 2022-02 (1,162), 2023-01
(1,169), 2023-02 (1,170), and capped at **1** in 2022-03 (1,240 cells at n=1,
zero at n≥2), 2023-03 (1,392 at n=1), 2023-12 (1,449 at n=1). Worked example
`ACA→DFW 2023-01`: lag-1 = 2022-01 (154.111, valid), lag-2 = 2021-01 (154.0,
**inside the 2020-03…2021-12 bar, dropped**), lag-3 = 2020-01 (146.0, **outside
the bar, kept**) → n=2, median 150.0556 = shipped `baseline_med`, excess
141.7778 − 150.0556 = **−8.2778** = shipped. From March the year-3 lag lands
inside the bar too, so n falls to 1 and the series dies until January returns.
2024 recovers fully (2024-03 has 1,357 cells at n≥2) because its lag-2 and lag-3
reach 2022 and 2021-03-onward months that are *valid cells* even where their own
excess is undefined.

**Use this two-block statement in FINDINGS.** It is now CSV-citable:
`baseline_failures.csv`, `granularity == 'month'`, 432 month rows (36 years ×
12) with `n_excess_computed`; `baseline_fail_share == 1.000000` on exactly the
20 blackout months and 0.171326 / 0.170000 / 0.240416 / 0.243697 on the four
surviving months. Year and month rows **reconcile exactly**: grouping the 432
month rows by year matches all 36 year rows on `n_valid_cells`,
`n_baseline_fail` and `n_excess_computed` with **zero mismatches**, and the
month rows sum to 515,875 / 122,727 / 393,148.

Figure: right-panel title is now `"2022, Jan-Feb ONLY (n=2,318) -- entirely
BEFORE the Feb-2022 event"`, with `span` and `n` computed from the data (lines
850–861) and `4/24` computed from `nonzero_ym`. Rendered PNG inspected at full
size: **both titles unclipped, no overflow into the neighbouring axes**, legends
readable, n=2,318 matches the CSV.

### Blocking item 2 — LANDED; both methods independently reproduced

`excess_speed_screen_sensitivity.csv`, 40 rows = 4 thresholds × 5 groups
(`all` + decades 1990/2000/2010/2020) × 2 methods. (The hand-off said "pooled +
5 decades"; it is pooled + **4** decades. The CSV is right, the description was
loose.)

- **`naive_filter_shipped_series` reproduced exactly by me** from the shipped
  `excess_min_w`: at 50/100/150/200 mph, n = 393,148 / 392,772 / 391,977 /
  388,727, removed = 0 / 376 / **1,171** / 4,421, mean = 0.034744 / 0.012692 /
  **0.014407** / 0.003292, sum = 13659.5679 / 4985.1383 / 5647.2627 / 1279.7275,
  p1/p99/sd all exact. The 150 mph row reconciles with my cycle-1 diagnostic to
  the digit: **1,171 cells, 0.03474 → 0.01441**.
- **`full_recompute_stricter_valid_mask` reproduced exactly by me** by
  re-running the whole pipeline (stricter valid mask → candidate merge → COVID
  bar → n≥2 → median → excess → per-route 1/99 clip) at each threshold:
  n_valid = 515,875 / 515,040 / 513,041 / 508,108, n_excess = 393,148 / 392,622
  / 391,769 / 387,697, mean = 0.034744 / 0.021699 / 0.020870 / 0.025337,
  sd/p1/p50/p99/sum all exact. **This is a genuine re-estimation, not a filter.**
- **Threshold was NOT moved.** The 50 mph row of the full-recompute method
  reproduces the shipped series bit for bit (515,875 valid, 393,148 excess, mean
  0.034744, sum 13659.5679), and the shipped constant is `IMPLIED_SPEED_MPH_MIN
  = 50.0`, untouched in the diff.
- **Labelling is correct and not mixed.** The `method` column separates the two
  and the `note` explicitly states that the full recompute "also cleans
  contaminated candidates out of OTHER cells' baselines" while the naive version
  "just drops the flagged cells … with no recomputation". No row blends them.
- Internal consistency: within every method × threshold, the four decade rows'
  `sum_excess_min_w` sums exactly to the `all` row's, and `n_excess_computed`
  sums exactly (e.g. 393,148 at 50 mph) — the decade partition is exhaustive and
  non-overlapping. Decade rows spot-recomputed at 100 and 200 mph for all four
  decades: **8/8 exact** on n, mean and p99.
- **Correction to the hand-off:** the >700 mph diagnostic is **not** "constant
  at 117". It is **117 on every `full_recompute` row and 48 on every
  `naive_filter` row**. I recomputed both: 117 cells with implied speed > 700
  among the 515,875 valid measurements, 48 among the 393,148 non-null-excess
  cells (241 panel-wide; max implied speed 33,913 mph). Each method carries the
  count for its own denominator, which is correct; but the CSV never says so
  (advisory B4).

### Blocking item 3 — LANDED; VERIFY item 3 now performable and satisfied

`excess_winsorization_cutoffs.csv`: 2,910 rows, keyed origin × dest × nation,
columns `n / p1 / p99 / n_clipped / cutoff_computed_on / sample`, zero nulls.
I rebuilt the whole table from `panel_excess.parquet` (`excess_min` grouped by
directed route, q01/q99, clipped-count) and merged: **2,910 matched both ways,
0 left-only, 0 right-only; max abs diff n = 0, n_clipped = 0, p1 = 7.1e-15,
p99 = 1.4e-14** (float round-trip only). `sum(n) = 393,148` = non-null
`excess_min`; `sum(n_clipped) = 11,040` = the winsorized count.

Route spot-checks against the raw excess (random draw plus my cycle-1 routes),
CSV vs my own quantiles: `NGO→PDX` n=98, −19.653346 / 15.567935, 2 clipped;
`MFE→MEX` n=106, −3.142521 / 3.603716, 4 clipped; `MBJ→TPA` n=117, −4.978452 /
9.711800, 4 clipped; `PVR→MDW` n=4, −2.847222 / 11.994478, 2 clipped;
`JFK→LHR` n=388, −19.82414 / 24.462299; `LHR→JFK` n=387, −27.095057 /
24.326884; `PTY→MIA` n=382, −6.802012 / 6.581079. **All exact**, and the last
three match my cycle-1 hand-computed values.

Degenerate groups: **55 groups have p1 == p99, covering 75 rows (0.019%)** —
52 with n=1, two with n=5 and one with n=13, all constant-valued — and **every
one has `n_clipped == 0`**, so the clip is a strict no-op there and no group is
collapsed to a point. Groups with n ≤ 5: **232 groups, 691 rows (0.176%)**.
Both figures match cycle 1 exactly. No row has p1 > p99.

`excess_construction_diagnostics.csv`: 12 rows, all 12 values independently
recomputed and **all 12 exact** — 515,875 / 398,220 / 393,148 / 11,040 / 1,629 /
389,446 / 5,904 / 429 / 328 / 141 / 2 / 80. Row 1's note correctly distinguishes
the 398,220 "any row" denominator from the 393,148 "valid target" denominator,
closing advisory A6.

### Blocking item 4 — LANDED

`desc_outcomes.csv` `excess_z` `formula` now carries the near-degenerate-MAD
caveat verbatim ("with at most 3 candidates, baseline_mad is itself a
near-degenerate statistic … p99 roughly 84, some cells beyond |z|=1000"),
directs the reader to check `excess_min` and `baseline_mad` first, cites
`excess_construction_diagnostics.csv` for the tail counts, and ends **"Treat as
NOT-FOR-USE pending a director-commissioned dispersion measure with a larger
candidate pool."** The moments are unchanged (n 391,519, sd 205.947675, p1
−71.77304, p99 83.995782) — the column was caveated, not re-specified, as
required.

### Advisories 5 — all LANDED

- `logs/05_build_excess.log` is now **26 lines, one run only** (02:33:17 →
  02:34:22 DONE). No VOID run survives. (A1 closed.)
- `dq_df.to_csv(DQ_EXCLUSIONS_CSV)` moved to **line 369, after both G8 raise
  points at 353 and 357**. (A2 closed for the gate.)
- `sample` column present on all 410 rows of
  `outcome_data_quality_exclusions.csv`, single value, rest of the file
  byte-equal to HEAD. (A3 closed.)
- `excess_min_w` `formula` now states the cutoffs use "ALL non-null excess_min
  for that route across the full 1990-2025 sample (not separately by year) -- a
  2022 cell's clip boundary can therefore depend on that same route's 2025
  data", and points at both new CSVs. (A4 closed.)

### Pathology sweep (all 27 round CSVs, not a manifest)

No p-value, SE or coefficient column exists anywhere in FIX-05 (G2/G3/G4 N/A —
no p = 0.0, no identical-p family, no |SE/coef| pathology possible). No value
exceeding 1e6 that is not a legitimate count (departures, bytes, row counts).
All NaN columns are structurally justified: `baseline_failures.month` (NaN on
the 36 year-granularity rows only), `excess_speed_screen_sensitivity`'s
`n_valid_measurement` (method-specific) and `n_removed_from_shipped_series`
(method-specific), `outcome_data_quality_exclusions`'s two count columns on the
`distance_zero` rows. `baseline_fail_share` ∈ [0.0454545, 1.0] — inside [0,1]
on all 468 rows. Shares/precisions elsewhere unchanged. No sign contradiction:
the decade means of `excess_min_w` are stable across all four thresholds and
both methods (−0.11/−0.19, +0.73/+0.75, −0.41/−0.44, −0.03/−0.06).

### Gate status

- **G1** — PASS. Keys unique; no unexplained empty cells in any of the three new
  CSVs (`excess_winsorization_cutoffs.csv` and
  `excess_construction_diagnostics.csv` have zero nulls anywhere).
- **G2/G3/G4** — N/A (no inference object produced).
- **G5** — PASS. `baseline_fail_share` ∈ [0,1] on all 468 rows.
- **G6/G7** — PASS, unchanged. All 468 `baseline_failures` rows, all 20
  `desc_outcomes` rows, all 40 sensitivity rows, all 2,910 cutoff rows, all 12
  diagnostics rows and all 410 exclusion rows carry the all-US `sample` label;
  `nation == 'US'` throughout. No cross-national quantity.
- **G8** — PASS, unchanged. COVID bar and n≥2 rule untouched in the diff
  (constants and raise points verbatim); the cycle-1 mutation proof stands.
- **G9** — **PASS (was PARTIAL).** All four previously log-only or parquet-only
  quantities are now citable from a round-folder CSV: month-resolution blackout
  (`baseline_failures.csv`, `granularity == 'month'`), 11,040 winsorized and
  1,629 zero-MAD rows (`excess_construction_diagnostics.csv`), per-route cutoffs
  (`excess_winsorization_cutoffs.csv`), speed-screen fragility
  (`excess_speed_screen_sensitivity.csv`).

### Findings — ADVISORY only (carry forward; none blocks)

B1. **Write-before-assert persists for the two NEW CSVs.** `winsor_cutoffs`
    writes at line 426 before its consistency assert at 429; `sensitivity_df`
    writes at line 632 before the asserts at 641 and 652. These guard internal
    consistency rather than a gate, so no gate can be bypassed — but it is the
    same pattern for the fourth round running. Move the writes below the
    asserts.
B2. **Line 652 hard-codes an overseer diagnostic into production code:**
    `assert int(naive_check["n_removed_from_shipped_series"]) == 1171`. Any
    legitimate future data refresh (a new BTS vintage, a FIX-04 panel change)
    will make the script raise for a non-error. Convert to a logged comparison
    against a value read from the CSV, or parameterise it.
B3. **The one remaining hand-typed date range is the one the director will
    read.** The right-panel title's second line contains the string literal
    `"2022-03..2023-12 mostly unobservable"` (line 882) while the `4/24` beside
    it is computed. Given the adjudication above, the true zero set is two
    blocks. `zero_ym` and `nonzero_ym` are already built at lines 867–873 and
    logged; build the range text from them. Not misleading as written ("mostly",
    plus the computed 4/24), so advisory — but the FINDINGS block must use the
    two-block wording, not this string.
B4. **The sensitivity CSV's `note` does not gloss its own denominators.**
    `n_speed_gt_700mph_diagnostic` is 117 on full-recompute rows and 48 on naive
    rows, and two count columns are NaN by method. Both are correct; neither is
    explained in the CSV, so a reader will read the 117/48 split as an
    inconsistency. One sentence in `note` fixes it.
B5. **Reading guide for the director, not a defect.** The pooled mean of
    `excess_min_w` (0.034744 min ≈ 2 seconds) is a near-cancellation of much
    larger and much more stable decade means (−0.111, +0.752, −0.412, −0.053;
    `excess_speed_screen_sensitivity.csv`, `screen_mph == 50`, both methods).
    That is why the pooled mean swings −59% under a 150 mph screen while every
    decade mean moves by less than 0.08. Do not headline the pooled mean of
    excess; report the decade structure, or a within-route/within-year design.

**VERDICT: PASS**

### FIX-05 block for ROUND_01_FINDINGS.md — FINAL, G9-traced (supersedes the cycle-1 block)

1. **What was built.** For every clean US cell we now have "excess airborne
   minutes": the cell's mean airborne minutes per departure, minus the median of
   the same directed route in the same calendar month over the trailing three
   years, with COVID months (March 2020 – December 2021) never counted and at
   least two prior years required. *(desc_outcomes.csv, column `formula`, rows
   `excess_min` / `excess_min_w` / `excess_z` / `bidir_sum`.)*
2. **Scale of the outcome.** 393,148 cells have an excess value; pooled p1
   −21.23, median 0.011, p99 21.25, mean 0.057, sd 8.85 minutes; after clipping
   the top and bottom 1% within each route ("winsorizing"), mean 0.035, sd 8.20.
   The bidirectional sum (outbound plus return leg, same month) exists for
   389,446 cells (mean 0.070, sd 12.60). *(desc_outcomes.csv, rows
   `excess_min` / `excess_min_w` / `bidir_sum`, `decade == all`.)* A median
   excess of essentially zero is what a correctly-centred baseline should give.
   **Do not headline the pooled mean:** 0.035 minutes is two seconds, and it is
   a near-cancellation of decade means −0.111 (1990s), +0.752 (2000s), −0.412
   (2010s), −0.053 (2020s) *(excess_speed_screen_sensitivity.csv,
   `screen_mph == 50`, `decade` rows)*.
3. **One cell in four has no usable baseline.** 122,727 of 515,875 valid cells
   (23.8%) fail the two-prior-years rule; 1990 and 1991 fail at 100% because no
   prior history exists. *(baseline_failures.csv, `granularity == 'year'`, rows
   `US,1990` … `US,2025`, columns `n_valid_cells`, `n_baseline_fail`,
   `baseline_fail_share`.)*
4. **The rule blacks out the event window — in two blocks, not one.** Baseline
   failure is 0.8684 in 2022 and 0.8750 in 2023, versus 0.1950 in 2024 and
   0.1448 in 2025 *(baseline_failures.csv, `granularity == 'year'`, rows
   `US,2022`–`US,2025`)*. At month resolution the pattern is **two ten-month
   blackouts, not one continuous twenty-two-month one**: the excess and
   bidirectional-sum outcomes exist for **no month in 2022-03 … 2022-12 and no
   month in 2023-03 … 2023-12** (`baseline_fail_share == 1.000000`,
   `n_excess_computed == 0` on all 20 of those rows), while **January and
   February of both years survive** — 1,156 cells in 2022-01, 1,162 in 2022-02,
   1,169 in 2023-01, 1,170 in 2023-02. *(baseline_failures.csv,
   `granularity == 'month'`, rows `US,2022,1` … `US,2023,12`, column
   `n_excess_computed`.)* The reason is mechanical: a January or February target
   can still reach its three-years-back month (January/February 2020), which
   sits just outside the COVID bar, so it keeps two baseline observations; from
   March onward both the two- and three-years-back months fall inside the bar
   and only one survives. **Every surviving 2022 and 2023 cell is therefore a
   January or February cell, and the 2022 ones are entirely before the February
   2022 event this paper studies.** Any 2022 event design must use the raw
   airborne level, a different baseline window agreed with the human, or the
   2024–25 recovery (15,712 cells in 2024, 17,253 in 2025). This is the round's
   principal limitation.
5. **Data-quality screen, and how much it matters.** Cells whose implied ground
   speed (miles ÷ airborne hours) is below 50 mph are excluded from both the
   target and the baseline role — 328 cells panel-wide, 141 of them
   otherwise-clean — and two zero-distance seaplane cells (`SWL↔WFB`) are
   deliberately kept, because 0 miles makes speed undefined rather than slow.
   *(outcome_data_quality_exclusions.csv, `check` values
   `implied_speed_below_50mph`, `distance_zero_cell_ok`,
   `diagnostic_only_gt_1000min_per_dep`; counts also in
   excess_construction_diagnostics.csv, rows `n_implied_speed_below_50mph`,
   `n_implied_speed_below_50mph_cell_ok`, `n_distance_zero_cell_ok`,
   `n_diagnostic_gt_1000min_per_dep_cell_ok`.)* **The 50 mph threshold was NOT
   changed**, but its fragility is now on the record two ways: simply dropping
   the cells implying under 150 mph from the shipped series removes 1,171 cells
   (0.30%) and moves the pooled mean from 0.034744 to 0.014407 (−59%), while
   re-estimating the whole pipeline with a 150 mph gate gives 0.020870. The
   screen is also one-sided — 117 valid cells imply over 700 mph (an
   under-reported airborne time, which reads as a spurious speed-up) and nothing
   screens them. *(excess_speed_screen_sensitivity.csv, 40 rows, columns
   `method` = `naive_filter_shipped_series` vs
   `full_recompute_stricter_valid_mask`, `screen_mph`, `mean`,
   `n_removed_from_shipped_series`, `n_speed_gt_700mph_diagnostic`.)* The
   threshold is a decision for the human, not for an agent.
6. **Winsorization is documented per route.** The 1st/99th-percentile clip is
   computed within each directed route (origin × destination × operator nation)
   over the full 1990–2025 sample, so a 2022 cell's clip boundary can depend on
   that route's 2025 data; 11,040 of 393,148 rows are clipped across 2,910
   routes. *(excess_winsorization_cutoffs.csv, columns `n`, `p1`, `p99`,
   `n_clipped`, `cutoff_computed_on`; excess_construction_diagnostics.csv, row
   `n_winsorized_rows`.)* 55 thin routes have p1 == p99 (75 rows, 0.019%), where
   the clip does nothing at all (`n_clipped == 0` on every one).
7. **`excess_z` must not be used.** The spread measure it divides by (a median
   absolute deviation) is built from at most three numbers, so it can be near
   zero by chance and the ratio then reads as a huge anomaly for an ordinary
   excess value: 5,904 cells exceed |z| = 100 and 429 exceed |z| = 1,000, with a
   99th percentile of 84. The column is marked NOT-FOR-USE pending a
   director-commissioned dispersion measure with a larger pool.
   *(desc_outcomes.csv, row `excess_z`, column `formula`;
   excess_construction_diagnostics.csv, rows `n_excess_z_abs_gt_100`,
   `n_excess_z_abs_gt_1000`.)*
8. **All-US, and only that.** Every row of every FIX-05 deliverable carries the
   sample label "US carriers' airborne time on US-touching international
   segments" and `nation == 'US'`. Nothing here is a carrier-nation comparison;
   the G6/G7 embargo is intact.
9. **The two hard rules hold, and were proven rather than asserted.** No
   baseline uses a COVID month and none uses fewer than two observations; the
   overseer mutation-tested both checks in cycle 1 and both abort the run.

### NEW-06 — RULING CONFIRMED, UNCHANGED

My cycle-1 final ruling on NEW-06 **stands in full and is unaffected by
anything in FIX-05 cycle 2** (which touched no coverage or corridor artifact).
NEW-06 may not ship as commissioned: the five wedge figures
(`fig_raw_wedge_useastasia.png`, `fig_raw_wedge_usindia.png`,
`fig_raw_wedge_usmideast.png`, `fig_raw_wedge_useurope_placebo.png`,
`fig_raw_wedge_bidir.png`) are prohibited in wedge form. Commission it in
exactly the reduced form specified:

1. `raw_wedge_by_corridor.csv` — the full commissioned family (4 corridors × 2
   windows × every operator nation ever observed on the corridor × every month),
   **including the n = 0 rows**, with `n_cells`, `n_cells_with_airborne` and a
   `reason_missing` column tracing the cause to `coverage_by_corridor.csv`
   (`gate_g6_pass` / `share_air_time_valid`).
2. `raw_wedge_diffs.csv` — a completeness record only: every row's
   `n_treated`/`n_control` plus a NaN `diff`, the required `definition` column,
   and an explicit "NaN by construction: no non-US operator reports airborne
   time" note. **Never plotted; no sign, direction or placebo comparison read
   from it anywhere.**
3. **One figure, and it is a data-availability figure, not a wedge figure** —
   corridor × operator-nation × month counts of cells with non-null airborne
   time, showing the zero band for every foreign nation against the populated US
   row, titled as coverage/availability.
4. **Optionally** a US-only raw-*level* corridor series (departures-weighted
   mean `airborne_min_mean` by corridor × month, weights
   `air_time_total / airborne_min_mean` per FIX-04 finding 5), titled **"US
   carriers only — not a cross-national comparison"**, with the 2022-02 line
   drawn. If any excess or bidirectional-sum panel is shown, it must carry the
   **two annotated gaps, 2022-03…2022-12 and 2023-03…2023-12** (finding 4 above)
   — a line that simply stops is not acceptable, and a single annotated
   2022-03…2023-12 gap is now known to be the wrong shape.

Standing conditions survive unchanged: NEW-06 is never a headline; corridor 1 /
ICN may be computed but not reported pending the FIX-02 human ruling; RU and IR
remain labelled MATCH-SENSITIVE; the agent-drafted
`data/raw/events/ban_nations_2022.csv` must be caveated wherever it is used.

---

## NEW-06 review (reduced form) — 2026-09-02 03:10 UTC

**Scope.** NEW-06 as reduced by my binding ruling of 02:14 UTC (re-confirmed
02:43): four permitted deliverables, the five `fig_raw_wedge_*.png` prohibited.
No analysis code was modified by the overseer; all mutation tests were run on a
copy in `/tmp/rev06`.

### Checks run (every number below recomputed by me, not read from a log)

C1. **Provenance and determinism.** Built an isolated root (`/tmp/rev06`,
`data/raw` and `data/interim` symlinked, an empty `rounds/round-1-t100-panel/`
seeded with only `carrier_nation_corridor_coverage.csv` and
`coverage_by_carrier_group.csv`) and ran the script there. Exit **0**; all four
artifacts **byte-identical** (`cmp`) to the ones in the round folder:
`raw_wedge_by_corridor.csv`, `raw_wedge_diffs.csv`,
`figures/fig_data_availability.png`, `figures/fig_us_only_corridor_series.png`.
No network import in the script (`requests|urllib|http|socket|trino|opensky` all
absent). No file under `data/raw/` has an mtime after 21:06. All four outputs
are inside the round folder; nothing was written outside it.

C2. **Extensive margin rebuilt from `panel_extensive.parquet`.** Independent
group-by on (corridor, nation, year, month): `n_routes_active`,
`n_routes_total` and `departures_performed_month_sum` match the CSV on **all
5,824 rows, 0 mismatches, max abs diff 0**.

C3. **Matched-population statistics rebuilt from `panel_excess.parquet`.**
`n_cells_matched`, `n_cells_airborne_valid`, `n_cells_excess_valid`,
`n_cells_bidir_valid`: **0 mismatches**. `airborne_min_mean_wtd` max abs diff
**1.14e-13**, `excess_min_w_wtd` **1.78e-15**, `bidir_sum_wtd` **1.42e-14**;
null patterns identical. The bidirectional dedupe (one row per unordered pair)
reproduces exactly.

C4. **Weight identity.** The ruling required weights `air_time_total /
airborne_min_mean` (FIX-04 finding 5). The script uses
`departures_airborne_eligible`; over all 568,568 cells with non-null
`airborne_min_mean`, `|air_time_total/airborne_min_mean −
departures_airborne_eligible|` maxes at **1.14e-13** — the same quantity.
Requirement met.

C5. **Governing fact.** At panel grain the four corridors hold **194,889**
cells, **114,993** non-US; non-US cells with non-null `airborne_min_mean`:
**0**; with `coverage_ok == True`: **0**. In the shipped CSV, **5,460** non-US
rows carry **0** non-null values across `airborne_min_mean_wtd`,
`excess_min_w_wtd`, `bidir_sum_wtd`. `coverage_by_carrier_group.csv`:
**0 of 1,133,545** `CARRIER_GROUP == 0` rows have `AIR_TIME > 0`.

C6. **Grid completeness / no hidden cell.** 5,824 rows = 4 corridors × 2 windows
× (23, 30, 9, 2 nations) × (72, 19) months; all 8 corridor × window pairs
present; **3,780** rows with `departures_performed_month_sum == 0`. Every
(corridor, nation, year, month) present in `panel_excess.parquet` for 2019–2024
is present in the family: **0 missing**; no corridor has a panel nation absent
from the family nation list.

C7. **`reason_missing` audit.** I re-derived the priority rule from each row's
own columns: **0 mismatches** on 5,824 rows. Category counts: `no_departures`
3,780; `foreign_structural_nonreporting` 1,685 (all non-US, all with
departures > 0; **0** US rows carry it); `observable` 226; `us_baseline_blackout`
120 (their (year, month) set is exactly 2022-03…2022-12 ∪ 2023-03…2023-12, no
other month); `us_baseline_fail_other` 12 (2021-07/08, 2024 months, usindia +
usmideast only); `us_airborne_excluded` 1 (usmideast/US/2021-02, 4 matched
cells, 0 airborne-valid, 11 departures). `us_unmatched` is in the vocabulary and
correctly used **0** times. Cross-checks: 0 `observable` rows with a null
excess; 0 non-`observable` rows with a non-null excess; `covid_flag` and
`in_excess_blackout` reproduce with 0 mismatches.

C8. **Departures reconcile to the raw file.** Family departures per corridor
(useastasia 407,670; useurope_placebo 818,572; usindia 31,788; usmideast
202,818) equal, **exactly**, class-F `DEPARTURES_PERFORMED > 0` on those
airports in 2019–2024 in `t100_raw.parquet` after dropping unmatched/icao-tier
carriers. The dropped residual is 28,506 of 436,176 on useastasia (6.54%: OZ
22,793, LJ 3,648, JX 2,065), 25 of 818,597 on useurope_placebo, **0** on
usindia and usmideast.

C9. **FIX-02 caveat traced, not typed.** `carrier_nation_corridor_coverage.csv`
rows ICN/full_2019_2024: `match_rate_foreign` **0.675340**,
`match_rate_foreign_precision_adjusted` **0.657241**; TPE **0.956194**. The
caveat string's "every other NEW-06 anchor is >= 0.956" is exactly true (min
over non-ICN anchors = 0.956194). Independent confirmation from the raw file:
KR reads 55,197 matched corridor departures against 81,638 actual (67.6%), TW
45,071 against 47,136 (95.6%) — the two rates the caveat quotes.

C10. **Mutation tests (on the `/tmp/rev06` copy, repo code untouched).** (a)
planted `fig_raw_wedge_bidir.png` → script exits **1** naming the file; (b)
`nation != "US"` → `nation != "ZZ"` in the governing-fact check → exits **1**
("568,568 non-US cells…"); (c) `diff = banned − 0.0` → exits **1** ("226 rows …
have a non-null diff"). All three guards are live, not decorative.

C11. **Prohibition, in substance.** No `fig_raw_wedge_*.png` exists. Both PNGs
inspected as rendered images. `fig_data_availability.png` is a 3-state
availability grid (gray/red/blue), no outcome value plotted, no nation-to-nation
comparison possible from it; title reads "Data availability, NOT a wedge --
US-touching international segments, 2019-2024" and the legend is legible.
`fig_us_only_corridor_series.png` is four corridor panels of one US series each;
title "US carriers only -- NOT a cross-national comparison", sample named,
2022-02 dashed line, COVID band, and **two** red blackout bands with a visible
white gap at 2023-01/02. Nothing is clipped in either figure. No line is
interpolated across a blackout: **0** US rows with a non-null excess fall inside
a blackout month.

C12. **Pathology sweep, all 29 round CSVs (not a manifest).** No p-value column
exists anywhere in the two new files (no inference is performed here, correctly).
No coefficient/SE columns. No exploded magnitudes: the largest value in
`raw_wedge_by_corridor.csv` is `airborne_min_mean_wtd` = 916.58 minutes
(usindia, a ~15-hour sector) and the smallest 468.65; `excess_min_w_wtd` ranges
−34.18…55.86; `bidir_sum_wtd` −29.98…111.71. No share/rate column out of [0,1]
in any round CSV. No empty strings in any text column. `python
code/99_validate_outputs.py` → **29 CSVs scanned, 0 FAIL, 0 WARN, exit 0**;
`python code/98_check_trino_usage.py` → **0 FAIL, exit 0**.

C13. **`raw_wedge_diffs.csv`.** 364 rows = 4 corridors × (72 + 19).
`diff_banned_minus_not_banned` non-null: **0/364**. `mean_excess_not_banned`,
`mean_excess_voluntary_avoidance`, `mean_excess_unclassified`: **0/364** non-null
each; `voluntary_avoidance` is its own column and is never pooled (verified in
code and in the file). `n_nations_not_banned_with_data` is 0 in every row.
`status` is the single value "NOT A RESULT -- COMPLETENESS RECORD ONLY" in all
364 rows, and the `definition` text names the agent-drafted, un-human-reviewed
status of `ban_nations_2022.csv`. **But** `mean_excess_banned` is non-null in
**226/364** rows and equals the US corridor `excess_min_w_wtd` series to
**8.9e-16** in every one of them (see blocking item 1).

### Gate status

- **G1** (no empty coef/se/pval; pval ∈ [0,1]) — **N/A, correctly**: this task
  estimates nothing. No coef/se/pval column exists. Nulls in the statistic
  columns are the deliverable and every one carries a `reason_missing` trace.
- **G2** (no |coef| > 100 on log/share outcomes) — **PASS**. No log or share
  outcome; the minute-scale values are physically sane for the sector lengths.
- **G3** (no p = 0.0, no repeated p across a family) — **N/A** (no p-values).
- **G4** (SE scale) — **N/A** (no SEs).
- **G5** (shares ∈ [0,1]; families report full cell counts) — **PASS**. No share
  column here; the family reports 5,824 of 5,824 cells including 3,780 zeros
  and 5,460 structurally empty non-US rows.
- **Round-specific NEW-06 gate** ("every corridor × window appears in the CSV
  even if empty, with n = 0") — **PASS**, 8/8 present, asserted in code and
  independently confirmed.
- **G6 / G7 embargo** — **PASS**. No nation-level number is reported for any
  foreign nation (there are none to report); corridor 1 carries the FIX-02
  caveat on every row; RU is flagged `match_sensitive_nation` (IR never appears
  on an anchor corridor, correctly).
- **G9 (traceability)** — **PARTIAL**, see blocking item 2 and advisory A6.

### Findings — BLOCKING

**B1. `raw_wedge_diffs.csv` ships the wedge's treated arm as a populated,
plottable column under a treatment label.** `mean_excess_banned` is non-null in
226 of 364 rows and is numerically the US corridor excess series (max abs
difference **8.9e-16** against `raw_wedge_by_corridor.csv`'s
`excess_min_w_wtd` for `nation == 'US'`, all 364 rows, null patterns identical).
The whole purpose of this file, per the ruling, is to prove the wedge is
uncomputable; it currently also hands a reader a treated-group time path that
plots in one line of pandas. The `definition` disclosure is unusually good and
`n_nations_banned_with_data` never exceeds 1, but the protection is prose in a
column most readers never print, while the risk is in a column *name*. The
ruling specified "every row's `n_treated`/`n_control` plus a NaN `diff`" — the
group-mean columns are an addition beyond spec, and the one that is populated is
the one that can be misread as the result.
*Required:* either null the four `mean_excess_*` columns (the counts already
carry the completeness content) or rename `mean_excess_banned` so its content is
unmistakable in the header itself (e.g.
`mean_excess_banned_side_US_ONLY_NOT_A_RESULT`), and add an in-code assert that
no `mean_excess_*` column is non-null for a group with
`n_nations_*_with_data > 1` while FIX-02 is blocked.

**B2. The `definition` string does not describe the code.** It states the
pooling is "weighted by `departures_airborne_eligible`". The code
(`06_wedge_availability.py`, the `groups[status]` block) weights nation-level
means by `n_cells_excess_valid`. The two coincide here only because at most one
nation ever has data (I verified the identity holds in all 364 rows) — the
stated definition would be simply wrong the moment a second nation reported. A
definition column that misdescribes its own computation is the exact failure G9
exists to prevent, and this one is the file's only defence against misreading.
*Required:* make the text describe the code, or make the code match the text.

**B3. The fourth deliverable shipped is not the fourth deliverable commissioned,
and the substitution blanks the event window.** The ruling's item 4 is a US-only
**raw-level** series (departures-weighted mean `airborne_min_mean` by corridor ×
month). What shipped plots `excess_min_w` only. In
`raw_wedge_by_corridor.csv`, US `excess_min_w_wtd` is non-null in 52/52/45/43
full-window months (useastasia / useurope_placebo / usindia / usmideast) with
**only January and February present in all of 2022 and 2023**, whereas
`airborne_min_mean_wtd` is non-null in **72/72, 72/72, 67/72 and 71/72** months
— including 2022-03 (useastasia 656.77, useurope_placebo 481.20, usindia
908.79, usmideast 666.18). The excess panel is permitted by the ruling's
conditional clause and carries its two gaps correctly, so the defect is not that
it exists; it is that the commissioned raw-level series was *replaced* rather
than added, leaving the round with no picture of the one outcome it can actually
observe across the event. As it stands the round's only time-series figure is
blank for 20 of the 24 months 2022-03…2023-12.
*Required:* add the raw-level `airborne_min_mean_wtd` panel (same 2×2 layout,
2022-02 line, "US carriers only — not a cross-national comparison" title); keep
the excess panel alongside if wanted.

### Findings — ADVISORY (carry forward; none blocks)

**A1. `departures_performed_month_sum` is a matched-carrier count and the CSV
never says so.** On useastasia it omits 28,506 of 436,176 class-F corridor
departures (6.54%): Asiana 22,793, Jin Air 3,648, Starlux 2,065. KR therefore
reads 55,197 where the raw file has 81,638 (67.6%) and TW 45,071 of 47,136
(95.6%). The corridor-level `fix02_caveat` names Asiana and quotes exactly these
rates, so nothing is hidden — but the column semantics should be stated in the
CSV, and the other three corridors carry no such note (their residual is 25 and
0 departures, so a one-line "matched carriers only" note suffices).

**A2. Two of the 3,780 n=0 rows are false zeros against raw T-100.**
useurope_placebo/AR has 1 real departure (LAN Argentina) in a month the CSV
reads 0, and Portugal (World2Fly, 2 departures) is absent from the corridor's
nation universe entirely. Precision of the n=0 claim is 3,778/3,780 at the
matched grain; 3 departures out of 818,597 on that corridor. The reason string
"this operator nation flew no corridor route this month" should read "no
matched-carrier departures this month".

**A3. No seasonality caveat on `n_routes_active` / `n_routes_total`.** FIX-04
advisory A3 (79% of "exits" are seasonal) is not strictly triggered — no
entry/exit flag is used and there is no event-study use — but the monthly active
route count is a seasonal schedule count and FINDINGS must say so in one line.

**A4. Free y-axis limits across the four panels** of `fig_us_only_corridor_series.png`
(the round file's step 2 asked for fixed limits so panels are comparable).
usindia's ±60-minute axis is driven by two points (2023-01, 2023-02, 55.86 and
~56 in `raw_wedge_by_corridor.csv`) that sit off a 2–3 observation baseline
(FIX-05 advisory). Nothing may be said about them.

**A5. Write-before-assert, fourth occurrence.** Under mutation (c) the script
wrote a `raw_wedge_diffs.csv` with 226 non-null diffs to disk and then exited 1.
Same pattern as FIX-01 advisory 1, FIX-04 A5, FIX-05.

**A6. STATUS.md types four numbers** (nations per corridor: 23, 30, 9, 2) with
no `(file.csv, row)` trace. They are correct — I checked all four — but the
convention is that numbers are written only by code.

**A7. `fig_us_only_corridor_series.png` carries no "not a headline / corridor-1
embargoed" note.** The US series is unaffected by the FIX-02 mapping (US
carriers match by construction), which is the right answer — but the figure
should say it rather than leave a reader to infer it.

### What was verified correct and needs no change

The governing fact and its three runtime guards; the full 4 × 2 × nation × month
family with genuine n=0 rows and a per-row reason trace that reproduces exactly
from the row's own columns; the extensive margin (exact to the raw file); every
weighted statistic (correct denominator, exact to 1e-13); the two-block blackout,
annotated as two blocks in code, in the CSV's reason text and in the rendered
figure; the ICN/TPE caveat sourced live and exactly right; determinism and
isolation; both checkers at exit 0; the prohibition honoured in substance, not
only in filenames.

### NEW-06 block for ROUND_01_FINDINGS.md (G9-traced; use verbatim once B1–B3 land)

**The comparison this task was commissioned to make cannot be made, and the
reason is in the data, not in our method.** NEW-06 was to plot airborne minutes
by operator nationality on four US-international corridors around February 2022.
Foreign airlines do not report airborne time to BTS at all: in
`coverage_by_carrier_group.csv`, **0 of 1,133,545** foreign-carrier-group
segment-months 1990–2025 have `AIR_TIME > 0`. On the four anchor corridors this
leaves **5,460 of 5,824** corridor × nation × month rows in
`raw_wedge_by_corridor.csv` with no outcome value at all — not a small sample, an
empty one. No mapping fix and no estimator can recover it; the only US-comparable
measurement of foreign flight times would have to come from another source
(this is what the Phase-2 OpenSky idea in PROJECT.md is for).

**What the round can honestly say instead, all of it traced:**
1. *Who is observable.* `raw_wedge_by_corridor.csv`: airborne time is
   computable in **358** of 5,824 corridor × nation × month rows, and every one
   of them is `nation == 'US'` (rows with `airborne_min_mean_wtd` non-null).
   Excess minutes are computable in **226** rows, again all US
   (`reason_missing == 'observable'`).
2. *Why each empty cell is empty.* Every row carries a reason:
   **3,780** rows have no departures at all that month; **1,685** are foreign
   carriers that flew but report no airborne time
   (`foreign_structural_nonreporting`); **120** are US months inside the two
   baseline blackouts; **12** are US months that fail the baseline for other
   reasons; **1** is a US month whose cells were too small to measure
   (usmideast, 2021-02, 11 departures).
3. *The event window is the darkest part of the record.* US excess minutes exist
   for only January and February of 2022 and of 2023 on every corridor; the
   blackout is **two ten-month blocks** (2022-03…2022-12 and 2023-03…2023-12),
   not one, because the trailing three-year, COVID-excluded baseline needs two
   candidate months and only January/February reach back past the COVID bar.
   Raw airborne minutes, by contrast, are available for **72 of 72** months on
   useastasia and useurope_placebo, 71 of 72 on usmideast and 67 of 72 on
   usindia.
4. *The difference table is a record of an absence, not a result.*
   `raw_wedge_diffs.csv` has **364** rows and
   `diff_banned_minus_not_banned` is empty in **all 364**, including every row of
   the placebo corridor: the non-banned side is entirely non-US and therefore
   never has data. The file's `status` column says so on every row. The ban list
   it uses (`data/raw/events/ban_nations_2022.csv`) was drafted by an agent and
   has not been reviewed by a human; "voluntary avoidance" is kept as its own
   category and never pooled with "banned".
5. *One corridor is embargoed.* Every useastasia row carries the FIX-02 caveat:
   the foreign-carrier match rate at Seoul/Incheon is **0.6753**
   (precision-adjusted **0.6572**) against **0.9562** at Taipei and ≥ 0.956
   everywhere else (`carrier_nation_corridor_coverage.csv`, full-window rows),
   because Asiana's flights never enter the matched population. Corridor 1
   numbers may be computed but not reported until a human rules on FIX-02.
6. *Route and departure counts are observable for everyone* and are carried in
   the same file, but the monthly active-route count is a seasonal schedule
   count, not market entry and exit, and no event study is run on it here.

**Glossary for this block.** *Corridor* = a set of US↔foreign airport pairs,
both directions. *Airborne time* = minutes wheels-off to wheels-on, averaged over
a route-month and weighted by the departures that actually reported it. *Excess
minutes* = airborne minutes minus the same route-month's own three-year median
in the same calendar month, with COVID months excluded from that median.
*Blackout* = months where that median could not be computed from at least two
clean prior years. *Placebo corridor* = US–Western Europe, chosen because no
differential overflight ban applies there, so it is where we expect to see
nothing.

**VERDICT: FAIL** — three blocking items (B1–B3), all additive: two are text /
column-naming fixes to `raw_wedge_diffs.csv`, one adds a panel that the existing
CSV already contains the numbers for. **No shipped number is wrong**; every
value in both CSVs and both figures reproduced exactly from the parquets, the
prohibition on the five wedge figures held in substance as well as in filenames,
and the documented null is the right call and is honestly presented.

## NEW-06 review (reduced form) — CYCLE 2 of max 3 — 2026-09-02 05:35 UTC

**Scope.** Confirm only that the cycle-1 blocking items B1–B3 landed and that
nothing previously verified was disturbed. Cycle-1 verifications (extensive
margin, n=0 family and `reason_missing` derivation, weight identity, ICN/TPE
embargo, two blackout blocks, substance of the wedge-figure prohibition) are
**not re-litigated**; they were re-confirmed only insofar as the cycle-2 diff
could have touched them. No analysis code was modified by the overseer; all
mutation tests ran on copies in `/tmp/rv6c`, `/tmp/rv6d`, `/tmp/rv6e`.

VERDICT: PASS

### Checks run (numbers recomputed by me from parquet/CSV, not read from a log)

**D0. Nothing previously verified moved.** Column-by-column comparison of
`raw_wedge_by_corridor.csv` against my retained cycle-1 copy
(`/tmp/rev06/rounds/round-1-t100-panel/`), on the identical 5,824-row index:
**every** cycle-1 column identical — `n_routes_active`, `n_routes_total`,
`departures_performed_month_sum`, `n_cells_matched`, `n_cells_airborne_valid`,
`airborne_min_mean_wtd`, `n_cells_excess_valid`, `excess_min_w_wtd`,
`n_cells_bidir_valid`, `bidir_sum_wtd` at max abs diff **0.0** with identical
null patterns, and `covid_flag` / `in_excess_blackout` /
`match_sensitive_nation` / `reason_missing` / `fix02_caveat` / `sample`
byte-equal. The cycle-2 change to this file is purely additive: one weight
column and three note columns. `fig_data_availability.png` is **byte-identical**
to its cycle-1 file.

**D1. B2 — the code now does what the `definition` says, and the shipped values
did not move.** (a) I rebuilt `departures_airborne_eligible_excess_sum` from
`panel_excess.parquet` (sum of `departures_airborne_eligible` over cells with a
non-null `excess_min_w`, by corridor × nation × year × month): max abs diff
**0.0** on 5,824 rows; non-zero in exactly **226** rows, i.e. only where an
excess exists. (b) I re-pooled the four ban-status groups myself under BOTH
weightings. Shipped
`mean_excess_banned_side_US_ONLY_NOT_A_RESULT` matches my departures-weighted
reconstruction to **2.2e-16** with identical null pattern (226/364 non-null),
and matches the cycle-1 cell-count weighting to **8.9e-16** — the two weightings
are analytically identical here because at most one nation ever contributes, and
they differ only at ulp scale. (c) The implementer's specific claim is exactly
true and slightly understates the improvement: shipped
`mean_excess_banned_side_US_ONLY_NOT_A_RESULT` now equals
`raw_wedge_by_corridor.csv`'s US `excess_min_w_wtd` at max abs diff **0.0**
(226/226 rows bit-equal), where the cycle-1 file was 8.9e-16 off. All four
`n_nations_*_with_data` columns reproduce with **0** mismatches;
`diff_banned_minus_not_banned` is null in **364/364**. **B2 discharged.**

**D2. B1 — rename judged, and the new assert mutation-tested.** All four columns
carry the `_side_US_ONLY_NOT_A_RESULT` suffix in the header; the two new
`n_nations_{voluntary_avoidance,unclassified}_with_data` columns were added so
the guard covers all four groups. Mutation test (`/tmp/rv6c`): I cloned the US
family rows as nation `DE` (status `banned` in `ban_nations_2022.csv`), injected
**after** the governing-fact guard so the B1 check is isolated. Result: exit
**1**, message "B1 VIOLATION: 226 rows … `mean_excess_banned_side_US_ONLY_NOT_A_RESULT`
non-null with `n_nations_banned_with_data` > 1 … Refusing to write the file", and
the md5 of `raw_wedge_diffs.csv` was **unchanged** — this guard sits before
`to_csv` and genuinely refuses to write, unlike the write-before-assert pattern
carried as advisory A5 elsewhere. **Ruling on the substance (mine, explicit):
the rename is ACCEPTED.** Reasons: (i) it is verbatim the option my cycle-1
required action offered; (ii) the header is now self-describing — the string
`US_ONLY_NOT_A_RESULT` travels into any axis label, legend or regression output
a reader could produce from it, which prose in a `definition` cell does not;
(iii) the "only one nation is behind this column" claim is no longer prose but a
runtime invariant that refuses to write, and I have proved it fires; (iv)
nulling the column would have destroyed the completeness content — a reader
could no longer verify that the treated side has exactly one nation with data
and that its values coincide with the US series, which is the file's entire
purpose. **Standing condition attached:** the column's values may never enter
`paper/`, `slides/`, PROJECT_STATE or FINDINGS as a level, a change or a sign;
FINDINGS may cite only its non-null **count** (226) and the fact that it is the
US series. **B1 discharged.**

**D3. B3 — raw-level panel present, correct, and additive.**
`figures/fig_us_only_corridor_series_airborne.png` plots `airborne_min_mean_wtd`
(confirmed in code at the `_plot_us_only_panel(value_col="airborne_min_mean_wtd" …)`
call and by eye against the CSV). Non-null months in the full window, recomputed
from `raw_wedge_by_corridor.csv`: useastasia **72/72**, useurope_placebo
**72/72**, usindia **67/72**, usmideast **71/72** — as claimed. Across the
event window 2022-03…2023-12 the raw series is non-null **22/22 on all four
corridors**, against 4/22 for the excess series: the cycle-1 defect (the round's
only time-series figure blank for 20 of 24 event-window months) is fully cured.
useastasia 2022-03 = **656.77345309** (`raw_wedge_by_corridor.csv`, corridor
useastasia / window full_2019_2024 / nation US / 2022-03), matching the claimed
≈656.8 and my cycle-1 number. Title line 1 reads "US carriers only -- not a
cross-national comparison"; sample named; 2022-02 dashed line present; gaps in
usindia/usmideast render as breaks, not interpolation; nothing clipped
(`bbox_inches="tight"`). The excess panel was **kept**, not replaced
(`fig_us_only_corridor_series_excess.png`, both red blackout blocks with the
visible white 2023-01/02 gap, verified as a rendered image). The stale
`fig_us_only_corridor_series.png` is gone from the round folder and from git;
the runtime deletion is mutation-tested — I planted a file under that name in an
isolated root, re-ran, and it was removed with the log line naming both
successors. **B3 discharged**, with advisory A8 below.

**D4. The `NameError` claim — refuted as applied to the reviewed cycle-1 code.**
I still hold the cycle-1 script (`/tmp/rev06/orig.py`, the exact file whose
outputs I proved byte-identical to the cycle-1 round folder). It defines
`FIG_US_ONLY` at line 82 and uses it at lines 601/603 — no undefined name. I
re-ran it today in a fresh isolated root (`/tmp/rv6d`, only `data/raw`,
`data/interim` and three seed CSVs): exit **0**, both cycle-1 figures written.
So no latent crash existed in the code I reviewed; the `NameError` was
introduced by the cycle-2 rename of the constant and fixed within cycle 2. The
implementer's phrasing ("a latent `NameError` that would have crashed the run")
is misleading if read as describing the cycle-1 script. **My cycle-1
determinism and provenance finding stands unamended.**

**D5. Determinism and provenance, re-established independently.** Fresh
isolated root `/tmp/rv6c` (code copied, `data/raw` and `data/interim` symlinked,
round folder seeded with only `carrier_nation_corridor_coverage.csv`,
`coverage_by_carrier_group.csv`, `extensive_margin_churn.csv`): exit **0**, and
all five artifacts **byte-identical** (`cmp`) to the round folder —
`raw_wedge_by_corridor.csv`, `raw_wedge_diffs.csv`, `fig_data_availability.png`,
`fig_us_only_corridor_series_airborne.png`,
`fig_us_only_corridor_series_excess.png`. Nothing was written outside
`rounds/round-1-t100-panel/`.

**D6. The three new note columns are accurate.** Recomputed from
`t100_raw.parquet` × `carrier_nation.parquet` with no reference to the script:
useastasia raw class-F 2019-2024 = **436,176**, matched **407,670**, unmatched
**28,506** = **0.0654** share, top unmatched OZ=**22,793**, LJ=**3,648**,
JX=**2,065** — every figure exact; usindia 31,788/0, usmideast 202,818/0,
useurope_placebo 818,597 / 23 unmatched (E9=14, BF=5, EB=3) — exact. The
seasonality note's **80,260** exits / **63,255** re-entering / median **5** of
432 active months trace exactly to `extensive_margin_churn.csv` (rows `n_exits`,
`n_exits_reentering_ever`, `active_months_per_triple_median`). The false-zero
note is accurate as written and I reconstructed both cases: the AR cell is
carrier `4M` (LAN Argentina, OpenFlights country Argentina) MIA–MAD 2019-10, **1**
departure, refused at FIX-02 as a suffix collision and therefore absent from the
grid while AR exists in the grid's nation universe; the PT case is `WPT`
(World2Fly Portugal) MCO–MAD + MAD–MCO 2024-03, **2** departures, and PT is
indeed absent from the corridor's nation universe. Both are sub-3-departure edge
cases against 818,597 corridor departures.

**D7. Pathology sweep and gates.** All 29 round CSVs re-scanned directly (not a
manifest): no `coef`/`se`/`pval` column exists anywhere in the round — this task
estimates nothing; no p-values, so no p=0.0 and no repeated-p family; no
share/rate column outside [0,1]; no empty cells in any statistic column (nulls
are the deliverable and each carries a `reason_missing` trace); largest
magnitudes are counts (departures, bytes) and minute-scale means
(`airborne_min_mean_wtd` ∈ [468.65, 916.58], physically sane for 8–15h sectors).
`departures_airborne_eligible_excess_sum` ∈ [0, 7,978], 0 nulls. No
`fig_raw_wedge_*.png` anywhere in the repo (`find` → 0 hits) and the script's
end-of-run guard is unchanged. `python code/99_validate_outputs.py` → **29 CSVs,
0 FAIL, 0 WARN, exit 0**; `python code/98_check_trino_usage.py` → **0 FAIL, exit
0**. Every number in the final run-log block located in data: 1,026,729 /
8,810,640 parquet rows, 457,018 non-US matched cells with 0 non-null airborne
and 0 `coverage_ok`, 194,889 / 965,520 corridor-restricted rows, 114,993 non-US
corridor cells, 0 of 1,133,545 `carrier_group==0` rows with `AIR_TIME>0`, 5,824
family rows, 3,780 n=0 rows, 364 diff rows — all reproduced.

### Gate status

- **G1** (no empty coef/se/pval; pval ∈ [0,1]) — **N/A, correctly**: no
  inference is performed and no such column exists.
- **G2** (no |coef| > 100 on log/share outcomes) — **PASS**: no log/share
  outcome; minute-scale values physically sane.
- **G3** (no p = 0.0, no repeated p) — **N/A** (no p-values).
- **G4** (SE scale) — **N/A** (no SEs).
- **G5** (shares ∈ [0,1]; families report full cell counts) — **PASS**: 5,824 of
  5,824 cells reported, including 3,780 zeros and 5,460 structurally empty
  non-US rows; 0 non-US rows carry any non-null statistic.
- **Round-specific NEW-06 gate** (every corridor × window in the CSV even if
  empty, n = 0 included) — **PASS**, 8/8, asserted in code and confirmed.
- **G6 / G7 embargo** — **PASS**: no foreign nation-level number is reported
  (none exists); every useastasia row carries the FIX-02 caveat with ICN
  0.675340 / precision-adjusted 0.657241 and TPE 0.956194 pulled live from
  `carrier_nation_corridor_coverage.csv`; RU/IR flagged `match_sensitive_nation`.
- **G9 (traceability)** — **PASS** (upgraded from cycle-1 PARTIAL): the
  `definition` string now describes the computation it performs, verified
  numerically, and the three advisory notes are recomputable from the round's own
  CSVs.

### Findings — no blocking items

**A8 (new, advisory).** `fig_us_only_corridor_series_airborne.png` inherits
`ax.axhline(0, …)` from the excess panel. On a raw-level series of 470–920
minutes this forces every y-axis to start at 0, so the entire series is
compressed into the top ~15% of each panel and the event-window movement the
figure exists to show is barely readable. The figure is correct, unclipped and
not misleading — this is legibility, not validity — but it must be fixed
(drop the zero line and/or set per-panel limits from the data) before this
figure enters `paper/` or `slides/`. Cycle-1 advisory A4 (free y-limits across
panels) still applies to the excess panel.

**A9 (new, advisory).** `departures_scope_note` defines "matched" as
FIX-02-mapped, which includes the icao match tier; the grid itself drops the
icao tier (`code/04_panel/04_build_panel.py` line 126, per the round-file
override). On useurope_placebo the note therefore says matched = **818,574**
while the grid sums to **818,572**. The gap is exactly **2** departures on one
corridor (the `WPT` pair below); every other corridor has **0** icao-tier
departures and reconciles exactly. Wording fix only: "matched and retained
(icao tier dropped)".

**A10 (new, advisory — belongs in the FIX-02 human decision packet).** Two
concrete mis-mappings surfaced while auditing the note columns, both on the
placebo corridor: `N0` → **AR** via the *iata* tier (OpenFlights has N0 = Norte
Lineas Aereas / Argentina; the 2023–2024 T-100 rows are JFK/MIA/LAX–CDG, i.e.
Norse Atlantic, Norway) — this single code carries **all 1,380** of the corridor's
"AR" departures; and `WPT` → **CA** via the *icao* tier (World2Fly Portugal, 2
departures). Neither affects any reported number — foreign nation-level values
are structurally empty and embargoed — but the nation labels in
`raw_wedge_by_corridor.csv` must not be read as nationality, and both are fresh
evidence for the precision reading of G7.

**A11 (new, advisory).** A third false zero exists that the note does not name:
`raw_wedge_by_corridor.csv` (useurope_placebo, CA, full_2019_2024, 2024-03)
reads `departures_performed_month_sum` = 0 against **2** matched departures in
`t100_raw.parquet` — the same `WPT` pair, seen from the mapped-nation side. At
the matched grain the n=0 claim is therefore **3,779 of 3,780** rows verified
true; no nation is missing from any corridor's universe under the current
mapping (0 right-only cells in my full outer join).

**Carried forward unchanged from cycle 1:** A1 (matched-carrier scope of the
departures counts — now largely discharged by `departures_scope_note`), A3
(seasonality — discharged by `extensive_margin_seasonality_note`), A4 (free
y-limits), A5 (write-before-assert: still true of `raw_wedge_by_corridor.csv`,
which is written before the diffs-stage guards; **not** true of the new B1
guard), A6 (STATUS.md types "23, 30, 9, 2" with no trace — and its 03:00 entry
still names the now-deleted `fig_us_only_corridor_series.png`; the cycle-2
STATUS entry must supersede both), A7 (the US-only figures carry no "not a
headline / corridor-1 embargoed" note).

**VERDICT: PASS** — B1, B2 and B3 all discharged; the fixes are additive; every
cycle-1-verified value is bit-identical; the new weight column, the three note
columns and both new figures reproduce exactly from the parquets; determinism
re-established from an empty root; both checkers exit 0; the wedge-figure
prohibition still holds in substance. NEW-06 remains a documented null and is
never a headline.

---

## ROUND 01 CLOSE — findings audit + OVERALL — 2026-09-02 06:05 UTC

Scope: the director's round-close documents (`ROUND_01_FINDINGS.md`,
`human-readable/PROJECT_STATE.md`, `RESEARCH_LOG.md`, `DECISIONS.md`,
`MIN_SCRIPTS.md`, `FINAL_RUN_LOG.md`), the round's 29 CSVs and 5 figures, and the
git history 8694d59…14dfeb3. Per-task verdicts are not re-litigated. No analysis
code, CSV or director document was modified by me.

### Per-task verdicts (from this file, unchanged)

FIX-00 PASS (21:08) · FIX-01 PASS cycle 2 (21:36) · **FIX-02 BLOCKED-NEEDS-HUMAN,
DEGENERATE-GATE, cycle 3 of 3 (no cycle-3 review section exists; STATUS 22:40
records the terminal state, which is correct under rule 7)** · FIX-03 PASS cycle 2
(00:51) · FIX-04 PASS cycle 2 (01:55) · FIX-05 PASS cycle 2 (02:43) · NEW-06 PASS
cycle 2 (05:35). All seven tasks terminal.

### Close checks re-run by me

- `python code/99_validate_outputs.py` → "29 CSVs scanned, 0 FAIL, 0 WARN", **exit 0**.
- `python code/98_check_trino_usage.py` → "0 FAIL", **exit 0**. No OpenSky pull this
  round (round file: "touches NO OpenSky data"), so T1–T9 are vacuously satisfied
  and `logs/opensky_queries.log` is correctly absent.
- All 29 result CSVs are inside `rounds/round-1-t100-panel/`; `find` over the repo
  outside `data/` and `rounds/` returns **zero** stray result CSVs.
- `FINAL_RUN_LOG.md` header present ("generated 2026-09-02 05:36:03 — git 14dfeb3"),
  mtime 05:36:03 > newest round CSV 05:23:39. Generated, not hand-edited.
- `MIN_SCRIPTS.md` header "generated 2026-09-02 05:45:50 by code/sync_min_scripts.py",
  this round; its 8-script minimal set equals the 8 analysis scripts in git.
- `human-readable/PRESENTATION.md` untouched (mtime 2026-09-01 01:30, clean in
  `git status`). PROJECT_STATE.md refreshed 05:44:36.
- Pathology sweep over **all 29 CSVs, file by file, not a manifest**: no `coef`/`se`/
  `pval` column exists anywhere in the round (no inference was run — consistent with
  the round file, which commissions only construction and raw means), so G2/G3/G4
  are N/A rather than passed-by-assertion; every `*share*`/`*rate*`/`*precision*`
  column in every file lies in [0,1] (0 violations); no exploded magnitudes; no
  empty cells in any cited column.

### Findings audit — item 1: every number traced (the substance)

I re-derived every numeric claim in `ROUND_01_FINDINGS.md` (≈90 figures) and in
`PROJECT_STATE.md` from the cited CSV at the cited row. **Zero transcription errors,
zero mis-traced citations, zero numbers drawn from prose.** Selected recomputations:

- Headline: `coverage_by_carrier_group.csv`, 36 rows `carrier_group==0` →
  n_rows 1,133,545; n_air_gt0 **0**; n_ramp_gt0 **0**; n_air_null **0**;
  n_ramp_null **0**; n_air_zero 1,133,545 and n_ramp_zero 1,133,545 (literal zeros,
  as claimed). `coverage_column_availability.csv`: foreign share_gt0 = 1.000000 dep,
  1.000000 distance, 0.840383 seats, 0.835525 pax, 0.000000 air/ramp/depsched;
  `(us, AIR_TIME)` 1,523,392/1,528,925 = 0.996381. All match the prose to the digit.
- **Independent re-derivation from `data/raw/` (not from any project artifact):** I
  re-read five raw year files (1995, 2008, 2019, 2022, 2025) and counted
  `CARRIER_GROUP==0` rows with `AIR_TIME>0`: 27,150/0, 27,956/0, 41,958/0, 42,821/0,
  50,399/0, zero nulls — row counts identical to the CSV's per-year values. The
  headline reproduces from the vendor files.
- G6: `coverage_audit.csv` 2,249 cells, 2,213 fail (max failing share exactly 0.0),
  36 pass, all `nation=='US'`, range 0.992300–1.0; dep-weighted failing share
  0.397647; `coverage_excluded_cells.csv` is a perfect two-way match to the failing
  set (0 fail-but-unlisted, 0 pass-but-listed). `coverage_by_corridor.csv`: 908
  non-US cells, **0** pass, and 0 pass within each of the four corridors separately
  (337/425/20/126) — the "identically on treated and placebo" claim is not vacuous.
- G7 split: `carrier_nation_matchrate.csv` foreign 0.902110 / 0.863077 / 0.843978;
  overall 0.959201; `foreign_classF` 0.930256 / 0.891128. Sensitivity:
  margin 41,643.3 dep; icao tier 47,345 dep at share_home0_dep 0.493759; excl-icao
  foreign coverage 0.899711. KV→RU 222,939 (0.0), RV→IR 191,266 (0.0), TA→CR 347,572
  (0.003783), VX(1)+B0+WO→US 19,410+10,871+4,887 = 35,168 (all 0.0), N0/Z0→AR
  7,272/5,630, WPT→CA 2. Unmatched 244 codes / 1,931,914 dep; AV 254,450; OZ 204,972
  (22,793 class-F). ICN 0.675340 / 0.657241; TPE 0.956194; other 20 anchors ≥0.999541.
- Name-churn null: flips file gives 146+23+4 = **173 eras across 67+11+2 = 80 codes**,
  4 cross-border rows on exactly 2 codes (AI, K8), both `resolution` = "unresolved …
  needs human review"; 22 suffix refusals; refused class-F departures 178,674.
- Panel/outcomes: 1,026,729 cells, 517,076 `cell_ok`, 457,018 G6-flagged, 1,681
  mixed-mapping cells, 311 routes / 41,348 dep lost, 60 rows / 483 dep and 8 rows /
  9 dep gap-excluded, 4,133 routes, `n_nations==1` in all four decade rows.
  `desc_outcomes.csv` `excess_min_w`/`all`: n 393,148, p50 0.011486, mean 0.034744,
  sd 8.196160; `bidir_sum` n 389,446, mean 0.069697, sd 12.603801.
- Blackouts: `baseline_failures.csv` month rows — `n_excess_computed == 0` on all 20
  rows 2022-03…2022-12 and 2023-03…2023-12; survivors 1,156 / 1,162 / 1,169 / 1,170;
  2024 15,712, 2025 17,253; 1990–91 fail share 1.0; year rows sum to 122,727 of
  515,875 (23.79%). **Re-derived independently from `data/interim/panel_excess.parquet`:
  identical monthly counts.**
- Speed screen: naive 150 mph removes 1,171 of 393,148 (0.298%), mean 0.034744 →
  0.014407, sum 13,659.57 → 5,647.26 (removed 8,012.31 = 58.66%); full recompute at
  150 mph mean 0.020870; 117 cells >700 mph on the full-recompute row (48 on the
  naive rows — the findings correctly cite the 117 row).
- Guards, verified by me on the parquet, not from the log: cells with
  `coverage_ok == False` **and** non-null `airborne_min_mean` = **0**; rows with
  `baseline_n < 2` and non-null `excess_min` = **0**; three randomly drawn cells'
  `baseline_med` recomputed from `panel_monthly` logic (LHR→BOS 1993-12 425.555556;
  YEG→PHX 2009-03 173.419355; DFW→GRU 2014-07 577.660377) match the shipped values
  and their excesses exactly.
- NEW-06: 5,824 rows = 8/8 corridor×window cells present; airborne non-null 358 and
  excess non-null 226, **all `nation=='US'`**; 5,460 non-US rows with 0 non-null
  outcomes of any kind; `reason_missing` 3,780 / 1,685 / 226 / 120 / 12 / 1 (sums to
  5,824); diffs 364 rows, `diff_banned_minus_not_banned` null in 364/364 including
  all 91 placebo rows; US level 72/72, 72/72, 71/72, 67/72; nations 23/30/9/2.
  No `fig_raw_wedge_*` figure exists and the script asserts their absence (line 820).

Trace-quality deviations (values all correct; the citation is the defect):
(i) `PROJECT_STATE.md` cites every number with a **file name but no row/spec** —
G9 and rule 5 require `(file.csv, row/spec)`. (ii) FINDINGS §3e cites the speed-screen
counts to "outcome_data_quality_exclusions.csv / excess_construction_diagnostics.csv"
with no row, though the rows exist (`n_implied_speed_below_50mph`, `_cell_ok`,
`n_distance_zero_cell_ok`). (iii) Three FINDINGS figures are hand-derived, not
transcribed: 23.8%, 0.30%, and 8,012 / 58.7% (the last is a subtraction of two CSV
cells). Each is arithmetically correct and shows its inputs; they should be marked
as derived.

### Findings audit — item 2: script list vs git

`git diff --stat 69280bc^ 14dfeb3 -- code/` touches **exactly 8 files, all new,
4,927 insertions**, and they are exactly the 8 listed in §4 with the correct commit
attributed to each. `05_build_excess.py` does appear in the FIX-04 commit 57d3fd8
(+503) and again in feabab9 (+444/−…): the director's disclosure of the premature
sweep is accurate. **The analysis-script list reconciles perfectly.** One defect in
the surrounding paragraph — see required correction 4.

### Findings audit — items 3–8

3. **Headline correctly stated, not overstated.** Independent of the blocked
   mapping (`03b_carrier_group_coverage.py` reads only `data/raw/t100/*.csv`; the
   strings `parquet` and `carrier_nation` do not appear in its data path), verified
   by me from the vendor files, and correctly scoped ("US-touching international
   segments"). One residual: the claim that this is the T-100(f) *form's* design is
   an inference from the data pattern, not yet checked against BTS documentation —
   see required correction 8.
4. **DEGENERATE-GATE reported split, neither reading chosen.** §3b gives both
   readings, both thresholds, the knife-edge margin and the tier that flips it, and
   states "Neither reading of G7 is presented as the answer anywhere in this round."
   I found no place in FINDINGS, PROJECT_STATE, RESEARCH_LOG or DECISIONS where one
   reading is adopted. D-01 records "Choice: None". **PASS** — with the caveat in
   required correction 2 (the shipped panel already implements part of option (a3),
   and that is not disclosed where the split is described).
5. **Two-block blackout wording.** FINDINGS §3d/§5, PROJECT_STATE, RESEARCH_LOG and
   DECISIONS D-04 all use "2022-03…2022-12 and 2023-03…2023-12, Jan/Feb computable".
   `fig_us_only_corridor_series_excess.png` shades both blocks with the 2023-01/02
   gap visible. **The prose is correct.** The *airborne* figure is not — correction 3.
6. **Embargoes.** No foreign nation-level outcome is reported anywhere (none exists).
   `excess_z` appears only as NOT-FOR-USE. The ban dictionary's agent-drafted,
   human-unreviewed status is disclosed in §3f, §5 and inside the CSV's `definition`.
   The pooled mean is explicitly de-headlined ("Do not headline the pooled mean").
   No cross-national comparison is implied; both US-only figures are titled "US
   carriers only -- not a cross-national comparison". **Two gaps:** the corridor-1
   embargo is stated more broadly in §3b than it is practised in §3f (corrections 1
   and 2 of the ruling's own wording, "must not be reported *as a corridor result*").
7. **Nulls as deliverables.** The placebo's emptiness is reported three times
   (§3a, §3f, PROJECT_STATE) and correctly interpreted as evidence about the source
   rather than about behaviour; the all-NaN diffs table ships as a completeness
   record; the name-churn null and the extensive-margin churn null are both reported.
   **PASS.**
8. **DECISIONS/register.** D-01, D-02, D-04, D-05 all carry "Choice: None" with the
   conservative default named; D-03 (close the round) is procedural and inside the
   standing rules. Rule 11 respected. PROJECT_STATE is genuinely undergrad-RA
   register — glosses T-100, ADS-B, excess time, bidirectional sum, extensive margin,
   z-score, and states dead ends. **PASS**, subject to corrections 5–7.

### Gate status

- **G1** N/A (no inference objects) — separately, no empty cells in any cited column.
- **G2 / G3 / G4** N/A — no coefficient, SE or p-value column exists in the round.
- **G5** PASS — every share/rate/precision column in all 29 CSVs ∈ [0,1]; every
  family reports its full cell count (2,249 coverage cells; 5,824 wedge cells
  including 3,780 zeros; 364 diff rows including the placebo).
- **G6** PASS as designed and enforced (2,213 exclusions written and reconciled).
- **G7** **DEGENERATE-GATE, BLOCKED-NEEDS-HUMAN** — correctly declared, neither
  reading chosen, decision-grade packet in the round folder.
- **G8** PASS — enforced in code and mutation-tested; the two rules were not relaxed.
- **G9** **PARTIAL** — FINDINGS complies (with the three derived figures noted);
  PROJECT_STATE gives file-level but not row-level traces; DECISIONS.md and
  RESEARCH_LOG.md carry typed result numbers outside rule 5's sanctioned exception.

### Required corrections (documentation only — no analysis re-run, no number changes)

1. **`ROUND_01_FINDINGS.md` §3f and `figures/fig_data_availability.png`: label the
   nation counts as mapping-derived.** "23 nations ever observed on US–East Asia,
   30 on the Europe placebo…" is a FIX-02-derived, MATCH-SENSITIVE quantity, and the
   availability grid prints those labels (including the "AR" row on the placebo,
   which is `N0`/`Z0` Norse Atlantic, and the "CA" row carrying the 2-departure
   `WPT` false zero) to a human's eye with no caveat. Add the NEW-06 cycle-2
   advisory A10 sentence — "these are mapped labels, not verified nationalities" —
   next to the counts and in the figure caption.
2. **§3c must disclose that the shipped panel drops the `icao` match tier**
   (`panel_filter_log.csv`, row `icao_tier_dropped`, 347 rows) under the overseer's
   conservative ruling. This matters because it is materially option **(a3)** of the
   decision the human is being asked to make in D-01, already partly in force. State
   it as a conservative default, explicitly **not** a resolution of the gate. Same
   sentence belongs in D-01 (which mentions it) and in §2's FIX-04 bullet (which
   does not).
3. **`figures/fig_us_only_corridor_series_airborne.png` subtitle contradicts the
   round's own finding.** It reads "…the 2022-03..2023-12 event window where the
   excess-level series (below) is blacked out", i.e. the single-block shape, while
   the excess panel beside it plots real 2023-01/02 points and the FINDINGS say two
   ten-month blocks. Regenerate the caption with the two-block wording, or add this
   to §5's carried advisories alongside the y-axis item (it is currently listed for
   the y-axis only).
4. **§4's ENV paragraph is inaccurate.** Commit 8694d59 did **not** commit
   `code/utils.py` (that file's last commit is 8221a6c; it was restored in the
   working tree with `git checkout --`, per STATUS 21:05). What 8694d59 actually
   added under `code/` is `98_check_trino_usage.py` (+58) and `opensky_query.py`
   (+307), neither of which is named. Restate the paragraph so the git reconciliation
   is literally true; the 8-script analysis list itself is correct and stays.
5. **`PROJECT_STATE.md`: add row/spec traces.** Every number there is correct and I
   located all of them, but G9 requires `(file.csv, row/spec)`; the file currently
   gives file names only (e.g. 1,133,545 → add "36 rows `carrier_group==0`,
   `n_rows` summed"; 0.9021/0.8631 → "row `foreign`"; "about 79%" → "row
   `share_exits_reentering_ever` = 0.788126").
6. **`RESEARCH_LOG.md` item 5 cites the wrong decision ID:** the blackout /
   baseline-rule decision is **D-04**, not D-03 (D-03 is the round-close decision).
7. **Typed result numbers in `DECISIONS.md` and `RESEARCH_LOG.md`.** Rule 5's
   sanctioned exception names only FINDINGS and PROJECT_STATE. Every number I
   checked in both files is correct and file-traced, and a decision packet arguably
   needs its evidence inline — so this needs either a human ruling that extends the
   exception to DECISIONS/RESEARCH_LOG with the same inline-trace requirement, or
   the numbers replaced by pointers. Do not silently continue the practice.
8. **Soften the one unverified external claim.** "This is a property of BTS's
   reporting schedule — the foreign-carrier form (T-100(f)) collects volume, not
   block or airborne time" is an inference; "(Confirming against BTS's published
   T-100(f) data-element list needs an attended web session; it is a confirmation
   step, not a doubt)" pre-judges it. The *pattern* is established beyond doubt (I
   reproduced it from the vendor files); the *form's* content is not yet sourced.
   Neutral wording, with next-steps item 9 kept.
9. **§3d, one clause is slightly wrong:** "Every surviving 2022 cell is therefore
   *before* the February-2022 event." The 1,162 surviving 2022-02 cells are *in* the
   event month (the Russian ban lands 24–28 Feb 2022), so they are contemporaneous,
   not pre-event. Restate as "in or before the event month".

Advisories (no action required this round): the `us` label in
`coverage_column_availability.csv` pools `CARRIER_GROUP == 7` (382 rows, 2002–2004),
whose US status is asserted by convention in `03b_carrier_group_coverage.py:39` and
disclosed only as an "oddity" in §3e — immaterial at 0.025% of US rows, but a
referee could ask. `FINAL_RUN_LOG.md` line 2 reads "Active round: # STATUS", i.e.
`build_run_log.py` is picking up STATUS.md's first line instead of the round path —
cosmetic, belongs in the next cleanup task. The NEW-06 advisory B4 (the 117 vs 48
`n_speed_gt_700mph_diagnostic` split by method) is not in §5's carried list, though
§3e cites the right one.

## OVERALL: NOT READY FOR HUMAN

Round 1 set out to measure a carrier-nationality wedge in airborne time on
US-touching international segments and instead established, at maximal strength,
that the wedge is not measurable in this source: across all 36 raw year files
1990–2025, 1,133,545 foreign-carrier rows contain zero positive airborne times,
zero positive ramp times and zero nulls — literal zeros in every row
(`coverage_by_carrier_group.csv`, `carrier_group == 0`) — while US carriers in the
very same files report airborne time in 0.996381 of rows
(`coverage_column_availability.csv`, row `(us, AIR_TIME)`). I reproduced that from
the vendor CSVs myself, independent of every project artifact, and it does not
depend on the blocked nationality mapping. The consequence propagates exactly as
the documents say: 2,213 of 2,249 nation × year coverage cells fail G6 at a share
of exactly 0.0, the 36 survivors are all US (`coverage_audit.csv`), and 0 of 908
non-US anchor-corridor cells pass — identically on the three treated corridors and
on the European placebo (`coverage_by_corridor.csv`), which is what tells us this is
a data property rather than a behavioural null. What was delivered instead is
solid: a reconciled ingest (2,662,470 rows read and written, 0 dropped,
`ingest_rowcounts.csv`), a 1,026,729-cell directed panel of which 517,076 pass
`cell_ok` with a mutation-tested guard that writes null rather than a fabricated
zero (`panel_filter_log.csv`), a US-only excess series on 393,148 cells centred at
median 0.011486 minutes (`desc_outcomes.csv`, `excess_min_w`, `decade == all`), and
a complete 5,824-row availability family in which every one of the 5,460 empty
non-US cells carries a machine-written reason (`raw_wedge_by_corridor.csv`). Two
ten-month blackouts (2022-03…2022-12, 2023-03…2023-12, Jan/Feb of both years
surviving at 1,156/1,162/1,169/1,170 cells — `baseline_failures.csv`) put the
excess outcome out of reach exactly at the motivating event, which is the round's
principal limitation and is stated as such. **Every number in the two human-facing
documents traced and recomputed correctly — I found no transcription or citation
error in ~90 checks.** The NOT READY verdict rests entirely on nine documentation
defects, three of which could actually mislead the human who is about to rule: a
shipped figure caption that still asserts the single-block blackout the round
disproved (correction 3), an undisclosed sample restriction that is itself one of
the options in the pending D-01 ruling (correction 2), and mapped-nation labels
printed on a figure and counted in the prose without the MATCH-SENSITIVE caveat the
task review demanded (correction 1). None requires re-running anything.

**Open flags:** DEGENERATE-GATE / BLOCKED-NEEDS-HUMAN on FIX-02 (G7 split
0.902110 coverage vs 0.863077 precision-adjusted, neither chosen, knife-edge by
41,643 departures against an `icao` tier of 47,345 at 0.493759 home-zero);
MATCH-SENSITIVE on mapped RU and IR (and now AR, CR, and three codes mis-mapped to
US); PLACEBO-EMPTY rather than PLACEBO-FAIL (the placebo is uninformative because
the data are absent, not because the design failed); `excess_z` NOT-FOR-USE;
`ban_nations_2022.csv` agent-drafted and human-unreviewed; the BTS T-100(f) form
citation unverified pending an attended web session.

**The three results a referee will attack first:**
1. *"Foreign carriers never report airborne time"* — attack: "you downloaded the
   wrong file / mis-parsed zeros as data." **Defended.** Same-file US completeness
   at 0.996381, zeros not blanks, 36 consecutive years, no exception, reproduced
   from raw by two independent implementations (the task script and mine). The only
   residual is the documentary citation to BTS's T-100(f) element list (correction 8).
2. *The carrier→nation mapping* — attack: "your nationality variable is wrong, so
   nothing built on it means anything." **Not defended, and correctly so:** the gate
   is declared degenerate, both readings are on the record, the specific failures are
   named (KV→RU 222,939 dep at home share 0.0; RV→IR 191,266; TA→CR 347,572;
   N0/Z0→AR; Asiana unmatched, ICN foreign coverage 0.675340), and no nation-level
   result is claimed. The correct posture, pending the human's D-01 ruling.
3. *The excess-time construction* — attack: "your outcome is missing exactly when
   your event happens, and its pooled mean is a knife-edge artifact of a one-sided
   speed screen." **Half defended.** The blackout is documented to the month and not
   papered over; the pooled mean is explicitly de-headlined and its −59% move under a
   150 mph screen is on the record (0.034744 → 0.014407, with 58.7% of the outcome's
   sum on 0.30% of cells). Undefended by design: the screen threshold and the
   baseline rule are D-05 and D-04, reserved to the human.

**Top items the human must decide (all evidence is in the round folder; agents need
nothing further):** (1) D-01 — which reading of G7 governs, and whether a dated
carrier-nationality source replaces the 2014 OpenFlights lookup; note that option
(a3) is already partly in force in the shipped panel (correction 2). (2) D-02 — the
Phase-1 re-scope among (A) volume/extensive margin, (B) US-only route-exposure
design, (C) accelerate OpenSky ADS-B, (D) acquire foreign block-time data; the
director's non-binding read is (C), and the attended extract request is the single
highest-value next action. (3) D-04 — the baseline rule against the 2022–23
blackouts. (4) D-05 — the implied-speed screen threshold and whether it becomes
two-sided. (5) Whether rule 5's number-citation exception extends to DECISIONS.md
and RESEARCH_LOG.md (correction 7).

Return path: corrections 1–9 are director-side text and one figure caption. On
their completion I will re-check only those items and flip this section to READY.

---

## ROUND 01 close — final verification of the 9 corrections — 2026-09-02 (overseer)
VERDICT: PASS (deltas only; prior audits not re-litigated)

**Checks run (recomputed from CSVs, not read from prose):**
- No CSV changed under the figure work. `git diff HEAD` over `rounds/round-1-t100-panel/`
  returns exactly one changed file: `figures/fig_us_only_corridor_series_airborne.png`.
  `raw_wedge_by_corridor.csv` and `raw_wedge_diffs.csv` were rewritten this cycle
  (mtime 06:00 vs commit 14dfeb3 at 05:36) and are **byte-identical to HEAD**; so are
  `fig_data_availability.png` and `fig_us_only_corridor_series_excess.png`. The
  determinism claim is therefore independently corroborated, not taken on report.
- Caption wording is true of the data, not just derived from a constant. From
  `raw_wedge_by_corridor.csv` (nation US, window full_2019_2024, 4 corridors):
  `airborne_min_mean_wtd` non-null 4/4 corridors in **every one of the 20 blackout
  months**; `excess_min_w_wtd` non-null 0/4 in all 20; non-null 4/4 in 2022-01,
  2022-02, 2023-01, 2023-02. The programmatic `blackout_desc`
  ("2022-03..2022-12 and 2023-03..2023-12") and `computable_desc`
  ("2022-01/02 and 2023-01/02") both match. Both captions now consume the same
  string, so drift is structurally prevented.
- §3d numbers re-derived from `baseline_failures.csv` (granularity == month):
  n_excess_computed = 1156 (2022-01), **1162 (2022-02)**, 1169 (2023-01), 1170
  (2023-02), and 0 in each of the twenty 2022-03…12 / 2023-03…12 rows. The new
  "in or before the event month" wording and the contemporaneity note are correct.
- icao disclosure: `panel_filter_log.csv`, step `icao_tier_dropped`, n_dropped =
  **347** (1,819,635 -> 1,819,288). Present in all three commissioned places —
  ROUND_01_FINDINGS §3c (L250-255), §2 FIX-04 bullet (L108-111), DECISIONS D-01
  options (L32-38) — each stating conservative default, materially option (a3),
  not a resolution of the gate.
- §3f MATCH-SENSITIVE naming: `carrier_nation_precision_audit.csv` rows `N0`
  (Norse Atlantic Airways -> nation_iso2 **AR**, 7,272 dep, home share 0.0),
  `Z0` (Norse Atlantic UK -> **AR**, 5,630 dep, home share 0.0), `WPT`
  (World2Fly Portugal -> **CA**, **2** dep, home share 0.0). Both AR and CA are
  in the placebo corridor's 30-nation list. Nation counts recomputed from
  `raw_wedge_by_corridor.csv`: useastasia 23, useurope_placebo 30, usmideast 9,
  usindia 2 — exact.
- ENV paragraph (§4, L442-450): `git show --stat 8694d59` adds under `code/`
  exactly `98_check_trino_usage.py` and `opensky_query.py`. Accurate as written,
  and correctly scoped to `code/`.
- PROJECT_STATE traces (correction 5), six recomputed, all exact:
  1,133,545 / 0 (`coverage_by_carrier_group.csv`, 36 rows carrier_group==0);
  2,662,470 read = written, 0 dropped (`ingest_rowcounts.csv`, 36 file rows);
  p50 = 0.011486 (`desc_outcomes.csv`, excess_min_w, decade==all);
  0.90211 and 0.863077 (`carrier_nation_matchrate.csv`, category==foreign,
  `match_rate_weighted` / `precision_adjusted_match_rate_home0`);
  0.788126 (`extensive_margin_churn.csv`); 5,904 (`excess_construction_diagnostics.csv`).
- RESEARCH_LOG item 5 now cites **D-04** (correction 6). Typed-number headers
  present in both RESEARCH_LOG.md and DECISIONS.md; D-06 raised as
  DECISION-PENDING (correction 7). T-100(f) pattern/inference split present in the
  headline (L32-41), §6 item 9, RESEARCH_LOG item 1 and PROJECT_STATE L51-55
  (correction 8). Three optional advisories folded in: group-7 pooling (§3e
  L358-363), build_run_log "Active round" cosmetic bug (§6 item 8), B4 117-vs-48
  conditioning split (§5 L485-489).
- Environment: `python code/99_validate_outputs.py` -> "29 CSVs scanned, 0 FAIL,
  0 WARN", exit 0 (run by me). `python code/98_check_trino_usage.py` -> 0 FAIL,
  exit 0 (run by me). No OpenSky pull this round, so no `logs/opensky_queries.log`
  is expected or required. `FINAL_RUN_LOG.md` header line present ("generated
  2026-09-02 06:07:54 — git 14dfeb3"), mtime 06:07 — newer than every round CSV
  (latest 06:00). `MIN_SCRIPTS.md`: I re-ran `code/sync_min_scripts.py` into a
  scratch comparison (exit 0, 15 artifacts / 7 scripts) — body byte-identical to
  the director's file apart from the header timestamp; original restored.
  `human-readable/PRESENTATION.md` untouched by agents (last commit 8221a6c, diff
  clean). No `fig_raw_wedge_*.png` exists; the script's own end-of-run assertion
  logged confirmation; `logs/06_wedge_availability.log` shows 0 warnings/errors.
- Figures rendered and read, not assumed. `fig_us_only_corridor_series_excess.png`
  and `fig_data_availability.png` are correct and legible. The airborne panel's
  y-axis now autoscales per corridor as intended (recomputed limits: useastasia
  569.9–697.8, useurope_placebo 466.5–497.1, usindia 794.7–925.6, usmideast
  611.4–814.9); the squeeze is gone and the two-block subtitle is on its face.

**Gate status:** G1–G5 PASS (validator 29/0/0, exit 0; no inferential CSV was
produced or altered this cycle). G6 PASS (unchanged). **G7 remains split and
unresolved — BLOCKED-NEEDS-HUMAN / DEGENERATE-GATE, correctly not chosen by any
agent**, and the correction-2 disclosure now makes explicit that the shipped
panel already runs part of option (a3) as a conservative default without
pre-committing the human. G8 PASS (baseline rules enforced, not relaxed). G9 PASS
(every FINDINGS number carries a `(file.csv, row/spec)` trace; the new §3f, §3c
and §3d numbers all recomputed above).

**Findings (all residual, none blocking):**
1. **Stale advisory text, conservative direction.** ROUND_01_FINDINGS §5
   (L478-481) and §6 item 8 (L546-548) still describe the airborne figure's
   squeezed y-axis and single-block subtitle as open defects "the econometrician
   is regenerating". Both are fixed in the artifact I just read. Direction of the
   error is safe (over-caveating), no number or conclusion is touched. CARRIED as
   advisory A1.
2. **New, minor layout regression on the airborne figure.** The one-line
   unwrapped suptitle plus `bbox_inches="tight"` widened the canvas from
   3,819 to 5,763 px (aspect 2.46 -> 3.71); the plot body now occupies 41% of the
   image width, against 62% before and 88% on the excess figure. Content is
   correct and legible at native resolution; this is layout only, and the figure
   is in no paper/ or slides/ artifact. One-line fix (wrap the subtitle before
   `suptitle`). CARRIED as advisory A2, to be fixed in the same cleanup edit as A1.
3. **Correction 8 did not propagate to the figure.** `fig_data_availability.png`
   subtitle still asserts the mechanism as fact: "structurally absent for every
   foreign operator (T-100(f) reporting schedule)", while the prose now correctly
   labels that attribution an inference. I grepped every shipped artifact: the
   unhedged phrasing exists **only** in this figure caption (source:
   `code/06_wedge/06_wedge_availability.py`) — not in any CSV, TeX table, paper,
   or slide. Unlike the AR/CA label gap, which §3f discloses, this one is
   undisclosed. CARRIED as advisory A3.
4. **Code nit, inert here.** In the new autoscale branch,
   `pad = 0.08 * (finite_y.max() - finite_y.min() or 1.0)` binds `or` to the
   minimum, not to the range; the intended guard is `(max - min) or 1.0`. Harmless
   at current data (per-corridor minima 468–804, n >= 67), but a constant or
   single-observation series would yield `set_ylim(v, v)`. CARRIED as advisory A4.
5. **Owed mechanics, not defects.** STATUS.md has no round-close entry yet, and
   the close commit (findings, RESEARCH_LOG, DECISIONS, PROJECT_STATE,
   MIN_SCRIPTS, FINAL_RUN_LOG, the figure fix, the script edit) is still
   uncommitted. §4's "reconciled against commits 69280bc … 14dfeb3" will be one
   commit short once the close commit lands, which touches
   `code/06_wedge/06_wedge_availability.py` (already listed by script, so the
   script list itself stays reconciled).

**Ruling on correction 7 (typed numbers in DECISIONS.md / RESEARCH_LOG.md).**
Rule 5's text is not genuinely ambiguous: "No one types a result number into a
log, report, or commit message… The one sanctioned exception: ROUND_NN_FINDINGS.md
and human-readable/PROJECT_STATE.md." RESEARCH_LOG.md is a log by name. The
conservative default was therefore pointers now, extension later — restoring
numbers after a ruling of (i) is as mechanical as removing them after (ii), so
the reversible-either-way argument does not favour keeping. The director picked
the non-conservative branch of a rule an agent may not widen. **I am not blocking
on it**, for three reasons that are specific and not general licence: every number
in both files was audited correct and carries an inline `(file.csv, row/spec)`
trace, so the drift risk rule 5 exists to stop is neutralised; the practice is
disclosed in both file headers and escalated as D-06 rather than continued
silently; and neither file feeds paper/, slides/, or PROJECT_STATE. **Conditions,
binding on the next round:** no further numbers may be added to DECISIONS.md or
RESEARCH_LOG.md until D-06 is ruled; if the human rules (ii), or has not ruled by
the close of round 2, the round-1 entries are converted to pointers in that
round's cleanup task. Correct call for the next occasion: apply the narrow reading
and ask.

## OVERALL: READY FOR HUMAN

All nine corrections landed as described and each was verified against the
artifact rather than the report. The figure work changed no data: both wedge CSVs
were regenerated this cycle and are byte-identical to their committed versions, as
are the two untouched figures, which also settles determinism independently of the
implementer's `diff -q` claim. The airborne panel's caption is now derived from
`BLACKOUT_BLOCKS` through a helper shared with the excess panel, and the wording it
produces is true of the data: airborne time is observed in 4 of 4 corridors in all
twenty blackout months, excess in none of them, with 1,156 / 1,162 / 1,169 / 1,170
computable cells in 2022-01, 2022-02, 2023-01, 2023-02 (baseline_failures.csv).
The y-axis squeeze is gone. On the documentation side, the 347-row icao-tier drop
(panel_filter_log.csv, `icao_tier_dropped`) is now disclosed in all three places
and is correctly framed as a conservative default that is materially part of
option (a3) without resolving G7; the §3f nation counts (23 / 30 / 9 / 2) are
labelled mapping-derived and MATCH-SENSITIVE with the AR (N0/Z0, Norse Atlantic)
and CA (WPT, 2 departures) rows named and traced; the T-100(f) attribution is
separated from the established pattern in every prose location; and every
PROJECT_STATE number now carries a row/column trace, six of which I recomputed
exactly. Validator (29 CSVs, 0 FAIL, 0 WARN), trino check, and the regenerated run
log are all clean and I ran the first two myself. Four residual defects remain,
all cosmetic or documentation, and I am closing with them carried rather than
spending a cycle: A1 stale advisory text describing two now-fixed figure defects;
A2 the airborne figure's over-wide canvas (plot body 41% of width); A3 the
undisclosed unhedged "(T-100(f) reporting schedule)" on the availability figure,
which appears in no other artifact; A4 the `or 1.0` precedence nit in the padding
expression. A1–A3 are one editing pass over one bullet and one caption; they
belong at the top of round 2's cleanup task.

**Open flags:** DEGENERATE-GATE on G7 / FIX-02 BLOCKED-NEEDS-HUMAN (3 cycles,
terminal, correctly unresolved by agents). MATCH-SENSITIVE on every mapped
nationality, now including the §3f corridor nation counts and the availability
figure's row labels. Reporting embargo on all nation-level FIX-04/FIX-05 numbers
still in force. DECISION-PENDING: D-01, D-02, D-04, D-05, D-06. Carried advisories
A1–A4 above plus the previously logged set (tex caption "segment-months",
write-before-assert, `departures_scope_note` wording, build_run_log "Active round"
header, STATUS.md's two early untraced entries). No PLACEBO-FAIL: the placebo
corridor is empty for the same structural reason as the treated corridors, which
is the correct reading of a data property rather than a behavioural null.

**The three results a referee will attack first, and their defense status:**
(1) "Foreign carriers never report airborne time — you must have downloaded it
wrong." **Fully defended.** Read straight from the 36 vendor CSVs using BTS's own
CARRIER_GROUP, independent of the blocked mapping, reproduced by me: 1,133,545
rows, 0 with AIR_TIME > 0, 0 nulls, against 0.9964 for US carriers in the same
files. The only soft spot is the *mechanism* label, now correctly stated as
inference in prose (and, per A3, not yet on the figure).
(2) "Your carrier nationalities are wrong, so the whole panel is suspect."
**Defended by containment, not by resolution.** G7 is split (0.9021 coverage vs
0.8631 precision-adjusted), FIX-02 is blocked, and the headline does not depend on
the mapping at all. The new disclosure that the shipped panel already drops the
icao tier closes the one gap a referee could have called a silent choice.
(3) "Your excess measure is an artefact of screening and baseline choices."
**Half defended, by design.** The 50 vs 150 mph screen moves the pooled mean
0.0347 -> 0.0144 with 58.7% of the outcome's sum on 0.30% of cells, and the
2022–23 blackouts are documented to the month; both are reserved to the human as
D-05 and D-04 rather than settled by an agent, and no pooled mean is headlined.

**Decisions the human must make, in priority order:**
1. **D-02 — what Phase 1 now is** (A volume/extensive margin, B US-only
   route-exposure, C accelerate OpenSky ADS-B, D acquire foreign block-time data).
   Everything else is downstream of this; the director's non-binding read is (C).
2. **D-01 — which reading of G7 governs**, and whether a dated carrier-nationality
   source replaces the 2014 OpenFlights lookup. Note option (a3) is already partly
   in force as a conservative default (347 rows).
3. **Authorise the attended OpenSky extract session** (T1–T9). Not a DECISIONS
   entry, but it is the single highest-value action and it gates (C).
4. **D-04 — the baseline rule** against the 2022–23 blackouts.
5. **D-05 — the implied-speed screen threshold** and whether it becomes two-sided.
6. **D-06 — whether rule 5's citation exception extends to DECISIONS.md and
   RESEARCH_LOG.md**, under the identical inline-trace requirement, or the numbers
   become pointers.
7. **Review `data/raw/events/ban_nations_2022.csv`** (agent-drafted,
   human-unreviewed) and supply `closures.csv`.
