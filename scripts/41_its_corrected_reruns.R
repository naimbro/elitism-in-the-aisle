# 41 -- R&R item A1 follow-up: inheritance of the 1925 zero-share artefact.
#
# Scripts 05, 16, 18, 22, 29, 30, 32 and 33 build the annual elite share as
# elite / max(n, 1) on Start <= year <= End. Congress did not sit in 1925, so
# 1925 enters as a 0% elite share and is the first post-break observation of
# every 1925 ITS. This script recomputes the 1925 break of every published
# robustness result under:
#   paper    : as published (1925 = 0)   -> must reproduce the published value
#   gap      : 1925 missing (share = NA when < 5 sitting, as 04/17/20)
#   fill1926 : 1926 roster assigned to 1925 (sensitivity)
#   nosub    : gap, and substitutes (Tipo "Suplente"/"Suplentes") removed
# It also reports decade means of the composition series (script 04 logic)
# with and without substitutes (item 8). Nothing under paper/ is modified.
#
# RUN FROM THE replication_repo ROOT:
#   "C:/Program Files/R/R-4.3.3/bin/Rscript.exe" scripts/41_its_corrected_reruns.R
# External inputs (same as 18/29): data/processed/business_x_historical.csv (shipped),
#   RAW_DATA_ROOT/"Chile - elite networks.xlsx", 1874 censo (RAW_DATA_ROOT env
#   var, default ".." = the paper_1925 project dir, as _measure_helpers.py).
#   The censo and workbook feed only the five script-18 deterministic rows; without
#   them the other 24 rows still run and outputs get the suffix "_norawdata".
# ITS spec identical to 05 (and to fit_its in 37): elite ~ t + post + t:post,
# window 1880-1970, HAC Bartlett 5 lags, no adjustment, normal p-values.
# Deterministic: no seed needed (INV-14).

suppressMessages({
  library(data.table)
  library(stringi)
  library(sandwich)
  library(readxl)
})

OUT_DIR  <- file.path("output", "rnr2026")
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)
BASELINE <- 1925L
WIN      <- c(1880L, 1970L)
HAC_LAGS <- 5L
MIN_N    <- 5L
SUB_TIPOS <- c("Suplente", "Suplentes")
PART <- c("DE", "DEL", "LA", "LAS", "LOS", "Y", "DA", "DI", "VON", "VAN",
          "SAN", "SANTA")
RAW_DATA_ROOT <- Sys.getenv("RAW_DATA_ROOT", "..")
XLSX <- file.path(RAW_DATA_ROOT, "Chile - elite networks.xlsx")
CENSO_REL <- file.path("censo_agricola", "1874", "censo_1874.csv")
CENSO <- Filter(file.exists, c(file.path(RAW_DATA_ROOT, CENSO_REL),
                               file.path(RAW_DATA_ROOT, "..", "..",
                                         CENSO_REL)))[1L]
# Round 2: shipped copy in the repo (was ../quality_reports/, outside the repo).
BIZ_FILE <- file.path("data", "processed", "business_x_historical.csv")
# Round 3: the 1874 censo and the elite-network workbook are needed ONLY for the
# five script-18 deterministic-rebuild rows. Without them (public clone) the script
# runs every other row and writes its outputs with the suffix "_norawdata", so the
# shipped full outputs are never overwritten by a partial run.
HAVE_RAW <- !is.na(CENSO) && file.exists(XLSX)
OUT_SUFFIX <- if (HAVE_RAW) "" else "_norawdata"
out_path <- \(name) file.path(OUT_DIR, sub("\\.(csv|tex)$",
                                          paste0(OUT_SUFFIX, ".\\1"), name))
if (!HAVE_RAW) {
  message("[41] 1874 censo / elite-network workbook not found (not redistributed): ",
          "the five script-18 deterministic rows are skipped; outputs -> *_norawdata.*")
}
VARIANTS <- c("paper", "gap", "fill1926", "nosub")

# ------------------------------------------------------------------ helpers
deaccent <- \(s) {
  s <- ifelse(is.na(s), "NAN", as.character(s))  # Python str(nan) -> "NAN"
  s <- stri_trans_nfkd(s)
  s <- gsub("[^\x01-\x7F]", "", s, perl = TRUE)
  trimws(toupper(s))
}
#' Tokens as _measure_helpers.toks: split on space/hyphen, len >= 4, no PART.
toks_all <- \(v) {
  u <- unlist(strsplit(deaccent(v), "[ -]"))
  unique(u[nchar(u) >= 4L & !(u %chin% PART)])
}
share_or_na <- \(k, n) fifelse(n >= MIN_N, 100 * k / pmax(n, 1), NA_real_)

#' Segmented ITS (identical to fit_its in 37 / the 05 spec).
fit_its <- function(dt, br = BASELINE) {
  d <- copy(dt)
  d[, `:=`(t = year - br, post = as.numeric(year >= br))]
  d[, tpost := t * post]
  m <- lm(elite ~ t + post + tpost, data = d)
  vc <- NeweyWest(m, lag = HAC_LAGS, prewhite = FALSE, adjust = FALSE)
  b <- unname(coef(m)["post"]); se <- sqrt(vc["post", "post"])
  tr <- unname(coef(m)["t"]); tr_se <- sqrt(vc["t", "t"])
  list(shift = b, se = se, p = 2 * pnorm(-abs(b / se)), pretrend = tr,
       pretrend_p = 2 * pnorm(-abs(tr / tr_se)), n = nrow(d))
}

# ------------------------------------------------------------------- roster
cong <- fread("data/processed/cong_df.csv", encoding = "UTF-8",
              colClasses = "character")
cong[, `:=`(s_yr = suppressWarnings(as.numeric(Start)),
            e_yr = suppressWarnings(as.numeric(End)))]
cong <- cong[!is.na(s_yr) & !is.na(e_yr)]
cong[, `:=`(pat = deaccent(Pat), mat = deaccent(Mat),
            is_sub = Tipo %chin% SUB_TIPOS)]
YRS <- seq.int(WIN[1L], WIN[2L])
SIT <- vapply(YRS, \(y) cong$s_yr <= y & cong$e_yr >= y,
              logical(nrow(cong)))                  # rows x years
KEEP_NOSUB <- !cong$is_sub

#' Annual 1880-1970 series for an elite flag under one 1925 treatment.
annual <- function(flag, variant) {
  keep <- if (variant == "nosub") KEEP_NOSUB else rep(TRUE, nrow(cong))
  n <- colSums(SIT & keep); k <- colSums(SIT & keep & flag)
  el <- if (variant == "paper") 100 * k / pmax(n, 1) else share_or_na(k, n)
  dt <- data.table(year = YRS, elite = el)
  if (variant == "fill1926") {
    dt[year == BASELINE, elite := dt[year == BASELINE + 1L, elite]]
  }
  dt[!is.na(elite)]
}
flag_or <- \(s) cong$pat %chin% s | cong$mat %chin% s

# ------------------------------------------------------------- surname sets
final <- fread("data/processed/enduring_elite_FINAL.csv", encoding = "UTF-8")
final[, s := deaccent(surname)]
full298 <- unique(final$s)
biz <- grepl("business_gate", fifelse(is.na(final$sources), "",
                                      final$sources))
base285 <- unique(final$s[!biz])
two <- c("PORTALES", "BALMACEDA")
four <- c(two, "BULNES", "GARCIA-HUIDOBRO")
stopifnot(all(four %chin% full298), length(full298) == 298L,
          length(base285) == 285L)

# Script 29 threshold sweep
bx <- fread(BIZ_FILE, encoding = "UTF-8")
bx[, s := deaccent(surname)]
cand <- bx[in_hist == TRUE & likely_given_name == FALSE]
sweep_set <- \(ov, ap) {
  union(base285, setdiff(cand[overrep_ratio >= ov & n_leaders >= ap]$s,
                         base285))
}

# Script 18 deterministic rebuild (_measure_helpers.build_hist / build_list)
if (HAVE_RAW) {
  cz <- fread(CENSO, encoding = "Latin-1", colClasses = "character",
              na.strings = c("", "NA", "N/A", "NULL", "nan", "NaN"))
  for (col in c("Paterno", "Materno", "Avaluacion")) {
    set(cz, j = col, value = iconv(cz[[col]], "latin1", "UTF-8"))
  }
  cz[, aval := suppressWarnings(as.numeric(Avaluacion))]
  thr <- quantile(cz$aval, 0.75, na.rm = TRUE, type = 7L)
  big <- cz[!is.na(aval) & aval >= thr]
  hist_tok <- toks_all(c(na.omit(big$Paterno), na.omit(big$Materno)))
  xl_cells <- unlist(lapply(excel_sheets(XLSX), \(sh) {
    x <- suppressMessages(read_excel(XLSX, sheet = sh, col_names = FALSE,
                                     col_types = "text"))
    v <- unlist(x, use.names = FALSE)
    v[!is.na(v)]
  }))
  HIST <- union(hist_tok, toks_all(xl_cells))
  nse <- fread("data/processed/surname_nse.csv", encoding = "UTF-8")
  nse[, s := deaccent(surname)]
  nse <- nse[, .SD[.N], by = s]            # Python dict: last duplicate wins
  # NB: NaN comparisons are False in Python, so an NA never excludes.
  build_list <- \(ses_cut, min_b) {
    drop_b <- (nse$n_occ < min_b) %in% TRUE
    drop_s <- (nse$mean_nse < ses_cut) %in% TRUE
    nse$s[!drop_b & !drop_s & nse$s %chin% HIST]
  }
}

# ---------------------------------------------------------------- the specs
# Each spec: published value (paper text/table), script output value, where.
LOC_05 <- "sections/05_break1925.tex:3; online_appendix.tex:131"
LOC_16 <- "online_appendix.tex:805; tables/table_its_robustness.tex"
LOC_18 <- "online_appendix.tex:841; tables/table_cutoff_sensitivity.tex"
LOC_22 <- "online_appendix.tex:894; tables/table_coding_rule.tex"
LOC_29 <- "online_appendix.tex:910"
LOC_33 <- "online_appendix.tex:857,880-883"
specs <- list(
  list("05", "headline (permissive OR, 298)", flag_or(full298), -13.32,
       -13.32, LOC_05, WIN),
  list("16", "window 1900-1955", flag_or(full298), -13.80, -13.80, LOC_16,
       c(1900L, 1955L)),
  list("16", "window 1890-1960", flag_or(full298), -13.45, -13.45, LOC_16,
       c(1890L, 1960L)),
  list("16", "window 1880-1970", flag_or(full298), -13.32, -13.32, LOC_16,
       WIN),
  list("18", "published measure (298)", flag_or(full298), -13.32, -13.32,
       LOC_18, WIN),
  list("22", "coding: permissive (OR)", flag_or(full298), -13.32, -13.32,
       LOC_22, WIN),
  list("22", "coding: strict (AND)",
       cong$pat %chin% full298 & cong$mat %chin% full298, -2.85, -2.85,
       LOC_22, WIN),
  list("22", "coding: paternal only", cong$pat %chin% full298, -7.58, -7.58,
       LOC_22, WIN),
  list("29", "drop 13 business-route surnames (285)", flag_or(base285),
       -11.13, -11.13,
       "online_appendix.tex:131,857,887,910", WIN)
)
specs_18det <- if (HAVE_RAW) list(
  list("18", "SES>=60, bearers>=30 (deterministic)",
       flag_or(build_list(60, 30)), -15.13, -15.13, LOC_18, WIN),
  list("18", "SES>=65, bearers>=30 (deterministic)",
       flag_or(build_list(65, 30)), -11.29, -11.29,
       paste0(LOC_18, "; online_appendix.tex:131"), WIN),
  list("18", "SES>=70, bearers>=30 (deterministic)",
       flag_or(build_list(70, 30)), -10.51, -10.51, LOC_18, WIN),
  list("18", "SES>=65, bearers>=5 (deterministic)",
       flag_or(build_list(65, 5)), -11.97, -11.97, LOC_18, WIN),
  list("18", "SES>=65, bearers>=50 (deterministic)",
       flag_or(build_list(65, 50)), -11.38, -11.38, LOC_18, WIN)
) else list()
# Integration note (2026-09-26): scripts 29 and 33 now use the n < 5 rule, so
# output/m2_business_route_robustness.csv and m4_depth_monotonicity.csv hold the
# CORRECTED values. The submitted script outputs they used to supply are frozen
# here (git tag submitted-RaP-2026-07-08), so the reproduction check still tests
# the published numbers.
sw_grid <- CJ(ov = c(6L, 8L, 12L), ap = c(3L, 5L, 10L))
pub_sweep <- c(-13.32, -13.32, -12.27,   # ov 6:  ap 3, 5, 10 (submitted 29)
               -13.32, -13.32, -12.27,   # ov 8
               -12.48, -12.48, -12.50)   # ov 12
specs_sweep <- lapply(seq_len(nrow(sw_grid)), \(i) {
  ov <- sw_grid$ov[i]; ap <- sw_grid$ap[i]
  list("29", sprintf("sweep overrep>=%d, appearances>=%d", ov, ap),
       flag_or(sweep_set(ov, ap)), NA_real_, pub_sweep[i],
       paste0(LOC_29, " (band -12.3 to -13.3)"), WIN)
})
pub_depth <- c(-13.32, -13.76, -9.49, -7.44)   # submitted 33 output = text
specs_depth <- lapply(1:4, \(dd) list(
  if (dd == 2L) "30/33" else "33", sprintf("depth >= %d", dd),
  flag_or(unique(final$s[final$n_sources >= dd])), pub_depth[dd],
  pub_depth[dd],
  if (dd == 2L) paste0(LOC_33, "; tables/table_depth_gate.tex (-13.8)")
  else LOC_33, WIN))
specs_dyn <- list(
  list("32", "drop Portales + Balmaceda", flag_or(setdiff(full298, two)),
       -12.24, -12.24, LOC_29, WIN),
  list("32", "drop four dynasties", flag_or(setdiff(full298, four)), -11.64,
       -11.64, LOC_29, WIN))
specs <- c(specs[1:5], specs_18det, specs[-(1:5)], specs_sweep, specs_depth, specs_dyn)

inh <- rbindlist(lapply(specs, \(sp) {
  fits <- lapply(VARIANTS, \(v) {
    a <- annual(sp[[3L]], v)
    fit_its(a[year >= sp[[7L]][1L] & year <= sp[[7L]][2L]])
  })
  names(fits) <- VARIANTS
  data.table(
    script = sp[[1L]], spec = sp[[2L]],
    window = paste(sp[[7L]], collapse = "-"), location = sp[[6L]],
    published_text = sp[[4L]], published_output = sp[[5L]],
    replicated = fits$paper$shift, replicated_p = fits$paper$p,
    gap = fits$gap$shift, gap_se = fits$gap$se, gap_p = fits$gap$p,
    fill1926 = fits$fill1926$shift, fill1926_p = fits$fill1926$p,
    nosub = fits$nosub$shift, nosub_se = fits$nosub$se,
    nosub_p = fits$nosub$p,
    pretrend_paper = fits$paper$pretrend, pretrend_gap = fits$gap$pretrend,
    pretrend_nosub = fits$nosub$pretrend)
}))
inh[, reproduces := abs(replicated - published_output) < 0.006]
inh[, change_gap := gap - replicated]
fwrite(inh, out_path("A1_inheritance_1925.csv"))
message(sprintf("[41] %d / %d published values reproduced to 2 dp",
                sum(inh$reproduces), nrow(inh)))
stopifnot(all(inh$reproduces))

# --------------------------------------------- script-16 placebo claims
claims <- rbindlist(lapply(VARIANTS, \(v) {
  a <- annual(flag_or(full298), v)
  prof <- rbindlist(lapply(1900:1950, \(b) {
    r <- fit_its(a, b); data.table(b = b, shift = r$shift, se = r$se)
  }))
  locmax <- vapply(list(c(1900L, 1955L), c(1890L, 1960L), c(1880L, 1970L)),
                   \(w) {
    aw <- a[year >= w[1L] & year <= w[2L]]
    cw <- seq.int(max(w[1L] + 5L, 1905L), min(w[2L] - 4L, 1950L))
    s <- vapply(cw, \(b) abs(fit_its(aw, b)$shift), numeric(1L))
    cw[which.max(s)]
  }, integer(1L))
  data.table(
    variant = v, argmax_abs_1900_1950 = prof[which.max(abs(shift))]$b,
    max_abs = max(abs(prof$shift)),
    shift_1922 = prof[b == 1922L]$shift, shift_1924 = prof[b == 1924L]$shift,
    shift_1925 = prof[b == 1925L]$shift, shift_1926 = prof[b == 1926L]$shift,
    shift_1927 = prof[b == 1927L]$shift,
    locmax_1900_1955 = locmax[1L], locmax_1890_1960 = locmax[2L],
    locmax_1880_1970 = locmax[3L],
    n_years_within_0.5_of_max = sum(abs(prof$shift) >=
                                      max(abs(prof$shift)) - 0.5))
}))
fwrite(claims, out_path("A1_inheritance_16_placebo_claims.csv"))

# ----------------------------- item 8: composition decade means (04 logic)
YRS_C <- seq.int(1830L, 2020L)
comp_series <- \(keep) {
  flag <- flag_or(full298)
  raw <- vapply(YRS_C, \(y) {
    m <- keep & cong$s_yr <= y & cong$e_yr >= y
    share_or_na(sum(flag[m]), sum(m))
  }, numeric(1L))
  sm <- vapply(seq_along(raw), \(i) {       # rolling(5, center, min 3)
    v <- raw[max(1L, i - 2L):min(length(raw), i + 2L)]
    v <- v[!is.na(v)]
    if (length(v) >= 3L) mean(v) else NA_real_
  }, numeric(1L))
  data.table(year = YRS_C, raw = raw, smoothed = sm)
}
ca <- comp_series(rep(TRUE, nrow(cong)))
cn <- comp_series(KEEP_NOSUB)
dec <- data.table(decade = 10L * (YRS_C %/% 10L),
                  all_smoothed = ca$smoothed, nosub_smoothed = cn$smoothed,
                  all_raw = ca$raw, nosub_raw = cn$raw)
dec <- dec[, lapply(.SD, \(x) mean(x, na.rm = TRUE)), by = decade]
dec[, diff_smoothed := nosub_smoothed - all_smoothed]
fwrite(dec, out_path("A1_composition_decades_substitutes.csv"))

# --------- item 5: published LEVEL numbers that change without substitutes
# Each quantity is recomputed with the exact convention of its script:
#   29/30/33 decade_share: mean of annual k / max(n, 1) over 1860-1869
#   22 share_at: annual share in 1865, NA if n < 5
#   18 cong_share: 5-yr smoothed (04 rule) value at 1865 (the "1860s" column)
#      and fold_1900 = smoothed share at 1900 / population share at 1900
#   Fig. 3 over-representation: smoothed Congress share / 7-yr smoothed
#      population share (pop_prevalence_by_year.csv), mean over 1884-1889
decade_share <- \(flag, keep, y0, y1) mean(vapply(y0:y1, \(y) {
  m <- keep & cong$s_yr <= y & cong$e_yr >= y
  100 * sum(flag[m]) / max(sum(m), 1)
}, numeric(1L)))
share_at <- \(flag, keep, y) {
  m <- keep & cong$s_yr <= y & cong$e_yr >= y
  share_or_na(sum(flag[m]), sum(m))
}
smooth_series <- \(flag, keep) {
  raw <- vapply(YRS_C, \(y) share_at(flag, keep, y), numeric(1L))
  vapply(seq_along(raw), \(i) {
    v <- raw[max(1L, i - 2L):min(length(raw), i + 2L)]
    v <- v[!is.na(v)]
    if (length(v) >= 3L) mean(v) else NA_real_
  }, numeric(1L))
}
pop <- fread("data/processed/pop_prevalence_by_year.csv")
setorder(pop, year)
pop[, pe := vapply(seq_len(.N), \(i) mean(pct_elite[max(1L, i - 3L):
                                                     min(.N, i + 3L)]),
                   numeric(1L))]
pop_at <- \(y) pop$pe[which.min(abs(pop$year - y))]
KEEP_ALL <- rep(TRUE, nrow(cong))
lvl_row <- function(script, quantity, location, published, flag, how) {
  vals <- vapply(list(KEEP_ALL, KEEP_NOSUB), \(kp) switch(how,
    dec1860 = decade_share(flag, kp, 1860L, 1869L),
    at1865 = share_at(flag, kp, 1865L),
    sm1865 = smooth_series(flag, kp)[YRS_C == 1865L],
    fold1900 = smooth_series(flag, kp)[YRS_C == 1900L] / pop_at(1900L),
    overrep8489 = {
      s <- smooth_series(flag, kp)
      mean(s[YRS_C %in% 1884:1889] / vapply(1884:1889, pop_at, numeric(1L)))
    }), numeric(1L))
  data.table(script = script, quantity = quantity, location = location,
             published = published, all_members = vals[1L],
             titular_only = vals[2L], change = vals[2L] - vals[1L])
}
f298 <- flag_or(full298)
levels_tab <- rbindlist(c(
  list(
    lvl_row("30/33/29", "1860s share, depth >= 1 (298)",
            "online_appendix.tex:857,880,910; table_depth_gate.tex",
            49.9, f298, "dec1860"),
    lvl_row("29", "1860s share, drop 13 (285)", "online_appendix.tex:910",
            47.1, flag_or(base285), "dec1860")),
  lapply(2:4, \(dd) lvl_row(
    "30/33", sprintf("1860s share, depth >= %d", dd),
    "online_appendix.tex:857,881-883",
    c(NA, 42.7, 33.9, 25.4)[dd],
    flag_or(unique(final$s[final$n_sources >= dd])), "dec1860")),
  list(
    lvl_row("22", "1865 share, permissive (OR)",
            "online_appendix.tex:894; table_coding_rule.tex", 52.0, f298,
            "at1865"),
    lvl_row("22", "1865 share, strict (AND)",
            "online_appendix.tex:894; table_coding_rule.tex", 14.0,
            cong$pat %chin% full298 & cong$mat %chin% full298, "at1865"),
    lvl_row("22", "1865 share, paternal only",
            "online_appendix.tex:894; table_coding_rule.tex", 32.0,
            cong$pat %chin% full298, "at1865"),
    lvl_row("18", "1860s share (smoothed at 1865), published 298",
            "table_cutoff_sensitivity.tex", 51.2, f298, "sm1865"),
    lvl_row("18", "over-representation fold ~1900, published 298",
            "online_appendix.tex:841; table_cutoff_sensitivity.tex", 21.1,
            f298, "fold1900"),
    lvl_row("04/20", "Fig. 3 over-representation, mean 1884-1889",
            "Fig. 3 (fig:composition)", NA_real_, f298, "overrep8489"))
))
levels_tab[, reproduces := is.na(published) |
             abs(round(all_members, 1) - published) < 0.051]
fwrite(levels_tab, out_path("A1_levels_titular_vs_all.csv"))
stopifnot(all(levels_tab$reproduces))

# ------------------------------------------------------------- LaTeX table
mth <- \(x, d = 2L) fifelse(is.na(x), "--",
                            sprintf(paste0("$%.", d, "f$"), x))
star <- \(p) fifelse(p < 0.01, "***", fifelse(p < 0.05, "**",
                     fifelse(p < 0.10, "*", "")))
writeLines(c(
  "\\begin{tabular}{llcccc}", "\\toprule",
  paste0("Script & Specification & Published & 1925 as gap & ",
         "1926 roster in 1925 & No substitutes \\\\"), "\\midrule",
  vapply(seq_len(nrow(inh)), \(i) sprintf(
    "%s & %s & %s & %s%s & %s%s & %s%s \\\\", inh$script[i],
    gsub(">=", "$\\\\geq$", inh$spec[i]), mth(inh$replicated[i]),
    mth(inh$gap[i]), star(inh$gap_p[i]), mth(inh$fill1926[i]),
    star(inh$fill1926_p[i]), mth(inh$nosub[i]), star(inh$nosub_p[i])), ""),
  "\\bottomrule", "\\end{tabular}"),
  out_path("A1_inheritance_1925.tex"))

options(width = 220L)
print(inh[, .(script, spec, pub = published_output,
              rep = round(replicated, 2), gap = round(gap, 2),
              gap_p = signif(gap_p, 2), fill = round(fill1926, 2),
              nosub = round(nosub, 2), nosub_p = signif(nosub_p, 2),
              tr_gap = round(pretrend_gap, 3))])
print(claims)
print(dec[decade <= 1900L])
print(levels_tab[, .(script, quantity, published, all = round(all_members, 2), titular = round(titular_only, 2), change = round(change, 2))])
