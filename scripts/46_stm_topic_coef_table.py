"""46 — R&R 2026: topic-level STM illustration table (appendix tab:stmcoefs), generated.

Replaces the hand-typed tab:stmcoefs. Nothing is re-estimated; the table is built from CSVs.

Selection (script 12b's tercile rule, then the crosswalk):
  * prev_e, prev_c = topic prevalence for the elite / common surname group with party bloc,
    chamber and year at their means (12b; recomputed by 46a from 12b's estimateEffect object).
  * te = 1/3-quantile of prev_e over the 80 topics, tc = 1/3-quantile of prev_c (R type 7 =
    numpy "linear").
  * elite side : prev_c <= tc and prev_e >= te;  common side: prev_e <= te and prev_c >= tc.
  * drop topics that data/processed/topic_theme_map.csv assigns to "Other" (procedural,
    rhetorical, low-coherence OCR topics; e.g. T13, the session-minutes topic).
Displayed numbers: coef_elite, coef_comun from 12b's estimateEffect summary (vs. the "other"
group), and contrast = coef_elite - coef_comun computed from those two columns. Rows are
ordered by that contrast within each panel (elite panel: largest first; common panel: most
negative first). Leading terms are 12b's top-4 terms by beta (Spanish, as in the corpus).

Guards: the rule applied here must return 12b's saved selection
(output/table1_v3style_adjusted_298.csv, same topics); the elite-panel contrasts must be > 0 and
the common-panel contrasts < 0.

Inputs : output/stm_topic_prevalence_at_means_298.csv (46a), output/table1_topic_coefs_298.csv
         (12b), output/table1_v3style_adjusted_298.csv (12b), data/processed/topic_theme_map.csv
Output : tables/table_stm_topic_coefs.tex (bare tabular, booktabs, INV-13), published to
         ../paper/tables if that tree exists. Deterministic, no seed (INV-14).
"""
import csv
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _measure_helpers import DATA, OUTPUT, TABLES, publish  # noqa: E402

PREV = OUTPUT / "stm_topic_prevalence_at_means_298.csv"
COEFS = OUTPUT / "table1_topic_coefs_298.csv"
SEL12B = OUTPUT / "table1_v3style_adjusted_298.csv"
XWALK = DATA / "topic_theme_map.csv"
DST = TABLES / "table_stm_topic_coefs.tex"
EXCLUDED_THEME = "Other"
N_TOPICS = 80


def read_rows(path):
    with Path(path).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


prev = {int(r["topic"]): r for r in read_rows(PREV)}
coef = {int(r["topic"]): r for r in read_rows(COEFS)}
theme = {int(r["topic"]): r["theme"] for r in read_rows(XWALK)}
assert set(prev) == set(coef) == set(theme) == set(range(1, N_TOPICS + 1)), "topic sets differ"

# ---- 12b tercile rule -------------------------------------------------------------------------
topics = np.arange(1, N_TOPICS + 1)
prev_e = np.array([float(prev[k]["prev_elite"]) for k in topics])
prev_c = np.array([float(prev[k]["prev_common"]) for k in topics])
te = np.quantile(prev_e, 1 / 3)             # numpy "linear" == R quantile type 7 (12b default)
tc = np.quantile(prev_c, 1 / 3)
elite_side = {int(k) for k in topics[(prev_c <= tc) & (prev_e >= te)]}
common_side = {int(k) for k in topics[(prev_e <= te) & (prev_c >= tc)]}


def sel_topics(col):
    return {int(v.split()[0][1:]) for v in (r[col] for r in read_rows(SEL12B)) if v}


assert elite_side == sel_topics("elite_topic"), "rule differs from 12b's elite selection"
assert common_side == sel_topics("common_topic"), "rule differs from 12b's common selection"

# ---- crosswalk exclusion, displayed values, order ----------------------------------------------
def panel(side, descending):
    keep = [k for k in side if theme[k] != EXCLUDED_THEME]
    rows = [(k, float(coef[k]["coef_elite"]), float(coef[k]["coef_comun"])) for k in keep]
    rows = [(k, e, c, e - c) for k, e, c in rows]
    return sorted(rows, key=lambda r: -r[3] if descending else r[3])


dropped = sorted(k for k in elite_side | common_side if theme[k] == EXCLUDED_THEME)
panel_a = panel(elite_side, descending=True)
panel_b = panel(common_side, descending=False)
assert all(r[3] > 0 for r in panel_a) and all(r[3] < 0 for r in panel_b), "contrast sign"


def coef_cell(x):
    """4 decimals, true minus sign, phantom minus on non-negatives (column alignment)."""
    s = f"{x:.4f}"
    return f"${s}$" if s.startswith("-") else f"$\\phantom{{-}}{s}$"


def contrast_cell(x):
    s = f"{x:+.4f}"
    return f"${s}$"


def terms(k):
    """12b's top-4 terms, slash-separated without spaces (fits the appendix text width)."""
    return "/".join(t.replace("_", " ") for t in prev[k]["leading_terms"].split("/"))


def body(rows):
    return [f"T{k} & {terms(k)} & {coef_cell(e)} & {coef_cell(c)} & {contrast_cell(d)} \\\\"
            for k, e, c, d in rows]


tex = "\n".join([
    "\\begin{tabular}{llrrr}",
    "\\toprule",
    "Topic & Leading terms & Elite & Common & Elite $-$ \\\\",
    "      &               & coef. & coef.  & Common \\\\",
    "\\midrule",
    "\\multicolumn{5}{l}{\\textit{Panel A: Policy topics the elite emphasizes more}} \\\\",
    "\\midrule",
    *body(panel_a),
    "\\addlinespace",
    "\\multicolumn{5}{l}{\\textit{Panel B: Policy topics the common group emphasizes more}} \\\\",
    "\\midrule",
    *body(panel_b),
    "\\bottomrule",
    "\\end{tabular}",
    "",
])
DST.write_text(tex, encoding="utf-8")

print(f"tercile thresholds: elite {te:.6f}, common {tc:.6f}")
print(f"12b selection: elite {sorted(elite_side)}, common {sorted(common_side)}")
print(f"dropped as '{EXCLUDED_THEME}' by the crosswalk: {['T%d' % k for k in dropped]}")
for name, rows in (("Panel A (elite)", panel_a), ("Panel B (common)", panel_b)):
    print(name)
    for k, e, c, d in rows:
        print(f"  T{k:<3d} {theme[k]:26s} elite={e:+.4f} common={c:+.4f} contrast={d:+.4f}"
              f"  [{prev[k]['leading_terms']}]")
print(f"wrote {DST}")
publish(DST, "tables")
