import os, pandas as pd, collections, unicodedata
from pathlib import Path
# Repo root = parent of this scripts/ directory; large raw sources live OUTSIDE the repo.
REPO = Path(__file__).resolve().parents[1]
# RAW_DATA_ROOT: the paper project dir (default), env-overridable -- same anchor as
# _measure_helpers.py. DATOS_ROOT is the shared data tree two levels above it that holds
# the large external primary sources (padron, censo, Registro Civil). Set DATOS_ROOT to
# override; the default reproduces the author's layout without any user-specific path.
RAW_DATA_ROOT = Path(os.environ.get("RAW_DATA_ROOT", REPO.parent))
DATOS_ROOT = Path(os.environ.get("DATOS_ROOT", RAW_DATA_ROOT.parent.parent))
# 2020 electoral padron with imputed NSE per surname (NOT shipped in the repo).
F=str(DATOS_ROOT / "geo_padron" / "geo_padron_2020" / "padron_2020_nse_surnames.csv")
agg=collections.defaultdict(lambda:[0,0.0,0])   # surname -> [n_occ, sum_nse, n_nse]
def clean(series):
    return (series.astype(str).str.normalize("NFKD").str.encode("ascii","ignore")
            .str.decode("ascii").str.upper().str.strip())
gsum=gn=0; rows=0
for chunk in pd.read_csv(F, usecols=["paterno","materno","new_nse"], chunksize=500000):
    rows+=len(chunk)
    nse=pd.to_numeric(chunk["new_nse"], errors="coerce")
    gsum+=nse.sum(); gn+=nse.notna().sum()
    for col in ["paterno","materno"]:
        long=pd.DataFrame({"s":clean(chunk[col]),"nse":nse.values})
        g=long.groupby("s")["nse"].agg(["size","sum","count"])
        for s,r in g.iterrows():
            if not s or s=="NAN": continue
            a=agg[s]; a[0]+=int(r["size"]); a[1]+= (0.0 if pd.isna(r["sum"]) else float(r["sum"])); a[2]+=int(r["count"])
    print(f"  processed {rows} rows, {len(agg)} unique surnames", flush=True)

print(f"\nglobal mean new_nse = {gsum/gn:.2f}")
out=pd.DataFrame([(s,a[0],a[2], (a[1]/a[2] if a[2] else None)) for s,a in agg.items()],
                 columns=["surname","n_occ","n_nse","mean_nse"])
out=out.sort_values("n_occ", ascending=False)
out.to_csv("/tmp/surname_nse.csv", index=False)
print(f"saved {len(out)} surnames -> /tmp/surname_nse.csv")
print("\n-- sanity: mean_nse for known elite vs common surnames (n>=50) --")
for s in ["LARRAIN","ERRAZURIZ","EDWARDS","SUBERCASEAUX","MATTE","VIAL","GONZALEZ","MUNOZ","ROJAS","PEREZ","SOTO"]:
    r=out[out.surname==s]
    if len(r): print(f"  {s:14} n={int(r.n_occ.iloc[0]):7}  mean_nse={r.mean_nse.iloc[0]:.1f}")
