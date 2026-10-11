# -*- coding: utf-8 -*-
"""Baixa previsoes do tempo de OUTROS modelos numericos para as usinas (piloto F2(a): combinar previsoes).

Mesma fonte, mesmas variaveis, mesmos pontos e mesmo horario do 08_previsao_tempo.py (Open-Meteo Previous
Runs, *_previous_day1 = o valor previsto na vespera). Arquivo separado, para nao tocar no previsao_tempo.parquet
do regime C publicado.

Cobertura conferida em 11/10/2026 (Cascavel, 07/03/2024 e 01/08/2025): ICON (DWD), Meteo-France, GEM (Canada)
e CMA tem valores desde o inicio do regime C; ECMWF AIFS (IA) e UKMO so mais tarde (o inicio exato sai impresso
aqui); JMA nao tem previous_day1.

Saida: dados/previsao_tempo_extra.parquet (serie, modelo_nwp, ds local, ghi_prev, temp_prev)
"""
import time
import truststore; truststore.inject_into_ssl()
import requests, pandas as pd
from comum import DADOS, SITIOS

URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
MODELOS_NWP = ["icon_seamless", "meteofrance_seamless", "gem_seamless", "cma_grapes_global",
               "ecmwf_aifs025_single", "ukmo_seamless"]
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
        print("%-9s %-21s %d horas, com valor de %s a %s (%d)" % (serie, nwp, len(t), ok.ds.min(), ok.ds.max(), len(ok)))
        tabs.append(t)
        time.sleep(1)
T = pd.concat(tabs, ignore_index=True)
T.to_parquet(DADOS / "previsao_tempo_extra.parquet", index=False)
