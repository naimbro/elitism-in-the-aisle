"""34 — Referee SHOULD-5: SYMMETRIC common-pole biographical markers.

The validation section reports ELITE-pole biographical rates (Club de la Union, elite private
school) as enduring-elite vs. other fold-gaps. The referee asks for the symmetric COMMON-pole
figure: the club / elite-school membership RATES among COMMON-surname legislators, to show they
are low (making the elite-vs-common contrast symmetric, not just an elite-vs-rest artifact).

Method mirrors script 06 EXACTLY (regex 'CLUB DE LA UNION' on the harvested biography text for
the club marker; the JSON field `c_elite_priv_school` for the 20th-c elite-school marker, start
year >= 1900), but partitions legislators into three surname groups (ELITE = enduring-elite list,
COMMON = the script-04/13/20 common-surname set not already elite, OTHER = neither) using the
same Pat/Mat classification used throughout the paper.

Deterministic -> no seed needed (INV-14). Run from PROJECT ROOT.
Inputs: replication_repo/data/processed/enduring_elite_FINAL.csv,
        /tmp/extract_sonnet_corrected.json (+ /tmp/harvest_all/*.txt) — same source as script 06
        (raw scraped biography text, NOT redistributed in the public repo).
"""
import json, re, os, unicodedata
import pandas as pd

BIOS_JSON = "/tmp/extract_sonnet_corrected.json"   # same source as scripts 06 / 24

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

ELITE = set(pd.read_csv("replication_repo/data/processed/enduring_elite_FINAL.csv").surname.map(dac))
COMMON = set(dac(s) for s in (
    'GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ '
    'SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO '
    'TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO '
    'GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS '
    'MOLINA RIVERA GUZMAN SANDOVAL ORTIZ'.split()))

if not os.path.exists(BIOS_JSON):
    raise SystemExit(f"\nBios JSON not found at {BIOS_JSON}. The matched-bios extraction is not "
                     "in the public repo (raw scraped text). Place it there and re-run; no numbers fabricated.")

recs = [x for x in json.load(open(BIOS_JSON)) if x.get("fields")]

# ---- surname-group classification (elite > common > other), as scripts 06/13/20/24 ----
def group(x):
    p, m = dac(x.get("pat", "")), dac(x.get("mat", ""))
    if p in ELITE or m in ELITE:
        return "elite"
    if p in COMMON or m in COMMON:
        return "common"
    return "other"
for x in recs:
    x["g"] = group(x)

# ---- club marker: regex on biography text (script 06's exact method) ----
CU = re.compile("CLUB DE LA UNION")
txt = {x["file"]: dac(open(x["file"]).read()) for x in recs}
for x in recs:
    x["club"] = bool(CU.search(txt[x["file"]]))

def yr(x):
    try:
        return int(x.get("start") or 0)
    except Exception:
        return 0

print("=" * 72)
print("SHOULD-5 — SYMMETRIC COMMON-POLE BIOGRAPHICAL MARKERS")
print("=" * 72)
print(f"\nBios with structured fields: {len(recs)}")
counts = {g: sum(1 for x in recs if x["g"] == g) for g in ["elite", "common", "other"]}
print(f"group sizes: {counts}\n")

rows = []
# ---- (1) Club de la Union, full sample ----
print("Club de la Union membership rate by surname group (all years):")
club_rate = {}
for g in ["elite", "common", "other"]:
    sub = [x for x in recs if x["g"] == g]
    rate = 100 * sum(x["club"] for x in sub) / len(sub)
    club_rate[g] = rate
    print(f"  {g.upper():7s}: n={len(sub):4d}  rate={rate:.1f}%")
    rows.append({"marker": "club_union", "group": g, "n": len(sub), "rate_pct": round(rate, 1)})

# ---- (2) Elite private school, 20th c (start >= 1900); JSON field, script 06's exact method ----
print("\nElite private school (20th c, start>=1900) rate by surname group:")
sch_rate = {}
for g in ["elite", "common", "other"]:
    sub = [x for x in recs if x["g"] == g and yr(x) >= 1900]
    rate = 100 * sum(bool(x["fields"].get("c_elite_priv_school")) for x in sub) / max(len(sub), 1)
    sch_rate[g] = rate
    print(f"  {g.upper():7s}: n={len(sub):4d}  rate={rate:.1f}%")
    rows.append({"marker": "elite_school_20c", "group": g, "n": len(sub), "rate_pct": round(rate, 1)})

# ---- contrast summary (symmetry) ----
print("\n========== SYMMETRY (elite vs common vs other) ==========")
print(f"  Club de la Union:     elite {club_rate['elite']:.1f}%  common {club_rate['common']:.1f}%  "
      f"other {club_rate['other']:.1f}%   (elite/common = {club_rate['elite']/max(club_rate['common'],.1):.1f}x)")
print(f"  Elite school (1900+): elite {sch_rate['elite']:.1f}%  common {sch_rate['common']:.1f}%  "
      f"other {sch_rate['other']:.1f}%   (elite/common = {sch_rate['elite']/max(sch_rate['common'],.1):.1f}x)")
rows.append({"marker": "club_union", "group": "elite_over_common_ratio", "n": "",
             "rate_pct": round(club_rate["elite"] / max(club_rate["common"], .1), 1)})
rows.append({"marker": "elite_school_20c", "group": "elite_over_common_ratio", "n": "",
             "rate_pct": round(sch_rate["elite"] / max(sch_rate["common"], .1), 1)})

pd.DataFrame(rows).to_csv("replication_repo/output/should5_common_pole_validation.csv", index=False)
print("\nsaved replication_repo/output/should5_common_pole_validation.csv")
