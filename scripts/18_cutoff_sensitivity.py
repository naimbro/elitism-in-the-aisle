"""18 — N3: SES-cutoff sensitivity of the headline results.
Re-runs the measure build varying the Gate-1 SES cutoff in {60, 65, 70} (65 = headline),
and reports for each: surname count, elite Congress share (1860s, 2010s), over-
representation fold ~1900, and the 1925 ITS level break. Optionally also varies the
bearer floor. Confirms headline results are stable across reasonable cutoffs.
Inputs : data/processed/cong_df.csv, pop_prevalence_by_year.csv, surname_nse.csv,
         1874 censo, elite-network xlsx (via _measure_helpers; SKIP exit if absent).
Output : tables/table_cutoff_sensitivity.tex (bare tabular, INV-13; published to
         ../paper/tables if that tree exists), data/processed/cutoff_sensitivity.csv
No stochastic element -> no seed needed (INV-14).

R&R 2026 correction (E1): its_break() uses the shared rule in _measure_helpers
(annual_share_frame): years with fewer than 5 sitting legislators are undefined and dropped
(1925, when Congress did not sit, was previously coded 0% via elite / max(n, 1)). The level
columns (1860s, 2010s, fold ~1900) already used the n >= 5 rule and are unchanged.
Round 2: the smoothed share also calls the shared annual_share (same n >= 5 rule, no inline
copy); repo-anchored paths; math-mode minus signs; comprehensions instead of append loops."""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf
from _measure_helpers import (dac, build_hist, load_ses, build_list, annual_share,
                              annual_share_frame, DATA, TABLES, publish, star, tex_num)

HIST = build_hist()
NSE, NOCC = load_ses()

# roster + population
d = pd.read_csv(DATA / "cong_df.csv")
d["S"] = pd.to_numeric(d.Start, errors="coerce"); d["E"] = pd.to_numeric(d.End, errors="coerce")
d = d.dropna(subset=["S", "E"])
pat = d.Pat.map(dac); mat = d.Mat.map(dac)
S = d.S.values; E = d.E.values
pop = pd.read_csv(DATA / "pop_prevalence_by_year.csv")
pe = pop.set_index("year").pct_elite.rolling(7, center=True, min_periods=1).mean()
yrs_full = np.arange(1830, 2021)


def pop_at(y):
    return pe.values[pe.index.get_indexer([y], method="nearest")[0]]


def cong_share(flag, y, smooth=True):
    """Elite share in year y (n >= 5 rule); smooth=True -> centred 5-yr mean (min 3 years)."""
    if smooth:
        s = pd.Series(annual_share(flag, S, E, yrs_full)).rolling(5, center=True, min_periods=3).mean()
        return s.values[np.where(yrs_full == y)[0][0]]
    return annual_share(flag, S, E, [y])[0]


def its_break(flag):
    df = annual_share_frame(flag, S, E, 1880, 1970)   # 1925 (no sitting Congress) dropped
    df["t"] = df.year - 1925; df["post"] = (df.year >= 1925).astype(int); df["tpost"] = df.t * df.post
    m = smf.ols("elite ~ t + post + tpost", df).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return m.params["post"], m.pvalues["post"]


# The PUBLISHED headline list (298 surnames, LLM-curated gate-2 + business gate).
# Reported as the headline row so the table matches the manuscript exactly; the
# deterministic SES-cutoff rows below show stability of the SAME pattern when the
# gate-2 attestation is reconstructed without the LLM.
PUB = set(dac(s) for s in pd.read_csv(DATA / "enduring_elite_FINAL.csv").surname)

configs = [(60, 30), (65, 30), (70, 30)]   # (ses_cut, min_bearers); 65/30 = headline cutoff
extra = [(65, 5), (65, 50)]                # cheap floor variations on the headline cutoff
# (label, surname_set, ses_cut, min_bearers, is_published)
specs = [("published", PUB, 65, 30, True)]
specs += [(None, build_list(HIST, NSE, NOCC, ses_cut=c, min_bearers=m, gate_ses=True), c, m, False)
          for c, m in configs + extra]


def spec_row(label, lst, ses_cut, minb, is_pub):
    flag = (pat.isin(lst) | mat.isin(lst)).values
    sh_1860 = cong_share(flag, 1865)
    sh_2010 = cong_share(flag, 2015)
    fold_1900 = cong_share(flag, 1900) / pop_at(1900)
    brk, brp = its_break(flag)
    tag = " <- PUBLISHED" if is_pub else (" <- headline cutoff (det.)" if (ses_cut == 65 and minb == 30) else "")
    nm = "PUBLISHED 298" if is_pub else f"SES>={ses_cut}, bearers>={minb}"
    print(f"[N3] {nm}: n={len(lst):4d}  1860s={sh_1860:.1f}%  "
          f"2010s={sh_2010:.1f}%  fold1900={fold_1900:.1f}x  break1925={brk:+.2f} (p={brp:.4f}){tag}")
    return {"spec": label or f"ses{ses_cut}_b{minb}", "ses_cut": ses_cut,
            "min_bearers": minb, "n_surnames": len(lst),
            "share_1860s": round(sh_1860, 1), "share_2010s": round(sh_2010, 1),
            "fold_1900": round(fold_1900, 1), "break_1925": round(brk, 2),
            "break_p": round(brp, 4),
            "published": is_pub, "headline": (ses_cut == 65 and minb == 30)}


res = pd.DataFrame([spec_row(*sp) for sp in specs])
res.to_csv(DATA / "cutoff_sensitivity.csv", index=False)

# ---- bare tabular (INV-13) ----
pub = res[res.published]
det = res[~res.published]
main = det[det.min_bearers == 30].sort_values("ses_cut")
floors = det[(det.ses_cut == 65)].sort_values("min_bearers")


def row(nm, r):
    return (f"{nm} & {r.n_surnames} & {r.share_1860s:.1f} & {r.share_2010s:.1f} & "
            f"{r.fold_1900:.1f}$\\times$ & {tex_num(r.break_1925, 2, star(r.break_p))} \\\\")


lines = ["\\begin{tabular}{lccccc}", "\\toprule",
         " & Surname & Elite share & Elite share & Over-rep. & 1925 level \\\\",
         "Specification & count & 1860s (\\%) & 2010s (\\%) & fold $\\sim$1900 & break (pts) \\\\",
         "\\midrule",
         *[row("Published measure (SES $\\geq$ 65)", r) for r in pub.itertuples()],
         "\\\\[0.3em]",
         "\\multicolumn{6}{l}{\\textit{Panel A: SES cutoff, gate-2 reconstructed (bearer floor = 30)}} \\\\",
         *[row(f"SES $\\geq$ {r.ses_cut}", r) for r in main.itertuples()],
         "\\\\[0.3em]",
         "\\multicolumn{6}{l}{\\textit{Panel B: bearer floor (SES $\\geq$ 65)}} \\\\",
         *[row(f"$\\geq$ {r.min_bearers} bearers", r) for r in floors.itertuples()],
         "\\bottomrule", "\\end{tabular}"]
out_tab = TABLES / "table_cutoff_sensitivity.tex"
out_tab.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"[N3] wrote {out_tab}")
publish(out_tab, "tables")
