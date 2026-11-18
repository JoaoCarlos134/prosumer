# -*- coding: utf-8 -*-
"""C1 (servidor, 18/11/2026): estende as usinas e a previsao do tempo ate 15/11/2026 para o V1 (teste intocado).

Entrada: os exports NOVOS de 5 min do Solar.web (01/01 -> 15/11/2026, um CSV por usina em
`$IA_SOLAR/dados_brutos/<usina>/exportacoes/*.csv`; o nome do arquivo traz o nome do dono e nunca e impresso nem
gravado) + `dados/usinas_horario.parquet` (ate 31/05/2026, nao e alterado).

Passos (portao em docs/projeto/PILOTOS_F1_F2.md, "C1", commitado antes de rodar):
 1. Energia horaria do export com as MESMAS regras do 01_prepara_dados.py (>= 11 de 12 registros; pontas do dia;
    noite = 0). A convencao do carimbo de 5 min (inicio ou fim do intervalo) e escolhida pela concordancia com a
    serie existente em 01/01-31/05/2026. PORTAO: nessa sobreposicao, as horas validas nas duas tem de bater ao Wh
    (|dif| < 0,5 Wh) em >= 99,5% das horas de sol; senao o script para sem gravar.
 2. poa_ceu_claro (geometria) de 01/06-15/11/2026 = o da mesma hora um ano antes (365 dias; 2026 nao e bissexto).
    Conferido em jan-mai/2026 contra o original (relatado: erro medio relativo nas horas de sol).
 3. Clima NASA POWER (ghi_horario, temp_ar_horaria) baixado de novo de 01/12/2025 a 15/11/2026; o deslocamento de
    hora de cada usina (0 ou +1 h; Curitiba tem 1 h de atraso declarado no LEIA-ME secao 7) e o que reproduz a
    coluna existente em jan-mai/2026. poa_estimada nova = poa_ceu_claro * clip(ghi/ghi_ceu_claro, 0, 1,3) (a mesma
    conversao do regime C); correlacao com a original em jan-mai relatada. So o regime B (teto) usa estas colunas.
 4. Previsao do tempo (Open-Meteo Previous Runs) baixada de novo ate 15/11/2026, em arquivos _v1 (os publicados
    ficam): previsao_tempo_v1 (IFS, GFS; lead 1), previsao_tempo_extra_v1 (os 6 extras; lead 1),
    previsao_tempo_horizonte_v1 (6 modelos padrao, leads 1-7). Diferenca maxima contra os publicados na
    sobreposicao relatada.

Saidas: dados/usinas_horario_v1.parquet (privado, ignorado pelo git), dados/previsao_tempo*_v1.parquet (publicos),
resultados/pilotos/estende_usinas.json (so agregados). Idempotente: pula o que ja existe (apague para refazer).
Uso (ambiente da biblioteca): python 01b_estende_usinas.py [--so-usinas | --so-tempo]
"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import DADOS, SITIOS, ghi_ceu_claro  # noqa: E402
from piloto_comum import PILOTOS  # noqa: E402

from prosumer.io import nasa_power, open_meteo as om  # noqa: E402

IA = Path(os.environ.get("IA_SOLAR", Path.home() / "Projeto_IA" / "ia_solar"))
PASTAS = {"Cascavel": "cascavel", "Curitiba": "curitiba"}
KWP = {"Cascavel": 3.96, "Curitiba": 9.60}
INI_NOVO, FIM = pd.Timestamp("2026-06-01"), pd.Timestamp("2026-11-15 23:00")
SOBRE = (pd.Timestamp("2026-01-01"), pd.Timestamp("2026-05-31 23:00"))
FUSO = "Etc/GMT+3"
SAIDA_JSON = PILOTOS / "estende_usinas.json"
URL_PREV = "https://previous-runs-api.open-meteo.com/v1/forecast"


def grava_json(parte):
    atual = json.loads(SAIDA_JSON.read_text()) if SAIDA_JSON.exists() else {}
    atual.update(parte)
    SAIDA_JSON.write_text(json.dumps(atual, indent=1, default=str))


def le_export(usina):
    arqs = sorted((IA / "dados_brutos" / PASTAS[usina] / "exportacoes").glob("*.csv"))
    if len(arqs) != 1:
        raise SystemExit(f"{usina}: esperava 1 CSV de export, achei {len(arqs)}")
    x = pd.read_csv(arqs[0], skiprows=[1], na_values=["n/a"])
    col = [c for c in x.columns if c.startswith("Energia |")]
    assert len(col) == 1, col
    t = pd.to_datetime(x.iloc[:, 0], format="%d.%m.%Y %H:%M")
    return pd.Series(pd.to_numeric(x[col[0]], errors="coerce").to_numpy(), index=t).sort_index()


def horaria(r, poa_cs):
    """As regras do 01_prepara_dados.py sobre a serie de 5 min `r` (Wh), na grade horaria de poa_cs."""
    r = r[~r.index.duplicated()]
    g = r.resample("h")
    y = g.sum(min_count=1).where(g.count() >= 11)
    idx = poa_cs.index
    y = y.reindex(idx)
    y[poa_cs.reindex(idx).fillna(0) <= 0] = 0.0
    cont = g.count().reindex(idx).fillna(0)
    meio = cont.where((cont.index.hour >= 9) & (cont.index.hour < 15)).groupby(cont.index.normalize()).sum()
    dia_ok = pd.Series(cont.index.normalize(), index=cont.index).map(meio) >= 60
    ponta = dia_ok & (poa_cs < 150) & y.isna()
    y[ponta] = g.sum().reindex(idx)[ponta].fillna(0.0)
    return y


def usinas():
    if (DADOS / "usinas_horario_v1.parquet").exists():
        print("ja existe usinas_horario_v1.parquet")
        return
    U = pd.read_parquet(DADOS / "usinas_horario.parquet")
    novos, rel = [], {}
    for usina in PASTAS:
        u = U[U.serie == usina].set_index("ds").sort_index()
        r = le_export(usina)
        # 2. geometria do ano anterior
        idx_novo = pd.date_range(INI_NOVO, FIM, freq="h")
        cs_ant = u.poa_ceu_claro.reindex(idx_novo - pd.Timedelta(days=365))
        cs_novo = pd.Series(cs_ant.to_numpy(), index=idx_novo)
        sob = pd.date_range(*SOBRE, freq="h")
        cs_copia = pd.Series(u.poa_ceu_claro.reindex(sob - pd.Timedelta(days=365)).to_numpy(), index=sob)
        sol = u.poa_ceu_claro.reindex(sob) > 0
        erro_cs = float((cs_copia[sol] - u.poa_ceu_claro.reindex(sob)[sol]).abs().sum()
                        / u.poa_ceu_claro.reindex(sob)[sol].sum())
        # 1. convencao do carimbo pela sobreposicao
        melhor = None
        for desl in (0, -5, 5):
            rr = r.copy(); rr.index = rr.index + pd.Timedelta(minutes=desl)
            y = horaria(rr, u.poa_ceu_claro.reindex(sob))
            ok = sol & y.notna() & u.y_Wh.reindex(sob).notna() & u.y_valido.reindex(sob)
            iguais = float(((y[ok] - u.y_Wh.reindex(sob)[ok]).abs() < 0.5).mean()) if ok.any() else 0.0
            print(f"  {usina} deslocamento {desl:+d} min: {iguais:.4f} das {int(ok.sum())} horas de sol batem ao Wh")
            if melhor is None or iguais > melhor[1]:
                melhor = (desl, iguais, int(ok.sum()))
        desl, iguais, n = melhor
        rel[usina] = dict(deslocamento_carimbo_min=desl, fracao_horas_iguais_ao_Wh=round(iguais, 5), horas_comparadas=n,
                          erro_rel_poa_ceu_claro_copiado=round(erro_cs, 5))
        if iguais < 0.995:
            grava_json({"usinas": rel, "portao_wh": "FALHOU"})
            raise SystemExit(f"PORTAO C1: {usina} so {iguais:.4f} das horas batem ao Wh (< 0,995). Nada gravado.")
        rr = r.copy(); rr.index = rr.index + pd.Timedelta(minutes=desl)
        y = horaria(rr, cs_novo)
        d = pd.DataFrame(index=idx_novo)
        d["y_Wh"], d["poa_ceu_claro"] = y, cs_novo.fillna(0.0)
        d["y_valido"], d["kwp"], d["serie"] = d.y_Wh.notna(), KWP[usina], usina
        novos.append(d)
        rel[usina].update(horas_novas=len(d), fracao_valida_nova=round(float(d.y_valido.mean()), 4),
                          kwh_novo=round(float(d.y_Wh.sum()) / 1000, 1))
    # 3. NASA
    for i, usina in enumerate(PASTAS):
        lat, lon = SITIOS[usina]
        u = U[U.serie == usina].set_index("ds").sort_index()
        n = nasa_power.fetch_hourly(lat, lon, start="2025-12-01", end="2026-11-16", variables=("ghi", "temperature"),
                                    tz=FUSO, pause_s=2)
        n = n.set_index(n.ds.dt.tz_localize(None))[["ghi", "temperature"]].sort_index()
        sob = pd.date_range(*SOBRE, freq="h")
        escolha = None
        for h in (0, 1):
            g = n.ghi.shift(h).reindex(sob)
            ok = g.notna() & u.ghi_horario.reindex(sob).notna() & (u.poa_ceu_claro.reindex(sob) > 0)
            c = float(np.corrcoef(g[ok], u.ghi_horario.reindex(sob)[ok])[0, 1])
            dm = float((g[ok] - u.ghi_horario.reindex(sob)[ok]).abs().mean())
            print(f"  {usina} NASA atraso {h} h: correlacao {c:.4f}, |dif| media {dm:.1f} W/m2")
            if escolha is None or c > escolha[1]:
                escolha = (h, c, dm)
        h = escolha[0]
        d = novos[i]
        ghi = n.ghi.shift(h).reindex(d.index)
        tmp = n.temperature.shift(h).reindex(d.index)
        sol = d.poa_ceu_claro > 0
        cobertura = float(ghi[sol].notna().mean())
        kc = (ghi / ghi_ceu_claro(usina, d.index).where(lambda x: x > 20)).clip(0, 1.3)
        d["ghi_horario"] = ghi.where(sol, 0.0)
        d["poa_estimada"] = (d.poa_ceu_claro * kc).where(sol, 0.0)
        d["temp_ar_horaria"] = tmp.interpolate(limit_direction="both")
        # proxy da poa_estimada conferido na sobreposicao
        kc_s = (n.ghi.shift(h).reindex(sob) / ghi_ceu_claro(usina, sob).where(lambda x: x > 20)).clip(0, 1.3)
        prox = u.poa_ceu_claro.reindex(sob) * kc_s
        ok = prox.notna() & (u.poa_ceu_claro.reindex(sob) > 0)
        cor_poa = float(np.corrcoef(prox[ok], u.poa_estimada.reindex(sob)[ok])[0, 1])
        rel[usina].update(nasa_atraso_h=h, nasa_correlacao_ghi_sobreposicao=round(escolha[1], 4),
                          nasa_dif_media_wm2=round(escolha[2], 1), nasa_cobertura_horas_sol_novas=round(cobertura, 4),
                          correlacao_poa_estimada_proxy=round(cor_poa, 4))
        d["ghi_horario"] = d.ghi_horario.fillna(0.0).where(sol, 0.0)       # sem NASA: zero (so o regime B usa)
        d["poa_estimada"] = d.poa_estimada.fillna(0.0)
    N = pd.concat([d.rename_axis("ds").reset_index() for d in novos], ignore_index=True)
    V = pd.concat([U, N[U.columns]], ignore_index=True).sort_values(["serie", "ds"], kind="stable")
    V.to_parquet(DADOS / "usinas_horario_v1.parquet", index=False)
    print(f"gravado usinas_horario_v1.parquet: {len(V)} linhas")
    grava_json({"usinas": rel, "portao_wh": "PASSOU"})


def baixa_lead1(modelos, arq_pub, arq_v1):
    if (DADOS / arq_v1).exists():
        print("ja existe", arq_v1)
        return
    import ssl
    import urllib.parse
    import urllib.request
    try:
        import truststore
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        ctx = ssl.create_default_context()
    tabs = []
    for serie, (lat, lon) in SITIOS.items():
        for nwp in modelos:
            q = dict(latitude=lat, longitude=lon, models=nwp, start_date="2024-01-01", end_date=FIM.date().isoformat(),
                     hourly="shortwave_radiation_previous_day1,temperature_2m_previous_day1", timezone="America/Sao_Paulo")
            for k in range(6):
                try:
                    with urllib.request.urlopen(URL_PREV + "?" + urllib.parse.urlencode(q), timeout=300, context=ctx) as r:
                        h = json.load(r)["hourly"]
                    break
                except Exception as e:  # 429/rede: espera e tenta de novo
                    print("   tentativa", k, e); time.sleep(70)
            else:
                raise RuntimeError(f"{serie} {nwp}: sem resposta")
            t = pd.DataFrame(dict(ds=pd.to_datetime(h["time"]), ghi_prev=h["shortwave_radiation_previous_day1"],
                                  temp_prev=h["temperature_2m_previous_day1"]))
            t["serie"], t["modelo_nwp"] = serie, nwp
            tabs.append(t)
            time.sleep(3)
    T = pd.concat(tabs, ignore_index=True)
    P = pd.read_parquet(DADOS / arq_pub)
    m = P.merge(T, on=["serie", "modelo_nwp", "ds"], suffixes=("_pub", "_novo"))
    dif = (m.ghi_prev_pub - m.ghi_prev_novo).abs()
    ok = T[T.ds > "2026-05-31"].dropna(subset=["ghi_prev"])
    grava_json({arq_v1: dict(dif_max_ghi_sobreposicao=float(dif.max()), fracao_igual=float((dif < 0.5).mean()),
                             horas_novas_com_valor=int(len(ok)), ultimo=str(T.dropna(subset=["ghi_prev"]).ds.max()))})
    T.to_parquet(DADOS / arq_v1, index=False)
    print(f"gravado {arq_v1}: dif max na sobreposicao {dif.max():.2f}")


def baixa_horizonte():
    arq = DADOS / "previsao_tempo_horizonte_v1.parquet"
    if arq.exists():
        print("ja existe", arq.name)
        return
    pasta = DADOS / "_cache" / "horizonte_v1"
    pasta.mkdir(parents=True, exist_ok=True)
    for serie, (lat, lon) in SITIOS.items():
        for m in om.DEFAULT_MODELS:
            for k in range(1, 8):
                f = pasta / f"{serie}__{m}__{k}.parquet"
                if f.exists():
                    continue
                for t in range(6):
                    try:
                        df = om.fetch_previous_runs(lat, lon, start="2024-03-01", end=FIM.date().isoformat(), models=[m],
                                                    variables=("ghi",), lead_days=k, tz=FUSO, pause_s=0)
                        break
                    except Exception as e:
                        print("   tentativa", t, e); time.sleep(70)
                else:
                    raise RuntimeError(f"{serie} {m} lead {k}: sem resposta")
                pd.DataFrame(dict(serie=serie, modelo_nwp=m, lead=k, ds=df.ds.dt.tz_localize(None),
                                  ghi=df.ghi.astype("float32"))).to_parquet(f, index=False)
                time.sleep(3)
    P = pd.concat([pd.read_parquet(f) for f in sorted(pasta.glob("*.parquet"))], ignore_index=True)
    P["lead"] = P["lead"].astype("int8")
    Q = pd.read_parquet(DADOS / "previsao_tempo_horizonte.parquet")
    m = Q.merge(P, on=["serie", "modelo_nwp", "lead", "ds"], suffixes=("_pub", "_novo"))
    dif = (m.ghi_pub - m.ghi_novo).abs()
    grava_json({arq.name: dict(dif_max_ghi_sobreposicao=float(dif.max()), fracao_igual=float((dif < 0.5).mean()),
                               ultimo=str(P.dropna(subset=["ghi"]).ds.max()))})
    P.sort_values(["serie", "modelo_nwp", "lead", "ds"]).to_parquet(arq, index=False)
    print(f"gravado {arq.name}: {len(P)} linhas; dif max na sobreposicao {dif.max():.2f}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if "--so-tempo" not in a:
        usinas()
    if "--so-usinas" not in a:
        baixa_lead1(["ecmwf_ifs025", "gfs_seamless"], "previsao_tempo.parquet", "previsao_tempo_v1.parquet")
        baixa_lead1(["icon_seamless", "meteofrance_seamless", "gem_seamless", "cma_grapes_global",
                     "ecmwf_aifs025_single", "ukmo_seamless"], "previsao_tempo_extra.parquet",
                    "previsao_tempo_extra_v1.parquet")
        baixa_horizonte()
