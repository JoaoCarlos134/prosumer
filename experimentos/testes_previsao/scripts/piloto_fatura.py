# -*- coding: utf-8 -*-
"""Piloto E6 (16/10/2026): a conta da `prosumer.economics.brazil` reproduz as faturas reais da Copel?

PERGUNTA. Com a tarifa convencional da Copel (`COPEL-DIS`, dados abertos da ANEEL), bandeiras, custo de
disponibilidade, SCEE / GD I da Lei 14.300 (usina de 2019) e ICMS + PIS/COFINS, o `brazil.Setup(...).bill`
reproduz o total pago mes a mes pelo dono da usina de Cascavel (2018-2026)? Ate agora so houve a regressao do
porte (0,80622 R$/kWh medio de 2018 com os CSV do legado; a fatura de 2018 deu 0,8457) e o README diz que nenhuma
fatura real foi conferida.

DADOS (privados, so nesta maquina). Planilha feita a mao pelo dono com o resumo das faturas
(`FATURA`, abaixo; o script le dali e pula se nao existir; nada dela e copiado para o repositorio). Aba
`Fatura`, uma linha por ano e campo, colunas jan-dez = MES DE REFERENCIA da fatura: `Consumo [kWh]` (energia
importada da rede, registrador do medidor), `Injetado [kWh]` (desde 08/2019), `Pagamento [R$]` (total pago),
`Credito [kWh]` e `Expirar [kWh]` (saldo; nao usados: a injecao do mes cobre o consumo acima do minimo em
todas as faturas com geracao, entao o saldo acumulado nunca entra na conta, e isso e conferido abaixo). Cabecalho:
leitura no dia 9, pagamento no dia 27. NAO HA na planilha: COSIP, aliquotas de ICMS e PIS/COFINS, bandeira,
valor da energia separado do total. Faturas com consumo e pagamento: 01/2018 a 08/2026 (104); sem geracao (P0):
01/2018 a 07/2019 (19); com geracao (P1, GD I): 08/2019 a 08/2026 (85).

O que foi VISTO antes de fixar o portao (declarado para a revisao): a estrutura da planilha e os numeros brutos
dela (inevitavel ao ler a estrutura), as razoes injecao/geracao abaixo, e o minimo de 50 kWh pela conta do saldo
de 2019 (credito = injetado - (consumo - 50)). A biblioteca NAO foi rodada contra as faturas antes do commit
deste script. Observacao feita nos numeros brutos (nao na biblioteca): nas faturas com geracao o pagamento sobe
com o consumo (ex.: o mes de maior consumo de 2020 paga ~70% a mais que o vizinho), o que a leitura padrao da
biblioteca (`icms_exempt_compensated="all"`: fatura = minimo + COSIP, sem depender do consumo) nao preve. O
portao continua na leitura padrao, porque e ela que a biblioteca aplica para quem a usa.

COMO A SERIE E MONTADA (a biblioteca fatura uma serie horaria). Na tarifa convencional o preco nao depende da
hora (so do dia: vigencia e bandeira) e o SCEE compensa em kWh no mes; a conta depende so do total importado I e
do total injetado X do periodo e de como os dias se distribuem entre meses-calendario. Entao basta uma serie cujo
total bate com a fatura: consumo I espalhado igual nas horas 0-5 e 18-23 de cada dia, geracao X nas horas 10-13
(sem sobreposicao: importacao = I e exportacao = X exatos, autoconsumo zero; o consumo "atras do medidor" real e
desconhecido e nao muda a conta). Fuso fixo `Etc/GMT+3` (o do benchmark para as usinas).

QUAL PERIODO. A fatura de referencia M cobre o ciclo de leitura de ~9/(M-1) a ~8/M (estrutura conferida antes:
injecao / geracao medida do inversor, por fatura, tem desvio-padrao 0,068 no ciclo do dia 9 contra 0,158 no mes
M-1 e 0,150 no mes M; o script refaz e grava essa conferencia). Duas montagens, as duas pre-declaradas:
- `ciclo` (PRIMARIA): o ciclo 9/(M-1)..8/M em dois pedacos de mes-calendario, cada um faturado por uma chamada
  `Setup.bill` com sua fracao de dias f dos kWh e do minimo (`connection = 50 x f`); fatura = soma dos pedacos.
  E o pro-rata por dias de tarifa e bandeira que a Copel aplica. Dias exatos de leitura (+-2 dias) desconhecidos.
- `calendario`: a fatura M inteira no mes-calendario M-1 (o mes com ~22 dos ~30 dias), como faria um usuario
  do aplicativo com uma serie mensal (a biblioteca fatura meses-calendario, declarado no docstring dela).
Cada fatura e faturada sozinha (sem saldo inicial): vale porque I - 50 <= X em todas as faturas P1 (conferido;
se falhar em alguma, ela e excluida e listada).

ENTRADAS (sem fatura impressa com aliquotas: SUPOSICOES). `TariffBook.from_aneel("COPEL-DIS")` (B1 residencial
convencional, bandeiras mensais da ANEEL; cache em `dados/aneel_copel_b1.csv` e `dados/aneel_bandeiras.csv`,
licenca ODbL 1.0, atribuicao ANEEL). `from_aneel` aceita UMA aliquota para todas as datas; o ICMS do PR mudou no
periodo, entao a tabela de impostos do livro e trocada pela do legado (`parametros_fiscais.csv`): ICMS 29% ate
22/06/2022, 18% de 23/06/2022, 19% de 18/03/2024; PIS/COFINS 9,25% nominal em todo o periodo (limite superior: a
Copel apura a efetiva mes a mes, em geral menor; a inclinacao do diagnostico D1 mostra a efetiva implicita).
Ligacao: minimo de 50 kWh (`bifasico_3`), conferido pelo saldo de 2019. GD I por `connected="2019-07-26"` (1o dia
da serie de geracao). `gd2_minimum` e `after_2028` NAO entram (so valem para GD II ou depois de 2045): ficam no
padrao. `pis_cofins_exempt_compensated=True` (padrao). COSIP: nao esta na planilha nem na ANEEL (ver abaixo).

COSIP (contribuicao de iluminacao publica, municipal). Valor fixo por mes, desconhecido:
- em P0, para a fatura m: c_m = mediana, nas OUTRAS 18 faturas P0, de (pago - conta da biblioteca) (deixa um
  fora: a fatura m nao entra na propria COSIP);
- em P1: c = mediana nas 19 faturas P0 (fixa, estimada so com 2018-2019; se a COSIP mudou depois, o erro aparece
  como deriva por ano, diagnostico D2).

PORTAO (fixado antes de rodar; configuracao primaria = `ciclo`, padroes da biblioteca: `icms_exempt_compensated
="all"`, `bandeira_on_minimum=True`, ICMS da tabela do PR, PIS/COFINS 9,25%):
- G1 (energia, P0): |E - (pago - c_m)| / (pago - c_m) <= 2% em >= 80% das faturas P0 (>= 16 de 19), E = conta da
  biblioteca sem COSIP; e a COSIP estimada c (mediana das 19) entre R$ 0 e R$ 30.
- G2 (total, P0): |E + c_m - pago| / pago <= 3% em >= 80% das faturas P0.
- G3 (total, P1): |E + c - pago| / pago <= 3% em >= 80% das faturas P1 (>= 68 de 85).
PASSA se G1, G2 e G3 passam na primaria. Excluidas (listadas): faturas sem consumo ou pagamento; faturas em
que a biblioteca levanta erro (dado da ANEEL faltando); faturas P1 com I - 50 > X.
- G4 (mesmos criterios G1-G3 na montagem `calendario`, padroes): veredito proprio, "o jeito do aplicativo".

GRADE (uma BUSCA sobre as mesmas faturas, nao validacao; relatada, nao muda o veredito): montagem {ciclo,
calendario} x `icms_exempt_compensated` {"all", "te_only", "none", "PR48"} x `bandeira_on_minimum` {True, False}
= 16 configuracoes, cada uma com G1-G3. "PR48" = leitura do teto de 48 meses do Convenio ICMS 16/2015 par. 3 no
PR (adesao 1/7/2018, teto revogado em 29/12/2023): "none" nos pedacos de 07/2022 a 12/2023, "all" no resto
(montagem pela data de cada pedaco). Leitura que passar so na grade e hipotese para um piloto novo (com faturas
detalhadas), nao mudanca na biblioteca.

DIAGNOSTICOS (sem portao): D1 reta pago = a x E + b nas P0 (a = 1 se o preco por kWh bate; PIS/COFINS efetivo
implicito supondo ICMS certo); D2 erro relativo mediano por ano em P1 (deriva da COSIP); D3 G3 com a COSIP por
ano civil deixando um fora (c = mediana das outras faturas do mesmo ano): separa o nivel da variacao dentro do
ano; D4 para cada fatura fora da faixa, as marcas que podem explicar (bandeira muda no ciclo, ICMS muda no ciclo,
vigencia nova no ciclo, consumo alto) e qual leitura da grade fica mais perto. Pilotos sem Holm nem DM aqui: nao
ha teste estatistico, so contagem de faturas dentro da faixa.

SAIDA: `resultados/pilotos/fatura.json` so com agregados e ERROS RELATIVOS por fatura (sem kWh nem R$ da fatura;
a unica quantia gravada e a COSIP estimada). Nunca gravar nome, numero da UC, endereco ou coordenada exata.

Uso (ambiente da biblioteca, CPU, ~1-3 min; 1a vez baixa da ANEEL):
    python piloto_fatura.py baixa     # baixa e guarda o livro da ANEEL em dados/ (rede)
    python piloto_fatura.py           # roda (sem rede, a partir do cache)
"""
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

import comum  # poe o src/ do repositorio no caminho
from prosumer.contracts import EnergySeries
from prosumer.economics import brazil

FATURA = os.environ.get(
    "FATURA_CASCAVEL",
    r"C:\Users\L08741\OneDrive - Lactec\Documentos\2026\Projeto_IA\ia_solar\dados_brutos\cascavel"
    r"\Fatura de energia.xlsx",
)
TAR = comum.DADOS / "aneel_copel_b1.csv"
BAND = comum.DADOS / "aneel_bandeiras.csv"
PROV = comum.DADOS / "aneel_copel_proveniencia.json"
SAIDA = comum.RES / "pilotos" / "fatura.json"
FUSO = "Etc/GMT+3"
LEITURA = 9  # dia da leitura (cabecalho da planilha)
MINIMO = 50.0  # kWh, bifasico a tres fios (conferido pelo saldo de 2019)
CONECTADA = "2019-07-26"
ICMS_PR = [("1900-01-01", 0.29), ("2022-06-23", 0.18), ("2024-03-18", 0.19)]  # parametros_fiscais.csv
PIS_COFINS = 0.0925
PR48 = (pd.Timestamp("2022-07-01"), pd.Timestamp("2023-12-31"))
TOL_E, TOL_T, FRAC = 0.02, 0.03, 0.80
COSIP_MAX = 30.0
HORAS_C = list(range(0, 6)) + list(range(18, 24))
HORAS_G = [10, 11, 12, 13]


# ---------------------------------------------------------------------- ANEEL (cache)
def baixa():
    """O livro pelo `TariffBook.from_aneel` (aliquotas daqui sao trocadas em `livro`); guarda tarifas e
    bandeiras em CSV para rodar sem rede."""
    bk = brazil.TariffBook.from_aneel("COPEL-DIS", icms=0.29, pis_cofins=PIS_COFINS)
    t = bk.tariffs
    b = bk.bandeiras.reset_index()
    t.to_csv(TAR, index=False)
    b.to_csv(BAND, index=False)
    from dataclasses import asdict

    prov = [{k: str(v) for k, v in asdict(p).items()} for p in bk.provenance]
    PROV.write_text(json.dumps({"baixado_em": time.strftime("%Y-%m-%d %H:%M"), "licenca": "ODbL-1.0 (ANEEL, "
                               "Dados Abertos; base derivada redistribuida fica sob ODbL)", "fontes": prov},
                               indent=1, ensure_ascii=False))
    print(f"tarifas {len(t)} linhas, bandeiras {len(b)} meses ({b['month'].min()} a {b['month'].max()})")


def livro():
    t = pd.read_csv(TAR, parse_dates=["start", "end"])
    b = pd.read_csv(BAND, dtype={"month": str})
    taxes = pd.DataFrame({"start": [d for d, _ in ICMS_PR], "icms": [r for _, r in ICMS_PR],
                          "pis_cofins": PIS_COFINS})
    return brazil.TariffBook(t, b, taxes, None, "COPEL-DIS")


# ---------------------------------------------------------------------- planilha
def le_faturas():
    import openpyxl

    ws = openpyxl.load_workbook(FATURA, data_only=True, read_only=True)["Fatura"]
    campos = {"Consumo": "imp", "Injetado": "inj", "Pagamento": "pago"}
    linhas, ano = [], None
    for row in ws.iter_rows(min_row=5, values_only=True):
        if isinstance(row[0], int):
            ano = row[0]
        rot = str(row[1] or "")
        chave = next((v for k, v in campos.items() if rot.startswith(k)), None)
        if ano is None or chave is None:
            continue
        for m in range(12):
            v = row[2 + m]
            if isinstance(v, (int, float)):
                linhas.append({"ref": pd.Timestamp(ano, m + 1, 1), "campo": chave, "v": float(v)})
    f = pd.DataFrame(linhas).pivot_table(index="ref", columns="campo", values="v", aggfunc="first")
    f = f.reindex(columns=["imp", "inj", "pago"]).sort_index()
    f["inj"] = f["inj"].fillna(0.0)  # antes da usina: nada injetado
    return f[f["imp"].notna() & f["pago"].notna()]


# ---------------------------------------------------------------------- series e conta
def serie(dias, total, horas, qty):
    ds = pd.date_range(dias[0], dias[-1] + pd.Timedelta(hours=23), freq="h")
    y = np.where(np.isin(ds.hour, horas), total / (len(horas) * len(dias)), 0.0)
    fr = pd.DataFrame({"unique_id": "u", "ds": ds, "y": y})
    return EnergySeries.from_dataframe(fr, unit="kWh", quantity=qty, tz=FUSO, freq="h")


def pedacos(ref, montagem):
    """[(dias do pedaco, fracao)] da fatura de referencia `ref`."""
    if montagem == "calendario":
        m1 = ref - pd.DateOffset(months=1)
        return [(pd.date_range(m1, ref - pd.Timedelta(days=1), freq="D"), 1.0)]
    ini = ref - pd.DateOffset(months=1) + pd.Timedelta(days=LEITURA - 1)
    fim = ref + pd.Timedelta(days=LEITURA - 2)
    dias = pd.date_range(ini, fim, freq="D")
    a, b = dias[dias < ref], dias[dias >= ref]
    return [(a, len(a) / len(dias)), (b, len(b) / len(dias))]


def icms_leitura(leitura, mes):
    if leitura != "PR48":
        return leitura
    return "none" if PR48[0] <= mes <= PR48[1] else "all"


_SERIES, _PEDACO = {}, {}  # so velocidade (commit depois do portao): o resultado e o mesmo por construcao


def conta(book, fat, ref, montagem, leitura, band_min):
    """Conta da biblioteca (sem COSIP) da fatura `ref`, somando os pedacos.

    Memoizada por pedaco: as series nao dependem da leitura; a leitura do ICMS so entra pela energia
    compensada, que e zero sem injecao (P0), entao ali todas as leituras dao a mesma conta; "PR48" e "all" ou
    "none" em cada pedaco."""
    imp, inj = fat.loc[ref, "imp"], fat.loc[ref, "inj"]
    tot = 0.0
    for j, (dias, f) in enumerate(pedacos(ref, montagem)):
        icms = icms_leitura(leitura, dias[0])
        chave = (ref, montagem, j, icms if inj > 0 else "n/a", band_min)
        if chave not in _PEDACO:
            if (ref, montagem, j) not in _SERIES:
                _SERIES[(ref, montagem, j)] = (serie(dias, imp * f, HORAS_C, "consumption"),
                                               serie(dias, inj * f, HORAS_G, "generation"))
            cons, gen = _SERIES[(ref, montagem, j)]
            s = brazil.Setup(book, connection=MINIMO * f, connected=CONECTADA, icms_exempt_compensated=icms,
                             bandeira_on_minimum=band_min)
            b = s.bill(cons, gen)
            assert len(b.monthly) == 1
            r = b.monthly.iloc[0]
            assert abs(r["grid_import"] - imp * f) < 1e-6 and abs(r["export"] - inj * f) < 1e-6
            _PEDACO[chave] = float(r["energy_bill"])
        tot += _PEDACO[chave]
    return tot


# ---------------------------------------------------------------------- avaliacao
def avalia(E, fat, p0, p1):
    """Erros e condicoes G1-G3 para uma serie de contas E (indice = ref)."""
    pago = fat["pago"]
    res = (pago - E)[p0]
    c_loo = pd.Series({m: float(res.drop(m).median()) for m in p0})
    c = float(res.median())
    e1 = (E[p0] - (pago[p0] - c_loo)) / (pago[p0] - c_loo)
    e2 = (E[p0] + c_loo - pago[p0]) / pago[p0]
    e3 = (E[p1] + c - pago[p1]) / pago[p1]
    # D3: COSIP por ano civil, deixando a propria fatura fora
    r1 = (pago - E)[p1]
    anos = pd.Series(p1.year, index=p1)
    c_ano = pd.Series({m: float(r1[(anos == m.year) & (r1.index != m)].median()) for m in p1})
    e3b = (E[p1] + c_ano - pago[p1]) / pago[p1]
    g = {
        "G1": {"dentro": int((e1.abs() <= TOL_E).sum()), "de": len(p0), "cosip_R$": round(c, 2),
               "cosip_ok": bool(0 <= c <= COSIP_MAX)},
        "G2": {"dentro": int((e2.abs() <= TOL_T).sum()), "de": len(p0)},
        "G3": {"dentro": int((e3.abs() <= TOL_T).sum()), "de": len(p1)},
        "D3_cosip_por_ano": {"dentro": int((e3b.abs() <= TOL_T).sum()), "de": len(p1)},
    }
    for k in ("G1", "G2", "G3", "D3_cosip_por_ano"):
        g[k]["frac"] = round(g[k]["dentro"] / g[k]["de"], 3)
        g[k]["passa"] = bool(g[k]["frac"] >= FRAC) and g[k].get("cosip_ok", True)
    # D1: reta pago = a E + b em P0
    a, b = np.polyfit(E[p0].to_numpy(), pago[p0].to_numpy(), 1)
    # PIS/COFINS efetivo implicito: o preco escala com 1/(1-ICMS-PIS); ICMS 29% em P0
    pis_impl = 1 - 0.29 - (1 - 0.29 - PIS_COFINS) / a
    g["D1"] = {"inclinacao": round(float(a), 4), "intercepto_R$": round(float(b), 2),
               "pis_cofins_implicito": round(float(pis_impl), 4)}
    g["D2_erro_mediano_por_ano"] = {int(y): round(float(v), 4) for y, v in e3.groupby(e3.index.year).median().items()}
    g["passa"] = bool(g["G1"]["passa"] and g["G2"]["passa"] and g["G3"]["passa"])
    erros = {"e_energia_P0": e1, "e_total_P0": e2, "e_total_P1": e3, "e_total_P1_cosip_ano": e3b}
    return g, erros


def marcas(book, ref, imp_alto):
    """Marcas que podem explicar uma fatura fora da faixa (D4)."""
    dias = pd.concat([pd.Series(d) for d, _ in pedacos(ref, "ciclo")]).reset_index(drop=True)
    out = []
    meses = sorted({d.strftime("%Y-%m") for d in dias})
    fl = [book.bandeira(m) for m in meses]
    if len({x[1] if x else None for x in fl}) > 1:
        out.append("bandeira muda no ciclo")
    icms = {book.tax(d)[0] for d in dias}
    if len(icms) > 1:
        out.append("ICMS muda no ciclo")
    starts = book.tariffs["start"]
    if ((starts > dias.iloc[0]) & (starts <= dias.iloc[-1])).any():
        out.append("vigencia nova no ciclo")
    if imp_alto:
        out.append("consumo alto (quartil de cima)")
    return out


def alinhamento(fat):
    """Estrutura: injecao / geracao medida, por fatura, em tres janelas (desvio-padrao entre faturas)."""
    d = pd.read_parquet(comum.DADOS / "usinas_horario.parquet")
    d = d[d["serie"] == "Cascavel"].set_index("ds")
    y = d["y_Wh"].where(d["y_valido"]) / 1000
    jan = {"mes_M-1": (-1, 0, 0, 0), "ciclo_dia9": (-1, LEITURA - 1, 0, LEITURA - 1), "mes_M": (0, 0, 1, 0)}
    out = {}
    for nome, (m0, d0, m1, d1) in jan.items():
        r = []
        for ref in fat.index[fat["inj"] > 0]:
            a = ref + pd.DateOffset(months=m0) + pd.Timedelta(days=d0)
            b = ref + pd.DateOffset(months=m1) + pd.Timedelta(days=d1)
            s = y[(y.index >= a) & (y.index < b)]
            if len(s) and s.notna().mean() > 0.97:
                r.append(fat.loc[ref, "inj"] / s.sum())
        out[nome] = {"n": len(r), "media": round(float(np.mean(r)), 3), "dp": round(float(np.std(r, ddof=1)), 3)}
    return out


def main():
    if not os.path.exists(FATURA):
        print(f"planilha da fatura nao encontrada ({FATURA}): piloto pulado (so roda no Lactec)")
        return
    t0 = time.time()
    book = livro()
    fat = le_faturas()
    p0_all = fat.index[fat["inj"] == 0]
    p1_all = fat.index[fat["inj"] > 0]
    excl = {}
    for m in p1_all:
        if fat.loc[m, "imp"] - MINIMO > fat.loc[m, "inj"]:
            excl[m.strftime("%Y-%m")] = "importado - 50 > injetado (o saldo entraria)"
    configs = [(mo, le, bm) for mo in ("ciclo", "calendario") for le in ("all", "te_only", "none", "PR48")
               for bm in (True, False)]
    contas = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for cfg in configs:
            E = {}
            for ref in fat.index:
                k = ref.strftime("%Y-%m")
                if k in excl:
                    continue
                try:
                    E[ref] = conta(book, fat, ref, *cfg)
                except ValueError as e:
                    excl[k] = f"biblioteca: {e}"
            contas[cfg] = pd.Series(E)
            print(f"{cfg} ok ({time.time() - t0:.0f} s)")
    ok = fat.index[~fat.index.strftime("%Y-%m").isin(list(excl))]
    p0, p1 = p0_all.intersection(ok), p1_all.intersection(ok)
    resultados, erros_cfg = {}, {}
    for cfg in configs:
        nome = f"{cfg[0]}|icms={cfg[1]}|band_min={cfg[2]}"
        g, er = avalia(contas[cfg].reindex(ok), fat.loc[ok], p0, p1)
        resultados[nome], erros_cfg[nome] = g, er
    prim = "ciclo|icms=all|band_min=True"
    cal = "calendario|icms=all|band_min=True"
    # D4: faturas fora da faixa na primaria
    q75 = fat["imp"].quantile(0.75)
    fora = []
    er = erros_cfg[prim]
    for chave, tol in (("e_energia_P0", TOL_E), ("e_total_P1", TOL_T)):
        for m, v in er[chave].items():
            if abs(v) <= tol:
                continue
            perto = min(resultados, key=lambda n: abs(erros_cfg[n][chave].get(m, np.inf)))
            fora.append({"ref": m.strftime("%Y-%m"), "erro": chave, "erro_rel": round(float(v), 4),
                         "marcas": marcas(book, m, fat.loc[m, "imp"] >= q75),
                         "leitura_mais_perto": perto, "erro_rel_nela": round(float(erros_cfg[perto][chave][m]), 4)})
    por_fatura = {}
    for chave in ("e_energia_P0", "e_total_P0", "e_total_P1", "e_total_P1_cosip_ano"):
        for nome in (prim, cal):
            for m, v in erros_cfg[nome][chave].items():
                por_fatura.setdefault(m.strftime("%Y-%m"), {})[f"{nome.split('|')[0]}:{chave}"] = round(float(v), 4)
    saida = {
        "pergunta": "a conta da prosumer.economics.brazil reproduz as faturas reais (Copel, Cascavel)?",
        "portao": {"G1": "energia P0 +-2% em >= 80% e COSIP em [0, 30]", "G2": "total P0 +-3% em >= 80%",
                   "G3": "total P1 +-3% em >= 80% (COSIP fixa de P0)", "G4": "G1-G3 na montagem calendario"},
        "primaria": prim,
        "veredito": {"primaria_G1_G3": resultados[prim]["passa"], "G4_calendario": resultados[cal]["passa"]},
        "n_faturas": {"P0": len(p0), "P1": len(p1), "excluidas": excl},
        "entradas": {"icms_pr": ICMS_PR, "pis_cofins": PIS_COFINS, "minimo_kWh": MINIMO, "gd": "GD I",
                     "conectada": CONECTADA, "fuso": FUSO, "leitura_dia": LEITURA,
                     "livro": "ANEEL COPEL-DIS B1 convencional + bandeiras mensais (ODbL-1.0)"},
        "alinhamento_injecao_geracao": alinhamento(fat),
        "configuracoes": resultados,
        "fora_da_faixa_primaria": fora,
        "erros_relativos_por_fatura": por_fatura,
        "tempo_s": round(time.time() - t0, 1),
    }
    SAIDA.write_text(json.dumps(saida, indent=1, ensure_ascii=False, default=str))
    print(json.dumps({k: saida[k] for k in ("veredito", "n_faturas", "alinhamento_injecao_geracao")}, indent=1,
                     default=str))
    for nome, g in resultados.items():
        print(f"{nome:40s} G1 {g['G1']['dentro']:>2}/{g['G1']['de']} G2 {g['G2']['dentro']:>2}/{g['G2']['de']} "
              f"G3 {g['G3']['dentro']:>2}/{g['G3']['de']} D3 {g['D3_cosip_por_ano']['dentro']:>2} "
              f"COSIP {g['G1']['cosip_R$']:6.2f} a {g['D1']['inclinacao']:.3f} {'PASSA' if g['passa'] else ''}")
    print(f"tempo {time.time() - t0:.0f} s")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "baixa":
        baixa()
    else:
        main()
