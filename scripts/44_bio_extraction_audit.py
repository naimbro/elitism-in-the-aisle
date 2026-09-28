"""44 -- R&R 2026 item A6: audit of the v2 biography extraction (bcn_extract_v2.json).

Why. The online appendix (sec. "Methodological lesson") says the LLM recovers grounded fields
"at roughly 98--100% accuracy against hand checks". That figure came from the audit of the lost
v1 extraction (2026-06-20). The paper now uses the v2 re-extraction (2026-07-10,
claude-sonnet-5, new prompt; script 09c), which had no audit. This script draws a seeded,
stratified sample of 50 v2 biographies and scores the v2 fields against a REFERENCE CODING of the
archived page text (data/raw/bcn_wayback/*.txt).

Who coded the reference. The reference coding in output/rnr2026/A6_bio_audit_handcoded.csv
was produced by an AI model (Claude, acting as the project's coding agent), which read each
archived page in full and recorded the values BLIND to the v2 extraction (the blind template
below carries no extracted values). It is therefore not a human hand check. It is a second,
independent reading by a model of the same family as the extractor, so correlated errors are
possible. A random 15 of the 50 bios are exported for an optional check by the PI
(quality_reports/rnr2026/A6_PI_verification_sheet.csv).

Stages:
  1. DRAW (always). Frame = every v2 record whose first-entry year (`start`) is in one of the four
     eras of script 38 (1834-1890, 1891-1924, 1925-1973, 1990-2020); the claim is limited to that
     frame (first entries 1811-1833 are excluded; none has a missing `start`). Strata = era x
     surname group (elite / common / other; published Pat-OR-Mat rule of scripts 24/34/38, with
     the enduring-elite list pinned by sha256). Allocation 4 per stratum (48), the last 2 by
     largest remainder. SRS without replacement within strata, generator default_rng(SEED).
  2. SCORE (if the reference coding exists; otherwise a BLIND template is written).
  3. CORPUS-WIDE CHECKS (all 3,417 bios): Club de la Union regex, every match read in context and
     classified (exported with verdicts); spouse-surname format used by the homogamy marker.
  4. PI verification sheet (random 15 of the 50; blank columns; no AI or extracted values).

Fields audited (who uses them):
  secondary_school        -> elite-school marker (PRIV regex; scripts 24/34/38/43); Instituto
                             Nacional and "school named" diagnostics (38)          [grounded]
  university              -> named in the appendix accuracy sentence                [grounded]
  father_surname_paternal -> named in the appendix accuracy sentence                [grounded]
  spouse_surnames         -> spouse homogamy (24/38)                                [grounded]
  birth_year, death_year  -> script 38 Club cohort-eligibility restrictions          [grounded]
  elite_club (LLM bool)   -> 38 `club_llm`; submitted script-24 fold. MODEL JUDGEMENT (is a club
                             "aristocratic"?), not a grounded extraction; reported separately.
Markers (as the paper codes them):
  school_priv   = PRIV regex (script 10) on the EXTRACTED secondary_school vs on the reference school
  club_union    = regex "CLUB DE LA UNION" on the RAW TEXT (not on the extraction) vs the reference
                  reading "the text states the legislator was a member/officer/founder of it"
  inst_nacional, school_named, spouse_elite (any spouse token in the elite list, rule of 24/38)

Comparison. Institution strings are compared as sets of institutions, each a content-token set
(de-accented; generic words such as colegio / liceo / universidad dropped; documented aliases
applied). Automatic category = strict: exact only if the institutions match one-to-one with equal
token sets. Any cell with more than one institution on either side, or a match only by token-subset,
is flagged `needs_verdict` and MUST carry a manual verdict (h_<field>_verdict) in the reference
file; the script stops otherwise. Results are reported both on the strict automatic basis and on
the adjudicated basis. Categories: exact, correct_null (both absent), partial, wrong, miss (stated,
not extracted), hallucinated (extracted, not stated). h_judgement lists fields whose disagreement
is a definitional call; they count as errors (a bound that accepts them is also reported).

Uncertainty. Field-level rates (one check per bio) get Wilson intervals; pooled rates (several
checks per bio) get a stratified bio-level cluster bootstrap (B = 2,000, resampling bios within
strata, percentile intervals).

Inputs (not redistributed; located via RAW_DATA_ROOT as in scripts 24/34/38):
  <RAW_DATA_ROOT>/data/processed/bcn_extract_v2.json, <RAW_DATA_ROOT>/data/raw/bcn_wayback/*.txt
  data/processed/enduring_elite_FINAL.csv (repo; sha256 pinned)
  output/rnr2026/A6_bio_audit_handcoded.csv (repo; reference coding)
Outputs (output/rnr2026/): A6_bio_audit_sample.csv, A6_bio_audit_results.csv,
  A6_bio_audit_itemlevel.csv, A6_bio_audit_disagreements.csv, A6_bio_audit_corpus_checks.csv,
  A6_bio_audit_club_contexts.csv (+ A6_bio_audit_handcoded_TEMPLATE.csv when not yet coded);
  <project>/quality_reports/rnr2026/A6_PI_verification_TEMPLATE.csv (never overwritten once any
  pi_ cell is filled; only if that tree exists,
  otherwise output/rnr2026/). If A6_PI_verification_completed.csv exists beside it, the PI values
  are scored against the extraction and the AI reference (A6_PI_agreement*.csv in output/rnr2026/).
Run with WSL python3:  python3 replication_repo/scripts/44_bio_extraction_audit.py
"""
import hashlib
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

# ---- seed (INV-14) ------------------------------------------------------------------------
SEED = 20260926
RNG = np.random.default_rng(SEED)       # used, in order: draw -> bootstrap -> PI subsample
N_SAMPLE = 50
N_MIN_PER_STRATUM = 4
B_BOOT = 2000
N_PI = 15

# ---- paths (INV-16) -----------------------------------------------------------------------
REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _measure_helpers import require  # noqa: E402

RAW_DATA_ROOT = Path(os.environ.get("RAW_DATA_ROOT", REPO.parent))
BIOS_JSON = RAW_DATA_ROOT / "data" / "processed" / "bcn_extract_v2.json"
BIOS_TXT = RAW_DATA_ROOT / "data" / "raw" / "bcn_wayback"
ELITE_CSV = REPO / "data" / "processed" / "enduring_elite_FINAL.csv"
ELITE_SHA256 = "55cd2071bab93f4d0fe48c7c8a9720e208f33e82e0809cd5fce20c4da0c5a7ee"
OUT = REPO / "output" / "rnr2026"
OUT.mkdir(parents=True, exist_ok=True)
QR_DIR = REPO.parent / "quality_reports" / "rnr2026"
F_SAMPLE = OUT / "A6_bio_audit_sample.csv"
F_HAND = OUT / "A6_bio_audit_handcoded.csv"
F_TEMPLATE = OUT / "A6_bio_audit_handcoded_TEMPLATE.csv"
F_RESULTS = OUT / "A6_bio_audit_results.csv"
F_ITEMS = OUT / "A6_bio_audit_itemlevel.csv"
F_DISAGREE = OUT / "A6_bio_audit_disagreements.csv"
F_CHECKS = OUT / "A6_bio_audit_corpus_checks.csv"
F_CLUBCTX = OUT / "A6_bio_audit_club_contexts.csv"
PI_DIR = QR_DIR if QR_DIR.is_dir() else OUT
F_PI_TEMPLATE = PI_DIR / "A6_PI_verification_TEMPLATE.csv"     # blank; never overwritten once filled
F_PI_DONE = PI_DIR / "A6_PI_verification_completed.csv"       # the PI's completed copy (read only)
F_PI_ITEMS = OUT / "A6_PI_agreement_items.csv"
F_PI_SUMMARY = OUT / "A6_PI_agreement.csv"

require([BIOS_JSON, BIOS_TXT], "BCN biography corpus (v2)")
_sha = hashlib.sha256(ELITE_CSV.read_bytes()).hexdigest()
if _sha != ELITE_SHA256:
    sys.exit(f"enduring_elite_FINAL.csv sha256 {_sha} != pinned {ELITE_SHA256}: strata would change")

# ---- coding rules, verbatim from scripts 10 / 34 / 38 --------------------------------------
PRIV = re.compile(r"SAN IGNACIO|SAGRADOS? CORAZ|PADRES FRANCESES|VERBO DIVINO|THE GRANGE|GRANGE SCHOOL|"
                  r"CRAIGHOUSE|SAINT GEORGE|SAN JORGE|SAINT GABRIEL|SAN GABRIEL|VILLA MARIA|MACKAY|"
                  r"SAINT JOHN|LICEO ALEMAN|COLEGIO ALEMAN")
CU = re.compile("CLUB DE LA UNION")
INST_NAC = re.compile(r"INSTITUTO NACIONAL")
ERAS = [("1834-1890", 1834, 1890), ("1891-1924", 1891, 1924),
        ("1925-1973", 1925, 1973), ("1990-2020", 1990, 2020)]
GROUPS = ["elite", "common", "other"]


def dac(s):
    """De-accent and upper-case (identical to scripts 24/34/38)."""
    return unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()


ELITE = set(pd.read_csv(ELITE_CSV).surname.map(dac))
COMMON = set(dac(s) for s in (
    "GONZALEZ MUNOZ DIAZ ROJAS PEREZ SILVA SOTO MARTINEZ LOPEZ MORALES CONTRERAS RODRIGUEZ "
    "SEPULVEDA FUENTES VALENZUELA RAMIREZ ESPINOZA REYES HERNANDEZ GUTIERREZ FLORES CASTRO "
    "TORRES SANCHEZ VASQUEZ CASTILLO FERNANDEZ ARAYA HERRERA VARGAS NUNEZ ALVAREZ CARRASCO "
    "GOMEZ BRAVO VERGARA GARCIA TAPIA JARA ZUNIGA ORELLANA FIGUEROA MIRANDA RIQUELME CAMPOS "
    "MOLINA RIVERA GUZMAN SANDOVAL ORTIZ").split())


def classify(pat, mat):
    """Surname group under the published Pat-OR-Mat rule (scripts 24/34/38)."""
    p, m = dac(pat), dac(mat)
    if p in ELITE or m in ELITE:
        return "elite"
    if p in COMMON or m in COMMON:
        return "common"
    return "other"


def era_of(y):
    """Era label for a first-entry year (None outside the four eras), as script 38."""
    if pd.isna(y):
        return None
    return next((lab for lab, lo, hi in ERAS if lo <= y <= hi), None)


def is_blank(v):
    """True for None / NaN / empty string / empty list."""
    if v is None:
        return True
    if isinstance(v, float) and np.isnan(v):
        return True
    if isinstance(v, (list, tuple)):
        return len(v) == 0
    return str(v).strip() == ""


def wilson(k, n, z=stats.norm.ppf(0.975)):
    """Wilson score interval for k successes in n independent trials."""
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z ** 2 / n
    centre = (p + z ** 2 / (2 * n)) / den
    half = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2)) / den
    return (max(0.0, centre - half), min(1.0, centre + half))


# =============================================================================================
# 1. DRAW
# =============================================================================================
with open(BIOS_JSON, encoding="utf-8") as fh:
    recs = json.load(fh)
full = pd.DataFrame([{
    "bio_id": Path(x["file"]).stem, "file": x["file"], "name": x["name"],
    "start": pd.to_numeric(x.get("start"), errors="coerce"),
    "pat": x.get("pat", ""), "mat": x.get("mat", ""),
    "group": classify(x.get("pat", ""), x.get("mat", "")),
} for x in recs])
full["era"] = full.start.map(era_of)
EXCLUDED = {"start_missing": int(full.start.isna().sum()),
            "start_before_1834": int((full.start < 1834).sum()),
            "start_1974_1989_or_after_2020": int(((full.start > 1973) & (full.start < 1990)).sum()
                                                 + (full.start > 2020).sum())}
assert sum(EXCLUDED.values()) == int(full.era.isna().sum())
frame = full.dropna(subset=["era"]).sort_values("file").reset_index(drop=True)
print(f"Frame: {len(frame)} of {len(recs)} v2 biographies with first entry 1834-2020; excluded {EXCLUDED}")

strata = (frame.groupby(["era", "group"]).size().rename("N_h").reset_index()
          .sort_values(["era", "group"]).reset_index(drop=True))
strata["n_h"] = N_MIN_PER_STRATUM
extra = N_SAMPLE - int(strata.n_h.sum())
quota = strata.N_h / strata.N_h.sum() * N_SAMPLE - strata.n_h
strata.loc[np.argsort(-quota.to_numpy(), kind="stable")[:extra], "n_h"] += 1
assert int(strata.n_h.sum()) == N_SAMPLE and (strata.n_h <= strata.N_h).all()


def draw_stratum(s):
    """SRS without replacement of n_h files from one era x group stratum (fixed stratum order)."""
    pool = frame[(frame.era == s.era) & (frame.group == s.group)]
    return pool.loc[np.sort(RNG.choice(pool.index.to_numpy(), size=int(s.n_h), replace=False))]


sample = pd.concat([draw_stratum(s) for s in strata.itertuples()]).merge(strata, on=["era", "group"])
sample["weight"] = sample.N_h / sample.n_h
sample.insert(0, "audit_no", np.arange(1, len(sample) + 1))
sample["seed"] = SEED
sample.to_csv(F_SAMPLE, index=False)
print(f"Sample: {len(sample)} biographies, seed {SEED} -> {F_SAMPLE.relative_to(REPO)}")
print(strata.to_string(index=False))

# =============================================================================================
# 2. SCORE
# =============================================================================================
STRING_FIELDS = ["secondary_school", "university"]
SURNAME_FIELDS = ["father_surname_paternal"]
LIST_FIELDS = ["spouse_surnames"]
INT_FIELDS = ["birth_year", "death_year"]
BOOL_FIELDS = ["elite_club"]
FIELDS = STRING_FIELDS + SURNAME_FIELDS + LIST_FIELDS + INT_FIELDS + BOOL_FIELDS
GROUNDED = [f for f in FIELDS if f not in BOOL_FIELDS]
APPENDIX_GROUNDED = ["father_surname_paternal", "university", "secondary_school"]
# coder evidence per field (excerpts from the page; '...' = elision; (...) / [...] = coder note)
EV_COL = {"secondary_school": "ev_secondary_school", "university": "ev_university",
          "father_surname_paternal": "ev_father", "spouse_surnames": "ev_spouse",
          "birth_year": "ev_birth_death", "death_year": "ev_birth_death", "elite_club": "ev_club",
          "school_priv": "ev_secondary_school", "inst_nacional": "ev_secondary_school",
          "school_named": "ev_secondary_school", "club_union_regex": "ev_club",
          "spouse_elite": "ev_spouse"}
HAND_COLS = (["audit_no", "bio_id"] + [f"h_{f}" for f in FIELDS]
             + [f"h_{f}_verdict" for f in FIELDS] + ["h_club_union"]
             + list(dict.fromkeys(EV_COL.values())) + ["h_judgement", "h_notes"])

if not F_HAND.exists():
    tmpl = sample[["audit_no", "bio_id", "name", "start", "era", "group"]].copy()
    tmpl[HAND_COLS[2:]] = ""
    tmpl.to_csv(F_TEMPLATE, index=False)
    print(f"\nNo reference coding yet. Blind template written -> {F_TEMPLATE.relative_to(REPO)}. "
          f"Fill it (reading data/raw/bcn_wayback/<bio_id>.txt), save as {F_HAND.name}, re-run.")
    sys.exit(0)

hand = pd.read_csv(F_HAND, dtype=str, keep_default_na=False)
missing_cols = [c for c in HAND_COLS if c not in hand.columns]
assert not missing_cols, f"reference file lacks columns: {missing_cols}"
assert list(hand.bio_id) == list(sample.bio_id), "reference IDs do not match the seeded draw"
H = hand.to_dict("records")
ext = {Path(x["file"]).stem: (x.get("fields") or {}) for x in recs}
RAW = {r["bio_id"]: (BIOS_TXT / f"{r['bio_id']}.txt").read_text(encoding="utf-8") for r in H}

STOP = {"DE", "DEL", "LA", "LAS", "LOS", "EL", "Y", "EN", "E", "COLEGIO", "LICEO", "UNIVERSIDAD",
        "THE", "SCHOOL", "ESCUELA"}   # generic words only; place names (SANTIAGO, CHILE, ...) are kept
# Documented name equivalences (same institution, different names); applied to both sides.
ALIASES = [(r"UNIVERSIDAD DEL ESTADO", "UNIVERSIDAD DE CHILE"),
           (r"PADRES FRANCESES", "SAGRADOS CORAZONES"),
           (r"SAGRADO CORAZON\b", "SAGRADOS CORAZONES"),
           (r"PONTIFICIA ", ""),
           (r"\bSALESIANOS\b", "SALESIANO")]
PARTICLES = {"DE", "DEL", "LA", "LAS", "LOS", "Y"}
SPLIT_INST = re.compile(r";|\s+Y\s+(?=(?:EL |LA |LOS )?(?:COLEGIO|LICEO|INSTITUTO|SEMINARIO|INTERNADO|"
                        r"UNIVERSIDAD|ESCUELA|CONVICTORIO))|,\s*(?=(?:EL |LA |LOS )?(?:COLEGIO|LICEO|"
                        r"INSTITUTO|SEMINARIO|INTERNADO|UNIVERSIDAD|ESCUELA|CONVICTORIO))")


def canon(s):
    """De-accented string with documented institution aliases applied."""
    out = dac(s)
    for pat, rep in ALIASES:
        out = re.sub(pat, rep, out)
    return out


def tokens(s):
    """Content-token set of one institution name (aliases applied, generic words removed)."""
    return frozenset(w for w in re.sub(r"[^A-Z0-9 ]", " ", canon(s)).split() if w not in STOP)


def surname_key(s):
    """Surname comparison key: de-accented, hyphens as spaces, particles (de, del, ...) dropped."""
    return " ".join(w for w in re.sub(r"[^A-Z ]", " ", dac(s)).split() if w not in PARTICLES)


def split_items(s):
    """Reference multi-valued cell: items separated by ';'."""
    return [t.strip() for t in str(s).split(";") if t.strip()]


def institutions(s):
    """List of institution token sets named in a school / university value."""
    return [] if is_blank(s) else [t for t in map(tokens, SPLIT_INST.split(dac(s))) if t]


def cat_sets(h_items, e_items):
    """Strict category for a set-valued comparison (items already normalised)."""
    h, e = set(h_items), set(e_items)
    if not h and not e:
        return "correct_null"
    if h and not e:
        return "miss"
    if e and not h:
        return "hallucinated"
    if h == e:
        return "exact"
    return "partial" if h & e else "wrong"


def cat_institutions(hv, ev):
    """(strict category, needs_verdict) for a school / university cell."""
    h, e = institutions(hv), institutions(ev)
    strict = cat_sets(h, e)
    if strict == "wrong" and any(a <= b or b <= a for a in h for b in e):
        strict = "partial"                                   # overlap only by token subset
    needs = bool(h and e) and (len(h) > 1 or len(e) > 1 or strict != "exact")
    return strict, needs


def fmt(v):
    """Printable extracted value."""
    if isinstance(v, list):
        return "; ".join(map(str, v))
    return "" if is_blank(v) else str(v)


def auto_category(fld, hv, ev):
    """(strict automatic category, needs_verdict) for one field of one bio."""
    if fld in STRING_FIELDS:
        return cat_institutions(hv, fmt(ev))
    if fld in SURNAME_FIELDS:
        return cat_sets([surname_key(hv)] if not is_blank(hv) else [],
                        [surname_key(ev)] if not is_blank(ev) else []), False
    if fld in LIST_FIELDS:
        return cat_sets([surname_key(t) for t in split_items(hv)],
                        [surname_key(t) for t in (ev or [])]), False
    if fld in INT_FIELDS:
        return cat_sets([int(hv)] if not is_blank(hv) else [],
                        [int(ev)] if not is_blank(ev) else []), False
    hb, eb = str(hv).strip().upper() in {"1", "TRUE"}, bool(ev)   # boolean: miss = FN, halluc. = FP
    return ("exact" if hb and eb else "correct_null" if not (hb or eb)
            else "miss" if hb else "hallucinated"), False


def score_item(r, fld):
    """Item-level record: strict automatic and adjudicated categories for one bio x field."""
    ev = ext[r["bio_id"]].get(fld)
    auto, needs = auto_category(fld, r[f"h_{fld}"], ev)
    verdict = r[f"h_{fld}_verdict"].strip()
    assert verdict or not needs, f"{r['bio_id']} {fld}: multi-institution/subset cell needs a verdict"
    cat = verdict or auto
    return {"audit_no": int(r["audit_no"]), "bio_id": r["bio_id"], "field": fld,
            "hand_value": r[f"h_{fld}"], "extracted_value": fmt(ev), "auto_category": auto,
            "needs_verdict": needs, "category": cat, "overridden": bool(verdict) and verdict != auto,
            "judgement": fld in split_items(r["h_judgement"]) and cat not in ("exact", "correct_null")}


items = pd.DataFrame([score_item(r, fld) for r in H for fld in FIELDS])


def marker_pairs(r):
    """(marker, coded, reference) triples for one bio, as the paper codes each marker."""
    f = ext[r["bio_id"]]
    e_sch, h_sch = dac(f.get("secondary_school") or ""), dac(r["h_secondary_school"])
    sp_e, sp_h = f.get("spouse_surnames") or [], split_items(r["h_spouse_surnames"])
    elite_sp = lambda sp: any(dac(t) in ELITE for s in sp for t in str(s).split())  # noqa: E731
    return [("school_priv", bool(PRIV.search(e_sch)), bool(PRIV.search(h_sch))),
            ("inst_nacional", bool(INST_NAC.search(e_sch)), bool(INST_NAC.search(h_sch))),
            ("school_named", bool(e_sch), bool(h_sch)),
            ("club_union_regex", bool(CU.search(dac(RAW[r["bio_id"]]))), r["h_club_union"].strip() == "1"),
            ("spouse_elite", elite_sp(sp_e), elite_sp(sp_h))]


markers = pd.DataFrame([{"audit_no": int(r["audit_no"]), "bio_id": r["bio_id"], "marker": m,
                         "coded": int(c), "hand": int(t)} for r in H for m, c, t in marker_pairs(r)])

# ---- stratified bio-level cluster bootstrap (resample bios within strata) ---------------------
bio_order = list(sample.bio_id)
stratum_key = (sample.era + "|" + sample.group).to_numpy()          # sample order = bio_order
strat_idx = [np.flatnonzero(stratum_key == key) for key in dict.fromkeys(stratum_key)]
BOOT_IDX = np.hstack([ix[RNG.integers(0, len(ix), size=(B_BOOT, len(ix)))] for ix in strat_idx])


def per_bio(d, cats):
    """Per-bio count (in sample order) of item rows whose category is in `cats`."""
    return d[d.category.isin(cats)].groupby("bio_id").size().reindex(bio_order, fill_value=0).to_numpy()


def boot_ratio(num, den):
    """(lo, hi, n_dropped): percentile 95% CI of sum(num)/sum(den) under the stratified bio
    bootstrap. Replicates whose resampled denominator is 0 are dropped (the ratio is undefined)
    and counted, not set to 0."""
    nb, db = num[BOOT_IDX].sum(axis=1), den[BOOT_IDX].sum(axis=1)
    keep = db > 0
    lo, hi = np.quantile(nb[keep] / db[keep], [0.025, 0.975]) if keep.any() else (np.nan, np.nan)
    return lo, hi, int((~keep).sum())


CATS = ["exact", "correct_null", "partial", "wrong", "miss", "hallucinated"]
w = sample.set_index("bio_id").weight


def summary_row(level, name, flds, basis):
    """Accuracy summary for a set of fields on the 'adjudicated' or strict 'automatic' basis."""
    d = items[items.field.isin(flds)].assign(category=lambda x: x[basis])
    n = len(d)
    c = d.category.value_counts().reindex(CATS, fill_value=0)
    agree, stated = int(c.exact + c.correct_null), int(c.exact + c.partial + c.wrong + c.miss)
    notstated = int(c.correct_null + c.hallucinated)
    ok = d.category.isin(["exact", "correct_null"])
    n_j = int((d.judgement & ~ok).sum()) if basis == "category" else 0
    if level == "field":
        ci, ci_rec, ci_hal = (wilson(agree, n) + (0,), wilson(int(c.exact), stated) + (0,),
                              wilson(int(c.hallucinated), notstated) + (0,))
        ci_method = "wilson"
    else:
        nb = per_bio(d, CATS)
        ci = boot_ratio(per_bio(d, ["exact", "correct_null"]), nb)
        ci_rec = boot_ratio(per_bio(d, ["exact"]), per_bio(d, ["exact", "partial", "wrong", "miss"]))
        ci_hal = boot_ratio(per_bio(d, ["hallucinated"]), per_bio(d, ["correct_null", "hallucinated"]))
        ci_method = "stratified_bio_bootstrap_B2000"
    ww = w.loc[d.bio_id].to_numpy()
    return {"level": level, "item": name, "basis": "adjudicated" if basis == "category" else "automatic_strict",
            "n_checks": n, "n_bios": d.bio_id.nunique(), **{k: int(c[k]) for k in CATS},
            "agreement": agree / n, "agreement_lo": ci[0], "agreement_hi": ci[1],
            "stated": stated, "stated_recovered_exact": int(c.exact),
            "stated_recovery": c.exact / stated if stated else np.nan,
            "stated_recovery_lo": ci_rec[0], "stated_recovery_hi": ci_rec[1],
            "not_stated": notstated, "extracted_when_not_stated": int(c.hallucinated),
            "overextraction": c.hallucinated / notstated if notstated else np.nan,
            "overextraction_lo": ci_hal[0], "overextraction_hi": ci_hal[1],
            "boot_dropped_agreement": ci[2], "boot_dropped_stated": ci_rec[2],
            "boot_dropped_overextraction": ci_hal[2],
            "agreement_incl_partial": (agree + c.partial) / n,
            "n_judgement": n_j, "agreement_judgement_accepted": (agree + n_j) / n,
            "agreement_design_weighted": float((ok.to_numpy() * ww).sum() / ww.sum()),
            "ci_method": ci_method}


POOLS = [("appendix_grounded(father,university,school)", APPENDIX_GROUNDED),
         ("appendix_incl_llm_club(father,university,school,elite_club)", APPENDIX_GROUNDED + ["elite_club"]),
         ("all_grounded(6 fields)", GROUNDED),
         ("all_7_fields", FIELDS)]
res = ([summary_row("field", f, [f], b) for b in ["category", "auto_category"] for f in FIELDS]
       + [summary_row("pooled", nm, fl, b) for b in ["category", "auto_category"] for nm, fl in POOLS])


def marker_row(m):
    """Agreement of a coded marker with the reference reading (Wilson CI, Cohen's kappa)."""
    d = markers[markers.marker == m]
    tp, tn = int(((d.coded == 1) & (d.hand == 1)).sum()), int(((d.coded == 0) & (d.hand == 0)).sum())
    fp, fn = int(((d.coded == 1) & (d.hand == 0)).sum()), int(((d.coded == 0) & (d.hand == 1)).sum())
    n = len(d)
    po = (tp + tn) / n
    pe = ((tp + fp) * (tp + fn) + (tn + fn) * (tn + fp)) / n ** 2
    lo, hi = wilson(tp + tn, n)
    return {"level": "marker", "item": m, "basis": "adjudicated", "n_checks": n, "n_bios": n,
            "tp": tp, "tn": tn, "fp": fp, "fn": fn, "agreement": po, "agreement_lo": lo, "agreement_hi": hi,
            "kappa": (po - pe) / (1 - pe) if pe < 1 else np.nan, "n_positive_reference": tp + fn,
            "coded_from": "raw text regex" if m == "club_union_regex" else "v2 extraction",
            "ci_method": "wilson"}


results = pd.DataFrame(res + [marker_row(m) for m in markers.marker.unique()])
results.to_csv(F_RESULTS, index=False, float_format="%.4f")
items.to_csv(F_ITEMS, index=False)

# ---- disagreements, with the coder's evidence and a verbatim check -----------------------------
def norm_text(s):
    """Normalisation for the verbatim check (entities, quotes, whitespace, accents, case)."""
    s = re.sub(r"&#160;|&#32;|[\"'“”‘’]", " ", str(s))
    return re.sub(r"\s+", " ", dac(s)).strip()


MIN_FRAG = 4   # excerpts shorter than 4 normalised characters (e.g. stray punctuation) are not checked


def evidence_verbatim(ev, bio_id):
    """True if the evidence's excerpts all occur verbatim in the page (excerpts separated by '...',
    ';' or ' vs '; (...) / [...] are coder notes unless the page itself carries them); None if the
    evidence is only a coder note, False if any excerpt is paraphrase."""
    page = norm_text(RAW[bio_id])

    def frags(s):
        return [g for g in (norm_text(f.strip(" ;:.,")) for f in re.split(r"\.\.\.|…|;| vs ", s)) if len(g) >= MIN_FRAG]
    no_notes, as_is = frags(re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", ev)), frags(ev)
    if not no_notes:
        return None
    return all(f in page for f in no_notes) or all(f in page for f in as_is)


EV = hand.set_index("bio_id")
dis_f = items[~items.category.isin(["exact", "correct_null"]) | ~items.auto_category.isin(["exact", "correct_null"])]
mk = markers[markers.coded != markers.hand]
dis = pd.concat([
    dis_f.assign(kind="field"),
    mk.assign(kind="marker", field=mk.marker, hand_value=mk.hand.astype(str),
              extracted_value=mk.coded.astype(str),
              category=np.where(mk.coded == 1, "false_positive", "false_negative"),
              auto_category=np.where(mk.coded == 1, "false_positive", "false_negative"),
              needs_verdict=False, overridden=False, judgement=False)
    [["audit_no", "bio_id", "field", "hand_value", "extracted_value", "auto_category", "needs_verdict",
      "category", "overridden", "judgement", "kind"]]], ignore_index=True)
dis["coder_evidence"] = [EV.loc[b, EV_COL[f]] for b, f in zip(dis.bio_id, dis.field)]
dis["evidence_verbatim"] = [evidence_verbatim(e, b) for e, b in zip(dis.coder_evidence, dis.bio_id)]
dis["notes"] = dis.bio_id.map(EV.h_notes)
dis = dis.sort_values(["audit_no", "kind", "field"])
dis[["audit_no", "bio_id", "kind", "field", "auto_category", "needs_verdict", "category", "overridden",
     "judgement", "hand_value", "extracted_value", "coder_evidence", "evidence_verbatim", "notes"]
    ].to_csv(F_DISAGREE, index=False)
ev_all = [evidence_verbatim(EV.loc[b, c], b) for b in EV.index for c in dict.fromkeys(EV_COL.values())]

pd.set_option("display.width", 250)
show = ["item", "basis", "n_checks", "exact", "correct_null", "partial", "wrong", "miss", "hallucinated",
        "agreement", "agreement_lo", "agreement_hi", "stated_recovered_exact", "stated",
        "extracted_when_not_stated", "not_stated"]
print("\nField and pooled rates:")
print(results[results.level != "marker"][show].to_string(index=False, float_format="%.3f"))
print("\nMarkers:")
print(results[results.level == "marker"][["item", "coded_from", "n_checks", "tp", "tn", "fp", "fn",
                                          "agreement", "agreement_lo", "kappa"]]
      .to_string(index=False, float_format="%.3f"))
print(f"\nDisagreement rows: {len(dis)}; evidence cells verbatim: "
      f"{sum(v is True for v in ev_all)} / {sum(v is not None for v in ev_all)} (others are coder notes only)")

# =============================================================================================
# 3. CORPUS-WIDE CHECKS (all 3,417 v2 bios; the sample holds only 3 Club-regex positives)
# =============================================================================================
# (a) Club de la Union regex. Every one of the 251 matches was read at sentence level (the
#     exported context CSV holds each first match with 250 characters either side). Classes:
#       santiago_explicit        "Club de la Union de Santiago" (detected by regex)
#       santiago_or_unqualified  no place qualifier; the Santiago club is assumed
#       provincial               an explicit non-Santiago qualifier attached to the club
#       ambiguous (narrow rule)  the text attaches a provincial place to the club itself or to
#                                the whole membership list that contains it, without an explicit
#                                "Club de la Union de X" qualifier (hand-classified, 3 bios)
#     Sensitivity (broad rule, scripted): an unqualified match whose sentence also names any
#     non-Santiago place (PLACES below; e.g. "socio del Club de la Union y del Club de La Serena").
#     Elite members of the Santiago club were often also members of their home-town club, so the
#     broad rule over-flags; it is reported as a worst case for precision.
#     Every match states the legislator's OWN membership / office / founding role (none is a
#     relative's membership or an event held at the club). A variant-spelling search (CLUB UNION,
#     CLUB LA UNION, CLUB DE UNION, punctuation between words) found 3 Santiago-club members spelled
#     "Club La Union" that the regex misses, and 3 matches that are other bodies.
CLUB_PROVINCIAL = {"DOMINGO_CONTRERAS_GOMEZ": "de Los Angeles", "VICTOR_RIOS_RUIZ": "de Los Angeles",
                   "MARIO_RIOS_PADILLA": "de Los Angeles", "JAIME_CONCHA_BARANAO": "de Linares",
                   "SEBASTIAN_BARJA_BLANCO": "ambos en la ciudad de Linares",
                   "EDMUNDO_FUENZALIDA_ESPINOSA": "de la misma ciudad (Antofagasta)"}
CLUB_AMBIGUOUS = {"CARLOS_VILLARROEL_MORA": "'socio del Club de la Union, siendo su presidente en Tarapaca'",
                  "RICARDO_OTTO_WEBER_KUNSTMANN": "'socio del Club de la Union, Club Autobotes, ... en Concepcion'",
                  "RAFAEL_CIFUENTES_LATHAM": "'del Club de la Union, y otros clubes locales de la region de Nuble'"}
PLACES = re.compile(r"\b(?:ARICA|IQUIQUE|TARAPACA|ANTOFAGASTA|TOCOPILLA|CALAMA|COPIAPO|ATACAMA|VALLENAR|"
                    r"LA SERENA|COQUIMBO|OVALLE|ILLAPEL|VALPARAISO|VINA DEL MAR|QUILLOTA|LA CALERA|SAN FELIPE|"
                    r"LOS ANDES|ACONCAGUA|MELIPILLA|SAN ANTONIO|RANCAGUA|RENGO|SAN FERNANDO|CHIMBARONGO|"
                    r"SANTA CRUZ|CURICO|TALCA|LINARES|PARRAL|CAUQUENES|SAN JAVIER|CHILLAN|NUBLE|SAN CARLOS|"
                    r"CONCEPCION|TALCAHUANO|TOME|LOS ANGELES|ANGOL|TRAIGUEN|TEMUCO|CAUTIN|VALDIVIA|OSORNO|"
                    r"PUERTO MONTT|LLANQUIHUE|CHILOE|ANCUD|AYSEN|PUNTA ARENAS|MAGALLANES|LOTA|LEBU|ARAUCO|"
                    r"PEMUCO|LIMACHE|QUILPUE)\b")
CLUB_MISSED = {"LADISLAO_ERRAZURIZ_PEREIRA": "Club La Union", "ARTURO_MATTE_LARRAIN": "Club La Union",
               "JOAQUIN_PRIETO_CONCHA": "Club La Union"}
CLUB_OTHER_BODY = {"AUGUSTO_DRIEN_BAFFOUE": "Club Union Social Mutualista de Chile",
                   "JAIME_CAMPOS_QUIROGA": "Club Union de su ciudad natal",
                   "MANUEL_CHAPARRO_RUMINOT": "Rotary Club; Union de Pequenos Ganaderos"}
VARIANT = re.compile(r"CLUB\W+(?:DE\W+)?(?:LA\W+)?UNION\b")
SANT = re.compile(r"CLUB DE LA UNION,? DE SANTIAGO")

corpus = pd.DataFrame([{
    "bio_id": Path(x["file"]).stem, "group": classify(x.get("pat", ""), x.get("mat", "")),
    "body": re.sub(r"&#160;|\s+", " ", dac((BIOS_TXT / x["file"]).read_text(encoding="utf-8"))
                   .partition("\n---\n")[2]),
    "text": dac((BIOS_TXT / x["file"]).read_text(encoding="utf-8")),
    "spouses": (x.get("fields") or {}).get("spouse_surnames") or []} for x in recs if x.get("fields")])
corpus["club"] = corpus.text.str.contains(CU)
corpus["variant_only"] = corpus.text.map(lambda t: bool(VARIANT.search(t)) and not CU.search(t))
assert set(corpus.loc[corpus.variant_only, "bio_id"]) == set(CLUB_MISSED) | set(CLUB_OTHER_BODY), \
    "variant-spelling matches changed; re-read them"
assert corpus.set_index("bio_id").loc[list(CLUB_PROVINCIAL) + list(CLUB_AMBIGUOUS), "club"].all()


def club_verdict(row):
    """(verdict, qualifier) for a bio with a regex or variant match."""
    b = row.bio_id
    if b in CLUB_PROVINCIAL:
        return "provincial", CLUB_PROVINCIAL[b]
    if b in CLUB_AMBIGUOUS:
        return "ambiguous", CLUB_AMBIGUOUS[b]
    if b in CLUB_MISSED:
        return "missed_by_regex_santiago", CLUB_MISSED[b]
    if b in CLUB_OTHER_BODY:
        return "variant_other_body", CLUB_OTHER_BODY[b]
    return ("santiago_explicit", "de Santiago") if SANT.search(row.body) else ("santiago_or_unqualified", "")


def context(body, pat):
    """First match of `pat` in the body with 250 characters either side."""
    m = pat.search(body)
    return body[max(0, m.start() - 250):m.end() + 250] if m else ""


hits = corpus[corpus.club | corpus.variant_only].copy()
hits[["verdict", "qualifier"]] = [club_verdict(r) for r in hits.itertuples()]
hits["matched_by"] = np.where(hits.club, "published_regex", "variant_only")
hits["context"] = [context(b, CU if c else VARIANT) for b, c in zip(hits.body, hits.club)]


def club_sentences(body):
    """Sentences (split at '. ') that contain the Club de la Union regex."""
    return [x for x in re.split(r"\.\s", body) if CU.search(x)]


hits["broad_places"] = ["; ".join(sorted({m.group(0) for x in club_sentences(b) for m in PLACES.finditer(x)}))
                        for b in hits.body]
hits["broad_ambiguous"] = hits.verdict.eq("ambiguous") | (
    hits.verdict.eq("santiago_or_unqualified") & hits.broad_places.ne(""))
hits[["bio_id", "group", "matched_by", "verdict", "qualifier", "broad_ambiguous", "broad_places",
      "context"]].sort_values(
    ["matched_by", "verdict", "bio_id"]).to_csv(F_CLUBCTX, index=False)

n_reg = int(corpus.club.sum())
n_prov, n_amb, n_miss = len(CLUB_PROVINCIAL), len(CLUB_AMBIGUOUS), len(CLUB_MISSED)
corpus["club_upper"] = (corpus.club & ~corpus.bio_id.isin(CLUB_PROVINCIAL)) | corpus.bio_id.isin(CLUB_MISSED)
corpus["club_lower"] = corpus.club_upper & ~corpus.bio_id.isin(CLUB_AMBIGUOUS)
BROAD = set(hits.loc[hits.broad_ambiguous, "bio_id"])
n_broad = len(BROAD)
corpus["club_broad"] = corpus.club_upper & ~corpus.bio_id.isin(BROAD)


def club_rates(flag, label):
    """Club rates by group (script-34 definition: all bios with fields, all years)."""
    rate = corpus.groupby("group")[flag].mean() * 100
    rest = corpus.loc[corpus.group != "elite", flag].mean() * 100
    return ([{"check": f"club_rates_{label}", "item": g, "value": rate[g]} for g in GROUPS]
            + [{"check": f"club_rates_{label}", "item": "rest", "value": rest},
               {"check": f"club_rates_{label}", "item": "elite_over_rest", "value": rate["elite"] / rest},
               {"check": f"club_rates_{label}", "item": "elite_over_common", "value": rate["elite"] / rate["common"]}])


# (b) spouse_surnames format. The 09c manual asks for the spouse's PATERNAL surname only; the
#     extraction sometimes appends the maternal one ("Boonen Rivera"). Scripts 24/38 flag an elite
#     spouse if ANY token is elite. Compare with a paternal-only key (first surname token after
#     dropping particles, so "de la Maza" -> MAZA; hyphenated names split at the hyphen).
def paternal_token(s):
    """First surname token of a spouse entry, particles dropped."""
    toks = [w for w in re.sub(r"[^A-Z\- ]", " ", dac(s)).split() if w not in PARTICLES]
    return toks[0].replace("-", " ").split()[0] if toks else ""


spouse_items = [s for sp in corpus.spouses for s in sp]
corpus["sp_named"] = corpus.spouses.map(len) > 0
corpus["sp_elite_any"] = corpus.spouses.map(lambda sp: any(dac(t) in ELITE for s in sp for t in str(s).split()))
corpus["sp_elite_pat"] = corpus.spouses.map(lambda sp: any(paternal_token(s) in ELITE for s in sp))
named = corpus[corpus.sp_named]


def homogamy(rule):
    """Elite-spouse rate among bios naming a spouse, elite vs non-elite legislators."""
    r_el = named.loc[named.group == "elite", rule].mean() * 100
    r_ne = named.loc[named.group != "elite", rule].mean() * 100
    return [{"check": f"homogamy_{rule}", "item": "elite_legislators_pct", "value": r_el},
            {"check": f"homogamy_{rule}", "item": "non_elite_legislators_pct", "value": r_ne},
            {"check": f"homogamy_{rule}", "item": "ratio", "value": r_el / r_ne}]


checks = pd.DataFrame(
    [{"check": "frame", "item": k, "value": v} for k, v in EXCLUDED.items()]
    + [{"check": "club_regex", "item": "regex_positive_bios", "value": n_reg},
       {"check": "club_regex", "item": "santiago_explicit", "value": int((hits.verdict == "santiago_explicit").sum())},
       {"check": "club_regex", "item": "santiago_or_unqualified",
        "value": int((hits.verdict == "santiago_or_unqualified").sum())},
       {"check": "club_regex", "item": "provincial_namesake", "value": n_prov},
       {"check": "club_regex", "item": "ambiguous_narrow_rule", "value": n_amb},
       {"check": "club_regex", "item": "ambiguous_broad_rule (worst case)", "value": n_broad},
       {"check": "club_regex", "item": "missed_spelling_Club_La_Union", "value": n_miss},
       {"check": "club_regex", "item": "precision_santiago_lower (ambiguous = false)",
        "value": (n_reg - n_prov - n_amb) / n_reg},
       {"check": "club_regex", "item": "precision_santiago_upper (ambiguous = true)",
        "value": (n_reg - n_prov) / n_reg},
       {"check": "club_regex", "item": "recall_vs_variant_spellings_lower",
        "value": (n_reg - n_prov - n_amb) / (n_reg - n_prov - n_amb + n_miss)},
       {"check": "club_regex", "item": "recall_vs_variant_spellings_upper",
        "value": (n_reg - n_prov) / (n_reg - n_prov + n_miss)},
       {"check": "club_regex", "item": "precision_santiago_worst_case (broad ambiguous = false)",
        "value": (n_reg - n_prov - n_broad) / n_reg}]
    + club_rates("club", "published_regex") + club_rates("club_upper", "corrected_ambiguous_kept")
    + club_rates("club_lower", "corrected_ambiguous_dropped")
    + club_rates("club_broad", "corrected_broad_ambiguous_dropped")
    + [{"check": "club_corrections_by_group", "item": g,
        "value": (f"provincial -{int(corpus[(corpus.group == g) & corpus.bio_id.isin(CLUB_PROVINCIAL)].shape[0])}; "
                  f"ambiguous {int(corpus[(corpus.group == g) & corpus.bio_id.isin(CLUB_AMBIGUOUS)].shape[0])}; "
                  f"missed +{int(corpus[(corpus.group == g) & corpus.bio_id.isin(CLUB_MISSED)].shape[0])}")}
       for g in GROUPS]
    + [{"check": "spouse_format", "item": "spouse_entries", "value": len(spouse_items)},
       {"check": "spouse_format", "item": "entries_with_more_than_one_token",
        "value": sum(len(str(s).split()) > 1 for s in spouse_items)},
       {"check": "spouse_format", "item": "bios_spouse_elite_any_token (scripts 24/38)",
        "value": int(corpus.sp_elite_any.sum())},
       {"check": "spouse_format", "item": "bios_spouse_elite_paternal_only", "value": int(corpus.sp_elite_pat.sum())},
       {"check": "spouse_format", "item": "bios_elite_only_via_non_paternal_token",
        "value": int((corpus.sp_elite_any & ~corpus.sp_elite_pat).sum())}]
    + homogamy("sp_elite_any") + homogamy("sp_elite_pat"))
checks.to_csv(F_CHECKS, index=False, float_format="%.4f")
print("\nCorpus-wide checks:")
print(checks.to_string(index=False))

# =============================================================================================
# 4. PI VERIFICATION SHEET (random 15 of the 50; blank columns, no AI or extracted values)
# =============================================================================================
pi = sample.iloc[np.sort(RNG.choice(len(sample), size=N_PI, replace=False))]
PI_FIELDS = {"pi_secondary_school": "secondary_school", "pi_university": "university",
             "pi_father_surname_paternal": "father_surname_paternal", "pi_spouse_surnames": "spouse_surnames",
             "pi_birth_year": "birth_year", "pi_death_year": "death_year",
             "pi_elite_club_member_any_aristocratic_club_0_1": "elite_club",
             "pi_club_de_la_union_member_0_1": "club_de_la_union"}
pi_sheet = pd.DataFrame({
    "pi_no": np.arange(1, N_PI + 1), "audit_no": pi.audit_no.to_numpy(), "bio_id": pi.bio_id.to_numpy(),
    "file_path": [f"data/raw/bcn_wayback/{f}" for f in pi.file], "era": pi.era.to_numpy(),
    **{c: "" for c in list(PI_FIELDS) + ["pi_minutes_spent", "pi_notes"]}})


def filled(path):
    """True if the PI sheet at `path` has any non-blank pi_ value (i.e. someone has worked on it)."""
    d = pd.read_csv(path, dtype=str, keep_default_na=False)
    return bool((d[[c for c in d.columns if c.startswith("pi_") and c != "pi_no"]] != "").any().any())


if F_PI_TEMPLATE.exists() and filled(F_PI_TEMPLATE):
    print(f"\n[PI] {F_PI_TEMPLATE.name} has entries: NOT overwritten. Save the PI's copy as {F_PI_DONE.name}.")
else:
    pi_sheet.to_csv(F_PI_TEMPLATE, index=False)
    print(f"\nPI verification template ({N_PI} bios) -> {F_PI_TEMPLATE}")

# ---- scoring branch: only when the PI's completed copy exists --------------------------------
# Convention for the PI: leave a cell blank if the page states nothing; write '?' if not checked
# (excluded); separate several values with ';'; 0/1 for the two club columns.
REF_COL = {"club_de_la_union": "h_club_union"}


def ref_as_extracted(fld, v):
    """A reference-coding string cast to the type the v2 extraction uses for that field."""
    if fld in LIST_FIELDS:
        return split_items(v)
    if fld in INT_FIELDS:
        return None if is_blank(v) else int(v)
    if fld in BOOL_FIELDS + ["club_de_la_union"]:
        return str(v).strip() == "1"
    return v


def pi_compare(pi_val, other, fld):
    """(strict category, needs_review) of the PI value against another coding of the same field."""
    if fld == "club_de_la_union":
        a, b = str(pi_val).strip() == "1", bool(other)
        return ("exact" if a and b else "correct_null" if not (a or b) else "miss" if a else "hallucinated"), False
    return auto_category(fld, pi_val, other)


if F_PI_DONE.exists():
    done = pd.read_csv(F_PI_DONE, dtype=str, keep_default_na=False)
    assert set(done.bio_id) <= set(sample.bio_id), "completed PI sheet has IDs outside the sample"
    ref = hand.set_index("bio_id")
    pi_items = pd.DataFrame([
        {"bio_id": r["bio_id"], "field": fld, "comparison": comp, "pi_value": r[col],
         "other_value": fmt(other), **dict(zip(["category", "needs_review"], pi_compare(r[col], other, fld)))}
        for r in done.to_dict("records") for col, fld in PI_FIELDS.items() if r[col].strip() != "?"
        for comp, other in [
            ("pi_vs_extraction", bool(CU.search(dac(RAW[r["bio_id"]]))) if fld == "club_de_la_union"
             else ext[r["bio_id"]].get(fld)),
            ("pi_vs_ai_reference", ref_as_extracted(fld, ref.loc[r["bio_id"], REF_COL.get(fld, f"h_{fld}")]))]])
    pi_items.to_csv(F_PI_ITEMS, index=False)
    ok = pi_items.category.isin(["exact", "correct_null"])
    pi_summary = (pi_items.assign(agree=ok).groupby(["comparison", "field"])
                  .agg(n=("agree", "size"), agree=("agree", "sum"), needs_review=("needs_review", "sum"))
                  .reset_index())
    pooled = (pi_items[pi_items.field.isin(APPENDIX_GROUNDED)].assign(agree=ok).groupby("comparison")
              .agg(n=("agree", "size"), agree=("agree", "sum"), needs_review=("needs_review", "sum"))
              .reset_index().assign(field="pooled_appendix_grounded"))
    pi_summary = pd.concat([pi_summary, pooled], ignore_index=True)
    pi_summary["agreement"] = pi_summary.agree / pi_summary.n
    pi_summary[["lo", "hi"]] = [wilson(a, n) for a, n in zip(pi_summary.agree, pi_summary.n)]
    pi_summary.to_csv(F_PI_SUMMARY, index=False, float_format="%.4f")
    print(f"\n[PI] completed sheet scored ({done.shape[0]} bios; strict matching, multi-institution cells "
          f"flagged needs_review) -> {F_PI_SUMMARY.relative_to(REPO)}")
    print(pi_summary.to_string(index=False, float_format="%.3f"))
else:
    print(f"[PI] no completed sheet ({F_PI_DONE.name}); PI scoring skipped.")
print(f"Outputs in {OUT.relative_to(REPO)}: sample, results, itemlevel, disagreements, corpus_checks, club_contexts")
