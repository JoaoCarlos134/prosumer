# -*- coding: utf-8 -*-
"""Planilha simples para o artigo de congresso: comparacao de modelos nos regimes A e B.

Le os resultados do benchmark (protocolo v2 + lote 2 + regime B nas casas) do repositorio prossumidor e
grava Comparacao_modelos_regimes_A_B.xlsx ao lado da pasta scripts/. O regime C e os diagnosticos
(B-curto, C-gfs) ficam de fora de proposito: o artigo so compara modelos.

Abas: Leia-me, Resumo, Ranking geral, uma aba por teste (caso x regime) com skill, IC, R2, nRMSE e vies,
e Ganho com o clima. Teste ainda sem resultado aparece com um aviso, nao some.

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

TESTES = [("usinas", "A"), ("usinas", "B"), ("casas_prod", "A"), ("casas_prod", "B"), ("casas_cons", "A"), ("casas_cons", "B")]
ABA = {("usinas", "A"): "Usinas A", ("usinas", "B"): "Usinas B", ("casas_prod", "A"): "FV casas A",
       ("casas_prod", "B"): "FV casas B", ("casas_cons", "A"): "Consumo A", ("casas_cons", "B"): "Consumo B"}
TITULO = {
    ("usinas", "A"): "Usinas solares (Cascavel e Curitiba) — regime A: só o histórico",
    ("usinas", "B"): "Usinas solares (Cascavel e Curitiba) — regime B: histórico + clima do dia (NASA POWER)",
    ("casas_prod", "A"): "Geração FV das 10 casas com painel — regime A: só o histórico",
    ("casas_prod", "B"): "Geração FV das 10 casas com painel — regime B: histórico + clima medido na estação de Dingle",
    ("casas_cons", "A"): "Consumo das 20 casas — regime A: só o histórico",
    ("casas_cons", "B"): "Consumo das 20 casas — regime B: histórico + clima medido na estação de Dingle",
}
CASO = {"usinas": "Usinas", "casas_prod": "FV das casas", "casas_cons": "Consumo das casas"}
REFERENCIA_DE = {"usinas": "persist_ceu_claro", "casas_prod": "persist_24h", "casas_cons": "persist_24h"}
NOME_REF = {"usinas": "persistência de céu claro (a nebulosidade de ontem aplicada ao céu claro de hoje)",
            "casas_prod": "igual a ontem (o mesmo horário do dia anterior)",
            "casas_cons": "igual a ontem (o mesmo horário do dia anterior)"}


def le(nome):
    return pd.read_csv(RES / nome, sep=";", decimal=",", encoding="utf-8-sig")


M = le("metricas.csv")
M = M[[(c, r) in TESTES for c, r in zip(M.caso, M.regime)]].copy()
DM = le("dm_vs_melhor.csv")
DM = DM[[(c, r) in TESTES for c, r in zip(DM.caso, DM.regime)]]
empata = {(r.caso, r.regime, r.modelo): bool(r.empatado_com_melhor) for r in DM.itertuples()}
melhor = {(r.caso, r.regime): r.melhor for r in DM.itertuples()}
for (c, r), m in melhor.items():
    empata[(c, r, m)] = True  # o proprio melhor
avaliados = [t for t in TESTES if ((M.caso == t[0]) & (M.regime == t[1])).any()]

# Posicao em cada teste, escalada de 0 (1o) a 1 (ultimo), e media nos testes em que o modelo rodou.
g = M.groupby(["caso", "regime"]).skill
M["pos"] = g.rank(ascending=False, method="min").astype(int)
M["n"] = g.transform("size")
M["pct"] = (M.pos - 1) / (M.n - 1)
media = M.groupby("modelo").pct.mean().sort_values()
POR = M.set_index(["caso", "regime", "modelo"])

# Modelos que rodaram nas usinas B mas ainda nao nas casas B. Os de CPU rodam na maquina do Lactec; o resto
# (redes treinadas e TabPFN-TS) precisa da GPU da maquina de casa.
RODA_EM_CPU = {"LightGBM", "linear_fisico", "Chronos-2", "TimesFM-2.5", "TiRex-2"}
faltam_b_casas = {
    c: sorted(set(M[(M.caso == "usinas") & (M.regime == "B")].modelo)
              - set(M[(M.caso == c) & (M.regime == "B")].modelo) - {"persist_ceu_claro", "Ensemble-mediana"}
              - ({"linear_fisico"} if c == "casas_cons" else set()))
    for c in ("casas_prod", "casas_cons")
}

# ---------------------------------------------------------------- estilo
AZUL, CINZA, TEXTO = "0F5C6E", "5A6470", "1D232A"
VERDE = PatternFill("solid", fgColor="D7EFDD")
CLARO = PatternFill("solid", fgColor="E8F1F3")
CAB = Font(name="Arial", bold=True, color="FFFFFF", size=10)
fino = Side(style="thin", color="D5DCE0")
F_SKILL, F_PCT, F_R2 = "+0.000;-0.000;0.000", "0.0%", "0.00"
wb = Workbook()


def cabecalho(ws, linha, nomes, larguras):
    for j, (n, w) in enumerate(zip(nomes, larguras), start=1):
        c = ws.cell(row=linha, column=j, value=n)
        c.font, c.fill = CAB, PatternFill("solid", fgColor=AZUL)
        c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.column_dimensions[get_column_letter(j)].width = w
    ws.row_dimensions[linha].height = 32


def celula(ws, i, j, v, fmt=None, negrito=False, cor=None, italico=False):
    c = ws.cell(row=i, column=j, value=None if (isinstance(v, float) and pd.isna(v)) else v)
    c.font = Font(name="Arial", size=10, bold=negrito, italic=italico, color=cor or TEXTO)
    c.alignment = Alignment(wrap_text=True, vertical="top")
    c.border = Border(bottom=fino)
    if fmt:
        c.number_format = fmt
    return c


def texto(ws, i, t, estilo=None, col=1):
    fonte = {"titulo": Font(name="Arial", size=13, bold=True, color=AZUL),
             "h": Font(name="Arial", size=11, bold=True, color=AZUL),
             "nota": Font(name="Arial", size=9, italic=True, color=CINZA),
             None: Font(name="Arial", size=10, color=TEXTO)}[estilo]
    c = ws.cell(row=i, column=col, value=t)
    c.font, c.alignment = fonte, Alignment(wrap_text=False, vertical="top")
    return c


def tipo_de(m):
    return TIPO.get(m, ("", ""))


# ---------------------------------------------------------------- Leia-me
ws = wb.active
ws.title = "Leia-me"
leia = [
    ("Comparação de modelos de previsão: regimes A e B", "titulo"),
    (f"Planilha para o artigo de congresso. Gerada em {date.today():%d/%m/%Y} por gera_comparacao_A_B.py, a partir "
     "dos resultados do benchmark (repositório prossumidor, experimentos/testes_previsao/resultados/).", "nota"),
    ("", None),
    ("A tarefa", "h"),
    ("Prever as 24 horas do dia seguinte (energia hora a hora), com a previsão feita à meia-noite e usando só o que "
     "se sabia até a véspera. Uma previsão por dia de teste.", None),
    ("", None),
    ("Os casos", "h"),
    ("Usinas: 2 usinas solares no Paraná (Cascavel, 3,96 kWp, e Curitiba, ~9,6 kWp). Teste de 01/08/2025 a 31/05/2026.", None),
    ("FV das casas: geração solar das 10 casas que têm painel (2,4 kW cada). Consumo das casas: consumo das 20 casas.", None),
    ("As casas são da comunidade de energia StoreNet, em Dingle, Irlanda: Khadem et al. (2024), Scientific Data, "
     "doi:10.1038/s41597-024-03454-2, licença CC0 (domínio público). Teste de 01/10/2020 a 31/12/2020.", None),
    ("", None),
    ("Os regimes (o que o modelo recebe)", "h"),
    ("Regime A — só o histórico. O modelo vê apenas a própria série até a véspera (e o calendário). É a situação de "
     "quem só tem o medidor.", None),
    ("Regime B — histórico + o clima do próprio dia, MEDIDO. Equivale a uma previsão do tempo perfeita, que não existe: "
     "o regime B é um TETO, mostra até onde dá para chegar se o clima fosse conhecido.", None),
    ("   Usinas: radiação e temperatura da NASA POWER, mais o céu claro calculado pela geometria do sol e pela "
     "orientação dos painéis.", None),
    ("   Casas: radiação, temperatura e céu claro da estação meteorológica da própria comunidade (medição a cada minuto). "
     "A orientação dos painéis não é publicada, então a radiação é a do plano horizontal.", None),
    ("Por que só A e B: este artigo compara modelos. O regime C (previsão do tempo real, emitida na véspera) é o "
     "operacional e fica para outro trabalho; nas casas ele nem existe (as previsões arquivadas só começam em 2024).", "nota"),
    ("", None),
    ("Como ler os números (abas de cada teste)", "h"),
    ("Skill — quanto o modelo erra MENOS que uma referência simples: 1 − (erro do modelo ÷ erro da referência), com o "
     "erro medido pelo RMSE. 0 = igual à referência; negativo = pior; +0,20 = 20% menos erro. É a medida principal.", None),
    ("   Referência nas usinas: persistência de céu claro. Nas casas: igual a ontem.", None),
    ("IC 95% — faixa de incerteza do skill (reamostrando dias inteiros). Se as faixas de dois modelos se sobrepõem "
     "muito, a diferença entre eles é pequena.", None),
    ("R² — quanto da variação hora a hora o modelo explica. 1 = perfeito; 0 = não é melhor que prever sempre a média; "
     "pode ser negativo. Nas usinas fica alto mesmo para modelos fracos, porque o dia e a noite já explicam muito; "
     "por isso o skill é a medida principal.", None),
    ("nRMSE — erro típico, em % da energia média das horas avaliadas. Menor = melhor.", None),
    ("Viés — erro médio, em % da energia média: positivo = prevê a mais; negativo = prevê a menos. Perto de 0 = sem "
     "tendência.", None),
    ("Empata com o melhor — o teste de Diebold–Mariano (com correção de Holm) não mostra diferença em relação ao "
     "melhor do teste (p ≥ 0,05). Linhas em verde. Posições próximas quase nunca são diferenças reais: use o verde "
     "para dizer quem está no grupo da frente.", None),
    ("Horas avaliadas: nas usinas, as horas com sol (céu claro > 0); na FV das casas, as horas em que a casa média "
     "gera mais de 1% do pico; no consumo, todas.", None),
    ("", None),
    ("Como o ranking geral foi feito (aba Ranking geral)", "h"),
    ("1) Em cada teste, os modelos são ordenados pelo skill. 2) A posição vira um número de 0 (1º) a 1 (último), para "
     "comparar testes com quantidades diferentes de modelos. 3) Tira-se a média nos testes em que o modelo rodou. "
     "Menor = melhor. A coluna 'Testes em que rodou' diz em quantos: quem rodou em poucos tem posição menos firme.", None),
    ("", None),
    ("O que mudou em 07/10/2026", "h"),
    ("As casas foram identificadas (Dingle, Irlanda, CC0) e ganharam o regime B com o clima medido da estação local: "
     "o artigo passa de 4 para 6 testes.", None),
    ("O relógio das casas é a hora local de Dublin (com horário de verão), conferido contra o sol; o clima, que vem em "
     "UTC, foi convertido para a hora local antes de juntar.", None),
    ("Abas por teste com skill, IC 95%, R², nRMSE e viés, para o leitor ver o tamanho das diferenças e não só a ordem.", None),
    ("Aba Modelos previstos: o que entrou depois dos 36 originais, o que ainda falta e o que ficou de fora, com o motivo.", None),
]
pend = [f"{CASO[c]}: {', '.join(m if m in RODA_EM_CPU else m + '*' for m in v)}" for c, v in faltam_b_casas.items() if v]
if pend:
    leia += [("", None), ("Ainda falta (resultados preliminares nas casas B)", "h"),
             ("Modelos que rodaram nas usinas B mas ainda não nas casas B (os marcados com * precisam de GPU e "
              "rodam na máquina de casa; os outros rodam em CPU):", None),
             *[(f"   {p}", None) for p in pend],
             ("Enquanto isso, a mediana de todos (Ensemble-mediana) nas casas B é só dos modelos já rodados e pode mudar.", None)]
nao = [ABA[t] for t in TESTES if t not in avaliados]
if nao:
    leia += [("", None), (f"Testes ainda sem nenhum resultado: {', '.join(nao)}.", None)]
for i, (t, e) in enumerate(leia, start=1):
    texto(ws, i, t, e).alignment = Alignment(wrap_text=True, vertical="top")
ws.column_dimensions["A"].width = 125

# ---------------------------------------------------------------- Resumo
wr = wb.create_sheet("Resumo")
texto(wr, 1, "Resumo por teste", "titulo")
cols = ["Teste", "Modelos avaliados", "Melhor modelo", "Skill do melhor", "R² do melhor", "Skill da mediana de todos",
        "No grupo da frente (melhor + empatados)", "Skill 0 = referência"]
cabecalho(wr, 3, cols, [16, 11, 20, 11, 10, 13, 13, 48])
i = 4
for t in TESTES:
    c, r = t
    celula(wr, i, 1, ABA[t], negrito=True)
    if t not in avaliados:
        celula(wr, i, 2, "ainda não avaliado", cor=CINZA, italico=True)
        i += 1
        continue
    x = M[(M.caso == c) & (M.regime == r)]
    b = x.sort_values("skill", ascending=False).iloc[0]
    ens = x[x.modelo == "Ensemble-mediana"]
    n_emp = sum(empata.get((c, r, m), False) for m in x.modelo)
    celula(wr, i, 2, len(x), "0")
    celula(wr, i, 3, b.modelo, negrito=True)
    celula(wr, i, 4, float(b.skill), F_SKILL)
    celula(wr, i, 5, float(b.R2), F_R2)
    celula(wr, i, 6, float(ens.skill.iloc[0]) if len(ens) else None, F_SKILL)
    celula(wr, i, 7, f"{n_emp} de {len(x)}")
    celula(wr, i, 8, NOME_REF[c])
    i += 1
i += 1
texto(wr, i, "Quanto o clima ajuda (regime B − regime A)", "h")
i += 1
cabecalho(wr, i, ["Caso", "Melhor em A", "Melhor em B", "Ganho do melhor", "LightGBM: A", "LightGBM: B",
                  "Ganho do LightGBM", ""], [16, 11, 20, 11, 10, 13, 13, 48])
i += 1
for c in CASO:
    if (c, "A") not in avaliados or (c, "B") not in avaliados:
        continue
    a = M[(M.caso == c) & (M.regime == "A")].skill.max()
    b = M[(M.caso == c) & (M.regime == "B")].skill.max()
    la, lb = POR.skill.get((c, "A", "LightGBM")), POR.skill.get((c, "B", "LightGBM"))
    celula(wr, i, 1, CASO[c], negrito=True)
    for j, v in enumerate([a, b, b - a, la, lb, (lb - la) if la is not None and lb is not None else None], start=2):
        celula(wr, i, j, None if v is None else float(v), F_SKILL)
    i += 1
for t in [
    "O LightGBM aparece porque rodou em todos os testes: é a comparação A x B mais limpa (o mesmo modelo, só muda o clima).",
    "Ganho grande = o clima do dia decide o resultado; ganho perto de zero = o clima não ajuda (caso do consumo).",
    "Lembre: o regime B usa o clima medido (teto), não uma previsão.",
]:
    i += 1
    texto(wr, i, t, "nota")
wr.freeze_panes = "B4"

# ---------------------------------------------------------------- Ranking geral
wg = wb.create_sheet("Ranking geral")
cols = ["Posição", "Modelo", "Tipo", "Parâmetros", "Posição relativa média (0 = melhor)", "Testes em que rodou",
        "No grupo da frente em", "Melhor posição", "Pior posição"]
cabecalho(wg, 1, cols, [8, 22, 14, 14, 13, 10, 12, 18, 18])
for i, (mod, pr) in enumerate(media.items(), start=2):
    tipo, par = tipo_de(mod)
    x = M[M.modelo == mod]
    feitos = len(x)
    verdes = sum(empata.get((c, r, mod), False) for c, r in zip(x.caso, x.regime))
    mel, pio = x.loc[x.pct.idxmin()], x.loc[x.pct.idxmax()]
    celula(wg, i, 1, i - 1, "0")
    celula(wg, i, 2, mod, negrito=True)
    celula(wg, i, 3, tipo)
    celula(wg, i, 4, par)
    celula(wg, i, 5, round(float(pr), 3), "0.000")
    celula(wg, i, 6, feitos, "0")
    celula(wg, i, 7, f"{verdes} de {feitos}")
    celula(wg, i, 8, f"{mel.pos}º de {mel.n} ({ABA[(mel.caso, mel.regime)]})")
    celula(wg, i, 9, f"{pio.pos}º de {pio.n} ({ABA[(pio.caso, pio.regime)]})")
n = len(media) + 3
for k, t in enumerate([
    "Os números de cada modelo (skill, R², erro, viés) estão nas abas de cada teste.",
    "Quem rodou em poucos testes (ex.: TFT, TSMixerx, linear físico: só com clima) tem posição menos firme.",
    "Referências (persistências) e Ensemble-mediana (mediana, hora a hora, de todos os modelos) entram no ranking para comparação.",
]):
    texto(wg, n + k, t, "nota")
wg.freeze_panes = "C2"

# ---------------------------------------------------------------- uma aba por teste
for t in TESTES:
    c, r = t
    w = wb.create_sheet(ABA[t])
    texto(w, 1, TITULO[t], "h")
    if t not in avaliados:
        texto(w, 3, "Ainda não avaliado: os modelos deste teste estão rodando ou esperando a máquina com GPU.", "nota")
        continue
    x = M[(M.caso == c) & (M.regime == r)].sort_values("skill", ascending=False)
    cols = ["Posição", "Modelo", "Tipo", "Skill", "IC 95% do skill", "R²", "nRMSE", "Viés", "Empata com o melhor"]
    cabecalho(w, 3, cols, [8, 22, 14, 9, 16, 8, 9, 9, 12])
    for i, m in enumerate(x.itertuples(), start=4):
        ref = m.modelo == REFERENCIA_DE[c]
        emp = "Melhor" if i == 4 else ("Sim" if empata.get((c, r, m.modelo)) else "Não")
        celula(w, i, 1, i - 3, "0")
        celula(w, i, 2, m.modelo, negrito=True, italico=ref)
        celula(w, i, 3, tipo_de(m.modelo)[0])
        celula(w, i, 4, float(m.skill), F_SKILL, italico=ref)
        celula(w, i, 5, f"{m.skill_ic95_inf:+.3f} a {m.skill_ic95_sup:+.3f}".replace(".", ","))
        celula(w, i, 6, float(m.R2), F_R2)
        celula(w, i, 7, float(m.nRMSE), F_PCT)
        celula(w, i, 8, float(m.MBE), "+0.0%;-0.0%;0.0%")
        celula(w, i, 9, emp, negrito=emp == "Melhor")
        if emp in ("Melhor", "Sim"):
            for j in range(1, 10):
                w.cell(row=i, column=j).fill = VERDE
    k = len(x) + 5
    notas = [f"Skill 0 = referência deste teste: {NOME_REF[c]} (linha em itálico, quando presente).",
             "Verde = empatado com o melhor (Diebold–Mariano com Holm, p ≥ 0,05)."]
    if r == "B" and c in faltam_b_casas and faltam_b_casas[c]:
        gpu = [m for m in faltam_b_casas[c] if m not in RODA_EM_CPU]
        notas.append(f"Preliminar: ainda faltam {len(faltam_b_casas[c])} modelos ({', '.join(faltam_b_casas[c])}); "
                     f"{len(gpu)} deles precisam da GPU. A mediana de todos pode mudar.")
    for j, nt in enumerate(notas):
        texto(w, k + j, nt, "nota")
    w.freeze_panes = "C4"

# ---------------------------------------------------------------- Ganho com o clima
wab = wb.create_sheet("Ganho com o clima")
texto(wab, 1, "O mesmo modelo sem e com o clima do dia (só modelos que rodaram nos dois regimes)", "h")
cabecalho(wab, 3, ["Caso", "Modelo", "Skill A (só histórico)", "Skill B (+ clima)", "Ganho de skill (B − A)",
                   "R² A", "R² B"], [18, 22, 13, 13, 13, 8, 8])
i = 4
for c in CASO:
    ab = M[M.caso == c].pivot_table(index="modelo", columns="regime", values=["skill", "R2"])
    if ("skill", "A") not in ab.columns or ("skill", "B") not in ab.columns:
        continue
    ab = ab.dropna().sort_values(("skill", "B"), ascending=False)
    for mod, v in ab.iterrows():
        celula(wab, i, 1, CASO[c])
        celula(wab, i, 2, mod, negrito=True)
        celula(wab, i, 3, float(v[("skill", "A")]), F_SKILL)
        celula(wab, i, 4, float(v[("skill", "B")]), F_SKILL)
        celula(wab, i, 5, float(v[("skill", "B")] - v[("skill", "A")]), F_SKILL, negrito=True)
        celula(wab, i, 6, float(v[("R2", "A")]), F_R2)
        celula(wab, i, 7, float(v[("R2", "B")]), F_R2)
        i += 1
    for j in range(1, 8):
        wab.cell(row=i - 1, column=j).border = Border(bottom=Side(style="medium", color=AZUL))
i += 1
topA = M[(M.caso == "usinas") & (M.regime == "A")].skill.nlargest(5)
ganho_us = (M[(M.caso == "usinas") & (M.regime == "B")].set_index("modelo").skill
            - M[(M.caso == "usinas") & (M.regime == "A")].set_index("modelo").skill).dropna()
for t in [
    f"Usinas: ganho mediano com o clima {ganho_us.median():+.3f}, contra {topA.iloc[0] - topA.iloc[-1]:.3f} de diferença "
    "entre o 1º e o 5º modelo em A — dar o clima ao modelo muda muito mais do que trocar de modelo.",
    "Casas: o clima medido ajuda a geração FV, mas bem menos que nas usinas (estação da comunidade, não do telhado, e "
    "orientação dos painéis desconhecida); no consumo praticamente não ajuda.",
]:
    texto(wab, i, t, "nota")
    i += 1
wab.freeze_panes = "C4"

# ---------------------------------------------------------------- Modelos previstos (ainda sem resultado)
# O que vai entrar neste artigo (regimes A e B). Por teste: "previsto", "a confirmar" (o modelo diz aceitar
# clima, falta verificar no codigo), "—" (nao se aplica). Fonte: plano do TCC (passo T) e aba Testaveis da
# Visao_geral_modelos_previsao.xlsx. Flags de clima do NeuralForecast lidas do codigo instalado (07/10/2026).
P, AC, NA = "previsto", "a confirmar", "—"
SO_A = [P, NA, P, NA, P, NA]
A_E_B = [P, P, P, P, P, P]
A_E_B_CONF = [P, AC, P, AC, P, AC]
NF = "NeuralForecast (já instalado)"
SF = "StatsForecast (instalar à parte)"
SK = "scikit-learn (já instalado)"
PREVISTOS = [  # modelo, grupo, testes (UsA, UsB, FVA, FVB, ConsA, ConsB), gpu, biblioteca, observacao
    ("TimeMixer", "Rede treinada (levantamento)", SO_A, "Recomendada", NF, "Não aceita clima no NeuralForecast."),
    ("TimesNet", "Rede treinada (levantamento)", A_E_B, "Recomendada", NF, ""),
    ("DeepAR", "Rede treinada (levantamento)", A_E_B, "Recomendada", NF, "Probabilístico: usar a mediana."),
    ("TimeXer", "Rede treinada (levantamento)", SO_A, "Recomendada", NF,
     "Feito para variáveis externas, mas no NeuralForecast só aceita o clima PASSADO, não o do dia: fica no A."),
    ("FEDformer", "Rede treinada (levantamento)", A_E_B, "Recomendada", NF, ""),
    ("Autoformer", "Rede treinada (levantamento)", A_E_B, "Recomendada", NF, ""),
    ("Informer", "Rede treinada (levantamento)", A_E_B, "Recomendada", NF, ""),
    ("xLSTM", "Rede treinada (levantamento)", A_E_B, "Recomendada", NF, "Sem os kernels CUDA do NX-AI/xlstm."),
    ("Time-LLM", "Rede treinada (levantamento)", SO_A, "Sim", NF, "Tem um LLM dentro: inviável sem GPU."),
    ("Moirai 1", "Fundacional (levantamento)", A_E_B, "Não", "uni2ts (ambiente moirai já existe)",
     "Aceita covariáveis passadas e futuras."),
    ("MOMENT", "Fundacional (levantamento)", SO_A, "Recomendada", "momentfm", "~385 milhões de parâmetros."),
    ("VisionTS", "Fundacional (levantamento)", SO_A, "Não", "visionts", "Trata a série como imagem."),
    ("Lag-Llama", "Fundacional (levantamento)", SO_A, "Não", "lag-llama (GitHub)", ""),
    ("FlowState", "Fundacional (levantamento)", SO_A, "Não", "granite-tsfm", "Completo só na máquina do Lactec."),
    ("BuildingsBench", "Fundacional (levantamento)", [NA, NA, NA, NA, P, AC], "Não", "BuildingsBench (NREL)",
     "Treinado em prédios: só no consumo."),
    ("TimesFM-3", "Fundacional (levantamento)", A_E_B, "Não", "timesfm",
     "Pesos só para pesquisa: entra no artigo, não na biblioteca."),
    ("TimeGPT", "Fundacional (levantamento)", [NA, NA, P, P, P, P], "Não", "nixtla (API paga)",
     "Envia os dados para fora: só as casas (CC0), NUNCA as usinas."),
    ("CycleNet", "Rede treinada (levantamento)", SO_A, "Recomendada", "GitHub (adaptador)", ""),
    ("DUET", "Rede treinada (levantamento)", A_E_B_CONF, "Recomendada", "TFB (adaptador)", ""),
    ("Crossformer", "Rede treinada (levantamento)", A_E_B_CONF, "Recomendada", "TSLib (adaptador)", ""),
    ("S-Mamba", "Rede treinada (levantamento)", A_E_B_CONF, "Sim", "TSLib + mamba_ssm",
     "Kernels só CUDA; pode exigir Linux (WSL)."),
    ("Mamba", "Rede treinada (levantamento)", A_E_B_CONF, "Sim", "mamba_ssm", "Kernels só CUDA; pode exigir Linux (WSL)."),
    ("LLMTime", "LLM (levantamento)", SO_A, "Sim", "llmtime (LLM local)", "Lento mesmo em GPU."),
    ("TimeGrad", "Generativo (levantamento)", A_E_B, "Recomendada", "PyTorchTS", "Prevê uma faixa: avaliar a mediana."),
    ("AutoARIMA", "Clássico estatístico", A_E_B, "Não", SF, "No B vira ARIMAX (clima como regressor)."),
    ("AutoETS", "Clássico estatístico", SO_A, "Não", SF, "Suavização exponencial (Holt-Winters)."),
    ("AutoTheta", "Clássico estatístico", SO_A, "Não", SF, ""),
    ("MSTL", "Clássico estatístico", SO_A, "Não", SF, "Sazonalidades diária e semanal."),
    ("Ridge", "Clássico (scikit-learn)", A_E_B, "Não", SK, "Regressão linear com os mesmos atributos do LightGBM."),
    ("Random Forest", "Clássico (scikit-learn)", A_E_B, "Não", SK, "Exporta para microcontrolador (emlearn)."),
    ("MLP", "Clássico (scikit-learn)", A_E_B, "Não", SK,
     "Rede rasa; a mesma família dos modelos TFLite do projeto. Exporta com emlearn."),
    ("k-NN", "Clássico (scikit-learn)", A_E_B, "Não", SK, "Dias parecidos no histórico."),
]
wp = wb.create_sheet("Modelos previstos")
texto(wp, 1, "Modelos deste artigo além dos 36 originais: o que já foi feito, o que falta e o que ficou de fora", "h")
cols = ["Modelo", "Grupo", *[ABA[t] for t in TESTES], "Precisa de GPU?", "Biblioteca", "Observação"]
cabecalho(wp, 3, cols, [16, 24, 10, 10, 10, 10, 10, 10, 12, 26, 60])
FORA_COR = PatternFill("solid", fgColor="EDEDED")
COR = {"feito": VERDE, "falta": CLARO, "falta (GPU)": PatternFill("solid", fgColor="FFF0C2"), P: CLARO, AC: CLARO,
       "fora": FORA_COR}
COR_GPU = {"Sim": PatternFill("solid", fgColor="F8D2BE"), "Recomendada": PatternFill("solid", fgColor="FFF0C2")}
# Nome na lista acima -> nome em metricas.csv
ALIAS = {"Random Forest": "RandomForest", "k-NN": "kNN", "Time-LLM": "TimeLLM"}
# Decisoes medidas na rodada do passo T (maquina de casa, 07-09/10/2026; ver CLAUDE.md e 04_redes_treinadas.py).
FORA = {  # so com evidencia (teste). Inviabilidade tecnica nao e "fora": vai para a etapa A do plano.
    "TimesNet": ({"B"}, "Aceita o clima mas o IGNORA (previsão idêntica com o clima embaralhado): fica só no A."),
}
A_ESTUDAR = {  # nao rodaram por viabilidade, nao por falta de valor (etapa A do plano)
    "xLSTM": "A estudar (etapa A): exige mlstm_kernels/ninja; rota: Linux/WSL com compilador.",
    "Time-LLM": "A estudar (etapa A): estourou a memória com o LLM padrão; rota: base menor (GPT-2) ou mais memória.",
}
blocos = []
# 1) ja testados que ainda faltam nas casas B
pend = sorted(set().union(*faltam_b_casas.values()))
for mod in pend:
    marc = []
    for c, r in TESTES:
        if ((M.caso == c) & (M.regime == r) & (M.modelo == mod)).any():
            marc.append("feito")
        elif c != "usinas" and r == "B" and mod in faltam_b_casas.get(c, []):
            marc.append("falta" if mod in RODA_EM_CPU else "falta (GPU)")
        else:
            marc.append(NA)
    cpu = mod in RODA_EM_CPU
    blocos.append((mod, "Já testado: falta casas B", marc,
                   "Não" if cpu else ("Sim" if mod == "TabPFN-TS" else "Recomendada"), "já no benchmark",
                   "Roda em CPU (máquina do Lactec)." if cpu else "Roda na máquina de casa (GPU)."))
# 2) os previstos, com a situacao tirada dos resultados (nao da lista)
feitos = falta = fora = 0
for mod, grupo, marc, gpu, lib, obs in PREVISTOS:
    nome = ALIAS.get(mod, mod)
    regs_fora, motivo = FORA.get(mod, (set(), ""))
    novo = []
    for (c, r), v in zip(TESTES, marc):
        if ((M.caso == c) & (M.regime == r) & (M.modelo == nome)).any():
            novo.append("feito")
        elif v != NA and mod in FORA and (regs_fora is None or r in regs_fora):
            novo.append("fora")
        else:
            novo.append(v)
    validos = [v for v in novo if v != NA]
    if validos and all(v == "fora" for v in validos):
        fora += 1
    elif any(v in (P, AC) for v in validos):
        falta += 1
    else:
        feitos += 1
    blocos.append((mod, grupo, novo, gpu, lib, " ".join(x for x in (motivo, A_ESTUDAR.get(mod, ""), obs) if x)))
i = 4
for mod, grupo, marc, gpu, lib, obs in blocos:
    celula(wp, i, 1, mod, negrito=True)
    celula(wp, i, 2, grupo)
    for j, v in enumerate(marc, start=3):
        cel = celula(wp, i, j, v, cor=CINZA if v in (NA, "fora") else None)
        if v in COR:
            cel.fill = COR[v]
    g = celula(wp, i, 9, gpu, negrito=gpu == "Sim")
    if gpu in COR_GPU:
        g.fill = COR_GPU[gpu]
    celula(wp, i, 10, lib)
    celula(wp, i, 11, obs)
    i += 1
i += 1
for t in [
    f"Hoje o artigo tem {len(media)} modelos. Dos {len(PREVISTOS)} previstos além dos 36 originais (do levantamento e "
    f"clássicos): {feitos} prontos, {falta} com algum teste ainda por fazer, {fora} fora (motivo na linha).",
    "A situação de cada célula sai dos resultados (metricas.csv), não desta lista: rodou, vira 'feito'.",
    "Fica de fora deste artigo: a previsão do tempo por IA (ECMWF AIFS), que é do regime C.",
    "'a confirmar' = o artigo do modelo diz aceitar variáveis externas, mas ainda não foi verificado no código se aceita "
    "o clima do PRÓPRIO dia (o que o regime B exige).",
    "Nenhum modelo sai sem estudo e evidência: os que não rodaram por viabilidade (xLSTM, Time-LLM) seguem previstos, "
    "com a rota para rodar. Fora = só o que um teste mostrou não funcionar.",
    "Cores: verde = feito; azul-claro = previsto; amarelo = falta e precisa da GPU; cinza = fora. GPU: laranja = "
    "inviável sem GPU; amarelo = roda em CPU, mas leva horas.",
]:
    texto(wp, i, t, "nota")
    i += 1
wp.freeze_panes = "B4"

wb.save(SAIDA)
print("ok", SAIDA, "| testes avaliados:", len(avaliados), "de", len(TESTES), "| modelos:", len(media),
      "| faltam nas casas B:", {k: len(v) for k, v in faltam_b_casas.items()}, "| resultados de", RES)
