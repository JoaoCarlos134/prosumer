# Fila do servidor de computacao (18/11/2026)

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
| C2 | **V11-b: o replay do piloto V11 no periodo intocado 06-11/2026** (`piloto_uso_prolongado.py` com o arquivo do tempo estendido; nada reajustado) | o piloto de 18/11 NAO PASSOU nas usinas: o a_k e o vies ja eram os padroes (ajustados nelas). Pergunta que sobra: a faixa conformal por sitio nos leads 4-7 (cobertura 0,59-0,73 -> 0,75-0,78). Portao novo, so sobre a faixa |
| C3 | V1 (parte CPU): referencias, LightGBM, fisico, fundacionais zero-shot | o do V1 |
| C4 | P2: leads 8-15 com abr-nov/2026 de rodadas unicas | baixar a Single Runs ate 15/11 |
| C5 | V2: PVDAQ + telhado medido (portoes ja commitados) | um job por sistema, `--mem=20G`; se algum sistema PVDAQ tiver dados de 2024 em diante, ele e o candidato para o V11 num sitio NOVO (o tempo arquivado comeca em 2024) |
| C6 | P4: conversao tempo -> kWh nas 21 usinas FIXAS do BR-PVGen (POA medida separa erro de conversao de erro de tempo) | BR-PVGen NAO TEM coordenadas (so o estado, anonimizado): posicao do sol pelo centro do estado e declarada; ou estimar longitude/latitude pelos proprios dados (o relogio contra o sol): decidir no portao |
| C7 | V6: CRPS e cobertura das faixas | minutos |
| C8 | V8: AutoARIMA (memoria) | `--mem=64G`, espera a memoria liberar |

**Bloqueado:** P5 (confianca por clima no BR-PVGen) e o V11 completo no BR-PVGen: sem coordenadas nao ha previsao do
tempo no sitio. Precisa de outro conjunto publico com coordenadas e dados de 2024 em diante (PVDAQ recente, a
colecao do EDS-lab, ou outro) ou da estimativa de posicao de C6.

## 3. Quando cada rodada termina

Resultados agregados + registro em `PILOTOS_F1_F2.md` no ramo do servidor, push do RAMO; a maquina de CPU revisa
(`work-reviewer`) e junta no `main`. Nada de dado de usina por hora no git (`git status` antes de cada commit).
