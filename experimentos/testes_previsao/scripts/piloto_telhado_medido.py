# -*- coding: utf-8 -*-
"""Piloto (17/10/2026): ajustar o telhado contra a irradiancia MEDIDA (NASA POWER) em vez do ceu claro?

ORIGEM (exploracao declarada, feita antes deste portao, em dois sistemas que FICAM FORA da avaliacao): no piloto
do PVDAQ (`piloto_pvdaq.py`) o ajuste da biblioteca (`diagnostics`: dias claros da propria serie contra o ceu
claro de Haurwitz) deu 60 graus (no limite) para o sistema 50 (verdade 45 / 158) e 45 graus para o 1200 (verdade
10 / 205). Com a orientacao verdadeira, o indice de desempenho dos dias claros cai ~40-45% do inverno ao verao
nesses dois sistemas (Cascavel: 14%): o Haurwitz nao tem altitude nem turbidez (NASA / Haurwitz nos dias mais
claros: Golden 1,17 em janeiro, 0,83 em julho; Maryland ~1,02 / ~0,88; Cascavel ~0,94-1,07) e falta a
temperatura do modulo. O ajuste "absorve" essa queda sazonal inclinando o telhado. Ajustando contra o GHI
horario da NASA em TODAS as horas (`physics.fit_orientation`, que so mede correlacao), o 50 deu 45 / 160 (a
verdade); o 1200 continuou errado (40 graus), com um relogio que nao e um erro limpo de horario de verao (0 h no
inverno, +2 h de abril a julho): sombra ou outro problema, sem verdade para separar.

PERGUNTA. Nos sistemas que NAO serviram para essa exploracao, o ajuste contra o GHI medido acerta o telhado
melhor que o atual, e a previsao dos proximos dias melhora (ou ao menos nao piora) com ele?

SITIOS (avaliacao): PVDAQ 1201 (NJ, 10/230), 1239 (ME, 10/155), 34 (NV, 11,2/180), 1433 (CO, 10/180) e Cascavel
(13/25, a ficha). Dados e periodos do `piloto_pvdaq.py` (mesmo cache; GHI da NASA do `io.nasa_power`).

METODOS:
- atual: `diagnostics.roof_orientation` (padroes; grade 0-60);
- medido: `physics.fit_orientation(energia horaria valida, GHI NASA da hora, sol medio da hora)`, todas as horas
  com GHI > 50 W/m2, grade de inclinacao 0-90 de 5 em 5 e azimute 0-350 de 10 em 10.

PORTAO (fixado antes de rodar a avaliacao; REVISTO antes de rodar, depois da revisao independente de 17/10, que
mostrou que um portao de inclinacao a +-10 graus nao falha quando os telhados verdadeiros sao todos de 10-13
graus: um estimador constante de 10 ou 15 graus passaria):
- H2 (o DECISIVO): o skill diario da cadeia fisica (o G3 do `piloto_pvdaq.py`: `forecast_ahead` com o GHI da NASA
  do dia como previsao perfeita, contra a expectativa sazonal), com o telhado MEDIDO dado (`tilt=`, `azimuth=`),
  tem mediana nos 5 sitios >= a do telhado ajustado pela biblioteca - 0,02.
- H1 (o telhado, comparativo): o medido tem erro de inclinacao MENOR OU IGUAL ao do atual em >= 4 dos 5 sitios e
  nunca mais de 5 graus pior. LIMITE DECLARADO: com telhados verdadeiros todos baixos, H1 so mostra que o metodo
  nao empina telhados baixos; nao mostra que identifica um telhado inclinado (so o sistema 50, de 45 graus, usado
  no desenho, mostrou isso).
PASSA se H1 e H2 => a biblioteca ganha o ajuste contra irradiancia medida (quando houver: `weather=` no
`diagnostics`, historico da NASA no app), e o ajuste por ceu claro fica como recurso sem rede, com a limitacao
declarada. Nao passa => fica declarado que o telhado ajustado so vale onde o ceu claro de Haurwitz vale (e o
`outlook` pede inclinacao e azimute).

SAIDA: `resultados/pilotos/telhado_medido.json`. Uso (ambiente da biblioteca, CPU, ~40 min; o H2 refaz o G3):
    python piloto_telhado_medido.py
"""
import json
import time
import warnings

import numpy as np
import pandas as pd

import comum
import piloto_pvdaq as P
from prosumer import diagnostics, physics

AVALIA = [1201, 1239, 34, 1433]
PIOR = 5.0
SAIDA = comum.RES / "pilotos" / "telhado_medido.json"


def medido(s, site, ghi):
    f = s.frame.loc[s.frame["valid"]].set_index("ds")["y"]
    g = ghi.set_index("ds")["ghi"].tz_convert(s.tz)
    j = pd.concat([f.rename("y"), g.rename("ghi")], axis=1, join="inner").dropna()
    sun = physics.mean_sun(pd.DatetimeIndex(j.index), *site)
    r2, t, a = physics.fit_orientation(j["y"].to_numpy(), j["ghi"].to_numpy(), sun, tilts=np.arange(0, 91, 5.0))
    return float(t), float(a), float(r2)


def g3_dado(s, site, ghi, kwp, tilt, az):
    """O G3 do piloto do PVDAQ, com o telhado dado."""
    orig = P.outlook.forecast_ahead

    def com_telhado(*a, **k):
        k.setdefault("tilt", tilt)
        k.setdefault("azimuth", az)
        return orig(*a, **k)

    P.outlook.forecast_ahead = com_telhado
    try:
        return P.g3(s, site, ghi, kwp)
    finally:
        P.outlook.forecast_ahead = orig


def um(nome, s, site, ghi, kwp, verdade):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        atual = diagnostics.roof_orientation(s, site).iloc[0]
        t, a, r2 = medido(s, site, ghi)
        g_atual = P.g3(s, site, ghi, kwp)
        g_medido = g3_dado(s, site, ghi, kwp, t, a)
    erro = lambda x, y: abs((x - y + 180) % 360 - 180)  # noqa: E731
    return {
        "verdade": list(verdade),
        "atual": [float(atual["tilt"]), float(atual["azimuth"]), round(float(atual["r2"]), 3)],
        "medido": [t, a, round(r2, 3)],
        "erro_tilt": {"atual": abs(float(atual["tilt"]) - verdade[0]), "medido": abs(t - verdade[0])},
        "erro_azimute": {"atual": erro(float(atual["azimuth"]), verdade[1]), "medido": erro(a, verdade[1])},
        "skill_diario": {"atual": g_atual.get("skill_diario"), "medido": g_medido.get("skill_diario")},
        "dias": g_atual.get("dias"),
    }


def main():
    t0 = time.time()
    info = P._sistemas()
    res = {}
    for sid in AVALIA:
        s = P.serie_pvdaq(sid, info)
        site = (info[sid]["latitude"], info[sid]["longitude"])
        ghi = pd.read_parquet(P.NASA / f"{sid}.parquet")
        res[str(sid)] = um(sid, s, site, ghi, info[sid]["kw"], (info[sid]["tilt"], info[sid]["azimuth"]))
        print(sid, res[str(sid)], f"({time.time() - t0:.0f} s)", flush=True)
    res["cascavel"] = um("cascavel", P.serie_cascavel(), P.CASCAVEL[2], pd.read_parquet(P.NASA / "cascavel.parquet"),
                         3.96, (13.0, 25.0))
    print("cascavel", res["cascavel"], flush=True)
    ok = [r["erro_tilt"]["medido"] <= r["erro_tilt"]["atual"] for r in res.values()]
    pior = [r["erro_tilt"]["medido"] - r["erro_tilt"]["atual"] > PIOR for r in res.values()]
    sk_a = [r["skill_diario"]["atual"] for r in res.values() if r["skill_diario"]["atual"] is not None]
    sk_m = [r["skill_diario"]["medido"] for r in res.values() if r["skill_diario"]["medido"] is not None]
    veredito = {
        "H1": {"medido_nao_pior": sum(ok), "de": len(ok), "pior_5_graus_em": sum(pior),
               "passa": sum(ok) >= 4 and not any(pior)},
        "H2": {"mediana_atual": round(float(np.median(sk_a)), 4), "mediana_medido": round(float(np.median(sk_m)), 4),
               "passa": bool(np.median(sk_m) >= np.median(sk_a) - 0.02)},
    }
    veredito["passa"] = veredito["H1"]["passa"] and veredito["H2"]["passa"]
    SAIDA.write_text(json.dumps({"veredito": veredito, "sitios": res, "tempo_s": round(time.time() - t0)},
                                indent=1, ensure_ascii=False))
    print(json.dumps(veredito, indent=1))


if __name__ == "__main__":
    main()
