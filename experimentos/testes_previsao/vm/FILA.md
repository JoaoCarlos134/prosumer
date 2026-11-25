# Fila do servidor de computacao (18/11/2026)

**Sem GitHub por desenho (decisao do usuario, 18/11/2026).** O clone do servidor NAO e ligado ao GitHub: nao ha
credencial e nao se faz push daqui. Os commits (portoes, scripts, registros) ficam no ramo local `vm/2026-11`; ao
fim das rodadas o usuario leva o ramo e os resultados a mao para a maquina de CPU (por exemplo `git bundle create
vm.bundle main..vm/2026-11` + os agregados de `resultados/pilotos/`), onde sao revisados e juntados no `main`.
`git fetch` do repositorio publico e permitido para atualizar a base. Toda rodada tem de andar SEM supervisao: jobs
em cadeia com `--dependency`, idempotentes, cada um registrando inicio/fim/falha em `~/Projeto_IA/STATUS.md`.

Complementa o prompt privado do servidor (que segue valendo: pastas, identidade, guarda de push, ambientes V0,
higiene dos jobs). Decisao do usuario em 18/11: **o maximo possivel vai para o servidor**, que tem espaco e esta
livre; a GPU costuma estar mais livre que a CPU, entao os jobs de GPU vem primeiro. A maquina de CPU fica com a
biblioteca, o site, as revisoes e a vitrine local. Regras do projeto valem para tudo: portao escrito e commitado
ANTES de cada rodada, saidas em `resultados/pilotos/` (ou `resultados_v3/`), registro honesto em
`docs/projeto/PILOTOS_F1_F2.md`, nada de dado de usina por hora no git. Um job por modelo/caso onde um modelo pode
derrubar a fila; no maximo uma GPU e ~24 threads ao mesmo tempo; `--mem=20G` salvo onde dito.

## 0. Agora, antes de tudo: coleta diaria dos ensembles (CPU, 1 min/dia, para sempre)

`scripts/10_coleta_ensembles.py` (testado em 18/11: IFS e AIFS 51 membros, GEFS 31, ICON-EPS 40, GEM 21; 16 dias;
GHI e temperatura; ~260 KB/dia para as duas usinas). A Open-Meteo apaga os membros em 3 dias: dia sem coleta e
perdido. Primeira vez (depois do ambiente da biblioteca):

    REPO=~/Projeto_IA/prosumer sbatch $REPO/experimentos/testes_previsao/vm/slurm/coleta_ensembles.sbatch

O job se reagenda para 02:30 UTC do dia seguinte antes de baixar. Conferir no dia seguinte: `squeue -u $USER -n
coleta_ens` (um pendente) e a linha `ok` em `~/Projeto_IA/STATUS.md`. Se o no nao aceitar `--begin` ou a corrente
cair, alternativa: `crontab -e` com `30 2 * * * <python> <repo>/experimentos/testes_previsao/scripts/10_coleta_ensembles.py --saida ~/Projeto_IA/ensembles`
(o cron usa o fuso do sistema: ajustar a hora para 02:30 UTC). O P3 (media do ensemble para os dias 4-15, membros
como faixa) e testado depois de 2-3 meses de coleta: escrever o portao entao.

## V0 (18/11): partido em dois

`slurm/01a_v0_rapido.sbatch` (test_auditoria + torch na GPU nos 3 ambientes; minutos) libera a fila (afterok);
`slurm/01b_v0_paridade.sbatch` (paridade completa, `gpu_train`, 24 h, 8 CPUs, sem GPU) roda ao lado e nao bloqueia
nada. A suite da biblioteca rodou em 17/11: 712 ok, 2 falhas = `test_clear_sky_is_bit_identical` por 1 ulp (numpy
2.5.5 / pandas 3.1.1; o mesmo do ambiente da nuvem em 23/10, CLAUDE.md): ambiente, nao codigo, nao bloqueia.
O V0 de 16/11 (um job so, 3 h) estourou o tempo na paridade e a fila afterok morreu (DependencyNeverSatisfied).

## Estado em 18/11/2026 (fim da sessao)

Tudo abaixo esta na fila Slurm (`slurm/fila_18nov.sh`, 57 jobs, ids em `~/Projeto_IA/logs/fila_18nov.ids`), com
portao commitado antes (`PILOTOS_F1_F2.md`). Mudancas em relacao ao plano: V9 DESTRAVADO (token de leitura do
HuggingFace do usuario, fora do repo; `huggyllama/llama-7b`, o checkpoint do codigo dos autores); V7 so com o
Chronos-2 (TiRex-2 e Toto-2.0 nao tem codigo de treino nos pacotes); V1 sem o regime B (NASA cobre 55 % das horas
novas); C10 feito na sessao (`docs/projeto/DADOS_PUBLICOS_C10.md`): o PVDAQ residencial (1158 sistemas com 2024-2025)
e o candidato para o V11 num sitio novo e para o P5 fora do Brasil (portao ainda por escrever).

## 1. GPU (em ordem; um job de GPU por vez)

| # | Rodada | Por que na GPU | Portao |
|---|---|---|---|
| G1 | **P1-gpu: modelos fundacionais com as 6 NWP como covariaveis, leads 1-7, nas usinas** (Chronos-2 com covariaveis futuras = GHI/POA de cada modelo e media/espalhamento; TabPFN-TS com as mesmas colunas), contra a cadeia fisica do `outlook` e o LightGBM 6-NWP do F2(a) | ataca a Prioridade 1 (previsao melhor nos leads 1-7) com o que so roda bem em GPU | escrever: ganho >= +0,02 no total do dia lead 1 sobre a cadeia fisica nas duas usinas, DM p < 0,05, e tempo de inferencia por sitio na CPU registrado (regra de velocidade de 16/10: so entra na biblioteca opt-in) |
| G2 | V5: regime C com as 6 NWP (+ AIFS, ~21 meses) em todo modelo que aceita clima | redes e fundacionais | a do plano (`REVISAO_TESTES_2026-11-16.md`) |
| G3 | V7: ajuste fino de Chronos-2, TiRex-2, Toto-2.0 por sitio | treino | +0,02 sobre o zero-shot em >= 2 casos |
| G4 | V1 (parte GPU): redes treinadas no periodo intocado 06-11/2026 | treino | o do V1 (escolhas congeladas, listadas antes) |
| G5 | V4: casas no ano todo (redes) | treino | o do plano |
| G6 | V3: benchmark inteiro, 3 sementes | dias de GPU (`gpu_sim`) | mesmos grupos de empate; nada decidido sobre v3 publicado |
| G7 | V9: Time-LLM com LLaMA-7B | 96 GB | baixa prioridade |

## 2. CPU (em paralelo aos jobs de GPU, ate ~24 threads)

| # | Rodada | Nota |
|---|---|---|
| C1 | V0 + `01b_estende_usinas.py` (prompt privado) | pre-requisito do V1 e do C2 |
| C2 | **V11-b: o replay do piloto V11 no periodo intocado 06-11/2026** (`piloto_uso_prolongado.py` com o arquivo do tempo estendido; nada reajustado) | o piloto de 18/11 NAO PASSOU nas usinas: o a_k e o vies ja eram os padroes (ajustados nelas). Pergunta que sobra: a faixa conformal por sitio (F cobre so 0,59-0,73 no lead 7). Portao novo, so sobre a faixa, com os quantis CONSERVADORES de amostra finita (floor/ceil de a(n+1)/n; a sonda pos hoc da revisao deu 0,77-0,84) e a regra exata escrita antes |
| C3 | V1 (parte CPU): referencias, LightGBM, fisico, fundacionais zero-shot | o do V1 |
| C4 | P2: leads 8-15 com abr-nov/2026 de rodadas unicas | baixar a Single Runs ate 15/11 |
| C5 | V2: PVDAQ + telhado medido (portoes ja commitados) | um job por sistema, `--mem=20G`; se algum sistema PVDAQ tiver dados de 2024 em diante, ele e o candidato para o V11 num sitio NOVO (o tempo arquivado comeca em 2024) |
| C6 | P4: conversao tempo -> kWh nas 21 usinas FIXAS do BR-PVGen (POA medida separa erro de conversao de erro de tempo) | BR-PVGen NAO TEM coordenadas (so o estado, anonimizado): posicao do sol pelo centro do estado e declarada; ou estimar longitude/latitude pelos proprios dados (o relogio contra o sol): decidir no portao |
| C7 | V6: CRPS e cobertura das faixas | minutos |
| C8 | V8: AutoARIMA (memoria) | `--mem=64G`, espera a memoria liberar |

| C9 | **Posicao das usinas do BR-PVGen pelos proprios dados** (pedido de 18/11): longitude pelo meio-dia solar medido (o `quality.clock_offset` / relogio contra o sol, ao contrario: hora conhecida -> longitude), latitude pela duracao do dia e pela altura do sol ao meio-dia nos dias claros, dentro do estado declarado | portao: validar ANTES nas duas usinas e no PVDAQ (coordenadas conhecidas): erro <= 0,5 grau. So entao usar as posicoes estimadas para baixar o tempo e destravar P5/V11 no BR-PVGen. Declarar a incerteza |
| C10 | **Busca de mais dados publicos** (pedido de 18/11): FV com coordenadas (ou ao menos o municipio) e dados de 2024 em diante, para cruzar com o arquivo de tempo; FV residencial de preferencia; Brasil e outros climas | candidatos a conferir: PVDAQ (sistemas ainda ativos), colecao FV do EDS-lab, Open Power System Data, UK PV (Sheffield Solar), dados abertos de distribuidoras, Solcast/PVOutput (licenca!), Kaggle. Para cada um: licenca, coordenadas, periodo, resolucao, tamanho. Lista em `docs/projeto/` (tabela), nada baixado sem licenca clara; nada de dado com nome de dono |

**Bloqueado:** P5 (confianca por clima no BR-PVGen) e o V11 completo no BR-PVGen: sem coordenadas nao ha previsao do
tempo no sitio. Precisa de outro conjunto publico com coordenadas e dados de 2024 em diante (PVDAQ recente, a
colecao do EDS-lab, ou outro) ou da estimativa de posicao de C6.

## 3. Quando cada rodada termina

Resultados agregados + registro em `PILOTOS_F1_F2.md` no ramo local do servidor (commit, SEM push); o usuario leva o ramo a maquina de CPU, que revisa
(`work-reviewer`) e junta no `main`. Nada de dado de usina por hora no git (`git status` antes de cada commit).

## Estado em 23/11/2026

Fila de 18/11 terminada; vereditos em `docs/projeto/PILOTOS_F1_F2.md` ("Resultados da fila do servidor de 18/11/2026").
Na fila so a coleta diaria dos ensembles (ok todo dia de 19 a 23/11). A refazer no servidor quando os scripts forem
consertados: C9 (validacao), P2 (fonte das rodadas unicas), V9 (dtype), Crossformer/Mamba (caminho `models`).

## Fila de 25/11/2026 (versao 0.6.4 do README): reprocessar o que quebrou em 18/11

Consertados na maquina de CPU em 25/11 (versao 0.6.3); o servidor so precisa de `git fetch` + `git merge
origin/main` no seu ramo local (o repositorio e publico) e destes jobs de GPU, com os portoes de 18/11 (nada muda
neles):

| # | Rodada | Conserto | Como |
|---|---|---|---|
| G7 | V9: Time-LLM com LLaMA-7B e a ablacao sem LLM (casas_cons A) | o LLaMA carregava em float16 e a camada treinada e float32: o LLM congelado vai para float32 (~28 GB) | os mesmos jobs `g7_v9_llama` e `g7_v9_llama_semllm` de `slurm/fila_18nov.sh`; conferir antes com `teste` (2 passos) |
| G4-G6 | Crossformer e Mamba nos jobs de redes (V3 com as 3 sementes, V4; no V1 eles ja estavam fora pelo portao) | o codigo da Time-Series-Library (commit 4e938a1) nao existia no servidor: `redes_proprias._tslib()` clona-o em `~/.cache/tslib-repo` se faltar (conferido na CPU em 25/11) | `04_redes_treinadas.py` pula o que ja esta em `tempos_redes_*.json`: relancar os jobs G5/G6 roda so os dois que faltam |

C9 e P2 rodaram na maquina de CPU em 25/11 (dados publicos, CPU leve): ver `PILOTOS_F1_F2.md`.
