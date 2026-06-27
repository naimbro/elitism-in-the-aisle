"""06c — Validation summary figure (three surname groups).

Supersedes the two-group (elite vs. rest) figure_validation produced by 06b. Renders the
two biographical markers that break out meaningfully across all three surname groups —
Club de la Union membership and 20th-c. elite private schooling — as grouped bars for
elite / common / other, matching the colour scheme and group order of the centrality
figure (07). The third validation marker, lineage homogamy, is intrinsically an
elite-concentration quantity (it is zero by construction for the common and other groups,
which are defined as having no elite parent) and is therefore reported in the text only,
not in this figure.

Input: output/should5_common_pole_validation.csv (the three-group rates computed from the
BCN biographies by script 34; the raw biography text is not redistributed in the public
repo, so the figure reads the deposited rates rather than recomputing them).
Output: figures/figure_validation.png + .pdf  (titleless, INV-12).

Deterministic; no seed needed (INV-14). Run from the replication_repo root.
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---- group order, colours, and labels match the centrality figure (script 07) ----
ORDER = ["elite", "common", "other"]
COL = {"elite": "#1f3a93", "common": "#b03030", "other": "#E7B800"}
LABEL = {"elite": "Elite surname", "common": "Common surname", "other": "Other surname"}

MARKERS = [
    ("club_union", "Club de la Unión\nmembership"),
    ("elite_school_20c", "Elite private school\n(20th c.)"),
]

df = pd.read_csv("output/should5_common_pole_validation.csv")
# keep only the per-group rate rows (drop the elite_over_common_ratio summary rows)
df = df[df.group.isin(ORDER)]

# rate[marker][group]
rate = {m: {g: float(df[(df.marker == m) & (df.group == g)].rate_pct.iloc[0]) for g in ORDER}
        for m, _ in MARKERS}

print("VALIDATION FIGURE (three groups, % of legislators):")
for m, lbl in MARKERS:
    print(f"  {lbl.splitlines()[0]:24s} " +
          "  ".join(f"{g}={rate[m][g]:4.1f}" for g in ORDER))

x = np.arange(len(MARKERS))
w = 0.26
plt.rcParams.update({"font.family": "serif", "font.size": 11})
fig, ax = plt.subplots(figsize=(8, 4.6))

for j, g in enumerate(ORDER):
    vals = [rate[m][g] for m, _ in MARKERS]
    pos = x + (j - 1) * w
    ax.bar(pos, vals, w, label=LABEL[g], color=COL[g], alpha=.9)
    for p, v in zip(pos, vals):
        ax.text(p, v + 0.6, f"{v:.0f}%", ha="center", fontsize=9)

ax.set_xticks(x)
ax.set_xticklabels([lbl for _, lbl in MARKERS], fontsize=9.5)
ax.set_ylabel("Share of legislators (%)")
ax.set_ylim(0, max(rate["elite_school_20c"].values()) * 1.18)
ax.legend(frameon=False, fontsize=10)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
ax.grid(axis="y", alpha=.25)
fig.tight_layout()
fig.savefig("figures/figure_validation.png", dpi=150)
fig.savefig("figures/figure_validation.pdf")
print("saved figures/figure_validation.{png,pdf}")
