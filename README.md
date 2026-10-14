# Replication — *Elitism in the Aisle: A Long-Run Surname Measure of Legislative Elite Composition in Chile, 1834–2020*

Replication code and processed data for the surname-based measure of legislative elite
composition and its validation. Naim Bro (Universidad Adolfo Ibáñez, Fondecyt 11251464).

## What this measures
A **replicable, surname-based measure of the "enduring elite"** — 298 surnames that were
elite *then* (1874 land census + 19th-c. elite compilations) **and** are still high-status
*now* (2020 electoral-roll SES or over-representation among ~5,400 business leaders) —
applied uniformly to every Chilean legislator, 1830–2020, to study how the class composition
of Congress shaped its discourse and priorities. The deposited `enduring_elite_FINAL.csv`
(298 surnames, including the 13 business-leader-route additions) is the **frozen canonical
input**: it is the exact list used for every result in the paper. Scripts `02`/`02b` rebuild
it deterministically from the raw sources, and the few manual source-spelling reconciliations
between that rebuild and the deposited list are logged and auditable in the script comments;
the deterministic rebuild recovers most but not all surnames and yields a slightly smaller
1925 break (−9.1 vs. the deposited −11.0 points; −11.3 vs. −13.3 before the R&R 2026 correction
described under *Methods notes*), a difference that reflects the business-route surnames, not
the finding. All reported numbers use the deposited canonical list.

## How to run
`bash scripts/00_run_all.sh` runs the pipeline in dependency order (Python 3 and `Rscript` on
PATH; override with `PY=... R=...`) and ends with an OK / SKIP summary. Or run the numbered
scripts individually, in order, per the table below.

- **Flags.** `RUN_STM=0` (default) skips the text-model steps (STM fit and everything that reads
  it, plus the TBIP steps 14/21/25), which need the non-public speech corpus; `RUN_STM=1` runs
  them (those scripts have no SKIP guard, so with `RUN_STM=1` a missing corpus makes the run
  **fail**, not skip). `REBUILD_MEASURE=0` (default) skips the measure build 01/02/02b/03: the canonical inputs
  are shipped in `data/processed/`, script 02 calls the Anthropic API, and 02b **overwrites**
  the frozen `enduring_elite_FINAL.csv`. `HAVE_PADRON`, `HAVE_BIOS`, `HAVE_RAW`,
  `HAVE_REGCIV`, `HAVE_NET` (default `auto`) can be set to `0` to skip the steps
  that need those sources. `HAVE_BQ=0` (default) skips the BigQuery re-extraction of the
  roll-call snapshot (15a); the NOMINATE steps 15b and 15 always run from the shipped snapshot.
  `HAVE_BQ=1` runs 15a, which needs `CONGRESO_BQ_KEY` (path to a service-account key for
  the IMFD `datos-congreso` BigQuery project; SKIP if unset) and **overwrites** the snapshot
  with the live database.
- **Missing data.** A script whose non-redistributed inputs are absent exits with code 3 and
  the runner reports it as SKIP, so a stand-alone clone of this repo runs to the end.
- **Working directory and outputs.** Non-STM scripts anchor their paths on the repo and run
  from any directory. Tables are written to `tables/`, figures to `figures/`, and both are
  copied to `../paper/{tables,figures}` only if that manuscript tree exists (`PAPER_DIR`
  overrides its location). The STM scripts that read the corpus from the project directory
  (11, 12b, 13, 14, 27, 28, 31, 35, 36, 39, 42, 46a) run from the parent of `replication_repo/`.

**Python environment.** If the local `numpy`/`pandas` binaries are mismatched (for example a
Windows install with numpy 2.x and a pandas built against numpy 1.x, which fails on
`import pandas`), run the Python steps under WSL/Linux `python3`
(e.g. `wsl.exe -e bash -lc "cd /mnt/c/.../replication_repo && python3 scripts/05_its_1925.py"`).
The R&R 2026 outputs were produced that way (Python 3 with pandas 2.1, numpy 1.26,
statsmodels 0.14); R scripts ran under R 4.3.3.

**Computational requirements.** A 16 GB laptop is sufficient. With `RUN_STM=0` and all data
present the run takes roughly 15–25 min (scripts 38 and 40 read the 23M-row Registro Civil),
plus about 45 min for script 15b (24 W-NOMINATE fits, single-threaded; the 2-D Chamber fits
dominate).
The heavy/optional steps are excluded: the STM fit (script 11, ~93 min) and the BCN biography
harvest/extraction (scripts 08–10, 08b, 09c; several hours, Anthropic-API-bound). The harvest's
outputs are **not** shipped: they live outside the repo under `RAW_DATA_ROOT` (see Data), so
the biography steps (24, 34, 38) SKIP without them. No GPU required.

## Pipeline (run in order)
| # | Script | Produces |
|---|---|---|
| 01 | `surname_ses_padron.py` | per-surname mean SES from the 2020 padrón → `surname_nse.csv` |
| 02 | `build_enduring_elite.py` | the two-gate surname list → `enduring_elite_FINAL.csv` |
| 02b | `business_gate_additions.py` | adds the 13 business-leader-route surnames → final 298-surname list |
| 03 | `population_reference.py` | dynamic surname prevalence 1884–2020 (Registro Civil) → `pop_prevalence_by_year.csv` |
| 04 | `figure2_composition.py` | **Figure 2** — elite/common share of Congress vs. population |
| 05 | `its_1925.py` | **Figure 4** — interrupted time series around the 1925 Constitution (break at 1925; 1925 itself has no sitting Congress) |
| 06 | `validation_lineage_bios.py` | *retired (R&R 2026)*: homogamy / Club / school on the lost v1 extraction; not run by `00_run_all.sh`, outputs no longer used in the paper |
| 06c | `validation_figure_3group.py` | **Figure 1** — Club / elite-school rates by surname group (reads script 34's output; run after 34) |
| 07 | `centrality_figVI.py` | **Figure VI** — family-network centrality by surname type |
| 08–10 | `bcn_*` | harvest + LLM-extract + quality-correct BCN biographies (individual validation) |
| 11 | `stm_topics.R` | 80-topic STM on 1910–50 speeches (prevalence ~ surname + party + chamber + year) |
| 12b | `stm_estimateEffect_298.R` | **Table 1** — re-estimates topic prevalence on the 298 coding (use this, not the deprecated `12`) |
| 13 | `topic_theme_effects.R` | theme-level elite / common emphasis on the 298 coding, party-adjusted, legislator-clustered SEs → `data/processed/theme_effects.csv` (= the party-adjusted column of 39; the earlier 285-list output is kept as `theme_effects_285.csv` for 39's reproduction check) |
| 14 | `tbip_ideal_points.R` | **Table 2** — text-based ideal points by surname type |
| 15a | `extract_rollcalls_bq.py` | roll-call snapshot (Chamber + Senate, 2002–2026 roll calls, votes, surnames, party per term) from the IMFD BigQuery dataset → `data/processed/nominate_snapshot/` (with `manifest.json`: queries, date, row counts, sha256). Needs `HAVE_BQ=1` + `CONGRESO_BQ_KEY` |
| 15b | `wnominate_by_period.R` | W-NOMINATE (defaults: 2 dims, lop 0.025, minvotes 20; UDI-anchored polarity) per chamber × legislative period, from the snapshot → `output/nominate/wnominate_coords.csv`, `wnominate_fitstats.csv` |
| 15 | `nominate_convergent_validity.py` | appendix: surname group / surname SES → W-NOMINATE dim 1 (pooled, period×chamber FE, legislator-clustered SEs; with/without party) → every appendix number, `tables/table_appendix_nominate.tex`, `figures/figure_appendix_nominate.pdf/.png`; runs after 15b |
| 16 | `its_placebo_bandwidth.py` | appendix: 1925 break-year placebo + estimation-window sweep |
| 17 | `survivorship_bound.py` | appendix: survivorship lower bound on the early elite share |
| 18 | `cutoff_sensitivity.py` | appendix: sensitivity of composition to the SES cutoff |
| 19 | `stm_theme_table.py` | theme-level contrast + topic multiplicity counts (reads 13) → `tables/table_stm_themes.tex`, `data/processed/stm_theme_summary.csv`; *superseded*: the table is not `\input` in the paper (Table 1 comes from 39) |
| 20 | `figure2_reshade.py` | appendix: Figure 2 pre-1884 reshade |
| 21 | `tbip_family_cluster_se.R` | family-clustered SE on the continuous-status ideal-point coefficient |
| 22 | `coding_rule_sensitivity.py` | appendix: composition + 1925 break under permissive / strict / paternal codings |
| 24 | `bio_coverage_by_group.py` | appendix: biography-coverage rate by surname group + reweighted fold-gaps |
| 25 | `tbip_permutation.R` | appendix: legislator-level permutation test + family-clustered SE for the categorical ideal-point contrast |
| 26 | `topic_theme_crosswalk.py` | appendix: topic-to-theme crosswalk (which of the 80 STM topics maps to each theme) |
| 27 | `within_elite_trajectory.R` | appendix §H.6: within-group labor-and-industry slope, 1910–49 (mobilization confound) |
| 28 | `stm_uncertainty_methodofcomposition.R` | appendix: propagates STM topic-estimation (θ) uncertainty into Table 1 + the §H.6 slope, by method of composition |
| 29 | `business_route_robustness.py` | appendix: 1925 break under dropping the 13 business-route surnames + threshold sweep |
| 30 | `depth_gate_robustness.py` | appendix: 1925 break under the stricter persistence-depth ≥2 gate |
| 31 | `statecraft_trajectory.R` | appendix §H.6: within-group statecraft slope (mirror of the labor result) |
| 32 | `two_dynasty_leaveout.py` | appendix: 1925 break dropping only Portales+Balmaceda (and +Bulnes+García-Huidobro) |
| 33 | `depth_monotonicity.py` | appendix: 1925 break + 1860s/2010s shares across persistence-depth gates ≥1/≥2/≥3/≥4 |
| 34 | `common_pole_validation.py` | appendix: symmetric common-pole biographical marker rates (club / elite school) — *needs non-public bios, see Data* |
| 35 | `theme_contrast_pvalues.R` | appendix: legislator-clustered p-values on the elite−common contrast for each Table 1 theme |
| 36 | `seed_robustness.R` | appendix: second-seed / B=200 confirmation of the §H.6 method-of-composition slope test |
| 37 | `franchise_breaks.R` | R&R A1: break tests at franchise/electoral events, legislature steps, Bai–Perron, event-comparison table |
| 38 | `validation_by_period.py` | R&R A2: validation by era (biographical markers, Senate vs. Chamber, party blocs, construction placebos) — *needs non-public bios* |
| 39 | `theme_effects_unconditional.R` | R&R A3: theme effects without party (STM second stage) — *added after the STM refit decision* |
| 40 | `cutoff_interpretation.py` | R&R A4: what the SES ≥ 65 and over-representation ≥ 8 cutoffs capture |
| 41 | `its_corrected_reruns.R` | R&R A1/E1: reproduces every submitted 1925 number and recomputes it with 1925 as a gap |
| 42 | `stm_refit_298_noparty.R` | R&R D14: STM refit on the 298 coding without party in the prior — *added after the STM refit decision* |
| 43 | `rnr_appendix_tables.py` | R&R appendix tables: event comparison (verbatim from 37) and validation by era (from 38) |
| 45 | `event_comparison_allmembers.py` | R&R appendix table `tab:eventcomparison`: all-member columns of the 37 event comparison (legislature step, ±25-year ITS) |
| 46a | `stm_prevalence_at_means_298.R` | topic prevalence at the covariate means (12b's tercile-rule input) recomputed from 12b's `stm_prep_298.rds` → `output/stm_topic_prevalence_at_means_298.csv`; checks it reproduces 12b's selection. Runs from the project root (`RUN_STM=1`) |
| 46 | `stm_topic_coef_table.py` | appendix `tab:stmcoefs` (topic-level illustration): 12b's tercile rule minus the topics the crosswalk assigns to *Other*; coefficients from `output/table1_topic_coefs_298.csv` → `tables/table_stm_topic_coefs.tex`. Reads shipped CSVs only |

Scripts 26–36 are the revision-round (R&R) robustness and inference checks; 37–43 answer the
2026 Research & Politics review. Scripts 27/28/31/35/36/39/42 depend on the STM fit (script 11)
and the speech corpus; scripts 06/24/34/38 read the harvested BCN biographies, which are **not
redistributed** (see Data).

## Methods notes
- **Annual elite share and the n < 5 rule.** The enduring-elite share of Congress in year *t*
  is the share of legislators sitting in *t* (Start ≤ *t* ≤ End, all roster rows including
  pre-1891 substitutes) with an elite paternal or maternal surname. Years with **fewer than 5
  sitting legislators have an undefined share and are dropped** (shared helper
  `_measure_helpers.annual_share`, used by every 1925 ITS script: 05, 16, 18, 22, 29, 30, 32,
  33, including the smoothed and snapshot shares in 18/22; the composition scripts 04/17/20 and
  the R scripts 37/41 apply the same n >= 5 rule inline). Congress did not sit in 1925
  (dissolved September 1924, reconvened March 1926), so 1925 is a gap in the series.
  *Correction (R&R 2026):* the submitted version computed elite / max(n, 1) in the ITS
  scripts, which entered 1925 as a 0% share. With the correction the headline 1925 level
  shift is −11.01 points (HAC SE 2.95, p = 0.0002), not −13.32; every robustness number
  moves 0.4–3.0 points toward zero, and the break-year placebo profile is flat over roughly
  1918–1927 (maximum at 1926 by 0.05 points). Script 41 documents old and new values.
- **ITS specification.** elite ~ t + post + t·post on annual shares, 1880–1970 unless stated,
  HAC (Newey–West, Bartlett, 5 lags) standard errors, normal p-values. The HAC lags count
  *rows*, not calendar years: once 1925 is dropped, 1924 and 1926 are adjacent observations
  in the lag window (statsmodels and R `sandwich::NeweyWest` treat the gap the same way).
- **Biographical markers.** Club de la Unión = regex `CLUB DE LA UNION` on the de-accented
  biography text; elite private school = script 10's regex on the extracted secondary school,
  entry from 1900. Since the R&R, scripts 24/34 read the persistent v2 extraction (see Data);
  the reweighted Club fold in script 24 now uses the Club regex (the submitted version used
  the broader LLM `elite_club` field).

## Data
`data/processed/` ships the small derived files (surname lists, yearly prevalence, topic
coefficients, validation tables). **Large source data are not redistributed here** — point
the scripts at them via the paths in each header:
- 2020 electoral roll w/ SES: `geo_padron/geo_padron_2020/padron_2020_nse_surnames.csv` (~4M rows)
- Registro Civil births 1884–2020: `Registro Civil/HISTORICO/` (~23M rows)
- 1874 agricultural census: `censo_agricola/1874/censo_1874.csv`
- 19th-c. elite compilations: `Chile - elite networks.xlsx`
- Legislative speeches 1910–50: `intervenciones.csv` (BCN OCR)
- Roll calls 2002–2026 (NOMINATE appendix): **shipped** as a frozen snapshot in
  `data/processed/nominate_snapshot/` (public roll-call records: names, party, recorded votes),
  extracted by script 15a from the IMFD `datos-congreso` BigQuery dataset; `manifest.json`
  records the queries, extraction date and file hashes. No credentials are needed to rerun 15b/15.
- `data/processed/legacy/`: superseded files kept for the record; no script reads them.
- Family network: fetched in-script from the author's site (Bro 2023)
- BCN legislator biographies (harvested by scripts 08b/09c, used by scripts 24/34/38 for the
  Club de la Unión / elite-school markers): the persistent 2026-07-10 re-harvest
  (`data/raw/bcn_wayback/*.txt`, Internet Archive copies of the *reseñas*) and its extraction
  (`data/processed/bcn_extract_v2.json`, 3,417 biographies) sit under `RAW_DATA_ROOT` and are
  scraped text, **not redistributed**; only the 20-biography gold standard
  (`bcn_gold_standard_20.json`) is shipped. The biographical rates are therefore regenerable
  only with that corpus; the retrieval and extraction procedure is documented in scripts
  08–10 / 08b / 09c and the online appendix. (The submitted version used an earlier
  extraction, `extract_sonnet_corrected.json`, 3,174 biographies, which no longer exists;
  script 06 still points to it.)

## Requirements
Python 3 (`pandas numpy scipy statsmodels matplotlib networkx anthropic`; optional
`google-cloud-bigquery google-auth` for script 15a only) and R (`dplyr tidyr ggplot2 stm
quanteda tidytext sandwich lmtest stargazer data.table readxl stringi wnominate pscl
R.utils`; `data.table readxl stringi` are used by the R&R scripts 37 and 41, `wnominate pscl
R.utils` by script 15b; the NOMINATE rebuild ran under wnominate 1.5 and pscl 1.5.9). Script 09 (BCN
extraction) calls the Anthropic API. See the paper's online appendix for full provenance.

_Paper and online appendices: [link to be added]. This repository is linked from the manuscript._
