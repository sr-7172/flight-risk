---
description: Run the tech-debt pass — quarantine legacy outputs, archive superseded code by dependency trace, promote production scripts into the numbered pipeline, and regenerate docs/REPO_MAP.md. Only runs when the validator is green.
---

Precondition: `python code/99_validate_outputs.py` exits 0 (under any approved quarantine) — verify this first; if it fails, stop and report instead of cleaning.

Execute these steps, with one commit per step ("DEBT.<step>: <one line>") so every move is individually revertable:

1. **Trace before touching.** Build docs/REPO_TRACE.csv (artifact → generating script → imports, derived from grepping read/write calls and the import graph) and commit it BEFORE any move. The trace decides what is kept; names and intuitions do not.
2. Outputs not produced by any current pipeline script → `git mv` to that round folder's legacy_quarantine/ subfolder and append provenance lines to its README.
3. Code unreachable from the pipeline runner or any kept script → `git mv` to archive/. Never delete; `git mv` only. Never touch data/raw/.
4. Load-bearing scripts living outside the numbered pipeline → promote into the numbered directories; update imports and the pipeline runner.
5. **Proof run.** After moves, re-run at minimum: regressions → tables → results guide → validator, and assert headline coefficients are byte-identical to pre-move values. Any drift = revert the offending move and flag.
6. Regenerate docs/REPO_MAP.md (≤150 lines, one-line purpose per kept file, pipeline-order section).
7. Delegate an `overseer` review: nothing load-bearing archived, no orphan outputs, map sufficient for a newcomer.

Report what was moved (counts by category), the proof-run result, and the overseer verdict. Nulls and "nothing to clean" are valid outcomes.

$ARGUMENTS
