## DEPRECATED for the 298 measure. This script reuses the saved estimateEffect (prep)
## from stm_prep_285.rds, which was computed under the 285 coding — it does NOT re-estimate
## the prevalence regression, so it reproduces the 285 topic contrast regardless of the
## current enduring_elite_FINAL.csv. Use 12b_stm_estimateEffect_298.R, which re-runs
## estimateEffect against the saved fitted model with the current coding.
suppressMessages({library(dplyr); library(tidytext); library(quanteda); library(stm)})
deaccent <- function(x) chartr("ÁÉÍÓÚÜÑáéíóúüñ","AEIOUUNAEIOUUN",toupper(as.character(x)))
prep <- readRDS('stm_prep_285.rds')

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

## rebuild the model's doc set (filter >20 tokens), same order as the fit
tokens <- iv %>% unnest_tokens(word, intervencion_list) %>% group_by(index) %>% mutate(ni=n()) %>% filter(ni>20)
dfm <- tokens %>% count(index, word, sort=TRUE) %>% cast_dfm(index, word, n)
io <- iv %>% filter(index %in% dfm@docvars$docname_) %>% distinct(index,.keep_all=TRUE) %>%
  summarise(.[match(dfm@docvars$docname_, index), ])
io$apellido <- relevel(as.factor(io$apellido), ref='otro')
io$sector   <- relevel(as.factor(io$sector),   ref='centro')
cat("docs:", nrow(io), "\n")

## design + means (party, chamber, year held at their means)
X <- model.matrix(~ apellido + sector + camara + Year, io)
xbar <- colMeans(X)
betas <- t(sapply(prep$parameters, function(tp) colMeans(do.call(rbind, lapply(tp, function(s) s$est)))))
stopifnot(ncol(betas) == ncol(X)); colnames(betas) <- colnames(X)
cat("design cols:", paste(colnames(X), collapse=', '), "\n")
## validation: extracted apellido coefs must match the saved estimateEffect table
saved <- read.csv('table1_topic_coefs_285.csv')
cat("coef-elite check (extracted vs saved, topics 31/53/59):",
    round(betas[c(31,53,59),'apellidoelite'],4), "vs", round(saved$coef_elite[c(31,53,59)],4), "\n")

mk <- function(lvl){ x<-xbar; x['apellidocomun']<-0; x['apellidoelite']<-0
                     if(lvl=='comun') x['apellidocomun']<-1; if(lvl=='elite') x['apellidoelite']<-1; x }
prev_e <- as.numeric(betas %*% mk('elite'))
prev_c <- as.numeric(betas %*% mk('comun'))

## v3 tercile rule on PARTY-ADJUSTED prevalence
te1 <- quantile(prev_e,1/3); tc1 <- quantile(prev_c,1/3)
elite_t <- which(prev_c<=tc1 & prev_e>=te1)
comun_t <- which(prev_e<=te1 & prev_c>=tc1)
terms <- read.csv('terms_stm_285.csv', stringsAsFactors=FALSE)
lab <- terms %>% arrange(desc(beta)) %>% group_by(topic) %>% slice(1:4) %>% summarise(w=paste(term,collapse='/'),.groups='drop')
labv <- setNames(lab$w, lab$topic)
ord_e <- elite_t[order(-(prev_e[elite_t]-prev_c[elite_t]))]
ord_c <- comun_t[order(-(prev_c[comun_t]-prev_e[comun_t]))]
cat("\n=========== TABLE 1 (v3-style, PARTY/CHAMBER/YEAR-ADJUSTED) ===========\n")
cat("\n--- Topics prevalent among ELITE surnames (net of party) ---\n")
for(k in ord_e) cat(sprintf("  T%-2d  %s\n", k, labv[as.character(k)]))
cat("\n--- Topics prevalent among COMMON surnames (net of party) ---\n")
for(k in ord_c) cat(sprintf("  T%-2d  %s\n", k, labv[as.character(k)]))
n<-max(length(ord_e),length(ord_c))
pad<-function(v) c(v, rep("",n-length(v)))
write.csv(data.frame(
  elite_topic =pad(sapply(ord_e,function(k)sprintf("T%d %s",k,labv[as.character(k)]))),
  common_topic=pad(sapply(ord_c,function(k)sprintf("T%d %s",k,labv[as.character(k)])))),
  'table1_v3style_adjusted.csv', row.names=FALSE)
cat("\nsaved table1_v3style_adjusted.csv\n")
