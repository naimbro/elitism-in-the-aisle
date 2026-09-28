"""22 — Both-surnames coding-rule sensitivity (referee robustness, task C1).

Shows that the composition decline and the 1925 level break are not artifacts of
the permissive "either-surname" elite coding rule. Re-runs the composition
snapshots (script 04 logic) and the 1925 ITS (script 05 logic) under three codings:

  (a) PERMISSIVE  : elite if pat in ELITE OR  mat in ELITE   (current measure)
  (b) STRICT      : elite if pat in ELITE AND mat in ELITE
  (c) PATERNAL    : elite if pat in ELITE                    (single, paternal line)

Inputs : data/processed/cong_df.csv, data/processed/enduring_elite_FINAL.csv
Outputs: output/coding_rule_sensitivity.csv
         tables/table_coding_rule.tex (bare booktabs tabular; published to ../paper/tables
         if that tree exists)
Paths are anchored on the repo (runs from any cwd). Deterministic — no random component.

R&R 2026 correction (E1): its_break() uses the shared rule in _measure_helpers
(annual_share_frame): years with fewer than 5 sitting legislators are undefined and dropped
(1925, when Congress did not sit, was previously coded 0% via elite / max(n, 1)). The share
snapshots already used the n >= 5 rule and are unchanged.
Round 2: share_at() calls the shared annual_share (no inline copy of the rule); math-mode
minus signs in the table; comprehension instead of an append loop (INV-17).
"""
import pandas as pd
import numpy as np
import unicodedata
import statsmodels.formula.api as smf
from _measure_helpers import annual_share, annual_share_frame, DATA, OUTPUT, TABLES, publish, tex_num, tex_p


def dac(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()


ELITE = set(dac(s) for s in pd.read_csv(DATA / "enduring_elite_FINAL.csv").surname)

d = pd.read_csv(DATA / "cong_df.csv")
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


def its_break(ie):
    """Replicate script 05 ITS on window 1880-1970 with HAC(maxlags=5) at BR=1925.

    Returns (level_shift_pt, level_p, pre_trend_pt_per_yr, pre_trend_p).
    """
    BR = 1925
    df = annual_share_frame(ie, S, E, 1880, 1970)   # 1925 (no sitting Congress) dropped
    df["t"] = df.year - BR
    df["post"] = (df.year >= BR).astype(int)
    df["tpost"] = df.t * df.post
    m = smf.ols("elite ~ t + post + tpost", df).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return (m.params["post"], m.pvalues["post"], m.params["t"], m.pvalues["t"])


def coding_row(label, ie):
    shares = dict(zip(SNAPSHOT_YEARS, annual_share(ie, S, E, SNAPSHOT_YEARS)))  # NaN if < 5 sitting
    lvl, lvl_p, tr, tr_p = its_break(ie)
    print(f"\n--- {label} ---\n  Elite share of Congress (%):")
    print("\n".join(f"    {y}: " + ("NaN (Congress <5)" if np.isnan(v) else f"{v:5.1f}%")
                    for y, v in shares.items()))
    print(f"  1925 pre-trend     {tr:+.3f} pts/yr (p={tr_p:.3f})")
    print(f"  1925 LEVEL break   {lvl:+.2f} pt   (p={lvl_p:.4f})")
    return {"coding": label, **{f"share_{y}": v for y, v in shares.items()},
            "level_break_pt": lvl, "level_p": lvl_p, "pre_trend_pt_yr": tr, "pre_trend_p": tr_p}


print("=" * 72)
print("TASK C1 — BOTH-SURNAMES CODING-RULE SENSITIVITY")
print("=" * 72)
res = pd.DataFrame([coding_row(label, ie) for label, ie in CODINGS.items()])
res.to_csv(OUTPUT / "coding_rule_sensitivity.csv", index=False)
print("\nsaved output/coding_rule_sensitivity.csv")


# ---- Bare LaTeX tabular -------------------------------------------------------
def fmt_share(v):
    return "--" if np.isnan(v) else f"{v:.1f}"


body = [f"{r['coding']} & {fmt_share(r['share_1865'])} & {fmt_share(r['share_1905'])} & "
        f"{fmt_share(r['share_2010'])} & {tex_num(r['level_break_pt'], 2)} & {tex_p(r['level_p'])} \\\\"
        for _, r in res.iterrows()]
lines = [r"\begin{tabular}{lccccc}", r"\toprule",
         r" & 1865 & 1905 & 2010 & 1925 break & $p$-value \\",
         r"Coding rule & share (\%) & share (\%) & share (\%) & (pt) & \\",
         r"\midrule", *body, r"\bottomrule", r"\end{tabular}"]
tex = "\n".join(lines) + "\n"
out_tab = TABLES / "table_coding_rule.tex"
out_tab.write_text(tex, encoding="utf-8")
print(f"saved {out_tab}")
publish(out_tab, "tables")
print("\n" + tex)
