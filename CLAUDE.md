# CLAUDE.md — starting point for a new session

The `prosumer` library (`src/prosumer/`: day-ahead forecasting, diagnostics and economics of PV generation and
household consumption) and the research around it: the TCC, the forecasting benchmark, the future master's.
GitHub `JoaoCarlos134/prosumer` (private; was `prossumidor` until 2026-10-09/11, the old URL redirects). The
user (João Carlos Jachenski Junior) works in English with Claude. The LIBRARY (`src/prosumer/`, `tests/`,
README, pyproject, `docs/library/`) is in English; project docs (`docs/projeto`, `docs/proposta`), benchmark
scripts and their comments stay in Portuguese (code comments without accents): keep that convention there.

This file holds the rules and the current state. The dated diary of 06/10-17/10/2026 (every run, pilot,
environment fix and decision, with numbers) moved verbatim to `docs/projeto/HISTORICO.md` on 2026-10-17:
look there for the history of anything below.

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
- **Every bug fix ships with a regression test (decided 2026-10-15).** In the library (`src/prosumer`,
  `examples`), a fix includes a test that reproduces the bug (fails before the fix, passes after), in the
  same commit. Test the bug actually hit plus its obvious neighbour; no retroactive tests for old bugs
  unless that code is touched again. Pilots and one-off benchmark scripts are exempt (their record is the
  saved output and the write-up).
- **Nada sob medida para os nossos dados (decidido 16/10/2026).** A biblioteca e o aplicativo tem de ler e fazer
  tudo para QUALQUER sistema: outras marcas de inversor (nao so Fronius Solar.web), outros paineis e telhados,
  medidores, resolucoes, hemisferios e climas. Fronius, as duas usinas do Parana e as casas de Dingle sao so as
  amostras que temos. Codigo de marca = adaptador fino que devolve o `EnergySeries` generico; o nucleo nunca supoe
  marca. Constante medida nos nossos sitios (`outlook.TRUST`/`SKILL`, `diagnostics.PENALTY`, limiares de dia claro,
  do relogio) fica DECLARADA como "medida em X" e vira parametro, nao padrao escondido; validar, quando der, num
  sitio/fonte que nao serviu para escolhe-la. Leitor novo ganha teste com amostra do formato REAL (o leitor do
  Fronius, escrito de suposicoes, recusava todo arquivo real: unidades `[Wh]`).
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

Benchmark results and findings (v2, 57 models, 260 rows of `resultados/metricas.csv`): `experimentos/testes_previsao/LEIA-ME.md`;
the state of 06/10 and its findings are in `docs/projeto/HISTORICO.md`. Pilots: `docs/projeto/PILOTOS_F1_F2.md`
(gate committed before every run; outputs in `resultados/pilotos/`, never in `previsoes/`).

## Machines

Two machines, one repository. Always work on `main`.

| | Lactec (work) | Home |
|---|---|---|
| Clone | `OneDrive - Lactec/Documentos/1Projects/prosumer` | `Downloads/projects/prosumer` |
| GPU | none (CPU torch) | RTX 4070 |
| Library env | `~/.venvs/prosumer` (extras dev, plots, lightgbm, fronius, net, docs); `~/.venvs/prosumer_tsfm` for FlowState (granite-tsfm needs scikit-learn < 1.8; `PYTHONPATH=src`); `~/.venvs/classicos` | repo `.venv` on the signed Python 3.12.10; `~/.venvs/previsao_gpu` (torch 2.9.1+cu128) for GPU runs |
| Benchmark envs | `~/.venvs/{previsao,lote2,lote2_hf,moirai}` = `ambientes/*.txt` | the same, see `ambientes/LEIA-ME.md` |
| Runs here | the library, evaluation, references, LightGBM, zero-shot foundation models, TTM/FlowState | trained networks, TabPFN-TS (GPU) |
| Raw data | 5-min Fronius exports and the bill summary in `Projeto_IA/ia_solar/dados_brutos` (private, never copied) | none |
| RAM | 15.7 GB | more than Lactec's (memory, not the GPU, is the bottleneck there) |

Home machine, Smart App Control (never turn it off: irreversible; WSL2 is the way out if needed): it blocks
torch 2.14 (use `previsao_gpu`), pyarrow 26 (the `.venv` has 25.0.1; `moirai` has 24.0.0), the compiled mypy
(the `.venv` has a pure mypy 2.4.0), `hypothesis._native` and the `statsmodels` of `classicos`. Tests at home:
`.venv/Scripts/python.exe -m pytest -p no:hypothesispytest --ignore=tests/test_contracts.py`. At Lactec everything
runs: `~/.venvs/prosumer/Scripts/python.exe -m pytest -n 6`.

The Lactec exporter (`Projeto_IA/biblioteca_tcc/scripts/exporta_repo_prossumidor.py`) copies OLD files over
new ones: never run it without comparing; the repository is the main copy. The Lactec clone's `origin` may
still point at the old URL (it redirects; `git remote set-url origin https://github.com/JoaoCarlos134/prosumer.git`).

## How to work here (the user's standing rules)

- **Library first.** The end product is the library and, on top of it, the app (the TCC). Papers are
  by-products. Generation (PV) forecasting is the main thing; consumption matters more to utilities. Never
  trade speed for a small skill gain: heavy foundation models stay opt-in (2026-10-16).
- **Pilot before any long run or method change**: a gate written and committed BEFORE the run, outputs in
  `resultados/pilotos/`, an honest record in `PILOTOS_F1_F2.md` (also when it fails). No model is dropped
  without study + evidence. Heavy runs at night; the day is for study, review, scripts and light tests.
- **Every bug fix ships with a regression test** (red before, green after, same commit), in `src/prosumer`
  and `examples`. Readers get a test with a sample of the REAL format.
- **Nothing tuned to our own data**: any brand, panel, roof, meter, step, hemisphere or climate must work.
  Brand code is a thin adapter returning an `EnergySeries`. A constant chosen on our sites is an argument with
  its origin declared (`docs/library/tuning.md`), validated where possible on a site that did not choose it.
- **Review after each step**: the `work-reviewer` agent (`.claude/agents/`), read-only, over the commit range.
  Builders: `library-builder`, `pilot-runner`. Keep subagents few (they count against the user's plan).
- **Before each commit**: `ruff check src tests`, `ruff format --check src tests`, mypy (all in the library
  env); the pre-commit hook runs them. On Windows, Python writes CRLF: the `mixed-line-ending` hook fixes it and
  fails the commit once, just add again. Commit messages end with the Co-Authored-By line.
- **Licence**: the author's decision, not taken yet (no LICENSE file); publication (PyPI, public repo) waits
  for it. Plant data stay private until the teacher's written permission.
- At 90% of the plan's token use: stop, update "Where to continue" below, commit and push.

## The library today (2026-10-17)

`prosumer` 0.1.0 tagged on 2026-10-12; everything since is in `docs/library/changelog.md`. Modules:
`analysis` (`analyze`, the report), `app` (`run`: the app's backend in one call, strict JSON out), `contracts`,
`protocol`, `metrics`, `forecast` (Naive, LightGBM(+Quantile), EmpiricalQuantiles, Chronos2, TiRex2, Toto2,
FlowState, each with a card), `postprocessing`, `physics`, `quality` (clock vs sun and clouds), `diagnostics`,
`outlook` (`forecast_ahead`, `best_windows`), `economics` (+ `brazil`: Lei 14.300, tarifa branca with PV),
`embedded` (C headers), `io` (auto, meter, fronius, pvdaq, open_meteo, nasa_power, geocode, aneel),
`provenance`, `data` (Dingle houses CC0, synthetic). User guide in `docs/library/` (mkdocs; every example runs
in `tests/test_docs.py`), API reference generated from the docstrings. Example site: `examples/site_local/`.

Known open points (details in `docs/projeto/HISTORICO.md` and `PILOTOS_F1_F2.md`):
- Real Copel bills: without PV the energy is within +-5%; with compensation (GD I) the library bills ~21% less
  than paid (the tax on compensated energy above the minimum): needs detailed bills (none available now).
- The outlook's `trust`/`skill` are measured only in Parana; the PVDAQ pilot (17/10) checks the roof fit, the
  clock and the physical chain on US systems.
- Benchmark: AutoARIMA (F1 d) does not fit in memory on either machine with exogenous weather; TimeGPT waits
  for the author's decision (paid API, sends data: houses only, never the plants).
- The Curitiba NASA GHI of the benchmark is 1 h late (declared in LEIA-ME section 7; decided not to redo).

## Where to continue (2026-10-19, Lactec)

Done on 17/10 (all pushed): counters read as counters (real Growatt file), `io.pvdaq`, tarifa branca with PV, the
app backend `prosumer.app.run` (strict JSON), the user guide `docs/library/` (mkdocs, examples tested), the
parity tolerance between machines, frames saved to parquet, this file split. The independent review of
`9d3ade0..f079512` came back "ready with fixes"; F1, F3 (gate of the follow-up pilot), F5, F6, F7 are fixed.

1. **Still open from that review** (each fix with a test):
   - F2: tarifa branca, a credit is spent in `posto_order` before its own posto (`brazil._branca_scee` step 3);
     decide the reading (own posto first, as step 1 and the docstring say) and test it.
   - F4: the `median_weather` note in `analyze` claims "1st of 24" for any composition; the pilot's 4 rows
     were 1st, LightGBM + the linear model alone 9th (+0.346). State what was measured.
   - F8: save the Growatt whole-file check (daily median 14.2 kWh, counter = integrated AC power, median 0.999)
     as a script and output; the counter thresholds are declared in `io.auto` and `docs/library/tuning.md`.
   - F9: `analysis.py` EconomicsSection docstring (by_block per posto for branca),
     `examples/site_local/README.md` ("tarifa branca with PV is not modelled"), changelog note that branca
     without PV now has per-posto by_block.
   - `BIAS_DAYS` and `CALIBRATION_DAYS` of `analyze` as arguments (tuning page lists them as constants).
2. **PVDAQ pilot** (`piloto_pvdaq.py`, gate `7bee35e`): the run of 17/10 was stopped by Claude Code for low
   memory after 2 of 6 systems (~1 h, ~7-15 min per system); rerun it only when the machine has memory to spare
   (close the browser; ask the user). Its G1 (+-10 degrees) and G2 are weak (review F3): report them as such.
   Already seen: the roof fit is far too steep outside Parana (clear-sky model without altitude/haze, no
   temperature; see `docs/library/validation.md`). Then **`piloto_telhado_medido.py`** (gate `0b985d2`, revised
   before running): fit the roof against NASA irradiance, H2 (the outlook chain) decides.
3. MPPT channel shares: did not pass (1 of 3 events); next idea in `PILOTOS_F1_F2.md` (DC voltages per MPPT).
4. Then the TypeScript site (own repository, after the library is published; runs locally like
   `1Projects/Keyword_map`, much more compact): its backend is a thin shell over `prosumer.app.run`.
   Publishing waits for the licence (the author's decision).
