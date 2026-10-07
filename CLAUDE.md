# CLAUDE.md — starting point for a new session

Snapshot written on 2026-10-05 from the work machine (Lactec), where the project lives in OneDrive
(`Documentos/2026/Projeto_IA`); state, findings and next steps updated on 2026-10-06 after the v2 +
batch 2 run finished on the home GPU. This repo is the exported, anonymized subset needed for the TCC, the
future master's and the `prossumidor` library. The user (João) works in English with Claude; all project
docs and code comments are in Portuguese (code comments without accents) — keep that convention.

## Ground rules

- **Private repo, third-party data.** Plant series belong to two private owners; no consent to publish.
  Owner names were replaced by city ("Usina Cascavel", "Usina Curitiba"); Cascavel coordinates rounded to
  2 decimals (-24.83, -53.65). Never reintroduce names or exact coordinates. The name map exists only on the
  Lactec machine (`biblioteca_tcc/scripts/exporta_repo_prossumidor.py`, never copied here).
- **Authorization:** management cleared academic use (TCC) on 2026-10-05. Ownership/licence follow the
  project terms (proposal section 10). There is deliberately **no LICENSE file** (the MIT one created with
  the repo was removed on 2026-10-05): all rights reserved until Lactec decides. Don't add one.
- **The 20 houses** (`casas`) come from a dataset of unknown origin/licence, apparently in Europe (northern
  hemisphere, DST). Don't publish them either.
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

**v2 (origem movel, 36 modelos, numeros finais de 06/10/2026):**

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

## Next steps

1. TCC passo **E2** (versao 0.1). O E1 (esqueleto, contratos, dados sinteticos, CI) esta feito: 47
   testes, 95% de cobertura, e `prossumidor.metricas` reproduz exatamente skill/nRMSE/MBE do
   `metricas.csv` a partir das previsoes gravadas (o IC difere ~0,005 porque o `05_avalia.py` usa um
   unico gerador para todos os modelos, entao o IC de cada um depende da ordem dos arquivos). Falta
   portar de `comum.py`/`05_avalia.py` para `protocolo`: `normaliza_por_treino`, interpolacao do
   historico nas janelas, mascara de horas avaliadas e corte de previsoes negativas, exogenas na
   `Janela`; depois `fisica` (Haurwitz igual ao benchmark), `previsao` (referencias, linear fisico,
   LightGBM, Chronos-2, TTM), e um teste de regressao local contra `metricas.csv` (pulado sem dados).
2. Ainda aberto nos testes: ajuste fino do TTM/Chronos-2 (o `granite-tsfm` esta incompleto na maquina
   de casa, mas **funciona no Lactec** — fazer la, em CPU), previsao probabilistica (CRPS), vies de
   consumo dos fundacionais (~-20%), localizacao das casas para o ceu claro, latencia/energia no
   Raspberry Pi 5 / ESP32 (passo E5 da proposta).
3. TFLite (feito em 05/10/2026 no Lactec, `legado/ia_solar/base_modelagem/referencia/verifica_tflite.py`):
   os 32 `.tflite` em `legado/ia_solar/base_modelagem/embarcado/` foram recarregados do disco e todos
   reproduzem o R2 original (`verificacao_tflite.csv`). O `.tflite` guarda so a rede: imputacao,
   escala e desnormalizacao foram reconstruidas e salvas em
   `embarcado/preprocessamento_<usina>_<conjunto>.json` — um dispositivo precisa do arquivo + JSON.
   A latencia x86 (~2,5 us float, ~11 us int8) e overhead de chamada Python, nao custo de rede.
4. Lacunas conhecidas do projeto: geometria do telhado de Curitiba desconhecida (travam os artigos A e
   B); artigos A e B sem bibliografia.
