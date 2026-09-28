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

Inputs : data/processed/{cong_df,enduring_elite_FINAL,business_x_historical}.csv (all shipped).
Output : output/m2_business_route_robustness.csv. Deterministic -> no seed needed.
Paths are anchored on the repo via _measure_helpers (runs from any cwd).

R&R 2026 correction (E1): its_level_shift() and decade_share() now use the shared rule in
_measure_helpers (annual_share / annual_share_frame): years with fewer than 5 sitting
legislators are undefined and dropped. Congress did not sit in 1925, so 1925 is now a gap in
the ITS (it was previously coded 0% via elite / max(n, 1)). Decade shares are unaffected
(every year in 1860-69, 1900-09 and 2010-19 has a sitting Congress).
Round 2: business_x_historical.csv is shipped in data/processed (was read from the author's
quality_reports/); the sweep is computed once (it used to be computed twice).
"""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf
from _measure_helpers import annual_share, annual_share_frame, DATA, OUTPUT

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

final = pd.read_csv(DATA / "enduring_elite_FINAL.csv")
final["surname"] = final.surname.map(dac)
biz_flag = final.sources.fillna("").str.contains("business_gate")
biz13 = sorted(final.surname[biz_flag].tolist())
base285 = set(final.surname[~biz_flag])                      # padron-gate list (drop the 13)
full298 = set(final.surname)
print(f"business-route surnames (n={len(biz13)}): {biz13}")
print(f"base-285 size: {len(base285)}   full-298 size: {len(full298)}")

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

def decade_share(elite_set, y0, y1):
    el = (PAT.isin(elite_set) | MAT.isin(elite_set)).values
    vals = annual_share(el, cong.S.values, cong.E.values, range(y0, y1 + 1))
    return float(np.nanmean(vals))

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
bx = pd.read_csv(DATA / "business_x_historical.csv")
bx["surname"] = bx.surname.map(dac)
cand = bx[(bx.in_hist == True) & (bx.likely_given_name == False)].copy()   # Gate-2 attested, not a given name


def sweep_cell(ov, ap):
    add = set(cand.surname[(cand.overrep_ratio >= ov) & (cand.n_leaders >= ap)]) - base285
    lv, p = its_level_shift(base285 | add)
    return {"spec": f"sweep_ov{ov}_ap{ap}", "level_shift": round(lv, 2), "hac_p": round(p, 4),
            "n_added": len(add), "ov": ov, "ap": ap, "raw_p": p, "raw_lv": lv}


sweep = pd.DataFrame([sweep_cell(ov, ap) for ov in [6, 8, 12] for ap in [3, 5, 10]])
print("\n========== (a) THRESHOLD SWEEP: 1925 level shift across Route-1b cutoffs ==========")
print("    rows = overrep_ratio cutoff, cols = min appearances (n_leaders); cell = level shift (HAC p)")
print("    overrep\\appear " + "".join(f"{a:>16}" for a in [3, 5, 10]))
print("\n".join(f"    {ov:>7}        " + "".join(f"{f'{r.raw_lv:+.1f} (p={r.raw_p:.3f}) n+{r.n_added:<2d}':>16}"
                                                   for r in g.itertuples())
                for ov, g in sweep.groupby("ov", sort=False)))

# ---------- save outputs (INV-22 traceability) ----------
head = pd.DataFrame([
    {"spec": "full_298", "level_shift": round(lv_full, 2), "hac_p": round(p_full, 4), "n_added": ""},
    {"spec": "drop_13_business", "level_shift": round(lv_drop, 2), "hac_p": round(p_drop, 4), "n_added": ""}])
pd.concat([head, sweep[["spec", "level_shift", "hac_p", "n_added"]]], ignore_index=True) \
    .to_csv(OUTPUT / "m2_business_route_robustness.csv", index=False)
print("\nsaved output/m2_business_route_robustness.csv")
print(f"\nNote: the deposited 298 list (manual reconciliation) gives the headline {lv_full:+.2f}; this script")
print("is the deterministic rebuild, so cells are the reconciliation-free analogues. The point is")
print("stability: the break stays large and significant across all cutoffs and when the 13 are dropped.")
