# -*- coding: utf-8 -*-
"""Roda o que falta, como processo independente: redes treinadas (pula as ja feitas) e Toto nas usinas.
Escreve tudo em resultados/log_restante.txt e termina com a linha FIM."""
import subprocess, sys, os, datetime
from pathlib import Path

AQUI = Path(__file__).parent
LOG = AQUI.parent / "resultados" / "log_restante.txt"
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PYTHONWARNINGS="ignore")
with open(LOG, "a", encoding="utf-8") as f:
    for etapa in (["04_redes_treinadas.py"], ["03_fundacionais.py", "Toto", "--casos", "usinas"]):
        f.write("=== %s %s ===\n" % (datetime.datetime.now().strftime("%d/%m %H:%M"), " ".join(etapa))); f.flush()
        r = subprocess.run([sys.executable, "-u"] + etapa, cwd=AQUI, env=env, stdout=f, stderr=subprocess.STDOUT)
        f.write("=== codigo de saida %d ===\n" % r.returncode); f.flush()
    f.write("FIM %s\n" % datetime.datetime.now().strftime("%d/%m %H:%M"))
