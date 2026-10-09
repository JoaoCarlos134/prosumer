# CLAUDE.md — starting point for a new session

Snapshot written on 2026-10-05 from the work machine (Lactec), where the project lives in OneDrive
(`Documentos/2026/Projeto_IA`); state, findings and next steps updated on 2026-10-06 after the v2 +
batch 2 run finished on the home GPU. This repo is the exported, anonymized subset needed for the TCC, the
future master's and the `prossumidor` library. The user (João) works in English with Claude; all project
docs and code comments are in Portuguese (code comments without accents) — keep that convention.

## Ground rules

- **Private repo; plant data needs the teacher's permission.** The plant series came to the user through his
  teacher, who is responsible for them; publishing needs only the teacher's permission (he is open to it, but
  until he gives it explicitly — in writing — they stay private). Owner names were replaced by city ("Usina Cascavel", "Usina Curitiba"); Cascavel coordinates rounded to
  2 decimals (-24.83, -53.65). Never reintroduce names or exact coordinates. The name map exists only on the
  Lactec machine (`biblioteca_tcc/scripts/exporta_repo_prossumidor.py`, never copied here).
- **Licence is the author's decision (updated 2026-10-09).** Lactec is involved ONLY if the user formally
  ties the project to a Lactec project; otherwise licence and publication are the user's call (with the
  teacher's permission for the plant data). There is still **no LICENSE file**: don't add one until the user
  picks a licence (due before E6).
- **Audience (decided 2026-10-09): international core + Brazilian layer.** English code and main docs (power
  sector worldwide + research/dev community), plus a Brazilian economics module (ANEEL, bandeiras, tarifa
  branca, Lei 14.300) and a Portuguese guide. The user wants the option of a master's/doctorate abroad. The
  rename to English (package `prosumer` was free on PyPI on 2026-10-09) happens at the START of E2. Until
  then, existing code and docs stay in Portuguese.
- **The 20 houses** (`casas`, H1-H20) are the public dataset of Khadem et al. (2024), "Comprehensive Dataset
  on Electrical Load Profiles for Energy Community in Ireland", Scientific Data, doi:10.1038/s41597-024-03454-2
  (figshare doi:10.6084/m9.figshare.c.6829134). Dingle Peninsula, Ireland (Europe/Dublin, with DST), 2020,
  1-min. Licence **CC0**: they can be published and used as real example data — cite the paper.
  (Identified 2026-10-07; before that they were treated as unknown origin and kept private.)
- Re-syncing from Lactec is done there by rerunning the export script; files here may be overwritten by it.
  Commit work done here before a re-sync. Its default destination is the Lactec clone in
  `OneDrive - Lactec/Documentos/1Projects/prossumidor` (was `~/repos/prossumidor` until 07/10/2026).

## Layout

- `docs/proposta/` — `Proposta_TCC_prossumidor.pdf` (10 pages, steps E0–E8, ~580 h, 9 months),
  `PROPOSTA_BIBLIOTECA.md` (8 modules, where each comes from), `gera_proposta_tcc.py` (needs reportlab).
- `docs/projeto/` — `ia_solar/ESTADO_DO_PROJETO.md` (plant analyses, pending items),
  `ia_solar/PLANO_ARTIGO.md` (papers A and B), `REDE_PROJETO.md` (project graph analysis), `RESUMO_*.txt`.
- `docs/literatura/` — `Visao_geral_modelos_previsao.xlsx` (127 models found, which were tested and why the
  rest weren't, no results), `Modelos_previsao_geracao_consumo.xlsx` (same survey with a results column),
  references, review draft `smart_buildings.docx`.
- `experimentos/testes_previsao/` — the forecasting benchmark (details below). `LEIA-ME.md` there is the
  v2 write-up (rewritten 2026-10-06), with the protocol, the final numbers and the six defects fixed
  along the way; `ambientes/LEIA-ME.md` has the install deviations each of the four envs needs.
- `legado/` — the project's original scripts (ia_solar analysis, modelling base, TFLite models, ANEEL
  tariffs, graph scripts). Reference only: raw 5-min data stayed at Lactec, so most won't run here.
  Some file names were changed by the anonymization (e.g. `*_curitiba*` scripts).

## The forecasting benchmark (`experimentos/testes_previsao/`)

Task: forecast the next day's 24 hourly values, issued at 00:00. Protocol lives in `scripts/comum.py`.
Cases: `usinas` (Cascavel 3.96 kWp + Curitiba ~9.6 kWp, test 2025-08-01→2026-05-31), `casas_prod`
(10 houses with PV), `casas_cons` (20 houses; test 2020-10-01→12-31). Skill = 1 − RMSE/RMSE of the reference
(clear-sky persistence for plants, "same as yesterday" for houses); 95% CI by day bootstrap.

Regimes (plants only beyond A):
- **A** history only. **B** + NASA weather of the day itself (perfect forecast, a ceiling).
- **C** + the real day-ahead NWP forecast (ECMWF IFS 0.25°, Open-Meteo Previous Runs, `*_previous_day1`),
  in training and test. Archive starts 2024-03-06, so C trains from 2024-03-07. Value labelled h+1 covers
  hour h. Diagnostics: `B-curto` (B with C's short training), `C-gfs` (GFS instead of ECMWF).

**Protocol v2 (2026-10-05):** rolling origin — every trained model is retrained from scratch at each fold
start (plants: 5 folds of 61 days; houses: 3 of ~31 days); identical batch settings for all networks;
regime C added. `05_avalia.py` writes metrics per fold, Diebold–Mariano vs the best model with Holm
correction (`dm_vs_melhor.csv`), and between regimes (`dm_regimes.csv`). v1 (single cut) is kept in
`resultados_v1_corte_unico/` for reference.

Pipeline (run from `scripts/`):

    02_referencias.py            references, linear physics, LightGBM (all regimes, all folds) — DONE in v2
    03_fundacionais.py           zero-shot foundation models (A/B done in v1, unchanged; C done in v2)
    03b_moirai.py                Moirai 2.0 (moirai env)
    04_redes_treinadas.py        trained networks; skips anything already in resultados/tempos_redes_*.json
    03c_fundacionais_lote2.py    batch 2 foundation models (lote2 / lote2_hf / moirai envs)
    07_ensemble.py → 05_avalia.py → 06_figuras.py
    roda_v2.py                   runs the v2 trained-network queue (plants and houses in two processes)
    roda_lote2.py                waits for v2's FIM lines, then runs batch 2 + ensemble + metrics + figures
    08_previsao_tempo.py         re-downloads the Open-Meteo forecast archive (already in dados/)
    09_clima_casas.py            measured weather of the houses (Dingle station, figshare CC0) -> dados/clima_casas_horario.parquet
    01_prepara_dados.py          builds dados/*.parquet from Lactec raw data — does NOT run here

Environments: four, frozen in `ambientes/*.txt` (see `ambientes/LEIA-ME.md` for uv commands). Scripts
expect them in `~/.venvs/<name>` (override with `VENVS`). `previsao` runs almost everything.

### State (2026-10-06) — v2 + lote 2 COMPLETOS na maquina de casa (RTX 4070)

A rodada acabou. Tudo o que a v2 e o lote 2 previam esta feito, em GPU, sem falhas pendentes:
52 entradas de rede treinada (todas com `dispositivo` anotado), 25 fundacionais v1 + 28 do lote 2,
131 linhas em `resultados/metricas.csv`, 7 figuras e os quatro CSVs de metricas regenerados.
Os 9 modelos que tinham rodado em CPU no Lactec foram refeitos em GPU para paridade de hardware.

Detalhes do protocolo, dos resultados e dos seis defeitos corrigidos no caminho:
`experimentos/testes_previsao/LEIA-ME.md` (reescrito para a v2 em 06/10/2026).
Desvios de instalacao dos quatro ambientes: `experimentos/testes_previsao/ambientes/LEIA-ME.md`.

Dois pontos que mudam numeros e precisam estar no texto do TCC:

- **TiDE nao usava o clima** nas versoes anteriores (LayerNorm sobre `temporal_width` apagava a
  amplitude das exogenas hora a hora). Corrigido com `layernorm=False`: skill em B de +0,07 para
  +0,487, em C para +0,356. Antes era a unica excecao no teste C x B; agora as 15 comparacoes dao
  significativas.
- **Normalizacao ajustada sobre o teste.** O `local_scaler_type` do NeuralForecast normalizava sobre
  todo o quadro, teste incluido. Trocado por `comum.normaliza_por_treino` (so treino anterior a
  validacao), com regressoes em `scripts/test_auditoria.py`. Efeito pequeno nos numeros, mas o
  procedimento anterior nao era defensavel. As entradas de B e C carregam o selo `normalizacao`.

### Findings so far

**v1 (corte unico):** a entrada de clima importa ~10x mais que o modelo (vao A->B ~0,40 contra ~0,03
entre modelos); um linear sobre uma variavel fisica chega a +0,42; fundacionais zero-shot empatam com
os treinados; SparseTSF (32 parametros) empata no consumo; LSTM/GRU so com historico perdem da
persistencia de ceu claro nas usinas.

**v2 (origem movel, 36 modelos, numeros de 06/10/2026 — registro; atuais, com o passo T, em `metricas.csv` e na
planilha do congresso: a mediana caiu para +0,508 e 2a nas usinas em B, atras do TiRex-2 +0,509, empatada):**

- A escada das usinas: melhor em **A +0,141** (TiRex-2) -> **C +0,372** -> **B +0,515** (mediana de
  todos nos dois ultimos). LightGBM nos cinco regimes: A +0,084, C-gfs +0,274, C +0,330,
  B-curto +0,469, B +0,480.
- A previsao real fecha **62%** do vao A->B no LightGBM e **72%** na mediana dos 12 modelos com os tres
  regimes. (A figura de regimes imprime a mediana; nao confundir com o numero do LightGBM.)
- O que falta e **qualidade da previsao, nao treino curto**: B-curto x B nao e significativo
  (Holm 0,081 no LightGBM, 0,070 no linear fisico). ECMWF ganha do GFS (C-gfs x C, p < 0,001).
  C x A e C x B significativos em todas as comparacoes (13/13 e 15/15).
- **Fundacionais lideram os tres casos no regime A.** Melhor ranking medio: Toto-2.0-313m (3,0),
  depois a mediana (4,3) e o TiRex-2 (6,3). TiRex-2 e o melhor modelo individual nas usinas nos tres
  regimes. Toto-2.0-313m e o 1o na geracao FV das casas; LightGBM o 1o no consumo.
- **Correcao da correcao sobre a mediana:** ela e 1a nas usinas em B e C, **2a** em A (o TiRex-2
  passou a frente) e na geracao FV, e **9a de 32** no consumo — ainda empatada com a melhor. Os textos
  antigos que dizem "5a no consumo" ou "nunca abaixo de 2o" estao desatualizados: o lote 2 acrescentou
  8 modelos fortes no consumo.
- Quantos empatam com o melhor (Holm >= 0,05): usinas A 3 de 33, B 1 de 15, **C nenhum de 15**;
  geracao FV das casas 21 de 32; consumo 9 de 32 (inclusive o SparseTSF de 32 parametros). O poder de
  separacao do teste muda muito de caso para caso.

## Machines

Duas maquinas, um repositorio. Trabalhar sempre em `main` (o ramo `correcoes-v2-gpu` foi juntado em
07/10/2026 e so fica como historico).

| | Lactec (trabalho) | Casa |
|---|---|---|
| Clone | `OneDrive - Lactec/Documentos/1Projects/prossumidor` (atalho em `2026/Projeto_IA`) | — |
| GPU | **nenhuma**: os quatro ambientes tem torch `+cpu` | RTX 4070 (torch cu128/cu130) |
| Ambientes | `~/.venvs/{previsao,lote2,lote2_hf,moirai}` iguais aos `.txt` congelados (conferido 07/10) + `~/.venvs/prossumidor` (biblioteca, `-e .[dev,graficos,lightgbm]`, pre-commit instalado) | os quatro, ver `ambientes/LEIA-ME.md` |
| TTM (`tsfm_public.toolkit`) | **funciona** | quebrado (instala sem o subpacote) |
| Dados brutos / exportador | sim (`Projeto_IA/biblioteca_tcc/scripts/exporta_repo_prossumidor.py`) | nao |

O que roda em cada uma: biblioteca, avaliacao (`05_avalia.py`, `06_figuras.py`), referencias, LightGBM,
fundacionais zero-shot e o ajuste fino do TTM rodam bem em CPU (Lactec). Redes treinadas em origem
movel e o TabPFN-TS ficam para a GPU de casa (`DISPOSITIVO=cuda`); sem GPU o `roda_lote2.py` ja pula o
TabPFN-TS. Os venvs ficam fora do OneDrive de proposito (milhares de arquivos sincronizando).

### Estado em 09/10/2026 (fim da sessao na maquina de casa)

`metricas.csv` tem **243 linhas e 51 modelos**. Entraram nesta sessao: regime B das casas (completo),
8 redes do passo T, 4 classicos do sklearn e 3 dos 4 classicos estatisticos.

**O que esta COMPLETO:** regime B das casas (24 redes + TiRex-2 + TabPFN-TS); as redes do passo T
(DeepAR, FEDformer, Autoformer e Informer em A/B/C; TimeMixer, TimeXer e TimesNet so em A);
Ridge, RandomForest, MLP e kNN em todos os casos e regimes; AutoETS, AutoTheta e MSTL nos tres casos.

**O que FALTA, e e a unica coisa pendente do passo T:** `AutoARIMA` em 6 combinacoes
(usinas B e C, casas_prod A e B, casas_cons A e B). Com os padroes do StatsForecast levou 15,2 h em
usinas|A; a configuracao reduzida (`approximation=True`, ordens limitadas) esta no `02b_classicos.py`
mas **nunca foi medida ate o fim** — a medicao em usinas|B foi interrompida. Medir UM caso antes de
soltar os seis. Rodar com `python 02b_classicos.py <caso> --regimes <A|B> --modelos AutoARIMA`,
um por processo.

**Custo dos classicos estatisticos nesta serie horaria (vale como resultado):** AutoETS cobre os tres
casos em 250 s; AutoTheta precisa de 4,8 h em usinas|A (139 s e 622 s nas casas); MSTL 2,3 h em
usinas|A; AutoARIMA 15,2 h em usinas|A no padrao. A familia e pouco pratica nesta resolucao.

**Bloqueios desta maquina (nao existem no Lactec):**

- O App Control bloqueia o `_native` do `hypothesis`, e o plugin do pytest carrega o hypothesis
  sempre: **a suite da biblioteca nao roda aqui**, nem com `-p no:hypothesis`. Ja esta na ultima
  versao, entao reinstalar nao muda os bytes. Rodar `pytest` no Lactec ou deixar para a CI. O teste de
  regressao contra o `metricas.csv` nao foi executado nesta ultima rodada por causa disso.
- O mesmo bloqueio tirou o `torch 2.11.0+cu128` do ambiente `previsao`, que foi para `2.14.1+cu130`.
- TimeLLM saiu do conjunto de redes: estoura o commit charge (limite 40,8 GB, folga ~13 GB) e derrubou
  a maquina quatro vezes. Ver o comentario no `04_redes_treinadas.py`.

**Armadilha de automacao, para nao repetir:** `subprocess.run(timeout=...)` marcou as etapas como
canceladas mas **nao matou os processos filhos** — AutoTheta e MSTL seguiram rodando soltos e
terminaram horas depois. Dois efeitos: um runner que espera `FIM` de outro pode esperar para sempre (foi
o que deixou 13 h sem produzir nada), e dois processos do mesmo script sobrescreviam o
`tempos_classicos.json` (corrigido: agora rele o arquivo antes de gravar).

### Cuidados novos de 08/10/2026 (maquina de casa)

- **O ambiente `previsao` esta com `torch 2.14.1+cu130`, nao mais 2.11.0+cu128.** A politica de
  Controle de Aplicativo do Windows passou a bloquear o `torch/lib/shm.dll` da versao antiga de forma
  persistente (`WinError 4551`; nao e o bloqueio transitorio de primeiro acesso, e reescrever o arquivo
  nao resolve). As 52 entradas originais de rede treinada sao de 2.11.0 e as do passo T sao de 2.14.1 —
  confundimento de versao a declarar. Nao desliguei o Smart App Control: no Windows e irreversivel e
  havia alternativa. Se um dia faltar alternativa, o caminho e o WSL2, nao desligar a protecao.
- **AutoARIMA so roda com configuracao reduzida.** Com o padrao levou 15,2 h em `usinas|A`. Agora usa
  `approximation=True` e ordens limitadas; a configuracao fica em cada entrada de
  `tempos_classicos.json`. Medir um caso antes de soltar os seis.
- **Memoria e o gargalo desta maquina, nao a GPU.** Tres rodadas morreram por falta de RAM (lote de 32
  do Time-MoE = 13 GB; redes do passo T junto com os classicos; o TimeLLM carrega um LLM). Rodar em
  lotes pequenos, um processo por lote, e nao misturar fila de CPU com fila de GPU.

## Where to continue (handoff de 07/10/2026, maquina do Lactec)

Feito em 07/10: ramo juntado em `main`; CI consertada (venv do setup-uv, nao `--system`); pre-commit com
mypy 2.4 e `.gitattributes` LF; **teste de regressao** `tests/test_regressao_benchmark.py` (recalcula as 131
linhas de `metricas.csv` com a biblioteca, igualdade numerica; 184 testes no total); plano do TCC em
`docs/proposta/Plano_TCC_simples.tex`; aba Testaveis e `Comparacao_modelos_regimes_A_B.xlsx` em
`docs/literatura/`; casas identificadas (CC0, Dingle). **O que isso muda na biblioteca** esta na secao 5c
de `docs/proposta/PROPOSTA_BIBLIOTECA.md` — ler antes de mexer em `contratos`, `protocolo` ou adaptadores.

**PLANO (revisao de 09/10/2026, Lactec). Fonte: `docs/proposta/Plano_TCC_simples.tex` (secoes 4-8).**
Prioridade: a BIBLIOTECA. Artigos sao subprodutos e nao atrasam a E2. Regra: toda melhoria comeca por um
PILOTO curto (1-4 h, um caso) e so vira trabalho completo se passar no PORTAO. Nada de rodada longa as cegas.

Pilotos ja feitos em 09/10 (sobre as previsoes gravadas, sem rodar modelo; ver PROPOSTA 5c):
- Correcao de vies causal (fator = real/previsto dos ultimos 14 dias, por serie): no CONSUMO leva o vies
  dos fundacionais de ~-20% a <1% e sobe a mediana de +0,191 para +0,207 (empata com o LightGBM); na
  GERACAO SOLAR piora ate -0,10 (Chronos-2 casas_prod B de +0,214 para +0,113). => so para consumo.
- Como combinar: escolher o melhor da dobra anterior piora em todos os 7 testes (ate -0,23); top-5/top-10
  instavel. => mediana de todos como saida; a biblioteca NAO escolhe modelo.
- Resolucao (consumo, LightGBM): hora R2 0,37 / skill +0,21; pico 17-20h 0,35 / +0,16; noite-dia 0,69 /
  +0,12; dia 0,58 / +0,10 (mediana +0,01; media 7 dias +0,04). 20 casas somadas: R2 0,64.

Pilotos feitos no Lactec em 09/10 a tarde (scripts `piloto_*.py`; saidas em `resultados/pilotos/`, FORA de
`previsoes/`: nao entram na mediana nem no metricas.csv; resumo em `resultados/pilotos/resumo.json`):
- **FlowState** (IBM, 9,1 M param., zero-shot, CPU): consumo A +0,192 (8o/47, empata com o melhor, p 0,098);
  FV casas A +0,134 (7o/47); usinas A +0,114 (5o/49). PASSOU o portao e ENTROU no benchmark em 09/10
  (`03_fundacionais.py FlowState`; as 3 previsoes do piloto foram gravadas com o mesmo `comum.grava`, janelas
  conferidas): 52 modelos, 246 linhas; mediana em A subiu 0,0003-0,0017; 3o no ranking geral do congresso. Melhor que
  o TTM na geracao solar (+0,134 x +0,119; +0,114 x +0,092): segundo candidato pequeno (Raspberry Pi; nao cabe
  no ESP32). ~0,4 s por janela em CPU. Devolve quantis (util no piloto F2c). So roda no Lactec.
- **Ajuste fino do TTM-r2** (F2e, origem movel, so dados anteriores a dobra): PIORA nos 3 casos. So a cabeca,
  lr 1e-4: consumo +0,181 (zero-shot +0,191), FV +0,100 (+0,119), usinas +0,075 (+0,092). Decoder + cabeca,
  lr 1e-3: consumo +0,148. => F2e REPROVADO com evidencia para o TTM: a biblioteca usa o TTM sem ajuste.
  (Ajuste fino do Chronos nao foi testado.)
- **GPU x CPU** (sobre as previsoes gravadas): o MELHOR modelo de cada teste roda em CPU (TiRex-2, Toto-2.0-313m,
  Chronos-2, LightGBM). A mediana so dos modelos de CPU (sem redes treinadas e TabPFN-TS) fica igual ou melhor
  em 4 dos 7 testes (consumo A +0,200 x +0,191) e no maximo 0,016 abaixo (usinas B). => a biblioteca e o
  aplicativo rodam SO EM CPU; a GPU so serve ao benchmark (etapa A e redes).

| Etapa | Horas | Onde | O que, e o PORTAO |
|---|---|---|---|
| F0 Decisoes | 0 | — | Idioma DECIDIDO (internacional + camada BR, ver Ground rules). Pendentes: licenca (do autor, antes da E6); permissao por escrito do professor para os dados das usinas; comprar Raspberry Pi 5 + ESP32 |
| F1 Fechar o teste | 17 | ver linha | (a) **casa:** congelar `classicos` e atualizar `previsao.txt` (torch 2.14.1+cu130), 0,5 h. (b) avaliacao por resolucao (hora, noite-dia, pico 17-20h, dia) no `05_avalia.py` e aba na planilha do congresso, 3 h. (c) `Ensemble-mediana-corrigida` so no consumo (correcao de vies acima), 2 h. (d) AutoARIMA: medir 1 caso com a config reduzida; PORTAO < 2 h/caso -> rodar os 6 e refazer `usinas|A` reduzido; senao relatar como inviavel em resolucao horaria. (e) MLP: piloto de ajuste em casas_prod A (alpha maior, validacao temporal); PORTAO ganho >= 0,05 e estavel, senao rotular "sem ajuste". (f) TimesFM-3, FlowState (Lactec), BuildingsBench (so consumo): piloto em casas_cons A; PORTAO entrar no grupo da frente, senao parar |
| **A Modelos pendentes** | 40 | casa (GPU) e Lactec | Os 13 pendentes (Moirai 1, CycleNet, VisionTS, MOMENT, Lag-Llama, DUET, Crossformer, Mamba/S-Mamba, xLSTM, TimeGrad, Time-LLM, LLMTime, TimeGPT): para CADA um, estudar como funciona (artigo, matematica), o que pode acrescentar e como fazer rodar; depois piloto num caso. **Regra do usuario (09/10): nao descartar modelo sem estudo + evidencia.** PORTAO para o teste completo: empatar com o melhor num caso ou trazer algo que nenhum outro traz (clima sem treino, tamanho de embarcado, faixa, dependencia entre series). Tabela com o porque de cada um: secao 7 do plano |
| F2 Pilotos de melhoria | 22 | CPU | Cada um num caso; PORTAO skill +0,02 (ou faixa calibrada): (a) combinar 2-3 NWP no regime C (IFS + AIFS + GFS/ICON, Open-Meteo Previous Runs; conferir arquivo) com LightGBM nas usinas; (b) estimar inclinacao/azimute de cada telhado pelos dados (`legado/.../a1_geometry.py`) e usar POA no B das casas; (c) quantis: LightGBM quantilico + quantis do Chronos-2, medir CRPS e cobertura; (d) atualizacao ao meio-dia (pico 17-20h); (e) ajuste fino do TTM (Lactec, granite-tsfm completo); (f) modelo direto para o total do dia (consumo) |
| F2b Levar para a biblioteca | ~40 | qualquer | so os pilotos que passaram |
| E2 Versao 0.1 | 130 | qualquer | PRIMEIRO trocar nomes e API para ingles (~10 h); depois portar o protocolo (normaliza_por_treino, interpolacao CAUSAL so do historico, mascara de horas, corte de negativos, exogenas, passo regular), metricas em varias resolucoes, `ranking()` e `empata_com_melhor()`, `fisica`, `io` (Fronius, medidores, clima: NASA, estacao local, Open-Meteo com checagem de cobertura), `qualidade` (verificacao do relogio pelo sol, proveniencia/licenca), `previsao` com metadados (GPU, licenca, envio de dados), mediana como saida (+ correcao de vies no consumo), `dados.casas_dingle()` |
| E3 Checagem 1 | 30 | qualquer | o benchmark refeito so com a biblioteca bate com as 243 linhas |
| E4 Versao 0.2 | 130 | qualquer | diagnostico; embarcado (TTM, SparseTSF, Ridge/RandomForest via emlearn, previsao do dia e por bloco de tarifa) |
| E5 Hardware | 50 | — | Raspberry Pi 5 e ESP32 |
| E6 Versao 0.3 | 110 | qualquer | economia: tarifas por horario genericas + modulo brasileiro (tarifa branca, bandeiras, Lei 14.300); documentacao em ingles + guia em portugues; licenca escolhida pelo autor; publicacao |
| **App: o TCC (ultimo passo)** | 120 | qualquer | So com a biblioteca pronta. Aplicativo facil de usar que recebe os dados do usuario (inversor, medidor, conta de luz) e faz a analise completa: qualidade (com relogio pelo sol), diagnostico, previsao comparada (mediana, regimes, resolucoes), economia, modelo para aparelho, e um relatorio. Duas formas, ambas ja feitas pelo autor: pagina web local em Streamlit como `1Projects/Keyword_map` (SciKeywordMap) ou programa de computador como `1Projects/Loom` (FastAPI + pywebview, sem servidor nem admin). Usa so a interface publica da biblioteca. PORTAO: um usuario sem programar faz a analise do comeco ao fim. Por isso a E2 ja desenha a API pensando nele: uma chamada que faz a analise completa e devolve um relatorio |
| E7 Escrita | 80 | — | em paralelo; o TCC descreve o APLICATIVO, a biblioteca por tras dele e as checagens |

Descartado SO com evidencia (testado): escolher "o melhor modelo" (piora/instavel) e correcao de vies na geracao
solar (piora ate -0,10); TimesNet so no A porque ignora o clima. Nada mais sai sem estudo + piloto (etapa A).
Ainda valem da revisao: `02b_classicos.prepara` interpola a serie inteira antes das dobras (nenhuma origem
afetada hoje; a biblioteca nao copia isso); LightGBM nao e bit a bit reprodutivel entre maquinas (<= 0,0006);
redes em duas versoes de torch (2.11 e 2.14.1). Total do plano: ~769 h (~12 meses, ate out/2027), com o
aplicativo (o TCC) no fim.

Cuidados: o exportador do Lactec (`Projeto_IA/biblioteca_tcc/scripts/exporta_repo_prossumidor.py`) copia
arquivos antigos por cima dos novos — nao rodar sem antes comparar; o repositorio e a copia principal.
No Windows, editar arquivos com Python grava CRLF: o gancho `mixed-line-ending` conserta e derruba o
commit uma vez, e so adicionar de novo.

## Next steps

1. TCC passo **E2** (versao 0.1). O E1 (esqueleto, contratos, dados sinteticos, CI) esta feito e o teste de
   regressao contra `metricas.csv` tambem (07/10). O que falta do E2 esta na tabela acima.
2. **Teste ampliado (passo T, ~80 h, GPU de casa, nov-dez/2026):** dos 99 modelos do levantamento nao
   testados, 70 nao tem codigo e 5 pedem satelite ou supercomputador; os 24 com codigo entram agora
   (mais forca para as conclusoes, nao para muda-las). Redes do NeuralForecast 3.1.9 ja instalado (9):
   TimeMixer, TimesNet, DeepAR, TimeXer, FEDformer, Autoformer, Informer, xLSTM, Time-LLM. Fundacionais (8):
   Moirai 1, MOMENT, VisionTS, Lag-Llama, FlowState (granite-tsfm: so no Lactec), BuildingsBench (so
   consumo), TimesFM-3 (pesos nao comerciais: so pesquisa), TimeGPT (API paga externa: so casas, NUNCA
   usinas). Repositorios proprios (5): CycleNet, DUET, Crossformer, S-Mamba, Mamba (mamba_ssm: talvez WSL).
   Outros (2): LLMTime, TimeGrad. Mais o regime C com o ECMWF AIFS (IA) no lugar do IFS, se a Open-Meteo
   tiver arquivo historico. Depois: 07 -> 05 -> 06 e atualizar a coluna "Testado" da planilha.
   Plano completo em `docs/proposta/Plano_TCC_simples.tex` (fonte editavel do PDF).
3. Ainda aberto nos testes: ajuste fino do TTM/Chronos-2 (o `granite-tsfm` esta incompleto na maquina
   de casa, mas **funciona no Lactec** — fazer la, em CPU), previsao probabilistica (CRPS), vies de
   consumo dos fundacionais (~-20%), ceu claro das casas (localizacao agora conhecida: peninsula de Dingle, Irlanda), latencia/energia no
   Raspberry Pi 5 / ESP32 (passo E5 da proposta).
4. TFLite (feito em 05/10/2026 no Lactec, `legado/ia_solar/base_modelagem/referencia/verifica_tflite.py`):
   os 32 `.tflite` em `legado/ia_solar/base_modelagem/embarcado/` foram recarregados do disco e todos
   reproduzem o R2 original (`verificacao_tflite.csv`). O `.tflite` guarda so a rede: imputacao,
   escala e desnormalizacao foram reconstruidas e salvas em
   `embarcado/preprocessamento_<usina>_<conjunto>.json` — um dispositivo precisa do arquivo + JSON.
   A latencia x86 (~2,5 us float, ~11 us int8) e overhead de chamada Python, nao custo de rede.
5. Lacunas conhecidas do projeto: geometria do telhado de Curitiba desconhecida (travam os artigos A e
   B); artigos A e B sem bibliografia.
