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

Deterministic -> no seed needed (INV-14). Paths are anchored on the repo (round 2); the
biography corpus is located via the RAW_DATA_ROOT env var (default: the repo parent).
If the corpus or any of its text files is absent the script exits with SKIP_CODE (3).
Inputs: replication_repo/data/processed/enduring_elite_FINAL.csv,
        <RAW_DATA_ROOT>/data/processed/bcn_extract_v2.json (+ <RAW_DATA_ROOT>/data/raw/bcn_wayback/*.txt)
        (raw scraped biography text, NOT redistributed in the public repo).

R&R 2026 CORPUS SWITCH (error E7, decision D11). The submitted numbers came from the
2026-06-20 extraction (/tmp/extract_sonnet_corrected.json, 3,174 bios), which no longer
exists. This script now reads the persistent 2026-07-10 re-harvest / re-extraction
(bcn_extract_v2.json, 3,417 bios; produced by scripts 08b / 09c), the same corpus as
script 38. Coding rules are unchanged:
  * Club de la Union = regex "CLUB DE LA UNION" on the de-accented biography text;
  * elite private school = script 10's PRIV regex on the extracted `secondary_school` field
    (in v1 this was stored as the derived field `c_elite_priv_school`; v2 has no derived
    field, so the identical regex is applied here), start year >= 1900.
The output file keeps its name, so script 06c (Figure 1) picks up the v2 rates. The v1
output is preserved in git tag submitted-RaP-2026-07-08.
"""
import json, re, os, sys, unicodedata
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _measure_helpers import RAW_DATA_ROOT, DATA, OUTPUT, require, skip  # noqa: E402

BIOS_JSON = RAW_DATA_ROOT / "data" / "processed" / "bcn_extract_v2.json"   # v2 corpus (as script 38)
BIOS_TXT = RAW_DATA_ROOT / "data" / "raw" / "bcn_wayback"

# script 10's corrected elite-private-school rule (verbatim regex; identical in script 38)
PRIV = re.compile(r"SAN IGNACIO|SAGRADOS? CORAZ|PADRES FRANCESES|VERBO DIVINO|THE GRANGE|GRANGE SCHOOL|"
                  r"CRAIGHOUSE|SAINT GEORGE|SAN JORGE|SAINT GABRIEL|SAN GABRIEL|VILLA MARIA|MACKAY|"
                  r"SAINT JOHN|LICEO ALEMAN|COLEGIO ALEMAN")

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

ELITE = set(pd.read_csv(DATA / "enduring_elite_FINAL.csv").surname.map(dac))
COMMON = set(dac(s) for s in (
    'GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ '
    'SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO '
    'TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO '
    'GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS '
    'MOLINA RIVERA GUZMAN SANDOVAL ORTIZ'.split()))

require([BIOS_JSON, BIOS_TXT], "BCN biography corpus (v2)")

with open(BIOS_JSON, encoding="utf-8") as fh:
    recs = [x for x in json.load(fh) if x.get("fields")]
n_missing = sum(not (BIOS_TXT / x["file"]).exists() for x in recs)
if n_missing:
    skip(f"{n_missing} of {len(recs)} biography text files missing under {BIOS_TXT}")
for x in recs:   # v2: apply script 10's rule to the extracted school field
    x["fields"]["c_elite_priv_school"] = bool(PRIV.search(dac(x["fields"].get("secondary_school") or "")))

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
txt = {x["file"]: dac((BIOS_TXT / x["file"]).read_text(encoding="utf-8")) for x in recs}
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

GROUPS = ["elite", "common", "other"]


def group_rate(marker, g, sub, flag):
    """Rate row for one marker x group; flag(x) -> bool."""
    k = sum(bool(flag(x)) for x in sub)
    rate = 100 * k / max(len(sub), 1)
    print(f"  {g.upper():7s}: n={len(sub):4d}  rate={rate:.1f}%")
    return {"marker": marker, "group": g, "n": len(sub), "k": k, "rate_pct": round(rate, 1), "_rate": rate}


# ---- (1) Club de la Union, full sample ----
print("Club de la Union membership rate by surname group (all years):")
club = [group_rate("club_union", g, [x for x in recs if x["g"] == g], lambda x: x["club"]) for g in GROUPS]
# ---- (2) Elite private school, 20th c (start >= 1900); script 10 PRIV regex on secondary_school ----
print("\nElite private school (20th c, start>=1900) rate by surname group:")
school = [group_rate("elite_school_20c", g, [x for x in recs if x["g"] == g and yr(x) >= 1900],
                     lambda x: x["fields"].get("c_elite_priv_school")) for g in GROUPS]
club_rate = {r["group"]: r["_rate"] for r in club}
sch_rate = {r["group"]: r["_rate"] for r in school}

# ---- contrast summary (symmetry) ----
print("\n========== SYMMETRY (elite vs common vs other) ==========")
print(f"  Club de la Union:     elite {club_rate['elite']:.1f}%  common {club_rate['common']:.1f}%  "
      f"other {club_rate['other']:.1f}%   (elite/common = {club_rate['elite']/max(club_rate['common'],.1):.1f}x)")
print(f"  Elite school (1900+): elite {sch_rate['elite']:.1f}%  common {sch_rate['common']:.1f}%  "
      f"other {sch_rate['other']:.1f}%   (elite/common = {sch_rate['elite']/max(sch_rate['common'],.1):.1f}x)")
ratios = [{"marker": "club_union", "group": "elite_over_common_ratio", "n": "",
           "rate_pct": round(club_rate["elite"] / max(club_rate["common"], .1), 1)},
          {"marker": "elite_school_20c", "group": "elite_over_common_ratio", "n": "",
           "rate_pct": round(sch_rate["elite"] / max(sch_rate["common"], .1), 1)}]

(pd.DataFrame(club + school + ratios).drop(columns="_rate").astype({"k": "Int64"})
 .to_csv(OUTPUT / "should5_common_pole_validation.csv", index=False))
print("\nsaved output/should5_common_pole_validation.csv")
