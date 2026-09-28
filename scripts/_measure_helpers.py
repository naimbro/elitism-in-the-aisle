"""Shared helpers for N2 (survivorship bound) and N3 (SES-cutoff sensitivity), and (R&R 2026)
the shared annual-share rule used by every 1925 ITS script (annual_share / annual_share_frame:
years with fewer than 5 sitting legislators are undefined and dropped).

Reconstructs the 19th-century historical-attestation set (HIST) DETERMINISTICALLY,
without the Anthropic API used in 02_build_enduring_elite.py. HIST = surname tokens
attested in (a) the 1874 censo agricola top-quartile (avaluo) landowners and (b) the
19th-century elite-network compilations (Chile - elite networks.xlsx). This
deterministic reconstruction recovers 287/298 of the published enduring-elite list,
so it is a faithful, reproducible stand-in for the LLM parse used in the main build.

Gate-1 (SES) and bearer/appearance floors are then applied on top of HIST, exactly as
in 02_build_enduring_elite.py (mean_nse>=T, n_occ>=MIN).

Inputs:
  1874 censo : <RAW_DATA_ROOT>/censo_agricola/1874/censo_1874.csv
  elite xlsx : <RAW_DATA_ROOT>/Chile - elite networks.xlsx
  SES        : data/processed/surname_nse.csv  (in the repo)

The 1874 censo and the elite-network workbook are large primary sources that live
OUTSIDE the public replication repo. Their location is resolved via RAW_DATA_ROOT
(see below) rather than hardcoded absolute paths, so any user can point the build at
their own copy by setting one environment variable or editing one constant.
"""
import os
import shutil
import sys
import pandas as pd, numpy as np, re, unicodedata, collections
from pathlib import Path

dac = lambda s: unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().upper().strip()
PART = {"DE", "DEL", "LA", "LAS", "LOS", "Y", "DA", "DI", "VON", "VAN", "SAN", "SANTA"}

# Repo root = parent of this scripts/ directory.
REPO = Path(__file__).resolve().parents[1]

# RAW_DATA_ROOT: directory holding the large primary sources that are NOT shipped in the
# repo (the 1874 censo agricola and the elite-network workbook). Set the RAW_DATA_ROOT
# environment variable to override; the default assumes the project layout in which the
# repo sits one level below the paper directory, with censo_agricola two levels above that.
#   - elite xlsx expected at:  RAW_DATA_ROOT / "Chile - elite networks.xlsx"
#   - 1874 censo expected at:   RAW_DATA_ROOT / "censo_agricola" / "1874" / "censo_1874.csv"
# In the author's tree these resolve to the paper_1925 dir and datos/censo_agricola; the
# default below reproduces that without any user-specific absolute path.
_default_raw = REPO.parent                       # the paper_1925 project dir (holds the xlsx)
RAW_DATA_ROOT = Path(os.environ.get("RAW_DATA_ROOT", _default_raw))

XLSX = str(RAW_DATA_ROOT / "Chile - elite networks.xlsx")
# The censo_agricola tree sits beside the papers/ dir in the author's layout
# (datos/censo_agricola), i.e. two levels above the paper_1925 dir. Resolve it relative
# to RAW_DATA_ROOT, falling back up the tree so an override of RAW_DATA_ROOT that points
# directly at a censo_agricola parent also works.
_censo_rel = Path("censo_agricola") / "1874" / "censo_1874.csv"
_censo_candidates = [
    RAW_DATA_ROOT / _censo_rel,                  # RAW_DATA_ROOT/censo_agricola/...
    RAW_DATA_ROOT.parent.parent / _censo_rel,    # author layout: datos/censo_agricola/...
]
CENSO = str(next((p for p in _censo_candidates if p.exists()), _censo_candidates[0]))

# ---------------------------------------------------------------------------------------
# Pipeline plumbing (R&R 2026, round 2).
#  * SKIP_CODE: a script whose non-redistributed inputs are absent exits with this code;
#    scripts/00_run_all.sh reports it as SKIP instead of failing.
#  * Generated tables go to REPO/tables, figures to REPO/figures; publish() then copies them
#    into the manuscript tree PAPER_DIR/{tables,figures} ONLY if that tree exists, so a
#    stand-alone clone of the repo never writes outside itself.
# ---------------------------------------------------------------------------------------

SKIP_CODE = 3
DATA = REPO / "data" / "processed"
OUTPUT = REPO / "output"
TABLES = REPO / "tables"
FIGURES = REPO / "figures"
PAPER_DIR = Path(os.environ.get("PAPER_DIR", REPO.parent / "paper"))


def skip(msg):
    """Exit with SKIP_CODE after printing why (missing non-redistributed input)."""
    print(f"[SKIP] {msg}", flush=True)
    sys.exit(SKIP_CODE)


def require(paths, what):
    """skip() unless every path in `paths` exists."""
    missing = [str(p) for p in paths if not Path(p).exists()]
    if missing:
        skip(f"{what} not found (not redistributed): {'; '.join(missing)}")


def require_raw():
    """The 1874 censo and the elite-network workbook (needed by build_hist)."""
    require([CENSO, XLSX], "1874 censo / elite-network workbook")


def publish(path, kind):
    """Copy a generated file to PAPER_DIR/<kind>/ (kind = 'tables' or 'figures') if the
    manuscript tree exists; otherwise keep it in the repo only."""
    path = Path(path)
    dst = PAPER_DIR / kind
    if dst.is_dir():
        shutil.copy2(path, dst / path.name)
        print(f"[publish] {path.name} -> {dst}")
    else:
        print(f"[publish] {dst} absent; {path.name} kept in {path.parent}")


def within_headline(level_shift, headline, tol=0.25):
    """Magnitude criterion relative to the headline break: |shift - headline| <= tol*|headline|."""
    return abs(level_shift - headline) <= tol * abs(headline)


def star(p):
    """Significance stars: *** p<0.01, ** p<0.05, * p<0.10."""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.10 else ""


def tex_num(x, digits=2, stars=""):
    """Math-mode number (true minus sign), stars as a superscript: $-11.01^{***}$."""
    return f"${x:.{digits}f}^{{{stars}}}$" if stars else f"${x:.{digits}f}$"


def tex_p(p):
    """p-value cell: $<$0.001 below 0.001, else three decimals."""
    return "$<$0.001" if p < 0.001 else f"{p:.3f}"


def toks(s):
    return [t for t in re.split(r"[ \-]", dac(s)) if len(t) >= 4 and t not in PART]


def build_hist():
    """Return defaultdict(set): surname-token -> set of source labels (deterministic)."""
    require_raw()   # exits with SKIP_CODE if the censo / workbook are absent
    HIST = collections.defaultdict(set)
    cz = pd.read_csv(CENSO, encoding="latin-1")
    cz["Avaluacion"] = pd.to_numeric(cz["Avaluacion"], errors="coerce")
    thr = cz["Avaluacion"].quantile(0.75)
    big = cz[cz["Avaluacion"] >= thr]
    for col in ["Paterno", "Materno"]:
        for v in big[col].dropna():
            for t in toks(v):
                HIST[t].add("censo1874")
    sheets = pd.read_excel(XLSX, sheet_name=None, header=None)
    for tab, d in sheets.items():
        for v in d.values.ravel():
            if str(v) == "nan":
                continue
            for t in toks(v):
                HIST[t].add(tab)
    return HIST


# ---------------------------------------------------------------------------------------
# Annual elite share of Congress: the shared "fewer than 5 sitting -> undefined" rule.
#
# R&R 2026 correction (error E1). Scripts 05, 16, 18, 22, 29, 30, 32 and 33 used to compute
# the annual share as elite / max(n, 1), so a year with no sitting legislators entered as a
# 0% elite share. Congress was dissolved on 11 Sept 1924 and did not sit again until
# March 1926, so 1925 entered every 1925 ITS as a spurious 0% first post-break observation.
# All scripts now use the rule already used by scripts 04 / 17 / 20: a year with fewer than
# MIN_SITTING legislators in office has an undefined (NaN) share and is dropped from the ITS.
# The roster itself is unchanged (all members, including pre-1891 substitutes; decision D8).
# ---------------------------------------------------------------------------------------
MIN_SITTING = 5


def annual_share(flag, S, E, years, min_n=MIN_SITTING):
    """Elite share (%) of legislators sitting in each year (Start <= y <= End).

    flag : boolean array, one entry per roster row (elite indicator).
    S, E : start / end years, aligned with flag.
    years: iterable of years.
    Returns a float array; NaN where fewer than `min_n` legislators sit (e.g. 1925).
    """
    flag = np.asarray(flag, dtype=bool)
    S = np.asarray(S)
    E = np.asarray(E)
    years = np.asarray(list(years))
    out = np.full(len(years), np.nan)
    for i, y in enumerate(years):
        m = (S <= y) & (E >= y)
        n = int(m.sum())
        if n >= min_n:
            out[i] = 100.0 * flag[m].sum() / n
    return out


def annual_share_frame(flag, S, E, y0, y1, min_n=MIN_SITTING):
    """DataFrame(year, elite) for y0..y1 with undefined (< min_n sitting) years DROPPED,
    ready for the segmented ITS regression."""
    yrs = np.arange(y0, y1 + 1)
    df = pd.DataFrame({"year": yrs, "elite": annual_share(flag, S, E, yrs, min_n)})
    return df.dropna(subset=["elite"]).reset_index(drop=True)


def load_ses():
    ns = pd.read_csv(DATA / "surname_nse.csv")
    ns["s"] = ns.surname.map(dac)
    NSE = dict(zip(ns["s"], ns.mean_nse))
    NOCC = dict(zip(ns["s"], ns.n_occ))
    return NSE, NOCC


def in_hist(surname, HIST):
    """A roster surname (possibly compound) is attested if it or any token is in HIST."""
    s = dac(surname)
    if s in HIST:
        return True
    return any(t in HIST for t in toks(s))


def build_list(HIST, NSE, NOCC, ses_cut, min_bearers=30, gate_ses=True):
    """Build a surname list at a given SES cutoff. If gate_ses=False -> unconditional
    19c list (HIST + bearer floor only). Returns set of surnames (deaccented)."""
    out = set()
    for s in NSE:
        if NOCC.get(s, 0) < min_bearers:
            continue
        if s not in HIST:
            continue
        if gate_ses and NSE[s] < ses_cut:
            continue
        out.add(s)
    return out
