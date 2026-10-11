#!/usr/bin/env bash
# Fila da noite (maquina de casa, RTX 4070): so o que pesa (GPU/CPU por horas). De dia a maquina fica livre.
# Uso (de scripts/):  bash fila_noite.sh        log em ../resultados/log_fila_noite_<data>.txt (fora do git)
# Cada etapa e independente e tem teto de tempo: uma falha nao para as seguintes. Nao roda o atualiza.py: a decisao
# de entrar no benchmark e conferida de dia, depois. Filas anteriores: no historico do git (10/10: Mamba, TimeGrad).
#
# 11/10/2026: os dois pilotos de LLM da etapa A, so no consumo (piloto curto, decisao de 10/10).
cd "$(dirname "$0")"
P=~/.venvs/previsao_gpu/Scripts/python.exe; B=../../../.venv/Scripts/python.exe
LOG=../resultados/log_fila_noite_$(date +%Y-%m-%d).txt
export DISPOSITIVO=cuda
nota() { echo "== $1 $2"; $B piloto_comum.py $1 $2 A 2>&1 | grep -E '"(skill|MBE|posicao|dm_p_vs_melhor|grupo_da_frente)"' | tr -d '\n'; echo; }
roda() { timeout "$1" "${@:2}" 2>&1 | grep -E "^OK|ABORTADO|Error|Traceback"; echo "  (saida ${PIPESTATUS[0]}; 124 = teto de tempo)"; }
{
date
# 1. Time-LLM com GPT-2 e a ablacao sem LLM (teto 2 h cada; guarda de memoria de 18 GB no proprio script)
roda 2h $P -u piloto_timellm.py casas_cons;        nota Time-LLM casas_cons; date
roda 2h $P -u piloto_timellm.py semLLM casas_cons; nota Time-LLM-semLLM casas_cons; date
# 2. LLMTime, Qwen2.5-1.5B base, 10 amostras (~3,5 h medido; teto 4 h 30)
roda 270m $P -u piloto_llmtime.py casas_cons;      nota LLMTime casas_cons
echo FIM; date
} >> "$LOG" 2>&1
