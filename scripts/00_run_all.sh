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
echo "== [06b] validation figure =="           ; $PY scripts/06b_validation_figure.py
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
echo "== DONE: all tables and figures regenerated into output/ and figures/ =="
