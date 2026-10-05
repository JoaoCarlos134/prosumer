# -*- coding: utf-8 -*-
###############################################################################
# PLANILHA DE TARIFAS - COPEL-DIS
#
# Monta um XLSX unico, explicado, com a base tarifaria das duas usinas:
#
#   Explicacao      como a conta e montada, de onde vem cada numero e o que falta
#   Vigencia_atual  os valores em vigor, ja com impostos e bandeira
#   Tarifa_mensal   serie mes a mes da tarifa cheia, 2019 -> hoje
#   Historico       TUSD e TE homologadas por vigencia, 2010 -> 2027
#   Bandeiras       bandeira acionada mes a mes e os valores de cada uma
#   Componentes     abertura da TUSD e da TE do B1 (inclui o Fio B)
#   Parametros      ICMS, PIS/COFINS e enquadramento de cada UC
#   HOMER           os campos do componente Grid, lado a lado para as duas usinas
#
# Le os CSV de ../dados/, gerados por baixa_tarifas_aneel.py.
#
# Requisitos: pandas, openpyxl
###############################################################################

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

###############################################################################
# CONFIGURACAO
###############################################################################

pasta_tarifas = Path(__file__).resolve().parents[1] / 'dados'
caminho_saida = Path(__file__).resolve().parents[1] / 'Tarifas_Copel.xlsx'

INICIO_SERIE = '2019-01'          # primeira competencia da aba Tarifa_mensal
PIS_COFINS_PCT = 9.25             # ver aba Parametros

AZUL = 'FF1F4E79'
CINZA = 'FFF2F2F2'
BORDA = Border(bottom=Side(style='thin', color='FFBFBFBF'))

###############################################################################
# LEITURA
###############################################################################

hist = pd.read_csv(pasta_tarifas / 'copel_tarifas_historico.csv', encoding='utf-8-sig')
band_mes = pd.read_csv(pasta_tarifas / 'bandeiras_mensal.csv', encoding='utf-8-sig')
band_val = pd.read_csv(pasta_tarifas / 'bandeiras_adicional.csv', encoding='utf-8-sig')
comp = pd.read_csv(pasta_tarifas / 'copel_componentes_b1.csv', encoding='utf-8-sig')
fisc = pd.read_csv(pasta_tarifas / 'parametros_fiscais.csv', encoding='utf-8-sig')
ucs = pd.read_csv(pasta_tarifas / 'parametros_usinas.csv', encoding='utf-8-sig')

icms = fisc[fisc.tributo == 'ICMS'].copy()
icms['vigencia_ini'] = pd.to_datetime(icms.vigencia_ini)
icms = icms.sort_values('vigencia_ini').reset_index(drop=True)

b1 = hist[(hist.subgrupo == 'B1') & (hist.modalidade == 'Convencional')].copy()
b1['vigencia_ini'] = pd.to_datetime(b1.vigencia_ini)
b1 = b1.sort_values('vigencia_ini').reset_index(drop=True)

VIG_ATUAL = hist.vigencia_ini.max()
REH_ATUAL = hist.loc[hist.vigencia_ini == VIG_ATUAL, 'resolucao'].iloc[0]

###############################################################################
# SERIE MENSAL DA TARIFA CHEIA
###############################################################################


def monta_mensal():
    comp_idx = pd.period_range(INICIO_SERIE, band_mes.competencia.max(), freq='M')
    m = pd.DataFrame({'competencia': comp_idx.astype(str)})
    m['_dia'] = pd.to_datetime(m.competencia + '-15')   # meio do mes decide a vigencia

    m = pd.merge_asof(m.sort_values('_dia'),
                      b1[['vigencia_ini', 'tusd_RS_MWh', 'te_RS_MWh', 'total_RS_MWh', 'resolucao']],
                      left_on='_dia', right_on='vigencia_ini', direction='backward')
    m = pd.merge_asof(m, icms[['vigencia_ini', 'aliquota_pct']].rename(
                          columns={'vigencia_ini': '_vi', 'aliquota_pct': 'icms_pct'}),
                      left_on='_dia', right_on='_vi', direction='backward')

    b = band_mes.set_index('competencia')
    m['bandeira'] = m.competencia.map(b.bandeira)
    m['adic_bandeira_RS_MWh'] = m.competencia.map(b.adicional_RS_MWh).fillna(0.0)

    m['pis_cofins_pct'] = PIS_COFINS_PCT
    fator = 1.0 / (1.0 - m.icms_pct / 100.0 - m.pis_cofins_pct / 100.0)
    m['fator_impostos'] = fator.round(4)
    m['tarifa_sem_impostos_RS_kWh'] = (m.total_RS_MWh / 1000).round(5)
    m['tarifa_cheia_RS_kWh'] = ((m.total_RS_MWh + m.adic_bandeira_RS_MWh) / 1000 * fator).round(5)
    return m[['competencia', 'tusd_RS_MWh', 'te_RS_MWh', 'total_RS_MWh',
              'tarifa_sem_impostos_RS_kWh', 'bandeira', 'adic_bandeira_RS_MWh',
              'icms_pct', 'pis_cofins_pct', 'fator_impostos',
              'tarifa_cheia_RS_kWh', 'resolucao']]


mensal = monta_mensal()
TARIFA_HOJE = float(mensal.tarifa_cheia_RS_kWh.iloc[-1])
BAND_HOJE = str(mensal.bandeira.iloc[-1])
ICMS_HOJE = float(mensal.icms_pct.iloc[-1])

###############################################################################
# FORMATACAO
###############################################################################


def escreve(wb, nome, df, larguras=None, formatos=None, congela='A2'):
    ws = wb.create_sheet(nome)
    ws.append(list(df.columns))
    for c in ws[1]:
        c.font = Font(bold=True, color='FFFFFFFF')
        c.fill = PatternFill('solid', fgColor=AZUL)
        c.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[1].height = 30
    for linha in df.itertuples(index=False, name=None):
        ws.append(list(linha))
    for i, col in enumerate(df.columns, start=1):
        letra = get_column_letter(i)
        ws.column_dimensions[letra].width = (larguras or {}).get(col, max(12, len(str(col)) + 2))
        if formatos and col in formatos:
            for c in ws[letra][1:]:
                c.number_format = formatos[col]
    for j, linha in enumerate(ws.iter_rows(min_row=2), start=2):
        if j % 2 == 0:
            for c in linha:
                c.fill = PatternFill('solid', fgColor=CINZA)
    ws.freeze_panes = congela
    ws.auto_filter.ref = 'A1:%s%d' % (get_column_letter(len(df.columns)), len(df) + 1)
    return ws


def aba_explicacao(wb):
    ws = wb.create_sheet('Explicacao', 0)
    ws.column_dimensions['A'].width = 3
    ws.column_dimensions['B'].width = 34
    ws.column_dimensions['C'].width = 96
    ws.sheet_view.showGridLines = False

    def titulo(txt):
        ws.append([]); ws.append(['', txt])
        c = ws.cell(row=ws.max_row, column=2)
        c.font = Font(bold=True, size=13, color=AZUL)

    def item(rotulo, texto):
        ws.append(['', rotulo, texto])
        r = ws.max_row
        ws.cell(row=r, column=2).font = Font(bold=True)
        ws.cell(row=r, column=2).alignment = Alignment(vertical='top')
        ws.cell(row=r, column=3).alignment = Alignment(wrap_text=True, vertical='top')
        ws.cell(row=r, column=2).border = BORDA
        ws.cell(row=r, column=3).border = BORDA
        ws.row_dimensions[r].height = max(15, 13 * (1 + len(texto) // 95))

    ws.append(['', 'TARIFAS DE ENERGIA - COPEL-DIS (PARANA)'])
    ws.cell(row=1, column=2).font = Font(bold=True, size=16, color=AZUL)
    ws.append(['', 'Base tarifaria das usinas de Cascavel (Usina Cascavel) e Curitiba (Usina Curitiba)'])
    ws.cell(row=2, column=2).font = Font(italic=True, size=11)

    titulo('1. DE ONDE VEM ESTE DADO')
    item('Fonte', 'API de dados abertos da ANEEL (dadosabertos.aneel.gov.br), conjuntos '
                  '"Tarifas de aplicacao das distribuidoras", "Componentes tarifarias" e '
                  '"Bandeiras tarifarias". Nao vem de site de terceiro nem de calculadora online.')
    item('Vigencia atual', '%s a %s, conforme %s.'
         % (VIG_ATUAL, hist.loc[hist.vigencia_ini == VIG_ATUAL, 'vigencia_fim'].iloc[0], REH_ATUAL))
    item('Reajuste', 'A revisao tarifaria de 2026 teve efeito medio de +20,51%. '
                     'Em baixa tensao o reajuste medio foi de +19,85%.')
    item('Por que nao o PDF', 'Os PDF de resolucao no www2.aneel.gov.br estao atras de Cloudflare e '
                              'devolvem 403 para qualquer script. A API serve a mesma informacao.')
    item('Como refazer', 'analise/tarifas/scripts/baixa_tarifas_aneel.py (precisa de rede). '
                         'Esta planilha sai de monta_planilha_tarifas.py.')

    titulo('2. COMO A TARIFA CHEIA E MONTADA')
    item('Componentes', 'A tarifa homologada tem duas partes: TUSD, que paga o uso da rede, e TE, '
                        'que paga a energia. As duas vem em R$/MWh e SEM impostos.')
    item('Formula', 'tarifa_cheia [R$/kWh]  =  (TUSD + TE + adicional_bandeira) / 1000  x  '
                    '1 / (1 - ICMS - PIS/COFINS)')
    item('Impostos "por dentro"', 'ICMS e PIS/COFINS compoem a propria base de calculo. Por isso se '
                                  'divide por (1 - aliquotas) em vez de multiplicar por (1 + aliquotas). '
                                  'Com ICMS 19%% e PIS/COFINS 9,25%% o fator e %.4f.'
         % (1 / (1 - ICMS_HOJE / 100 - PIS_COFINS_PCT / 100)))
    item('Conta de hoje', 'TUSD %.2f + TE %.2f = %.2f R$/MWh, bandeira %s, ICMS %.0f%%  ->  '
                          'R$ %.4f/kWh.'
         % (b1.tusd_RS_MWh.iloc[-1], b1.te_RS_MWh.iloc[-1], b1.total_RS_MWh.iloc[-1],
            BAND_HOJE, ICMS_HOJE, TARIFA_HOJE))
    item('Fora do R$/kWh', 'Custo de disponibilidade e COSIP nao entram na tarifa: sao encargos fixos '
                           'mensais. Ver aba Parametros e aba HOMER.')

    titulo('3. O QUE MUDOU NO PERIODO DOS DADOS')
    item('ICMS mudou duas vezes', '29% ate 22/06/2022; 18% de 23/06/2022 a 17/03/2024 (LC 194/2022, '
                                  'que tornou energia bem essencial); 19% desde 18/03/2024 '
                                  '(Decreto PR 5.143/2023). Quem usa aliquota unica erra 10 pontos '
                                  'no comeco da serie do Curitiba.')
    item('Bandeiras', 'O adicional muda todo mes. A aba Bandeiras tem o historico desde jan/2015. '
                      'Os valores de cada bandeira mudam por resolucao: os atuais valem desde '
                      '01/04/2024 (REH 3.306/2024).')
    item('Lei 14.300', 'As duas usinas conectaram antes de 07/01/2023 (Cascavel 07/2019, Curitiba '
                       '07/2021), entao tem direito adquirido: compensacao integral, SEM pagar Fio B '
                       'sobre a energia injetada, ate 31/12/2045. O Fio B esta na aba Componentes '
                       'apenas como referencia, caso se queira simular uma usina nova.')

    titulo('4. AFERICAO CONTRA FATURA REAL')
    item('O teste', '2018 e o unico ano de Cascavel sem geracao. Ali "pago / consumo" e a tarifa de '
                    'varejo de verdade, sem o efeito da compensacao.')
    item('Resultado', 'Modelo 0,8062 R$/kWh contra 0,8457 medido na fatura, media de 12 meses. '
                      'O residuo de 0,0395 R$/kWh sobre ~250 kWh/mes equivale a R$ 10,62/mes, '
                      'que e a ordem de grandeza da COSIP. A parte variavel fecha.')
    item('Limite do teste', 'De 2019 em diante essa conferencia nao vale mais: com a compensacao, '
                            '"pago/consumo" mede o piso da fatura e nao a tarifa.')
    item('Mes de virada', 'A aba Tarifa_mensal decide a vigencia pelo dia 15 do mes. Como o reajuste '
                          'cai sempre em 24/06, o mes de junho fica com a tarifa antiga inteira. '
                          'A serie de 5 min nas planilhas das usinas nao tem essa aproximacao: la a '
                          'tarifa e resolvida dia a dia.')

    titulo('5. O QUE AINDA FALTA')
    item('COSIP', 'Contribuicao municipal de iluminacao publica. Nao e publicada pela ANEEL: cada '
                  'municipio define por lei. Tem de sair de uma fatura de Cascavel e de Curitiba. '
                  'Para Cascavel da para partir dos R$ 10,62/mes de 2018, corrigidos.')
    item('PIS/COFINS efetivo', 'Aqui esta o nominal, 1,65 + 7,60 = 9,25%. A Copel apura a aliquota '
                               'efetiva mes a mes e ela costuma ser MENOR. E o unico parametro '
                               'realmente frouxo desta planilha: conferir na fatura e reajustar. '
                               'O teste de 2018 nao consegue separa-lo da COSIP.')
    item('Curva de carga', 'O HOMER precisa do consumo, e so ha geracao. Cascavel tem consumo mensal '
                           'nas faturas ate dez/2024; Curitiba nao tem nenhum dado de consumo.')

    titulo('6. AS ABAS')
    for nome, desc in [
        ('Vigencia_atual', 'Os valores em vigor, B1 e B3, convencional e branca, ja com o R$/kWh '
                           'com impostos calculado.'),
        ('Tarifa_mensal', 'Serie mes a mes de %s ate %s: tarifa homologada, bandeira do mes, ICMS '
                          'da epoca e a tarifa cheia resultante. E esta coluna que aparece por linha '
                          'nas planilhas de 5 min.' % (mensal.competencia.iloc[0], mensal.competencia.iloc[-1])),
        ('Historico', 'TUSD e TE homologadas por vigencia, de 2010 a 2027. Sem impostos.'),
        ('Bandeiras', 'Bandeira acionada mes a mes e o valor homologado de cada bandeira.'),
        ('Componentes', 'Abertura da TUSD e da TE do B1 residencial. Inclui o TUSD_FioB.'),
        ('Parametros', 'ICMS por periodo, PIS/COFINS e o enquadramento de cada unidade consumidora.'),
        ('HOMER', 'Os campos do componente Grid, com o numero pronto, para as duas usinas.'),
    ]:
        item(nome, desc)


def aba_homer(wb):
    linhas = []
    for _, u in ucs.iterrows():
        disp = int(u.disponibilidade_kWh_mes)
        linhas.append(dict(
            campo='Grid power price', usina=u.usina, valor=round(TARIFA_HOJE, 4), unidade='R$/kWh',
            observacao='Tarifa cheia: TUSD+TE + bandeira %s, com ICMS %.0f%% e PIS/COFINS %.2f%%'
                       % (BAND_HOJE, ICMS_HOJE, PIS_COFINS_PCT)))
        linhas.append(dict(
            campo='Grid sellback rate', usina=u.usina, valor=round(TARIFA_HOJE, 4), unidade='R$/kWh',
            observacao='Compensacao 1:1 em kWh. Direito adquirido da Lei 14.300 ate 31/12/2045.'))
        linhas.append(dict(
            campo='Net metering', usina=u.usina, valor='Sim', unidade='',
            observacao='Creditos em kWh, validade 60 meses. Nao ha pagamento por excedente.'))
        linhas.append(dict(
            campo='Grid demand rate', usina=u.usina, valor=0, unidade='R$/kW/mes',
            observacao='Grupo B nao tem cobranca de demanda'))
        linhas.append(dict(
            campo='Custo de disponibilidade', usina=u.usina, valor=disp, unidade='kWh/mes',
            observacao='Ligacao %s. Piso cobrado mesmo com a geracao zerando o consumo.' % u.ligacao))
        linhas.append(dict(
            campo='Custo de disponibilidade', usina=u.usina, valor=round(disp * TARIFA_HOJE, 2),
            unidade='R$/mes', observacao='%d kWh x %.4f R$/kWh' % (disp, TARIFA_HOJE)))
        linhas.append(dict(
            campo='COSIP / CIP', usina=u.usina, valor='A DEFINIR', unidade='R$/mes',
            observacao='Municipal, nao publicada pela ANEEL. Cascavel: partir de R$ 10,62/mes (2018).'))
        linhas.append(dict(
            campo='Fio B', usina=u.usina, valor='nao cobrado', unidade='',
            observacao='Conexao em %s, anterior a 07/01/2023.' % u.data_conexao))
        linhas.append(dict(
            campo='Fator de emissao da rede', usina=u.usina, valor='A DEFINIR', unidade='g CO2/kWh',
            observacao='Usar o fator medio do SIN publicado pelo MCTI.'))
    d = pd.DataFrame(linhas)[['usina', 'campo', 'valor', 'unidade', 'observacao']]
    escreve(wb, 'HOMER', d,
            larguras={'usina': 12, 'campo': 28, 'valor': 14, 'unidade': 12, 'observacao': 92})


###############################################################################
# MONTAGEM
###############################################################################

if __name__ == '__main__':
    wb = Workbook()
    wb.remove(wb.active)

    aba_explicacao(wb)

    atual = hist[hist.vigencia_ini == VIG_ATUAL].copy()
    fator_hoje = 1.0 / (1 - ICMS_HOJE / 100 - PIS_COFINS_PCT / 100)
    adic_hoje = float(mensal.adic_bandeira_RS_MWh.iloc[-1])
    atual['tarifa_sem_impostos_RS_kWh'] = (atual.total_RS_MWh / 1000).round(5)
    atual['tarifa_cheia_RS_kWh'] = ((atual.total_RS_MWh + adic_hoje) / 1000 * fator_hoje).round(5)
    escreve(wb, 'Vigencia_atual',
            atual[['subgrupo', 'modalidade', 'posto', 'tusd_RS_MWh', 'te_RS_MWh', 'total_RS_MWh',
                   'tarifa_sem_impostos_RS_kWh', 'tarifa_cheia_RS_kWh', 'vigencia_ini',
                   'vigencia_fim', 'resolucao']],
            larguras={'modalidade': 14, 'posto': 15, 'resolucao': 58,
                      'tarifa_sem_impostos_RS_kWh': 16, 'tarifa_cheia_RS_kWh': 16},
            formatos={'tusd_RS_MWh': '0.00', 'te_RS_MWh': '0.00', 'total_RS_MWh': '0.00',
                      'tarifa_sem_impostos_RS_kWh': '0.0000', 'tarifa_cheia_RS_kWh': '0.0000'})

    escreve(wb, 'Tarifa_mensal', mensal,
            larguras={'competencia': 13, 'bandeira': 13, 'resolucao': 58,
                      'tarifa_sem_impostos_RS_kWh': 16, 'tarifa_cheia_RS_kWh': 16,
                      'adic_bandeira_RS_MWh': 14, 'fator_impostos': 13},
            formatos={'tusd_RS_MWh': '0.00', 'te_RS_MWh': '0.00', 'total_RS_MWh': '0.00',
                      'adic_bandeira_RS_MWh': '0.00', 'icms_pct': '0.00', 'pis_cofins_pct': '0.00',
                      'fator_impostos': '0.0000', 'tarifa_sem_impostos_RS_kWh': '0.0000',
                      'tarifa_cheia_RS_kWh': '0.0000'})

    escreve(wb, 'Historico', hist,
            larguras={'modalidade': 14, 'posto': 15, 'resolucao': 58},
            formatos={'tusd_RS_MWh': '0.00', 'te_RS_MWh': '0.00', 'total_RS_MWh': '0.00'})

    band = band_mes.copy()
    band['adicional_RS_kWh'] = (band.adicional_RS_MWh / 1000).round(5)
    escreve(wb, 'Bandeiras', band,
            larguras={'competencia': 13, 'bandeira': 14, 'adicional_RS_MWh': 17,
                      'adicional_RS_kWh': 17},
            formatos={'adicional_RS_MWh': '0.00', 'adicional_RS_kWh': '0.00000'})
    ws = wb['Bandeiras']
    inicio = len(band) + 4
    ws.cell(row=inicio, column=1, value='Valores homologados de cada bandeira').font = Font(
        bold=True, color=AZUL)
    ws.cell(row=inicio + 1, column=1, value='vigencia_ini').font = Font(bold=True)
    ws.cell(row=inicio + 1, column=2, value='bandeira').font = Font(bold=True)
    ws.cell(row=inicio + 1, column=3, value='adicional_RS_MWh').font = Font(bold=True)
    ws.cell(row=inicio + 1, column=4, value='resolucao').font = Font(bold=True)
    for k, (_, r) in enumerate(band_val.iterrows()):
        ws.cell(row=inicio + 2 + k, column=1, value=r.vigencia_ini)
        ws.cell(row=inicio + 2 + k, column=2, value=r.bandeira)
        ws.cell(row=inicio + 2 + k, column=3, value=float(r.adicional_RS_MWh)).number_format = '0.00'
        ws.cell(row=inicio + 2 + k, column=4, value=r.resolucao)

    escreve(wb, 'Componentes', comp,
            larguras={'componente': 24, 'valor_RS_MWh': 16, 'resolucao': 58},
            formatos={'valor_RS_MWh': '0.0000'})

    par = pd.concat([
        fisc.assign(tabela='fiscal')[['tabela', 'vigencia_ini', 'vigencia_fim', 'tributo',
                                      'aliquota_pct', 'base', 'fonte']],
    ], ignore_index=True)
    escreve(wb, 'Parametros', par,
            larguras={'tabela': 10, 'tributo': 13, 'base': 13, 'fonte': 92},
            formatos={'aliquota_pct': '0.00'})
    ws = wb['Parametros']
    ini = len(par) + 4
    ws.cell(row=ini, column=1, value='Enquadramento das unidades consumidoras').font = Font(
        bold=True, color=AZUL)
    for j, c in enumerate(ucs.columns, start=1):
        ws.cell(row=ini + 1, column=j, value=c).font = Font(bold=True)
    for k, (_, r) in enumerate(ucs.iterrows()):
        for j, c in enumerate(ucs.columns, start=1):
            v = r[c]
            ws.cell(row=ini + 2 + k, column=j, value=None if pd.isna(v) else v)

    aba_homer(wb)

    wb.save(caminho_saida)
    print('OK  %s' % caminho_saida)
    print('    abas: %s' % ', '.join(wb.sheetnames))
    print('    tarifa cheia de hoje: R$ %.4f/kWh  (bandeira %s, ICMS %.0f%%)'
          % (TARIFA_HOJE, BAND_HOJE, ICMS_HOJE))
