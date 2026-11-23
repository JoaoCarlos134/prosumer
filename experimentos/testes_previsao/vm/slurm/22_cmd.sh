#!/bin/bash
# Roda um comando de shell em scripts/ com o registro de inicio/fim/falha em STATUS.md:
#   22_cmd.sh "<comando>"      (as variaveis BENCH_*, SEMENTE, DISPOSITIVO vem do sbatch --export)
source "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/_comum.sh"
set -u
cd "$BENCH/scripts" || exit 1
echo "$(date) | $*"
bash -c "$*"
rc=$?
status "$* terminou (status $rc)"
exit $rc
