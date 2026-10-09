# -*- coding: utf-8 -*-
"""Refaz tudo o que DERIVA das previsoes gravadas, num comando so, cada passo no ambiente certo.

Antes eram seis comandos em tres ambientes, repetidos a cada modelo novo (09/10/2026):
  07_ensemble -> 05_avalia -> 06_figuras        (ambiente previsao_gpu)
  05b_resolucao                                 (ambiente da biblioteca: .venv do repositorio)
  planilhas do levantamento e do congresso      (previsao_gpu; docs/literatura/scripts)
  teste de regressao contra o metricas.csv      (.venv; confere que a biblioteca reproduz tudo)
Para no primeiro passo que falhar. Nao treina nem preve nada: leva ~1 min.

Sem timeout de proposito: `subprocess.run(timeout=...)` nao mata os processos filhos no Windows (armadilha
de 08/10/2026). Os ambientes vem de VENVS (padrao ~/.venvs) e do .venv na raiz do repositorio.

Uso: python atualiza.py [--sem-planilhas] [--sem-teste]
"""
import os
import subprocess
import sys
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[2]
VENVS = Path(os.environ.get("VENVS", Path.home() / ".venvs"))
EXE = "Scripts/python.exe" if os.name == "nt" else "bin/python"
GPU = VENVS / "previsao_gpu" / EXE
LIB = RAIZ / ".venv" / EXE
DOCS = RAIZ / "docs" / "literatura" / "scripts"

PASSOS = [
    ("ensemble", GPU, [AQUI / "07_ensemble.py"], AQUI),
    ("avaliacao", GPU, [AQUI / "05_avalia.py"], AQUI),
    ("figuras", GPU, [AQUI / "06_figuras.py"], AQUI),
    ("resolucoes", LIB, [AQUI / "05b_resolucao.py"], AQUI),
]
if "--sem-planilhas" not in sys.argv:
    PASSOS += [("planilha do levantamento", GPU, [DOCS / "gera_visao_geral_modelos.py"], DOCS),
               ("planilha do congresso", GPU, [DOCS / "gera_comparacao_A_B.py"], DOCS)]
if "--sem-teste" not in sys.argv:
    PASSOS += [("regressao", LIB, ["-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "no:hypothesispytest",
                                   str(RAIZ / "tests" / "test_benchmark_regression.py")], RAIZ)]

if __name__ == "__main__":
    t_total = time.time()
    for nome, py, args, cwd in PASSOS:
        t0 = time.time()
        r = subprocess.run([str(py), *map(str, args)], cwd=cwd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ultima = (r.stdout.strip().splitlines() or [""])[-1][:150]
        print(f"{'OK   ' if r.returncode == 0 else 'FALHA'} {nome:26s} {time.time() - t0:6.1f} s  {ultima}", flush=True)
        if r.returncode != 0:
            print(r.stdout[-3000:], r.stderr[-3000:], sep="\n")
            sys.exit(1)
    print(f"tudo atualizado em {time.time() - t_total:.0f} s")
