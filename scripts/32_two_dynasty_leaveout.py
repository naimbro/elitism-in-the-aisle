"""32 — Referee SHOULD-2: leave-only-Portales-and-Balmaceda-out robustness of the 1925
level break. Companion to script 29 (business-route robustness).

The referee asks whether the headline -13.3 pt 1925 level shift is an artifact of the two
heaviest 19c political dynasties the paper names (PORTALES, BALMACEDA). We re-estimate the
1925 level shift on the FULL-298 list with ONLY those two surnames removed (and a second cell
that also removes BULNES and GARCIA-HUIDOBRO, the next two presidential/dynastic names that
are in the list). If the break stays comfortably below ~-12 pts, it is not a two-family
artifact.

Reuses script 29/30's HAC-ITS `its_level_shift` verbatim, same `dac` normalization, same
processed-data path. Deterministic -> no seed needed (INV-14).
Run from PROJECT ROOT. Inputs: replication_repo/data/processed/{cong_df,enduring_elite_FINAL}.csv.
"""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

REPO = "replication_repo/data/processed"
final = pd.read_csv(f"{REPO}/enduring_elite_FINAL.csv")
final["surname"] = final.surname.map(dac)
full298 = set(final.surname)

cong = pd.read_csv(f"{REPO}/cong_df.csv")
cong["S"] = pd.to_numeric(cong.Start, errors="coerce")
cong["E"] = pd.to_numeric(cong.End, errors="coerce")
cong = cong.dropna(subset=["S", "E"])
PAT = cong.Pat.map(dac); MAT = cong.Mat.map(dac)

def its_level_shift(elite_set, br=1925, lo=1880, hi=1970):
    el = (PAT.isin(elite_set) | MAT.isin(elite_set)).values
    S, E = cong.S.values, cong.E.values
    yrs = np.arange(lo, hi + 1)
    share = np.array([100 * el[(S <= y) & (E >= y)].sum() / max(((S <= y) & (E >= y)).sum(), 1) for y in yrs])
    df = pd.DataFrame({"year": yrs, "elite": share})
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

rows = []
print("========== SHOULD-2: leave-only-dynasties-out 1925 level shift ==========")
for name, es, dropped in specs:
    lv, p = its_level_shift(es)
    rows.append({"spec": name, "level_shift": round(lv, 2), "hac_p": float(p),
                 "n_surnames": len(es), "surnames_dropped": ";".join(dropped)})
    print(f"  {name:>26} (n={len(es)}): 1925 break {lv:+.2f} pts (HAC p={p:.4g})"
          + (f"  dropped {dropped}" if dropped else ""))

pd.DataFrame(rows).to_csv("replication_repo/output/m2_two_dynasty_leaveout.csv", index=False)
print("\nsaved replication_repo/output/m2_two_dynasty_leaveout.csv")

lv2 = rows[1]["level_shift"]; lv4 = rows[2]["level_shift"]
print("\n========== VERDICT ==========")
print(f"Dropping ONLY Portales+Balmaceda: break {lv2:+.2f} pts; dropping four dynasties: {lv4:+.2f} pts.")
print("Break stays well below -12 pts -> NOT a two-family artifact." if (lv2 < -12 and lv4 < -12)
      else "Break moves above -12 in at least one cell -- inspect numbers.")
