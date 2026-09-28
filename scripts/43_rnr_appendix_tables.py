"""43 — R&R 2026: appendix tables built from the approved A1 / A2 outputs (no re-estimation).

(1) Event comparison (A1, referee R1.2b). Copies the approved bare tabular
    output/rnr2026/A1_event_comparison.tex (script 37) VERBATIM to
    ../paper/tables/table_event_comparison.tex. Nothing is recomputed.
(2) Validation by era (A2, referee R2.1; decision D10: one appendix table with the by-period
    checks). Compact bare tabular from the existing script-38 CSVs, one column per era
    (1834-1890, 1891-1924, 1925-1973, 1990-2020):
      Panel A  biographical markers, elite vs rest (first-entry era; v2 biography corpus):
               rates and elite/rest ratio with Katz 95% CI  <- a2_markers_by_era.csv
      Panel B  known groups: Senate vs Chamber elite share and the gap (pp, SE clustered by
               legislator)                                   <- a2_senate_chamber_by_era.csv
      Panel C  party blocs: right minus left elite share (pp, legislator-cluster bootstrap
               95% CI; 12b bloc mapping + extension)         <- a2_party_bloc_by_era.csv
    The markers-only table (a2_markers_by_era.tex) stays in output/rnr2026/.
Output: tables/table_event_comparison.tex, tables/table_validation_by_era.tex, published to
        ../paper/tables if that tree exists (bare tabular, booktabs, INV-13).
Paths anchored on the repo (any cwd). Deterministic, no seed (INV-14). Needs 37 and 38 outputs.
"""
import shutil
from pathlib import Path
import sys

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
IN = REPO / "output" / "rnr2026"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _measure_helpers import TABLES as TAB, publish  # noqa: E402
ERAS = ["1834-1890", "1891-1924", "1925-1973", "1990-2020"]

# ---- (1) event comparison: verbatim copy -------------------------------------------------
src = IN / "A1_event_comparison.tex"
dst = TAB / "table_event_comparison.tex"
shutil.copyfile(src, dst)
assert src.read_bytes() == dst.read_bytes()
print(f"copied {src.name} -> {dst}")
publish(dst, "tables")

# ---- (2) validation by era ---------------------------------------------------------------
mk = pd.read_csv(IN / "a2_markers_by_era.csv")
mk = mk[mk.era_def == "first_entry"].set_index(["marker", "era"])
sc = pd.read_csv(IN / "a2_senate_chamber_by_era.csv")
sc = sc[sc.variant == "all"].set_index("era")
pb = pd.read_csv(IN / "a2_party_bloc_by_era.csv")
pb = pb[pb.mapping == "12b_plus_ext"].set_index("window")


def num(x, d=1, sign=False):
    """Math-mode number with a true minus sign."""
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    return f"${s}$"


def marker_rate(r):
    """Elite % / rest % for one marker x era row."""
    return f"{r.rate_elite:.1f} / {100 * (r.k_common + r.k_other) / (r.n_common + r.n_other):.1f}"


def marker_ratio(r):
    """Elite/rest ratio [Katz 95% CI], or n.e. when the elite cell is zero."""
    if int(r.k_elite) == 0 or bool(r.rr_e_rest_zero_cell):
        return f"n.e.\\ (0 of {int(r.n_elite)})"
    return f"{r.rr_e_rest:.2f} [{r.rr_e_rest_lo:.2f}, {r.rr_e_rest_hi:.2f}]"


def marker_cells(marker):
    rows_ = [mk.loc[(marker, e)] for e in ERAS]
    return [marker_rate(r) for r in rows_], [marker_ratio(r) for r in rows_]


def row(label, cells):
    return f"{label} & " + " & ".join(cells) + " \\\\"


club_rates, club_ratios = marker_cells("club")
sch_rates, sch_ratios = marker_cells("school")
n_bios = [f"{int(mk.loc[('club', e)].n_elite)} / "
          f"{int(mk.loc[('club', e)].n_common + mk.loc[('club', e)].n_other)}" for e in ERAS]

sen_rates = [f"{sc.loc[e].elite_pct_senate:.1f} / {sc.loc[e].elite_pct_chamber:.1f}" for e in ERAS]
sen_gap = [f"{num(sc.loc[e].gap_pp, 1, True)} ({sc.loc[e].gap_se_clustered:.1f})" for e in ERAS]
sen_n = [f"{int(sc.loc[e].n_terms_senate)} / {int(sc.loc[e].n_terms_chamber)}" for e in ERAS]

bloc_rates = [f"{pb.loc[e].elite_pct_derecha:.1f} / "
              + ("--" if pd.isna(pb.loc[e].gap_pp) else f"{pb.loc[e].elite_pct_izquierda:.1f}") for e in ERAS]
bloc_gap = ["n.e.\\ (no left bloc)" if pd.isna(pb.loc[e].gap_pp)
            else f"{num(pb.loc[e].gap_pp, 1, True)} [{num(pb.loc[e].gap_lo, 1)}, {num(pb.loc[e].gap_hi, 1)}]"
            for e in ERAS]

lines = [
    "\\begin{tabular}{lcccc}",
    "\\toprule",
    " & 1834--1890 & 1891--1924 & 1925--1973 & 1990--2020 \\\\",
    "\\midrule",
    "\\multicolumn{5}{l}{\\textit{Panel A: Biographical markers, elite vs.\\ rest (\\%)}} \\\\",
    row("\\quad Club de la Uni\\'on", club_rates),
    row("\\quad \\quad ratio [95\\% CI]", club_ratios),
    row("\\quad Elite private school", sch_rates),
    row("\\quad \\quad ratio [95\\% CI]", sch_ratios),
    row("\\quad Biographies (elite / rest)", n_bios),
    "\\\\[0.3em]",
    "\\multicolumn{5}{l}{\\textit{Panel B: Senate vs.\\ Chamber, enduring-elite share (\\%)}} \\\\",
    row("\\quad Senate / Chamber", sen_rates),
    row("\\quad Gap, pp (SE)", sen_gap),
    row("\\quad Terms (Senate / Chamber)", sen_n),
    "\\\\[0.3em]",
    "\\multicolumn{5}{l}{\\textit{Panel C: Party blocs, enduring-elite share (\\%)}} \\\\",
    row("\\quad Right / Left", bloc_rates),
    row("\\quad Gap, pp [95\\% CI]", bloc_gap),
    "\\bottomrule",
    "\\end{tabular}",
]
out = TAB / "table_validation_by_era.tex"
out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"wrote {out}")
publish(out, "tables")
print("\n".join(lines))
