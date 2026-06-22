library(dplyr)
library(tidyr)
library(ggplot2)
library(lmtest)
library(sandwich)
library(stargazer)
library(stringr)

## ===========================================================================
## puntos_ideales_revised.R
## Changes vs. the original (each marked [EDIT N]); rationale at bottom of file.
##   [EDIT 1] Elite classification now uses the 285-surname ENDURING-ELITE list
##            (enduring_elite_FINAL.csv), replacing the old precomputed 65-list
##            `elite` column.
##   [EDIT 2] ELITE takes precedence over COMMON (matches the paper's Fig.2 rule;
##            the original coded common-first, contradicting the text).
##   [EDIT 3] Removed the non-reproducible `sector = sample(sector, 1)`: a
##            legislator's party is now their MODAL party (deterministic).
##   [EDIT 4] First-Year (entry cohort) is treated as a MECHANISM, not a
##            confounder: primary models exclude it; it appears only as a
##            conservative robustness column, with a decade-FE alternative.
##   [EDIT 5] Added an external-validity check of the ideal-point axis
##            (punto ~ sector) to address the circularity critique.
##   [EDIT 6] Added a CONTINUOUS surname-SES specification (mean NSE from the
##            2020 padrón) that bypasses the black-box 'other' reference category.
##   [EDIT 7] Standard errors also clustered by family surname (paternal), not
##            only by speaker.
## ===========================================================================

## accent/upper normaliser so surname matching is robust (ñ, á, ...)
deaccent <- function(x) chartr("ÁÉÍÓÚÜÑáéíóúüñ", "AEIOUUNAEIOUUN", toupper(as.character(x)))

intervenciones <- read.csv('intervenciones.csv', stringsAsFactors = FALSE)
intervenciones$camara <- relevel(as.factor(intervenciones$camara), ref = 'diputados')

## ----------------------------------------------------------- SECTOR IDEOLÓGICO
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
    TRUE ~ 'otro'))
intervenciones <- intervenciones %>% filter(sector != 'otro')
intervenciones$sector <- relevel(as.factor(intervenciones$sector), ref = 'centro')

## --------------------------------------------------------------- SURNAME TYPE
comunes <- deaccent(c('GONZALEZ','MUNOZ','DIAZ','ROJAS','PEREZ','SILVA','SOTO','MARTINEZ',
  'LOPEZ','MORALES','CONTRERAS','RODRIGUEZ','SEPULVEDA','FUENTES','VALENZUELA','RAMIREZ',
  'ESPINOZA','REYES','HERNANDEZ','GUTIERREZ','FLORES','CASTRO','TORRES','SANCHEZ','VASQUEZ',
  'CASTILLO','FERNANDEZ','ARAYA','HERRERA','VARGAS','NUÑEZ','ALVAREZ','CARRASCO','GOMEZ',
  'BRAVO','VERGARA','GARCIA','TAPIA','JARA','ZUÑIGA','ORELLANA','FIGUEROA','MIRANDA',
  'RIQUELME','CAMPOS','MOLINA','RIVERA','GUZMAN','SANDOVAL','ORTIZ'))

## [EDIT 1] enduring-elite list (285 surnames) from our final file
elite_list <- deaccent(read.csv('enduring_elite_FINAL.csv', stringsAsFactors = FALSE)$surname)

intervenciones$PatN <- deaccent(intervenciones$Pat)
intervenciones$MatN <- deaccent(intervenciones$Mat)
intervenciones$comun <- intervenciones$PatN %in% comunes | intervenciones$MatN %in% comunes
intervenciones$elite <- intervenciones$PatN %in% elite_list | intervenciones$MatN %in% elite_list

## [EDIT 2] ELITE precedence over COMMON (paper's stated rule)
intervenciones$apellido <- ifelse(intervenciones$elite, 'elite',
                            ifelse(intervenciones$comun, 'comun', 'otro'))
intervenciones$apellido <- relevel(as.factor(intervenciones$apellido), ref = 'otro')

## ----------------------------------------------------- AUTOR-PUNTO (ideal pts)
autor_punto <- read.csv('autor_punto_80k_210722.csv', stringsAsFactors = FALSE)
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

autor_punto <- left_join(intervenciones, autor_punto, by = c('Hablante' = 'autor'))
autor_punto <- autor_punto %>% distinct(Hablante, Year, .keep_all = TRUE) %>% drop_na(punto)
autor_punto <- autor_punto %>% group_by(Year) %>% mutate(n = n()) %>% filter(n > 10) %>% ungroup()
autor_punto <- autor_punto %>% select(Hablante, Year, camara, sector, Partido, apellido, punto, PatN, MatN)

## ------------------------------------------- FIRST YEAR / tenure / urban (cong_df)
cong_df <- read.csv("cong_df.csv", stringsAsFactors = FALSE)
first_year <- cong_df %>%
  mutate(urbano = str_detect(Localidad, "Santiago|Concepcion|Valparaiso")) %>%
  group_by(Name) %>%
  summarise(Start = min(Start), total_years = max(End) - min(Start),
            urbano = any(urbano), .groups = 'drop')

## [EDIT 6] continuous surname SES (2020 padrón mean NSE), keyed by surname
ses <- read.csv('surname_nse.csv', stringsAsFactors = FALSE)
ses$surname <- deaccent(ses$surname)
ses_map <- setNames(ses$mean_nse, ses$surname)

## ------------------------------------------------- BUILD per-legislator dataset
## [EDIT 3] deterministic collapse: modal sector, no random sampling
mode_chr <- function(v){ v <- v[!is.na(v)]; if (!length(v)) NA_character_ else names(sort(table(v), decreasing = TRUE))[1] }

data_lm <- autor_punto %>%
  left_join(first_year, by = c("Hablante" = "Name")) %>%
  mutate(Year = ifelse(is.na(Start), Year, Start)) %>%
  group_by(Hablante) %>%
  summarise(
    punto             = first(punto),
    apellido          = first(apellido),
    sector            = mode_chr(as.character(sector)),
    PatN              = first(PatN),
    MatN              = first(MatN),
    Year              = min(Year),                       # entry-year (First Year)
    total_years       = first(total_years),
    urbano            = first(urbano),
    senate_vs_chamber = (sum(camara == 'senado') - sum(camara == 'diputados')) / n(),
    .groups = 'drop')

data_lm$sector   <- relevel(as.factor(data_lm$sector),   ref = 'centro')
data_lm$apellido <- relevel(as.factor(data_lm$apellido), ref = 'otro')
## continuous surname SES = the higher-status of the two surnames (matches "elite if either")
data_lm$surname_ses <- pmax(ses_map[data_lm$PatN], ses_map[data_lm$MatN], na.rm = TRUE)
data_lm$decade <- factor(floor(data_lm$Year / 10) * 10)

cat("\nN legislators in regression sample:", nrow(data_lm), "\n")
print(data_lm %>% count(apellido))

## ============================ [EDIT 5] AXIS VALIDATION ======================
## Does the text-based ideal-point axis independently recover party ideology?
## If izquierda > centro > derecha, the axis is meaningful (not 'circular').
cat("\n--- External validity: mean ideal point by party sector ---\n")
print(data_lm %>% group_by(sector) %>% summarise(mean_punto = mean(punto), n = n()))
m_val <- lm(punto ~ sector, data = data_lm)
print(summary(m_val))

## ================================ MAIN REGRESSIONS =========================
## Primary models (do NOT control for entry cohort — see [EDIT 4] note):
m_1 <- lm(punto ~ apellido, data = data_lm)
m_2 <- lm(punto ~ apellido + sector, data = data_lm)
m_3 <- lm(punto ~ apellido + sector + senate_vs_chamber + total_years + urbano, data = data_lm)
## [EDIT 6] continuous surname-SES (no 'other' category):
m_ses <- lm(punto ~ surname_ses + sector + senate_vs_chamber + total_years + urbano, data = data_lm)
## [EDIT 4] robustness that DOES net out the cohort mechanism (over-controls):
m_fy  <- lm(punto ~ apellido + sector + senate_vs_chamber + total_years + urbano + Year, data = data_lm)
m_dec <- lm(punto ~ apellido + sector + senate_vs_chamber + total_years + urbano + decade, data = data_lm)

stargazer(list(m_1, m_2, m_3, m_fy, m_dec), type = 'html', out = 'reg_revised.doc',
          dep.var.labels = "Text-based ideal point",
          column.labels = c("base","+party","primary","+First Yr*","+decade FE*"),
          notes = "* First Year / decade net out the cohort-replacement mechanism (likely over-control).",
          title = 'OLS: ideal points and social background (285-surname elite measure)')

stargazer(m_ses, type = 'html', out = 'reg_revised_ses.doc',
          dep.var.labels = "Text-based ideal point",
          covariate.labels = c("Surname SES (continuous)","Right (ref=center)","Left (ref=center)",
                               "Senate vs Chamber","Number of Years","Urban locality"),
          title = 'OLS: ideal points and continuous surname SES')

## ======================= [EDIT 7] CLUSTERED SEs (speaker AND family) ========
robust_se <- function(m, cl) sqrt(diag(vcovCL(m, cluster = cl)))
models <- list(m_1, m_2, m_3)
se_hablante <- lapply(models, function(m) robust_se(m, ~Hablante))   # original clustering
se_family   <- lapply(seq_along(models), function(i)
                 sqrt(diag(vcovCL(models[[i]], cluster = data_lm$PatN))))  # by paternal surname
stargazer(models, type = 'html', out = 'reg_revised_cluster.doc', se = se_family,
          dep.var.labels = "Text-based ideal point",
          title = "OLS with SEs clustered by family surname (paternal)")

## ================================ PLOTS ====================================
## Mean ideal point per year (Figure 3 equivalent)
autor_punto %>% distinct(Hablante, Year, .keep_all = TRUE) %>%
  group_by(Year) %>% summarise(mean_punto = mean(punto), .groups='drop') %>%
  ggplot(aes(Year, mean_punto)) + geom_path() + geom_point() +
  scale_x_continuous(n.breaks = 12) +
  geom_vline(xintercept = 1925, linetype = 'dotdash', color = 'red') +
  theme_classic() + labs(x='Year', y='Mean Ideal Point',
  title='Ideological evolution in the Chilean Congress, 1910-1950')
ggsave('evolucion_puntos_revised.png', width = 10, height = 5)

## Ideal points by surname type over time (elite / common / other)
autor_punto %>% group_by(Year, apellido) %>% summarise(mean_punto = mean(punto), .groups='drop') %>%
  ggplot(aes(Year, mean_punto, color = apellido)) +
  geom_point(alpha = .5) + geom_smooth(method='loess', formula='y ~ x') +
  scale_x_continuous(n.breaks = 12) +
  geom_vline(xintercept = 1925, linetype = 'dotdash', color = 'red') +
  theme_classic() +
  scale_color_manual(values = c('#E7B800','#FC4E07','blue'),
                     labels = c('Other','Common','Elite')) +
  labs(x='Year', y='Mean Ideal Point', color='Surname type',
       title='Ideal points by surname type (285-surname elite measure)')
ggsave('puntos_apellido_revised.png', width = 10, height = 5)

## ===========================================================================
## NOTE ON [EDIT 4] — why entry-year is a mechanism, not a confounder:
## The dependent variable (discursive ideal point) rises strongly over time, and
## the social transformation operates THROUGH cohort replacement: later-entering
## legislators are BOTH more likely to bear common surnames AND to speak more
## progressively. Entry-year is therefore post-treatment relative to the
## descriptive-representation shift. Conditioning on it ("within the same entry
## cohort, do surnames still differ?") removes the very channel of interest and
## mechanically attenuates the surname coefficients (this is exactly what drove
## elite -> non-significant in the original Table 2 Model 3/4). We therefore make
## the cohort-free models primary and report First-Year / decade-FE only as
## conservative robustness, clearly labelled.
## ===========================================================================
