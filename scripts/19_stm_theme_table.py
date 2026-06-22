"""19 — N4: theme-level STM exhibit (PRIMARY) + topic-level multiplicity count.
Aggregates the EXISTING topic-level STM estimateEffect output into the 11 substantive
themes (no new model fit) and produces a theme-level elite-vs-common contrast table.
Also counts how many of the 80 individual topics are nominally "significant" so the
multiplicity can be stated honestly (the cluster-robust theme test is the headline; the
80 doc-level topic tests overstate significance).
Inputs : data/processed/theme_effects.csv  (theme-level, cluster-robust by legislator)
         output/table1_topic_coefs_298.csv  (80 topic-level coefs + p, doc-level)
         data/processed/topic_theme_map.csv
Output : ../paper/tables/table_stm_themes.tex  (bare tabular, INV-13)
         data/processed/stm_theme_summary.csv
No stochastic element -> no seed needed (INV-14)."""
import pandas as pd, numpy as np
from scipy import stats

# ---- theme-level (cluster-robust) effects ----
th = pd.read_csv("data/processed/theme_effects.csv")
th["elite_t"] = th.elite / th.elite_se
th["comun_t"] = th.comun / th.comun_se
th["elite_p"] = 2 * (1 - stats.norm.cdf(th.elite_t.abs()))
th["comun_p"] = 2 * (1 - stats.norm.cdf(th.comun_t.abs()))
th["contrast"] = th.elite - th.comun            # elite minus common emphasis (pts)
th = th.sort_values("contrast")                 # common-leaning (neg) -> elite-leaning (pos)
th.to_csv("data/processed/stm_theme_summary.csv", index=False)

print("[N4] theme-level elite vs common contrast (cluster-robust by legislator):")
for r in th.itertuples():
    lean = "ELITE" if r.contrast > 0 else "common"
    print(f"  {r.theme:28s} elite={r.elite:+.2f} (p={r.elite_p:.3f})  "
          f"common={r.comun:+.2f} (p={r.comun_p:.3f})  contrast={r.contrast:+.2f} -> {lean}")

# ---- multiplicity among the 80 topics (doc-level, no clustering) ----
tp = pd.read_csv("output/table1_topic_coefs_298.csv")
n_topics = len(tp)
for a in [0.05, 0.01]:
    sig_e = int((tp.p_elite < a).sum()); sig_c = int((tp.p_comun < a).sum())
    print(f"[N4] topics with |p|<{a}: elite={sig_e}/{n_topics}, common={sig_c}/{n_topics} (doc-level, UNclustered)")
# Bonferroni-style expectation under the null
exp_false_05 = 0.05 * n_topics
sig_e05 = int((tp.p_elite < 0.05).sum())
sig_c05 = int((tp.p_comun < 0.05).sum())
print(f"[N4] expected false positives at .05 under null: ~{exp_false_05:.1f} of {n_topics}")
# BH-FDR adjusted count (honest)
def n_bh(p, q=0.05):
    p = np.sort(p.values); m = len(p)
    thr = q * (np.arange(1, m + 1)) / m
    below = p <= thr
    # BH-FDR survivor count = largest index k (1-based) with p_(k) <= thr_(k).
    # The previous one-liner used below[::-1].argmax(), which short-circuits to 0 when the
    # LARGEST sorted p-value passes (argmax==0), spuriously reporting 0 survivors.
    return int(np.where(below)[0].max() + 1) if below.any() else 0
nbh_e = n_bh(tp.p_elite); nbh_c = n_bh(tp.p_comun)
print(f"[N4] BH-FDR(0.05) survivors: elite={nbh_e}/{n_topics}, common={nbh_c}/{n_topics}")

# ---- bare tabular (INV-13) ----
def star_from_p(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""

lines = ["\\begin{tabular}{lccc}", "\\toprule"]
lines.append(" & Elite & Common & Elite $-$ Common \\\\")
lines.append("Theme & emphasis & emphasis & contrast \\\\")
lines.append("\\midrule")
for r in th.itertuples():
    theme = str(r.theme).replace("&", "\\&")
    lines.append(
        f"{theme} & {r.elite:+.2f}{star_from_p(r.elite_p)} & "
        f"{r.comun:+.2f}{star_from_p(r.comun_p)} & {r.contrast:+.2f} \\\\")
lines += ["\\bottomrule", "\\end{tabular}"]
with open("../paper/tables/table_stm_themes.tex", "w") as f:
    f.write("\n".join(lines) + "\n")
print("[N4] wrote ../paper/tables/table_stm_themes.tex")
