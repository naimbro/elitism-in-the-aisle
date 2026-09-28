# 46a -- R&R 2026: topic prevalence at the covariate means, 298 coding (input to script 46).
#
# Script 12b selects the topic-level illustration (appendix tab:stmcoefs) by a tercile rule on
# topic prevalence evaluated with party bloc, chamber and year at their means. Those
# prevalences are not in 12b's shipped CSV (table1_topic_coefs_298.csv holds only the
# coefficients), so this script recomputes them from 12b's saved estimateEffect object with
# 12b's exact code, and writes them to a small CSV that script 46 reads. Nothing is
# re-estimated: the numbers are deterministic functions of stm_prep_298.rds.
#
#   X      = model.matrix(~ apellido + sector + camara + Year, prep$data); xbar = colMeans(X)
#   betas  = per topic, mean over the Global-uncertainty draws of the estimateEffect coefficients
#   prev_e = betas %*% xbar with (apellidoelite, apellidocomun) = (1, 0)
#   prev_c = betas %*% xbar with (apellidoelite, apellidocomun) = (0, 1)
#   leading terms = top 4 terms by beta per topic (terms_stm_285.csv), as 12b labels them
#
# Guard: the tercile rule applied to these prevalences must return exactly the topics (and
# order) that 12b wrote to output/table1_v3style_adjusted_298.csv; the script stops otherwise.
#
# RUN FROM THE PROJECT ROOT (reads stm_prep_298.rds and terms_stm_285.csv there, as 12b).
# The repo directory is taken from this script's path. Deterministic, no seed (INV-14).
# Output: <repo>/output/stm_topic_prevalence_at_means_298.csv

suppressMessages({
  library(dplyr)
  library(stm)                       # class/methods of the saved estimateEffect object
})

# ---- paths ------------------------------------------------------------------
script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
REPO <- if (length(script_arg) == 1L) {
  dirname(dirname(normalizePath(sub("^--file=", "", script_arg))))
} else {
  "replication_repo"
}
PREP  <- "stm_prep_298.rds"
TERMS <- "terms_stm_285.csv"
SEL12B <- file.path(REPO, "output", "table1_v3style_adjusted_298.csv")
OUT    <- file.path(REPO, "output", "stm_topic_prevalence_at_means_298.csv")
stopifnot("Run from the project root (needs stm_prep_298.rds, terms_stm_285.csv)" =
            all(file.exists(c(PREP, TERMS, SEL12B))))

# ---- prevalence at the means (verbatim logic of script 12b) --------------------
prep <- readRDS(PREP)
X <- model.matrix(~ apellido + sector + camara + Year, prep$data)
xbar <- colMeans(X)
betas <- t(vapply(prep$parameters,
                  function(tp) colMeans(do.call(rbind, lapply(tp, function(s) s$est))),
                  numeric(ncol(X))))
colnames(betas) <- colnames(X)

#' Covariate profile at the means with the surname-group dummies set for one group.
#' @param lvl "elite" or "comun".
#' @return Named numeric vector aligned with the columns of `X`.
profile_at_means <- function(lvl) {
  x <- xbar
  x["apellidocomun"] <- 0
  x["apellidoelite"] <- 0
  x[paste0("apellido", lvl)] <- 1
  x
}
prev_e <- as.numeric(betas %*% profile_at_means("elite"))
prev_c <- as.numeric(betas %*% profile_at_means("comun"))
K <- nrow(betas)

# ---- leading terms (12b's labels) ----------------------------------------------
lab <- read.csv(TERMS, stringsAsFactors = FALSE) |>
  arrange(desc(beta)) |>
  group_by(topic) |>
  slice(1:4) |>
  summarise(w = paste(term, collapse = "/"), .groups = "drop")
labv <- setNames(lab$w, lab$topic)
stopifnot(length(labv) == K)

out <- data.frame(topic = seq_len(K),
                  prev_elite = prev_e, prev_common = prev_c,
                  beta_elite = betas[, "apellidoelite"],
                  beta_comun = betas[, "apellidocomun"],
                  leading_terms = unname(labv[as.character(seq_len(K))]))
write.csv(out, OUT, row.names = FALSE)

# ---- guard: 12b's tercile rule reproduces 12b's saved selection -----------------
te1 <- quantile(prev_e, 1 / 3)
tc1 <- quantile(prev_c, 1 / 3)
elite_t <- which(prev_c <= tc1 & prev_e >= te1)
comun_t <- which(prev_e <= te1 & prev_c >= tc1)
ord_e <- elite_t[order(-(prev_e[elite_t] - prev_c[elite_t]))]
ord_c <- comun_t[order(-(prev_c[comun_t] - prev_e[comun_t]))]
sel <- read.csv(SEL12B, stringsAsFactors = FALSE)
topic_num <- function(v) as.integer(sub("^T([0-9]+) .*$", "\\1", v[nzchar(v)]))
stopifnot("tercile rule does not reproduce 12b's elite selection" =
            identical(ord_e, topic_num(sel$elite_topic)),
          "tercile rule does not reproduce 12b's common selection" =
            identical(ord_c, topic_num(sel$common_topic)))

message(sprintf("thresholds: elite prevalence 1/3-quantile %.6f, common %.6f", te1, tc1))
message("elite-side topics:  ", paste0("T", ord_e, collapse = " "))
message("common-side topics: ", paste0("T", ord_c, collapse = " "))
message("matches 12b selection (", basename(SEL12B), "); wrote ", OUT)
