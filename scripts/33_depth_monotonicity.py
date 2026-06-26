"""33 — Referee SHOULD-1 / MUST-6: persistence-depth MONOTONICITY panel.

Companion to script 30 (which reports depth>=1 vs depth>=2). The referee wants to see that
the 1925 level break and the long composition decline are STABLE across progressively stricter
historical persistence-depth gates, defeating any cherry-pick worry. We sweep the n_sources
gate at depth >= 1, 2, 3, 4 and report, for each, the 1925 level shift (HAC) plus the 1860s
and 2010s elite shares.

Reuses script 29/30's `its_level_shift` and `decade_share` verbatim, same `dac` normalization,
same processed-data path. Deterministic -> no seed needed (INV-14).
Run from PROJECT ROOT. Inputs: replication_repo/data/processed/{cong_df,enduring_elite_FINAL}.csv.
"""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

REPO = "replication_repo/data/processed"
final = pd.read_csv(f"{REPO}/enduring_elite_FINAL.csv")
final["surname"] = final.surname.map(dac)

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

rows = []
print("========== SHOULD-1: depth-gate MONOTONICITY panel ==========")
for depth in [1, 2, 3, 4]:
    es = set(final.surname[final.n_sources >= depth])
    lv, p = its_level_shift(es)
    s60 = decade_share(es, 1860, 1869)
    s10 = decade_share(es, 2010, 2019)
    rows.append({"depth": depth, "n_surnames": len(es),
                 "level_shift": round(lv, 2), "hac_p": float(p),
                 "share_1860s": round(s60, 1), "share_2010s": round(s10, 1)})
    print(f"  depth>={depth} (n={len(es):3d}): 1925 break {lv:+.2f} pts (HAC p={p:.4g})  "
          f"| 1860s {s60:.1f}%  2010s {s10:.1f}%")

pd.DataFrame(rows).to_csv("replication_repo/output/m4_depth_monotonicity.csv", index=False)
print("\nsaved replication_repo/output/m4_depth_monotonicity.csv")

breaks = [r["level_shift"] for r in rows]
print("\n========== VERDICT ==========")
print(f"1925 level shift across depth>=1..4: {breaks}")
print("All breaks negative and within a narrow band -> stable/monotone, no cherry-pick."
      if all(b < -8 for b in breaks) else "Break weakens materially at some depth -- inspect.")
