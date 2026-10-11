#!/usr/bin/env bash
# Fila da noite (maquina de casa, RTX 4070): so o que pesa (GPU/CPU por horas). De dia a maquina fica livre.
# Uso (de scripts/):  bash fila_noite.sh        log em ../resultados/log_fila_noite_<data>.txt (fora do git)
# MODO_TESTE=1 bash fila_noite.sh: liga o modo_teste.ps1 antes (fecha a lista de programas, plano Alto desempenho) e
# restaura no fim. Sem a variavel, nada e fechado.
# Cada etapa e independente e tem teto de tempo: uma falha nao para as seguintes. Nao roda o atualiza.py: a decisao
# de entrar no benchmark e conferida de dia, depois. Filas anteriores: no historico do git (10/10: Mamba, TimeGrad).
#
# 11/10/2026 (noite): conferencia E3, os modelos da BIBLIOTECA refazem as previsoes gravadas (tudo em CPU,
# < 1 h): LightGBM nas 9 combinacoes (teste exato) e os fundacionais de CPU (confere_biblioteca.py).
cd "$(dirname "$0")"
P=~/.venvs/previsao_gpu/Scripts/python.exe; B=../../../.venv/Scripts/python.exe
LOG=../resultados/log_fila_noite_$(date +%Y-%m-%d).txt
export DISPOSITIVO=cuda
nota() { echo "== $1 $2"; $B piloto_comum.py $1 $2 A 2>&1 | grep -E '"(skill|MBE|posicao|dm_p_vs_melhor|grupo_da_frente)"' | tr -d '\n'; echo; }
roda() { timeout "$1" "${@:2}" 2>&1 | grep -E "^OK|ABORTADO|Error|Traceback"; echo "  (saida ${PIPESTATUS[0]}; 124 = teto de tempo)"; }
MT="powershell -NoProfile -ExecutionPolicy Bypass -File $(cygpath -w "$PWD/modo_teste.ps1")"
[ "$MODO_TESTE" = 1 ] && $MT -Aplicar >> "$LOG" 2>&1
trap '[ "$MODO_TESTE" = 1 ] && $MT -Restaurar >> "$LOG" 2>&1' EXIT
{
date
# 1. LightGBM da biblioteca x gravado, as 9 combinacoes (~3 min; igualdade ate 1e-12)
( cd ../../.. && PROSUMER_FULL=1 timeout 30m .venv/Scripts/python.exe -m pytest -p no:hypothesispytest     tests/test_forecast_parity.py 2>&1 | tail -3 ); date
# 2. Fundacionais de CPU pela biblioteca (resultados/conferencia_biblioteca.json; ~25 min medidos no benchmark)
roda 1h ~/.venvs/lote2/Scripts/python.exe -u confere_biblioteca.py TiRex-2 Toto-2.0-313m Toto-2.0-22m; date
roda 1h $P -u confere_biblioteca.py Chronos-2; date
echo FIM; date
} >> "$LOG" 2>&1
