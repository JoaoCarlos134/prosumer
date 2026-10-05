# -*- coding: utf-8 -*-
###############################################################################
# ABLACAO DE PREDITORES
#
# De onde vem o R2? Acrescenta os preditores em camadas, da fisica pura ate a
# base completa, e mede quanto cada camada agrega. Dois modelos de extremos
# opostos - regressao linear e HistGradientBoosting - para separar o que e
# informacao do que e capacidade de ajuste.
#
# Saida: ablacao_preditores.csv
#
# Requisitos: pandas, numpy, scikit-learn, pyarrow
###############################################################################

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, r2_score

warnings.filterwarnings('ignore')

###############################################################################
# CONFIGURACAO
###############################################################################

pasta_base = Path(__file__).resolve().parents[1]
caminho_saida = pasta_base / 'embarcado' / 'ablacao_preditores.csv'

USINAS = {
    'Cascavel': pasta_base / 'cascavel/base_Cascavel_5min.parquet',
    'Curitiba': pasta_base / 'curitiba/base_Curitiba_5min.parquet',
}

DATA_CORTE = '2025-08-01'
SEMENTE = 42
ALVO = 'potencia_ca_W'

GEO = ['dia_do_ano', 'hora_solar', 'elevacao_solar', 'cos_zenite', 'poa_ceu_claro']
NASA_H = ['kc_horario', 'poa_estimada', 'ghi_horario', 'dni_horario',
          'temp_ar_horaria', 'vento_horario']
NASA_D = ['kt_diario', 'ghi_diario', 'temp_ar_diaria', 'umidade_diaria',
          'vento_diario', 'chuva_diaria', 'nuvens_diaria', 'aerossol_diario']
SUJEIRA = ['estado_sujeira']
COMPLETO = GEO + NASA_H + NASA_D + SUJEIRA

CAMADAS = [
    ('1. so poa_estimada', ['poa_estimada']),
    ('2. so geometria', GEO),
    ('3. geometria + poa_estimada', GEO + ['poa_estimada']),
    ('4. + resto da NASA horaria', GEO + NASA_H),
    ('5. + NASA diaria', GEO + NASA_H + NASA_D),
    ('6. + estado_sujeira = COMPLETO', COMPLETO),
]

###############################################################################
# EXECUCAO
###############################################################################

if __name__ == '__main__':
    linhas = []
    for usina, caminho in USINAS.items():
        d = pd.read_parquet(caminho).sort_values('data_hora')
        d = d.dropna(subset=COMPLETO + [ALVO])       # mesmas linhas em toda a ablacao
        tr = d[d.data_hora < DATA_CORTE]
        te = d[d.data_hora >= DATA_CORTE]
        print('=== %s === treino %d  teste %d' % (usina, len(tr), len(te)))
        for rotulo, feats in CAMADAS:
            reg = dict(usina=usina, camada=rotulo, n_preditores=len(feats))
            for nome, mod in [('Linear', LinearRegression()),
                              ('HistGB', HistGradientBoostingRegressor(random_state=SEMENTE))]:
                mod.fit(tr[feats], tr[ALVO])
                p = np.clip(mod.predict(te[feats]), 0, None)
                reg['R2_%s' % nome] = round(r2_score(te[ALVO], p), 4)
                reg['MAE_%s' % nome] = round(mean_absolute_error(te[ALVO], p), 1)
            linhas.append(reg)
            print('   %-32s %2d preditores  Linear R2 %.4f   HistGB R2 %.4f'
                  % (rotulo, len(feats), reg['R2_Linear'], reg['R2_HistGB']), flush=True)

    R = pd.DataFrame(linhas)
    R.to_csv(caminho_saida, index=False, sep=';', decimal=',', encoding='utf-8-sig')
    print('\nsalvo em %s' % caminho_saida.name)

    for usina in USINAS:
        s = R[R.usina == usina]
        uma = max(s.iloc[0].R2_Linear, s.iloc[0].R2_HistGB)
        tudo = max(s.iloc[-1].R2_Linear, s.iloc[-1].R2_HistGB)
        print('%-9s  uma coluna %.4f  |  vinte colunas %.4f  |  uma coluna entrega %.1f%%'
              % (usina, uma, tudo, 100 * uma / tudo))
