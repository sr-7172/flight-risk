---
description: Have the director read the current state of evidence and draft the next round file (plus RESEARCH_LOG.md and DECISIONS.md entries). Use at kickoff to draft ROUND_01 from PROJECT.md, or between runs to plan the next round without executing it.
---

Delegate to the `director` subagent with this brief: read PROJECT.md, STANDING_RULES.md, STATUS.md, REVIEW_REPORT.md, FINAL_RUN_LOG.md, **the most recent rounds/round-*/ROUND_*_FINDINGS.md — its "Suggested next steps" section, including any edits the human has made to it, is the PRIMARY input for what the next round contains** — and the underlying round-folder CSVs behind anything relied on; then (1) append the RESEARCH_LOG.md entry, (2) append any DECISIONS.md entries, (3) create the next round folder `rounds/round-NN-<slug>/` (slug = 2–4 words recalling the focus) and write `ROUND_NN.md` inside it following rounds/ROUND_TEMPLATE.md, with every deliverable path inside that folder. Departures from the findings' suggested next steps are fine but must be justified in a DECISIONS.md entry.

At kickoff (no rounds yet, so no findings to seed from), ROUND_01 must be a data-foundations round: ingestion, sample construction, merge/match diagnostics with logged match rates, and descriptives — no headline regressions before the panel passes its gates.

When the director returns, report back: the round file path, a one-line summary per task with its EXPLORE/CONFIRM label, and any DECISION-PENDING items verbatim. Do not begin executing the round; that is /run-analysis.

$ARGUMENTS
