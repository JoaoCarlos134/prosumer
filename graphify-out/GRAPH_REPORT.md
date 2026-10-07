# Graph Report - prossumidor  (2026-10-06)

## Corpus Check
- 26 files · ~218,021 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1273 nodes · 2589 edges · 72 communities (57 shown, 15 thin omitted)
- Extraction: 88% EXTRACTED · 11% INFERRED · 1% AMBIGUOUS · INFERRED: 294 edges (avg confidence: 0.88)
- Token cost: 476,771 input · 0 output

## Community Hubs (Navigation)
- Irradiancia Medida vs NASA
- Visao Geral dos Modelos e Tarifas
- Construcao da Rede do Projeto
- Orquestradores das Rodadas
- Ranking FV das Casas v2
- Base de Modelagem e Economia
- Ranking das Usinas v1
- Geometria do Arranjo FV
- Ranking FV das Casas v1
- Ranking do Consumo v1
- Ranking do Consumo v2
- Relatorio HTML Autonomo
- Correcao do Regime B e Vizualizacoes
- Custo x Skill v1
- Preparacao dos Dados Horarios
- Skill por Dobra (origem movel)
- Moirai e Ensemble
- Tarifas ANEEL e Lei 14.300
- Anonimizacao e Diagnostico das Usinas
- Ranking das Usinas v2
- Pipeline Reprodutivel e Rede
- Dias de Exemplo Cascavel
- Custo x Skill v2
- Lote 2 de Fundacionais
- Gerador da Proposta do TCC
- Dias de Exemplo v1
- Redes Treinadas (NeuralForecast)
- Ambientes moirai e previsao
- Figura dos Regimes Meteorologicos
- Referencias e LightGBM
- Metrica Skill e Defeito do TiDE
- Downscaling e NASA Diaria
- Geracao das Figuras
- Protocolo do Benchmark e Ambientes
- Inversao de Familias entre Regimes
- Dados Abertos da ANEEL
- Clima x Modelo e B-curto
- Embarcado: SparseTSF e TFLite
- Avaliacao e Diebold-Mariano
- Protocolo como Semente da Biblioteca
- Fisica Errada em Curitiba
- Ambiente previsao e TTM
- Vies e Melhorias por Caso
- Estado v2 e Normalizacao so-Treino
- Achados dos Regimes A/C/B
- Regras de Validacao Temporal
- Metricas na Convencao FV
- Conclusao: o Clima Domina
- Fundacionais do Lote 2
- Testes de Auditoria do Protocolo
- Referencias e Rede VOSviewer
- Levantamento dos 127 Modelos
- Referencias Ingenuas e Skill
- Fundacionais Zero-Shot v1
- TFLite e Pre-processamento
- Autorizacao e Licenca
- Revisao Edge AI e OCR
- Energia em Edificacoes Inteligentes
- ResNet-1D Propria
- TinyML no Medidor
- Ambiente lote2
- NASA POWER Horario vs Diario
- Downscaling de Irradiancia
- Fragmento Isolado 63
- Fragmento Isolado 64
- Fragmento Isolado 65
- Fragmento Isolado 66
- Fragmento Isolado 68
- Fragmento Isolado 69
- Fragmento Isolado 70
- Fragmento Isolado 71

## God Nodes (most connected - your core abstractions)
1. `Figura (v1 corte unico): Ranking de usinas (Cascavel + Curitiba) - ganho de skill sobre a persistencia de ceu claro` - 47 edges
2. `Figura: Ranking de modelos - Geracao FV das 10 casas com FV (ganho sobre 'igual a ontem') [v1 corte unico]` - 36 edges
3. `Figure (v1 single-cut): Consumption of 20 houses - skill gain over 'igual a ontem'` - 35 edges
4. `Ranking order: 32 entries sorted by skill, best at top` - 34 edges
5. `Covariate regime A: history only (every entry marked (A), hollow markers)` - 33 edges
6. `Metrica skill = 1 - RMSE / RMSE da referencia (eixo x da figura v1 corte unico)` - 31 edges
7. `Testes de modelos de previsao (36 modelos, 3 casos)` - 29 edges
8. `Metric: skill = 1 - RMSE / RMSE of the reference (v1 single-cut)` - 24 edges
9. `Figura: regimes de entrada meteorologica nas usinas (dumbbell A/C/B)` - 24 edges
10. `Regime A: history-only inputs - every entry in this v1 panel is marked (A)` - 23 edges

## Surprising Connections (you probably didn't know these)
- `paper/protocolo_canonico.py (nunca criado)` --semantically_similar_to--> `scripts/comum.py (protocolo)`  [INFERRED] [semantically similar]
  docs/projeto/ia_solar/PLANO_ARTIGO.md → CLAUDE.md
- `Etapas E0-E8 do TCC (~580 h, 9 meses)` --references--> `Biblioteca prossumidor`  [INFERRED]
  docs/proposta/Proposta_TCC_prossumidor.pdf → README.md
- `Lorenzo-Fonseca et al. (2026), LSTM leve em Raspberry Pi (campus)` --semantically_similar_to--> `TFLite de 3,4 KB (MLP 16-8 int8, R2 0,8117)`  [INFERRED] [semantically similar]
  graphify-out/converted/Referencias_previsao_consumo_embarcado_718e8d95.md → docs/projeto/ia_solar/ESTADO_DO_PROJETO.md
- `Nunca usar train_test_split aleatorio (autocorrelacao 0,90)` --semantically_similar_to--> `Origem movel (retreino do zero em cada dobra)`  [INFERRED] [semantically similar]
  docs/projeto/ia_solar/LEIA-ME.md → experimentos/testes_previsao/LEIA-ME.md
- `Benchmark FV: estatistico x DL x zero-shot (7 anos de usina real)` --semantically_similar_to--> `Achado: fundacionais zero-shot lideram os tres casos`  [INFERRED] [semantically similar]
  graphify-out/converted/Visao_geral_modelos_previsao_7fd0849f.md → experimentos/testes_previsao/LEIA-ME.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Cadeia física que gera poa_estimada: geometria → Haurwitz → Erbs → HDKR → kc horário** — graphify_out_converted_documentacao_base_modelagem_b9eeb66b_geometria_solar_spencer, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_haurwitz, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_erbs, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_hdkr, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_poa_ceu_claro, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_kc_horario, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_poa_estimada [EXTRACTED 1.00]
- **O gargalo é a irradiância, não o modelo (ablação, vão A→B, sensor, fonte de clima)** — graphify_out_converted_documentacao_resultados_7ef0e129_ablacao_preditores, graphify_out_converted_documentacao_resultados_7ef0e129_sensor_substitui_nasa, legado_ia_solar_analise_irradiancia_inversa_leia_me_kc_nasa_r2_negativo, legado_ia_solar_analise_irradiancia_inversa_leia_me_fonte_horaria_melhor [INFERRED 0.85]
- **A escada de regimes das usinas (A < C-gfs < C < B-curto < B)** — experimentos_testes_previsao_leia_me_regime_a, experimentos_testes_previsao_leia_me_c_gfs, experimentos_testes_previsao_leia_me_regime_c, experimentos_testes_previsao_leia_me_b_curto, claude_regime_b, claude_lightgbm, experimentos_testes_previsao_leia_me_skill_bootstrap_dias [EXTRACTED 1.00]
- **Os seis defeitos corrigidos no caminho da v2** — experimentos_testes_previsao_leia_me_defeito_recorte_dobra, experimentos_testes_previsao_leia_me_defeito_tide_layernorm, experimentos_testes_previsao_leia_me_defeito_normalizacao_teste, experimentos_testes_previsao_leia_me_defeito_familias_figuras, experimentos_testes_previsao_leia_me_defeito_exclusao_figura_regimes, experimentos_testes_previsao_leia_me_defeito_memoria_time_moe, experimentos_testes_previsao_leia_me_test_auditoria [EXTRACTED 1.00]
- **Os oito modulos da biblioteca prossumidor** — docs_proposta_proposta_biblioteca_prossumidor_io, docs_proposta_proposta_biblioteca_prossumidor_qualidade, docs_proposta_proposta_biblioteca_prossumidor_fisica, docs_proposta_proposta_biblioteca_prossumidor_diagnostico, docs_proposta_proposta_biblioteca_prossumidor_previsao, docs_proposta_proposta_biblioteca_prossumidor_protocolo, docs_proposta_proposta_biblioteca_prossumidor_embarcado, docs_proposta_proposta_biblioteca_prossumidor_economia, docs_proposta_proposta_biblioteca_camada_dominio_fina [EXTRACTED 1.00]

## Communities (72 total, 15 thin omitted)

### Community 0 - "Irradiancia Medida vs NASA"
Cohesion: 0.06
Nodes (22): cv(), run(), calibra_k(), downscale_ml(), _erro(), irradiancia_inversa(), processa(), roda() (+14 more)

### Community 1 - "Visao Geral dos Modelos e Tarifas"
Cohesion: 0.06
Nodes (29): aba_homer(), escreve_tabela(), le_bandeiras(), le_fiscais(), le_tarifas(), monta_calendario(), processa(), aba_explicacao() (+21 more)

### Community 2 - "Construcao da Rede do Projeto"
Cohesion: 0.06
Nodes (24): camada(), carregar_semantica(), chave(), completar(), grava(), inventario(), main(), relativo() (+16 more)

### Community 4 - "Ranking FV das Casas v2"
Cohesion: 0.10
Nodes (46): Ranking Figure: PV Generation of 10 Houses with PV - Skill over 'igual a ontem', Case: House PV generation (10 houses with PV), day-ahead, 95% CI from per-day bootstrap (error bars), Family: Arvore / fisica (tree / physical models, blue), Ensemble (median of all models, black diamond), Family: Fundacional (time-series foundation model, green), Family: Rede treinada (trained network, orange), Family: Referencia (reference baselines, gray) (+38 more)

### Community 5 - "Base de Modelagem e Economia"
Cohesion: 0.05
Nodes (28): Base de 5 min do inversor Fronius × NASA POWER (620.278 registros, 28 colunas), Comparação de 13 algoritmos nas duas usinas, Documentação da base de modelagem (planilha consolidada), Correlação de Erbs (fração difusa), estado_sujeira — mediana móvel de 30 dias do PI, defasada 1 dia, Geometria solar (Spencer, equação do tempo, hora solar verdadeira), Modelo de céu claro de Haurwitz, Transposição HDKR para o plano inclinado (+20 more)

### Community 6 - "Ranking das Usinas v1"
Cohesion: 0.11
Nodes (40): Figura (v1 corte unico): Ranking de usinas (Cascavel + Curitiba) - ganho de skill sobre a persistencia de ceu claro, Caso usinas fotovoltaicas: Cascavel + Curitiba (previsao day-ahead), Chronos-2 [figura v1 corte unico, usinas; regimes: A e B; B ~0.44; A ~0.06], Chronos-Bolt-small [figura v1 corte unico, usinas; regimes: A; A ~0.09], DLinear [figura v1 corte unico, usinas; regimes: A; A ~-0.07], Dot plot ordenado por skill com IC 95%, cor = familia e preenchimento = regime, Ensemble-mediana (mediana de todos os modelos) [figura v1 corte unico, usinas; regimes: A e B; B ~0.50 (1o lugar geral); A ~0.11 (melhor do regime A)], Familia: Arvore / fisica - azul (+32 more)

### Community 7 - "Geometria do Arranjo FV"
Cohesion: 0.10
Nodes (20): poa(), r2(), evaluate(), r2_5(), r2_d(), obj(), metrics(), cell_temp_faiman() (+12 more)

### Community 8 - "Ranking FV das Casas v1"
Cohesion: 0.09
Nodes (33): Figura: Ranking de modelos - Geracao FV das 10 casas com FV (ganho sobre 'igual a ontem') [v1 corte unico], Caso de estudo: geracao fotovoltaica das 10 casas com FV, Familia Arvore / fisica (azul), Familia Ensemble (mediana de todos, losango preto), Familia Fundacional (foundation models de series temporais, verde), Familia Rede treinada (deep learning treinado nos dados, laranja), Familia Referencia (baselines ingenuos, cinza), Intervalo de confianca 95% por bootstrap por dia (barras de erro do ranking) (+25 more)

### Community 9 - "Ranking do Consumo v1"
Cohesion: 0.17
Nodes (33): Figure (v1 single-cut): Consumption of 20 houses - skill gain over 'igual a ontem', Case: aggregated consumption of 20 houses, day-ahead forecast (v1 single-cut), Uncertainty: 95% confidence interval bars, bootstrap by day (v1 single-cut), Model family: Arvore / fisica (tree-based / physical, blue), Model family: Ensemble - median of all models (black diamond), Model family: Fundacional (pretrained time-series foundation models, green), Model family: Rede treinada (locally trained deep nets, orange), Model family: Referencia (naive baselines, gray) (+25 more)

### Community 10 - "Ranking do Consumo v2"
Cohesion: 0.07
Nodes (31): Caso de avaliacao: consumo de 20 residencias, Chronos-2 — 10o lugar, skill ~ 0.182 (fundacional), Chronos-Bolt-small — 6o lugar, skill ~ 0.190 (fundacional), DLinear — skill ~ 0.08, pior modelo treinado do campo, Ensemble-mediana (mediana de todos os modelos) — 9o lugar, skill ~ 0.188, Familia: Arvore / fisica, Familia: Fundacional (foundation models zero-shot), Familia: Rede treinada (deep learning treinado no dataset) (+23 more)

### Community 11 - "Relatorio HTML Autonomo"
Cohesion: 0.11
Nodes (9): b64(), fig(), b64(), fig(), cell(), b64(), fig(), caminho() (+1 more)

### Community 12 - "Correcao do Regime B e Vizualizacoes"
Cohesion: 0.17
Nodes (3): save(), save(), save()

### Community 13 - "Custo x Skill v1"
Cohesion: 0.17
Nodes (19): Figura v1 (corte unico): custo computacional x skill (3 paineis), Cenario A: so historico (marcador vazado) - v1, Cenario B: + clima do dia (marcador preenchido) - v1, Familia 'Fundacional' (verde, zero-shot) - v1 corte unico, Familia 'Rede treinada' (laranja) - v1 corte unico, Metrica skill (ganho sobre baseline, eixo Y) - v1 corte unico, Chronos-Bolt-small (fundacional, ~40 s, skill ~0.19) - v1, KAN (melhor skill em FV das casas, ~0.17) - v1 (+11 more)

### Community 14 - "Preparacao dos Dados Horarios"
Cohesion: 0.11
Nodes (6): preenche_por_hora(), seasonal_cv(), dp(), pack(), tabela(), prep()

### Community 15 - "Skill por Dobra (origem movel)"
Cohesion: 0.16
Nodes (17): 3 dobras das casas (out, nov-dez, dez; ~31 dias cada), 5 dobras das usinas (ago-set, out-nov, dez-jan, jan-abr, abr-mai; ~61 dias cada), Figura: Origem movel - skill em cada dobra (3 paineis), LightGBM (consumo das casas: 0,197 / 0,209 / 0,209), Mediana de todos os modelos (linha preta de referencia nos paineis das casas), Metrica: skill na dobra (eixo y de todos os paineis), Origem movel (rolling origin) com retreino no inicio de cada dobra, Painel 3: Consumo das casas (skill ~0,19-0,21) (+9 more)

### Community 16 - "Moirai e Ensemble"
Cohesion: 0.12
Nodes (3): carrega(), exog_previsao(), ghi_ceu_claro()

### Community 17 - "Tarifas ANEEL e Lei 14.300"
Cohesion: 0.10
Nodes (8): Pendencia: COSIP e PIS/COFINS efetivo, ICMS do Parana mudou duas vezes no periodo, Lei 14.300 e direito adquirido das duas usinas, Contexto tarifario brasileiro (TUSD/TE, bandeiras, ICMS, Lei 14.300), prossumidor.economia, Ambiente lote2 (Toto 2.0, TiRex-2, TabPFN-TS), Ambiente lote2_hf (Sundial, Timer-XL, Time-MoE), Ambiente moirai (Python 3.11, uni2ts, torch 2.4)

### Community 18 - "Anonimizacao e Diagnostico das Usinas"
Cohesion: 0.12
Nodes (14): Pendencia: geometria do telhado de Curitiba, Usina Cascavel (3,96 kWp), Usina Curitiba (~9,6 kWp), Diagnostico Curitiba: falha da string 1 e reconfiguracao, Diagnostico Cascavel: sujeira progressiva, nao degradacao, dicionario_colunas.csv (28 colunas, unidade e faltantes), Dois rastreadores MPPT: uma string controla a outra, Projeto IA Solar (Cascavel e Curitiba) (+6 more)

### Community 19 - "Ranking das Usinas v2"
Cohesion: 0.15
Nodes (16): Caso de Estudo Usinas FV (Cascavel 3,96 kWp + Curitiba ~9,6 kWp), Familia Arvore / Fisica (azul): LightGBM, linear_fisico, Familia Ensemble (losango preto): mediana de todos os modelos, Familia Fundacional (verde): foundation models de series temporais, Figura: Ranking de Modelos - Usinas (Cascavel + Curitiba), Chronos-2 (ultimo em B ~0,445; penultimo em C ~0,28), Ensemble-mediana (lider em B ~0,52 e em C ~0,37; topo de A ~0,12), LightGBM (presente nos tres regimes) (+8 more)

### Community 20 - "Pipeline Reprodutivel e Rede"
Cohesion: 0.12
Nodes (10): Pipeline reprodutivel do bruto ao relatorio (42 etapas), analise/comum/scripts/caminhos.py (funcao caminho()), Analise de rede do projeto (1.342 nos, 2.570 arestas), Cadeia de linhagem de 14 passos (NASA -> relatorio), Camada de linhagem de dados (01_linhagem.py), frame5.parquet (no mais conectado, nao existe no disco), Graphify (camada de codigo do grafo), Leiden (deteccao de comunidades) (+2 more)

### Community 21 - "Dias de Exemplo Cascavel"
Cohesion: 0.19
Nodes (15): Curva horaria de geracao (kWh na hora, 5h-20h), Estratificacao de dias por condicao de ceu (limpo/tipico/nublado), Figura: Dias de Exemplo Cascavel (real vs previsto), Modelo Ensemble-mediana (regimes B e C), Modelo baseline persist_ceu_claro (regime A), Modelo TiRex-2 (regime A), Painel 1: 04/01/2026 - dia limpo, Painel 3: 17/11/2025 - dia nublado (+7 more)

### Community 22 - "Custo x Skill v2"
Cohesion: 0.21
Nodes (13): Familia: redes treinadas (laranja, treino por dobra), Figura: custo computacional x skill (3 paineis), LightGBM ausente da figura (roda em segundos, tempo nao medido), Referencias e linear fisico ausentes da figura, Metrica skill (eixo Y), Tempo total, todas as dobras (s, CPU) - eixo X log, Painel: Usinas, Protocolo de dobras: 5 dobras nas usinas, 3 nas casas; fundacionais sem treino (+5 more)

### Community 23 - "Lote 2 de Fundacionais"
Cohesion: 0.24
Nodes (15): Regime A (so historico), Toto-2.0-313m, Achado: fundacionais zero-shot lideram os tres casos, Lote 2 (geracao seguinte de fundacionais, 05/10/2026), Moirai-MoE-small, Sundial-128m, Time-MoE-50M, Timer-XL-84m (+7 more)

### Community 25 - "Dias de Exemplo v1"
Cohesion: 0.18
Nodes (13): Figure (v1 single-cut): Cascavel example days - observed vs forecast hourly PV generation, 3 panels, Scenario/feature-set suffixes (A) and (B) distinguishing forecast input configurations, Chronos-Bolt-small (A) - foundation time-series forecaster (green curve), Observed hourly generation curve 'real' (kWh na hora, black reference line), Clear-day regime panel (dia limpo, 04/01/2026, peak ~3.35 kWh/h), Cloudy-day regime panel (dia nublado, 17/11/2025, suppressed ~1.7 kWh/h peak), Typical-day regime panel (dia tipico, 27/08/2025, double-humped ~2.7 kWh/h peak), Ensemble-mediana (A) - median ensemble, configuration A (blue curve) (+5 more)

### Community 26 - "Redes Treinadas (NeuralForecast)"
Cohesion: 0.13
Nodes (6): anota(), para_janelas(), roda_nf(), SparseTSF, treina_proprio(), janelas()

### Community 27 - "Ambientes moirai e previsao"
Cohesion: 0.13
Nodes (16): Ambiente moirai (Python 3.11, torch 2.4.1+cpu) — Moirai 2.0 e Moirai-MoE, uni2ts 2.0.0 (implementação do Moirai), neuralforecast 3.1.9 (redes treinadas: NHITS, TiDE, TFT, LSTM, GRU, KAN…), Chronos-Bolt-small, DLinear, iTransformer, KAN, Moirai 2.0 (+8 more)

### Community 28 - "Figura dos Regimes Meteorologicos"
Cohesion: 0.13
Nodes (15): Figura: regimes de entrada meteorologica nas usinas (dumbbell A/C/B), Metrica: skill sobre a persistencia de ceu claro (eixo x, -0.2 a 0.5), Ensemble-mediana, GRU, KAN, LightGBM, linear_fisico, LSTM (+7 more)

### Community 29 - "Referencias e LightGBM"
Cohesion: 0.19
Nodes (8): lgbm(), linear_fisico(), matriz(), roda(), salva(), tabela_features(), dias_teste(), grava()

### Community 30 - "Metrica Skill e Defeito do TiDE"
Cohesion: 0.13
Nodes (11): Mediana de todos os modelos, Skill = 1 - RMSE/RMSE da referencia, NeuralForecast / Darts, OpenSTEF 4.0 (exportar, nao competir), prossumidor.previsao, TiDE, Aba Bibliotecas (40 bibliotecas de previsao), Darts (+3 more)

### Community 31 - "Downscaling e NASA Diaria"
Cohesion: 0.13
Nodes (12): Duas coordenadas a 19 km caem na mesma celula da NASA, NASA POWER diaria le 3,2% abaixo (piso de erro), Serie horaria da NASA termina em 31/05/2026 (~15% do teste), Um sensor de irradiancia substitui toda a NASA POWER (+0,22), Artigo A: a qualidade da entrada, nao o algoritmo, limita a estimativa FV, Referencia fisica de base (pvlib ou PVWatts), Fonte de satelite no lugar da NASA (CAMS, NSRDB, ERA5), Irradiancia medida em solo (INMET, piranometro) (+4 more)

### Community 32 - "Geracao das Figuras"
Cohesion: 0.23
Nodes (9): custo(), dias_exemplo(), familia(), legenda_regimes(), limpa(), marca(), por_dobra(), ranking() (+1 more)

### Community 33 - "Protocolo do Benchmark e Ambientes"
Cohesion: 0.14
Nodes (12): 01_prepara_dados.py (nao roda no repo exportado), Benchmark de previsao do dia seguinte, Quatro ambientes Python congelados, Regime C (previsao do tempo real da vespera), Diagnostico C-gfs, As 20 casas (dataset de origem desconhecida), As casas sao do hemisferio norte (provavelmente Europa), prossumidor.qualidade (+4 more)

### Community 34 - "Inversao de Familias entre Regimes"
Cohesion: 0.18
Nodes (12): Familia Rede Treinada (laranja), DLinear (pior do ranking, skill ~-0,33 no regime A), GRU (bom em B ~0,47, negativo em A ~-0,13), iTransformer (skill ~-0,24 no regime A), KAN, LSTM (bom em B ~0,48, negativo em A ~-0,18), NHITS, ResNet-1D (melhor rede treinada no regime A ~0,11) (+4 more)

### Community 35 - "Dados Abertos da ANEEL"
Cohesion: 0.27
Nodes (6): bandeiras(), busca(), cacheado(), componentes_b1(), num(), tarifas_copel()

### Community 36 - "Clima x Modelo e B-curto"
Cohesion: 0.17
Nodes (10): Achado: o clima importa ~10x mais que o modelo, Regime B (clima NASA do proprio dia, teto), Diagnostico B-curto, Achado: falta qualidade de previsao, nao treino mais longo, B-curto (B com treino cortado onde C comeca), scripts/comum.py (datas, regimes, dobras, janelas), Melhoria: previsao do tempo por IA (Aurora, GraphCast, WeatherNext), comum.normaliza_por_treino (+2 more)

### Community 37 - "Embarcado: SparseTSF e TFLite"
Cohesion: 0.21
Nodes (10): SparseTSF (32 parametros), LiteRT (TFLite) e emlearn, prossumidor.embarcado, Achado: a mediana e robusta mas nem sempre a melhor (9a de 32 no consumo), Tsoukas et al. (2024), A Review on the emerging technology of TinyML, Moura et al. (2026), previsao mensal no ESP32-S3, Frameworks de implantacao embarcada, Poda de redes (pruning) (+2 more)

### Community 38 - "Avaliacao e Diebold-Mariano"
Cohesion: 0.26
Nodes (7): avalia(), diebold_mariano(), holm(), metricas(), real(), skill_ic(), dobras()

### Community 39 - "Protocolo como Semente da Biblioteca"
Cohesion: 0.22
Nodes (7): 05_avalia.py (metricas), scripts/comum.py (protocolo), Diebold-Mariano com correcao de Holm, Etapa E1 do TCC (esqueleto do pacote, contratos, CI), Fundacao do pacote src/prossumidor/ (etapa E1), prossumidor.protocolo, Ambiente previsao (Python 3.12, quase tudo)

### Community 40 - "Fisica Errada em Curitiba"
Cohesion: 0.20
Nodes (10): Base de modelagem (620.278 linhas, 28 colunas), Eficiencia do inversor > 1 por falta de simultaneidade, HistGradientBoosting (modelo escolhido, R2 0,7609), NASA POWER horaria: carimbo LST alinha em -55 min, poa_estimada (uma coluna entrega 99,6% do R2), Exportacao de 5 min do inversor Fronius, analise/comum/scripts/solar.py (geometria e transposicao), prossumidor.io (+2 more)

### Community 41 - "Ambiente previsao e TTM"
Cohesion: 0.18
Nodes (11): TTM (3M parametros, roda em CPU), Ambiente previsao (Python 3.12, torch 2.11 CPU) — quase tudo, chronos-forecasting 2.3.2, granite-tsfm (IBM, git pin) — implementação do TTM, lightgbm 4.7.0 (pinado em previsao e lote2), timesfm 3.0.2, tirex-ts 1.4.2, toto-ts 0.2.0 (Toto 1.0) (+3 more)

### Community 42 - "Vies e Melhorias por Caso"
Cohesion: 0.20
Nodes (9): Tres casos: usinas, FV das casas, consumo das casas, Melhoria: estimar a localizacao das casas pelo perfil diario, Vies dos fundacionais no consumo (~-20%), Aba Benchmarks (12 benchmarks da area), Benchmark FV: estatistico x DL x zero-shot (7 anos de usina real), FETS (benchmark de energia), fev-bench, GIFT-Eval (+1 more)

### Community 43 - "Estado v2 e Normalizacao so-Treino"
Cohesion: 0.22
Nodes (7): Estado 06/10/2026: v2 + lote 2 completos em GPU, comum.normaliza_por_treino, roda_lote2.py (lote 2 + ensemble), roda_v2.py (fila da v2), KAN (Kolmogorov-Arnold), Testes v1 (33 modelos, 3 casos, corte unico), xLSTM e variantes (xLSTMTime, xLSTM-Mixer)

### Community 44 - "Achados dos Regimes A/C/B"
Cohesion: 0.20
Nodes (10): LightGBM global, Achado: o C fecha 62-71% do vao A->B, Achado: nas usinas quem decide e o clima, nao o modelo, Achado: ECMWF ganha do GFS, C-gfs (GFS no lugar do ECMWF), ECMWF IFS 0,25 graus, Open-Meteo Previous Runs (arquivo de previsoes), Regime C (previsao real da vespera, regime operacional) (+2 more)

### Community 45 - "Regras de Validacao Temporal"
Cohesion: 0.20
Nodes (4): Plano de publicacao (dois artigos, nao um), paper/protocolo_canonico.py (nunca criado), Arquivar versao com DOI no Zenodo, Diebold-Mariano por dia com Holm (quem empata com o melhor)

### Community 46 - "Metricas na Convencao FV"
Cohesion: 0.20
Nodes (9): Metricas na convencao FV (nRMSE, nMAE, MBE, skill score), Yang et al. (2020), verificacao de previsoes solares deterministicas, resultados/metricas.csv e CSVs de metricas, Persistencia de ceu claro (referencia das usinas), Persistencia 'igual a ontem' (referencia das casas), Skill com IC 95% por bootstrap de dias inteiros, Aba Encontrados (127 modelos e motivos de exclusao), Aba Testados (36 modelos, 131 combinacoes caso/regime) (+1 more)

### Community 47 - "Conclusao: o Clima Domina"
Cohesion: 0.27
Nodes (9): Dispersao entre modelos comprimida no regime C (~0.26-0.38) e ampla no regime A (~-0.17 a 0.14), ECMWF IFS (fonte NWP day-ahead por tras do regime C), Fechamento do gap A->B pelo regime C: 72% da distancia (mediana dos modelos), Skill negativa no regime A para varios modelos (LSTM ~-0.17, GRU ~-0.13, TiDE ~-0.06, KAN ~-0.05), Regime A: so historico (circulo vazado, pior), Regime B: + clima do dia (teto) - circulo preto, previsao perfeita, Regime C: + previsao do tempo real (quadrado azul, day-ahead operacional), Teto B homogeneo entre modelos (~0.42-0.52), com linear_fisico e Chronos-2 abaixo (+1 more)

### Community 48 - "Fundacionais do Lote 2"
Cohesion: 0.33
Nodes (8): em_lotes(), hf_causal(), f(), moirai_moe(), tabpfn_ts(), tirex2(), toto2(), f()

### Community 50 - "Referencias e Rede VOSviewer"
Cohesion: 0.22
Nodes (6): 1Referencias_projetoIA.xlsx (71 referencias), rede_keywords_vosviewer.json, Referencias_previsao_consumo_embarcado.xlsx (15 artigos), Revisao de literatura e levantamento de modelos, smart_buildings.docx (rascunho da revisao Edge AI), Visao_geral_modelos_previsao.xlsx (127 entradas, sem resultados)

### Community 51 - "Levantamento dos 127 Modelos"
Cohesion: 0.25
Nodes (6): Modelos_previsao_geracao_consumo.xlsx (levantamento de 28/09/2026), Cobertura das familias de modelos (levantamento x testados), Tan et al., NeurIPS 2024 (remover o LLM nao piora), DeepAR, Levantamento de 127 modelos (28/09/2026), TimesNet

### Community 52 - "Referencias Ingenuas e Skill"
Cohesion: 0.25
Nodes (8): Familia: Referencia (baselines ingenuos), Metrica skill = 1 - RMSE / RMSE da referencia, persist_24h — referencia 'igual a ontem' (skill = 0 por construcao), semanal_168h — baseline sazonal semanal (skill ~ -0.13, unico abaixo da referencia), Baselines ingenuos: media_7d (~0,03), persist_24h (~-0,09), semanal_168h (~-0,29), Familia Referencia (cinza): persist_ceu_claro, persist_24h, media_7d, semanal_168h, Intervalo de Confianca 95% por bootstrap por dia, Referencia: persistencia de ceu claro (persist_ceu_claro)

### Community 53 - "Fundacionais Zero-Shot v1"
Cohesion: 0.36
Nodes (6): chronos2(), chronos_bolt(), em_lotes(), tirex(), toto(), ttm()

### Community 54 - "TFLite e Pre-processamento"
Cohesion: 0.25
Nodes (7): preprocessamento_<usina>_<conjunto>.json, Verificacao dos 32 modelos TFLite a partir do arquivo, TFLite de 3,4 KB (MLP 16-8 int8, R2 0,8117), ~27 saidas de analise que nenhum script le, Os 32 TFLite nunca carregados de volta por script, Lorenzo-Fonseca et al. (2026), LSTM leve em Raspberry Pi (campus), Plataformas de hardware embarcado (SBC, microcontroladores, NPU)

### Community 55 - "Autorizacao e Licenca"
Cohesion: 0.33
Nodes (4): gera_proposta_tcc.py (gera o PDF, precisa de reportlab), Proposta da biblioteca prossumidor e do TCC, Decisoes pedidas a gestao (secao 10: titularidade e licenca), Etapas E0-E8 do TCC (~580 h, 9 meses)

### Community 56 - "Revisao Edge AI e OCR"
Cohesion: 0.33
Nodes (7): Artigo OCR (ICIT 2027), Comunidade OCR + revisao Edge AI (21 artigos em comum), Computacao de borda para edificacoes inteligentes, IA explicavel na borda, Lacunas de pesquisa e direcoes futuras, OCR para leitura automatica de hidrometros, Revisao Edge AI em edificacoes inteligentes

### Community 57 - "Energia em Edificacoes Inteligentes"
Cohesion: 0.38
Nodes (7): LSTM e GRU, Aguilar et al. (2021), revisao sistematica de IA em autogestao de energia, Gestao de energia em edificacoes inteligentes, Jayashankara et al. (2023), CNN+GRU para previsao horaria, Planilha-mestre de referencias da revisao Edge AI, Saberi et al. (2024), Multi-Agent Deep Constrained Q-Learning, Yu et al. (2021), revisao de DRL para gestao de energia predial

### Community 59 - "TinyML no Medidor"
Cohesion: 0.33
Nodes (7): Almaini et al. (2025), TinyML no medidor com privacidade, John & P (2026), EELNet comprimida em Raspberry Pi 5 / Jetson Orin Nano, Kandil & McArthur (2026), regressao simbolica para carga de resfriamento, Li et al. (2024), federated split learning em medidores (192 KB SRAM), Previsao de consumo com IA embarcada (15 artigos), Aprendizado federado na borda, Destilacao de conhecimento

### Community 60 - "Ambiente lote2"
Cohesion: 0.50
Nodes (5): Ambiente lote2 (Python 3.12, torch 2.14.1) — Toto 2.0, TiRex-2, TabPFN-TS, tabpfn-time-series 1.3.0 (ficou de fora em CPU), tirex-2 (git pin NX-AI/tirex-2), toto-2 2.0.0, xlstm 2.0.6 (base do TiRex)

## Ambiguous Edges - Review These
- `Cenario A: so historico (marcador vazado) - v1` → `KAN (melhor skill em FV das casas, ~0.17) - v1`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/custo_x_skill.png · relation: conceptually_related_to
- `KAN (melhor skill em FV das casas, ~0.17) - v1` → `NHITS (FV das casas, skill ~0.14) - v1`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/custo_x_skill.png · relation: semantically_similar_to
- `TFT (Usinas, skill ~0.49 ao maior custo ~1200 s) - v1` → `TSMixerx (Usinas, skill ~0.48 no cenario B) - v1`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/custo_x_skill.png · relation: semantically_similar_to
- `Scenario/feature-set suffixes (A) and (B) distinguishing forecast input configurations` → `Cloudy-day regime panel (dia nublado, 17/11/2025, suppressed ~1.7 kWh/h peak)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/dias_exemplo_cascavel.png · relation: conceptually_related_to
- `Clear-day regime panel (dia limpo, 04/01/2026, peak ~3.35 kWh/h)` → `v1 single-cut (corte unico) evaluation protocol - superseded by v2 rolling origin`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/dias_exemplo_cascavel.png · relation: conceptually_related_to
- `KAN (rank 11, skill ~0.111)` → `TiDE (rank 10, skill ~0.112)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/ranking_casas_prod.png · relation: semantically_similar_to
- `Day-ahead forecasting benchmark, protocol v2` → `Ranking Figure: PV Generation of 10 Houses with PV - Skill over 'igual a ontem'`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/ranking_casas_prod.png · relation: conceptually_related_to
- `TiDE [figura v1 corte unico, usinas; regimes: A e B; B ~0.07 (anomalo, fora do bloco B); A ~-0.03]` → `Anomalia: TiDE (B) aparece em ~0.07, fora do bloco B e no meio do bloco A - possivel falha de treino ou de uso das covariaveis futuras`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/ranking_usinas.png · relation: rationale_for
- `DLinear — skill ~ 0.08, pior modelo treinado do campo` → `SparseTSF — 7o lugar, skill ~ 0.189 (melhor rede treinada)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/ranking_casas_cons.png · relation: semantically_similar_to
- `LightGBM — 1o lugar, skill ~ 0.205 (arvore)` → `Time-MoE-50M — 2o lugar, skill ~ 0.203 (fundacional)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/ranking_casas_cons.png · relation: conceptually_related_to
- `Protocolo v1 de corte unico (single-cut), anterior ao v2 rolling-origin` → `Insight: o ganho maximo sobre 'igual a ontem' e modesto (~16%), e varios modelos (DLinear, LSTM, semanal_168h) ficam abaixo da referencia`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/ranking_casas_prod.png · relation: conceptually_related_to
- `Regime B: + clima do dia (teto) - presente apenas na legenda, sem pontos nesta figura` → `Figura: Ranking de modelos - Geracao FV das 10 casas com FV (ganho sobre 'igual a ontem') [v1 corte unico]`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/ranking_casas_prod.png · relation: references
- `Regime B: plus same-day weather (ceiling) - in legend only, no B points plotted here` → `Figure (v1 single-cut): Consumption of 20 houses - skill gain over 'igual a ontem'`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/ranking_casas_cons.png · relation: references
- `Vies dos fundacionais no consumo (~-20%)` → `Rankings divergem entre benchmarks estaticos e ao vivo`  [AMBIGUOUS]
  experimentos/testes_previsao/LEIA-ME.md · relation: conceptually_related_to
- `Figura: custo computacional x skill (3 paineis)` → `Protocolo v2 com rolling origin e 36 modelos`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/custo_x_skill.png · relation: references
- `Metrica skill (eixo Y)` → `Referencias e linear fisico ausentes da figura`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/custo_x_skill.png · relation: conceptually_related_to
- `Protocolo de dobras: 5 dobras nas usinas, 3 nas casas; fundacionais sem treino` → `Protocolo v2 com rolling origin e 36 modelos`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/custo_x_skill.png · relation: conceptually_related_to
- `Modelo TiRex-2 (regime A)` → `Modelo Ensemble-mediana (regimes B e C)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/dias_exemplo_cascavel.png · relation: shares_data_with
- `Protocolo de avaliacao v2 (numeros finais)` → `Estratificacao de dias por condicao de ceu (limpo/tipico/nublado)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/dias_exemplo_cascavel.png · relation: rationale_for
- `Intervalo de Confianca 95% por bootstrap por dia` → `Insight (ambiguo): os IC 95% dentro de um mesmo regime se sobrepoem fortemente, logo a ordem fina entre modelos vizinhos nao e estatisticamente distinguivel`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/ranking_usinas.png · relation: rationale_for
- `Figura: regimes de entrada meteorologica nas usinas (dumbbell A/C/B)` → `Protocolo v2 (numeros finais regerados)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/regimes_usinas.png · relation: references
- `Regime C: + previsao do tempo real (quadrado azul, day-ahead operacional)` → `ECMWF IFS (fonte NWP day-ahead por tras do regime C)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/regimes_usinas.png · relation: references
- `Painel 1: Usinas (skill 0,08-0,60 por regime)` → `Mediana de todos os modelos (linha preta de referencia nos paineis das casas)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/skill_por_dobra.png · relation: references
- `Regime B: mediana (skill mais alto, 0,40-0,60)` → `Toto-2.0-313m (FV das casas: 0,150 / 0,181 / 0,205)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/skill_por_dobra.png · relation: semantically_similar_to

## Knowledge Gaps
- **126 isolated node(s):** `Keras MLP 16-8 e 32-16 (origem dos TFLite)`, `TCN (FV das casas, skill ~0.15 a custo alto) - v1`, `lightgbm 4.7.0 (pinado em previsao e lote2)`, `tirex-ts 1.4.2`, `toto-ts 0.2.0 (Toto 1.0)` (+121 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 376 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **15 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `Cenario A: so historico (marcador vazado) - v1` and `KAN (melhor skill em FV das casas, ~0.17) - v1`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Testes de modelos de previsao (36 modelos, 3 casos)` connect `Ambientes moirai e previsao` to `Inversao de Familias entre Regimes`, `Clima x Modelo e B-curto`, `Embarcado: SparseTSF e TFLite`, `Fisica Errada em Curitiba`, `Ambiente previsao e TTM`, `Vies e Melhorias por Caso`, `Achados dos Regimes A/C/B`, `Metricas na Convencao FV`, `Tarifas ANEEL e Lei 14.300`, `Levantamento dos 127 Modelos`, `Pipeline Reprodutivel e Rede`, `Lote 2 de Fundacionais`, `Energia em Edificacoes Inteligentes`, `Metrica Skill e Defeito do TiDE`?**
  _High betweenness centrality (0.232) - this node is a cross-community bridge._
- **What connects `Keras MLP 16-8 e 32-16 (origem dos TFLite)`, `TCN (FV das casas, skill ~0.15 a custo alto) - v1`, `lightgbm 4.7.0 (pinado em previsao e lote2)` to the rest of the system?**
  _126 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Irradiancia Medida vs NASA` be split into smaller, more focused modules?**
  _Cohesion score 0.05714285714285714 - nodes in this community are weakly interconnected._
- **What is the exact relationship between `KAN (melhor skill em FV das casas, ~0.17) - v1` and `NHITS (FV das casas, skill ~0.14) - v1`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **Why does `Modelos_previsao_geracao_consumo.xlsx (levantamento de 28/09/2026)` connect `Levantamento dos 127 Modelos` to `Visao Geral dos Modelos e Tarifas`, `Referencias e Rede VOSviewer`, `Ambientes moirai e previsao`?**
  _High betweenness centrality (0.192) - this node is a cross-community bridge._
- **Should `Visao Geral dos Modelos e Tarifas` be split into smaller, more focused modules?**
  _Cohesion score 0.06019871420222092 - nodes in this community are weakly interconnected._