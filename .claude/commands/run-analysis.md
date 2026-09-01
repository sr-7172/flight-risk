---
description: Orchestrate an unattended analysis round — econometrician implements, overseer reviews, director writes the round's FINDINGS and closes out. Usage. /run-analysis rounds/round-NN-<slug>/ROUND_NN.md [auto N]
---

You are the ORCHESTRATOR for an unattended run (~hours). The human is away; you must not wait for input. $ARGUMENTS names the round file, optionally followed by `auto N` (chain up to N director-drafted rounds; default 1, i.e. run only the named round).

Your contract:

1. FIRST ACTION, before reading anything: ensure the gate flag exists — `touch .remediation_active` (idempotent; ./launch.sh may already have created it) — and start STATUS.md with a timestamped header line naming the active round file (update this header whenever the active round changes). This must be your first tool call so the watchdog is protecting the run from the start.
2. Read the round file in full, plus STANDING_RULES.md, including the completion criteria.
3. Work the tasks in the stated priority order.
4. For EACH task:
   a. Delegate implementation to the `econometrician` subagent, passing it the full text of that FIX/NEW section plus any reviewer findings from prior cycles.
   b. When it returns, run `python code/99_validate_outputs.py` yourself.
   c. Delegate review to the `overseer` subagent for that task.
   d. If the overseer FAILs: send its "Required actions" back to the econometrician (resume the same subagent if possible). Maximum 3 implement→review cycles per task; then mark BLOCKED-NEEDS-HUMAN in STATUS.md and move on.
   e. On PASS: `git add -A && git commit -m "FIX-NN: <one line>"`, append the STATUS.md line, proceed.
5. Keep your own context lean: delegate all heavy reading/coding to subagents; you track state via STATUS.md and REVIEW_REPORT.md only.
6. Round close, when all tasks are DONE or BLOCKED: run `python code/build_run_log.py` then `python code/99_validate_outputs.py`; delegate to the `director` subagent for the close-out writes — `ROUND_NN_FINDINGS.md` in the round folder (per the ROUND_TEMPLATE.md contract, including the complete scripts-touched list and Suggested next steps), the human-readable/PROJECT_STATE.md refresh, `uv run python code/sync_min_scripts.py`, RESEARCH_LOG.md and DECISIONS.md entries; then have the overseer write the `OVERALL:` verdict in REVIEW_REPORT.md INCLUDING its findings-audit (numbers traced, script list vs git). Append `ROUND <name> COMPLETE` to STATUS.md and commit.
7. Next-round handling — the findings' Suggested next steps section is the handoff artifact; no next round file exists by default:
   - If rounds remain under `auto N`: commission the `director` to draft `rounds/round-MM-<slug>/ROUND_MM.md` FROM the just-written Suggested next steps. If it has runnable tasks and its header is not NEEDS-HUMAN, return to step 3 with the new round.
   - Otherwise (default single-round mode, N exhausted, or NEEDS-HUMAN): append `ALL COMPLETE` to STATUS.md and stop — the human reads the FINDINGS, optionally edits its Suggested next steps, and later invokes /plan-round to draft the next round from it. The Stop hook will verify, lift the gate, and send the completion notification.
8. Never relax a sanity gate, never hand-write a result number, never choose between disagreeing estimators (flag DEGENERATE-INFERENCE instead), and never use git push or destructive commands.

If something environmental blocks all progress (e.g., a package cannot install, an expected data/raw/ extract is missing), document it in STATUS.md, mark affected tasks BLOCKED, complete whatever is unblocked, and still finish steps 6–7 so the gate lifts cleanly.

$ARGUMENTS
