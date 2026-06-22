import os, pandas as pd, glob, collections, unicodedata
from pathlib import Path
# Repo root = parent of this scripts/ directory; large raw sources live OUTSIDE the repo.
REPO = Path(__file__).resolve().parents[1]
# RAW_DATA_ROOT: paper project dir (default); DATOS_ROOT: shared data tree (two levels up)
# holding the 23M-row Registro Civil HISTORICO births. Env-overridable; same anchor scheme
# as _measure_helpers.py / 01 / 02. The default reproduces the author's layout.
RAW_DATA_ROOT = Path(os.environ.get("RAW_DATA_ROOT", REPO.parent))
DATOS_ROOT = Path(os.environ.get("DATOS_ROOT", RAW_DATA_ROOT.parent.parent))
E285=set(pd.read_csv("/tmp/enduring_elite_FINAL.csv").surname.map(
    lambda s: unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()))
COMMON=set('GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS MOLINA RIVERA GUZMAN SANDOVAL ORTIZ'.split())
def clean(s): return (s.astype(str).str.normalize("NFKD").str.encode("ascii","ignore").str.decode("ascii").str.upper().str.strip())
agg=collections.defaultdict(lambda:[0,0,0])   # year -> [n_total, n_elite, n_common]
_regciv_glob=str(DATOS_ROOT / "Registro Civil" / "HISTORICO" / "aaaa_appat_apmat_nac_*.csv")
files=sorted(glob.glob(_regciv_glob),
             key=lambda p:int(p.split("_")[-1].split(".")[0]))
tot=0
for i,f in enumerate(files,1):
    d=pd.read_csv(f, encoding="latin-1", sep=None, engine="python")
    d.columns=["yr","pat","mat","nac"]
    d=d[(d.nac.astype(str).str.startswith("CHILEN")) & (pd.to_numeric(d.yr,errors="coerce")>=1884)]
    if len(d)==0: continue
    yr=pd.to_numeric(d.yr,errors="coerce").astype("Int64")
    pat=clean(d.pat); mat=clean(d.mat)
    ie=pat.isin(E285)|mat.isin(E285); ic=(~ie)&(pat.isin(COMMON)|mat.isin(COMMON))
    g=pd.DataFrame({"yr":yr,"ie":ie.values,"ic":ic.values}).groupby("yr").agg(n=("ie","size"),e=("ie","sum"),c=("ic","sum"))
    for y,r in g.iterrows():
        a=agg[int(y)]; a[0]+=int(r.n); a[1]+=int(r.e); a[2]+=int(r.c)
    tot+=len(d)
    if i%15==0: print(f"  {i}/{len(files)} files, {tot} chilean rows, {len(agg)} years", flush=True)
out=pd.DataFrame([(y,a[0],a[1],a[2],100*a[1]/a[0],100*a[2]/a[0]) for y,a in sorted(agg.items())],
                 columns=["year","n_total","n_elite","n_common","pct_elite","pct_common"])
out.to_csv("/tmp/pop_prevalence_by_year.csv",index=False)
print(f"\nDONE. {tot} chilean rows, years {out.year.min()}-{out.year.max()}")
print("decadal elite% / common% (population):")
for dec in range(1890,2021,20):
    s=out[(out.year>=dec)&(out.year<dec+20)]
    if len(s): print(f"  {dec}s-{dec+19}: elite {100*s.n_elite.sum()/s.n_total.sum():.2f}%  common {100*s.n_common.sum()/s.n_total.sum():.1f}%  (n={s.n_total.sum()})")
print("saved /tmp/pop_prevalence_by_year.csv")
