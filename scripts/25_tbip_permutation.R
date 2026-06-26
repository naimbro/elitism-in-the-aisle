## 25 — MUST #2 / SHOULD #2: legislator-level PERMUTATION TEST and FAMILY-CLUSTERED SEs
## for the CATEGORICAL surname contrast in the text-based ideal-point model.
##
## Motivation. In the preferred specification (script 14 / Table 2, col 3) the
## common-vs-other categorical gap (+0.19) is positive but not significant under
## default OLS SEs. The domain referee's headline concern is whether the categorical
## contrast is significant at all. This script answers it two ways that do NOT rely on
## the OLS SE being correct:
##   (a) an SE-FREE legislator-level PERMUTATION TEST: shuffle the surname labels across
##       the 281 legislators, refit the preferred model, and read the two-sided p-value
##       off the permutation null of the apellido coefficients;
##   (b) FAMILY-CLUSTERED SEs (cluster by paternal surname) on the same categorical model,
##       to show whether clustering the categorical contrast changes the inference.
##
## Mirrors the data prep of 21_tbip_family_cluster_se.R (and 14_tbip_ideal_points.R);
## uses the authoritative 298-surname list from the replication repo.
## Inputs (raw discourse CSVs read from the project dir; processed lists from the repo):
##   intervenciones.csv, autor_punto_80k_210722.csv, cong_df.csv  (DATA = repo parent)
##   enduring_elite_FINAL.csv, surname_nse.csv                     (REPO/data/processed)
## Output: ../paper/tables/table_tbip_permutation.tex (bare tabular, INV-13)
##         printed observed coefs, default/clustered SEs, permutation p-values.
## Stochastic (label shuffling) -> set.seed() ONCE at top (INV-14). Libraries at top (INV-15).
suppressMessages({
  library(dplyr); library(tidyr); library(stringr)
  library(sandwich); library(lmtest)
})
set.seed(1925)

## Resolve paths relative to THIS script (runs unchanged on any machine / Windows Rscript).
get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  m <- grep("^--file=", args, value = TRUE)
  if (length(m)) return(dirname(normalizePath(sub("^--file=", "", m[1]))))
  file.path(normalizePath(getwd()), "scripts")
}
SCRIPT_DIR <- get_script_dir()
REPO <- normalizePath(file.path(SCRIPT_DIR, ".."))   # replication_repo root
DATA <- normalizePath(file.path(REPO, ".."))         # paper_1925 project dir (repo parent)
ELITE_CSV <- file.path(REPO, "data/processed/enduring_elite_FINAL.csv")

deaccent <- function(x) chartr("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNAEIOUUN", toupper(as.character(x)))

intervenciones <- read.csv(file.path(DATA, "intervenciones.csv"), stringsAsFactors = FALSE)
intervenciones$camara <- relevel(as.factor(intervenciones$camara), ref = "diputados")

intervenciones <- intervenciones %>%
  mutate(sector = case_when(
    Partido %in% c('Partido Conservador','Partido Conservador Tradicionalista',
      'Partido Conservador Social Cristiano','Partido Conservador Unido','Partido Liberal',
      'Partido Liberal Democratico','Partido Liberal Doctrinario','Partido Liberal Progresista',
      'Partido Liberal Unido','Partido Nacional o Monttvarista','Partido Nacional',
      'Partido Agrario Laborista','Partido Nacional Socialista',
      'Movimiento Nacional Socialista de Chile') ~ 'derecha',
    Partido %in% c('Partido Radical','Partido Radical de Chile','Partido Radical Independiente',
      'Partido Democratico de Chile','Partido Social Republicano','Falange Nacional',
      'Partido Accion Republicana','Partido Regionalista','Partido Agrario') ~ 'centro',
    Partido %in% c('Partido Obrero Socialista','Partido Socialista de Chile',
      'Partido Socialista Popular','Partido Comunista de Chile','Partido Radical Socialista',
      'Confederacion Republicana de Accion Civica de Obreros y Empleados',
      'Partido Progresista Nacional','Union Social Republicana de Asalariados de Chile',
      'Union Social Republicana de los Asalariados de Chile','Nueva Accion Publica',
      'Vanguardia Popular Socialista','Partido Democratico del Pueblo','Partido Democrata',
      'Partido Democratico') ~ 'izquierda',
    TRUE ~ 'otro')) %>%
  filter(sector != 'otro')
intervenciones$sector <- relevel(as.factor(intervenciones$sector), ref = 'centro')

comunes <- deaccent(c('GONZALEZ','MUNOZ','DIAZ','ROJAS','PEREZ','SILVA','SOTO','MARTINEZ',
  'LOPEZ','MORALES','CONTRERAS','RODRIGUEZ','SEPULVEDA','FUENTES','VALENZUELA','RAMIREZ',
  'ESPINOZA','REYES','HERNANDEZ','GUTIERREZ','FLORES','CASTRO','TORRES','SANCHEZ','VASQUEZ',
  'CASTILLO','FERNANDEZ','ARAYA','HERRERA','VARGAS','NUÑEZ','ALVAREZ','CARRASCO','GOMEZ',
  'BRAVO','VERGARA','GARCIA','TAPIA','JARA','ZUÑIGA','ORELLANA','FIGUEROA','MIRANDA',
  'RIQUELME','CAMPOS','MOLINA','RIVERA','GUZMAN','SANDOVAL','ORTIZ'))
elite_list <- deaccent(read.csv(ELITE_CSV, stringsAsFactors = FALSE)$surname)
cat("elite-list surnames:", length(elite_list), "\n")

intervenciones$PatN <- deaccent(intervenciones$Pat)
intervenciones$MatN <- deaccent(intervenciones$Mat)
intervenciones$comun <- intervenciones$PatN %in% comunes | intervenciones$MatN %in% comunes
intervenciones$elite <- intervenciones$PatN %in% elite_list | intervenciones$MatN %in% elite_list
intervenciones$apellido <- ifelse(intervenciones$elite, 'elite',
                            ifelse(intervenciones$comun, 'comun', 'otro'))
intervenciones$apellido <- relevel(as.factor(intervenciones$apellido), ref = 'otro')

autor_punto <- read.csv(file.path(DATA, "autor_punto_80k_210722.csv"), stringsAsFactors = FALSE)
autor_punto$autor <- gsub('\n', '', autor_punto$autor, fixed = TRUE)
autor_punto <- autor_punto %>%
  mutate(autor = case_when(
    autor == "Carlos Acharan Perez De Arce" ~ "Carlos Acharan Perez de Arce",
    autor == "Eliodoro Yañez Ponce De Leon" ~ "Eliodoro Yañez Ponce de Leon",
    autor == "Enrique Bermudez De La Paz" ~ "Enrique Bermudez de la Paz",
    autor == "Hector Rodriguez De La Sotta" ~ "Hector Rodriguez de la Sotta",
    autor == "Juan De Dios Valenzuela Rodriguez" ~ "Juan de Dios Valenzuela Rodriguez",
    autor == "Julio Rene De La Jara Zuñiga" ~ "Julio Rene De la Jara Zuñiga",
    autor == "Marco Antonio De La Cuadra Poisson" ~ "Marco Antonio De la Cuadra Poisson",
    autor == "Paulino Alfonso Del Barrio" ~ "Paulino Alfonso del Barrio",
    autor == "Ramon De La Vega Corces" ~ "Ramon De la Vega Corces",
    autor == "Roberto Sanchez Garcia De La Huerta" ~ "Roberto Sanchez Garcia de la Huerta",
    autor == "Vidal Antonio Arellano Peña Y Lillo" ~ "Vidal Antonio Arellano Peña y Lillo",
    TRUE ~ autor))

autor_punto <- left_join(intervenciones, autor_punto, by = c('Hablante' = 'autor')) %>%
  distinct(Hablante, Year, .keep_all = TRUE) %>% drop_na(punto) %>%
  group_by(Year) %>% mutate(n = n()) %>% filter(n > 10) %>% ungroup() %>%
  select(Hablante, Year, camara, sector, Partido, apellido, punto, PatN, MatN)

cong_df <- read.csv(file.path(DATA, "cong_df.csv"), stringsAsFactors = FALSE)
first_year <- cong_df %>%
  mutate(urbano = str_detect(Localidad, "Santiago|Concepcion|Valparaiso")) %>%
  group_by(Name) %>%
  summarise(Start = min(Start), total_years = max(End) - min(Start),
            urbano = any(urbano), .groups = 'drop')

mode_chr <- function(v){ v <- v[!is.na(v)]; if (!length(v)) NA_character_ else names(sort(table(v), decreasing = TRUE))[1] }
data_lm <- autor_punto %>%
  left_join(first_year, by = c("Hablante" = "Name")) %>%
  mutate(Year = ifelse(is.na(Start), Year, Start)) %>%
  group_by(Hablante) %>%
  summarise(
    punto = first(punto), apellido = first(apellido),
    sector = mode_chr(as.character(sector)),
    PatN = first(PatN), MatN = first(MatN),
    Year = min(Year), total_years = first(total_years), urbano = first(urbano),
    senate_vs_chamber = (sum(camara == 'senado') - sum(camara == 'diputados')) / n(),
    .groups = 'drop')
data_lm$sector   <- relevel(as.factor(data_lm$sector),   ref = 'centro')
data_lm$apellido <- relevel(as.factor(data_lm$apellido), ref = 'otro')

cat("N legislators in regression sample:", nrow(data_lm), "\n")
print(data_lm %>% count(apellido))

## ---- preferred CATEGORICAL model (Table 2, col 3) ----
m3 <- lm(punto ~ apellido + sector + senate_vs_chamber + total_years + urbano, data = data_lm)
coefs <- coef(m3)
b_comun <- coefs["apellidocomun"]
b_elite <- coefs["apellidoelite"]

## (a) default OLS SE / p
ct_def  <- coeftest(m3)
se_comun_def <- ct_def["apellidocomun", "Std. Error"]; p_comun_def <- ct_def["apellidocomun", "Pr(>|t|)"]
se_elite_def <- ct_def["apellidoelite", "Std. Error"]; p_elite_def <- ct_def["apellidoelite", "Pr(>|t|)"]

## (b) SHOULD #2 — FAMILY-clustered SE (cluster by paternal surname) on the categorical model
ct_fam  <- coeftest(m3, vcov = vcovCL(m3, cluster = data_lm$PatN))
se_comun_fam <- ct_fam["apellidocomun", "Std. Error"]; p_comun_fam <- ct_fam["apellidocomun", "Pr(>|t|)"]
se_elite_fam <- ct_fam["apellidoelite", "Std. Error"]; p_elite_fam <- ct_fam["apellidoelite", "Pr(>|t|)"]
n_fam <- length(unique(data_lm$PatN))

## (c) MUST #2 — legislator-level PERMUTATION TEST.
## This is an UNCONDITIONAL randomization test of the sharp null of no surname effect:
## we shuffle the apellido labels marginally across the 281 legislators and refit the SAME
## preferred model on each draw (the covariates are retained in the refit to absorb residual
## variance and sharpen the test, but the shuffle is not stratified on them). Under the sharp
## null the resulting p-values are exact. Two-sided p = share of permutations with
## |coef| >= |observed|. (A within-sector stratified shuffle would instead target the
## conditional null; the marginal version here is the standard, more conservative choice.)
B <- 10000L
perm_comun <- numeric(B); perm_elite <- numeric(B)
dperm <- data_lm
for (i in seq_len(B)) {
  dperm$apellido <- sample(data_lm$apellido)              # shuffle labels across legislators
  cf <- coef(lm(punto ~ apellido + sector + senate_vs_chamber + total_years + urbano, data = dperm))
  perm_comun[i] <- cf["apellidocomun"]
  perm_elite[i] <- cf["apellidoelite"]
}
## two-sided permutation p-values (add-one correction so p is never exactly 0)
p_comun_perm <- (1 + sum(abs(perm_comun) >= abs(b_comun))) / (B + 1)
p_elite_perm <- (1 + sum(abs(perm_elite) >= abs(b_elite))) / (B + 1)

cat(sprintf("\n[MUST2] preferred categorical model (col 3), N = %d, families = %d, B = %d perms\n",
            nrow(data_lm), n_fam, B))
cat(sprintf("  Common vs other:  b = %+0.4f | default SE %.4f (p=%.4f) | fam-clust SE %.4f (p=%.4f) | PERM p=%.4f\n",
            b_comun, se_comun_def, p_comun_def, se_comun_fam, p_comun_fam, p_comun_perm))
cat(sprintf("  Elite  vs other:  b = %+0.4f | default SE %.4f (p=%.4f) | fam-clust SE %.4f (p=%.4f) | PERM p=%.4f\n",
            b_elite, se_elite_def, p_elite_def, se_elite_fam, p_elite_fam, p_elite_perm))

## ---- bare tabular (INV-13): permutation + clustered inference for the categorical contrast ----
fmt  <- function(x) sprintf("%+.3f", x)
fmtp <- function(p) sprintf("%.3f", p)
L <- c(
  "\\begin{tabular}{lcc}",
  "\\toprule",
  " & Common surname & Elite surname \\\\",
  " & (ref.\\ other) & (ref.\\ other) \\\\",
  "\\midrule",
  sprintf("Coefficient (col 3 model) & $%s$ & $%s$ \\\\", fmt(b_comun), fmt(b_elite)),
  sprintf("Default OLS SE & (%.3f) & (%.3f) \\\\", se_comun_def, se_elite_def),
  sprintf("Family-clustered SE & (%.3f) & (%.3f) \\\\", se_comun_fam, se_elite_fam),
  "\\midrule",
  sprintf("$p$, default OLS & %s & %s \\\\", fmtp(p_comun_def), fmtp(p_elite_def)),
  sprintf("$p$, family-clustered & %s & %s \\\\", fmtp(p_comun_fam), fmtp(p_elite_fam)),
  sprintf("$p$, permutation & %s & %s \\\\", fmtp(p_comun_perm), fmtp(p_elite_perm)),
  "\\midrule",
  sprintf("Legislators & %d & %d \\\\", nrow(data_lm), nrow(data_lm)),
  sprintf("Clusters (families) & %d & %d \\\\", n_fam, n_fam),
  sprintf("Permutations & %s & %s \\\\", format(B, big.mark=","), format(B, big.mark=",")),
  "\\bottomrule",
  "\\end{tabular}")
out_tab <- file.path(REPO, "../paper/tables/table_tbip_permutation.tex")
writeLines(L, out_tab)
cat("[MUST2] wrote", normalizePath(out_tab, mustWork = FALSE), "\n")
