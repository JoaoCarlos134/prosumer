# -*- coding: utf-8 -*-
"""Baixa a previsao do tempo REAL do dia seguinte para as duas usinas (regime C).

Fonte: Open-Meteo Previous Runs API, variaveis *_previous_day1 = o valor que o modelo numerico previa
um dia antes para aquela hora. E a previsao que existiria as 00:00 do dia (ver nota de horario em
comum.py). Modelo principal escolhido antes de ver o teste: ECMWF IFS 0,25 grau. GFS so como
sensibilidade. O arquivo comeca em 2024 (antes disso a API devolve vazio).

Saida: testes_modelos/dados/previsao_tempo.parquet (serie, modelo_nwp, ds local, ghi_prev, temp_prev)
"""
import time
import truststore; truststore.inject_into_ssl()
import requests, pandas as pd
from comum import DADOS

URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
SITIOS = {"Cascavel": (-24.83, -53.65), "Curitiba": (-25.4284, -49.2733)}
MODELOS_NWP = ["ecmwf_ifs025", "gfs_seamless"]
INI, FIM = "2024-01-01", "2026-05-31"

tabs = []
for serie, (lat, lon) in SITIOS.items():
    for nwp in MODELOS_NWP:
        r = requests.get(URL, params=dict(latitude=lat, longitude=lon, models=nwp, start_date=INI, end_date=FIM,
                                          hourly="shortwave_radiation_previous_day1,temperature_2m_previous_day1",
                                          timezone="America/Sao_Paulo"), timeout=300)
        r.raise_for_status()
        h = r.json()["hourly"]
        t = pd.DataFrame(dict(ds=pd.to_datetime(h["time"]), ghi_prev=h["shortwave_radiation_previous_day1"],
                              temp_prev=h["temperature_2m_previous_day1"]))
        t["serie"], t["modelo_nwp"] = serie, nwp
        ok = t.dropna(subset=["ghi_prev"])
        print("%-9s %-13s %d horas, com valor de %s a %s" % (serie, nwp, len(t), ok.ds.min(), ok.ds.max()))
        tabs.append(t)
        time.sleep(1)
T = pd.concat(tabs, ignore_index=True)
T.to_parquet(DADOS / "previsao_tempo.parquet", index=False)
