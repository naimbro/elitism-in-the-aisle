"""24 — Biography-coverage selection bound (referee robustness, task C3).

Validation Figure 1 fold-gaps (homogamy, Club de la Union, elite school) rest on
3,174 BCN biographies covering ~81% of the legislator roster. This script tests
whether coverage correlates with surname status (which would inflate the gaps).

It computes the biography-coverage RATE separately for ELITE (enduring-elite,
permissive rule), COMMON (the script-04 common set, non-elite) and OTHER
(neither) surname groups, then re-estimates the three Fig-1 fold-gaps with
inverse-coverage weights (each covered legislator reweighted to its full-roster
group composition) to check whether the gaps survive.

Inputs : data/processed/cong_df.csv, data/processed/enduring_elite_FINAL.csv
         BCN bios: v2 corpus (see the R&R header below; v1 /tmp/extract_sonnet_corrected.json is lost)
Outputs: output/bio_coverage_by_group.csv
         tables/table_bio_coverage.tex (bare booktabs tabular; published to ../paper/tables
         if that tree exists), output/bio_foldgaps_reweighted.csv

Paths anchored on the repo (any cwd). Corpus absent -> exit code 3 (SKIP). Deterministic.

NOTE on bios path: the matched-bios extraction is not committed to the public repo (it
contains raw scraped biography text). If it (or any biography text file) is absent, the
script exits with SKIP_CODE rather than fabricating numbers.

R&R 2026 CORPUS SWITCH AND CLUB FIX (errors E7, decision D11):
  * Corpus: the v1 file /tmp/extract_sonnet_corrected.json (3,174 bios) no longer exists.
    The script now reads the persistent v2 re-extraction <RAW_DATA_ROOT>/data/processed/
    bcn_extract_v2.json (3,417 bios) and its texts <RAW_DATA_ROOT>/data/raw/bcn_wayback/,
    the same corpus as scripts 34 / 38.
  * Club fold: the submitted "Club de la Union 2.6x" reweighted fold was computed from the
    LLM `elite_club` field, which covers several elite clubs, not the Club de la Union. The
    Club marker now uses the same regex as scripts 06 / 34 / 38 ("CLUB DE LA UNION" on the
    de-accented biography text), so the reweighted fold measures what its label says.
  * School: v2 has no derived `c_elite_priv_school` field; script 10's PRIV regex is applied
    to `secondary_school` (the rule that produced that field in v1).
  * New output: output/bio_foldgaps_reweighted.csv (unweighted and reweighted fold-gaps).
The v1 outputs are preserved in git tag submitted-RaP-2026-07-08.
"""
import os
import re
import sys
import json
import unicodedata
from pathlib import Path
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _measure_helpers import RAW_DATA_ROOT, DATA, OUTPUT, TABLES, publish, require, skip  # noqa: E402

BIOS_JSON = RAW_DATA_ROOT / "data" / "processed" / "bcn_extract_v2.json"   # v2 corpus (as 34 / 38)
BIOS_TXT = RAW_DATA_ROOT / "data" / "raw" / "bcn_wayback"
CU = re.compile("CLUB DE LA UNION")             # scripts 06 / 34 / 38
# script 10's corrected elite-private-school rule (verbatim regex; identical in 34 / 38)
PRIV = re.compile(r"SAN IGNACIO|SAGRADOS? CORAZ|PADRES FRANCESES|VERBO DIVINO|THE GRANGE|GRANGE SCHOOL|"
                  r"CRAIGHOUSE|SAINT GEORGE|SAN JORGE|SAINT GABRIEL|SAN GABRIEL|VILLA MARIA|MACKAY|"
                  r"SAINT JOHN|LICEO ALEMAN|COLEGIO ALEMAN")


def dac(s):
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()


ELITE = set(dac(s) for s in pd.read_csv(DATA / "enduring_elite_FINAL.csv").surname)
COMMON = set(
    'GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS '
    'RODRIGUEZ SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ '
    'GUTIERREZ FLORES CASTRO TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA '
    'HERRERA VARGAS NUNEZ ALVAREZ CARRASCO GOMEZ BRAVO VERGARA GARCIA TAPIA JARA '
    'ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS MOLINA RIVERA GUZMAN '
    'SANDOVAL ORTIZ'.split()
)

print("=" * 72)
print("TASK C3 — BIOGRAPHY-COVERAGE SELECTION BOUND")
print("=" * 72)

# Non-redistributed corpus absent -> exit with SKIP_CODE (3); no numbers fabricated.
require([BIOS_JSON, BIOS_TXT], "BCN biography corpus (v2)")

# ---- Unique legislators and surname group ------------------------------------
d = pd.read_csv(DATA / "cong_df.csv")
u = d.drop_duplicates(subset="Name").copy()  # one row per legislator
pat = u.Pat.map(dac)
mat = u.Mat.map(dac)
ie = (pat.isin(ELITE) | mat.isin(ELITE)).values
ic = ((~ie) & (pat.isin(COMMON) | mat.isin(COMMON))).values
io = ~(ie | ic)
group = np.where(ie, "elite", np.where(ic, "common", "other"))
u["group"] = group

# ---- Coverage flag (exact match on normalized full Name, as in roster<->bios) -
with open(BIOS_JSON, encoding="utf-8") as fh:
    recs = json.load(fh)
n_missing = sum(not (BIOS_TXT / x["file"]).exists() for x in recs)
if n_missing:
    skip(f"{n_missing} of {len(recs)} biography text files missing under {BIOS_TXT}")
for x in recs:   # markers under the published coding rules (see header)
    f = x.get("fields") or {}
    f["c_elite_priv_school"] = bool(PRIV.search(dac(f.get("secondary_school") or "")))
    f["club_union_regex"] = bool(CU.search(dac((BIOS_TXT / x["file"]).read_text(encoding="utf-8"))))
    x["fields"] = f
covered_names = set(dac(x["name"]) for x in recs)
u["covd"] = u.Name.map(lambda n: dac(n) in covered_names).values

print(f"\nRoster: {len(u)} unique legislators; {len(recs)} matched biographies.")
print(f"Overall coverage: {int(u.covd.sum())} / {len(u)} = {100*u.covd.mean():.1f}%\n")

# ---- (1) Coverage rate by group ----------------------------------------------
rows = []
print("Coverage rate by surname group:")
for lab in ["elite", "common", "other"]:
    g = u[u.group == lab]
    n = len(g)
    cov = int(g.covd.sum())
    rate = 100 * g.covd.mean()
    print(f"  {lab.upper():7s}: n={n:4d}  covered={cov:4d}  rate={rate:.1f}%")
    rows.append({"group": lab, "n": n, "covered": cov, "coverage_pct": rate})
overall = {"group": "overall", "n": len(u), "covered": int(u.covd.sum()),
           "coverage_pct": 100 * u.covd.mean()}
print(f"  {'OVERALL':7s}: n={overall['n']:4d}  covered={overall['covered']:4d}  rate={overall['coverage_pct']:.1f}%")
rows.append(overall)
cov_df = pd.DataFrame(rows)

# ---- (2) Direction and size of imbalance -------------------------------------
r_elite = cov_df.loc[cov_df.group == "elite", "coverage_pct"].iloc[0]
r_common = cov_df.loc[cov_df.group == "common", "coverage_pct"].iloc[0]
r_other = cov_df.loc[cov_df.group == "other", "coverage_pct"].iloc[0]
print("\n(2) Imbalance:")
print(f"  elite minus common = {r_elite - r_common:+.1f} pp")
print(f"  elite minus other  = {r_elite - r_other:+.1f} pp")
print(f"  elite minus overall= {r_elite - overall['coverage_pct']:+.1f} pp")
if abs(r_elite - overall["coverage_pct"]) < 2:
    print("  -> Coverage is essentially balanced across groups (<2 pp); selection on")
    print("     surname status is negligible, so the Fig-1 gaps cannot be a coverage artifact.")

# ---- (3) Reweighted fold-gaps (inverse-coverage weights) ---------------------
# Map each bio record to a roster group via the same normalized-Name match.
name2group = dict(zip(u.Name.map(dac), u.group))
for x in recs:
    x["g"] = name2group.get(dac(x["name"]), "other")
    x["e285"] = dac(x.get("pat", "")) in ELITE or dac(x.get("mat", "")) in ELITE

# Inverse-coverage weight per legislator = (full-roster group size) / (covered in group).
# This reweights the covered sample back to the full-roster group composition.
cov_n = {lab: int((u[u.group == lab]).covd.sum()) for lab in ["elite", "common", "other"]}
full_n = {lab: int((u.group == lab).sum()) for lab in ["elite", "common", "other"]}
w = {lab: (full_n[lab] / cov_n[lab] if cov_n[lab] > 0 else 0.0) for lab in cov_n}
print("\n(3) Inverse-coverage weights (full/covered) by group:")
for lab in ["elite", "common", "other"]:
    print(f"  {lab}: {full_n[lab]}/{cov_n[lab]} = {w[lab]:.4f}")


def wmean(records, value_fn):
    num = 0.0
    den = 0.0
    for x in records:
        wt = w[x["g"]]
        v = value_fn(x)
        if v is None:
            continue
        num += wt * float(v)
        den += wt
    return 100 * num / den if den > 0 else float("nan")


def umean(records, value_fn):
    vals = [float(value_fn(x)) for x in records if value_fn(x) is not None]
    return 100 * np.mean(vals) if vals else float("nan")


# Marker availability check on fields.
fk = set()
for x in recs[:200]:
    fk |= set(x.get("fields", {}).keys())
have_school = "c_elite_priv_school" in fk
have_club = "club_union_regex" in fk
have_spouse = "spouse_surnames" in fk
print(f"\nMarker fields available: club={have_club} school={have_school} spouse(homogamy)={have_spouse}")

el = [x for x in recs if x["e285"]]
ot = [x for x in recs if not x["e285"]]


def yr(x):
    try:
        return int(x.get("start") or 0)
    except Exception:
        return 0


print("\nFold-gaps (elite-285 vs other): unweighted vs inverse-coverage reweighted")
gap_rows = []

# Homogamy: spouse surname matches an enduring-elite surname.
if have_spouse:
    def spouse_elite(x):
        sp = x.get("fields", {}).get("spouse_surnames") or []
        toks = []
        for s in sp:
            toks += [dac(t) for t in str(s).split()]
        return 1 if any(t in ELITE for t in toks) else 0
    eu = umean(el, spouse_elite); ou = umean(ot, spouse_elite)
    ew = wmean(el, spouse_elite); ow = wmean(ot, spouse_elite)
    print(f"  Homogamy (elite spouse): unwt {eu:.1f}% vs {ou:.1f}% ({eu/max(ou,.1):.1f}x) | "
          f"reweighted {ew:.1f}% vs {ow:.1f}% ({ew/max(ow,.1):.1f}x)")
    gap_rows.append(("homogamy", eu, ou, ew, ow))
else:
    print("  Homogamy: spouse_surnames field unavailable -- skipped.")

# Club de la Union.
if have_club:
    def club(x):
        return 1 if x.get("fields", {}).get("club_union_regex") else 0   # regex, not LLM elite_club
    eu = umean(el, club); ou = umean(ot, club)
    ew = wmean(el, club); ow = wmean(ot, club)
    print(f"  Club de la Union:        unwt {eu:.1f}% vs {ou:.1f}% ({eu/max(ou,.1):.1f}x) | "
          f"reweighted {ew:.1f}% vs {ow:.1f}% ({ew/max(ow,.1):.1f}x)")
    gap_rows.append(("club_union", eu, ou, ew, ow))
else:
    print("  Club de la Union: elite_club field unavailable -- skipped.")

# Elite private school, 20th c (start >= 1900).
if have_school:
    el20 = [x for x in el if yr(x) >= 1900]
    ot20 = [x for x in ot if yr(x) >= 1900]

    def school(x):
        return 1 if x.get("fields", {}).get("c_elite_priv_school") else 0
    eu = umean(el20, school); ou = umean(ot20, school)
    ew = wmean(el20, school); ow = wmean(ot20, school)
    print(f"  Elite school (1900+):    unwt {eu:.1f}% vs {ou:.1f}% ({eu/max(ou,.1):.1f}x) | "
          f"reweighted {ew:.1f}% vs {ow:.1f}% ({ew/max(ow,.1):.1f}x)")
    gap_rows.append(("elite_school_20c", eu, ou, ew, ow))
else:
    print("  Elite school: c_elite_priv_school field unavailable -- skipped.")

fg = pd.DataFrame(gap_rows, columns=["marker", "elite_unwt_pct", "rest_unwt_pct",
                                     "elite_reweighted_pct", "rest_reweighted_pct"])
fg["fold_unwt"] = fg.elite_unwt_pct / fg.rest_unwt_pct
fg["fold_reweighted"] = fg.elite_reweighted_pct / fg.rest_reweighted_pct
fg["n_bios"] = len(recs)

# Survival verdict, computed rather than asserted: each gap keeps its sign (fold > 1) and the
# reweighted fold is within 10% of the unweighted one.
fg["survives"] = (fg.fold_unwt > 1) & (fg.fold_reweighted > 1) & \
    ((fg.fold_reweighted / fg.fold_unwt - 1).abs() <= 0.10)
print("\nSurvival verdict (fold > 1 both ways; reweighted within 10% of unweighted):")
print("\n".join(f"  {r.marker}: {r.fold_unwt:.2f}x -> {r.fold_reweighted:.2f}x  "
                f"{'survives' if r.survives else 'DOES NOT SURVIVE'}" for r in fg.itertuples()))
print("  -> all gaps survive reweighting; not a coverage-selection artifact." if fg.survives.all()
      else "  -> at least one gap does NOT survive reweighting -- inspect.")

# ---- Save CSV ----------------------------------------------------------------
cov_df.to_csv(OUTPUT / "bio_coverage_by_group.csv", index=False)
print("\nsaved output/bio_coverage_by_group.csv")
fg.to_csv(OUTPUT / "bio_foldgaps_reweighted.csv", index=False)
print("saved output/bio_foldgaps_reweighted.csv")
print(fg.round(3).to_string(index=False))

# ---- Bare LaTeX tabular ------------------------------------------------------
label_map = {"elite": "Elite", "common": "Common", "other": "Other", "overall": "Overall"}
body = [(r"\midrule" + "\n" if r["group"] == "overall" else "")
        + f"{label_map[r['group']]} & {int(r['n'])} & {int(r['covered'])} & {r['coverage_pct']:.1f} \\\\"
        for _, r in cov_df.iterrows()]
lines = [r"\begin{tabular}{lccc}", r"\toprule", r"Surname group & $N$ & Covered & Coverage (\%) \\",
         r"\midrule", *body, r"\bottomrule", r"\end{tabular}"]
tex = "\n".join(lines) + "\n"
out_tab = TABLES / "table_bio_coverage.tex"
out_tab.write_text(tex, encoding="utf-8")
print(f"saved {out_tab}")
publish(out_tab, "tables")
print("\n" + tex)
