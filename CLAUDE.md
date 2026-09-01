# Project conventions (read first)

Binding documents, in order: **STANDING_RULES.md** (inference, gates, git — never weakened), **PROJECT.md** (question, phasing, sample, pitfalls, exploration stance), and the active **rounds/ROUND_NN.md** (named in the STATUS.md header).

## Layout

- `code/` — numbered pipeline directories (`01_ingest/ … 07_output/`), created as the project needs them, plus `utils.py`, `99_validate_outputs.py`, `build_run_log.py`, `sync_min_scripts.py`.
- `data/raw/` — read-only vendor extracts (T-100 CSVs, OpenSky parquet, event dictionaries). Never modified, never committed (gitignored), never touched by cleanup passes.
- `data/interim/` — parquet intermediaries (gitignored).
- `rounds/round-NN-<slug>/` — one folder per round: the work order (`ROUND_NN.md`), ALL of that round's outputs (result CSVs in the standard schema, figures, TeX tables; committed), and `ROUND_NN_FINDINGS.md` (plain-language findings + script list + Suggested next steps). `rounds/*/legacy_quarantine/` holds superseded artifacts. There is no top-level output/ — the validator and run-log builder scan `rounds/round-*/` directory-wide.
- `human-readable/` — the human's dashboard: `PRESENTATION.md` (HUMAN-OWNED deck skeleton naming key artifacts — agents never rewrite its content), `MIN_SCRIPTS.md` (generated ONLY by `code/sync_min_scripts.py`: minimum scripts to rebuild the presentation's artifacts), `PROJECT_STATE.md` (director-maintained state-of-project for an undergrad RA: plain words, glossed jargon, traced numbers only).
- `docs/` — REPO_MAP.md, traces, and LIT_NOTES.md (author's literature file).
- `paper/` — main.tex + generated `tables/*.tex` and `figures/`; `slides/` — seminar.tex (beamer). Numbers enter these only via generation scripts (`code/spec_to_tex.py` etc.) reading round-folder CSVs — never typed by hand.
- State files at root: STATUS.md (task states, never coefficients), REVIEW_REPORT.md (overseer, append-only), RESEARCH_LOG.md and DECISIONS.md (director), FINAL_RUN_LOG.md (generated only).

## Conventions

- `utils.setup_logger` / `utils.log_merge` for logging and merge diagnostics; `sys.path.insert` imports.
- Targeted edits to existing scripts, not wholesale rewrites.
- Every spec CSV uses the schema in STANDING_RULES.md.
- **Numbers are written only by code** — never type a result number into STATUS.md, commit messages, or reports. FINAL_RUN_LOG.md comes from `python code/build_run_log.py` only; MIN_SCRIPTS.md from `python code/sync_min_scripts.py` only. FINDINGS/PROJECT_STATE may cite numbers only transcribed from a round-folder CSV with an inline `(file.csv, row)` trace.
- OpenSky/Trino credentials live in `~/.config/pyopensky/settings.conf` (restored from the secrets volume). Unattended runs never query live sources: they read `data/raw/` extracts, and mark tasks BLOCKED if the extract is missing.

## Workflow

`/plan-round` (director drafts the next round INTO a new `rounds/round-NN-<slug>/` folder, seeded from the latest ROUND findings' Suggested next steps plus any human edits) → `/run-analysis rounds/round-NN-<slug>/ROUND_NN.md [auto N]` (unattended implement→review loop; round close = overseer OVERALL verdict, ROUND_NN_FINDINGS.md, PROJECT_STATE refresh, sync_min_scripts, run log + validator) → `/tech-debt` (only when the validator is green). Writing side, run attended: `/lit-review [topic]` (author searches the literature, flags NOVELTY-RISK and method provenance into docs/LIT_NOTES.md — needs the WebSearch/WebFetch deny lines temporarily removed) and `/write-up paper|slides|both` (author drafts from verified results only).

Methods default to seminar-friendly (STANDING_RULES.md rule 12): raw-data plots and means first, then OLS/FE, canonical DiD with event studies, simple IV. Anything fancier needs a written commission in the round file plus the simple benchmark alongside.
