"""05 — Interrupted time series: enduring-elite share of Congress and the 1925 break.
Inputs : data/processed/cong_df.csv, data/processed/enduring_elite_FINAL.csv
Outputs: figures/figure_its_1925.png/.pdf (published to ../paper/figures if that tree exists),
         output/its_1925_headline.csv, plus printed segmented-regression coefficients.

R&R 2026 correction (E1): the annual share uses the shared rule in _measure_helpers
(annual_share_frame): years with fewer than 5 sitting legislators are undefined and dropped.
Congress did not sit in 1925, so 1925 is a gap in the series (it was previously coded 0% via
elite / max(n, 1)). Published headline -13.32 -> corrected -11.01 (matches script 41, gap column).
Round 2: paths anchored on the repo (runs from any cwd); the in-figure marker reads
"1925 Constitution" (the paper does not attribute the break to the salary reform alone).
Deterministic; no seed needed (INV-14)."""
import pandas as pd, numpy as np, unicodedata
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
from _measure_helpers import annual_share_frame, MIN_SITTING, DATA, OUTPUT, FIGURES, publish
dac=lambda s: unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()
ELITE=set(dac(s) for s in pd.read_csv(DATA / "enduring_elite_FINAL.csv").surname)
d=pd.read_csv(DATA / "cong_df.csv"); d["S"]=pd.to_numeric(d.Start,errors="coerce"); d["E"]=pd.to_numeric(d.End,errors="coerce")
d=d.dropna(subset=["S","E"]); el=(d.Pat.map(dac).isin(ELITE)|d.Mat.map(dac).isin(ELITE)).values
S=d.S.values; E=d.E.values
df=annual_share_frame(el,S,E,1880,1970); BR=1925
dropped=sorted(set(range(1880,1971))-set(df.year))
print(f"years dropped (< {MIN_SITTING} sitting): {dropped}   N={len(df)}")
df["t"]=df.year-BR; df["post"]=(df.year>=BR).astype(int); df["tpost"]=df.t*df.post
m=smf.ols("elite ~ t + post + tpost",df).fit(cov_type="HAC",cov_kwds={"maxlags":5})
print(f"pre-1925 trend     {m.params['t']:+.3f} pts/yr (p={m.pvalues['t']:.3f})")
print(f"LEVEL shift 1925   {m.params['post']:+.2f} pts   (se={m.bse['post']:.2f}, p={m.pvalues['post']:.4f})")
print(f"slope change       {m.params['tpost']:+.3f} pts/yr (p={m.pvalues['tpost']:.3f})")
ci=m.conf_int()
pd.DataFrame([{"term":k,"coef":m.params[k],"se":m.bse[k],"p":m.pvalues[k],
               "ci_lo":ci.loc[k,0],"ci_hi":ci.loc[k,1]} for k in ["Intercept","t","post","tpost"]]
             ).assign(n_years=len(df),years_dropped=";".join(map(str,dropped))
             ).to_csv(OUTPUT / "its_1925_headline.csv",index=False)
print(f"95% CI level shift [{ci.loc['post',0]:.2f}, {ci.loc['post',1]:.2f}]  -> saved output/its_1925_headline.csv")
plt.rcParams.update({"font.family":"serif","font.size":11}); fig,ax=plt.subplots(figsize=(9,5))
ax.scatter(df.year,df.elite,s=14,color="#1f3a93",alpha=.6)
for seg,c in [(df[df.post==0],"#1f3a93"),(df[df.post==1],"#b03030")]: ax.plot(seg.year,m.predict(seg),color=c,lw=2.5)
ax.axvline(BR,ls="--",color="grey"); ax.text(1926,ax.get_ylim()[1]*.93,"1925 Constitution",color="grey",fontsize=9)
ax.set_xlabel("Year"); ax.set_ylabel("Enduring-elite share of Congress (%)")
# No in-figure title (INV-12): title lives in the LaTeX \caption.
for s in ["top","right"]: ax.spines[s].set_visible(False)
ax.grid(alpha=.25); fig.tight_layout()
for ext, kw in [("png", {"dpi": 150}), ("pdf", {})]:
    fig.savefig(FIGURES / f"figure_its_1925.{ext}", **kw)
    publish(FIGURES / f"figure_its_1925.{ext}", "figures")
