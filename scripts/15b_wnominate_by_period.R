# 15b -- W-NOMINATE ideal points by chamber x legislative period (R&R 2026, D18).
#
# RUN FROM THE replication_repo ROOT:
#   "C:/Program Files/R/R-4.3.3/bin/Rscript.exe" scripts/15b_wnominate_by_period.R
# Reads ONLY the frozen roll-call snapshot written by 15a
# (data/processed/nominate_snapshot/); no BigQuery access is needed.
#
# ESTIMATION (one fit per chamber x period; 2 chambers x 6 periods, LI-LVI, 2002-2026):
#   * vote coding: yea = "Afirmativo"/"Si", nay = "En Contra"/"No"; every other label
#     (Abstencion, No Vota, Pareo, Dispensado) and absence from the roll = missing.
#   * wnominate() defaults (Poole-Rosenthal standard settings): dims = 2, lop = 0.025
#     (votes whose minority side is < 2.5% of yea+nay voters are dropped), minvotes = 20
#     (legislators with < 20 scaled votes are dropped), ubeta = 15, uweights = 0.5,
#     trials = 3 (< 4 -> no bootstrap SEs). The paper uses the FIRST dimension (coord1D).
#   * robustness fit: the same call with dims = 1 (coord1D_1d).
#   * polarity: W-NOMINATE's sign is arbitrary, so each fit is anchored on a clearly
#     right-wing legislator: the member of the UDI (Union Democrata Independiente) with the
#     most yea/nay votes in that chamber-period is set positive on both dimensions (the
#     second dimension is not interpreted). The anchor is written to the fit table, and the
#     orientation is checked afterwards: the mean coord1D of UDI+RN+Republicano members must
#     exceed that of PS+PC members, otherwise the script stops.
#
# OUTPUTS (output/nominate/):
#   wnominate_coords.csv   politician_id, chamber, period, coord1D, coord2D, coord1D_1d,
#                          gmp, cc, n_yeanay, is_anchor
#   wnominate_fitstats.csv per fit: legislators / votes in and scaled, classification,
#                          APRE, GMP, anchor, orientation check
# W-NOMINATE is deterministic given the data (SVD starts; trials < 4 draws nothing); the
# seed below is set only as a guard (INV-14).

suppressMessages({
  library(data.table)
  library(stringi)
  library(pscl)
  library(wnominate)
})
set.seed(1925L)

# ---------------------------------------------------------------- constants
SNAP      <- file.path("data", "processed", "nominate_snapshot")
OUT_DIR   <- file.path("output", "nominate")
YEA       <- c("afirmativo", "si")
NAY       <- c("en contra", "no")
MINVOTES  <- 20L
LOP       <- 0.025
ANCHOR_RE <- "uni.n dem.crata independiente"
RIGHT_RE  <- "uni.n dem.crata independiente|renovaci.n nacional|republicano"
LEFT_RE   <- "partido socialista|partido comunista"
dir.create(OUT_DIR, recursive = TRUE, showWarnings = FALSE)

need <- file.path(SNAP, c("vote_selections.csv.gz", "votes.csv.gz", "legislators.csv"))
if (!all(file.exists(need))) {
  message("[SKIP] roll-call snapshot not found in ", SNAP, " (run 15a)")
  quit(status = 3L)
}

# ---------------------------------------------------------------- data
norm_lab <- function(x) tolower(stri_trans_general(trimws(x), "Latin-ASCII"))

sel   <- fread(file.path(SNAP, "vote_selections.csv.gz"), encoding = "UTF-8")
votes <- fread(file.path(SNAP, "votes.csv.gz"), encoding = "UTF-8",
               select = c("vote_id", "source", "period"))
legs  <- fread(file.path(SNAP, "legislators.csv"), encoding = "UTF-8")

sel[, lab := norm_lab(selection)]
sel[, code := fifelse(lab %chin% YEA, 1L, fifelse(lab %chin% NAY, 0L, NA_integer_))]
sel <- merge(sel[, .(vote_id, politician_id, code)], votes, by = "vote_id",
             all.x = TRUE)
stopifnot(!anyNA(sel$period), !anyDuplicated(sel, by = c("vote_id", "politician_id")))
legs[, party_lc := norm_lab(party_name)]
legs[, name := paste(first_name, fathers_surname, mothers_surname)]

fits <- CJ(chamber = c("chamber", "senate"),
           period = c("LI", "LII", "LIII", "LIV", "LV", "LVI"), sorted = FALSE)

# ---------------------------------------------------------------- one fit
fit_one <- function(ch, pr) {
  d  <- sel[source == ch & period == pr & !is.na(code)]
  lg <- legs[chamber == ch & period == pr]
  wide <- dcast(d, politician_id ~ vote_id, value.var = "code")
  ids  <- wide$politician_id
  mat  <- as.matrix(wide[, -1L])
  rownames(mat) <- as.character(ids)
  n_yeanay <- rowSums(!is.na(mat))

  # anchor: most active UDI member of this chamber-period
  udi <- lg[grepl(ANCHOR_RE, party_lc) & politician_id %in% ids]
  if (nrow(udi) == 0L) stop("no UDI member to anchor ", ch, " ", pr)
  udi[, n_yn := n_yeanay[as.character(politician_id)]]
  setorder(udi, -n_yn, politician_id)
  anchor_id  <- udi$politician_id[1L]
  anchor_row <- match(anchor_id, ids)

  rc <- rollcall(mat, yea = 1L, nay = 0L, missing = NA, notInLegis = 9L,
                 legis.names = rownames(mat), vote.names = colnames(mat),
                 source = sprintf("IMFD roll calls, %s %s", ch, pr))
  f2 <- wnominate(rc, dims = 2L, minvotes = MINVOTES, lop = LOP,
                  polarity = c(anchor_row, anchor_row), verbose = FALSE)
  f1 <- wnominate(rc, dims = 1L, minvotes = MINVOTES, lop = LOP,
                  polarity = anchor_row, verbose = FALSE)
  L2 <- f2$legislators
  L1 <- f1$legislators
  co <- data.table(politician_id = ids, chamber = ch, period = pr,
                   coord1D = L2$coord1D, coord2D = L2$coord2D,
                   coord1D_1d = L1$coord1D, gmp = L2$GMP, cc = L2$CC,
                   n_yeanay = as.integer(n_yeanay), is_anchor = ids == anchor_id)

  # orientation check on party means (right bloc must be to the right of PS+PC)
  pm <- merge(co, lg[, .(politician_id, party_lc)], by = "politician_id")
  r_mean <- pm[grepl(RIGHT_RE, party_lc), mean(coord1D, na.rm = TRUE)]
  l_mean <- pm[grepl(LEFT_RE, party_lc), mean(coord1D, na.rm = TRUE)]
  r1 <- pm[grepl(RIGHT_RE, party_lc), mean(coord1D_1d, na.rm = TRUE)]
  l1 <- pm[grepl(LEFT_RE, party_lc), mean(coord1D_1d, na.rm = TRUE)]
  if (!(r_mean > l_mean && r1 > l1)) stop("orientation check failed ", ch, " ", pr)

  fs <- data.table(
    chamber = ch, period = pr, n_legis_in = length(ids), n_votes_in = ncol(mat),
    n_legis_scaled = sum(!is.na(L2$coord1D)),
    n_votes_scaled = sum(!is.na(f2$rollcalls$spread1D)),
    correct_class_2d = f2$fits[["correctclass2D"]],
    apre_1d = f2$fits[["apre1D"]], apre_2d = f2$fits[["apre2D"]],
    gmp_2d = f2$fits[["gmp2D"]], correct_class_1dfit = f1$fits[["correctclass1D"]],
    anchor_id = anchor_id, anchor_name = lg[politician_id == anchor_id, name],
    anchor_party = lg[politician_id == anchor_id, party_name],
    right_mean_coord1D = r_mean, left_mean_coord1D = l_mean,
    cor_dim1_2d_vs_1d = cor(L2$coord1D, L1$coord1D, use = "complete.obs"))
  message(sprintf("[15b] %-7s %-4s legislators %d/%d  votes %d/%d  CC %.1f%%  APRE1 %.3f  anchor %s",
                  ch, pr, fs$n_legis_scaled, fs$n_legis_in, fs$n_votes_scaled,
                  fs$n_votes_in, fs$correct_class_2d, fs$apre_1d, fs$anchor_name))
  list(coords = co, fit = fs)
}

res <- Map(fit_one, fits$chamber, fits$period)
coords  <- rbindlist(lapply(res, `[[`, "coords"))
fitstat <- rbindlist(lapply(res, `[[`, "fit"))
setorder(coords, chamber, period, politician_id)
fwrite(coords, file.path(OUT_DIR, "wnominate_coords.csv"))
fwrite(fitstat, file.path(OUT_DIR, "wnominate_fitstats.csv"))
message("[15b] wrote ", file.path(OUT_DIR, "wnominate_coords.csv"), " (",
        nrow(coords), " rows) and wnominate_fitstats.csv")
