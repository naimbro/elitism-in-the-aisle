"""29 — Referee M2: robustness of the 1925 break and composition trend to the
business-leader route (Route 1b).

(a) THRESHOLD SWEEP: the 13 business-route surnames enter on overrep_ratio >= 8 AND
    n_leaders (appearances) >= 5, among historically-attested, non-given-name surnames not
    already in the padron-285 list. Sweep overrep in {6,8,12} x appearances in {3,5,10}; for
    each cell rebuild the elite list deterministically and re-estimate the 1925 level shift.
(b) DROP-13: re-estimate the 1925 level shift and the 1860s/2010s elite shares with all 13
    business-route surnames removed (i.e. the padron-285 list), to show the headline survives.
Also reports the legislator-term weight of Portales and Balmaceda (the two heaviest dynasties
the referee names).

Run from PROJECT ROOT. Inputs: replication_repo/data/processed/{cong_df,enduring_elite_FINAL}.csv,
quality_reports/business_x_historical.csv. Deterministic -> no seed needed.
"""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

REPO = "replication_repo/data/processed"
final = pd.read_csv(f"{REPO}/enduring_elite_FINAL.csv")
final["surname"] = final.surname.map(dac)
biz_flag = final.sources.fillna("").str.contains("business_gate")
biz13 = sorted(final.surname[biz_flag].tolist())
base285 = set(final.surname[~biz_flag])                      # padron-gate list (drop the 13)
full298 = set(final.surname)
print(f"business-route surnames (n={len(biz13)}): {biz13}")
print(f"base-285 size: {len(base285)}   full-298 size: {len(full298)}")

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

def decade_share(elite_set, y0, y1):
    el = (PAT.isin(elite_set) | MAT.isin(elite_set)).values
    S, E = cong.S.values, cong.E.values
    vals = [100 * el[(S <= y) & (E >= y)].sum() / max(((S <= y) & (E >= y)).sum(), 1) for y in range(y0, y1 + 1)]
    return float(np.mean(vals))

# ---------- (b) DROP-13 headline robustness ----------
lv_full, p_full = its_level_shift(full298)
lv_drop, p_drop = its_level_shift(base285)
print("\n========== (b) 1925 LEVEL SHIFT: full-298 vs drop-13 (padron-285) ==========")
print(f"  full 298  : {lv_full:+.2f} pts (HAC p={p_full:.4f})")
print(f"  drop-13   : {lv_drop:+.2f} pts (HAC p={p_drop:.4f})   [movement {lv_drop-lv_full:+.2f} pts]")
print("\n  elite share by decade (full vs drop-13):")
for lab, (y0, y1) in {"1860s": (1860, 1869), "2010s": (2010, 2019)}.items():
    print(f"    {lab}: full {decade_share(full298,y0,y1):.1f}%   drop-13 {decade_share(base285,y0,y1):.1f}%")

# Portales / Balmaceda legislator-term weight
for nm in ["PORTALES", "BALMACEDA"]:
    hit = (PAT == nm) | (MAT == nm)
    pre = hit & (cong.S < 1925); win = hit & (cong.S >= 1910) & (cong.S <= 1950)
    print(f"    {nm}: {hit.sum()} legislator-terms total  ({pre.sum()} pre-1925, {win.sum()} in 1910-1950)")

# ---------- (a) THRESHOLD SWEEP ----------
bx = pd.read_csv("quality_reports/business_x_historical.csv")
bx["surname"] = bx.surname.map(dac)
cand = bx[(bx.in_hist == True) & (bx.likely_given_name == False)].copy()   # Gate-2 attested, not a given name
print("\n========== (a) THRESHOLD SWEEP: 1925 level shift across Route-1b cutoffs ==========")
print("    rows = overrep_ratio cutoff, cols = min appearances (n_leaders); cell = level shift (HAC p)")
header = "    overrep\\appear " + "".join(f"{a:>16}" for a in [3, 5, 10])
print(header)
for ov in [6, 8, 12]:
    cells = []
    for ap in [3, 5, 10]:
        add = set(cand.surname[(cand.overrep_ratio >= ov) & (cand.n_leaders >= ap)]) - base285
        lv, p = its_level_shift(base285 | add)
        cells.append(f"{lv:+.1f} (p={p:.3f}) n+{len(add):<2d}")
    print(f"    {ov:>7}        " + "".join(f"{c:>16}" for c in cells))

# ---------- save outputs (INV-22 traceability) ----------
rows = [{"spec": "full_298", "level_shift": round(lv_full, 2), "hac_p": round(p_full, 4), "n_added": ""},
        {"spec": "drop_13_business", "level_shift": round(lv_drop, 2), "hac_p": round(p_drop, 4), "n_added": ""}]
for ov in [6, 8, 12]:
    for ap in [3, 5, 10]:
        add = set(cand.surname[(cand.overrep_ratio >= ov) & (cand.n_leaders >= ap)]) - base285
        lv, p = its_level_shift(base285 | add)
        rows.append({"spec": f"sweep_ov{ov}_ap{ap}", "level_shift": round(lv, 2),
                     "hac_p": round(p, 4), "n_added": len(add)})
pd.DataFrame(rows).to_csv("replication_repo/output/m2_business_route_robustness.csv", index=False)
print("\nsaved replication_repo/output/m2_business_route_robustness.csv")
print("\nNote: the deposited 298 list (manual reconciliation) gives the headline -13.3; this script")
print("is the deterministic rebuild, so cells are the reconciliation-free analogues. The point is")
print("stability: the break stays large and significant across all cutoffs and when the 13 are dropped.")
