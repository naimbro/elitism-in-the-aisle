# 42 -- R&R 2026 item A5 (Referee 1, R1.3; tracker D2): REFIT the structural
# topic model with the canonical 298-surname coding and WITHOUT party bloc in
# the prevalence prior, then re-run the script-39 second stage on the new theta.
#
# Motivation (A3 memo, section 2): the fitted STM (stm_model_285.rds) has
# prevalence ~ apellido(285) + sector + camara + Year, so every theme result
# regresses the 298 coding on theta shrunk toward a 285-coded, party-inclusive
# prior. This script removes both features at once.
#
# Fit: identical to stm_revised.r / script 11 (same corpus, same tokens -> dfm,
# same document order, K = 80, init.type = "Spectral", seed = 1,
# max.em.its = 75, all other stm() arguments at the defaults used there,
# em.converge.thresh 1e-5), changing ONLY
#   prevalence = ~ apellido(285) + sector + camara + Year
#   ->           ~ apellido(298) +          camara + Year
# The refit is saved to a NEW file (MODEL_RDS); stm_model_285.rds is only read.
#
# Sections
#   1. Document frame exactly as script 39 (+ audit against A3 outputs)
#   2. Original-model checks (frame identity, vocabulary)
#   3. Refit (skipped if MODEL_RDS exists), runtime / convergence / settings
#   4. Refit checks (prior design = 298 coding, no sector; same vocabulary)
#   5. Topic alignment: 80 x 80 cosine of beta, one-to-one Hungarian
#      assignment (base R; `clue`/`lpSolve` not installed), theme map carried
#   6. Script-39 second stage (theme contrasts, both specs; slope tests, both
#      specs) on the OLD theta (reproduction of A3) and on the NEW theta
#   7. Method of composition on the new model (script 28/39 logic, B = 50,
#      same seed and draw scheme)
#   8. Old-vs-new comparison, verdict checks, bare tabular drafts (INV-13)
#
# RUN FROM PROJECT ROOT (reads intervenciones.csv, stm_model_285.rds,
# enduring_elite_FINAL.csv, topic_theme_map.csv from the root, as scripts
# 13/27/28/31/35/39). `here` is not installed, so paths are relative to the
# working directory with an explicit root guard (INV-16).
#   A5_FIT_ONLY=1  -> stop after section 3 (fit + fit diagnostics)
#   The refit model (MODEL_RDS, ~159 MB) is NOT version-controlled
#   (replication_repo/.gitignore). To regenerate it: delete it if present, run
#   A5_FIT_ONLY=1 Rscript replication_repo/scripts/42_stm_refit_298_noparty.R
#   from the project root (~1.7 h: 5,976 s, 33 EM iterations on the authors'
#   machine), then run the script again without the flag (~10 min). If the rds
#   exists, the fit is skipped.
#   A5_MOC_B       -> number of posterior draws (default 50 = scripts 28/39)
# Stochastic elements: stm() uses its own `seed = 1` argument (as the original
# fit); the posterior draws use set.seed(1925) below. The RNG state right after
# set.seed(1925) is stored and reinstated before section 7, so the draw stream
# is the same as scripts 28/39 whether or not the fit ran in this session.
# Runtime: fit ~1.5-2 h (original: 5,575 s, 34 EM iterations); sections 5-8
# ~30 min. Not in 00_run_all.sh (add at integration).

suppressMessages({
  library(dplyr)
  library(tidyr)
  library(tidytext)
  library(quanteda)
  library(stm)
  library(sandwich)
  library(lmtest)
})
set.seed(1925)                       # identical to scripts 28/39 (draw stream)
RNG_AT_SEED <- .Random.seed          # reinstated before section 7 (see header)

# ---- parameters -------------------------------------------------------------
OUT_DIR   <- file.path("replication_repo", "output", "rnr2026")
MODEL_RDS <- file.path(OUT_DIR, "A5_stm_model_298_noparty.rds")   # NEW file
OLD_RDS   <- "stm_model_285.rds"                                   # read only
FIT_ONLY  <- identical(Sys.getenv("A5_FIT_ONLY"), "1")
B_DRAWS   <- as.integer(Sys.getenv("A5_MOC_B", "50"))  # 50 = scripts 28/39
BATCH     <- 10L                     # draws per thetaPosterior call, as 28/39
K_TOPICS  <- 80L                     # stm_revised.r: n_k <- 80 (double; the
                                     # refit was run with 80L -> stored type
                                     # differs, value identical)
EM_ITS    <- 75L                     # stm_revised.r: STM_EMITS default 75
STM_SEED  <- 1                       # stm_revised.r: seed = 1
PREV_NEW  <- ~ apellido + camara + Year          # the only change vs original
WEAK_COS  <- 0.8                     # flag threshold for matched topics
N_TOP     <- 10L                     # top words shown per topic
STATECRAFT_THEMES <- c("Elections & parties", "Defense & security",
                       "State administration", "Foreign relations")
LABOR_THEME <- "Labor & industry"
BUNDLE <- "Statecraft bundle"
SPECS <- c(no_party       = "apellido + camara + Year",
           party_adjusted = "apellido + sector + camara + Year")
SLOPE_SPECS <- c(no_party = "camara", party_adjusted = "sector + camara")
A3 <- \(f) file.path(OUT_DIR, paste0("A3_", f))   # script-39 outputs (old theta)
A5 <- \(f) file.path(OUT_DIR, paste0("A5_", f))

needed <- c("intervenciones.csv", OLD_RDS, "enduring_elite_FINAL.csv",
            "topic_theme_map.csv",
            A3(c("sample_counts.csv", "reclassification_285_to_298.csv",
                 "theme_contrasts_long.csv",
                 "within_group_slopes_both_specs.csv",
                 "methodofcomposition_both_specs.csv")))
stopifnot("Run from the project root (paper_1925/)" = all(file.exists(needed)))
dir.create(OUT_DIR, showWarnings = FALSE, recursive = TRUE)
t_script <- proc.time()[["elapsed"]]

# ---- helpers (fit_contrast, slope_tests, slope_diff, rubin: verbatim 39) ----
#' Upper-case and strip Spanish accents (as scripts 13/27/28/31/35/39).
deaccent <- function(x) {
  chartr("ÁÉÍÓÚÜÑáéíóúüñ",
         "AEIOUUNAEIOUUN", toupper(as.character(x)))
}

#' Surname group from paternal/maternal surnames (elite precedence).
code_apellido <- function(pat, mat, elite, common) {
  ifelse(pat %in% elite | mat %in% elite, "elite",
         ifelse(pat %in% common | mat %in% common, "comun", "otro"))
}

#' Elite and common coefficients (vs 'otro') and their contrast (script 39).
#' @param d data.frame with y, apellido (ref 'otro'), controls, Hablante
#' @param rhs character. Right-hand side of the formula.
#' @return one-row data.frame: estimates, legislator-clustered variances
#'   (vcovCL default HC1), SEs and normal p-values
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

#' Within-group and pooled decade-slope tests (scripts 27/31/39 logic).
#' @param s data.frame restricted to 1910-1949 with y, dec10, apellido, controls
#' @param ctrl character. Controls added to the slope regressions.
#' @param orient 'comun' -> common-minus-elite slope (labor);
#'   'elite' -> elite-minus-common slope (statecraft)
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

#' Minimum-cost one-to-one assignment (Hungarian / Kuhn-Munkres, O(n^3)).
#' Base-R implementation with dual potentials; the returned certificate
#' (dual feasibility + complementary slackness) proves optimality.
#' @param cost square numeric matrix (rows = old topics, cols = new topics)
#' @return list(assignment = column for each row, total, dual_feasible,
#'   comp_slack, dual_obj)
hungarian_min <- function(cost) {
  n <- nrow(cost)
  stopifnot(ncol(cost) == n, all(is.finite(cost)))
  u <- numeric(n + 1L); v <- numeric(n + 1L)        # index 1 = dummy column 0
  p <- integer(n + 1L); way <- integer(n + 1L)      # p[j + 1] = row on col j
  for (i in seq_len(n)) {
    p[1L] <- i; j0 <- 0L
    minv <- rep(Inf, n + 1L); used <- rep(FALSE, n + 1L)
    repeat {
      used[j0 + 1L] <- TRUE
      i0 <- p[j0 + 1L]
      free <- !used[-1L]
      cur <- cost[i0, ] - u[i0 + 1L] - v[-1L]
      upd <- free & cur < minv[-1L]
      minv[-1L][upd] <- cur[upd]; way[-1L][upd] <- j0
      cand <- which(free)
      j1 <- cand[which.min(minv[cand + 1L])]
      delta <- minv[j1 + 1L]
      uj <- which(used)
      u[p[uj] + 1L] <- u[p[uj] + 1L] + delta
      v[uj] <- v[uj] - delta
      minv[!used] <- minv[!used] - delta
      j0 <- j1
      if (p[j0 + 1L] == 0L) break
    }
    repeat {
      j1 <- way[j0 + 1L]; p[j0 + 1L] <- p[j1 + 1L]; j0 <- j1
      if (j0 == 0L) break
    }
  }
  col_of_row <- integer(n); col_of_row[p[-1L]] <- seq_len(n)
  ur <- u[-1L]; vc <- v[-1L]
  slack <- cost - outer(ur, vc, "+")
  idx <- cbind(seq_len(n), col_of_row)
  list(assignment = col_of_row, total = sum(cost[idx]),
       dual_feasible = min(slack) > -1e-9,
       comp_slack = max(abs(slack[idx])) < 1e-9,
       dual_obj = sum(ur) + sum(vc))
}

#' Greedy maximum-similarity matching (comparison only).
greedy_max <- function(sim) {
  n <- nrow(sim); out <- integer(n); s <- sim
  for (k in seq_len(n)) {
    w <- arrayInd(which.max(s), dim(s))[1L, ]        # no float equality
    out[w[1L]] <- w[2L]; s[w[1L], ] <- -Inf; s[, w[2L]] <- -Inf
  }
  out
}

#' Row-wise cosine similarity between two K x V matrices (rows of a vs b).
cosine_rows <- function(a, b) {
  an <- a / sqrt(rowSums(a^2)); bn <- b / sqrt(rowSums(b^2))
  an %*% t(bn)
}

#' Top words of each topic by beta.
top_words <- function(logbeta, vocab, n) {
  vapply(seq_len(nrow(logbeta)),
         \(k) paste(vocab[order(-logbeta[k, ])[seq_len(n)]], collapse = " "),
         character(1L))
}

# =============================================================================
# 1. Document frame (verbatim logic of scripts 13/27/28/31/35/39)
# =============================================================================
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
stopifnot(nrow(elite_df) == 298L, sum(is_biz) == 13L,
          length(unique(deaccent(elite_df$surname))) == 298L)
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
rm(iv); invisible(gc())

io$apellido    <- relevel(as.factor(io$apellido), ref = "otro")
io$apellido285 <- relevel(as.factor(io$apellido285), ref = "otro")
io$sector   <- relevel(as.factor(io$sector),   ref = "centro")
io$camara   <- as.factor(io$camara)
io$Year     <- as.numeric(io$Year)
stopifnot(!anyNA(io[, c("apellido", "sector", "camara", "Year", "Hablante")]))
io$dec10 <- ((io$Year %/% 10) * 10 - 1910) / 10          # 0..3 for 1910s-1940s

# ---- 1a. the 298 coding is exactly script 39's (A3 outputs) ---------------
samp <- io |> group_by(apellido) |>
  summarise(n_docs = n(), n_legislators = n_distinct(Hablante),
            .groups = "drop") |> mutate(apellido = as.character(apellido))
samp_a3 <- read.csv(A3("sample_counts.csv"), stringsAsFactors = FALSE)
chk_samp <- inner_join(samp, samp_a3, by = "apellido", suffix = c("", "_a3"))
recl <- io |> count(apellido285, apellido298 = apellido, name = "n_docs") |>
  mutate(across(c(apellido285, apellido298), as.character))
recl_a3 <- read.csv(A3("reclassification_285_to_298.csv"),
                    stringsAsFactors = FALSE)
chk_recl <- inner_join(recl, recl_a3, by = c("apellido285", "apellido298"),
                       suffix = c("", "_a3"))
stopifnot(nrow(chk_samp) == 3L, nrow(chk_recl) == nrow(recl_a3),
          nrow(recl) == nrow(recl_a3))
checks <- data.frame(
  check = c("docs by group vs A3_sample_counts.csv",
            "legislators by group vs A3_sample_counts.csv",
            "285->298 reclassified docs vs A3_reclassification_285_to_298.csv"),
  value = c(max(abs(chk_samp$n_docs - chk_samp$n_docs_a3)),
            max(abs(chk_samp$n_legislators - chk_samp$n_legislators_a3)),
            max(abs(chk_recl$n_docs - chk_recl$n_docs_a3))),
  pass = NA)
checks$pass <- checks$value == 0
message(sprintf("docs %d, legislators %d, elite list %d",
                nrow(io), n_distinct(io$Hablante), length(elite_298)))

# =============================================================================
# 2. Original model: frame identity and vocabulary
# =============================================================================
m_old <- readRDS(OLD_RDS)
stopifnot(nrow(m_old$theta) == nrow(io), ncol(m_old$theta) == K_TOPICS)
Xo <- m_old$settings$covariates$X
old_design_mismatch <- c(
  apellidoelite_vs285 = sum(Xo[, "apellidoelite"] != (io$apellido285 == "elite")),
  apellidocomun_vs285 = sum(Xo[, "apellidocomun"] != (io$apellido285 == "comun")),
  sectorderecha   = sum(Xo[, "sectorderecha"] != (io$sector == "derecha")),
  sectorizquierda = sum(Xo[, "sectorizquierda"] != (io$sector == "izquierda")),
  sectorotro      = sum(Xo[, "sectorotro"] != (io$sector == "otro")),
  camarasenado    = sum(Xo[, "camarasenado"] != (io$camara == "senado")),
  Year            = sum(abs(Xo[, "Year"] - io$Year) > 1e-9))
old_vocab <- m_old$vocab
old_version <- if (is.null(m_old$version)) NA_character_ else m_old$version
old_settings <- m_old$settings; old_settings$covariates <- NULL
old_cov_other <- m_old$settings$covariates[c("betaindex", "yvarlevels")]
old_fit <- list(time = m_old$time, its = m_old$convergence$its,
                converged = m_old$convergence$converged,
                bound = m_old$convergence$bound)
checks <- rbind(checks, data.frame(
  check = c(paste("original prior design vs rebuilt frame:",
                  names(old_design_mismatch), "(mismatching rows)"),
            "dfm features == original model vocabulary (set, size)"),
  value = c(unname(old_design_mismatch),
            as.numeric(!(setequal(featnames(dfm), old_vocab) &&
                           nfeat(dfm) == length(old_vocab)))),
  pass = NA))
checks$pass <- checks$value == 0
rm(Xo, m_old); invisible(gc())
stopifnot("rebuilt frame/dfm differs from the original fit" = all(checks$pass))

# =============================================================================
# 3. Refit (only change: prevalence formula)
# =============================================================================
if (!file.exists(MODEL_RDS)) {
  fit_data <- io[, c("apellido", "camara", "Year")]
  message("fitting STM: K = ", K_TOPICS, ", prevalence ",
          deparse(PREV_NEW), ", start ", format(Sys.time()))
  t0 <- Sys.time()
  m_new <- stm(dfm, K = K_TOPICS, data = fit_data, max.em.its = EM_ITS,
               seed = STM_SEED, prevalence = PREV_NEW,
               init.type = "Spectral")
  t1 <- Sys.time()
  saveRDS(m_new, MODEL_RDS)
  conv <- m_new$convergence
  write.csv(data.frame(
    model = c("original (stm_model_285.rds)", "refit (A5)"),
    prevalence = c("~ apellido(285) + sector + camara + Year",
                   "~ apellido(298) + camara + Year"),
    stm_time_sec = c(old_fit$time, m_new$time),
    wall_clock_sec = c(NA, as.numeric(difftime(t1, t0, units = "secs"))),
    start = c(NA, format(t0)), end = c(NA, format(t1)),
    em_iterations = c(old_fit$its, conv$its),
    converged = c(old_fit$converged, conv$converged),
    max_em_its = c(old_settings$convergence$max.em.its,
                   m_new$settings$convergence$max.em.its),
    em_converge_thresh = c(old_settings$convergence$em.converge.thresh,
                           m_new$settings$convergence$em.converge.thresh),
    final_bound = c(tail(old_fit$bound, 1L), tail(conv$bound, 1L)),
    final_rel_change = c(
      diff(tail(old_fit$bound, 2L)) / abs(tail(old_fit$bound, 2L)[1L]),
      diff(tail(conv$bound, 2L)) / abs(tail(conv$bound, 2L)[1L])),
    stm_version = c(old_version, as.character(packageVersion("stm"))),
    R_version = c(NA, R.version.string)),
    A5("fit_runtime_convergence.csv"), row.names = FALSE)
  nb <- max(length(old_fit$bound), length(conv$bound))
  pad <- \(x) c(x, rep(NA_real_, nb - length(x)))
  write.csv(data.frame(em_iteration = seq_len(nb),
                       bound_original = pad(old_fit$bound),
                       bound_refit = pad(conv$bound)),
            A5("fit_bound_trace.csv"), row.names = FALSE)
  rm(m_new); invisible(gc())
  message("fit done: ", format(t1), "; saved ", MODEL_RDS)
}
rm(dfm); invisible(gc())
if (FIT_ONLY) {
  write.csv(checks, A5("checks_fit_phase.csv"), row.names = FALSE)
  message("A5_FIT_ONLY=1: stopping after the fit")
  quit(save = "no", status = 0)
}

# =============================================================================
# 4. Refit checks: settings identical except the prevalence design
# =============================================================================
m_new <- readRDS(MODEL_RDS)
theta_new <- m_new$theta; K <- ncol(theta_new)
stopifnot(nrow(theta_new) == nrow(io), K == K_TOPICS)
Xn <- m_new$settings$covariates$X
new_settings <- m_new$settings; new_settings$covariates <- NULL
new_cov_other <- m_new$settings$covariates[c("betaindex", "yvarlevels")]
same_setting <- \(nm) isTRUE(all.equal(old_settings[[nm]], new_settings[[nm]]))
#' Full settings list minus the parts that legitimately differ: covariates$X
#' and $formula (the intended change; removed above) and $call (it embeds the
#' formula and the data-object name). K is stored as double in the original
#' (K = n_k, n_k <- 80) and integer in the refit (80L): compare the value.
norm_settings <- function(st) {
  st$call <- NULL
  st$dim$K <- as.numeric(st$dim$K)
  st
}
full_settings_diff <- all.equal(norm_settings(old_settings),
                                norm_settings(new_settings))
if (!isTRUE(full_settings_diff)) message("settings differ: ",
                                         paste(full_settings_diff, collapse = " | "))
set_names <- c("convergence", "gamma", "sigma", "kappa", "tau", "init", "seed",
               "ngroups", "topicreportevery")
checks <- rbind(checks, data.frame(
  check = c(
    "refit prior design columns == (Intercept) apellidocomun apellidoelite camarasenado Year",
    "refit prior apellidoelite vs 298 coding (mismatching rows)",
    "refit prior apellidocomun vs 298 coding (mismatching rows)",
    "refit prior camarasenado vs frame (mismatching rows)",
    "refit prior Year vs frame (mismatching rows)",
    "refit vocabulary identical (order and content) to original",
    "refit K / V / N values identical to original",
    "refit corpus word counts (settings$dim$wcounts) identical to original",
    paste("refit stm settings identical to original:", set_names),
    paste("refit FULL stm settings identical to original (all elements;",
          "excl. covariates$X/$formula and $call; K compared by value)"),
    "refit covariates$betaindex and $yvarlevels identical to original"),
  value = c(
    as.numeric(!identical(colnames(Xn), c("(Intercept)", "apellidocomun",
                                          "apellidoelite", "camarasenado",
                                          "Year"))),
    sum(Xn[, "apellidoelite"] != (io$apellido == "elite")),
    sum(Xn[, "apellidocomun"] != (io$apellido == "comun")),
    sum(Xn[, "camarasenado"] != (io$camara == "senado")),
    sum(abs(Xn[, "Year"] - io$Year) > 1e-9),
    as.numeric(!identical(m_new$vocab, old_vocab)),
    as.numeric(!identical(                  # values (K stored as int vs dbl)
      as.numeric(unlist(new_settings$dim[c("K", "V", "N")])),
      as.numeric(unlist(old_settings$dim[c("K", "V", "N")])))),
    as.numeric(!identical(new_settings$dim$wcounts,
                          old_settings$dim$wcounts)),
    vapply(set_names, \(nm) as.numeric(!same_setting(nm)), numeric(1L)),
    as.numeric(!isTRUE(full_settings_diff)),
    as.numeric(!identical(new_cov_other, old_cov_other))),
  pass = NA))
checks$pass <- checks$value == 0
rm(Xn); invisible(gc())
write.csv(data.frame(
  quantity = c("stm_time_sec", "em_iterations", "converged", "max_em_its",
               "em_converge_thresh", "final_bound", "K_topics",
               "V_vocabulary", "N_documents"),
  original = c(old_fit$time, old_fit$its, old_fit$converged,
               old_settings$convergence$max.em.its,
               old_settings$convergence$em.converge.thresh,
               tail(old_fit$bound, 1L), unlist(old_settings$dim[c("K", "V", "N")])),
  refit = c(m_new$time, m_new$convergence$its, m_new$convergence$converged,
            new_settings$convergence$max.em.its,
            new_settings$convergence$em.converge.thresh,
            tail(m_new$convergence$bound, 1L),
            unlist(new_settings$dim[c("K", "V", "N")]))),
  A5("model_diagnostics.csv"), row.names = FALSE)

# =============================================================================
# 5. Topic alignment (old topic -> new topic), theme map carried across
# =============================================================================
m_old <- readRDS(OLD_RDS)
theta_old <- m_old$theta
lb_old <- m_old$beta$logbeta[[1L]]; lb_new <- m_new$beta$logbeta[[1L]]
stopifnot(identical(dim(lb_old), dim(lb_new)))
cos_b  <- cosine_rows(exp(lb_old), exp(lb_new))      # K x K, old rows x new cols
cos_lb <- cosine_rows(lb_old, lb_new)                # raw log-beta cosine
cor_lb <- cor(t(lb_old), t(lb_new))                  # centred log-beta
hung <- hungarian_min(1 - cos_b)
hung_lb <- hungarian_min(1 - cor_lb)
greedy <- greedy_max(cos_b)
stopifnot(hung$dual_feasible, hung$comp_slack,
          length(unique(hung$assignment)) == K)
match_new <- hung$assignment                          # new topic of old k

tm <- read.csv("topic_theme_map.csv", stringsAsFactors = FALSE)
stopifnot(nrow(tm) == K, identical(tm$topic, seq_len(K)))
themes <- setdiff(unique(tm$theme), "Other")          # script-39 order
stopifnot(length(themes) == 11L, all(STATECRAFT_THEMES %in% themes))
theme_old <- tm$theme
theme_new <- character(K); theme_new[match_new] <- theme_old   # carried
best_old_for_new <- apply(cos_b, 2L, which.max)
best_new_for_old <- apply(cos_b, 1L, which.max)
theta_cor <- cor(theta_old, theta_new)                          # K x K
words_old <- top_words(lb_old, old_vocab, N_TOP)
words_new <- top_words(lb_new, m_new$vocab, N_TOP)
second_best <- \(x, j) max(x[-j])
align <- data.frame(
  old_topic = seq_len(K), new_topic = match_new,
  theme = theme_old,
  cos_beta = cos_b[cbind(seq_len(K), match_new)],
  second_best_cos_for_old = vapply(seq_len(K), \(k)
    second_best(cos_b[k, ], match_new[k]), numeric(1L)),
  cos_logbeta = cos_lb[cbind(seq_len(K), match_new)],
  cor_logbeta = cor_lb[cbind(seq_len(K), match_new)],
  theta_cor_docs = theta_cor[cbind(seq_len(K), match_new)],
  mean_theta_old = colMeans(theta_old),
  mean_theta_new = colMeans(theta_new)[match_new],
  mutual_best = best_new_for_old == match_new &
    best_old_for_new[match_new] == seq_len(K),
  best_old_for_new = best_old_for_new[match_new],
  theme_of_best_old_for_new = theme_old[best_old_for_new[match_new]],
  greedy_new_topic = greedy,
  logbeta_cor_assignment_new_topic = hung_lb$assignment,
  words_old = words_old, words_new = words_new[match_new])
align <- align |> mutate(
  weak_match = cos_beta < WEAK_COS,
  theme_consistent = theme_of_best_old_for_new == theme,
  same_as_greedy = greedy_new_topic == new_topic,
  same_as_logbeta_assignment = logbeta_cor_assignment_new_topic == new_topic,
  flag = weak_match | !theme_consistent)
write.csv(align, A5("topic_alignment.csv"), row.names = FALSE)
write.csv(data.frame(topic = seq_len(K), theme = theme_new,
                     matched_old_topic = match(seq_len(K), match_new)),
          A5("topic_theme_map_refit.csv"), row.names = FALSE)
q <- quantile(align$cos_beta, c(0, 0.05, 0.10, 0.25, 0.5, 0.75, 1))
align_sum <- data.frame(
  statistic = c(paste0("cos_beta_q", c(0, 5, 10, 25, 50, 75, 100)),
                "cos_beta_mean", "n_cos_below_0.8", "n_cos_below_0.9",
                "n_cos_below_0.95", "n_mutual_best", "n_theme_inconsistent",
                "n_flagged", "n_same_as_greedy",
                "n_same_as_logbeta_cor_assignment",
                "theta_cor_median", "theta_cor_min",
                "hungarian_total_cos", "greedy_total_cos",
                "hungarian_dual_feasible", "hungarian_comp_slack",
                "diag_cos_beta_mean_(identity_mapping)"),
  value = c(unname(q), mean(align$cos_beta),
            sum(align$cos_beta < 0.8), sum(align$cos_beta < 0.9),
            sum(align$cos_beta < 0.95), sum(align$mutual_best),
            sum(!align$theme_consistent), sum(align$flag),
            sum(align$same_as_greedy), sum(align$same_as_logbeta_assignment),
            median(align$theta_cor_docs), min(align$theta_cor_docs),
            K - hung$total, sum(cos_b[cbind(seq_len(K), greedy)]),
            hung$dual_feasible, hung$comp_slack, mean(diag(cos_b))))
write.csv(align_sum, A5("topic_alignment_summary.csv"), row.names = FALSE)

# theme membership matrices (script-39 construction), old map / carried map
make_tmat <- function(theme_vec) {
  outcomes <- c(themes, BUNDLE)
  Tm <- matrix(0, K, length(outcomes), dimnames = list(NULL, outcomes))
  for (j in seq_along(themes)) Tm[theme_vec == themes[j], j] <- 1
  Tm[theme_vec %in% STATECRAFT_THEMES, BUNDLE] <- 1
  Tm
}
outcomes <- c(themes, BUNDLE)
Tmat_old <- make_tmat(theme_old); Tmat_new <- make_tmat(theme_new)
stopifnot(identical(colSums(Tmat_old), colSums(Tmat_new)))
prev_old <- (theta_old %*% Tmat_old) * 100            # percentage points
prev_new <- (theta_new %*% Tmat_new) * 100
theme_prev <- data.frame(
  outcome = outcomes, n_topics = colSums(Tmat_old),
  mean_prev_old = colMeans(prev_old), mean_prev_new = colMeans(prev_new),
  doc_cor_old_new = vapply(outcomes, \(o) cor(prev_old[, o], prev_new[, o]),
                           numeric(1L)),
  row.names = NULL)
write.csv(theme_prev, A5("theme_prevalence_old_vs_new.csv"), row.names = FALSE)
rm(m_old, lb_old, lb_new, cos_lb, cor_lb, theta_cor, theta_old)
invisible(gc())
message(sprintf("alignment: median cos %.3f, min %.3f, %d below %.1f",
                median(align$cos_beta), min(align$cos_beta),
                sum(align$weak_match), WEAK_COS))

# =============================================================================
# 6. Script-39 second stage on old theta (reproduction) and new theta
# =============================================================================
base_cols <- c("apellido", "sector", "camara", "Year", "Hablante")
sidx <- which(io$Year >= 1910 & io$Year <= 1949)
sub_df <- io[sidx, c("apellido", "sector", "camara", "Hablante", "dec10")]
slope_defs <- data.frame(outcome = c(LABOR_THEME, BUNDLE),
                         orient = c("comun", "elite"), stringsAsFactors = FALSE)
sl_grid <- merge(slope_defs, data.frame(spec = names(SLOPE_SPECS)))

#' All script-39 deterministic quantities for one theme-prevalence matrix.
#' @return list(long = theme contrasts, slopes = within-group slope tests)
second_stage <- function(prev) {
  grid <- expand.grid(outcome = outcomes, spec = names(SPECS),
                      stringsAsFactors = FALSE)
  res <- vector("list", nrow(grid))
  for (i in seq_len(nrow(grid))) {
    d <- io[, base_cols]; d$y <- prev[, grid$outcome[i]]
    res[[i]] <- cbind(grid[i, ], fit_contrast(d, SPECS[[grid$spec[i]]]))
  }
  long <- do.call(rbind, res); rownames(long) <- NULL
  sl_res <- vector("list", nrow(sl_grid))
  for (i in seq_len(nrow(sl_grid))) {
    s <- sub_df; s$y <- prev[sidx, sl_grid$outcome[i]]
    sl_res[[i]] <- data.frame(sl_grid[i, c("outcome", "spec")],
                              slope_tests(s, SLOPE_SPECS[[sl_grid$spec[i]]],
                                          sl_grid$orient[i]),
                              row.names = NULL)
  }
  slopes <- do.call(rbind, sl_res); rownames(slopes) <- NULL
  list(long = long, slopes = slopes)
}

ss_old <- second_stage(prev_old)
ss_new <- second_stage(prev_new)

# reproduction of script 39 (old theta) -- joined on keys, not row position
a3_long <- read.csv(A3("theme_contrasts_long.csv"), stringsAsFactors = FALSE)
a3_sl <- read.csv(A3("within_group_slopes_both_specs.csv"),
                  stringsAsFactors = FALSE)
val_cols <- c("elite", "elite_se", "elite_p", "comun", "comun_se", "comun_p",
              "contrast", "contrast_se", "contrast_p")
jl <- inner_join(ss_old$long[, c("outcome", "spec", val_cols)],
                 a3_long[, c("outcome", "spec", val_cols)],
                 by = c("outcome", "spec"), suffix = c("", "_a3"))
js <- inner_join(ss_old$slopes, a3_sl[, c("outcome", "spec", "quantity",
                                          "estimate", "se", "p")],
                 by = c("outcome", "spec", "quantity"), suffix = c("", "_a3"))
stopifnot(nrow(jl) == 2L * length(outcomes), nrow(js) == 12L)
checks <- rbind(checks, data.frame(
  check = c("old theta rerun vs A3_theme_contrasts_long.csv (max abs diff)",
            "old theta rerun vs A3_within_group_slopes_both_specs.csv (max abs diff)"),
  value = c(max(abs(as.matrix(jl[, val_cols]) -
                      as.matrix(jl[, paste0(val_cols, "_a3")]))),
            max(abs(as.matrix(js[, c("estimate", "se", "p")]) -
                      as.matrix(js[, c("estimate_a3", "se_a3", "p_a3")])))),
  pass = NA))
checks$pass <- ifelse(grepl("max abs diff", checks$check),
                      checks$value < 1e-10, checks$value == 0)

new_long <- ss_new$long
new_long$n_docs <- nrow(io); new_long$n_clusters <- n_distinct(io$Hablante)
write.csv(new_long |> select(-ends_with("_var")),
          A5("theme_contrasts_long_refit.csv"), row.names = FALSE)
write.csv(ss_new$slopes, A5("within_group_slopes_refit.csv"),
          row.names = FALSE)

# =============================================================================
# 7. Method of composition on the refit (script 28/39 logic)
# =============================================================================
assign(".Random.seed", RNG_AT_SEED, envir = globalenv())   # = set.seed(1925)
qty <- c("elite", "comun", "contrast")
est_arr <- array(NA_real_, c(B_DRAWS, length(outcomes), length(SPECS), 3L),
                 dimnames = list(NULL, outcomes, names(SPECS), qty))
var_arr <- est_arr
sl_est <- array(NA_real_, c(B_DRAWS, 2L, length(SLOPE_SPECS)),
                dimnames = list(NULL, c(LABOR_THEME, BUNDLE),
                                names(SLOPE_SPECS)))
sl_var <- sl_est
sub_ec <- io$apellido[sidx] %in% c("elite", "comun")
t_moc <- proc.time()[["elapsed"]]
ndone <- 0L
while (ndone < B_DRAWS) {
  nb <- min(BATCH, B_DRAWS - ndone)
  dr <- thetaPosterior(m_new, nsims = nb, type = "Global")
  for (b in seq_len(nb)) {
    theta_b <- t(vapply(dr, \(x) x[b, ], numeric(K)))
    pv <- (theta_b %*% Tmat_new) * 100
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
t_moc <- proc.time()[["elapsed"]] - t_moc
saveRDS(list(est = est_arr, var = var_arr, slope_est = sl_est,
             slope_var = sl_var, seed = 1925L, B = B_DRAWS,
             model = MODEL_RDS,
             note = "per-draw estimates and legislator-clustered variances"),
        A5("moc_draws_refit.rds"))
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
  data.frame(g, quantity = "slope_diff", t(rb), B = B_DRAWS, row.names = NULL)
}))
moc <- rbind(moc, moc_sl)
write.csv(moc, A5("methodofcomposition_refit.csv"), row.names = FALSE)

# =============================================================================
# 8. Old theta (script 39) vs refit theta: comparison and verdict checks
# =============================================================================
to_long_q <- function(long) {
  bind_rows(lapply(qty, \(qq) data.frame(
    outcome = long$outcome, spec = long$spec, quantity = qq,
    est = long[[qq]], se = long[[paste0(qq, "_se")]],
    p = long[[paste0(qq, "_p")]])))
}
a3_moc <- read.csv(A3("methodofcomposition_both_specs.csv"),
                   stringsAsFactors = FALSE)
moc_cols <- \(x, sfx) x |> select(outcome, spec, quantity, est, se, p) |>
  rename_with(\(n) paste0("moc_", n, "_", sfx), c(est, se, p))
cmp <- inner_join(to_long_q(a3_long), to_long_q(new_long),
                  by = c("outcome", "spec", "quantity"),
                  suffix = c("_old", "_new")) |>
  left_join(moc_cols(a3_moc, "old"), by = c("outcome", "spec", "quantity")) |>
  left_join(moc_cols(moc, "new"), by = c("outcome", "spec", "quantity")) |>
  mutate(diff = est_new - est_old,
         sign_flip = sign(est_new) != sign(est_old),
         sig05_old = p_old < 0.05, sig05_new = p_new < 0.05,
         sig05_changed = sig05_old != sig05_new,
         stars_old = star_n(p_old), stars_new = star_n(p_new),
         stars_changed = stars_old != stars_new,
         moc_sig05_old = moc_p_old < 0.05, moc_sig05_new = moc_p_new < 0.05,
         moc_sig05_changed = moc_sig05_old != moc_sig05_new)
stopifnot(nrow(cmp) == length(outcomes) * length(SPECS) * length(qty),
          !anyNA(cmp$moc_p_old), !anyNA(cmp$moc_p_new))
write.csv(cmp, A5("comparison_table1_cells.csv"), row.names = FALSE)

# row order of Table 1 (contrast, descending), per column
ranks <- cmp |> filter(quantity == "contrast", outcome %in% themes) |>
  group_by(spec) |>
  mutate(rank_old = rank(-est_old), rank_new = rank(-est_new)) |>
  ungroup() |> select(spec, outcome, est_old, est_new, rank_old, rank_new) |>
  arrange(spec, rank_new)
write.csv(ranks, A5("comparison_row_order.csv"), row.names = FALSE)

# slope tests
a3_moc_sl <- a3_moc |> filter(quantity == "slope_diff")
cmp_sl <- inner_join(a3_sl[, c("outcome", "spec", "quantity", "estimate", "se",
                               "p")],
                     ss_new$slopes, by = c("outcome", "spec", "quantity"),
                     suffix = c("_old", "_new")) |>
  mutate(diff = estimate_new - estimate_old,
         sign_flip = sign(estimate_new) != sign(estimate_old),
         sig05_old = p_old < 0.05, sig05_new = p_new < 0.05)
is_diff_row <- grepl("minus", cmp_sl$quantity)
mo <- \(x, oc, sp, col) x[x$outcome == oc & x$spec == sp, col]
cmp_sl$moc_est_old <- NA_real_; cmp_sl$moc_p_old <- NA_real_
cmp_sl$moc_est_new <- NA_real_; cmp_sl$moc_p_new <- NA_real_
for (i in which(is_diff_row)) {
  oc <- cmp_sl$outcome[i]; sp <- cmp_sl$spec[i]
  cmp_sl$moc_est_old[i] <- mo(a3_moc_sl, oc, sp, "est")
  cmp_sl$moc_p_old[i]   <- mo(a3_moc_sl, oc, sp, "p")
  cmp_sl$moc_est_new[i] <- mo(moc_sl, oc, sp, "est")
  cmp_sl$moc_p_new[i]   <- mo(moc_sl, oc, sp, "p")
}
stopifnot(nrow(cmp_sl) == 12L, !anyNA(cmp_sl$moc_p_new[is_diff_row]))
write.csv(cmp_sl, A5("comparison_slope_tests.csv"), row.names = FALSE)

# verdict checks (computed, not typed)
ct <- cmp |> filter(quantity == "contrast", outcome %in% themes)
sig_list <- \(spec_, col) paste(sort(ct$outcome[ct$spec == spec_ &
                                                  ct[[col]] < 0.05]),
                                collapse = "; ")
verdict <- bind_rows(lapply(names(SPECS), \(sp) {
  x <- ct[ct$spec == sp, ]; r <- ranks[ranks$spec == sp, ]
  data.frame(
    spec = sp,
    item = c("n_contrasts_sig05_det_old", "n_contrasts_sig05_det_new",
             "n_contrasts_sig05_moc_old", "n_contrasts_sig05_moc_new",
             "contrasts_sig05_det_old", "contrasts_sig05_det_new",
             "contrasts_sig05_moc_old", "contrasts_sig05_moc_new",
             "n_contrast_sign_flips", "contrast_sign_flip_themes",
             "n_contrast_sig05_changes_det", "n_contrast_sig05_changes_moc",
             "n_contrasts_sig10_det_old", "n_contrasts_sig10_det_new",
             "row_order_identical", "row_order_spearman",
             "max_abs_rank_shift", "max_abs_contrast_diff",
             "bundle_contrast_old", "bundle_contrast_new",
             "bundle_p_det_new", "bundle_p_moc_new"),
    value = c(sum(x$p_old < 0.05), sum(x$p_new < 0.05),
              sum(x$moc_p_old < 0.05), sum(x$moc_p_new < 0.05),
              sig_list(sp, "p_old"), sig_list(sp, "p_new"),
              sig_list(sp, "moc_p_old"), sig_list(sp, "moc_p_new"),
              sum(x$sign_flip), paste(x$outcome[x$sign_flip], collapse = "; "),
              sum(x$sig05_changed), sum(x$moc_sig05_changed),
              sum(x$p_old < 0.10), sum(x$p_new < 0.10),
              identical(r$outcome[order(r$rank_old)],
                        r$outcome[order(r$rank_new)]),
              round(cor(r$rank_old, r$rank_new, method = "spearman"), 4),
              max(abs(r$rank_old - r$rank_new)),
              round(max(abs(x$diff)), 4),
              round(cmp$est_old[cmp$outcome == BUNDLE & cmp$spec == sp &
                                  cmp$quantity == "contrast"], 4),
              round(cmp$est_new[cmp$outcome == BUNDLE & cmp$spec == sp &
                                  cmp$quantity == "contrast"], 4),
              signif(cmp$p_new[cmp$outcome == BUNDLE & cmp$spec == sp &
                                 cmp$quantity == "contrast"], 3),
              signif(cmp$moc_p_new[cmp$outcome == BUNDLE & cmp$spec == sp &
                                     cmp$quantity == "contrast"], 3)) |>
      as.character())
}))
write.csv(verdict, A5("verdict_checks.csv"), row.names = FALSE)

# no-party vs party-adjusted gap ratios (script-39 `wide` definitions)
gap_ratios <- function(long, theta_label) {
  w <- inner_join(long[long$spec == "no_party", c("outcome", "contrast")],
                  long[long$spec == "party_adjusted", c("outcome", "contrast")],
                  by = "outcome", suffix = c("_no_party", "_party_adjusted"))
  w |> mutate(theta = theta_label,
              delta_contrast = contrast_no_party - contrast_party_adjusted,
              abs_ratio = abs(contrast_no_party) / abs(contrast_party_adjusted),
              same_sign = sign(contrast_no_party) ==
                sign(contrast_party_adjusted),
              gap_grows = same_sign & abs_ratio > 1,
              gap_grows_gt10pct = same_sign & abs_ratio > 1.1)
}
gr <- rbind(gap_ratios(a3_long, "old"), gap_ratios(new_long, "refit"))
write.csv(gr, A5("gap_ratios_old_vs_refit.csv"), row.names = FALSE)
gr_th <- gr[gr$outcome %in% themes, ]
write.csv(data.frame(
  theta = c("old", "refit"),
  n_themes = c(sum(gr_th$theta == "old"), sum(gr_th$theta == "refit")),
  n_gap_grows = c(sum(gr_th$gap_grows[gr_th$theta == "old"]),
                  sum(gr_th$gap_grows[gr_th$theta == "refit"])),
  themes_gt10pct = c(
    paste(gr_th$outcome[gr_th$theta == "old" & gr_th$gap_grows_gt10pct],
          collapse = "; "),
    paste(gr_th$outcome[gr_th$theta == "refit" & gr_th$gap_grows_gt10pct],
          collapse = "; ")),
  labor_abs_ratio = c(
    gr_th$abs_ratio[gr_th$theta == "old" & gr_th$outcome == LABOR_THEME],
    gr_th$abs_ratio[gr_th$theta == "refit" & gr_th$outcome == LABOR_THEME]),
  bundle_abs_ratio = c(gr$abs_ratio[gr$theta == "old" & gr$outcome == BUNDLE],
                       gr$abs_ratio[gr$theta == "refit" &
                                      gr$outcome == BUNDLE])),
  A5("gap_ratios_summary.csv"), row.names = FALSE)

# bare tabular drafts (INV-13), refit theta, same layout as A3
wide_new <- new_long |> filter(outcome %in% themes) |>
  select(outcome, spec, contrast, contrast_se, contrast_p) |>
  pivot_wider(names_from = spec,
              values_from = c(contrast, contrast_se, contrast_p)) |>
  arrange(desc(contrast_no_party))
body <- character(2L * nrow(wide_new))
for (i in seq_len(nrow(wide_new))) {
  th <- gsub("&", "\\\\&", wide_new$outcome[i])
  body[2L * i - 1L] <- sprintf("%s & %s & %s \\\\", th,
    cell(wide_new$contrast_no_party[i], wide_new$contrast_p_no_party[i]),
    cell(wide_new$contrast_party_adjusted[i],
         wide_new$contrast_p_party_adjusted[i]))
  body[2L * i] <- sprintf(" & (%.2f) & (%.2f) \\\\",
                          wide_new$contrast_se_no_party[i],
                          wide_new$contrast_se_party_adjusted[i])
}
n_fmt <- format(nrow(io), big.mark = "{,}")
n_cl <- n_distinct(io$Hablante)
writeLines(c("\\begin{tabular}{lcc}", "\\toprule",
             " & (1) & (2) \\\\",
             " & No party control & Party-adjusted \\\\",
             "\\midrule",
             "\\multicolumn{3}{l}{\\textit{Elite $-$ common contrast}} \\\\",
             body, "\\midrule",
             "Chamber and year controls & Yes & Yes \\\\",
             "Party-bloc control & No & Yes \\\\",
             sprintf("Speeches & %s & %s \\\\", n_fmt, n_fmt),
             sprintf("Legislators (clusters) & %d & %d \\\\", n_cl, n_cl),
             "\\bottomrule", "\\end{tabular}"),
           A5("table1_two_column_refit.tex"))
slw <- ss_new$slopes |> filter(grepl("minus", quantity))
sl_rows <- vapply(c(LABOR_THEME, BUNDLE), \(oc) {
  u <- slw[slw$outcome == oc & slw$spec == "no_party", ]
  a <- slw[slw$outcome == oc & slw$spec == "party_adjusted", ]
  lab <- if (oc == LABOR_THEME) "Labor \\& industry (common $-$ elite)" else
    "Statecraft (elite $-$ common)"
  sprintf("%s & %s (%.2f) & %s (%.2f) \\\\", lab,
          cell(u$estimate, u$p), u$se, cell(a$estimate, a$p), a$se)
}, character(1L))
writeLines(c("\\begin{tabular}{lcc}", "\\toprule",
             "Difference in decade slopes, 1910--1949 & No party control & Party-adjusted \\\\",
             "\\midrule", sl_rows, "\\midrule",
             "Chamber control & Yes & Yes \\\\",
             "Party-bloc control & No & Yes \\\\",
             "\\bottomrule", "\\end{tabular}"),
           A5("slope_tests_two_column_refit.tex"))

write.csv(checks, A5("checks.csv"), row.names = FALSE)
write.csv(data.frame(
  item = c("analysis_runtime_sec", "moc_runtime_sec", "moc_draws", "moc_seed",
           "stm_version", "R_version", "model_file", "all_checks_pass"),
  value = c(round(proc.time()[["elapsed"]] - t_script, 1), round(t_moc, 1),
            B_DRAWS, 1925L, as.character(packageVersion("stm")),
            R.version.string, MODEL_RDS, all(checks$pass))),
  A5("run_info.csv"), row.names = FALSE)
stopifnot("a reproduction/identity check failed; see A5_checks.csv" =
            all(checks$pass))
message("saved A5 outputs to ", OUT_DIR)
