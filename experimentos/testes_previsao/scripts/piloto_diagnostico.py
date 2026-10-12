# -*- coding: utf-8 -*-
"""Piloto E4 (12/10/2026): o diagnostico da usina so com a energia horaria CA e o local reencontra os achados antigos?

Os achados (docs/projeto/ia_solar/ESTADO_DO_PROJETO.md, "Diagnosticos fechados") vieram dos dados de 5 min do
Lactec, com corrente e tensao CC e geometria conhecida (Cascavel). A biblioteca recebe, no caso comum, so a
energia horaria do inversor e o local. Aqui:

1. dias claros SEM sensor: razao diaria energia / GHI de ceu claro, dia claro se >= 0,9 x o percentil 90 da janela
   centrada de 31 dias (a propria serie diz quais dias foram limpos de nuvem);
2. orientacao ajustada nos dias claros (`prosumer.physics.fit_orientation` com o GHI de ceu claro: em dia limpo
   a forma do dia e a da POA de ceu claro);
3. indice de desempenho por dia claro (energia do dia / kWp x POA de ceu claro do dia);
4. pontos de mudanca em retas por trecho (DP exato, BIC): sujeira e dente de serra (desce devagar, sobe no degrau
   da limpeza), entao o trecho tem inclinacao propria.

PORTAO: reencontrar, a +-1 mes, Cascavel: limpezas (degrau para CIMA) em nov/2023 e set/2024; Curitiba: queda em
dez/2022 com volta em jul/2023 e degrau para cima em jun/2025 (reconfiguracao, +15% CC). Sem rodar modelo.

Uso (ambiente da biblioteca): python piloto_diagnostico.py [--biblioteca]
(--biblioteca grava tambem a varredura do fator da penalidade e a conferencia nas 10 casas de Dingle)
(--biblioteca: a mesma cadeia pela `prosumer.diagnostics.diagnose`, que exige o dia com todas as horas de sol
medidas; o piloto aceita dia com >= 8 horas)
"""
import json

import numpy as np
import pandas as pd

import comum
from prosumer.physics import clear_sky_ghi, fit_orientation, mean_sun, poa_isotropic

ESPERADO = {
    "Cascavel": [("2023-11", "sobe", "limpeza"), ("2024-09", "sobe", "limpeza")],
    "Curitiba": [("2022-12", "desce", "falha string 1"), ("2023-07", "sobe", "volta da string 1"),
                 ("2025-06", "sobe", "reconfiguracao")],
}
MIN_SEG = 15      # dias claros (~1 a 2 meses)
K_MAX = 12


def dias_claros(y, cs, fuso):
    d = pd.DataFrame({"y": y, "cs": cs}).groupby(y.index.date).sum(min_count=20)
    d.index = pd.DatetimeIndex(d.index)
    r = d.y / d.cs.where(d.cs > 0)
    topo = r.rolling(31, center=True, min_periods=10).quantile(0.9)
    return set(d.index[(r >= 0.9 * topo)].date)


def custo_reta(t, y):
    """SSE de uma reta por trecho [a, b) para todos os pares, via somas acumuladas."""
    n = len(y)
    c = [np.concatenate([[0.0], np.cumsum(v)]) for v in (np.ones(n), t, y, t * t, t * y, y * y)]
    C = np.full((n + 1, n + 1), np.inf)
    for a in range(n):
        b = np.arange(a + 2, n + 1)
        s0, s1, sy, s2, sty, syy = (v[b] - v[a] for v in c)
        stt = s2 - s1 ** 2 / s0
        sxy = sty - s1 * sy / s0
        ssy = syy - sy ** 2 / s0
        C[a, b] = np.maximum(ssy - np.where(stt > 1e-12, sxy ** 2 / np.where(stt > 1e-12, stt, 1), 0), 0)
    return C


def segmenta(t, y):
    n = len(y)
    C = custo_reta(t, y)
    melhor = None
    for k in range(1, K_MAX + 1):
        if k * MIN_SEG > n:
            break
        F = np.full((k + 1, n + 1), np.inf)
        bk = np.zeros((k + 1, n + 1), int)
        F[0, 0] = 0
        for j in range(1, k + 1):
            for e in range(j * MIN_SEG, n + 1):
                s = np.arange((j - 1) * MIN_SEG, e - MIN_SEG + 1)
                v = F[j - 1, s] + C[s, e]
                i = int(np.argmin(v))
                F[j, e], bk[j, e] = v[i], s[i]
        cps, e = [], n
        for j in range(k, 0, -1):
            e = bk[j, e]
            cps.append(e)
        cps = sorted(c for c in cps if c > 0)
        bic = n * np.log(F[k, n] / n) + (3 * k - 1) * np.log(n)
        if melhor is None or bic < melhor[0]:
            melhor = (bic, cps)
    return melhor[1]


def diagnostica(serie):
    d = comum.carrega("usinas").query("unique_id == @serie").set_index("ds")
    kwp = float(pd.read_parquet(comum.DADOS / "usinas_horario.parquet").query("serie == @serie").kwp.iloc[0])
    lat, lon = comum.SITIOS[serie]
    idx = pd.DatetimeIndex(d.index).tz_localize(comum.FUSO["usinas"])
    y = pd.Series(d.y.to_numpy(), index=idx)
    cs = pd.Series(clear_sky_ghi(idx, lat, lon), index=idx)
    claros = dias_claros(y, cs, comum.FUSO["usinas"])
    m = np.isin(idx.date, list(claros)) & y.notna().to_numpy()
    sol = mean_sun(idx, lat, lon)
    r2, incl, az = fit_orientation(y.to_numpy(), cs.to_numpy() * m, sol)
    poa = pd.Series(poa_isotropic(cs.to_numpy(), sol, incl, az), index=idx)
    # indice DIARIO (energia do dia claro / esperado do dia): o relogio e a forma do dia (telhado de varios planos)
    # pesam menos que hora a hora; a 1a versao semanal por hora era ruidosa demais em Curitiba
    dd = pd.DataFrame({"y": y.where(m), "p": (kwp * poa / 1000).where(m)}).groupby(idx.date).sum(min_count=8)
    sem = (dd.y / dd.p).dropna()
    sem.index = pd.DatetimeIndex(sem.index)
    t = ((sem.index - sem.index[0]).days / 365.25).to_numpy()
    cps = segmenta(t, sem.to_numpy())
    bordas = [0, *cps, len(sem)]
    trechos = []
    for a, b in zip(bordas[:-1], bordas[1:], strict=True):
        tt, yy = t[a:b], sem.to_numpy()[a:b]
        incl_t, base = np.polyfit(tt, yy, 1)
        trechos.append(dict(inicio=str(sem.index[a].date()), fim=str(sem.index[b - 1].date()), dias=b - a,
                            ini=float(base + incl_t * tt[0]), fim_nivel=float(base + incl_t * tt[-1]),
                            pct_ano=float(100 * incl_t / yy.mean())))
    degraus = [dict(data=str(sem.index[c].date()), antes=trechos[i]["fim_nivel"], depois=trechos[i + 1]["ini"],
                    pct=100 * (trechos[i + 1]["ini"] / trechos[i]["fim_nivel"] - 1)) for i, c in enumerate(cps)]
    return dict(serie=serie, r2=r2, inclinacao=incl, azimute=az, dias_claros=len(claros), semanas=len(sem),
                trechos=trechos, degraus=degraus)


def confere(res):
    ach = []
    for mes, sentido, rotulo in ESPERADO[res["serie"]]:
        alvo = pd.Period(mes, "M")
        bate = [g for g in res["degraus"]
                if abs((pd.Period(g["data"][:7], "M") - alvo).n) <= 1 and (g["pct"] > 0) == (sentido == "sobe")]
        ach.append(dict(esperado=mes, sentido=sentido, rotulo=rotulo, achado=bate[0]["data"] if bate else None,
                        pct=round(bate[0]["pct"], 1) if bate else None))
    return ach


def biblioteca(serie):
    """O mesmo pela biblioteca (`prosumer.diagnostics.diagnose`), no formato de `diagnostica` para o portao."""
    from prosumer.diagnostics import diagnose

    s, kwp = _serie_biblioteca(serie)
    dg = diagnose(s, comum.SITIOS[serie], kwp=kwp)
    o = dg.orientation.iloc[0]
    trechos = [dict(inicio=str(r.start.date()), fim=str(r.end.date()), dias=int(r.days), ini=r.level_start,
                    fim_nivel=r.level_end, pct_ano=r.trend_pct_per_year) for r in dg.segments.itertuples()]
    degraus = [dict(data=str(r.date.date()), antes=r.before, depois=r.after, pct=r.step_pct)
               for r in dg.steps.itertuples()]
    return dict(serie=serie, r2=float(o.r2), inclinacao=float(o.tilt), azimute=float(o.azimuth),
                dias_claros=len(dg.index), semanas=len(dg.index), trechos=trechos, degraus=degraus, notas=dg.notes)


def varredura(fatores=(1, 2, 3, 4, 6)):
    """Fator da penalidade do BIC x eventos, nas duas usinas, na cadeia INTEIRA (o fator vale tambem nas
    passadas do ajuste da orientacao, que usam a segmentacao). Registro da escolha do fator, feita NESTAS usinas."""
    from prosumer import diagnostics as D

    padrao = D.changepoints.__kwdefaults__["penalty"]
    out = {}
    try:
        for f in fatores:
            D.changepoints.__kwdefaults__["penalty"] = f
            for serie in ("Cascavel", "Curitiba"):
                s, kwp = _serie_biblioteca(serie)
                dg = D.diagnose(s, comum.SITIOS[serie], kwp=kwp)
                ev = dg.steps[dg.steps.event]
                o = dg.orientation.iloc[0]
                res = dict(serie=serie, degraus=[dict(data=str(r.date.date()), pct=float(r.step_pct))
                                                 for r in ev.itertuples()])
                out.setdefault(str(f), {})[serie] = dict(inclinacao=float(o.tilt), azimute=float(o.azimuth),
                                                         degraus=res["degraus"], portao=confere(res))
    finally:
        D.changepoints.__kwdefaults__["penalty"] = padrao
    return out


def casas(fator=3):
    """Falso alarme nas 10 casas com FV de Dingle (2020, nenhum evento conhecido), no fuso certo (Europe/Dublin).
    Limite: ~65-70 dias claros por casa e ajuste do telhado nao confiavel em quase todas (inclinacao no limite)."""
    from prosumer import data
    from prosumer import diagnostics as D

    s = data.dingle_houses("generation", path=comum.DADOS / "casas_horario.parquet", tz="Europe/Dublin")
    padrao = D.changepoints.__kwdefaults__["penalty"]
    try:
        D.changepoints.__kwdefaults__["penalty"] = fator
        dg = D.diagnose(s, (52.14, -10.27))  # peninsula de Dingle, aproximado
    finally:
        D.changepoints.__kwdefaults__["penalty"] = padrao
    ev = dg.steps[dg.steps.event]
    return dict(orientacao=dg.orientation.to_dict(orient="records"),
                dias_claros=dg.index.groupby("unique_id").size().to_dict(),
                eventos=[dict(casa=r.unique_id, data=str(r.date.date()), pct=float(r.step_pct)) for r in ev.itertuples()])


def _serie_biblioteca(serie):
    from prosumer import EnergySeries

    d = comum.carrega("usinas").query("unique_id == @serie").reset_index(drop=True)
    x = pd.DataFrame({"unique_id": serie, "ds": pd.to_datetime(d.ds).dt.tz_localize(comum.FUSO["usinas"]),
                      "y": d.y.astype(float)})
    x["valid"] = x.y.notna()
    s = EnergySeries(frame=x, unit="kWh", quantity="generation", tz=comum.FUSO["usinas"], freq="h")
    kwp = float(pd.read_parquet(comum.DADOS / "usinas_horario.parquet").query("serie == @serie").kwp.iloc[0])
    return s, kwp


if __name__ == "__main__":
    import sys

    fonte = biblioteca if "--biblioteca" in sys.argv else diagnostica
    saida = {}
    for serie in ("Cascavel", "Curitiba"):
        res = fonte(serie)
        res["portao"] = confere(res)
        saida[serie] = res
        print(f"\n== {serie}: orientacao R2 {res['r2']:.3f} incl {res['inclinacao']:.0f} az {res['azimute']:.0f}; "
              f"{res['dias_claros']} dias claros, {res['semanas']} dias claros no indice")
        for tr in res["trechos"]:
            print(f"  {tr['inicio']} .. {tr['fim']} ({tr['dias']:3d} d) {tr['ini']:.3f} -> {tr['fim_nivel']:.3f}"
                  f"  {tr['pct_ano']:+6.1f} %/ano")
        for g in res["degraus"]:
            print(f"  degrau {g['data']}: {g['pct']:+.1f} %")
        for p in res["portao"]:
            achado = f"ACHADO {p['achado']} ({p['pct']:+.1f} %)" if p["achado"] else "nao achado"
            print(f"  esperado {p['esperado']} {p['sentido']:5s} ({p['rotulo']}): {achado}")
        for n in res.get("notas", []):
            print("  nota:", n)
    comum.RES.joinpath("pilotos").mkdir(exist_ok=True)
    nome = "diagnostico_biblioteca.json" if fonte is biblioteca else "diagnostico.json"
    if fonte is biblioteca:
        saida["varredura_penalidade"] = varredura()
        saida["casas_dingle"] = casas()
        saida["casas_dingle_fator2"] = casas(2)
        for f, r in saida["varredura_penalidade"].items():
            ev = {k: [(g["data"], round(g["pct"])) for g in v["degraus"]] for k, v in r.items()}
            print()
            print("fator", f, ev)
            print("   portao:", {k: sum(p["achado"] is not None for p in v["portao"]) for k, v in r.items()})
        print()
        print("casas: eventos", saida["casas_dingle"]["eventos"])
        print("casas, fator 2: eventos", saida["casas_dingle_fator2"]["eventos"])
        print("   orientacao:", [(o["unique_id"], o["tilt"], o["azimuth"], round(o["r2"], 2), o["edge"])
                                for o in saida["casas_dingle"]["orientacao"]])
    (comum.RES / "pilotos" / nome).write_text(json.dumps(saida, indent=1, default=float))
