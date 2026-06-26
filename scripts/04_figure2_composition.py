import pandas as pd, numpy as np, unicodedata
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
def dac(s): return unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()
ELITE=set(pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname.map(dac))
COMMON=set('GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS MOLINA RIVERA GUZMAN SANDOVAL ORTIZ'.split())
d=pd.read_csv("data/processed/cong_df.csv"); d["S"]=pd.to_numeric(d.Start,errors="coerce"); d["E"]=pd.to_numeric(d.End,errors="coerce")
d=d.dropna(subset=["S","E"]); pat=d.Pat.map(dac); mat=d.Mat.map(dac)
ie=(pat.isin(ELITE)|mat.isin(ELITE)).values; ic=((~ie)&(pat.isin(COMMON)|mat.isin(COMMON))).values
S=d.S.values; E=d.E.values; yrs=np.arange(1830,2021)
def ser(f):
    o=[]
    for y in yrs:
        m=(S<=y)&(E>=y); n=m.sum()
        o.append(100*f[m].sum()/n if n>=5 else np.nan)   # NaN when Congress closed/empty
    return pd.Series(o).rolling(5,center=True,min_periods=3).mean()
el,co=ser(ie),ser(ic)
pop=pd.read_csv("data/processed/pop_prevalence_by_year.csv")
pe=pop.set_index("year").pct_elite.rolling(7,center=True,min_periods=1).mean()
pc=pop.set_index("year").pct_common.rolling(7,center=True,min_periods=1).mean()
plt.rcParams.update({"font.size":11,"font.family":"serif"})
fig,ax=plt.subplots(figsize=(10,5.2))
ax.plot(yrs,el,color="#1f3a93",lw=2.3,label="Elite surnames (Congress)")
ax.plot(yrs,co,color="#b03030",lw=2.3,label="Common surnames (Congress)")
ax.plot(pe.index,pe.values,color="#1f3a93",lw=1.6,ls=":",label="Elite, population (dynamic)")
ax.plot(pc.index,pc.values,color="#b03030",lw=1.6,ls=":",label="Common, population (dynamic)")
ax.axvspan(1834,1884,color="grey",alpha=.07)  # pre-1884: no contemporaneous population reference
ax.axvline(1884,ls=":",color="grey",lw=1.1,alpha=.8); ax.text(1885,57,"pop. ref.\nbegins 1884",color="grey",fontsize=7.5,va="top")
ax.axvspan(1973,1990,color="grey",alpha=.10); ax.text(1981.5,3,"Congress\nclosed",ha="center",fontsize=7,color="grey")
ax.axvline(1925,ls="--",color="grey",lw=1.1,alpha=.8); ax.text(1926,50,"1925",color="grey",fontsize=9)
ax.set_xlabel("Year"); ax.set_ylabel("Share (%)")
# No in-figure title (INV-12): title lives in the LaTeX \caption.
ax.set_xlim(1834,2020); ax.set_ylim(0,60)  # start at 1834 (first Congress); drops the pre-1834 rolling-mean edge artifact
ax.legend(frameon=False,fontsize=9,loc="center left",bbox_to_anchor=(1.01,0.5)); ax.grid(alpha=.25,lw=.5)
for s in ["top","right"]: ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig("figures/figure2_dynamic.png",dpi=150,bbox_inches="tight")
fig.savefig("figures/figure2_dynamic.pdf",bbox_inches="tight")
def at(s,y): return s.values[s.index.get_indexer([y],method="nearest")[0]]
def cong(s,y): return s.values[np.where(yrs==y)[0][0]]
print("OVER/UNDER-representation  (Congress share ÷ population share):")
for y in [1900,1950,2010]:
    print(f"  {y}: elite {cong(el,y):.0f}% / {at(pe,y):.1f}% = {cong(el,y)/at(pe,y):.0f}x over   |   common {cong(co,y):.0f}% / {at(pc,y):.0f}% = {cong(co,y)/at(pc,y):.2f}x")
print("saved")
