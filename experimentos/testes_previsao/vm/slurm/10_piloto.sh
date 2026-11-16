#!/bin/bash
# Roda um script de scripts/ num ambiente: 10_piloto.sh <ambiente> <script.py> [args]. O script e idempotente por si
# (saidas em resultados/pilotos/). Registra inicio/fim em STATUS.md. Falha => exit != 0.
source "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/_comum.sh"
set -u
AMB=$1; SCRIPT=$2; shift 2
cd "$BENCH/scripts" || exit 1
echo "$(date) | $AMB $SCRIPT $*"
"$VENVS/$AMB/bin/python" "$SCRIPT" "$@"
rc=$?
status "$SCRIPT $* terminou (status $rc)"
exit $rc
