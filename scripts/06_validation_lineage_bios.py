import pandas as pd, json, re, unicodedata
def dac(s): return unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()
E285=set(pd.read_csv("/tmp/enduring_elite_FINAL.csv").surname.map(dac))

print("=== 1) ELITE HOMOGAMY (roster Pat/Mat) ===")
d=pd.read_csv("data/processed/cong_df.csv")
d["pe"]=d.Pat.map(lambda s:dac(s) in E285); d["me"]=d.Mat.map(lambda s:dac(s) in E285)
pe=d[d.pe]; npe=d[~d.pe]
print(f"  P(mother elite | father elite) = {100*pe.me.mean():.1f}%  vs  father-not = {100*npe.me.mean():.1f}%  ({pe.me.mean()/max(npe.me.mean(),1e-9):.1f}x)")
print(f"  [65-list was 29.7% vs 5.8% = 5.1x]")

recs=[x for x in json.load(open("/tmp/extract_sonnet_corrected.json")) if x.get("fields")]
txt={x["file"]: dac(open(x["file"]).read()) for x in recs}
for x in recs:
    x["e"]= dac(x.get("pat","")) in E285 or dac(x.get("mat","")) in E285
el=[x for x in recs if x["e"]]; ot=[x for x in recs if not x["e"]]
print(f"\n=== 2) CLUB DE LA UNION (bios) — elite-285 vs other ===")
CU=re.compile("CLUB DE LA UNION")
re_=100*sum(bool(CU.search(txt[x['file']])) for x in el)/len(el)
ro =100*sum(bool(CU.search(txt[x['file']])) for x in ot)/len(ot)
print(f"  elite-285 {re_:.1f}%  vs other {ro:.1f}%  ({re_/max(ro,.1):.1f}x)   [65-list: 14.1% vs 6.3% = 2.2x]")
print(f"\n=== 3) ELITE-PRIVATE SCHOOL, 20th c (1900+) — elite-285 vs other ===")
def yr(x):
    try: return int(x.get("start") or 0)
    except: return 0
el20=[x for x in el if yr(x)>=1900]; ot20=[x for x in ot if yr(x)>=1900]
re_=100*sum(x['fields'].get('c_elite_priv_school') for x in el20)/len(el20)
ro =100*sum(x['fields'].get('c_elite_priv_school') for x in ot20)/len(ot20)
print(f"  elite-285 {re_:.1f}%  vs other {ro:.1f}%  ({re_/max(ro,.1):.1f}x)  n={len(el20)}/{len(ot20)}   [65-list: 48.8% vs 16.6% = 2.9x]")
print(f"\n  elite-285 share of all bio'd legislators: {100*len(el)/len(recs):.0f}% (n={len(el)})")
