# -*- coding: utf-8 -*-
"""Protocolo unico dos testes: dados, janelas de previsao e gravacao.

Tarefa: previsao do dia seguinte, 24 valores horarios emitidos as 00:00, com historico
ate 23:00 da vespera. Uma janela por dia de teste.

Casos
  usinas     Cascavel e Curitiba, kWh/h. Teste 01/08/2025 -> 31/05/2026 (fim da NASA horaria).
  casas_prod producao FV das 10 casas que tem FV (as outras 10 nao geram), kWh/h. Teste 01/10/2020 -> 31/12/2020.
  casas_cons consumo das 20 casas, kWh/h. Mesmo teste.

Regimes
  A  so o historico da propria serie (+ calendario)
  B  (so usinas) + ceu claro (geometria) + clima NASA do proprio dia: previsao do tempo PERFEITA.
     E um teto, nao uma previsao operacional.
  C  (so usinas) + ceu claro + previsao do tempo REAL emitida na vespera (ECMWF IFS 0,25 grau,
     Open-Meteo Previous Runs, *_previous_day1), no treino e no teste. O arquivo de previsoes comeca
     em 06/03/2024, entao o treino de C comeca em INICIO_C. E o regime operacional.
     Horario: o valor rotulado h+1 da Open-Meteo e a media da hora anterior, logo cobre a hora h dos
     dados (confirmado pela correlacao com a geracao). Nas horas 21-23 a rodada usada pode ter saido
     poucas horas depois das 00:00; sao horas de noite, sem efeito na avaliacao (so horas de sol).
  Diagnosticos (so LightGBM e linear fisico): B-curto = B com o treino cortado em INICIO_C (separa o
  efeito da previsao do efeito do treino mais curto); C-gfs = C com o GFS no lugar do ECMWF.
  B nas casas (07/10/2026): clima MEDIDO na estacao de Dingle (dados/clima_casas_horario.parquet, de
  09_clima_casas.py), ja na hora local das casas. Usa os mesmos nomes de EXOG das usinas para o resto do
  pipeline nao mudar: como a orientacao dos paineis nao e publicada, nao ha POA, e os nomes 'poa_*' recebem
  o plano HORIZONTAL (poa_ceu_claro = GHI de ceu claro; poa_estimada = GHI medido). Nao existe C nas casas:
  as previsoes arquivadas da Open-Meteo so comecam em 2024.

Origem movel (protocolo v2, 05/10/2026)
  Todo modelo treinado e retreinado no inicio de cada dobra, so com dados anteriores a ela:
  usinas a cada 61 dias (5 dobras), casas a cada 31 dias (3 dobras). Fundacionais nao treinam e ja
  usam todo o historico ate a vespera. Mesmos lotes em todas as redes (COMUM em 04_redes_treinadas.py).
"""
import os
from pathlib import Path
import numpy as np, pandas as pd

# CPU por padrao (como foi rodado no Lactec). DISPOSITIVO=cuda leva as redes treinadas para a GPU; os lotes e o
# resto do protocolo nao mudam, mas os numeros podem variar um pouco: o dispositivo fica anotado nos tempos.
DISPOSITIVO = os.environ.get("DISPOSITIVO", "cpu")

RAIZ = Path(__file__).resolve().parents[1]
DADOS, RES = RAIZ / "dados", RAIZ / "resultados"
PREV = RES / "previsoes"
PREV.mkdir(parents=True, exist_ok=True)
H = 24
CONTEXTO_FM = 1024          # horas de historico dadas aos modelos fundacionais
ENTRADA_NN = 168            # horas de historico das redes treinadas (7 dias)
EXOG = ["poa_ceu_claro", "ghi_horario", "poa_estimada", "temp_ar_horaria"]
REFIT_DIAS = {"usinas": 61, "casas_prod": 31, "casas_cons": 31}
INICIO_C = pd.Timestamp("2024-03-07")       # primeiro dia completo com previsao arquivada
REGIMES = {"usinas": ["A", "B", "C"], "casas_prod": ["A", "B"], "casas_cons": ["A", "B"]}
DIAGNOSTICOS = ["B-curto", "C-gfs"]
NWP = {"C": "ecmwf_ifs025", "C-gfs": "gfs_seamless"}
SITIOS = {"Cascavel": (-24.83, -53.65), "Curitiba": (-25.4284, -49.2733)}
CASOS = {
    "usinas": dict(ini="2025-08-01", fim="2026-05-31 23:00"),
    "casas_prod": dict(ini="2020-10-01", fim="2020-12-31 23:00"),
    "casas_cons": dict(ini="2020-10-01", fim="2020-12-31 23:00"),
}


def dobras(caso):
    """[(inicio, fim)] das dobras de teste; o modelo treinado e refeito no inicio de cada uma."""
    ini, fim = pd.Timestamp(CASOS[caso]["ini"]), pd.Timestamp(CASOS[caso]["fim"]).normalize()
    out, a = [], ini
    while a <= fim:
        b = min(a + pd.Timedelta(days=REFIT_DIAS[caso] - 1), fim)
        out.append((a, b + pd.Timedelta("23h"))); a = b + pd.Timedelta(days=1)
    return out


def ghi_ceu_claro(serie, idx):
    """GHI de ceu claro (Haurwitz, a mesma do projeto), media de cada hora a partir de 5 min, hora local UTC-3."""
    lat, lon = SITIOS[serie]
    t = pd.date_range(idx.min(), idx.max() + pd.Timedelta("55min"), freq="5min") + pd.Timedelta("150s")
    n = t.dayofyear.to_numpy(); g = 2 * np.pi / 365 * (n - 1 + (t.hour.to_numpy() - 12) / 24)
    eot = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g) - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    dec = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g) + 0.000907 * np.sin(2 * g)
           - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    min_solar = (t.hour.to_numpy() + 3) * 60 + t.minute.to_numpy() + t.second.to_numpy() / 60 + eot + 4 * lon
    w = np.radians(min_solar / 4 - 180)
    cz = np.sin(np.radians(lat)) * np.sin(dec) + np.cos(np.radians(lat)) * np.cos(dec) * np.cos(w)
    czp = np.clip(cz, 1e-3, None)
    cs = np.where(cz > 0, 1098.0 * czp * np.exp(-0.059 / czp), 0.0)
    return pd.Series(cs, index=t - pd.Timedelta("150s")).resample("h").mean().reindex(idx).fillna(0.0)


def exog_previsao(d, regime):
    """Troca o clima NASA pela previsao real da vespera (regime C / C-gfs). Ceu claro (geometria) fica."""
    P = pd.read_parquet(DADOS / "previsao_tempo.parquet")
    P = P[P.modelo_nwp == NWP[regime]]
    partes = []
    for uid, g in d.groupby("unique_id", sort=False):
        p = P[P.serie == uid].set_index("ds").sort_index()
        g = g.set_index("ds").copy()
        ghi = p.ghi_prev.shift(-1).reindex(g.index)                       # rotulo h+1 -> hora h
        tmp = ((p.temp_prev + p.temp_prev.shift(-1)) / 2).reindex(g.index)
        kc = (ghi / ghi_ceu_claro(uid, g.index).where(lambda x: x > 20)).clip(0, 1.3).fillna(0.0)
        g["ghi_horario"] = ghi.where(g.poa_ceu_claro > 0, 0.0)
        g["poa_estimada"] = (g.poa_ceu_claro * kc).where(g.poa_ceu_claro > 0, 0.0)
        g["temp_ar_horaria"] = tmp.interpolate(limit_direction="both")
        partes.append(g.reset_index())
    return pd.concat(partes, ignore_index=True)


def carrega(caso, regime="A"):
    """DataFrame longo: unique_id, ds, y (kWh/h, NaN onde invalido) e, nas usinas, as exogenas.
    Regimes C, C-gfs e B-curto (usinas) comecam em INICIO_C; C e C-gfs trocam o clima pela previsao."""
    if caso == "usinas":
        u = pd.read_parquet(DADOS / "usinas_horario.parquet")
        d = u.rename(columns={"serie": "unique_id"})
        d["y"] = d.y_Wh / 1000.0
        d = d[["unique_id", "ds", "y"] + EXOG]
    else:
        c = pd.read_parquet(DADOS / "casas_horario.parquet")
        col = "prod_kWh" if caso == "casas_prod" else "cons_kWh"
        d = c.rename(columns={"casa": "unique_id", col: "y"})[["unique_id", "ds", "y"]]
        if caso == "casas_prod":
            # 10 das 20 casas nao tem FV (producao zero o ano todo): ficam so as que geram
            com_fv = d.groupby("unique_id").y.sum()
            d = d[d.unique_id.isin(com_fv[com_fv > 0].index)]
        if regime == "B":
            d = d.merge(clima_casas(), on="ds", how="left")
    d = d[d.ds <= CASOS[caso]["fim"]]
    if caso == "usinas" and regime in ("C", "C-gfs", "B-curto"):
        d = d[d.ds >= INICIO_C]
        if regime != "B-curto":
            d = exog_previsao(d, regime)
    d["_o"] = d.unique_id.str.extract(r"H(\d+)", expand=False).astype(float).fillna(0)
    d = d.sort_values(["_o", "unique_id", "ds"]).drop(columns="_o")
    return d.reset_index(drop=True)


def clima_casas():
    """Clima medido das casas com os nomes de EXOG das usinas (plano horizontal; ver o cabecalho)."""
    c = pd.read_parquet(DADOS / "clima_casas_horario.parquet")
    sol = c.ghi_ceu_claro > 0
    return pd.DataFrame({"ds": c.ds, "poa_ceu_claro": c.ghi_ceu_claro,
                         "ghi_horario": c.ghi_horario.where(sol, 0.0), "poa_estimada": c.ghi_horario.where(sol, 0.0),
                         "temp_ar_horaria": c.temp_ar_horaria})


def dias_teste(d, caso):
    """(unique_id, dia) com as 24 horas validas dentro do periodo de teste."""
    t = d[(d.ds >= CASOS[caso]["ini"]) & (d.ds <= CASOS[caso]["fim"])].copy()
    t["dia"] = t.ds.dt.normalize()
    ok = t.groupby(["unique_id", "dia"]).y.agg(lambda s: s.notna().sum() == H and len(s) == H)
    return [k for k, v in ok.items() if v]


def janelas(d, caso, contexto=CONTEXTO_FM, exog=False):
    """Uma janela por dia de teste: historico (interpolado nos buracos) e, se pedido, exogenas passadas e futuras."""
    out = []
    series = {u: g.set_index("ds") for u, g in d.groupby("unique_id")}
    for uid, dia in dias_teste(d, caso):
        g = series[uid]
        hist = g.loc[:dia - pd.Timedelta("1h")].tail(contexto)
        w = dict(unique_id=uid, dia=dia, ds_fut=pd.date_range(dia, periods=H, freq="h"),
                 y=hist.y.interpolate(limit_direction="both").fillna(0.0).to_numpy(np.float32))
        if exog:
            fut = g.loc[dia:dia + pd.Timedelta("23h")]
            w["x_pass"] = {c: hist[c].to_numpy(np.float32) for c in EXOG}
            w["x_fut"] = {c: fut[c].to_numpy(np.float32) for c in EXOG}
        out.append(w)
    return out


def normaliza_por_treino(df, corte, colunas):
    """Padroniza por serie usando apenas alvos validos anteriores ao corte.

    O corte deve excluir validacao e teste. Retorna os parametros para inverter
    a previsao; alterar qualquer valor posterior ao corte nao altera a escala.
    """
    out, parametros = df.copy(), {}
    for uid, g in df.groupby("unique_id", sort=False):
        valido = g.ds < corte
        if "available_mask" in g:
            valido &= g.available_mask > 0
        treino = g.loc[valido, colunas]
        if treino.empty or not np.isfinite(treino.to_numpy(float)).all():
            raise ValueError(f"Treino vazio ou nao finito para normalizacao: {uid}")
        media = treino.mean()
        desvio = treino.std(ddof=0).replace(0, 1.0)
        out.loc[g.index, colunas] = (g[colunas] - media) / desvio
        parametros[uid] = {c: (float(media[c]), float(desvio[c])) for c in colunas}
    return out, parametros


def grava(modelo, caso, regime, janelas_, previsoes, extra=None):
    """previsoes: array (n_janelas, 24). Grava formato longo em resultados/previsoes/."""
    linhas = []
    for w, p in zip(janelas_, previsoes):
        linhas.append(pd.DataFrame(dict(unique_id=w["unique_id"], ds=w["ds_fut"], yhat=np.asarray(p, float)[:H])))
    df = pd.concat(linhas, ignore_index=True)
    df["modelo"], df["caso"], df["regime"] = modelo, caso, regime
    if extra:
        for k, v in extra.items():
            df[k] = v
    nome = f"{modelo}__{caso}__{regime}.parquet".replace(" ", "_").replace("/", "-")
    df.to_parquet(PREV / nome, index=False)
    return PREV / nome


def grava_tempos(log, tempos):
    """Junta `tempos` ao que ja esta no arquivo e grava. Dois processos podem escrever no mesmo log (o 03 e o
    03b dividem o tempos_fundacionais.json): gravar so o que este processo leu no inicio apagava as entradas
    do outro (armadilha de 08/10/2026)."""
    import json
    atual = json.loads(log.read_text()) if log.exists() else {}
    atual.update(tempos)
    log.write_text(json.dumps(atual, indent=1))
