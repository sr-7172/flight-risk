#!/usr/bin/env python3
"""99_validate_outputs.py — directory-wide pathology scan of rounds/round-*/**/*.csv.

Implements the standing gates (STANDING_RULES.md G1–G5) plus the reviewer's
degenerate-statistics hunt, over EVERY csv under rounds/round-*/ (legacy_quarantine
excluded) — not a manifest. Exit 0 = clean (warnings allowed), exit 1 = at
least one FAIL. Findings print to stdout, one line each, with file+row.

FAIL conditions
  - spec-style CSV missing required schema columns
  - empty cells in coef/se/pval; pval outside [0,1]                    (G1)
  - |coef| > 1e4 anywhere (rank-deficiency signature)                  (G2 hard)
  - pval exactly 0.0; one p-value repeated across >=30% of rows (>=4)  (G3)
  - starred/significant coefficient with |SE/coef| > 20                (G4)
  - column named *share*/*rate*/*survival*/*precision* outside [0,1]   (G5)
  - reported pval < .001 while |coef/se| implies p > .5 (transcription)

WARN conditions (printed, do not fail the run; the overseer judges)
  - 100 < |coef| <= 1e4 (G2 depends on outcome units)
  - reported vs implied p disagree materially but not egregiously
  - unreadable CSV
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ROUNDS = ROOT / "rounds"
SCHEMA = ["spec", "outcome", "variable", "coef", "se", "pval",
          "n_obs", "cluster_level", "stars_source"]
BOUNDED_TOKENS = ("share", "rate", "survival", "precision")

findings: list[tuple[str, str]] = []  # (severity, message)


def add(sev: str, msg: str) -> None:
    findings.append((sev, msg))


def implied_p(coef: float, se: float) -> float:
    """Two-sided normal p from |coef/se| (approximation; used loosely)."""
    if se <= 0 or not np.isfinite(se) or not np.isfinite(coef):
        return float("nan")
    t = abs(coef / se)
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(t / math.sqrt(2.0))))


def check_csv(path: Path) -> None:
    rel = path.relative_to(ROOT)
    try:
        df = pd.read_csv(path)
    except Exception as exc:  # noqa: BLE001
        add("WARN", f"{rel}: unreadable as CSV ({exc})")
        return
    if df.empty:
        add("WARN", f"{rel}: empty file")
        return

    cols = {c.lower(): c for c in df.columns}
    has_coef = "coef" in cols

    # Schema check for spec-style files
    if has_coef or "spec" in path.name.lower():
        missing = [c for c in SCHEMA if c not in cols]
        if has_coef and missing:
            add("FAIL", f"{rel}: spec CSV missing schema columns {missing}")

    # G5: bounded columns
    for lc, orig in cols.items():
        if any(tok in lc for tok in BOUNDED_TOKENS):
            vals = pd.to_numeric(df[orig], errors="coerce").dropna()
            bad = vals[(vals < -1e-9) | (vals > 1 + 1e-9)]
            if len(bad):
                add("FAIL", f"{rel}: column '{orig}' outside [0,1] in "
                            f"{len(bad)} rows (e.g. row {bad.index[0]}: {bad.iloc[0]})")

    if not has_coef:
        return

    coef = pd.to_numeric(df[cols["coef"]], errors="coerce")
    se = pd.to_numeric(df[cols["se"]], errors="coerce") if "se" in cols else None
    pval = pd.to_numeric(df[cols["pval"]], errors="coerce") if "pval" in cols else None

    # G1: empties / bounds
    for name, series in (("coef", coef), ("se", se), ("pval", pval)):
        if series is not None and series.isna().any():
            rows = list(series[series.isna()].index[:5])
            add("FAIL", f"{rel}: empty/non-numeric {name} in rows {rows}")
    if pval is not None:
        oob = pval.dropna()[(pval.dropna() < 0) | (pval.dropna() > 1)]
        if len(oob):
            add("FAIL", f"{rel}: pval outside [0,1] in {len(oob)} rows "
                        f"(e.g. row {oob.index[0]}: {oob.iloc[0]})")

    # G2: exploded coefficients
    big = coef.dropna()[coef.dropna().abs() > 1e4]
    if len(big):
        add("FAIL", f"{rel}: |coef|>1e4 in {len(big)} rows "
                    f"(e.g. row {big.index[0]}: {big.iloc[0]:.3g}) — rank deficiency?")
    mid = coef.dropna()[(coef.dropna().abs() > 100) & (coef.dropna().abs() <= 1e4)]
    if len(mid):
        add("WARN", f"{rel}: |coef|>100 in {len(mid)} rows "
                    f"(e.g. row {mid.index[0]}: {mid.iloc[0]:.3g}) — check outcome units")

    if pval is not None:
        pv = pval.dropna()
        # G3: exact zeros and mass repetition
        zeros = pv[pv == 0.0]
        if len(zeros):
            add("FAIL", f"{rel}: pval exactly 0.0 in {len(zeros)} rows "
                        f"(e.g. row {zeros.index[0]})")
        if len(pv) >= 4:
            counts = pv.round(12).value_counts()
            top_val, top_n = counts.index[0], int(counts.iloc[0])
            if top_n >= max(4, int(0.3 * len(pv))):
                sev = "FAIL" if top_val < 0.05 else "WARN"
                add(sev, f"{rel}: p-value {top_val} repeated {top_n}/{len(pv)} "
                         f"rows — degenerate bootstrap signature")

    # G4 + consistency, rowwise
    if se is not None and pval is not None:
        for idx in df.index:
            c, s, p = coef.get(idx), se.get(idx), pval.get(idx)
            if any(v is None or not np.isfinite(v) for v in (c, s, p)):
                continue
            if p < 0.05 and c != 0 and abs(s / c) > 20:
                add("FAIL", f"{rel} row {idx}: significant (p={p:.3g}) with "
                            f"|SE/coef|={abs(s / c):.1f} > 20")
            ip = implied_p(c, s)
            if np.isfinite(ip):
                if p < 1e-3 and ip > 0.5:
                    add("FAIL", f"{rel} row {idx}: reported p={p:.2g} but |t|="
                                f"{abs(c / s):.2f} implies p≈{ip:.2f} — transcription?")
                elif (p < 0.05) != (ip < 0.05) and abs(ip - p) > 0.10:
                    add("WARN", f"{rel} row {idx}: reported p={p:.3g} vs implied "
                                f"p≈{ip:.3g} (may be fine for bootstrap/t-dof)")


def main() -> int:
    if not ROUNDS.is_dir():
        print("validate: rounds/ does not exist yet — nothing to check (OK)")
        return 0
    files = []
    for rdir in sorted(ROUNDS.glob("round-*")):
        if rdir.is_dir():
            files += sorted(p for p in rdir.rglob("*.csv")
                            if "legacy_quarantine" not in p.parts)
    if not files:
        print("validate: no CSVs under rounds/round-*/ — nothing to check (OK)")
        return 0
    for f in files:
        check_csv(f)

    fails = [m for s, m in findings if s == "FAIL"]
    warns = [m for s, m in findings if s == "WARN"]
    for m in warns:
        print(f"WARN  {m}")
    for m in fails:
        print(f"FAIL  {m}")
    print(f"validate: {len(files)} CSVs scanned, "
          f"{len(fails)} FAIL, {len(warns)} WARN")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
