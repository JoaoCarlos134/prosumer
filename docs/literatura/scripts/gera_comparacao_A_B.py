# -*- coding: utf-8 -*-
"""Planilha simples para o artigo de congresso: comparacao de modelos so nos regimes A e B.

Le os resultados do protocolo v2 (+ lote 2) do repositorio prossumidor e grava
Comparacao_modelos_regimes_A_B.xlsx ao lado da pasta scripts/. O regime C e os diagnosticos
(B-curto, C-gfs) ficam de fora de proposito: o artigo so compara modelos.

Uso: python gera_comparacao_A_B.py [pasta_resultados]
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

AQUI = Path(__file__).resolve().parents[1]
SAIDA = AQUI / "Comparacao_modelos_regimes_A_B.xlsx"
# Resultados: dentro do repositorio (docs/literatura -> experimentos) ou no clone do Lactec.
CANDIDATOS = [
    Path(sys.argv[1]) if len(sys.argv) > 1 else None,
    AQUI.parents[1] / "experimentos" / "testes_previsao" / "resultados",
    Path("C:/Users/L08741/OneDrive - Lactec/Documentos/1Projects/prossumidor/experimentos/testes_previsao/resultados"),
]
RES = next(p for p in CANDIDATOS if p is not None and (p / "metricas.csv").exists())


def le(nome):
    return pd.read_csv(RES / nome, sep=";", decimal=",", encoding="utf-8-sig")


TESTES = [("usinas", "A"), ("usinas", "B"), ("casas_prod", "A"), ("casas_cons", "A")]
NOME_TESTE = {("usinas", "A"): "Usinas A", ("usinas", "B"): "Usinas B",
              ("casas_prod", "A"): "FV das casas A", ("casas_cons", "A"): "Consumo das casas A"}
REFERENCIA_DE = {"usinas": "persist_ceu_claro", "casas_prod": "persist_24h", "casas_cons": "persist_24h"}

M = le("metricas.csv")
M = M[[(c, r) in TESTES for c, r in zip(M.caso, M.regime)]].copy()
DM = le("dm_vs_melhor.csv")
DM = DM[[(c, r) in TESTES for c, r in zip(DM.caso, DM.regime)]]
empata = {(r.caso, r.regime, r.modelo): bool(r.empatado_com_melhor) for r in DM.itertuples()}
melhor = {(r.caso, r.regime): r.melhor for r in DM.itertuples()}
for (c, r), m in melhor.items():
    empata[(c, r, m)] = True  # o proprio melhor

# Posicao em cada teste, escalada de 0 (1o) a 1 (ultimo), e media nos testes em que o modelo rodou.
g = M.groupby(["caso", "regime"]).skill
M["pos"] = g.rank(ascending=False, method="min").astype(int)
M["n"] = g.transform("size")
M["pct"] = (M.pos - 1) / (M.n - 1)
media = M.groupby("modelo").pct.mean().sort_values()
skill = M.set_index(["modelo", "caso", "regime"]).skill
pos = M.set_index(["modelo", "caso", "regime"])[["pos", "n"]]

TIPO = {  # modelo: (tipo, parametros) — copiado do catalogo T de docs/literatura/scripts/gera_visao_geral_modelos.py
    'persist_24h': ('Referência', '0'),
    'semanal_168h': ('Referência', '0'),
    'media_7d': ('Referência', '0'),
    'persist_ceu_claro': ('Referência', '0'),
    'linear_fisico': ('Física', '2 por usina'),
    'LightGBM': ('Árvore', '—'),
    'LSTM': ('Rede treinada', '≈ 216 mil'),
    'GRU': ('Rede treinada', '≈ 389 mil'),
    'TCN': ('Rede treinada', '≈ 153 mil'),
    'ResNet-1D': ('Rede treinada', '≈ 122 mil'),
    'NHITS': ('Rede treinada', '≈ 2,8 milhões'),
    'TiDE': ('Rede treinada', '≈ 1,5 milhão'),
    'DLinear': ('Rede treinada', '≈ 8 mil'),
    'TSMixerx': ('Rede treinada', '≈ 82 mil'),
    'SparseTSF': ('Rede treinada', '32'),
    'PatchTST': ('Rede treinada', '≈ 467 mil'),
    'iTransformer': ('Rede treinada', '≈ 6,4 milhões'),
    'TFT': ('Rede treinada', '≈ 1,4 milhão'),
    'KAN': ('Rede treinada', '≈ 1,0 milhão'),
    'Chronos-2': ('Fundacional', '≈ 120 milhões'),
    'Chronos-Bolt-small': ('Fundacional', '≈ 48 milhões'),
    'TimesFM-2.5': ('Fundacional', '≈ 200 milhões'),
    'TiRex': ('Fundacional', '≈ 35 milhões'),
    'TTM-r2': ('Fundacional', '≈ 3 milhões'),
    'Toto': ('Fundacional', '≈ 151 milhões'),
    'Moirai-2.0-small': ('Fundacional', '≈ 11 milhões'),
    'NBEATSx': ('Rede treinada', '—'),
    'Toto-2.0-22m': ('Fundacional', '22 milhões'),
    'Toto-2.0-313m': ('Fundacional', '313 milhões'),
    'TiRex-2': ('Fundacional', 'Não registrado'),
    'TabPFN-TS': ('Fundacional', 'Não registrado'),
    'Sundial-128m': ('Fundacional', '128 milhões'),
    'Timer-XL-84m': ('Fundacional', '84 milhões'),
    'Time-MoE-50M': ('Fundacional', '50 milhões'),
    'Moirai-MoE-small': ('Fundacional', 'Não registrado'),
    'Ensemble-mediana': ('Combinação', '—'),
}

# ---------------------------------------------------------------- estilo
AZUL, CINZA, TEXTO = "0F5C6E", "5A6470", "1D232A"
VERDE = PatternFill("solid", fgColor="D7EFDD")
CAB = Font(name="Arial", bold=True, color="FFFFFF", size=10)
TXT = Font(name="Arial", size=10, color=TEXTO)
fino = Side(style="thin", color="D5DCE0")
wb = Workbook()


def cabecalho(ws, linha, nomes, larguras):
    for j, (n, w) in enumerate(zip(nomes, larguras), start=1):
        c = ws.cell(row=linha, column=j, value=n)
        c.font, c.fill = CAB, PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[linha].height = 32


def celula(ws, i, j, v, fmt=None, negrito=False, cor=None):
    c = ws.cell(row=i, column=j, value=None if (isinstance(v, float) and pd.isna(v)) else v)
    c.font = Font(name="Arial", size=10, bold=negrito, color=cor or TEXTO)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    c.border = Border(bottom=fino)
    if fmt:
        c.number_format = fmt
    return c


# ---------------------------------------------------------------- Leia-me
ws = wb.active
ws.title = "Leia-me"
texto = [
    ("Comparação de modelos de previsão: regimes A e B", "titulo"),
    (f"Planilha para o artigo de congresso. Gerada em {date.today():%d/%m/%Y} por "
     "revisao_edge_ai/scripts/gera_comparacao_A_B.py, a partir dos resultados do protocolo v2 + lote 2 "
     "(repositório prossumidor, experimentos/testes_previsao/resultados/).", "nota"),
    ("", None),
    ("A tarefa", "h"),
    ("Prever as 24 horas do dia seguinte (energia hora a hora), com a previsão feita à meia-noite e usando só "
     "o que se sabia até a véspera. Uma previsão por dia de teste.", None),
    ("", None),
    ("Os casos", "h"),
    ("Usinas: 2 usinas solares no Paraná (Cascavel, 3,96 kWp, e Curitiba, ~9,6 kWp). Teste de 01/08/2025 a 31/05/2026.", None),
    ("FV das casas: geração solar das 10 casas que têm painel. Consumo das casas: consumo das 20 casas. "
     "Comunidade de energia em Dingle, Irlanda (Khadem et al., 2024, Scientific Data, CC0). Teste de 01/10/2020 a 31/12/2020.", None),
    ("", None),
    ("Os regimes (o que o modelo recebe)", "h"),
    ("Regime A — só o histórico. O modelo vê apenas a própria série até a véspera (e o calendário). "
     "É a situação de quem só tem o medidor.", None),
    ("Regime B — histórico + o clima do próprio dia. Além do histórico, o modelo recebe o clima MEDIDO no dia que "
     "está prevendo (irradiância e temperatura da NASA POWER, mais o céu claro calculado pela geometria do sol). "
     "Na prática isso equivale a uma previsão do tempo perfeita, que não existe: o regime B é um TETO, mostra até "
     "onde dá para chegar se o clima fosse conhecido. Só existe nas usinas.", None),
    ("Por que só A e B: este artigo compara modelos. O regime C (previsão do tempo real, emitida na véspera) é o "
     "operacional e fica para outro trabalho.", "nota"),
    ("", None),
    ("Como os modelos foram avaliados", "h"),
    ("Skill = 1 − (erro do modelo ÷ erro de uma referência simples), com o erro medido pelo RMSE. Referência: nas "
     "usinas, a persistência de céu claro (a nebulosidade de ontem aplicada ao céu claro de hoje); nas casas, o mesmo "
     "horário de ontem. Skill 0 = igual à referência; negativo = pior; +0,20 = 20% menos erro.", None),
    ("Modelos treinados foram retreinados do zero a cada período do teste (usinas: 5 períodos de 61 dias; casas: 3 de "
     "~31 dias), só com dados anteriores. Modelos fundacionais (pré-treinados) não treinam: só recebem o histórico.", None),
    ("", None),
    ("Como o ranking foi feito (aba Ranking)", "h"),
    ("1) Em cada um dos 4 testes (Usinas A, Usinas B, FV das casas A, Consumo das casas A), os modelos são ordenados pelo skill. "
     "2) A posição vira um número de 0 (1º) a 1 (último), para comparar testes com quantidades diferentes de modelos. "
     "3) Tira-se a média nos testes em que o modelo rodou. Menor = melhor.", None),
    ("Células em verde = empatado com o melhor daquele teste: o teste de Diebold–Mariano (com correção de Holm) não "
     "mostra diferença (p ≥ 0,05). Posições próximas quase nunca são diferenças reais; use o verde para dizer "
     "quem está no grupo da frente.", None),
    ("", None),
    ("Abas", "h"),
    ("Ranking — todos os modelos que rodaram em A ou B, do melhor ao pior, com o skill em cada teste.", None),
    ("A x B (usinas) — o ganho de cada modelo ao receber o clima: mostra que o clima pesa mais que a escolha do modelo.", None),
]
estilos = {"titulo": Font(name="Arial", size=13, bold=True, color=AZUL), "h": Font(name="Arial", size=11, bold=True, color=AZUL),
           "nota": Font(name="Arial", size=9, italic=True, color=CINZA), None: TXT}
for i, (t, e) in enumerate(texto, start=1):
    c = ws.cell(row=i, column=1, value=t)
    c.font, c.alignment = estilos[e], Alignment(wrap_text=True, vertical="top")
ws.column_dimensions["A"].width = 120

# ---------------------------------------------------------------- Ranking
wr = wb.create_sheet("Ranking")
cols = ["Posição", "Modelo", "Tipo", "Parâmetros", *[f"Skill {NOME_TESTE[t]}" for t in TESTES],
        "Posição relativa média (0 = melhor)", "Testes em que rodou", "Empata com o melhor em"]
cabecalho(wr, 1, cols, [8, 22, 14, 14, 11, 11, 11, 13, 13, 10, 13])
for i, (mod, pr) in enumerate(media.items(), start=2):
    tipo, par = TIPO.get(mod, ("", ""))
    celula(wr, i, 1, i - 1, "0")
    celula(wr, i, 2, mod, negrito=True)
    celula(wr, i, 3, tipo)
    celula(wr, i, 4, par)
    feitos = verdes = 0
    for j, (c, r) in enumerate(TESTES, start=5):
        k = (mod, c, r)
        if k in skill.index:
            feitos += 1
            cel = celula(wr, i, j, round(float(skill[k]), 3), "+0.000;-0.000;0.000")
            if empata.get((c, r, mod)):
                verdes += 1
                cel.fill = VERDE
            if mod == REFERENCIA_DE[c]:
                cel.font = Font(name="Arial", size=10, italic=True, color=CINZA)
        else:
            celula(wr, i, j, "—", cor=CINZA)
    celula(wr, i, 9, round(float(pr), 3), "0.000")
    celula(wr, i, 10, feitos, "0")
    celula(wr, i, 11, f"{verdes} de {feitos}")
n = len(media) + 2
notas = [
    "Verde = empatado com o melhor do teste (Diebold–Mariano com Holm, p ≥ 0,05). '—' = o modelo não rodou nesse teste.",
    "Referências (persistências) têm skill 0 no próprio teste por definição (em itálico). Ensemble-mediana = mediana, hora a hora, de todos os modelos.",
    "TFT, TSMixerx e linear físico só rodaram com clima (Usinas B); a posição relativa permite compará-los com os demais, "
    "mas vem de um teste só: é menos firme que a de quem rodou nos quatro (ver 'Testes em que rodou').",
]
for k, t in enumerate(notas):
    c = wr.cell(row=n + 1 + k, column=1, value=t)
    c.font = Font(name="Arial", size=9, italic=True, color=CINZA)
wr.freeze_panes = "C2"

# ---------------------------------------------------------------- A x B (usinas)
wab = wb.create_sheet("A x B (usinas)")
ab = M[M.caso == "usinas"].pivot(index="modelo", columns="regime", values="skill").dropna()
ab = ab.assign(ganho=ab.B - ab.A).sort_values("B", ascending=False)
cabecalho(wab, 1, ["Modelo", "Skill A (só histórico)", "Skill B (+ clima do dia)", "Ganho com o clima (B − A)"],
          [24, 16, 16, 18])
for i, (mod, r) in enumerate(ab.iterrows(), start=2):
    celula(wab, i, 1, mod, negrito=True)
    for j, v in enumerate([r.A, r.B, r.ganho], start=2):
        celula(wab, i, j, round(float(v), 3), "+0.000;-0.000;0.000")
melhorA, melhorB = M[(M.caso == "usinas") & (M.regime == "A")].skill.max(), M[(M.caso == "usinas") & (M.regime == "B")].skill.max()
topA = M[(M.caso == "usinas") & (M.regime == "A")].skill.nlargest(5)
k = len(ab) + 3
resumo = [
    f"Melhor skill nas usinas: {melhorA:+.3f} em A e {melhorB:+.3f} em B. Ganho mediano com o clima: {ab.ganho.median():+.3f}.",
    f"Diferença entre o 1º e o 5º modelo em A: {topA.iloc[0] - topA.iloc[-1]:.3f}. "
    "Ou seja: dar o clima ao modelo muda o resultado muito mais do que trocar de modelo.",
    "Só modelos que rodaram nos dois regimes. Lembre que B usa o clima medido (teto), não uma previsão.",
]
for t in resumo:
    c = wab.cell(row=k, column=1, value=t)
    c.font = Font(name="Arial", size=10, bold=t is resumo[0], color=TEXTO)
    k += 1
wab.freeze_panes = "B2"

wb.save(SAIDA)
print("ok", SAIDA, "| modelos no ranking:", len(media), "| A x B:", len(ab), "| resultados de", RES)
