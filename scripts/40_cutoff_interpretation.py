"""40 -- R&R item A4 (Referee 1, comment R1.4): substantive reading of the two
Criterion-1 cutoffs of the enduring-elite measure.

Route 1a (SES index >= 65, >= 30 bearers): what share of the 2020 electoral roll
(persons) carries a passing surname, and where 65 sits in the person-level
distribution of the surname index (context cutoffs 60 and 70). Same quantities
for the final 298-surname list (after the historical gate).

Route 1b (business over-representation >= 8, >= 5 appearances): how many surnames
clear it, what share of the 5,411 CMF directors/managers carry one, what share
carry one of the 13 route-1b additions, and what share carry any of the 298
(with the implied over-representation of the enduring elite among business
leaders, token- and person-level).

Descriptive only: no estimation, no stochastic element -> no seed (INV-14).
Run from anywhere; paths are anchored on the repo root (INV-16). Large raw
sources live OUTSIDE the repo and are resolved exactly as in
_measure_helpers.py / 01 / 03 (RAW_DATA_ROOT, DATOS_ROOT; env-overridable):
  padron 2020 (persons) : DATOS_ROOT/geo_padron/geo_padron_2020/padron_2020_nse_surnames.csv
  Registro Civil births : DATOS_ROOT/Registro Civil/HISTORICO/aaaa_appat_apmat_nac_*.csv
  CMF business leaders  : BIZ_ROOT/personas_{directores,gerentes}_empresas.csv
                          (BIZ_ROOT default: RAW_DATA_ROOT/../mobility_surnames/data/chile/clean)
  given-name flags,
  historical attestation: data/processed/business_{elite_candidates,x_historical}.csv (shipped)
In-repo inputs: data/processed/surname_nse.csv, data/processed/enduring_elite_FINAL.csv.

Outputs (output/rnr2026/):
  A4_cutoff_interpretation.csv      long table: block, quantity, value, numerator, denominator
  A4_ses_percentiles.csv            where 60/65/70 sit in three distributions
  A4_business_ratio_check.csv       recomputed vs deposited per-surname ratios (validation)
  A4_cutoff_interpretation_table.tex bare tabular (INV-13), not wired into the paper
  A4_roll_comunas.csv               comunas covered by the geocoded roll (persons per comuna)
  A4_298_business_ratios.csv        per-surname business ratio for the 298 with >= 5 appearances
  A4_route1b_attestation_cells.csv  raw historical cells that attest each route-1b surname
  A4_route1b_context_cutoffs.csv    route-1b set size and coverage at ratio 5 / 8 / 10

Inherited dependency: the given-name flags and the route-1b historical attestation are
read from data/processed/business_*.csv (shipped copies, as script 29 does); they
are derived files produced by explorations/business_leaders_gate/scripts/.
"""

import glob
import os
import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from _measure_helpers import CENSO, XLSX, toks, require, skip  # raw 19c sources, same resolution

# ---------------------------------------------------------------- paths ----
REPO = Path(__file__).resolve().parents[1]
RAW_DATA_ROOT = Path(os.environ.get("RAW_DATA_ROOT", REPO.parent))
DATOS_ROOT = Path(os.environ.get("DATOS_ROOT", RAW_DATA_ROOT.parent.parent))
BIZ_ROOT = Path(
    os.environ.get(
        "BIZ_ROOT",
        RAW_DATA_ROOT.parent / "mobility_surnames" / "data" / "chile" / "clean",
    )
)
PADRON = DATOS_ROOT / "geo_padron" / "geo_padron_2020" / "padron_2020_nse_surnames.csv"
REGCIV_GLOB = str(DATOS_ROOT / "Registro Civil" / "HISTORICO" / "aaaa_appat_apmat_nac_*.csv")
BIZ_FILES = [
    BIZ_ROOT / "personas_directores_empresas.csv",
    BIZ_ROOT / "personas_gerentes_empresas.csv",
]
SES_FILE = REPO / "data" / "processed" / "surname_nse.csv"
FINAL_FILE = REPO / "data" / "processed" / "enduring_elite_FINAL.csv"
BIZ_CAND_FILE = REPO / "data" / "processed" / "business_elite_candidates.csv"   # shipped (R&R round 2)
BIZ_HIST_FILE = REPO / "data" / "processed" / "business_x_historical.csv"      # shipped (R&R round 2)
OUT = REPO / "output" / "rnr2026"
# R&R round 2: non-redistributed inputs absent -> exit with SKIP_CODE (3), nothing written.
require([PADRON, CENSO, XLSX, *BIZ_FILES], "padron 2020 / 1874 censo / elite workbook / CMF business registry")
if not glob.glob(REGCIV_GLOB):
    skip(f"no Registro Civil files at {REGCIV_GLOB}")
OUT.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------ parameters ----
SES_CUT = 65.0  # Route 1a cutoff (headline)
MIN_BEARERS = 30  # Route 1a bearer floor (n_occ, paternal + maternal slots)
CONTEXT_CUTS = (60.0, 65.0, 70.0)
OVERREP_CUT = 8.0  # Route 1b ratio cutoff
OVERREP_CONTEXT = (5.0, 8.0, 10.0)
MIN_APPEAR = 5  # Route 1b appearance floor
MISSING_TOKENS = {"", "NAN", "NA"}

# --------------------------------------------------------- normalisation ----
_DAC_CACHE: dict[str, str] = {}


def dac(s: object) -> str:
    """Pipeline normalisation (01/02/03): NFKD -> ASCII -> upper -> strip."""
    raw = str(s)
    hit = _DAC_CACHE.get(raw)
    if hit is None:
        hit = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode()
        hit = hit.upper().strip()
        _DAC_CACHE[raw] = hit
    return hit


def match_key(s: object) -> str:
    """Cross-source key: dac + hyphen/underscore -> space, whitespace collapsed.

    Needed because the same compound surname is written GARCIA-HUIDOBRO (padron,
    final list), GARCIA_HUIDOBRO (CMF registry) and GARCIA HUIDOBRO (Registro
    Civil). Used ONLY to match the 298 / 13 lists across sources.
    """
    return re.sub(r"\s+", " ", re.sub(r"[-_]", " ", dac(s))).strip()


def clean_series(x: pd.Series) -> pd.Series:
    """Exactly the vectorised cleaner of script 01 (keys of surname_nse.csv)."""
    return (
        x.astype(str)
        .str.normalize("NFKD")
        .str.encode("ascii", "ignore")
        .str.decode("ascii")
        .str.upper()
        .str.strip()
    )


def pct(num: float, den: float) -> float:
    """Percentage, guarded against a zero denominator."""
    return float("nan") if den <= 0 else 100.0 * float(num) / float(den)


def safe_ratio(num: float, den: float) -> float:
    """num / den, NaN when the denominator is zero, negative or NaN."""
    return float(num) / float(den) if (den == den and den > 0) else float("nan")


# ================================================================ inputs ====
ses = pd.read_csv(SES_FILE)
ses["surname"] = ses["surname"].astype(str)
NSE = dict(zip(ses["surname"], ses["mean_nse"]))
NOCC = dict(zip(ses["surname"], ses["n_occ"]))

final = pd.read_csv(FINAL_FILE)
final["is_biz_route"] = final["sources"].fillna("").str.contains("business_gate")
K298 = set(final["surname"].map(match_key))
K13 = set(final.loc[final["is_biz_route"], "surname"].map(match_key))
K285 = set(final.loc[~final["is_biz_route"], "surname"].map(match_key))
assert len(final) == 298 and len(K298) == 298, "final list is not 298 unique keys"
assert len(K13) == 13 and len(K285) == 285
# every SES-route surname should itself clear route 1a
ses_route = final.loc[~final["is_biz_route"]]
n_285_below_cut = int(np.sum(ses_route["mean_nse"] < SES_CUT))
n_285_below_floor = int(np.sum(ses_route["n_holders"] < MIN_BEARERS))

# ====================================== BLOCK 1: Route 1a, SES >= 65 ========
# (a) surname counts
n_surnames_all = len(ses)
is_floor = ses["n_occ"] >= MIN_BEARERS
n_surnames_floor = int(is_floor.sum())
n_pass = {c: int(((ses["mean_nse"] >= c) & is_floor).sum()) for c in CONTEXT_CUTS}
pass_sets = {
    c: set(ses.loc[(ses["mean_nse"] >= c) & is_floor, "surname"]) for c in CONTEXT_CUTS
}
pass_keys_65 = {match_key(s) for s in pass_sets[SES_CUT]}

# (b)-(d) persons on the roll
pad = pd.read_csv(
    PADRON, usecols=["comuna", "paterno", "materno", "new_nse"], dtype={"comuna": str}
)
n_roll = len(pad)
n_comunas = pad["comuna"].nunique()
(
    pad["comuna"].value_counts().rename_axis("comuna").reset_index(name="n_persons")
    .sort_values("comuna")
    .to_csv(OUT / "A4_roll_comunas.csv", index=False)
)
pat = clean_series(pad["paterno"])
mat = clean_series(pad["materno"])
own_nse = pd.to_numeric(pad["new_nse"], errors="coerce")
pat_ses = pat.map(NSE)
mat_ses = mat.map(NSE)
pat_nocc = pat.map(NOCC).fillna(0)
mat_nocc = mat.map(NOCC).fillna(0)
n_pat_missing = int(pat.isin(MISSING_TOKENS).sum())
n_mat_missing = int(mat.isin(MISSING_TOKENS).sum())

share_pat = {}
share_either = {}
share_pat_noflr = {}
for c in CONTEXT_CUTS:
    pass_pat = (pat_ses >= c) & (pat_nocc >= MIN_BEARERS)
    pass_mat = (mat_ses >= c) & (mat_nocc >= MIN_BEARERS)
    share_pat[c] = (int(pass_pat.sum()), pct(pass_pat.sum(), n_roll))
    share_either[c] = (int((pass_pat | pass_mat).sum()), pct((pass_pat | pass_mat).sum(), n_roll))
    share_pat_noflr[c] = pct((pat_ses >= c).sum(), pat_ses.notna().sum())

# (c) where the cutoffs sit: three distributions
pat_ses_valid = pat_ses.dropna().to_numpy(dtype=np.float64)
own_valid = own_nse.dropna().to_numpy(dtype=np.float64)
ses_floor_vals = ses.loc[is_floor, "mean_nse"].to_numpy(dtype=np.float64)
pctl_rows = [
    {
        "cutoff": c,
        "pctile_person_paternal_surname_index": pct(np.sum(pat_ses_valid < c), pat_ses_valid.size),
        "pctile_person_own_residential_ses": pct(np.sum(own_valid < c), own_valid.size),
        "pctile_surname_level_floor30": pct(np.sum(ses_floor_vals < c), ses_floor_vals.size),
    }
    for c in CONTEXT_CUTS
]
pctl = pd.DataFrame(pctl_rows)
q_levels = np.array([0.50, 0.75, 0.90, 0.95, 0.99], dtype=np.float64)
q_pat = np.quantile(pat_ses_valid, q_levels)
q_own = np.quantile(own_valid, q_levels)
pctl.to_csv(OUT / "A4_ses_percentiles.csv", index=False)

# (d) the final 298 list on the roll
pat_k = pat.map(match_key)
mat_k = mat.map(match_key)
in298_pat = pat_k.isin(K298)
in298_either = in298_pat | mat_k.isin(K298)
in285_pat = pat_k.isin(K285)
in13_pat = pat_k.isin(K13)
roll_keys = set(pat_k) | set(mat_k)
n_298_found_on_roll = len(K298 & roll_keys)
pass65_pat = (pat_ses >= SES_CUT) & (pat_nocc >= MIN_BEARERS)
retained_298 = pct((pass65_pat & in298_pat).sum(), pass65_pat.sum())
retained_285 = pct((pass65_pat & in285_pat).sum(), pass65_pat.sum())
ses_298_bearers = pat_ses[in298_pat].dropna().to_numpy(dtype=np.float64)
med_298 = float(np.median(ses_298_bearers))
pctile_med_298 = pct(np.sum(pat_ses_valid < med_298), pat_ses_valid.size)
own_298_med = float(np.median(own_nse[in298_pat].dropna()))
pctile_own_298_med = pct(np.sum(own_valid < own_298_med), own_valid.size)

# ============================ BLOCK 2: Route 1b, over-representation >= 8 ====
# business leaders (pooled rows, as in the exploration and the paper's 5,411)
biz = pd.concat(
    [pd.read_csv(f, dtype=str, keep_default_na=False) for f in BIZ_FILES],
    ignore_index=True,
)
n_biz = len(biz)
n_biz_unique = biz["fullname"].nunique()
biz_pat_tok = biz["pat"].map(lambda v: dac(v).replace("_", " ").strip())
biz_mat_tok = biz["mat"].map(lambda v: dac(v).replace("_", " ").strip())
biz_counts = Counter(
    v for v in pd.concat([biz_pat_tok, biz_mat_tok]) if v not in MISSING_TOKENS
)
biz_total = sum(biz_counts.values())

# Registro Civil births. Pass 1 (tokens): the exploration's line parser, all rows,
# both slots -> the ~45M-token denominator of the per-surname ratio. Pass 2
# (persons, below): script-03 filter [Chilean, year >= 1884].
rc_files = sorted(glob.glob(REGCIV_GLOB))
assert rc_files, f"no Registro Civil files at {REGCIV_GLOB}"


def registry_rows(files: list[str]):
    """Yield split rows (>= 3 fields) of the Registro Civil files, header skipped."""
    for path in files:
        with open(path, "r", encoding="latin-1") as fh:
            fh.readline()
            for line in fh:
                parts = line.rstrip("\n").split(";")
                if len(parts) >= 3:
                    yield parts


pop_counts: Counter = Counter()
n_rc_rows = 0
for parts in registry_rows(rc_files):
    n_rc_rows += 1
    pop_counts[dac(parts[1])] += 1
    pop_counts[dac(parts[2])] += 1
for tok in MISSING_TOKENS:
    pop_counts.pop(tok, None)
pop_total = sum(pop_counts.values())

# per-surname ratios, replicating the exploration's candidate table
cand_rows = [
    (s, nb, pop_counts.get(s, 0))
    for s, nb in biz_counts.items()
    if nb >= MIN_APPEAR
]
cand = pd.DataFrame(cand_rows, columns=["surname", "n_leaders", "pop_count"])
n_ge5_zero_pop = int((cand["pop_count"] == 0).sum())
cand = cand[cand["pop_count"] > 0].copy()
cand["overrep_ratio"] = (cand["n_leaders"] / biz_total) / (cand["pop_count"] / pop_total)
dep = pd.read_csv(BIZ_CAND_FILE)
chk = cand.merge(
    dep[["surname", "n_leaders", "pop_count", "overrep_ratio", "likely_given_name"]],
    on="surname",
    how="outer",
    suffixes=("", "_dep"),
    indicator=True,
)
chk.to_csv(OUT / "A4_business_ratio_check.csv", index=False)
n_chk_mismatch_rows = int((chk["_merge"] != "both").sum())
max_ratio_rel_diff = float(
    np.nanmax(np.abs(chk["overrep_ratio"] / chk["overrep_ratio_dep"] - 1.0))
)
cand = cand.merge(dep[["surname", "likely_given_name"]], on="surname", how="left")
cand["likely_given_name"] = cand["likely_given_name"].fillna(False).astype(bool)

is_c8 = (cand["overrep_ratio"] >= OVERREP_CUT) & ~cand["likely_given_name"]
C8 = set(cand.loc[is_c8, "surname"])
n_c8 = len(C8)
n_c8_incl_given = int((cand["overrep_ratio"] >= OVERREP_CUT).sum())
C8_keys = {match_key(s) for s in C8}
# historically attested subset (deposited derivative of the 1874 censo + 13 registers)
bxh = pd.read_csv(BIZ_HIST_FILE)
att_keys = set(bxh["surname"].map(match_key))
n_c8_attested = len(att_keys & C8_keys)
n_c8_attested_in285 = len(att_keys & C8_keys & K285)
n_c8_attested_new = len((att_keys & C8_keys) - K285)
n_c8_in_ses65_pass = len(C8_keys & pass_keys_65)

bp_all = biz_pat_tok.map(match_key)
bm_all = biz_mat_tok.map(match_key)
k_counts: Counter = Counter()
for s, n in biz_counts.items():
    k_counts[match_key(s)] += n
n_298_ge5 = sum(1 for k in K298 if k_counts.get(k, 0) >= MIN_APPEAR)
n_298_ge5_c8 = len(K298 & C8_keys)
n_13_pass65 = len(K13 & pass_keys_65)
n_13_pass65_list = sorted(K13 & pass_keys_65)

# per-surname ratios for the 298 at key level (hyphen/space-insensitive)
kpop_counts: Counter = Counter()
for s, n in pop_counts.items():
    kpop_counts[match_key(s)] += n
route_of = dict(
    zip(final["surname"].map(match_key), np.where(final["is_biz_route"], "1b", "1a"))
)
r298 = pd.DataFrame(
    [
        (k, route_of[k], k_counts.get(k, 0), kpop_counts.get(k, 0))
        for k in sorted(K298)
        if k_counts.get(k, 0) >= MIN_APPEAR
    ],
    columns=["surname_key", "route", "n_leaders", "pop_count"],
)
r298["overrep_ratio"] = [
    safe_ratio(nb / biz_total, npop / pop_total)
    for nb, npop in zip(r298["n_leaders"], r298["pop_count"])
]
r298["in_ratio8_set"] = r298["surname_key"].isin(C8_keys)
r298["in_business_x_historical"] = r298["surname_key"].isin(att_keys)
r298 = r298.sort_values("overrep_ratio")
r298.to_csv(OUT / "A4_298_business_ratios.csv", index=False)
min_ratio_298_ge5 = float(r298["overrep_ratio"].min())
below8_298 = r298[r298["overrep_ratio"] < OVERREP_CUT]
gap_c8_not_attested = sorted((K298 & C8_keys) - att_keys)


def ctx_row(ov: float) -> dict[str, float]:
    """Route-1b set at ratio >= ov (>= 5 appearances, given names excluded)."""
    sel = (cand["overrep_ratio"] >= ov) & ~cand["likely_given_name"]
    keys_ov = {match_key(x) for x in cand.loc[sel, "surname"]}
    hit = bp_all.isin(keys_ov) | bm_all.isin(keys_ov)
    ceiling = safe_ratio(MIN_APPEAR / biz_total, ov)
    return {
        "overrep_cut": ov,
        "n_surnames": len(keys_ov),
        # business_x_historical.csv is pre-filtered at ratio >= 8, so below 8 this
        # count is capped at the ratio-8 value (a lower bound, not a re-test).
        "n_attested_in_bxh_capped_at_ratio8": len(keys_ov & att_keys),
        "pct_business_leaders_either": pct(hit.sum(), n_biz),
        "max_pop_token_share_pct_at_5_appearances": 100.0 * ceiling,
        "max_pop_tokens_at_5_appearances": ceiling * pop_total,
    }


ctx = pd.DataFrame([ctx_row(ov) for ov in OVERREP_CONTEXT])
ctx.to_csv(OUT / "A4_route1b_context_cutoffs.csv", index=False)

# person-level shares among business leaders
bp = biz_pat_tok.map(match_key)
bm = biz_mat_tok.map(match_key)


def biz_share(keys: set[str], either: bool = True) -> tuple[int, float]:
    """Count and % of the 5,411 business-leader rows carrying a surname in `keys`."""
    hit = bp.isin(keys) | bm.isin(keys) if either else bp.isin(keys)
    return int(hit.sum()), pct(hit.sum(), n_biz)


def biz_share_unique(keys: set[str]) -> float:
    """Same share after de-duplicating persons listed as both director and manager."""
    u = biz.assign(_p=bp, _m=bm).drop_duplicates("fullname")
    return pct((u["_p"].isin(keys) | u["_m"].isin(keys)).sum(), len(u))


s_c8 = biz_share(C8_keys)
s_c8_pat = biz_share(C8_keys, either=False)
s_13 = biz_share(K13)
s_13_pat = biz_share(K13, either=False)
s_att = biz_share(att_keys & C8_keys)
s_298 = biz_share(K298)
s_298_pat = biz_share(K298, either=False)
s_285 = biz_share(K285)
s_ses65 = biz_share(pass_keys_65)

# token-level implied over-representation of the 298 among business leaders
biz_tok_298 = sum(n for s, n in biz_counts.items() if match_key(s) in K298)
pop_tok_298 = sum(n for s, n in pop_counts.items() if match_key(s) in K298)
tokshare_biz_298 = pct(biz_tok_298, biz_total)
tokshare_pop_298 = pct(pop_tok_298, pop_total)
overrep_tok_298 = safe_ratio(tokshare_biz_298, tokshare_pop_298)

# person-level population share (pass 2: Chilean births >= 1884, script-03 convention)
_tok_flags: dict[str, tuple[bool, bool, bool, bool]] = {}
D298 = set(final["surname"].map(dac))  # script-03-style exact forms


def tok_flags(tok: str) -> tuple[bool, bool, bool, bool]:
    """(in 298, in 13, in ratio>=8 set, in 298 by exact dac) for a raw surname."""
    hit = _tok_flags.get(tok)
    if hit is None:
        k = match_key(tok)
        hit = (k in K298, k in K13, k in C8_keys, dac(tok) in D298)
        _tok_flags[tok] = hit
    return hit


n_rc_chl = n_rc_chl_298 = n_rc_chl_13 = n_rc_chl_c8 = n_rc_chl_298_exact = 0
for parts in registry_rows(rc_files):
    if len(parts) < 4 or not parts[3].strip().startswith("CHILEN"):
        continue
    try:
        yr = int(parts[0])
    except ValueError:
        continue
    if yr < 1884:
        continue
    n_rc_chl += 1
    fa = tok_flags(parts[1])
    fb = tok_flags(parts[2])
    n_rc_chl_298 += fa[0] or fb[0]
    n_rc_chl_13 += fa[1] or fb[1]
    n_rc_chl_c8 += fa[2] or fb[2]
    n_rc_chl_298_exact += fa[3] or fb[3]
popshare_298 = pct(n_rc_chl_298, n_rc_chl)
popshare_13 = pct(n_rc_chl_13, n_rc_chl)
popshare_c8 = pct(n_rc_chl_c8, n_rc_chl)
overrep_person_298 = safe_ratio(s_298[1], popshare_298)
overrep_person_298_vs_roll = safe_ratio(s_298[1], pct(in298_either.sum(), n_roll))
overrep_person_13 = safe_ratio(s_13[1], popshare_13)
overrep_person_c8 = safe_ratio(s_c8[1], popshare_c8)
# script 03 matches the list by exact dac (no hyphen/space folding)
popshare_298_exact = pct(n_rc_chl_298_exact, n_rc_chl)
hyphen_entries = sorted(x for x in final["surname"].map(dac) if "-" in x or " " in x)
dep_pop = pd.read_csv(REPO / "data" / "processed" / "pop_prevalence_by_year.csv")
dep_pop_share = pct(dep_pop["n_elite"].sum(), dep_pop["n_total"].sum())

# ---- raw historical cells attesting each route-1b surname -------------------
# business_x_historical.py:17,23 adds dac(cell) and toks(cell) for EVERY raw cell
# (xlsx: all cells; censo: Paterno/Materno of top-quartile landowners), with no
# length floor on the full-cell form and no given-name filter. Re-apply that test
# to the 13 surnames (in the form used in business_x_historical.csv) and keep the
# matching cells so the attestation can be inspected.
bx_form = {match_key(x): dac(x) for x in bxh["surname"]}
forms13 = {k: bx_form.get(k, k) for k in sorted(K13)}
cz = pd.read_csv(CENSO, encoding="latin-1")
cz["Avaluacion"] = pd.to_numeric(cz["Avaluacion"], errors="coerce")
cz_big = cz[cz["Avaluacion"] >= cz["Avaluacion"].quantile(0.75)]
censo_cells = [
    ("censo1874_top_quartile", str(v))
    for col in ["Paterno", "Materno"]
    for v in cz_big[col].dropna()
]
xlsx_cells = [
    (f"xlsx:{tab}", str(v))
    for tab, dfx in pd.read_excel(XLSX, sheet_name=None, header=None).items()
    for v in dfx.values.ravel()
    if str(v) != "nan"
]
att_cells = pd.DataFrame(
    [
        {
            "surname_key": k,
            "source": src,
            "match": "full_cell" if dac(cell) == form else "token",
            "cell": cell,
        }
        for src, cell in censo_cells + xlsx_cells
        for k, form in forms13.items()
        if dac(cell) == form or form in toks(cell)
    ],
    columns=["surname_key", "source", "match", "cell"],
)
att_cells.to_csv(OUT / "A4_route1b_attestation_cells.csv", index=False)
att_summary = (
    att_cells.groupby("surname_key")
    .agg(n_cells=("cell", "size"), n_sources=("source", "nunique"))
    .reindex(sorted(K13))
    .fillna(0)
)

# ================================================================ output ====
R = [
    # ---- block 1a
    ("1a", "surnames in surname_nse.csv (all)", n_surnames_all, None, None),
    ("1a", f"surnames with >= {MIN_BEARERS} bearers", n_surnames_floor, None, None),
    *[
        ("1a", f"surnames passing SES>={c:g} & >={MIN_BEARERS} bearers", n_pass[c],
         n_pass[c], n_surnames_floor)
        for c in CONTEXT_CUTS
    ],
    ("1a", "persons on geocoded 2020 roll (denominator)", n_roll, None, None),
    ("1a", "comunas represented on the roll file", n_comunas, None, None),
    ("1a", "persons with missing paternal surname", n_pat_missing, None, None),
    ("1a", "persons with missing maternal surname", n_mat_missing, None, None),
    ("1a", "person-level mean of own residential SES (new_nse)", float(own_nse.mean()),
     None, None),
    *[
        ("1b", f"% roll: paternal surname passes SES>={c:g}", share_pat[c][1],
         share_pat[c][0], n_roll)
        for c in CONTEXT_CUTS
    ],
    *[
        ("1b", f"% roll: paternal OR maternal passes SES>={c:g}", share_either[c][1],
         share_either[c][0], n_roll)
        for c in CONTEXT_CUTS
    ],
    *[
        ("1b", f"% roll: paternal index >= {c:g} (no bearer floor)", share_pat_noflr[c],
         None, None)
        for c in CONTEXT_CUTS
    ],
    *[
        ("1c", f"percentile of {r.cutoff:g}: person paternal-surname index",
         r.pctile_person_paternal_surname_index, None, None)
        for r in pctl.itertuples()
    ],
    *[
        ("1c", f"percentile of {r.cutoff:g}: person own residential SES",
         r.pctile_person_own_residential_ses, None, None)
        for r in pctl.itertuples()
    ],
    *[
        ("1c", f"percentile of {r.cutoff:g}: surname-level (>=30 bearers)",
         r.pctile_surname_level_floor30, None, None)
        for r in pctl.itertuples()
    ],
    *[
        ("1c", f"P{int(round(100 * q))} person paternal-surname index", float(v), None, None)
        for q, v in zip(q_levels, q_pat)
    ],
    *[
        ("1c", f"P{int(round(100 * q))} person own residential SES", float(v), None, None)
        for q, v in zip(q_levels, q_own)
    ],
    # ---- block 1d: final 298 list
    ("1d", "surnames in final list", 298, None, None),
    ("1d", "of which SES route (285) / business route (13)", 285, 13, None),
    ("1d", "SES-route surnames below SES 65 / below 30 bearers (check=0)",
     n_285_below_cut, n_285_below_floor, None),
    ("1d", "final-list surnames found on roll (either slot)", n_298_found_on_roll, None, None),
    ("1d", "% roll: paternal surname in 298", pct(in298_pat.sum(), n_roll),
     int(in298_pat.sum()), n_roll),
    ("1d", "% roll: paternal OR maternal in 298", pct(in298_either.sum(), n_roll),
     int(in298_either.sum()), n_roll),
    ("1d", "% roll: paternal in SES-route 285", pct(in285_pat.sum(), n_roll),
     int(in285_pat.sum()), n_roll),
    ("1d", "% roll: paternal in business-route 13", pct(in13_pat.sum(), n_roll),
     int(in13_pat.sum()), n_roll),
    ("1d", "% of SES>=65 paternal bearers kept by historical gate (SES-route 285)",
     retained_285, int((pass65_pat & in285_pat).sum()), int(pass65_pat.sum())),
    ("1d", "% of SES>=65 paternal bearers whose surname is in final 298 "
     "(incl. route-1b surnames that also clear SES>=65)", retained_298,
     int((pass65_pat & in298_pat).sum()), int(pass65_pat.sum())),
    ("1d", "median paternal-surname index among 298 bearers", med_298, None, None),
    ("1d", "percentile of that median in person index distribution", pctile_med_298,
     None, None),
    ("1d", "median own residential SES among 298 bearers", own_298_med, None, None),
    ("1d", "percentile of that median in own-SES distribution", pctile_own_298_med,
     None, None),
    # ---- block 2a
    ("2a", "business-leader rows (directors + managers)", n_biz, None, None),
    ("2a", "unique persons (by fullname)", n_biz_unique, None, None),
    ("2a", "business-leader surname tokens (pat + mat)", biz_total, None, None),
    ("2a", "Registro Civil surname tokens (pat + mat)", pop_total, None, None),
    ("2a", "298 surnames with >= 5 business appearances", n_298_ge5, None, None),
    ("2a", "  of which ratio >= 8", n_298_ge5_c8, None, None),
    ("2a", "min business over-rep ratio among 298 with >= 5 appearances",
     min_ratio_298_ge5, None, None),
    ("2a", "298 with >= 5 appearances and ratio < 8", len(below8_298), None, None),
    ("2a", "298 in ratio>=8 set but not in business_x_historical: "
     + ";".join(gap_c8_not_attested), len(gap_c8_not_attested), None, None),
    *[
        ("2a", f"route-1b context: ratio>={r.overrep_cut:g} & >={MIN_APPEAR}, "
         "n surnames / n attested (attestation file pre-filtered at ratio>=8)",
         r.n_surnames, r.n_attested_in_bxh_capped_at_ratio8, None)
        for r in ctx.itertuples()
    ],
    *[
        ("2a", f"route-1b context: % business leaders carrying ratio>={r.overrep_cut:g} "
         "surname (either)", r.pct_business_leaders_either, None, None)
        for r in ctx.itertuples()
    ],
    *[
        ("2a", f"ratio>={r.overrep_cut:g} at 5 appearances: max population token share (%) "
         "/ max population tokens", r.max_pop_token_share_pct_at_5_appearances,
         r.max_pop_tokens_at_5_appearances, None)
        for r in ctx.itertuples()
    ],
    ("2a", "Registro Civil rows read", n_rc_rows, None, None),
    ("2a", f"surnames with >= {MIN_APPEAR} appearances (pop>0)", len(cand), None, None),
    ("2a", f"surnames with >= {MIN_APPEAR} appearances but zero pop count (dropped)",
     n_ge5_zero_pop, None, None),
    ("2a", "rows recomputed vs deposited candidates not matched (check=0)",
     n_chk_mismatch_rows, None, None),
    ("2a", "max relative diff recomputed vs deposited ratio", max_ratio_rel_diff, None, None),
    ("2a", f"surnames ratio>={OVERREP_CUT:g} & >={MIN_APPEAR} (incl. given-name artifacts)",
     n_c8_incl_given, None, None),
    ("2a", f"surnames ratio>={OVERREP_CUT:g} & >={MIN_APPEAR} (excl. given names)", n_c8,
     None, None),
    ("2a", "  of which historically attested", n_c8_attested, None, None),
    ("2a", "  attested and already in SES-route 285", n_c8_attested_in285, None, None),
    ("2a", "  attested and new (= route-1b additions)", n_c8_attested_new, None, None),
    ("2a", "  of the ratio>=8 set, also passing SES>=65 & 30 bearers", n_c8_in_ses65_pass,
     None, None),
    # ---- block 2b-2d
    ("2b", "% business leaders carrying a ratio>=8 surname (either)", s_c8[1], s_c8[0], n_biz),
    ("2b", "% business leaders carrying a ratio>=8 surname (paternal)", s_c8_pat[1],
     s_c8_pat[0], n_biz),
    ("2b", "% business leaders: ratio>=8 AND attested surname (either)", s_att[1],
     s_att[0], n_biz),
    ("2b", "% business leaders ratio>=8 (either), unique persons", biz_share_unique(C8_keys),
     None, None),
    ("2b", "% Chilean births >=1884 carrying a ratio>=8 surname", popshare_c8, n_rc_chl_c8,
     n_rc_chl),
    ("2b", "implied person-level over-rep, ratio>=8 set", overrep_person_c8, None, None),
    ("2c", "route-1b surnames that also clear SES>=65 & 30 bearers", n_13_pass65,
     None, None),
    *[
        ("2c", f"raw historical cells attesting {k} (n cells / n sources)",
         int(r.n_cells), int(r.n_sources), None)
        for k, r in att_summary.iterrows()
    ],
    ("2c", "% business leaders carrying one of the 13 (either)", s_13[1], s_13[0], n_biz),
    ("2c", "% business leaders carrying one of the 13 (paternal)", s_13_pat[1], s_13_pat[0],
     n_biz),
    ("2c", "% Chilean births >=1884 carrying one of the 13", popshare_13, n_rc_chl_13,
     n_rc_chl),
    ("2c", "implied person-level over-rep, the 13", overrep_person_13, None, None),
    ("2d", "% business leaders carrying any of the 298 (either)", s_298[1], s_298[0], n_biz),
    ("2d", "% business leaders carrying any of the 298 (paternal)", s_298_pat[1],
     s_298_pat[0], n_biz),
    ("2d", "% business leaders any of 298, unique persons", biz_share_unique(K298), None, None),
    ("2d", "% business leaders carrying any SES-route 285 (either)", s_285[1], s_285[0], n_biz),
    ("2d", "% business leaders carrying any SES>=65 passing surname (either)", s_ses65[1],
     s_ses65[0], n_biz),
    ("2d", "% business surname tokens in 298", tokshare_biz_298, biz_tok_298, biz_total),
    ("2d", "% population surname tokens in 298", tokshare_pop_298, pop_tok_298, pop_total),
    ("2d", "implied token-level over-rep of 298 among business leaders", overrep_tok_298,
     None, None),
    ("2d", "% Chilean births >=1884 carrying any of 298", popshare_298, n_rc_chl_298, n_rc_chl),
    ("2d", "implied person-level over-rep of 298 (vs births)", overrep_person_298, None, None),
    ("2d", "implied person-level over-rep of 298 (vs 2020 roll, either)",
     overrep_person_298_vs_roll, None, None),
    ("7", "% Chilean births >=1884 with 298 surname, EXACT dac match (script-03 style)",
     popshare_298_exact, n_rc_chl_298_exact, n_rc_chl),
    ("7", "  vs hyphen-insensitive match_key (this script)", popshare_298, n_rc_chl_298,
     n_rc_chl),
    ("7", "deposited pop_prevalence_by_year.csv pooled elite share (%)", dep_pop_share,
     int(dep_pop["n_elite"].sum()), int(dep_pop["n_total"].sum())),
    ("7", "final-list entries with hyphen or space: " + ";".join(hyphen_entries),
     len(hyphen_entries), None, None),
]
res = pd.DataFrame(R, columns=["block", "quantity", "value", "numerator", "denominator"])
res.to_csv(OUT / "A4_cutoff_interpretation.csv", index=False)
pd.set_option("display.width", 200)
pd.set_option("display.max_colwidth", 80)
print(res.to_string(index=False))
print(pctl.to_string(index=False))
print("route-1b surnames already clearing SES>=65 & 30 bearers:", n_13_pass65_list)
print("comunas on roll file:", sorted(pad["comuna"].dropna().unique()))
print("298 with >=5 appearances and ratio < 8:")
print(below8_298.to_string(index=False))
print("in ratio>=8 set but not attested in business_x_historical:", gap_c8_not_attested)
print(ctx.to_string(index=False))
print(att_summary.to_string())
print(att_cells.groupby("surname_key").head(8).to_string(index=False))

# ------------------------------------------------ bare tabular (INV-13) ----
tex = "\n".join(
    [
        "\\begin{tabular}{lrr}",
        "\\toprule",
        " & Route 1a & Final list \\\\",
        " & (SES $\\geq$ 65) & (298 surnames) \\\\",
        "\\midrule",
        "\\multicolumn{3}{l}{\\textit{Panel A: 2020 Greater Santiago electoral roll (persons, 34 comunas)}} \\\\",
        f"Surnames & {n_pass[SES_CUT]:,} & 298 \\\\",
        f"Paternal surname in set (\\%) & {share_pat[SES_CUT][1]:.1f} & "
        f"{pct(in298_pat.sum(), n_roll):.1f} \\\\",
        f"Paternal or maternal in set (\\%) & {share_either[SES_CUT][1]:.1f} & "
        f"{pct(in298_either.sum(), n_roll):.1f} \\\\",
        "\\\\[0.3em]",
        "\\multicolumn{3}{l}{\\textit{Panel B: 5,411 business leaders (national CMF registry, 2023)}} \\\\",
        f"Carrying a surname in set (\\%) & {s_ses65[1]:.1f} & {s_298[1]:.1f} \\\\",
        "\\bottomrule",
        "\\end{tabular}",
    ]
)
(OUT / "A4_cutoff_interpretation_table.tex").write_text(tex + "\n", encoding="utf-8")
print(f"wrote {OUT}")
