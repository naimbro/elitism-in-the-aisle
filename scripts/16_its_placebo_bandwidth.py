"""16 — N1: 1925 break-year placebo-in-time + estimation-window (bandwidth) sweep.
Extends the ITS logic in 05_its_1925.py.
 (a) Placebo-in-time: re-estimate the level shift with the break placed at each
     candidate year 1900-1950; figure of |level shift| and t-stat by break year.
 (b) Window sweep: re-estimate the 1925 level shift over several estimation windows.
Inputs : data/processed/cong_df.csv, data/processed/enduring_elite_FINAL.csv
Outputs: ../paper/figures/figure_its_placebo.pdf (+ .png)
         ../paper/tables/table_its_robustness.tex  (bare tabular, INV-13)
No stochastic element -> no seed needed (INV-14)."""
import pandas as pd, numpy as np, unicodedata
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import statsmodels.formula.api as smf

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()
ELITE = set(dac(s) for s in pd.read_csv("data/processed/enduring_elite_FINAL.csv").surname)

d = pd.read_csv("data/processed/cong_df.csv")
d["S"] = pd.to_numeric(d.Start, errors="coerce"); d["E"] = pd.to_numeric(d.End, errors="coerce")
d = d.dropna(subset=["S", "E"])
el = (d.Pat.map(dac).isin(ELITE) | d.Mat.map(dac).isin(ELITE)).values
S = d.S.values; E = d.E.values

def yearly_share(y0, y1):
    yrs = np.arange(y0, y1 + 1)
    share = np.array([100 * el[(S <= y) & (E >= y)].sum() / max(((S <= y) & (E >= y)).sum(), 1) for y in yrs])
    return pd.DataFrame({"year": yrs, "elite": share})

def fit_break(df, br):
    df = df.copy()
    df["t"] = df.year - br
    df["post"] = (df.year >= br).astype(int)
    df["tpost"] = df.t * df.post
    m = smf.ols("elite ~ t + post + tpost", df).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
    return m.params["post"], m.bse["post"], m.pvalues["post"], m.tvalues["post"]

# ---------------- (a) placebo-in-time, fixed window 1880-1970 ----------------
base = yearly_share(1880, 1970)
cand = np.arange(1900, 1951)
rows = []
for br in cand:
    shift, se, p, t = fit_break(base, br)
    rows.append({"break": int(br), "shift": shift, "se": se, "p": p, "t": t})
pl = pd.DataFrame(rows)
pl["abs_shift"] = pl["shift"].abs()
pl["abs_t"] = pl["t"].abs()
pl.to_csv("data/processed/its_placebo_byyear.csv", index=False)

shift_1925, se_1925, p_1925, t_1925 = fit_break(base, 1925)
argmax_mag = int(pl.loc[pl.abs_shift.idxmax(), "break"])
argmax_t = int(pl.loc[pl.abs_t.idxmax(), "break"])
print(f"[N1a] 1925 level shift (1880-1970): {shift_1925:+.2f} pts  se={se_1925:.2f}  p={p_1925:.4f}  t={t_1925:+.2f}")
print(f"[N1a] break-year with MAX |shift|: {argmax_mag}  (|shift|={pl.abs_shift.max():.2f})")
print(f"[N1a] break-year with MAX |t|   : {argmax_t}  (|t|={pl.abs_t.max():.2f})")
# local-max check: is 1925 >= its neighbours within +/-5 yrs in |shift|?
win = pl[(pl["break"] >= 1920) & (pl["break"] <= 1930)]
loc = win.loc[win.abs_shift.idxmax(), "break"]
print(f"[N1a] within 1920-1930, max |shift| at {int(loc)} (local-max check)")

# ---------------- (a) figure ----------------
plt.rcParams.update({"font.family": "serif", "font.size": 11})
fig, ax1 = plt.subplots(figsize=(9, 5))
ax1.plot(pl["break"], pl["abs_shift"], color="#1f3a93", lw=2.0, marker="o", ms=3, label="|Level shift| (pts)")
ax1.axvline(1925, ls="--", color="grey", lw=1.1)
ax1.text(1925.6, ax1.get_ylim()[1] * 0.93, "1925", color="grey", fontsize=9)
ax1.set_xlabel("Candidate break year")
ax1.set_ylabel("|Estimated level shift| (percentage points)", color="#1f3a93")
ax1.tick_params(axis="y", labelcolor="#1f3a93")
ax2 = ax1.twinx()
ax2.plot(pl["break"], pl["abs_t"], color="#b03030", lw=1.4, ls=":", marker="s", ms=2.5, label="|t-statistic|")
ax2.set_ylabel("|t-statistic|", color="#b03030")
ax2.tick_params(axis="y", labelcolor="#b03030")
for s in ["top"]:
    ax1.spines[s].set_visible(False); ax2.spines[s].set_visible(False)
ax1.grid(alpha=.25)
fig.tight_layout()
fig.savefig("../paper/figures/figure_its_placebo.pdf")
fig.savefig("../paper/figures/figure_its_placebo.png", dpi=150)

# ---------------- (b) window / bandwidth sweep at 1925 ----------------
windows = [(1900, 1955), (1890, 1960), (1880, 1970)]
wr = []
for y0, y1 in windows:
    df = yearly_share(y0, y1)
    shift, se, p, t = fit_break(df, 1925)
    # placebo local-max within THIS window
    cand_w = np.arange(max(y0 + 5, 1905), min(y1 - 4, 1950) + 1)
    sm = [(c, abs(fit_break(df, c)[0])) for c in cand_w]
    locmax = max(sm, key=lambda z: z[1])[0]
    wr.append({"window": f"{y0}-{y1}", "n": len(df), "shift": shift, "se": se, "p": p, "locmax": int(locmax)})
    print(f"[N1b] window {y0}-{y1}: shift={shift:+.2f} se={se:.2f} p={p:.4f}  placebo-locmax={int(locmax)}")
wd = pd.DataFrame(wr)
wd.to_csv("data/processed/its_window_sweep.csv", index=False)

# ---------------- (b) bare tabular fragment (INV-13) ----------------
def star(p):
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""

lines = []
lines.append("\\begin{tabular}{lccc}")
lines.append("\\toprule")
lines.append(" & 1925 level shift & Std.\\ error & $p$-value \\\\")
lines.append("Estimation window & (pts) & (HAC, 5 lags) & \\\\")
lines.append("\\midrule")
for r in wr:
    lines.append(f"{r['window']} & {r['shift']:+.2f}{star(r['p'])} & ({r['se']:.2f}) & {r['p']:.3f} \\\\")
lines.append("\\bottomrule")
lines.append("\\end{tabular}")
with open("../paper/tables/table_its_robustness.tex", "w") as f:
    f.write("\n".join(lines) + "\n")
print("[N1] wrote ../paper/tables/table_its_robustness.tex")
print("[N1] saved figure_its_placebo.pdf")
