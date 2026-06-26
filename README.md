# Replication — *Elitism in the Aisle: Class Background and Legislative Representation in Chile, 1830–2020*

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
1925 break (−11.3 vs. the deposited −13.3 points), a difference that reflects the reconciliation
step alone, not the finding. All reported numbers use the deposited canonical list.

## How to run
`bash scripts/00_run_all.sh` runs the full pipeline in dependency order (Python 3 and
`Rscript` on PATH). Or run the numbered scripts individually, in order, per the table below.

**Computational requirements.** A 16 GB laptop is sufficient. End-to-end runtime is
~30–45 min, **excluding** two heavy/optional steps: the STM fit (script 11, ~20 min) and
the BCN biography harvest (scripts 08–10, several hours, Anthropic-API-bound — its outputs
are already shipped in `data/processed/`, so 08–10 can be skipped). No GPU required.

## Pipeline (run in order)
| # | Script | Produces |
|---|---|---|
| 01 | `surname_ses_padron.py` | per-surname mean SES from the 2020 padrón → `surname_nse.csv` |
| 02 | `build_enduring_elite.py` | the two-gate surname list → `enduring_elite_FINAL.csv` |
| 02b | `business_gate_additions.py` | adds the 13 business-leader-route surnames → final 298-surname list |
| 03 | `population_reference.py` | dynamic surname prevalence 1884–2020 (Registro Civil) → `pop_prevalence_by_year.csv` |
| 04 | `figure2_composition.py` | **Figure 2** — elite/common share of Congress vs. population |
| 05 | `its_1925.py` | interrupted time series at the 1925 salary reform |
| 06 | `validation_lineage_bios.py` | homogamy, Club de la Unión, schooling validations |
| 07 | `centrality_figVI.py` | **Figure VI** — family-network centrality by surname type |
| 08–10 | `bcn_*` | harvest + LLM-extract + quality-correct BCN biographies (individual validation) |
| 11 | `stm_topics.R` | 80-topic STM on 1910–50 speeches (prevalence ~ surname + party + chamber + year) |
| 12b | `stm_estimateEffect_298.R` | **Table 1** — re-estimates topic prevalence on the 298 coding (use this, not the deprecated `12`) |
| 13 | `topic_theme_effects.R` | macro-theme topic-emphasis figure (clustered by legislator) |
| 14 | `tbip_ideal_points.R` | **Table 2** — text-based ideal points by surname type |
| 15 | `nominate_convergent_validity.py` | appendix: surname → W-NOMINATE, 2014–2026 |
| 16 | `its_placebo_bandwidth.py` | appendix: 1925 break-year placebo + estimation-window sweep |
| 17 | `survivorship_bound.py` | appendix: survivorship lower bound on the early elite share |
| 18 | `cutoff_sensitivity.py` | appendix: sensitivity of composition to the SES cutoff |
| 19 | `stm_theme_table.py` | appendix: theme-level topic contrast with multiplicity statement |
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

Scripts 26–36 are the revision-round (R&R) robustness and inference checks. Scripts
27/28/31/35/36 depend on the STM fit (script 11) and the speech corpus; scripts 06/24/34
read the harvested BCN biographies, which are **not redistributed** (see Data).

## Data
`data/processed/` ships the small derived files (surname lists, yearly prevalence, topic
coefficients, validation tables). **Large source data are not redistributed here** — point
the scripts at them via the paths in each header:
- 2020 electoral roll w/ SES: `geo_padron/geo_padron_2020/padron_2020_nse_surnames.csv` (~4M rows)
- Registro Civil births 1884–2020: `Registro Civil/HISTORICO/` (~23M rows)
- 1874 agricultural census: `censo_agricola/1874/censo_1874.csv`
- 19th-c. elite compilations: `Chile - elite networks.xlsx`
- Legislative speeches 1910–50: `intervenciones.csv` (BCN OCR)
- W-NOMINATE estimates: companion project `2026_graph_based_ideal_points/`
- Family network: fetched in-script from the author's site (Bro 2023)
- BCN legislator biographies (harvested by scripts 08–10, used by scripts 06/24/34 for the
  Club de la Unión / elite-school / homogamy markers): the full extracted JSON
  (`extract_sonnet_corrected.json`) is scraped *reseñas* text and is **not redistributed**;
  only the 20-biography gold standard (`bcn_gold_standard_20.json`) is shipped. The biographical
  validation rates therefore cannot be regenerated from this public repo; the retrieval and
  extraction procedure is documented in scripts 08–10 and the online appendix.

## Requirements
Python 3 (`pandas numpy scipy statsmodels matplotlib networkx anthropic`) and R
(`dplyr tidyr ggplot2 stm quanteda tidytext sandwich lmtest stargazer`). Script 09 (BCN
extraction) calls the Anthropic API. See the paper's online appendix for full provenance.

_Paper and online appendices: [link to be added]. This repository is linked from the manuscript._
