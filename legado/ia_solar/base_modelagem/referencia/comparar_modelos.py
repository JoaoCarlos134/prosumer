# -*- coding: utf-8 -*-
###############################################################################
# COMPARACAO DOS MODELOS DE REGRESSAO - as duas usinas
#
# Mesma familia de algoritmos testada no Projeto_solo, na versao de REGRESSAO:
#   Dummy, LinearRegression, DecisionTree, KNN, SVR, AdaBoost, Bagging,
#   RandomForest, ExtraTrees, GradientBoosting, HistGradientBoosting, XGBoost, MLP
# (GaussianNB e o clustering nao tem equivalente em regressao e ficaram de fora.)
#
# SEM AJUSTE DE HIPERPARAMETROS. Todos com os valores padrao da biblioteca;
# so foi fixado random_state=42 (e n_jobs, que nao muda o resultado, so o tempo).
###############################################################################
import pandas as pd, numpy as np, time, sys, json, warnings
from pathlib import Path
BASE = Path(__file__).resolve().parents[1]            # base_modelagem/
AMBAS = BASE / "ambas_usinas"
warnings.filterwarnings("ignore")
from sklearn.dummy import DummyRegressor
from sklearn.linear_model import LinearRegression
from sklearn.tree import DecisionTreeRegressor
from sklearn.neighbors import KNeighborsRegressor
from sklearn.svm import SVR
from sklearn.ensemble import (AdaBoostRegressor, BaggingRegressor, RandomForestRegressor,
                              ExtraTreesRegressor, GradientBoostingRegressor,
                              HistGradientBoostingRegressor)
from sklearn.neural_network import MLPRegressor
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from xgboost import XGBRegressor

SEED = 42
CORTE = pd.Timestamp("2025-08-01")
N_SVR = 20000          # SVR e O(n^2): roda numa amostra e fica marcado como tal

GEO = ['hora_solar','dia_do_ano','elevacao_solar','cos_zenite','poa_ceu_claro']
DAY = ['kt_diario','ghi_diario','temp_ar_diaria','umidade_diaria','vento_diario',
       'chuva_diaria','nuvens_diaria','aerossol_diario']
VARS = GEO + DAY + ['estado_sujeira']
ALVO = 'potencia_ca_W'

def imp(m):   return make_pipeline(SimpleImputer(strategy='median'), m)
def imp_sc(m): return make_pipeline(SimpleImputer(strategy='median'), StandardScaler(), m)

def modelos():
    return {
      'Dummy (media)'        : (DummyRegressor(strategy='mean'), False),
      'Regressao Linear'     : (imp_sc(LinearRegression()), False),
      'Arvore de Decisao'    : (imp(DecisionTreeRegressor(random_state=SEED)), False),
      'KNN'                  : (imp_sc(KNeighborsRegressor(n_jobs=-1)), False),
      'SVR'                  : (imp_sc(SVR()), True),
      'AdaBoost'             : (imp(AdaBoostRegressor(random_state=SEED)), False),
      'Bagging'              : (imp(BaggingRegressor(random_state=SEED, n_jobs=-1)), False),
      'Random Forest'        : (imp(RandomForestRegressor(random_state=SEED, n_jobs=-1)), False),
      'Extra Trees'          : (imp(ExtraTreesRegressor(random_state=SEED, n_jobs=-1)), False),
      'Gradient Boosting'    : (imp(GradientBoostingRegressor(random_state=SEED)), False),
      'HistGradientBoosting' : (HistGradientBoostingRegressor(random_state=SEED), False),
      'XGBoost'              : (XGBRegressor(random_state=SEED, n_jobs=-1), False),
      'Rede Neural MLP'      : (imp_sc(MLPRegressor(random_state=SEED)), False),
    }

linhas = []
for usina, arq in [("Cascavel", BASE / "cascavel" / "base_Cascavel_5min.parquet"),
                   ("Curitiba", BASE / "curitiba" / "base_Curitiba_5min.parquet")]:
    d = pd.read_parquet(arq).sort_values("data_hora")
    tr, te = d[d.data_hora < CORTE], d[d.data_hora >= CORTE]
    Xtr, ytr = tr[VARS], tr[ALVO]
    Xte, yte = te[VARS], te[ALVO]
    nom = d.pot_nominal_kWp.median()*1000
    print("\n" + "="*84)
    print("%s | treino %d | teste %d | nominal %.2f kWp" % (usina, len(tr), len(te), nom/1000))
    print("="*84)
    print("%-22s %8s %9s %10s %8s %9s" % ("MODELO","R2","MAE (W)","RMSE (W)","MAE %","seg"))
    print("-"*84)
    for nome, (mod, amostra) in modelos().items():
        t0 = time.time()
        try:
            if amostra:
                idx = np.random.default_rng(SEED).choice(len(Xtr), min(N_SVR,len(Xtr)), replace=False)
                mod.fit(Xtr.iloc[idx], ytr.iloc[idx])
            else:
                mod.fit(Xtr, ytr)
            p = np.clip(mod.predict(Xte), 0, None)
            r2  = r2_score(yte, p); mae = mean_absolute_error(yte, p)
            rmse = float(np.sqrt(mean_squared_error(yte, p)))
            dt = time.time()-t0
            tag = " (amostra %d)" % N_SVR if amostra else ""
            print("%-22s %8.4f %9.1f %10.1f %7.2f%% %9.1f%s" % (nome,r2,mae,rmse,100*mae/nom,dt,tag))
            linhas.append(dict(usina=usina, modelo=nome, R2=r2, MAE_W=mae, RMSE_W=rmse,
                               MAE_pct=100*mae/nom, tempo_s=dt, amostrado=amostra))
        except Exception as e:
            print("%-22s  FALHOU: %s" % (nome, str(e)[:60]))
            linhas.append(dict(usina=usina, modelo=nome, R2=np.nan, MAE_W=np.nan,
                               RMSE_W=np.nan, MAE_pct=np.nan, tempo_s=time.time()-t0, amostrado=amostra))
        sys.stdout.flush()

R = pd.DataFrame(linhas)
R.to_csv(AMBAS / "comparacao_modelos_completa.csv", index=False, sep=";", decimal=",", encoding="utf-8-sig")

print("\n" + "="*84)
print("RANKING POR USINA (R2 no periodo futuro)")
print("="*84)
for u in ["Cascavel","Curitiba"]:
    s = R[R.usina==u].sort_values("R2", ascending=False)
    print("\n%s:" % u)
    print(s[["modelo","R2","MAE_W","MAE_pct","tempo_s"]].round(4).to_string(index=False))

piv = R.pivot(index="modelo", columns="usina", values="R2")
piv["media"] = piv.mean(axis=1)
piv = piv.sort_values("media", ascending=False)
print("\n" + "="*84)
print("R2 NAS DUAS USINAS")
print("="*84)
print(piv.round(4).to_string())
melhor = piv.index[0]
print("\nMELHOR NAS DUAS: %s  (R2 medio %.4f)" % (melhor, piv.iloc[0]["media"]))
json.dump(dict(melhor=melhor, r2_medio=float(piv.iloc[0]["media"]),
               r2_cascavel=float(piv.iloc[0]["Cascavel"]), r2_curitiba=float(piv.iloc[0]["Curitiba"])),
          open(AMBAS / "melhor_modelo.json","w"), indent=1)
# cada pasta de usina leva uma copia, para rodar sozinha
import shutil
for pasta in ("cascavel", "curitiba"):
    for f_ in ("comparacao_modelos_completa.csv", "melhor_modelo.json"):
        shutil.copy2(AMBAS / f_, BASE / pasta / f_)
