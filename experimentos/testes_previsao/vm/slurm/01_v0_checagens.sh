#!/bin/bash
# V0: ambiente da biblioteca + suite + test_auditoria + paridade completa (PROSUMER_FULL=1) + GPU nos ambientes com torch.
# Idempotente: o ambiente da biblioteca so e criado se faltar; as checagens sempre rodam (sao baratas, e o resultado vai
# para $PROJ/logs/v0_resultado.txt). Qualquer vermelho => exit 1 e a fila seguinte (afterok) nao e liberada.
# PARTES (padrao "suite paridade auditoria gpu") escolhe o que roda; RESULTADO muda o arquivo de resumo.
# 18/11: a suite ja rodou (712 ok; as 2 falhas de test_clear_sky_is_bit_identical sao 1 ulp do numpy novo, ja
# registradas no CLAUDE.md como ambiente); a paridade completa estourou 3 h. Por isso agora em dois jobs:
# 01a (auditoria + gpu, curto, libera a fila) e 01b (paridade, longo, sem GPU, nao bloqueia nada).
source "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/_comum.sh"
set -u
UV=${UV:-$PROJ/tools/bin/uv}
PARTES=${PARTES:-suite paridade auditoria gpu}
OUT=${RESULTADO:-$PROJ/logs/v0_resultado.txt}; : > "$OUT"
tem() { case " $PARTES " in *" $1 "*) return 0;; esac; return 1; }
rc=0
V=$VENVS/prosumer
if [ ! -f "$V/.montado" ]; then
  rm -rf "$V"; "$UV" venv "$V" --python 3.12 || exit 1
  (cd "$REPO" && "$UV" pip install --python "$V/bin/python" -e ".[dev,plots,lightgbm,fronius,net,docs]") || exit 1
  date > "$V/.montado"
fi
cd "$REPO"
if tem suite; then
echo "== biblioteca: pytest -n ${PYTEST_N:-4}" | tee -a "$OUT"
"$V/bin/python" -m pytest -n "${PYTEST_N:-4}" tests 2>&1 | tail -15 | tee -a "$OUT"; [ ${PIPESTATUS[0]} -eq 0 ] || rc=1
fi
if tem paridade; then
echo "== paridade completa (PROSUMER_FULL=1)" | tee -a "$OUT"
PROSUMER_FULL=1 "$V/bin/python" -m pytest -n "${PYTEST_N:-4}" tests/test_forecast_parity.py -rs 2>&1 | tail -15 | tee -a "$OUT"; [ ${PIPESTATUS[0]} -eq 0 ] || rc=1
fi
if tem auditoria; then
echo "== test_auditoria (ambiente previsao)" | tee -a "$OUT"
(cd "$BENCH/scripts" && "$VENVS/previsao/bin/python" -m unittest discover -s . -p test_auditoria.py 2>&1 | tail -8 | tee -a "$OUT"; exit ${PIPESTATUS[0]}) || rc=1
fi
if tem gpu; then
echo "== GPU nos ambientes com torch" | tee -a "$OUT"
for n in previsao previsao_gpu lote2; do
  "$VENVS/$n/bin/python" - <<'P' 2>&1 | tee -a "$OUT"
import sys, torch
x = torch.randn(2048, 2048, device="cuda"); y = (x @ x).sum().item()
print(sys.prefix.split("/")[-1], "torch", torch.__version__, "cuda", torch.version.cuda, torch.cuda.get_device_name(0), "ok", y == y)
P
  [ ${PIPESTATUS[0]} -eq 0 ] || rc=1
done
fi
status "V0 [$PARTES] terminou (status $rc); resumo em $OUT"
exit $rc
