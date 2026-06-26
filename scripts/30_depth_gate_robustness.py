"""30 — Referee M4: robustness of the 1925 break and composition trend to a STRICTER
historical persistence-depth gate.

The enduring-elite measure passes a surname through two gates (1874 census attestation +
19c-elite ∩ 2020-SES). The persistence-depth score (`n_sources` in enduring_elite_FINAL.csv)
counts how many independent historical elite sources name each surname. The referee asks
whether the headline pattern — a long composition decline plus a sharp, significant 1925
level break — depends on surnames attested by only a SINGLE source. We re-estimate on the
stricter depth>=2 subset (surnames named by at least two independent sources).

Reuses script 29's HAC-ITS `its_level_shift` and `decade_share` verbatim, same `dac`
normalization, same processed-data path. Deterministic -> no seed needed (INV-14).
Run from PROJECT ROOT. Inputs: replication_repo/data/processed/{cong_df,enduring_elite_FINAL}.csv.
"""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

REPO = "replication_repo/data/processed"
final = pd.read_csv(f"{REPO}/enduring_elite_FINAL.csv")
final["surname"] = final.surname.map(dac)
full298  = set(final.surname)                                   # both criteria (depth >= 1)
depth_ge2 = set(final.surname[final.n_sources >= 2])            # stricter historical gate
print(f"full-298 size: {len(full298)}   depth>=2 size: {len(depth_ge2)}")

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

# ---------- estimate both gates ----------
specs = {"full_298": (full298, 298), "depth_ge2": (depth_ge2, 102)}
rows = []
for name, (es, n) in specs.items():
    lv, p = its_level_shift(es)
    s60 = decade_share(es, 1860, 1869)
    s10 = decade_share(es, 2010, 2019)
    s1900 = decade_share(es, 1900, 1909)                       # ~1900 decade share (over-rep numerator proxy)
    rows.append({"spec": name, "n_surnames": n,
                 "level_shift": round(lv, 2), "hac_p": round(p, 4),
                 "share_1860s": round(s60, 1), "share_2010s": round(s10, 1),
                 "share_1900s": round(s1900, 1)})

print("\n========== M4: 1925 LEVEL SHIFT + COMPOSITION TREND, both criteria vs depth>=2 ==========")
for r in rows:
    print(f"  {r['spec']:>10} (n={r['n_surnames']}): 1925 break {r['level_shift']:+.2f} pts (HAC p={r['hac_p']:.4f})  "
          f"| 1860s {r['share_1860s']:.1f}%  1900s {r['share_1900s']:.1f}%  2010s {r['share_2010s']:.1f}%")

# ---------- save output CSV (INV-22 traceability) ----------
pd.DataFrame(rows)[["spec", "n_surnames", "level_shift", "hac_p", "share_1860s", "share_2010s"]] \
    .to_csv("replication_repo/output/m4_depth_gate.csv", index=False)
print("\nsaved replication_repo/output/m4_depth_gate.csv")

# ---------- bare tabular for the online appendix (INV-13: no float/caption/notes) ----------
lab = {"full_298": "Both criteria (depth $\\geq$ 1)", "depth_ge2": "Stricter historical gate (depth $\\geq$ 2)"}
trow = lambda r: (f"{lab[r['spec']]} & {r['n_surnames']} & {r['share_1860s']:.1f} & "
                  f"{r['share_2010s']:.1f} & {r['level_shift']:+.1f} \\\\")
tex = ["\\begin{tabular}{lcccc}", "\\toprule",
       "Gate & Surnames & 1860s share & 2010s share & 1925 level shift \\\\", "\\midrule",
       trow(rows[0]), trow(rows[1]),
       "\\bottomrule", "\\end{tabular}"]
with open("paper/tables/table_depth_gate.tex", "w") as fh:
    fh.write("\n".join(tex) + "\n")
print("saved paper/tables/table_depth_gate.tex")

# ---------- verdict ----------
r2 = rows[1]
decline = r2["share_1860s"] - r2["share_2010s"]
print("\n========== VERDICT ==========")
print(f"Under depth>=2 (n=102): elite share falls {r2['share_1860s']:.1f}% (1860s) -> {r2['share_2010s']:.1f}% (2010s) "
      f"[decline {decline:.1f} pts]; 1925 break {r2['level_shift']:+.2f} pts, HAC p={r2['hac_p']:.4g}.")
print("Long decline + sharp significant 1925 break SURVIVE the depth>=2 gate." if (decline > 0 and r2["level_shift"] < 0 and r2["hac_p"] < 0.05)
      else "Pattern does NOT cleanly survive — inspect numbers.")
