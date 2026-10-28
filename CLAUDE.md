# CLAUDE.md — starting point for a new session

The `prosumer` library (`src/prosumer/`: day-ahead forecasting, diagnostics and economics of PV generation and
household consumption) and the research around it: the TCC, the forecasting benchmark, the future master's.
GitHub `JoaoCarlos134/prosumer` (private; was `prossumidor` until 2026-10-09/11, the old URL redirects). The
user (João Carlos Jachenski Junior) works in English with Claude. The LIBRARY (`src/prosumer/`, `tests/`,
README, pyproject, `docs/library/`) is in English; project docs (`docs/projeto`, `docs/proposta`), benchmark
scripts and their comments stay in Portuguese (code comments without accents): keep that convention there.

This file holds the rules and the current state; `docs/REPO_MAP.md` is the map of the whole repository (every
part, its main functions, where each piece of data comes from and goes). The dated diary of 06/10-17/10/2026 (every run, pilot,
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
  along the way; `ambientes/LEIA-ME.md` has the install deviations each of the six envs needs.
- `webapp/` — the TCC's site (FastAPI over `prosumer.app.run` + React/ECharts page; standalone exe planned):
  `webapp/README.md` has its layout, how to run it and what is left.
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

Environments: six (`previsao`, `previsao_gpu`, `lote2`, `lote2_hf`, `moirai`, `classicos`), frozen in `ambientes/*.txt` (see `ambientes/LEIA-ME.md` for uv commands). Scripts
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
`provenance`, `data` (Dingle houses CC0, synthetic), `i18n` (every note/log line/person-facing error is a `Note`:
English text + template; `to_dict(lang="pt")`; the Portuguese catalog is `i18n/pt.py`, data only, and
`tests/test_i18n.py` fails when a `Note("...")` in the code has no translation: add it there). User guide in `docs/library/` (mkdocs; every example runs
in `tests/test_docs.py`), API reference generated from the docstrings. Example site: `examples/site_local/`.

Known open points (details in `docs/projeto/HISTORICO.md` and `PILOTOS_F1_F2.md`):
- Real Copel bills: without PV the energy is within +-5%; with compensation (GD I) the library bills ~21% less
  than paid (the tax on compensated energy above the minimum): needs detailed bills (none available now).
- The outlook's `trust`/`skill` are measured only in Parana; the PVDAQ pilot (17/10) checks the roof fit, the
  clock and the physical chain on US systems.
- Benchmark: AutoARIMA (F1 d) does not fit in memory on either machine with exogenous weather; TimeGPT waits
  for the author's decision (paid API, sends data: houses only, never the plants).
- The Curitiba NASA GHI of the benchmark is 1 h late (declared in LEIA-ME section 7; decided not to redo).

## Where to continue (2026-10-26, cloud)

Done in the cloud on 26/10 (branch `claude/optimistic-lamport-b8s8u1`, restarted from `main` after the merge):
the suns of the logo, the landing drawing and the loader turn about their centre (`webapp/web/src/components/
Spin.tsx`; the rays orbited a point off the sun; SMIL barely moved in Chrome there); the Inputs pane opens over
the whole screen with a slide (landing "add your files", the pane's maximise button), with a site map ("use my
location"), time-zone suggestions, a preview of each dropped file (`/api/peek` -> new `prosumer.app.peek`) and
the new request fields `weeks`, `issue_hour`, `price.credit` (library + tests + docs). What the library can do
that the pane still does not offer: `webapp/README.md` "2026-10-26 (cloud)". Next: rebuild the exe at Lactec
(`prosumer_site.cmd rebuild`) and look at the pane there.

### 2026-10-26, Lactec (kept for the record)

**The user is reworking the site's pages (26/10: "the site is not 100%")**: keep `webapp/README.md`
"Left" as the list; ask before redesigning pages. One launcher now: `webapp/prosumer_site.cmd` (builds
`dist/prosumer/prosumer.exe` the first time and runs it; later runs start it without building; `rebuild` after
changes; `dev` = API --reload with the library from `../src` + Vite on :5173); it replaced
`run.cmd`/`dev.cmd`/`build_exe.cmd`/`run.sh`, one env `webapp/.venv` (`.venv-build` gone). The mkdocs user
guide now builds into `build/docs` (was the confusing top-level `site/`).

Done on 26/10 at Lactec: pulled the cloud branch (fast-forward, pushed), library suite 698 passed / 23 skipped,
`webapp/tests` 12 passed (FastAPI etc. added to `~/.venvs/prosumer`); the Windows exe built and checked through
its API: demo with live Open-Meteo, a real Cascavel Fronius 5-min year (read as Fronius Solar.web) with live
ANEEL tariff and bandeira. Then the library fixes the site exposed (README "Left" 3-4): the consumption
outlook's daily range = range of past daily totals (was the sum of hourly extremes), `Report.skipped` (the pages
read it), `app.FOR_PEOPLE` rewords programmer notes on the app's pages, credits' notes translated. Still left: a
browser pass over the pages (after the user's changes).

### 2026-10-23, cloud -> Lactec (kept for the record)

The cloud's `work-reviewer` pass over `941dae7..f6fc344` (ready with fixes, 1 MAJOR) is fixed in `8676a80`; its
open minors are in `webapp/README.md` "Left" 3.

Done in the cloud on 23/10 (branch `claude/optimistic-lamport-b8s8u1`): the five missing pages, `npm run build`
clean, `webapp/tests/test_api.py` (10 tests, `python -m pytest tests` from `webapp/`), `run.cmd`/`dev.cmd`/
`run.sh`/`requirements.txt`, `server/launch.py` + `prosumer_site.spec` + `build_exe.cmd` (built on Linux: 465 MB,
answers, port fallback), a Playwright check of every page (en/pt, light/dark, 1440 px and a 390 px phone, focus,
table, CSV, cross-filter by day and by month). The user asked mid-way (23/10) for livelier tiles ("3D rounded")
and no overlaps: rounded tiles with layered shadows and a hover lift, KPI cards that tilt toward the pointer,
a pill tab bar; legends one scrolling row clear of the axis names; range whiskers cut at the axis top.
- Library fix found by the site's tests: pandas 3.1 deprecates `dayofweek`/`dayofyear` (12 uses; an error
  under the suite's `filterwarnings`, so CI on the newest pandas would go red): now `day_of_week`/`day_of_year`,
  regression test `tests/test_pandas_compat.py` (a source scan, red before).
- Library issue left open (README "Left" 3): the consumption outlook's daily `low`/`high` is the SUM of the
  hourly 4-week min/max (`outlook._daily`), up to ~13x the day on Dingle H1; a range of daily totals is honest.
- Library change from that review: `Diagnosis.orientation.reliable`, `segments.trend_reported`/`loss_reported`
  (what the notes report, as columns), `analyze(orientation=)`, `app.run` passes a typed roof to the diagnostics.
- In the cloud env (numpy 2.5.4, pandas 3.1.0) `test_benchmark_protocol::test_clear_sky_is_bit_identical` fails
  by 1 ulp on the old code too (environment, not this work): CI on the newest numpy would show it.
- Cloud sandbox note: its proxy drops some TLS connections to Open-Meteo (the library turns it into a message);
  the browser checks used the test suite's fake weather.

### 2026-10-23 morning, Lactec (kept for the record)

**On "continue": build the site in `webapp/` following `webapp/README.md` "State ... and what is left", steps
1-7 in order** (the five missing pages, `npm run build` and its type errors, `webapp/tests/test_api.py`,
`run.cmd`/`dev.cmd`/`requirements.txt`, the standalone exe, a browser check, the review). What the user
asked on 23/10: the "full v1" of the site, looking like a Power BI report (KPI cards, white tiles on a grey
canvas, page tabs at the bottom, a filter-like Inputs pane, focus mode / show as table / export on each
visual, cross-filter by day) WITH animations, visual objects from open-source tools (no paid service needed:
ECharts, Framer Motion, Leaflet + OpenStreetMap, lucide; the user offered to create an account / API key if
one is ever needed); then the whole site must run from an exe in a standalone folder that carries the
library and every dependency (PyInstaller one-folder; the Windows build and its test happen on the Lactec
machine, see README step 5).

- The site lives in `webapp/` of THIS repo (moved on 23/10 from a sibling folder `1Projects/prosumer_site` so
  the cloud can continue; it can become its own private repo later). (The mkdocs build, once the ignored
  top-level `site/`, goes to `build/docs` since 26/10.) Pre-commit runs ruff on `webapp/server/*.py` too (FastAPI's `File()` defaults carry `# noqa: B008`).
- The server is a thin shell over `prosumer.app.run`; nothing of the analysis is re-implemented in the site.
  The page labels the library's codes itself (`web/src/i18n.ts`, `code()`); its notes arrive translated.
- Done on 23/10 besides: pulled the cloud branch (already merged into `main`); suite 694 passed / 23 skipped
  (expected skips), ruff/mypy/`mkdocs build --strict` clean, CI green; `origin` set to the new URL; fix
  `acc0abd` (`app.run` reads a wall-clock file with every hour of the DST changes, with a log note; found on
  the Dingle files; `contracts.DaylightSavingError`). Not done: deleting the merged remote branches
  `claude/cool-pascal-hxh4ol` and `correcoes-v2-gpu` (the auto-mode classifier refused; the user can run
  `git push origin --delete claude/cool-pascal-hxh4ol correcoes-v2-gpu`).
- Library review on 23/10 (quick, by hand): nothing left but the site; open items are optional (speed
  leftovers below) or blocked (outlook trust/skill outside Parana, detailed bills, licence, the teacher's
  written permission).

### 2026-10-21 (kept for the record)

Done on 21/10: **translations EN/PT** (`prosumer.i18n`, ~230 templates; `Report/Outlook/Diagnosis/Bill/
app.Result.to_dict(lang="pt")`, `i18n.message(error, "pt")`; codes, names and licences stay untranslated by
design). pandas 3 turns a text column into its string type and drops the `Note`: tables that carry notes are
built with `i18n.frame`. Also: `app.run` turns failed weather/address/time-zone downloads into messages; fixed
the bare `KeyError` of an unknown Brazilian `connection` (regression tests in `test_app`, `test_economics_brazil`).
The user does not want the project doubled by the translations: keep Portuguese in the catalog only, never
per-language code paths.

Speed (21/10, stopped by the user mid-way, committed after this note): `app.run` on Cascavel's 7 years
~10 s -> ~6 s naive, JSON byte-identical to `24045e5` (checked with a scratch script that runs both trees).
Done: `physics._PoaParts` (fit_orientation computes the plane-independent part once), `diagnostics._roof`
remembered by a fingerprint of its inputs (`_fit_roof` does the work; LRU of 4, lock, returns copies),
`physics.clear_sky_ghi`/`mean_sun` remembered on spans >= 1000 times (`MEMORY` = 6), `_complete_days` without a
lambda per day. Tests of the memories: written in the cloud on 21/10 (below). Second pass in the cloud (21/10,
`library-builder`): `_segment` vectorised (0.5 -> 0.07 s per call) and `clock_offset` centred once (1.2 -> 0.5 s);
`app.run` ~6.0 -> ~4.1 s naive, ~8.3 -> ~6.6 s LightGBM (cloud, 4 CPUs), JSON byte-identical en/pt. Left: reading
the file (~1.5 s cold: dates parsed 4 times; not clearly safe to merge), `_changepoints` runs twice on the same
input, the cold sun inside `clock_offset` (~0.6 s).

**Review of `9119619..24045e5` (work-reviewer, 21/10; verdict: ready with fixes): all 9 findings fixed in the
cloud on 21/10** (branch `claude/cool-pascal-hxh4ol`, `cb3e96c` and the commit after it; each crash fix with
its regression test, checked red on the old code). What changed: `app.run` checks `kind`, `timezone`,
`price.scheme`, ICMS/PIS each in [0, 1) and their sum < 1, `peak_start` (HH:MM, also in
`brazil.branca_blocks`), `gd` (required with PV) with Notes before any download; `read_energy(time_column=)`
not in the file is a message; ANEEL's missing components file is a Note; `analyze` skips the forecast check
(note) when every evaluated test hour is zero (dead inverter); typed-price/typed-rate/"not declared" sources
are Notes; `i18n` renders a `timedelta` as "5 min"/"1 day" (English changed too, was "0 days 00:05:00") and a
monthly `pd.Period` as 2026-02 / 02/2026, joins lists that hold Notes or months; `median_weather` note says
the benchmark's linear model used POA irradiance; `docs/library/app.md` claims corrected; `_ROLE.get`;
`i18n.frame` takes a generator. Left as is: role "weather" also labels measured weather (consistent with the
row name). Tests of the memories written (`test_physics` long-span memory, `test_diagnostics` roof fitted once
across `forecast_ahead` + `diagnose`, a changed value misses, copies, LRU of `ROOF_MEMORY`).
Timings reproduced by the reviewer before the speed commit: 8.0 s naive / 10.5 s default on 60,000 h.

Also done in the cloud on 21/10 (same branch): the example site is a thin shell over `app.run`; `app.run` takes
blank price fields as "not given" and ignores `gd` without PV; CI installs `lightgbm` and runs `-n auto`;
`tests/series.py` (shared helper), `test_economics_app.py` -> `test_economics_pricing.py`; `docs/REPO_MAP.md`
(the map of the repository, with two Mermaid diagrams). Speed of `_segment`/`clock_offset`: given to the
`library-builder` agent. Growatt trust/skill pilot (item 3): blocked here (the full file needs a Kaggle login).

Review of `24045e5..HEAD` (work-reviewer, 21/10): **ready with fixes, nothing MAJOR**; speed commits checked
byte-identical (en/pt) on 7 years with steps, vectorised `_segment` = old loop on 3000 cases, the 9 earlier
findings fixed with red-before tests, REPO_MAP names verified, full suite 691 passed. Its findings 1-8 fixed the
same day (example bill message and % tax messages, ported peak-hour and GD II tests to `test_app`, `mean_sun`
cache index, quiet bootstrap NaN, CI paths for `examples/` and `docs/library/`, app.md timing, REPO_MAP import
notes). Left: nit 9 (example shows ANEEL codes, "Price: flat"); a nearly dead test period (one non-zero hour)
still scores meaningless numbers without a note (a threshold would be a constant chosen on nothing).

The user's decision (21/10), done: the branch `claude/cool-pascal-hxh4ol` was reviewed, fixed and merged into
`main` (fast-forward, `9be5078`).

### The list of 2026-10-19 (item 2 done on 21/10)

Done on 19/10 (all pushed): review fixes F2/F4/F8/F9 and `analyze(bias_days=, calibration_days=)` (`3898067`);
`app.run` runs LightGBM in the forecast check by default (`models`: lightgbm/naive/all), `Result.charts`
(daily history, test hours = `Report.hourly`, clear-day performance), fix of the past folds of `analyze`
(`7895d7f`). Licence: decided to stay PRIVATE for now (all rights reserved; site installs from the private
repo); recommended path when publishing is in the Lactec machine's memory only: AGPL-3.0 + dual licensing,
product layer closed, exception for `embedded` output; check Lactec ownership (Lei 9.609 art. 4), university
IP rules, patents, AI-written code first.

The user asked to do groups 1 and 2 of "is the library done" (library first, then the site):
1. **Review** `9119619..7895d7f` with the `work-reviewer` (no agents were allowed on 19/10).
2. **Translations EN/PT (decided: both, switchable)**: ~90 notes (`analysis` 27, `outlook` 15, `brazil` 13,
   `diagnostics` 9, `economics.core` 7, `quality` 5, readers), the app's log/errors/`pending`. Design chosen
   but not started: `Note(str)` subclass whose text is English (nothing breaks) carrying `key` + params; one
   catalog key -> (en, pt); PT numbers with a decimal comma; nested Notes for fragments; `Result.to_dict(lang=)`
   translates; a test that the app's JSON in pt has no untranslated note on the tested paths.
3. **Group 2 without the roof pilots** (the user said skip them for now): the outlook's trust/skill outside
   Parana could be checked on the Growatt India file (2026-03..09, overlaps the Open-Meteo previous-runs
   archive; a light pilot, gate first); bills (GD I 21%, branca with PV) need real detailed bills: blocked.
4. **Speed**: `app.run` on 7 years of hourly PV ~9 s naive / ~12 s LightGBM; the roof is fitted TWICE (outlook
   and diagnose, ~2 s each; `physics.solar_position` recomputed per grid point): fit once / cache the sun.
5. **Tests (asked 19/10)**: 30 files in `tests/` (one per module, flat, no conftest; helpers `aneel_fake.py`,
   `wasm_c.py`, `fixtures/`), 683 pass (21/10) in ~110 s with `-n 6` (12 logical CPUs; `-n 8` is slower,
   `--dist worksteal` no gain: keep `-n 6`). ~480 s of test time: `test_diagnostics` 113 s, `test_analysis` 68,
   `test_forecast_parity` 63 (two benchmark combinations by default, one 45 s), `test_outlook` 50,
   `test_benchmark_protocol` 45. Redundancy found: `examples/site_local/app.py` re-implements `prosumer.app`
   (own `_pricing`, `_peak_hours`, the 7 steps) and `test_example_site.py` re-tests it: make the example a thin
   shell over `app.run` (or retire it when the TS site exists); `_series` helper copied in 6 test files;
   `test_economics_app.py` tests `analyze(economics=)`, not the app (misnamed). CI installs only `dev,plots`
   (no LightGBM: its tests and the app's default path skip there) and runs pytest serially: add `lightgbm`
   and `-n auto`.
6. PVDAQ + measured-roof pilots (gates `7bee35e`, `0b985d2`): only with memory to spare and the user's OK.
7. Then the TypeScript site: STARTED 23/10 in `webapp/` (React + Vite + TS + Tailwind, FastAPI serving the
   build, `run.cmd`, like `1Projects/Keyword_map`); see "Where to continue" and `webapp/README.md`.
