"""Convert a standard spec CSV (STANDING_RULES.md schema) into a booktabs .tex table.

The only sanctioned path for regression numbers to enter paper/ or slides/:
    uv run python code/spec_to_tex.py rounds/round-NN-<slug>/foo.csv paper/tables/foo.tex \
        --caption "Baseline estimates" --label tab:baseline \
        [--specs spec1 spec2] [--variables x1 x2] [--digits 3]

Layout: one column per spec, one coefficient row (SE beneath in parens) per
variable, N and cluster level in the footer. Stars from `pval`:
*** p<0.01, ** p<0.05, * p<0.1 (stars_source column is echoed in the note).
"""
import argparse
import sys

import pandas as pd


def stars(p):
    if pd.isna(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


def esc(s):
    return (str(s).replace("\\", r"\textbackslash{}").replace("&", r"\&")
            .replace("%", r"\%").replace("_", r"\_").replace("#", r"\#")
            .replace("$", r"\$"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv_in")
    ap.add_argument("tex_out")
    ap.add_argument("--caption", default="")
    ap.add_argument("--label", default="")
    ap.add_argument("--specs", nargs="*", help="subset + order of spec column")
    ap.add_argument("--variables", nargs="*", help="subset + order of variable column")
    ap.add_argument("--digits", type=int, default=3)
    a = ap.parse_args()

    df = pd.read_csv(a.csv_in)
    need = {"spec", "variable", "coef", "se", "pval", "n_obs", "cluster_level"}
    missing = need - set(df.columns)
    if missing:
        sys.exit(f"FAIL: {a.csv_in} missing columns {sorted(missing)}")

    specs = a.specs or list(dict.fromkeys(df["spec"]))
    variables = a.variables or list(dict.fromkeys(df["variable"]))
    fmt = f"{{:.{a.digits}f}}"

    def cell(sp, var, which):
        r = df[(df["spec"] == sp) & (df["variable"] == var)]
        if r.empty:
            return ""
        r = r.iloc[0]
        if which == "coef":
            return fmt.format(r["coef"]) + stars(r["pval"])
        return "(" + fmt.format(r["se"]) + ")"

    L = []
    L.append(r"\begin{table}[!htbp]\centering")
    if a.caption:
        L.append(rf"\caption{{{esc(a.caption)}}}")
    if a.label:
        L.append(rf"\label{{{a.label}}}")
    L.append(r"\begin{tabular}{l" + "c" * len(specs) + "}")
    L.append(r"\toprule")
    L.append(" & " + " & ".join(rf"({i+1})" for i in range(len(specs))) + r" \\")
    L.append(" & " + " & ".join(esc(s) for s in specs) + r" \\")
    L.append(r"\midrule")
    for v in variables:
        L.append(esc(v) + " & " + " & ".join(cell(s, v, "coef") for s in specs) + r" \\")
        L.append(" & " + " & ".join(cell(s, v, "se") for s in specs) + r" \\[2pt]")
    L.append(r"\midrule")
    n_row, cl_row = [], []
    for s in specs:
        r = df[df["spec"] == s]
        n_row.append(f"{int(r['n_obs'].iloc[0]):,}" if not r.empty else "")
        cl_row.append(esc(r["cluster_level"].iloc[0]) if not r.empty else "")
    L.append("Observations & " + " & ".join(n_row) + r" \\")
    L.append("Clustering & " + " & ".join(cl_row) + r" \\")
    L.append(r"\bottomrule")
    L.append(r"\end{tabular}")
    src = esc(", ".join(sorted(df.get("stars_source", pd.Series(dtype=str)).dropna().unique())) or "pval")
    L.append(rf"\par\smallskip\footnotesize Standard errors in parentheses; stars from {src}: *** $p<0.01$, ** $p<0.05$, * $p<0.1$.")
    L.append(r"\end{table}")

    with open(a.tex_out, "w") as f:
        f.write("\n".join(L) + "\n")
    print(f"wrote {a.tex_out}: {len(variables)} variables x {len(specs)} specs from {a.csv_in}")


if __name__ == "__main__":
    main()
