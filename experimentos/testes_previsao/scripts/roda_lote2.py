# -*- coding: utf-8 -*-
"""Lote 2: espera a rodada v2 terminar (linha FIM nos dois logs) e roda os modelos novos, cada um no seu
ambiente, depois o ensemble, as metricas e as figuras. Log em resultados/log_lote2.txt (termina com FIM).

Ficaram de fora, testados em 05/10/2026: TabPFN-TS (mais de 10 min para 9 janelas em CPU; o completo levaria
dias) e TimeXer (no NeuralForecast nao aceita covariaveis futuras, entao nao usaria a previsao do tempo).
"""
import subprocess, sys, os, time, datetime
from pathlib import Path

AQUI = Path(__file__).parent
RES = AQUI.parent / "resultados"
LOG = RES / "log_lote2.txt"
V = Path(os.environ.get("VENVS", Path.home() / ".venvs"))       # pasta dos ambientes (ver ../ambientes/)
BIN = ("Scripts", "python.exe") if os.name == "nt" else ("bin", "python")
PY = {k: str(V / k / BIN[0] / BIN[1]) for k in ("previsao", "lote2", "lote2_hf", "moirai")}
ETAPAS = [
    ("lote2", ["03c_fundacionais_lote2.py", "Toto-2.0-22m", "Toto-2.0-313m", "TiRex-2"]),
    ("lote2_hf", ["03c_fundacionais_lote2.py", "Sundial-128m", "Timer-XL-84m", "Time-MoE-50M"]),
    ("moirai", ["03c_fundacionais_lote2.py", "Moirai-MoE-small"]),
    ("previsao", ["04_redes_treinadas.py", "usinas", "casas_prod", "casas_cons", "--modelos", "NBEATSx"]),
    ("previsao", ["07_ensemble.py"]),
    ("previsao", ["05_avalia.py"]),
    ("previsao", ["06_figuras.py"]),
]
env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", PYTHONWARNINGS="ignore")
agora = lambda: datetime.datetime.now().strftime("%d/%m %H:%M")


def v2_terminou():
    n = 0
    for nome in ("log_v2_usinas.txt", "log_v2_casas.txt"):
        p = RES / nome
        if p.exists() and any(l.startswith("FIM") for l in p.read_text(encoding="utf-8", errors="ignore").splitlines()):
            n += 1
    return n == 2


with open(LOG, "a", encoding="utf-8") as f:
    f.write("=== %s lote 2 na fila: esperando a v2 ===\n" % agora()); f.flush()
    while not v2_terminou():
        time.sleep(60)
    for amb, etapa in ETAPAS:
        f.write("=== %s [%s] %s ===\n" % (agora(), amb, " ".join(etapa))); f.flush()
        r = subprocess.run([PY[amb], "-u"] + etapa, cwd=AQUI, env=env, stdin=subprocess.DEVNULL,
                           stdout=f, stderr=subprocess.STDOUT)
        f.write("=== codigo de saida %d ===\n" % r.returncode); f.flush()
    f.write("FIM %s\n" % agora())
