# Graph Report - prossumidor  (2026-10-11)

## Corpus Check
- 72 files · ~314,282 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1736 nodes · 3718 edges · 93 communities (69 shown, 24 thin omitted)
- Extraction: 90% EXTRACTED · 9% INFERRED · 1% AMBIGUOUS · INFERRED: 345 edges (avg confidence: 0.88)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- Referencias, LightGBM e classicos
- Planilhas e documentacao (legado)
- Diagnostico das usinas (legado)
- Figura ranking FV casas (en)
- Figura ranking usinas v1
- Biblioteca: contratos e testes
- Geometria solar e POA
- Figura ranking FV casas (pt)
- Protocolo comum e regime C
- Figura ranking consumo (en)
- Biblioteca: metricas
- Biblioteca: protocolo day-ahead
- Figura ranking consumo (pt)
- Redes proprias e pilotos da etapa A
- Resolucoes e avaliacao de pilotos
- Conceitos e visualizacao (legado)
- Biblioteca: esquemas e erros
- Usinas anonimizadas e diagnostico
- Testes de metricas
- Benchmark: achados e regimes
- Embarcado e TFLite
- Ambientes Python
- Figura regimes das usinas
- Estado do projeto ia_solar
- Janelas e carga de dados
- Relatorios 5 min (legado)
- Revisao de literatura
- Classicos estatisticos
- Figura custo x skill v1
- Fundacionais zero-shot
- Figura skill por dobra
- Redes NeuralForecast (04)
- Tarifas e regulacao BR
- Teste de regressao do benchmark
- Metricas e referencias do benchmark
- Rede do projeto (constroi_rede)
- Figura ranking usinas (pt)
- Protocolo v2 e filas
- Linhagem e rede do projeto
- Figura dias de exemplo
- Guardas de memoria (pilotos)
- Decisoes da biblioteca
- Figura custo x skill
- Fundacionais lote 2
- SparseTSF, casas e qualidade
- misc (17)
- dias_exemplo_cascavel.png (17)
- test_covariates.py (16)
- 03c_fundacionais_lote2.py (15)
- 06_figuras.py (15)
- test_resolution_and_bias.py (15)
- ranking_usinas.png (14)
- 01_linhagem.py (13)
- contracts.py (13)
- baixa_tarifas_aneel.py (13)
- CLAUDE.md (11)
- README.md (11)
- test_auditoria.py (10)
- Documentacao_Base_Modelagem_b9eeb66b.md (10)
- LEIA-ME.md (10)
- 03_literatura.py (10)
- estima_irradiancia.py (10)
- ranking_usinas.png (9)
- Documentacao_Base_Modelagem_b9eeb66b.md (9)
- piloto_moment.py (8)
- Documentacao_Base_Modelagem_b9eeb66b.md (8)
- 05_monta_grafo.py (8)
- 09_clima_casas.py (7)
- piloto_geometria.py (7)
- redes_proprias.py (7)
- LEIA-ME.md (7)
- Documentacao_Base_Modelagem_b9eeb66b.md (6)
- aplicar_melhor_modelo.py (6)
- lote2.txt (5)
- fila_noite.sh (5)
- piloto_llmtime.py (5)
- Documentacao_Base_Modelagem_b9eeb66b.md (5)
- h2_model.py (5)
- ml1_experiment.py (5)
- 01_prepara_dados.py (4)
- piloto_llmtime.py (4)
- Documentacao_Resultados_7ef0e129.md (4)
- vizstyle.py (4)
- changepoint.py (3)
- ESTADO_DO_PROJETO.md (2)
- lote2_hf.txt (2)
- LEIA-ME.md (2)
- Documentacao_Base_Modelagem_b9eeb66b.md (1)
- pyproject.toml (1)

## God Nodes (most connected - your core abstractions)
1. `Figura (v1 corte unico): Ranking de usinas (Cascavel + Curitiba) - ganho de skill sobre a persistencia de ceu claro` - 47 edges
2. `carrega()` - 46 edges
3. `Figura: Ranking de modelos - Geracao FV das 10 casas com FV (ganho sobre 'igual a ontem') [v1 corte unico]` - 36 edges
4. `EnergySeries` - 36 edges
5. `Figure (v1 single-cut): Consumption of 20 houses - skill gain over 'igual a ontem'` - 35 edges
6. `Ranking order: 32 entries sorted by skill, best at top` - 34 edges
7. `Covariate regime A: history only (every entry marked (A), hollow markers)` - 33 edges
8. `Metrica skill = 1 - RMSE / RMSE da referencia (eixo x da figura v1 corte unico)` - 31 edges
9. `dobras()` - 30 edges
10. `Testes de modelos de previsao (36 modelos, 3 casos)` - 29 edges

## Surprising Connections (you probably didn't know these)
- `Benchmark FV: estatistico x DL x zero-shot (7 anos de usina real)` --semantically_similar_to--> `Achado: fundacionais zero-shot lideram os tres casos`  [INFERRED] [semantically similar]
  graphify-out/converted/Visao_geral_modelos_previsao_7fd0849f.md → experimentos/testes_previsao/LEIA-ME.md
- `xLSTM e variantes (xLSTMTime, xLSTM-Mixer)` --references--> `TiRex-2`  [INFERRED]
  graphify-out/converted/Modelos_previsao_geracao_consumo_7c09b438.md → experimentos/testes_previsao/resultados/figuras/regimes_usinas.png
- `paper/protocolo_canonico.py (nunca criado)` --semantically_similar_to--> `scripts/comum.py (protocolo)`  [INFERRED] [semantically similar]
  docs/projeto/ia_solar/PLANO_ARTIGO.md → CLAUDE.md
- `Nunca usar train_test_split aleatorio (autocorrelacao 0,90)` --semantically_similar_to--> `Origem movel (retreino do zero em cada dobra)`  [INFERRED] [semantically similar]
  docs/projeto/ia_solar/LEIA-ME.md → experimentos/testes_previsao/LEIA-ME.md
- `Lorenzo-Fonseca et al. (2026), LSTM leve em Raspberry Pi (campus)` --semantically_similar_to--> `TFLite de 3,4 KB (MLP 16-8 int8, R2 0,8117)`  [INFERRED] [semantically similar]
  graphify-out/converted/Referencias_previsao_consumo_embarcado_718e8d95.md → docs/projeto/ia_solar/ESTADO_DO_PROJETO.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Cadeia física que gera poa_estimada: geometria → Haurwitz → Erbs → HDKR → kc horário** — graphify_out_converted_documentacao_base_modelagem_b9eeb66b_geometria_solar_spencer, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_haurwitz, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_erbs, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_hdkr, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_poa_ceu_claro, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_kc_horario, graphify_out_converted_documentacao_base_modelagem_b9eeb66b_poa_estimada [EXTRACTED 1.00]
- **A escada de regimes das usinas (A < C-gfs < C < B-curto < B)** — experimentos_testes_previsao_leia_me_regime_a, experimentos_testes_previsao_leia_me_c_gfs, experimentos_testes_previsao_leia_me_regime_c, experimentos_testes_previsao_leia_me_b_curto, claude_regime_b, claude_lightgbm, experimentos_testes_previsao_leia_me_skill_bootstrap_dias [EXTRACTED 1.00]
- **Os oito modulos da biblioteca prossumidor** — docs_proposta_proposta_biblioteca_prossumidor_io, docs_proposta_proposta_biblioteca_prossumidor_qualidade, docs_proposta_proposta_biblioteca_prossumidor_fisica, docs_proposta_proposta_biblioteca_prossumidor_diagnostico, docs_proposta_proposta_biblioteca_prossumidor_previsao, docs_proposta_proposta_biblioteca_prossumidor_protocolo, docs_proposta_proposta_biblioteca_prossumidor_embarcado, docs_proposta_proposta_biblioteca_prossumidor_economia, docs_proposta_proposta_biblioteca_camada_dominio_fina [EXTRACTED 1.00]
- **Os seis defeitos corrigidos no caminho da v2** — experimentos_testes_previsao_leia_me_defeito_recorte_dobra, experimentos_testes_previsao_leia_me_defeito_tide_layernorm, experimentos_testes_previsao_leia_me_defeito_normalizacao_teste, experimentos_testes_previsao_leia_me_defeito_familias_figuras, experimentos_testes_previsao_leia_me_defeito_exclusao_figura_regimes, experimentos_testes_previsao_leia_me_defeito_memoria_time_moe, experimentos_testes_previsao_leia_me_test_auditoria [EXTRACTED 1.00]
- **O gargalo é a irradiância, não o modelo (ablação, vão A→B, sensor, fonte de clima)** — graphify_out_converted_documentacao_resultados_7ef0e129_ablacao_preditores, graphify_out_converted_documentacao_resultados_7ef0e129_sensor_substitui_nasa, legado_ia_solar_analise_irradiancia_inversa_leia_me_kc_nasa_r2_negativo, legado_ia_solar_analise_irradiancia_inversa_leia_me_fonte_horaria_melhor [INFERRED 0.85]

## Communities (93 total, 24 thin omitted)

### Community 0 - "Referencias, LightGBM e classicos"
Cohesion: 0.05
Nodes (19): classicos(), lgbm(), linear_fisico(), matriz(), tabela_features(), avalia(), carrega(), latencia() (+11 more)

### Community 1 - "Planilhas e documentacao (legado)"
Cohesion: 0.05
Nodes (29): aba_homer(), escreve_tabela(), le_bandeiras(), le_fiscais(), le_tarifas(), monta_calendario(), processa(), aba_explicacao() (+21 more)

### Community 2 - "Diagnostico das usinas (legado)"
Cohesion: 0.07
Nodes (6): pack(), probe(), run(), caminho(), _dados(), dp()

### Community 3 - "Figura ranking FV casas (en)"
Cohesion: 0.10
Nodes (46): Ranking Figure: PV Generation of 10 Houses with PV - Skill over 'igual a ontem', Case: House PV generation (10 houses with PV), day-ahead, 95% CI from per-day bootstrap (error bars), Family: Arvore / fisica (tree / physical models, blue), Ensemble (median of all models, black diamond), Family: Fundacional (time-series foundation model, green), Family: Rede treinada (trained network, orange), Family: Referencia (reference baselines, gray) (+38 more)

### Community 4 - "Figura ranking usinas v1"
Cohesion: 0.11
Nodes (40): Figura (v1 corte unico): Ranking de usinas (Cascavel + Curitiba) - ganho de skill sobre a persistencia de ceu claro, Caso usinas fotovoltaicas: Cascavel + Curitiba (previsao day-ahead), Chronos-2 [figura v1 corte unico, usinas; regimes: A e B; B ~0.44; A ~0.06], Chronos-Bolt-small [figura v1 corte unico, usinas; regimes: A; A ~0.09], DLinear [figura v1 corte unico, usinas; regimes: A; A ~-0.07], Dot plot ordenado por skill com IC 95%, cor = familia e preenchimento = regime, Ensemble-mediana (mediana de todos os modelos) [figura v1 corte unico, usinas; regimes: A e B; B ~0.50 (1o lugar geral); A ~0.11 (melhor do regime A)], Familia: Arvore / fisica - azul (+32 more)

### Community 5 - "Biblioteca: contratos e testes"
Cohesion: 0.08
Nodes (21): ContractError, EnergySeries, with_gaps(), _filled_local_grid(), _hourly_frame(), test_accepts_minimal_frame(), test_conversion_to_kwh(), test_drop_removes_only_the_impossible_hours_and_warns() (+13 more)

### Community 6 - "Geometria solar e POA"
Cohesion: 0.08
Nodes (23): tabela_dias(), poa(), r2(), evaluate(), pr(), run(), r2_5(), r2_d() (+15 more)

### Community 7 - "Figura ranking FV casas (pt)"
Cohesion: 0.09
Nodes (33): Figura: Ranking de modelos - Geracao FV das 10 casas com FV (ganho sobre 'igual a ontem') [v1 corte unico], Caso de estudo: geracao fotovoltaica das 10 casas com FV, Familia Arvore / fisica (azul), Familia Ensemble (mediana de todos, losango preto), Familia Fundacional (foundation models de series temporais, verde), Familia Rede treinada (deep learning treinado nos dados, laranja), Familia Referencia (baselines ingenuos, cinza), Intervalo de confianca 95% por bootstrap por dia (barras de erro do ranking) (+25 more)

### Community 8 - "Protocolo comum e regime C"
Cohesion: 0.09
Nodes (7): exog_previsao(), ghi_ceu_claro(), grava_piloto(), preditor(), preve(), com_nwp(), preve()

### Community 9 - "Figura ranking consumo (en)"
Cohesion: 0.17
Nodes (33): Figure (v1 single-cut): Consumption of 20 houses - skill gain over 'igual a ontem', Case: aggregated consumption of 20 houses, day-ahead forecast (v1 single-cut), Uncertainty: 95% confidence interval bars, bootstrap by day (v1 single-cut), Model family: Arvore / fisica (tree-based / physical, blue), Model family: Ensemble - median of all models (black diamond), Model family: Fundacional (pretrained time-series foundation models, green), Model family: Rede treinada (locally trained deep nets, orange), Model family: Referencia (naive baselines, gray) (+25 more)

### Community 10 - "Biblioteca: metricas"
Cohesion: 0.08
Nodes (15): aggregate(), align(), by_blocks(), f(), by_resolution(), daily(), diebold_mariano(), holm() (+7 more)

### Community 11 - "Biblioteca: protocolo day-ahead"
Cohesion: 0.09
Nodes (14): DayAhead, Fold, plant(), test_check_support_raises_when_a_series_ends_early(), test_context_shorter_than_horizon_is_refused(), test_end_before_start_is_refused(), test_fold_of_assigns_each_day_to_exactly_one_fold(), test_fold_of_refuses_day_outside_the_test() (+6 more)

### Community 12 - "Figura ranking consumo (pt)"
Cohesion: 0.07
Nodes (31): Caso de avaliacao: consumo de 20 residencias, Chronos-2 — 10o lugar, skill ~ 0.182 (fundacional), Chronos-Bolt-small — 6o lugar, skill ~ 0.190 (fundacional), DLinear — skill ~ 0.08, pior modelo treinado do campo, Ensemble-mediana (mediana de todos os modelos) — 9o lugar, skill ~ 0.188, Familia: Arvore / fisica, Familia: Fundacional (foundation models zero-shot), Familia: Rede treinada (deep learning treinado no dataset) (+23 more)

### Community 13 - "Redes proprias e pilotos da etapa A"
Cohesion: 0.09
Nodes (12): config(), fabrica(), Mamba(), dobra(), estimador(), CycleNet, fase_de(), largo() (+4 more)

### Community 14 - "Resolucoes e avaliacao de pilotos"
Cohesion: 0.09
Nodes (13): previsao(), avalia_piloto(), com_manha(), recorte(), somado(), seasonal_cv(), step(), _clear_sky() (+5 more)

### Community 15 - "Conceitos e visualizacao (legado)"
Cohesion: 0.14
Nodes (4): _le_tempos(), save(), save(), save()

### Community 16 - "Biblioteca: esquemas e erros"
Cohesion: 0.08
Nodes (5): schema(), correct_bias(), Regime, SupportError, Window

### Community 17 - "Usinas anonimizadas e diagnostico"
Cohesion: 0.08
Nodes (17): Usina Cascavel (3,96 kWp), Usina Curitiba (~9,6 kWp), Diagnostico Curitiba: falha da string 1 e reconfiguracao, Diagnostico Cascavel: sujeira progressiva, nao degradacao, dicionario_colunas.csv (28 colunas, unidade e faltantes), Exportacao de 5 min do inversor Fronius, Dois rastreadores MPPT: uma string controla a outra, Projeto IA Solar (Cascavel e Curitiba) (+9 more)

### Community 18 - "Testes de metricas"
Cohesion: 0.09
Nodes (15): _frame(), test_align_fails_instead_of_comparing_nothing(), test_align_refuses_duplicate_key(), test_align_uses_only_common_finite_hours(), test_bias_has_known_sign_and_magnitude(), test_daily_r2_defined_with_several_days(), test_daily_r2_is_nan_with_a_single_day(), test_dm_detects_the_worse_model() (+7 more)

### Community 19 - "Benchmark: achados e regimes"
Cohesion: 0.08
Nodes (25): 01_prepara_dados.py (nao roda no repo exportado), Achado: o clima importa ~10x mais que o modelo, Benchmark de previsao do dia seguinte, LightGBM global, Quatro ambientes Python congelados, Regime B (clima NASA do proprio dia, teto), Diagnostico B-curto, Regime C (previsao do tempo real da vespera) (+17 more)

### Community 20 - "Embarcado e TFLite"
Cohesion: 0.09
Nodes (24): preprocessamento_<usina>_<conjunto>.json, Verificacao dos 32 modelos TFLite a partir do arquivo, TFLite de 3,4 KB (MLP 16-8 int8, R2 0,8117), ~27 saidas de analise que nenhum script le, Os 32 TFLite nunca carregados de volta por script, LiteRT (TFLite) e emlearn, prossumidor.embarcado, Linear sobre poa_estimada (linear fisico) (+16 more)

### Community 21 - "Ambientes Python"
Cohesion: 0.09
Nodes (27): TTM (3M parametros, roda em CPU), Ambiente moirai (Python 3.11, torch 2.4.1+cpu) — Moirai 2.0 e Moirai-MoE, uni2ts 2.0.0 (implementação do Moirai), Ambiente previsao (Python 3.12, torch 2.11 CPU) — quase tudo, chronos-forecasting 2.3.2, granite-tsfm (IBM, git pin) — implementação do TTM, lightgbm 4.7.0 (pinado em previsao e lote2), neuralforecast 3.1.9 (redes treinadas: NHITS, TiDE, TFT, LSTM, GRU, KAN…) (+19 more)

### Community 22 - "Figura regimes das usinas"
Cohesion: 0.10
Nodes (24): Figura: regimes de entrada meteorologica nas usinas (dumbbell A/C/B), Dispersao entre modelos comprimida no regime C (~0.26-0.38) e ampla no regime A (~-0.17 a 0.14), ECMWF IFS (fonte NWP day-ahead por tras do regime C), Fechamento do gap A->B pelo regime C: 72% da distancia (mediana dos modelos), Metrica: skill sobre a persistencia de ceu claro (eixo x, -0.2 a 0.5), Ensemble-mediana, GRU, KAN (+16 more)

### Community 23 - "Estado do projeto ia_solar"
Cohesion: 0.09
Nodes (21): Pendencia: geometria do telhado de Curitiba, Base de modelagem (620.278 linhas, 28 colunas), Duas coordenadas a 19 km caem na mesma celula da NASA, Eficiencia do inversor > 1 por falta de simultaneidade, HistGradientBoosting (modelo escolhido, R2 0,7609), NASA POWER diaria le 3,2% abaixo (piso de erro), Serie horaria da NASA termina em 31/05/2026 (~15% do teste), NASA POWER horaria: carimbo LST alinha em -55 min (+13 more)

### Community 24 - "Janelas e carga de dados"
Cohesion: 0.14
Nodes (10): carrega(), clima_casas(), dias_teste(), janelas(), avalia(), gera_chronos2(), gera_flowstate(), gera_lgbm() (+2 more)

### Community 25 - "Relatorios 5 min (legado)"
Cohesion: 0.12
Nodes (7): b64(), fig(), b64(), fig(), cell(), b64(), fig()

### Community 26 - "Revisao de literatura"
Cohesion: 0.10
Nodes (21): 1Referencias_projetoIA.xlsx (71 referencias), rede_keywords_vosviewer.json, Referencias_previsao_consumo_embarcado.xlsx (15 artigos), Revisao de literatura e levantamento de modelos, smart_buildings.docx (rascunho da revisao Edge AI), Visao_geral_modelos_previsao.xlsx (127 entradas, sem resultados), Artigo OCR (ICIT 2027), Comunidade OCR + revisao Edge AI (21 artigos em comum) (+13 more)

### Community 27 - "Classicos estatisticos"
Cohesion: 0.11
Nodes (11): roda(), salva(), para_janelas(), prepara(), roda(), corrige_vies(), dobras(), grava() (+3 more)

### Community 28 - "Figura custo x skill v1"
Cohesion: 0.17
Nodes (19): Figura v1 (corte unico): custo computacional x skill (3 paineis), Cenario A: so historico (marcador vazado) - v1, Cenario B: + clima do dia (marcador preenchido) - v1, Familia 'Fundacional' (verde, zero-shot) - v1 corte unico, Familia 'Rede treinada' (laranja) - v1 corte unico, Metrica skill (ganho sobre baseline, eixo Y) - v1 corte unico, Chronos-Bolt-small (fundacional, ~40 s, skill ~0.19) - v1, KAN (melhor skill em FV das casas, ~0.17) - v1 (+11 more)

### Community 29 - "Fundacionais zero-shot"
Cohesion: 0.12
Nodes (9): chronos2(), chronos_bolt(), em_lotes(), flowstate(), tirex(), toto(), ttm(), visiontspp() (+1 more)

### Community 30 - "Figura skill por dobra"
Cohesion: 0.16
Nodes (17): 3 dobras das casas (out, nov-dez, dez; ~31 dias cada), 5 dobras das usinas (ago-set, out-nov, dez-jan, jan-abr, abr-mai; ~61 dias cada), Figura: Origem movel - skill em cada dobra (3 paineis), LightGBM (consumo das casas: 0,197 / 0,209 / 0,209), Mediana de todos os modelos (linha preta de referencia nos paineis das casas), Metrica: skill na dobra (eixo y de todos os paineis), Origem movel (rolling origin) com retreino no inicio de cada dobra, Painel 3: Consumo das casas (skill ~0,19-0,21) (+9 more)

### Community 31 - "Redes NeuralForecast (04)"
Cohesion: 0.10
Nodes (7): anota(), para_janelas(), roda_nf(), normaliza_por_treino(), chama_tslib(), crossformer(), SparseTSF

### Community 32 - "Tarifas e regulacao BR"
Cohesion: 0.10
Nodes (8): Pendencia: COSIP e PIS/COFINS efetivo, ICMS do Parana mudou duas vezes no periodo, Lei 14.300 e direito adquirido das duas usinas, Contexto tarifario brasileiro (TUSD/TE, bandeiras, ICMS, Lei 14.300), prossumidor.economia, Ambiente lote2 (Toto 2.0, TiRex-2, TabPFN-TS), Ambiente lote2_hf (Sundial, Timer-XL, Time-MoE), Ambiente moirai (Python 3.11, uni2ts, torch 2.4)

### Community 33 - "Teste de regressao do benchmark"
Cohesion: 0.17
Nodes (10): _aligned(), evaluated_actual(), _forecast(), _published(), _read_metrics(), reference(), test_benchmark_corrected_median_is_the_library_one(), test_ci95_close_to_published() (+2 more)

### Community 34 - "Metricas e referencias do benchmark"
Cohesion: 0.14
Nodes (14): Metricas na convencao FV (nRMSE, nMAE, MBE, skill score), Yang et al. (2020), verificacao de previsoes solares deterministicas, resultados/metricas.csv e CSVs de metricas, Persistencia de ceu claro (referencia das usinas), Persistencia 'igual a ontem' (referencia das casas), Skill com IC 95% por bootstrap de dias inteiros, alinha_previsoes(), avalia() (+6 more)

### Community 35 - "Rede do projeto (constroi_rede)"
Cohesion: 0.16
Nodes (9): camada(), carregar_semantica(), chave(), completar(), grava(), inventario(), main(), relativo() (+1 more)

### Community 36 - "Figura ranking usinas (pt)"
Cohesion: 0.15
Nodes (16): Caso de Estudo Usinas FV (Cascavel 3,96 kWp + Curitiba ~9,6 kWp), Familia Arvore / Fisica (azul): LightGBM, linear_fisico, Familia Ensemble (losango preto): mediana de todos os modelos, Familia Fundacional (verde): foundation models de series temporais, Figura: Ranking de Modelos - Usinas (Cascavel + Curitiba), Chronos-2 (ultimo em B ~0,445; penultimo em C ~0,28), Ensemble-mediana (lider em B ~0,52 e em C ~0,37; topo de A ~0,12), LightGBM (presente nos tres regimes) (+8 more)

### Community 37 - "Protocolo v2 e filas"
Cohesion: 0.12
Nodes (13): Estado 06/10/2026: v2 + lote 2 completos em GPU, comum.normaliza_por_treino, roda_lote2.py (lote 2 + ensemble), roda_v2.py (fila da v2), Modelos_previsao_geracao_consumo.xlsx (levantamento de 28/09/2026), Cobertura das familias de modelos (levantamento x testados), KAN (Kolmogorov-Arnold), Testes v1 (33 modelos, 3 casos, corte unico) (+5 more)

### Community 38 - "Linhagem e rede do projeto"
Cohesion: 0.12
Nodes (10): Pipeline reprodutivel do bruto ao relatorio (42 etapas), analise/comum/scripts/caminhos.py (funcao caminho()), Analise de rede do projeto (1.342 nos, 2.570 arestas), Cadeia de linhagem de 14 passos (NASA -> relatorio), Camada de linhagem de dados (01_linhagem.py), frame5.parquet (no mais conectado, nao existe no disco), Graphify (camada de codigo do grafo), Leiden (deteccao de comunidades) (+2 more)

### Community 39 - "Figura dias de exemplo"
Cohesion: 0.19
Nodes (15): Curva horaria de geracao (kWh na hora, 5h-20h), Estratificacao de dias por condicao de ceu (limpo/tipico/nublado), Figura: Dias de Exemplo Cascavel (real vs previsto), Modelo Ensemble-mediana (regimes B e C), Modelo baseline persist_ceu_claro (regime A), Modelo TiRex-2 (regime A), Painel 1: 04/01/2026 - dia limpo, Painel 3: 17/11/2025 - dia nublado (+7 more)

### Community 40 - "Guardas de memoria (pilotos)"
Cohesion: 0.14
Nodes (6): memoria_privada_gb(), registra(), vigia(), fabrica(), guarda(), SemLLM

### Community 41 - "Decisoes da biblioteca"
Cohesion: 0.11
Nodes (14): Mediana de todos os modelos, Skill = 1 - RMSE/RMSE da referencia, NeuralForecast / Darts, OpenSTEF 4.0 (exportar, nao competir), prossumidor.previsao, Achado: a mediana e robusta mas nem sempre a melhor (9a de 32 no consumo), TiDE, Aba Bibliotecas (40 bibliotecas de previsao) (+6 more)

### Community 42 - "Figura custo x skill"
Cohesion: 0.21
Nodes (13): Familia: redes treinadas (laranja, treino por dobra), Figura: custo computacional x skill (3 paineis), LightGBM ausente da figura (roda em segundos, tempo nao medido), Referencias e linear fisico ausentes da figura, Metrica skill (eixo Y), Tempo total, todas as dobras (s, CPU) - eixo X log, Painel: Usinas, Protocolo de dobras: 5 dobras nas usinas, 3 nas casas; fundacionais sem treino (+5 more)

### Community 43 - "Fundacionais lote 2"
Cohesion: 0.24
Nodes (15): Regime A (so historico), Toto-2.0-313m, Achado: fundacionais zero-shot lideram os tres casos, Lote 2 (geracao seguinte de fundacionais, 05/10/2026), Moirai-MoE-small, Sundial-128m, Time-MoE-50M, Timer-XL-84m (+7 more)

### Community 44 - "SparseTSF, casas e qualidade"
Cohesion: 0.12
Nodes (13): SparseTSF (32 parametros), As 20 casas (dataset de origem desconhecida), As casas sao do hemisferio norte (provavelmente Europa), prossumidor.qualidade, Tres casos: usinas, FV das casas, consumo das casas, Melhoria: estimar a localizacao das casas pelo perfil diario, Vies dos fundacionais no consumo (~-20%), Aba Benchmarks (12 benchmarks da area) (+5 more)

### Community 46 - "dias_exemplo_cascavel.png (17)"
Cohesion: 0.18
Nodes (13): Figure (v1 single-cut): Cascavel example days - observed vs forecast hourly PV generation, 3 panels, Scenario/feature-set suffixes (A) and (B) distinguishing forecast input configurations, Chronos-Bolt-small (A) - foundation time-series forecaster (green curve), Observed hourly generation curve 'real' (kWh na hora, black reference line), Clear-day regime panel (dia limpo, 04/01/2026, peak ~3.35 kWh/h), Cloudy-day regime panel (dia nublado, 17/11/2025, suppressed ~1.7 kWh/h peak), Typical-day regime panel (dia tipico, 27/08/2025, double-humped ~2.7 kWh/h peak), Ensemble-mediana (A) - median ensemble, configuration A (blue curve) (+5 more)

### Community 47 - "test_covariates.py (16)"
Cohesion: 0.15
Nodes (6): _fit_predict(), test_adapter_that_uses_weather_reacts_to_a_weather_swap(), test_adapter_with_weather_errs_less_than_without(), test_example_data_ties_generation_to_weather(), test_gaps_do_not_become_zero(), test_the_test_catches_an_adapter_that_ignores_weather()

### Community 48 - "03c_fundacionais_lote2.py (15)"
Cohesion: 0.19
Nodes (8): em_lotes(), hf_causal(), f(), moirai_moe(), tabpfn_ts(), tirex2(), toto2(), f()

### Community 49 - "06_figuras.py (15)"
Cohesion: 0.23
Nodes (9): custo(), dias_exemplo(), familia(), legenda_regimes(), limpa(), marca(), por_dobra(), ranking() (+1 more)

### Community 50 - "test_resolution_and_bias.py (15)"
Cohesion: 0.24
Nodes (12): _biased_consumption(), _days(), test_block_count_per_level(), test_constant_bias_is_removed_after_the_minimum_days(), test_correction_does_not_use_the_day_itself(), test_error_that_cancels_within_the_day_vanishes_in_the_daily_total(), test_factor_is_bounded(), test_generation_is_blocked_by_default() (+4 more)

### Community 51 - "ranking_usinas.png (14)"
Cohesion: 0.18
Nodes (12): Familia Rede Treinada (laranja), DLinear (pior do ranking, skill ~-0,33 no regime A), GRU (bom em B ~0,47, negativo em A ~-0,13), iTransformer (skill ~-0,24 no regime A), KAN, LSTM (bom em B ~0,48, negativo em A ~-0,18), NHITS, ResNet-1D (melhor rede treinada no regime A ~0,11) (+4 more)

### Community 52 - "01_linhagem.py (13)"
Cohesion: 0.23
Nodes (6): e_caminho(), literais(), nome_chamada(), padrao(), rel(), resolve()

### Community 55 - "baixa_tarifas_aneel.py (13)"
Cohesion: 0.27
Nodes (6): bandeiras(), busca(), cacheado(), componentes_b1(), num(), tarifas_copel()

### Community 56 - "CLAUDE.md (11)"
Cohesion: 0.22
Nodes (7): 05_avalia.py (metricas), scripts/comum.py (protocolo), Diebold-Mariano com correcao de Holm, Etapa E1 do TCC (esqueleto do pacote, contratos, CI), Fundacao do pacote src/prossumidor/ (etapa E1), prossumidor.protocolo, Ambiente previsao (Python 3.12, quase tudo)

### Community 57 - "README.md (11)"
Cohesion: 0.20
Nodes (7): gera_proposta_tcc.py (gera o PDF, precisa de reportlab), Proposta da biblioteca prossumidor e do TCC, Decisoes pedidas a gestao (secao 10: titularidade e licenca), Etapas E0-E8 do TCC (~580 h, 9 meses), Pasta legado/ (codigo que vira os modulos), Biblioteca prossumidor, TCC de Joao Jachenski Junior

### Community 59 - "Documentacao_Base_Modelagem_b9eeb66b.md (10)"
Cohesion: 0.20
Nodes (7): Comparação de 13 algoritmos nas duas usinas, Documentação da base de modelagem (planilha consolidada), HistGradientBoosting — modelo escolhido (por tempo de treino, não por R²), Documentacao_Dados.xlsx — metade "o que a base É", Documentacao_Resultados.xlsx — metade "o que foi encontrado", Irradiância inversa estimada a partir da potência, Base tarifária de referência Copel-DIS

### Community 60 - "LEIA-ME.md (10)"
Cohesion: 0.20
Nodes (4): Melhor modelo por orçamento de memória (microcontrolador / Linux embarcado / servidor), Voting (HGB+RF+Linear) — melhor R² absoluto, 2,6 GB, G_inv — irradiância invertida de P = G·A·η, Temperatura de célula modelada (T_c = T_ar + 0,03125·G, NOCT 45 °C)

### Community 61 - "03_literatura.py (10)"
Cohesion: 0.31
Nodes (4): texto(), adiciona(), chave(), doi_de()

### Community 62 - "estima_irradiancia.py (10)"
Cohesion: 0.33
Nodes (6): calibra_k(), downscale_ml(), _erro(), irradiancia_inversa(), processa(), roda()

### Community 63 - "ranking_usinas.png (9)"
Cohesion: 0.25
Nodes (8): Familia: Referencia (baselines ingenuos), Metrica skill = 1 - RMSE / RMSE da referencia, persist_24h — referencia 'igual a ontem' (skill = 0 por construcao), semanal_168h — baseline sazonal semanal (skill ~ -0.13, unico abaixo da referencia), Baselines ingenuos: media_7d (~0,03), persist_24h (~-0,09), semanal_168h (~-0,29), Familia Referencia (cinza): persist_ceu_claro, persist_24h, media_7d, semanal_168h, Intervalo de Confianca 95% por bootstrap por dia, Referencia: persistencia de ceu claro (persist_ceu_claro)

### Community 64 - "Documentacao_Base_Modelagem_b9eeb66b.md (9)"
Cohesion: 0.25
Nodes (6): estado_sujeira — mediana móvel de 30 dias do PI, defasada 1 dia, indice_desempenho (PI) — diagnóstico apenas, proibido como preditor, potencia_ca_W — alvo (potência CA média de 5 min), COSIP/CIP — contribuição de iluminação pública (R$ 10,62/mês estimado), Custo de disponibilidade (50/100 kWh/mês, encargo fixo no HOMER), Montagem da tarifa cheia (TUSD+TE, bandeira, impostos por dentro)

### Community 66 - "Documentacao_Base_Modelagem_b9eeb66b.md (8)"
Cohesion: 0.25
Nodes (3): Base de 5 min do inversor Fronius × NASA POWER (620.278 registros, 28 colunas), Conjunto COMPLETO — 20 preditores com NASA POWER, Conjunto EMBARCADO — 7 preditores que o dispositivo obtém sozinho

### Community 67 - "05_monta_grafo.py (8)"
Cohesion: 0.46
Nodes (5): frente(), no(), no_dado(), no_doc(), no_script()

### Community 69 - "09_clima_casas.py (7)"
Cohesion: 0.43
Nodes (3): baixa(), ghi_ceu_claro_utc(), main()

### Community 70 - "piloto_geometria.py (7)"
Cohesion: 0.33
Nodes (3): geometria_solar(), melhor_geometria(), poa()

### Community 72 - "LEIA-ME.md (7)"
Cohesion: 0.33
Nodes (3): kc_horario — índice de céu claro horário da NASA POWER (elo fraco), poa_estimada = poa_ceu_claro × kc_horario (relação multiplicativa construída à mão), Decomposição da variância do kc de 5 min (83%/79% entre horas)

### Community 76 - "lote2.txt (5)"
Cohesion: 0.50
Nodes (5): Ambiente lote2 (Python 3.12, torch 2.14.1) — Toto 2.0, TiRex-2, TabPFN-TS, tabpfn-time-series 1.3.0 (ficou de fora em CPU), tirex-2 (git pin NX-AI/tirex-2), toto-2 2.0.0, xlstm 2.0.6 (base do TiRex)

### Community 77 - "fila_noite.sh (5)"
Cohesion: 0.60
Nodes (4): DISPOSITIVO, nota(), roda(), fila_noite.sh script

### Community 79 - "Documentacao_Base_Modelagem_b9eeb66b.md (5)"
Cohesion: 0.40
Nodes (5): Correlação de Erbs (fração difusa), Geometria solar (Spencer, equação do tempo, hora solar verdadeira), Modelo de céu claro de Haurwitz, Transposição HDKR para o plano inclinado, poa_ceu_claro — POA de céu claro (preditor mais importante)

## Ambiguous Edges - Review These
- `DLinear — skill ~ 0.08, pior modelo treinado do campo` → `SparseTSF — 7o lugar, skill ~ 0.189 (melhor rede treinada)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/ranking_casas_cons.png · relation: semantically_similar_to
- `LightGBM — 1o lugar, skill ~ 0.205 (arvore)` → `Time-MoE-50M — 2o lugar, skill ~ 0.203 (fundacional)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/ranking_casas_cons.png · relation: conceptually_related_to
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
- `Protocolo v1 de corte unico (single-cut), anterior ao v2 rolling-origin` → `Insight: o ganho maximo sobre 'igual a ontem' e modesto (~16%), e varios modelos (DLinear, LSTM, semanal_168h) ficam abaixo da referencia`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/ranking_casas_prod.png · relation: conceptually_related_to
- `Regime B: + clima do dia (teto) - presente apenas na legenda, sem pontos nesta figura` → `Figura: Ranking de modelos - Geracao FV das 10 casas com FV (ganho sobre 'igual a ontem') [v1 corte unico]`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/ranking_casas_prod.png · relation: references
- `Regime B: plus same-day weather (ceiling) - in legend only, no B points plotted here` → `Figure (v1 single-cut): Consumption of 20 houses - skill gain over 'igual a ontem'`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados_v1_corte_unico/figuras/ranking_casas_cons.png · relation: references
- `Mediana de todos os modelos (linha preta de referencia nos paineis das casas)` → `Painel 1: Usinas (skill 0,08-0,60 por regime)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/skill_por_dobra.png · relation: references
- `Regime B: mediana (skill mais alto, 0,40-0,60)` → `Toto-2.0-313m (FV das casas: 0,150 / 0,181 / 0,205)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/skill_por_dobra.png · relation: semantically_similar_to
- `Estratificacao de dias por condicao de ceu (limpo/tipico/nublado)` → `Protocolo de avaliacao v2 (numeros finais)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/dias_exemplo_cascavel.png · relation: rationale_for
- `Modelo Ensemble-mediana (regimes B e C)` → `Modelo TiRex-2 (regime A)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/dias_exemplo_cascavel.png · relation: shares_data_with
- `Referencias e linear fisico ausentes da figura` → `Metrica skill (eixo Y)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/custo_x_skill.png · relation: conceptually_related_to
- `Protocolo de dobras: 5 dobras nas usinas, 3 nas casas; fundacionais sem treino` → `Protocolo v2 com rolling origin e 36 modelos`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/custo_x_skill.png · relation: conceptually_related_to
- `Protocolo v2 com rolling origin e 36 modelos` → `Figura: custo computacional x skill (3 paineis)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/custo_x_skill.png · relation: references
- `Protocolo v2 (numeros finais regerados)` → `Figura: regimes de entrada meteorologica nas usinas (dumbbell A/C/B)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/regimes_usinas.png · relation: references
- `Vies dos fundacionais no consumo (~-20%)` → `Rankings divergem entre benchmarks estaticos e ao vivo`  [AMBIGUOUS]
  experimentos/testes_previsao/LEIA-ME.md · relation: conceptually_related_to
- `ECMWF IFS (fonte NWP day-ahead por tras do regime C)` → `Regime C: + previsao do tempo real (quadrado azul, day-ahead operacional)`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/regimes_usinas.png · relation: references
- `Intervalo de Confianca 95% por bootstrap por dia` → `Insight (ambiguo): os IC 95% dentro de um mesmo regime se sobrepoem fortemente, logo a ordem fina entre modelos vizinhos nao e estatisticamente distinguivel`  [AMBIGUOUS]
  experimentos/testes_previsao/resultados/figuras/ranking_usinas.png · relation: rationale_for

## Knowledge Gaps
- **128 isolated node(s):** `Chronos-2 — 10o lugar, skill ~ 0.182 (fundacional)`, `Chronos-Bolt-small — 6o lugar, skill ~ 0.190 (fundacional)`, `iTransformer — 17o lugar, skill ~ 0.161 (rede treinada)`, `Moirai-2.0-small — 16o lugar, skill ~ 0.170 (fundacional)`, `ResNet-1D — skill ~ 0.10 (penultimo entre os modelos treinados)` (+123 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 582 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **What is the exact relationship between `DLinear — skill ~ 0.08, pior modelo treinado do campo` and `SparseTSF — 7o lugar, skill ~ 0.189 (melhor rede treinada)`?**
  _Edge tagged AMBIGUOUS (relation: semantically_similar_to) - confidence is low._
- **Why does `Testes de modelos de previsao (36 modelos, 3 casos)` connect `Ambientes Python` to `Tarifas e regulacao BR`, `Metricas e referencias do benchmark`, `Protocolo v2 e filas`, `Linhagem e rede do projeto`, `Decisoes da biblioteca`, `Fundacionais lote 2`, `SparseTSF, casas e qualidade`, `Benchmark: achados e regimes`, `Embarcado e TFLite`, `ranking_usinas.png (14)`, `Revisao de literatura`?**
  _High betweenness centrality (0.222) - this node is a cross-community bridge._
- **What connects `Chronos-2 — 10o lugar, skill ~ 0.182 (fundacional)`, `Chronos-Bolt-small — 6o lugar, skill ~ 0.190 (fundacional)`, `iTransformer — 17o lugar, skill ~ 0.161 (rede treinada)` to the rest of the system?**
  _128 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Referencias, LightGBM e classicos` be split into smaller, more focused modules?**
  _Cohesion score 0.05443371378402107 - nodes in this community are weakly interconnected._
- **What is the exact relationship between `LightGBM — 1o lugar, skill ~ 0.205 (arvore)` and `Time-MoE-50M — 2o lugar, skill ~ 0.203 (fundacional)`?**
  _Edge tagged AMBIGUOUS (relation: conceptually_related_to) - confidence is low._
- **Why does `Modelos_previsao_geracao_consumo.xlsx (levantamento de 28/09/2026)` connect `Protocolo v2 e filas` to `Planilhas e documentacao (legado)`, `Revisao de literatura`, `Ambientes Python`?**
  _High betweenness centrality (0.217) - this node is a cross-community bridge._
- **Should `Planilhas e documentacao (legado)` be split into smaller, more focused modules?**
  _Cohesion score 0.05096153846153846 - nodes in this community are weakly interconnected._