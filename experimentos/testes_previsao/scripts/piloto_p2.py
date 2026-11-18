"""C4 / P2 (servidor, 18/11/2026): os leads 8-15 tem habilidade? Medido de novo com ~7,5 meses de rodadas unicas.

Portao em docs/projeto/PILOTOS_F1_F2.md, "P2" (commitado antes de rodar). Metodo:
  Rodada das 12 UTC de cada dia (Open-Meteo Single Runs, IFS 0,25 e GFS; 16 dias de GHI), de 28/03 a 14/11/2026, nos
  pontos arredondados das usinas. Toda noite e (dados ate 23:00), o `outlook.forecast_ahead` da biblioteca com
  days=15 e a rodada das 12 UTC de e (a ultima que existe as 23:30 locais), em duas versoes: confianca total no
  tempo em todos os leads (W, trust = 1) e nenhuma (S, a expectativa sazonal, trust = 0). Telhado ajustado com os
  dados ANTES do mes (causal, como no V11). Total do dia por lead k = 1..15.
  Por lead: skill_W = 1 - RMSE(W)/RMSE(S) nos totais diarios, DM (perda quadratica, HAC lag 7) W x S, e o a_k que
  minimiza o RMSE de S + a (W - S) em [0, 1] (so relato: NAO vira padrao sem outro sitio).

Uso (ambiente da biblioteca, CPU):
  python piloto_p2.py baixa          (~1 h; retoma pelo cache)
  python piloto_p2.py replay SERIE   (retoma)
  python piloto_p2.py avalia
Saidas: dados/previsao_tempo_rodadas_v1.parquet (publico), resultados/pilotos/p2__usinas__<serie>.parquet (privado,
fora do git), resultados/pilotos/p2.json (agregados).
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from comum import DADOS, SITIOS  # noqa: E402
from piloto_comum import PILOTOS  # noqa: E402

import piloto_horizonte as PH  # noqa: E402  (pega, SemRodada, URL_RODADAS)
import piloto_uso_prolongado as V  # noqa: E402

from prosumer import outlook  # noqa: E402
from prosumer.diagnostics import roof_orientation  # noqa: E402
from prosumer.io import open_meteo as om  # noqa: E402

FUSO = "Etc/GMT+3"
INI, FIM = pd.Timestamp("2026-03-28"), pd.Timestamp("2026-11-14")
MODELOS = ["ecmwf_ifs025", "gfs_seamless"]
ARQ = DADOS / "previsao_tempo_rodadas_v1.parquet"
DIAS = 15
V.ARQ_USINAS = "usinas_horario_v1.parquet"


def arq(serie):
    return PILOTOS / f"p2__usinas__{serie}.parquet"


def baixa():
    pasta = DADOS / "_cache" / "rodadas_v1"
    pasta.mkdir(parents=True, exist_ok=True)
    indisp = []
    for serie, (lat, lon) in SITIOS.items():
        for m in MODELOS:
            for dia in pd.date_range(INI, FIM, freq="D"):
                run = f"{dia.date()}T12:00"
                f = pasta / f"{serie}__{m}__{dia.date()}.parquet"
                if f.exists():
                    continue
                q = dict(latitude=lat, longitude=lon, models=m, run=run, hourly="shortwave_radiation", timezone="GMT",
                         forecast_days=16)
                try:
                    h = PH.pega(PH.URL_RODADAS, q)["hourly"]
                except PH.SemRodada:
                    indisp.append(f"{serie}|{m}|{run}")
                    continue
                df = om.parse_hourly(h, {"shortwave_radiation": "ghi"}, tz=FUSO)
                pd.DataFrame(dict(serie=serie, modelo_nwp=m, run=pd.Timestamp(run), ds=df.ds.dt.tz_localize(None),
                                  ghi=df.ghi.astype("float32"))).to_parquet(f, index=False)
                time.sleep(1.0)
            print(serie, m, "ok", flush=True)
    R = pd.concat([pd.read_parquet(f) for f in sorted(pasta.glob("*.parquet"))], ignore_index=True)
    R.sort_values(["serie", "modelo_nwp", "run", "ds"]).to_parquet(ARQ, index=False)
    (PILOTOS / "p2_download.json").write_text(json.dumps(dict(linhas=len(R), indisponiveis=len(indisp),
                                                               exemplos=indisp[:10]), indent=1))


def replay(serie):
    site = SITIOS[serie]
    x = V._serie(serie)
    R = pd.read_parquet(ARQ)
    R = R[R.serie == serie]
    antigos = pd.read_parquet(arq(serie)) if arq(serie).exists() else None
    feitas = set(pd.to_datetime(antigos.emissao).unique()) if antigos is not None else set()
    partes = [antigos] if antigos is not None else []
    telhado, t0 = {}, time.time()
    for e in pd.date_range(INI, FIM, freq="D"):
        if e in feitas:
            continue
        primeiro = e + pd.Timedelta(days=1)
        r = R[R.run == e + pd.Timedelta(hours=12)]       # rodada das 12 UTC do dia e (09 locais)
        if r.empty:
            continue
        w = r.pivot_table(index="ds", columns="modelo_nwp", values="ghi", dropna=False)
        w.columns = ["ghi_" + c for c in w.columns]
        w = w.reset_index()
        w["ds"] = pd.to_datetime(w.ds).dt.tz_localize(FUSO)
        w = w[w.ds >= primeiro.tz_localize(FUSO)]
        mes = primeiro.replace(day=1)
        if mes not in telhado:
            o = roof_orientation(V._ate(x, mes), site).iloc[0]
            telhado[mes] = (float(o.tilt), float(o.azimuth))
        tilt, az = telhado[mes]
        s = V._ate(x, primeiro)
        tot = {}
        for nome, tr in (("W", (1.0,) * DIAS), ("S", (0.0,) * DIAS)):
            o = outlook.forecast_ahead(s, days=DIAS, site=site, weather=w, start=primeiro, tilt=tilt, azimuth=az, trust=tr)
            tot[nome] = o.daily.set_index("date").total
        d = pd.DataFrame({"W": tot["W"], "S": tot["S"]}).reset_index().rename(columns={"date": "alvo"})
        d["alvo"] = pd.to_datetime(d.alvo)
        if d.alvo.dt.tz is not None:
            d["alvo"] = d.alvo.dt.tz_localize(None)
        d["alvo"] = d.alvo.dt.normalize()
        d["emissao"], d["lead"] = e, (d.alvo - e).dt.days
        partes.append(d)
        if len(partes) % 30 == 0:
            pd.concat(partes, ignore_index=True).to_parquet(arq(serie), index=False)
            print(serie, e.date(), f"{time.time() - t0:.0f} s", flush=True)
    pd.concat(partes, ignore_index=True).to_parquet(arq(serie), index=False)


def avalia():
    rel = {"portao": "docs/projeto/PILOTOS_F1_F2.md, P2"}
    trust_novo = {}
    for serie in SITIOS:
        x = V._serie(serie)
        y = x.set_index(x.ds.dt.tz_localize(None)).y
        diario = y.groupby(y.index.normalize()).sum(min_count=24)
        cheio = y.notna().groupby(y.index.normalize()).sum() == 24
        d = pd.read_parquet(arq(serie))
        d["Y"] = diario.reindex(d.alvo).where(cheio.reindex(d.alvo).fillna(False).to_numpy()).to_numpy()
        d = d.dropna(subset=["Y"])
        R = {}
        for k in range(1, DIAS + 1):
            q = d[d.lead == k]
            if len(q) < 30:
                continue
            rmS = float(np.sqrt(((q.Y - q.S) ** 2).mean()))
            rmW = float(np.sqrt(((q.Y - q.W) ** 2).mean()))
            dl = ((q.Y - q.W) ** 2 - (q.Y - q.S) ** 2).groupby(q.alvo).mean().sort_index()
            grade = np.linspace(0, 1, 101)
            erro = [float(np.sqrt(((q.Y - (q.S + a * (q.W - q.S))) ** 2).mean())) for a in grade]
            R[k] = dict(n=len(q), skill_W=1 - rmW / rmS, p_dm=V._dm(dl.to_numpy()), a_otimo=float(grade[int(np.argmin(erro))]),
                        skill_a_otimo=1 - min(erro) / rmS)
        rel[serie] = R
        for k in (8, 9, 10):
            c = R.get(k)
            trust_novo.setdefault(k, []).append(bool(c and c["n"] >= 150 and c["skill_W"] > 0 and c["p_dm"] < 0.05))
    rel["lead_ganha_peso"] = {k: all(v) for k, v in trust_novo.items()}
    (PILOTOS / "p2.json").write_text(json.dumps(rel, indent=1, default=float), encoding="utf-8")
    print(json.dumps(rel, indent=1, default=float)[:3000])


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "baixa":
        baixa()
    elif c == "replay":
        replay(sys.argv[2])
    elif c == "avalia":
        avalia()
