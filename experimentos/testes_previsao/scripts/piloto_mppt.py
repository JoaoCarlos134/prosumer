# -*- coding: utf-8 -*-
"""Piloto (17/10/2026): a parcela de cada canal (MPPT, string, inversor) separa falha de string de sujeira?

PERGUNTA. O `diagnostics` acha degraus no indice de desempenho dos dias claros da energia CA total (limpezas,
falhas), mas nao diz se o degrau e de um canal so (string, MPPT, inversor: falha, sombra nova, religacao) ou da
usina toda (sujeira, limpeza, inversor). O README lista "sujeira x sombra x falha de string" como o que falta.
Quando o inversor exporta a energia por canal (o Fronius da usina de Curitiba tem `Energia MPP1` e `Energia
MPP2`; varios sistemas do PVDAQ tem uma coluna por inversor), a PARCELA de cada canal na energia dos dias claros
deve mudar so num evento de canal: a sujeira e a limpeza mexem nos canais juntos e deixam a parcela parada.

METODO (nada ajustado aqui: as pecas e os padroes sao os da biblioteca). Dias claros pela energia CA total
(`diagnostics.clear_days`, padroes). Em cada dia claro, a parcela do canal k = energia_k / soma dos canais.
A serie diaria de cada parcela vai para `diagnostics.changepoints` (mesmos padroes: penalidade 3 x BIC, trecho
minimo 15 dias claros, degrau notado >= 5%).

CASOS (escolhidos antes de rodar):
- Curitiba (Fronius Symo, 2 MPPT, 07/2021 a 07/2026, 5 min; privada, so agregados saem): eventos conhecidos da
  analise de 5 min (`docs/projeto/ia_solar/ESTADO_DO_PROJETO.md`): falha da string 1 em dez/2022 (a string 1
  caiu ~50%, a 2 ~18%), volta em jul/2023, reconfiguracao em jun/2025 (a energia CA total so a mostra com o fator
  2; com o 3, o padrao, o `diagnose` a perde).
- Controle negativo: PVDAQ 1199 (Cockeysville, MD; SMA, 7 inversores, uma coluna `inv<k>_ac_power` cada; 2019,
  5 min; sem evento conhecido): todo degrau numa parcela conta como alarme falso.

PORTAO (fixado antes de rodar):
- G1: na parcela do MPPT1 de Curitiba, um degrau a +-45 dias de >= 2 dos 3 eventos (dez/2022, jul/2023,
  jun/2025), com o sinal esperado nos dois primeiros (para baixo, para cima).
- G2: no controle negativo, no maximo 1 degrau somando as 7 parcelas.
PASSA se G1 e G2 => a biblioteca ganha a decomposicao por canal (uma funcao no `diagnostics` e a secao no
`analyze` quando houver canais). Relatado sem portao: a reconfiguracao de jun/2025 achada ou nao (o que o
indice CA perde) e os degraus fora dos eventos em Curitiba.

SAIDA: `resultados/pilotos/mppt.json` (datas e tamanhos dos degraus; nada da serie de Curitiba). Uso (ambiente
da biblioteca, CPU, ~2 min; o PVDAQ 1199 baixa na 1a vez):
    python piloto_mppt.py
"""
import glob
import json
import os
import time
import warnings
from pathlib import Path

import pandas as pd

import comum
from prosumer import EnergySeries, diagnostics
from prosumer.io import fronius, pvdaq

CURITIBA = os.environ.get(
    "CURITIBA_5MIN",
    r"C:\Users\L08741\OneDrive - Lactec\Documentos\2026\Projeto_IA\ia_solar\dados_brutos\curitiba\serie_5min",
)
SITIO_CURITIBA = comum.SITIOS["Curitiba"]
EVENTOS = {"falha string 1": ("2022-12-15", -1), "volta": ("2023-07-15", +1), "reconfiguracao": ("2025-06-15", 0)}
JANELA = pd.Timedelta(days=45)
CONTROLE = (1199, "2019-01-01", "2019-12-31", [f"inv{k}_ac_power" for k in range(1, 8)])
SAIDA = comum.RES / "pilotos" / "mppt.json"


def parcelas(total: EnergySeries, canais: dict[str, EnergySeries], site: tuple[float, float]) -> pd.DataFrame:
    """A parcela de cada canal nos dias claros da energia total, no formato de `performance_index`."""
    claro = diagnostics.clear_days(total, site)
    dias = claro.loc[claro["clear"], ["date"]].drop_duplicates()
    diario = {}
    for nome, s in canais.items():
        f = s.frame.loc[s.frame["valid"]]
        diario[nome] = f.groupby(f["ds"].dt.tz_localize(None).dt.normalize())["y"].sum(min_count=1)
    d = pd.DataFrame(diario).reindex(pd.DatetimeIndex(dias["date"]))
    d = d.dropna()
    soma = d.sum(axis=1)
    d = d[soma > 0]
    linhas = [pd.DataFrame({"unique_id": nome, "date": d.index, "index": (d[nome] / d.sum(axis=1)).to_numpy()})
              for nome in canais]
    return pd.concat(linhas, ignore_index=True)


def degraus(idx: pd.DataFrame) -> pd.DataFrame:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        _, steps = diagnostics.changepoints(idx)
    return steps[steps["event"]] if "event" in steps else steps


def curitiba():
    arquivos = sorted(glob.glob(str(Path(CURITIBA) / "*.xlsx")))
    kw = dict(tz="Etc/GMT+3", site=SITIO_CURITIBA)
    total = fronius.read_solarweb(arquivos, **kw)
    canais = {f"mpp{k}": fronius.read_solarweb(arquivos, energy_column=f"energy_mpp{k}_Wh", **kw) for k in (1, 2)}
    canais = {k: EnergySeries.from_dataframe(v.frame.assign(unique_id=k), unit="kWh", quantity="generation",
                                             tz=v.tz, freq=v.freq) for k, v in canais.items()}
    idx = parcelas(total, canais, SITIO_CURITIBA)
    st = degraus(idx[idx["unique_id"] == "mpp1"])
    achados = {}
    for nome, (quando, sinal) in EVENTOS.items():
        t = pd.Timestamp(quando)
        perto = st[(pd.to_datetime(st["date"]) - t).abs() <= JANELA]
        ok = not perto.empty and (sinal == 0 or (perto["step_pct"] * sinal > 0).any())
        achados[nome] = {"achado": bool(ok),
                         "degraus": [[str(pd.Timestamp(r["date"]).date()), round(float(r["step_pct"]), 1)]
                                     for _, r in perto.iterrows()]}
    fora = st[~st["date"].isin([d for a in achados.values() for d, _ in a["degraus"]])]
    return {"dias_claros": int(idx["date"].nunique()), "eventos": achados,
            "degraus_fora_dos_eventos": [[str(pd.Timestamp(r["date"]).date()), round(float(r["step_pct"]), 1)]
                                         for _, r in fora.iterrows()]}


def controle():
    sid, ini, fim, cols = CONTROLE
    meta = pvdaq.metadata(sid)
    site = (pvdaq.site_of(meta)["latitude"], pvdaq.site_of(meta)["longitude"])
    tz = pvdaq.zone(pvdaq.systems().set_index("system_id").loc[sid, "timezone_or_utc_offset"])
    canais = {}
    for c in cols:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            s = pvdaq.fetch(sid, ini, fim, column=c, tz=tz, dst="drop", unit="W")
        canais[c] = EnergySeries.from_dataframe(s.frame.assign(unique_id=c), unit="kWh", quantity="generation",
                                                tz=s.tz, freq=s.freq)
    soma = pd.concat([c.frame.set_index(["ds"])["y"] for c in canais.values()], axis=1).sum(axis=1, min_count=7)
    f = pd.DataFrame({"unique_id": "total", "ds": soma.index, "y": soma.to_numpy()})
    total = EnergySeries.from_dataframe(f, unit="kWh", quantity="generation", tz=tz, freq="h")
    idx = parcelas(total, canais, site)
    st = degraus(idx)
    return {"dias_claros": int(idx["date"].nunique()), "degraus": len(st),
            "lista": [[r["unique_id"], str(pd.Timestamp(r["date"]).date()), round(float(r["step_pct"]), 1)]
                      for _, r in st.iterrows()]}


if __name__ == "__main__":
    t0 = time.time()
    cur = curitiba()
    print(json.dumps(cur, indent=1), flush=True)
    neg = controle()
    print(json.dumps(neg, indent=1), flush=True)
    veredito = {"G1": bool(sum(e["achado"] for e in cur["eventos"].values()) >= 2),
                "G2": bool(neg["degraus"] <= 1)}
    veredito["passa"] = veredito["G1"] and veredito["G2"]
    SAIDA.write_text(json.dumps({"veredito": veredito, "curitiba": cur, "controle_pvdaq_1199": neg,
                                 "tempo_s": round(time.time() - t0)}, indent=1, ensure_ascii=False))
    print(veredito, f"({time.time() - t0:.0f} s)")
