#!/usr/bin/env python3
"""98_check_trino_usage.py — enforce OPENSKY_TRINO_RULES.md T1 and guard integrity.

FAIL (exit 1) if:
  - any file under code/ other than opensky_query.py imports pyopensky,
    trino, or traffic (the one-door rule);
  - opensky_query.py's caps/guards differ from the sanctioned values
    (someone raised MAX_HOURS_PER_QUERY etc. without a DECISIONS.md memo);
  - any script calls .query(...) with allow_unbounded=True outside a line
    carrying a '# T4-approved:' comment naming the round file.
Run at every round close (with 99_validate_outputs.py) and by the overseer.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CODE = ROOT / "code"
DOOR = CODE / "opensky_query.py"
SELF = Path(__file__).resolve()
SANCTIONED = {"MAX_HOURS_PER_QUERY": 6, "MAX_DAYS_PER_QUERY": 7,
              "SOFT_LIMIT_S": 5 * 60, "HARD_LIMIT_S": 25 * 60}
IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+(pyopensky|trino|traffic)\b", re.M)

fails: list[str] = []
for py in sorted(CODE.rglob("*.py")):
    txt = py.read_text(encoding="utf-8", errors="replace")
    rel = py.relative_to(ROOT)
    if py != DOOR:
        for m in IMPORT_RE.finditer(txt):
            fails.append(f"{rel}: imports '{m.group(1)}' directly — T1: use code/opensky_query.py")
    for i, line in enumerate(txt.splitlines(), 1):
        if "allow_unbounded=True" in line and "# T4-approved:" not in line and py not in (DOOR, SELF):
            fails.append(f"{rel}:{i}: allow_unbounded=True without '# T4-approved: <round file>' comment")

door = DOOR.read_text(encoding="utf-8")
for name, val in SANCTIONED.items():
    m = re.search(rf"^{name}\s*=\s*(.+)$", door, re.M)
    if not m:
        fails.append(f"opensky_query.py: {name} missing — guard tampered")
        continue
    try:
        got = eval(m.group(1), {}, {})  # noqa: S307 — literal arithmetic only
    except Exception:  # noqa: BLE001
        got = None
    if got != val:
        fails.append(f"opensky_query.py: {name}={got} differs from sanctioned {val} — "
                     f"raising caps needs a DECISIONS.md memo and human approval")
for must in ("check_sql(sql, allow_unbounded=allow_unbounded)", "with _LOCK:"):
    if must not in door:
        fails.append(f"opensky_query.py: guard call '{must}' missing — guard tampered")

for f in fails:
    print(f"FAIL  {f}")
print(f"trino-usage check: {len(fails)} FAIL")
sys.exit(1 if fails else 0)
