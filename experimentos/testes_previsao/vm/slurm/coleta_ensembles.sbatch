#!/bin/bash
# Coleta diaria dos ensembles da Open-Meteo (scripts/10_coleta_ensembles.py). Job de 1 CPU, sem GPU, ~1 min.
# Ao comecar, ele mesmo se agenda para amanha 02:30 UTC (23:30 no Brasil) ANTES de baixar: uma falha de hoje nao
# quebra a corrente. Nao agenda se ja houver uma copia pendente (nunca duas correntes).
# Primeira vez:   REPO=~/Projeto_IA/prosumer sbatch $REPO/experimentos/testes_previsao/vm/slurm/coleta_ensembles.sbatch
# Parar:          scancel -n coleta_ens
#SBATCH --job-name=coleta_ens
#SBATCH --cpus-per-task=1
#SBATCH --mem=2G
#SBATCH --time=00:20:00
#SBATCH --output=%x-%j.out
set -u
REPO=${REPO:-$HOME/Projeto_IA/prosumer}
BASE=${BASE:-$HOME/Projeto_IA}
ESTE="$REPO/experimentos/testes_previsao/vm/slurm/coleta_ensembles.sbatch"
mkdir -p "$BASE/logs" "$BASE/ensembles"
if [ -z "$(squeue -h -u "$USER" -n coleta_ens -t PENDING)" ]; then
  quando=$(date -d "tomorrow 02:30 UTC" +%Y-%m-%dT%H:%M:%S)
  sbatch --begin="$quando" --output="$BASE/logs/coleta_ens-%j.out" --export=ALL,REPO="$REPO",BASE="$BASE" "$ESTE"
fi
STATUS="$BASE/STATUS.md" "${PY:-$HOME/.venvs/prosumer/bin/python}" \
  "$REPO/experimentos/testes_previsao/scripts/10_coleta_ensembles.py" --saida "$BASE/ensembles"
