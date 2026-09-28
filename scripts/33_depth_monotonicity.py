"""33 — Referee SHOULD-1 / MUST-6: persistence-depth MONOTONICITY panel.

Companion to script 30 (which reports depth>=1 vs depth>=2). The referee wants to see that
the 1925 level break and the long composition decline are STABLE across progressively stricter
historical persistence-depth gates, defeating any cherry-pick worry. We sweep the n_sources
gate at depth >= 1, 2, 3, 4 and report, for each, the 1925 level shift (HAC) plus the 1860s
and 2010s elite shares.

VERDICT CRITERIA (R&R 2026, round 2 — stated honestly):
  * The ORIGINAL criterion was "every break below -8 pts". It ALREADY FAILED at depth >= 4
    with the submitted series (1925 coded 0%): -13.32, -13.76, -9.49, -7.44, and -7.44 is not
    below -8. After the E1 correction (1925 a gap) the breaks are -11.01, -12.18, -8.28, -6.33;
    the criterion still fails at depth >= 4 only.
  * Reported now, side by side: (i) sign and significance (negative, HAC p < 0.05), and
    (ii) a magnitude criterion RELATIVE to the corrected headline: within 25% of the depth>=1
    break (for -11.01: between -8.26 and -13.76). Depth >= 4 (37 surnames) fails (ii):
    the break attenuates as the surname base shrinks.

Reuses script 29/30's `its_level_shift` and `decade_share` verbatim, same `dac` normalization.
Inputs : data/processed/{cong_df,enduring_elite_FINAL}.csv (paths anchored on the repo).
Output : output/m4_depth_monotonicity.csv. Deterministic -> no seed needed (INV-14).

R&R 2026 correction (E1): its_level_shift() and decade_share() now use the shared rule in
_measure_helpers (annual_share / annual_share_frame): years with fewer than 5 sitting
legislators are undefined and dropped. Congress did not sit in 1925, so 1925 is now a gap in
the ITS (it was previously coded 0% via elite / max(n, 1)). Decade shares are unaffected
(every year in 1860-69, 1900-09 and 2010-19 has a sitting Congress).
"""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf
from _measure_helpers import annual_share, annual_share_frame, DATA, OUTPUT, within_headline

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

final = pd.read_csv(DATA / "enduring_elite_FINAL.csv")
final["surname"] = final.surname.map(dac)

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


def depth_row(depth):
    es = set(final.surname[final.n_sources >= depth])
    lv, p = its_level_shift(es)
    s60 = decade_share(es, 1860, 1869)
    s10 = decade_share(es, 2010, 2019)
    print(f"  depth>={depth} (n={len(es):3d}): 1925 break {lv:+.2f} pts (HAC p={p:.4g})  "
          f"| 1860s {s60:.1f}%  2010s {s10:.1f}%")
    return {"depth": depth, "n_surnames": len(es),
            "level_shift": round(lv, 2), "hac_p": float(p),
            "share_1860s": round(s60, 1), "share_2010s": round(s10, 1)}


print("========== SHOULD-1: depth-gate MONOTONICITY panel ==========")
rows = [depth_row(depth) for depth in [1, 2, 3, 4]]
pd.DataFrame(rows).to_csv(OUTPUT / "m4_depth_monotonicity.csv", index=False)
print("\nsaved output/m4_depth_monotonicity.csv")

head = rows[0]["level_shift"]
print("\n========== VERDICT ==========")
print(f"1925 level shift across depth>=1..4: {[r['level_shift'] for r in rows]} (headline {head:+.2f})")
print("  (i)  sign + significance (negative, HAC p < 0.05) at every depth: "
      + ("YES" if all(r["level_shift"] < 0 and r["hac_p"] < 0.05 for r in rows) else "NO"))
print(f"  (ii) magnitude within 25% of the headline ({1.25 * head:+.2f} to {0.75 * head:+.2f}): "
      + ", ".join(f"depth>={r['depth']} {'yes' if within_headline(r['level_shift'], head) else 'NO'}"
                  for r in rows))
fails = [f"depth>={r['depth']}" for r in rows if not r["level_shift"] < -8]
print("  original absolute criterion (every break < -8; set against the submitted -13.3): "
      + ("holds" if not fails else f"DOES NOT HOLD ({', '.join(fails)})"))
