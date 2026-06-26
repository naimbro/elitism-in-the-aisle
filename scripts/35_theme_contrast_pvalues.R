# 35 — Referee MUST-1: legislator-CLUSTERED p-value on the ELITE-COMMON CONTRAST for each
# Table 1 theme. Table 1 currently stars the elite-vs-other and common-vs-other emphasis
# columns, but the paper interprets the elite-MINUS-common CONTRAST column, which has no
# significance test. For each of the 11 themes we run the SAME theme-prevalence OLS used in
# scripts 13/28 (prop ~ apellido + sector + camara + Year, apellido factor elite/comun/otro
# with otro = reference), cluster SE by legislator (Hablante), and test the linear combination
# b_elite - b_comun using the full cluster-robust vcov:
#     se = sqrt( V[elite,elite] + V[comun,comun] - 2*V[elite,comun] ),  z = contrast/se.
#
# DETERMINISTIC (uses the fitted STM theta, no posterior draws) -> this is the gating M1
# deliverable and needs NO set.seed (INV-14). The method-of-composition contrast p (which would
# propagate STM topic uncertainty) is NOT computed here: script 28's draw loop did not store the
# within-draw elite-comun covariance, so it would require a full expensive posterior rerun; the
# clustered-only contrast p is the deliverable the referee gates on.
#
# RUN FROM PROJECT ROOT (reads intervenciones.csv + stm_model_285.rds from root, as script 13).
suppressMessages({library(dplyr); library(tidytext); library(quanteda); library(stm); library(sandwich); library(lmtest)})
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
io$camara   <- as.factor(io$camara)

tm <- read.csv('topic_theme_map.csv', stringsAsFactors=FALSE)
themes <- setdiff(unique(tm$theme), 'Other')
res <- lapply(themes, function(th){
  cols <- tm$topic[tm$theme==th]
  io$prop <- rowSums(theta[, cols, drop=FALSE]) * 100               # percentage points
  fit <- lm(prop ~ apellido + sector + camara + Year, data=io)
  V <- vcovCL(fit, cluster=~Hablante)
  be <- coef(fit)['apellidoelite']; bc <- coef(fit)['apellidocomun']
  contrast <- be - bc
  se <- sqrt(V['apellidoelite','apellidoelite'] + V['apellidocomun','apellidocomun']
             - 2*V['apellidoelite','apellidocomun'])
  z <- contrast/se; p <- 2*pnorm(-abs(z))
  data.frame(theme=th, contrast=unname(contrast), se_clustered=unname(se), p_clustered=unname(p))
})
out <- do.call(rbind, res)
out <- out[order(out$contrast), ]; rownames(out) <- NULL

dir.create('replication_repo/output', showWarnings=FALSE, recursive=TRUE)
write.csv(out, 'replication_repo/output/m1_contrast_pvalues.csv', row.names=FALSE)

cat("\n=========  TABLE 1 ELITE-COMMON CONTRAST: legislator-clustered test  =========\n")
print(format(out, digits=3))
nsig <- sum(out$p_clustered < 0.05)
cat(sprintf("\nThemes with individually significant contrast at 5%%: %d of %d.\n", nsig, nrow(out)))
cat("Most individual theme contrasts are NOT individually significant -> the paper must anchor\n")
cat("agenda inference on the slope/widening tests (within-elite trajectory, statecraft), not on\n")
cat("any single theme's contrast magnitude.\n")
cat("\nsaved replication_repo/output/m1_contrast_pvalues.csv\n")
