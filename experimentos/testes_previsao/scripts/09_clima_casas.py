# -*- coding: utf-8 -*-
"""Clima medido das casas (Dingle, Irlanda), hora a hora, alinhado com dados/casas_horario.parquet.

Abre o regime B nas casas (clima do proprio dia). Fonte: arquivo `weather.csv` da colecao de Khadem et al.
(2024), Scientific Data, doi:10.1038/s41597-024-03454-2, figshare doi:10.6084/m9.figshare.25927249 (CC0).
Estacao local, 1 minuto, ano de 2020: vento (speed, dir), temperatura (drybulb), pressao (cbl),
radiacao global (soltot) e chuva (rain).

O que foi conferido (07/10/2026), e por isso o script faz o que faz:
- soltot esta em J/cm2 por minuto: x 1e4/60 = W/m2. Maximo ~1.315 W/m2, media anual ~112 W/m2 (Irlanda).
- O clima esta em UTC: o centro de cada dia de radiacao cai a 0,1-0,4 h do meio-dia solar em UTC o ano
  todo, sem salto de horario de verao; a grade de minutos e completa, sem hora faltando nem repetida.
- As CASAS estao em hora local de Dublin (GMT no inverno, UTC+1 no verao), rotulo = inicio da hora, numa
  grade sem buraco: o horario da geracao FV das 10 casas salta ~+1 h em 29/03 em todas elas. A linha de
  29/03 01:00 (hora que nao existe) e a unica de 25/10 01:00 (hora que existiu duas vezes) vem preenchidas.
- Por isso o clima e convertido para a hora local de Dublin e so entao agregado por hora: a correlacao com
  a FV media das casas sobe em todos os periodos (ano 0,710 -> 0,717; teste out-dez 0,639 -> 0,644).
  A hora repetida de 25/10 recebe a media das duas horas reais; a de 29/03 nao tem clima e e interpolada
  (coluna clima_interpolado).
- Defeitos: 1 minuto com soltot negativo (-98,8; zerado) e 18 minutos de chuva em branco (NaN).
- Unidades nao confirmadas pelo LEIA-ME do conjunto: `vento` (media 10,3; provavelmente nos, padrao da
  Met Eireann, e nao m/s) e `chuva_mm` (soma por hora; mm e o mais provavel). Temperatura em graus C e
  pressao em hPa batem com os valores.

Saida: dados/clima_casas_horario.parquet, uma linha por hora local (ds ingenuo, como nas casas). O clima e
um so para as 20 casas (uma estacao). O download fica em dados/_cache/ (fora do git).

Rodar do diretorio scripts/:  python 09_clima_casas.py
"""
import hashlib
import json
import urllib.request

import numpy as np
import pandas as pd
from comum import DADOS

ARTIGO_FIGSHARE = 25927249
MD5 = "56035b96a1250e3476c62588d40a8875"
LAT, LON = 52.14, -10.27  # Dingle (a localizacao exata das casas nao e publicada)
FUSO = "Europe/Dublin"
CACHE = DADOS / "_cache" / "weather.csv"


def baixa():
    if CACHE.exists() and hashlib.md5(CACHE.read_bytes()).hexdigest() == MD5:
        return
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    art = json.load(urllib.request.urlopen(f"https://api.figshare.com/v2/articles/{ARTIGO_FIGSHARE}"))
    urllib.request.urlretrieve(art["files"][0]["download_url"], CACHE)
    if hashlib.md5(CACHE.read_bytes()).hexdigest() != MD5:
        raise RuntimeError("weather.csv baixado nao confere com o MD5 do figshare")


def ghi_ceu_claro_utc(t):
    """GHI de ceu claro (Haurwitz, a mesma formula de comum.ghi_ceu_claro) em instantes UTC."""
    n = t.dayofyear.to_numpy()
    h = t.hour.to_numpy() + t.minute.to_numpy() / 60
    g = 2 * np.pi / 365 * (n - 1 + (h - 12) / 24)
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g)
                    - 0.040849 * np.sin(2 * g))
    dec = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
           + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    w = np.radians((h * 60 + eot + 4 * LON) / 4 - 180)  # angulo horario a partir do tempo solar verdadeiro
    cz = np.sin(np.radians(LAT)) * np.sin(dec) + np.cos(np.radians(LAT)) * np.cos(dec) * np.cos(w)
    czp = np.clip(cz, 1e-3, None)
    return np.where(cz > 0, 1098.0 * czp * np.exp(-0.059 / czp), 0.0)


def main():
    baixa()
    w = pd.read_csv(CACHE, low_memory=False)
    w["ds_utc"] = pd.to_datetime(w["date"], format="%d/%m/%Y %H:%M")
    m = pd.DataFrame({
        "ghi": w["soltot"].clip(lower=0) * 1e4 / 60,                      # J/cm2/min -> W/m2
        "ghi_ceu_claro": ghi_ceu_claro_utc(pd.DatetimeIndex(w["ds_utc"] + pd.Timedelta("30s"))),
        "temp": w["drybulb"], "vento": w["speed"], "pressao": w["cbl"],
        "chuva": pd.to_numeric(w["rain"], errors="coerce"),
    })
    # UTC -> hora local de Dublin (relogio), sem fuso, como nas casas; agrega pela hora local
    local = pd.DatetimeIndex(w["ds_utc"]).tz_localize("UTC").tz_convert(FUSO).tz_localize(None)
    hora = local.floor("h")
    agg = m.groupby(hora).agg(ghi_horario=("ghi", "mean"), ghi_ceu_claro=("ghi_ceu_claro", "mean"),
                              temp_ar_horaria=("temp", "mean"), vento=("vento", "mean"),
                              pressao_hpa=("pressao", "mean"), chuva_mm=("chuva", "sum"),
                              minutos=("ghi", "size"))
    agg.index.name = "ds"

    casas = pd.read_parquet(DADOS / "casas_horario.parquet")
    grade = pd.DatetimeIndex(sorted(casas["ds"].unique()), name="ds")
    c = agg.reindex(grade)
    c["clima_interpolado"] = c["ghi_horario"].isna()
    fora = c.index > agg.index.max()                                        # 2021-01-01 00:00: fim do arquivo
    cols = [k for k in c.columns if k not in ("minutos", "clima_interpolado")]
    c.loc[~fora, cols] = c.loc[~fora, cols].interpolate(limit=2)
    c["clima_interpolado"] &= ~fora
    # indice de ceu claro, como poa_estimada/poa_ceu_claro nas usinas (so com sol de verdade)
    c["kc"] = (c["ghi_horario"] / c["ghi_ceu_claro"].where(c["ghi_ceu_claro"] > 20)).clip(0, 1.3)
    c = c.reset_index()
    c.to_parquet(DADOS / "clima_casas_horario.parquet", index=False)

    # conferencia, a mesma feita na investigacao
    fv = casas.groupby("casa")["prod_kWh"].sum()
    pv = casas[casas["casa"].isin(fv[fv > 0].index)].groupby("ds")["prod_kWh"].mean()
    x = c.set_index("ds")["ghi_horario"].reindex(pv.index)
    teste = pv.index >= "2020-10-01"
    print(f"ok {DADOS / 'clima_casas_horario.parquet'} | {len(c)} horas | interpoladas {int(c['clima_interpolado'].sum())} "
          f"| sem clima {int(c['ghi_horario'].isna().sum())} (fim do arquivo)")
    print(f"correlacao FV media das casas x GHI local: ano {pv.corr(x):.3f} | teste out-dez {pv[teste].corr(x[teste]):.3f}")


if __name__ == "__main__":
    main()
