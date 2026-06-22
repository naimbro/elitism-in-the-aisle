"""02b — Business-leader Gate-1 alternative. Adds surnames that are (a) overrepresented
among contemporary business leaders (directores+gerentes, vs population) AND (b) present in
a 19th-century historical source (Gate 2), but which the padron-SES Gate 1 missed because
their surnames have diluted across the population. Gate 2 is preserved -> the estimand stays
'enduring elite'. See quality_reports/business_x_historical.csv for the selection.
Inputs: data/processed/enduring_elite_FINAL.csv (the 285 padron-gate list), surname_nse.csv.
Output: overwrites data/processed/enduring_elite_FINAL.csv with the augmented list; backs up
the 285 list to data/processed/enduring_elite_FINAL_285.csv; also refreshes /tmp copy."""
import pandas as pd, unicodedata, shutil, os
def dac(s): return unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()

BASE="data/processed/enduring_elite_FINAL.csv"
cur=pd.read_csv(BASE); cur["surname"]=cur.surname.map(dac)
nse=pd.read_csv("data/processed/surname_nse.csv"); NSE=dict(zip(nse.surname.map(dac),nse.mean_nse)); NOC=dict(zip(nse.surname.map(dac),nse.n_occ))

# 14 business-overrep AND historically-attested surnames, in roster-matching form.
# RUIZ-TAGLE is already in the 285 (kept via dedup). SANTA CRUZ/JAMES/SALVADOR match 0 legislators
# but are retained for completeness of the measure definition.
ADD=["GARCIA-HUIDOBRO","GANA","PASCUAL","COX","BULNES","NOGUERA","BALMACEDA",
     "DOMINGUEZ","GREZ","PORTALES","SANTA CRUZ","JAMES","SALVADOR","RUIZ-TAGLE"]
rows=[]
for s in ADD:
    if s in set(cur.surname): continue
    rows.append({"surname":s,"mean_nse":round(NSE.get(s,float("nan")),1) if s in NSE else "",
                 "n_holders":int(NOC[s]) if s in NOC else "","n_sources":1,
                 "sources":"['business_gate']","in_cur65":False})
addn=pd.DataFrame(rows)
out=pd.concat([cur,addn],ignore_index=True).drop_duplicates(subset="surname",keep="first")

# backup + write both copies
if not os.path.exists("data/processed/enduring_elite_FINAL_285.csv"):
    shutil.copy(BASE,"data/processed/enduring_elite_FINAL_285.csv")
out.to_csv(BASE,index=False)
out.to_csv("/tmp/enduring_elite_FINAL.csv",index=False)
print(f"base 285-list: {len(cur)}  |  genuinely new added: {len(addn)}  |  total: {len(out)}")
print("added:", list(addn.surname))
print("saved -> data/processed/enduring_elite_FINAL.csv (+ /tmp copy); backup -> enduring_elite_FINAL_285.csv")
