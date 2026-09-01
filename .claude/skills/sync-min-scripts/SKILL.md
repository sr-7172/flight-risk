---
name: sync-min-scripts
description: Keep human-readable/MIN_SCRIPTS.md in sync with the human-edited human-readable/PRESENTATION.md. Use this skill whenever PRESENTATION.md has been edited or mentioned, whenever the user asks which scripts are needed to reproduce the presentation/deck/results, whenever a round closes and artifacts moved, or whenever anyone asks to "sync", "update the script list", or doubts that MIN_SCRIPTS.md is current. Trigger even if the user only says they changed the presentation.
---

# sync-min-scripts

Regenerates `human-readable/MIN_SCRIPTS.md` — the minimum set of python
scripts needed to reconstruct every artifact (CSV/PNG/PDF/TeX) named in the
human-edited `human-readable/PRESENTATION.md` — and then verifies the parts
the automatic tracer could not pin down.

## Procedure

1. Run the tracer:

   ```bash
   uv run python code/sync_min_scripts.py
   ```

   It parses PRESENTATION.md for artifact filenames, locates each under
   `rounds/round-*/`, finds producer scripts under `code/` by literal
   basename match, walks `data/interim//data/raw/` dependencies upstream to
   the scripts that write them, and rewrites MIN_SCRIPTS.md.

2. Open the freshly written `human-readable/MIN_SCRIPTS.md` and read the
   **UNRESOLVED** and **AMBIGUOUS** sections. For each entry:
   - UNRESOLVED with "NOT FOUND under rounds/": the human probably renamed
     or misspelled the artifact in PRESENTATION.md, or the artifact hasn't
     been produced yet. Grep `rounds/` for near-miss names; report the
     mismatch to the user rather than silently guessing.
   - UNRESOLVED with "NONE FOUND" producer: the script builds the filename
     dynamically (f-strings, os.path.join with variables). Grep `code/` for
     fragments of the name and read the candidate scripts to identify the
     true producer.
   - AMBIGUOUS: read each candidate script and decide which actually
     WRITES the artifact (the others merely read it). The reader scripts do
     not belong in the artifact's chain unless they are upstream writers of
     something else in it.

3. If step 2 changed your understanding, edit ONLY the tracing inputs that
   make the automatic run correct next time (e.g., fix the artifact name in
   PRESENTATION.md **only with the user's confirmation** — it is
   human-owned) and rerun step 1. Never hand-edit MIN_SCRIPTS.md itself:
   it must remain fully regenerable.

4. Report back: number of artifacts traced, the minimal script count, what
   changed vs. the previous MIN_SCRIPTS.md (`git diff` it), and any items
   that still need a human decision.

## Constraints

- MIN_SCRIPTS.md is generated-only (standing rule: numbers and manifests
  are written by code). PRESENTATION.md is human-owned: never rewrite its
  content beyond a confirmed filename fix.
- Do not "helpfully" trim the minimal set by judgment; the tracer's closure
  plus your step-2 corrections is the list. If it looks too big, that is a
  finding about pipeline structure to mention, not something to edit away.
