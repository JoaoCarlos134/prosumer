# -*- coding: utf-8 -*-
###############################################################################
# DIVIDE A DOCUMENTACAO EM DUAS PLANILHAS
#
#   Documentacao_Dados.xlsx       o que a base E
#     Leia-me, Colunas da base, Colunas removidas, Equacoes, Qualidade dos dados,
#     Tarifas, Graficos, Revisao
#
#   Documentacao_Resultados.xlsx  o que foi ENCONTRADO
#     Leia-me, Ablacao, Comparacao de modelos, Modelos embarcado,
#     Cenarios irradiancia, Economia, Graficos
#
# As abas originais sao copiadas celula a celula, com formatacao. As abas novas
# sao reconstruidas por amplia_documentacao.py, que ja tem os dados na mao.
#
# Requisitos: pandas, openpyxl
###############################################################################

import sys
from copy import copy
from pathlib import Path

import pandas as pd
from openpyxl import Workbook, load_workbook
from openpyxl.chart import BarChart, LineChart, Reference, ScatterChart, Series
from openpyxl.chart.label import DataLabelList
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import amplia_documentacao as ad                                   # noqa: E402

###############################################################################
# CONFIGURACAO
###############################################################################

pasta_base = Path(__file__).resolve().parents[1]
pasta_projeto = Path(__file__).resolve().parents[2]

# Origem das abas copiadas: o arquivo unico, ampliado por amplia_documentacao.py.
# Feche-o no Excel antes de rodar.
CANDIDATOS_ORIGEM = [
    pasta_base / 'Documentacao_Base_Modelagem.xlsx',
]

SAIDA_DADOS = pasta_base / 'Documentacao_Dados.xlsx'
SAIDA_RESULTADOS = pasta_base / 'Documentacao_Resultados.xlsx'
CSV_EMBARCADO = pasta_base / 'embarcado' / 'comparacao_embarcado.csv'
CSV_ABLACAO = pasta_base / 'embarcado' / 'ablacao_preditores.csv'
CSV_SENSOR = pasta_base / 'embarcado' / 'sensor_irradiancia.csv'

ABAS_DADOS = ['Colunas da base', 'Colunas removidas', 'Equacoes', 'Qualidade dos dados']
ABAS_RESULTADOS = ['Comparacao de modelos']

###############################################################################
# COPIA DE ABAS COM FORMATACAO
###############################################################################


def abre_origem():
    for c in CANDIDATOS_ORIGEM:
        if not c.exists():
            continue
        try:
            wb = load_workbook(c)
            print('origem: %s' % c.name)
            return wb
        except PermissionError:
            print('   %s esta travado (aberto no Excel), tentando o proximo' % c.name)
    raise SystemExit('nenhuma origem legivel')


def copia_aba(ws_src, wb_dst, nome=None):
    ws = wb_dst.create_sheet(nome or ws_src.title)
    for linha in ws_src.iter_rows():
        for c in linha:
            d = ws.cell(row=c.row, column=c.column, value=c.value)
            if c.has_style:
                d.font = copy(c.font)
                d.fill = copy(c.fill)
                d.border = copy(c.border)
                d.alignment = copy(c.alignment)
                d.number_format = c.number_format
    for k, dim in ws_src.column_dimensions.items():
        ws.column_dimensions[k].width = dim.width
    for k, dim in ws_src.row_dimensions.items():
        ws.row_dimensions[k].height = dim.height
    for rng in ws_src.merged_cells.ranges:
        ws.merge_cells(str(rng))
    ws.freeze_panes = ws_src.freeze_panes
    ws.sheet_view.showGridLines = ws_src.sheet_view.showGridLines
    if ws_src.auto_filter.ref:
        ws.auto_filter.ref = ws_src.auto_filter.ref
    return ws


###############################################################################
# LEIA-ME DE CADA PLANILHA
###############################################################################


def leiame(wb, titulo, subtitulo, blocos):
    ws = wb.create_sheet('Leia-me', 0)
    ws.sheet_view.showGridLines = False
    ws.column_dimensions['A'].width = 3
    ws.column_dimensions['B'].width = 26
    ws.column_dimensions['C'].width = 104
    ws['B1'] = titulo
    ws['B1'].font = Font(bold=True, size=16, color=ad.AZUL)
    ws['B2'] = subtitulo
    ws['B2'].font = Font(italic=True, size=11)
    L = 4
    for cabeca, itens in blocos:
        ws.cell(row=L, column=2, value=cabeca).font = Font(bold=True, size=13, color=ad.AZUL)
        L += 1
        for rot, txt in itens:
            L = ad.texto_longo(ws, L, rot, txt, larg_corpo=100)
            ws.cell(row=L - 1, column=2).alignment = ad.Alignment(vertical='top')
        L += 1
    return ws


###############################################################################
# ABA NOVA: MODELOS EMBARCADO
###############################################################################


def aba_embarcado(wb):
    R = pd.read_csv(CSV_EMBARCADO, sep=';', decimal=',', encoding='utf-8-sig')
    ws = ad.nova_aba(wb, 'Modelos embarcado',
                     '20 modelos, 2 conjuntos de preditores, 2 usinas. Inclui TensorFlow Lite.')
    L = 4
    L = ad.titulo(ws, L, 'O QUE FOI TESTADO')
    for rot, txt in [
        ('Modelos novos', 'LightGBM, CatBoost, Huber, ElasticNet, PLS e Voting, alem dos ja '
                          'comparados. Mais Keras MLP em duas larguras (32-16 e 16-8), que sao '
                          'a origem dos TFLite.'),
        ('TFLite', 'Quatro conversoes por arquitetura: float32, float16, int8 dinamico e int8 '
                   'total com dataset representativo. Metricas: R2, MAE, tamanho em KB e '
                   'latencia por amostra, invocando UMA amostra por vez.'),
        ('Dois conjuntos', 'COMPLETO = os 20 preditores atuais, com NASA POWER. '
                           'EMBARCADO = os 7 que um dispositivo na usina obtem sozinho: '
                           'geometria solar (relogio + coordenada), temperatura local e o '
                           'proprio historico de desempenho.'),
        ('Por que a divisao', 'A NASA POWER e reanalise: chega com dias de atraso. Um modelo '
                              'embarcado no inversor nao tem irradiancia em tempo real, e e '
                              'isso que define o teto dele.'),
        ('Linhas usadas', 'Treino e teste so com linhas de NASA horaria completa, nas DUAS '
                          'configuracoes, para que a diferenca entre elas meça o conjunto de '
                          'preditores e mais nada. Por isso estes numeros NAO sao comparaveis '
                          'com a aba Comparacao de modelos, que usou outro pre-processamento.'),
    ]:
        L = ad.texto_longo(ws, L, rot, txt)
    L += 1

    L = ad.titulo(ws, L, 'O PRECO DE EMBARCAR')
    resumo = []
    for u in ['Cascavel', 'Curitiba']:
        linha = dict(usina=u)
        for c in ['COMPLETO', 'EMBARCADO']:
            s = R[(R.usina == u) & (R.conjunto == c)]
            linha['melhor_%s' % c] = round(s.R2.max(), 4)
        linha['perda_R2'] = round(linha['melhor_COMPLETO'] - linha['melhor_EMBARCADO'], 4)
        resumo.append(linha)
    L = ad.tabela(ws, L, pd.DataFrame(resumo),
                  larguras={'melhor_COMPLETO': 18, 'melhor_EMBARCADO': 18, 'perda_R2': 14},
                  formatos={'melhor_COMPLETO': '0.0000', 'melhor_EMBARCADO': '0.0000',
                            'perda_R2': '0.0000'})

    L = ad.titulo(ws, L, 'MELHOR MODELO POR ORCAMENTO DE MEMORIA')
    faixas = []
    for u in ['Cascavel', 'Curitiba']:
        for c in ['COMPLETO', 'EMBARCADO']:
            s = R[(R.usina == u) & (R.conjunto == c)]
            for lim, rot in [(10, 'microcontrolador  (< 10 KB)'),
                             (500, 'Linux embarcado  (< 500 KB)'),
                             (1e12, 'servidor  (sem limite)')]:
                f = s[s.KB < lim].sort_values('R2', ascending=False)
                if len(f):
                    b = f.iloc[0]
                    faixas.append(dict(usina=u, conjunto=c, orcamento=rot, modelo=b.modelo,
                                       R2=b.R2, MAE=b.MAE, KB=b.KB))
    L = ad.tabela(ws, L, pd.DataFrame(faixas),
                  larguras={'orcamento': 28, 'modelo': 28},
                  formatos={'R2': '0.0000', 'MAE': '#,##0.0', 'KB': '#,##0.0'})

    L = ad.titulo(ws, L, 'LEITURA')
    for rot, txt in [
        ('TFLite cabe sobrando', 'O MLP 16-8 em int8 total ocupa 3,4 KB e roda em ~11 us. O '
                                 'HistGradientBoosting em pickle sao 389 KB; o Random Forest, '
                                 '2,6 GB — esse nao entra em microcontrolador nenhum.'),
        ('Quantizacao quase de graca', 'float32, float16 e int8 dinamico deram R2 IDENTICO ao '
                                       'Keras de origem. So o int8 total perde algo: 0,8166 -> '
                                       '0,8117 em Cascavel e 0,7453 -> 0,7358 em Curitiba.'),
        ('CUIDADO com a latencia', 'O int8 total ficou MAIS LENTO que o float32 aqui (11 us '
                                   'contra 2,8). E artefato de x86, que nao tem caminho '
                                   'otimizado para int8 nessa forma. Num Cortex-M com CMSIS-NN '
                                   'a ordem se inverte. Nao use este numero para decidir.'),
        ('Surpresa em Cascavel', 'Regressao Linear, 0,7 KB, R2 0,8228 — a frente do '
                                 'HistGradientBoosting (0,8199) e de todos os TFLite. Com '
                                 'poa_estimada disponivel a relacao e quase P = eta x A x POA. '
                                 'Em Curitiba o linear desaba (0,7132), coerente com a '
                                 'geometria de dois planos nao resolvida.'),
        ('Nao esqueca o pre-processamento', 'As redes usam imputacao por mediana e '
                                            'padronizacao. Esses parametros tambem vao para o '
                                            'firmware. Sao poucos bytes, mas sem eles o modelo '
                                            'nao funciona.'),
    ]:
        L = ad.texto_longo(ws, L, rot, txt)
    L += 1

    L = ad.titulo(ws, L, 'TABELA COMPLETA')
    ini_tab = L
    completa = R.sort_values(['usina', 'conjunto', 'R2'], ascending=[True, True, False])
    L = ad.tabela(ws, L, completa,
                  larguras={'modelo': 30, 'us_por_amostra': 16, 'conjunto': 13},
                  formatos={'R2': '0.0000', 'MAE': '#,##0.0', 'KB': '#,##0.0',
                            'us_por_amostra': '#,##0.0', 'treino_s': '0.0'},
                  destaque=lambda r: 'TFLite' in str(r[3]))

    # fonte dos graficos: Cascavel COMPLETO, um ponto por modelo
    L = ad.titulo(ws, L, 'FONTE DOS GRAFICOS (Cascavel, conjunto COMPLETO)')
    disp = R[(R.usina == 'Cascavel') & (R.conjunto == 'COMPLETO')][['modelo', 'KB', 'R2']]
    disp = disp.sort_values('KB')
    ini_disp = L
    L = ad.tabela(ws, L, disp, larguras={'modelo': 30},
                  formatos={'KB': '#,##0.0', 'R2': '0.0000'})
    return ws, ini_tab, len(completa), ini_disp, len(disp), resumo



###############################################################################
# ABA NOVA: ABLACAO DE PREDITORES
###############################################################################


def aba_ablacao(wb):
    A = pd.read_csv(CSV_ABLACAO, sep=';', decimal=',', encoding='utf-8-sig')
    ws = ad.nova_aba(wb, 'Ablacao',
                     'De onde vem o R2. O achado mais forte do conjunto.')
    L = 4
    L = ad.titulo(ws, L, 'O ACHADO')
    for rot, txt in [
        ('Em uma frase', 'UMA coluna, poa_estimada, num modelo linear, entrega 99,6% do R2 de '
                         'Cascavel e 95,0% do de Curitiba. As outras 19 colunas valem +0,0032 '
                         'e +0,037.'),
        ('Metodo', 'Preditores acrescentados em camadas, da fisica pura ate a base completa. '
                   'Sempre as mesmas linhas (NASA horaria completa) e o mesmo corte de '
                   '01/08/2025. Dois modelos de extremos opostos — regressao linear e '
                   'HistGradientBoosting — para separar informacao de capacidade de ajuste.'),
        ('Script', 'referencia/ablacao_preditores.py'),
    ]:
        L = ad.texto_longo(ws, L, rot, txt)
    L += 1

    L = ad.titulo(ws, L, 'A TABELA')
    ini = L
    L = ad.tabela(ws, L, A, larguras={'camada': 32, 'n_preditores': 14},
                  formatos={'R2_Linear': '0.0000', 'R2_HistGB': '0.0000',
                            'MAE_Linear': '#,##0.0', 'MAE_HistGB': '#,##0.0'},
                  destaque=lambda r: str(r[1]).startswith('1.'))

    L = ad.titulo(ws, L, 'DE ONDE VEM')
    for rot, txt in [
        ('A coluna', 'poa_estimada = poa_ceu_claro x kc_horario. E construida a mao, nao '
                     'descoberta pelo modelo. A equacao esta em Documentacao_Dados.xlsx, aba '
                     'Equacoes, celula C21 (poa_ceu_claro) e C23 (poa_estimada).'),
        ('Fator forte', 'poa_ceu_claro — fisica pura, calculada e exata: Haurwitz para o ceu '
                        'claro, Erbs para separar difusa e direta, HDKR para transpor ao plano '
                        'inclinado. E o teto do que a usina poderia receber.'),
        ('Fator fraco', 'kc_horario — quanto as nuvens tiraram desse teto, segundo a NASA '
                        'POWER. Tem R2 NEGATIVO contra o kc medido (-0,38 e -0,59, ver aba '
                        'Cenarios irradiancia). E o elo fraco da cadeia inteira.'),
        ('Por que', 'A fisica e P = eta x A x POA: linear na irradiancia. Depois de construir '
                    'a POA corretamente, nao sobra muito para o aprendizado de maquina fazer. '
                    'O trabalho estava na engenharia de variavel, nao na escolha do modelo.'),
    ]:
        L = ad.texto_longo(ws, L, rot, txt)
    L += 1

    L = ad.titulo(ws, L, 'O QUE ISSO EXPLICA, DE UMA VEZ')
    for rot, txt in [
        ('Linear empata com arvore', 'Em Cascavel, 0,8228 contra 0,8199. A relacao e linear '
                                     'mesmo: o gradient boosting nao tem nao-linearidade para '
                                     'capturar.'),
        ('Curitiba e diferente', 'La o HistGB ganha do linear (0,7483 contra 0,7132) porque o '
                                 'poa_ceu_claro esta ERRADO: o telhado tem dois planos e o '
                                 'modelo usa um so. A arvore corrige nao-linearmente o que a '
                                 'fisica errou. E a pendencia da potencia/geometria aparecendo '
                                 'como vantagem espuria de algoritmo.'),
        ('Embarcado desaba', 'Tirar a NASA e tirar o kc_horario, e sobra so geometria: 0,5837. '
                             'Bate quase exato com o conjunto EMBARCADO (0,5980), na aba '
                             'Modelos embarcado.'),
        ('Downscaling nao ajudou', 'A informacao ja estava dentro de poa_estimada. Reorganizar '
                                   'nao cria. Ver aba Cenarios irradiancia, cenario C.'),
        ('Sensor substitui a NASA', 'Um unico canal de irradiancia fecha 99% do vao entre o '
                                    'embarcado e o completo. Ver a secao SENSOR DE IRRADIANCIA '
                                    'logo abaixo.'),
    ]:
        L = ad.texto_longo(ws, L, rot, txt)
    L += 1

    L = ad.titulo(ws, L, 'SENSOR DE IRRADIANCIA: SUBSTITUI A NASA POWER?')
    S = pd.read_csv(CSV_SENSOR, sep=';', decimal=',', encoding='utf-8-sig')
    L = ad.tabela(ws, L, S, larguras={'config': 34, 'n_preditores': 14},
                  formatos={'R2_Linear': '0.0000', 'R2_HistGB': '0.0000',
                            'R2_melhor': '0.0000', 'MAE_Linear': '#,##0.0',
                            'MAE_HistGB': '#,##0.0'},
                  destaque=lambda r: str(r[1]).startswith('B.'))
    for rot, txt in [
        ('Resposta', 'Sim, com folga. O vao entre o embarcado e o completo e 0,225 em Cascavel '
                     'e 0,232 em Curitiba. UM canal de irradiancia fecha 99,3% e 98,7% dele. '
                     'Todo o resto da NASA (nuvens, aerossol, umidade, chuva, vento, '
                     'temperatura diaria, Kt diario: oito variaveis) vale os ~1% restantes.'),
        ('O minimo', 'POA + temperatura, DOIS preditores, da 0,8201 em Cascavel. Praticamente '
                     'empata com as 20 colunas. Piranometro, termometro e relogio bastam.'),
        ('E o sensor supera', 'A linha B usa irradiancia de QUALIDADE NASA, ruim em dois '
                              'sentidos. Exatidao: o kc horario da NASA tem R2 NEGATIVO contra '
                              'o kc medido (-0,38 e -0,59). Resolucao: e horaria, e 17% a 21% '
                              'da variacao do kc de 5 min mora dentro da hora. Um piranometro '
                              'no plano dos modulos corrige os dois.'),
        ('CORRECAO IMPORTANTE', 'Versoes anteriores desta documentacao diziam que o '
                                'piranometro valia +0,18 de R2, tirado do cenario B da aba '
                                'Cenarios irradiancia. AQUELE NUMERO E OTIMISTA DEMAIS e nao '
                                'deve ser usado: o G_inv de la carrega junto o estado da usina '
                                '(sujeira, sombreamento, eficiencia do inversor), que um '
                                'piranometro nao mede. Um sensor da a irradiancia, nao o '
                                'desempenho.'),
        ('O que os dados sustentam', 'PISO: +0,22 de R2 sobre o embarcado sem sensor, com '
                                     'irradiancia de qualidade NASA. Isso e medido. TETO: nao '
                                     'e mensuravel sem o sensor. O residuo que sobraria depois '
                                     'de uma POA exata e a variacao de estado da usina, e nao '
                                     'ha como separa-la com os dados atuais. A unica afirmacao '
                                     'segura e que um sensor real fica ACIMA de 0,82 em '
                                     'Cascavel; quanto acima, nao se sabe.'),
        ('Curitiba ganha mais', 'Na linha B o HistGB ainda bate o linear la (0,7454 contra '
                                '0,7085) porque o poa_ceu_claro de plano unico esta errado. Com '
                                'um piranometro fisico isso desaparece: o sensor mede o plano '
                                'real, e o erro de geometria some junto. Curitiba ganharia mais '
                                'que Cascavel, por um motivo que nao aparece nesta tabela.'),
        ('Script', 'referencia/sensor_irradiancia.py'),
    ]:
        L = ad.texto_longo(ws, L, rot, txt)
    L += 1

    L = ad.titulo(ws, L, 'CONSEQUENCIA PRATICA')
    L = ad.texto_longo(ws, L, 'Onde investir',
                       'A comparacao de 13 algoritmos, e depois a de 20, respondeu a pergunta '
                       'errada. A diferenca entre o melhor e o pior modelo razoavel e 0,03 de '
                       'R2. A diferenca entre ter e nao ter poa_estimada e 0,24. Se for '
                       'investir esforco: resolver a geometria de Curitiba e trocar o kc da '
                       'NASA por fonte melhor ou por medicao. Nao em hiperparametro nem em '
                       'arquitetura.')
    L = ad.texto_longo(ws, L, 'O projeto em uma linha',
                       'Vinte preditores fazem o trabalho de dois. A NASA POWER inteira esta '
                       'ali como substituta ruim de um piranometro, e uma substituta que, '
                       'alem de ruim, chega com dias de atraso, o que inviabiliza qualquer uso '
                       'em tempo real.')
    return ws, ini, len(A)



###############################################################################
# CORRECOES APLICADAS AS ABAS ORIGINAIS
###############################################################################


def corrige_qualidade(ws):
    """Aplica os dois erros factuais apontados na aba Revisao.

    Nao e reescrita: sao dois textos que contradiziam o dado. O historico do que
    mudou fica na aba Revisao, marcado como APLICADO.
    """
    trocas = 0
    for linha in ws.iter_rows():
        for c in linha:
            v = str(c.value or '')
            if v == '367.129':
                c.value = '362.996'
                trocas += 1
            elif '47 % da base é noite' in v:
                c.value = ('47 % da base e noite. 367.129 diurnos ANTES de descartar '
                           'as linhas de alvo ausente')
                trocas += 1
            elif v.startswith('Mantidos: a arvore trata NaN'):
                c.value = ('Preditor NaN: mantido, a arvore trata. ALVO NaN: linha '
                           'descartada por build_base_modelagem.py')
                trocas += 1
    return trocas


def acrescenta_revisao(ws, linhas_extra):
    """Anexa linhas a tabela ja escrita por ad.aba_revisao."""
    # a tabela comeca na linha 4 (cabecalho) e segue ate a primeira linha vazia
    r = 5
    while ws.cell(row=r, column=1).value:
        r += 1
    for reg in linhas_extra:
        for j, v in enumerate(reg, start=1):
            c = ws.cell(row=r, column=j, value=v)
            c.alignment = ad.Alignment(wrap_text=True, vertical='top')
            if j == 2:
                c.font = Font(bold=True)
        ws.row_dimensions[r].height = 74
        r += 1
    return r


###############################################################################
# GRAFICOS
###############################################################################


def graficos_dados(wb, ws_tarifas, l_mensal, n_mensal):
    ws = ad.nova_aba(wb, 'Graficos', 'A serie tarifaria usada para custear as series de 5 min.')
    ch = LineChart()
    ch.add_data(Reference(ws_tarifas, min_col=3, min_row=l_mensal, max_col=3,
                          max_row=l_mensal + n_mensal), titles_from_data=True)
    ch.add_data(Reference(ws_tarifas, min_col=2, min_row=l_mensal, max_col=2,
                          max_row=l_mensal + n_mensal), titles_from_data=True)
    ch.set_categories(Reference(ws_tarifas, min_col=1, min_row=l_mensal + 1, max_col=1,
                                max_row=l_mensal + n_mensal))
    ch.title = 'Tarifa Copel-DIS B1: a queda de 2022 e o ICMS, a alta de 2026 e a RTP'
    ch.y_axis.title = 'R$/kWh'
    ch.width, ch.height = 26, 12
    ch.style = 2
    ws.add_chart(ch, 'A4')
    return ws


def graficos_resultados(wb, ref):
    ws = ad.nova_aba(wb, 'Graficos', 'Seis comparacoes. Graficos nativos do Excel, editaveis.')

    def coloca(ch, anc, t, larg=26, alt=11):
        ch.title = t
        ch.width, ch.height = larg, alt
        ch.style = 2
        ws.add_chart(ch, anc)

    src, l0, n = ref['cenarios']
    ch = BarChart(); ch.type = 'col'; ch.gapWidth = 60
    ch.add_data(Reference(src, min_col=3, min_row=l0, max_col=3, max_row=l0 + n),
                titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=l0 + 1, max_col=2, max_row=l0 + n))
    ch.y_axis.title = 'R2 no teste'; ch.y_axis.scaling.min = 0.6
    ch.dLbls = DataLabelList(); ch.dLbls.showVal = True
    coloca(ch, 'A4', '1. Cenarios de irradiancia: B e vazamento, nao ganho')

    src, l0, n = ref['economia_ano']
    ch = LineChart(); ch.marker = True
    ch.add_data(Reference(src, min_col=9, min_row=l0, max_col=9, max_row=l0 + n),
                titles_from_data=True)
    ch.add_data(Reference(src, min_col=7, min_row=l0, max_col=7, max_row=l0 + n),
                titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=l0 + 1, max_col=1, max_row=l0 + n))
    ch.y_axis.title = 'R$/kWh'; ch.x_axis.title = 'ano'
    coloca(ch, 'A27', '2. Cascavel: o kWh gerado vale ~1/4 da tarifa de varejo')

    src, l0, n = ref['alavancas']
    ch = BarChart(); ch.type = 'bar'; ch.gapWidth = 50
    ch.add_data(Reference(src, min_col=4, min_row=l0, max_col=4, max_row=l0 + n),
                titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=l0 + 1, max_col=1, max_row=l0 + n))
    ch.x_axis.title = 'R$ por ano'
    ch.dLbls = DataLabelList(); ch.dLbls.showVal = True
    coloca(ch, 'A50', '3. Deslocar carga vale 6x mais que tudo que o modelo pode dar')

    src = wb['Comparacao de modelos']
    ch = BarChart(); ch.type = 'bar'; ch.gapWidth = 40
    ch.add_data(Reference(src, min_col=8, min_row=4, max_col=8, max_row=17), titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=5, max_col=1, max_row=17))
    ch.x_axis.title = 'R2 medio das duas usinas'
    coloca(ch, 'A73', '4. Os 13 algoritmos: HistGradientBoosting escolhido por tempo, nao por R2')

    # 5 - R2 contra tamanho, escala log
    src, l0, n = ref['dispersao']
    ch = ScatterChart(); ch.style = 13
    xs = Reference(src, min_col=2, min_row=l0 + 1, max_col=2, max_row=l0 + n)
    ys = Reference(src, min_col=3, min_row=l0, max_col=3, max_row=l0 + n)
    s = Series(ys, xs, title_from_data=True)
    s.marker.symbol = 'circle'
    s.graphicalProperties.line.noFill = True
    ch.series.append(s)
    ch.x_axis.title = 'tamanho do modelo (KB, escala log)'
    ch.y_axis.title = 'R2'
    ch.x_axis.scaling.logBase = 10
    coloca(ch, 'A96', '5. R2 contra tamanho: o linear de 0,7 KB empata com arvores de 389 KB')

    # 6 - completo contra embarcado
    src, l0, n = ref['preco_embarcar']
    ch = BarChart(); ch.type = 'col'; ch.gapWidth = 70
    ch.add_data(Reference(src, min_col=2, min_row=l0, max_col=3, max_row=l0 + n),
                titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=l0 + 1, max_col=1, max_row=l0 + n))
    ch.y_axis.title = 'melhor R2'
    ch.dLbls = DataLabelList(); ch.dLbls.showVal = True
    coloca(ch, 'A119', '6. O preco de embarcar: sem NASA em tempo real, perde-se ~0,22 de R2')

    # 7 - ablacao
    src, l0, n = ref['ablacao']
    ch = BarChart(); ch.type = 'col'; ch.gapWidth = 60
    ch.add_data(Reference(src, min_col=4, min_row=l0, max_col=4, max_row=l0 + n),
                titles_from_data=True)
    ch.add_data(Reference(src, min_col=6, min_row=l0, max_col=6, max_row=l0 + n),
                titles_from_data=True)
    ch.set_categories(Reference(src, min_col=1, min_row=l0 + 1, max_col=2, max_row=l0 + n))
    ch.y_axis.title = 'R2 no teste'
    ch.dLbls = DataLabelList(); ch.dLbls.showVal = True
    coloca(ch, 'A142', '7. Uma coluna (poa_estimada) entrega 99,6% do resultado em Cascavel')
    return ws


###############################################################################
# MONTAGEM
###############################################################################

if __name__ == '__main__':
    origem = abre_origem()

    atual, fisc, ucs, mensal, cal = ad.dados_tarifas()
    g, alav, val, auto = ad.dados_economia(cal)
    cen, var = ad.dados_cenarios()

    # ---------------------------------------------------------------- DADOS
    wd = Workbook()
    wd.remove(wd.active)
    leiame(wd, 'Documentacao da base — DADOS',
           'Usinas Usina Cascavel (Cascavel-PR) e Usina Curitiba (Curitiba-PR)',
           [('O QUE E ESTA PLANILHA',
             [('Conteudo', 'O que a base E: de onde vem cada coluna, o que foi descartado, a '
                           'fisica que gera as derivadas, a qualidade do dado bruto e a base '
                           'tarifaria usada para custear as series.'),
              ('A outra metade', 'Os resultados — comparacao de modelos, TFLite, irradiancia '
                                 'inversa e economia — estao em Documentacao_Resultados.xlsx.'),
              ('A base', 'Dados de 5 minutos do inversor Fronius cruzados com a reanalise NASA '
                         'POWER. 620.278 registros diurnos, 28 colunas. O alvo e a potencia CA '
                         'media do intervalo.')]),
            ('AS ABAS',
             [('Colunas da base', 'as 28 colunas, o motivo de cada uma e a equacao quando existe'),
              ('Colunas removidas', 'o que saiu do arquivo bruto e por que'),
              ('Equacoes', 'a fisica completa, da geometria solar ate o indice de desempenho'),
              ('Qualidade dos dados', 'faltantes, duplicatas, outliers e o que foi feito'),
              ('Tarifas', 'a base tarifaria da Copel-DIS e as 4 colunas de custo'),
              ('Graficos', 'a serie tarifaria mensal'),
              ('Revisao', 'conferencia das abas originais contra os dados')]),
            ('QUATRO REGRAS QUE NAO PODEM SER QUEBRADAS',
             [('1.', 'Nao reintroduza as colunas removidas por vazamento. Sao o alvo reescrito.'),
              ('2.', 'Nao use train_test_split aleatorio. Separe por data (o script ja faz).'),
              ('3.', 'O alvo nao e estacionario: as usinas mudaram de estado no meio da serie.'),
              ('4.', 'Nao use as colunas de tarifa como preditor. Sao funcao-degrau da data: '
                     'no corte temporal viram proxy de ano.')])])
    for nome in ABAS_DADOS:
        copia_aba(origem[nome], wd)
    n_corr = corrige_qualidade(wd['Qualidade dos dados'])
    ws_t, l_mensal, n_mensal = ad.aba_tarifas(wd, atual, fisc, ucs, mensal)
    graficos_dados(wd, ws_t, l_mensal, n_mensal)
    ws_rev = ad.aba_revisao(wd)
    acrescenta_revisao(ws_rev, [
        ('Qualidade dos dados', 'APLICADO',
         'Contagem de diurnos de Cascavel e o tratamento de NaN.',
         'Corrigido nesta versao: 367.129 -> 362.996, e a frase sobre NaN agora separa '
         'preditor de alvo.',
         'Feito. %d celulas alteradas. O texto anterior esta no arquivo unico '
         'Documentacao_Base_Modelagem.xlsx, preservado.' % n_corr),
        ('Colunas da base', 'ACHADO NOVO',
         'poa_ceu_claro marcada como "PREDITOR - o mais importante".',
         'Confirmado com numero: poa_estimada (= poa_ceu_claro x kc_horario) sozinha '
         'entrega 99,6% do R2 de Cascavel e 95,0% do de Curitiba.',
         'Ver Documentacao_Resultados.xlsx, aba Ablacao. A equacao esta na aba Equacoes, '
         'celulas C21 e C23.'),
    ])
    wd.save(SAIDA_DADOS)
    print('OK  %s  -> %s' % (SAIDA_DADOS.name, ', '.join(wd.sheetnames)))

    # ----------------------------------------------------------- RESULTADOS
    wr = Workbook()
    wr.remove(wr.active)
    leiame(wr, 'Documentacao da base — RESULTADOS',
           'O que foi encontrado, e quanto disso vale',
           [('O QUE E ESTA PLANILHA',
             [('Conteudo', 'O que foi ENCONTRADO: comparacao de algoritmos, modelos para '
                           'embarcamento em TensorFlow Lite, o teste de estimar irradiancia '
                           'pela potencia e o valor economico de tudo isso.'),
              ('A outra metade', 'A descricao da base — colunas, equacoes, qualidade e tarifas — '
                                 'esta em Documentacao_Dados.xlsx.')]),
            ('AS ABAS',
             [('Comparacao de modelos', 'os 13 algoritmos da primeira rodada, nas duas usinas'),
              ('Modelos embarcado', '20 modelos e 2 conjuntos de preditores, com TensorFlow Lite'),
              ('Cenarios irradiancia', 'o teste de estimar irradiancia pela potencia'),
              ('Economia', 'o valor realizado do kWh e as alavancas em R$/ano'),
              ('Graficos', 'seis comparacoes, graficos nativos do Excel')]),
            ('O FIO CONDUTOR',
             [('0. COMECE AQUI', 'Aba Ablacao. UMA coluna, poa_estimada, num modelo linear, '
                                 'entrega 99,6% do R2 de Cascavel. A escolha de algoritmo vale '
                                 '0,03; ter ou nao ter essa coluna vale 0,24. Tudo abaixo se '
                                 'le melhor depois disso.'),
              ('1. O modelo', 'HistGradientBoosting com R2 0,8047 em Cascavel e 0,7170 em '
                              'Curitiba, escolhido por tempo de treino e nao por R2.'),
              ('2. Melhorar o modelo', 'Nao da para quebrar a NASA em 5 min pela potencia: o '
                                       'ganho aparente e vazamento. Um sensor de irradiancia '
                                       'fecha 99% do vao ate o modelo completo (aba Ablacao).'),
              ('3. Embarcar', 'TFLite int8 cabe em 3,4 KB. Mas sem NASA em tempo real o teto '
                              'cai ~0,22 de R2, e em Cascavel um linear de 0,7 KB ganha de '
                              'todos eles.'),
              ('4. Quanto vale', 'Em Cascavel, R$ 109/ano. Cada kWh gerado realiza 25% da '
                                 'tarifa, porque 2,34x de cobertura faz o credito expirar. '
                                 'Deslocar carga vale 6x mais que qualquer modelo.')])])
    for nome in ABAS_RESULTADOS:
        copia_aba(origem[nome], wr)
    ws_abl, l_abl, n_abl = aba_ablacao(wr)
    wr.move_sheet('Ablacao', offset=-1)      # logo depois do Leia-me: e por onde se comeca
    _, ini_tab, n_tab, ini_disp, n_disp, resumo = aba_embarcado(wr)
    ws_c, l_cen, n_cen = ad.aba_cenarios(wr, cen, var)
    ws_e, l_g, n_g, l_a, n_a = ad.aba_economia(wr, g, alav, val, auto)

    # tabela pequena que alimenta o grafico 6
    ws_emb = wr['Modelos embarcado']
    base_l = ws_emb.max_row + 3
    ad.titulo(ws_emb, base_l, 'FONTE DO GRAFICO 6')
    dfp = pd.DataFrame(resumo)[['usina', 'melhor_COMPLETO', 'melhor_EMBARCADO']]
    l_preco = base_l + 1
    ad.tabela(ws_emb, l_preco, dfp,
              larguras={'melhor_COMPLETO': 18, 'melhor_EMBARCADO': 18},
              formatos={'melhor_COMPLETO': '0.0000', 'melhor_EMBARCADO': '0.0000'})

    graficos_resultados(wr, dict(cenarios=(ws_c, l_cen, n_cen),
                                 economia_ano=(ws_e, l_g, n_g),
                                 alavancas=(ws_e, l_a, n_a),
                                 dispersao=(ws_emb, ini_disp, n_disp),
                                 preco_embarcar=(ws_emb, l_preco, len(dfp)),
                                 ablacao=(ws_abl, l_abl, n_abl)))
    wr.save(SAIDA_RESULTADOS)
    print('OK  %s  -> %s' % (SAIDA_RESULTADOS.name, ', '.join(wr.sheetnames)))
