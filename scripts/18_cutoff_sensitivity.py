"""18 — N3: SES-cutoff sensitivity of the headline results.
Re-runs the measure build varying the Gate-1 SES cutoff in {60, 65, 70} (65 = headline),
and reports for each: surname count, elite Congress share (1860s, 2010s), over-
representation fold ~1900, and the 1925 ITS level break. Optionally also varies the
bearer floor. Confirms headline results are stable across reasonable cutoffs.
Inputs : data/processed/cong_df.csv, pop_prevalence_by_year.csv, surname_nse.csv,
         1874 censo, elite-network xlsx (via _measure_helpers).
Output : ../paper/tables/table_cutoff_sensitivity.tex  (bare tabular, INV-13)
         data/processed/cutoff_sensitivity.csv
No stochastic element -> no seed needed (INV-14)."""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf
from _measure_helpers import dac, build_hist, load_ses, build_list

HIST = build_hist()
NSE, NOCC = load_ses()

# roster + population
d = pd.read_csv("data/processed/cong_df.csv")
d["S"] = pd.to_numeric(d.Start, errors="coerce"); d["E"] = pd.to_numeric(d.End, errors="coerce")
d = d.dropna(subset=["S", "E"])
pat = d.Pat.map(dac); mat = d.Mat.map(dac)
S = d.S.values; E = d.E.values
pop = pd.read_csv("data/processed/pop_prevalence_by_year.csv")
pe = pop.set_index("year").pct_elite.rolling(7, center=True, min_periods=1).mean()
yrs_full = np.arange(1830, 2021)


def pop_at(y):
    return pe.values[pe.index.get_indexer([y], method="nearest")[0]]


def cong_share(flag, y, smooth=True):
    if smooth:
        o = []
        for yy in yrs_full:
            m = (S <= yy) & (E >= yy); n = m.sum()
            o.append(100 * flag[m].sum() / n if n >= 5 else np.nan)
        s = pd.Series(o).rolling(5, center=True, min_periods=3).mean()
        return s.values[np.where(yrs_full == y)[0][0]]
    m = (S <= y) & (E >= y); n = m.sum()
    return 100 * flag[m].sum() / max(n, 1)


def its_break(flag):
    yrs = np.arange(1880, 1971)
    share = np.array([100 * flag[(S <= y) & (E >= y)].sum() / max(((S <= y) & (E >= y)).sum(), 1) for y in yrs])
    df = pd.DataFrame({"year": yrs, "elite": share})
    df["t"] = df.year - 1925; df["post"] = (df.year >= 1925).astype(int); df["tpost"] = df.t * df.post
    m = smf.ols("elite ~ t + post + tpost", df).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return m.params["post"], m.pvalues["post"]


# The PUBLISHED headline list (298 surnames, LLM-curated gate-2 + business gate).
# Reported as the headline row so the table matches the manuscript exactly; the
# deterministic SES-cutoff rows below show stability of the SAME pattern when the
# gate-2 attestation is reconstructed without the LLM.
PUB = set(dac(s) for s in pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname)

rows = []
configs = [(60, 30), (65, 30), (70, 30)]   # (ses_cut, min_bearers); 65/30 = headline cutoff
# extra cheap floor variations on the headline cutoff
extra = [(65, 5), (65, 50)]
# (label, surname_set, ses_cut, min_bearers, is_published)
specs = [("published", PUB, 65, 30, True)]
specs += [(None, build_list(HIST, NSE, NOCC, ses_cut=c, min_bearers=m, gate_ses=True), c, m, False)
          for c, m in configs + extra]
for label, lst, ses_cut, minb, is_pub in specs:
    flag = (pat.isin(lst) | mat.isin(lst)).values
    sh_1860 = cong_share(flag, 1865)
    sh_2010 = cong_share(flag, 2015)
    fold_1900 = cong_share(flag, 1900) / pop_at(1900)
    brk, brp = its_break(flag)
    rows.append({"spec": label or f"ses{ses_cut}_b{minb}", "ses_cut": ses_cut,
                 "min_bearers": minb, "n_surnames": len(lst),
                 "share_1860s": round(sh_1860, 1), "share_2010s": round(sh_2010, 1),
                 "fold_1900": round(fold_1900, 1), "break_1925": round(brk, 2),
                 "break_p": round(brp, 4),
                 "published": is_pub, "headline": (ses_cut == 65 and minb == 30)})
    tag = " <- PUBLISHED" if is_pub else (" <- headline cutoff (det.)" if (ses_cut == 65 and minb == 30) else "")
    nm = "PUBLISHED 298" if is_pub else f"SES>={ses_cut}, bearers>={minb}"
    print(f"[N3] {nm}: n={len(lst):4d}  1860s={sh_1860:.1f}%  "
          f"2010s={sh_2010:.1f}%  fold1900={fold_1900:.1f}x  break1925={brk:+.2f} (p={brp:.4f}){tag}")

res = pd.DataFrame(rows)
res.to_csv("data/processed/cutoff_sensitivity.csv", index=False)

# ---- bare tabular (INV-13) ----
pub = res[res.published]
det = res[~res.published]
main = det[det.min_bearers == 30].sort_values("ses_cut")
floors = det[(det.ses_cut == 65)].sort_values("min_bearers")


def star(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def row(nm, r):
    return (f"{nm} & {r.n_surnames} & {r.share_1860s:.1f} & {r.share_2010s:.1f} & "
            f"{r.fold_1900:.1f}$\\times$ & {r.break_1925:+.2f}{star(r.break_p)} \\\\")


lines = ["\\begin{tabular}{lccccc}", "\\toprule"]
lines.append(" & Surname & Elite share & Elite share & Over-rep. & 1925 level \\\\")
lines.append("Specification & count & 1860s (\\%) & 2010s (\\%) & fold $\\sim$1900 & break (pts) \\\\")
lines.append("\\midrule")
for r in pub.itertuples():
    lines.append(row("Published measure (SES $\\geq$ 65)", r))
lines.append("\\\\[0.3em]")
lines.append("\\multicolumn{6}{l}{\\textit{Panel A: SES cutoff, gate-2 reconstructed (bearer floor = 30)}} \\\\")
for r in main.itertuples():
    lines.append(row(f"SES $\\geq$ {r.ses_cut}", r))
lines.append("\\\\[0.3em]")
lines.append("\\multicolumn{6}{l}{\\textit{Panel B: bearer floor (SES $\\geq$ 65)}} \\\\")
for r in floors.itertuples():
    lines.append(row(f"$\\geq$ {r.min_bearers} bearers", r))
lines += ["\\bottomrule", "\\end{tabular}"]
with open("../paper/tables/table_cutoff_sensitivity.tex", "w") as f:
    f.write("\n".join(lines) + "\n")
print("[N3] wrote ../paper/tables/table_cutoff_sensitivity.tex")
