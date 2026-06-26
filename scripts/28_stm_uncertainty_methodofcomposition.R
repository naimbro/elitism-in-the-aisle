# 28 — Referee M1: propagate STM topic-estimation uncertainty into the headline
# theme-level inference (Table 1) AND the within-group slope test (appendix §H.6),
# combined with legislator clustering, via the METHOD OF COMPOSITION (Rubin's rules).
#
# For each of B draws of the document-topic matrix theta from the STM variational
# posterior (thetaPosterior, type="Global" — the same mechanism estimateEffect uses):
#   (1) compute theme prevalence per document,
#   (2) run the SAME legislator-clustered OLS used in scripts 13 (Table 1) and 27 (§H.6),
#   (3) store the point estimate and its legislator-clustered variance.
# Combine across draws:  Qbar = mean(est_b);  Ubar = mean(var_b)  [clustered sampling var];
#   Bvar = var(est_b)  [topic-model uncertainty];  T = Ubar + (1+1/B)*Bvar;  z = Qbar/sqrt(T).
# This is exactly the method of composition: the OLS clustering handles non-independence of a
# legislator's speeches WITHIN each draw; the between-draw variance adds topic-estimation error.
#
# RUN FROM PROJECT ROOT (Windows R; reads intervenciones.csv + stm_model_285.rds).
# Stochastic (posterior draws) -> set.seed once at top (INV-14). Memory-batched.
suppressMessages({library(dplyr); library(tidytext); library(quanteda); library(stm); library(sandwich); library(lmtest)})
set.seed(1925)
B <- 50L; BATCH <- 10L                       # 50 posterior draws, in batches of 10
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

# theme membership matrix (K x nThemes), excluding 'Other'
tm <- read.csv('topic_theme_map.csv', stringsAsFactors=FALSE)
themes <- setdiff(sort(unique(tm$theme)), 'Other')
Tmat <- sapply(themes, function(th){ v<-numeric(K); v[tm$topic[tm$theme==th]]<-1; v })  # K x nThemes
labor_col <- which(themes=='Labor & industry')

io$sector <- relevel(as.factor(io$sector), ref='centro'); io$camara <- as.factor(io$camara)
io$apellido <- relevel(as.factor(io$apellido), ref='otro'); io$Year <- as.numeric(io$Year)
# subset for the §H.6 within-group slope test
io$dec10 <- ((io$Year %/% 10)*10 - 1910)/10
sidx <- which(io$Year>=1910 & io$Year<=1949 & io$apellido %in% c('elite','comun'))
sub <- io[sidx,]; sub$apellido <- relevel(factor(as.character(sub$apellido)), ref='elite')

# accumulators
H6_int <- numeric(0); H6_int_v <- numeric(0)           # common-minus-elite slope diff
H6_e <- numeric(0); H6_e_v <- numeric(0)               # elite slope
H6_c <- numeric(0); H6_c_v <- numeric(0)               # common slope
T1e <- matrix(0,0,length(themes)); T1e_v <- matrix(0,0,length(themes))   # Table1 elite contrast
T1c <- matrix(0,0,length(themes)); T1c_v <- matrix(0,0,length(themes))   # Table1 common contrast

getcl <- function(fit, cl, term){ V<-vcovCL(fit, cluster=cl); c(est=coef(fit)[term], var=V[term,term]) }

ndone <- 0L
while (ndone < B) {
  nb <- min(BATCH, B-ndone)
  d <- thetaPosterior(m, nsims=nb, type="Global")               # list length N, each nb x K
  for (b in 1:nb) {
    theta_b <- t(vapply(d, function(x) x[b,], numeric(K)))       # N x K draw
    prev <- (theta_b %*% Tmat) * 100                             # N x nThemes (percentage pts)
    # ---- §H.6 within-group slope test on the labor theme ----
    sub$lab <- prev[sidx, labor_col]
    fp <- lm(lab ~ apellido*dec10 + sector + camara, data=sub)
    Vp <- vcovCL(fp, cluster=sub$Hablante)
    H6_int <- c(H6_int, coef(fp)['apellidocomun:dec10']); H6_int_v <- c(H6_int_v, Vp['apellidocomun:dec10','apellidocomun:dec10'])
    fe <- lm(lab ~ dec10 + sector + camara, data=sub[sub$apellido=='elite',]); Ve<-vcovCL(fe,cluster=sub$Hablante[sub$apellido=='elite'])
    fc <- lm(lab ~ dec10 + sector + camara, data=sub[sub$apellido=='comun',]); Vc<-vcovCL(fc,cluster=sub$Hablante[sub$apellido=='comun'])
    H6_e<-c(H6_e,coef(fe)['dec10']); H6_e_v<-c(H6_e_v,Ve['dec10','dec10'])
    H6_c<-c(H6_c,coef(fc)['dec10']); H6_c_v<-c(H6_c_v,Vc['dec10','dec10'])
    # ---- Table 1: each theme contrast (elite & common vs other), legislator-clustered ----
    re<-numeric(length(themes)); rev<-numeric(length(themes)); rc<-numeric(length(themes)); rcv<-numeric(length(themes))
    for (j in seq_along(themes)) {
      io$prop <- prev[,j]
      ft <- lm(prop ~ apellido + sector + camara + Year, data=io)
      Vt <- vcovCL(ft, cluster=io$Hablante)
      re[j]<-coef(ft)['apellidoelite']; rev[j]<-Vt['apellidoelite','apellidoelite']
      rc[j]<-coef(ft)['apellidocomun']; rcv[j]<-Vt['apellidocomun','apellidocomun']
    }
    T1e<-rbind(T1e,re); T1e_v<-rbind(T1e_v,rev); T1c<-rbind(T1c,rc); T1c_v<-rbind(T1c_v,rcv)
    ndone <- ndone + 1L; cat("draw", ndone, "/", B, "done\n")
  }
  rm(d); gc()
}

# ---- Rubin combination ----
rubin <- function(est, var){
  Qbar<-mean(est); Ubar<-mean(var); Bv<-var(est); Tt<-Ubar+(1+1/length(est))*Bv
  z<-Qbar/sqrt(Tt); p<-2*pnorm(-abs(z)); frac<-(1+1/length(est))*Bv/Tt
  c(est=Qbar, se=sqrt(Tt), z=z, p=p, se_clustered_only=sqrt(Ubar), frac_topic_unc=frac)
}
cat("\n=================  §H.6 WITHIN-GROUP SLOPE TEST (method of composition)  =================\n")
r_int<-rubin(H6_int,H6_int_v); r_e<-rubin(H6_e,H6_e_v); r_c<-rubin(H6_c,H6_c_v)
cat(sprintf("elite slope  : %+.3f (combined SE %.3f, p=%.4f) [clustered-only SE %.3f]\n", r_e['est'],r_e['se'],r_e['p'],r_e['se_clustered_only']))
cat(sprintf("common slope : %+.3f (combined SE %.3f, p=%.4f) [clustered-only SE %.3f]\n", r_c['est'],r_c['se'],r_c['p'],r_c['se_clustered_only']))
cat(sprintf("DIFF (c-e)   : %+.3f (combined SE %.3f, p=%.4f) [clustered-only SE %.3f]  topic-unc share of var=%.1f%%\n",
            r_int['est'],r_int['se'],r_int['p'],r_int['se_clustered_only'],100*r_int['frac_topic_unc']))

cat("\n=================  TABLE 1 THEME CONTRASTS (method of composition)  =================\n")
t1 <- do.call(rbind, lapply(seq_along(themes), function(j){
  re<-rubin(T1e[,j],T1e_v[,j]); rc<-rubin(T1c[,j],T1c_v[,j])
  data.frame(theme=themes[j], elite=re['est'], elite_p=re['p'], comun=rc['est'], comun_p=rc['p'],
             contrast=re['est']-rc['est']) }))
t1 <- t1[order(t1$contrast),]; rownames(t1)<-NULL
print(format(t1, digits=3))

dir.create('replication_repo/output', showWarnings=FALSE, recursive=TRUE)
write.csv(rbind(elite=r_e, common=r_c, diff=r_int), 'replication_repo/output/m1_withinelite_methodofcomposition.csv')
write.csv(t1, 'replication_repo/output/m1_table1_methodofcomposition.csv', row.names=FALSE)
cat("\nB =", B, "draws.  saved m1_withinelite_methodofcomposition.csv + m1_table1_methodofcomposition.csv\n")
