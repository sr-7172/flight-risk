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
