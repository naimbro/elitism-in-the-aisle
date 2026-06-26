# 36 — Referee SHOULD-3: seed / draw-count confirmation of the appendix §H.6 within-group
# slope test (the +0.84 / SE 0.29 / p=0.004 method-of-composition result from script 28,
# m1_withinelite_methodofcomposition.csv "diff" row = common-minus-elite labor-slope difference).
#
# This ISOLATES only the §H.6 within-group slope portion of script 28 (one interaction
# regression per draw on the 1910-1949 elite+comun subset) to avoid the expensive 11-theme
# Table-1 loop. It draws B=200 document-topic matrices from the STM variational posterior under
# an ALTERNATIVE seed (2025, vs script 28's 1925), then Rubin-combines on BOTH the first 50 draws
# (B=50 cell) and all 200 draws (B=200 cell) from the SAME seeded stream — so a single set.seed
# (INV-14) yields a seed change AND a draw-count change. Goal: confirm slope diff ~ +0.84,
# combined SE ~ 0.29, p ~ 0.004, topic-uncertainty variance share ~ 7%.
#
# Method of composition (Rubin's rules): Qbar = mean(est_b); Ubar = mean(clustered var_b);
#   Bvar = var(est_b) [topic-model uncertainty]; T = Ubar + (1+1/B)*Bvar; z = Qbar/sqrt(T).
# RUN FROM PROJECT ROOT (reads intervenciones.csv + stm_model_285.rds). Memory-batched.
suppressMessages({library(dplyr); library(tidytext); library(quanteda); library(stm); library(sandwich); library(lmtest)})
set.seed(2025)                                   # INV-14: alternative seed vs script 28's 1925
B <- 200L; BATCH <- 10L
deaccent <- function(x) chartr("ÁÉÍÓÚÜÑáéíóúüñ","AEIOUUNAEIOUUN",toupper(as.character(x)))

m <- readRDS('stm_model_285.rds'); K <- ncol(m$theta)
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
dfm <- tokens %>% count(index, word, sort=TRUE) %>% cast_dfm(index, word, n); rm(tokens); gc()
io <- iv %>% filter(index %in% dfm@docvars$docname_) %>% distinct(index,.keep_all=TRUE) %>%
  summarise(.[match(dfm@docvars$docname_, index), ])
stopifnot(nrow(io)==nrow(m$theta))

tm <- read.csv('topic_theme_map.csv', stringsAsFactors=FALSE)
labor_topics <- tm$topic[tm$theme=='Labor & industry']
io$sector <- relevel(as.factor(io$sector), ref='centro'); io$camara <- as.factor(io$camara)
io$Year <- as.numeric(io$Year)
io$dec10 <- ((io$Year %/% 10)*10 - 1910)/10
sidx <- which(io$Year>=1910 & io$Year<=1949 & io$apellido %in% c('elite','comun'))
sub <- io[sidx,]; sub$apellido <- relevel(factor(as.character(sub$apellido)), ref='elite')

# accumulators (common-minus-elite slope diff = interaction term apellidocomun:dec10)
H6_int <- numeric(B); H6_int_v <- numeric(B)
ndone <- 0L
while (ndone < B) {
  nb <- min(BATCH, B-ndone)
  d <- thetaPosterior(m, nsims=nb, type="Global")            # list length N, each nb x K
  for (b in 1:nb) {
    theta_b <- t(vapply(d, function(x) x[b,], numeric(K)))    # N x K draw
    sub$lab <- rowSums(theta_b[sidx, labor_topics, drop=FALSE]) * 100
    fp <- lm(lab ~ apellido*dec10 + sector + camara, data=sub)
    Vp <- vcovCL(fp, cluster=sub$Hablante)
    ndone <- ndone + 1L
    H6_int[ndone]   <- coef(fp)['apellidocomun:dec10']
    H6_int_v[ndone] <- Vp['apellidocomun:dec10','apellidocomun:dec10']
    cat("draw", ndone, "/", B, "done\n")
  }
  rm(d); gc()
}

rubin <- function(est, var){
  B <- length(est); Qbar<-mean(est); Ubar<-mean(var); Bv<-var(est)
  Tt<-Ubar+(1+1/B)*Bv; z<-Qbar/sqrt(Tt); p<-2*pnorm(-abs(z)); frac<-(1+1/B)*Bv/Tt
  c(slope_diff=Qbar, combined_se=sqrt(Tt), p=p, frac_topic_unc=frac)
}

cells <- list(c(seed=2025, B=50), c(seed=2025, B=200))
rows <- do.call(rbind, lapply(cells, function(cc){
  nB <- cc['B']; r <- rubin(H6_int[1:nB], H6_int_v[1:nB])
  data.frame(seed=cc['seed'], B=nB, slope_diff=r['slope_diff'], combined_se=r['combined_se'],
             p=r['p'], frac_topic_unc=r['frac_topic_unc'], row.names=NULL)
}))

dir.create('replication_repo/output', showWarnings=FALSE, recursive=TRUE)
write.csv(rows, 'replication_repo/output/should3_seed_robustness.csv', row.names=FALSE)

cat("\n=========  SHOULD-3: §H.6 within-group slope diff (common - elite), seed/B robustness  =========\n")
cat("(script 28 reference: seed 1925, B=50  ->  +0.84, combined SE 0.29, p=0.004, topic-unc ~7%)\n\n")
for (i in seq_len(nrow(rows))) cat(sprintf(
  "seed %d, B=%3d : slope diff %+.3f  (combined SE %.3f, p=%.4f)  topic-unc share %.1f%%\n",
  rows$seed[i], rows$B[i], rows$slope_diff[i], rows$combined_se[i], rows$p[i], 100*rows$frac_topic_unc[i]))
cat("\nsaved replication_repo/output/should3_seed_robustness.csv\n")
