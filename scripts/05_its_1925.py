"""05 — Interrupted time series: enduring-elite share of Congress & the 1925 salary reform.
Inputs: data/processed/cong_df.csv, data/processed/enduring_elite_FINAL.csv
Output: figures/figure_its_1925.png  +  printed segmented-regression coefficients."""
import pandas as pd, numpy as np, unicodedata
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
dac=lambda s: unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()
ELITE=set(dac(s) for s in pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname)
d=pd.read_csv("data/processed/cong_df.csv"); d["S"]=pd.to_numeric(d.Start,errors="coerce"); d["E"]=pd.to_numeric(d.End,errors="coerce")
d=d.dropna(subset=["S","E"]); el=(d.Pat.map(dac).isin(ELITE)|d.Mat.map(dac).isin(ELITE)).values
S=d.S.values; E=d.E.values
yrs=np.arange(1880,1971)
share=np.array([100*el[(S<=y)&(E>=y)].sum()/max(((S<=y)&(E>=y)).sum(),1) for y in yrs])
df=pd.DataFrame({"year":yrs,"elite":share}); BR=1925
df["t"]=df.year-BR; df["post"]=(df.year>=BR).astype(int); df["tpost"]=df.t*df.post
m=smf.ols("elite ~ t + post + tpost",df).fit(cov_type="HAC",cov_kwds={"maxlags":5})
print(f"pre-1925 trend     {m.params['t']:+.3f} pts/yr (p={m.pvalues['t']:.3f})")
print(f"LEVEL shift 1925   {m.params['post']:+.2f} pts   (p={m.pvalues['post']:.3f})")
print(f"slope change       {m.params['tpost']:+.3f} pts/yr (p={m.pvalues['tpost']:.3f})")
plt.rcParams.update({"font.family":"serif","font.size":11}); fig,ax=plt.subplots(figsize=(9,5))
ax.scatter(df.year,df.elite,s=14,color="#1f3a93",alpha=.6)
for seg,c in [(df[df.post==0],"#1f3a93"),(df[df.post==1],"#b03030")]: ax.plot(seg.year,m.predict(seg),color=c,lw=2.5)
ax.axvline(BR,ls="--",color="grey"); ax.text(1926,ax.get_ylim()[1]*.93,"1925 salary reform",color="grey",fontsize=9)
ax.set_xlabel("Year"); ax.set_ylabel("Enduring-elite share of Congress (%)")
# No in-figure title (INV-12): title lives in the LaTeX \caption.
for s in ["top","right"]: ax.spines[s].set_visible(False)
ax.grid(alpha=.25); fig.tight_layout()
fig.savefig("figures/figure_its_1925.png",dpi=150)
fig.savefig("figures/figure_its_1925.pdf")
