"""04 — Figure 3: elite, common, and OTHER surname composition of Congress, 1834-2020,
against the dynamic person-level population reference (Registro Civil, from 1884).

This is the base generator for the composition figure. 20_figure2_reshade.py produces the
byte-identical manuscript copy (same six series and styling) and additionally deposits it to
../paper/figures and writes the M3 'other'-trajectory CSV. The two are kept in sync: any
change to the figure must be made in both.

Six series: three Congress shares (elite / common / other, solid) and three matching
dynamic population references (dotted). 'Other' is the residual (100 - elite - common) in
both Congress and population, added per referee MUST M3 so the 12% elite endpoint is read as
the enduring-Iberian-elite share, with each Congress line shown against its own benchmark.

Inputs : data/processed/cong_df.csv, enduring_elite_FINAL.csv, pop_prevalence_by_year.csv
Output : figures/figure2_dynamic.pdf (+ .png)
No stochastic element -> no seed needed (INV-14). Run from the replication_repo root."""
import pandas as pd, numpy as np, unicodedata
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
def dac(s): return unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()
ELITE=set(pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname.map(dac))
COMMON=set('GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS MOLINA RIVERA GUZMAN SANDOVAL ORTIZ'.split())
d=pd.read_csv("data/processed/cong_df.csv"); d["S"]=pd.to_numeric(d.Start,errors="coerce"); d["E"]=pd.to_numeric(d.End,errors="coerce")
d=d.dropna(subset=["S","E"]); pat=d.Pat.map(dac); mat=d.Mat.map(dac)
ie=(pat.isin(ELITE)|mat.isin(ELITE)).values
ic=((~ie)&(pat.isin(COMMON)|mat.isin(COMMON))).values
io=~(ie|ic)                                                # M3: residual "other" surnames
S=d.S.values; E=d.E.values; yrs=np.arange(1830,2021)
def ser(f):
    o=[]
    for y in yrs:
        m=(S<=y)&(E>=y); n=m.sum()
        o.append(100*f[m].sum()/n if n>=5 else np.nan)     # NaN when Congress closed/empty
    return pd.Series(o).rolling(5,center=True,min_periods=3).mean()
el,co,ot=ser(ie),ser(ic),ser(io)
pop=pd.read_csv("data/processed/pop_prevalence_by_year.csv")
pe=pop.set_index("year").pct_elite.rolling(7,center=True,min_periods=1).mean()
pc=pop.set_index("year").pct_common.rolling(7,center=True,min_periods=1).mean()
# M3 symmetry: population reference for the residual "other" group (= 100 - elite - common).
po=(100-pop.set_index("year").pct_elite-pop.set_index("year").pct_common).rolling(7,center=True,min_periods=1).mean()
plt.rcParams.update({"font.size":11,"font.family":"serif"})
fig,ax=plt.subplots(figsize=(10,5.2))
# pre-1884 region where over-representation ratios are not computable
ax.axvspan(1830,1884,color="#999999",alpha=.12,zorder=0)
ax.axvline(1884,ls="-",color="#666666",lw=1.0,alpha=.8,zorder=1)
ax.text(1857,56,"Over-representation\nratios start 1884",ha="center",va="top",fontsize=7.5,color="#555555")
ax.plot(yrs,el,color="#1f3a93",lw=2.3,label="Elite surnames (Congress)")
ax.plot(yrs,co,color="#b03030",lw=2.3,label="Common surnames (Congress)")
ax.plot(yrs,ot,color="#8a7a2e",lw=2.3,label="Other surnames (Congress)")          # M3: residual
ax.plot(pe.index,pe.values,color="#1f3a93",lw=1.6,ls=":",label="Elite, population (dynamic)")
ax.plot(pc.index,pc.values,color="#b03030",lw=1.6,ls=":",label="Common, population (dynamic)")
ax.plot(po.index,po.values,color="#8a7a2e",lw=1.6,ls=":",label="Other, population (dynamic)")  # M3: benchmark
ax.axvspan(1973,1990,color="grey",alpha=.10); ax.text(1981.5,3,"Congress\nclosed",ha="center",fontsize=7,color="grey")
ax.axvline(1925,ls="--",color="grey",lw=1.1,alpha=.8); ax.text(1926,92,"1925",color="grey",fontsize=9)
ax.set_xlabel("Year"); ax.set_ylabel("Share (%)")
# No in-figure title (INV-12): title lives in the LaTeX \caption.
ax.set_xlim(1830,2020); ax.set_ylim(0,100)               # M3: raise ylim so the large "other" residual is visible
ax.legend(frameon=False,fontsize=9,loc="center left",bbox_to_anchor=(1.01,0.5)); ax.grid(alpha=.25,lw=.5)
for s in ["top","right"]: ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig("figures/figure2_dynamic.png",dpi=150,bbox_inches="tight")
fig.savefig("figures/figure2_dynamic.pdf",bbox_inches="tight")
def at(s,y): return s.values[s.index.get_indexer([y],method="nearest")[0]]
def cong(s,y): return s.values[np.where(yrs==y)[0][0]]
print("OVER/UNDER-representation  (Congress share / population share):")
for y in [1900,1950,2010]:
    print(f"  {y}: elite {cong(el,y):.0f}% / {at(pe,y):.1f}% = {cong(el,y)/at(pe,y):.0f}x over   |   common {cong(co,y):.0f}% / {at(pc,y):.0f}% = {cong(co,y)/at(pc,y):.2f}x")
print("saved figures/figure2_dynamic.{png,pdf}")
