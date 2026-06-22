import os, re, json, unicodedata, collections
import pandas as pd
from pathlib import Path
# Repo root = parent of this scripts/ directory; large raw sources live OUTSIDE the repo.
REPO = Path(__file__).resolve().parents[1]
# RAW_DATA_ROOT: paper project dir (default), env-overridable -- same anchor as
# _measure_helpers.py. DATOS_ROOT is the shared data tree (two levels up) holding the
# large external sources (censo). Set RAW_DATA_ROOT / DATOS_ROOT to override.
RAW_DATA_ROOT = Path(os.environ.get("RAW_DATA_ROOT", REPO.parent))
DATOS_ROOT = Path(os.environ.get("DATOS_ROOT", RAW_DATA_ROOT.parent.parent))
# .env holding ANTHROPIC_API_KEY: prefer the env var if already set; otherwise read it
# from the path in ANTHROPIC_ENV_FILE, defaulting to the author's shared .env. Skip
# silently if absent (e.g. when the key is supplied directly via the environment).
_env_file = Path(os.environ.get(
    "ANTHROPIC_ENV_FILE", RAW_DATA_ROOT.parent / "2026_faction_detection" / ".env"))
if "ANTHROPIC_API_KEY" not in os.environ and _env_file.exists():
    for l in open(_env_file):
        if l.startswith("ANTHROPIC_API_KEY="): os.environ["ANTHROPIC_API_KEY"]=l.split("=",1)[1].strip()
import anthropic
client=anthropic.Anthropic()
def dac(s): return unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper().strip()
PART={"DE","DEL","LA","LAS","LOS","Y","DA","DI","VON","VAN","SAN","SANTA"}
def toks(s):
    return [t for t in re.split(r"[ \-]", dac(s)) if len(t)>=4 and t not in PART]

# ---------- padron gate ----------
ns=pd.read_csv("/tmp/surname_nse.csv"); NSE=dict(zip(ns.surname,ns.mean_nse)); NOCC=dict(zip(ns.surname,ns.n_occ))

# ---------- 1874 censo: large landowners ----------
# 1874 censo agricola (NOT shipped in the repo). Resolved relative to the data tree,
# matching _measure_helpers.py; falls back across the layout candidates.
_censo_rel = Path("censo_agricola") / "1874" / "censo_1874.csv"
_censo_candidates = [DATOS_ROOT / _censo_rel, RAW_DATA_ROOT / _censo_rel]
CENSO = str(next((p for p in _censo_candidates if p.exists()), _censo_candidates[0]))
cz=pd.read_csv(CENSO, encoding="latin-1")
cz["Avaluacion"]=pd.to_numeric(cz["Avaluacion"],errors="coerce")
thr=cz["Avaluacion"].quantile(0.75)
big=cz[cz["Avaluacion"]>=thr]
print(f"censo: {len(cz)} landowners; large (top 25%, avaluo>={thr:.0f}): {len(big)}")
HIST=collections.defaultdict(set)   # surname-token -> set of sources
for col in ["Paterno","Materno"]:
    for v in big[col].dropna():
        for t in toks(v): HIST[t].add("censo1874")

# ---------- LLM-parse the xlsx tabs ----------
# elite-network workbook (NOT shipped in the repo) -- lives under RAW_DATA_ROOT, same as _measure_helpers.py.
xl=str(RAW_DATA_ROOT / "Chile - elite networks.xlsx")
SCHEMA={"type":"object","properties":{"surnames":{"type":"array","items":{"type":"string"}}},"required":["surnames"]}
PROMPT=("Raw text of one tab from a compilation of 19th-century Chilean ELITE families "
"(landowners, merchants, financiers, nobility, shareholders). Extract every FAMILY SURNAME of an "
"elite person/family. RULES: surnames only, never given/first names; keep compound surnames intact "
"(Fernández Concha, Ruiz-Tagle, Toro Zambrano, Santa Cruz); EXCLUDE given names, company/ship names, "
"place names, captions, source citations (e.g. 'Salazar 2015'), nationalities, footnote letters; "
"INCLUDE foreign surnames of the Chilean elite (Edwards, Lyon, Walker, Délano, Gibbs). Return JSON list.")
sheets=pd.read_excel(xl, sheet_name=None, header=None)
for tab,d in sheets.items():
    txt=" | ".join(str(v) for v in d.values.ravel() if str(v)!="nan")[:24000]
    try:
        m=client.messages.create(model="claude-sonnet-4-6", max_tokens=4000,
            tools=[{"name":"rec","description":"record surnames","input_schema":SCHEMA}],
            tool_choice={"type":"tool","name":"rec"},
            messages=[{"role":"user","content":PROMPT+"\n\nTAB '"+tab+"':\n"+txt}])
        sn=next((b.input.get("surnames",[]) for b in m.content if b.type=="tool_use"),[])
    except Exception as e:
        print("  ERR",tab,str(e)[:60]); sn=[]
    for s in sn:
        full=dac(s)
        if len(full)>=4: HIST[full].add(tab)
        for t in toks(s): HIST[t].add(tab)
    print(f"  parsed {tab}: {len(sn)} surnames")

# ---------- apply gates ----------
CUR=set('LARRAIN VIAL UNDURRAGA ERRAZURIZ IZQUIERDO TAGLE ALDUNATE ALCALDE IRARRAZAVAL EDWARDS FONTECILLA COX AMENABAR CLARO HUIDOBRO MORANDE MATTE CANEPA EGUIGUREN ASTABURUAGA MANTEROLA ECHENIQUE BEZANILLA SUBERCASEAUX SWETT ASPILLAGA LLONA TOCORNAL MACKENNA ANINAT ELZO AMUNATEGUI FONTAINE SANFUENTES GANDARILLAS CRUCHAGA COSTABAL TORNERO URMENETA RIO CAMPINO AMOR ECHAURREN MOURE DENEGRI SECO GROSSI OCHAGAVIA ABASOLO GARRIGA OPASO ECHAZARRETA ELGART TELECHEA PATRICKSON CERVERO GUEMES PRIDA HUICI BURKE NIXON ESPIGA DUENAS GLEN BASCUNAN'.split())
T,MIN=65,30
enduring=[]
for s in NSE:
    if NSE[s]>=T and NOCC[s]>=MIN and s in HIST:
        enduring.append((s, round(NSE[s],1), int(NOCC[s]), len(HIST[s]), sorted(HIST[s]), s in CUR))
out=pd.DataFrame(enduring,columns=["surname","mean_nse","n_holders","n_sources","sources","in_cur65"]).sort_values(["n_sources","mean_nse"],ascending=False)
out.to_csv("/tmp/enduring_elite_FINAL.csv",index=False)
ks=set(out.surname)
print(f"\n=== FINAL enduring-elite list: {len(out)} surnames (mean_nse>={T}, n>={MIN}, in historical source) ===")
print(f"  current 65 retained: {len(ks&CUR)}  dropped: {sorted(CUR-ks)}")
print(f"  NEW vs 65: {len(ks-CUR)}")
print(f"  censo1874 contributed surnames: {sum('censo1874' in s for s in [set(r[4]) for r in enduring])}")
print("  top by source-breadth:")
for r in out.head(20).itertuples():
    print(f"    {r.surname:16} nse={r.mean_nse:.0f} n={r.n_holders:6} sources={r.n_sources} {'*65' if r.in_cur65 else ''}")
print("saved -> /tmp/enduring_elite_FINAL.csv")
