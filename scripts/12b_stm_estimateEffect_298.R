## 12b — Re-run estimateEffect (STM Table 1) for the 298-surname measure.
## The fitted topic model (stm_model_285.rds) is word-driven and reused as-is; only the
## prevalence regression is re-estimated with the new apellido coding (this is the operation
## script 12 was MISSING — it reused the saved 285 estimateEffect). Outputs the party/chamber/
## year-adjusted topic contrast for the 298 measure.
suppressMessages({library(dplyr); library(tidytext); library(quanteda); library(stm)})
deaccent <- function(x) chartr("ÁÉÍÓÚÜÑáéíóúüñ","AEIOUUNAEIOUUN",toupper(as.character(x)))

intervenciones <- read.csv('intervenciones.csv', stringsAsFactors = FALSE)
intervenciones <- intervenciones %>% mutate(sector = case_when(
  Partido %in% c('Partido Conservador','Partido Conservador Tradicionalista','Partido Conservador Social Cristiano','Partido Conservador Unido','Partido Liberal','Partido Liberal Democratico','Partido Liberal Doctrinario','Partido Liberal Progresista','Partido Liberal Unido','Partido Nacional o Monttvarista','Partido Nacional','Partido Agrario Laborista','Partido Nacional Socialista','Movimiento Nacional Socialista de Chile') ~ 'derecha',
  Partido %in% c('Partido Radical','Partido Radical de Chile','Partido Radical Independiente','Partido Democratico de Chile','Partido Social Republicano','Falange Nacional','Partido Accion Republicana','Partido Regionalista','Partido Agrario') ~ 'centro',
  Partido %in% c('Partido Obrero Socialista','Partido Socialista de Chile','Partido Socialista Popular','Partido Comunista de Chile','Partido Radical Socialista','Confederacion Republicana de Accion Civica de Obreros y Empleados','Partido Progresista Nacional','Union Social Republicana de Asalariados de Chile','Union Social Republicana de los Asalariados de Chile','Nueva Accion Publica','Vanguardia Popular Socialista','Partido Democratico del Pueblo','Partido Democrata','Partido Democratico') ~ 'izquierda',
  TRUE ~ 'otro'))
intervenciones$sector <- relevel(as.factor(intervenciones$sector), ref = 'centro')

## ---- 298-surname coding (elite precedence) ----
comunes <- deaccent(c('GONZALEZ','MUNOZ','DIAZ','ROJAS','PEREZ','SILVA','SOTO','MARTINEZ','LOPEZ','MORALES','CONTRERAS','RODRIGUEZ','SEPULVEDA','FUENTES','VALENZUELA','RAMIREZ','ESPINOZA','REYES','HERNANDEZ','GUTIERREZ','FLORES','CASTRO','TORRES','SANCHEZ','VASQUEZ','CASTILLO','FERNANDEZ','ARAYA','HERRERA','VARGAS','NUÑEZ','ALVAREZ','CARRASCO','GOMEZ','BRAVO','VERGARA','GARCIA','TAPIA','JARA','ZUÑIGA','ORELLANA','FIGUEROA','MIRANDA','RIQUELME','CAMPOS','MOLINA','RIVERA','GUZMAN','SANDOVAL','ORTIZ'))
elite_list <- deaccent(read.csv('enduring_elite_FINAL.csv', stringsAsFactors=FALSE)$surname)
cat("elite list size:", length(unique(elite_list)), "\n")
PatN <- deaccent(intervenciones$Pat); MatN <- deaccent(intervenciones$Mat)
elite <- PatN %in% elite_list | MatN %in% elite_list
comun <- PatN %in% comunes | MatN %in% comunes
intervenciones$apellido <- ifelse(elite,'elite', ifelse(comun,'comun','otro'))
intervenciones$apellido <- relevel(as.factor(intervenciones$apellido), ref='otro')
cat("speaker-level apellido counts (298):\n"); print(intervenciones %>% distinct(Hablante,.keep_all=TRUE) %>% count(apellido))
cat("DOC-level apellido counts (298):\n"); print(intervenciones %>% count(apellido))

## ---- rebuild the exact doc set / order the model was fit on ----
tokens <- intervenciones %>% unnest_tokens(word, intervencion_list) %>%
  group_by(index) %>% mutate(n_intervencion=n()) %>% filter(n_intervencion>20)
dfm <- tokens %>% count(index, word, sort=TRUE) %>% cast_dfm(index, word, n)
rm(tokens); gc()
io <- intervenciones %>% filter(index %in% dfm@docvars$docname_) %>%
  distinct(index,.keep_all=TRUE) %>% summarise(.[match(dfm@docvars$docname_, index), ])
io$apellido <- relevel(as.factor(io$apellido), ref='otro')
io$sector   <- relevel(as.factor(io$sector),   ref='centro')
cat("dfm docs:", nrow(dfm), " io docs:", nrow(io), "\n")
cat("MODEL-doc apellido counts (298):\n"); print(io %>% count(apellido))

## ---- reuse fitted model; RE-ESTIMATE prevalence regression with 298 coding ----
topic_model <- readRDS('stm_model_285.rds')
prep <- estimateEffect(1:80 ~ apellido + sector + camara + Year, topic_model,
                       meta = io, uncertainty = "Global")
saveRDS(prep, 'stm_prep_298.rds')

## per-topic coefficients
tab <- summary(prep)$tables
ge <- function(m,term,col) if(term %in% rownames(m)) m[term,col] else NA
t1 <- do.call(rbind, lapply(seq_along(tab), function(k){ m<-tab[[k]]
  data.frame(topic=k, coef_comun=ge(m,'apellidocomun','Estimate'), p_comun=ge(m,'apellidocomun','Pr(>|t|)'),
             coef_elite=ge(m,'apellidoelite','Estimate'), p_elite=ge(m,'apellidoelite','Pr(>|t|)')) }))
write.csv(t1, 'table1_topic_coefs_298.csv', row.names=FALSE)

## ---- party/chamber/year-adjusted prevalence contrast (v3 tercile rule) ----
X <- model.matrix(~ apellido + sector + camara + Year, io); xbar <- colMeans(X)
betas <- t(sapply(prep$parameters, function(tp) colMeans(do.call(rbind, lapply(tp, function(s) s$est)))))
colnames(betas) <- colnames(X)
mk <- function(lvl){ x<-xbar; x['apellidocomun']<-0; x['apellidoelite']<-0
                     if(lvl=='comun') x['apellidocomun']<-1; if(lvl=='elite') x['apellidoelite']<-1; x }
prev_e <- as.numeric(betas %*% mk('elite')); prev_c <- as.numeric(betas %*% mk('comun'))
te1 <- quantile(prev_e,1/3); tc1 <- quantile(prev_c,1/3)
elite_t <- which(prev_c<=tc1 & prev_e>=te1); comun_t <- which(prev_e<=te1 & prev_c>=tc1)
terms <- read.csv('terms_stm_285.csv', stringsAsFactors=FALSE)
lab <- terms %>% arrange(desc(beta)) %>% group_by(topic) %>% slice(1:4) %>% summarise(w=paste(term,collapse='/'),.groups='drop')
labv <- setNames(lab$w, lab$topic)
ord_e <- elite_t[order(-(prev_e[elite_t]-prev_c[elite_t]))]
ord_c <- comun_t[order(-(prev_c[comun_t]-prev_e[comun_t]))]
cat("\n=== ELITE-distinctive topics (298, net of party) ===\n"); for(k in ord_e) cat(sprintf("  T%-2d %s\n",k,labv[as.character(k)]))
cat("\n=== COMMON-distinctive topics (298, net of party) ===\n"); for(k in ord_c) cat(sprintf("  T%-2d %s\n",k,labv[as.character(k)]))
n<-max(length(ord_e),length(ord_c)); pad<-function(v) c(v, rep("",n-length(v)))
write.csv(data.frame(
  elite_topic =pad(sapply(ord_e,function(k)sprintf("T%d %s",k,labv[as.character(k)]))),
  common_topic=pad(sapply(ord_c,function(k)sprintf("T%d %s",k,labv[as.character(k)])))),
  'table1_v3style_adjusted_298.csv', row.names=FALSE)
cat("\nsaved stm_prep_298.rds, table1_topic_coefs_298.csv, table1_v3style_adjusted_298.csv\n")
