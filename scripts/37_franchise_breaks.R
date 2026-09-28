# 37 -- R&R item A1 (Referee 1, comment R1.2b): break tests at franchise and
# electoral-law events; roster-construction sensitivity of the 1925 break.
# Round 2 (after coder-critic 68/100).
#
# RUN FROM THE replication_repo ROOT:
#   "C:/Program Files/R/R-4.3.3/bin/Rscript.exe" scripts/37_franchise_breaks.R
#
# ELITE CODING (identical to 05/16): a legislator is elite if the paternal OR
# maternal surname (NFKD-deaccented, upper, stripped) is in
# enduring_elite_FINAL.csv.
#
# SERIES VARIANTS (one helper, share = NA when fewer than 5 sitting, as 04/17/20)
#   primary     : Start <= year <= End (the 05/16 rule), all members
#   nosub       : same rule, Tipo "Suplente"/"Suplentes" (substitutes) removed
#   fixed       : members sitting on 1 July of the year (Period dates), all
#   fixed_nosub : 1 July roster, substitutes removed
#   cohort      : one observation per legislature (members sharing a Period
#                 start date), all / nosub
#   paper       : primary rule with 05/16's max(n, 1) denominator -> 1925 = 0;
#                 used ONLY to reproduce the published numbers.
# 1925 has no sitting Congress (dissolved Sept 1924; next sat March 1926):
#   gap (primary treatment) or "1926 roster assigned to 1925" (sensitivity).
#
# ITS SPEC (identical to 05/16): elite ~ t + post + t:post, t = year - break,
#   post = 1[year >= break]; Newey-West/Bartlett HAC, 5 lags (cohort series:
#   automatic lag floor(4 (n/100)^(2/9))), no small-sample adjustment, normal
#   p-values and 95% CIs (= statsmodels cov_type="HAC").
#
# Written in R because the Python env currently fails to import pandas
# (numpy 2.5.2 / pandas 2.2.1 binary mismatch). strucchange is not installed:
# Bai-Perron is implemented here (exact global-SSR partition by dynamic
# programming, as strucchange::breakpoints; checked by brute force for m <= 2),
# break count by BIC (strucchange df convention) and LWZ (Bai-Perron 2003);
# break-date intervals from a moving-block residual bootstrap that FIXES the
# number of breaks at the BIC choice and matches breaks by order.
#
# Outputs: output/rnr2026/A1_*.csv, A1_*.tex (bare tabular, INV-13);
#          figures/rnr2026/A1_*.pdf/.png (serif, no title, INV-12).

suppressMessages({
  library(data.table)
  library(stringi)
  library(sandwich)
  library(ggplot2)
})
set.seed(1925L)  # INV-14: only stochastic step is the break-date bootstrap

# ---------------------------------------------------------------- constants
PRE_START  <- 1834L  # first year under the 1833 Constitution; 1811-33 erratic
PRE_END    <- 1973L  # Congress dissolved Sept 1973 (sat Mar-Sep 1973)
POST_START <- 1990L  # Congress reopened March 1990
POST_END   <- 2021L  # 2022 cohort has only 23 legislators (incomplete)
YEARS_ALL  <- seq.int(1811L, 2026L)
MIN_N      <- 5L     # share undefined below 5 sitting members (04/17/20 rule)
HAC_LAGS   <- 5L
HALF_WINDOWS <- c(25L, 15L)  # window = [br - H, br + H - 1]
MIN_SIDE   <- 10L   # flag a test when either side has < 10 obs
MIN_EST    <- 3L    # below this on either side the break is not estimated
BASELINE   <- 1925L
FIXED_MMDD <- "07-01"
SUB_TIPOS  <- c("Suplente", "Suplentes")
TRIM       <- 0.15
MIN_SEG    <- 6L
M_CAP      <- 8L
N_BOOT     <- 499L
BLOCK_LEN  <- 8L    # ~two legislative terms
Z95        <- qnorm(0.975)
OUT_DIR <- file.path("output", "rnr2026")
FIG_DIR <- file.path("figures", "rnr2026")
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)
dir.create(FIG_DIR, recursive = TRUE, showWarnings = FALSE)

# ------------------------------------------------------------------- events
# !!! ALL DATES ARE PROVISIONAL -- to be verified by the authors against
# !!! primary sources. Ley 2.883 is most likely of February 1914 (earlier
# !!! drafts used 1912). type = "law" or "election" (first congressional
# !!! election plausibly affected; composition only changes at elections).
EVENTS <- data.table(
  short = c("1874 law", "1874 law", "1888 reform", "1888 reform",
            "1914 reform", "1914 reform", "1925 baseline",
            "1934 women municipal", "1934 women municipal",
            "1949 women national", "1949 women national",
            "1958 ballot", "1958 ballot", "1962 registration",
            "1962 registration", "1970 illiterate/18+",
            "1970 illiterate/18+"),
  event = c(
    rep("1874 electoral law (literacy presumed to meet income req.)", 2L),
    rep("1888 reform removing property qualification", 2L),
    rep("Ley 2.883 electoral reform, new registry (likely 1914; PROVISIONAL)",
        2L),
    "1925 salary reform / new constitution (baseline)",
    rep("1934 women's municipal vote (not national)", 2L),
    rep("1949 women's national suffrage (Ley 9.292)", 2L),
    rep("1958 single official ballot (Ley 12.889)", 2L),
    rep("1962 compulsory registration", 2L),
    rep("1970 illiterate and 18+ suffrage (Ley 17.284)", 2L)),
  type = c("law", "election", "law/election", "election", "law",
           "election", "law/election", "law", "next cong. election",
           "law", "election", "law", "election", "law", "election",
           "law", "election"),
  year = c(1874L, 1876L, 1888L, 1891L, 1914L, 1915L, 1925L, 1934L, 1937L,
           1949L, 1953L, 1958L, 1961L, 1962L, 1965L, 1970L, 1973L)
)

# ------------------------------------------------------------------- roster
deaccent <- \(s) {
  s <- ifelse(is.na(s), "NAN", as.character(s))  # Python str(nan) -> "NAN"
  s <- stri_trans_nfkd(s)
  s <- gsub("[^\x01-\x7F]", "", s, perl = TRUE)   # encode("ascii","ignore")
  trimws(toupper(s))
}
elite_set <- unique(deaccent(
  fread("data/processed/enduring_elite_FINAL.csv", encoding = "UTF-8")$surname
))
cong <- fread("data/processed/cong_df.csv", encoding = "UTF-8",
              colClasses = "character")
cong[, `:=`(s_yr = suppressWarnings(as.numeric(Start)),
            e_yr = suppressWarnings(as.numeric(End)))]
cong <- cong[!is.na(s_yr) & !is.na(e_yr)]
per <- tstrsplit(cong$Period, " a ", fixed = TRUE)
cong[, `:=`(s_date = as.IDate(per[[1L]], format = "%d-%m-%Y"),
            e_date = as.IDate(per[[2L]], format = "%d-%m-%Y"))]
stopifnot(!anyNA(cong$s_date), !anyNA(cong$e_date))
cong[, is_sub := Tipo %chin% SUB_TIPOS]
cong[, is_elite := deaccent(Pat) %chin% elite_set |
                   deaccent(Mat) %chin% elite_set]
message(sprintf("[A1] roster rows %d; substitutes %d (last Start %d)",
                nrow(cong), sum(cong$is_sub), max(cong[is_sub == TRUE]$s_yr)))

# ------------------------------------------------------------ series helpers
#' Elite share with the 04/17/20 rule: NA when fewer than MIN_N sitting.
share_or_na <- \(n_el, n) fifelse(n >= MIN_N, 100 * n_el / pmax(n, 1), NA_real_)

#' Annual counts and share. rule "interval": Start <= y <= End;
#' "fixed": sitting on 1 July of y (Period dates). keep: logical row filter.
annual_series <- function(keep, rule) {
  cnt <- vapply(YEARS_ALL, \(y) {
    on <- if (rule == "interval") {
      cong$s_yr <= y & cong$e_yr >= y
    } else {
      d0 <- as.IDate(sprintf("%d-%s", y, FIXED_MMDD))
      cong$s_date <= d0 & cong$e_date >= d0
    }
    m <- keep & on
    c(sum(m), sum(cong$is_elite[m]))
  }, numeric(2L))
  data.table(year = YEARS_ALL, n_sitting = cnt[1L, ], n_elite = cnt[2L, ],
             elite = share_or_na(cnt[2L, ], cnt[1L, ]))
}

#' One observation per legislature (members sharing a Period start date).
cohort_series <- function(keep) {
  cg <- cong[keep, .(n = .N, n_elite = sum(is_elite)), by = s_date]
  setorder(cg, s_date)
  cg[, `:=`(time = year(s_date) + (yday(s_date) - 1) / 365.25,
            elite = share_or_na(n_elite, n))]
  cg[!is.na(elite)]
}

fill_1926 <- \(dt) {
  o <- copy(dt)
  o[year == BASELINE, elite := o[year == BASELINE + 1L, elite]]
  o
}
pre_span  <- \(dt) dt[year >= PRE_START & year <= PRE_END & !is.na(elite)]
post_span <- \(dt) dt[year >= POST_START & year <= POST_END & !is.na(elite)]
nw_auto_lag <- \(n) as.integer(floor(4 * (n / 100)^(2 / 9)))

keep_all <- rep(TRUE, nrow(cong))
keep_nosub <- !cong$is_sub
# Sensitivity: also drop the 50 senate "Subrogante" rows (1837-1876).
keep_nosubrog <- keep_nosub & !(cong$Tipo %chin% "Subrogante")
ann <- list(
  primary       = annual_series(keep_all, "interval"),
  nosub         = annual_series(keep_nosub, "interval"),
  fixed         = annual_series(keep_all, "fixed"),
  fixed_nosub   = annual_series(keep_nosub, "fixed"),
  nosub_nosubrog = annual_series(keep_nosubrog, "interval")
)
ann$paper <- copy(ann$primary)[, elite := 100 * n_elite / pmax(n_sitting, 1)]
SERIES_LABEL <- c(
  primary = "All members, Start<=y<=End (primary)",
  nosub = "Titular (propietario) members only, Start<=y<=End",
  fixed = "All members sitting on 1 July",
  fixed_nosub = "Titular members only, sitting on 1 July",
  nosub_nosubrog = "Titular only, also without Subrogante, Start<=y<=End",
  paper = "Paper series (1925 coded as 0% elite)")
ann_long <- rbindlist(lapply(names(ann), \(k) ann[[k]][, series := k]))
fwrite(ann_long, file.path(OUT_DIR, "A1_annual_series_full.csv"))
for (k in names(ann)) ann[[k]][, series := NULL]
coh <- list(all = cohort_series(keep_all), nosub = cohort_series(keep_nosub))
message(sprintf("[A1] zero/NA years in 1834-1973 (primary): %s; (fixed): %s",
                paste(ann$primary[year %between% c(PRE_START, PRE_END) &
                                    is.na(elite)]$year, collapse = ","),
                paste(ann$fixed[year %between% c(PRE_START, PRE_END) &
                                  is.na(elite)]$year, collapse = ",")))

# --------------------------------------------------------------- ITS fitter
#' Segmented ITS level shift at `br` with HAC SEs.
#' @param dt data.table(year, elite) (year may be decimal for cohorts)
#' @param ctrl optional second break entered as extra level + slope terms
#' @return list with shift, se, p, lo, hi, n, n_pre, n_post, pre-trend
fit_its <- function(dt, br, ctrl = NA_integer_, lag = HAC_LAGS) {
  d <- copy(dt)
  d[, `:=`(t = year - br, post = as.numeric(year >= br))]
  d[, tpost := t * post]
  n_pre <- sum(d$post < 0.5); n_post <- sum(d$post > 0.5)
  out <- list(shift = NA_real_, se = NA_real_, p = NA_real_, lo = NA_real_,
              hi = NA_real_, n = nrow(d), n_pre = n_pre, n_post = n_post,
              pretrend = NA_real_, pretrend_p = NA_real_, int = NA_real_,
              lag = lag)
  if (n_pre < MIN_EST || n_post < MIN_EST) return(out)
  fml <- elite ~ t + post + tpost
  if (!is.na(ctrl)) {
    d[, post_c := as.numeric(year >= ctrl)]
    d[, tpost_c := (year - ctrl) * post_c]
    fml <- elite ~ t + post + tpost + post_c + tpost_c
  }
  m <- lm(fml, data = d)
  vc <- NeweyWest(m, lag = lag, prewhite = FALSE, adjust = FALSE)
  est <- unname(coef(m)["post"]); se <- sqrt(vc["post", "post"])
  tr_se <- sqrt(vc["t", "t"])
  out$shift <- est; out$se <- se; out$p <- 2 * pnorm(-abs(est / se))
  out$lo <- est - Z95 * se; out$hi <- est + Z95 * se
  out$pretrend <- unname(coef(m)["t"])
  out$pretrend_p <- 2 * pnorm(-abs(out$pretrend / tr_se))
  out$int <- unname(coef(m)["(Intercept)"])
  out
}

# ------------------------------- (A) reproduction of 05/16 (Python) outputs
# Integration note (2026-09-26): scripts 05/16 now use the shared n < 5 rule
# (_measure_helpers.annual_share), so data/processed/its_placebo_byyear.csv holds the
# corrected all-member series with 1925 as a gap. The check therefore compares
# against `primary` (NA years dropped). Before integration it compared the
# `paper` series (1925 coded 0), which reproduced the submitted output.
prim_8070 <- ann$primary[year >= 1880L & year <= 1970L & !is.na(elite)]
paper_8070 <- ann$paper[year >= 1880L & year <= 1970L]   # used by profile D below
chk <- rbindlist(lapply(1900:1950, \(b) {
  r <- fit_its(prim_8070, b)
  data.table(break_yr = b, r_shift = r$shift, r_se = r$se)
}))
py <- fread("data/processed/its_placebo_byyear.csv")
chk <- merge(chk, py[, .(break_yr = `break`, py_shift = shift, py_se = se)],
             by = "break_yr")
chk[, `:=`(abs_dev_shift = abs(r_shift - py_shift),
           abs_dev_se = abs(r_se - py_se))]
stopifnot(nrow(chk) == 51L)          # guard: an empty or partial merge would pass max_dev
max_dev <- max(chk$abs_dev_shift, chk$abs_dev_se)
fwrite(chk, file.path(OUT_DIR, "A1_replication_check.csv"))
message(sprintf("[A1] R vs Python (16) over 1900-1950: max |dev| = %.2e",
                max_dev))
stopifnot(max_dev < 1e-6)
# The `paper` series (1925 coded 0) must still reproduce the SUBMITTED placebo
# values (online_appendix / 05_break1925.tex, 2 dp): 1922 -12.98, 1924 -13.19,
# 1925 -13.32.
pub_chk <- rbindlist(lapply(c(1922L, 1924L, 1925L), \(b) {
  data.table(break_yr = b, shift = fit_its(paper_8070, b)$shift)
}))
pub_chk[, submitted := c(-12.98, -13.19, -13.32)]
message(sprintf("[A1] paper series vs submitted: %s",
                paste(sprintf("%d %.2f (%.2f)", pub_chk$break_yr, pub_chk$shift,
                              pub_chk$submitted), collapse = "; ")))
stopifnot(all(abs(round(pub_chk$shift, 2) - pub_chk$submitted) < 1e-9))

# ------------------------- (B) headline 1925 shift across roster constructions
win_list <- list(c(1880L, 1970L), c(1890L, 1960L), c(1900L, 1955L))
k <- 0L
annual_specs <- list(
  list("Start<=y<=End", "all", "primary"),
  list("Start<=y<=End", "titular only", "nosub"),
  list("1 July roster", "all", "fixed"),
  list("1 July roster", "titular only", "fixed_nosub"))
head_rows <- vector("list", 3L * (length(annual_specs) * 2L + 1L + 2L))
for (w in win_list) {
  sel_w <- \(dt) dt[year >= w[1L] & year <= w[2L] & !is.na(elite)]
  mk <- \(roster, members, treat, r) data.table(
    window = paste(w, collapse = "-"), roster = roster, members = members,
    treatment_1925 = treat, n = r$n, shift = r$shift, se = r$se, p = r$p,
    lo = r$lo, hi = r$hi, pretrend = r$pretrend, pretrend_p = r$pretrend_p,
    hac_lag = r$lag)
  for (sp in annual_specs) {
    base <- ann[[sp[[3L]]]]
    k <- k + 1L
    head_rows[[k]] <- mk(sp[[1L]], sp[[2L]], "gap",
                         fit_its(sel_w(base), BASELINE))
    k <- k + 1L
    head_rows[[k]] <- mk(sp[[1L]], sp[[2L]], "1926 roster assigned to 1925",
                         fit_its(sel_w(fill_1926(base)), BASELINE))
  }
  k <- k + 1L
  head_rows[[k]] <- mk("Start<=y<=End", "all", "coded 0 (published 05/16)",
                       fit_its(sel_w(ann$paper), BASELINE))
  for (cm in names(coh)) {
    cd <- coh[[cm]][time >= w[1L] & time < w[2L] + 1,
                    .(year = time, elite)]
    k <- k + 1L
    head_rows[[k]] <- mk("one obs. per legislature",
                         ifelse(cm == "all", "all", "titular only"),
                         "n/a (no 1925 legislature)",
                         fit_its(cd, BASELINE, lag = nw_auto_lag(nrow(cd))))
  }
}
headline <- rbindlist(head_rows)
fwrite(headline, file.path(OUT_DIR, "A1_headline_1925_roster_sensitivity.csv"))

# ------------------------------------------- (C) legislature-to-legislature
# Balmaceda's wartime Congress (15 Apr - 18 Aug 1891) is irregular: it is kept
# as a row but excluded from the step computation, so the 1891 step compares
# the last regular Congress (1888) with the post-war Congress (Nov 1891).
IRREGULAR_COHORTS <- as.IDate("1891-04-15")
cd_one <- \(cg, tag) {
  o <- cg[year(s_date) >= PRE_START, .(s_date, n, elite)]
  o[, irregular := s_date %in% IRREGULAR_COHORTS]
  o[irregular == FALSE, `:=`(prev_date = shift(s_date),
                             change = elite - shift(elite))]
  o[, crosses_gap := !is.na(prev_date) & year(prev_date) <= PRE_END &
      year(s_date) >= POST_START]
  setnames(o, c("n", "elite", "change", "prev_date"),
           paste0(c("n_", "share_", "change_", "prev_date_"), tag))
  o
}
cdiff <- merge(cd_one(coh$all, "all"), cd_one(coh$nosub, "nosub"),
               by = c("s_date", "irregular", "crosses_gap"), all = TRUE)
cdiff <- cdiff[year(s_date) >= PRE_START & year(s_date) <= POST_END]
setorder(cdiff, s_date)
fwrite(cdiff, file.path(OUT_DIR, "A1_cohort_differences.csv"))

# ----------------------------------- (D) why the ITS shift exceeds the step
# Accounting identity (holds by construction, checked below):
#   shift = [last pre obs - pre line at br] + [first post obs - last pre obs]
#         + [post line at br - first post obs]
decomp_one <- function(v, br, lo, hi) {
  dt <- ann[[v]][year >= lo & year <= hi & !is.na(elite)]
  r <- fit_its(dt, br)
  pre_fit <- r$int; post_fit <- r$int + r$shift
  last_pre <- dt[year < br][.N]; first_post <- dt[year >= br][1L]
  m <- lm(elite ~ year, data = dt[year < br])
  res <- dt[year < br][, resid := elite - fitted(m)]
  data.table(
    series = v, break_yr = br, window = sprintf("%d-%d", lo, hi),
    its_shift = r$shift, pre_line_at_break = pre_fit,
    post_line_at_break = post_fit, last_pre_year = last_pre$year,
    last_pre_obs = last_pre$elite, first_post_year = first_post$year,
    first_post_obs = first_post$elite,
    c_pre_overshoot = last_pre$elite - pre_fit,
    c_observed_step = first_post$elite - last_pre$elite,
    c_post_segment = post_fit - first_post$elite,
    mean_resid_pre_last10 = mean(tail(res$resid, 10L)),
    mean_resid_1892_1908 = if (lo <= 1892L && br > 1908L)
      mean(res[year %between% c(1892L, 1908L)]$resid) else NA_real_)
}
decomp_specs <- CJ(series = c("primary", "nosub"), k = 1:5)
DECOMP_WIN <- list(c(1925L, 1880L, 1970L), c(1925L, 1890L, 1960L),
                   c(1925L, 1900L, 1955L), c(1876L, 1851L, 1900L),
                   c(1965L, 1940L, 1973L))
decomp <- rbindlist(lapply(seq_len(nrow(decomp_specs)), \(i) {
  w <- DECOMP_WIN[[decomp_specs$k[i]]]
  decomp_one(decomp_specs$series[i], w[1L], w[2L], w[3L])
}))
stopifnot(all(abs(decomp$its_shift - (decomp$c_pre_overshoot +
  decomp$c_observed_step + decomp$c_post_segment)) < 1e-8))
fwrite(decomp, file.path(OUT_DIR, "A1_its_decomposition.csv"))

# ------------------------------------------------------ (E) event tests
year_window <- \(dt, br, half) dt[year >= br - half & year <= br + half - 1L]

#' Net-of-1925 variant. Method "terms": add 1925 level + slope terms when
#' 1925 lies inside the window with >= 5 obs each side; method "cut":
#' otherwise truncate the window at 1925.
fit_net_1925 <- function(w, br) {
  na <- list(shift = NA_real_, se = NA_real_, p = NA_real_, lo = NA_real_,
             hi = NA_real_, n = NA_integer_, how = "n/a")
  if (br == BASELINE || !(BASELINE > min(w$year) &&
                          BASELINE <= max(w$year))) return(na)
  n_b <- sum(w$year < BASELINE); n_a <- sum(w$year >= BASELINE)
  if (n_b >= 5L && n_a >= 5L) {
    r <- fit_its(w, br, ctrl = BASELINE); r$how <- "terms"
  } else {
    w2 <- if (br > BASELINE) w[year >= BASELINE] else w[year < BASELINE]
    r <- fit_its(w2, br); r$how <- "cut"
  }
  r
}

other_events_in <- \(lo, hi, own) {
  o <- unique(EVENTS[short != own & year >= lo & year <= hi]$year)
  if (length(o) == 0L) "" else paste(sort(o), collapse = ";")
}

ev_series <- c("primary", "nosub", "fixed", "fixed_nosub", "nosub_nosubrog",
               "paper")
grid <- CJ(row = seq_len(nrow(EVENTS)), half = HALF_WINDOWS,
           series = ev_series)
res <- rbindlist(lapply(seq_len(nrow(grid)), \(i) {
  ev <- EVENTS[grid$row[i]]; h <- grid$half[i]
  w <- year_window(pre_span(ann[[grid$series[i]]]), ev$year, h)
  r <- fit_its(w, ev$year)
  rn <- fit_net_1925(w, ev$year)
  flags <- c(
    if (ev$year + h - 1L > PRE_END) "post window truncated at 1973 gap",
    if (ev$year - h < PRE_START) "pre window truncated at 1834",
    if (min(r$n_pre, r$n_post) < MIN_SIDE) "SHORT side (<10 obs)",
    if (is.na(r$shift)) "NOT ESTIMABLE (<3 post obs)")
  data.table(
    series = grid$series[i], event = ev$event, short = ev$short,
    type = ev$type, test_year = ev$year, half_window = h,
    win_start = min(w$year), win_end = max(w$year), n = r$n,
    n_pre = r$n_pre, n_post = r$n_post, shift = r$shift, se = r$se,
    p = r$p, ci_lo = r$lo, ci_hi = r$hi,
    contains_1925 = ev$year != BASELINE & BASELINE >= min(w$year) &
      BASELINE <= max(w$year),
    other_events_in_window = other_events_in(min(w$year), max(w$year),
                                             ev$short),
    net1925_shift = rn$shift, net1925_se = rn$se, net1925_p = rn$p,
    net1925_lo = rn$lo, net1925_hi = rn$hi, net1925_n = rn$n,
    net1925_method = rn$how, flags = paste(flags, collapse = "; "))
}))
# Gap-spanning variant for the 1970 event (primary series only, flagged).
gap_rows <- rbindlist(lapply(c(1970L, 1973L), \(b) {
  s <- rbind(pre_span(ann$primary), post_span(ann$primary))
  w <- rbind(s[year >= b - 25L & year < b], head(s[year >= b], 25L))
  r <- fit_its(w, b)
  data.table(
    series = "primary", event = EVENTS[year == b]$event,
    short = "1970 illiterate/18+",
    type = paste(EVENTS[year == b]$type, "(GAP-SPANNING)"), test_year = b,
    half_window = 25L, win_start = min(w$year), win_end = max(w$year),
    n = r$n, n_pre = r$n_pre, n_post = r$n_post, shift = r$shift,
    se = r$se, p = r$p, ci_lo = r$lo, ci_hi = r$hi, contains_1925 = FALSE,
    other_events_in_window = "", net1925_shift = NA_real_,
    net1925_se = NA_real_, net1925_p = NA_real_, net1925_lo = NA_real_,
    net1925_hi = NA_real_, net1925_n = NA_integer_, net1925_method = "n/a",
    flags = paste("CROSSES 1973-1990 gap; post = 1973 + 1990-onward;",
                  "confounded with dictatorship/binomial system"))
}))
res <- rbind(res, gap_rows)
# Bonferroni within each series over its estimable, non-gap-spanning tests
# (both windows). Tests are dependent (overlapping windows): conservative.
res[, n_tests_family := sum(!is.na(p) & !grepl("GAP", type)), by = series]
res[, p_bonferroni := fifelse(grepl("GAP", type), NA_real_,
                              pmin(1, p * n_tests_family))]
res[, series := factor(series, levels = ev_series)]
setorder(res, series, -half_window, test_year, type)
res[, series := as.character(series)]
fwrite(res, file.path(OUT_DIR, "A1_event_tests.csv"))

# ------------------------ (E2) one metric per event: legislature step + ITS
# Step = elite share of the first regular legislature starting in or after
# the event's election year minus that of the previous regular legislature.
# The 1888 row is dropped (its affected election is the 1891 row).
cmp_events <- EVENTS[type != "law" & year != 1888L]
step_at <- \(cg, y) {
  rc <- cg[!(s_date %in% IRREGULAR_COHORTS) & year(s_date) >= PRE_START]
  i <- which(year(rc$s_date) >= y)[1L]
  if (is.na(i) || i < 2L || year(rc$s_date[i]) > PRE_END) {
    return(list(from = as.IDate(NA), to = as.IDate(NA), step = NA_real_))
  }
  list(from = rc$s_date[i - 1L], to = rc$s_date[i],
       step = rc$elite[i] - rc$elite[i - 1L])
}
its_cell <- \(v, y, h) {
  r <- res[series == v & test_year == y & half_window == h &
             !grepl("GAP", type)]
  list(b = r$shift, p = r$p, short = min(r$n_pre, r$n_post) < MIN_SIDE)
}
cmp <- rbindlist(lapply(seq_len(nrow(cmp_events)), \(i) {
  ev <- cmp_events[i]
  sa <- step_at(coh$all, ev$year); sn <- step_at(coh$nosub, ev$year)
  o <- data.table(event = ev$short, test_year = ev$year,
                  from_legislature = sa$from, to_legislature = sa$to,
                  step_all = sa$step, step_titular = sn$step)
  for (v in c("primary", "nosub", "fixed_nosub")) {
    for (h in HALF_WINDOWS) {
      cc <- its_cell(v, ev$year, h)
      set(o, j = sprintf("its%d_%s", h, v), value = cc$b)
      set(o, j = sprintf("its%d_%s_p", h, v), value = cc$p)
      set(o, j = sprintf("its%d_%s_short", h, v), value = cc$short)
    }
  }
  o
}))
fwrite(cmp, file.path(OUT_DIR, "A1_event_comparison.csv"))

# ----------------------------------------------- (F) break-year profiles
#' Level-shift profile across candidate break years ("fixed" window or
#' "moving" [c-25, c+24] cut at the data limits).
profile_breaks <- function(dt, cands, mode, label, series) {
  rbindlist(lapply(cands, \(b) {
    w <- if (mode == "fixed") dt else year_window(dt, b, 25L)
    r <- fit_its(w, b)
    data.table(series = series, profile = label, break_yr = b,
               shift = r$shift, se = r$se, p = r$p, n = r$n,
               n_pre = r$n_pre, n_post = r$n_post)
  }))
}
cand_full <- seq.int(PRE_START + MIN_SIDE, PRE_END - MIN_SIDE + 1L)
prof <- rbindlist(lapply(c("primary", "nosub"), \(v) {
  s <- pre_span(ann[[v]])
  rbind(
    profile_breaks(s, cand_full, "fixed", "A. Fixed window 1834-1973", v),
    profile_breaks(s, cand_full, "moving",
                   "B. Moving window, 25 years each side", v),
    profile_breaks(s[year >= 1880L & year <= 1970L], 1890:1961, "fixed",
                   "C. Fixed window 1880-1970 (paper's frame)", v))
}))
prof <- rbind(prof, profile_breaks(
  paper_8070, 1890:1961, "fixed",
  "D. Fixed window 1880-1970, paper series (1925 coded 0)", "paper"))
prof[, abs_t := abs(shift / se)]
fwrite(prof, file.path(OUT_DIR, "A1_break_profile.csv"))

# Distinct episodes: most extreme (same sign) within +/-5 years, |t| >= 2.
prof[, is_episode := {
  v <- shift; tt <- abs_t; yr <- break_yr
  vapply(seq_along(v), \(i) {
    nb <- abs(yr - yr[i]) <= 5L & !is.na(v)
    if (is.na(v[i]) || tt[i] < 2) return(FALSE)
    if (v[i] < 0) v[i] <= min(v[nb]) else v[i] >= max(v[nb])
  }, logical(1L))
}, by = .(series, profile)]
episodes <- prof[is_episode == TRUE][order(series, profile, shift)]
fwrite(episodes, file.path(OUT_DIR, "A1_break_profile_episodes.csv"))

# Flatness of the profile around the minimum: candidate years whose shift is
# within 1 SE (of the minimum) of the minimum, and the 1915-1930 range.
flat <- prof[, {
  i <- which.min(shift)
  within <- break_yr[!is.na(shift) & shift <= shift[i] + se[i]]
  zone <- .SD[break_yr %between% c(1915L, 1930L)]
  .(argmin = break_yr[i], min_shift = shift[i], se_at_min = se[i],
    within_1se_first = min(within), within_1se_last = max(within),
    within_1se_n = length(within),
    range_1918_1927_min = min(zone[break_yr %between% c(1918L, 1927L)]$shift),
    range_1918_1927_max = max(zone[break_yr %between% c(1918L, 1927L)]$shift))
}, by = .(series, profile)]
fwrite(flat, file.path(OUT_DIR, "A1_break_profile_flatness.csv"))

# ------------------------------------------------------------ (G) Bai-Perron
#' Segment RSS for every (i, j), i <= j, via cumulative sums (O(1) each).
segment_rss <- function(y, tt, model) {
  n <- length(y)
  cs <- \(v) c(0, cumsum(v))
  sy <- cs(y); syy <- cs(y^2); st <- cs(tt); stt <- cs(tt^2); sty <- cs(tt * y)
  rss <- matrix(NA_real_, n, n)
  for (i in seq_len(n)) {
    j <- seq.int(i, n); m <- j - i + 1
    s_y <- sy[j + 1] - sy[i]; s_yy <- syy[j + 1] - syy[i]
    yc <- s_yy - s_y^2 / m
    if (model == "level") {
      rss[i, j] <- pmax(yc, 0)
    } else {
      s_t <- st[j + 1] - st[i]; s_tt <- stt[j + 1] - stt[i]
      s_ty <- sty[j + 1] - sty[i]
      sxx <- s_tt - s_t^2 / m; sxy <- s_ty - s_t * s_y / m
      val <- yc - ifelse(sxx > 1e-10, sxy^2 / sxx, 0)
      rss[i, j] <- pmax(val, 0)
    }
  }
  rss
}

#' Exact optimal partitions for 0..m_max breaks (Bai & Perron 2003 DP).
#' break index = last observation of a regime.
optimal_partitions <- function(rss, h, m_max) {
  n <- nrow(rss)
  cost <- matrix(Inf, m_max + 1L, n); arg <- matrix(NA_integer_, m_max + 1L, n)
  cost[1L, h:n] <- rss[1L, h:n]
  if (m_max >= 1L) {
    for (s in 2:(m_max + 1L)) {
      for (j in seq.int(s * h, n)) {
        i <- seq.int((s - 1L) * h, j - h)
        v <- cost[s - 1L, i] + rss[cbind(i + 1L, j)]
        kk <- which.min(v); cost[s, j] <- v[kk]; arg[s, j] <- i[kk]
      }
    }
  }
  brk <- vector("list", m_max + 1L)
  for (m in 0:m_max) {
    b <- integer(m); j <- n
    for (s in seq_len(m)) {
      j <- arg[m + 2L - s, j]; b[m + 1L - s] <- j
    }
    brk[[m + 1L]] <- b
  }
  list(rss = cost[, n], brk = brk)
}

fitted_partition <- function(y, tt, brk, model) {
  ends <- c(brk, length(y)); starts <- c(1L, brk + 1L)
  f <- numeric(length(y))
  for (s in seq_along(ends)) {
    ix <- seq.int(starts[s], ends[s])
    f[ix] <- if (model == "level") mean(y[ix]) else
      fitted(lm(y[ix] ~ tt[ix]))
  }
  f
}

block_index <- \(n, l) {
  n_blk <- ceiling(n / l)
  st <- sample.int(n - l + 1L, n_blk, replace = TRUE)
  as.vector(outer(0:(l - 1L), st, `+`))[seq_len(n)]
}

#' Bai-Perron on one sample: BIC and LWZ selection; block-bootstrap intervals
#' for the BIC-selected m (m fixed in every draw; breaks matched by order).
run_bai_perron <- function(dt, series, label, model, h_min = NA_integer_) {
  y <- dt$elite; yr <- dt$year; n <- length(y)
  tt <- (yr - mean(yr)) / 10
  q <- if (model == "level") 1L else 2L
  h <- if (is.na(h_min)) max(floor(TRIM * n), MIN_SEG) else h_min
  m_max <- min(floor(n / h) - 1L, M_CAP)
  op <- optimal_partitions(segment_rss(y, tt, model), h, m_max)
  m_vec <- 0:m_max
  loglik <- -0.5 * n * (log(op$rss) + 1 - log(n) + log(2 * pi))
  bic <- -2 * loglik + (q + 1L) * (m_vec + 1L) * log(n)
  p_star <- (m_vec + 1L) * q + m_vec          # Bai & Perron (2003), p = 0
  lwz <- log(op$rss / (n - p_star)) + (p_star / n) * 0.299 * log(n)^2.1
  m_hat <- m_vec[which.min(bic)]; m_lwz <- m_vec[which.min(lwz)]
  by_m <- data.table(
    series = series, sample = label, model = model, n = n, h = h,
    m_max = m_max, m = m_vec, rss = op$rss, bic = bic, lwz = lwz,
    selected_bic = m_vec == m_hat, selected_lwz = m_vec == m_lwz,
    new_regime_starts = vapply(op$brk, \(b) paste(yr[b + 1L],
                                                  collapse = ";"), ""))
  brk_tab <- NULL
  b_hat <- op$brk[[m_hat + 1L]]
  f <- fitted_partition(y, tt, b_hat, model)
  if (m_hat > 0L) {
    e <- y - f
    boot <- matrix(NA_real_, N_BOOT, m_hat)
    for (b in seq_len(N_BOOT)) {
      ys <- f + e[block_index(n, BLOCK_LEN)]
      opb <- optimal_partitions(segment_rss(ys, tt, model), h, m_hat)
      boot[b, ] <- yr[opb$brk[[m_hat + 1L]] + 1L]
    }
    brk_tab <- data.table(
      series = series, sample = label, model = model, m_bic = m_hat,
      m_lwz = m_lwz, m_max = m_max, break_no = seq_len(m_hat),
      new_regime_starts = yr[b_hat + 1L],
      boot_lo95 = apply(boot, 2L, quantile, 0.025, type = 1L),
      boot_hi95 = apply(boot, 2L, quantile, 0.975, type = 1L),
      boot_share_within2 = colMeans(abs(sweep(boot, 2L,
                                              yr[b_hat + 1L])) <= 2L))
    brk_tab[, events_in_ci := vapply(seq_len(.N), \(i) {
      ev <- EVENTS[year >= boot_lo95[i] & year <= boot_hi95[i]]
      if (nrow(ev) == 0L) "" else paste(unique(sprintf("%d (%s)", ev$year,
                                                       ev$short)),
                                        collapse = "; ")
    }, "")]
    brk_tab[, nearest_event := vapply(new_regime_starts, \(x) {
      if (x > PRE_END) return("none (no listed event after 1973)")
      d <- abs(EVENTS$year - x); i <- which.min(d)
      sprintf("%d %s (%+d yrs)", EVENTS$year[i], EVENTS$short[i],
              x - EVENTS$year[i])
    }, "")]
  }
  fit_dt <- data.table(series = series, sample = label, model = model,
                       year = yr, elite = y, fitted = f,
                       regime = findInterval(seq_len(n), b_hat + 1L))
  list(by_m = by_m, breaks = brk_tab, fit = fit_dt, rss = op$rss,
       brk = op$brk, h = h)
}

bp_specs <- list(
  list(s = "primary", lab = "1834-1973", dt = pre_span(ann$primary)),
  list(s = "primary", lab = "1880-1970",
       dt = pre_span(ann$primary)[year >= 1880L & year <= 1970L]),
  list(s = "primary", lab = "1990-2021", dt = post_span(ann$primary)),
  list(s = "primary", lab = "1834-1973, min. regime 8 yrs",
       dt = pre_span(ann$primary), h = 8L),
  list(s = "nosub", lab = "1834-1973", dt = pre_span(ann$nosub)),
  list(s = "nosub", lab = "1880-1970",
       dt = pre_span(ann$nosub)[year >= 1880L & year <= 1970L]),
  list(s = "nosub", lab = "1834-1973, min. regime 8 yrs",
       dt = pre_span(ann$nosub), h = 8L),
  list(s = "fixed_nosub", lab = "1834-1973", dt = pre_span(ann$fixed_nosub))
)
bp_runs <- vector("list", length(bp_specs) * 2L)
ix <- 0L
for (sp in bp_specs) {
  for (md in c("trend", "level")) {
    ix <- ix + 1L
    h_sp <- if (is.null(sp$h)) NA_integer_ else sp$h
    bp_runs[[ix]] <- run_bai_perron(sp$dt, sp$s, sp$lab, md, h_sp)
  }
}
bp_by_m <- rbindlist(lapply(bp_runs, `[[`, "by_m"))
bp_breaks <- rbindlist(lapply(bp_runs, `[[`, "breaks"))
bp_fit <- rbindlist(lapply(bp_runs, `[[`, "fit"))
fwrite(bp_by_m, file.path(OUT_DIR, "A1_bai_perron_bic.csv"))
fwrite(bp_breaks, file.path(OUT_DIR, "A1_bai_perron_breaks.csv"))
fwrite(bp_fit, file.path(OUT_DIR, "A1_bai_perron_fitted.csv"))

# Brute-force check of the DP for m = 1, 2 (primary 1834-1973, both models):
# enumerate every admissible partition, fit each segment by OLS (qr).
seg_rss_ols <- \(y, tt, model) {
  x <- if (model == "level") matrix(1, length(y), 1L) else cbind(1, tt)
  sum(.lm.fit(x, y)$residuals^2)
}
brute <- rbindlist(lapply(c("trend", "level"), \(md) {
  dt <- pre_span(ann$primary); y <- dt$elite; yr <- dt$year; n <- length(y)
  tt <- (yr - mean(yr)) / 10; h <- max(floor(TRIM * n), MIN_SEG)
  run <- bp_runs[[which(vapply(bp_runs, \(r) r$by_m$series[1L] == "primary" &&
                                 r$by_m$sample[1L] == "1834-1973" &&
                                 r$by_m$model[1L] == md, logical(1L)))]]
  b1 <- seq.int(h, n - h)
  r1 <- vapply(b1, \(b) seg_rss_ols(y[1:b], tt[1:b], md) +
                 seg_rss_ols(y[(b + 1):n], tt[(b + 1):n], md), numeric(1L))
  pairs <- CJ(b1 = seq.int(h, n - 2L * h), b2 = seq.int(2L * h, n - h))
  pairs <- pairs[b2 - b1 >= h]
  r2 <- vapply(seq_len(nrow(pairs)), \(i) {
    a <- pairs$b1[i]; b <- pairs$b2[i]
    seg_rss_ols(y[1:a], tt[1:a], md) +
      seg_rss_ols(y[(a + 1):b], tt[(a + 1):b], md) +
      seg_rss_ols(y[(b + 1):n], tt[(b + 1):n], md)
  }, numeric(1L))
  i2 <- which.min(r2)
  data.table(
    model = md, m = 1:2,
    brute_rss = c(min(r1), min(r2)), dp_rss = run$rss[2:3],
    brute_starts = c(as.character(yr[b1[which.min(r1)] + 1L]),
                     paste(yr[c(pairs$b1[i2], pairs$b2[i2]) + 1L],
                           collapse = ";")),
    dp_starts = c(paste(yr[run$brk[[2L]] + 1L], collapse = ";"),
                  paste(yr[run$brk[[3L]] + 1L], collapse = ";")),
    n_partitions = c(length(r1), length(r2)))
}))
brute[, `:=`(abs_rss_diff = abs(brute_rss - dp_rss),
             same_dates = brute_starts == dp_starts)]
fwrite(brute, file.path(OUT_DIR, "A1_bp_bruteforce_check.csv"))
stopifnot(all(brute$abs_rss_diff < 1e-6), all(brute$same_dates))

# ------------------------------------------------------------- LaTeX tables
star <- \(p) fifelse(is.na(p), "", fifelse(p < 0.01, "***",
                     fifelse(p < 0.05, "**", fifelse(p < 0.10, "*", ""))))
mth <- \(x, d = 2L) fifelse(is.na(x), "--",               # math-mode minus
                            sprintf(paste0("$%.", d, "f$"), x))
est <- \(b, p) fifelse(is.na(b), "--", paste0(mth(b), star(p)))
ci  <- \(lo, hi) fifelse(is.na(lo), "",
                         sprintf("[%s, %s]", mth(lo, 1L), mth(hi, 1L)))
# Markers as \textsuperscript (never adjacent math shifts, which TeX would
# read as display math): a = side < 10 obs; b = post window cut at 1973;
# c = net of 1925 by added 1925 terms; d = net of 1925 by cutting at 1925.
sup <- \(x) if (length(x) == 0L) "" else
  sprintf("\\textsuperscript{%s}", paste(x, collapse = ","))
mark <- \(r) sup(c(
  if (min(r$n_pre, r$n_post) < MIN_SIDE) "a",
  if (r$test_year + r$half_window - 1L > PRE_END) "b"))
net_mark <- \(how) fifelse(how == "terms", sup("c"),
                           fifelse(how == "cut", sup("d"), ""))

event_table <- function(v, file) {
  r <- res[series == v]
  w25 <- r[half_window == 25L & !grepl("GAP", type)]
  w15 <- r[half_window == 15L & !grepl("GAP", type)]
  head <- c("\\begin{tabular}{llcrcrc}", "\\toprule",
            paste0(" & & \\multicolumn{2}{c}{Window $\\pm$25} & ",
                   "\\multicolumn{2}{c}{Window $\\pm$15} & Net of 1925 \\\\"),
            "\\cmidrule(lr){3-4} \\cmidrule(lr){5-6} \\cmidrule(lr){7-7}",
            paste0("Event & Test year & Level shift & $N$ & ",
                   "Level shift & $N$ & ($\\pm$25) \\\\"),
            "\\midrule")
  body <- unlist(lapply(seq_len(nrow(EVENTS)), \(i) {
    a <- w25[test_year == EVENTS$year[i]]
    b <- w15[test_year == EVENTS$year[i]]
    c(sprintf("%s & %d (%s) & %s%s & %d & %s%s & %d & %s%s \\\\",
              EVENTS$short[i], EVENTS$year[i], EVENTS$type[i],
              est(a$shift, a$p), mark(a), a$n, est(b$shift, b$p), mark(b),
              b$n, est(a$net1925_shift, a$net1925_p),
              net_mark(a$net1925_method)),
      sprintf(" & & %s & & %s & & %s \\\\", ci(a$ci_lo, a$ci_hi),
              ci(b$ci_lo, b$ci_hi), ci(a$net1925_lo, a$net1925_hi)))
  }))
  extra <- character(0)
  if (v == "primary") {
    pa <- res[series == "paper" & test_year == BASELINE & half_window == 25L]
    pb <- res[series == "paper" & test_year == BASELINE & half_window == 15L]
    g <- r[grepl("GAP", type)]
    extra <- c(
      "\\midrule",
      sprintf("1925, 1925 coded as 0\\%% elite & %d & %s & %d & %s & %d & \\\\",
              BASELINE, est(pa$shift, pa$p), pa$n, est(pb$shift, pb$p), pb$n),
      sprintf(" & & %s & & %s & & \\\\", ci(pa$ci_lo, pa$ci_hi),
              ci(pb$ci_lo, pb$ci_hi)),
      "\\midrule",
      paste0("\\multicolumn{7}{l}{\\textit{Gap-spanning ",
             "(post = 1973 and 1990 onward)}} \\\\"),
      unlist(lapply(seq_len(nrow(g)), \(i) c(
        sprintf("%s & %d (%s) & %s & %d & & & \\\\", g$short[i],
                g$test_year[i], sub(" \\(GAP-SPANNING\\)", "", g$type[i]),
                est(g$shift[i], g$p[i]), g$n[i]),
        sprintf(" & & %s & & & & \\\\", ci(g$ci_lo[i], g$ci_hi[i]))))))
  }
  writeLines(c(head, body, extra, "\\bottomrule", "\\end{tabular}"),
             file.path(OUT_DIR, file))
}
event_table("primary", "A1_event_tests.tex")
event_table("nosub", "A1_event_tests_nosub.tex")

sel <- bp_by_m[selected_bic == TRUE]
tex2_body <- vapply(seq_len(nrow(sel)), \(i) {
  bt <- bp_breaks[series == sel$series[i] & sample == sel$sample[i] &
                    model == sel$model[i]]
  txt <- if (nrow(bt) == 0L) "none" else paste(
    sprintf("%d [%d, %d]", bt$new_regime_starts, bt$boot_lo95,
            bt$boot_hi95), collapse = "; ")
  lwz_m <- bp_by_m[series == sel$series[i] & sample == sel$sample[i] &
                     model == sel$model[i] & selected_lwz == TRUE]$m
  sprintf("%s & %s & %s & %d & %d & %d%s & %d & %s \\\\",
          c(primary = "All members", nosub = "Titular only",
            fixed_nosub = "Titular, 1 July")[sel$series[i]],
          sel$sample[i],
          ifelse(sel$model[i] == "trend", "Level + trend", "Level only"),
          sel$n[i], sel$h[i], sel$m[i],
          ifelse(sel$m[i] == sel$m_max[i], "\\textsuperscript{\\dag}", ""),
          lwz_m, txt)
}, "")
writeLines(c("\\begin{tabular}{lllccccl}", "\\toprule",
             paste0("Series & Sample & Regime model & $N$ & Min.\\ regime & ",
                    "$m$ (BIC) & $m$ (LWZ) & New regime starts ",
                    "[95\\% bootstrap interval] \\\\"), "\\midrule",
             tex2_body, "\\bottomrule", "\\end{tabular}"),
           file.path(OUT_DIR, "A1_bai_perron.tex"))

hl <- headline[window == "1880-1970"]
writeLines(c(
  "\\begin{tabular}{lllcc}", "\\toprule",
  paste0("Roster construction & Members & Treatment of 1925 & ",
         "1925 level shift & $N$ \\\\"), "\\midrule",
  vapply(seq_len(nrow(hl)), \(i) sprintf(
    "%s & %s & %s & %s %s & %d \\\\",
    gsub("<=", "$\\\\leq$", hl$roster[i]), hl$members[i],
    hl$treatment_1925[i], est(hl$shift[i], hl$p[i]),
    ci(hl$lo[i], hl$hi[i]), hl$n[i]), ""),
  "\\bottomrule", "\\end{tabular}"),
  file.path(OUT_DIR, "A1_headline_1925_roster_sensitivity.tex"))

# Union of the 10 largest drops on each roster (irregular April 1891 Congress
# excluded from steps; changes across the 1973-90 gap excluded), ranked per
# roster, in chronological order.
cd_ok <- cdiff[irregular == FALSE & crosses_gap == FALSE &
                 !is.na(change_all)]
cd_ok[, `:=`(rank_all = frank(change_all, ties.method = "min"),
             rank_titular = frank(change_nosub, ties.method = "min"))]
top_cd <- cd_ok[rank_all <= 10L | rank_titular <= 10L][order(s_date)]
fwrite(top_cd, file.path(OUT_DIR, "A1_cohort_differences_top10.csv"))
writeLines(c(
  "\\begin{tabular}{llcccccc}", "\\toprule",
  paste0(" & & \\multicolumn{3}{c}{All members} & ",
         "\\multicolumn{3}{c}{Titular members only} \\\\"),
  "\\cmidrule(lr){3-5} \\cmidrule(lr){6-8}",
  paste0("From & To & Share & Change & Rank & Share & Change & Rank \\\\"),
  "\\midrule",
  vapply(seq_len(nrow(top_cd)), \(i) sprintf(
    "%s & %s & %.1f & %s & %d & %.1f & %s & %d \\\\",
    format(top_cd$prev_date_all[i], "%Y-%m"),
    format(top_cd$s_date[i], "%Y-%m"), top_cd$share_all[i],
    mth(top_cd$change_all[i], 1L), top_cd$rank_all[i],
    top_cd$share_nosub[i], mth(top_cd$change_nosub[i], 1L),
    top_cd$rank_titular[i]), ""),
  "\\bottomrule", "\\end{tabular}"),
  file.path(OUT_DIR, "A1_cohort_differences_top10.tex"))

# Candidate event table: one metric (legislature step) with the ITS
# alongside; ITS cells with a side < 10 obs are suppressed ("--") because
# their HAC SEs are implausibly small (e.g. 1965, 1 July, +/-15: SE 0.32).
its_tex <- \(b, p, short) fifelse(is.na(b) | short, "--",
                                  paste0(mth(b), star(p)))
writeLines(c(
  "\\begin{tabular}{llcccccc}", "\\toprule",
  paste0(" & & \\multicolumn{2}{c}{Legislature step} & ",
         "\\multicolumn{3}{c}{ITS level shift ($\\pm$25)} \\\\"),
  "\\cmidrule(lr){3-4} \\cmidrule(lr){5-7}",
  paste0("Event & First affected legislature & All & Titular & ",
         "All & Titular & Titular, 1 July \\\\"), "\\midrule",
  vapply(seq_len(nrow(cmp)), \(i) sprintf(
    "%s & %s & %s & %s & %s & %s & %s \\\\", cmp$event[i],
    ifelse(is.na(cmp$to_legislature[i]), "--",
           format(cmp$to_legislature[i], "%Y-%m")),
    mth(cmp$step_all[i], 1L), mth(cmp$step_titular[i], 1L),
    its_tex(cmp$its25_primary[i], cmp$its25_primary_p[i],
            cmp$its25_primary_short[i]),
    its_tex(cmp$its25_nosub[i], cmp$its25_nosub_p[i],
            cmp$its25_nosub_short[i]),
    its_tex(cmp$its25_fixed_nosub[i], cmp$its25_fixed_nosub_p[i],
            cmp$its25_fixed_nosub_short[i])), ""),
  "\\bottomrule", "\\end{tabular}"),
  file.path(OUT_DIR, "A1_event_comparison.tex"))

# ------------------------------------------------------------------ figures
ev_years <- sort(unique(EVENTS$year))
tier <- integer(length(ev_years))
for (i in seq_along(ev_years)[-1L]) {
  tier[i] <- if (ev_years[i] - ev_years[i - 1L] <= 2L &&
                 tier[i - 1L] == 0L) 1L else 0L
}
ev_lab <- data.table(year = ev_years, hj = ifelse(tier == 0L, 1.05, 2.5))
ev_text <- geom_text(data = ev_lab, aes(x = year, y = Inf, label = year,
                                        hjust = hj),
                     angle = 90, vjust = -0.35, size = 2.3,
                     family = "serif", colour = "grey30",
                     inherit.aes = FALSE)
ev_vlines <- geom_vline(data = ev_lab[year != BASELINE],
                        aes(xintercept = year), linetype = "dotted",
                        colour = "grey45", linewidth = 0.4)
theme_a1 <- theme_minimal(base_family = "serif", base_size = 11) +
  theme(panel.grid.minor = element_blank(), legend.position = "bottom",
        strip.text = element_text(hjust = 0, face = "bold"))
ser_lab <- c(primary = "All members (primary)",
             nosub = "Titular (propietario) members only")

pd <- prof[substr(profile, 1L, 1L) %chin% c("A", "B") &
             series %chin% c("primary", "nosub")]
pd[, series_lab := factor(ser_lab[series], levels = ser_lab)]
p1 <- ggplot(pd, aes(break_yr, shift)) +
  geom_hline(yintercept = 0, colour = "grey40", linewidth = 0.3) +
  ev_vlines +
  geom_vline(xintercept = BASELINE, linetype = "dashed", colour = "black",
             linewidth = 0.5) +
  geom_ribbon(data = pd[series == "primary"],
              aes(ymin = shift - Z95 * se, ymax = shift + Z95 * se),
              fill = "#1f3a93", alpha = 0.16) +
  geom_line(aes(colour = series_lab, linetype = series_lab),
            linewidth = 0.7) +
  ev_text +
  scale_colour_manual(values = c("#1f3a93", "#b03030"), name = NULL) +
  scale_linetype_manual(values = c("solid", "longdash"), name = NULL) +
  facet_wrap(~profile, ncol = 1L, scales = "free_y") +
  scale_x_continuous(breaks = seq(1840L, 1970L, 10L)) +
  labs(x = "Candidate break year",
       y = "Estimated level shift (percentage points)") +
  theme_a1
ggsave(file.path(FIG_DIR, "A1_break_profile.pdf"), p1, width = 9,
       height = 7.5, device = cairo_pdf)
ggsave(file.path(FIG_DIR, "A1_break_profile.png"), p1, width = 9,
       height = 7.5, dpi = 200)

fig_s <- c("primary", "nosub")
fd <- bp_fit[model == "trend" & series %chin% fig_s &
               sample %chin% c("1834-1973", "1990-2021")]
fd <- rbind(fd, bp_fit[model == "trend" & series == "primary" &
                         sample == "1990-2021"][, series := "nosub"])
bd <- bp_breaks[model == "trend" & series %chin% fig_s &
                  sample %chin% c("1834-1973", "1990-2021")]
bd <- rbind(bd, bp_breaks[model == "trend" & series == "primary" &
                            sample == "1990-2021"][, series := "nosub"])
fd[, series_lab := factor(ser_lab[series], levels = ser_lab)]
bd[, series_lab := factor(ser_lab[series], levels = ser_lab)]
LEG_PT <- "Annual elite share"
LEG_FIT <- "Bai-Perron fit (level + trend, BIC)"
LEG_BRK <- "Break date [95% block-bootstrap interval]"
p2 <- ggplot() +
  annotate("rect", xmin = PRE_END + 0.5, xmax = POST_START - 0.5,
           ymin = -Inf, ymax = Inf, fill = "grey85", alpha = 0.6) +
  geom_vline(data = ev_lab[year != BASELINE],
             aes(xintercept = year, linetype = "Listed event (provisional)"),
             colour = "grey45", linewidth = 0.4) +
  geom_vline(data = data.table(x = BASELINE),
             aes(xintercept = x, linetype = "1925 reform"),
             colour = "black", linewidth = 0.5) +
  geom_point(data = fd, aes(year, elite, colour = LEG_PT), size = 0.9,
             shape = 16, alpha = 0.7) +
  geom_line(data = fd, aes(year, fitted, colour = LEG_FIT,
                           group = interaction(sample, regime)),
            linewidth = 0.9) +
  geom_errorbarh(data = bd, aes(xmin = boot_lo95, xmax = boot_hi95, y = -2,
                                colour = LEG_BRK), height = 1.6) +
  geom_point(data = bd, aes(new_regime_starts, -2, colour = LEG_BRK),
             shape = 17, size = 2) +
  ev_text +
  facet_wrap(~series_lab, ncol = 1L) +
  scale_colour_manual(values = setNames(c("grey30", "#b03030", "#1f3a93"),
                                        c(LEG_PT, LEG_FIT, LEG_BRK)),
                      breaks = c(LEG_PT, LEG_FIT, LEG_BRK), name = NULL) +
  scale_linetype_manual(values = c("Listed event (provisional)" = "dotted",
                                   "1925 reform" = "dashed"), name = NULL) +
  scale_x_continuous(breaks = seq(1840L, 2020L, 20L)) +
  labs(x = "Year (shaded: Congress closed 1973-1990)",
       y = "Enduring-elite share of Congress (%)") +
  theme_a1 + theme(legend.box = "vertical")
ggsave(file.path(FIG_DIR, "A1_bai_perron_series.pdf"), p2, width = 9,
       height = 8, device = cairo_pdf)
ggsave(file.path(FIG_DIR, "A1_bai_perron_series.png"), p2, width = 9,
       height = 8, dpi = 200)

# ------------------------------------------------------------ console digest
options(width = 200L)
message("[A1] headline 1925 shift, 1880-1970:")
print(headline[window == "1880-1970", .(roster, members, treatment_1925, n,
                                        shift = round(shift, 2),
                                        se = round(se, 2), p = signif(p, 3),
                                        pretrend = round(pretrend, 3))])
message("[A1] decomposition:"); print(decomp)
message("[A1] brute-force check:"); print(brute)
message("[A1] flatness:"); print(flat)
