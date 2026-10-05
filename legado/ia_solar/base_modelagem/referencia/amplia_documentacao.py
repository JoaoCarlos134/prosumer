# -*- coding: utf-8 -*-
###############################################################################
# AMPLIA A DOCUMENTACAO DA BASE DE MODELAGEM
#
# Acrescenta ao Documentacao_Base_Modelagem.xlsx:
#
#   Tarifas              a base tarifaria da Copel-DIS usada nas series de 5 min
#   Economia             o valor realizado de cada kWh gerado e as alavancas
#   Cenarios irradiancia o teste de inverter a potencia para estimar irradiancia
#   Graficos             cinco graficos nativos do Excel, editaveis
#   Revisao              conferencia de tudo que ja estava na planilha
#
# As abas que ja existiam nao sao alteradas, com uma excecao: o Leia-me ganha a
# descricao das abas novas e uma quarta regra.
#
# Requisitos: pandas, openpyxl
###############################################################################

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from openpyxl import load_workbook
from openpyxl.chart import BarChart, LineChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

###############################################################################
# CONFIGURACAO
###############################################################################

pasta_projeto = Path(__file__).resolve().parents[2]
caminho_doc = pasta_projeto / r'base_modelagem/Documentacao_Base_Modelagem.xlsx'
pasta_tarifas = pasta_projeto / r'analise/tarifas/dados'
pasta_inversa = pasta_projeto / r'analise/irradiancia_inversa'

sys.path.insert(0, str(pasta_projeto / r'analise/tarifas/scripts'))
import aplica_tarifas as at                                     # noqa: E402

COSIP_MES = 10.62          # estimado da fatura de 2018 de Cascavel
TARIFA_HOJE = 1.0967       # R$/kWh, vigencia 24/06/2026, bandeira amarela
GER_ANO_CASCAVEL = 5553    # kWh/ano, media recente

AZUL = 'FF1F4E79'
CINZA = 'FFF2F2F2'
AMARELO = 'FFFFF2CC'

###############################################################################
# AUXILIARES DE ESCRITA
###############################################################################


def nova_aba(wb, nome, subtitulo):
    if nome in wb.sheetnames:
        del wb[nome]
    ws = wb.create_sheet(nome)
    ws.sheet_view.showGridLines = False
    ws['A1'] = nome
    ws['A1'].font = Font(bold=True, size=15, color=AZUL)
    ws['A2'] = subtitulo
    ws['A2'].font = Font(italic=True, size=10)
    return ws


def titulo(ws, linha, texto):
    ws.cell(row=linha, column=1, value=texto).font = Font(bold=True, size=12, color=AZUL)
    return linha + 1


def tabela(ws, linha, df, larguras=None, formatos=None, destaque=None):
    """Escreve df a partir de `linha`. Devolve a primeira linha livre depois."""
    for j, c in enumerate(df.columns, start=1):
        cel = ws.cell(row=linha, column=j, value=str(c))
        cel.font = Font(bold=True, color='FFFFFFFF')
        cel.fill = PatternFill('solid', fgColor=AZUL)
        cel.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
    ws.row_dimensions[linha].height = 28
    for i, reg in enumerate(df.itertuples(index=False, name=None), start=1):
        for j, v in enumerate(reg, start=1):
            cel = ws.cell(row=linha + i, column=j,
                          value=None if (isinstance(v, float) and np.isnan(v)) else v)
            if i % 2 == 0:
                cel.fill = PatternFill('solid', fgColor=CINZA)
            col = df.columns[j - 1]
            if formatos and col in formatos:
                cel.number_format = formatos[col]
            if destaque and destaque(reg):
                cel.fill = PatternFill('solid', fgColor=AMARELO)
                cel.font = Font(bold=True)
    for j, c in enumerate(df.columns, start=1):
        larg = (larguras or {}).get(c, max(12, min(60, len(str(c)) + 4)))
        atual = ws.column_dimensions[get_column_letter(j)].width or 0
        ws.column_dimensions[get_column_letter(j)].width = max(atual, larg)
    return linha + len(df) + 3


def texto_longo(ws, linha, rotulo, corpo, larg_corpo=110):
    ws.cell(row=linha, column=1, value=rotulo).font = Font(bold=True)
    c = ws.cell(row=linha, column=2, value=corpo)
    c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.row_dimensions[linha].height = max(15, 13 * (1 + len(corpo) // larg_corpo))
    return linha + 1


###############################################################################
# DADOS
###############################################################################


def dados_tarifas():
    hist = pd.read_csv(pasta_tarifas / 'copel_tarifas_historico.csv', encoding='utf-8-sig')
    fisc = pd.read_csv(pasta_tarifas / 'parametros_fiscais.csv', encoding='utf-8-sig')
    ucs = pd.read_csv(pasta_tarifas / 'parametros_usinas.csv', encoding='utf-8-sig')

    vig = hist.vigencia_ini.max()
    atual = hist[hist.vigencia_ini == vig].copy()
    atual['tarifa_sem_impostos_RS_kWh'] = (atual.total_RS_MWh / 1000).round(5)
    atual['tarifa_cheia_RS_kWh'] = ((atual.total_RS_MWh + 18.85) / 1000 * 1.3937).round(5)

    t = at.le_tarifas()
    icms, pis = at.le_fiscais()
    band = at.le_bandeiras()
    cal = at.monta_calendario(pd.Timestamp('2019-01-01'), pd.Timestamp('2026-09-30'),
                              t, icms, pis, band)
    mensal = cal.groupby(cal.dia.dt.to_period('M')).agg(
        tarifa_sem_impostos=('tarifa_sem_impostos_RS_kWh', 'mean'),
        tarifa_cheia=('tarifa_cheia_RS_kWh', 'mean'),
        icms_pct=('icms_pct', 'mean')).reset_index()
    mensal['competencia'] = mensal.dia.astype(str)
    mensal = mensal[['competencia', 'tarifa_sem_impostos', 'tarifa_cheia', 'icms_pct']].round(5)
    return atual, fisc, ucs, mensal, cal


def dados_economia(cal):
    mens = cal.groupby(cal.dia.dt.to_period('M')).tarifa_cheia_RS_kWh.mean()
    f = pd.read_csv(pasta_projeto / r'analise/cascavel/dados/billing.csv')
    f = f.dropna(subset=['consumo', 'pago']).copy()
    f['comp'] = pd.PeriodIndex(f.date, freq='M')
    f['tarifa'] = f.comp.map(mens)
    f['sem_solar'] = f.consumo * f.tarifa + COSIP_MES
    f['economia'] = f.sem_solar - f.pago
    p = f[f.year >= 2019]
    g = p.groupby('year').agg(geracao=('geracao', 'sum'), consumo=('consumo', 'sum'),
                              injetado=('injetado', 'sum'), pago=('pago', 'sum'),
                              economia=('economia', 'sum'), tarifa=('tarifa', 'mean'))
    g['autoconsumo_pct'] = (100 * (g.geracao - g.injetado) / g.geracao).round(1)
    g['valor_kWh_gerado'] = (g.economia / g.geracao).round(4)
    g['pct_da_tarifa'] = (100 * g.valor_kWh_gerado / g.tarifa).round(1)
    g = g.round(2).reset_index().rename(columns={'year': 'ano'})

    tot = p[['geracao', 'injetado', 'economia']].sum()
    val = tot.economia / tot.geracao
    auto = (tot.geracao - tot.injetado) / tot.geracao

    alav = pd.DataFrame([
        ('Zerar por completo o erro do modelo', 1.36 * 365, val,
         'Limite teorico de um modelo perfeito. NAO e o ganho de um piranometro'),
        ('Limpar a sujeira (recupera 8%)', 0.08 * GER_ANO_CASCAVEL, val,
         'Queda de corrente CC observada desde a limpeza de set/2024'),
        ('Autoconsumo de 24% para 35%', (0.35 - auto) * GER_ANO_CASCAVEL, TARIFA_HOJE,
         'Deslocar carga para o meio do dia. Vale a tarifa CHEIA, nao o valor realizado'),
        ('Autoconsumo de 24% para 50%', (0.50 - auto) * GER_ANO_CASCAVEL, TARIFA_HOJE,
         'Idem, cenario agressivo'),
    ], columns=['alavanca', 'kWh_por_ano', 'valor_unitario_RS_kWh', 'observacao'])
    alav['RS_por_ano'] = (alav.kWh_por_ano * alav.valor_unitario_RS_kWh).round(2)
    alav['kWh_por_ano'] = alav.kWh_por_ano.round(0)
    alav = alav[['alavanca', 'kWh_por_ano', 'valor_unitario_RS_kWh', 'RS_por_ano', 'observacao']]
    return g, alav, val, auto


def dados_cenarios():
    c = pd.read_csv(pasta_inversa / 'comparativo_irradiancia_inversa.csv',
                    sep=';', decimal=',', encoding='utf-8-sig')
    c = c[['usina', 'cenario', 'R2', 'MAE', 'R2_diario', 'MAE_diario']].copy()
    for col in ['R2', 'MAE', 'R2_diario', 'MAE_diario']:
        c[col] = pd.to_numeric(c[col]).round(4)

    linhas = []
    for usina in ['Cascavel', 'Curitiba']:
        d = pd.read_parquet(pasta_inversa / ('irradiancia_inversa_%s.parquet' % usina))
        d = d.dropna(subset=['kc_5min'])
        med_h = d.groupby(d.data_hora.dt.floor('h')).kc_5min.transform('mean')
        vt, ve = d.kc_5min.var(), med_h.var()
        linhas.append(dict(usina=usina,
                           entre_horas_pct=round(100 * ve / vt, 1),
                           dentro_da_hora_pct=round(100 * (vt - ve) / vt, 1)))
    var = pd.DataFrame(linhas)
    return c, var


###############################################################################
# ABAS
###############################################################################


def aba_tarifas(wb, atual, fisc, ucs, mensal):
    ws = nova_aba(wb, 'Tarifas',
                  'Base tarifaria da Copel-DIS usada para custear as series. NAO e preditor.')
    L = 4
    L = titulo(ws, L, 'POR QUE ISTO ESTA AQUI')
    L = texto_longo(ws, L, 'Para que serve',
                    'Converter erro de modelo e perda de geracao em R$. A tarifa nao prediz '
                    'geracao: ela precifica o resultado.')
    L = texto_longo(ws, L, 'REGRA',
                    'NAO use nenhuma coluna de tarifa como preditor. A tarifa e uma funcao-degrau '
                    'da data. No corte temporal, o periodo de teste tem valores que nunca '
                    'apareceram no treino (768,02 R$/MWh so existe desde 24/06/2026), e o modelo '
                    'passa a usar a tarifa como proxy de ano.')
    L = texto_longo(ws, L, 'Fonte',
                    'API de dados abertos da ANEEL. Coleta em analise/tarifas/scripts/'
                    'baixa_tarifas_aneel.py. Base completa em analise/tarifas/Tarifas_Copel.xlsx.')
    L = texto_longo(ws, L, 'Vale para as duas',
                    'A tarifa e homologada por distribuidora, nao por municipio. Cascavel e '
                    'Curitiba sao a mesma Copel-DIS, mesmo subgrupo B1. O R$/kWh e identico; '
                    'so o encargo fixo difere (ligacao bifasica x trifasica).')
    L += 1

    L = titulo(ws, L, 'VIGENCIA ATUAL (REH 3.592/2026, 24/06/2026 a 23/06/2027)')
    L = tabela(ws, L, atual[['subgrupo', 'modalidade', 'posto', 'tusd_RS_MWh', 'te_RS_MWh',
                             'total_RS_MWh', 'tarifa_sem_impostos_RS_kWh', 'tarifa_cheia_RS_kWh']],
               larguras={'modalidade': 14, 'posto': 15, 'tarifa_sem_impostos_RS_kWh': 16,
                         'tarifa_cheia_RS_kWh': 16},
               formatos={'tusd_RS_MWh': '0.00', 'te_RS_MWh': '0.00', 'total_RS_MWh': '0.00',
                         'tarifa_sem_impostos_RS_kWh': '0.0000', 'tarifa_cheia_RS_kWh': '0.0000'},
               destaque=lambda r: r[0] == 'B1' and r[1] == 'Convencional')

    L = titulo(ws, L, 'COMO A TARIFA CHEIA E MONTADA')
    L = texto_longo(ws, L, 'Formula',
                    'tarifa_cheia [R$/kWh] = (TUSD + TE + adicional_bandeira) / 1000 '
                    'x 1 / (1 - ICMS - PIS/COFINS)')
    L = texto_longo(ws, L, 'Impostos por dentro',
                    'ICMS e PIS/COFINS compoem a propria base de calculo: divide-se por '
                    '(1 - aliquotas) em vez de multiplicar por (1 + aliquotas).')
    L = texto_longo(ws, L, 'Hoje',
                    'TUSD 457,17 + TE 310,85 = 768,02 R$/MWh, bandeira amarela, ICMS 19%, '
                    'PIS/COFINS 9,25% -> R$ 1,0967/kWh.')
    L += 1

    L = titulo(ws, L, 'PARAMETROS FISCAIS')
    L = tabela(ws, L, fisc[['vigencia_ini', 'vigencia_fim', 'tributo', 'aliquota_pct', 'fonte']],
               larguras={'fonte': 80}, formatos={'aliquota_pct': '0.00'})

    L = titulo(ws, L, 'ENQUADRAMENTO DAS UNIDADES CONSUMIDORAS')
    L = tabela(ws, L, ucs[['usina', 'subgrupo', 'modalidade', 'ligacao',
                           'disponibilidade_kWh_mes', 'data_conexao', 'fio_b_cobrado']],
               larguras={'disponibilidade_kWh_mes': 16, 'data_conexao': 14})

    L = titulo(ws, L, 'AS QUATRO COLUNAS QUE ENTRARAM NAS SERIES DE 5 MIN')
    dic = pd.DataFrame([
        ('tarifa_sem_impostos_RS_kWh', 'R$/kWh', '(TUSD + TE) / 1000 da vigencia daquele dia'),
        ('bandeira', 'texto', 'Bandeira acionada no mes-calendario'),
        ('adic_bandeira_RS_kWh', 'R$/kWh', 'Adicional da bandeira, sem impostos'),
        ('tarifa_cheia_RS_kWh', 'R$/kWh',
         '(tarifa_sem_impostos + adic_bandeira) x fator de impostos'),
    ], columns=['coluna', 'unidade', 'como e calculada'])
    L = tabela(ws, L, dic, larguras={'coluna': 28, 'como e calculada': 62})

    L = titulo(ws, L, 'SERIE MENSAL (fonte do grafico 4)')
    inicio_mensal = L
    L = tabela(ws, L, mensal, larguras={'competencia': 13, 'tarifa_sem_impostos': 18,
                                        'tarifa_cheia': 14},
               formatos={'tarifa_sem_impostos': '0.0000', 'tarifa_cheia': '0.0000',
                         'icms_pct': '0.00'})
    return ws, inicio_mensal, len(mensal)


def aba_economia(wb, g, alav, val, auto):
    ws = nova_aba(wb, 'Economia',
                  'O que cada kWh gerado vale de verdade, e o que isso faz com a regressao.')
    L = 4
    L = titulo(ws, L, 'O ACHADO')
    L = texto_longo(ws, L, 'Resumo',
                    'Em Cascavel, cada kWh gerado realiza R$ %.3f — %.0f%% da tarifa de varejo. '
                    'A razao bate com a fracao de autoconsumo (%.1f%%), e esse e o mecanismo: so '
                    'o kWh consumido na hora vale a tarifa. O resto vira credito, e com 2,34x de '
                    'cobertura o credito empilha e expira (1.548 kWh expiraram em 2024).'
                    % (val, 100 * val / 0.887, 100 * auto))
    L = texto_longo(ws, L, 'Consequencia',
                    'O MAE de 1,36 kWh/dia parece valer R$ 544/ano a tarifa cheia. Ao valor '
                    'realizado sao R$ 109/ano. Nenhuma melhoria do lado da geracao se paga.')
    L = texto_longo(ws, L, 'Curitiba',
                    'NAO da para repetir esta conta: nao ha fatura nem dado de consumo. Uma '
                    'fatura de Curitiba vale mais que qualquer refinamento de modelo la.')
    L += 1

    L = titulo(ws, L, 'CASCAVEL, ANO A ANO (contrafactual com COSIP de R$ %.2f/mes)' % COSIP_MES)
    inicio_g = L
    L = tabela(ws, L, g, larguras={'autoconsumo_pct': 15, 'valor_kWh_gerado': 16,
                                   'pct_da_tarifa': 14},
               formatos={'geracao': '#,##0', 'consumo': '#,##0', 'injetado': '#,##0',
                         'pago': '#,##0.00', 'economia': '#,##0.00', 'tarifa': '0.000',
                         'valor_kWh_gerado': '0.0000', 'autoconsumo_pct': '0.0',
                         'pct_da_tarifa': '0.0'})

    L = titulo(ws, L, 'ALAVANCAS, EM R$/ANO')
    inicio_a = L
    L = tabela(ws, L, alav, larguras={'alavanca': 42, 'kWh_por_ano': 13,
                                      'valor_unitario_RS_kWh': 18, 'RS_por_ano': 13,
                                      'observacao': 62},
               formatos={'kWh_por_ano': '#,##0', 'valor_unitario_RS_kWh': '0.0000',
                         'RS_por_ano': '#,##0.00'})

    L = titulo(ws, L, 'O QUE ISSO MUDA NO TRABALHO DE REGRESSAO')
    L = texto_longo(ws, L, 'Alvo',
                    'Prever potencia_ca_W otimiza uma grandeza de valor marginal quase zero. O que '
                    'tem valor e a COINCIDENCIA entre geracao e carga: o mesmo kWh vale R$ 1,0967 '
                    'se cai sobre consumo e ~R$ 0 se e injetado.')
    L = texto_longo(ws, L, 'Perda ponderada',
                    'Uma funcao de perda ponderada pelo valor marginal do instante mudaria o '
                    'modelo de verdade. Exige dado de carga, que nao existe em nenhuma das duas.')
    L = texto_longo(ws, L, 'O que segue valendo',
                    'O modelo como DIAGNOSTICO. Foi ele que achou a falha da string 1 em Curitiba '
                    'e a assinatura angular da sujeira em Cascavel. Isso e saude de ativo e nao '
                    'passa por esta conta.')
    L += 1
    L = titulo(ws, L, 'RESSALVAS')
    for r, t in [('COSIP', 'R$ %.2f/mes estimado da fatura de 2018 de Cascavel. E o unico item '
                           'inventado na conta.' % COSIP_MES),
                 ('Periodo', 'As faturas param em dez/2024. 2025 e 2026 nao entram.'),
                 ('Contrafactual', 'Assume o mesmo consumo sem solar. Se houve efeito rebote, a '
                                   'economia real e menor.')]:
        L = texto_longo(ws, L, r, t)
    return ws, inicio_g, len(g), inicio_a, len(alav)


def aba_cenarios(wb, cen, var):
    ws = nova_aba(wb, 'Cenarios irradiancia',
                  'Inverter a potencia para estimar irradiancia a 5 min: o teste e o resultado.')
    L = 4
    L = titulo(ws, L, 'A PERGUNTA')
    L = texto_longo(ws, L, 'Proposta testada',
                    'Inverter P = G x A x eta para obter irradiancia a 5 min e usar isso para '
                    'quebrar a NASA POWER em 5 min, melhorando o modelo.')
    L = texto_longo(ws, L, 'Resposta', 'Nao funciona. E a versao que "funciona" e vazamento.')
    L += 1
    L = titulo(ws, L, 'OS QUATRO CENARIOS (treino ate 01/08/2025)')
    inicio = L
    L = tabela(ws, L, cen, larguras={'cenario': 52, 'R2_diario': 12, 'MAE_diario': 12},
               formatos={'R2': '0.0000', 'MAE': '#,##0.0', 'R2_diario': '0.0000',
                         'MAE_diario': '0.00'},
               destaque=lambda r: str(r[1]).startswith('B'))

    L = titulo(ws, L, 'LEITURA')
    for r, t in [
        ('B e vazamento', 'G_inv sai de potencia_ca_W por transformacao quase monotonica. '
                          'R2 0,9999 e a prova aritmetica disso, nao um ganho. Lido de outro '
                          'jeito, B e um teto FROUXO: o G_inv carrega o estado da usina '
                          'junto, coisa que um piranometro nao mede. Para o ganho real de um '
                          'sensor, ver a aba Ablacao.'),
        ('C e o teste honesto', 'Preve o kc de 5 min a partir de NASA + geometria, usando G_inv '
                                'so como alvo de treino. Na previsao nao usa potencia. PIORA: '
                                '-0,011 em Cascavel, -0,008 em Curitiba. Downscaling reorganiza '
                                'informacao, nao cria.'),
        ('D muda a pergunta', 'Irradiancia medida 1 h antes vale +0,015 e +0,017 de R2, e no '
                              'acumulado diario 0,908 -> 0,943 e 0,878 -> 0,930. Mas e nowcast: '
                              'exige a usina rodando. Nao serve para simular um ano de clima.'),
    ]:
        L = texto_longo(ws, L, r, t)
    L += 1

    L = titulo(ws, L, 'O NUMERO QUE FECHA O ASSUNTO: VARIANCIA DO kc DE 5 MIN')
    L = tabela(ws, L, var, larguras={'entre_horas_pct': 26, 'dentro_da_hora_pct': 26},
               formatos={'entre_horas_pct': '0.0', 'dentro_da_hora_pct': '0.0'})
    L = texto_longo(ws, L, 'Interpretacao',
                    'So ~20% da variacao esta fora do alcance de um dado horario. O teto de um '
                    'dado horario PERFEITO e R2 0,795 e 0,783 contra o kc medido. O kc horario '
                    'cru da NASA da R2 NEGATIVO (-0,38 e -0,59): pior que prever a media. '
                    'O gargalo nao e a resolucao temporal da NASA, e a qualidade dela.')
    L += 1
    L = titulo(ws, L, 'O QUE MOVE O PONTEIRO')
    for i, t in enumerate([
        'Piranometro ou celula de referencia na usina: fecha 99% do vao entre o modelo '
        'embarcado e o completo, +0,22 de R2 medido (ver aba Ablacao). Mas ver a aba Economia '
        'antes: em Cascavel isso vale R$ 109/ano.',
        'Fonte horaria melhor que a NASA POWER (CAMS, SARAH-3, Solcast, INPE).',
        'Resolver a geometria de Curitiba, pre-requisito para qualquer medida la.'], start=1):
        L = texto_longo(ws, L, '%d.' % i, t)
    return ws, inicio, len(cen)


def aba_graficos(wb, ref):
    ws = nova_aba(wb, 'Graficos', 'Cinco comparacoes. Graficos nativos do Excel, editaveis.')

    def coloca(ch, anc, titulo_, larg=24, alt=11):
        ch.title = titulo_
        ch.width, ch.height = larg, alt
        ch.style = 2
        ws.add_chart(ch, anc)

    # 1 - cenarios de irradiancia, R2 por usina
    src, l0, n = ref['cenarios']
    ch = BarChart(); ch.type = 'col'; ch.gapWidth = 60
    dados = Reference(src, min_col=3, min_row=l0, max_col=3, max_row=l0 + n)
    cats = Reference(src, min_col=1, min_row=l0 + 1, max_col=2, max_row=l0 + n)
    ch.add_data(dados, titles_from_data=True)
    ch.set_categories(cats)
    ch.y_axis.title = 'R2 no teste'
    ch.y_axis.scaling.min = 0.6
    ch.dLbls = DataLabelList(); ch.dLbls.showVal = True
    coloca(ch, 'A4', '1. Cenarios de irradiancia: B e vazamento, nao ganho')

    # 2 - valor do kWh contra a tarifa
    src, l0, n = ref['economia_ano']
    ch = LineChart(); ch.marker = True
    v = Reference(src, min_col=9, min_row=l0, max_col=9, max_row=l0 + n)      # valor_kWh_gerado
    t = Reference(src, min_col=7, min_row=l0, max_col=7, max_row=l0 + n)      # tarifa
    ch.add_data(v, titles_from_data=True)
    ch.add_data(t, titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=l0 + 1, max_col=1, max_row=l0 + n))
    ch.y_axis.title = 'R$/kWh'; ch.x_axis.title = 'ano'
    coloca(ch, 'A27', '2. Cascavel: o kWh gerado vale ~1/4 da tarifa de varejo')

    # 3 - alavancas
    src, l0, n = ref['alavancas']
    ch = BarChart(); ch.type = 'bar'; ch.gapWidth = 50
    ch.add_data(Reference(src, min_col=4, min_row=l0, max_col=4, max_row=l0 + n),
                titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=l0 + 1, max_col=1, max_row=l0 + n))
    ch.x_axis.title = 'R$ por ano'
    ch.dLbls = DataLabelList(); ch.dLbls.showVal = True
    coloca(ch, 'A50', '3. Deslocar carga vale 6x mais que tudo que o modelo pode dar')

    # 4 - tarifa mensal
    src, l0, n = ref['tarifa_mensal']
    ch = LineChart()
    ch.add_data(Reference(src, min_col=3, min_row=l0, max_col=3, max_row=l0 + n),
                titles_from_data=True)
    ch.add_data(Reference(src, min_col=2, min_row=l0, max_col=2, max_row=l0 + n),
                titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=l0 + 1, max_col=1, max_row=l0 + n))
    ch.y_axis.title = 'R$/kWh'
    coloca(ch, 'A73', '4. Tarifa Copel-DIS B1: a queda de 2022 e o ICMS, a alta de 2026 e a RTP')

    # 5 - comparacao de modelos, R2 medio
    src = wb['Comparacao de modelos']
    ch = BarChart(); ch.type = 'bar'; ch.gapWidth = 40
    ch.add_data(Reference(src, min_col=8, min_row=4, max_col=8, max_row=17), titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=5, max_col=1, max_row=17))
    ch.x_axis.title = 'R2 medio das duas usinas'
    coloca(ch, 'A96', '5. Os 13 algoritmos: HistGradientBoosting escolhido por tempo, nao por R2')
    return ws


def aba_revisao(wb):
    ws = nova_aba(wb, 'Revisao',
                  'Conferencia do que ja estava na planilha contra os dados, em 21/09/2026.')
    L = 4
    ach = pd.DataFrame([
        ('Leia-me / Qualidade dos dados', 'ERRO DE CONTAGEM',
         '"620.278 registros" no Leia-me; "Cascavel diurnos 367.129" e "Curitiba diurnos 257.282" '
         'na aba Qualidade.',
         '367.129 + 257.282 = 624.411, mas a base tem 620.278. Faltam 4.133 linhas de Cascavel.',
         'A causa e o filtro p_ac.notna() do build_base_modelagem.py: linhas com ALVO ausente sao '
         'descartadas. Sao ~4.075 linhas (1,11% citado na propria aba) mais as 94 remocoes duras. '
         'Corrigir o texto: 367.129 sao os diurnos ANTES de descartar alvo ausente.'),
        ('Qualidade dos dados', 'TEXTO ENGANOSO',
         '"Faltantes de dia 1,11% | Tratamento: Mantidos: a arvore trata NaN"',
         'Verdadeiro para PREDITORES, falso para o ALVO: alvo NaN e descartado.',
         'Separar as duas frases. E a mesma raiz do erro de contagem acima.'),
        ('Comparacao de modelos', 'JUSTIFICATIVA AUSENTE',
         'HistGradientBoosting marcado como ESCOLHIDO com R2 Cascavel 0,8047.',
         'Gradient Boosting tem R2 0,8062 em Cascavel, MAIOR que o escolhido.',
         'A escolha esta certa (3,3 s contra 57,4 s, e R2 medio maior), mas a planilha nao diz '
         'isso. Acrescentar a coluna de tempo ao criterio, no texto.'),
        ('Colunas da base / Equacoes', 'PENDENCIA CONHECIDA',
         'pot_nominal_kWp de Curitiba = 9,603 kWp, marcada como ESTIMADA.',
         'Confirmado: a planilha original do cliente divide por 12,000 kWp, que e a potencia CA '
         'do inversor. Todo numero por kWp de Curitiba e provisorio.',
         'Ja esta sinalizado na aba Colunas da base. Mantido. Destrava com foto do telhado e '
         'mapa de strings.'),
        ('Qualidade dos dados', 'DESATUALIZADO',
         '"Cascavel: 7 arquivos anuais, 2019-07 a 2026-07"',
         'Correto para a base, mas ha exportacoes ate 11/09/2026 em dados_brutos/cascavel/'
         'exportacoes/ que nao entraram no consolidado de 5 min.',
         'Decidir se vale reprocessar. Sao ~6 semanas de dado parado.'),
        ('Qualidade dos dados', 'CONFERIDO, OK',
         '"Cobertura horaria da NASA POWER: 85% no teste"',
         'Medido: 85,2% em Cascavel e 84,4% em Curitiba. Ultima hora valida 30/05/2026.',
         'Nenhuma acao.'),
        ('Qualidade dos dados', 'COSMETICO',
         '"47 % da base é noite"',
         'Unico texto acentuado numa planilha que e ASCII em todo o resto.',
         'Padronizar.'),
        ('Leia-me', 'FALTAVA',
         'Tres regras que nao podem ser quebradas.',
         'Falta a regra sobre tarifa: e funcao-degrau da data e vira proxy de ano.',
         'Acrescentada como regra 4 nesta revisao.'),
    ], columns=['Aba', 'Tipo', 'O que a planilha diz', 'O que os dados dizem', 'Acao'])
    L = tabela(ws, L, ach,
               larguras={'Aba': 26, 'Tipo': 22, 'O que a planilha diz': 52,
                         'O que os dados dizem': 56, 'Acao': 62},
               destaque=lambda r: r[1] in ('ERRO DE CONTAGEM', 'TEXTO ENGANOSO'))
    for linha in ws.iter_rows(min_row=5, max_row=4 + len(ach)):
        for c in linha:
            c.alignment = Alignment(wrap_text=True, vertical='top')
        ws.row_dimensions[linha[0].row].height = 74

    L = titulo(ws, L, 'O QUE NAO FOI ALTERADO')
    L = texto_longo(ws, L, 'Criterio',
                    'As abas originais nao foram editadas, com uma excecao (o Leia-me ganhou a '
                    'descricao das abas novas e a regra 4). Os erros acima estao APONTADOS, nao '
                    'corrigidos em silencio: a correcao muda numeros que ja circularam.')
    L = texto_longo(ws, L, 'Backup',
                    'A versao anterior a esta ampliacao foi copiada para a pasta de trabalho '
                    'temporaria da sessao antes de qualquer escrita.')
    return ws


def atualiza_leiame(wb):
    ws = wb['Leia-me']
    alvo = None
    for r in range(1, ws.max_row + 1):
        v = str(ws.cell(row=r, column=1).value or '')
        if v.startswith('4. Nao use as colunas de tarifa'):
            return                      # ja atualizado: nao duplica
        if v.startswith('Tres regras que nao podem ser quebradas'):
            ws.cell(row=r, column=1, value='Quatro regras que nao podem ser quebradas')
        if v.startswith('3. O alvo nao e estacionario'):
            alvo = r
    if alvo is None:
        return
    ws.insert_rows(alvo + 1, 6)
    ws.cell(row=alvo + 1, column=1,
            value='4. Nao use as colunas de tarifa como preditor. Sao funcao-degrau da data: no '
                  'corte temporal viram proxy de ano.')
    ws.cell(row=alvo + 3, column=1, value='Abas acrescentadas em 21/09/2026').font = Font(bold=True)
    ws.cell(row=alvo + 4, column=1,
            value='Tarifas                a base tarifaria da Copel-DIS e as 4 colunas de custo')
    ws.cell(row=alvo + 5, column=1,
            value='Economia               o valor realizado do kWh e as alavancas em R$/ano')
    ws.cell(row=alvo + 6, column=1,
            value='Cenarios irradiancia   o teste de estimar irradiancia pela potencia')
    ws.insert_rows(alvo + 7, 2)
    ws.cell(row=alvo + 7, column=1,
            value='Graficos               cinco comparacoes, graficos nativos do Excel')
    ws.cell(row=alvo + 8, column=1,
            value='Revisao                conferencia das abas originais contra os dados')


###############################################################################
# MONTAGEM
###############################################################################

if __name__ == '__main__':
    atual, fisc, ucs, mensal, cal = dados_tarifas()
    g, alav, val, auto = dados_economia(cal)
    cen, var = dados_cenarios()

    wb = load_workbook(caminho_doc)
    ws_t, l_mensal, n_mensal = aba_tarifas(wb, atual, fisc, ucs, mensal)
    ws_e, l_g, n_g, l_a, n_a = aba_economia(wb, g, alav, val, auto)
    ws_c, l_cen, n_cen = aba_cenarios(wb, cen, var)
    aba_graficos(wb, dict(cenarios=(ws_c, l_cen, n_cen),
                          economia_ano=(ws_e, l_g, n_g),
                          alavancas=(ws_e, l_a, n_a),
                          tarifa_mensal=(ws_t, l_mensal, n_mensal)))
    aba_revisao(wb)
    atualiza_leiame(wb)

    wb.save(caminho_doc)
    print('OK  %s' % caminho_doc.name)
    print('    abas: %s' % ', '.join(wb.sheetnames))
    print('    valor realizado do kWh em Cascavel: R$ %.4f  (autoconsumo %.1f%%)'
          % (val, 100 * auto))
