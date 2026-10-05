# -*- coding: utf-8 -*-
###############################################################################
# IRRADIANCIA ESTIMADA A PARTIR DA POTENCIA - E O QUE ELA PODE E NAO PODE FAZER
#
# Inverte P = P_nom (G/1000) [1 + gamma (T_c - 25)] K  para obter G a 5 minutos,
# e depois testa, com numero, quatro hipoteses:
#
#   A  BASE        preditores atuais (NASA horaria + diaria + geometria)
#   B  TETO        base + G_inv do MESMO instante
#                  -> mede o teto. NAO e um modelo valido: G_inv vem do alvo.
#   C  DOWNSCALE   base + POA reconstruida por um modelo que preve kc de 5 min
#                  a partir de NASA + geometria, treinado com G_inv como ALVO.
#                  Na hora de prever nao usa potencia nenhuma: e legitimo.
#   D  PERSIST     base + G_inv defasada de 1 hora (cenario de nowcast, em que
#                  havia sensor no passado mas nao no instante previsto)
#
# A pergunta do Joao: "quebrar a irradiancia da NASA em 5 min melhora o modelo?"
# A resposta esta na distancia entre C e B.
#
# Requisitos: pandas, numpy, scikit-learn, pyarrow
###############################################################################

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, r2_score

###############################################################################
# CONFIGURACAO
###############################################################################

pasta_projeto = Path(__file__).resolve().parents[2]
pasta_saida = Path(__file__).resolve().parent

USINAS = {
    'Cascavel': dict(
        caminho_base=pasta_projeto / r'base_modelagem/cascavel/base_Cascavel_5min.parquet',
        titulo='USINA_CASCAVEL - CASCAVEL-PR - 3,96 kWp - Fronius Primo 4.0-1'),
    'Curitiba': dict(
        caminho_base=pasta_projeto / r'base_modelagem/curitiba/base_Curitiba_5min.parquet',
        titulo='USINA_CURITIBA - CURITIBA-PR - ~9,6 kWp ESTIMADO - Fronius Symo 12.0-3'),
}

DATA_CORTE = '2025-08-01'      # mesma divisao usada no resto do projeto

ETA_INV = 0.97                 # rendimento do inversor Fronius (decimal)
GAMMA = -0.004                 # coef. de temperatura da potencia (1/C), datasheet Cascavel
C_TERM = (45.0 - 20.0) / 800.0 # NOCT 45 C -> T_c = T_ar + C_TERM * G
PCT_CALIB = 98                 # percentil de G_inv/poa_ceu_claro usado para calibrar K

SEMENTE = 42

###############################################################################
# INVERSAO: DA POTENCIA PARA A IRRADIANCIA
###############################################################################


def irradiancia_inversa(p_ca_W, t_ar_C, p_nom_kWp, k_perdas):
    """Resolve G em  P_cc = (P_nom K / 1000) G [1 + gamma (T_ar + C G - 25)].

    Substituindo T_c = T_ar + C_TERM * G, a equacao vira uma quadratica em G:

        b G^2 + a G - P_cc = 0
        a = (P_nom K / 1000) [1 + gamma (T_ar - 25)]
        b = (P_nom K / 1000) gamma C_TERM          (negativo, pois gamma < 0)

    Raiz fisica: G = (-a + sqrt(a^2 + 4 b P_cc)) / (2 b).
    """
    p_cc = p_ca_W / ETA_INV
    escala = p_nom_kWp * 1000.0 * k_perdas / 1000.0
    a = escala * (1.0 + GAMMA * (t_ar_C - 25.0))
    b = escala * GAMMA * C_TERM
    disc = a ** 2 + 4.0 * b * p_cc
    g = np.where(disc > 0, (-a + np.sqrt(np.maximum(disc, 0))) / (2.0 * b), np.nan)
    # acima do joelho da quadratica a inversao deixa de ter solucao: satura
    return np.where(np.isfinite(g) & (g >= 0), g, np.nan)


def calibra_k(d):
    """K nao e conhecido. Calibra para que o topo do envelope de G_inv/poa_ceu_claro
    em ceu claro caia em 1,0 - ou seja, o melhor dia observado vira ceu claro pleno.
    """
    k = 1.0
    for _ in range(12):
        g = irradiancia_inversa(d.potencia_ca_W.values, d.temp_ar_horaria.values,
                                d.pot_nominal_kWp.values, k)
        m = (d.poa_ceu_claro.values > 400) & np.isfinite(g) & (g > 0)
        if m.sum() < 500:
            break
        raz = np.percentile(g[m] / d.poa_ceu_claro.values[m], PCT_CALIB)
        if abs(raz - 1.0) < 1e-4:
            break
        k *= raz
    return k


###############################################################################
# EXPERIMENTOS
###############################################################################

GEO = ['dia_do_ano', 'hora_solar', 'elevacao_solar', 'cos_zenite', 'poa_ceu_claro']
NASA_H = ['kc_horario', 'poa_estimada', 'ghi_horario', 'dni_horario',
          'temp_ar_horaria', 'vento_horario']
NASA_D = ['kt_diario', 'ghi_diario', 'temp_ar_diaria', 'umidade_diaria',
          'vento_diario', 'chuva_diaria', 'nuvens_diaria', 'aerossol_diario']
SUJEIRA = ['estado_sujeira']
BASE = GEO + NASA_H + NASA_D + SUJEIRA
ALVO = 'potencia_ca_W'


def roda(rotulo, feats, tr, te):
    a = tr.dropna(subset=feats + [ALVO])
    b = te.dropna(subset=feats + [ALVO])
    t0 = time.time()
    m = HistGradientBoostingRegressor(random_state=SEMENTE).fit(a[feats], a[ALVO])
    p = np.clip(m.predict(b[feats]), 0, None)
    y = b[ALVO].values
    dia = b.assign(prev=p).groupby(b.data_hora.dt.date).agg(
        real=(ALVO, lambda s: s.sum() * 5 / 60 / 1000),
        prev=('prev', lambda s: s.sum() * 5 / 60 / 1000))
    r = dict(cenario=rotulo, n_treino=len(a), n_teste=len(b),
             R2=r2_score(y, p), MAE=mean_absolute_error(y, p),
             R2_diario=r2_score(dia.real, dia.prev),
             MAE_diario=mean_absolute_error(dia.real, dia.prev),
             segundos=time.time() - t0)
    print('   %-46s R2 %.4f   MAE %7.1f W   | diario R2 %.4f  MAE %.2f kWh'
          % (rotulo, r['R2'], r['MAE'], r['R2_diario'], r['MAE_diario']), flush=True)
    return r


def downscale_ml(tr, te, d):
    """Modelo C: preve o kc de 5 min a partir de NASA + geometria.

    O alvo de treino e o kc medido (via G_inv), mas na previsao nenhuma coluna
    depende da potencia. Treina so no periodo de treino.
    """
    feats = GEO + NASA_H + NASA_D
    alvo = 'kc_5min'
    a = tr.dropna(subset=feats + [alvo])
    m = HistGradientBoostingRegressor(random_state=SEMENTE).fit(a[feats], a[alvo])
    kc = np.full(len(d), np.nan)
    ok = d[feats].notna().all(axis=1).values
    kc[ok] = np.clip(m.predict(d.loc[ok, feats]), 0, 1.2)
    return kc


def processa(usina, cfg):
    print('\n' + '=' * 79)
    print(cfg['titulo'])
    print('=' * 79)
    d = pd.read_parquet(cfg['caminho_base']).sort_values('data_hora').reset_index(drop=True)

    ###########################################################################
    # 1. INVERSAO E CALIBRACAO
    ###########################################################################
    k = calibra_k(d)
    d['G_inv'] = irradiancia_inversa(d.potencia_ca_W.values, d.temp_ar_horaria.values,
                                     d.pot_nominal_kWp.values, k)
    d['kc_5min'] = (d.G_inv / d.poa_ceu_claro).clip(0, 1.2)
    val = d.G_inv.notna()
    print('\n1) INVERSAO')
    print('   K calibrado (perdas globais)      %.4f' % k)
    print('   G_inv resolvida                   %d de %d linhas (%.1f%%)'
          % (val.sum(), len(d), 100 * val.mean()))
    print('   G_inv media / mediana / p99       %.0f / %.0f / %.0f W/m2'
          % (d.G_inv.mean(), d.G_inv.median(), d.G_inv.quantile(.99)))

    ###########################################################################
    # 2. G_inv CONTRA A NASA POWER
    ###########################################################################
    h = d.dropna(subset=['G_inv', 'poa_estimada']).copy()
    h['hora'] = h.data_hora.dt.floor('h')
    ag = h.groupby('hora').agg(G_inv=('G_inv', 'mean'), nasa=('poa_estimada', 'mean'),
                               n=('G_inv', 'size'))
    ag = ag[ag.n >= 8]
    r_h = np.corrcoef(ag.G_inv, ag.nasa)[0, 1]
    r_5 = np.corrcoef(h.G_inv, h.poa_estimada)[0, 1]
    vies = 100 * (ag.nasa.mean() / ag.G_inv.mean() - 1)
    print('\n2) G_inv CONTRA A NASA POWER (poa_estimada = poa_ceu_claro x kc horario)')
    print('   correlacao na hora                r = %.4f  (%d horas)' % (r_h, len(ag)))
    print('   correlacao a 5 min                r = %.4f  (%d intervalos)' % (r_5, len(h)))
    print('   vies da NASA contra G_inv         %+.1f %%' % vies)
    disp = (h.poa_estimada - h.G_inv).abs().mean()
    print('   erro absoluto medio a 5 min       %.0f W/m2' % disp)

    ###########################################################################
    # 3. OS QUATRO CENARIOS
    ###########################################################################
    corte = pd.Timestamp(DATA_CORTE)
    d['G_inv_1h'] = d.G_inv.shift(12)          # 12 intervalos de 5 min = 1 hora
    d['kc_ml'] = np.nan

    tr = d[d.data_hora < corte]
    te = d[d.data_hora >= corte]
    d.loc[:, 'kc_ml'] = downscale_ml(tr, te, d)
    d['poa_dsc_ml'] = d.poa_ceu_claro * d.kc_ml
    tr = d[d.data_hora < corte]
    te = d[d.data_hora >= corte]

    print('\n3) CENARIOS  (treino ate %s, teste depois: %d / %d linhas)'
          % (DATA_CORTE, len(tr), len(te)))
    res = [
        roda('A  BASE      NASA horaria + diaria + geometria', BASE, tr, te),
        roda('B  TETO      + G_inv do mesmo instante', BASE + ['G_inv'], tr, te),
        roda('C  DOWNSCALE + POA reconstruida por ML (sem potencia)',
             BASE + ['poa_dsc_ml', 'kc_ml'], tr, te),
        roda('D  PERSIST   + G_inv defasada de 1 hora', BASE + ['G_inv_1h'], tr, te),
    ]
    R = pd.DataFrame(res)
    R.insert(0, 'usina', usina)

    base, teto = R.iloc[0], R.iloc[1]
    dsc, pers = R.iloc[2], R.iloc[3]
    print('\n   ganho de C sobre A (legitimo)     %+.4f R2   %+.1f W de MAE'
          % (dsc.R2 - base.R2, dsc.MAE - base.MAE))
    print('   ganho de D sobre A (nowcast)      %+.4f R2   %+.1f W de MAE'
          % (pers.R2 - base.R2, pers.MAE - base.MAE))
    print('   distancia de A ate o teto B       %+.4f R2   %+.1f W de MAE'
          % (teto.R2 - base.R2, teto.MAE - base.MAE))
    if teto.R2 > base.R2:
        print('   C aproveitou do teto              %.1f %%'
              % (100 * (dsc.R2 - base.R2) / (teto.R2 - base.R2)))

    ###########################################################################
    # 4. ONDE O ERRO MORA
    ###########################################################################
    print('\n4) ERRO POR CONDICAO DE CEU (kc medido a 5 min)')
    fa, fb = BASE, BASE + ['poa_dsc_ml', 'kc_ml']
    ea = _erro(fa, tr, te)
    eb = _erro(fb, tr, te)
    et = _erro(BASE + ['G_inv'], tr, te)
    cmp = pd.DataFrame({'A': ea, 'C': eb, 'B_teto': et}).dropna()
    cmp['kc'] = te.loc[cmp.index, 'kc_5min']
    faixas = cmp.groupby(pd.cut(cmp.kc, [0, .2, .4, .6, .8, 1.2]), observed=True).agg(
        n=('A', 'size'), MAE_A=('A', 'mean'), MAE_C=('C', 'mean'), MAE_teto=('B_teto', 'mean'))
    faixas['ganho_C_%'] = (100 * (1 - faixas.MAE_C / faixas.MAE_A)).round(1)
    faixas['ganho_teto_%'] = (100 * (1 - faixas.MAE_teto / faixas.MAE_A)).round(1)
    print(faixas.round(1).to_string())

    d[['data_hora', 'potencia_ca_W', 'poa_ceu_claro', 'poa_estimada',
       'G_inv', 'kc_5min', 'kc_ml', 'poa_dsc_ml']].to_parquet(
        pasta_saida / ('irradiancia_inversa_%s.parquet' % usina), index=False,
        compression='zstd')
    return R, dict(usina=usina, k_perdas=float(k), r_horario=float(r_h),
                   r_5min=float(r_5), vies_nasa_pct=float(vies),
                   mae_nasa_5min_Wm2=float(disp))


def _erro(feats, tr, te):
    a = tr.dropna(subset=feats + [ALVO])
    b = te.dropna(subset=feats + [ALVO])
    m = HistGradientBoostingRegressor(random_state=SEMENTE).fit(a[feats], a[ALVO])
    return pd.Series(np.abs(np.clip(m.predict(b[feats]), 0, None) - b[ALVO].values),
                     index=b.index)


if __name__ == '__main__':
    tabelas, resumos = [], []
    for usina, cfg in USINAS.items():
        R, resumo = processa(usina, cfg)
        tabelas.append(R)
        resumos.append(resumo)

    R = pd.concat(tabelas, ignore_index=True)
    R.to_csv(pasta_saida / 'comparativo_irradiancia_inversa.csv',
             index=False, sep=';', decimal=',', encoding='utf-8-sig')
    json.dump(resumos, open(pasta_saida / 'inversao_resumo.json', 'w'), indent=1)
    print('\n\nRESUMO')
    print(R[['usina', 'cenario', 'R2', 'MAE', 'R2_diario']].round(4).to_string(index=False))
