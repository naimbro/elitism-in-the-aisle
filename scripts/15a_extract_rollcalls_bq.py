"""15a -- Extract the roll-call SNAPSHOT used by the NOMINATE appendix (R&R 2026, D18).

Pulls every recorded roll call of the Chilean Chamber of Deputies and Senate in the
legislative periods LI-LVI (11 March 2002 - 10 March 2026), each member's recorded vote,
the members' surnames, and their party for each term, from the IMFD "datos congreso"
BigQuery dataset. Writes a frozen snapshot to data/processed/nominate_snapshot/ so that the
rest of the NOMINATE pipeline (15b W-NOMINATE, 15 analysis) runs WITHOUT BigQuery access.

ACCESS. Needs a service-account key for project datos-congreso-461817. The key path is read
from the environment variable CONGRESO_BQ_KEY and is never written anywhere. If the variable
is unset, the file is missing, or google-cloud-bigquery is not installed, the script exits
with code 3 (SKIP) and the shipped snapshot is used as is.

    CONGRESO_BQ_KEY=/path/to/key.json python3 scripts/15a_extract_rollcalls_bq.py

RE-EXTRACTION OVERWRITES THE SNAPSHOT. The dataset is live (records are added and corrected),
so a later extraction can differ from the shipped one; compare the sha256 values in
manifest.json before and after.

OUTPUTS (data/processed/nominate_snapshot/):
  legislative_periods.csv   period id, label (LI..LVI), start/end dates
  votes.csv.gz              one row per roll call: vote_id, external_id (the chamber's own
                            roll-call id; missing for every Senate vote), vote_date, source
                            (chamber|senate), period, session_id, type, result, bill_id,
                            article, recorded tallies (in_favor, against, abstention,
                            dispensed, pareo), topic. The database holds re-ingested copies of
                            many Chamber roll calls (same external_id, new vote_id); they are
                            kept here and removed in 15b.
  vote_selections.csv.gz    long vote matrix: selection_id, vote_id, politician_id, selection
                            (raw label: Afirmativo/Si, En Contra/No, Abstencion, No Vota,
                            Pareo, Dispensado)
  politician_periods.csv    raw term records for the members who voted: term_id,
                            politician_id, position (DIP/SEN), start_year, end_year, party_id,
                            district (raw representation-unit name; missing for the
                            designated and lifetime senators of 2002-06)
  political_parties.csv     party id -> name
  legislators.csv           one row per politician x chamber x period with >= 1 recorded
                            vote: politician_id, chamber, period, label, first_name,
                            fathers_surname, mothers_surname, bcn_id (Biblioteca del Congreso
                            id), term_id, party_id, party_name, district of the matching term,
                            party_source (term_same_chamber | term_other_chamber |
                            no_term_record), n_selections
  manifest.json             query text + parameters, extraction timestamp (UTC), dataset,
                            row counts, sha256 of every file above
Only public roll-call information is extracted: names, party, and recorded votes.
"""
import datetime as dt
import gzip
import hashlib
import io
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _measure_helpers import DATA, skip  # noqa: E402  (repo-anchored paths, SKIP code 3)

BQ_PROJECT = "datos-congreso-461817"
BQ_DATASET = "datos-congreso-461817.datos_congreso"
KEY_ENV = "CONGRESO_BQ_KEY"
DATE_FROM = "2002-03-11"          # start of period LI (first chamber roll call: 2002-03-19)
DATE_TO = "2026-03-10"            # end of period LVI (LVII is ongoing and excluded)
MAX_BYTES = 2 * 10**9             # refuse any query whose dry run exceeds 2 GB
SNAP = DATA / "nominate_snapshot"
POSITION_OF = {"chamber": "DIP", "senate": "SEN"}

# ------------------------------------------------------------------ access guard
key_path = os.environ.get(KEY_ENV, "")
if not key_path or not Path(key_path).is_file():
    skip(f"{KEY_ENV} unset or not a file; using the shipped snapshot in {SNAP}")
try:
    from google.cloud import bigquery
    from google.oauth2 import service_account
except ImportError:
    skip("google-cloud-bigquery / google-auth not installed; using the shipped snapshot")

credentials = service_account.Credentials.from_service_account_file(key_path)
client = bigquery.Client(project=BQ_PROJECT, credentials=credentials)
del key_path  # the path is not needed (or recorded) past this point

PARAMS = [
    bigquery.ScalarQueryParameter("date_from", "DATE", DATE_FROM),
    bigquery.ScalarQueryParameter("date_to", "DATE", DATE_TO),
]
DS = BQ_DATASET
QUERIES = {
    "legislative_periods": f"""
        SELECT id AS period_id, name AS period_name, DATE(start) AS start_date,
               DATE(`end`) AS end_date
        FROM `{DS}.legislative_periods`
        WHERE DATE(start) >= @date_from AND DATE(`end`) <= @date_to
        ORDER BY period_id""",
    "votes": f"""
        SELECT id AS vote_id, external_id, vote_date, source, session_id, type, result,
               bill_id, article, in_favor, against, abstention, dispensed, pareo, topic
        FROM `{DS}.votes`
        WHERE vote_date BETWEEN @date_from AND @date_to
        ORDER BY vote_id""",
    "vote_selections": f"""
        SELECT vs.id AS selection_id, vs.vote_id, vs.politician_id, vs.selection
        FROM `{DS}.vote_selections` vs
        JOIN `{DS}.votes` v ON v.id = vs.vote_id
        WHERE v.vote_date BETWEEN @date_from AND @date_to
        ORDER BY selection_id""",
    "politicians": f"""
        SELECT p.id AS politician_id, p.first_name, p.fathers_surname, p.mothers_surname,
               p.bcn_id
        FROM `{DS}.politicians` p
        WHERE p.id IN (
          SELECT DISTINCT vs.politician_id
          FROM `{DS}.vote_selections` vs JOIN `{DS}.votes` v ON v.id = vs.vote_id
          WHERE v.vote_date BETWEEN @date_from AND @date_to)
        ORDER BY politician_id""",
    "politician_periods": f"""
        SELECT pp.id AS term_id, pp.politician_id, pp.position, pp.start_year, pp.end_year,
               pp.party_id, pp.representation_unit_raw_name AS district
        FROM `{DS}.politician_periods` pp
        WHERE pp.end_year >= EXTRACT(YEAR FROM @date_from)
          AND pp.start_year <= EXTRACT(YEAR FROM @date_to)
          AND pp.politician_id IN (
            SELECT DISTINCT vs.politician_id
            FROM `{DS}.vote_selections` vs JOIN `{DS}.votes` v ON v.id = vs.vote_id
            WHERE v.vote_date BETWEEN @date_from AND @date_to)
        ORDER BY term_id""",
    "political_parties": f"""
        SELECT id AS party_id, name AS party_name
        FROM `{DS}.political_parties`
        ORDER BY party_id""",
}


def run_query(name: str, sql: str) -> tuple[pd.DataFrame, int]:
    """Dry-run (bytes check), then run; returns the frame and the dry-run byte count."""
    uses_params = "@date_" in sql
    dry = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False,
            query_parameters=PARAMS if uses_params else []),
    )
    n_bytes = int(dry.total_bytes_processed or 0)
    print(f"[15a] {name}: dry run {n_bytes / 1e6:.1f} MB", flush=True)
    if n_bytes > MAX_BYTES:
        raise SystemExit(f"[15a] {name}: dry run exceeds {MAX_BYTES / 1e9:.0f} GB; aborting")
    job = client.query(
        sql, job_config=bigquery.QueryJobConfig(query_parameters=PARAMS if uses_params else []))
    df = job.to_dataframe()
    print(f"[15a] {name}: {len(df):,} rows", flush=True)
    return df, n_bytes


frames, dry_bytes = {}, {}
for qname, qsql in QUERIES.items():
    frames[qname], dry_bytes[qname] = run_query(qname, qsql)

lp = frames["legislative_periods"].copy()
votes = frames["votes"].copy()
sel = frames["vote_selections"].copy()
pol = frames["politicians"].copy()
terms = frames["politician_periods"].copy()
parties = frames["political_parties"].copy()

# ------------------------------------------------------------------ periods
ROMAN = lp.period_name.str.extract(r"^([IVXL]+)\s")[0]
lp["period"] = ROMAN
lp["start_date"] = pd.to_datetime(lp.start_date)
lp["end_date"] = pd.to_datetime(lp.end_date)
lp["label"] = lp.start_date.dt.year.astype(str) + "-" + (lp.start_date.dt.year + 4).astype(str)
lp = lp[["period_id", "period", "label", "start_date", "end_date", "period_name"]]
if lp.period.isna().any() or len(lp) != 6:
    raise SystemExit(f"[15a] expected the six periods LI..LVI, got {lp.period.tolist()}")

votes["vote_date"] = pd.to_datetime(votes.vote_date)
bins = pd.IntervalIndex.from_arrays(lp.start_date, lp.end_date, closed="both")
idx = bins.get_indexer(votes.vote_date)
if (idx < 0).any():
    raise SystemExit(f"[15a] {int((idx < 0).sum())} votes fall outside every period")
votes["period"] = lp.period.to_numpy()[idx]
votes = votes[["vote_id", "external_id", "vote_date", "source", "period", "session_id",
               "type", "result", "bill_id", "article", "in_favor", "against",
               "abstention", "dispensed", "pareo", "topic"]]
for c in ["external_id", "session_id", "bill_id"]:
    votes[c] = votes[c].astype("Int64")

# ------------------------------------------------------------------ legislators
sv = sel.merge(votes[["vote_id", "source", "period"]], on="vote_id", how="left",
               validate="many_to_one")
leg = (sv.groupby(["politician_id", "source", "period"], as_index=False)
         .agg(n_selections=("selection_id", "size")))
leg = leg.merge(lp[["period", "label", "start_date", "end_date"]], on="period", how="left")
leg["p0"] = leg.start_date.dt.year
leg["p1"] = leg.p0 + 4

# party of the term that covers the chamber-period: same position (DIP/SEN), overlapping
# years; if several overlap, the longest overlap, then the latest start. Fallback: a term
# in the other chamber overlapping the period (members who switched). Otherwise none.
cand = leg[["politician_id", "source", "period", "p0", "p1"]].merge(
    terms, on="politician_id", how="inner")
cand = cand[(cand.start_year < cand.p1) & (cand.end_year > cand.p0)].copy()
cand["same_pos"] = cand.position.to_numpy() == cand.source.map(POSITION_OF).to_numpy()
cand["overlap"] = (np.minimum(cand.end_year, cand.p1) - np.maximum(cand.start_year, cand.p0))
cand = cand.sort_values(["politician_id", "source", "period", "same_pos", "overlap",
                         "start_year", "term_id"],
                        ascending=[True, True, True, False, False, False, True])
best = cand.drop_duplicates(["politician_id", "source", "period"], keep="first")
best = best.assign(party_source=np.where(best.same_pos, "term_same_chamber",
                                         "term_other_chamber"))
leg = leg.merge(best[["politician_id", "source", "period", "term_id", "party_id",
                      "district", "party_source"]],
                on=["politician_id", "source", "period"], how="left", validate="one_to_one")
leg["party_source"] = leg.party_source.fillna("no_term_record")
leg = leg.merge(parties, on="party_id", how="left")
leg = leg.merge(pol, on="politician_id", how="left", validate="many_to_one")
leg = leg.rename(columns={"source": "chamber"})
leg = leg[["politician_id", "chamber", "period", "label", "first_name", "fathers_surname",
           "mothers_surname", "bcn_id", "term_id", "party_id", "party_name",
           "district", "party_source", "n_selections"]]
leg = leg.sort_values(["chamber", "period", "politician_id"]).reset_index(drop=True)
for c in ["bcn_id", "term_id", "party_id"]:
    leg[c] = leg[c].astype("Int64")

# ------------------------------------------------------------------ write + manifest
SNAP.mkdir(parents=True, exist_ok=True)


def write_csv(df: pd.DataFrame, name: str) -> Path:
    """UTF-8 CSV; .gz files are written with mtime 0 so the bytes are deterministic."""
    path = SNAP / name
    if name.endswith(".gz"):
        buf = io.StringIO()
        df.to_csv(buf, index=False, lineterminator="\n")
        with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0,
                                                    filename="") as gz:
            gz.write(buf.getvalue().encode("utf-8"))
    else:
        df.to_csv(path, index=False, lineterminator="\n", encoding="utf-8")
    return path


lp_out = lp.assign(start_date=lp.start_date.dt.date, end_date=lp.end_date.dt.date)
votes_out = votes.assign(vote_date=votes.vote_date.dt.date)
outputs = {
    "legislative_periods.csv": lp_out,
    "votes.csv.gz": votes_out,
    "vote_selections.csv.gz": sel.sort_values("selection_id"),
    "politician_periods.csv": terms.sort_values("term_id"),
    "political_parties.csv": parties.sort_values("party_id"),
    "legislators.csv": leg,
}
files = {}
for fname, df in outputs.items():
    path = write_csv(df, fname)
    files[fname] = {"rows": int(len(df)),
                    "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                    "bytes": path.stat().st_size}

n_dup = int(sel.duplicated(["vote_id", "politician_id"]).sum())
manifest = {
    "description": "Roll-call snapshot for the NOMINATE appendix (Elitism in the Aisle, "
                   "R&R 2026). Produced by scripts/15a_extract_rollcalls_bq.py.",
    "source": {"bigquery_project": BQ_PROJECT, "dataset": BQ_DATASET,
               "provider": "IMFD datos congreso (Camara de Diputados / Senado roll calls)"},
    "extracted_at_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "window": {"date_from": DATE_FROM, "date_to": DATE_TO,
               "periods": lp.period.tolist()},
    "queries": {k: {"sql": " ".join(v.split()), "dry_run_bytes": dry_bytes[k]}
                for k, v in QUERIES.items()},
    "query_parameters": {"date_from": DATE_FROM, "date_to": DATE_TO},
    "files": files,
    "checks": {"duplicate_vote_politician_pairs": n_dup,
               "legislators_without_term_record": int((leg.party_source ==
                                                        "no_term_record").sum()),
               "legislators_without_party": int(leg.party_id.isna().sum())},
    "software": {"python": sys.version.split()[0], "pandas": pd.__version__,
                 "google-cloud-bigquery": bigquery.__version__},
}
(SNAP / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                    encoding="utf-8")
print(json.dumps({k: v["rows"] for k, v in files.items()}, indent=1))
print(f"[15a] duplicate (vote, politician) pairs: {n_dup}")
print(f"[15a] snapshot written to {SNAP}")
