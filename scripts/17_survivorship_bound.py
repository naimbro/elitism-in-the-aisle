"""17 — N2: survivorship lower bound on early elite presence.
The headline measure conditions on enduring to 2020 (the SES gate). This script builds
an UNCONDITIONAL 19th-century elite list = surnames attested in the 19c historical
sources (1874 censo top-quartile landowners + 19c elite-network registers) WITHOUT the
2020 SES gate, re-codes the legislative roster against it, and plots the pre-1920 elite
composition trend alongside the enduring-elite trend. Because the enduring list is a
SUBSET of the unconditional list, the enduring-elite trend is a LOWER bound on early
elite presence.
Inputs : data/processed/cong_df.csv, enduring_elite_FINAL.csv, surname_nse.csv,
         1874 censo, elite-network xlsx (via _measure_helpers).
Outputs: ../paper/figures/figure_survivorship_bound.pdf (+ .png)
         data/processed/survivorship_series.csv
No stochastic element -> no seed needed (INV-14)."""
import pandas as pd, numpy as np, unicodedata
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from _measure_helpers import dac, build_hist, load_ses, build_list

# ---- enduring (published) list ----
ENDUR = set(dac(s) for s in pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname)

# ---- unconditional 19c list (no SES gate) ----
HIST = build_hist()
NSE, NOCC = load_ses()
UNCOND = build_list(HIST, NSE, NOCC, ses_cut=None, min_bearers=30, gate_ses=False)
# the unconditional list should (super)set the enduring list's HIST-recoverable part
print(f"[N2] enduring list: {len(ENDUR)} surnames")
print(f"[N2] unconditional 19c list (HIST, no SES gate, >=30 bearers): {len(UNCOND)} surnames")
print(f"[N2] enduring surnames also in unconditional list: {len(ENDUR & UNCOND)} / {len(ENDUR)}")

# ---- roster ----
d = pd.read_csv("data/processed/cong_df.csv")
d["S"] = pd.to_numeric(d.Start, errors="coerce"); d["E"] = pd.to_numeric(d.End, errors="coerce")
d = d.dropna(subset=["S", "E"])
pat = d.Pat.map(dac); mat = d.Mat.map(dac)
S = d.S.values; E = d.E.values
ie_end = (pat.isin(ENDUR) | mat.isin(ENDUR)).values
ie_unc = (pat.isin(UNCOND) | mat.isin(UNCOND)).values
yrs = np.arange(1830, 2021)


def ser(flag):
    o = []
    for y in yrs:
        m = (S <= y) & (E >= y); n = m.sum()
        o.append(100 * flag[m].sum() / n if n >= 5 else np.nan)
    return pd.Series(o).rolling(5, center=True, min_periods=3).mean()


end = ser(ie_end); unc = ser(ie_unc)


def at(s, y):
    return s.values[np.where(yrs == y)[0][0]]


print("\n[N2] series values (smoothed), enduring vs unconditional, with gap:")
report = []
for y in [1865, 1885, 1905, 1915]:
    e = at(end, y); u = at(unc, y)
    print(f"  {y}s region (yr {y}): enduring {e:.1f}%  unconditional {u:.1f}%  gap {u - e:+.1f} pts")
    report.append({"year": y, "enduring": round(e, 2), "unconditional": round(u, 2), "gap": round(u - e, 2)})
pd.DataFrame({"year": yrs, "enduring": end.values, "unconditional": unc.values}).to_csv(
    "data/processed/survivorship_series.csv", index=False)

# check ordering: unconditional >= enduring in 19c
pre = (yrs >= 1830) & (yrs <= 1920)
viol = np.nansum((unc.values[pre] + 1e-9 < end.values[pre]))
print(f"[N2] pre-1920 years where unconditional < enduring (should be ~0): {int(viol)}")

# ---- figure ----
plt.rcParams.update({"font.size": 11, "font.family": "serif"})
fig, ax = plt.subplots(figsize=(10, 5.2))
ax.plot(yrs, unc, color="#444444", lw=2.3, ls="-", label="Unconditional 19c-elite (no SES gate)")
ax.plot(yrs, end, color="#1f3a93", lw=2.3, ls="--", label="Enduring-elite (headline measure)")
ax.fill_between(yrs, end, unc, where=(unc >= end), color="#1f3a93", alpha=.10)
ax.axvspan(1973, 1990, color="grey", alpha=.10)
ax.axvline(1925, ls=":", color="grey", lw=1.0, alpha=.8); ax.text(1927, 5, "1925", color="grey", fontsize=9)
ax.set_xlabel("Year"); ax.set_ylabel("Elite share of Congress (%)")
ax.set_xlim(1830, 2020); ax.set_ylim(0, max(np.nanmax(unc), np.nanmax(end)) * 1.05)
ax.legend(frameon=False, fontsize=9, loc="upper right")
ax.grid(alpha=.25, lw=.5)
for s in ["top", "right"]:
    ax.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig("../paper/figures/figure_survivorship_bound.pdf")
fig.savefig("../paper/figures/figure_survivorship_bound.png", dpi=150)
print("[N2] saved figure_survivorship_bound.pdf")
