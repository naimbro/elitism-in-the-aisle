# 39 -- R&R 2026 item A3 (Referee 1, comment R1.3): surname-agenda relationship
# WITHOUT the party-bloc control, reported next to the party-adjusted one.
#
# Referee 1 asks for the surname-agenda relationship "with chamber and year
# controls only", with the party-bloc-adjusted version as the harder test. This
# script re-runs the SAME second-stage theme regressions as scripts 13 / 35
# (document-level OLS of theme prevalence, legislator-clustered SEs) under:
#   no_party       : prop ~ apellido +          camara + Year   (R1.3)
#   party_adjusted : prop ~ apellido + sector + camara + Year   (scripts 13/35)
# and the within-group decade-slope tests of scripts 27 (labor) and 31
# (statecraft) with and without the party-bloc control.
#
# CAVEAT (quantified in section 2): the fitted STM (stm_model_285.rds) has
# ~ apellido + sector + camara + Year in its PREVALENCE prior (stm_revised.r:55),
# with apellido coded on the 285-surname list. Theta is reused as-is; only the
# SECOND-STAGE regressions change. The model is not refit here.
#
# Sections
#   1. Document frame exactly as scripts 13/27/28/31/35 (theta-order guard)
#   2. Coding audit: 285 list (= canonical minus the 13 business_gate rows) vs
#      298; reclassified documents/legislators; fitted-model design matrix
#   3. Theme contrasts, both specs; reproduction of scripts 35 (298 list) and
#      13 / theme_effects_285.csv (285 list); stale-number inventory of the
#      hand-transcribed main-text Table 1
#   4. Within-group decade slopes, both specs (reproduces scripts 27, 31)
#   5. Bare tabular drafts (INV-13)
#   6. Method of composition (script 28 logic): all 11 themes + statecraft
#      bundle, both specs, elite / common / contrast, plus slope differences.
#      Same seed and draw scheme as 28 -> party-adjusted results reproduce 28.
#
# RUN FROM PROJECT ROOT (reads intervenciones.csv, stm_model_285.rds,
# enduring_elite_FINAL.csv, topic_theme_map.csv from the root, as scripts
# 13/27/28/31/35). `here` is not installed on this machine, so paths are
# relative to the working directory with an explicit root guard (INV-16).
# Stochastic element: posterior theta draws in section 6 -> one seed (INV-14).
# Runtime ~25 min (section 6 dominates). Not yet in 00_run_all.sh (add at
# integration).

suppressMessages({
  library(dplyr)
  library(tidyr)
  library(tidytext)
  library(quanteda)
  library(stm)
  library(sandwich)
  library(lmtest)
})
set.seed(1925)                       # identical to script 28 (same draw stream)

# ---- parameters -------------------------------------------------------------
RUN_MOC  <- TRUE                     # section 6 (method of composition)
B_DRAWS  <- as.integer(Sys.getenv("A3_MOC_B", "50"))  # 50 = script 28
BATCH    <- 10L                      # draws per thetaPosterior call, as 28
OUT_DIR  <- file.path("replication_repo", "output", "rnr2026")
STATECRAFT_THEMES <- c("Elections & parties", "Defense & security",
                       "State administration", "Foreign relations")
LABOR_THEME <- "Labor & industry"
BUNDLE <- "Statecraft bundle"
SPECS <- c(no_party       = "apellido + camara + Year",
           party_adjusted = "apellido + sector + camara + Year")
SLOPE_SPECS <- c(no_party = "camara", party_adjusted = "sector + camara")
TABLE1_TEX <- file.path("paper", "tables", "table_themes_main.tex")  # read-only

needed <- c("intervenciones.csv", "stm_model_285.rds",
            "enduring_elite_FINAL.csv", "topic_theme_map.csv", TABLE1_TEX)
stopifnot("Run from the project root (paper_1925/)" = all(file.exists(needed)))
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)

# ---- helpers ----------------------------------------------------------------
#' Upper-case and strip Spanish accents (as scripts 13/27/28/31/35).
deaccent <- function(x) {
  chartr("ÁÉÍÓÚÜÑáéíóúüñ",
         "AEIOUUNAEIOUUN", toupper(as.character(x)))
}

#' Surname group from paternal/maternal surnames (elite precedence).
code_apellido <- function(pat, mat, elite, common) {
  ifelse(pat %in% elite | mat %in% elite, "elite",
         ifelse(pat %in% common | mat %in% common, "comun", "otro"))
}

#' Elite and common coefficients (vs 'otro') and their contrast.
#' @param d data.frame with y, apellido (ref 'otro'), controls, Hablante
#' @param rhs character. Right-hand side of the formula.
#' @return one-row data.frame: estimates, legislator-clustered variances
#'   (vcovCL default HC1, as scripts 13/35), SEs and normal p-values
fit_contrast <- function(d, rhs) {
  fit <- lm(as.formula(paste("y ~", rhs)), data = d)
  stopifnot(nobs(fit) == nrow(d))
  V  <- vcovCL(fit, cluster = d$Hablante)
  e <- "apellidoelite"; c_ <- "apellidocomun"
  be <- unname(coef(fit)[e]); bc <- unname(coef(fit)[c_])
  v_e <- V[e, e]; v_c <- V[c_, c_]; v_k <- v_e + v_c - 2 * V[e, c_]
  pz <- \(est, v) 2 * pnorm(-abs(est / sqrt(v)))
  data.frame(elite = be, elite_se = sqrt(v_e), elite_p = pz(be, v_e),
             comun = bc, comun_se = sqrt(v_c), comun_p = pz(bc, v_c),
             contrast = be - bc, contrast_se = sqrt(v_k),
             contrast_p = pz(be - bc, v_k),
             elite_var = v_e, comun_var = v_c, contrast_var = v_k)
}

#' Within-group and pooled decade-slope tests (scripts 27/31 logic).
#' @param s data.frame restricted to 1910-1949 with y, dec10, apellido, controls
#' @param ctrl character. Controls added to the slope regressions.
#' @param orient 'comun' -> common-minus-elite slope (27, labor);
#'   'elite' -> elite-minus-common slope (31, statecraft)
#' @return data.frame: elite slope, common slope, slope difference (t-based p)
slope_tests <- function(s, ctrl, orient) {
  one <- function(g) {
    dg  <- s[s$apellido == g, ]
    fit <- lm(as.formula(paste("y ~ dec10 +", ctrl)), data = dg)
    ct  <- coeftest(fit, vcovCL(fit, cluster = dg$Hablante))
    ct["dec10", c("Estimate", "Std. Error", "Pr(>|t|)")]
  }
  pooled <- slope_diff(s[s$apellido %in% c("elite", "comun"), ], ctrl, orient)
  dq <- if (orient == "comun") "common_minus_elite_slope" else
    "elite_minus_common_slope"
  rows <- rbind(one("elite"), one("comun"), pooled$ct)
  data.frame(quantity = c("elite_slope_per_decade", "common_slope_per_decade",
                          dq),
             estimate = rows[, 1], se = rows[, 2], p = rows[, 3],
             row.names = NULL)
}

#' Pooled difference-in-slopes (interaction) with legislator-clustered vcov.
#' @return list(est, var, ct) where ct = c(Estimate, SE, t-based p)
slope_diff <- function(ec, ctrl, orient) {
  ref <- if (orient == "comun") "elite" else "comun"
  ec$apellido <- relevel(factor(as.character(ec$apellido)), ref = ref)
  fit <- lm(as.formula(paste("y ~ apellido * dec10 +", ctrl)), data = ec)
  V <- vcovCL(fit, cluster = ec$Hablante)
  term <- paste0("apellido", orient, ":dec10")
  ct <- coeftest(fit, V)[term, c("Estimate", "Std. Error", "Pr(>|t|)")]
  list(est = unname(coef(fit)[term]), var = V[term, term], ct = ct)
}

#' Rubin's rules (script 28 definition).
rubin <- function(est, var) {
  qbar <- mean(est); ubar <- mean(var); bv <- var(est)
  tt <- ubar + (1 + 1 / length(est)) * bv
  c(est = qbar, se = sqrt(tt), p = 2 * pnorm(-abs(qbar / sqrt(tt))),
    se_clustered_only = sqrt(ubar),
    frac_topic_unc = (1 + 1 / length(est)) * bv / tt)
}

star_n <- \(p) ifelse(p < 0.05, 2L, ifelse(p < 0.10, 1L, 0L))  # paper rule
stars  <- \(p) c("", "^{*}", "^{**}")[star_n(p) + 1L]
fmt_signed <- \(x) sprintf("%s%.2f", ifelse(x < 0, "$-$", "$+$"), abs(x))
cell <- \(est, p) paste0(fmt_signed(est),
                         ifelse(stars(p) == "", "", paste0("$", stars(p), "$")))

# =============================================================================
# 1. Document frame (verbatim logic of scripts 13/27/28/31/35)
# =============================================================================
m <- readRDS("stm_model_285.rds"); theta <- m$theta; K <- ncol(theta)
iv <- read.csv("intervenciones.csv", stringsAsFactors = FALSE)

right_parties <- c(
  "Partido Conservador", "Partido Conservador Tradicionalista",
  "Partido Conservador Social Cristiano", "Partido Conservador Unido",
  "Partido Liberal", "Partido Liberal Democratico",
  "Partido Liberal Doctrinario", "Partido Liberal Progresista",
  "Partido Liberal Unido", "Partido Nacional o Monttvarista",
  "Partido Nacional", "Partido Agrario Laborista",
  "Partido Nacional Socialista", "Movimiento Nacional Socialista de Chile")
centre_parties <- c(
  "Partido Radical", "Partido Radical de Chile",
  "Partido Radical Independiente", "Partido Democratico de Chile",
  "Partido Social Republicano", "Falange Nacional",
  "Partido Accion Republicana", "Partido Regionalista", "Partido Agrario")
left_parties <- c(
  "Partido Obrero Socialista", "Partido Socialista de Chile",
  "Partido Socialista Popular", "Partido Comunista de Chile",
  "Partido Radical Socialista",
  "Confederacion Republicana de Accion Civica de Obreros y Empleados",
  "Partido Progresista Nacional",
  "Union Social Republicana de Asalariados de Chile",
  "Union Social Republicana de los Asalariados de Chile",
  "Nueva Accion Publica", "Vanguardia Popular Socialista",
  "Partido Democratico del Pueblo", "Partido Democrata",
  "Partido Democratico")
iv <- iv |> mutate(sector = case_when(
  Partido %in% right_parties  ~ "derecha",
  Partido %in% centre_parties ~ "centro",
  Partido %in% left_parties   ~ "izquierda",
  TRUE ~ "otro"))

comunes <- deaccent(c(
  "GONZALEZ", "MUNOZ", "DIAZ", "ROJAS", "PEREZ", "SILVA", "SOTO", "MARTINEZ",
  "LOPEZ", "MORALES", "CONTRERAS", "RODRIGUEZ", "SEPULVEDA", "FUENTES",
  "VALENZUELA", "RAMIREZ", "ESPINOZA", "REYES", "HERNANDEZ", "GUTIERREZ",
  "FLORES", "CASTRO", "TORRES", "SANCHEZ", "VASQUEZ", "CASTILLO", "FERNANDEZ",
  "ARAYA", "HERRERA", "VARGAS", "NUÑEZ", "ALVAREZ", "CARRASCO", "GOMEZ",
  "BRAVO", "VERGARA", "GARCIA", "TAPIA", "JARA", "ZUÑIGA", "ORELLANA",
  "FIGUEROA", "MIRANDA", "RIQUELME", "CAMPOS", "MOLINA", "RIVERA", "GUZMAN",
  "SANDOVAL", "ORTIZ"))
elite_df <- read.csv("enduring_elite_FINAL.csv", stringsAsFactors = FALSE)
is_biz <- grepl("business_gate", elite_df$sources, fixed = TRUE)
stopifnot(nrow(elite_df) == 298L, sum(is_biz) == 13L)
elite_298 <- deaccent(elite_df$surname)
elite_285 <- deaccent(elite_df$surname[!is_biz])      # pre-business-route list
pat_n <- deaccent(iv$Pat); mat_n <- deaccent(iv$Mat)
iv$apellido    <- code_apellido(pat_n, mat_n, elite_298, comunes)
iv$apellido285 <- code_apellido(pat_n, mat_n, elite_285, comunes)

tokens <- iv |> unnest_tokens(word, intervencion_list) |> group_by(index) |>
  mutate(ni = n()) |> filter(ni > 20)
dfm <- tokens |> count(index, word, sort = TRUE) |> cast_dfm(index, word, n)
rm(tokens); invisible(gc())
io <- iv |> filter(index %in% dfm@docvars$docname_) |>
  distinct(index, .keep_all = TRUE)
io <- io[match(dfm@docvars$docname_, io$index), ]        # dfm (= theta) order
rownames(io) <- NULL
stopifnot(nrow(io) == nrow(theta))
rm(iv, dfm); invisible(gc())

io$apellido    <- relevel(as.factor(io$apellido), ref = "otro")
io$apellido285 <- relevel(as.factor(io$apellido285), ref = "otro")
io$sector   <- relevel(as.factor(io$sector),   ref = "centro")
io$camara   <- as.factor(io$camara)
io$Year     <- as.numeric(io$Year)
stopifnot(!anyNA(io[, c("apellido", "sector", "camara", "Year", "Hablante")]))
io$dec10 <- ((io$Year %/% 10) * 10 - 1910) / 10          # 0..3 for 1910s-1940s

# theme membership matrix (K x outcomes), themes in script-35 order + bundle
tm <- read.csv("topic_theme_map.csv", stringsAsFactors = FALSE)
themes <- setdiff(unique(tm$theme), "Other")
stopifnot(length(themes) == 11L, all(STATECRAFT_THEMES %in% themes))
outcomes <- c(themes, BUNDLE)
Tmat <- matrix(0, K, length(outcomes), dimnames = list(NULL, outcomes))
for (j in seq_along(themes)) Tmat[tm$topic[tm$theme == themes[j]], j] <- 1
Tmat[tm$topic[tm$theme %in% STATECRAFT_THEMES], BUNDLE] <- 1
prev <- (theta %*% Tmat) * 100                           # percentage points

# sample description (documents and legislators by group; group x bloc)
samp <- io |> group_by(apellido) |>
  summarise(n_docs = n(), n_legislators = n_distinct(Hablante),
            .groups = "drop")
bloc_doc <- io |> count(apellido, sector) |> group_by(apellido) |>
  mutate(share_docs = n / sum(n)) |> ungroup()
bloc_leg <- io |> distinct(Hablante, apellido, sector) |>
  count(apellido, sector, name = "n_leg_bloc_pairs")
write.csv(samp, file.path(OUT_DIR, "A3_sample_counts.csv"), row.names = FALSE)
write.csv(left_join(bloc_doc, bloc_leg, by = c("apellido", "sector")),
          file.path(OUT_DIR, "A3_surname_by_bloc.csv"), row.names = FALSE)
message(sprintf("docs %d, legislators %d", nrow(io), n_distinct(io$Hablante)))

# =============================================================================
# 2. Coding audit: 285 vs 298 lists and the fitted model's prior design matrix
# =============================================================================
recl_doc <- io |> count(apellido285, apellido298 = apellido, name = "n_docs")
recl_leg <- io |> distinct(Hablante, apellido285, apellido) |>
  count(apellido285, apellido298 = apellido, name = "n_legislators")
recl <- full_join(recl_doc, recl_leg, by = c("apellido285", "apellido298"))
recl$reclassified <- as.character(recl$apellido285) !=
  as.character(recl$apellido298)
write.csv(recl, file.path(OUT_DIR, "A3_reclassification_285_to_298.csv"),
          row.names = FALSE)

Xp <- m$settings$covariates$X                      # prior design, model rows
stopifnot(nrow(Xp) == nrow(io))
design_cols <- list(
  apellidoelite   = \(a) as.numeric(a == "elite"),
  apellidocomun   = \(a) as.numeric(a == "comun"))
dchk <- do.call(rbind, lapply(names(design_cols), \(cc) {
  data.frame(column = cc,
             prior_sum = sum(Xp[, cc]),
             coding285_sum = sum(design_cols[[cc]](io$apellido285)),
             coding298_sum = sum(design_cols[[cc]](io$apellido)),
             mismatch_vs_285 = sum(Xp[, cc] != design_cols[[cc]](io$apellido285)),
             mismatch_vs_298 = sum(Xp[, cc] != design_cols[[cc]](io$apellido)))
}))
other_cols <- data.frame(
  column = c("sectorderecha", "sectorizquierda", "sectorotro", "camarasenado",
             "Year"),
  prior_sum = colSums(Xp[, c("sectorderecha", "sectorizquierda", "sectorotro",
                             "camarasenado", "Year")]),
  coding285_sum = NA_real_, coding298_sum = NA_real_,
  mismatch_vs_285 = c(sum(Xp[, "sectorderecha"] != (io$sector == "derecha")),
                      sum(Xp[, "sectorizquierda"] != (io$sector == "izquierda")),
                      sum(Xp[, "sectorotro"] != (io$sector == "otro")),
                      sum(Xp[, "camarasenado"] != (io$camara == "senado")),
                      sum(abs(Xp[, "Year"] - io$Year) > 1e-9)),
  mismatch_vs_298 = NA_real_, row.names = NULL)
other_cols$mismatch_vs_298 <- other_cols$mismatch_vs_285  # apellido-free cols
dchk <- rbind(dchk, other_cols)
write.csv(dchk, file.path(OUT_DIR, "A3_stm_prior_design_check.csv"),
          row.names = FALSE)
message(sprintf("prior design: elite mismatches vs 285 = %d, vs 298 = %d",
                dchk$mismatch_vs_285[1], dchk$mismatch_vs_298[1]))
rm(Xp); invisible(gc())

# =============================================================================
# 3. Theme contrasts, both specifications
# =============================================================================
base_cols <- c("apellido", "sector", "camara", "Year", "Hablante")
grid <- expand.grid(outcome = outcomes, spec = names(SPECS),
                    stringsAsFactors = FALSE)
res <- vector("list", nrow(grid))
for (i in seq_len(nrow(grid))) {
  d <- io[, base_cols]; d$y <- prev[, grid$outcome[i]]
  res[[i]] <- cbind(grid[i, ], fit_contrast(d, SPECS[[grid$spec[i]]]))
}
long <- do.call(rbind, res); rownames(long) <- NULL
long$n_docs <- nrow(io); long$n_clusters <- n_distinct(io$Hablante)
write.csv(long |> select(-ends_with("_var")),
          file.path(OUT_DIR, "A3_theme_contrasts_long.csv"), row.names = FALSE)

val_cols <- c("elite", "elite_se", "elite_p", "comun", "comun_se", "comun_p",
              "contrast", "contrast_se", "contrast_p")
wide <- long |> select(outcome, spec, all_of(val_cols)) |>
  pivot_wider(names_from = spec, values_from = all_of(val_cols)) |>
  mutate(delta_contrast = contrast_no_party - contrast_party_adjusted,
         abs_ratio = abs(contrast_no_party) / abs(contrast_party_adjusted),
         same_sign = sign(contrast_no_party) == sign(contrast_party_adjusted),
         gap_grows = same_sign & abs_ratio > 1,
         sig05_no_party       = contrast_p_no_party       < 0.05,
         sig05_party_adjusted = contrast_p_party_adjusted < 0.05) |>
  arrange(desc(contrast_no_party))
write.csv(wide, file.path(OUT_DIR, "A3_theme_contrasts_both_specs.csv"),
          row.names = FALSE)

# ---- 3a. reproduction: party-adjusted, 298 list vs script 35 ---------------
adj <- long[long$spec == "party_adjusted" & long$outcome %in% themes, ]
s35 <- read.csv(file.path("replication_repo", "output",
                          "m1_contrast_pvalues.csv"))
chk35 <- inner_join(adj |> select(theme = outcome, contrast, contrast_se,
                                  contrast_p),
                    s35, by = "theme")
stopifnot(nrow(chk35) == 11L)
max35 <- max(abs(c(chk35$contrast - chk35$contrast.y,
                   chk35$contrast_se - chk35$se_clustered,
                   chk35$contrast_p - chk35$p_clustered)))

# ---- 3b. reproduction: party-adjusted, 285 list vs script 13 ---------------
res285 <- vector("list", length(themes))
for (j in seq_along(themes)) {
  d <- io[, base_cols]; d$apellido <- io$apellido285
  d$y <- prev[, themes[j]]
  res285[[j]] <- cbind(theme = themes[j],
                       fit_contrast(d, SPECS[["party_adjusted"]]))
}
res285 <- do.call(rbind, res285)
s13 <- read.csv(file.path("replication_repo", "data", "processed",
                          "theme_effects_285.csv"))  # 285-era script-13 output (13 now writes the 298 version)
chk13 <- inner_join(res285 |> select(theme, elite, elite_se, comun, comun_se),
                    s13 |> select(theme, elite, elite_se, comun, comun_se),
                    by = "theme", suffix = c("_285rerun", "_script13"))
stopifnot(nrow(chk13) == 11L)
max13_285 <- max(abs(c(chk13$elite_285rerun - chk13$elite_script13,
                       chk13$elite_se_285rerun - chk13$elite_se_script13,
                       chk13$comun_285rerun - chk13$comun_script13,
                       chk13$comun_se_285rerun - chk13$comun_se_script13)))
write.csv(chk13, file.path(OUT_DIR, "A3_reproduce_table1_285list.csv"),
          row.names = FALSE)
message(sprintf("285-list rerun vs theme_effects_285.csv: max |diff| %.3g",
                max13_285))

# ---- 3c. stale-number inventory of the printed main-text Table 1 -----------
# table_themes_main.tex is hand-written (no script emits it); parse its 11 rows.
tx <- readLines(TABLE1_TEX, warn = FALSE)
rows_tx <- tx[grepl("^[A-Z].*&.*\\\\\\\\\\s*$", tx) & !grepl("^Theme", tx)]
parse_cell <- \(s) {
  num <- as.numeric(sub(".*?([+-][0-9]+\\.[0-9]+).*", "\\1", s, perl = TRUE))
  data.frame(value = num, stars = lengths(regmatches(s, gregexpr("\\*", s))))
}
printed <- do.call(rbind, lapply(seq_along(rows_tx), \(i) {
  parts <- trimws(strsplit(rows_tx[i], "(?<!\\\\)&", perl = TRUE)[[1]])
  parts[4] <- sub("\\\\\\\\\\s*$", "", parts[4])
  data.frame(theme = gsub("\\\\&", "&", parts[1]), printed_rank = i,
             printed_elite = parse_cell(parts[2])$value,
             printed_elite_stars = parse_cell(parts[2])$stars,
             printed_comun = parse_cell(parts[3])$value,
             printed_comun_stars = parse_cell(parts[3])$stars,
             printed_contrast = parse_cell(parts[4])$value)
}))
stopifnot(nrow(printed) == 11L, setequal(printed$theme, themes))
cur <- wide |> filter(outcome %in% themes) |>
  transmute(theme = outcome,
            cur_elite = elite_party_adjusted, cur_elite_p = elite_p_party_adjusted,
            cur_comun = comun_party_adjusted, cur_comun_p = comun_p_party_adjusted,
            cur_contrast = contrast_party_adjusted,
            cur_contrast_p = contrast_p_party_adjusted,
            nop_contrast = contrast_no_party)
inv <- inner_join(printed, cur, by = "theme") |>
  mutate(cur_elite_stars = star_n(cur_elite_p),
         cur_comun_stars = star_n(cur_comun_p),
         cur_rank_party_adjusted = rank(-cur_contrast),
         rank_no_party = rank(-nop_contrast),
         elite_round_changed = abs(round(cur_elite, 2) - printed_elite) > 0.001,
         comun_round_changed = abs(round(cur_comun, 2) - printed_comun) > 0.001,
         contrast_round_changed =
           abs(round(cur_contrast, 2) - printed_contrast) > 0.001,
         elite_sign_flip = sign(cur_elite) != sign(printed_elite),
         comun_sign_flip = sign(cur_comun) != sign(printed_comun),
         contrast_sign_flip = sign(cur_contrast) != sign(printed_contrast),
         elite_stars_changed = cur_elite_stars != printed_elite_stars,
         comun_stars_changed = cur_comun_stars != printed_comun_stars) |>
  arrange(printed_rank)
write.csv(inv, file.path(OUT_DIR, "A3_stale_inventory_table1.csv"),
          row.names = FALSE)

# =============================================================================
# 4. Within-group decade slopes 1910-1949, both specifications
# =============================================================================
sidx <- which(io$Year >= 1910 & io$Year <= 1949)
sub_df <- io[sidx, c("apellido", "sector", "camara", "Hablante", "dec10")]
slope_defs <- data.frame(outcome = c(LABOR_THEME, BUNDLE),
                         orient = c("comun", "elite"), stringsAsFactors = FALSE)
sl_grid <- merge(slope_defs, data.frame(spec = names(SLOPE_SPECS)))
sl_res <- vector("list", nrow(sl_grid))
for (i in seq_len(nrow(sl_grid))) {
  s <- sub_df; s$y <- prev[sidx, sl_grid$outcome[i]]
  sl_res[[i]] <- data.frame(sl_grid[i, c("outcome", "spec")],
                            slope_tests(s, SLOPE_SPECS[[sl_grid$spec[i]]],
                                        sl_grid$orient[i]),
                            row.names = NULL)
}
slopes <- do.call(rbind, sl_res); rownames(slopes) <- NULL
ec_n <- sub_df |> filter(apellido %in% c("elite", "comun")) |>
  group_by(apellido) |>
  summarise(n_docs = n(), n_leg = n_distinct(Hablante), .groups = "drop")
slopes$n_docs_elite  <- ec_n$n_docs[ec_n$apellido == "elite"]
slopes$n_docs_common <- ec_n$n_docs[ec_n$apellido == "comun"]
slopes$n_leg_elite   <- ec_n$n_leg[ec_n$apellido == "elite"]
slopes$n_leg_common  <- ec_n$n_leg[ec_n$apellido == "comun"]
write.csv(slopes, file.path(OUT_DIR, "A3_within_group_slopes_both_specs.csv"),
          row.names = FALSE)

#' Max abs diff between a party-adjusted slope block and a 27/31 output,
#' joined on `quantity` (not row position).
slope_check <- function(oc, ref_file) {
  ref <- read.csv(file.path("replication_repo", "output", ref_file))
  j <- inner_join(slopes |> filter(spec == "party_adjusted", outcome == oc),
                  ref, by = "quantity", suffix = c("", "_ref"))
  stopifnot(nrow(j) == 3L)
  max(abs(c(j$estimate - j$estimate_ref, j$se - j$se_ref, j$p - j$p_ref)))
}
max27 <- slope_check(LABOR_THEME, "within_elite_trajectory.csv")
max31 <- slope_check(BUNDLE, "statecraft_trajectory.csv")
message(sprintf("max |diff| vs script 27: %.3g; vs script 31: %.3g",
                max27, max31))

checks <- data.frame(
  reference = c(
    "35 m1_contrast_pvalues.csv (298 list; contrast, se, p; join on theme)",
    "13 theme_effects_285.csv (285 list rerun; elite, se, comun, se; join on theme)",
    "27 within_elite_trajectory.csv (est, se, p; join on quantity)",
    "31 statecraft_trajectory.csv (est, se, p; join on quantity)"),
  max_abs_diff = c(max35, max13_285, max27, max31))

# =============================================================================
# 5. Bare tabular drafts (INV-13: no float, caption, or notes)
# =============================================================================
tab <- wide |> filter(outcome %in% themes)
body <- character(2L * nrow(tab))
for (i in seq_len(nrow(tab))) {
  th <- gsub("&", "\\\\&", tab$outcome[i])
  body[2L * i - 1L] <- sprintf("%s & %s & %s \\\\", th,
    cell(tab$contrast_no_party[i], tab$contrast_p_no_party[i]),
    cell(tab$contrast_party_adjusted[i], tab$contrast_p_party_adjusted[i]))
  body[2L * i] <- sprintf(" & (%.2f) & (%.2f) \\\\",
                          tab$contrast_se_no_party[i],
                          tab$contrast_se_party_adjusted[i])
}
n_fmt <- format(nrow(io), big.mark = "{,}")
n_cl <- n_distinct(io$Hablante)
tex1 <- c("\\begin{tabular}{lcc}", "\\toprule",
          " & (1) & (2) \\\\",
          " & No party control & Party-adjusted \\\\",
          "\\midrule",
          "\\multicolumn{3}{l}{\\textit{Elite $-$ common contrast}} \\\\",
          body, "\\midrule",
          "Chamber and year controls & Yes & Yes \\\\",
          "Party-bloc control & No & Yes \\\\",
          sprintf("Speeches & %s & %s \\\\", n_fmt, n_fmt),
          sprintf("Legislators (clusters) & %d & %d \\\\", n_cl, n_cl),
          "\\bottomrule", "\\end{tabular}")
writeLines(tex1, file.path(OUT_DIR, "A3_table1_two_column.tex"))

slw <- slopes |> filter(grepl("minus", quantity))
sl_rows <- vapply(c(LABOR_THEME, BUNDLE), \(oc) {
  u <- slw[slw$outcome == oc & slw$spec == "no_party", ]
  a <- slw[slw$outcome == oc & slw$spec == "party_adjusted", ]
  lab <- if (oc == LABOR_THEME) "Labor \\& industry (common $-$ elite)" else
    "Statecraft (elite $-$ common)"
  sprintf("%s & %s (%.2f) & %s (%.2f) \\\\", lab,
          cell(u$estimate, u$p), u$se, cell(a$estimate, a$p), a$se)
}, character(1L))
tex2 <- c("\\begin{tabular}{lcc}", "\\toprule",
          "Difference in decade slopes, 1910--1949 & No party control & Party-adjusted \\\\",
          "\\midrule", sl_rows, "\\midrule",
          "Chamber control & Yes & Yes \\\\",
          "Party-bloc control & No & Yes \\\\",
          "\\bottomrule", "\\end{tabular}")
writeLines(tex2, file.path(OUT_DIR, "A3_slope_tests_two_column.tex"))

# =============================================================================
# 6. Method of composition (script 28 logic), all themes, both specs
# =============================================================================
if (RUN_MOC) {
  qty <- c("elite", "comun", "contrast")
  dims <- list(NULL, outcomes, names(SPECS), qty)
  est_arr <- array(NA_real_, c(B_DRAWS, length(outcomes), length(SPECS), 3L),
                   dimnames = dims)
  var_arr <- est_arr
  sl_dims <- list(NULL, c(LABOR_THEME, BUNDLE), names(SLOPE_SPECS))
  sl_est <- array(NA_real_, c(B_DRAWS, 2L, length(SLOPE_SPECS)),
                  dimnames = sl_dims)
  sl_var <- sl_est
  sub_ec <- io$apellido[sidx] %in% c("elite", "comun")
  ndone <- 0L
  while (ndone < B_DRAWS) {
    nb <- min(BATCH, B_DRAWS - ndone)
    dr <- thetaPosterior(m, nsims = nb, type = "Global")
    for (b in seq_len(nb)) {
      theta_b <- t(vapply(dr, \(x) x[b, ], numeric(K)))
      pv <- (theta_b %*% Tmat) * 100
      r <- ndone + 1L
      d <- io[, base_cols]
      for (oc in outcomes) {
        d$y <- pv[, oc]
        for (sp in names(SPECS)) {
          fc <- fit_contrast(d, SPECS[[sp]])
          est_arr[r, oc, sp, ] <- unlist(fc[qty])
          var_arr[r, oc, sp, ] <- unlist(fc[paste0(qty, "_var")])
        }
      }
      for (oc in c(LABOR_THEME, BUNDLE)) {
        ec <- sub_df[sub_ec, ]; ec$y <- pv[sidx[sub_ec], oc]
        orient <- if (oc == LABOR_THEME) "comun" else "elite"
        for (sp in names(SLOPE_SPECS)) {
          sd_ <- slope_diff(ec, SLOPE_SPECS[[sp]], orient)
          sl_est[r, oc, sp] <- sd_$est; sl_var[r, oc, sp] <- sd_$var
        }
      }
      ndone <- r
      message("MoC draw ", ndone, "/", B_DRAWS)
    }
    rm(dr); invisible(gc())
  }
  saveRDS(list(est = est_arr, var = var_arr, slope_est = sl_est,
               slope_var = sl_var, seed = 1925L, B = B_DRAWS,
               note = "per-draw estimates and legislator-clustered variances"),
          file.path(OUT_DIR, "A3_moc_draws.rds"))

  mg <- expand.grid(outcome = outcomes, spec = names(SPECS), quantity = qty,
                    stringsAsFactors = FALSE)
  moc <- do.call(rbind, lapply(seq_len(nrow(mg)), \(i) {
    g <- mg[i, ]
    rb <- rubin(est_arr[, g$outcome, g$spec, g$quantity],
                var_arr[, g$outcome, g$spec, g$quantity])
    data.frame(g, t(rb), B = B_DRAWS, row.names = NULL)
  }))
  sg <- expand.grid(outcome = c(LABOR_THEME, BUNDLE),
                    spec = names(SLOPE_SPECS), stringsAsFactors = FALSE)
  moc_sl <- do.call(rbind, lapply(seq_len(nrow(sg)), \(i) {
    g <- sg[i, ]
    rb <- rubin(sl_est[, g$outcome, g$spec], sl_var[, g$outcome, g$spec])
    data.frame(g, quantity = "slope_diff", t(rb), B = B_DRAWS,
               row.names = NULL)
  }))
  moc <- rbind(moc, moc_sl)
  write.csv(moc, file.path(OUT_DIR, "A3_methodofcomposition_both_specs.csv"),
            row.names = FALSE)

  # wide contrast view with deterministic p for the memo
  moc_w <- moc |> filter(quantity == "contrast") |>
    select(outcome, spec, est, se, p, frac_topic_unc) |>
    pivot_wider(names_from = spec, values_from = c(est, se, p, frac_topic_unc)) |>
    left_join(wide |> select(outcome, contrast_p_no_party,
                             contrast_p_party_adjusted), by = "outcome") |>
    mutate(sig05_moc_no_party = p_no_party < 0.05,
           sig05_moc_party_adjusted = p_party_adjusted < 0.05) |>
    arrange(desc(est_no_party))
  write.csv(moc_w, file.path(OUT_DIR, "A3_moc_contrasts_wide.csv"),
            row.names = FALSE)

  # reproduction of script 28 (party-adjusted), joined on theme / quantity
  t28 <- read.csv(file.path("replication_repo", "output",
                            "m1_table1_methodofcomposition.csv"))
  pa <- \(q, col, new) {
    x <- moc[moc$spec == "party_adjusted" & moc$quantity == q,
             c("outcome", col)]
    names(x) <- c("theme", new)
    x
  }
  j28 <- t28 |>
    inner_join(pa("elite", "est", "elite_39"), by = "theme") |>
    inner_join(pa("elite", "p", "elite_p_39"), by = "theme") |>
    inner_join(pa("comun", "est", "comun_39"), by = "theme") |>
    inner_join(pa("comun", "p", "comun_p_39"), by = "theme") |>
    inner_join(pa("contrast", "est", "contrast_39"), by = "theme")
  stopifnot(nrow(j28) == 11L)
  max28t <- max(abs(c(j28$elite - j28$elite_39, j28$elite_p - j28$elite_p_39,
                      j28$comun - j28$comun_39, j28$comun_p - j28$comun_p_39,
                      j28$contrast - j28$contrast_39)))
  s28 <- read.csv(file.path("replication_repo", "output",
                            "m1_withinelite_methodofcomposition.csv"))
  r28 <- moc_sl[moc_sl$outcome == LABOR_THEME &
                  moc_sl$spec == "party_adjusted", ]
  ref28 <- s28[s28$X == "diff", ]
  max28s <- max(abs(c(r28$est - ref28$est, r28$se - ref28$se,
                      r28$p - ref28$p)))
  checks <- rbind(checks, data.frame(
    reference = c(paste("28 m1_table1_methodofcomposition.csv (11 themes;",
                        "elite, elite_p, comun, comun_p, contrast)"),
                  "28 m1_withinelite_methodofcomposition.csv (diff: est, se, p)"),
    max_abs_diff = c(max28t, max28s)))
  message(sprintf("vs script 28: themes %.3g, slope diff %.3g",
                  max28t, max28s))
}
write.csv(checks, file.path(OUT_DIR, "A3_reproduction_checks.csv"),
          row.names = FALSE)

message("saved outputs to ", OUT_DIR)
