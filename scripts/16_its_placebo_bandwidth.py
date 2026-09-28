"""16 — N1: 1925 break-year placebo-in-time + estimation-window (bandwidth) sweep.
Extends the ITS logic in 05_its_1925.py.
 (a) Placebo-in-time: re-estimate the level shift with the break placed at each
     candidate year 1900-1950; figure of |level shift| and t-stat by break year.
 (b) Window sweep: re-estimate the 1925 level shift over several estimation windows.
Inputs : data/processed/cong_df.csv, data/processed/enduring_elite_FINAL.csv
Outputs: figures/figure_its_placebo.pdf (+ .png), tables/table_its_robustness.tex (bare
         tabular, INV-13); both published to ../paper/{figures,tables} if that tree exists.
No stochastic element -> no seed needed (INV-14).
Round 2 (R&R 2026): repo-anchored paths; p-values below 0.001 print as $<$0.001; math-mode
minus signs; loops replaced by comprehensions (INV-17).

R&R 2026 correction (E1): yearly_share() now uses the shared rule in _measure_helpers
(annual_share_frame): years with fewer than 5 sitting legislators are undefined and dropped.
Congress did not sit in 1925, so 1925 is a gap (previously coded 0% via elite / max(n, 1)).
With 1925 missing, breaks placed at 1925 and 1926 share the same post indicator, so the
placebo profile cannot distinguish them; the corrected profile is flat over ~1918-1927.
Also saves the placebo summary (argmax, local maxima) to data/processed/its_placebo_summary.csv."""
import pandas as pd, numpy as np, unicodedata
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import statsmodels.formula.api as smf
from _measure_helpers import (annual_share_frame, DATA, FIGURES, TABLES, publish, star,
                              tex_num, tex_p)

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()
ELITE = set(dac(s) for s in pd.read_csv(DATA / "enduring_elite_FINAL.csv").surname)

d = pd.read_csv(DATA / "cong_df.csv")
d["S"] = pd.to_numeric(d.Start, errors="coerce"); d["E"] = pd.to_numeric(d.End, errors="coerce")
d = d.dropna(subset=["S", "E"])
el = (d.Pat.map(dac).isin(ELITE) | d.Mat.map(dac).isin(ELITE)).values
S = d.S.values; E = d.E.values

def yearly_share(y0, y1):
    """Annual elite share y0..y1; years with < 5 sitting (1925) dropped (shared rule)."""
    return annual_share_frame(el, S, E, y0, y1)

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
pl = pd.DataFrame([fit_break(base, br) for br in cand], columns=["shift", "se", "p", "t"])
pl.insert(0, "break", cand.astype(int))
pl["abs_shift"] = pl["shift"].abs()
pl["abs_t"] = pl["t"].abs()
pl.to_csv(DATA / "its_placebo_byyear.csv", index=False)

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
near = pl[pl.abs_shift >= pl.abs_shift.max() - 0.5]["break"].tolist()
flat = pl[(pl["break"] >= 1918) & (pl["break"] <= 1927)]["shift"]
print(f"[N1a] years within 0.5 pt of max |shift|: {near}")
print(f"[N1a] level shift range over break years 1918-1927: {flat.max():+.2f} to {flat.min():+.2f}")
pd.DataFrame([{"shift_1925": shift_1925, "se_1925": se_1925, "p_1925": p_1925,
               "argmax_abs_shift": argmax_mag, "max_abs_shift": pl.abs_shift.max(),
               "argmax_abs_t": argmax_t, "max_abs_t": pl.abs_t.max(),
               "locmax_1920_1930": int(loc), "n_within_0p5_of_max": len(near),
               "years_within_0p5_of_max": ";".join(map(str, near)),
               "shift_min_1918_1927": flat.min(), "shift_max_1918_1927": flat.max()}]
             ).to_csv(DATA / "its_placebo_summary.csv", index=False)

# ---------------- (a) figure ----------------
plt.rcParams.update({"font.family": "serif", "font.size": 11})
fig, ax1 = plt.subplots(figsize=(9, 5))
ax1.plot(pl["break"], pl["abs_shift"], color="#1f3a93", lw=2.0, marker="o", ms=3, label="|Level shift| (pts)")
ax1.axvline(1925, ls="--", color="grey", lw=1.1)
ax1.text(1925.6, ax1.get_ylim()[1] * 0.03, "1925", color="grey", fontsize=9)  # bottom: the profile is flat at the top near 1925
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
for ext, kw in [("pdf", {}), ("png", {"dpi": 150})]:
    fig.savefig(FIGURES / f"figure_its_placebo.{ext}", **kw)
    publish(FIGURES / f"figure_its_placebo.{ext}", "figures")

# ---------------- (b) window / bandwidth sweep at 1925 ----------------
windows = [(1900, 1955), (1890, 1960), (1880, 1970)]


def window_row(y0, y1):
    """1925 shift in one window + the placebo local max within that window."""
    df = yearly_share(y0, y1)
    shift, se, p, t = fit_break(df, 1925)
    cand_w = np.arange(max(y0 + 5, 1905), min(y1 - 4, 1950) + 1)
    locmax = int(cand_w[np.argmax([abs(fit_break(df, c)[0]) for c in cand_w])])
    print(f"[N1b] window {y0}-{y1}: shift={shift:+.2f} se={se:.2f} p={p:.4f}  placebo-locmax={locmax}")
    return {"window": f"{y0}-{y1}", "n": len(df), "shift": shift, "se": se, "p": p, "locmax": locmax}


wd = pd.DataFrame([window_row(y0, y1) for y0, y1 in windows])
wd.to_csv(DATA / "its_window_sweep.csv", index=False)

# ---------------- (b) bare tabular fragment (INV-13) ----------------
body = [f"{r.window} & {tex_num(r.shift, 2, star(r.p))} & ({r.se:.2f}) & {tex_p(r.p)} \\\\"
        for r in wd.itertuples()]
lines = ["\\begin{tabular}{lccc}", "\\toprule",
         " & 1925 level shift & Std.\\ error & $p$-value \\\\",
         "Estimation window & (pts) & (HAC, 5 lags) & \\\\",
         "\\midrule", *body, "\\bottomrule", "\\end{tabular}"]
out_tab = TABLES / "table_its_robustness.tex"
out_tab.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"[N1] wrote {out_tab}")
publish(out_tab, "tables")
