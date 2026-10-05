import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report, ConfusionMatrixDisplay, roc_curve, auc
from imblearn.under_sampling import RandomUnderSampler
from sklearn.preprocessing import MinMaxScaler, StandardScaler, RobustScaler



###############################################################################
###############################################################################
###############################################################################
###############################################################################
# Carregar o arquivo Excel
caminho_arquivo = r'C:\Users\L08741\OneDrive - Lactec\Documentos\2025_2\Projeto_solo\codigos\Base de Dados2.xlsx'

# Ler a primeira planilha do arquivo
dados = pd.read_excel(
    caminho_arquivo,
    parse_dates=['Time_15min'],
    index_col='Time_15min'
)


# Salvar os dados para cada um dos 4 painéis de teste
painel_1 = dados.copy()
painel_2 = dados.copy()
painel_3 = dados.copy()
painel_4 = dados.copy()


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# Determinar a potência de cada painel
def calcular_potencia(tensao, corrente):
    potencia = tensao * corrente
    return potencia

# Calcular a potência de todos os paineis e salvar estes dados em cada arquivo 
painel_1['Pot1_W'] = calcular_potencia(painel_1['Panel_1 - voltage'], painel_1['Panel_1 - current'])
painel_2['Pot2_W'] = calcular_potencia(painel_2['Panel_2 - voltage'], painel_2['Panel_2 - current'])
painel_3['Pot3_W'] = calcular_potencia(painel_3['Panel_3 - voltage'], painel_3['Panel_3 - current'])
painel_4['Pot4_W'] = calcular_potencia(painel_4['Panel_4 - voltage'], painel_4['Panel_4 - current'])


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# Remover colunas dos painéis
colunas_comuns_remover = [
    'AVGBAT', 'AVGGHI1', 'AVGGHI2', 'AVGORV', 'AVGTEMP', 'AVGUMID', 'AVGVEL', 'BAT',
    'ModbusID', 'LibraryIndex', 'TotalEnergy_kWh', 'Power_W',
    'ACVoltageA_V', 'ACVoltageB_V', 'ACVoltageC_V', 'PowerLimit_%',
    'Vrms_V', 'DCCount', 'Vdc1_V', 'Vdc2_V', 'Vdc3_V', 'Vdc4_V',
    'Idc1_A', 'Idc2_A', 'Idc3_A', 'Idc4_A'] #'Time_15min',

colunas_remover_painel_1 = colunas_comuns_remover + [
    'Panel_1 - temperature2',
    'Panel_2 - current', 'Panel_2 - temperature1', 'Panel_2 - temperature2', 'Panel_2 - voltage',
    'Panel_3 - current', 'Panel_3 - temperature1', 'Panel_3 - temperature2', 'Panel_3 - voltage',
    'Panel_4 - current', 'Panel_4 - temperature1', 'Panel_4 - temperature2', 'Panel_4 - voltage']

colunas_remover_painel_2 = colunas_comuns_remover + [
    'Panel_2 - temperature2',
    'Panel_1 - current', 'Panel_1 - temperature1', 'Panel_1 - temperature2', 'Panel_1 - voltage',
    'Panel_3 - current', 'Panel_3 - temperature1', 'Panel_3 - temperature2', 'Panel_3 - voltage',
    'Panel_4 - current', 'Panel_4 - temperature1', 'Panel_4 - temperature2', 'Panel_4 - voltage']

colunas_remover_painel_3 = colunas_comuns_remover + [
    'Panel_3 - temperature2',
    'Panel_1 - current', 'Panel_1 - temperature1', 'Panel_1 - temperature2', 'Panel_1 - voltage',
    'Panel_2 - current', 'Panel_2 - temperature1', 'Panel_2 - temperature2', 'Panel_2 - voltage',
    'Panel_4 - current', 'Panel_4 - temperature1', 'Panel_4 - temperature2', 'Panel_4 - voltage']

colunas_remover_painel_4 = colunas_comuns_remover + [
    'Panel_4 - temperature2',
    'Panel_1 - current', 'Panel_1 - temperature1', 'Panel_1 - temperature2', 'Panel_1 - voltage',
    'Panel_2 - current', 'Panel_2 - temperature1', 'Panel_2 - temperature2', 'Panel_2 - voltage',
    'Panel_3 - current', 'Panel_3 - temperature1', 'Panel_3 - temperature2', 'Panel_3 - voltage']

painel_1 = painel_1.drop(columns=colunas_remover_painel_1)
painel_2 = painel_2.drop(columns=colunas_remover_painel_2)
painel_3 = painel_3.drop(columns=colunas_remover_painel_3)
painel_4 = painel_4.drop(columns=colunas_remover_painel_4)

del colunas_comuns_remover, colunas_remover_painel_1, colunas_remover_painel_2, colunas_remover_painel_3, colunas_remover_painel_4

###############################################################################
###############################################################################
###############################################################################
###############################################################################
# Converter a coluna Time_15min para datetime (necessário para usar .dt.time)
#for df in [painel_1, painel_2, painel_3, painel_4]:
 #   df['Time_15min'] = pd.to_datetime(df['Time_15min'])

# Adicionar coluna de rótulo fixa para painel_3 (referência)
painel_3['Rotulo'] = 0

# Limiar de queda de corrente (5%)
q_cor = 0.95

# Horário de interesse
hora_ini = pd.to_datetime("10:00:00").time()
hora_fim = pd.to_datetime("15:00:00").time()

# Função para aplicar rotulagem com base em corrente e horário
def rotular(painel, corrente_col):
    return np.where(
        (painel[corrente_col] < q_cor * painel_3['Panel_3 - current']) &
        (painel.index.time >= hora_ini) &
        (painel.index.time <= hora_fim),
        1, 0)

# Aplicar rótulo aos demais paineis
painel_1['Rotulo'] = rotular(painel_1, 'Panel_1 - current')
painel_2['Rotulo'] = rotular(painel_2, 'Panel_2 - current')
painel_4['Rotulo'] = rotular(painel_4, 'Panel_4 - current')


###############################################################################
###############################################################################
###############################################################################
###############################################################################
# Agrupar todos os paineis em um único dataframe
###############################################################################
# Renomear colunas para padronizar
painel_1 = painel_1.rename(columns={'Panel_1 - voltage': 'Voltage_V', 'Panel_1 - current': 'Current_A', 'Panel_1 - temperature1': 'Temperature_C', 'Pot1_W': 'Pot_W'})
painel_2 = painel_2.rename(columns={'Panel_2 - voltage': 'Voltage_V', 'Panel_2 - current': 'Current_A', 'Panel_2 - temperature1': 'Temperature_C', 'Pot2_W': 'Pot_W'})
painel_3 = painel_3.rename(columns={'Panel_3 - voltage': 'Voltage_V', 'Panel_3 - current': 'Current_A', 'Panel_3 - temperature1': 'Temperature_C', 'Pot3_W': 'Pot_W'})
painel_4 = painel_4.rename(columns={'Panel_4 - voltage': 'Voltage_V', 'Panel_4 - current': 'Current_A', 'Panel_4 - temperature1': 'Temperature_C', 'Pot4_W': 'Pot_W'})

###############################################################################
# Agrupar os dados dos paineis um abaixo do outro
dados_geral = pd.concat([painel_1, painel_2, painel_3, painel_4], ignore_index=True)

'''dados_geral['Apparent_Power_VA'] = dados_geral['Voltage_V'] * dados_geral['Current_A']
dados_geral['Power_Factor'] = dados_geral['Pot_W'] / dados_geral['Apparent_Power_VA']
df_chuva_diaria = dados['Chuva_mm'].resample('D').sum().to_frame()
LIMIAR_CHUVA_LIMPANTE = 1.0 
df_chuva_diaria['Chuva_Limpante'] = (df_chuva_diaria['Chuva_mm'] > LIMIAR_CHUVA_LIMPANTE).astype(int)
grupos_sem_chuva = df_chuva_diaria['Chuva_Limpante'].cumsum()
df_chuva_diaria['Dias_Sem_Chuva'] = df_chuva_diaria.groupby(grupos_sem_chuva).cumcount()'''
###############################################################################
###############################################################################
###############################################################################
###############################################################################
# Modelo de árvore de decisão
# Definir variáveis independentes (features) e dependente (target)
#X = dados_geral[['GHI1', 'GHI2', 'ORV', 'TEMP.', 'UMID.', 'VEL', 'Voltage_V', 'Temperature_C', 'Pot_W']]
X = dados_geral[['GHI1', 'GHI2','ORV', 'TEMP.', 'UMID.', 'VEL','Chuva_mm']]
#X = dados_geral[['Voltage_V', 'Current_A', 'Pot_W']]
y = dados_geral['Rotulo']

# Balanceamento dos dados
rus = RandomUnderSampler(random_state=42)
X, y = rus.fit_resample(X, y)

# Dividir em conjunto de treino e teste
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Instanciar e treinar o modelo
HG_clf = HistGradientBoostingClassifier(random_state=42)
HG_clf.fit(X_train, y_train)


# Fazer previsões probabilísticas com limiar 0.6 para 0.939

predict_proba = HG_clf.predict_proba(X_test)[:, 1]
y_pred = (predict_proba >= 0.5).astype(int)
  
# Avaliar o modelo
print("\nAcurácia:", accuracy_score(y_test, y_pred))
print("\nMatriz de confusão:\n", confusion_matrix(y_test, y_pred))
print("\nRelatório de classificação:\n", classification_report(y_test, y_pred))

###############################################################################
# Plotar a matriz de confusão
cm = confusion_matrix(y_test, y_pred)
ConfusionMatrixDisplay(cm, display_labels=["Painel Limpo (0)", "Painel Sujo (1)"]).plot(cmap='Blues')
plt.title('Matriz de Confusão - HistGrad com Probabilidade')
plt.show()

###############################################################################
# Plotar a curva ROC
# Calcular curva ROC
fpr, tpr, thresholds = roc_curve(y_test, predict_proba)
roc_auc = auc(fpr, tpr)

# Plotar
plt.figure()
plt.plot(fpr, tpr, color='darkorange', lw=2, label='Curva ROC (área = %0.2f)' % roc_auc)
plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('Taxa de Falsos Positivos (1 - Especificidade)')
plt.ylabel('Taxa de Verdadeiros Positivos (Sensibilidade)')
plt.title('Curva ROC - HistGrad')
plt.legend(loc="lower right")
plt.grid(True)
plt.show()

