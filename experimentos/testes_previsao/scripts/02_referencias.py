# -*- coding: utf-8 -*-
"""Referencias ingenuas, fisica linear e LightGBM global.

  persist_24h        o mesmo horario de ontem
  semanal_168h       o mesmo horario de 7 dias atras
  media_7d           media do mesmo horario nos ultimos 7 dias
  persist_ceu_claro  (usinas) indice de ceu claro de ontem x ceu claro de hoje; so geometria
  linear_fisico      (usinas e FV das casas, B) energia = a + b * poa_estimada, ajustado no treino
                     (nas casas e o plano horizontal: GHI medido; ver comum.py)
  LightGBM           global; A: defasagens + calendario; B: + ceu claro e clima do dia (usinas: NASA;
                     casas: estacao de Dingle);
                     C: + ceu claro e previsao real da vespera
LightGBM e linear fisico sao retreinados no inicio de cada dobra (origem movel, comum.dobras).
Nas usinas rodam tambem os diagnosticos B-curto e C-gfs (ver comum.py).
"""
import sys
import numpy as np, pandas as pd, lightgbm as lgb
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.neighbors import KNeighborsRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from comum import carrega, dias_teste, dobras, grava, CASOS, EXOG, H, REGIMES, DIAGNOSTICOS


def matriz(g, col):
    """dia x hora (24 colunas)."""
    m = g.assign(dia=g.ds.dt.normalize(), h=g.ds.dt.hour).pivot_table(index="dia", columns="h", values=col, dropna=False)
    m = m.reindex(columns=range(24))
    return m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="D"))


def tabela_features(d, caso):
    """Uma linha por (serie, dia, hora) com tudo o que se sabe as 00:00 do dia."""
    blocos = []
    for k, (uid, g) in enumerate(d.groupby("unique_id", sort=False)):
        Y = matriz(g, "y")
        f = {}
        for lag in (1, 2, 7):
            f[f"y_d{lag}"] = Y.shift(lag)
        f["y_media7"] = sum(Y.shift(i) for i in range(1, 8)) / 7
        tot = Y.sum(axis=1, min_count=20)
        f["tot_d1"] = pd.DataFrame(np.repeat(tot.shift(1).to_numpy()[:, None], 24, 1), index=Y.index, columns=Y.columns)
        f["tot_media7"] = pd.DataFrame(np.repeat(tot.shift(1).rolling(7, min_periods=5).mean().to_numpy()[:, None], 24, 1),
                                       index=Y.index, columns=Y.columns)
        if "poa_ceu_claro" in g.columns:          # usinas (todo regime) e casas no regime B
            X = {c: matriz(g, c) for c in EXOG}
            cs = X["poa_ceu_claro"]
            k_ontem = (tot.shift(1) / cs.sum(axis=1).shift(1)).replace([np.inf, -np.inf], np.nan)
            f["persist_ceu_claro"] = cs.mul(k_ontem, axis=0)
            for c in EXOG:
                f[c] = X[c]
        longo = pd.concat({n: m.stack(future_stack=True) for n, m in f.items()}, axis=1)
        longo["y"] = Y.stack(future_stack=True)
        longo.index.names = ["dia", "h"]
        longo = longo.reset_index()
        longo["unique_id"], longo["serie_cod"] = uid, k
        blocos.append(longo)
    t = pd.concat(blocos, ignore_index=True)
    t["ds"] = t.dia + pd.to_timedelta(t.h, unit="h")
    t["dow"] = t.dia.dt.dayofweek
    t["doy_sin"], t["doy_cos"] = np.sin(2 * np.pi * t.dia.dt.dayofyear / 365.25), np.cos(2 * np.pi * t.dia.dt.dayofyear / 365.25)
    return t


def linear_fisico(treino, tt):
    """energia = a + b * poa_estimada, por usina, so horas de sol."""
    out = pd.Series(np.nan, index=tt.index)
    for uid, g in treino.groupby("unique_id"):
        sol = g[g.poa_ceu_claro > 0]
        coef = np.linalg.lstsq(np.c_[np.ones(len(sol)), sol.poa_estimada], sol.y.to_numpy(), rcond=None)[0]
        m = tt.unique_id == uid
        out[m] = np.where(tt.loc[m, "poa_ceu_claro"] > 0, coef[0] + coef[1] * tt.loc[m, "poa_estimada"], 0.0)
    return out


def lgbm(treino, tt, cols):
    m = lgb.LGBMRegressor(n_estimators=600, learning_rate=0.03, num_leaves=63, min_child_samples=40,
                          subsample=0.8, subsample_freq=1, colsample_bytree=0.8, random_state=42, verbose=-1)
    m.fit(treino[cols], treino.y, categorical_feature=["serie_cod"])
    return m.predict(tt[cols])


# Classicos de aprendizado de maquina (passo T, 07/10/2026), com os MESMOS atributos do LightGBM.
# Duas diferencas obrigatorias em relacao a ele: o LightGBM aceita NaN e nao precisa de escala; estes
# precisam dos dois, entao cada um vai num pipeline com imputacao pela mediana (os atributos de
# defasagem sao NaN no inicio da serie) e, menos a floresta, padronizacao.
# `serie_cod` e uma CATEGORIA (qual usina/casa), nao um numero: o LightGBM a recebe como categorica. Nos
# modelos que usam distancia ou combinacao linear (Ridge, MLP, kNN) ela vai em one-hot; antes de 09/10/2026
# entrava como numero, o que punha a casa 3 "entre" a 2 e a 4 e entrava na distancia do kNN. A floresta
# separa os codigos por cortes e fica como estava.
def classicos():
    imp = lambda: SimpleImputer(strategy="median")

    def com_serie(modelo):
        prep = ColumnTransformer([("serie", OneHotEncoder(handle_unknown="ignore", sparse_output=False), ["serie_cod"])],
                                 remainder=make_pipeline(imp(), StandardScaler()))
        return make_pipeline(prep, modelo)

    return {
        "Ridge": lambda: com_serie(Ridge(alpha=1.0)),
        "RandomForest": lambda: make_pipeline(
            imp(), RandomForestRegressor(n_estimators=300, min_samples_leaf=5, n_jobs=-1, random_state=42)),
        "MLP": lambda: com_serie(
            MLPRegressor(hidden_layer_sizes=(64, 32), max_iter=600, early_stopping=True, random_state=42)),
        "kNN": lambda: com_serie(KNeighborsRegressor(n_neighbors=25, weights="distance")),
    }


def roda(caso, so_regimes=None, so_modelos=None):
    cal = ["h", "dow", "doy_sin", "doy_cos", "serie_cod"]
    lags = ["y_d1", "y_d2", "y_d7", "y_media7", "tot_d1", "tot_media7"]
    regimes = REGIMES[caso] + (DIAGNOSTICOS if caso == "usinas" else [])
    regimes = [r for r in regimes if so_regimes is None or r in so_regimes]
    # linear fisico = energia ~ irradiancia: so faz sentido para geracao, nao para o consumo
    com_linear = caso != "casas_cons"
    for regime in regimes:
        d = carrega(caso, regime)
        t = tabela_features(d, caso)
        teste = pd.DataFrame(dias_teste(d, caso), columns=["unique_id", "dia"])
        tt = teste.merge(t, on=["unique_id", "dia"], how="left").sort_values(["unique_id", "dia", "h"]).reset_index(drop=True)
        teste = tt[["unique_id", "dia"]].drop_duplicates().reset_index(drop=True)
        jan = [dict(unique_id=u, ds_fut=pd.date_range(dia, periods=H, freq="h")) for u, dia in teste.itertuples(index=False)]

        def salva(nome, col):
            grava(nome, caso, regime, jan, tt[col].to_numpy().reshape(-1, H))

        # --modelos: refaz so esses classicos, sem tocar nas referencias, no LightGBM e no linear fisico
        so_classicos = so_modelos is not None
        if regime == "A" and not so_classicos:     # referencias: nao treinam, uma vez so
            salva("persist_24h", "y_d1"); salva("semanal_168h", "y_d7"); salva("media_7d", "y_media7")
            if caso == "usinas":
                salva("persist_ceu_claro", "persist_ceu_claro")
        cols = cal + lags + (["persist_ceu_claro"] + EXOG if regime != "A" else [])
        cls = {k: f for k, f in classicos().items() if not so_classicos or k in so_modelos}
        tt["lgb"], tt["linear_fisico"] = np.nan, np.nan
        for nome in cls:
            tt[nome] = np.nan
        for ini, fim in dobras(caso):
            treino = t[(t.dia < ini) & t.y.notna()]
            m = (tt.dia >= ini) & (tt.dia <= fim)
            if not so_classicos:
                tt.loc[m, "lgb"] = lgbm(treino, tt[m], cols)
            for nome, fab in cls.items():
                mod = fab()
                mod.fit(treino[cols], treino.y)
                tt.loc[m, nome] = mod.predict(tt.loc[m, cols])
            if regime != "A" and com_linear and not so_classicos:
                tt.loc[m, "linear_fisico"] = linear_fisico(treino, tt[m])[m[m].index]
        if not so_classicos:
            salva("LightGBM", "lgb")
        for nome in cls:
            salva(nome, nome)
        if regime != "A" and com_linear and not so_classicos:
            salva("linear_fisico", "linear_fisico")
        print("%-10s %-7s %4d dias de teste, %d dobras, treino desde %s" % (caso, regime, len(teste), len(dobras(caso)), t.dia.min().date()), flush=True)


if __name__ == "__main__":
    # Uso: python 02_referencias.py [caso ...] [--regimes A,B] [--modelos Ridge,MLP,kNN]
    # Sem argumentos: tudo, como na v2. Com --modelos: so esses classicos (o resto nao e refeito).
    args = sys.argv[1:]
    so_regimes = args[args.index("--regimes") + 1].split(",") if "--regimes" in args else None
    so_modelos = args[args.index("--modelos") + 1].split(",") if "--modelos" in args else None
    for caso in [a for a in args if a in CASOS] or list(CASOS):
        roda(caso, so_regimes, so_modelos)
