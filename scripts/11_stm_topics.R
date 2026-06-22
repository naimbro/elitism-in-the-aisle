library(dplyr)
library(tidytext)
library(quanteda)
library(stm)

## ===========================================================================
## stm_revised.r  — Table 1 (STM topic prevalence) with the 285-surname measure
## Edits vs original:
##  [E1] elite classification uses the 285 enduring-elite list (not old 65 col)
##  [E2] ELITE precedence over COMMON (paper's rule; original was common-first)
##  [E3] saves the fitted model (stm_model_285.rds) + estimateEffect (prep) so
##       Table 1 can be regenerated WITHOUT a refit
##  [E4] writes a tidy Table-1 table: per-topic elite/common coefficients
##  STM_EMITS env var controls EM iterations (default 75; set 2 for smoke test)
## ===========================================================================
deaccent <- function(x) chartr("ÁÉÍÓÚÜÑáéíóúüñ","AEIOUUNAEIOUUN",toupper(as.character(x)))
EMITS <- as.integer(Sys.getenv("STM_EMITS","75"))
cat("STM max.em.its =", EMITS, "\n")

intervenciones <- read.csv('intervenciones.csv', stringsAsFactors = FALSE)

## ---- sector ----
intervenciones <- intervenciones %>% mutate(sector = case_when(
  Partido %in% c('Partido Conservador','Partido Conservador Tradicionalista','Partido Conservador Social Cristiano','Partido Conservador Unido','Partido Liberal','Partido Liberal Democratico','Partido Liberal Doctrinario','Partido Liberal Progresista','Partido Liberal Unido','Partido Nacional o Monttvarista','Partido Nacional','Partido Agrario Laborista','Partido Nacional Socialista','Movimiento Nacional Socialista de Chile') ~ 'derecha',
  Partido %in% c('Partido Radical','Partido Radical de Chile','Partido Radical Independiente','Partido Democratico de Chile','Partido Social Republicano','Falange Nacional','Partido Accion Republicana','Partido Regionalista','Partido Agrario') ~ 'centro',
  Partido %in% c('Partido Obrero Socialista','Partido Socialista de Chile','Partido Socialista Popular','Partido Comunista de Chile','Partido Radical Socialista','Confederacion Republicana de Accion Civica de Obreros y Empleados','Partido Progresista Nacional','Union Social Republicana de Asalariados de Chile','Union Social Republicana de los Asalariados de Chile','Nueva Accion Publica','Vanguardia Popular Socialista','Partido Democratico del Pueblo','Partido Democrata','Partido Democratico') ~ 'izquierda',
  TRUE ~ 'otro'))
intervenciones$sector <- relevel(as.factor(intervenciones$sector), ref = 'centro')

## ---- [E1][E2] surname type with the 285-surname list, elite precedence ----
comunes <- deaccent(c('GONZALEZ','MUNOZ','DIAZ','ROJAS','PEREZ','SILVA','SOTO','MARTINEZ','LOPEZ','MORALES','CONTRERAS','RODRIGUEZ','SEPULVEDA','FUENTES','VALENZUELA','RAMIREZ','ESPINOZA','REYES','HERNANDEZ','GUTIERREZ','FLORES','CASTRO','TORRES','SANCHEZ','VASQUEZ','CASTILLO','FERNANDEZ','ARAYA','HERRERA','VARGAS','NUÑEZ','ALVAREZ','CARRASCO','GOMEZ','BRAVO','VERGARA','GARCIA','TAPIA','JARA','ZUÑIGA','ORELLANA','FIGUEROA','MIRANDA','RIQUELME','CAMPOS','MOLINA','RIVERA','GUZMAN','SANDOVAL','ORTIZ'))
elite_list <- deaccent(read.csv('enduring_elite_FINAL.csv', stringsAsFactors=FALSE)$surname)
PatN <- deaccent(intervenciones$Pat); MatN <- deaccent(intervenciones$Mat)
comun <- PatN %in% comunes | MatN %in% comunes
elite <- PatN %in% elite_list | MatN %in% elite_list
intervenciones$apellido <- ifelse(elite, 'elite', ifelse(comun, 'comun', 'otro'))
intervenciones$apellido <- relevel(as.factor(intervenciones$apellido), ref = 'otro')
print(intervenciones %>% distinct(Hablante, .keep_all=TRUE) %>% count(apellido))

## ---- tokens -> dfm ----
tokens <- intervenciones %>%
  unnest_tokens(word, intervencion_list) %>%
  group_by(index) %>% mutate(n_intervencion = n()) %>% filter(n_intervencion > 20)
dfm <- tokens %>% count(index, word, sort = TRUE) %>% cast_dfm(index, word, n)
rm(tokens); gc()
cat("dfm:", nrow(dfm), "docs x", ncol(dfm), "terms\n")

intervenciones_ordered <- intervenciones %>%
  filter(index %in% dfm@docvars$docname_) %>% distinct(index, .keep_all = TRUE) %>%
  summarise(.[match(dfm@docvars$docname_, index), ])

## ---- fit STM ----
n_k <- 80
topic_model <- stm(dfm, K = n_k, data = intervenciones_ordered, max.em.its = EMITS,
                   seed = 1, prevalence = ~ apellido + sector + camara + Year,
                   init.type = "Spectral")
saveRDS(topic_model, 'stm_model_285.rds')                       # [E3]
write.csv(tidy(topic_model), 'terms_stm_285.csv', row.names = FALSE)
write.csv(topic_model$theta, 'model_theta_285.csv', row.names = FALSE)

## ---- estimateEffect (Table 1) ----
intervenciones_ordered$apellido <- relevel(as.factor(intervenciones_ordered$apellido), ref='otro')
prep <- estimateEffect(1:n_k ~ apellido + sector + camara + Year, topic_model,
                       meta = intervenciones_ordered, uncertainty = "Global")
saveRDS(prep, 'stm_prep_285.rds')                               # [E3]

## ---- [E4] tidy per-topic elite/common coefficients -> Table 1 source ----
tab <- summary(prep)$tables
rows <- lapply(seq_along(tab), function(k){
  m <- tab[[k]]
  ge <- function(term, col) if (term %in% rownames(m)) m[term, col] else NA
  data.frame(topic=k,
             coef_comun=ge('apellidocomun','Estimate'), p_comun=ge('apellidocomun','Pr(>|t|)'),
             coef_elite=ge('apellidoelite','Estimate'), p_elite=ge('apellidoelite','Pr(>|t|)'))
})
table1 <- do.call(rbind, rows)
write.csv(table1, 'table1_topic_coefs_285.csv', row.names = FALSE)
cat("\n=== topics most ELITE-leaning (coef_elite>0) ===\n");  print(head(table1[order(-table1$coef_elite),],12))
cat("\n=== topics most COMMON-leaning (coef_comun>0) ===\n"); print(head(table1[order(-table1$coef_comun),],12))
cat("\nSaved: stm_model_285.rds, stm_prep_285.rds, table1_topic_coefs_285.csv, terms_stm_285.csv, model_theta_285.csv\n")
