# -*- coding: utf-8 -*-
###############################################################################
# MAIS MODELOS + TENSORFLOW LITE PARA EMBARCAMENTO
#
# Continua a comparacao de 13 algoritmos ja feita, acrescentando:
#
#   LightGBM, CatBoost, Huber, ElasticNet, PLS, Voting  (familia classica)
#   Keras MLP em duas larguras                          (origem do TFLite)
#   TFLite float32, float16, int8 dinamico, int8 total  (embarcado)
#
# E, principalmente, separa DOIS conjuntos de preditores:
#
#   COMPLETO   os 24 preditores atuais, com NASA POWER horaria e diaria
#   EMBARCADO  so o que um dispositivo na usina consegue ter SOZINHO:
#              geometria solar (relogio + coordenada), temperatura local e o
#              proprio historico de desempenho. SEM NASA.
#
# Essa separacao e o ponto do exercicio. A NASA POWER e reanalise: chega com
# dias de atraso. Um modelo embarcado no inversor nao tem irradiancia nenhuma
# em tempo real, e e isso que define o teto dele.
#
# Metricas por modelo: R2, MAE, tamanho em KB e latencia por amostra.
#
# Requisitos: pandas, numpy, scikit-learn, tensorflow, lightgbm, catboost, xgboost
###############################################################################

import json
import pickle
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cross_decomposition import PLSRegression
from sklearn.ensemble import (HistGradientBoostingRegressor, RandomForestRegressor,
                              VotingRegressor)
from sklearn.impute import SimpleImputer
from sklearn.linear_model import ElasticNet, HuberRegressor, LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')

###############################################################################
# CONFIGURACAO
###############################################################################

pasta_projeto = Path(__file__).resolve().parents[2]
pasta_saida = Path(__file__).resolve().parents[1] / 'embarcado'
pasta_saida.mkdir(exist_ok=True)

USINAS = {
    'Cascavel': pasta_projeto / r'base_modelagem/cascavel/base_Cascavel_5min.parquet',
    'Curitiba': pasta_projeto / r'base_modelagem/curitiba/base_Curitiba_5min.parquet',
}

DATA_CORTE = '2025-08-01'
SEMENTE = 42
ALVO = 'potencia_ca_W'

# -- conjuntos de preditores ---------------------------------------------------
GEO = ['dia_do_ano', 'hora_solar', 'elevacao_solar', 'cos_zenite', 'poa_ceu_claro']
NASA_H = ['kc_horario', 'poa_estimada', 'ghi_horario', 'dni_horario',
          'temp_ar_horaria', 'vento_horario']
NASA_D = ['kt_diario', 'ghi_diario', 'temp_ar_diaria', 'umidade_diaria',
          'vento_diario', 'chuva_diaria', 'nuvens_diaria', 'aerossol_diario']
SUJEIRA = ['estado_sujeira']

CONJUNTOS = {
    # tudo que a base oferece hoje
    'COMPLETO': GEO + NASA_H + NASA_D + SUJEIRA,
    # so o que o dispositivo obtem sozinho: relogio, coordenada, termometro local
    # e a propria media movel de desempenho, que ele calcula do que ja mediu
    'EMBARCADO': GEO + ['temp_ar_horaria'] + SUJEIRA,
}

# -- redes ---------------------------------------------------------------------
EPOCAS = 40
LOTE = 512
ARQUITETURAS = {'MLP 32-16': (32, 16), 'MLP 16-8': (16, 8)}

###############################################################################
# DADOS
###############################################################################


def carrega(caminho, feats):
    """Devolve treino/teste ja filtrados.

    As linhas validas sao SEMPRE as do conjunto COMPLETO, mesmo quando se avalia
    o conjunto EMBARCADO. Duas razoes:

      1. A serie horaria da NASA POWER termina em 30/05/2026. Nas linhas sem ela
         o modelo com NASA despenca, e mante-las no teste derruba o R2 do
         HistGradientBoosting de 0,82 para 0,64 — que nao e o desempenho do
         modelo, e o buraco no dado. Os demais scripts do projeto ja descartam.
      2. So assim COMPLETO e EMBARCADO sao pontuados nas MESMAS linhas, e a
         diferenca entre eles mede o conjunto de preditores e mais nada.
    """
    d = pd.read_parquet(caminho).sort_values('data_hora')
    d = d.dropna(subset=CONJUNTOS['COMPLETO'] + [ALVO])
    corte = pd.Timestamp(DATA_CORTE)
    tr, te = d[d.data_hora < corte], d[d.data_hora >= corte]
    return tr[feats], tr[ALVO].values, te[feats], te[ALVO].values, te.data_hora


def avalia(y, p):
    p = np.clip(p, 0, None)
    return r2_score(y, p), mean_absolute_error(y, p)


def tamanho_pickle(modelo):
    return len(pickle.dumps(modelo)) / 1024.0


def latencia(fn, X, n=300):
    """Microssegundos por amostra, uma amostra por vez (como no embarcado)."""
    amostras = X[:n]
    t0 = time.perf_counter()
    for i in range(len(amostras)):
        fn(amostras[i:i + 1])
    return 1e6 * (time.perf_counter() - t0) / len(amostras)


###############################################################################
# MODELOS CLASSICOS
###############################################################################


def modelos_classicos():
    m = {}
    m['HistGradientBoosting'] = HistGradientBoostingRegressor(random_state=SEMENTE)
    m['Random Forest'] = RandomForestRegressor(random_state=SEMENTE, n_jobs=-1)
    m['Regressao Linear'] = LinearRegression()
    try:
        from lightgbm import LGBMRegressor
        m['LightGBM'] = LGBMRegressor(random_state=SEMENTE, verbose=-1)
    except ImportError:
        pass
    try:
        from catboost import CatBoostRegressor
        m['CatBoost'] = CatBoostRegressor(random_state=SEMENTE, verbose=0,
                                           allow_writing_files=False)  # sem catboost_info/
    except ImportError:
        pass
    try:
        from xgboost import XGBRegressor
        m['XGBoost'] = XGBRegressor(random_state=SEMENTE)
    except ImportError:
        pass
    m['Huber'] = HuberRegressor()
    m['ElasticNet'] = ElasticNet(random_state=SEMENTE)
    m['PLS'] = PLSRegression(n_components=5)
    m['Voting (HGB+RF+Linear)'] = VotingRegressor([
        ('hgb', HistGradientBoostingRegressor(random_state=SEMENTE)),
        ('rf', RandomForestRegressor(random_state=SEMENTE, n_jobs=-1)),
        ('lin', LinearRegression())])
    return m


PRECISA_IMPUTAR = ('Regressao Linear', 'Huber', 'ElasticNet', 'PLS',
                   'Random Forest', 'Voting (HGB+RF+Linear)')


def roda_classicos(Xtr, ytr, Xte, yte, conj):
    linhas = []
    imp = SimpleImputer(strategy='median').fit(Xtr)
    Xtr_i, Xte_i = imp.transform(Xtr), imp.transform(Xte)
    esc = StandardScaler().fit(Xtr_i)
    for nome, mod in modelos_classicos().items():
        precisa = nome in PRECISA_IMPUTAR
        A, B = (Xtr_i, Xte_i) if precisa else (Xtr.values, Xte.values)
        if nome in ('Huber', 'ElasticNet', 'PLS'):
            A, B = esc.transform(Xtr_i), esc.transform(Xte_i)
        t0 = time.time()
        mod.fit(A, ytr)
        seg = time.time() - t0
        p = np.asarray(mod.predict(B)).ravel()
        r2, mae = avalia(yte, p)
        linhas.append(dict(conjunto=conj, familia='classico', modelo=nome,
                           R2=round(r2, 4), MAE=round(mae, 1),
                           KB=round(tamanho_pickle(mod), 1),
                           us_por_amostra=round(latencia(
                               lambda x: mod.predict(x), B), 1),
                           treino_s=round(seg, 1)))
        print('   %-24s R2 %.4f  MAE %7.1f  %8.1f KB  %7.1f us'
              % (nome, r2, mae, linhas[-1]['KB'], linhas[-1]['us_por_amostra']), flush=True)
    return linhas


###############################################################################
# KERAS + TENSORFLOW LITE
###############################################################################


def roda_redes(Xtr, ytr, Xte, yte, conj, usina):
    try:
        import tensorflow as tf
    except ImportError:
        print('   TensorFlow ausente: etapa TFLite pulada', flush=True)
        return []

    tf.random.set_seed(SEMENTE)
    np.random.seed(SEMENTE)

    imp = SimpleImputer(strategy='median').fit(Xtr)
    esc = StandardScaler().fit(imp.transform(Xtr))
    A = esc.transform(imp.transform(Xtr)).astype(np.float32)
    B = esc.transform(imp.transform(Xte)).astype(np.float32)
    # normaliza o alvo: acelera e estabiliza o treino
    my, sy = ytr.mean(), ytr.std()
    Atr_y = ((ytr - my) / sy).astype(np.float32)

    linhas = []
    for rotulo, camadas in ARQUITETURAS.items():
        modelo = tf.keras.Sequential(
            [tf.keras.layers.Input(shape=(A.shape[1],))] +
            [tf.keras.layers.Dense(n, activation='relu') for n in camadas] +
            [tf.keras.layers.Dense(1)])
        modelo.compile(optimizer='adam', loss='mse')
        t0 = time.time()
        modelo.fit(A, Atr_y, epochs=EPOCAS, batch_size=LOTE, verbose=0,
                   validation_split=0.1,
                   callbacks=[tf.keras.callbacks.EarlyStopping(patience=6,
                                                               restore_best_weights=True)])
        seg = time.time() - t0
        p = modelo.predict(B, verbose=0).ravel() * sy + my
        r2, mae = avalia(yte, p)
        kb = sum(w.nbytes for w in modelo.get_weights()) / 1024.0
        linhas.append(dict(conjunto=conj, familia='keras', modelo='Keras %s' % rotulo,
                           R2=round(r2, 4), MAE=round(mae, 1), KB=round(kb, 1),
                           us_por_amostra=None, treino_s=round(seg, 1)))
        print('   %-24s R2 %.4f  MAE %7.1f  %8.1f KB' % ('Keras ' + rotulo, r2, mae, kb),
              flush=True)

        # ---------------- conversoes TFLite ----------------
        def representativo():
            for i in range(0, min(len(A), 500)):
                yield [A[i:i + 1]]

        conversoes = {
            'float32': dict(),
            'float16': dict(otimiza=True, tipos=[tf.float16]),
            'int8 dinamico': dict(otimiza=True),
            'int8 total': dict(otimiza=True, total=True),
        }
        for nome_c, cfg in conversoes.items():
            conv = tf.lite.TFLiteConverter.from_keras_model(modelo)
            if cfg.get('otimiza'):
                conv.optimizations = [tf.lite.Optimize.DEFAULT]
            if cfg.get('tipos'):
                conv.target_spec.supported_types = cfg['tipos']
            if cfg.get('total'):
                conv.representative_dataset = representativo
                conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
                conv.inference_input_type = tf.int8
                conv.inference_output_type = tf.int8
            try:
                blob = conv.convert()
            except Exception as e:
                print('   %-24s FALHOU na conversao: %s' % (nome_c, str(e)[:60]), flush=True)
                continue
            arq = pasta_saida / ('%s_%s_%s_%s.tflite'
                                 % (usina, conj.lower(), rotulo.replace(' ', ''),
                                    nome_c.replace(' ', '')))
            arq.write_bytes(blob)

            interp = __import__('tensorflow').lite.Interpreter(model_content=blob)
            interp.allocate_tensors()
            ent, sai = interp.get_input_details()[0], interp.get_output_details()[0]

            def prever(x):
                if ent['dtype'] == np.int8:
                    s, z = ent['quantization']
                    x = np.clip(np.round(x / s + z), -128, 127).astype(np.int8)
                interp.set_tensor(ent['index'], x.astype(ent['dtype']))
                interp.invoke()
                o = interp.get_tensor(sai['index'])
                if sai['dtype'] == np.int8:
                    s, z = sai['quantization']
                    o = (o.astype(np.float32) - z) * s
                return o

            pred = np.array([prever(B[i:i + 1]).ravel()[0] for i in range(len(B))])
            pred = pred * sy + my
            r2q, maeq = avalia(yte, pred)
            lat = latencia(prever, B)
            linhas.append(dict(conjunto=conj, familia='tflite',
                               modelo='TFLite %s %s' % (rotulo, nome_c),
                               R2=round(r2q, 4), MAE=round(maeq, 1),
                               KB=round(len(blob) / 1024.0, 1),
                               us_por_amostra=round(lat, 1), treino_s=None))
            print('   %-24s R2 %.4f  MAE %7.1f  %8.1f KB  %7.1f us'
                  % ('TFLite ' + nome_c, r2q, maeq, len(blob) / 1024.0, lat), flush=True)
    return linhas


###############################################################################
# EXECUCAO
###############################################################################

if __name__ == '__main__':
    todas = []
    for usina, caminho in USINAS.items():
        for conj, feats in CONJUNTOS.items():
            print('\n' + '=' * 79)
            print('%s  |  conjunto %s  |  %d preditores' % (usina, conj, len(feats)))
            print('=' * 79)
            Xtr, ytr, Xte, yte, _ = carrega(caminho, feats)
            print('   treino %d  teste %d' % (len(Xtr), len(Xte)), flush=True)
            linhas = roda_classicos(Xtr, ytr, Xte, yte, conj)
            linhas += roda_redes(Xtr, ytr, Xte, yte, conj, usina)
            for r in linhas:
                r['usina'] = usina
            todas += linhas

    R = pd.DataFrame(todas)[['usina', 'conjunto', 'familia', 'modelo', 'R2', 'MAE',
                             'KB', 'us_por_amostra', 'treino_s']]
    R.to_csv(pasta_saida / 'comparacao_embarcado.csv', index=False,
             sep=';', decimal=',', encoding='utf-8-sig')

    print('\n\n' + '=' * 79)
    print('RESUMO')
    print('=' * 79)
    for usina in USINAS:
        for conj in CONJUNTOS:
            s = R[(R.usina == usina) & (R.conjunto == conj)].sort_values('R2', ascending=False)
            if s.empty:
                continue
            melhor = s.iloc[0]
            print('%-9s %-10s melhor: %-28s R2 %.4f  %6.1f KB'
                  % (usina, conj, melhor.modelo, melhor.R2, melhor.KB))
    print('\nArquivos .tflite em %s' % pasta_saida)
