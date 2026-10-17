# -*- coding: utf-8 -*-
"""Piloto (17/10/2026): o que foi ajustado nas usinas do Parana vale em sistemas que nao serviram para ajusta-lo?

PERGUNTA. A biblioteca tem pecas escolhidas ou postas a mao nas duas usinas do Parana (e nas casas de Dingle): o
ajuste da orientacao do telhado e a regra de dia claro (`diagnostics`), a checagem do relogio pelo sol
(`quality.clock_offset`) e a cadeia fisica da previsao dos proximos dias (`outlook.forecast_ahead`: potencia
efetiva aprendida nos dias claros x irradiancia no plano dos paineis a partir do GHI). A regra do usuario
(16/10/2026, "nada sob medida para os nossos dados") pede validar, quando der, num sitio que nao serviu para
escolhe-las. O NREL PVDAQ (CC BY 4.0) tem sistemas reais nos EUA com a orientacao no metadata: verdade para o
telhado e para o relogio, outros climas, outro hemisferio, horario de verao, outras marcas de inversor.

SISTEMAS (escolhidos ANTES de olhar qualquer resultado, pela lista de 16/10: qa "pass", fixos, orientacao no
metadata, um ano de arquivos diarios no balde publico, UMA coluna de potencia AC da usina inteira; os de colunas
por inversor, passo irregular ou sentinela ficaram de fora: 1199, 1203, 1283, 4902):

| id | lugar | clima | kWp | inclinacao/azimute | inversor | passo | periodo | coluna |
|---|---|---|---|---|---|---|---|---|
| 50 | Golden, CO | BSk | 6 | 45 / 158 | Fronius | 1 min | 2022-02-01 a 2023-01-31 | ac_power |
| 1200 | Linthicum Heights, MD | Cfa | 51,8 | 10 / 205 | SMA | 5 min | 2019 | ac_power_metered_kw (W) |
| 1201 | Cherry Hill, NJ | Cfa | 140,1 | 10 / 230 | Satcon | 5 min | 2019 | ac_power_hw |
| 1239 | Presque Isle, ME | Dfb | 20,2 | 10 / 155 | Solectria | 15 min | 2019 | ac_power_metered_kw (W) |
| 34 | Las Vegas, NV | BWh | 146,6 | 11,2 / 180 | Satcon | 15 min | 2019 | ac_power_hw |
| 1433 | Golden, CO | BSk | 449,3 | 10 / 180 | ? | 15 min | 2017 | ac_power (kW) |

Fuso: o da lista de sistemas (`io.pvdaq.zone`); os de horario de verao sao lidos com `dst="drop"` (a hora que
nao existe ou que se repete sai, com aviso). Unidade: inferida da placa (`io.pvdaq.unit_from_nameplate`).
Referencia: a usina de Cascavel (o sitio onde as pecas foram escolhidas), 2022-02-01 a 2023-01-31, do
`usinas_horario.parquet`, com o MESMO tratamento (GHI da NASA baixado agora pelo `io.nasa_power`, nao a coluna
do benchmark).

PERGUNTAS E PORTAO (fixados antes de baixar os dados):

- G1, telhado (`diagnostics.diagnose`, padroes): inclinacao ajustada a +-10 graus da do metadata em >= 4 dos 6
  sistemas. Azimute (circular, +-25 graus) so onde a inclinacao verdadeira e >= 15 graus (so o 50: telhado de
  10 graus quase nao tem azimute identificavel); nos outros, relatado sem portao.
- G2, relogio (`quality.clock_offset`, padroes): desvio da serie inteira 0 e confiante em >= 5 dos 6. Os meses
  sao relatados (um registrador sem horario de verao num fuso com ele da 0 numa parte do ano e +-1 na outra:
  e o que a checagem deve mostrar, nao falha dela).
- G3, cadeia fisica da previsao: dias de teste = do 121o dia ao fim, com as 24 horas validas no real e o GHI da
  NASA em todas as horas (os dias de troca de horario de verao, de 23 ou 25 horas, ficam de fora). Para cada dia d, `forecast_ahead(serie ate d-1, days=1, site)` duas vezes: com o GHI
  da NASA do dia d como "previsao perfeita" (lead 1, confianca 1) e sem tempo (expectativa sazonal). Skill
  diario = 1 - RMSE(total com o tempo) / RMSE(total sazonal). PASSA se a mediana dos 6 sistemas >= o skill de
  Cascavel - 0,10. Relatados: skill horario (horas de sol), potencia efetiva / kWp, orientacao usada.
- Sem filtro de neve (Golden e Maine tem): o dado de um usuario tambem tem. Sem teste estatistico (contagem e
  mediana); a referencia e um sitio so.

DECISAO conforme o resultado: G1 falha => o telhado ajustado nao e confiavel fora daqui (o `outlook` e o
`diagnostics` passam a pedir inclinacao e azimute com mais forca); G2 falha => investigar a checagem do relogio
nesses sitios antes de confiar nela; G3 falha => a previsao de geracao, o principal da biblioteca, piora fora do
Parana: investigar (telhado, transposicao, potencia efetiva) antes do site TypeScript.

SAIDA: `resultados/pilotos/pvdaq.json` (agregados por sistema; nada privado: so Cascavel e privado, e dele sai so
o skill). Os arquivos diarios do PVDAQ ficam no cache (`$PROSUMER_DATA` ou `~/.cache/prosumer`), fora do
repositorio.

Uso (ambiente da biblioteca, CPU, ~1 h; rede para baixar):
    python piloto_pvdaq.py baixa      # PVDAQ + NASA para o cache (uma vez)
    python piloto_pvdaq.py            # roda
"""
import json
import os
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

import comum
from prosumer import EnergySeries, diagnostics, outlook, quality
from prosumer.io import nasa_power, pvdaq

SISTEMAS = {
    50: ("2022-02-01", "2023-01-31", "ac_power"),
    1200: ("2019-01-01", "2019-12-31", "ac_power_metered_kw"),
    1201: ("2019-01-01", "2019-12-31", "ac_power_hw"),
    1239: ("2019-01-01", "2019-12-31", "ac_power_metered_kw"),
    34: ("2019-01-01", "2019-12-31", "ac_power_hw"),
    1433: ("2017-01-01", "2017-12-31", "ac_power"),
}
CASCAVEL = ("2022-02-01", "2023-01-31", (-24.83, -53.65), "Etc/GMT+3")
AQUECIMENTO = 120
TOL_TILT, TOL_AZ, TOL_G3 = 10.0, 25.0, 0.10
CACHE = Path(os.environ.get("PROSUMER_DATA") or Path.home() / ".cache" / "prosumer")
NASA = CACHE / "pvdaq" / "nasa"
SAIDA = comum.RES / "pilotos" / "pvdaq.json"


def _sistemas():
    lista = pvdaq.systems().set_index("system_id")
    out = {}
    for sid in SISTEMAS:
        meta = pvdaq.metadata(sid)
        site = pvdaq.site_of(meta)
        site["tz"] = pvdaq.zone(lista.loc[sid, "timezone_or_utc_offset"])
        site["local"] = meta.get("Site", {}).get("location") or lista.loc[sid, "site_location"]
        out[sid] = site
    return out


def baixa():
    info = _sistemas()
    NASA.mkdir(parents=True, exist_ok=True)

    def um(item):
        sid, (ini, fim, col) = item
        t0 = time.time()
        meses = pd.date_range(ini, fim, freq="MS")
        for m in meses:  # mes a mes: um pedido de listagem por mes, arquivos no cache
            fim_m = min(m + pd.offsets.MonthEnd(0), pd.Timestamp(fim))
            try:
                pvdaq.fetch(sid, m, fim_m, column=col, tz=info[sid]["tz"], dst="drop")
            except ValueError as e:
                print(f"{sid} {m:%Y-%m}: {e}")
        return sid, round(time.time() - t0)

    with ThreadPoolExecutor(max_workers=6) as ex:
        for sid, s in ex.map(um, SISTEMAS.items()):
            print(f"PVDAQ {sid} ok ({s} s)", flush=True)
    for sid, (ini, fim, _) in SISTEMAS.items():
        s = info[sid]
        f = NASA / f"{sid}.parquet"
        if not f.exists():
            nasa_power.fetch_hourly(round(s["latitude"], 2), round(s["longitude"], 2), start=ini, end=fim,
                                    variables=("ghi",), tz=s["tz"]).to_parquet(f)
            print(f"NASA {sid} ok", flush=True)
    ini, fim, site, tz = CASCAVEL
    f = NASA / "cascavel.parquet"
    if not f.exists():
        nasa_power.fetch_hourly(*site, start=ini, end=fim, variables=("ghi",), tz=tz).to_parquet(f)
        print("NASA Cascavel ok", flush=True)


def serie_pvdaq(sid, info):
    ini, fim, col = SISTEMAS[sid]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pvdaq.fetch(sid, ini, fim, column=col, tz=info[sid]["tz"], dst="drop")


def serie_cascavel():
    ini, fim, _, tz = CASCAVEL
    d = pd.read_parquet(comum.DADOS / "usinas_horario.parquet")
    d = d[(d["serie"] == "Cascavel") & (d["ds"] >= ini) & (d["ds"] < pd.Timestamp(fim) + pd.Timedelta(days=1))]
    f = pd.DataFrame({"unique_id": "cascavel", "ds": d["ds"], "y": d["y_Wh"] / 1000, "valid": d["y_valido"]})
    return EnergySeries.from_dataframe(f, unit="kWh", quantity="generation", tz=tz, freq="h")


def g3(s, site, ghi, kwp):
    """Skill diario e horario da cadeia fisica com o GHI 'perfeito' contra a expectativa sazonal."""
    f = s.frame
    tz = s.tz
    g = ghi.set_index("ds")["ghi"]
    dias = sorted(f["ds"].dt.tz_localize(None).dt.normalize().unique())
    inicio = dias[0] + pd.Timedelta(days=AQUECIMENTO)
    linhas, horas = [], []
    for d in dias:
        if d < inicio:
            continue
        dia = pd.date_range(pd.Timestamp(d).tz_localize(tz), (pd.Timestamp(d) + pd.Timedelta(days=1)).tz_localize(tz),
                            freq="h", inclusive="left")
        if len(dia) != 24:  # troca de horario de verao
            continue
        real = f[f["ds"].isin(dia)]
        if len(real) < 24 or not real["valid"].all() or g.reindex(dia).isna().any():
            continue
        antes = replace(s, frame=f[f["ds"] < dia[0]].reset_index(drop=True))
        w = pd.DataFrame({"ds": dia, "ghi": g.reindex(dia).to_numpy()})
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ow = outlook.forecast_ahead(antes, days=1, site=site, weather=w, start=dia[0], kwp=kwp)
            os_ = outlook.forecast_ahead(antes, days=1, site=site, start=dia[0], kwp=kwp)
        yw, ys = ow.hourly["y_hat"].to_numpy(), os_.hourly["y_hat"].to_numpy()
        y = real.sort_values("ds")["y"].to_numpy()
        linhas.append({"dia": str(pd.Timestamp(d).date()), "real": y.sum(), "tempo": yw.sum(), "sazonal": ys.sum(),
                       "fonte": ow.daily["source"].iloc[0]})
        sol = ow.hourly["sun"].to_numpy()
        horas.append(np.column_stack([y[sol], yw[sol], ys[sol]]))
    t = pd.DataFrame(linhas)
    if t.empty:
        return {"dias": 0}
    h = np.vstack(horas)
    rmse = lambda a, b: float(np.sqrt(np.mean((a - b) ** 2)))  # noqa: E731
    m = ow.method["series"][s.series[0]]
    return {
        "dias": len(t),
        "skill_diario": round(1 - rmse(t["tempo"], t["real"]) / rmse(t["sazonal"], t["real"]), 4),
        "skill_horario_sol": round(1 - rmse(h[:, 1], h[:, 0]) / rmse(h[:, 2], h[:, 0]), 4),
        "fonte_tempo_em_todos": bool((t["fonte"] == "weather").all()),
        "kw_eff_ultimo": round(float(m["kw_eff"]), 3),
        "kw_eff_sobre_kwp": round(float(m["kw_eff"]) / kwp, 3) if kwp else None,
        "orientacao_usada": [round(float(m["tilt"]), 1), round(float(m["azimuth"]), 1), m["orientation"]],
        "vies_diario_tempo": round(float((t["tempo"] - t["real"]).mean() / t["real"].mean()), 4),
    }


def avalia_sistema(s, site, ghi, kwp, verdade):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        diag = diagnostics.diagnose(s, site, kwp=kwp)
        relogio = quality.clock_offset(s, site)
    o = diag.orientation.iloc[0]
    r = {"cobertura_horaria": round(float(s.frame["valid"].mean()), 3),
         "telhado": {"ajustado": [round(float(o["tilt"]), 1), round(float(o["azimuth"]), 1)],
                     "r2": round(float(o["r2"]), 3), "borda": bool(o["edge"])}}
    if verdade is not None:
        tilt, az = verdade
        dt = abs(float(o["tilt"]) - tilt)
        daz = abs((float(o["azimuth"]) - az + 180) % 360 - 180)
        r["telhado"].update({"verdade": [tilt, az], "erro_tilt": round(dt, 1), "erro_azimute": round(daz, 1),
                             "tilt_ok": bool(dt <= TOL_TILT),
                             "azimute_ok": bool(daz <= TOL_AZ) if tilt >= 15 else None})
    w = relogio[relogio["period"] == "all"].iloc[0]
    meses = relogio[relogio["period"] != "all"]
    r["relogio"] = {"desvio_h": float(w["offset_h"]), "confiante": bool(w["confident"]),
                    "concordancia": round(float(w["agreement"]), 3), "ok": bool(w["offset_h"] == 0 and w["confident"]),
                    "meses": {m["period"]: [float(m["offset_h"]), bool(m["confident"])] for _, m in meses.iterrows()}}
    r["passos_diagnostico"] = int(diag.steps["event"].sum()) if "event" in diag.steps else len(diag.steps)
    r["g3"] = g3(s, site, ghi, kwp)
    return r


def main():
    t0 = time.time()
    info = _sistemas()
    res = {}
    for sid in SISTEMAS:
        s = serie_pvdaq(sid, info)
        site = (info[sid]["latitude"], info[sid]["longitude"])
        ghi = pd.read_parquet(NASA / f"{sid}.parquet")
        res[str(sid)] = {"local": info[sid]["local"], "clima": info[sid]["climate"], "kwp": info[sid]["kw"],
                         "tz": info[sid]["tz"],
                         **avalia_sistema(s, site, ghi, info[sid]["kw"], (info[sid]["tilt"], info[sid]["azimuth"]))}
        print(sid, json.dumps(res[str(sid)]["telhado"]), res[str(sid)]["relogio"]["desvio_h"],
              res[str(sid)]["g3"].get("skill_diario"), f"({time.time() - t0:.0f} s)", flush=True)
    cas = serie_cascavel()
    ghi = pd.read_parquet(NASA / "cascavel.parquet")
    ref = avalia_sistema(cas, CASCAVEL[2], ghi, 3.96, None)
    s_ref = ref["g3"]["skill_diario"]
    print("Cascavel", ref["g3"], flush=True)
    tilt_ok = [r["telhado"]["tilt_ok"] for r in res.values()]
    clock_ok = [r["relogio"]["ok"] for r in res.values()]
    skills = [r["g3"]["skill_diario"] for r in res.values() if r["g3"].get("dias")]
    veredito = {
        "G1_telhado": {"tilt_ok": sum(tilt_ok), "de": len(tilt_ok), "passa": sum(tilt_ok) >= 4,
                       "azimute_50_ok": res["50"]["telhado"]["azimute_ok"]},
        "G2_relogio": {"ok": sum(clock_ok), "de": len(clock_ok), "passa": sum(clock_ok) >= 5},
        "G3_cadeia_fisica": {"mediana_pvdaq": round(float(np.median(skills)), 4), "cascavel": s_ref,
                             "passa": bool(np.median(skills) >= s_ref - TOL_G3)},
    }
    saida = {"pergunta": "pecas ajustadas no Parana valem em sistemas do PVDAQ (EUA)?", "veredito": veredito,
             "sistemas": res, "cascavel": ref, "tempo_s": round(time.time() - t0),
             "licenca_dados": "NREL PVDAQ, CC BY 4.0, doi:10.25984/1846021; NASA POWER"}
    SAIDA.write_text(json.dumps(saida, indent=1, ensure_ascii=False))
    print(json.dumps(veredito, indent=1))


if __name__ == "__main__":
    baixa() if "baixa" in sys.argv[1:] else main()
