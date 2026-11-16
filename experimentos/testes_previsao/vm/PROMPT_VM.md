# Prompt for Claude Code on the Lactec VM: set up and leave every heavy run queued

Written 2026-11-16 at Lactec. The plan behind it, with the reasons: `docs/projeto/REVISAO_TESTES_2026-11-16.md`
(read sections 3-5 and 8 first). The project's rules: `CLAUDE.md` (read it all; the pilot discipline and the
plant-data rules are not optional). This file never names the server, its users or its paths outside the
project's own folder: keep it that way, the repository is public.

## The machine

A shared Slurm node (Ubuntu 24.04): 48 threads, 2 x ~96 GB GPU (Blackwell; driver CUDA 13.2), 251 GB RAM, but
another user's job holds most of the RAM: plan on **~20 GB per job** (`--mem=20G`) and **at most one GPU**
(`--gres=gpu:1`). Partitions (same node): `gpu_dev` (default, 12 h max), `gpu_train` (2 days), `gpu_sim`
(7 days), `gpu_unlimited`. Others use the machine: never more than ~24 CPU threads and one GPU at a time across
all your jobs, and never `scancel` anything that is not yours.

## Goal of this session

Set everything up, write and COMMIT every gate, then submit the runs as Slurm jobs that chain by themselves
(`--dependency=afterok`/`afterany`) so they keep running after this session ends. Each job is idempotent
(the benchmark scripts already skip what `resultados/tempos_*.json` has; new scripts must do the same), logs to
`~/Projeto_IA/logs/<job>-%j.out`, and appends one line to `~/Projeto_IA/STATUS.md` when it starts, ends or fails.
Before leaving, the session writes in `STATUS.md` what was submitted, the job ids, the expected order and how
to check them (`squeue -u $USER`, `sacct` is disabled here).

## 0. Folders and data (owners allowed all data on this machine)

    ~/Projeto_IA/                      chmod 700 (others use this machine)
      prosumer/                        WORKING clone of the PUBLIC repo (github.com/JoaoCarlos134/prosumer)
      prosumer-private/                READ-ONLY clone of the PRIVATE repo prosumer-private (full old history,
                                       plant data included): a source of files only, NEVER a remote of the
                                       working clone, never pushed anywhere
      ia_solar/                        copied by the user from the Lactec PC (2026/Projeto_IA/ia_solar): raw 5-min
                                       exports (dados_brutos/<plant>/exportacoes, incl. 01/01-15/11/2026), the 5-min
                                       parquets (analise/*/dados), the hourly bases (base_modelagem)
      logs/, STATUS.md

1. Ask the user for anything missing (GitHub auth for the private clone; whether `ia_solar/` was copied).
2. Working clone: `git config user.name JoaoCarlos134` and
   `git config user.email 93523542+JoaoCarlos134@users.noreply.github.com` (the personal identity, never an
   employer's). Install the push guard as `.git/hooks/pre-push` (executable):

       #!/bin/sh
       # refuses any history that ever touched the plant data
       zero=0000000000000000000000000000000000000000
       while read lr ls rr rs; do
         [ "$ls" = "$zero" ] && continue
         if [ -n "$(git rev-list -n1 "$ls" -- experimentos/testes_previsao/dados/usinas_horario.parquet)" ]; then
           echo "pre-push: $lr carries the old history with the plant data. Refusing." >&2; exit 1
         fi
       done

3. Copy the plant files into the working clone's IGNORED paths from the private clone's checkout:
   `dados/usinas_horario.parquet`, every `resultados/**/*__usinas__*` and `horizonte_usina_*`,
   `resultados/pilotos/Emb-redes__usinas.npz` (173 paths; the list is `git diff --name-only --diff-filter=A
   <public main> <private main>` run inside the private clone after fetching the public one, or simply every
   ignored file the private checkout has under `experimentos/testes_previsao/`). Check `git status` stays clean.
4. Work on a branch `vm/2026-11` in the working clone. Commit gates, scripts, aggregate results and write-ups
   there and push THE BRANCH (the Lactec session reviews and merges into main). Never commit per-hour plant
   forecasts or plant series (`.gitignore` blocks them; check before every commit with `git status`).

## 1. Environments (V0)

Linux, no Smart App Control: one fresh env per `experimentos/testes_previsao/ambientes/*.txt` with `uv`, in
`~/.venvs/<name>` (the scripts look there; `VENVS` overrides). The frozen files are Windows freezes: keep every
version, but take the Linux wheel of torch for this GPU (Blackwell needs CUDA >= 12.8 wheels: `+cu128` or newer;
the home machine's `previsao_gpu` used torch 2.9.1+cu128) and drop Windows-only packages. Record every deviation
in `ambientes/LEIA-ME.md` (a "Linux / VM" section). The library env: `uv venv ~/.venvs/prosumer` +
`uv pip install -e ".[dev,plots,lightgbm,fronius,net,docs]"` from the working clone.

V0 check, in one CPU job: the library suite (`pytest -n 8`), `scripts/test_auditoria.py`, and the FULL parity
(`test_forecast_parity` all combinations, plant ones included now that the files are there; see the test's
options). Record the counts. Anything red stops the queue: write it in `STATUS.md` and do not submit the rest.

## 2. The runs, in order (each: gate committed BEFORE the job is submitted)

The pilot discipline of `CLAUDE.md` holds for every item: a gate written and committed before the run,
outputs in `resultados/pilotos/` (or `resultados_v3/` for V3), never in `previsoes/`, never in `metricas.csv`,
and an honest record in `docs/projeto/PILOTOS_F1_F2.md` (Portuguese, no accents in code comments) also when it
fails. Write all gates of this batch first, commit them in one commit, push the branch, then submit.

| # | What | Resources | Notes |
|---|---|---|---|
| V2 | PVDAQ generality + measured-roof pilots | CPU, `--mem=20G`, one job per system | gates already committed (`d630450`, `08aba0b`/`06827c2`); they stopped for memory on the Lactec PC |
| V6 | CRPS + coverage of every model with quantiles, with and without `postprocessing.conformal_quantiles` | CPU, minutes | a `05c_faixas.py` over saved forecasts; no model rerun |
| V1 | fresh plant test, 01/06 -> 15/11/2026, every choice FROZEN | CPU; GPU for the trained nets | first extend the plant series (below); then rerun regimes A and C of the benchmark's models on the new period only, training on data up to 31/05/2026. The gate lists, before any number, what is frozen (median of all, `median_weather`, `TRUST`/`SKILL`, penalty 3, conformal 28 days) and what counts as "holds" |
| V5 | regime C with the 6 NWP (+ AIFS, now ~21 months) for every model that takes weather | GPU + CPU | re-download `08b_previsao_tempo_extra.py` up to 15/11/2026 first |
| V4 | houses over the whole of 2020 (rolling origin Apr-Dec, four seasons) | CPU + GPU | Dingle (CC0, in the repo) |
| V3 | full benchmark rerun on Linux, one torch, 3 seeds (42, 1, 2) per trained network | the GPU, days (`gpu_sim`) | outputs in `resultados_v3/`; gate: same tie groups (DM + Holm) and per-model skill within the seed spread. The user has not decided whether v3 replaces v2: write it as a check, decide nothing |
| V7 | fine-tuning Chronos-2, TiRex-2, Toto-2.0 per site, rolling origin | GPU | gate: +0.02 over zero-shot in >= 2 cases; the library stays zero-shot unless the gain is large |
| V8 | AutoARIMA: `piloto_autoarima_memoria.py` (one series, one fold, peak memory) | CPU, `--mem=64G` or more, `gpu_sim` | will wait in the queue until memory frees; if it never fits, declare it infeasible with the measurement |
| V9 | Time-LLM with LLaMA-7B (the paper's setting), consumption only | GPU | low priority, last |

Not in this batch: V10 (Curitiba clock redo: the user's decision), TimeGPT (paid API: the user's decision),
V11 (the long-use replay: needs the local database/learning code first; only draft its gate from section 8 of
the review, do not run it).

**Extending the plant series for V1** (the only data work): the old `01_prepara_dados.py` reads the 5-min
parquets and the hourly NASA base from `ia_solar/` and stops at 31/05/2026 (`FIM_NASA`). For 01/06-15/11/2026
write `01b_estende_usinas.py` that reads the NEW Solar.web CSV exports with the LIBRARY's reader
(`prosumer.io.read_energy` / `io.fronius`: a real-format test of it; if it fails, that is a library bug: fix it
with a regression test carrying a few anonymised rows, per `CLAUDE.md`), sums to hours with the same validity
rule (>= 11 of 12), gets NASA POWER hourly for the new months with `prosumer.io.nasa_power` (check the -55 min
alignment and the known Curitiba +1 h clock issue, LEIA-ME section 7: report, do not silently fix), and writes
`dados/usinas_horario_2026b.parquet` (ignored; never committed). Check the overlap months (Jan-May 2026) against
the existing series: the energy must match to the Wh; any difference is reported before V1 runs.

## 3. Job hygiene

- One Slurm script per run under `experimentos/testes_previsao/vm/slurm/` (committed), one model or case per
  job where a model can crash the run (the Windows history: memory blow-ups killed whole queues). `--time` set to
  a real bound, never unlimited without a reason.
- `DISPOSITIVO=cuda` only in GPU jobs; record the device and the torch version in each `tempos_*.json` entry, as
  the scripts already do.
- Never two jobs writing the same `tempos_*.json` at once (chain them, or one file per job and merge after).
- Heavy GPU jobs on `gpu_train`/`gpu_sim`; quick checks on `gpu_dev`.
- At the end of each run, `atualiza.py` only when it touches the published benchmark (V3 writes elsewhere).

## 4. When the queue is submitted

Update `STATUS.md`, commit the gates and scripts, push the branch, and write the short summary for the user:
what runs, in what order, what each needs, what to check tomorrow. Do not wait for the jobs.
