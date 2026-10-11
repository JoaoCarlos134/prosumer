# -*- coding: utf-8 -*-
"""F1(d) do plano: piloto de MEMORIA do AutoARIMA com exogenas, antes de declarar o caso inviavel.

Historia: com a configuracao reduzida do 02b_classicos.py, `usinas|B` (ARIMAX, 4 exogenas de clima, 2 series,
~60 mil horas cada) passou de ~20 GB em menos de 30 min e foi morto duas vezes (09/10), sem nenhuma dobra gravada.
Nao se sabe se o problema e o ajuste em si, a validacao cruzada do StatsForecast, ou a soma das series.

Piloto: UMA serie, UMA dobra (a 1a), o mesmo modelo e a mesma configuracao do 02b (modelos('B')['AutoARIMA']),
`n_jobs=1`. Uma linha de vigia mede a memoria privada do processo a cada 2 s, grava o pico e encerra o processo
se passar de LIMITE_GB (a maquina tem ~23 GB livres; o VS Code e o resto ficam de pe). Mede, em etapas:
  1. ajuste so no treino (StatsForecast.fit), sem previsao;
  2. a dobra inteira como o 02b faz (cross_validation, refit=False, 61 janelas de 24 h).
`historico=N` corta o treino nas ultimas N horas (ex.: 8760 = 1 ano) para ver como a memoria cresce com o
comprimento. Nada vai para resultados/previsoes; o resumo vai para resultados/pilotos/resumo.json.
Portao (plano): < 2 h por caso e cabendo na memoria -> rodar os 6; senao relatar como inviavel em resolucao horaria.

Uso: python piloto_autoarima_memoria.py [serie=Cascavel] [historico=N] [regime=B]   (ambiente classicos, CPU)
"""
import importlib
import json
import os
import sys
import threading
import time
import warnings

warnings.filterwarnings("ignore")
from statsforecast import StatsForecast  # noqa: E402

from comum import H, dobras  # noqa: E402
from piloto_comum import PILOTOS  # noqa: E402

C = importlib.import_module("02b_classicos")
LIMITE_GB = 16
ARGS = dict(a.split("=", 1) for a in sys.argv[1:] if "=" in a)
SERIE, REGIME = ARGS.get("serie", "Cascavel"), ARGS.get("regime", "B")
HIST = int(ARGS["historico"]) if "historico" in ARGS else None
pico = {"gb": 0.0}
etapa = {"nome": "carga"}


def memoria_privada_gb():
    """Memoria privada (commit) do processo pela API do Windows: o ambiente classicos e congelado e nao tem psutil."""
    import ctypes
    from ctypes import wintypes

    class PMC(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD)] + [
            (n, ctypes.c_size_t) for n in ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                                           "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                                           "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage",
                                           "PrivateUsage")]
    c = PMC(); c.cb = ctypes.sizeof(c)
    k = ctypes.WinDLL("kernel32"); k.GetCurrentProcess.restype = wintypes.HANDLE
    ctypes.WinDLL("psapi").GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.PrivateUsage / 2**30


def vigia():
    while True:
        gb = memoria_privada_gb()
        pico["gb"] = max(pico["gb"], gb)
        if gb > LIMITE_GB:
            print(f"ABORTADO na etapa '{etapa['nome']}': memoria privada {gb:.1f} GB > {LIMITE_GB} GB", flush=True)
            os._exit(3)
        time.sleep(2)


def registra(r):
    f = PILOTOS / "resumo.json"
    tudo = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    tudo[f"AutoARIMA-memoria|usinas-{SERIE}|{REGIME}|hist={HIST or 'todo'}"] = r
    f.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    threading.Thread(target=vigia, daemon=True).start()
    df = C.prepara("usinas", REGIME)
    df = df[df.unique_id == SERIE]
    ini, fim = dobras("usinas")[0]
    treino = df[df.ds < ini]
    if HIST:
        treino = treino.tail(HIST)
        df = df[df.ds >= treino.ds.min()]
    fab = C.modelos(REGIME)["AutoARIMA"]
    r = dict(serie=SERIE, regime=REGIME, horas_treino=len(treino), limite_gb=LIMITE_GB,
             config="approximation=True max_p=3 max_q=3 max_P=1 max_Q=1 nmodels=24 (02b)")
    print(f"{SERIE} {REGIME}: {len(treino)} horas de treino, memoria inicial {pico['gb']:.1f} GB", flush=True)

    etapa["nome"] = "ajuste"; t0 = time.time()
    exog = [c for c in treino.columns if c not in ("unique_id", "ds", "y")]
    sf = StatsForecast(models=[fab()], freq="h", n_jobs=1).fit(treino)
    r["ajuste_s"], r["pico_ajuste_gb"] = round(time.time() - t0, 1), round(pico["gb"], 2)
    try:
        r["ordem"] = str(sf.fitted_[0, 0].model_["arma"])
    except Exception:  # noqa: BLE001 - so informativo
        pass
    print(f"  ajuste: {r['ajuste_s']} s, pico {r['pico_ajuste_gb']} GB, exogenas {exog}", flush=True)
    registra(r)

    etapa["nome"] = "dobra"; t0 = time.time()
    n = (fim.normalize() - ini).days + 1
    cv = StatsForecast(models=[fab()], freq="h", n_jobs=1).cross_validation(
        df=df[df.ds <= fim], h=H, n_windows=n, step_size=H, refit=False)
    r["dobra_s"], r["pico_dobra_gb"], r["janelas"] = round(time.time() - t0, 1), round(pico["gb"], 2), n
    print(f"  dobra ({n} janelas): {r['dobra_s']} s, pico {r['pico_dobra_gb']} GB", flush=True)
    registra(r)
    print("OK AutoARIMA memoria", json.dumps(r, ensure_ascii=False), flush=True)
