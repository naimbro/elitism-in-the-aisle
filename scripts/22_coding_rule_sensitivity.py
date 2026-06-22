"""22 — Both-surnames coding-rule sensitivity (referee robustness, task C1).

Shows that the composition decline and the 1925 level break are not artifacts of
the permissive "either-surname" elite coding rule. Re-runs the composition
snapshots (script 04 logic) and the 1925 ITS (script 05 logic) under three codings:

  (a) PERMISSIVE  : elite if pat in ELITE OR  mat in ELITE   (current measure)
  (b) STRICT      : elite if pat in ELITE AND mat in ELITE
  (c) PATERNAL    : elite if pat in ELITE                    (single, paternal line)

Inputs : data/processed/cong_df.csv, data/processed/enduring_elite_FINAL.csv
Outputs: output/coding_rule_sensitivity.csv
         paper/tables/table_coding_rule.tex  (bare booktabs tabular)

Run from replication_repo/ (cwd), matching scripts 04/05 relative-path convention.
Deterministic — no random component.
"""
import pandas as pd
import numpy as np
import unicodedata
import statsmodels.formula.api as smf


def dac(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()


ELITE = set(dac(s) for s in pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname)

# COMMON set is unused for C1 but kept identical to script 04 for documentation parity.

d = pd.read_csv("data/processed/cong_df.csv")
d["S"] = pd.to_numeric(d.Start, errors="coerce")
d["E"] = pd.to_numeric(d.End, errors="coerce")
d = d.dropna(subset=["S", "E"])
pat = d.Pat.map(dac)
mat = d.Mat.map(dac)
S = d.S.values
E = d.E.values

# Three elite indicators, all aligned to rows of d.
CODINGS = {
    "Permissive (OR)": (pat.isin(ELITE) | mat.isin(ELITE)).values,
    "Strict (AND)": (pat.isin(ELITE) & mat.isin(ELITE)).values,
    "Paternal only": pat.isin(ELITE).values,
}

SNAPSHOT_YEARS = [1865, 1905, 1925, 1965, 2010]


def share_at(ie, y):
    """Elite share (%) of legislators active in year y; NaN if fewer than 5 in office."""
    m = (S <= y) & (E >= y)
    n = int(m.sum())
    return 100.0 * ie[m].sum() / n if n >= 5 else np.nan


def its_break(ie):
    """Replicate script 05 ITS on window 1880-1970 with HAC(maxlags=5) at BR=1925.

    Returns (level_shift_pt, level_p, pre_trend_pt_per_yr, pre_trend_p).
    """
    yrs = np.arange(1880, 1971)
    share = np.array([
        100.0 * ie[(S <= y) & (E >= y)].sum() / max(int(((S <= y) & (E >= y)).sum()), 1)
        for y in yrs
    ])
    BR = 1925
    df = pd.DataFrame({"year": yrs, "elite": share})
    df["t"] = df.year - BR
    df["post"] = (df.year >= BR).astype(int)
    df["tpost"] = df.t * df.post
    m = smf.ols("elite ~ t + post + tpost", df).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return (m.params["post"], m.pvalues["post"], m.params["t"], m.pvalues["t"])


# ---- Compute everything -------------------------------------------------------
rows = []
print("=" * 72)
print("TASK C1 — BOTH-SURNAMES CODING-RULE SENSITIVITY")
print("=" * 72)
for label, ie in CODINGS.items():
    shares = {y: share_at(ie, y) for y in SNAPSHOT_YEARS}
    lvl, lvl_p, tr, tr_p = its_break(ie)
    print(f"\n--- {label} ---")
    print("  Elite share of Congress (%):")
    for y in SNAPSHOT_YEARS:
        v = shares[y]
        print(f"    {y}: " + ("NaN (Congress <5)" if np.isnan(v) else f"{v:5.1f}%"))
    print(f"  1925 pre-trend     {tr:+.3f} pts/yr (p={tr_p:.3f})")
    print(f"  1925 LEVEL break   {lvl:+.2f} pt   (p={lvl_p:.4f})")
    row = {"coding": label}
    for y in SNAPSHOT_YEARS:
        row[f"share_{y}"] = shares[y]
    row["level_break_pt"] = lvl
    row["level_p"] = lvl_p
    row["pre_trend_pt_yr"] = tr
    row["pre_trend_p"] = tr_p
    rows.append(row)

res = pd.DataFrame(rows)
res.to_csv("output/coding_rule_sensitivity.csv", index=False)
print("\nsaved output/coding_rule_sensitivity.csv")


# ---- Bare LaTeX tabular -------------------------------------------------------
def fmt_share(v):
    return "--" if np.isnan(v) else f"{v:.1f}"


def fmt_p(p):
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


lines = []
lines.append(r"\begin{tabular}{lccccc}")
lines.append(r"\toprule")
lines.append(r" & 1865 & 1905 & 2010 & 1925 break & $p$-value \\")
lines.append(r"Coding rule & share (\%) & share (\%) & share (\%) & (pt) & \\")
lines.append(r"\midrule")
for _, r in res.iterrows():
    lines.append(
        f"{r['coding']} & {fmt_share(r['share_1865'])} & {fmt_share(r['share_1905'])} & "
        f"{fmt_share(r['share_2010'])} & {r['level_break_pt']:+.2f} & {fmt_p(r['level_p'])} \\\\"
    )
lines.append(r"\bottomrule")
lines.append(r"\end{tabular}")
tex = "\n".join(lines) + "\n"
with open("../paper/tables/table_coding_rule.tex", "w") as f:
    f.write(tex)
print("saved ../paper/tables/table_coding_rule.tex")
print("\n" + tex)
