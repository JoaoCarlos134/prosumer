# CLAUDE.md — starting point for a new session

Snapshot written on 2026-10-05 from the work machine (Lactec), where the project lives in OneDrive
(`Documentos/2026/Projeto_IA`). This repo is the exported, anonymized subset needed for the TCC, the
future master's and the `prossumidor` library. The user (João) works in English with Claude; all project
docs and code comments are in Portuguese (code comments without accents) — keep that convention.

## Ground rules

- **Private repo, third-party data.** Plant series belong to two private owners; no consent to publish.
  Owner names were replaced by city ("Usina Cascavel", "Usina Curitiba"); Cascavel coordinates rounded to
  2 decimals (-24.83, -53.65). Never reintroduce names or exact coordinates. The name map exists only on the
  Lactec machine (`biblioteca_tcc/scripts/exporta_repo_prossumidor.py`, never copied here).
- **Authorization:** management cleared academic use (TCC) on 2026-10-05. Ownership/licence follow the
  project terms (proposal section 10). The MIT `LICENSE` was created with the repo; confirm the licence with
  Lactec before making anything public.
- **The 20 houses** (`casas`) come from a dataset of unknown origin/licence, apparently in Europe (northern
  hemisphere, DST). Don't publish them either.
- Re-syncing from Lactec is done there by rerunning the export script; files here may be overwritten by it.
  Commit work done here before a re-sync.

## Layout

- `docs/proposta/` — `Proposta_TCC_prossumidor.pdf` (10 pages, steps E0–E8, ~580 h, 9 months),
  `PROPOSTA_BIBLIOTECA.md` (8 modules, where each comes from), `gera_proposta_tcc.py` (needs reportlab).
- `docs/projeto/` — `ia_solar/ESTADO_DO_PROJETO.md` (plant analyses, pending items),
  `ia_solar/PLANO_ARTIGO.md` (papers A and B), `REDE_PROJETO.md` (project graph analysis), `RESUMO_*.txt`.
- `docs/literatura/` — `Visao_geral_modelos_previsao.xlsx` (127 models found, which were tested and why the
  rest weren't, no results), `Modelos_previsao_geracao_consumo.xlsx` (same survey with a results column),
  references, review draft `smart_buildings.docx`.
- `experimentos/testes_previsao/` — the forecasting benchmark (details below). `LEIA-ME.md` there is the
  v1 write-up; it has NOT yet been updated for v2.
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

### State at export (2026-10-05 10:30)

v2 was running on the work laptop (CPU only, ~2–3× slower per fold than v1 because two processes share it).
Finished in v2: all references, LightGBM and linear physics (A, B, C, B-curto, C-gfs); Chronos-2 and
TimesFM-2.5 in C; networks LSTM/GRU/NHITS/TiDE/KAN for `casas_prod`, LSTM for `usinas` A.
Not finished: all other trained networks (TCN, DLinear, iTransformer, PatchTST, SparseTSF, ResNet-1D, the
B and C networks incl. TFT/TSMixerx, and all of `casas_cons`), then batch 2. `04_redes_treinadas.py` skips
what is listed in `resultados/tempos_redes_*.json`, so a run here resumes where the snapshot ends.
**Decide with the user whether the Lactec laptop keeps running too** — don't merge two sets of results for
the same model without checking they agree.

Batch 2 (queued after v2): Toto-2.0-22m, Toto-2.0-313m, TiRex-2 (A/B/C), Sundial-128m, Timer-XL-84m,
Time-MoE-50M, Moirai-MoE-small, N-BEATSx (A/B/C; `04 ... --modelos NBEATSx`). Smoke-tested on 3 windows.
Dropped: TabPFN-TS (default weights need a Prior Labs account → pinned the open v2 weights, but >10 min for
9 windows on CPU; **feasible on a GPU** — consider it if the home machine has one), TimeXer (NeuralForecast's
version can't take future covariates). TiRex-2 needs `torch._dynamo` disabled on Windows without MSVC.

With a GPU: `COMUM` in `04_redes_treinadas.py` hard-codes `accelerator="cpu"` and `torch.set_num_threads`;
changing it changes run times (and possibly results slightly) — record it if you do.

### Findings so far

v1 (single cut): weather input matters ~10× more than the model (A→B gap ~0.40 vs ~0.03 between models);
a linear model on one physical variable gets +0.42; zero-shot foundation models tie with trained ones,
TTM most consistent; SparseTSF (32 params) ties on consumption; LSTM/GRU history-only lose to clear-sky
persistence on plants. Correction: the median ensemble is 1st on plants, 2nd on house PV but **5th** on
consumption (tie within 0.012) — not "never below 2nd" as some older docs say.

v2 early (LightGBM, all p < 0.001 unless noted): A +0.09 → **C +0.33** → B +0.48; the real forecast closes
~62% of the A→B gap. B with C's short training: +0.47 (n.s. vs B, p = 0.17), so the remaining gap is
forecast quality, not training length. ECMWF beats GFS (C-gfs +0.27). Rolling origin barely moved the A
average (+0.085 vs +0.088) but per-fold skill ranges −0.01 to +0.15. ECMWF day-ahead GHI correlates 0.93
with generation at Cascavel vs 0.96 for NASA.

## Next steps

1. Finish v2 + batch 2; run `07 → 05 → 06`; rewrite `experimentos/testes_previsao/LEIA-ME.md` for v2
   (regime C, folds, DM ties, batch 2) and update `docs/literatura/Visao_geral_modelos_previsao.xlsx`
   (regenerate with `docs/literatura/scripts/gera_visao_geral_modelos.py`).
2. TCC step E1 of the proposal: package skeleton (`src/prossumidor/`), data contracts, synthetic data, CI.
   Start from `scripts/comum.py` (protocol) and `05_avalia.py` (metrics) — they are the seed of
   `prossumidor.protocolo`.
3. Still open from the tests: fine-tuning TTM/Chronos-2, probabilistic forecasts (CRPS), consumption bias of
   foundation models (~−20%), house location for clear-sky, embedded latency/energy on Raspberry Pi 5 / ESP32
   (proposal step E5), loading the 32 TFLite models back (never done).
4. Known project gaps: Curitiba roof geometry unknown (blocks papers A and B); papers A and B have no
   bibliography yet.
