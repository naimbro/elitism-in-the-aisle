"""45 — R&R 2026: all-member event-comparison table for the online appendix (tab:eventcomparison).

Decision D8: the canonical roster is all members (including pre-1891 substitutes). The approved
A1 table (output/rnr2026/A1_event_comparison.tex, script 37; copied verbatim by script 43 to
table_event_comparison.tex) also carries titular-only columns, which stay in the A1 memo. This
script rebuilds the same rows from output/rnr2026/A1_event_comparison.csv keeping only the
all-member columns: the legislature step and the long-window (+/-25 years) ITS level shift, with
its HAC standard error taken from output/rnr2026/A1_event_tests.csv (series "primary",
half_window 25, same test year; the shift is asserted equal to the comparison file's).
Nothing is re-estimated.

Stars: *** p<0.01, ** p<0.05, * p<0.10 (HAC p-values from script 37). ITS cells with fewer than
10 annual observations on either side of the break (flag its25_primary_short) print as "--".
Output: tables/table_event_comparison_all.tex (bare tabular, booktabs, INV-13), published to
../paper/tables if that tree exists. Deterministic, no seed. Needs script 37 output.
"""
import csv
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _measure_helpers import TABLES as TAB, publish, star, tex_num  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "output" / "rnr2026" / "A1_event_comparison.csv"
TESTS = REPO / "output" / "rnr2026" / "A1_event_tests.csv"
DST = TAB / "table_event_comparison_all.tex"

LABELS = {  # CSV event label -> printed label
    "1874 law": "1874 electoral law",
    "1888 reform": "1888 constitutional reform",
    "1914 reform": "1914 electoral law",
    "1925 baseline": "1925 Constitution",
    "1934 women municipal": "1934 women's municipal vote",
    "1949 women national": "1949 women's national vote",
    "1958 ballot": "1958 official ballot",
    "1962 registration": "1962 compulsory registration",
    "1970 illiterate/18+": "1970 illiterate and 18+ vote",
}

with SRC.open(newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
assert len(rows) == 9 and {r["event"] for r in rows} == set(LABELS), "unexpected A1 rows"

with TESTS.open(newline="", encoding="utf-8") as fh:
    SE = {(t["short"], t["test_year"]): t for t in csv.DictReader(fh)
          if t["series"] == "primary" and t["half_window"] == "25" and "GAP" not in t["type"]}


def its_cells(r):
    """Level shift with stars, and its HAC SE in parentheses ("--" for short windows)."""
    if r["its25_primary_short"] == "TRUE" or r["its25_primary"] == "":
        return "--", ""
    t = SE[(r["event"], r["test_year"])]
    assert abs(float(t["shift"]) - float(r["its25_primary"])) < 1e-9, r["event"]
    return (tex_num(float(r["its25_primary"]), 2, star(float(r["its25_primary_p"]))),
            f"({float(t['se']):.2f})")


body = [
    f"{LABELS[r['event']]} & {r['to_legislature'][:7]} & "
    f"{tex_num(float(r['step_all']), 1)} & {its_cells(r)[0]} & {its_cells(r)[1]} \\\\"
    for r in rows
]
tex = "\n".join([
    "\\begin{tabular}{llccc}",
    "\\toprule",
    " & First affected & Legislature & \\multicolumn{2}{c}{ITS level shift ($\\pm$25 years)} \\\\",
    "\\cmidrule(lr){4-5}",
    "Event & legislature & step & Shift & (SE) \\\\",
    "\\midrule",
    *body,
    "\\bottomrule",
    "\\end{tabular}",
    "",
])
DST.write_text(tex, encoding="utf-8")
print(f"wrote {DST}")
publish(DST, "tables")
