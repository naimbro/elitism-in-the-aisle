"""38 -- R&R 2026 item A2 (Referee 2, R2.1): validation of the surname measure BY PERIOD.

Referee 2: "all validation is cross sectional ... could you validate over time showing it's not
just a similar time trend for everything due to measurement? Maybe you can run some validation
tests by period?"

Round 2 (after coder-critic 61/100). Sections:
  0. Roster + parse diagnostics (two-token names stored as Pat = given name, Mat = surname).
  1. Biographical markers by era (Club de la Union; elite private school) for the three surname
     groups; first-entry and mid-career eras; Club founding-date and school-recording
     sensitivities; spouse-homogamy decomposition; Instituto Nacional diagnostic; LR tests of
     group x era with convergence logging (tests with zero cells are dropped, not forced).
  1b. v1 -> v2 crosswalk: every published number that came from the lost v1 biography corpus,
     recomputed on the v2 corpus (script 24 definitions reproduced).
  2. Senate vs Chamber by era and decade (+ post-1990 without designated/life senators;
     + dropping mis-parsed rows).
  3. Party blocs by era (12b mapping + documented extension), with legislator-cluster bootstrap
     CIs for shares, gaps and ratios; 1990-2020 coalition coding; bounds for unassigned terms.
  4. Population reference by birth decade; roster surname missingness.
  5. Homogamy by era (legislator level first; script-06 term rows second; spouse version).
  6. Genealogical-network centrality by entry cohort (network pinned to a commit).
  7. Construction placebos (R2's "trend due to measurement"), round 3: 1:1 matched lists WITHOUT
     replacement (Hungarian) -- SES-only (no 19th-c attestation; matched on 2020 SES + bearers, and
     a variant also matched on 1885-1904 population presence) and history-only (19th-c attested,
     SES < 65; bearer-matched); three gate definitions (full, 1874 census only, workbook without the
     political office-holder sheets); Congress shares with legislator-cluster CIs and draw ranges;
     population denominators from the person-level Registro Civil (script 03 logic, reproduced
     exactly) -> over-representation ratios for entrants from 1930.

Coding rules reused EXACTLY from the published validation:
  * ELITE = Pat or Mat in enduring_elite_FINAL.csv; COMMON = Pat or Mat in the 50-surname list
    and not elite; OTHER = neither (scripts 04 / 24 / 34).
  * Club de la Union = regex "CLUB DE LA UNION" on the de-accented biography text (06 / 34).
  * elite private school = script 10's PRIV regex on `secondary_school` (c_elite_priv_school).
  * homogamy = P(Mat elite | Pat elite) vs P(Mat elite | Pat not elite) (06).

DATA NOTE. The published marker numbers came from the 2026-06-20 extraction
(/tmp/extract_sonnet_corrected.json, 3,174 bios), which no longer exists. This script uses the
persistent 2026-07-10 re-harvest + re-extraction (scripts 08b / 09c; different model and prompt,
so it is a re-measurement, not a copy): <RAW_DATA_ROOT>/data/processed/bcn_extract_v2.json and
<RAW_DATA_ROOT>/data/raw/bcn_wayback/*.txt (3,417 bios, not redistributed).

Inputs  : data/processed/{cong_df.csv, enduring_elite_FINAL.csv, pop_prevalence_by_year.csv,
          surname_nse.csv}; biography corpus above; genealogical network (pinned commit + sha256);
          1874 censo + elite-network workbook (paths from _measure_helpers); Registro Civil
          <DATOS_ROOT>/Registro Civil/HISTORICO/*.csv (23M rows, not redistributed). Optional env
          A2_RC_CACHE=<file.npz> caches the parsed Registro Civil codes between runs.
Outputs : output/rnr2026/a2_*.csv, output/rnr2026/a2_markers_by_era.tex (bare tabular)
          figures/rnr2026/a2_validation_by_period.{pdf,png}, a2_placebo_series.{pdf,png}
Stochastic elements: centrality bootstrap, legislator-cluster bootstrap, random placebo draws
-> one generator, seeded once below (INV-14).
Run with python3 from anywhere; paths resolve from this file's location (INV-16).
"""
# ---- packages (INV-15) --------------------------------------------------------------------
import hashlib
import io
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.request
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
import statsmodels.formula.api as smf
from statsmodels.tools.sm_exceptions import PerfectSeparationError
from scipy import stats
from scipy.optimize import linear_sum_assignment
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _measure_helpers import CENSO, XLSX, build_hist, in_hist, toks, require, skip  # noqa: E402  (deterministic 19th-c gate)

# ---- seed (INV-14) ------------------------------------------------------------------------
RNG = np.random.default_rng(20260926)
N_BOOT = 2000          # centrality + cluster bootstraps
N_PLACEBO = 500        # random matched placebo lists (full gate)
N_PLACEBO_VARIANT = 200  # random matched lists for the circularity gate variants
K_NN = 5               # nearest-neighbour pool per enduring surname

# ---- paths (INV-16) -----------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
RAW_DATA_ROOT = Path(os.environ.get("RAW_DATA_ROOT", REPO.parent))
DATOS_ROOT = Path(os.environ.get("DATOS_ROOT", RAW_DATA_ROOT.parent.parent))   # as script 03
BIOS_JSON = RAW_DATA_ROOT / "data" / "processed" / "bcn_extract_v2.json"
BIOS_TXT = RAW_DATA_ROOT / "data" / "raw" / "bcn_wayback"
NET_SHA = "75b0fd334a058ee967efa58a2b155c9f5be640e3"   # last commit touching the file (2023-08-21)
NET_SHA256 = "efa46173980aa82d7c78383c3a0b0cab66163e4380c3153e9660d6f125674887"   # expected file hash
NET_URL = (f"https://raw.githubusercontent.com/naimbro/naimbro.github.io/{NET_SHA}/data/"
           "naimbro_chilean_political_networks.csv")    # same file as script 07, pinned
OUT = REPO / "output" / "rnr2026"
FIG = REPO / "figures" / "rnr2026"
OUT.mkdir(parents=True, exist_ok=True)
FIG.mkdir(parents=True, exist_ok=True)

# R&R round 2: non-redistributed inputs absent -> exit with SKIP_CODE (3) before any output is
# written. Biographies, 1874 censo + elite workbook, and the Registro Civil files are required
# (the optional A2_RC_CACHE replaces the last); the network download is optional (section 6).
require([BIOS_JSON, BIOS_TXT, CENSO, XLSX], "BCN biographies / 1874 censo / elite workbook")
if not (os.environ.get("A2_RC_CACHE") and Path(os.environ["A2_RC_CACHE"]).exists()):
    require([DATOS_ROOT / "Registro Civil" / "HISTORICO"], "Registro Civil HISTORICO directory")

# ---- constants ----------------------------------------------------------------------------
Z = stats.norm.ppf(0.975)
ERAS = [("1834-1890", 1834, 1890), ("1891-1924", 1891, 1924),
        ("1925-1973", 1925, 1973), ("1990-2020", 1990, 2020)]
ERA_LABELS = [e[0] for e in ERAS]
GROUPS = ["elite", "common", "other"]
GROUP_COL = {"elite": "#1f3a93", "common": "#b03030", "other": "#8a7a2e"}
GROUP_HATCH = {"elite": "", "common": "//", "other": ".."}
BLOC_COL = {"derecha": "#6a3d9a", "centro": "#1b9e77", "izquierda": "#d95f02"}
BLOC_HATCH = {"derecha": "", "centro": "xx", "izquierda": "\\\\"}
BLOC_LAB = {"derecha": "Right", "centro": "Centre", "izquierda": "Left"}

PUBLISHED = {  # manuscript section 3 (Fig. 1) -- v1 corpus
    ("club_union", "elite"): 12.7, ("club_union", "common"): 4.1, ("club_union", "other"): 5.3,
    ("elite_school_20c", "elite"): 41.2, ("elite_school_20c", "common"): 7.6,
    ("elite_school_20c", "other"): 15.4,
}


def dac(s):
    """De-accent + upper + strip (identical to scripts 04/06/24/34)."""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()


def norm_name(s):
    """Roster <-> biography name key (identical to script 08b's norm())."""
    return re.sub(r"\s+", " ", dac(s)).strip()


ELITE = set(pd.read_csv(REPO / "data" / "processed" / "enduring_elite_FINAL.csv").surname.map(dac))
COMMON = set(dac(s) for s in (
    "GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ "
    "SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO "
    "TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO "
    "GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS "
    "MOLINA RIVERA GUZMAN SANDOVAL ORTIZ").split())

# script 10's corrected elite-private-school rule (verbatim regex)
PRIV = re.compile(r"SAN IGNACIO|SAGRADOS? CORAZ|PADRES FRANCESES|VERBO DIVINO|THE GRANGE|GRANGE SCHOOL|"
                  r"CRAIGHOUSE|SAINT GEORGE|SAN JORGE|SAINT GABRIEL|SAN GABRIEL|VILLA MARIA|MACKAY|"
                  r"SAINT JOHN|LICEO ALEMAN|COLEGIO ALEMAN")
INST_NAC = re.compile(r"INSTITUTO NACIONAL")   # public meritocratic route excluded by script 10
CU = re.compile("CLUB DE LA UNION")             # scripts 06 / 34

# ---- party-bloc mapping: scripts 12b / 13 / 14 verbatim ------------------------------------
BLOC_12B = {
    "derecha": ["Partido Conservador", "Partido Conservador Tradicionalista",
                "Partido Conservador Social Cristiano", "Partido Conservador Unido", "Partido Liberal",
                "Partido Liberal Democratico", "Partido Liberal Doctrinario", "Partido Liberal Progresista",
                "Partido Liberal Unido", "Partido Nacional o Monttvarista", "Partido Nacional",
                "Partido Agrario Laborista", "Partido Nacional Socialista",
                "Movimiento Nacional Socialista de Chile"],
    "centro": ["Partido Radical", "Partido Radical de Chile", "Partido Radical Independiente",
               "Partido Democratico de Chile", "Partido Social Republicano", "Falange Nacional",
               "Partido Accion Republicana", "Partido Regionalista", "Partido Agrario"],
    "izquierda": ["Partido Obrero Socialista", "Partido Socialista de Chile", "Partido Socialista Popular",
                  "Partido Comunista de Chile", "Partido Radical Socialista",
                  "Confederacion Republicana de Accion Civica de Obreros y Empleados",
                  "Partido Progresista Nacional", "Union Social Republicana de Asalariados de Chile",
                  "Union Social Republicana de los Asalariados de Chile", "Nueva Accion Publica",
                  "Vanguardia Popular Socialista", "Partido Democratico del Pueblo", "Partido Democrata",
                  "Partido Democratico"],
}
# Extension (NEW, author-chosen, needs sign-off): parties absent from 12b because that mapping
# only covered the 1910-50 speech corpus. The PDC goes to 'centro' because its predecessor
# Falange Nacional is 'centro' in 12b; the PRSD goes to 'centro' because the main Radical
# parties (Partido Radical, Partido Radical de Chile, Partido Radical Independiente) are 'centro'
# in 12b (12b does put the Partido Radical Socialista on the left). Ambiguous small parties
# (PADENA, Partido Liberal 2013-, PRI, Amplitud, Independiente) are left unmapped.
BLOC_EXT = {
    "derecha": ["Partido Union Democrata Independiente", "Partido Renovacion Nacional", "Evopoli",
                "Partido Evolucion Politica", "Partido Union de Centro Centro Progresista",
                "Partido Union de Centro Centro"],
    "centro": ["Partido Democrata Cristiano", "Partido Radical Socialdemocrata"],
    "izquierda": ["Partido por la Democracia", "Revolucion Democratica", "Partido Humanista",
                  "Movimiento de Accion Popular Unitaria", "Movimiento de Accion Popular Unitario",
                  "Izquierda Cristiana", "Izquierda Ciudadana", "Partido Progresista",
                  "Movimiento Amplio Social, MAS", "Partido Amplio de Izquierda Socialista",
                  "Partido Union Socialista Popular", "Independiente de Izquierda",
                  "Accion Popular Independiente", "Partido Ecologista Verde", "Partido Poder",
                  "Federacion Regionalista Verde Social", "Partido Federacion Regionalista Verde Social"],
}
BLOC_12B_MAP = {p: b for b, ps in BLOC_12B.items() for p in ps}
BLOC_MAP = {**BLOC_12B_MAP, **{p: b for b, ps in BLOC_EXT.items() for p in ps}}
BLOC_MAP_PPD_CENTRE = {**BLOC_MAP, "Partido por la Democracia": "centro"}   # sensitivity

# 1990-2020 coalition coding (party-based; the roster has no electoral-pact field, so
# independents elected on coalition lists cannot be assigned -- they are bounded instead).
COAL_RIGHT = ["Partido Union Democrata Independiente", "Partido Renovacion Nacional", "Evopoli",
              "Partido Evolucion Politica", "Partido Union de Centro Centro Progresista",
              "Partido Union de Centro Centro"]               # Alianza / Coalicion / Chile Vamos
COAL_CL = ["Partido Democrata Cristiano", "Partido Socialista de Chile", "Partido por la Democracia",
           "Partido Radical Socialdemocrata", "Partido Radical de Chile",
           "Izquierda Ciudadana", "Partido Amplio de Izquierda Socialista"]  # Concertacion / Nueva Mayoria
PC_NM_FROM = 2014   # Partido Comunista joins the centre-left coalition with Nueva Mayoria (terms from 2014)


# ---- statistics helpers --------------------------------------------------------------------
def wilson(k, n):
    """Wilson score 95% interval for k/n, in percent."""
    if n == 0:
        return np.nan, np.nan
    p = k / n
    den = 1 + Z ** 2 / n
    ctr = (p + Z ** 2 / (2 * n)) / den
    half = Z * np.sqrt(p * (1 - p) / n + Z ** 2 / (4 * n ** 2)) / den
    return 100 * (ctr - half), 100 * (ctr + half)


def risk_ratio(a, n1, b, n2):
    """Rate ratio (a/n1)/(b/n2) with Katz log 95% CI; Haldane +0.5 if a zero cell (flagged)."""
    if n1 == 0 or n2 == 0:
        return np.nan, np.nan, np.nan, False
    zero = (a == 0) or (b == 0)
    if zero:
        a, b, n1, n2 = a + 0.5, b + 0.5, n1 + 1, n2 + 1
    rr = (a / n1) / (b / n2)
    se = np.sqrt(1 / a - 1 / n1 + 1 / b - 1 / n2)
    return rr, rr * np.exp(-Z * se), rr * np.exp(Z * se), zero


def newcombe(a, n1, b, n2):
    """Rate difference (pp) with Newcombe hybrid-score 95% CI."""
    if n1 == 0 or n2 == 0:
        return np.nan, np.nan, np.nan
    p1, p2 = a / n1, b / n2
    l1, u1 = [v / 100 for v in wilson(a, n1)]
    l2, u2 = [v / 100 for v in wilson(b, n2)]
    d = p1 - p2
    return (100 * d, 100 * (d - np.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)),
            100 * (d + np.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)))


def contrast(prefix, a, n1, b, n2):
    """Dict with ratio (Katz) and difference (Newcombe) for a vs b."""
    rr, rl, rh, zc = risk_ratio(a, n1, b, n2)
    dd, dl, dh = newcombe(a, n1, b, n2)
    return {f"{prefix}_ratio": rr, f"{prefix}_ratio_lo": rl, f"{prefix}_ratio_hi": rh,
            f"{prefix}_zero_cell": zc, f"{prefix}_diff_pp": dd, f"{prefix}_diff_lo": dl,
            f"{prefix}_diff_hi": dh}


def era_of(y):
    """Era label for a year (None outside the four eras)."""
    if pd.isna(y):
        return None
    return next((lab for lab, lo, hi in ERAS if lo <= y <= hi), None)


def era_or_pre(y):
    """Era label, with a pre-1834 bucket."""
    return era_of(y) or ("1811-1833" if pd.notna(y) and y < 1834 else None)


def classify(pat, mat):
    """Surname group under the published Pat-OR-Mat rule."""
    p, m = dac(pat), dac(mat)
    if p in ELITE or m in ELITE:
        return "elite"
    if p in COMMON or m in COMMON:
        return "common"
    return "other"


def fit_logit(formula, d):
    """Newton logit; returns (result or None, converged flag, warning text)."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        try:
            res = smf.logit(formula, d).fit(disp=0, method="newton", maxiter=200)
            conv = bool(res.mle_retvals.get("converged", False))
        except (np.linalg.LinAlgError, ValueError, PerfectSeparationError) as ex:
            return None, False, str(ex)[:120]
    return res, conv, "; ".join(sorted({str(x.message)[:80] for x in w}))


def lr_interaction(d, y, grp, era):
    """LR test y ~ grp*era vs grp+era. Dropped (not forced) if any grp x era cell has 0 events or
    0 non-events (quasi-separation); convergence of both fits logged."""
    d = d[[y, grp, era]].dropna().copy()
    d[y] = d[y].astype(int)
    cells = d.groupby([grp, era])[y].agg(["sum", "count"])
    min_ev = int(np.minimum(cells["sum"], cells["count"] - cells["sum"]).min())
    base = {"n": len(d), "min_cell_events_or_nonevents": min_ev}
    if min_ev == 0:
        return {**base, "status": "dropped: zero cell (separation)", "lr_chi2": np.nan, "df": np.nan,
                "p": np.nan, "conv_full": np.nan, "conv_reduced": np.nan, "warnings": ""}
    full, cf, wf = fit_logit(f"{y} ~ C({grp}) * C({era})", d)
    red, cr, wr = fit_logit(f"{y} ~ C({grp}) + C({era})", d)
    if full is None or red is None or not (cf and cr):
        return {**base, "status": "dropped: non-convergence", "lr_chi2": np.nan, "df": np.nan,
                "p": np.nan, "conv_full": cf, "conv_reduced": cr, "warnings": f"{wf} | {wr}"}
    lr = 2 * (full.llf - red.llf)
    k = int(full.df_model - red.df_model)
    return {**base, "status": "ok", "lr_chi2": lr, "df": k, "p": stats.chi2.sf(lr, k),
            "conv_full": cf, "conv_reduced": cr, "warnings": f"{wf} | {wr}".strip(" |")}


def lpm_gap(df, y, x, cluster):
    """LPM coefficient of binary x on binary y (pp), SE clustered by `cluster`."""
    d = df[[y, x, cluster]].dropna().copy()
    d[y] = d[y].astype(float)
    d[x] = d[x].astype(float)
    if d[x].nunique() < 2:
        return np.nan, np.nan, np.nan
    m = smf.ols(f"{y} ~ {x}", d).fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d[cluster])[0]})
    return 100 * m.params[x], 100 * m.bse[x], m.pvalues[x]


def cluster_boot_blocs(w, blocs, a_bloc, b_bloc):
    """Legislator-cluster bootstrap for bloc elite shares, a-b gap (pp) and a/b ratio.
    `w` = term rows with columns nm, bloc, elite. Returns dict of point estimates + 95% CIs."""
    agg = (w.assign(one=1).pivot_table(index="nm", columns="bloc", values=["one", "elite"],
                                       aggfunc="sum", fill_value=0))
    cols_n = [("one", b) for b in blocs]
    cols_e = [("elite", b) for b in blocs]
    X_n = agg.reindex(columns=cols_n, fill_value=0).to_numpy(float)
    X_e = agg.reindex(columns=cols_e, fill_value=0).to_numpy(float)
    L = X_n.shape[0]
    W = RNG.multinomial(L, np.full(L, 1 / L), size=N_BOOT).astype(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        sh_b = 100 * (W @ X_e) / (W @ X_n)
    with np.errstate(divide="ignore", invalid="ignore"):
        sh = 100 * X_e.sum(0) / X_n.sum(0)
    ia, ib = blocs.index(a_bloc), blocs.index(b_bloc)
    out = {f"elite_pct_{b}": sh[i] for i, b in enumerate(blocs)}
    out.update({f"n_{b}": int(X_n[:, i].sum()) for i, b in enumerate(blocs)})
    out.update({f"cb_lo_{b}": np.nanpercentile(sh_b[:, i], 2.5) for i, b in enumerate(blocs)})
    out.update({f"cb_hi_{b}": np.nanpercentile(sh_b[:, i], 97.5) for i, b in enumerate(blocs)})
    gap_b = sh_b[:, ia] - sh_b[:, ib]
    with np.errstate(divide="ignore", invalid="ignore"):
        rat_b = sh_b[:, ia] / sh_b[:, ib]
    out.update({"gap_pp": sh[ia] - sh[ib], "gap_lo": np.nanpercentile(gap_b, 2.5),
                "gap_hi": np.nanpercentile(gap_b, 97.5),
                "ratio": sh[ia] / sh[ib] if sh[ib] > 0 else np.nan,
                "ratio_lo": np.nanpercentile(rat_b[np.isfinite(rat_b)], 2.5) if np.isfinite(rat_b).any() else np.nan,
                "ratio_hi": np.nanpercentile(rat_b[np.isfinite(rat_b)], 97.5) if np.isfinite(rat_b).any() else np.nan,
                "n_legislators": L})
    return out


# =============================================================================================
# 0. ROSTER + PARSE DIAGNOSTICS
# =============================================================================================
ros = pd.read_csv(REPO / "data" / "processed" / "cong_df.csv")
ros["Start"] = pd.to_numeric(ros.Start, errors="coerce").astype("Int64")
ros["End"] = pd.to_numeric(ros.End, errors="coerce").astype("Int64")
ros["nm"] = ros.Name.map(norm_name)
name_toks = ros.Name.map(lambda s: norm_name(s).split())
# two-token names stored as Pat = given name, Mat = surname (e.g. "Ramon Concha")
ros["misparse"] = (name_toks.str.len() == 2) & (name_toks.str[0] == ros.Pat.map(dac))
ros["group"] = [classify(p, m) for p, m in zip(ros.Pat, ros.Mat)]
ros["elite"] = (ros.group == "elite").astype(int)
ros["common"] = (ros.group == "common").astype(int)
# re-parsed variant: surname moved to Pat, Mat unknown
ros["group_reparsed"] = [classify(m, "") if mp else g
                         for g, mp, m in zip(ros.group, ros.misparse, ros.Mat)]
ros["era"] = ros.Start.map(era_of)
ros["era2"] = ros.Start.map(era_or_pre)

leg = (ros.groupby("nm")
       .agg(first=("Start", "min"), last_end=("End", "max"), Pat=("Pat", "first"), Mat=("Mat", "first"),
            misparse=("misparse", "max"))
       .reset_index())
leg["mid"] = ((leg["first"] + leg["last_end"]) // 2).astype("Int64")
leg["group"] = [classify(p, m) for p, m in zip(leg.Pat, leg.Mat)]
leg["era_first"] = leg["first"].map(era_of)
leg["era_mid"] = leg["mid"].map(era_of)
print(f"Roster: {len(ros)} legislator-term rows, {len(leg)} unique legislators (norm-name key).")

mp_tab = (ros[ros.era2.notna()].groupby("era2")
          .agg(n_terms=("nm", "size"), n_misparse=("misparse", "sum"),
               misparse_elite=("elite", lambda s: int(s[ros.loc[s.index, "misparse"]].sum())))
          .reset_index())
mp_tab["misparse_pct"] = 100 * mp_tab.n_misparse / mp_tab.n_terms
mp_era = pd.DataFrame([{
    "era": era,
    "elite_pct_all": 100 * ros.loc[ros.era2 == era, "elite"].mean(),
    "elite_pct_drop_misparse": 100 * ros.loc[(ros.era2 == era) & ~ros.misparse, "elite"].mean(),
    "elite_pct_reparsed": 100 * (ros.loc[ros.era2 == era, "group_reparsed"] == "elite").mean(),
} for era in ["1811-1833"] + ERA_LABELS])
mp_tab = mp_tab.merge(mp_era, left_on="era2", right_on="era").drop(columns="era")
mp_tab.to_csv(OUT / "a2_misparse_by_era.csv", index=False)
print("\nTwo-token mis-parse (Pat = given name) by era:")
print(mp_tab.round(2).to_string(index=False))

# =============================================================================================
# 1. BIOGRAPHICAL MARKERS BY ERA
# =============================================================================================
print("\n" + "=" * 78 + "\n1. BIOGRAPHICAL MARKERS BY ERA\n" + "=" * 78)
if not BIOS_JSON.exists():
    skip(f"Biography extraction not found at {BIOS_JSON} (not redistributed). "
         "Set RAW_DATA_ROOT; no numbers fabricated.")
with open(BIOS_JSON, encoding="utf-8") as fh:
    recs = [x for x in json.load(fh) if x.get("fields")]


def bio_row(x):
    """One biography -> analysis record (coding rules of scripts 06/10/34)."""
    f = x["fields"]
    text = dac((BIOS_TXT / x["file"]).read_text(encoding="utf-8"))
    body = text.partition("\n---\n")[2]
    school = dac(f.get("secondary_school") or "")
    spouses = f.get("spouse_surnames") or []
    by = pd.to_numeric(f.get("birth_year"), errors="coerce")
    dy = pd.to_numeric(f.get("death_year"), errors="coerce")
    return {
        "nm": norm_name(x["name"]), "name": x["name"], "file": x["file"],
        "start": pd.to_numeric(x.get("start"), errors="coerce"),
        "pat": x.get("pat", ""), "mat": x.get("mat", ""),
        "group": classify(x.get("pat", ""), x.get("mat", "")),
        "two_token": len(norm_name(x["name"]).split()) == 2,
        "club": int(bool(CU.search(text))), "club_body": int(bool(CU.search(body))),
        "club_llm": int(bool(f.get("elite_club"))),
        "school": int(bool(PRIV.search(school))), "school_named": int(bool(school)),
        "inst_nacional": int(bool(INST_NAC.search(school))),
        "rich": int(f.get("richness") == "rich"), "sparse": int(f.get("richness") == "sparse"),
        "landholding": int(bool(f.get("landholding"))), "nobiliary": int(bool(f.get("nobiliary_particle"))),
        "birth_year": by, "death_year": dy,
        "spouse_named": int(len(spouses) > 0),
        "spouse_elite": int(any(dac(t) in ELITE for s in spouses for t in str(s).split())),
    }


bio = pd.DataFrame([bio_row(x) for x in recs])
bio = bio.merge(leg[["nm", "mid", "first"]], on="nm", how="left")
bio["start"] = bio.start.astype("Int64")
bio["era_first"] = bio.start.map(era_of)
bio["era_mid"] = bio["mid"].map(era_of)
bio["elite_bin"] = (bio.group == "elite").astype(int)
match_diag = pd.DataFrame([{
    "n_bios_with_fields": len(bio),
    "n_matched_to_roster_key": int(bio["first"].notna().sum()),
    "start_equals_roster_first_entry_pct": 100 * float((bio.start == bio["first"]).fillna(False).mean()),
    "club_fulltext_vs_body_disagreements": int((bio.club != bio.club_body).sum()),
    "n_two_token_bios": int(bio.two_token.sum()),
}])
match_diag.to_csv(OUT / "a2_bio_match_diagnostics.csv", index=False)
print(match_diag.T.to_string(header=False))


def group_counts(e, marker):
    """(k, n) per group for a marker in data subset e."""
    return {g: (int(e.loc[e.group == g, marker].sum()), int((e.group == g).sum())) for g in GROUPS}


def marker_row(e, era, marker, label):
    """Rates, Wilson CIs, elite ratios and differences for one era subset."""
    cnt = group_counts(e, marker)
    rest = (int(e.loc[e.group != "elite", marker].sum()), int((e.group != "elite").sum()))
    row = {"era_def": label, "era": era, "marker": marker, "n_total": len(e),
           "elite_share_of_bios_pct": 100 * (e.group == "elite").mean() if len(e) else np.nan}
    for g in GROUPS:
        k, n = cnt[g]
        lo, hi = wilson(k, n)
        row.update({f"n_{g}": n, f"k_{g}": k, f"rate_{g}": 100 * k / n if n else np.nan,
                    f"lo_{g}": lo, f"hi_{g}": hi})
    a, n1 = cnt["elite"]
    for tag, (b, n2) in [("common", cnt["common"]), ("other", cnt["other"]), ("rest", rest)]:
        c = contrast(f"e_{tag}", a, n1, b, n2)
        row.update({f"rr_e_{tag}": c[f"e_{tag}_ratio"], f"rr_e_{tag}_lo": c[f"e_{tag}_ratio_lo"],
                    f"rr_e_{tag}_hi": c[f"e_{tag}_ratio_hi"], f"rr_e_{tag}_zero_cell": c[f"e_{tag}_zero_cell"],
                    f"diff_e_{tag}_pp": c[f"e_{tag}_diff_pp"], f"diff_e_{tag}_lo": c[f"e_{tag}_diff_lo"],
                    f"diff_e_{tag}_hi": c[f"e_{tag}_diff_hi"]})
    return row


def marker_table(df, era_col, marker, label):
    return [marker_row(df[df[era_col] == era], era, marker, label) for era in ERA_LABELS]


# ---- 1a. pooled calibration against the published (v1 corpus) numbers ---------------------
cal = pd.DataFrame([
    {"marker": mk_, "group": g, "n": len(sub), "k": int(sub[col].sum()),
     "rate_pct": 100 * sub[col].mean(), "published_pct": PUBLISHED[(mk_, g)],
     "diff_pp": 100 * sub[col].mean() - PUBLISHED[(mk_, g)]}
    for g in GROUPS
    for mk_, col, sub in [("club_union", "club", bio[bio.group == g]),
                          ("elite_school_20c", "school", bio[(bio.group == g) & (bio.start >= 1900).fillna(False)])]])
cal.to_csv(OUT / "a2_pooled_calibration.csv", index=False)
print("\nPooled calibration (v2 corpus vs published v1 numbers):")
print(cal.round(2).to_string(index=False))

# ---- 1b. rates, ratios, differences by era --------------------------------------------------
specs = [
    (bio, "era_first", "club", "first_entry"), (bio, "era_first", "school", "first_entry"),
    (bio, "era_mid", "club", "mid_career"), (bio, "era_mid", "school", "mid_career"),
    # Club founded 1864: (i) first entry >= 1864; (ii) birth known and >= 1830
    (bio[(bio.start >= 1864).fillna(False)], "era_first", "club", "first_entry_1864plus"),
    (bio[bio.birth_year >= 1830], "era_first", "club", "first_entry_born_1830plus"),
    (bio[(bio.start >= 1864).fillna(False)], "era_first", "school", "first_entry_1864plus"),
    # school conditional on the biography naming a secondary school
    (bio[bio.school_named == 1], "era_first", "school", "first_entry_school_named"),
    # dropping two-token (mis-parsed) names
    (bio[~bio.two_token], "era_first", "club", "first_entry_drop_two_token"),
    (bio[~bio.two_token], "era_first", "school", "first_entry_drop_two_token"),
]
mk = pd.DataFrame([r for df_, ec, m_, lab in specs for r in marker_table(df_, ec, m_, lab)])
mk.to_csv(OUT / "a2_markers_by_era.csv", index=False)
show = ["era_def", "era", "marker", "n_elite", "rate_elite", "n_common", "rate_common", "n_other",
        "rate_other", "rr_e_common", "rr_e_other", "rr_e_other_lo", "rr_e_other_hi", "rr_e_rest",
        "rr_e_rest_lo", "rr_e_rest_hi"]
print("\nMarker rates by era (pct) and elite fold ratios:")
print(mk[show].round(2).to_string(index=False))

# ---- 1c. LR tests of group x era -----------------------------------------------------------
test_specs = [("club", ERA_LABELS), ("club", ERA_LABELS[1:3]), ("school", ERA_LABELS),
              ("school", ERA_LABELS[1:])]
tests = pd.DataFrame([
    {"marker": m_, "eras": "+".join(eu), "contrast": gdesc,
     **lr_interaction(bio[bio.era_first.isin(eu)], m_, gvar, "era_first")}
    for m_, eu in test_specs for gvar, gdesc in [("elite_bin", "elite_vs_rest"), ("group", "three_groups")]])
tests.to_csv(OUT / "a2_marker_era_interaction_tests.csv", index=False)
print("\nLR tests, group x era interaction in logit(marker) (convergence logged):")
print(tests.drop(columns="warnings").round(4).to_string(index=False))

# ---- 1d. diagnostics by era x group ----------------------------------------------------------
diag = (bio[bio.era_first.notna()]
        .groupby(["era_first", "group"])
        .agg(n=("nm", "size"), rich_pct=("rich", "mean"), sparse_pct=("sparse", "mean"),
             school_named_pct=("school_named", "mean"), inst_nacional_pct=("inst_nacional", "mean"),
             elite_priv_school_pct=("school", "mean"), landholding_pct=("landholding", "mean"),
             nobiliary_pct=("nobiliary", "mean"), club_llm_pct=("club_llm", "mean"),
             club_union_pct=("club", "mean"), spouse_named_pct=("spouse_named", "mean"),
             birth_known_pct=("birth_year", lambda s: s.notna().mean()))
        .reset_index())
for c in [c for c in diag.columns if c.endswith("_pct")]:
    diag[c] = 100 * diag[c]
diag["inst_nacional_given_school_named_pct"] = 100 * diag.inst_nacional_pct / diag.school_named_pct
diag.to_csv(OUT / "a2_bio_diagnostics_by_era.csv", index=False)


def inst_row(era, conditional):
    e = bio[bio.era_first == era]
    if conditional:
        e = e[e.school_named == 1]
    el, ne = e[e.group == "elite"], e[e.group != "elite"]
    return {"era": era, "sample": "school_named" if conditional else "all_bios",
            "n_elite": len(el), "pct_elite": 100 * el.inst_nacional.mean(), "n_rest": len(ne),
            "pct_rest": 100 * ne.inst_nacional.mean(),
            **contrast("elite_vs_rest", int(el.inst_nacional.sum()), len(el), int(ne.inst_nacional.sum()), len(ne))}


pd.DataFrame([inst_row(era, c) for era in ERA_LABELS for c in [False, True]]).to_csv(
    OUT / "a2_inst_nacional_by_era.csv", index=False)
print("\nBiography diagnostics by era x group (pct):")
print(diag.round(1).to_string(index=False))

# ---- 1e. spouse decomposition (replaces the maternal-surname argument) ---------------------


def spouse_row(era, marker):
    """(a) non-elite legislators with vs without an elite-surname spouse (spouse named);
    (b) elite vs non-elite, full and excluding non-elite legislators with an elite spouse."""
    e = bio[bio.era_first == era]
    ne = e[e.group != "elite"]
    w_ = ne[(ne.spouse_named == 1) & (ne.spouse_elite == 1)]
    wo = ne[(ne.spouse_named == 1) & (ne.spouse_elite == 0)]
    el = e[e.group == "elite"]
    ne_x = ne[ne.spouse_elite == 0]
    row = {"era": era, "marker": marker,
           "n_nonelite_elite_spouse": len(w_), "rate_nonelite_elite_spouse": 100 * w_[marker].mean() if len(w_) else np.nan,
           "n_nonelite_nonelite_spouse": len(wo), "rate_nonelite_nonelite_spouse": 100 * wo[marker].mean() if len(wo) else np.nan,
           "n_elite": len(el), "rate_elite": 100 * el[marker].mean(),
           "n_nonelite_all": len(ne), "rate_nonelite_all": 100 * ne[marker].mean(),
           "n_nonelite_excl_elite_spouse": len(ne_x), "rate_nonelite_excl_elite_spouse": 100 * ne_x[marker].mean()}
    row.update(contrast("spouse_within_nonelite", int(w_[marker].sum()), len(w_), int(wo[marker].sum()), len(wo)))
    row.update(contrast("elite_vs_nonelite_all", int(el[marker].sum()), len(el), int(ne[marker].sum()), len(ne)))
    row.update(contrast("elite_vs_nonelite_excl", int(el[marker].sum()), len(el), int(ne_x[marker].sum()), len(ne_x)))
    return row


sp = pd.DataFrame([spouse_row(era, m_) for era in ERA_LABELS for m_ in ["club", "school"]])
sp.to_csv(OUT / "a2_spouse_decomposition_by_era.csv", index=False)
print("\nSpouse decomposition:")
print(sp[["era", "marker", "n_nonelite_elite_spouse", "rate_nonelite_elite_spouse", "n_nonelite_nonelite_spouse",
          "rate_nonelite_nonelite_spouse", "spouse_within_nonelite_ratio", "elite_vs_nonelite_all_ratio",
          "elite_vs_nonelite_excl_ratio", "elite_vs_nonelite_excl_ratio_lo",
          "elite_vs_nonelite_excl_ratio_hi"]].round(2).to_string(index=False))

# ---- 1f. biography coverage by era x group -------------------------------------------------
leg["covd"] = leg.nm.isin(set(bio.nm))
cov = (leg[leg.era_first.notna()].groupby(["era_first", "group"])
       .agg(n=("nm", "size"), covered=("covd", "sum")).reset_index())
cov["coverage_pct"] = 100 * cov.covered / cov.n
cov.to_csv(OUT / "a2_bio_coverage_by_era.csv", index=False)

# =============================================================================================
# 1b. v1 -> v2 CROSSWALK OF PUBLISHED NUMBERS
# =============================================================================================
print("\n" + "=" * 78 + "\n1b. v1 -> v2 CROSSWALK\n" + "=" * 78)
# script 24 definitions: unique roster Names, exact de-accented Name match to biography names
u24 = ros.drop_duplicates(subset="Name").copy()
bio_names = set(bio.name.map(dac))
u24["covd"] = u24.Name.map(lambda n: dac(n) in bio_names)
cov24 = u24.groupby("group").covd.agg(["size", "sum", "mean"])
full_n = cov24["size"].to_dict()
cov_n = cov24["sum"].to_dict()
wgt = {g: full_n[g] / cov_n[g] for g in GROUPS}
name2group = dict(zip(u24.Name.map(dac), u24.group))
bio["g24"] = bio.name.map(lambda n: name2group.get(dac(n), "other"))
bio["w24"] = bio.g24.map(wgt)
el24, ot24 = bio[bio.elite_bin == 1], bio[bio.elite_bin == 0]
el24_20, ot24_20 = el24[(el24.start >= 1900).fillna(False)], ot24[(ot24.start >= 1900).fillna(False)]


def wrate(d, col):
    return 100 * np.average(d[col], weights=d.w24)


def rate(d, col):
    return 100 * d[col].mean()


club_e, club_r = rate(el24, "club"), rate(ot24, "club")
sch_e, sch_r = rate(el24_20, "school"), rate(ot24_20, "school")
v2 = {g: cal.set_index(["marker", "group"]).rate_pct[(m_, g)] for m_ in ["club_union"] for g in GROUPS}
v2s = {g: cal.set_index(["marker", "group"]).rate_pct[("elite_school_20c", g)] for g in GROUPS}
xw = pd.DataFrame([
    ("Biographies matched (N)", 3174, len(bio), "03_validation.tex; app. B"),
    ("Roster coverage overall (%)", 81.1, 100 * u24.covd.mean(), "tab:biocoverage"),
    ("Roster coverage elite (%)", 80.5, 100 * cov24.loc["elite", "mean"], "tab:biocoverage"),
    ("Roster coverage common (%)", 80.0, 100 * cov24.loc["common", "mean"], "tab:biocoverage"),
    ("Roster coverage other (%)", 82.0, 100 * cov24.loc["other", "mean"], "tab:biocoverage"),
    ("Covered legislators (N, unique Names)", 3175, int(u24.covd.sum()), "tab:biocoverage note"),
    ("Club elite (%)", 12.7, v2["elite"], "Fig. 1"),
    ("Club common (%)", 4.1, v2["common"], "Fig. 1"),
    ("Club other (%)", 5.3, v2["other"], "Fig. 1"),
    ("Club non-elite 'rest' (%)", 4.9, club_r, "app. B list"),
    ("School elite (%)", 41.2, v2s["elite"], "Fig. 1"),
    ("School common (%)", 7.6, v2s["common"], "Fig. 1"),
    ("School other (%)", 15.4, v2s["other"], "Fig. 1"),
    ("School non-elite 'rest' (%)", 12.5, sch_r, "app. B list"),
    ("Club elite/common (x)", 12.7 / 4.1, v2["elite"] / v2["common"], "derived"),
    ("Club elite/other (x)", 12.7 / 5.3, v2["elite"] / v2["other"], "derived"),
    ("Club elite/rest (x)", 12.7 / 4.9, club_e / club_r, "derived (quality gate 2.6x)"),
    ("School elite/common (x)", 41.2 / 7.6, v2s["elite"] / v2s["common"], "derived"),
    ("School elite/other (x)", 41.2 / 15.4, v2s["elite"] / v2s["other"], "derived"),
    ("School elite/rest (x)", 41.2 / 12.5, sch_e / sch_r, "derived (quality gate 3.3x)"),
    ("Club reweighted fold, script-24 def (LLM elite_club field) (x)", 2.6,
     wrate(el24, "club_llm") / wrate(ot24, "club_llm"), "app. B / tab:biocoverage note"),
    ("Club reweighted fold, regex def (x)", np.nan, wrate(el24, "club") / wrate(ot24, "club"), "new"),
    ("School reweighted fold (x)", 3.3, wrate(el24_20, "school") / wrate(ot24_20, "school"),
     "app. B / tab:biocoverage note"),
], columns=["quantity", "published_v1", "v2", "where_in_paper"])
xw["relative_change"] = xw.v2 / xw.published_v1
xw.to_csv(OUT / "a2_v1_to_v2_crosswalk.csv", index=False)
print(xw.round(3).to_string(index=False))

# =============================================================================================
# 2. KNOWN-GROUPS: SENATE vs CHAMBER BY ERA AND DECADE
# =============================================================================================
print("\n" + "=" * 78 + "\n2. SENATE vs CHAMBER ELITE SHARE\n" + "=" * 78)
sc = ros[ros.Camara.isin(["Diputado", "Senador"]) & ros.Start.notna()].copy()
sc["senate"] = (sc.Camara == "Senador").astype(int)
sc["designated"] = sc.Tipo.isin(["Institucional", "Vitalicio"])


def senate_row(e, era, variant):
    row = {"era": era, "variant": variant}
    for c, lab in [(1, "senate"), (0, "chamber")]:
        s = e[e.senate == c]
        k, n = int(s.elite.sum()), len(s)
        lo, hi = wilson(k, n)
        u = s.drop_duplicates("nm")
        row.update({f"n_terms_{lab}": n, f"elite_pct_{lab}": 100 * k / n if n else np.nan,
                    f"lo_{lab}": lo, f"hi_{lab}": hi, f"n_legislators_{lab}": len(u),
                    f"elite_pct_legislators_{lab}": 100 * u.elite.mean() if len(u) else np.nan})
    g, se, p = lpm_gap(e, "elite", "senate", "nm")
    row.update({"gap_pp": g, "gap_se_clustered": se, "gap_p": p,
                "ratio_senate_chamber": row["elite_pct_senate"] / row["elite_pct_chamber"]
                if row["elite_pct_chamber"] else np.nan})
    return row


kg = pd.DataFrame(
    [senate_row(sc[sc.era2 == era], era, "all") for era in ["1811-1833"] + ERA_LABELS]
    + [senate_row(sc[(sc.era2 == era) & ~sc.misparse], era, "drop_misparse") for era in ["1811-1833"] + ERA_LABELS]
    + [senate_row(sc[(sc.era2 == "1990-2020") & ~sc.designated], "1990-2020", "no_designated_life_senators")])
kg.to_csv(OUT / "a2_senate_chamber_by_era.csv", index=False)
print(kg[["era", "variant", "n_terms_senate", "elite_pct_senate", "n_terms_chamber", "elite_pct_chamber",
          "gap_pp", "gap_se_clustered", "gap_p", "ratio_senate_chamber"]].round(3).to_string(index=False))

sc["decade"] = (sc.Start // 10 * 10).astype(int)
dec = (sc.groupby(["decade", "senate"]).agg(n=("elite", "size"), k=("elite", "sum")).reset_index()
       .pivot(index="decade", columns="senate", values=["n", "k"]))
dec.columns = [f"{a}_{'senate' if b == 1 else 'chamber'}" for a, b in dec.columns]
dec = dec.fillna(0).astype(int).reset_index()
dec["elite_pct_senate"] = np.where(dec.n_senate > 0, 100 * dec.k_senate / dec.n_senate.clip(lower=1), np.nan)
dec["elite_pct_chamber"] = np.where(dec.n_chamber > 0, 100 * dec.k_chamber / dec.n_chamber.clip(lower=1), np.nan)
dec["gap_pp"] = dec.elite_pct_senate - dec.elite_pct_chamber
dec["fisher_p"] = [stats.fisher_exact([[r.k_senate, r.n_senate - r.k_senate],
                                       [r.k_chamber, r.n_chamber - r.k_chamber]])[1]
                   if r.n_senate > 0 and r.n_chamber > 0 else np.nan for r in dec.itertuples()]
dec["usable"] = (dec.n_senate >= 20) & (dec.n_chamber > 0)
dec.to_csv(OUT / "a2_senate_chamber_by_decade.csv", index=False)
dd = dec[dec.usable]
n_pos = int((dd.gap_pp > 0).sum())
print(f"Usable decades: {len(dd)}; Senate > Chamber in {n_pos}; "
      f"sign test p = {stats.binomtest(n_pos, len(dd)).pvalue:.4f}")

# =============================================================================================
# 3. PARTY KNOWN-GROUPS BY ERA
# =============================================================================================
print("\n" + "=" * 78 + "\n3. PARTY BLOCS BY ERA\n" + "=" * 78)
pt = ros[ros.Start.notna()].copy()
cal_g = pt[(pt.End >= 1910) & (pt.Start <= 1950)]   # reproduces tab:gradient Ns exactly
calg = (cal_g.groupby("Partido").agg(n=("elite", "size"), elite_pct=("elite", "mean"),
                                    common_pct=("common", "mean")).reset_index())
calg = calg[calg.Partido.isin(["Partido Conservador", "Partido Liberal", "Partido Liberal Democratico",
                               "Partido Nacional o Monttvarista", "Partido Democratico", "Partido Radical",
                               "Partido Socialista de Chile", "Partido Comunista de Chile"])]
calg[["elite_pct", "common_pct"]] *= 100
calg.to_csv(OUT / "a2_party_gradient_calibration_1910_1950.csv", index=False)

BLOCS = ["derecha", "centro", "izquierda"]
windows = ERAS + [("1910-1973", 1910, 1973), ("1910-1950", 1910, 1950)]


def bloc_row(mapname, mp, lab, lo, hi):
    w = pt[(pt.Start >= lo) & (pt.Start <= hi)].assign(bloc=lambda d: d.Partido.map(mp))
    mapped = w[w.bloc.notna()]
    row = {"mapping": mapname, "window": lab, "n_terms": len(w),
           "party_recorded_pct": 100 * w.Partido.notna().mean(),
           "bloc_mapped_pct": 100 * w.bloc.notna().mean(),
           "unmapped_elite_pct": 100 * w.loc[w.bloc.isna(), "elite"].mean() if w.bloc.isna().any() else np.nan}
    present = [b for b in BLOCS if (mapped.bloc == b).any()]
    both = "derecha" in present and "izquierda" in present
    # shares + cluster CIs for every bloc present; the right-left contrast only if both exist
    row.update(cluster_boot_blocs(mapped, present, present[0], present[-1]))
    row.update({f"n_{b}": 0 for b in BLOCS if b not in present})
    row.update({f"elite_pct_{b}": np.nan for b in BLOCS if b not in present})
    if both:
        rl = mapped[mapped.bloc.isin(["derecha", "izquierda"])].assign(right=lambda d: (d.bloc == "derecha").astype(int))
        g, se, p = lpm_gap(rl, "elite", "right", "nm")
        row.update({"rl_lpm_pp": g, "rl_se_clustered": se, "rl_p": p})
    else:
        row.update({k: np.nan for k in ["gap_pp", "gap_lo", "gap_hi", "ratio", "ratio_lo", "ratio_hi"]})
    row["monotone_r_gt_c_gt_l"] = bool(row.get("elite_pct_derecha", np.nan) > row.get("elite_pct_centro", np.nan)
                                       > row.get("elite_pct_izquierda", np.nan))
    return row


pb = pd.DataFrame([bloc_row(mn, mp, lab, lo, hi)
                   for mn, mp in [("12b_plus_ext", BLOC_MAP), ("12b_only", BLOC_12B_MAP),
                                  ("ext_PPD_centre", BLOC_MAP_PPD_CENTRE)]
                   for lab, lo, hi in windows])
pb.to_csv(OUT / "a2_party_bloc_by_era.csv", index=False)
print(pb[["mapping", "window", "bloc_mapped_pct", "n_derecha", "elite_pct_derecha", "n_centro", "elite_pct_centro",
          "n_izquierda", "elite_pct_izquierda", "gap_pp", "gap_lo", "gap_hi", "ratio", "ratio_lo", "ratio_hi",
          "rl_p", "monotone_r_gt_c_gt_l"]].round(2).to_string(index=False))

# ---- 3b. 1990-2020 coalition coding + bounds for unassigned terms --------------------------
w90 = pt[(pt.Start >= 1990) & (pt.Start <= 2020)].copy()
in_cl = w90.Partido.isin(COAL_CL) | ((w90.Partido == "Partido Comunista de Chile") & (w90.Start >= PC_NM_FROM))
w90["coal"] = np.where(w90.Partido.isin(COAL_RIGHT), "right_coalition",
                       np.where(in_cl.fillna(False), "centre_left_coalition", None))
un = w90[w90.coal.isna()]
un_comp = (un.Partido.fillna("(missing)").value_counts().rename_axis("Partido").reset_index(name="n_terms"))
un_comp["elite_pct"] = [100 * un.loc[un.Partido.fillna("(missing)") == p, "elite"].mean() for p in un_comp.Partido]
un_comp.to_csv(OUT / "a2_unassigned_1990_2020.csv", index=False)
coal_specs = [("coalition_party_based", w90[w90.coal.notna()]),
              ("bound_unassigned_to_right", w90.assign(coal=w90.coal.fillna("right_coalition"))),
              ("bound_unassigned_to_centre_left", w90.assign(coal=w90.coal.fillna("centre_left_coalition")))]
coal = pd.DataFrame([{"spec": nm_, "n_terms": len(d), "n_unassigned_1990_2020": len(un),
                      "unassigned_pct_1990_2020": 100 * len(un) / len(w90),
                      **cluster_boot_blocs(d.rename(columns={"coal": "bloc"}),
                                           ["right_coalition", "centre_left_coalition"],
                                           "right_coalition", "centre_left_coalition")}
                     for nm_, d in coal_specs])
coal.to_csv(OUT / "a2_coalition_1990_2020.csv", index=False)
print("\n1990-2020 coalition coding (cluster-bootstrap CIs):")
print(coal.round(2).to_string(index=False))
print("Unassigned 1990-2020 terms by party label (top):")
print(un_comp.head(10).round(1).to_string(index=False))

# =============================================================================================
# 4. MEASUREMENT-ARTIFACT CHECKS
# =============================================================================================
print("\n" + "=" * 78 + "\n4. MEASUREMENT-ARTIFACT CHECKS\n" + "=" * 78)
pop = pd.read_csv(REPO / "data" / "processed" / "pop_prevalence_by_year.csv")
pop["decade"] = pop.year // 10 * 10
pd_ = pop.groupby("decade").agg(first_year=("year", "min"), n_births=("n_total", "sum"),
                                n_elite=("n_elite", "sum"), n_common=("n_common", "sum")).reset_index()
pd_["elite_pct"] = 100 * pd_.n_elite / pd_.n_births
pd_["common_pct"] = 100 * pd_.n_common / pd_.n_births
pd_["other_pct"] = 100 - pd_.elite_pct - pd_.common_pct
pd_.to_csv(OUT / "a2_pop_prevalence_by_decade.csv", index=False)
print(pd_.round(2).to_string(index=False))

cong_era = (ros[ros.era.notna()].groupby("era").agg(n_terms=("elite", "size"), elite_pct=("elite", "mean"),
                                                    common_pct=("common", "mean")).reset_index())
cong_era[["elite_pct", "common_pct"]] *= 100
miss = (ros[ros.era2.notna()]
        .assign(mat_missing=ros.Mat.isna() | (ros.Mat.astype(str).str.strip() == ""),
                pat_missing=ros.Pat.isna() | (ros.Pat.astype(str).str.strip() == ""))
        .groupby("era2").agg(mat_missing_pct=("mat_missing", "mean"), pat_missing_pct=("pat_missing", "mean"),
                             misparse_pct=("misparse", "mean")).reset_index())
miss[["mat_missing_pct", "pat_missing_pct", "misparse_pct"]] *= 100
art = miss.merge(cong_era, left_on="era2", right_on="era", how="left").drop(columns="era")
art.to_csv(OUT / "a2_roster_composition_and_missingness_by_era.csv", index=False)
print(art.round(2).to_string(index=False))

# =============================================================================================
# 5. HOMOGAMY BY ERA (legislator level first)
# =============================================================================================
print("\n" + "=" * 78 + "\n5. HOMOGAMY BY ERA\n" + "=" * 78)
ros["pe"] = ros.Pat.map(lambda s: dac(s) in ELITE)
ros["me"] = ros.Mat.map(lambda s: dac(s) in ELITE)
leg_h = ros.sort_values("Start").drop_duplicates("nm")[["nm", "pe", "me", "misparse", "Start"]]
leg_h["era"] = leg_h.Start.map(era_of)


def homog(df, unit, era):
    a, n1 = int(df[df.pe].me.sum()), int(df.pe.sum())
    b, n2 = int(df[~df.pe].me.sum()), int((~df.pe).sum())
    return {"unit": unit, "era": era, "n_pat_elite": n1,
            "pct_mat_elite_if_pat_elite": 100 * a / n1 if n1 else np.nan, "n_pat_not": n2,
            "pct_mat_elite_if_pat_not": 100 * b / n2 if n2 else np.nan,
            **{k.replace("h_", ""): v for k, v in contrast("h", a, n1, b, n2).items()}}


def spouse_hom(era):
    e = bio[(bio.era_first == era) & (bio.spouse_named == 1)]
    a, n1 = int(e[e.elite_bin == 1].spouse_elite.sum()), int((e.elite_bin == 1).sum())
    b, n2 = int(e[e.elite_bin == 0].spouse_elite.sum()), int((e.elite_bin == 0).sum())
    return {"unit": "bios_spouse_named", "era": era, "n_pat_elite": n1,
            "pct_mat_elite_if_pat_elite": 100 * a / n1 if n1 else np.nan, "n_pat_not": n2,
            "pct_mat_elite_if_pat_not": 100 * b / n2 if n2 else np.nan,
            **{k.replace("h_", ""): v for k, v in contrast("h", a, n1, b, n2).items()}}


hom = pd.DataFrame(
    [homog(leg_h[leg_h.era == era], "legislators_first_entry", era) for era in ERA_LABELS]
    + [homog(leg_h[(leg_h.era == era) & ~leg_h.misparse], "legislators_first_entry_drop_misparse", era)
       for era in ERA_LABELS]
    + [homog(ros, "terms_script06_pooled", "all")]
    + [homog(ros[ros.era == era], "terms_script06", era) for era in ERA_LABELS]
    + [spouse_hom(era) for era in ERA_LABELS])
hom.to_csv(OUT / "a2_homogamy_by_era.csv", index=False)
print("(spouse rows: 'pat_elite' = elite-surname legislator; 'mat_elite' = elite spouse surname)")
print(hom[["unit", "era", "n_pat_elite", "pct_mat_elite_if_pat_elite", "n_pat_not", "pct_mat_elite_if_pat_not",
           "ratio", "ratio_lo", "ratio_hi", "diff_pp"]].round(2).to_string(index=False))

# =============================================================================================
# 6. CENTRALITY BY ENTRY COHORT (19th-c network, script 07; pinned commit)
# =============================================================================================
print("\n" + "=" * 78 + "\n6. NETWORK CENTRALITY BY ENTRY COHORT\n" + "=" * 78)
CENT_FILES = [OUT / "a2_centrality_by_subperiod.csv", OUT / "a2_centrality_match_by_group.csv"]
try:
    with urllib.request.urlopen(NET_URL, timeout=60) as resp:
        raw = resp.read()
except (urllib.error.URLError, TimeoutError) as ex:
    print(f"Centrality skipped: network download failed ({ex}); stale outputs removed.")
    for f_ in CENT_FILES:
        f_.unlink(missing_ok=True)
    raw = None

if raw is not None and hashlib.sha256(raw).hexdigest() != NET_SHA256:
    print(f"Centrality skipped: network sha256 {hashlib.sha256(raw).hexdigest()} != expected {NET_SHA256}; "
          "stale outputs removed.")
    for f_ in CENT_FILES:
        f_.unlink(missing_ok=True)
    raw = None

if raw is not None:
    print(f"network sha256 verified = {NET_SHA256} (commit {NET_SHA})")
    net = pd.read_csv(io.BytesIO(raw), index_col=0)
    net.index = net.index.astype(str)
    M = (net.fillna(0).values != 0).astype(int)
    A = np.maximum(M, M.T)
    np.fill_diagonal(A, 0)
    nodes = list(net.index)
    G = nx.from_numpy_array(A)
    cent = {"Degree": nx.degree_centrality(G), "Betweenness": nx.betweenness_centrality(G),
            "Closeness": nx.closeness_centrality(G), "Eigenvector": nx.eigenvector_centrality_numpy(G)}

    def grp07(n):  # script 07 verbatim
        t = dac(n).split(".")
        pat = t[0] if t else ""
        mat = t[1] if len(t) > 1 else ""
        return "Elite" if (pat in ELITE or mat in ELITE) else "Common" if (pat in COMMON or mat in COMMON) else "Other"

    nd = pd.DataFrame({"node": nodes, "group": [grp07(n) for n in nodes],
                       **{k: [v[i] for i in range(len(nodes))] for k, v in cent.items()}})
    # node "Pat.Mat.Given..." -> roster "Given Pat Mat"
    r1 = ros.drop_duplicates("nm").assign(p=lambda d: d.Pat.map(dac), m=lambda d: d.Mat.map(dac))
    r1["sfx"] = " " + r1.p + " " + r1.m
    r1 = r1[[nm_.endswith(s) for nm_, s in zip(r1.nm, r1.sfx)]]
    r1["key"] = r1.p + "|" + r1.m + "|" + [nm_[: -len(s)] for nm_, s in zip(r1.nm, r1.sfx)]
    key2nm = r1.drop_duplicates("key").set_index("key").nm.to_dict()
    first_by_nm = dict(zip(leg.nm, leg["first"]))
    node_keys = [(lambda t: f"{t[0]}|{t[1]}|{' '.join(t[2:])}" if len(t) >= 3 else "")(dac(n).replace("-", " ").split("."))
                 for n in nodes]
    nd["first"] = pd.array([first_by_nm.get(key2nm.get(k)) for k in node_keys], dtype="Int64")
    nd["matched"] = nd["first"].notna()
    match_g = nd.groupby("group").matched.agg(["size", "sum", "mean"]).reset_index()
    match_g.columns = ["group", "n_nodes", "n_matched", "match_rate"]
    match_g["match_rate"] *= 100
    print(match_g.round(1).to_string(index=False))
    nd["sub"] = pd.cut(nd["first"].astype(float), [1800, 1833, 1860, 1890, 2030],
                       labels=["1811-1833", "1834-1860", "1861-1890", "1891_only"])   # matched entries end in 1891

    def cent_row(sub, s, k):
        el, ot = s.loc[s.group == "Elite", k].to_numpy(), s.loc[s.group == "Other", k].to_numpy()
        with np.errstate(divide="ignore", invalid="ignore"):
            br = RNG.choice(el, (N_BOOT, len(el))).mean(1) / RNG.choice(ot, (N_BOOT, len(ot))).mean(1)
        br = br[np.isfinite(br)]      # draws with zero mean in the 'other' group are dropped (logged)
        return {"n_boot_finite": len(br),"subperiod": sub, "measure": k, "n_elite": len(el), "n_other": len(ot),
                "n_common": int((s.group == "Common").sum()), "ratio_elite_other": el.mean() / ot.mean(),
                "boot_lo": np.percentile(br, 2.5), "boot_hi": np.percentile(br, 97.5)}

    subs = [("all_nodes", nd), ("matched_nodes", nd[nd.matched])] + \
           [(s_, nd[nd["sub"] == s_]) for s_ in ["1811-1833", "1834-1860", "1861-1890", "1891_only"]]
    cent_out = pd.DataFrame([cent_row(sub, s, k) for sub, s in subs for k in cent
                             if (s.group == "Elite").sum() >= 5 and (s.group == "Other").sum() >= 5])
    cent_out.to_csv(CENT_FILES[0], index=False)
    match_g.to_csv(CENT_FILES[1], index=False)
    print(cent_out.round(2).to_string(index=False))

# =============================================================================================
# 7. CONSTRUCTION PLACEBOS (R2: "not just a similar time trend for everything due to measurement")
# =============================================================================================
print("\n" + "=" * 78 + "\n7. CONSTRUCTION PLACEBOS\n" + "=" * 78)
# Workbook sheets whose rows are political office-holders (circularity with a Congress roster):
# '$$$' = "Kinship, Parliament and the millionaires of old Chile"; 'SA4' = "largest investors and
# public offices, 1850-75"; 'Cco' = intendentes of Curico.
POLITICAL_SHEETS = ["$$$", "SA4", "Cco"]


def hist_parts():
    """Surname tokens per historical source, replicating _measure_helpers.build_hist exactly."""
    cz = pd.read_csv(CENSO, encoding="latin-1")
    cz["Avaluacion"] = pd.to_numeric(cz["Avaluacion"], errors="coerce")
    big = cz[cz["Avaluacion"] >= cz["Avaluacion"].quantile(0.75)]
    parts = {"censo1874": {t for col in ["Paterno", "Materno"] for v in big[col].dropna() for t in toks(v)}}
    sheets = pd.read_excel(XLSX, sheet_name=None, header=None)
    parts.update({tab: {t for v in d.values.ravel() if str(v) != "nan" for t in toks(v)}
                  for tab, d in sheets.items()})
    return parts


PARTS = hist_parts()
HIST_FULL = set(build_hist())
assert HIST_FULL == set().union(*PARTS.values()), "gate-part reconstruction differs from build_hist()"
GATES = {"full": HIST_FULL, "census_only": PARTS["censo1874"],
         "no_political_sheets": set().union(*[v for k, v in PARTS.items() if k not in POLITICAL_SHEETS])}
pd.DataFrame([{"part": k, "n_tokens": len(v), "political_office_sheet": k in POLITICAL_SHEETS}
              for k, v in PARTS.items()]).to_csv(OUT / "a2_placebo_gate_parts.csv", index=False)

# ---- SES table ---------------------------------------------------------------------------------
nse_raw = pd.read_csv(REPO / "data" / "processed" / "surname_nse.csv")
nse_raw["s"] = nse_raw.surname.map(dac)
nse_all = (nse_raw.assign(w=nse_raw.mean_nse * nse_raw.n_occ).groupby("s")
           .agg(n_occ=("n_occ", "sum"), w=("w", "sum")).reset_index())
nse_all["mean_nse"] = nse_all.w / nse_all.n_occ

# ---- 7a. Registro Civil person-level pass (script 03 logic) ------------------------------------
# Year field is the registration year ('ANO INSC'), used as birth year exactly as in script 03.
VOCAB = pd.Index(sorted(set(nse_all.s) | ELITE | COMMON))
RC_GLOB = sorted((DATOS_ROOT / "Registro Civil" / "HISTORICO").glob("aaaa_appat_apmat_nac_*.csv"),
                 key=lambda p: int(p.stem.split("_")[-1]))
RC_CACHE = os.environ.get("A2_RC_CACHE")       # optional dev cache (codes only); unset in normal runs


def clean_codes(col):
    """Surname strings -> VOCAB codes (-1 if absent), de-accenting unique values only."""
    codes, uniq = pd.factorize(col.fillna(""))
    idx = VOCAB.get_indexer([dac(u) for u in uniq])
    return idx[codes].astype(np.int32) if len(uniq) else np.empty(0, np.int32)


def read_rc(path):
    d = pd.read_csv(path, sep=";", encoding="latin-1", dtype=str, header=0, names=["yr", "pat", "mat", "nac"])
    yr = pd.to_numeric(d.yr, errors="coerce")
    keep = (d.nac.astype(str).str.startswith("CHILEN") & (yr >= 1884)).to_numpy()
    return yr.to_numpy()[keep].astype(np.int16), clean_codes(d.pat[keep]), clean_codes(d.mat[keep])


if RC_CACHE and Path(RC_CACHE).exists():
    with np.load(RC_CACHE) as z:
        RC_Y, RC_P, RC_M = z["y"], z["p"], z["m"]
else:
    if not RC_GLOB:
        skip("Registro Civil HISTORICO files not found under DATOS_ROOT; no numbers fabricated.")
    _parts = [read_rc(p) for p in RC_GLOB]
    RC_Y, RC_P, RC_M = (np.concatenate([x[i] for x in _parts]) for i in range(3))
    del _parts
    if RC_CACHE:
        np.savez(RC_CACHE, y=RC_Y, p=RC_P, m=RC_M)
Y0 = 1884
YEARS = np.arange(Y0, int(RC_Y.max()) + 1)
BIRTHS = np.bincount(RC_Y - Y0, minlength=len(YEARS)).astype(float)
print(f"Registro Civil: {len(RC_Y):,} Chilean registrations {YEARS[0]}-{YEARS[-1]} from {len(RC_GLOB)} files")


def pop_by_year(sset):
    """Persons (Pat or Mat in sset) per registration year -- exact, person-level."""
    mem = np.zeros(len(VOCAB) + 1, bool)            # last slot = code -1 (not in vocabulary)
    ix = VOCAB.get_indexer(list(sset))
    mem[ix[ix >= 0]] = True
    return np.bincount(RC_Y - Y0, weights=mem[RC_P] | mem[RC_M], minlength=len(YEARS))


# calibration against script 03's shipped reference
pop03 = pd.read_csv(REPO / "data" / "processed" / "pop_prevalence_by_year.csv").set_index("year")
cal_rc = pd.DataFrame({"year": YEARS, "n_total_38": BIRTHS, "n_elite_38": pop_by_year(ELITE)}).set_index("year")
cal_rc = cal_rc.join(pop03[["n_total", "n_elite"]], how="left").reset_index()
cal_rc.to_csv(OUT / "a2_rc_calibration.csv", index=False)
print(f"RC calibration vs pop_prevalence_by_year.csv: total births identical in "
      f"{int((cal_rc.n_total_38 == cal_rc.n_total).sum())}/{int(cal_rc.n_total.notna().sum())} years; "
      f"elite count identical in {int((cal_rc.n_elite_38 == cal_rc.n_elite).sum())} years; "
      f"max |diff| elite = {int((cal_rc.n_elite_38 - cal_rc.n_elite).abs().max())}")

# early-cohort presence per surname: persons bearing it among registrations 1885-1904
early = (RC_Y >= 1885) & (RC_Y <= 1904)
p_e, m_e = RC_P[early], RC_M[early]
both = (p_e == m_e) & (p_e >= 0)
early_cnt = (np.bincount(p_e[p_e >= 0], minlength=len(VOCAB)) + np.bincount(m_e[m_e >= 0], minlength=len(VOCAB))
             - np.bincount(p_e[both], minlength=len(VOCAB)))
nse_all["early_per100k"] = 1e5 * early_cnt[VOCAB.get_indexer(nse_all.s)] / early.sum()

# ---- 7b. surname table with gate flags ---------------------------------------------------------
nse = nse_all[nse_all.n_occ >= 30].reset_index(drop=True)        # bearer floor used in the build
nse = nse.assign(is_elite=nse.s.isin(ELITE), is_common=nse.s.isin(COMMON),
                 **{f"att_{g}": [in_hist(s, H) for s in nse.s] for g, H in GATES.items()})
FEAT = {"ses": nse.mean_nse / nse.mean_nse.std(),
        "bearers": np.log(nse.n_occ) / np.log(nse.n_occ).std(),
        "early": np.log1p(nse.early_per100k) / np.log1p(nse.early_per100k).std()}
nse = nse.assign(**{f"f_{k}": v for k, v in FEAT.items()})


def match_wor(target, pool, feats):
    """Optimal 1:1 matching WITHOUT replacement (Hungarian) on standardised features."""
    Xt = target[[f"f_{f}" for f in feats]].to_numpy()
    Xp = pool[[f"f_{f}" for f in feats]].to_numpy()
    D = np.sqrt(((Xt[:, None, :] - Xp[None, :, :]) ** 2).sum(-1))
    r, c = linear_sum_assignment(D)
    col = np.empty(len(target), int)
    col[r] = c
    return col, D


def draws_wor(D, n_draws):
    """Random matched lists without replacement: in a random order, each target surname takes one
    of its K_NN nearest still-unused pool surnames. Pre-allocated (INV-17)."""
    n, P = D.shape
    out = np.empty((n_draws, n), int)
    for r in range(n_draws):
        used = np.zeros(P, bool)
        for i in RNG.permutation(n):
            row = np.where(used, np.inf, D[i])
            pick = RNG.choice(np.argpartition(row, K_NN)[:K_NN])
            out[r, i] = pick
            used[pick] = True
    return out


rp, rm = ros.Pat.map(dac).to_numpy(), ros.Mat.map(dac).to_numpy()
leg_codes = pd.factorize(ros.nm)[0]


def flags(sset):
    return np.array([(p in sset) or (m in sset) for p, m in zip(rp, rm)])


def draw_shares(draws, names, mask):
    """Congress share for each random draw (vectorised through name -> index maps)."""
    idx = {s: i for i, s in enumerate(names)}
    pi = np.array([idx.get(p, len(names)) for p in rp[mask]])
    mi = np.array([idx.get(m, len(names)) for m in rm[mask]])
    member = np.zeros((draws.shape[0], len(names) + 1), bool)
    member[np.arange(draws.shape[0])[:, None], draws] = True
    member[:, -1] = False
    return 100 * (member[:, pi] | member[:, mi]).mean(1)


def boot_share(flag, mask, weights=None):
    """Legislator-cluster bootstrap of a Congress share (%) over rows in mask; optional per-row
    weights (population-share denominators) turn it into a ratio of weighted means."""
    lc = pd.factorize(leg_codes[mask])[0]
    L = lc.max() + 1
    X_n = np.bincount(lc, minlength=L).astype(float)
    X_f = np.bincount(lc, weights=flag[mask], minlength=L)
    X_w = np.bincount(lc, weights=weights[mask], minlength=L) if weights is not None else None
    W = RNG.multinomial(L, np.full(L, 1 / L), size=N_BOOT).astype(float)
    share_b = 100 * (W @ X_f) / (W @ X_n)
    point = 100 * X_f.sum() / X_n.sum()
    if X_w is None:
        return point, share_b
    popw_b = (W @ X_w) / (W @ X_n)                    # term-weighted population share, %
    return point / (X_w.sum() / X_n.sum()), share_b / popw_b


# ---- 7c. build lists per gate ----------------------------------------------------------------
ARMS = {"ses_only": ["ses", "bearers"], "ses_only_early": ["ses", "bearers", "early"],
        "history_only": ["bearers"]}
LISTS = {"enduring_298": ELITE}
ses65 = nse.mean_nse >= 65
LISTS["ses65_all"] = set(nse.loc[ses65, "s"])
LISTS["ses65_not_attested"] = set(nse.loc[ses65 & ~nse.att_full & ~nse.is_elite, "s"])
e_mask_early = (ros.era2 == "1834-1890").to_numpy(dtype=bool)


def bal_row(gate, arm, target, matched, pool_size, n_unique):
    fl = flags(set(matched.s))
    t_1834 = int(fl[e_mask_early].sum())
    return {"gate": gate, "list": arm, "pool_size": pool_size, "n_slots": len(target), "n_unique": n_unique,
            "mean_ses_target": target.mean_nse.mean(), "mean_ses_list": matched.mean_nse.mean(),
            "bearers_target": int(target.n_occ.sum()), "bearers_list": int(matched.n_occ.sum()),
            "early_per100k_target": target.early_per100k.sum(), "early_per100k_list": matched.early_per100k.sum(),
            "terms_1834_1890": t_1834, "terms_1834_1890_per_surname": t_1834 / n_unique,
            "terms_1834_1890_per_1k_bearers_2020": 1000 * t_1834 / matched.n_occ.sum()}


def build_gate(gate):
    """Enduring list restricted to one gate + its three matched placebo arms (1:1, no replacement)."""
    att = nse[f"att_{gate}"]
    target = nse[nse.is_elite & att].reset_index(drop=True)
    pools = {"ses_only": nse[~nse.is_elite & ~nse.is_common & ~att].reset_index(drop=True),
             "ses_only_early": nse[~nse.is_elite & ~nse.is_common & ~att].reset_index(drop=True),
             "history_only": nse[~nse.is_elite & ~nse.is_common & att & (nse.mean_nse < 65)].reset_index(drop=True)}
    fits = {arm: match_wor(target, pools[arm], feats) for arm, feats in ARMS.items()}
    matched = {arm: pools[arm].iloc[fits[arm][0]] for arm in ARMS}
    n_draws = N_PLACEBO if gate == "full" else N_PLACEBO_VARIANT
    lists = {f"enduring_{gate}": set(target.s), **{f"{arm}_{gate}": set(matched[arm].s) for arm in ARMS}}
    draws = {f"{arm}_{gate}": (draws_wor(fits[arm][1], n_draws), pools[arm].s.to_numpy()) for arm in ARMS}
    bal = ([bal_row(gate, "enduring", target, target, len(target), len(target))]
           + [bal_row(gate, arm, target, matched[arm], len(pools[arm]), matched[arm].s.nunique()) for arm in ARMS])
    return lists, draws, bal


BUILT = {g: build_gate(g) for g in GATES}
LISTS.update({k: v for g in BUILT for k, v in BUILT[g][0].items()})
DRAWS = {k: v for g in BUILT for k, v in BUILT[g][1].items()}
BAL = [r for g in BUILT for r in BUILT[g][2]]
BAL = pd.DataFrame(BAL)
BAL.to_csv(OUT / "a2_placebo_balance.csv", index=False)
print(BAL.round(2).to_string(index=False))

# ---- 7d. Congress shares by era, late/early ratios (cluster CI + draw range) -------------------
ERA_ALL = ["1811-1833"] + ERA_LABELS
era_mask = {era: (ros.era2 == era).to_numpy(dtype=bool) for era in ERA_ALL}
FLAGS = {k: flags(v) for k, v in LISTS.items()}


def era_series(k):
    row = {"list": k, **{f"share_{e}": 100 * FLAGS[k][era_mask[e]].mean() for e in ERA_ALL}}
    if k in DRAWS:
        dr, nm_ = DRAWS[k]
        s = {e: draw_shares(dr, nm_, era_mask[e]) for e in ["1834-1890", "1990-2020"]}
        rat = s["1990-2020"] / s["1834-1890"]
        rat = rat[np.isfinite(rat)]
        row.update({"draws": dr.shape[0], "draw_mean_1834_1890": s["1834-1890"].mean(),
                    "draw_mean_1990_2020": s["1990-2020"].mean(),
                    "draw_range_ratio_p2.5": np.percentile(rat, 2.5),
                    "draw_range_ratio_p97.5": np.percentile(rat, 97.5),
                    "draws_declining_pct": 100 * np.mean(rat < 1)})
    pe, be = boot_share(FLAGS[k].astype(float), era_mask["1834-1890"])
    pl, bl = boot_share(FLAGS[k].astype(float), era_mask["1990-2020"])
    with np.errstate(divide="ignore", invalid="ignore"):
        rb = bl / be
    rb = rb[np.isfinite(rb)]
    row.update({"ratio_late_early": pl / pe if pe > 0 else np.nan,
                "cluster_ci_lo": np.percentile(rb, 2.5), "cluster_ci_hi": np.percentile(rb, 97.5)})
    return row


ps_era = pd.DataFrame([era_series(k) for k in LISTS])
ps_era.to_csv(OUT / "a2_placebo_series_by_era.csv", index=False)
print(ps_era.round(3).to_string(index=False))

dec_keys = sorted(int(d) for d in (ros.Start.dropna() // 10 * 10).unique())
dec_mask = {d: ((ros.Start // 10 * 10) == d).fillna(False).to_numpy(dtype=bool) for d in dec_keys}
FULL_KEYS = ["enduring_298", "ses_only_full", "ses_only_early_full", "history_only_full", "ses65_all",
             "ses65_not_attested"]
ps_dec = pd.DataFrame([{"decade": d, "n_terms": int(m.sum()),
                        **{f"{k}_pct": 100 * FLAGS[k][m].mean() for k in FULL_KEYS},
                        **{f"{k}_draw_lo": np.percentile(draw_shares(*DRAWS[k], m), 2.5)
                           for k in ["ses_only_full", "history_only_full"]},
                        **{f"{k}_draw_hi": np.percentile(draw_shares(*DRAWS[k], m), 97.5)
                           for k in ["ses_only_full", "history_only_full"]}}
                       for d, m in dec_mask.items() if m.sum() >= 50])
ps_dec.to_csv(OUT / "a2_placebo_series_by_decade.csv", index=False)

# ---- 7e. over-representation ratios with population denominators (entrants 1930 on) ----------
# Congress share of terms starting in decade D  /  list's share of registrations in [D-50, D-30)
# (legislators' approximate birth cohorts). Registrations start 1884/85, so D >= 1930; the 1930s
# window (1880-1899) is only partly covered (1884-1899). Congress side: legislator-cluster bootstrap.
OR_DECADES = [d for d in dec_keys if 1930 <= d <= 2010]


def pop_share_window(counts, d):
    lo, hi = d - 50 - Y0, d - 30 - Y0
    lo = max(lo, 0)
    return 100 * counts[lo:hi].sum() / BIRTHS[lo:hi].sum()


POPC = {k: pop_by_year(v) for k, v in LISTS.items()}
dec_of_row = (ros.Start // 10 * 10).fillna(0).astype(int).to_numpy()
OR_WIN = {"1930-1973": (dec_of_row >= 1930) & (dec_of_row <= 1970) & (ros.Start <= 1973).fillna(False).to_numpy(dtype=bool),
          "1990-2020": era_mask["1990-2020"]}


def overrep_rows(k):
    popd = {d: pop_share_window(POPC[k], d) for d in OR_DECADES}
    wrow = np.array([popd.get(d, np.nan) for d in dec_of_row])      # per-row denominator (%)
    rows = [{"list": k, "unit": "decade", "key": str(d), "congress_share": 100 * FLAGS[k][dec_mask[d]].mean(),
             "pop_share": popd[d], "overrep": 100 * FLAGS[k][dec_mask[d]].mean() / popd[d] if popd[d] > 0 else np.nan}
            for d in OR_DECADES if dec_mask[d].sum() > 0]
    boots = {w: boot_share(FLAGS[k].astype(float), m, weights=np.nan_to_num(wrow)) for w, m in OR_WIN.items()}
    win_rows = [{"list": k, "unit": "window", "key": w, "congress_share": 100 * FLAGS[k][m].mean(),
                 "pop_share": float(np.average(np.nan_to_num(wrow[m]))), "overrep": boots[w][0],
                 "ci_lo": np.percentile(boots[w][1][np.isfinite(boots[w][1])], 2.5),
                 "ci_hi": np.percentile(boots[w][1][np.isfinite(boots[w][1])], 97.5)}
                for w, m in OR_WIN.items()]
    with np.errstate(divide="ignore", invalid="ignore"):
        rb = boots["1990-2020"][1] / boots["1930-1973"][1]
    rb = rb[np.isfinite(rb)]
    late, early_ = boots["1990-2020"][0], boots["1930-1973"][0]
    ratio_row = {"list": k, "unit": "ratio", "key": "overrep 1990-2020 / 1930-1973",
                 "overrep": late / early_ if early_ > 0 else np.nan,
                 "ci_lo": np.percentile(rb, 2.5) if len(rb) else np.nan,
                 "ci_hi": np.percentile(rb, 97.5) if len(rb) else np.nan}
    return rows + win_rows + [ratio_row]


orr = pd.DataFrame([r for k in LISTS for r in overrep_rows(k)])
orr.to_csv(OUT / "a2_placebo_overrep.csv", index=False)
print(orr[orr.unit != "decade"].round(3).to_string(index=False))

# =============================================================================================
# 8. FIGURES + BARE TABULAR
# =============================================================================================
plt.rcParams.update({"font.family": "serif", "font.size": 10})
fig, axes = plt.subplots(2, 2, figsize=(11, 8))
x = np.arange(len(ERA_LABELS))
for ax, marker, ttl in [(axes[0, 0], "club", "A. Club de la Unión membership"),
                        (axes[0, 1], "school", "B. Elite private secondary school")]:
    t = mk[(mk.era_def == "first_entry") & (mk.marker == marker)].set_index("era").reindex(ERA_LABELS)
    for j, g in enumerate(GROUPS):
        r = t[f"rate_{g}"].to_numpy()
        err = np.vstack([r - t[f"lo_{g}"].to_numpy(), t[f"hi_{g}"].to_numpy() - r])
        ax.bar(x + (j - 1) * 0.27, r, 0.27, yerr=err, capsize=3, color=GROUP_COL[g], alpha=.85,
               hatch=GROUP_HATCH[g], edgecolor="white", label=f"{g.capitalize()} surnames")
    ax.set_xticks(x)
    ax.set_xticklabels(ERA_LABELS)
    ax.set_ylabel("Share with marker (%)")
    ax.set_xlabel("Era of first entry")
    ax.set_title(ttl, loc="left", fontsize=10)
    ax.legend(frameon=False, fontsize=8)
ax = axes[1, 0]
dplot = pd.concat([dec, pd.DataFrame({"decade": [1980]})]).sort_values("decade").reset_index(drop=True)
sen = dplot.elite_pct_senate.where(dplot.usable.fillna(False).astype(bool))
cha = dplot.elite_pct_chamber.where(dplot.n_chamber.fillna(0) > 0)
ax.plot(dplot.decade, cha, ls="--", marker="o", ms=3, color="#7f7f7f", label="Chamber of Deputies")
ax.plot(dplot.decade, sen, ls="-", marker="s", ms=3, color="black", label="Senate (decades with ≥20 terms)")
ax.axvspan(1973, 1990, color="grey", alpha=.12)
ax.set_xlabel("Decade of term start")
ax.set_ylabel("Enduring-elite share (%)")
ax.set_title("C. Known groups: Senate vs Chamber", loc="left", fontsize=10)
ax.legend(frameon=False, fontsize=8)
ax = axes[1, 1]
b = pb[(pb.mapping == "12b_plus_ext") & pb.window.isin(ERA_LABELS)].set_index("window").reindex(ERA_LABELS)
for j, bl in enumerate(BLOCS):
    r = b[f"elite_pct_{bl}"].to_numpy(float)
    lo = b.get(f"cb_lo_{bl}", pd.Series(np.nan, index=b.index)).to_numpy(float)
    hi = b.get(f"cb_hi_{bl}", pd.Series(np.nan, index=b.index)).to_numpy(float)
    err = np.vstack([np.nan_to_num(r - lo), np.nan_to_num(hi - r)])
    ax.bar(x + (j - 1) * 0.27, r, 0.27, yerr=err, capsize=3, color=BLOC_COL[bl], alpha=.85,
           hatch=BLOC_HATCH[bl], edgecolor="white", label=f"{BLOC_LAB[bl]} bloc")
ax.set_xticks(x)
ax.set_xticklabels(ERA_LABELS)
ax.set_xlabel("Era of term start")
ax.set_ylabel("Enduring-elite share (%)")
ax.set_title("D. Known groups: party blocs (legislator-clustered 95% CIs)", loc="left", fontsize=10)
ax.legend(frameon=False, fontsize=8)
for a in axes.ravel():
    for s in ["top", "right"]:
        a.spines[s].set_visible(False)
    a.grid(alpha=.2, lw=.5)
fig.tight_layout()   # no overall title (INV-12)
fig.savefig(FIG / "a2_validation_by_period.pdf", bbox_inches="tight")
fig.savefig(FIG / "a2_validation_by_period.png", dpi=200, bbox_inches="tight")
plt.close(fig)

fig, (ax, ax2) = plt.subplots(1, 2, figsize=(13, 4.8), gridspec_kw={"width_ratios": [1.35, 1]})
pdp = pd.concat([ps_dec, pd.DataFrame({"decade": [1980]})]).sort_values("decade")
STY = {"enduring_298": ("-", GROUP_COL["elite"], "Enduring elite (298)"),
       "ses_only_full": ("--", "#d95f02", "SES-only placebo (matched 1:1)"),
       "ses_only_early_full": ((0, (5, 1, 1, 1)), "#e7298a", "SES-only placebo, also matched on 1885-1904 presence"),
       "history_only_full": (":", "#1b9e77", "History-only placebo (matched 1:1)"),
       "ses65_all": ("-.", "#555555", "All SES≥65 surnames"),
       "ses65_not_attested": ((0, (1, 3)), "#555555", "SES≥65, not 19th-c attested")}
for k, (ls_, c_, lab) in STY.items():
    ax.plot(pdp.decade, pdp[f"{k}_pct"], ls=ls_, color=c_, lw=1.9, label=lab)
for k, c_ in [("ses_only_full", "#d95f02"), ("history_only_full", "#1b9e77")]:
    ax.fill_between(pdp.decade, pdp[f"{k}_draw_lo"], pdp[f"{k}_draw_hi"], color=c_, alpha=.15, lw=0)
ax.axvspan(1973, 1990, color="grey", alpha=.12)
ax.set_xlabel("Decade of term start")
ax.set_ylabel("Share of legislator-terms (%)")
ax.set_title("A. Congress share (shading: 95% draw range)", loc="left", fontsize=10)
odp = orr[orr.unit == "decade"].assign(decade=lambda d: d.key.astype(int))
for k, (ls_, c_, lab) in STY.items():
    o = odp[odp.list == k].set_index("decade").reindex(sorted(set(odp.decade) | {1980}))
    ax2.plot(o.index, o.overrep, ls=ls_, color=c_, lw=1.9, marker="o", ms=2.5, label=lab)
ax2.axhline(1, color="black", lw=.8)
ax2.set_yscale("log")
ax2.axvspan(1973, 1990, color="grey", alpha=.12)
ax2.set_xlabel("Decade of term start")
ax2.set_ylabel("Over-representation (×, log scale)")
ax2.set_title("B. Over-representation vs births 30-50 years earlier", loc="left", fontsize=10)
for a in (ax, ax2):
    a.grid(alpha=.2, lw=.5)
    for sp_ in ["top", "right"]:
        a.spines[sp_].set_visible(False)
fig.legend(*ax.get_legend_handles_labels(), frameon=False, fontsize=8, loc="lower center", ncol=3)
fig.tight_layout(rect=[0, 0.12, 1, 1])
fig.savefig(FIG / "a2_placebo_series.pdf", bbox_inches="tight")
fig.savefig(FIG / "a2_placebo_series.png", dpi=200, bbox_inches="tight")
plt.close(fig)


def rr_txt(r, tag):
    """Ratio [CI]; zero-cell (Haldane-corrected) ratios reported as not estimable."""
    if getattr(r, f"rr_e_{tag}_zero_cell"):
        return "n.e."
    return f"{getattr(r, f'rr_e_{tag}'):.1f} [{getattr(r, f'rr_e_{tag}_lo'):.1f}, {getattr(r, f'rr_e_{tag}_hi'):.1f}]"


tex_rows = [
    f"{lab if i == 0 else ''} & {r.era.replace('-', '--')} & {r.n_elite} & {r.rate_elite:.1f} & "
    f"{r.rate_common:.1f} & {r.rate_other:.1f} & {rr_txt(r, 'common')} & {rr_txt(r, 'other')} \\\\"
    for marker, lab in [("club", "Club de la Uni\\'on"), ("school", "Elite private school")]
    for i, r in enumerate(mk[(mk.era_def == "first_entry") & (mk.marker == marker)].itertuples())]
tex = ([r"\begin{tabular}{llrrrrrc}", r"\toprule",
        r"Marker & Era & $N_E$ & Elite \% & Common \% & Other \% & Elite/Common & Elite/Other \\", r"\midrule"]
       + tex_rows[:4] + [r"\midrule"] + tex_rows[4:] + [r"\bottomrule", r"\end{tabular}"])
(OUT / "a2_markers_by_era.tex").write_text("\n".join(tex) + "\n")
print(f"\nsaved outputs to {OUT} and figures to {FIG}")
