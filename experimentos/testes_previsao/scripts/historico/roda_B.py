# -*- coding: utf-8 -*-
"""Retreina as 7 redes do regime B (usinas) com a normalizacao global corrigida.
Guarda as metricas da versao com defeito (para o registro) e roda como processo independente.
Log: resultados/log_B.txt, termina com a linha FIM."""
import json, shutil, subprocess, sys, os, datetime
from pathlib import Path

AQUI = Path(__file__).parent
RES = AQUI.parent / "resultados"
LOG = RES / "log_B.txt"
t = RES / "tempos_redes.json"
tempos = json.loads(t.read_text())
antigos = {k: v for k, v in tempos.items() if k.endswith("|usinas|B")}
(RES / "regime_B_com_defeito_tempos.json").write_text(json.dumps(antigos, indent=1))
if (RES / "metricas.csv").exists():
    shutil.copy2(RES / "metricas.csv", RES / "metricas_antes_da_correcao_B.csv")
t.write_text(json.dumps({k: v for k, v in tempos.items() if k not in antigos}, indent=1))
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PYTHONWARNINGS="ignore")
with open(LOG, "a", encoding="utf-8") as f:
    f.write("=== %s retreino regime B (%d modelos) ===\n" % (datetime.datetime.now().strftime("%d/%m %H:%M"), len(antigos))); f.flush()
    r = subprocess.run([sys.executable, "-u", "04_redes_treinadas.py", "usinas"], cwd=AQUI, env=env, stdout=f, stderr=subprocess.STDOUT)
    f.write("=== codigo de saida %d ===\nFIM %s\n" % (r.returncode, datetime.datetime.now().strftime("%d/%m %H:%M")))
