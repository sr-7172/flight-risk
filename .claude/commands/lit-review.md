---
description: Have the author agent run a literature review — where the methods come from, and whether the finding already exists in published or working papers. Usage: /lit-review [topic or axis, e.g. "war-risk insurance premia shipping"]. Requires web access (see note below). Run attended.
---

First check web access: attempt a single WebSearch. If it is denied, stop and tell the user exactly this — WebSearch/WebFetch are denied in `.claude/settings.json` (a deliberate default: unattended runs should not read arbitrary web content). To run a literature review, temporarily delete the two lines `"WebFetch"` and `"WebSearch"` from the deny list, run /lit-review attended, then restore them before the next unattended /run-analysis.

If web access works, delegate to the `author` subagent: read PROJECT.md and RESEARCH_LOG.md, then follow its Literature review procedure on $ARGUMENTS (default: the whole project — question, setting, data, and each method in use). Output is an appended section in docs/LIT_NOTES.md with relation tags (COMPETES / COMPLEMENTS / METHOD-SOURCE / BACKGROUND), NOVELTY-RISK flags where applicable, method-provenance citations, and a 5-paper reading queue.

When the author returns, report verbatim: every NOVELTY-RISK flag, the COMPETES entries, and the reading queue.

$ARGUMENTS
