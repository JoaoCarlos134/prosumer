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
import sys
from pathlib import Path
import numpy as np, pandas as pd

# O protocolo (dobras, dias de teste, janelas) vem da BIBLIOTECA desde 11/10/2026 (etapa E2/E3 do plano): um
# protocolo so, o mesmo que o usuario da biblioteca recebe. Os ambientes congelados do benchmark nao tem a
# biblioteca instalada nem o pandera: o src/ entra no caminho e a serie e montada sem validacao (o construtor de
# EnergySeries nao revalida). tests/test_benchmark_protocol.py confere, no ambiente da biblioteca, que o resultado e
# IDENTICO ao da implementacao v2 que gerou todas as previsoes publicadas (copiada la, congelada).
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
from prosumer.contracts import EnergySeries  # noqa: E402
from prosumer.physics import clear_sky_ghi  # noqa: E402
from prosumer.protocol import DayAhead, folds, standardize_by_training  # noqa: E402

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


# Fuso dos dados: os parquets tem relogio local SEM fuso, numa grade sem buraco. A biblioteca exige fuso, entao a
# grade recebe um fuso FIXO que a preserva hora a hora: usinas UTC-3 (o mesmo que o ghi_ceu_claro assume; o Brasil
# nao tem horario de verao desde 2019) e casas UTC+0 (a grade das casas ja e a de Dublin com as duas horas de troca
# de horario preenchidas pelo conjunto, ver 09_clima_casas.py; um fuso com horario de verao a quebraria).
FUSO = {"usinas": "Etc/GMT+3", "casas_prod": "Etc/GMT", "casas_cons": "Etc/GMT"}


def dobras(caso):
    """[(inicio, fim)] das dobras de teste; o modelo treinado e refeito no inicio de cada uma."""
    return [(f.start, f.end) for f in folds(CASOS[caso]["ini"], CASOS[caso]["fim"], REFIT_DIAS[caso])]


def tarefa(d, caso, contexto=CONTEXTO_FM, exog=False):
    """O DayAhead da biblioteca para este caso (serie longa de carrega(); exogenas como covariaveis se exog)."""
    fuso = FUSO[caso]
    d = d.reset_index(drop=True)
    x = pd.DataFrame({"unique_id": d.unique_id.astype(str), "ds": pd.to_datetime(d.ds).dt.tz_localize(fuso),
                      "y": d.y.astype(float)})
    x["valid"] = x.y.notna()
    cov = None
    if exog:
        cov = pd.concat([x[["unique_id", "ds"]], d[EXOG]], axis=1)
    serie = EnergySeries(frame=x.sort_values(["unique_id", "ds"], kind="stable").reset_index(drop=True), unit="kWh",
                         quantity="consumption" if caso == "casas_cons" else "generation", tz=fuso, freq="h")
    return DayAhead(serie, test_start=CASOS[caso]["ini"], test_end=CASOS[caso]["fim"], refit_days=REFIT_DIAS[caso],
                    context=contexto, covariates=cov, min_history=0)


def ghi_ceu_claro(serie, idx):
    """GHI de ceu claro (Haurwitz, a mesma do projeto), media de cada hora a partir de 5 min, hora local UTC-3.
    Biblioteca: `prosumer.physics.clear_sky_ghi` (identica bit a bit; tests/test_benchmark_protocol.py)."""
    lat, lon = SITIOS[serie]
    idx = pd.DatetimeIndex(idx)
    return pd.Series(clear_sky_ghi(idx.tz_localize(FUSO["usinas"]), lat, lon), index=idx)


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
    return [(u, dia.tz_localize(None)) for u, dia in tarefa(d, caso).test_days()]


def janelas(d, caso, contexto=CONTEXTO_FM, exog=False):
    """Uma janela por dia de teste: historico (interpolado nos buracos, so com o proprio historico) e, se pedido,
    exogenas passadas e futuras. Formato de sempre (dicionarios, float32, datas sem fuso)."""
    out = []
    for w in tarefa(d, caso, contexto, exog).windows():
        j = dict(unique_id=w.unique_id, dia=w.day.tz_localize(None),
                 ds_fut=pd.date_range(w.day.tz_localize(None), periods=H, freq="h"),
                 y=w.history.astype(np.float32))
        if exog:
            j["x_pass"] = {c: np.asarray(w.past_covariates[c], dtype=np.float32) for c in EXOG}
            j["x_fut"] = {c: np.asarray(w.future_covariates[c], dtype=np.float32) for c in EXOG}
        out.append(j)
    return out


def normaliza_por_treino(df, corte, colunas):
    """Padroniza por serie usando apenas alvos validos anteriores ao corte (biblioteca:
    `protocol.standardize_by_training`; o NeuralForecast marca buracos em `available_mask`).

    O corte deve excluir validacao e teste. Retorna os parametros para inverter
    a previsao; alterar qualquer valor posterior ao corte nao altera a escala.
    """
    try:
        return standardize_by_training(df, corte, colunas, mask_column="available_mask")
    except ValueError as e:
        raise ValueError(str(e).replace("Empty or non-finite training rows for standardization",
                                        "Treino vazio ou nao finito para normalizacao")) from e


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
