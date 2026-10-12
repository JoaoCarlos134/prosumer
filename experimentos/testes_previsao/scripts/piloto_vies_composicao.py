# -*- coding: utf-8 -*-
"""Piloto (12/10/2026): a correcao de vies do consumo depende de QUAIS modelos estao na mediana?

O piloto de 09/10 decidiu "correcao de vies so no consumo" com a mediana de TODOS os modelos do benchmark
(~40; +0,194 -> +0,209). A biblioteca roda medianas pequenas (ingenuas, + LightGBM, + fundacionais). Aqui:
a mesma `prosumer.postprocessing.correct_bias` (14 dias, por casa) sobre medianas de varias composicoes,
com as previsoes gravadas de casas_cons A, nas horas avaliadas do benchmark. Nada roda modelo.

Resultado: a correcao tira o vies de todas (MBE < 1%), mas so melhora o skill da mediana de ~40 modelos;
nas pequenas piora (ingenuas +0,145 -> +0,113). => no `analyze`, a mediana corrigida e uma LINHA, nao a saida.

Uso (ambiente da biblioteca): python piloto_vies_composicao.py
"""
import sys
from pathlib import Path

import pandas as pd

import comum
from prosumer import metrics as pm
from prosumer.postprocessing import correct_bias

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "tests"))
import test_benchmark_regression as T  # noqa: E402

INGENUAS = ["persist_24h", "semanal_168h", "media_7d"]
FM = ["TiRex-2", "Toto-2.0-313m", "Chronos-2"]
COMPOSICOES = {
    "ingenuas": INGENUAS,
    "ingenuas+LightGBM": INGENUAS + ["LightGBM"],
    "ingenuas+3 fundacionais": INGENUAS + FM,
    "ingenuas+LightGBM+3 fundacionais": INGENUAS + ["LightGBM"] + FM,
    "3 fundacionais": FM,
    "ingenuas+LightGBM+TiRex-2": INGENUAS + ["LightGBM", "TiRex-2"],
    "Ensemble-mediana (todos)": None,
}


def prev(nome):
    p = pd.read_parquet(comum.PREV / f"{nome}__casas_cons__A.parquet")[["unique_id", "ds", "yhat"]]
    return p.rename(columns={"yhat": nome})


if __name__ == "__main__":
    real = comum.carrega("casas_cons")[["unique_id", "ds", "y"]]
    act, ref = T.evaluated_actual("casas_cons"), T.reference("casas_cons")
    for nome, membros in COMPOSICOES.items():
        if membros is None:
            med = pd.read_parquet(comum.PREV / "Ensemble-mediana__casas_cons__A.parquet")[["unique_id", "ds", "yhat"]]
        else:
            j = prev(membros[0])
            for m in membros[1:]:
                j = j.merge(prev(m), on=["unique_id", "ds"])
            med = j[["unique_id", "ds"]].assign(yhat=j[membros].median(axis=1))
        cor = correct_bias(med, real, quantity="consumption")[["unique_id", "ds", "yhat"]]
        linha = []
        for rotulo, f in (("mediana", med), ("corrigida", cor)):
            m, r = pm.align(f.assign(yhat=f.yhat.clip(lower=0)), act, ref)
            linha.append(f"{rotulo} {pm.skill(m, r):+.3f} (MBE {pm.metrics(m)['MBE']:+.3f})")
        print(f"{nome:34s}", " | ".join(linha), flush=True)
