# 27 — Within-group labor & industry trajectory, 1910-1949 (R2, mobilization confound)
# Tests whether the elite-common agenda contrast in table_themes_main is an artifact of
# the period's secular agenda opening (FOCH, Socialist Workers' Party, Alessandri 1920).
# Reuses script 13's exact doc pipeline so the STM theta rows align (stopifnot guard).
# RUN FROM PROJECT ROOT (where intervenciones.csv and stm_model_285.rds live), as script 13.
# No stochastic element -> no seed needed (INV-14).
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

# Labor & industry theme = topics mapped in topic_theme_map.csv
tm <- read.csv('topic_theme_map.csv', stringsAsFactors=FALSE)
labor_topics <- tm$topic[tm$theme=='Labor & industry']
io$labor  <- rowSums(theta[, labor_topics, drop=FALSE]) * 100   # percentage points
io$decade <- (io$Year %/% 10) * 10
io$dec10  <- (io$decade - 1910)/10                              # 0..3 over 1910s-1940s
io$sector <- relevel(as.factor(io$sector), ref='centro')
io$camara <- as.factor(io$camara)
sub <- io %>% filter(Year>=1910, Year<=1949)

# ---- decade means by group ----
means <- sub %>% group_by(apellido, decade) %>%
  summarise(mean_labor=mean(labor), n=n(), .groups='drop') %>% arrange(apellido, decade)

# ---- party+chamber-adjusted within-group decade slope ----
adj_slope <- function(g){
  fit <- lm(labor ~ dec10 + sector + camara, data=sub %>% filter(apellido==g))
  ct  <- coeftest(fit, vcovCL(fit, cluster=~Hablante))
  ct['dec10', c('Estimate','Std. Error','Pr(>|t|)')]
}
sl_elite <- adj_slope('elite'); sl_comun <- adj_slope('comun')

# ---- pooled difference-in-slopes (common minus elite), net of party+chamber ----
ec <- sub %>% filter(apellido %in% c('elite','comun')); ec$apellido <- relevel(as.factor(ec$apellido), ref='elite')
fitp <- lm(labor ~ apellido*dec10 + sector + camara, data=ec)
ctp  <- coeftest(fitp, vcovCL(fitp, cluster=~Hablante))
diff <- ctp['apellidocomun:dec10', c('Estimate','Std. Error','Pr(>|t|)')]

out <- data.frame(
  quantity = c('elite_slope_per_decade','common_slope_per_decade','common_minus_elite_slope'),
  estimate = c(sl_elite[1], sl_comun[1], diff[1]),
  se       = c(sl_elite[2], sl_comun[2], diff[2]),
  p        = c(sl_elite[3], sl_comun[3], diff[3]))
write.csv(out,   'replication_repo/output/within_elite_trajectory.csv',       row.names=FALSE)
write.csv(means, 'replication_repo/output/within_elite_trajectory_means.csv', row.names=FALSE)

# ---- bare tabular for the online appendix (INV-13: no float/caption/notes) ----
wide <- means %>% filter(apellido %in% c('elite','comun')) %>%
  tidyr::pivot_wider(id_cols=decade, names_from=apellido, values_from=mean_labor) %>%
  mutate(gap = comun - elite) %>% arrange(decade)
lab <- c('1910'='1910s','1920'='1920s','1930'='1930s','1940'='1940s')
rows <- apply(wide, 1, function(r)
  sprintf("%s & %.1f & %.1f & %.1f \\\\", lab[as.character(r['decade'])],
          r['elite'], r['comun'], r['gap']))
tex <- c("\\begin{tabular}{lccc}", "\\toprule",
         "Decade & Elite & Common & Gap (Common $-$ Elite) \\\\", "\\midrule",
         rows, "\\bottomrule", "\\end{tabular}")
writeLines(tex, 'paper/tables/table_within_elite.tex')
cat("\nParty+chamber-adjusted labor&industry slope (pts/decade), 1910-1949:\n")
print(format(out, digits=3))
cat("\nsaved within_elite_trajectory.csv (+ _means.csv)\n")
