"""26 — Topic-to-theme crosswalk table.
Documents which of the 80 STM topics is assigned to each substantive theme, so the
theme aggregation in Table 1 / appendix is auditable from the paper itself.
Inputs : data/processed/topic_theme_map.csv  (topic, theme)
         data/processed/theme_effects.csv     (theme ordering by elite/common emphasis)
Output : ../paper/tables/table_theme_crosswalk.tex  (bare tabular, INV-13)"""
import pandas as pd

m = pd.read_csv("data/processed/topic_theme_map.csv")

# Theme order = the eleven substantive themes in the same order as main-text Table 1
# (by elite-minus-common contrast, descending), with the residual "Other" bucket last.
ORDER = [
    "Elections & parties", "Defense & security", "State administration",
    "Foreign relations", "Education", "Finance & taxation",
    "Social welfare & health", "Local government & land", "Justice & law",
    "Public works", "Labor & industry", "Other",
]

def fmt_topics(nums):
    return ", ".join(str(n) for n in sorted(nums))

rows = []
for theme in ORDER:
    nums = m.topic[m.theme == theme].tolist()
    if not nums:
        continue
    label = theme.replace("&", "\\&")
    rows.append(f"{label} & {len(nums)} & {fmt_topics(nums)} \\\\")

assert sum(len(m.topic[m.theme == t]) for t in ORDER) == len(m), "theme order misses a theme"

lines = [
    "\\begin{tabular}{lcL{8.2cm}}",
    "\\toprule",
    "Theme & \\# topics & Constituent topic numbers \\\\",
    "\\midrule",
    *rows,
    "\\bottomrule",
    "\\end{tabular}",
]
with open("../paper/tables/table_theme_crosswalk.tex", "w") as f:
    f.write("\n".join(lines) + "\n")
print("wrote ../paper/tables/table_theme_crosswalk.tex")
print(f"  {len(rows)} themes, {len(m)} topics total")
