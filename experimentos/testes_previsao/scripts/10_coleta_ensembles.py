"""Coleta diaria das previsoes por CONJUNTO (ensemble) da Open-Meteo, como foram emitidas (18/11/2026).

Por que: a Open-Meteo apaga os membros do ensemble depois de 3 dias e guarda a media so como serie "mais recente",
nao por antecedencia. Para testar o P3 (media do ensemble como previsao dos dias 4-15, espalhamento dos membros
como faixa) precisamos da previsao que EXISTIA em cada noite: so coletando todo dia. Dia sem coleta = perdido.

O que faz (uma vez por dia, ~1 min, sem GPU): para cada sitio, pede 16 dias de GHI (`shortwave_radiation`) e
temperatura a 2 m de cinco ensembles (IFS 0,25, AIFS 0,25, GEFS 0,25, ICON-EPS, GEM global), TODOS os membros, e
grava um parquet longo por dia de coleta: sitio, modelo, membro (0 = controle), ds (UTC), ghi, temp, coletado_utc.
Idempotente: se o arquivo do dia ja existe, nao baixa de novo. Rodar perto de 23:30 do horario local dos sitios
(02:30 UTC no Brasil), que e o que o aplicativo teria as 00:00 da emissao.

  python 10_coleta_ensembles.py [--saida DIR] [--sitios arquivo.json]

Sitios padrao: as duas usinas, nas coordenadas ARREDONDADAS de `comum.SITIOS` (publicas). `--sitios` aceita
{"nome": [lat, lon], ...}. Variavel STATUS (opcional): arquivo onde uma linha por execucao e acrescentada.
Sem dependencia alem de pandas/pyarrow (e truststore se houver, para redes que inspecionam TLS).
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

URL = "https://ensemble-api.open-meteo.com/v1/ensemble"
MODELOS = ["ecmwf_ifs025", "ecmwf_aifs025", "gfs025", "icon_seamless", "gem_global"]
VARIAVEIS = {"shortwave_radiation": "ghi", "temperature_2m": "temp"}
DIAS = 16
SITIOS_PADRAO = {"Cascavel": (-24.83, -53.65), "Curitiba": (-25.4284, -49.2733)}   # = comum.SITIOS
PADRAO_SAIDA = Path(__file__).resolve().parents[1] / "dados" / "ensembles"
TENTATIVAS, PAUSA = 4, 3.0


def _ctx():
    try:
        import truststore
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return ssl.create_default_context()


def _pede(lat, lon):
    q = dict(latitude=lat, longitude=lon, hourly=",".join(VARIAVEIS), models=",".join(MODELOS),
             forecast_days=DIAS, timezone="GMT")
    url = URL + "?" + urllib.parse.urlencode(q)
    erro = None
    for i in range(TENTATIVAS):
        try:
            with urllib.request.urlopen(url, context=_ctx(), timeout=120) as r:
                return json.load(r)
        except Exception as e:  # rede, 429, 5xx: espera e tenta de novo
            erro = e
            time.sleep(PAUSA * 4 ** i)
    raise RuntimeError(f"falhou depois de {TENTATIVAS} tentativas: {erro}")


def _longo(d, sitio, coletado):
    """Colunas `<var>[_memberNN]_<modelo>` -> formato longo."""
    h = d["hourly"]
    ds = pd.to_datetime(h["time"], utc=True)
    partes = []
    for col, val in h.items():
        if col == "time":
            continue
        var = next(v for v in VARIAVEIS if col.startswith(v + "_"))
        resto = col[len(var) + 1:]
        membro = 0
        if resto.startswith("member"):
            membro, resto = int(resto[6:8]), resto[9:]
        partes.append(pd.DataFrame({"sitio": sitio, "modelo": resto, "membro": membro, "ds": ds,
                                    "var": VARIAVEIS[var], "valor": pd.to_numeric(pd.Series(val), errors="coerce")}))
    x = pd.concat(partes, ignore_index=True)
    # unstack, nao pivot_table(dropna=False): este cruzaria todo modelo com todo membro (GEM tem 21, IFS 51)
    x = x.set_index(["sitio", "modelo", "membro", "ds", "var"]).valor.unstack("var").reset_index()
    x.columns.name = None
    x["coletado_utc"] = coletado
    return x


def _status(msg):
    arq = os.environ.get("STATUS")
    if arq:
        with open(arq, "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC coleta_ensembles: {msg}\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--saida", type=Path, default=PADRAO_SAIDA)
    ap.add_argument("--sitios", type=Path)
    a = ap.parse_args()
    sitios = SITIOS_PADRAO if a.sitios is None else json.loads(a.sitios.read_text(encoding="utf-8"))
    agora = datetime.now(timezone.utc)
    a.saida.mkdir(parents=True, exist_ok=True)
    arq = a.saida / f"ens_{agora:%Y-%m-%d}.parquet"
    if arq.exists():
        print(f"ja existe: {arq}")
        return 0
    partes = []
    try:
        for nome, (lat, lon) in sitios.items():
            partes.append(_longo(_pede(lat, lon), nome, pd.Timestamp(agora)))
            time.sleep(PAUSA)
    except Exception as e:
        _status(f"FALHOU ({e})")
        print(e, file=sys.stderr)
        return 1
    x = pd.concat(partes, ignore_index=True)
    tmp = arq.with_suffix(".tmp")
    x.to_parquet(tmp, index=False)
    tmp.replace(arq)                                   # escrita atomica: nunca um arquivo pela metade
    resumo = x.groupby("modelo").membro.nunique().to_dict()
    _status(f"ok {arq.name}, {len(x)} linhas, membros {resumo}")
    print(arq, len(x), resumo)
    return 0


if __name__ == "__main__":
    sys.exit(main())
