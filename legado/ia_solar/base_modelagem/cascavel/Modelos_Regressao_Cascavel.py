# -*- coding: utf-8 -*-
###############################################################################
# MODELOS DE REGRESSAO - PREVISAO DE GERACAO FOTOVOLTAICA
#
# Usina:  USINA_CASCAVEL - CASCAVEL-PR - 3,96 kWp - inversor Fronius Primo 4.0-1
#
# Potencia e geometria vem da ficha tecnica (12 x 330 Wp, 13 graus, 25 graus a leste
# do norte) e foram confirmadas pelos dados. Os numeros por kWp sao confiaveis.
# Base:   dados de 5 minutos do inversor Fronius + NASA POWER (diario e horario)
# Alvo:   potencia_ca_W  (potencia CA media no intervalo, em W)
#
# Para rodar em outra maquina basta alterar 'caminho_arquivo' logo abaixo.
# Nao e preciso nenhum outro arquivo: a base ja vem limpa e sem vazamento.
#
#
# MODELO ESCOLHIDO: HistGradientBoosting
#
# Comparados 13 algoritmos (a mesma familia testada no Projeto_solo, na versao
# de regressao), todos com parametros padrao e apenas random_state fixado.
# Resultado no periodo de teste desta usina:
#   Gradient Boosting      R2 0.8062   MAE   315.9 W     57.4 s
#   HistGradientBoosting   R2 0.8047   MAE   316.5 W      3.3 s  <== ESCOLHIDO
#   Rede Neural MLP        R2 0.8047   MAE   315.9 W     96.7 s
#   Extra Trees            R2 0.7948   MAE   325.7 W     25.9 s
#   Random Forest          R2 0.7891   MAE   328.5 W     47.4 s
#   XGBoost                R2 0.7822   MAE   336.9 W      1.2 s
#   Bagging                R2 0.7710   MAE   340.6 W      8.2 s
#   Regressao Linear       R2 0.7699   MAE   384.5 W      0.4 s
#   AdaBoost               R2 0.7434   MAE   420.0 W     12.2 s
#   SVR                    R2 0.6988   MAE   456.4 W     56.5 s
#   KNN                    R2 0.6519   MAE   413.9 W      3.6 s
#   Arvore de Decisao      R2 0.5971   MAE   442.0 W      3.5 s
#   Dummy (media)          R2 -0.0008   MAE   924.7 W      0.0 s
#
# A comparacao completa esta em comparacao_modelos_completa.csv.
# Para repetir: referencia/comparar_modelos.py
#
# Requisitos: pandas, numpy, matplotlib, seaborn, scikit-learn, pyarrow
#   pip install pandas numpy matplotlib seaborn scikit-learn pyarrow
###############################################################################

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import time

from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.dummy import DummyRegressor
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import GroupKFold
from sklearn.metrics import r2_score, mean_absolute_error, mean_squared_error
from sklearn.inspection import permutation_importance


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 1. CONFIGURACAO - altere apenas esta secao

caminho_arquivo = r'base_Cascavel_5min.parquet'
# Alternativa mais leve (abre no Excel):
# caminho_arquivo = r'base_Cascavel_horaria.csv'

USINA          = 'Cascavel'    # esta base contem apenas esta usina
DATA_CORTE     = '2025-08-01'  # tudo antes = treino, tudo depois = teste
USAR_SUJEIRA   = True          # inclui o estado de sujeira (media movel defasada de 30 dias)
USAR_HORARIA   = 'auto'        # 'auto' | True | False - ver o aviso da secao 4.1
SEED           = 42            # semente unica, nada de ajuste de hiperparametros
PASTA_SAIDA    = 'resultados_Cascavel'

os.makedirs(PASTA_SAIDA, exist_ok=True)


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 2. CARREGAR OS DADOS

print('Carregando %s ...' % caminho_arquivo)
if caminho_arquivo.lower().endswith('.parquet'):
    dados = pd.read_parquet(caminho_arquivo)
elif caminho_arquivo.lower().endswith('.csv'):
    dados = pd.read_csv(caminho_arquivo, sep=';', decimal=',', encoding='utf-8-sig')
else:
    dados = pd.read_excel(caminho_arquivo)

dados['data_hora'] = pd.to_datetime(dados['data_hora'])

if USINA != 'TODAS':
    dados = dados[dados['site'] == USINA].copy()

dados = dados.sort_values('data_hora').reset_index(drop=True)
print('Registros: %d   periodo: %s a %s' % (len(dados),
      dados['data_hora'].min().date(), dados['data_hora'].max().date()))
print('Usinas na base:', ', '.join(sorted(dados['site'].unique())))


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 3. VARIAVEIS EXPLICATIVAS E ALVO
#
# ATENCAO - VAZAMENTO DE DADOS
# As colunas do inversor que descrevem a propria geracao (energia_Wh,
# producao_fotovoltaica_Wh, rendimento_especifico, potencia_aparente x fator de
# potencia, corrente x tensao CA/CC) JA FORAM REMOVIDAS desta base. Elas sao o
# proprio alvo reescrito: um modelo que as use atinge R2 = 0,9999 e nao prediz
# nada. Nao as traga de volta.
#
# A coluna 'indice_desempenho' tambem NAO pode entrar: ela e calculada a partir
# do alvo. Serve apenas para diagnostico.

alvo = 'potencia_ca_W'

# Geometria solar (calculada, sempre disponivel, inclusive para o futuro)
var_geometria = ['hora_solar', 'dia_do_ano', 'elevacao_solar', 'cos_zenite', 'poa_ceu_claro']

# Meteorologia horaria da NASA POWER (ja rebaixada para 5 min)
var_horaria = ['poa_estimada', 'kc_horario', 'ghi_horario', 'dni_horario',
               'temp_ar_horaria', 'vento_horario']

# Meteorologia diaria da NASA POWER (um valor por dia, repetido no dia todo)
var_diaria = ['kt_diario', 'ghi_diario', 'temp_ar_diaria', 'umidade_diaria',
              'vento_diario', 'chuva_diaria', 'nuvens_diaria', 'aerossol_diario']

# Estado da usina (media movel de 30 dias DEFASADA - nao usa o dia corrente)
var_estado = ['estado_sujeira'] if USAR_SUJEIRA else []

variaveis = var_geometria + var_horaria + var_diaria + var_estado
variaveis = [c for c in variaveis if c in dados.columns]

print('\nVariaveis explicativas (%d):' % len(variaveis))
for v in variaveis:
    print('   %-20s  faltantes: %5.2f %%' % (v, 100 * dados[v].isna().mean()))


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 4. SEPARACAO TREINO / TESTE
#
# ATENCAO - NAO USE train_test_split ALEATORIO NESTA BASE.
# Registros de 5 minutos sao fortemente autocorrelacionados (r = 0,90 no passo
# seguinte, 0,48 uma hora depois). Um sorteio aleatorio coloca o minuto 10:05 no
# treino e o 10:10 no teste, e o modelo praticamente decora a resposta.
# Medido nesta base: R2 de 0,839 no k-fold aleatorio contra 0,799 num periodo
# futuro de verdade. Aqui separamos por data.

corte = pd.Timestamp(DATA_CORTE)
treino = dados[dados['data_hora'] < corte]
teste  = dados[dados['data_hora'] >= corte]

print('\nTreino: %6d registros ate %s' % (len(treino), corte.date()))
print('Teste : %6d registros a partir de %s' % (len(teste), corte.date()))
if len(teste) < 1000:
    raise SystemExit('Conjunto de teste pequeno demais. Ajuste DATA_CORTE.')


###############################################################################
# 4.1 COBERTURA DA METEOROLOGIA HORARIA
#
# ARMADILHA IMPORTANTE. A NASA POWER publica a serie HORARIA com atraso bem
# maior que a diaria: aqui a horaria termina em 31/05/2026 enquanto a diaria vai
# ate o fim de julho. Ou seja, os meses mais recentes - justamente o periodo de
# teste - ficam sem irradiancia horaria.
#
# Efeito medido nesta base (Cascavel, corte em 2025-08-01):
#     linhas COM dado horario : R2 = 0,816   MAE = 304 W
#     linhas SEM dado horario : R2 = -0,864  MAE = 922 W
# O modelo despenca onde a variavel some. Com dado horario disponivel ele e
# melhor que so com dado diario (0,816 contra 0,801); sem o dado, e muito pior.
#
# Por isso: se a cobertura horaria no periodo de teste for baixa, o script
# descarta as variaveis horarias automaticamente e usa apenas as diarias.

cob_treino = 1 - treino['kc_horario'].isna().mean() if 'kc_horario' in treino else 0.0
cob_teste  = 1 - teste['kc_horario'].isna().mean()  if 'kc_horario' in teste  else 0.0
print('\nCobertura da meteorologia horaria: treino %.1f %%   teste %.1f %%'
      % (100 * cob_treino, 100 * cob_teste))

if USAR_HORARIA == 'auto':
    usar_h = cob_teste >= 0.90
    if not usar_h:
        print('   AVISO: cobertura horaria de apenas %.1f %% no periodo de teste.' % (100 * cob_teste))
        print('   As variaveis horarias serao DESCARTADAS (USAR_HORARIA = "auto").')
        print('   Para forcar o uso, defina USAR_HORARIA = True; para sempre ignorar, False.')
    else:
        print('   Cobertura suficiente: as variaveis horarias serao usadas.')
else:
    usar_h = bool(USAR_HORARIA)
    print('   USAR_HORARIA definido manualmente como %s.' % usar_h)

if not usar_h:
    variaveis = [v for v in variaveis if v not in var_horaria]
    print('   Variaveis em uso agora: %d' % len(variaveis))

X_train, y_train = treino[variaveis], treino[alvo]
X_test,  y_test  = teste[variaveis],  teste[alvo]

pot_nominal_W = dados['pot_nominal_kWp'].median() * 1000


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 5. MODELOS

modelos = {
    # Unico modelo mantido apos a comparacao das 13 alternativas testadas no
    # Projeto_solo (ver o cabecalho). Parametros padrao da biblioteca; a unica
    # coisa fixada e random_state, para o resultado ser reproduzivel.
    'Media (referencia)'   : DummyRegressor(strategy='mean'),
    'HistGradientBoosting' : HistGradientBoostingRegressor(random_state=SEED),
}


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 6. TREINAR E AVALIAR

resultados = []
previsoes  = {}

print('\n' + '=' * 78)
print('%-24s %8s %9s %9s %8s %7s' % ('MODELO', 'R2', 'MAE (W)', 'RMSE (W)', 'MAE %', 'seg'))
print('=' * 78)

for nome, modelo in modelos.items():
    t0 = time.time()
    modelo.fit(X_train, y_train)
    y_pred = np.clip(modelo.predict(X_test), 0, None)
    dt = time.time() - t0

    r2   = r2_score(y_test, y_pred)
    mae  = mean_absolute_error(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))

    previsoes[nome] = y_pred
    resultados.append({'modelo': nome, 'R2': r2, 'MAE_W': mae, 'RMSE_W': rmse,
                       'MAE_pct_nominal': 100 * mae / pot_nominal_W, 'tempo_s': dt})
    print('%-24s %8.4f %9.1f %9.1f %7.2f%% %7.1f' %
          (nome, r2, mae, rmse, 100 * mae / pot_nominal_W, dt))

print('=' * 78)
res = pd.DataFrame(resultados).sort_values('R2', ascending=False).reset_index(drop=True)
res.to_csv(os.path.join(PASTA_SAIDA, 'metricas_%s.csv' % USINA), index=False,
           sep=';', decimal=',', encoding='utf-8-sig')

melhor = res.iloc[0]['modelo']
print('\nMelhor modelo: %s' % melhor)


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 7. AGREGACAO DIARIA
#
# Os erros de 5 minutos sao em boa parte independentes e se cancelam ao somar o
# dia. Se o uso final for energia diaria (e nao potencia instantanea), este e o
# numero que interessa.

teste_d = teste.copy()
teste_d['previsto'] = previsoes[melhor]
diario = teste_d.groupby(teste_d['data_hora'].dt.date).agg(
    real_kWh     = (alvo,       lambda s: s.sum() * 5 / 60 / 1000),
    previsto_kWh = ('previsto', lambda s: s.sum() * 5 / 60 / 1000))

r2_d  = r2_score(diario['real_kWh'], diario['previsto_kWh'])
mae_d = mean_absolute_error(diario['real_kWh'], diario['previsto_kWh'])
print('\nAgregado por dia (%d dias): R2 = %.4f   MAE = %.2f kWh (%.1f %% da media diaria de %.2f kWh)'
      % (len(diario), r2_d, mae_d, 100 * mae_d / diario['real_kWh'].mean(), diario['real_kWh'].mean()))
diario.to_csv(os.path.join(PASTA_SAIDA, 'previsao_diaria_%s.csv' % USINA),
              sep=';', decimal=',', encoding='utf-8-sig')


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 8. VALIDACAO CRUZADA AGRUPADA POR DIA
#
# Demonstra por que o sorteio aleatorio engana: o GroupKFold mantem cada dia
# inteiro de um lado so da divisao.

print('\nValidacao cruzada (5 pastas, agrupadas por dia) - %s:' % melhor)
grupos = treino['data_hora'].dt.normalize()
gkf = GroupKFold(n_splits=5)
notas = []
for i, (itr, ite) in enumerate(gkf.split(X_train, y_train, grupos), start=1):
    m = modelos[melhor]
    m.fit(X_train.iloc[itr], y_train.iloc[itr])
    p = np.clip(m.predict(X_train.iloc[ite]), 0, None)
    notas.append(r2_score(y_train.iloc[ite], p))
    print('   pasta %d: R2 = %.4f' % (i, notas[-1]))
print('   media: R2 = %.4f (desvio %.4f)' % (np.mean(notas), np.std(notas)))
print('   teste no periodo futuro: R2 = %.4f' % res.iloc[0]['R2'])

# reajusta no treino completo para os graficos
modelos[melhor].fit(X_train, y_train)


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 9. GRAFICOS

sns.set_style('whitegrid')
y_pred = previsoes[melhor]

# --- 9.1 comparacao dos modelos ---
fig, ax = plt.subplots(1, 2, figsize=(13, 4.5))
ax[0].barh(res['modelo'][::-1], res['R2'][::-1], color='#2a78d6')
ax[0].set_xlabel('R2 no periodo de teste'); ax[0].set_xlim(0, 1)
ax[0].set_title('Desempenho por modelo')
for i, v in enumerate(res['R2'][::-1]):
    ax[0].text(v + 0.01, i, '%.3f' % v, va='center', fontsize=9)
ax[1].barh(res['modelo'][::-1], res['MAE_W'][::-1], color='#eb6834')
ax[1].set_xlabel('MAE (W)'); ax[1].set_title('Erro absoluto medio')
plt.tight_layout()
plt.savefig(os.path.join(PASTA_SAIDA, 'comparacao_modelos_%s.png' % USINA), dpi=130)
plt.show()

# --- 9.2 previsto x real ---
fig, ax = plt.subplots(1, 3, figsize=(15, 4.4))
passo = max(1, len(y_test) // 20000)
ax[0].scatter(y_pred[::passo], y_test.values[::passo], s=4, alpha=0.25, color='#2a78d6')
lim = [0, max(y_test.max(), y_pred.max()) * 1.03]
ax[0].plot(lim, lim, 'k--', lw=1.2); ax[0].set_xlim(lim); ax[0].set_ylim(lim)
ax[0].set_xlabel('Previsto (W)'); ax[0].set_ylabel('Real (W)')
ax[0].set_title('%s - 5 min (R2 %.3f)' % (melhor, res.iloc[0]['R2']))

ax[1].scatter(diario['previsto_kWh'], diario['real_kWh'], s=16, alpha=0.6, color='#1baf7a')
lim2 = [0, max(diario.max()) * 1.03]
ax[1].plot(lim2, lim2, 'k--', lw=1.2); ax[1].set_xlim(lim2); ax[1].set_ylim(lim2)
ax[1].set_xlabel('Previsto (kWh/dia)'); ax[1].set_ylabel('Real (kWh/dia)')
ax[1].set_title('Agregado por dia (R2 %.3f)' % r2_d)

residuo = y_test.values - y_pred
ax[2].hist(residuo, bins=80, color='#b4690e', alpha=0.85)
ax[2].axvline(0, color='k', lw=1.2)
ax[2].set_xlabel('Residuo: real - previsto (W)'); ax[2].set_ylabel('Registros')
ax[2].set_title('Vies medio: %+.1f W' % residuo.mean())
plt.tight_layout()
plt.savefig(os.path.join(PASTA_SAIDA, 'previsto_x_real_%s.png' % USINA), dpi=130)
plt.show()

# --- 9.3 erro por condicao de ceu e por hora ---
teste_g = teste.copy(); teste_g['erro_abs'] = np.abs(residuo)
fig, ax = plt.subplots(1, 2, figsize=(13, 4.3))
faixas = pd.cut(teste_g['kt_diario'], [0, .3, .45, .6, .7, .85])
g1 = teste_g.groupby(faixas, observed=True).agg(erro=('erro_abs', 'mean'), pot=(alvo, 'mean'))
ax[0].bar(range(len(g1)), 100 * g1['erro'] / g1['pot'], color='#e34948')
ax[0].set_xticks(range(len(g1)))
ax[0].set_xticklabels([str(i) for i in g1.index], rotation=25, ha='right', fontsize=8)
ax[0].set_ylabel('MAE em % da potencia media'); ax[0].set_xlabel('indice de claridade diario (Kt)')
ax[0].set_title('O erro se concentra nos dias nublados')

g2 = teste_g.groupby(teste_g['hora_solar'].round()).agg(erro=('erro_abs', 'mean'))
ax[1].plot(g2.index, g2['erro'], marker='o', color='#2a78d6')
ax[1].set_xlabel('hora solar'); ax[1].set_ylabel('MAE (W)')
ax[1].set_title('Erro ao longo do dia')
plt.tight_layout()
plt.savefig(os.path.join(PASTA_SAIDA, 'erro_por_condicao_%s.png' % USINA), dpi=130)
plt.show()

# --- 9.4 importancia das variaveis (permutacao) ---
print('\nCalculando importancia por permutacao (pode demorar ~1 min)...')
amostra = teste.sample(min(8000, len(teste)), random_state=42)
imp = permutation_importance(modelos[melhor], amostra[variaveis], amostra[alvo],
                             n_repeats=5, random_state=42, scoring='r2', n_jobs=1)
ordem = np.argsort(imp.importances_mean)
fig, ax = plt.subplots(figsize=(8, 0.34 * len(variaveis) + 2))
ax.barh(np.array(variaveis)[ordem], imp.importances_mean[ordem],
        xerr=imp.importances_std[ordem], color='#4a3aa7')
ax.set_xlabel('queda no R2 ao embaralhar a variavel')
ax.set_title('Importancia das variaveis - %s' % melhor)
plt.tight_layout()
plt.savefig(os.path.join(PASTA_SAIDA, 'importancia_%s.png' % USINA), dpi=130)
plt.show()

pd.DataFrame({'variavel': variaveis,
              'importancia': imp.importances_mean,
              'desvio': imp.importances_std}).sort_values('importancia', ascending=False) \
  .to_csv(os.path.join(PASTA_SAIDA, 'importancia_%s.csv' % USINA),
          index=False, sep=';', decimal=',', encoding='utf-8-sig')


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# 10. RESUMO

print('\n' + '=' * 78)
print('RESUMO - usina %s' % USINA)
print('=' * 78)
print(res.to_string(index=False))
print('\nArquivos gravados em "%s":' % PASTA_SAIDA)
for f in sorted(os.listdir(PASTA_SAIDA)):
    print('   %s' % f)
print('''
Leitura dos numeros:
  * O modelo "Media (referencia)" e o piso: qualquer modelo util tem de superá-lo.
  * MAE % e o erro medio como fracao da potencia nominal da usina.
  * O R2 de 5 minutos e sempre pior que o diario, porque a meteorologia da NASA
    POWER e horaria/diaria e nao sabe em que minuto exato passou a nuvem.
  * Se o R2 da validacao cruzada for muito maior que o do periodo futuro, a
    usina mudou de estado (sujeira, falha, limpeza) entre treino e teste.
''')
