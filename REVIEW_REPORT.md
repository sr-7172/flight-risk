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
