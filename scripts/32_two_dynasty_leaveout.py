"""32 — Referee SHOULD-2: leave-only-Portales-and-Balmaceda-out robustness of the 1925
level break. Companion to script 29 (business-route robustness).

The referee asks whether the headline 1925 level shift is an artifact of the two heaviest
19c political dynasties the paper names (PORTALES, BALMACEDA). We re-estimate the 1925 level
shift on the FULL-298 list with ONLY those two surnames removed (and a second cell that also
removes BULNES and GARCIA-HUIDOBRO, the next two presidential/dynastic names in the list).

VERDICT CRITERIA (R&R 2026, round 2 — stated honestly):
  * The ORIGINAL criterion was "the break stays below -12 pts in both cells". With the
    submitted series (1925 coded 0%) it held (-12.24, -11.64). After the E1 correction
    (1925 a gap) the headline is -11.01 and the cells are -9.95 and -9.35, so the ORIGINAL
    MAGNITUDE CRITERION NO LONGER HOLDS. It was an absolute threshold tied to the old headline.
  * Reported now, side by side: (i) sign and significance (negative, HAC p < 0.01), and
    (ii) a magnitude criterion RELATIVE to the corrected headline: each cell within 25% of
    the full-298 break (for -11.01: between -8.26 and -13.76).

Reuses script 29/30's HAC-ITS `its_level_shift` verbatim, same `dac` normalization.
Inputs : data/processed/{cong_df,enduring_elite_FINAL}.csv (paths anchored on the repo).
Output : output/m2_two_dynasty_leaveout.csv. Deterministic -> no seed needed (INV-14).

R&R 2026 correction (E1): its_level_shift() uses the shared rule in _measure_helpers
(annual_share_frame): years with fewer than 5 sitting legislators are undefined and dropped.
Congress did not sit in 1925, so 1925 is now a gap in the ITS (it was previously coded 0% via
elite / max(n, 1)).
"""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf
from _measure_helpers import annual_share_frame, DATA, OUTPUT, within_headline

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

final = pd.read_csv(DATA / "enduring_elite_FINAL.csv")
final["surname"] = final.surname.map(dac)
full298 = set(final.surname)

cong = pd.read_csv(DATA / "cong_df.csv")
cong["S"] = pd.to_numeric(cong.Start, errors="coerce")
cong["E"] = pd.to_numeric(cong.End, errors="coerce")
cong = cong.dropna(subset=["S", "E"])
PAT = cong.Pat.map(dac); MAT = cong.Mat.map(dac)

def its_level_shift(elite_set, br=1925, lo=1880, hi=1970):
    el = (PAT.isin(elite_set) | MAT.isin(elite_set)).values
    df = annual_share_frame(el, cong.S.values, cong.E.values, lo, hi)   # < 5 sitting (1925) dropped
    df["t"] = df.year - br; df["post"] = (df.year >= br).astype(int); df["tpost"] = df.t * df.post
    m = smf.ols("elite ~ t + post + tpost", df).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return m.params["post"], m.pvalues["post"]

# ---- specifications ----
two = {dac("PORTALES"), dac("BALMACEDA")}
four = two | {dac("BULNES"), dac("GARCIA-HUIDOBRO")}
for nm in (two | four):
    assert nm in full298, f"{nm} not in full-298 list"

specs = [
    ("full_298", full298, []),
    ("drop_portales_balmaceda", full298 - two, sorted(two)),
    ("drop_four_dynasties", full298 - four, sorted(four)),
]


def spec_row(name, es, dropped):
    lv, p = its_level_shift(es)
    print(f"  {name:>26} (n={len(es)}): 1925 break {lv:+.2f} pts (HAC p={p:.4g})"
          + (f"  dropped {dropped}" if dropped else ""))
    return {"spec": name, "level_shift": round(lv, 2), "hac_p": float(p),
            "n_surnames": len(es), "surnames_dropped": ";".join(dropped)}


print("========== SHOULD-2: leave-only-dynasties-out 1925 level shift ==========")
rows = [spec_row(*sp) for sp in specs]
pd.DataFrame(rows).to_csv(OUTPUT / "m2_two_dynasty_leaveout.csv", index=False)
print("\nsaved output/m2_two_dynasty_leaveout.csv")

head = rows[0]["level_shift"]
cells = rows[1:]
sign_sig = all(r["level_shift"] < 0 and r["hac_p"] < 0.01 for r in cells)
rel = all(within_headline(r["level_shift"], head) for r in cells)
orig = all(r["level_shift"] < -12 for r in cells)
print("\n========== VERDICT ==========")
print(f"Headline (full 298): {head:+.2f}. Dropping ONLY Portales+Balmaceda: {cells[0]['level_shift']:+.2f}; "
      f"dropping four dynasties: {cells[1]['level_shift']:+.2f}.")
print(f"  (i)  sign + significance (negative, HAC p < 0.01) in both cells: {'YES' if sign_sig else 'NO'}")
print(f"  (ii) magnitude within 25% of the headline ({1.25 * head:+.2f} to {0.75 * head:+.2f}) in both cells: "
      f"{'YES' if rel else 'NO'}")
print(f"  original absolute criterion (< -12 in both cells; set against the submitted -13.3): "
      f"{'holds' if orig else 'NO LONGER HOLDS after the E1 correction'}")
