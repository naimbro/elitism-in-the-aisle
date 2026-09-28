#!/usr/bin/env bash
# Master replication script — Elitism in the Aisle (Bro & Luna, R&P)
# Runs the pipeline in dependency order and prints an OK / SKIP summary at the end.
#
# Usage:  bash scripts/00_run_all.sh
#         PY=python3 R=Rscript RUN_STM=0 bash scripts/00_run_all.sh
#
# FLAGS (environment variables)
#   RUN_STM=0          (default) do NOT run the text-model steps: STM fit and everything that
#                      reads it (11, 12b, 46a, 13, 19, 26, 27, 28, 31, 35, 36, 42fit/42; 39 after the
#                      refit decision) and the TBIP steps (14, 21, 25). They need the non-public speech
#                      corpus; 11 refits the STM (~93 min) and 25 runs 10,000 permutations.
#                      Set RUN_STM=1 to run them (STM/TBIP scripts that read the corpus from the
#                      project dir run from the parent of the repo directory, whose name is
#                      taken from $PWD as REPO_NAME). NOTE: the STM/TBIP scripts have no SKIP
#                      guard, so with RUN_STM=1 a missing speech corpus makes the run FAIL
#                      (non-zero exit), not SKIP.
#   REBUILD_MEASURE=0  (default) do NOT rebuild the surname measure (01, 02, 02b, 03). The
#                      canonical inputs are shipped in data/processed/. WARNING: 02 calls the
#                      Anthropic API and 02b OVERWRITES data/processed/enduring_elite_FINAL.csv
#                      (the frozen canonical list); 01/02/03 write to /tmp only.
#   HAVE_PADRON, HAVE_BIOS, HAVE_RAW (1874 censo + elite workbook), HAVE_REGCIV (Registro
#   Civil), HAVE_NET (network download):
#                      default "auto" = run the step and let the script check its inputs;
#                      set to 0 to skip the step without running it.
#   HAVE_BQ=0          (default) do NOT re-extract the roll-call snapshot (15a) from BigQuery.
#                      15b (W-NOMINATE) and 15 (appendix numbers + figure) always run from the
#                      shipped snapshot in data/processed/nominate_snapshot/. HAVE_BQ=1 runs 15a,
#                      which needs CONGRESO_BQ_KEY=<service-account key path> (else it SKIPs) and
#                      OVERWRITES the snapshot with the live database (check manifest.json).
#
# SKIPS: a script whose non-redistributed inputs are absent exits with code 3; this runner
# reports it as SKIP and continues. Any other non-zero exit stops the run.
# OUTPUTS: scripts write inside the repo (output/, tables/, figures/, data/processed/) and copy
# manuscript tables/figures to ../paper/{tables,figures} only if that tree exists.
# PYTHON: if the local numpy/pandas binaries are mismatched (e.g. Windows numpy 2.x with a pandas
# built for numpy 1.x), run under WSL/Linux python3.
# Runtime (RUN_STM=0, all data present): ~15-25 min on a 16 GB laptop (38 and 40 read the
# 23M-row Registro Civil), plus ~45 min for 15b (24 W-NOMINATE fits; the 2-D Chamber fits
# dominate). With RUN_STM=1 add ~93 min for the STM fit, ~1.7 h for the A5 refit
# (42fit, only if its rds is absent), plus the TBIP steps.
# The BCN biography harvest/extraction (08-10, 08b, 09c) is never run here: it is API-bound and
# its outputs (data/raw/bcn_wayback, data/processed/bcn_extract_v2.json) live OUTSIDE the repo
# under RAW_DATA_ROOT and are NOT redistributed.
set -uo pipefail
cd "$(dirname "$0")/.."
REPO_NAME=$(basename "$PWD")              # repo directory name, used by root_run invocations

PY=${PY:-python3}
R=${R:-Rscript}
RUN_STM=${RUN_STM:-0}
REBUILD_MEASURE=${REBUILD_MEASURE:-0}
HAVE_PADRON=${HAVE_PADRON:-auto}
HAVE_BIOS=${HAVE_BIOS:-auto}
HAVE_RAW=${HAVE_RAW:-auto}
HAVE_REGCIV=${HAVE_REGCIV:-auto}
HAVE_NET=${HAVE_NET:-auto}
HAVE_BQ=${HAVE_BQ:-0}
SKIP_CODE=3
OK=(); SKIPPED=()

root_run() { (cd .. && "$@"); }            # run a command from the project root (repo parent)
gate() {                                   # gate FLAG... -> "0" if any flag is 0, else "1"
  local v; for v in "$@"; do [ "$v" = 0 ] && { echo 0; return; }; done; echo 1
}
summary() {
  echo; echo "== SUMMARY =="
  echo "OK      (${#OK[@]}): ${OK[*]:-}"
  echo "SKIPPED (${#SKIPPED[@]}): ${SKIPPED[*]:-}"
}
step() {                                   # step TAG GATE command...
  local tag=$1 on=$2; shift 2
  echo; echo "== [$tag] $* =="
  if [ "$on" = 0 ]; then
    echo "-- SKIP [$tag] (disabled by flag)"; SKIPPED+=("$tag"); return 0
  fi
  local t0=$SECONDS; "$@"; local rc=$?
  case $rc in
    0) OK+=("$tag"); echo "-- OK [$tag] ($((SECONDS - t0)) s)" ;;
    "$SKIP_CODE") SKIPPED+=("$tag"); echo "-- SKIP [$tag] (non-redistributed input absent)" ;;
    *) echo "!! FAIL [$tag] (exit $rc)"; summary; exit "$rc" ;;
  esac
}

# ---- measure construction (default off; canonical outputs shipped) ----
step 01  "$(gate "$REBUILD_MEASURE" "$HAVE_PADRON")" $PY scripts/01_surname_ses_padron.py
step 02  "$(gate "$REBUILD_MEASURE" "$HAVE_RAW")"    $PY scripts/02_build_enduring_elite.py
step 02b "$(gate "$REBUILD_MEASURE")"                $PY scripts/02b_business_gate_additions.py
step 03  "$(gate "$REBUILD_MEASURE" "$HAVE_REGCIV")" $PY scripts/03_population_reference.py

# ---- composition, 1925 break, validation ----
step 04  1                   $PY scripts/04_figure2_composition.py
step 05  1                   $PY scripts/05_its_1925.py
# [06] retired: it reads the lost v1 extraction (/tmp/extract_sonnet_corrected.json) and its
# outputs (homogamy etc.) are no longer used in the paper; Figure 1 comes from 34 + 06c (v2).
# step 06 "$HAVE_BIOS"       $PY scripts/06_validation_lineage_bios.py
step 07  "$(gate "$HAVE_NET")" $PY scripts/07_centrality_figVI.py

# ---- text models: STM + TBIP (default off; RUN_STM=1) ----
step 11  "$RUN_STM" root_run $R "$REPO_NAME"/scripts/11_stm_topics.R
step 12b "$RUN_STM" root_run $R "$REPO_NAME"/scripts/12b_stm_estimateEffect_298.R
# 46a: prevalence at the covariate means from 12b's estimateEffect object (stm_prep_298.rds);
# 46: appendix tab:stmcoefs from shipped CSVs only (46a + 12b outputs, crosswalk) -> plain step.
step 46a "$RUN_STM" root_run $R "$REPO_NAME"/scripts/46a_stm_prevalence_at_means_298.R
step 46  1                   $PY scripts/46_stm_topic_coef_table.py
step 13  "$RUN_STM" root_run $R "$REPO_NAME"/scripts/13_topic_theme_effects.R
step 14  "$RUN_STM" root_run $R "$REPO_NAME"/scripts/14_tbip_ideal_points.R

# ---- NOMINATE appendix (R&R 2026, D18): snapshot -> W-NOMINATE -> appendix numbers ----
step 15a "$HAVE_BQ"          $PY scripts/15a_extract_rollcalls_bq.py
step 15b 1                   $R  scripts/15b_wnominate_by_period.R
step 15  1                   $PY scripts/15_nominate_convergent_validity.py   # reads 15b output
step 16  1                   $PY scripts/16_its_placebo_bandwidth.py
step 17  "$(gate "$HAVE_RAW")" $PY scripts/17_survivorship_bound.py
step 18  "$(gate "$HAVE_RAW")" $PY scripts/18_cutoff_sensitivity.py
step 19  "$RUN_STM"          $PY scripts/19_stm_theme_table.py
step 20  1                   $PY scripts/20_figure2_reshade.py
step 21  "$RUN_STM"          $R  scripts/21_tbip_family_cluster_se.R
step 22  1                   $PY scripts/22_coding_rule_sensitivity.py
step 24  "$(gate "$HAVE_BIOS")" $PY scripts/24_bio_coverage_by_group.py

# ---- revision-round robustness and inference checks ----
step 25  "$RUN_STM"          $R  scripts/25_tbip_permutation.R
step 26  "$RUN_STM"          $PY scripts/26_topic_theme_crosswalk.py
step 27  "$RUN_STM" root_run $R "$REPO_NAME"/scripts/27_within_elite_trajectory.R
step 28  "$RUN_STM" root_run $R "$REPO_NAME"/scripts/28_stm_uncertainty_methodofcomposition.R
step 29  1                   $PY scripts/29_business_route_robustness.py
step 30  1                   $PY scripts/30_depth_gate_robustness.py
step 31  "$RUN_STM" root_run $R "$REPO_NAME"/scripts/31_statecraft_trajectory.R
step 32  1                   $PY scripts/32_two_dynasty_leaveout.py
step 33  1                   $PY scripts/33_depth_monotonicity.py
step 34  "$(gate "$HAVE_BIOS")" $PY scripts/34_common_pole_validation.py
step 06c 1                   $PY scripts/06c_validation_figure_3group.py   # Figure 1; reads 34's output
step 35  "$RUN_STM" root_run $R "$REPO_NAME"/scripts/35_theme_contrast_pvalues.R
step 36  "$RUN_STM" root_run $R "$REPO_NAME"/scripts/36_seed_robustness.R

# ---- R&R 2026 (RAP-26-0197); outputs in output/rnr2026/ and figures/rnr2026/ ----
# All 1925 ITS scripts (05, 16, 18, 22, 29, 30, 32, 33) use the shared rule in
# _measure_helpers.annual_share: years with < 5 sitting legislators (1925) are dropped.
# 37 checks its series against 16's output (runs after 16); 41 reproduces the submitted
# numbers (hard-coded) and computes the corrected ones; 43 needs 37 and 38.
step 37  1                   $R  scripts/37_franchise_breaks.R
step 38  "$(gate "$HAVE_BIOS" "$HAVE_RAW" "$HAVE_REGCIV")" $PY scripts/38_validation_by_period.py
# [39] added after STM refit decision: unconditional theme effects (A3)
# step 39 "$RUN_STM" root_run $R "$REPO_NAME"/scripts/39_theme_effects_unconditional.R
step 40  "$(gate "$HAVE_PADRON" "$HAVE_REGCIV" "$HAVE_RAW")" $PY scripts/40_cutoff_interpretation.py
step 41  1                   $R  scripts/41_its_corrected_reruns.R   # without censo/workbook: 24 of 29 rows, outputs *_norawdata
# [42] STM refit on the 298 coding without party in the prior (A5, R1.3/D2). Two phases:
#   42fit: A5_FIT_ONLY=1 fits and saves output/rnr2026/A5_stm_model_298_noparty.rds (~1.7 h;
#          skipped inside the script if that rds exists -- delete it to force a refit; the rds
#          is .gitignored, ~159 MB). Needs the speech corpus and stm_model_285.rds (step 11).
#   42:    alignment, script-39 second stage and MoC on the refit (~10 min); compares against
#          39's output/rnr2026/A3_*.csv, so it must run after 39 (or with 39's outputs present).
step 42fit "$RUN_STM" root_run env A5_FIT_ONLY=1 $R "$REPO_NAME"/scripts/42_stm_refit_298_noparty.R
step 42    "$RUN_STM" root_run $R "$REPO_NAME"/scripts/42_stm_refit_298_noparty.R
step 43  1                   $PY scripts/43_rnr_appendix_tables.py
# 44: audit of the v2 biography extraction (A6); reads the reference coding in output/rnr2026/
step 44  "$(gate "$HAVE_BIOS")" $PY scripts/44_bio_extraction_audit.py
# 45: all-member event-comparison table for the appendix (D8: titular columns stay in the A1 memo); needs 37
step 45  1                   $PY scripts/45_event_comparison_allmembers.py

summary
echo "== DONE =="
