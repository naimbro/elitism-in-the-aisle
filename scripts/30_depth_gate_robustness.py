"""30 — Referee M4: robustness of the 1925 break and composition trend to a STRICTER
historical persistence-depth gate.

The enduring-elite measure passes a surname through two gates (1874 census attestation +
19c-elite ∩ 2020-SES). The persistence-depth score (`n_sources` in enduring_elite_FINAL.csv)
counts how many independent historical elite sources name each surname. The referee asks
whether the headline pattern — a long composition decline plus a sharp, significant 1925
level break — depends on surnames attested by only a SINGLE source. We re-estimate on the
stricter depth>=2 subset (surnames named by at least two independent sources).

Reuses script 29's HAC-ITS `its_level_shift` and `decade_share` verbatim, same `dac`
normalization. Deterministic -> no seed needed (INV-14).
Inputs : data/processed/{cong_df,enduring_elite_FINAL}.csv (paths anchored on the repo).
Outputs: output/m4_depth_gate.csv; tables/table_depth_gate.tex (published to ../paper/tables
         if that tree exists). The table carries no stars.

R&R 2026 correction (E1): its_level_shift() and decade_share() now use the shared rule in
_measure_helpers (annual_share / annual_share_frame): years with fewer than 5 sitting
legislators are undefined and dropped. Congress did not sit in 1925, so 1925 is now a gap in
the ITS (it was previously coded 0% via elite / max(n, 1)). Decade shares are unaffected
(every year in 1860-69, 1900-09 and 2010-19 has a sitting Congress).
Round 2: repo-anchored paths (no cwd dependence), math-mode minus signs, comprehension (INV-17).
"""
import pandas as pd, numpy as np, unicodedata
import statsmodels.formula.api as smf
from _measure_helpers import annual_share, annual_share_frame, DATA, OUTPUT, TABLES, publish, tex_num

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()

final = pd.read_csv(DATA / "enduring_elite_FINAL.csv")
final["surname"] = final.surname.map(dac)
full298  = set(final.surname)                                   # both criteria (depth >= 1)
depth_ge2 = set(final.surname[final.n_sources >= 2])            # stricter historical gate
print(f"full-298 size: {len(full298)}   depth>=2 size: {len(depth_ge2)}")

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

# ---------- estimate both gates ----------
def gate_row(name, es):
    lv, p = its_level_shift(es)
    return {"spec": name, "n_surnames": len(es),
            "level_shift": round(lv, 2), "hac_p": round(p, 4),
            "share_1860s": round(decade_share(es, 1860, 1869), 1),
            "share_2010s": round(decade_share(es, 2010, 2019), 1),
            "share_1900s": round(decade_share(es, 1900, 1909), 1)}   # ~1900 decade share


rows = [gate_row("full_298", full298), gate_row("depth_ge2", depth_ge2)]
print("\n========== M4: 1925 LEVEL SHIFT + COMPOSITION TREND, both criteria vs depth>=2 ==========")
print("\n".join(f"  {r['spec']:>10} (n={r['n_surnames']}): 1925 break {r['level_shift']:+.2f} pts (HAC p={r['hac_p']:.4f})  "
                f"| 1860s {r['share_1860s']:.1f}%  1900s {r['share_1900s']:.1f}%  2010s {r['share_2010s']:.1f}%"
                for r in rows))

# ---------- save output CSV (INV-22 traceability) ----------
pd.DataFrame(rows)[["spec", "n_surnames", "level_shift", "hac_p", "share_1860s", "share_2010s"]] \
    .to_csv(OUTPUT / "m4_depth_gate.csv", index=False)
print("\nsaved output/m4_depth_gate.csv")

# ---------- bare tabular for the online appendix (INV-13: no float/caption/notes) ----------
lab = {"full_298": "Both criteria (depth $\\geq$ 1)", "depth_ge2": "Stricter historical gate (depth $\\geq$ 2)"}
trow = lambda r: (f"{lab[r['spec']]} & {r['n_surnames']} & {r['share_1860s']:.1f} & "
                  f"{r['share_2010s']:.1f} & {tex_num(r['level_shift'], 1)} \\\\")
tex = ["\\begin{tabular}{lcccc}", "\\toprule",
       "Gate & Surnames & 1860s share & 2010s share & 1925 level shift \\\\", "\\midrule",
       *[trow(r) for r in rows],
       "\\bottomrule", "\\end{tabular}"]
out_tab = TABLES / "table_depth_gate.tex"
out_tab.write_text("\n".join(tex) + "\n", encoding="utf-8")
print(f"saved {out_tab}")
publish(out_tab, "tables")

# ---------- verdict ----------
r2 = rows[1]
decline = r2["share_1860s"] - r2["share_2010s"]
print("\n========== VERDICT ==========")
print(f"Under depth>=2 (n={r2['n_surnames']}): elite share falls {r2['share_1860s']:.1f}% (1860s) -> {r2['share_2010s']:.1f}% (2010s) "
      f"[decline {decline:.1f} pts]; 1925 break {r2['level_shift']:+.2f} pts, HAC p={r2['hac_p']:.4g}.")
print("Long decline + sharp significant 1925 break SURVIVE the depth>=2 gate." if (decline > 0 and r2["level_shift"] < 0 and r2["hac_p"] < 0.05)
      else "Pattern does NOT cleanly survive — inspect numbers.")
