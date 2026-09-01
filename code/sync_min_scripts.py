#!/usr/bin/env python3
"""sync_min_scripts.py — regenerate human-readable/MIN_SCRIPTS.md from
human-readable/PRESENTATION.md.

PRESENTATION.md is HUMAN-EDITED and is the source of truth for which output
artifacts (CSVs / PNGs / PDFs / TeX tables) the current presentation relies
on. This script:

  1. parses PRESENTATION.md for artifact filenames,
  2. locates each artifact under rounds/round-*/,
  3. finds the script(s) under code/ whose text mentions the artifact's
     basename (the producer),
  4. walks upstream: any data/interim/ or data/raw/ file the producer
     mentions is traced to the script(s) that appear to WRITE it
     (heuristic: same basename on/near a to_parquet/to_csv/savefig/write
     call), recursively,
  5. writes MIN_SCRIPTS.md: per-artifact chains plus one de-duplicated
     minimal script list in pipeline order.

The tracing is literal-string matching, so it is deliberately conservative:
anything it cannot pin down is listed under UNRESOLVED / AMBIGUOUS for a
human (or the sync-min-scripts skill) to settle by actually reading the
scripts. Never hand-edit MIN_SCRIPTS.md — fix the tracing or the scripts.
"""
from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRES = ROOT / "human-readable" / "PRESENTATION.md"
DEST = ROOT / "human-readable" / "MIN_SCRIPTS.md"
CODE = ROOT / "code"
ROUNDS = ROOT / "rounds"

ARTIFACT_EXT = ("csv", "png", "pdf", "jpg", "jpeg", "svg", "tex", "parquet")
ARTIFACT_RE = re.compile(
    r"[\w\-./]+\.(?:" + "|".join(ARTIFACT_EXT) + r")\b", re.IGNORECASE)
WRITE_TOKENS = ("to_parquet", "to_csv", "savefig", "write_text", "open(",
                "to_excel", "np.save", "plt.save")
INTERIM_RE = re.compile(r"data/(?:interim|raw)/[\w\-./]+\.\w+")
ALWAYS = ["code/utils.py"]  # imported by every pipeline script


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))


def code_scripts() -> list[Path]:
    return sorted(p for p in CODE.rglob("*.py"))


def mentions(script_text: str, basename: str) -> bool:
    return basename in script_text


def writes(script_text: str, basename: str) -> bool:
    """Heuristic: basename appears on a line that also smells like a write."""
    for line in script_text.splitlines():
        if basename in line and any(tok in line for tok in WRITE_TOKENS):
            return True
    # write call and basename may be split across lines (e.g. path built
    # earlier); fall back to: mentions it AND contains any write token.
    return basename in script_text and any(t in script_text for t in WRITE_TOKENS)


def main() -> int:
    if not PRES.is_file():
        print(f"sync: {rel(PRES)} not found — nothing to do")
        return 1
    pres_text = PRES.read_text(encoding="utf-8", errors="replace")
    artifacts = []
    for m in ARTIFACT_RE.finditer(pres_text):
        tok = m.group(0).lstrip("./")
        if tok.lower().endswith((".md",)):
            continue
        # slides/ and paper/ are the deck/paper themselves, not round
        # artifacts; code/ mentions are scripts, not artifacts.
        if tok.startswith(("slides/", "paper/", "code/")):
            continue
        if tok not in artifacts:
            artifacts.append(tok)

    scripts = {rel(p): p.read_text(encoding="utf-8", errors="replace")
               for p in code_scripts()}

    chains: dict[str, dict] = {}
    for art in artifacts:
        base = Path(art).name
        located = sorted(str(p.relative_to(ROOT))
                         for p in ROUNDS.rglob(base)) if ROUNDS.is_dir() else []
        producers = sorted(s for s, txt in scripts.items()
                           if s not in ALWAYS and mentions(txt, base))
        chain: list[str] = list(producers)
        seen_files: set[str] = set()
        frontier = list(producers)
        while frontier:
            sc = frontier.pop()
            for dep in INTERIM_RE.findall(scripts[sc]):
                dbase = Path(dep).name
                if dbase in seen_files:
                    continue
                seen_files.add(dbase)
                for s2, txt in scripts.items():
                    if s2 in chain or s2 in ALWAYS:
                        continue
                    if writes(txt, dbase):
                        chain.append(s2)
                        frontier.append(s2)
        chains[art] = {"located": located, "producers": producers,
                       "chain": sorted(set(chain))}

    minimal = sorted({s for c in chains.values() for s in c["chain"]})
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    L = [f"# MIN_SCRIPTS — generated {stamp} by code/sync_min_scripts.py",
         "",
         "Minimum set of python scripts needed to reconstruct every artifact",
         "named in human-readable/PRESENTATION.md. Do not hand-edit; rerun",
         "`uv run python code/sync_min_scripts.py` (or invoke the",
         "sync-min-scripts skill) after editing PRESENTATION.md.",
         "",
         "## Minimal script set (pipeline order)",
         ""]
    for s in ALWAYS + [s for s in minimal if s not in ALWAYS]:
        L.append(f"- `{s}`")
    if not minimal:
        L.append("- _no artifacts traced yet_")
    L += ["", "## Per-artifact trace", ""]
    unresolved, ambiguous = [], []
    for art, c in chains.items():
        L.append(f"### `{art}`")
        L.append("- located: " + (", ".join(f"`{x}`" for x in c["located"])
                                  or "**NOT FOUND under rounds/**"))
        L.append("- producer script(s): " +
                 (", ".join(f"`{x}`" for x in c["producers"]) or "**NONE FOUND**"))
        if len(c["chain"]) > len(c["producers"]):
            ups = [x for x in c["chain"] if x not in c["producers"]]
            L.append("- upstream: " + ", ".join(f"`{x}`" for x in ups))
        L.append("")
        if not c["producers"] or not c["located"]:
            unresolved.append(art)
        elif len(c["producers"]) > 1:
            ambiguous.append(art)

    L.append("## UNRESOLVED (fix by reading scripts, then rerun)")
    L += [f"- `{a}`" for a in unresolved] or ["- none"]
    L.append("")
    L.append("## AMBIGUOUS (multiple candidate producers — verify)")
    L += [f"- `{a}`" for a in ambiguous] or ["- none"]
    L.append("")

    DEST.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {rel(DEST)}: {len(artifacts)} artifacts, "
          f"{len(minimal)} scripts, {len(unresolved)} unresolved, "
          f"{len(ambiguous)} ambiguous")
    return 0


if __name__ == "__main__":
    sys.exit(main())
