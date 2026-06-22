## 21 — N6: family-clustered SE for the CONTINUOUS surname-status coefficient in the
## text-based ideal-point model (m_ses from 14_tbip_ideal_points.R). The manuscript
## currently says only that the result is "unchanged" under family clustering; this
## script extracts and prints the ACTUAL coefficient, family-clustered SE, and p-value.
## Mirrors the data prep of 14_tbip_ideal_points.R; uses the authoritative 298-surname
## list from the replication repo.
## Inputs (CWD = the paper_1925 data dir, as in script 14):
##   intervenciones.csv, autor_punto_80k_210722.csv, cong_df.csv, surname_nse.csv
##   + enduring_elite_FINAL.csv (read from the repo, authoritative)
## Output: ../paper/tables/table_tbip_ses_cluster.tex (bare tabular, INV-13)
##         printed coefficient / clustered SE / p
## No stochastic element -> no seed (INV-14). Libraries at top (INV-15).
suppressMessages({
  library(dplyr); library(tidyr); library(stringr)
  library(sandwich); library(lmtest)
})

## Paths are resolved relative to THIS script's location, so the script runs unchanged
## on any machine and under either native R or Windows Rscript.exe (which still receives
## a --file=... argument, used here to find the script dir). No hardcoded user paths.
##   REPO = replication_repo root (= scripts/ parent), holds data/processed/*.
##   DATA = the paper_1925 project dir (= repo parent), holds the raw discourse CSVs
##          (intervenciones.csv, autor_punto_80k_210722.csv, cong_df.csv) read by script 14.
get_script_dir <- function() {
  args <- commandArgs(trailingOnly = FALSE)
  m <- grep("^--file=", args, value = TRUE)
  if (length(m)) return(dirname(normalizePath(sub("^--file=", "", m[1]))))
  ## interactive / sourced fallback: assume CWD is the repo root (existing convention)
  file.path(normalizePath(getwd()), "scripts")
}
SCRIPT_DIR <- get_script_dir()
REPO <- normalizePath(file.path(SCRIPT_DIR, ".."))   # replication_repo root
DATA <- normalizePath(file.path(REPO, ".."))         # paper_1925 project dir (repo parent)
ELITE_CSV <- file.path(REPO, "data/processed/enduring_elite_FINAL.csv")
SES_CSV   <- file.path(REPO, "data/processed/surname_nse.csv")

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

ses <- read.csv(SES_CSV, stringsAsFactors = FALSE)
ses$surname <- deaccent(ses$surname)
ses_map <- setNames(ses$mean_nse, ses$surname)

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
data_lm$sector <- relevel(as.factor(data_lm$sector), ref = 'centro')
data_lm$apellido <- relevel(as.factor(data_lm$apellido), ref = 'otro')
data_lm$surname_ses <- pmax(ses_map[data_lm$PatN], ses_map[data_lm$MatN], na.rm = TRUE)

cat("N legislators in regression sample:", nrow(data_lm), "\n")

## ---- the continuous surname-SES model (m_ses), as in script 14 ----
m_ses <- lm(punto ~ surname_ses + sector + senate_vs_chamber + total_years + urbano, data = data_lm)

## classical / default SE
ct_def <- coeftest(m_ses)
b   <- coef(m_ses)["surname_ses"]
se0 <- ct_def["surname_ses", "Std. Error"]
p0  <- ct_def["surname_ses", "Pr(>|t|)"]

## [N6] FAMILY-clustered SE: cluster by paternal surname (PatN)
ct_fam <- coeftest(m_ses, vcov = vcovCL(m_ses, cluster = data_lm$PatN))
se_fam <- ct_fam["surname_ses", "Std. Error"]
t_fam  <- ct_fam["surname_ses", "t value"]
p_fam  <- ct_fam["surname_ses", "Pr(>|t|)"]
n_fam  <- length(unique(data_lm$PatN))

## [N6 robustness] also speaker-clustered (each legislator is one row here, so == HC0-ish)
cat(sprintf("\n[N6] continuous surname-status coefficient (m_ses):\n"))
cat(sprintf("     coef            = %.5f\n", b))
cat(sprintf("     default SE      = %.5f  (p = %.4f)\n", se0, p0))
cat(sprintf("     family-clust SE = %.5f  (t = %.2f, p = %.4f)  [%d families]\n",
            se_fam, t_fam, p_fam, n_fam))

## ---- bare tabular (INV-13) ----
star <- function(p) if (p < 0.01) "***" else if (p < 0.05) "**" else if (p < 0.10) "*" else ""
L <- c(
  "\\begin{tabular}{lcc}",
  "\\toprule",
  " & Default SE & Family-clustered SE \\\\",
  " & (1) & (2) \\\\",
  "\\midrule",
  sprintf("Surname status (continuous) & %.4f%s & %.4f%s \\\\", b, star(p0), b, star(p_fam)),
  sprintf(" & (%.4f) & (%.4f) \\\\", se0, se_fam),
  "\\midrule",
  sprintf("$p$-value & %.4f & %.4f \\\\", p0, p_fam),
  sprintf("Legislators & %d & %d \\\\", nrow(data_lm), nrow(data_lm)),
  sprintf("Clusters (families) & --- & %d \\\\", n_fam),
  "\\bottomrule",
  "\\end{tabular}")
out_tab <- file.path(REPO, "../paper/tables/table_tbip_ses_cluster.tex")
writeLines(L, out_tab)
cat("[N6] wrote", normalizePath(out_tab, mustWork = FALSE), "\n")
