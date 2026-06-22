"""15 — Appendix: contemporary convergent validity. Does the enduring-elite surname
measure (and continuous surname-SES) predict W-NOMINATE ideology across three periods?
External dependency: W-NOMINATE estimates from the companion project
  ../2026_graph_based_ideal_points/output/nominate_{diputados,senado}_{2014-2018,2018-2022,2022-2026}.csv
  + output/crosswalk.csv (politician_id->name) + data/congress_matched.csv (party/bloc).
Each period is re-oriented (right=+) before pooling (W-NOMINATE polarity is arbitrary per run)."""
import pandas as pd, numpy as np, unicodedata, glob, os
import statsmodels.formula.api as smf
dac=lambda s: unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()
GIP=os.environ.get("GIP_DIR","../2026_graph_based_ideal_points")   # path to companion project
ELITE=set(dac(s) for s in pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname)
COMMON=set(dac(x) for x in "GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS MOLINA RIVERA GUZMAN SANDOVAL ORTIZ".split())
ses=pd.read_csv("data/processed/surname_nse.csv"); ses["surname"]=ses.surname.map(dac); smap=dict(zip(ses.surname,ses.mean_nse))
cw=pd.read_csv(f"{GIP}/output/crosswalk.csv")[["politician_id","full_name","node_id"]]
cm=pd.read_csv(f"{GIP}/data/congress_matched.csv")[["node_id","bloc"]]
RIGHT={"RN","UDI","EVOPOLI","REPUBLICANO","PRI"}; LEFT={"PS","PC","PPD","PRSD","FRENTE AMPLIO","PH"}
sect=lambda b:"der" if str(b).upper() in RIGHT else "izq" if str(b).upper() in LEFT else "otro"
rows=[]
for f in sorted(glob.glob(f"{GIP}/output/nominate_*_201*.csv")+glob.glob(f"{GIP}/output/nominate_*_2022-2026.csv")):
    d=pd.read_csv(f).merge(cw,on="politician_id",how="left").merge(cm,on="node_id",how="left")
    d["sector"]=d.bloc.map(sect)
    tk=d.full_name.fillna("").map(lambda x:[dac(t) for t in str(x).split()])
    pat=tk.map(lambda t:t[-2] if len(t)>=2 else (t[-1] if t else "")); mat=tk.map(lambda t:t[-1] if t else "")
    d["ses"]=[np.nanmax([smap.get(p,np.nan),smap.get(m,np.nan)]) for p,m in zip(pat,mat)]
    el=[(p in ELITE)or(m in ELITE) for p,m in zip(pat,mat)]; co=[((p in COMMON)or(m in COMMON))and not e for p,m,e in zip(pat,mat,el)]
    d["apellido"]=np.where(el,"elite",np.where(co,"comun","otro"))
    rm=d[d.sector=="der"].coord1D.mean(); lm=d[d.sector=="izq"].coord1D.mean()
    d["ideo"]=d.coord1D*(-1 if rm<lm else 1); d["pc"]=f.split("nominate_")[1].replace(".csv","")
    rows.append(d[["pc","ideo","ses","apellido","sector","full_name"]])
A=pd.concat(rows).dropna(subset=["ideo"]); A["apellido"]=pd.Categorical(A.apellido,["otro","comun","elite"])
print("obs:",len(A))
print("CONTINUOUS SES (pooled, period/chamber FE):",
      smf.ols("ideo ~ ses + C(pc)",A.dropna(subset=['ses'])).fit(cov_type="cluster",cov_kwds={"groups":A.dropna(subset=['ses']).full_name.factorize()[0]}).params.get("ses"))
m=smf.ols('ideo ~ C(apellido,Treatment("otro")) + C(pc)',A).fit(cov_type="cluster",cov_kwds={"groups":A.full_name.factorize()[0]})
print("CATEGORICAL (vs other):",{k.split('T.')[1][:5]:round(v,3) for k,v in m.params.items() if "apellido" in k})
A.groupby("apellido").ideo.agg(["mean","count"]).to_csv("output/nominate_by_surname_type.csv")
