"""06b — Validation summary figure: elite vs. other on three independent criteria.
Mirrors the computations in 06_validation_lineage_bios.py and renders them as one
titleless figure (INV-12). Output: figures/figure_validation.png + .pdf.
Criteria: (1) lineage homogamy from the roster, (2) Club de la Union membership and
(3) 20th-c. elite private schooling from BCN legislator biographies."""
import pandas as pd, json, re, unicodedata, numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
def dac(s): return unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()
E285=set(pd.read_csv("/tmp/enduring_elite_FINAL.csv").surname.map(dac))

# (1) Lineage homogamy: P(mother elite | father elite) vs father-not-elite
d=pd.read_csv("data/processed/cong_df.csv")
d["pe"]=d.Pat.map(lambda s:dac(s) in E285); d["me"]=d.Mat.map(lambda s:dac(s) in E285)
homog_e=100*d[d.pe].me.mean(); homog_o=100*d[~d.pe].me.mean()

# BCN bios
recs=[x for x in json.load(open("/tmp/extract_sonnet_corrected.json")) if x.get("fields")]
txt={x["file"]: dac(open(x["file"]).read()) for x in recs}
for x in recs: x["e"]= dac(x.get("pat","")) in E285 or dac(x.get("mat","")) in E285
el=[x for x in recs if x["e"]]; ot=[x for x in recs if not x["e"]]
# (2) Club de la Union
CU=re.compile("CLUB DE LA UNION")
club_e=100*sum(bool(CU.search(txt[x['file']])) for x in el)/len(el)
club_o=100*sum(bool(CU.search(txt[x['file']])) for x in ot)/len(ot)
# (3) Elite private school, 20th c.
def yr(x):
    try: return int(x.get("start") or 0)
    except: return 0
el20=[x for x in el if yr(x)>=1900]; ot20=[x for x in ot if yr(x)>=1900]
school_e=100*sum(x['fields'].get('c_elite_priv_school') for x in el20)/len(el20)
school_o=100*sum(x['fields'].get('c_elite_priv_school') for x in ot20)/len(ot20)

crit=["Lineage homogamy\n(P elite parent)","Club de la Unión\nmembership","Elite private school\n(20th c.)"]
ev=[homog_e,club_e,school_e]; ov=[homog_o,club_o,school_o]
print("VALIDATION FIGURE (elite vs other %):")
for c,e,o in zip(crit,ev,ov): print(f"  {c.splitlines()[0]:26s} {e:5.1f} vs {o:4.1f}  ({e/max(o,.1):.1f}x)")

x=np.arange(len(crit)); w=0.38
plt.rcParams.update({"font.family":"serif","font.size":11})
fig,ax=plt.subplots(figsize=(8,4.6))
ax.bar(x-w/2,ev,w,label="Elite surname",color="#1f3a93",alpha=.9)
ax.bar(x+w/2,ov,w,label="Other surname",color="#E7B800",alpha=.9)
for i,(e,o) in enumerate(zip(ev,ov)):
    ax.text(i-w/2,e+0.7,f"{e:.0f}%",ha="center",fontsize=9)
    ax.text(i+w/2,o+0.7,f"{o:.0f}%",ha="center",fontsize=9)
ax.set_xticks(x); ax.set_xticklabels(crit,fontsize=9.5)
ax.set_ylabel("Share of legislators (%)"); ax.set_ylim(0,max(ev)*1.18)
ax.legend(frameon=False,fontsize=10)
for s in ["top","right"]: ax.spines[s].set_visible(False)
ax.grid(axis="y",alpha=.25); fig.tight_layout()
fig.savefig("figures/figure_validation.png",dpi=150)
fig.savefig("figures/figure_validation.pdf")
print("saved figures/figure_validation.{png,pdf}")
