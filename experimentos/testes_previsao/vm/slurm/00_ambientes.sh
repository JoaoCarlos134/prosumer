#!/bin/bash
# V0: monta no Linux os ambientes de ambientes/*.txt em ~/.venvs/<nome> (uv). Idempotente: pula o que ja tem python.
# Desvios dos .txt (congelados no Windows): torch e torchvision instalados COM dependencias (as bibliotecas nvidia-*
# do wheel Linux), o resto com --no-deps; fora pywinpty/triton-windows; o indice do torch vem da etiqueta local da versao.
# Uso: 00_ambientes.sh [nome ...]   (padrao: os seis)
source "$HOME/Projeto_IA/prosumer/experimentos/testes_previsao/vm/slurm/_comum.sh"
set -u
UV=${UV:-$PROJ/tools/bin/uv}
AMB=$BENCH/ambientes
declare -A PY=( [previsao]=3.12 [previsao_gpu]=3.12 [lote2]=3.12 [lote2_hf]=3.12 [moirai]=3.11 [classicos]=3.12 )
declare -A IDX=( [previsao]=cu130 [previsao_gpu]=cu128 [lote2]=cu130 [lote2_hf]=cpu [moirai]=cpu [classicos]=none )
NOMES=("$@"); [ ${#NOMES[@]} -eq 0 ] && NOMES=(previsao previsao_gpu lote2 lote2_hf moirai classicos)
rc_total=0
for n in "${NOMES[@]}"; do
  V=$VENVS/$n
  if [ -x "$V/bin/python" ] && [ -f "$V/.montado" ]; then echo "== $n: ja montado"; continue; fi
  echo "== $n (python ${PY[$n]}, indice ${IDX[$n]}) $(date)"
  rm -rf "$V"; "$UV" venv "$V" --python "${PY[$n]}" || { rc_total=1; continue; }
  T=$(mktemp -d); grep -vE '^(pywinpty|triton-windows|pywin32)==' "$AMB/$n.txt" > "$T/todos.txt"
  grep -E '^(torch|torchvision|torchaudio)==' "$T/todos.txt" > "$T/torch.txt" || true
  grep -vE '^(torch|torchvision|torchaudio)==' "$T/todos.txt" | grep -vE ' @ git\+' > "$T/resto.txt"
  grep -E ' @ git\+' "$T/todos.txt" > "$T/git.txt" || true
  EXTRA=()
  if [ "${IDX[$n]}" != none ]; then EXTRA=(--extra-index-url "https://download.pytorch.org/whl/${IDX[$n]}"); fi
  if [ -s "$T/torch.txt" ]; then
    "$UV" pip install --python "$V/bin/python" -r "$T/torch.txt" --index-strategy unsafe-best-match "${EXTRA[@]}" || { echo "FALHOU torch em $n"; rc_total=1; continue; }
  fi
  "$UV" pip install --python "$V/bin/python" --no-deps -r "$T/resto.txt" --index-strategy unsafe-best-match "${EXTRA[@]}" || { echo "FALHOU resto em $n"; rc_total=1; continue; }
  if [ -s "$T/git.txt" ]; then
    "$UV" pip install --python "$V/bin/python" setuptools wheel
    while IFS= read -r l; do "$UV" pip install --python "$V/bin/python" --no-deps --no-build-isolation "$l" || echo "AVISO git dep: $l"; done < "$T/git.txt"
  fi
  "$V/bin/python" -c "import sys; print(sys.version.split()[0])"
  if [ -s "$T/torch.txt" ]; then CUDA_VISIBLE_DEVICES= "$V/bin/python" -c "import torch; print('torch', torch.__version__, 'cuda build', torch.version.cuda)" || rc_total=1; fi
  date > "$V/.montado"; rm -rf "$T"
done
status "ambientes terminados (status $rc_total)"
exit $rc_total
