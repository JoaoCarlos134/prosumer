# -*- coding: utf-8 -*-
"""Protocolo v2 (origem movel + regime C + lotes iguais): roda tudo o que treina, em dois processos
paralelos e independentes. Usinas: fundacionais no regime C e depois as redes (A, B, C). Casas: as
redes. Logs em resultados/log_v2_usinas.txt e log_v2_casas.txt; cada um termina com a linha FIM.
Depois: 07_ensemble.py, 05_avalia.py, 06_figuras.py (a mao)."""
import subprocess, sys, os, datetime
from pathlib import Path

AQUI = Path(__file__).parent
RES = AQUI.parent / "resultados"
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PYTHONWARNINGS="ignore")
FILAS = {
    "usinas": [["03_fundacionais.py", "Chronos-2", "TimesFM-2.5", "--casos", "usinas", "--regimes", "C"],
               ["04_redes_treinadas.py", "usinas"]],
    "casas": [["04_redes_treinadas.py", "casas_prod", "casas_cons"]],
}
agora = lambda: datetime.datetime.now().strftime("%d/%m %H:%M")

if len(sys.argv) > 1:                      # modo filho: roda uma fila
    nome = sys.argv[1]
    with open(RES / f"log_v2_{nome}.txt", "a", encoding="utf-8") as f:
        for etapa in FILAS[nome]:
            f.write("=== %s %s ===\n" % (agora(), " ".join(etapa))); f.flush()
            r = subprocess.run([sys.executable, "-u"] + etapa, cwd=AQUI, env=env, stdout=f, stderr=subprocess.STDOUT)
            f.write("=== codigo de saida %d ===\n" % r.returncode); f.flush()
        f.write("FIM %s\n" % agora())
else:
    ps = [subprocess.Popen([sys.executable, __file__, n], cwd=AQUI, env=env) for n in FILAS]
    for p in ps:
        p.wait()
    print("FIM", agora())
