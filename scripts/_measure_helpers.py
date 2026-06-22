"""Shared helpers for N2 (survivorship bound) and N3 (SES-cutoff sensitivity).

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


def toks(s):
    return [t for t in re.split(r"[ \-]", dac(s)) if len(t) >= 4 and t not in PART]


def build_hist():
    """Return defaultdict(set): surname-token -> set of source labels (deterministic)."""
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


def load_ses():
    ns = pd.read_csv("data/processed/surname_nse.csv")
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
