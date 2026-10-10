#!/usr/bin/env bash
# Fila da noite (maquina de casa, RTX 4070): so o que pesa (GPU/CPU por horas). De dia a maquina fica livre.
# Uso (de scripts/):  bash fila_noite.sh        log em ../resultados/log_fila_noite_<data>.txt (fora do git)
# Cada etapa e independente: uma falha nao para as seguintes. Nao roda o atualiza.py: a decisao de entrar no
# benchmark (sementes, determinismo) e conferida de dia, depois.
cd "$(dirname "$0")"
P=~/.venvs/previsao_gpu/Scripts/python.exe; B=../../../.venv/Scripts/python.exe
LOG=../resultados/log_fila_noite_$(date +%Y-%m-%d).txt
export DISPOSITIVO=cuda
nota() { echo "== $1 $2"; $B piloto_comum.py $1 $2 A 2>&1 | grep -E '"(skill|MBE|posicao|dm_p_vs_melhor|grupo_da_frente)"' | tr -d '\n'; echo; }
{
date
# 1. Mamba no benchmark (regime A, 3 casos; usinas ~3 h pela varredura sequencial)
$P -u 04_redes_treinadas.py casas_prod casas_cons usinas --modelos Mamba --regimes A
date
# 2. estabilidade do Mamba na FV das casas (sementes 1 e 2, ~20 min cada); relatar como sair
for s in 1 2; do $P -u piloto_mamba.py Mamba semente=$s casas_prod; nota Mamba-s$s casas_prod; done
date
# 3. determinismo: benchmark x piloto (mesma semente) nas casas
$B - <<'EOF'
import pandas as pd
for c in ("casas_prod", "casas_cons"):
    a = pd.read_parquet(f"../resultados/previsoes/Mamba__{c}__A.parquet")
    b = pd.read_parquet(f"../resultados/pilotos/Mamba__{c}__A.parquet")
    m = a.merge(b, on=["unique_id", "ds"], suffixes=("_b", "_p"))
    print(c, len(a), len(b), len(m), "max diff", float((m.yhat_b - m.yhat_p).abs().max()))
EOF
date
# 4. TimeGrad (etapa A; ambiente lagllama, GPU): FV das casas, consumo, usinas
~/.venvs/lagllama/Scripts/python.exe -u piloto_timegrad.py casas_prod casas_cons usinas 2>&1 | grep -E "^OK|Error|Traceback"
for c in casas_prod casas_cons usinas; do nota TimeGrad $c; nota TimeGrad-media $c; done
echo FIM; date
} >> "$LOG" 2>&1
