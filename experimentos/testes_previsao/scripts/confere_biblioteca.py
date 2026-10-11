# -*- coding: utf-8 -*-
"""Conferencia E3: os modelos da BIBLIOTECA (`prosumer.forecast`) refazem as previsoes gravadas do benchmark?

Para cada modelo pedido, roda o adaptador da biblioteca com o protocolo do benchmark (`comum.tarefa`, que ja vem
de `prosumer.protocol`) e compara com `resultados/previsoes/<modelo>__<caso>__<regime>.parquet`:
- diferenca maxima e media por hora (mesmas series-horas dos dois lados, senao falha);
- skill dos dois contra a referencia do caso, nas horas avaliadas do 05_avalia (o que o texto reporta).
Fundacionais nao treinam, mas o torch muda entre versoes e maquinas: espera-se igualdade so ate o arredondamento
(as previsoes gravadas sao do torch 2.11/2.14; registrar a versao de agora).

Saida: resultados/conferencia_biblioteca.json (uma entrada por modelo|caso|regime). Nao toca no metricas.csv.

Uso (cada modelo no ambiente do pacote dele):
  ~/.venvs/lote2/Scripts/python.exe confere_biblioteca.py TiRex-2 Toto-2.0-313m Toto-2.0-22m [--smoke]
  ~/.venvs/previsao_gpu/Scripts/python.exe confere_biblioteca.py Chronos-2 [--smoke]
  --smoke: 3 janelas de um caso, nao grava (confere que o adaptador roda antes da fila da noite)
"""
import importlib
import json
import os
import sys
import time

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "-1")  # tudo em CPU, como a biblioteca (e o TiRex-2 exige)
import numpy as np
import pandas as pd

from comum import CONTEXTO_FM, EXOG, FUSO, PREV, RES, carrega, tarefa

from prosumer.forecast import Chronos2, TiRex2, Toto2, rolling_forecast

MODELOS = {  # nome no benchmark: (fabrica(com_clima), regimes gravados com clima)
    "Chronos-2": (lambda clima: Chronos2(EXOG if clima else None), {"usinas": ["B", "C"], "casas_prod": ["B"], "casas_cons": ["B"]}),
    "TiRex-2": (lambda clima: TiRex2(EXOG if clima else None), {"usinas": ["B", "C"], "casas_prod": ["B"], "casas_cons": ["B"]}),
    "Toto-2.0-313m": (lambda clima: Toto2("313m"), {}),
    "Toto-2.0-22m": (lambda clima: Toto2("22m"), {}),
}
SAIDA = RES / "conferencia_biblioteca.json"


def confere(nome, caso, regime, smoke=False):
    fabrica, _ = MODELOS[nome]
    clima = regime != "A"
    task = tarefa(carrega(caso, regime), caso, contexto=CONTEXTO_FM, exog=clima)
    modelo = fabrica(clima)
    t0 = time.time()
    if smoke:
        p = modelo.predict(task.windows()[:3])
        assert p.shape == (3, 24) and np.isfinite(p).all(), p.shape
        return dict(smoke=True, segundos=round(time.time() - t0, 1), max=float(p.max()))
    nossa = rolling_forecast(modelo, task)
    dt = time.time() - t0
    gravada = pd.read_parquet(PREV / f"{nome}__{caso}__{regime}.parquet")
    gravada["ds"] = gravada.ds.dt.tz_localize(FUSO[caso])
    m = nossa.merge(gravada[["unique_id", "ds", "yhat"]], on=["unique_id", "ds"], how="outer", suffixes=("", "_g"))
    if len(m) != len(nossa) or len(m) != len(gravada):
        return dict(erro=f"series-horas diferentes: nossa {len(nossa)}, gravada {len(gravada)}, juntas {len(m)}")
    dif = (m.yhat - m.yhat_g).abs()
    av = importlib.import_module("05_avalia")
    base = av.real(caso)
    base = base[base.avalia][["unique_id", "ds", "y"]]
    base["ds"] = base.ds.dt.tz_localize(FUSO[caso]) if base.ds.dt.tz is None else base.ds
    ref = pd.read_parquet(PREV / f"{av.REF[caso]}__{caso}__A.parquet")
    ref["ds"] = ref.ds.dt.tz_localize(FUSO[caso])
    j = base.merge(m, on=["unique_id", "ds"]).merge(ref[["unique_id", "ds", "yhat"]].rename(columns={"yhat": "r"}),
                                                     on=["unique_id", "ds"]).dropna()
    rmse = lambda c: float(np.sqrt(np.mean((j[c].clip(lower=0) - j.y) ** 2)))
    import torch
    return dict(segundos=round(dt, 1), torch=torch.__version__, horas=int(len(m)),
                max_dif=float(dif.max()), media_dif=float(dif.mean()),
                skill_biblioteca=round(1 - rmse("yhat") / rmse("r"), 6), skill_gravada=round(1 - rmse("yhat_g") / rmse("r"), 6))


if __name__ == "__main__":
    args = sys.argv[1:]
    smoke = "--smoke" in args
    for nome in [a for a in args if a in MODELOS]:
        _, com_clima = MODELOS[nome]
        combos = [("usinas", "A")] if smoke else [(c, r) for c in ("usinas", "casas_prod", "casas_cons")
                                                  for r in ["A"] + com_clima.get(c, [])]
        for caso, regime in combos:
            chave = f"{nome}|{caso}|{regime}"
            try:
                r = confere(nome, caso, regime, smoke)
            except Exception as e:  # uma falha nao para as outras
                r = dict(erro=f"{type(e).__name__}: {str(e)[:300]}")
            print(("SMOKE " if smoke else "OK    ") + chave, json.dumps(r), flush=True)
            if not smoke:
                tudo = json.loads(SAIDA.read_text(encoding="utf-8")) if SAIDA.exists() else {}
                tudo[chave] = r
                SAIDA.write_text(json.dumps(tudo, indent=1, ensure_ascii=False), encoding="utf-8")
