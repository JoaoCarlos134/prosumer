# -*- coding: utf-8 -*-
###############################################################################
# UM SENSOR DE IRRADIANCIA SUBSTITUI A NASA POWER?
#
# Mede quanto do vao entre o modelo embarcado (sem NASA) e o modelo completo
# vem de UM canal de irradiancia, e quanto vem de todo o resto da reanalise -
# nuvens, aerossol, umidade, chuva, vento, temperatura diaria, Kt diario.
#
# Quatro configuracoes:
#   A  embarcado sem sensor        geometria + temperatura + estado de sujeira
#   B  + um canal de irradiancia   A + poa_estimada (qualidade NASA)
#   C  so POA + temperatura        o minimo absoluto de um dispositivo
#   D  completo                    os 20 preditores atuais
#
# ATENCAO ao ler: a linha B usa irradiancia de QUALIDADE NASA, que e ruim.
# Um piranometro real mede melhor (o kc da NASA tem R2 negativo contra o kc
# medido) e em resolucao de 5 min, nao horaria. B e piso, nao teto.
#
# Saida: sensor_irradiancia.csv
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
caminho_saida = pasta_base / 'embarcado' / 'sensor_irradiancia.csv'

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

CONFIGS = [
    ('A. embarcado, sem sensor', GEO + ['temp_ar_horaria'] + SUJEIRA),
    ('B. + um canal de irradiancia', GEO + ['temp_ar_horaria'] + SUJEIRA + ['poa_estimada']),
    ('C. so POA + temperatura', ['poa_estimada', 'temp_ar_horaria']),
    ('D. completo, toda a NASA', COMPLETO),
]

###############################################################################
# EXECUCAO
###############################################################################

if __name__ == '__main__':
    linhas = []
    for usina, caminho in USINAS.items():
        d = pd.read_parquet(caminho).sort_values('data_hora')
        d = d.dropna(subset=COMPLETO + [ALVO])
        tr = d[d.data_hora < DATA_CORTE]
        te = d[d.data_hora >= DATA_CORTE]
        print('=== %s === treino %d  teste %d' % (usina, len(tr), len(te)))
        melhores = {}
        for rotulo, feats in CONFIGS:
            reg = dict(usina=usina, config=rotulo, n_preditores=len(feats))
            melhor = -9
            for nome, mod in [('Linear', LinearRegression()),
                              ('HistGB', HistGradientBoostingRegressor(random_state=SEMENTE))]:
                mod.fit(tr[feats], tr[ALVO])
                p = np.clip(mod.predict(te[feats]), 0, None)
                reg['R2_%s' % nome] = round(r2_score(te[ALVO], p), 4)
                reg['MAE_%s' % nome] = round(mean_absolute_error(te[ALVO], p), 1)
                melhor = max(melhor, reg['R2_%s' % nome])
            reg['R2_melhor'] = round(melhor, 4)
            melhores[rotulo[0]] = melhor
            linhas.append(reg)
            print('   %-30s %2d preditores  melhor R2 %.4f'
                  % (rotulo, len(feats), melhor), flush=True)

        vao = melhores['D'] - melhores['A']
        canal = melhores['B'] - melhores['A']
        resto = melhores['D'] - melhores['B']
        linhas.append(dict(usina=usina, config='vao total da NASA (D - A)', n_preditores=None,
                           R2_melhor=round(vao, 4)))
        linhas.append(dict(usina=usina, config='so o canal de irradiancia (B - A)',
                           n_preditores=None, R2_melhor=round(canal, 4)))
        linhas.append(dict(usina=usina, config='todo o resto da NASA (D - B)',
                           n_preditores=None, R2_melhor=round(resto, 4)))
        print('   vao da NASA %+.4f  |  canal de irradiancia %+.4f (%.1f%%)  |  resto %+.4f (%.1f%%)'
              % (vao, canal, 100 * canal / vao, resto, 100 * resto / vao))
        print()

    R = pd.DataFrame(linhas)
    R.to_csv(caminho_saida, index=False, sep=';', decimal=',', encoding='utf-8-sig')
    print('salvo em %s' % caminho_saida.name)
