import json, re, unicodedata, statistics
def dac(s): return unicodedata.normalize("NFKD",str(s)).encode("ascii","ignore").decode().upper()
recs=json.load(open("/tmp/extract_sonnet.json"))
ELITE=set("""LARRAIN VIAL UNDURRAGA ERRAZURIZ IZQUIERDO TAGLE ALDUNATE ALCALDE IRARRAZAVAL EDWARDS FONTECILLA
COX AMENABAR CLARO HUIDOBRO MORANDE MATTE CANEPA EGUIGUREN ASTABURUAGA MANTEROLA ECHENIQUE BEZANILLA
SUBERCASEAUX SWETT ASPILLAGA LLONA TOCORNAL MACKENNA ANINAT ELZO AMUNATEGUI FONTAINE SANFUENTES GANDARILLAS
CRUCHAGA COSTABAL TORNERO URMENETA RIO CAMPINO AMOR ECHAURREN MOURE DENEGRI SECO GROSSI OCHAGAVIA ABASOLO
GARRIGA OPASO ECHAZARRETA ELGART TELECHEA PATRICKSON CERVERO GUEMES PRIDA HUICI BURKE NIXON ESPIGA DUENAS GLEN BASCUNAN""".split())
# genuine aristocratic private schools (Santiago Catholic/foreign elite)
PRIV=re.compile(r"SAN IGNACIO|SAGRADOS? CORAZ|PADRES FRANCESES|VERBO DIVINO|THE GRANGE|GRANGE SCHOOL|CRAIGHOUSE|SAINT GEORGE|SAN JORGE|SAINT GABRIEL|SAN GABRIEL|VILLA MARIA|MACKAY|SAINT JOHN|LICEO ALEMAN|COLEGIO ALEMAN")
# public / meritocratic — the NON-aristocratic pathway (must NOT count as elite)
PUB=re.compile(r"INSTITUTO NACIONAL|LICEO DE|LICEO FISCAL|INTERNADO NACIONAL|BARROS ARANA|SEMINARIO|ESCUELA NORMAL|LICEO DE HOMBRES|LICEO DE APLICACION|ESCUELA PUBLICA|LICEO FRANCES")

n_flip=0
for x in recs:
    f=x.get("fields")
    if not f: continue
    sch=dac(f.get("secondary_school") or "")
    priv = bool(PRIV.search(sch)) and not (PUB.search(sch) and not PRIV.search(sch))
    # corrected elite-private flag: names a genuine elite private school
    f["c_elite_priv_school"] = bool(PRIV.search(sch))
    if f.get("elite_secondary_school") and not f["c_elite_priv_school"]:
        n_flip += 1
    # corrected ARISTOCRATIC score from grounded, non-surname, non-land markers (0-3)
    f["c_aristo_score"] = (int(bool(f.get("nobiliary_particle")))
                           + int(f["c_elite_priv_school"])
                           + int(bool(f.get("elite_club"))))

print(f"elite_secondary_school=true flipped to NOT-elite-private (Instituto Nacional etc.): {n_flip}")

def means(key):
    el=[x["fields"][key] for x in recs if x.get("fields") and dac(x.get("pat","")) in ELITE and isinstance(x["fields"].get(key),(int,float))]
    ne=[x["fields"][key] for x in recs if x.get("fields") and dac(x.get("pat","")) not in ELITE and isinstance(x["fields"].get(key),(int,float))]
    return statistics.mean(el),len(el),statistics.mean(ne),len(ne)

for key,label in [("independent_elite_score","RAW model score (contaminated)"),
                  ("c_aristo_score","CORRECTED aristocratic score (0-3)")]:
    em,en,nm,nn=means(key)
    print(f"{label}: elite-surname {em:.2f} (n={en}) vs other {nm:.2f} (n={nn})  gap {em-nm:+.2f}")

# corrected elite-private school rate by surname class
def rate(key):
    el=[x["fields"][key] for x in recs if x.get("fields") and dac(x.get("pat","")) in ELITE]
    ne=[x["fields"][key] for x in recs if x.get("fields") and dac(x.get("pat","")) not in ELITE]
    return 100*sum(bool(v) for v in el)/len(el), 100*sum(bool(v) for v in ne)/len(ne)
ep,npr=rate("c_elite_priv_school")
print(f"elite-PRIVATE school rate: elite-surname {ep:.1f}% vs other {npr:.1f}%")
ic_e=[x for x in recs if x.get('fields') and re.search('INSTITUTO NACIONAL',dac(x['fields'].get('secondary_school') or ''))]
print(f"\nInstituto Nacional attendees overall: {len(ic_e)} (a substantive 'meritocratic pathway' signal, now separated from elite-private)")
json.dump(recs, open("/tmp/extract_sonnet_corrected.json","w"), ensure_ascii=False)
print("saved -> /tmp/extract_sonnet_corrected.json")
