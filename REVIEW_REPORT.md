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
