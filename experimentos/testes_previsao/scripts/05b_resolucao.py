# -*- coding: utf-8 -*-
"""Metricas em quatro resolucoes (09/10/2026): hora, blocos dia/noite, pico 17-21 h e total do dia.

Por que: o consumo de uma casa hora a hora e em grande parte imprevisivel, mas o total do dia nao; e a
decisao do usuario raramente e por hora (fatura mensal, bateria olhando o pico da noite, tarifa por
bloco). Cada uso escolhe a resolucao da sua decisao.

Roda no AMBIENTE DA BIBLIOTECA (~/.venvs/prossumidor): usa `prossumidor.metricas.por_resolucao`. As horas
avaliadas sao as mesmas do 05_avalia.py (importado daqui), entao o nivel "hora" reproduz exatamente o
skill do metricas.csv; o script confere isso e para se nao bater. Os niveis somam as previsoes e o real
nessas horas (na geracao, as horas fora da mascara tem energia ~0, entao o total do dia praticamente nao
muda). O skill de cada nivel e contra a referencia somada no mesmo nivel.

Blocos: dia = 08-23 h, noite = 23-08 h (tarifa dia/noite da Irlanda, onde estao as casas); pico = 17-21 h.
Para a tarifa branca brasileira, a biblioteca aceita outros blocos (`metricas.por_blocos`).

Saida: resultados/metricas_por_resolucao.csv.  Uso: python 05b_resolucao.py
"""
import importlib
import warnings

import pandas as pd

from comum import RES

warnings.filterwarnings("ignore")
av = importlib.import_module("05_avalia")
from prossumidor import metricas as pm  # noqa: E402

KW = dict(sep=";", decimal=",", encoding="utf-8-sig")
M = pd.read_csv(RES / "metricas.csv", **KW)
M = M[M.regime.isin(["A", "B", "C"])]


def previsao(modelo, caso, regime):
    p = pd.read_parquet(RES / "previsoes" / f"{modelo}__{caso}__{regime}.parquet")[["unique_id", "ds", "yhat"]]
    return p.assign(yhat=p.yhat.clip(lower=0))


linhas = []
for caso, g in M.groupby("caso"):
    base = av.real(caso)
    base = base[base.avalia][["unique_id", "ds", "y"]]
    ref = previsao(av.REF[caso], caso, "A").merge(base, on=["unique_id", "ds"])
    for r in g.itertuples():
        m, rr = pm.alinha(previsao(r.modelo, caso, r.regime), base, ref)
        res = pm.por_resolucao(m, rr)
        hora = res.loc[res.nivel == "hora", "skill"].iloc[0]
        if abs(hora - r.skill) > 1e-9:
            raise AssertionError(f"{r.modelo}|{caso}|{r.regime}: skill por hora {hora} != metricas.csv {r.skill}")
        linhas.append(res.assign(caso=caso, modelo=r.modelo, regime=r.regime))
R = pd.concat(linhas, ignore_index=True)[["caso", "modelo", "regime", "nivel", "blocos", "skill", "R2",
                                          "R2_referencia", "nRMSE", "MBE"]]
R.to_csv(RES / "metricas_por_resolucao.csv", index=False, **KW)
print(f"ok {RES / 'metricas_por_resolucao.csv'} | {len(R)} linhas | {R.groupby(['caso', 'modelo', 'regime']).ngroups} modelos x teste")
