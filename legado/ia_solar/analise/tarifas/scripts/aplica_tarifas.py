# -*- coding: utf-8 -*-
###############################################################################
# TARIFAS NAS SERIES DE 5 MINUTOS -> PLANILHA PARA O HOMER
#
# Junta a base tarifaria oficial da Copel-DIS (ANEEL, dados abertos) as series
# brutas de 5 min de cada usina e grava um XLSX por usina com:
#
#   aba <usina>_5min   a serie completa + 4 colunas de tarifa por linha
#   aba Tarifas        TUSD/TE homologadas por vigencia (B1 e B3, conv. e branca)
#   aba Bandeiras      bandeira acionada mes a mes e o adicional
#   aba Componentes    abertura da TUSD/TE do B1 na vigencia atual (inclui Fio B)
#   aba Parametros     ICMS, PIS/COFINS e enquadramento da UC
#   aba HOMER          os campos prontos para digitar no componente Grid
#
# Roda sem rede: consome os CSV de ../dados/, gerados por baixa_tarifas_aneel.py.
#
# Requisitos: pandas, openpyxl
#   pip install pandas openpyxl
###############################################################################

import time
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

###############################################################################
# CONFIGURACAO
###############################################################################

pasta_tarifas = Path(__file__).resolve().parents[1] / 'dados'
pasta_projeto = Path(__file__).resolve().parents[3]

USINAS = {
    'Curitiba': dict(
        rotulo='curitiba',
        titulo='USINA_CURITIBA - CURITIBA-PR - Fronius Symo 12.0-3',
        caminho_csv=pasta_projeto / r'analise/curitiba/dados/curitiba_5min_2021-2026.csv',
        caminho_xlsx=pasta_projeto / r'analise/curitiba/dados/curitiba_5min_2021-2026.xlsx',
        aba='curitiba_5min',
    ),
    'Cascavel': dict(
        rotulo='cascavel',
        titulo='USINA_CASCAVEL - CASCAVEL-PR - Fronius Primo 4.0-1',
        caminho_csv=pasta_projeto / r'analise/cascavel/dados/dados_5min_2019-2026.csv',
        caminho_xlsx=pasta_projeto / r'analise/cascavel/dados/dados_5min_2019-2026.xlsx',
        aba='cascavel_5min',
    ),
}

# B1 residencial convencional: e o enquadramento das duas UCs.
SUBGRUPO, MODALIDADE = 'B1', 'Convencional'

FMT_DATA = 'yyyy-mm-dd hh:mm'
FMT_TARIFA = '0.0000'
LARGURAS = {'timestamp': 18, 'data_hora_raw': 17, 'arquivo': 38, 'planilha': 12,
            'tarifa_sem_impostos_RS_kWh': 15, 'bandeira': 13,
            'adic_bandeira_RS_kWh': 15, 'tarifa_cheia_RS_kWh': 15}

###############################################################################
# BASE TARIFARIA
###############################################################################


def le_tarifas():
    """Vigencias do B1 residencial convencional, em R$/kWh sem impostos."""
    t = pd.read_csv(pasta_tarifas / 'copel_tarifas_historico.csv', encoding='utf-8-sig')
    t = t[(t.subgrupo == SUBGRUPO) & (t.modalidade == MODALIDADE)].copy()
    t['vigencia_ini'] = pd.to_datetime(t.vigencia_ini)
    t['vigencia_fim'] = pd.to_datetime(t.vigencia_fim)
    t['tarifa_RS_kWh'] = t.total_RS_MWh / 1000.0
    return t.sort_values('vigencia_ini').reset_index(drop=True)


def le_fiscais():
    f = pd.read_csv(pasta_tarifas / 'parametros_fiscais.csv', encoding='utf-8-sig')
    icms = f[f.tributo == 'ICMS'].copy()
    icms['vigencia_ini'] = pd.to_datetime(icms.vigencia_ini)
    icms = icms.sort_values('vigencia_ini').reset_index(drop=True)
    pis = float(f.loc[f.tributo == 'PIS_COFINS', 'aliquota_pct'].iloc[0])
    return icms, pis


def le_bandeiras():
    b = pd.read_csv(pasta_tarifas / 'bandeiras_mensal.csv', encoding='utf-8-sig')
    b['adic_RS_kWh'] = b.adicional_RS_MWh / 1000.0
    return b.set_index('competencia')


def monta_calendario(inicio, fim, tarifas, icms, pis_cofins, bandeiras):
    """Uma linha por dia, com a tarifa cheia ja resolvida.

    tarifa_cheia = (tarifa_sem_impostos + adicional_bandeira) / (1 - ICMS - PIS/COFINS)

    ICMS e PIS/COFINS incidem "por dentro": compoem a propria base de calculo.
    """
    cal = pd.DataFrame({'dia': pd.date_range(inicio.normalize(), fim.normalize(), freq='D')})

    cal = pd.merge_asof(cal, tarifas[['vigencia_ini', 'tarifa_RS_kWh', 'resolucao']],
                        left_on='dia', right_on='vigencia_ini', direction='backward')
    cal = pd.merge_asof(cal, icms[['vigencia_ini', 'aliquota_pct']].rename(
                            columns={'vigencia_ini': 'vig_icms', 'aliquota_pct': 'icms_pct'}),
                        left_on='dia', right_on='vig_icms', direction='backward')

    comp = cal.dia.dt.strftime('%Y-%m')
    cal['bandeira'] = comp.map(bandeiras.bandeira).fillna('sem dado')
    cal['adic_bandeira_RS_kWh'] = comp.map(bandeiras.adic_RS_kWh).fillna(0.0)

    fator = 1.0 / (1.0 - cal.icms_pct / 100.0 - pis_cofins / 100.0)
    cal['tarifa_sem_impostos_RS_kWh'] = cal.tarifa_RS_kWh.round(6)
    cal['tarifa_cheia_RS_kWh'] = ((cal.tarifa_RS_kWh + cal.adic_bandeira_RS_kWh) * fator).round(6)
    cal['adic_bandeira_RS_kWh'] = cal.adic_bandeira_RS_kWh.round(6)
    return cal.set_index(cal.dia.dt.normalize())


###############################################################################
# ABAS DE REFERENCIA
###############################################################################


def escreve_tabela(wb, nome, df, formatos=None, largura_padrao=16):
    ws = wb.create_sheet(nome)
    for i, c in enumerate(df.columns, start=1):
        ws.column_dimensions[get_column_letter(i)].width = max(largura_padrao, len(str(c)) + 2)
    ws.freeze_panes = 'A2'
    cab = []
    for c in df.columns:
        cel = WriteOnlyCell(ws, value=str(c))
        cel.font = Font(bold=True)
        cel.alignment = Alignment(horizontal='center', wrap_text=True)
        cab.append(cel)
    ws.append(cab)
    for linha in df.itertuples(index=False, name=None):
        saida = []
        for c, v in zip(df.columns, linha):
            cel = WriteOnlyCell(ws, value=v)
            if formatos and c in formatos:
                cel.number_format = formatos[c]
            saida.append(cel)
        ws.append(saida)


def aba_homer(wb, usina, cfg, cal, tarifas, pis_cofins):
    """Campos do componente Grid do HOMER, ja com o numero pronto."""
    hoje = cal.iloc[-1]
    disp = int(cfg['disponibilidade_kWh_mes'])
    tarifa = float(hoje.tarifa_cheia_RS_kWh)
    linhas = [
        ('Usina', cfg['usina'], '', ''),
        ('Distribuidora', 'COPEL-DIS (Parana)', '', 'Subgrupo B1, modalidade convencional'),
        ('Vigencia usada', str(hoje.dia.date()), '', str(hoje.resolucao)),
        ('', '', '', ''),
        ('--- COMPONENTE GRID ---', '', '', ''),
        ('Grid power price', round(tarifa, 4), 'R$/kWh',
         'Tarifa cheia: TUSD+TE + bandeira %s, com ICMS e PIS/COFINS' % hoje.bandeira),
        ('Grid sellback rate', round(tarifa, 4), 'R$/kWh',
         'Compensacao 1:1 em kWh. A UC tem direito adquirido da Lei 14.300 ate 2045.'),
        ('Net metering', 'Sim', '',
         'Creditos em kWh, validade 60 meses. Nao ha pagamento por excedente.'),
        ('Net purchases capacity', 0, 'kW', 'Grupo B nao tem contrato de demanda'),
        ('Grid demand rate', 0, 'R$/kW/mes', 'Grupo B nao tem cobranca de demanda'),
        ('Sale capacity', 0, 'kW', 'Sem venda de energia, apenas compensacao'),
        ('', '', '', ''),
        ('--- ENCARGO FIXO MENSAL ---', '', '', ''),
        ('Custo de disponibilidade', disp, 'kWh/mes',
         'Ligacao %s. Piso cobrado mesmo com a geracao zerando o consumo.' % cfg['ligacao']),
        ('Custo de disponibilidade', round(disp * tarifa, 2), 'R$/mes',
         '%d kWh x %.4f R$/kWh' % (disp, tarifa)),
        ('COSIP / CIP', 'A DEFINIR', 'R$/mes',
         'Contribuicao municipal de iluminacao publica. Nao e publicada pela ANEEL: '
         'tem de sair de uma fatura recente.'),
        ('', '', '', ''),
        ('--- PREMISSAS ---', '', '', ''),
        ('ICMS', float(hoje.icms_pct), '%', 'Parana, energia eletrica, por dentro'),
        ('PIS/COFINS', pis_cofins, '%',
         'PARAMETRO. Nominal 1,65 + 7,60. A aliquota efetiva e apurada mes a mes '
         'pela Copel e costuma ser menor: conferir na fatura.'),
        ('Bandeira do ultimo mes', hoje.bandeira, '',
         '%.4f R$/kWh de adicional, sem impostos' % hoje.adic_bandeira_RS_kWh),
        ('Fio B', 'nao cobrado', '',
         'Conexao em %s, anterior a 07/01/2023: compensacao integral ate 31/12/2045.'
         % cfg['data_conexao']),
        ('Fator de emissao da rede', 'A DEFINIR', 'g CO2/kWh',
         'Grid emissions no HOMER. Usar o fator medio do SIN publicado pelo MCTI.'),
        ('', '', '', ''),
        ('--- SE FOR SIMULAR TARIFA BRANCA ---', '', '', ''),
        ('Ponta', '', '', 'Dias uteis 17:30-20:30'),
        ('Intermediario', '', '', 'Dias uteis 16:30-17:30 e 20:30-21:30'),
        ('Fora ponta', '', '', 'Demais horas, sabados, domingos e feriados'),
        ('Valores', 'aba Tarifas', '', "Linhas com modalidade='Branca'"),
    ]
    df = pd.DataFrame(linhas, columns=['campo', 'valor', 'unidade', 'observacao'])
    ws = wb.create_sheet('HOMER')
    for i, w in enumerate([30, 18, 12, 88], start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    cab = []
    for c in df.columns:
        cel = WriteOnlyCell(ws, value=c)
        cel.font = Font(bold=True)
        cab.append(cel)
    ws.append(cab)
    for linha in df.itertuples(index=False, name=None):
        celulas = []
        for v in linha:
            cel = WriteOnlyCell(ws, value=v)
            if isinstance(v, str) and v.startswith('---'):
                cel.font = Font(bold=True)
            celulas.append(cel)
        ws.append(celulas)


###############################################################################
# MONTAGEM DO XLSX
###############################################################################


def processa(usina, cfg_usina, cfg_uc, tarifas, icms, pis_cofins, bandeiras,
             tab_tarifas, tab_bandeiras, tab_componentes, tab_fiscais):
    t0 = time.time()
    csv = cfg_usina['caminho_csv']
    colunas = list(pd.read_csv(csv, nrows=0).columns)
    novas = ['tarifa_sem_impostos_RS_kWh', 'bandeira',
             'adic_bandeira_RS_kWh', 'tarifa_cheia_RS_kWh']

    # limites da serie, para dimensionar o calendario
    ts = pd.read_csv(csv, usecols=['timestamp'], parse_dates=['timestamp']).timestamp
    cal = monta_calendario(ts.min(), ts.max(), tarifas, icms, pis_cofins, bandeiras)
    n_total = len(ts)
    del ts

    wb = Workbook(write_only=True)
    ws = wb.create_sheet(cfg_usina['aba'])
    todas = colunas + novas
    for i, c in enumerate(todas, start=1):
        ws.column_dimensions[get_column_letter(i)].width = LARGURAS.get(c, max(11, len(c) + 2))
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = 'A1:%s%d' % (get_column_letter(len(todas)), n_total + 1)

    cab = []
    for c in todas:
        cel = WriteOnlyCell(ws, value=c)
        cel.font = Font(bold=True)
        cel.alignment = Alignment(horizontal='center', wrap_text=True)
        cab.append(cel)
    ws.append(cab)

    n = 0
    for bloco in pd.read_csv(csv, chunksize=50_000, parse_dates=['timestamp']):
        dia = bloco.timestamp.dt.normalize()
        bloco['tarifa_sem_impostos_RS_kWh'] = dia.map(cal.tarifa_sem_impostos_RS_kWh).values
        bloco['bandeira'] = dia.map(cal.bandeira).values
        bloco['adic_bandeira_RS_kWh'] = dia.map(cal.adic_bandeira_RS_kWh).values
        bloco['tarifa_cheia_RS_kWh'] = dia.map(cal.tarifa_cheia_RS_kWh).values
        for linha in bloco[todas].itertuples(index=False, name=None):
            c_ts = WriteOnlyCell(ws, value=linha[0])
            c_ts.number_format = FMT_DATA
            fim = []
            for v in linha[-4:]:
                cel = WriteOnlyCell(ws, value=v)
                if not isinstance(v, str):
                    cel.number_format = FMT_TARIFA
                fim.append(cel)
            ws.append([c_ts, *linha[1:-4], *fim])
        n += len(bloco)
        print('   %7d / %d linhas  %6.1f s' % (n, n_total, time.time() - t0), flush=True)

    fmt_t = {'tusd_RS_MWh': '0.00', 'te_RS_MWh': '0.00', 'total_RS_MWh': '0.00'}
    escreve_tabela(wb, 'Tarifas', tab_tarifas, fmt_t, 14)
    escreve_tabela(wb, 'Bandeiras', tab_bandeiras, {'adicional_RS_MWh': '0.00'}, 14)
    escreve_tabela(wb, 'Componentes', tab_componentes, {'valor_RS_MWh': '0.0000'}, 14)
    escreve_tabela(wb, 'Parametros', tab_fiscais, None, 14)
    aba_homer(wb, usina, cfg_uc, cal, tarifas, pis_cofins)

    wb.save(cfg_usina['caminho_xlsx'])
    print('   OK  %s  (%d linhas, %d colunas)  %.1f s'
          % (cfg_usina['caminho_xlsx'].name, n, len(todas), time.time() - t0), flush=True)


if __name__ == '__main__':
    tarifas = le_tarifas()
    icms, pis_cofins = le_fiscais()
    bandeiras = le_bandeiras()

    tab_tarifas = pd.read_csv(pasta_tarifas / 'copel_tarifas_historico.csv', encoding='utf-8-sig')
    tab_bandeiras = pd.read_csv(pasta_tarifas / 'bandeiras_mensal.csv', encoding='utf-8-sig')
    tab_componentes = pd.read_csv(pasta_tarifas / 'copel_componentes_b1.csv', encoding='utf-8-sig')
    tab_fiscais = pd.read_csv(pasta_tarifas / 'parametros_fiscais.csv', encoding='utf-8-sig')
    ucs = pd.read_csv(pasta_tarifas / 'parametros_usinas.csv', encoding='utf-8-sig')

    for usina, cfg_usina in USINAS.items():
        print(cfg_usina['titulo'])
        cfg_uc = ucs[ucs.usina == usina].iloc[0].to_dict()
        processa(usina, cfg_usina, cfg_uc, tarifas, icms, pis_cofins, bandeiras,
                 tab_tarifas, tab_bandeiras, tab_componentes, tab_fiscais)
