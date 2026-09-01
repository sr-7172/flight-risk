---
description: Full overnight autonomous campaign. Usage: /overnight [N] [no-writeup] [no-litreview] — plans a round if none is pending, runs up to N rounds (default 3) via the /run-analysis contract, then closes out with a literature scan (if web access is enabled), a paper/slides draft, and a MORNING_BRIEF.md. Start the watchdog first.
---

Parse $ARGUMENTS: an integer N (max rounds, default 3); the flags `no-writeup` and `no-litreview` disable those closeout phases.

## Phase 0 — Preflight (do these checks, report, and continue where possible)

0. FIRST ACTION: `touch .remediation_active` (idempotent — ./launch.sh usually did it) so the watchdog covers preflight and planning, not just the analysis loop. If STATUS.md does not exist yet, create it with a timestamped header `overnight campaign started — planning` so a resumed session can tell which phase it is in.
1. `git status` — if there are uncommitted changes, commit them as `overnight: pre-run snapshot` before anything else.
2. Confirm PROJECT.md is filled in (not the template placeholders). If it still contains template angle-bracket placeholders in the starred sections, STOP: report that the brief is unfinished and do nothing else.
3. Check whether the watchdog is running (`pgrep -f watchdog.sh`). If not, warn in your first status line that resume-on-stall is off, and continue.
4. Run `python code/99_validate_outputs.py`. A FAIL on pre-existing outputs means the last session ended dirty: the first round of the night must begin with remediation of exactly those failures (pass this instruction to the director in Phase 1).

## Phase 1 — Ensure there is a runnable round

Read STATUS.md. If it names an active round that is not COMPLETE, that round is the entry point — do not plan a new one on top of it. Otherwise invoke the `/plan-round` procedure (director creates rounds/round-NN-<slug>/ and drafts ROUND_NN.md inside it, seeded from the latest ROUND findings' Suggested next steps if any exist, appending RESEARCH_LOG.md and DECISIONS.md as it goes), passing along any Phase 0 remediation instruction.

## Phase 2 — The campaign

Execute the `/run-analysis <round file> auto N` contract exactly as written in that command: per-task implement → validate → overseer loop, round close, director handoff, chaining up to N rounds total for the night. All standing machinery applies unchanged: the .remediation_active flag, the stop gate, STANDING_RULES.md, EXPLORE/CONFIRM discipline. If the director marks NEEDS-HUMAN, the campaign stops chaining and proceeds to Phase 3 with whatever closed.

## Phase 3 — Closeout (runs once, after the last round closes or chaining stops)

1. **Literature scan** (skip if `no-litreview`): attempt one WebSearch. If web tools are denied, skip silently and note it in the brief — never treat this as an error. If available, delegate to the `author` subagent for a scoped scan: only topics touched by tonight's rounds (new methods used, new results found), appended to docs/LIT_NOTES.md with NOVELTY-RISK flags per its procedure.
2. **Write-up** (skip if `no-writeup`, or if no round closed tonight, or if the validator is not green): run the `/write-up both` contract — author drafts/updates paper/main.tex and slides/seminar.tex from verified results only, tables generated from output CSVs, compile with latexmk.
3. **Morning brief.** Write MORNING_BRIEF.md (overwrite; it is a per-night artifact) containing ONLY statuses, verbatim quotes, and file pointers — never a result number typed by you (STANDING_RULES.md rule 5; numbers live in FINAL_RUN_LOG.md and the generated tables):
   - Timestamp, rounds attempted vs closed, and each round's OVERALL verdict line copied verbatim from REVIEW_REPORT.md.
   - Every DECISION-PENDING entry from DECISIONS.md, verbatim.
   - Every BLOCKED / BLOCKED-NEEDS-HUMAN task with its one-line reason from STATUS.md.
   - Open flags (DEGENERATE-INFERENCE, PLACEBO-FAIL, MATCH-SENSITIVE, LIMITATION).
   - Writing status: whether paper/slides compiled, any WRITING-NEEDS entries, any NOVELTY-RISK flags from tonight's scan.
   - Pointers to each closed round's FINDINGS file (path only) and to human-readable/PROJECT_STATE.md.
   - A reading order: the latest ROUND_NN_FINDINGS.md → human-readable/PROJECT_STATE.md → this brief → REVIEW_REPORT.md → FINAL_RUN_LOG.md → paper/main.pdf.
4. Commit closeout artifacts: `git add -A && git commit -m "overnight: closeout <date>"`.
5. Notify: `curl -s -m 10 -d "overnight campaign done: <rounds closed>/<N> rounds, <k> pending decisions" https://ntfy.sh/<topic>` using the topic from ./.ntfy_topic or ~/.secrets/ntfy_topic if present.

Sequencing rule: phases run strictly in order; the flag stays in place through Phase 3 and is lifted only by the Stop hook on ALL COMPLETE. nothing in Phase 3 may modify code/, data/, round work orders, or round-folder outputs (paper/, slides/, docs/ and the brief are Phase 3's only writable surfaces). If the session is interrupted during Phase 3, all analysis results are already committed and gated; only the brief and drafts are at risk, and re-running /overnight 0 regenerates Phase 3 alone (N=0 means: no new rounds, closeout only).

$ARGUMENTS
