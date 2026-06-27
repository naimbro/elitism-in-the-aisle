#!/usr/bin/env bash
# Master replication script — Elitism in the Aisle (Bro & Luna, R&P)
# Runs the full pipeline in dependency order. Python 3 and Rscript must be on PATH.
# Large source data are NOT redistributed (see README "Data"); set the paths in each
# script header before running. Steps 08-10 (BCN harvest/extract) call the Anthropic
# API and are slow/optional — the extracted biographies are already shipped in data/.
#
# Usage:  bash scripts/00_run_all.sh
# Runtime: ~30-45 min end-to-end on a 16 GB laptop, EXCLUDING the optional BCN
#          harvest (08-10, several hours, API-bound) and the STM fit (11, ~20 min).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=python3
R=Rscript

echo "== [01] surname SES =="                 ; $PY scripts/01_surname_ses_padron.py
echo "== [02] enduring-elite list =="          ; $PY scripts/02_build_enduring_elite.py
echo "== [02b] business-gate additions =="     ; $PY scripts/02b_business_gate_additions.py
echo "== [03] population reference =="         ; $PY scripts/03_population_reference.py
echo "== [04] Figure 2 composition =="         ; $PY scripts/04_figure2_composition.py
echo "== [05] 1925 ITS =="                     ; $PY scripts/05_its_1925.py
echo "== [06] biography validations =="        ; $PY scripts/06_validation_lineage_bios.py
# [06b] superseded: the validation figure (Figure 1) is now built three-group by [06c],
# which runs after [34] because it reads should5_common_pole_validation.csv.
echo "== [07] network centrality =="           ; $PY scripts/07_centrality_figVI.py
# 08-10 BCN harvest/extract are optional (API-bound); outputs already in data/.
echo "== [11] STM fit (~20 min) =="            ; $R  scripts/11_stm_topics.R
echo "== [12b] Table 1 topics (298) =="        ; $R  scripts/12b_stm_estimateEffect_298.R
echo "== [13] theme effects =="                ; $R  scripts/13_topic_theme_effects.R
echo "== [14] Table 2 TBIP ideal points =="    ; $R  scripts/14_tbip_ideal_points.R
echo "== [15] NOMINATE convergent validity ==" ; $PY scripts/15_nominate_convergent_validity.py
echo "== [16] 1925 placebo + window sweep =="  ; $PY scripts/16_its_placebo_bandwidth.py
echo "== [17] survivorship bound =="           ; $PY scripts/17_survivorship_bound.py
echo "== [18] cutoff sensitivity =="           ; $PY scripts/18_cutoff_sensitivity.py
echo "== [19] STM theme table =="              ; $PY scripts/19_stm_theme_table.py
echo "== [20] Figure 2 reshade =="             ; $PY scripts/20_figure2_reshade.py
echo "== [21] TBIP family-clustered SE =="     ; $R  scripts/21_tbip_family_cluster_se.R
echo "== [22] coding-rule sensitivity =="      ; $PY scripts/22_coding_rule_sensitivity.py
echo "== [24] biography coverage by group ==" ; $PY scripts/24_bio_coverage_by_group.py

# ---- Revision-round (R&R) robustness and inference checks ----
# 27/28/31/35/36 depend on the STM fit (step 11) and the speech corpus.
# 34 reads the harvested BCN biographies (non-public; see README "Data") and self-skips if absent.
echo "== [25] TBIP permutation test =="        ; $R  scripts/25_tbip_permutation.R
echo "== [26] topic-theme crosswalk =="        ; $PY scripts/26_topic_theme_crosswalk.py
echo "== [27] within-elite labor slope =="     ; $R  scripts/27_within_elite_trajectory.R
echo "== [28] STM uncertainty (method of comp.) ==" ; $R scripts/28_stm_uncertainty_methodofcomposition.R
echo "== [29] business-route robustness =="    ; $PY scripts/29_business_route_robustness.py
echo "== [30] depth-gate (>=2) robustness =="  ; $PY scripts/30_depth_gate_robustness.py
echo "== [31] within-elite statecraft slope ==" ; $R scripts/31_statecraft_trajectory.R
echo "== [32] two-dynasty leave-out =="        ; $PY scripts/32_two_dynasty_leaveout.py
echo "== [33] depth-gate monotonicity =="      ; $PY scripts/33_depth_monotonicity.py
echo "== [34] common-pole validation =="       ; $PY scripts/34_common_pole_validation.py
echo "== [06c] validation figure (3-group) ==" ; $PY scripts/06c_validation_figure_3group.py
echo "== [35] Table 1 contrast p-values =="    ; $R  scripts/35_theme_contrast_pvalues.R
echo "== [36] seed/B robustness of H.6 =="     ; $R  scripts/36_seed_robustness.R
echo "== DONE: all tables and figures regenerated into output/ and figures/ =="
