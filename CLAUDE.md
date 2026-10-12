# CLAUDE.md — starting point for a new session

Snapshot written on 2026-10-05 from the work machine (Lactec), where the project lives in OneDrive
(`Documentos/2026/Projeto_IA`); state, findings and next steps updated on 2026-10-06 after the v2 +
batch 2 run finished on the home GPU. This repo is the exported, anonymized subset needed for the TCC, the
future master's and the `prosumer` library (called `prossumidor` until 2026-10-09; GitHub repo renamed to
`JoaoCarlos134/prosumer` on 2026-10-11, the old URL redirects; the home folder became `Downloads/projects/prosumer` the same day,
via `~/renomeia_prosumer.ps1`, which also fixes the editable install, graphify's root and copies the Claude Code memory;
at Lactec rename the clone to `1Projects/prosumer`, run `git remote set-url origin https://github.com/JoaoCarlos134/prosumer.git` and change the exporter's default destination). The user (João) works in English with Claude. The LIBRARY (`src/prosumer/`,
`tests/`, README, pyproject) is in English since 2026-10-09; project docs, benchmark scripts and their
comments stay in Portuguese (code comments without accents) — keep that convention there.

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
  rename to English was DONE on 2026-10-09 (package `prosumer`, free on PyPI that day; recheck before
  publishing). Name map old -> new: top of `docs/proposta/PROPOSTA_BIBLIOTECA.md`. New library code is
  written in English; the benchmark keeps its Portuguese files and CSV columns (`metricas.csv` unchanged).
- **The 20 houses** (`casas`, H1-H20) are the public dataset of Khadem et al. (2024), "Comprehensive Dataset
  on Electrical Load Profiles for Energy Community in Ireland", Scientific Data, doi:10.1038/s41597-024-03454-2
  (figshare doi:10.6084/m9.figshare.c.6829134). Dingle Peninsula, Ireland (Europe/Dublin, with DST), 2020,
  1-min. Licence **CC0**: they can be published and used as real example data — cite the paper.
  (Identified 2026-10-07; before that they were treated as unknown origin and kept private.)
- Re-syncing from Lactec is done there by rerunning the export script; files here may be overwritten by it.
  Commit work done here before a re-sync. Its default destination is the Lactec clone in
  `OneDrive - Lactec/Documentos/1Projects/prossumidor` (to be renamed `prosumer`: update the exporter) (was `~/repos/prossumidor` until 07/10/2026).

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
    05b_resolucao.py             metricas em 4 resolucoes (hora, dia/noite, pico 17-21 h, dia); roda no ambiente da
                                 BIBLIOTECA (usa prosumer.metrics.by_resolution) e confere o skill por hora
    atualiza.py                  ONE command for everything derived from saved forecasts: 07 -> 05 -> 06 -> 05b ->
                                 both spreadsheets -> regression test, each in its env (~1 min). Use after any new model
    redes_proprias.py            SparseTSF, ResNet-1D, CycleNet + their training loop, shared by 04 and the pilots
    piloto_*.py, piloto_comum.py step-A / F2 pilots; outputs in resultados/pilotos/, never in metricas.csv
    historico/                   finished one-off queues (roda_v2, roda_lote2, roda_B, ...): record only, don't rerun
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
| Ambientes | `~/.venvs/{previsao,lote2,lote2_hf,moirai}` iguais aos `.txt` congelados (conferido 07/10) + `~/.venvs/prossumidor` (biblioteca; **reinstalar** apos o nome novo: `uv pip install -e ".[dev,plots,lightgbm]"`, os extras mudaram de nome; os scripts agora citam `~/.venvs/prosumer`) | os quatro, ver `ambientes/LEIA-ME.md` |
| TTM (`tsfm_public.toolkit`) | **funciona** | quebrado (instala sem o subpacote) |
| Dados brutos / exportador | sim (`Projeto_IA/biblioteca_tcc/scripts/exporta_repo_prossumidor.py`) | nao |

O que roda em cada uma: biblioteca, avaliacao (`05_avalia.py`, `06_figuras.py`), referencias, LightGBM,
fundacionais zero-shot e o ajuste fino do TTM rodam bem em CPU (Lactec). Redes treinadas em origem
movel e o TabPFN-TS ficam para a GPU de casa (`DISPOSITIVO=cuda`); sem GPU o `historico/roda_lote2.py` pulava o
TabPFN-TS. Os venvs ficam fora do OneDrive de proposito (milhares de arquivos sincronizando).

### Estado em 09/10/2026 a tarde (maquina de casa): Smart App Control e o nome em ingles

Feito: reset para o `origin/main` reescrito (o HEAD antigo ficou no ramo local
`backup-pre-reescrita-2026-10-09`, mesmo conteudo do `c6b5726`); identidade git = endereco noreply do GitHub;
`classicos.txt` congelado e `previsao.txt` recongelado (torch `2.14.1+cu130`, + openpyxl, packaging 26.3);
**biblioteca renomeada para `prosumer` com a API em ingles** (mapa no topo da PROPOSTA_BIBLIOTECA.md);
`05b_resolucao.py`, `07_ensemble.py` e `piloto_comum.py` atualizados para a API nova; o
`metricas_por_resolucao.csv` regerado sai identico. Testes: 320 de 321 passam aqui (todo o teste de
regressao contra o `metricas.csv` incluido); o unico de fora e o de propriedade do hypothesis.

**O Smart App Control passou a bloquear (09/10, ~12:30) coisas que rodavam no dia anterior:**

- o `python.exe` do CPython 3.12.13 do uv (`~/AppData/Roaming/uv/python/cpython-3.12.13...`): todo venv 3.12
  parou. **Conserto aplicado:** Python 3.12.10 oficial (assinado, `winget install Python.Python.3.12`, em
  `~/AppData/Local/Programs/Python/Python312`). Nos venvs `previsao`, `lote2`, `lote2_hf` e `classicos` o
  `home` do `pyvenv.cfg` aponta para ele e o `Scripts/python(w).exe` foi trocado pelo lancador oficial
  (`Lib/venv/scripts/nt/`), porque o lancador do uv traz o caminho do interpretador antigo gravado dentro.
  Originais guardados como `pyvenv.cfg.uv31213.bak` e `Scripts/python.exe.uv.bak`. O `.venv` do repositorio
  foi recriado sobre o 3.12.10. O 3.11 (moirai) e o 3.14 do uv continuam rodando.
- **`torch 2.14.1+cu130` (`torch/lib/c10.dll`) em `previsao` e `lote2`: a GPU esta INUTILIZAVEL nativamente.**
  O `torch 2.8.0+cpu` do `lote2_hf` carrega. Testado num venv descartavel: **`torch 2.9.1+cu128` carrega e
  roda na GPU**; `2.14.1+cu126` tambem e bloqueado (`shm.dll`). Opcoes: (1) um ambiente novo com torch
  2.9.1+cu128 para a etapa A (terceira versao de torch no benchmark, declarar; as 52 + passo T ficam como
  estao); (2) WSL2 (a nota da memoria dizia "adiar ate o TTM/embarcado": este e o gatilho). Nunca desligar
  o Smart App Control (irreversivel). **Decidido 09/10: opcao (1).** Ambiente `~/.venvs/previsao_gpu`
  (= `previsao` com `torch==2.9.1+cu128`, congelado em `ambientes/previsao_gpu.txt`) e o que roda redes e
  modelos na GPU daqui para frente; `torch.cuda.is_available()` True, imports do benchmark ok (o
  `tsfm_public.toolkit` falta, como no `previsao`). Os scripts escolhem o ambiente pelo `VENVS`/nome: para a
  etapa A, chamar `~/.venvs/previsao_gpu/Scripts/python.exe` direto.
- `pyarrow 26.0.0`: bloqueado; o `.venv` usa `pyarrow==25.0.1` (o `classicos` ja tinha 25.0.1).
- `mypy` (compilado com mypyc, e o `librt` que ele usa): bloqueado. Rodar o mypy na CI ou no Lactec.
- `hypothesis._native`: continua bloqueado (so o teste de propriedade de `test_contracts.py`).

Para rodar a suite aqui: `.venv/Scripts/python.exe -m pytest -p no:hypothesispytest --ignore=tests/test_contracts.py`.

**Etapa A (iniciada 09/10 a tarde):** registro em `docs/projeto/ESTUDO_ETAPA_A.md` (como funciona, o que
acrescenta, como rodar, piloto, decisao, para cada modelo). Ambiente: `~/.venvs/previsao_gpu` (+ o pacote de
cada modelo com `--no-deps`, refazendo o freeze). Feitos: **VisionTS++ PASSA** (FV das casas, 9o/48, empata com o
Toto-2.0-313m, p 0,14; devolve quantis) -> **entrou no benchmark em 09/10** (`03_fundacionais.py VisionTS++`,
no ~/.venvs/previsao_gpu, GPU; previsoes identicas as do piloto): **54 modelos, 251 linhas**; so as medianas do A
mudaram (+0,0002 a +0,001); regressao, 05b e as duas planilhas regeradas; **VisionTS nao passa**; **Moirai 1.1 nao passa**
(usa mal o clima: ultimo em B nas usinas; patch 16 da ~zero, so 32/64 valem no horario). **CycleNet PASSA** (Linear, ciclo de 24 h: 6o de 49 na FV das casas com 4.296 parametros,
empata, p 0,13, estavel em 3 sementes; +0,139 contra +0,033 do SparseTSF) -> **entrou no benchmark em 09/10** (em CPU: na GPU o gather nao e determinístico): **55 modelos, 254 linhas**.
**MOMENT nao passa** (3 tamanhos x 3 casos: terco de baixo; cabeca linear sobre codificador congelado). **Lag-Llama nao passa**
(10/10; contexto 32: FV das casas -0,037, 43o/50; consumo +0,084, 42o/51; subestima ~1/3; contexto 256 rodou
3 h 09 min sem terminar um caso e foi interrompido; ambiente proprio `~/.venvs/lagllama`, ver o ESTUDO). **DUET nao passa** (10/10; 3 casos: 26o-36o; menor, d_model 64: FV das
casas 16o/50, p 0,035; consumo 36o). **xLSTM nao passa** (10/10, NeuralForecast + `xlstm` --no-deps, CUDA_HOME = pasta do
torch; consumo +0,159 26o, FV +0,035, usinas -0,55; o `xlstm` foi DESINSTALADO depois: instalado, quebra o
`from neuralforecast import models` sem CUDA_HOME). **Crossformer PASSA** (10/10; TSLib em ~/.cache/tslib-repo,
receita oficial ECL; 1o de 52 nas usinas +0,150 e 2o na FV das casas +0,166, estavel em 3 sementes, deterministico
na GPU) -> **entrou no benchmark em 10/10** (`04_redes_treinadas.py`, dicionario `MULTIVARIADAS`, laco
`redes_proprias.treina_multivariado`, so regime A): **56 modelos, 257 linhas**; e o 1o nas usinas em A, a frente
do TiRex-2. No caminho: o laco multivariado interpolava a serie inteira (buraco no fim da entrada preenchido com o
dia previsto; 19 serie-dias no consumo, nenhum nas usinas/FV); corrigido e tudo refeito. **S-Mamba nao passa** (10/10; 19o-27o).
**Mamba PASSA** na FV das casas (10/10; TSLib MambaSimple, bloco em PyTorch puro no lugar do `mamba_ssm`; +0,133,
10o/51, p 0,064; empata nas 3 sementes; 0,24 M param.; usinas 4o +0,121; lento: varredura sequencial, 2 h nas usinas)
-> **entrou no benchmark em 11/10** (dicionario `MULTIVARIADAS` do 04, deterministico na GPU): **57 modelos, 260 linhas**.
**TimeGrad nao passa** (11/10; pytorch-ts oficial no `~/.venvs/lagllama`; 12o-40o, a mediana subestima 19-28%).
**Regra do usuario (10/10): de dia a maquina fica livre (estudo, revisao, scripts, testes leves); rodadas pesadas de
GPU/CPU vao para a fila da noite** (`scripts/fila_noite.sh`, log em `resultados/log_fila_noite_*.txt`).
**Time-LLM nao passa** (11/10, consumo A: GPT-2 +0,043, 49o/53; sem o LLM +0,122, 41o: o LLM PIORA, p < 0,001,
como Tan et al. 2024). **LLMTime nao passa** (Qwen2.5-1.5B base: -0,056, 52o/53, vies -37%, 3 h 09 min de GPU).
Etapa A fechada nesta maquina; falta so o TimeGPT (espera a decisao do usuario: API paga, envia dados).
Teste de fumaca da GPU no `previsao_gpu`: NHITS treina e preve em 2,6 s.

**Revisao de eficiencia (09/10):** (1) `04_redes_treinadas.py` decidia o que pular olhando so o
`tempos_redes_<casos da linha de comando>.json`: `04 casas_cons` sozinho retreinaria ~30 redes. Agora le todos
os `tempos_redes_*.json`; os logs compartilhados (03/03b/03c/04) releem o arquivo antes de gravar
(`comum.grava_tempos`). (2) Redes proprias e o laco de treino num modulo so, `redes_proprias.py`, usado pelo 04 e
pelos pilotos (conferido em CPU: previsoes identicas as do codigo antigo); o piloto do VisionTS++ chama a funcao
do benchmark. (3) `atualiza.py`: um comando para 07 -> 05 -> 06 -> 05b -> planilhas -> regressao, cada um no seu
ambiente, ~50 s (eram seis comandos em tres ambientes). (4) Filas antigas em `scripts/historico/`. (5) Um ambiente
de GPU so (`previsao_gpu`; o `etapa_a` foi juntado). O pos-processamento nunca foi gargalo (~50 s); o custo real
e treino, memoria e retrabalho. Ainda duplicado de proposito: a mascara de horas avaliadas existe no 05_avalia e
na copia do teste de regressao (o teste e a checagem independente; sai quando a mascara for para a biblioteca).

**AutoARIMA (F1 d):** medicao de `usinas|B` com a configuracao reduzida iniciada 09/10 as 12:42 no
`classicos`; o Claude Code matou o processo por falta de memoria da maquina por volta das 13:10
(~28 min, sem nenhuma dobra gravada; usava ~17 GB). Refeito as 15:13 com a maquina vazia (22,7 GB livres, so o
VS Code aberto): morto de novo por falta de memoria antes das 15:43, sem nenhuma dobra gravada. Ja roda com
`n_jobs=1`, entao e o proprio ARIMAX (com as exogenas de clima, ~60 mil pontos por serie) que passa de
~20 GB em menos de 30 min. **Leitura para o portao (< 2 h/caso):** nesta maquina o AutoARIMA com exogenas
nao cabe nem na configuracao reduzida; nao soltar os seis. Proximo passo possivel, antes de declarar
inviavel: um piloto de memoria (uma serie, uma dobra, medindo o pico) ou rodar no Lactec.

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

Feito em 09/10 (F1 b e c), com o codigo na BIBLIOTECA primeiro:
- `prosumer.metrics.by_resolution` (+ `daily`, `by_blocks`, `hour_window`, `DEFAULT_LEVELS`; blocos configuraveis
  para a tarifa branca) e `prosumer.postprocessing.correct_bias` (bloqueada para geracao). 321 testes.
  (Nomes atuais; na epoca eram `prossumidor.metricas.por_resolucao` e `posprocessamento.corrige_vies`.)
- Benchmark: `05b_resolucao.py` -> `resultados/metricas_por_resolucao.csv`; `07_ensemble.py` grava
  `Ensemble-mediana-corrigida` so no consumo (mesmo algoritmo; teste confere biblioteca == benchmark).
  53 modelos, 248 linhas. A corrigida e a 1a no consumo A (+0,207) e B (+0,208), vies ~-0,5%.
- **O melhor modelo muda com a resolucao.** Consumo A: corrigida na hora, mas Timer-XL-84m no dia/noite (+0,143),
  no pico (+0,202) e no dia (+0,146). Consumo B: Ridge no dia/noite e no dia. Geracao solar: o R2 do DIA e MENOR
  que o da hora (FV casas 0,36 x 0,43; usinas A 0,48 x 0,74): por hora a forma do dia de sol e previsivel, o
  total do dia depende das nuvens. Aba "Por resolucao" da planilha do congresso; 5c da PROPOSTA.

Pendente NO LACTEC (so la roda o FlowState): piloto F2c de faixas com os quantis do FlowState,
`piloto_quantis.py gera usinas` (ambiente previsao) e depois `piloto_quantis.py avalia usinas` (ambiente da
biblioteca). Forma da saida ja corrigida: (janelas, 9 quantis, 24 h). Portao: cobertura de 80% e 60% dentro de
+-5 pontos e CRPS melhor que os quantis dos 14 dias anteriores.

| Etapa | Horas | Onde | O que, e o PORTAO |
|---|---|---|---|
| F0 Decisoes | 0 | — | Idioma DECIDIDO (internacional + camada BR, ver Ground rules). Pendentes: licenca (do autor, antes da E6); permissao por escrito do professor para os dados das usinas; comprar Raspberry Pi 5 + ESP32 |
| F1 Fechar o teste | 17 | ver linha | (a) ~~casa: congelar `classicos` e atualizar `previsao.txt`~~ **feito 09/10**. (b) avaliacao por resolucao (hora, noite-dia, pico 17-20h, dia) no `05_avalia.py` e aba na planilha do congresso, 3 h. (c) `Ensemble-mediana-corrigida` so no consumo (correcao de vies acima), 2 h. (d) AutoARIMA: medir 1 caso com a config reduzida; PORTAO < 2 h/caso -> rodar os 6 e refazer `usinas|A` reduzido; senao relatar como inviavel em resolucao horaria. (e) MLP: piloto de ajuste em casas_prod A (alpha maior, validacao temporal); PORTAO ganho >= 0,05 e estavel, senao rotular "sem ajuste". (f) TimesFM-3, FlowState (Lactec), BuildingsBench (so consumo): piloto em casas_cons A; PORTAO entrar no grupo da frente, senao parar |
| **A Modelos pendentes** | 40 | casa (GPU) e Lactec | Os 13 pendentes (Moirai 1, CycleNet, VisionTS, MOMENT, Lag-Llama, DUET, Crossformer, Mamba/S-Mamba, xLSTM, TimeGrad, Time-LLM, LLMTime, TimeGPT): para CADA um, estudar como funciona (artigo, matematica), o que pode acrescentar e como fazer rodar; depois piloto num caso. **Regra do usuario (09/10): nao descartar modelo sem estudo + evidencia.** PORTAO para o teste completo: empatar com o melhor num caso ou trazer algo que nenhum outro traz (clima sem treino, tamanho de embarcado, faixa, dependencia entre series). Tabela com o porque de cada um: secao 7 do plano |
| F2 Pilotos de melhoria | 22 | CPU | Cada um num caso; PORTAO skill +0,02 (ou faixa calibrada): (a) combinar 2-3 NWP no regime C (IFS + AIFS + GFS/ICON, Open-Meteo Previous Runs; conferir arquivo) com LightGBM nas usinas; (b) estimar inclinacao/azimute de cada telhado pelos dados (`legado/.../a1_geometry.py`) e usar POA no B das casas; (c) quantis: LightGBM quantilico + quantis do Chronos-2, medir CRPS e cobertura; (d) atualizacao ao meio-dia (pico 17-20h); (e) ajuste fino do TTM (Lactec, granite-tsfm completo); (f) modelo direto para o total do dia (consumo) |
| F2b Levar para a biblioteca | ~40 | qualquer | so os pilotos que passaram |
| E2 Versao 0.1 | 120 | qualquer | ~~Trocar nomes e API para ingles~~ **feito 09/10** (`prosumer`). Portar o protocolo (normaliza_por_treino, interpolacao CAUSAL so do historico, mascara de horas, corte de negativos, exogenas, passo regular), metricas em varias resolucoes, `ranking()` e `empata_com_melhor()`, `fisica`, `io` (Fronius, medidores, clima: NASA, estacao local, Open-Meteo com checagem de cobertura), `qualidade` (verificacao do relogio pelo sol, proveniencia/licenca), `previsao` com metadados (GPU, licenca, envio de dados), mediana como saida (+ correcao de vies no consumo), `data.dingle_houses()` |
| E3 Checagem 1 | 30 | qualquer | o benchmark refeito so com a biblioteca bate com as 243 linhas |
| E4 Versao 0.2 | 130 | qualquer | diagnostico; embarcado (TTM, SparseTSF, Ridge/RandomForest via emlearn, previsao do dia e por bloco de tarifa) |
| E5 Hardware | 50 | — | Raspberry Pi 5 e ESP32 |
| E6 Versao 0.3 | 110 | qualquer | economia: tarifas por horario genericas + modulo brasileiro (tarifa branca, bandeiras, Lei 14.300); documentacao em ingles + guia em portugues; licenca escolhida pelo autor; publicacao |
| **App: o TCC (ultimo passo)** | 120 | qualquer | So com a biblioteca pronta. Aplicativo facil de usar que recebe os dados do usuario (inversor, medidor, conta de luz) e faz a analise completa: qualidade (com relogio pelo sol), diagnostico, previsao comparada (mediana, regimes, resolucoes), economia, modelo para aparelho, e um relatorio. Duas formas, ambas ja feitas pelo autor: pagina web local em Streamlit como `1Projects/Keyword_map` (SciKeywordMap) ou programa de computador como `1Projects/Loom` (FastAPI + pywebview, sem servidor nem admin). Usa so a interface publica da biblioteca. PORTAO: um usuario sem programar faz a analise do comeco ao fim. Por isso a E2 ja desenha a API pensando nele: uma chamada que faz a analise completa e devolve um relatorio |
| E7 Escrita | 80 | — | em paralelo; o TCC descreve o APLICATIVO, a biblioteca por tras dele e as checagens |

**Pilotos F1/F2 feitos em 11/10/2026 (casa, CPU, minutos cada; detalhes em `docs/projeto/PILOTOS_F1_F2.md`):**
PASSAM: **F2(a)** varias previsoes do tempo no C das usinas (LightGBM com 6 NWP +0,373, 1o de 24, a frente da
mediana; IFS+GFS+ICON +0,365; AIFS +0,047 sobre o IFS com o mesmo treino curto; arquivo extra em
`dados/previsao_tempo_extra.parquet` via `08b_previsao_tempo_extra.py`); **F2(d)** previsao do pico 17-20 h do
consumo emitida ao meio-dia (+0,265 x +0,237 do melhor das 00:00, p 0,023); **F2(c)** faixas calibradas no regime A
em todos os casos (TimesFM-3 nos tres; Chronos-2 e LightGBM quantilico em dois cada); no C erram a calibracao por
< 1 ponto alem da tolerancia (calibracao conformal a pilotar). NAO PASSAM: F1(e) MLP ajustado (instavel entre
sementes: -0,22 / +0,13 / -0,07); F1(f) TimesFM-3 (+0,184 no consumo, 16o; ~igual ao 2.5); F2(b) geometria do
telhado (LightGBM piora -0,029; inclinacao no limite da grade); F2(f) total do dia direto (empata com o melhor
somado, +0,147 x +0,146). BuildingsBench (L +0,127 no consumo, 40o; faixas descalibradas; instalado com --no-deps no
`previsao_gpu`, pesos em `~/.cache/buildingsbench`). PENDENTES: F1(d) AutoARIMA no Lactec (**o ambiente `classicos` foi bloqueado aqui em
11/10**: Smart App Control no `statsmodels/_smoothers_lowess`); FlowState nas faixas (Lactec).

**E2/E3 comecou (11/10/2026): o protocolo do benchmark vem da biblioteca.** `comum.dobras`, `dias_teste`, `janelas`,
`normaliza_por_treino` e `05_avalia.real` viraram envelopes finos de `prosumer.protocol` (`folds`, `DayAhead` com
preenchimento causal, mascara de validade, covariaveis e `min_history`; `standardize_by_training`) e de
`prosumer.metrics.evaluated_mask`. `tests/test_benchmark_protocol.py` guarda a v2 CONGELADA e exige igualdade exata
nos 3 casos e regimes (15 testes); `atualiza.py` regera tudo identico. Os ambientes congelados nao tem a biblioteca
nem o pandera: o `comum.py` poe o `src/` no caminho e monta a serie sem validar (pandera e scipy sao importados so
onde sao usados). Fuso fixo da grade: usinas `Etc/GMT+3`, casas `Etc/GMT` (ver `comum.FUSO`). Mesmo hash das janelas
em .venv, previsao, previsao_gpu, lagllama, lote2 e lote2_hf. O ambiente `moirai` deixou de ler parquet
(Smart App Control no `_parquet` do pyarrow 25.0.1 cp311): **consertado** com pyarrow 24.0.0, `moirai.txt` recongelado. **`prosumer.physics` feito (11/10):** posicao do sol, ceu claro de Haurwitz, vetor medio do sol, Erbs, POA
isotropica e ajuste de orientacao, so numpy (o pvlib virou extra opcional: o h5py dele esta bloqueado aqui). O
`comum.ghi_ceu_claro` e o `piloto_geometria` usam a biblioteca; o ceu claro sai IDENTICO bit a bit (soma de Kahan
como o pandas; teste de paridade) e o C refeito pelo piloto multi-NWP bate com 0,0. O piloto da geometria tinha
um erro (amostras do sol 30 s cedo); refeito, a decisao nao muda. `metrics.ranking` e
`ties_with_best` feitos (o `05_avalia` usa; `dm_vs_melhor.csv` identico). Proximo passo de codigo: a chamada unica do aplicativo e os 3 pilotos que passaram (varias NWP, `issue_hour`, faixas). Revisao geral do plano:
`docs/projeto/REVISAO_GERAL_2026-10-11.md`. **Depois (11/10, noite):** `DayAhead(issue_hour=...)` (piloto F2(d):
emitida dentro do dia, alvo = horas de `issue_hour` a 23 h; 0 = benchmark, v2 congelada continua identica) e
`metrics.band_scores`/`quantile_loss` (F2(c): CRPS, cobertura e largura por par simetrico); o `piloto_quantis avalia`
usa a biblioteca e o `resumo.json` sai identico byte a byte nas 14 fontes. A CI (`qualidade`) falhou nos tres pushes de 11/10 (`ce3ac70`, `2937238`, `250c43c`)
por ruff (linhas > 110 e formato): consertado; rodar `ruff check src tests && ruff format --check src tests` antes de
cada commit (o mypy so roda na CI). `gh` instalado (winget, `C:\Program Files\GitHub CLI`, logado como JoaoCarlos134). **Chamada unica do
aplicativo feita (11/10):** `prosumer.analyze(series, site=None, test_days=28, issue_hour=0) -> Report` (qualidade,
checagem de previsao com as ingenuas e a MEDIANA delas como saida, por resolucao, notas e a lista `pending` do que
falta; `to_dict`/`to_markdown`). No consumo das casas reproduz as linhas `persist_24h`, `semanal_168h` e `media_7d`
do `metricas.csv` (teste com dados reais, tolerancia 1e-12). Cada modulo novo (io, forecast, diagnostico, economia)
entra como secao do `Report`. `DayAhead` aceita datas com fuso. **`prosumer.io.open_meteo` feito (11/10):** `fetch_previous_runs` (varias NWP,
`previous_dayN`, pedido em UTC e convertido, stdlib + `truststore` opcional, extra `net`), `coverage`, `wide` (por modelo
+ media e espalhamento). Reproduz a conversao do `comum.exog_previsao` hora a hora (teste sobre o arquivo salvo); ao
vivo o GHI bate exato com o download do benchmark e a temperatura difere 0,1-0,2 C (o arquivo da Open-Meteo foi
revisto: guardar o arquivo baixado de todo resultado publicado). `analyze(weather=...)`: secao de cobertura por modelo e,
na geracao, `weather_linear` (regime C, y = a + b x GHI medio previsto, horas de sol antes do teste), todas as linhas
nas mesmas horas; nas usinas (teste do benchmark, 6 NWP) +0,370 Cascavel e +0,247 Curitiba (benchmark, IFS so,
juntas: linear_fisico +0,312, LightGBM +0,330). **mypy roda aqui:** o `.venv` tem o mypy 2.4.0 puro
(`uv pip install --reinstall --no-binary mypy mypy==2.4.0`; o compilado e bloqueado); `.venv/Scripts/python.exe -m mypy`.
CI: `upload-artifact@v6` (Node 24). **Modulo `prosumer.forecast` feito (11/10, tarde):** `ModelCard` (licenca,
CPU/GPU, envia dados?, regimes), interface `fit(series, cutoff, covariates)`/`predict(windows)` e `rolling_forecast`
(origem movel: corta a serie no inicio de cada dobra). `Naive`, `LightGBM` (porte exato do 02_referencias: mesmas
features, codigos de serie, ordem das linhas e parametros) e adaptadores `Chronos2`, `TiRex2`, `Toto2`
(`forecast.foundation`, pacotes importados so no uso). **E3 forte:** o LightGBM da biblioteca REFAZ as previsoes
gravadas nas 9 combinacoes caso/regime com diferenca <= 3,5e-18 (`tests/test_forecast_parity.py`; 2 rapidas por
padrao, `PROSUMER_FULL=1` para as 9, ~3 min). Fundacionais: 3 janelas conferidas (TiRex-2 A/C, Toto-22m, Chronos-2 A
~1e-6; Chronos-2 C 1e-3); a conferencia completa (`scripts/confere_biblioteca.py`, saida
`resultados/conferencia_biblioteca.json`) esta na fila da noite de 11/10, AGENDADA no Agendador de Tarefas do
Windows (`prosumer_fila_noite`, 23:00, MODO_TESTE=1; apagar a tarefa depois). `analyze(models=[...])`: modelo de
historico vira linha A e entra na mediana; modelo com covariaveis vira linha C (precisa de `weather`); fundacionais
com 1024 h. Casas (consumo, 92 dias): LightGBM +0,199, mediana +0,145 -> +0,190. O extra `lightgbm` inclui o
scikit-learn (o LGBMRegressor exige). Licencas conferidas em 11/10 (cartoes do HF e repositorios): TiRex-2, Toto-2.0 e Chronos-2 sao Apache-2.0
nos pesos e no codigo, uso comercial permitido (o TiRex-2 traz NOTICE e um INTENDED_USE que exclui usos de alto risco do
AI Act, sem mudar a licenca). **Faixas (11/10, tarde):** `LightGBMQuantile` (um LightGBM por nivel; refaz o piloto F2(c) com dif 0,0 em
casas_prod A e usinas C), `EmpiricalQuantiles` (referencia: quantis do mesmo horario nos 14 dias; = a do piloto ate
1e-15), quantis no `Chronos2` (= piloto ate 2e-6; o ponto e o nivel 0,5) e no `TiRex2`; `rolling_quantiles` (um ajuste
serve ponto e faixa); secao `bands` no `analyze` (cobertura 80/60, largura, CRPS e skill contra a empirica nas mesmas
horas, `calibrated` = +-5 pontos, nota quando nao calibra). Casas, 92 dias: consumo calibrado (0,771/0,573, CRPS
+0,082), FV estreita (0,618/0,423) - como no piloto. A diferenca de 1e-3 do Chronos-2 no C e do ambiente antigo do
benchmark (o piloto, ambiente de hoje, bate a 2e-6). A fila das 23:00 (tarefa agendada, acorda o PC) confere tambem
os quantis do Chronos-2 e do LightGBM. **Calibracao conformal causal das faixas (11/10, noite): PASSA** (piloto
`piloto_conformal.py` sobre os quantis gravados, ~20 s; detalhes em `docs/projeto/PILOTOS_F1_F2.md`, F2(c')): um
deslocamento por nivel, quantil a de (y - q_a)/largura de 80% nos 28 dias anteriores, so nas horas de producao (sol nas
usinas, perfil de ANTES do teste na FV das casas; sem isso a noite enche a calibracao de zeros); 10 de 11 fontes
calibradas contra 7 de 11 brutas, inclusive as 4 que falhavam (LightGBM FV 0,651 -> 0,814; C 0,741 -> 0,810;
Chronos-2 C largo demais 0,837/0,654 -> 0,804/0,605); CQR por par fica em 9. Na biblioteca:
`postprocessing.conformal_quantiles` (= piloto, dif 0,0) e linha `<modelo>+conformal` na secao `bands` do `analyze`
(28 dias de previsoes antes do teste). Casas 92 dias: FV 0,618/0,423 -> 0,783/0,593, calibrada. **Noite de 11/10 (agentes em
worktrees, juntados em `main`):** `prosumer.quality.clock_offset`/`clock_notes` (relogio da geracao pelo sol: perfil medio
x ceu claro em 17 orientacoes, por serie e por mes, `confident` quando a maioria dos dias concorda; secao `clock` do
`analyze` com `site`); `prosumer.io.nasa_power` (POWER horario, pedido em UTC, -999 -> NaN, regime B) e
`data.dingle_houses()` (figshare CC0 com MD5 e cache em `$PROSUMER_DATA` ou `~/.cache/prosumer`, ou o parquet do
benchmark; H1 baixada bate com `casas_horario.parquet` com dif 0,0); Fronius/medidores NAO feitos (nao ha amostra do
formato bruto aqui). **ACHADO a declarar (benchmark):** o GHI da NASA de Curitiba (`ghi_horario` e, derivados,
`poa_estimada`/`temp_ar_horaria`, regime B e B-curto) esta **1 h atrasado**: o script de Curitiba reusou o deslocamento
de -55 min de Cascavel, mas Curitiba esta noutra faixa de hora solar local (LST = UTC-3, Cascavel UTC-4).
`clock_offset` da +1 h confiante em TODOS os meses de 2021-2026; Cascavel 0. A geracao de Curitiba sai ambigua (0 ou
+1 conforme o mes; geometria desconhecida). Confirmado por fora do sol: o GHI da NASA de Curitiba casa com a
previsao da Open-Meteo 1 h ANTES (corr 0,966 x 0,921 em L=0; Cascavel 0,968 em L=0), e a previsao da Open-Meteo da
0 h no `clock_offset` nas duas usinas. **Mas corrigir nao melhora o modelo** (`piloto_curitiba_hora.py`, LightGBM,
saidas em `resultados/pilotos/`): NASA adiantada 1 h no B, Curitiba +0,471 -> +0,440; so o ceu claro atrasado 1 h no
B, +0,471 -> +0,469; previsao + ceu claro atrasados 1 h no C, +0,326 -> +0,313. Leitura: o relogio da geracao de
Curitiba nao e um +1 h limpo (talvez rotulo deslocado de fracao de hora); os numeros publicados ficam, o atraso
do clima da NASA de Curitiba e DECLARADO no texto. **Decidido 12/10: nao refazer** (motivo abaixo).
**Relogio por nuvens (12/10):** `prosumer.quality.clock_offset_weather` (+ `clock_weather_notes`, secao
`clock_weather` do `analyze` quando ha `weather`): correlacao das anomalias horarias (serie menos o perfil do mes)
da geracao e do GHI, pico refinado por parabola entre passos, IC 90% por reamostragem de dias; mede fracao de hora e
ignora a orientacao do telhado (os pontos cegos do `clock_offset`). Nas usinas: a GERACAO de Curitiba tambem esta
atrasada e quase compensa a NASA: -0,16 h da NASA do B, +0,45 h da previsao do C (Cascavel -0,11 e -0,36). Toda
correcao de hora inteira afasta (por isso os dois pilotos pioraram); o conserto real seria reagregar Curitiba dos
5 min do Lactec com deslocamento fracionario e refazer as usinas nos tres regimes: NAO vale. Paragrafo declarado em
`experimentos/testes_previsao/LEIA-ME.md` secao 7.
**E2 FECHADA, versao 0.1.0 (12/10/2026, tag `v0.1.0`).** Entraram por ultimo: `io.fronius` (`read_solarweb`,
`read_solarweb_raw`, `canonical`/`ALIASES`; formato dos exportadores antigos do `legado`: xlsx por ano, linha 1
nomes `Energia | <aparelho>`, linha 2 unidades, 5 min em Wh, `n/a`, anos sobrepostos; regra 11/12 por hora;
`site=` zera a noite; extra `fronius` = openpyxl) e `io.meter.read_table` (CSV/Excel de medidor ou estacao:
`interval`, `cumulative` com reset detectado, `power`; `;` e virgula decimal). **Rotulo do Fronius NAO confirmado**
(`label="start"` como o benchmark; conferir com `clock_offset`/`clock_offset_weather` no primeiro arquivo real; so
os nomes em portugues vieram de arquivo real). `analyze`: linha `median_corrected` no consumo (14 dias antes do
teste) mas a SAIDA continua a mediana: piloto `piloto_vies_composicao.py` (PILOTOS_F1_F2.md) mostrou que a
correcao so ajuda a mediana de ~40 modelos (+0,194 -> +0,209) e piora as pequenas (ingenuas +0,145 -> +0,113;
+LightGBM +0,192 -> +0,175). README reescrito para a 0.1. Testes: 461 passam, 10 pulados. Proximo: E4 (diagnostico,
embarcado).
**Fila da noite de 11/10 (22:11-23:2x, tarefa agendada apagada depois): CONFERENCIA E3 COMPLETA.** LightGBM e LightGBM
quantilico 11/11 testes (9 combinacoes); TiRex-2 (7), Toto-2.0-313m (3), Toto-2.0-22m (3) e Chronos-2 (7): previsoes
iguais as gravadas ate <= 8e-6 e skill IDENTICO a 6 casas em todas (Chronos-2 C: 1e-3 de dif maxima, skill igual);
quantis do Chronos-2 = piloto com dif 0,0 nos 4. `resultados/conferencia_biblioteca.json`, 24 entradas, nenhum erro.
As rodadas v1 dos fundacionais em casas_prod A (Chronos-2, Chronos-Bolt-small, Moirai-2.0-small, TTM-r2, TiRex,
TimesFM-2.5 e o Ensemble) gravaram as 20 casas, inclusive as 10 sem FV: o 05_avalia so avalia as 10, nenhum numero
muda; a conferencia compara nas comuns e anota `series_extra_gravada`.
**Proveniencia (12/10, madrugada; agente em worktree, juntado):** `prosumer.provenance` (`Provenance`, `attach`, `of`),
campo opcional `EnergySeries.provenance`, preenchido por `data.dingle_houses` (CC0 + citacao), pelos sinteticos e pelos
leitores (`attrs["provenance"]` em `open_meteo`/`nasa_power`); secao "Data sources and licences" no `Report`, com notas
para licenca desconhecida, uso nao comercial e modelo que envia dados. Conferido: dados da Open-Meteo CC BY 4.0, mas a
**API gratuita e so para uso nao comercial** (< 10 mil chamadas/dia; https://open-meteo.com/en/terms) - pesa no
aplicativo se ele for comercial; NASA POWER sem licenca propria, CC0 pela regra geral da NASA, pede citacao e aviso de
publicacao. Testes: 355 passam, 10 pulados. Modo teste: `scripts/modo_teste.ps1` (`MODO_TESTE=1` na fila da noite).

Descartado SO com evidencia (testado): escolher "o melhor modelo" (piora/instavel) e correcao de vies na geracao
solar (piora ate -0,10); TimesNet so no A porque ignora o clima. Nada mais sai sem estudo + piloto (etapa A).
Ainda valem da revisao: `02b_classicos.prepara` interpola a serie inteira antes das dobras (nenhuma origem
afetada hoje; a biblioteca nao copia isso); LightGBM nao e bit a bit reprodutivel entre maquinas (<= 0,0006);
redes em duas versoes de torch (2.11 e 2.14.1).
**Revisao dos scripts do benchmark (11/10/2026, so leitura + checagens sobre as previsoes gravadas; nada mudou nos
numeros).** Conferido e OK: interpolacao causal no `comum.janelas`; exogenas sem NaN em todas as janelas de B/C;
series sem salto de tempo; `normaliza_por_treino`; correcao de vies causal (07); regra fixa do ensemble; formula do
DM (HLN, Newey-West) e Holm; todos os modelos avaliados nas MESMAS horas em cada caso/regime (excecao: as 3
referencias ingenuas das usinas A, 8.800-8.933 de 8.940 horas, por falta de defasagem). Achados a declarar:
(1) as redes do NeuralForecast (04, `df_nf`) recebem as horas faltantes como 0 (com `available_mask`), enquanto
todas as outras familias recebem interpolacao causal: 49 de 598 janelas de teste das usinas, 199 horas, todas de sol
(nas casas nenhuma). Medido sobre as previsoes: sem penalidade sistematica (o skill nesses dias sobe em uns
modelos e desce em outros); corrigir so se as redes do NF forem refeitas por outro motivo. (2) A parada antecipada
das redes proprias e multivariadas (`redes_proprias`) valida em 10% de janelas SORTEADAS que se sobrepoem as de
treino (a cada 6 h, 192 h de comprimento): validacao fraca, sem vazamento do teste; o NF usa os ultimos 30 dias. A
biblioteca deve usar validacao temporal. (3) A mascara de horas da FV das casas (05) sai do perfil medio do proprio
periodo de teste: igual para todos, nao e entrada de modelo. (4) O 03 pula modelo so pelo `tempos_fundacionais.json`
(o 04 confere tambem o parquet). (5) O portao dos pilotos e DM sem Holm (de proposito, mais permissivo); o
benchmark usa Holm. Testes: auditoria 4/4, biblioteca 313/313 (sem o de propriedade do hypothesis). Total do plano: ~759 h (~12 meses, ate out/2027), com o
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
