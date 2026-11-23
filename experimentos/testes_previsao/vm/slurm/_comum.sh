#!/bin/bash
# Funcoes comuns dos jobs da VM. Usar com: source "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/_comum.sh"
# Cada job registra inicio, fim ou falha em ~/Projeto_IA/STATUS.md (uma linha) e e idempotente (pula o que ja existe).
PROJ=${PROJ:-$HOME/Projeto_IA}
REPO=$PROJ/prosumer
BENCH=$REPO/experimentos/testes_previsao
export VENVS=${VENVS:-$HOME/.venvs}
STATUS_MD=$PROJ/STATUS.md
status() { echo "$(date '+%Y-%m-%d %H:%M') | ${SLURM_JOB_NAME:-manual} ${SLURM_JOB_ID:-} | $*" >> "$STATUS_MD"; }
trap 'rc=$?; if [ $rc -ne 0 ]; then status "FALHOU (status $rc)"; fi' EXIT
status "inicio"
