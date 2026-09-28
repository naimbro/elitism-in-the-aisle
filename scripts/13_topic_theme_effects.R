## 13 — theme-level topic emphasis (party/chamber/year-adjusted, legislator-clustered SEs).
## Coding: the canonical 298-surname list (enduring_elite_FINAL.csv). Its elite/common
## estimates equal the party-adjusted column of script 39 (A3_theme_contrasts_both_specs.csv).
## RUN FROM THE PROJECT ROOT. R&R 2026: output moved from the root into the repo,
## <repo>/data/processed/theme_effects.csv (read by script 19). The earlier 285-list version of
## that file is kept as data/processed/theme_effects_285.csv (script 39's 285-list check).
suppressMessages({library(dplyr); library(tidytext); library(quanteda); library(stm); library(sandwich); library(lmtest)})
script_arg <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
REPO <- if (length(script_arg) == 1L) dirname(dirname(normalizePath(sub("^--file=", "", script_arg)))) else "replication_repo"
OUT <- file.path(REPO, "data", "processed", "theme_effects.csv")
stopifnot("Run from the project root (paper_1925/)" =
            all(file.exists(c("stm_model_285.rds", "intervenciones.csv", "enduring_elite_FINAL.csv", "topic_theme_map.csv"))))
deaccent <- function(x) chartr("ÁÉÍÓÚÜÑáéíóúüñ","AEIOUUNAEIOUUN",toupper(as.character(x)))
m <- readRDS('stm_model_285.rds'); theta <- m$theta

iv <- read.csv('intervenciones.csv', stringsAsFactors=FALSE)
iv <- iv %>% mutate(sector = case_when(
  Partido %in% c('Partido Conservador','Partido Conservador Tradicionalista','Partido Conservador Social Cristiano','Partido Conservador Unido','Partido Liberal','Partido Liberal Democratico','Partido Liberal Doctrinario','Partido Liberal Progresista','Partido Liberal Unido','Partido Nacional o Monttvarista','Partido Nacional','Partido Agrario Laborista','Partido Nacional Socialista','Movimiento Nacional Socialista de Chile') ~ 'derecha',
  Partido %in% c('Partido Radical','Partido Radical de Chile','Partido Radical Independiente','Partido Democratico de Chile','Partido Social Republicano','Falange Nacional','Partido Accion Republicana','Partido Regionalista','Partido Agrario') ~ 'centro',
  Partido %in% c('Partido Obrero Socialista','Partido Socialista de Chile','Partido Socialista Popular','Partido Comunista de Chile','Partido Radical Socialista','Confederacion Republicana de Accion Civica de Obreros y Empleados','Partido Progresista Nacional','Union Social Republicana de Asalariados de Chile','Union Social Republicana de los Asalariados de Chile','Nueva Accion Publica','Vanguardia Popular Socialista','Partido Democratico del Pueblo','Partido Democrata','Partido Democratico') ~ 'izquierda',
  TRUE ~ 'otro'))
comunes <- deaccent(c('GONZALEZ','MUNOZ','DIAZ','ROJAS','PEREZ','SILVA','SOTO','MARTINEZ','LOPEZ','MORALES','CONTRERAS','RODRIGUEZ','SEPULVEDA','FUENTES','VALENZUELA','RAMIREZ','ESPINOZA','REYES','HERNANDEZ','GUTIERREZ','FLORES','CASTRO','TORRES','SANCHEZ','VASQUEZ','CASTILLO','FERNANDEZ','ARAYA','HERRERA','VARGAS','NUÑEZ','ALVAREZ','CARRASCO','GOMEZ','BRAVO','VERGARA','GARCIA','TAPIA','JARA','ZUÑIGA','ORELLANA','FIGUEROA','MIRANDA','RIQUELME','CAMPOS','MOLINA','RIVERA','GUZMAN','SANDOVAL','ORTIZ'))
elite_list <- deaccent(read.csv('enduring_elite_FINAL.csv', stringsAsFactors=FALSE)$surname)
PatN<-deaccent(iv$Pat); MatN<-deaccent(iv$Mat)
iv$apellido <- ifelse(PatN%in%elite_list|MatN%in%elite_list,'elite', ifelse(PatN%in%comunes|MatN%in%comunes,'comun','otro'))

tokens <- iv %>% unnest_tokens(word, intervencion_list) %>% group_by(index) %>% mutate(ni=n()) %>% filter(ni>20)
dfm <- tokens %>% count(index, word, sort=TRUE) %>% cast_dfm(index, word, n)
io <- iv %>% filter(index %in% dfm@docvars$docname_) %>% distinct(index,.keep_all=TRUE) %>%
  summarise(.[match(dfm@docvars$docname_, index), ])
stopifnot(nrow(io)==nrow(theta))
io$apellido <- relevel(as.factor(io$apellido), ref='otro')
io$sector   <- relevel(as.factor(io$sector),   ref='centro')

tm <- read.csv('topic_theme_map.csv', stringsAsFactors=FALSE)
themes <- setdiff(unique(tm$theme), 'Other')
res <- lapply(themes, function(th){
  cols <- tm$topic[tm$theme==th]
  io$prop <- rowSums(theta[, cols, drop=FALSE]) * 100      # percentage points
  fit <- lm(prop ~ apellido + sector + camara + Year, data=io)
  ct <- coeftest(fit, vcovCL(fit, cluster=~Hablante))
  data.frame(theme=th, n_topics=length(cols),
    elite=ct['apellidoelite','Estimate'], elite_se=ct['apellidoelite','Std. Error'],
    comun=ct['apellidocomun','Estimate'], comun_se=ct['apellidocomun','Std. Error'])
})
out <- do.call(rbind, res)
out <- out[order(out$elite - out$comun), ]
write.csv(out, OUT, row.names=FALSE)
message(paste(capture.output(print(format(out, digits=3))), collapse = "\n"))
message("\nsaved ", OUT)
