"""20 — N5: regenerate Figure 2 (composition) with a pre-1884 shaded region marking
that over-representation ratios are computable only from 1884 onward (the dynamic
population denominator from the Registro Civil starts in 1884). Mirrors
04_figure2_composition.py exactly; ONLY adds the visual marker. Underlying numbers
unchanged.
Inputs : data/processed/cong_df.csv, enduring_elite_FINAL.csv, pop_prevalence_by_year.csv
Output : ../paper/figures/figure2_dynamic.pdf (+ .png)   [the manuscript figure]
No stochastic element -> no seed needed (INV-14)."""
import pandas as pd, numpy as np, unicodedata
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

def dac(s): return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()
ELITE = set(pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname.map(dac))
COMMON = set('GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS MOLINA RIVERA GUZMAN SANDOVAL ORTIZ'.split())
d = pd.read_csv("data/processed/cong_df.csv")
d["S"] = pd.to_numeric(d.Start, errors="coerce"); d["E"] = pd.to_numeric(d.End, errors="coerce")
d = d.dropna(subset=["S", "E"]); pat = d.Pat.map(dac); mat = d.Mat.map(dac)
ie = (pat.isin(ELITE) | mat.isin(ELITE)).values
ic = ((~ie) & (pat.isin(COMMON) | mat.isin(COMMON))).values
io = ~(ie | ic)                                            # M3: residual "other" surnames
S = d.S.values; E = d.E.values; yrs = np.arange(1830, 2021)
def ser(f):
    o = []
    for y in yrs:
        m = (S <= y) & (E >= y); n = m.sum()
        o.append(100 * f[m].sum() / n if n >= 5 else np.nan)
    return pd.Series(o).rolling(5, center=True, min_periods=3).mean()
el, co, ot = ser(ie), ser(ic), ser(io)                     # other = 100 - elite - common
pop = pd.read_csv("data/processed/pop_prevalence_by_year.csv")
pe = pop.set_index("year").pct_elite.rolling(7, center=True, min_periods=1).mean()
pc = pop.set_index("year").pct_common.rolling(7, center=True, min_periods=1).mean()
plt.rcParams.update({"font.size": 11, "font.family": "serif"})
fig, ax = plt.subplots(figsize=(10, 5.2))
# --- N5 marker: pre-1884 region where over-rep ratios are not computable ---
ax.axvspan(1830, 1884, color="#999999", alpha=.12, zorder=0)
ax.axvline(1884, ls="-", color="#666666", lw=1.0, alpha=.8, zorder=1)
ax.text(1857, 56, "Over-representation\nratios start 1884", ha="center", va="top",
        fontsize=7.5, color="#555555")
ax.plot(yrs, el, color="#1f3a93", lw=2.3, label="Elite surnames (Congress)")
ax.plot(yrs, co, color="#b03030", lw=2.3, label="Common surnames (Congress)")
ax.plot(yrs, ot, color="#8a7a2e", lw=2.3, label="Other surnames (Congress)")   # M3: residual
ax.plot(pe.index, pe.values, color="#1f3a93", lw=1.6, ls=":", label="Elite, population (dynamic)")
ax.plot(pc.index, pc.values, color="#b03030", lw=1.6, ls=":", label="Common, population (dynamic)")
ax.axvspan(1973, 1990, color="grey", alpha=.10); ax.text(1981.5, 3, "Congress\nclosed", ha="center", fontsize=7, color="grey")
ax.axvline(1925, ls="--", color="grey", lw=1.1, alpha=.8); ax.text(1926, 92, "1925", color="grey", fontsize=9)
ax.set_xlabel("Year"); ax.set_ylabel("Share (%)")
ax.set_xlim(1830, 2020); ax.set_ylim(0, 100)            # M3: raise ylim so the large "other" residual is visible
ax.legend(frameon=False, fontsize=9, loc="center left", bbox_to_anchor=(1.01, 0.5)); ax.grid(alpha=.25, lw=.5)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig("../paper/figures/figure2_dynamic.pdf", bbox_inches="tight")
fig.savefig("../paper/figures/figure2_dynamic.png", dpi=150, bbox_inches="tight")
# also refresh the repo copy for consistency
fig.savefig("figures/figure2_dynamic.pdf", bbox_inches="tight")
fig.savefig("figures/figure2_dynamic.png", dpi=150, bbox_inches="tight")
def at(s, y): return s.values[s.index.get_indexer([y], method="nearest")[0]]
def cong(s, y): return s.values[np.where(yrs == y)[0][0]]
print("[N5] over/under-representation (unchanged numbers):")
for y in [1900, 1950, 2010]:
    print(f"  {y}: elite {cong(el, y):.0f}% / {at(pe, y):.1f}% = {cong(el, y) / at(pe, y):.0f}x over")
print("[N5] saved ../paper/figures/figure2_dynamic.pdf with pre-1884 shading")

# ---- M3: "other" Congress trajectory (residual = 100 - elite - common) ----
print("\n[M3] Congress surname-group shares (smoothed) at benchmark years:")
m3_rows = []
for y in [1860, 1900, 1925, 1950, 2010]:
    e, c, o = cong(el, y), cong(co, y), cong(ot, y)
    print(f"  {y}: elite {e:.1f}%  common {c:.1f}%  other {o:.1f}%")
    m3_rows.append({"year": y, "elite": round(e, 1), "common": round(c, 1), "other": round(o, 1)})
pd.DataFrame(m3_rows).to_csv("output/m3_other_trajectory.csv", index=False)
print("[M3] saved output/m3_other_trajectory.csv ; 'other' line added to figure2_dynamic")
