# -*- coding: utf-8 -*-
"""Visao geral dos modelos de previsao: o que foi encontrado no levantamento e o que foi testado, SEM
resultados (os resultados estao em experimentos/testes_previsao/). Le o levantamento original e as
metricas atuais; grava Visao_geral_modelos_previsao.xlsx sem alterar o levantamento original.
"""
from datetime import date
from pathlib import Path
import json
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.table import Table, TableStyleInfo

AQUI = Path(__file__).resolve().parents[1]
FONTE = AQUI / "Modelos_previsao_geracao_consumo.xlsx"
SAIDA = AQUI / "Visao_geral_modelos_previsao.xlsx"
BENCHMARK = AQUI.parents[1] / "experimentos" / "testes_previsao"
METRICAS = BENCHMARK / "resultados" / "metricas.csv"
x = pd.read_excel(FONTE, sheet_name=None)
M = x["Modelos"].drop(columns=["Skill no teste (dia seguinte)"])
MOTIVO = {
    "Imagem de ceu / satelite": "Exige câmera de céu ou série de satélite, que o projeto não tem.",
    "Previsao do tempo por IA": "Produz o clima de entrada, não a geração; entra no lugar da fonte de clima (regime C).",
    "LLM": "Exige LLM grande e GPU; Tan et al. (NeurIPS 2024) mostram que tirar o LLM desses modelos não piora o resultado.",
    "Generativo (difusao e outros)": "Previsão probabilística, pesada em CPU; fica para quando o foco for incerteza.",
    "xLSTM": "Precisa de kernels compilados para GPU; a família está representada pelo TiRex (fundacional baseado em xLSTM).",
    "Espaco de estados (Mamba)": "Sem código aberto pronto para estas séries (horárias, uma a uma) em CPU.",
    "Informado por fisica": "Cada artigo usa a física da sua aplicação; a ideia está coberta pelo linear físico e pelo regime com clima.",
    "Grafo espaco-temporal": "Precisa de muitas séries vizinhas ligadas por um grafo e de código aberto; o projeto tem 2 usinas e 20 casas "
                             "de uma só comunidade (Dingle, Irlanda), sem coordenadas de cada casa.",
    "Transferencia / meta-aprendizado": "Sem código aberto pronto para estas séries; os fundacionais cobrem a ideia de transferir sem treino.",
    "Outros (arquitetura propria)": "Sem código aberto pronto para estas séries.",
}


def motivo(r):
    if r["Testado neste projeto"] == "Sim":
        return ""
    if "TimesFM-3" in r.Modelo:
        return "Pesos só para uso não comercial e fora do pacote do PyPI; testado o TimesFM-2.5."
    if r.Abordagem in MOTIVO:
        return MOTIVO[r.Abordagem]
    rep = TESTADOS_POR_FAMILIA.get(r.Abordagem)
    return f"Família já representada por {rep}; ficou fora para limitar o tempo de CPU." if rep else "Sem código aberto pronto para estas séries."


# ---------------------------------------------------------------- modelos testados (caracteristicas, sem resultado)
CASOS = {"usinas": "Usinas", "casas_prod": "FV das casas", "casas_cons": "Consumo das casas"}
T = [  # modelo, tipo, familia, no levantamento, implementacao, parametros, treina, aceita clima, observacao
    ("persist_24h", "Referência", "Persistência", "—", "próprio (02_referencias.py)", "0", "Não", "Não", "O mesmo horário de ontem."),
    ("semanal_168h", "Referência", "Persistência", "—", "próprio (02_referencias.py)", "0", "Não", "Não", "O mesmo horário de 7 dias atrás."),
    ("media_7d", "Referência", "Persistência", "—", "próprio (02_referencias.py)", "0", "Não", "Não", "Média do mesmo horário nos últimos 7 dias."),
    ("persist_ceu_claro", "Referência", "Física simples", "—", "próprio (02_referencias.py)", "0", "Não", "Só geometria",
     "Índice de céu claro de ontem aplicado ao céu claro de hoje. Referência das usinas."),
    ("linear_fisico", "Física", "Regressão linear", "—", "próprio (numpy)", "2 por usina", "Sim", "Sim (obrigatório)",
     "energia = a + b · irradiância no plano estimada."),
    ("LightGBM", "Árvore", "Gradient boosting", "—", "lightgbm", "—", "Sim", "Sim", "Um modelo global; defasagens e calendário (+ clima nos regimes B e C)."),
    ("LSTM", "Rede treinada", "Recorrente / convolucional", "LSTM", "NeuralForecast", "≈ 216 mil", "Sim", "Sim", ""),
    ("GRU", "Rede treinada", "Recorrente / convolucional", "GRU", "NeuralForecast", "≈ 389 mil", "Sim", "Sim", ""),
    ("TCN", "Rede treinada", "Recorrente / convolucional", "TCN", "NeuralForecast", "≈ 153 mil", "Sim", "Sim", "Rodou só sem clima."),
    ("ResNet-1D", "Rede treinada", "Recorrente / convolucional", "ResNet", "próprio (PyTorch, 04_redes_treinadas.py)", "≈ 122 mil", "Sim", "Não",
     "Wang et al. (2017) com cabeça de 24 saídas."),
    ("NHITS", "Rede treinada", "MLP / linear", "N-HiTS", "NeuralForecast", "≈ 2,8 milhões", "Sim", "Sim", ""),
    ("TiDE", "Rede treinada", "MLP / linear", "TiDE", "NeuralForecast", "≈ 1,5 milhão", "Sim", "Sim", ""),
    ("DLinear", "Rede treinada", "MLP / linear", "DLinear / NLinear", "NeuralForecast", "≈ 8 mil", "Sim", "Não", ""),
    ("TSMixerx", "Rede treinada", "MLP / linear", "TSMixer", "NeuralForecast", "≈ 82 mil", "Sim", "Sim", "Versão com variáveis externas; rodou só com clima."),
    ("SparseTSF", "Rede treinada", "MLP / linear", "SparseTSF", "próprio (PyTorch, 04_redes_treinadas.py)", "32", "Sim", "Não",
     "Lin et al. (2024); candidato ao embarcado."),
    ("PatchTST", "Rede treinada", "Transformer", "PatchTST", "NeuralForecast", "≈ 467 mil", "Sim", "Não", ""),
    ("iTransformer", "Rede treinada", "Transformer", "iTransformer", "NeuralForecast", "≈ 6,4 milhões", "Sim", "Não",
     "Trata as séries como variáveis de um mesmo sistema."),
    ("TFT", "Rede treinada", "Transformer", "Temporal Fusion Transformer (TFT)", "NeuralForecast", "≈ 1,4 milhão", "Sim", "Sim", "Rodou só com clima."),
    ("KAN", "Rede treinada", "Kolmogorov-Arnold (KAN)", "KAN", "NeuralForecast", "≈ 1,0 milhão", "Sim", "Sim", ""),
    ("Chronos-2", "Fundacional", "Fundacional (zero-shot)", "Chronos-2", "chronos-forecasting (Amazon)", "≈ 120 milhões", "Não", "Sim", "Covariáveis passadas e futuras."),
    ("Chronos-Bolt-small", "Fundacional", "Fundacional (zero-shot)", "Chronos", "chronos-forecasting (Amazon)", "≈ 48 milhões", "Não", "Não", ""),
    ("TimesFM-2.5", "Fundacional", "Fundacional (zero-shot)", "TimesFM", "timesfm (Google)", "≈ 200 milhões", "Não", "Sim",
     "Com clima: regressão linear nas covariáveis + TimesFM no resíduo."),
    ("TiRex", "Fundacional", "Fundacional (zero-shot)", "TiRex", "tirex (NX-AI)", "≈ 35 milhões", "Não", "Não", "Baseado em xLSTM."),
    ("TTM-r2", "Fundacional", "Fundacional (zero-shot)", "Tiny Time Mixers (TTM)", "granite-tsfm (IBM)", "≈ 3 milhões", "Não", "Não",
     "Roda em CPU em segundos; candidato ao embarcado."),
    ("Toto", "Fundacional", "Fundacional (zero-shot)", "Toto", "toto (Datadog)", "≈ 151 milhões", "Não", "Não", ""),
    ("Moirai-2.0-small", "Fundacional", "Fundacional (zero-shot)", "Moirai 2.0", "uni2ts (Salesforce), ambiente separado", "≈ 11 milhões", "Não", "Não",
     "Exige torch antigo; roda num ambiente Python à parte."),
    ("NBEATSx", "Rede treinada", "MLP / linear", "N-BEATS", "NeuralForecast", "—", "Sim", "Sim",
     "Variante N-BEATSx com covariáveis; lote 2."),
    ("Toto-2.0-22m", "Fundacional", "Fundacional (zero-shot)", "Toto 2.0", "toto2 (Datadog), ambiente lote2", "22 milhões", "Não", "Não",
     "Datadog/Toto-2.0-22m; mediana da distribuição prevista."),
    ("Toto-2.0-313m", "Fundacional", "Fundacional (zero-shot)", "Toto 2.0", "toto2 (Datadog), ambiente lote2", "313 milhões", "Não", "Não",
     "Datadog/Toto-2.0-313m; mediana da distribuição prevista."),
    ("TiRex-2", "Fundacional", "Fundacional (zero-shot)", "TiRex-2", "tirex (NX-AI), ambiente lote2", "Não registrado", "Não", "Sim",
     "NX-AI/TiRex-2; covariáveis futuras nos regimes B e C."),
    ("TabPFN-TS", "Fundacional", "Fundacional (zero-shot)", "TabPFN-TS", "tabpfn-time-series, ambiente lote2", "Não registrado", "Não", "Sim",
     "Pesos abertos v2; modo LOCAL, sem envio dos dados; executado em CUDA."),
    ("Sundial-128m", "Fundacional", "Fundacional (zero-shot)", "Sundial", "transformers, ambiente lote2_hf", "128 milhões", "Não", "Não",
     "thuml/sundial-base-128m; média de 20 amostras."),
    ("Timer-XL-84m", "Fundacional", "Fundacional (zero-shot)", "Timer / Timer-XL", "transformers, ambiente lote2_hf", "84 milhões", "Não", "Não",
     "Rótulo do benchmark; o checkpoint carregado é thuml/timer-base-84m (Timer base). Não comprova avaliação do Timer-XL."),
    ("Time-MoE-50M", "Fundacional", "Fundacional (zero-shot)", "Time-MoE", "transformers, ambiente lote2_hf", "50 milhões", "Não", "Não",
     "Maple728/TimeMoE-50M; previsão determinística."),
    ("Moirai-MoE-small", "Fundacional", "Fundacional (zero-shot)", "Moirai-MoE", "uni2ts (Salesforce), ambiente moirai", "Não registrado", "Não", "Não",
     "Salesforce/moirai-moe-1.0-R-small; mediana da distribuição prevista."),
    ("Ensemble-mediana", "Combinação", "Combinação", "—", "próprio (07_ensemble.py)", "—", "Não", "Herda dos membros",
     "Mediana, hora a hora, de todos os modelos não referência do mesmo caso e regime. Regra fixada antes do teste."),
]
metricas = pd.read_csv(METRICAS, sep=";", decimal=",")
rodou = {nome: set(zip(g.caso, g.regime)) for nome, g in metricas.groupby("modelo")}
sem_catalogo = set(rodou) - {r[0] for r in T}
if sem_catalogo:
    raise ValueError(f"Modelos presentes nas metricas sem descricao no catalogo: {sorted(sem_catalogo)}")
# Uma entrada bibliografica pode representar mais de uma variante (por exemplo, Toto 2.0).
testados = {r[3] for r in T if r[0] in rodou and r[3] != "—"}
M["Testado neste projeto"] = M.Modelo.map(lambda nome: "Sim" if nome in testados else "Não")
TESTADOS_POR_FAMILIA = M[M["Testado neste projeto"] == "Sim"].groupby("Abordagem").Modelo.apply(lambda s: ", ".join(s))
M["Por que não foi testado"] = M.apply(motivo, axis=1)
tempos = {}
for arquivo in sorted((BENCHMARK / "resultados").glob("tempos_redes*.json")):
    tempos.update(json.loads(arquivo.read_text(encoding="utf-8")))
ordem_regimes = {nome: i for i, nome in enumerate(["A", "B", "C", "B-curto", "C-gfs"])}
linhas = []
for mod, tipo, fam, lev, impl, par, treina, clima, obs in T:
    r = rodou.get(mod, set())
    if not r:
        continue
    us = sorted({rg for c, rg in r if c == "usinas"}, key=lambda rg: (ordem_regimes.get(rg, 99), rg))
    contagens = sorted({v["parametros"] for chave, v in tempos.items()
                        if chave.split("|")[:2] == [mod, "usinas"] and "parametros" in v})
    if contagens:
        par = " a ".join(f"{n:,}".replace(",", ".") for n in [contagens[0], contagens[-1]]) if len(contagens) > 1 else f"{contagens[0]:,}".replace(",", ".")
    linhas.append([mod, tipo, fam, lev, impl, par, treina, clima,
                   ", ".join(us) if us else "—",
                   "Sim" if ("casas_prod", "A") in r else "Não", "Sim" if ("casas_cons", "A") in r else "Não", obs])
TT = pd.DataFrame(linhas, columns=["Modelo", "Tipo", "Família", "Nome no levantamento", "Implementação", "Parâmetros",
                                   "Treina nos dados?", "Aceita clima?", "Usinas: regimes", "FV das casas", "Consumo das casas",
                                   "Observação"])

# ---------------------------------------------------------------- testaveis: testados (do melhor ao pior) + o que falta
# GPU: "Sim" = inviavel sem GPU; "Recomendada" = roda em CPU, mas lento (horas); "Não" = CPU basta.
GPU_RAPIDO = ("Não", "Roda em segundos em CPU.")
GPU_ZERO_SHOT = ("Não", "Zero-shot: só inferência, minutos em CPU.")
GPU_REDE = ("Recomendada", "Retreinada a cada dobra; na v2 rodou em CUDA. Em CPU funciona, mas leva horas.")
GPU_TESTADOS = {
    "TabPFN-TS": ("Sim", "Em CPU leva dias; rodou em CUDA."),
    "TiRex-2": ("Não", "Roda em CPU e precisa da GPU ESCONDIDA (CUDA_VISIBLE_DEVICES=-1): o kernel sLSTM exige nvcc."),
    "DLinear": ("Não", "Rede minúscula; CPU basta."),
    "SparseTSF": ("Não", "32 parâmetros; CPU basta."),
}
for mod, tipo, *_ in T:
    if mod not in GPU_TESTADOS:
        GPU_TESTADOS[mod] = {"Fundacional": GPU_ZERO_SHOT, "Rede treinada": GPU_REDE}.get(tipo, GPU_RAPIDO)

# Os 24 do levantamento com codigo aberto que ainda faltam (plano do TCC, passo T). Nome = coluna Modelo do levantamento.
FALTA = [  # nome no levantamento, grupo, gpu, por que (gpu), cuidado
    ("TimeMixer", "Rede treinada (NeuralForecast)", *GPU_REDE, "Já no NeuralForecast instalado; entra no 04_redes_treinadas.py."),
    ("TimesNet", "Rede treinada (NeuralForecast)", *GPU_REDE, "Já no NeuralForecast instalado."),
    ("DeepAR", "Rede treinada (NeuralForecast)", *GPU_REDE, "Já no NeuralForecast instalado; probabilístico (usar a mediana)."),
    ("TimeXer", "Rede treinada (NeuralForecast)", *GPU_REDE, "Já no NeuralForecast instalado; feito para variáveis externas (regimes B e C)."),
    ("FEDformer", "Rede treinada (NeuralForecast)", *GPU_REDE, "Já no NeuralForecast instalado."),
    ("Autoformer", "Rede treinada (NeuralForecast)", *GPU_REDE, "Já no NeuralForecast instalado."),
    ("Informer", "Rede treinada (NeuralForecast)", *GPU_REDE, "Já no NeuralForecast instalado."),
    ("xLSTM", "Rede treinada (NeuralForecast)", *GPU_REDE, "Usar a versão do NeuralForecast, que não precisa dos kernels CUDA do NX-AI/xlstm."),
    ("Time-LLM", "Rede treinada (NeuralForecast)", "Sim", "Tem um LLM dentro (GPT-2 ou maior); inviável em CPU.",
     "Já no NeuralForecast instalado."),
    ("Moirai", "Fundacional", *GPU_ZERO_SHOT, "Moirai 1.x; o ambiente moirai (uni2ts) já existe."),
    ("MOMENT", "Fundacional", "Recomendada", "Modelo grande (~385 milhões); lento em CPU.", "Pacote momentfm; precisa de ambiente próprio."),
    ("VisionTS", "Fundacional", *GPU_ZERO_SHOT, "Pacote visionts (trata a série como imagem)."),
    ("Lag-Llama", "Fundacional", *GPU_ZERO_SHOT, "Código no GitHub; dependências antigas (gluonts)."),
    ("FlowState", "Fundacional", *GPU_ZERO_SHOT, "granite-tsfm: completo só na máquina do Lactec."),
    ("BuildingsBench (Transformer pre-treinado)", "Fundacional", *GPU_ZERO_SHOT, "Treinado em prédios: só no consumo das casas."),
    ("TimesFM-3", "Fundacional", *GPU_ZERO_SHOT, "Pesos só para uso não comercial: vale para o TCC, não entra na biblioteca."),
    ("TimeGPT", "Fundacional (serviço)", "Não", "Roda nos servidores da Nixtla (API paga).",
     "Envia os dados para fora: SÓ com as casas (CC0), NUNCA com as usinas."),
    ("CycleNet", "Rede treinada (repositório próprio)", *GPU_REDE, "Precisa de adaptador."),
    ("DUET", "Rede treinada (repositório próprio)", *GPU_REDE, "Precisa de adaptador (código no TFB)."),
    ("Crossformer", "Rede treinada (repositório próprio)", *GPU_REDE, "Precisa de adaptador (código no TSLib)."),
    ("S-Mamba", "Rede treinada (repositório próprio)", "Sim", "Usa mamba_ssm, que só tem kernels CUDA.",
     "Precisa de adaptador (TSLib); pode exigir Linux (WSL)."),
    ("Mamba", "Rede treinada (repositório próprio)", "Sim", "Usa mamba_ssm, que só tem kernels CUDA.",
     "Precisa de adaptador; pode exigir Linux (WSL)."),
    ("LLMTime", "LLM", "Sim", "Roda um LLM local para gerar a série.", "Lento mesmo em GPU; usar um LLM aberto no lugar do GPT-3."),
    ("TimeGrad", "Generativo (difusão)", *GPU_REDE, "PyTorchTS; prevê uma faixa (avaliar a mediana e, depois, o CRPS)."),
]
sem_levantamento = {f[0] for f in FALTA} - set(M.Modelo)
if sem_levantamento:
    raise ValueError(f"Modelos a testar que nao estao no levantamento: {sorted(sem_levantamento)}")
ja_testados = {f[0] for f in FALTA} & testados
if ja_testados:
    raise ValueError(f"Ja testados, tirar da lista FALTA: {sorted(ja_testados)}")

# Posicao: em cada (caso, regime) principal, rank pelo skill; normaliza para 0 (1o) .. 1 (ultimo) e tira a media.
# Assim um modelo que so rodou com clima (TFT) e comparavel a um que rodou em tudo. O "ranking medio" do
# LEIA-ME dos testes (regime A, tres casos) vai numa coluna a parte e e reproduzido exatamente.
principais = metricas[metricas.regime.isin(["A", "B", "C"])].copy()
grupo = principais.groupby(["caso", "regime"]).skill
principais["rk"] = grupo.rank(ascending=False, method="min")
principais["pct"] = (principais.rk - 1) / (grupo.transform("size") - 1)
pos_rel = principais.groupby("modelo").pct.agg(["mean", "size"])
noA = principais[principais.regime == "A"].pivot(index="modelo", columns="caso", values="rk")
rk_medio_A = noA.dropna().mean(axis=1)
skill = principais.pivot_table(index="modelo", columns=["caso", "regime"], values="skill")
COLS_SKILL = [("usinas", "A"), ("usinas", "B"), ("usinas", "C"), ("casas_prod", "A"), ("casas_cons", "A")]
tipo_de = {r[0]: r[1] for r in T}
obs_de = {r[0]: r[8] for r in T}
lin_t = []
for pos, (mod, r) in enumerate(pos_rel.sort_values("mean").iterrows(), start=1):
    gpu, por_que = GPU_TESTADOS[mod]
    lin_t.append([pos, mod, "Testado", tipo_de[mod], gpu, por_que, round(r["mean"], 3),
                  round(rk_medio_A[mod], 1) if mod in rk_medio_A else None, int(r["size"]),
                  *[round(skill.at[mod, c], 3) if c in skill.columns and pd.notna(skill.at[mod, c]) else None for c in COLS_SKILL],
                  obs_de.get(mod, "")])
for nome, grp, gpu, por_que, cuidado in FALTA:
    lin_t.append([None, nome, "Falta testar", grp, gpu, por_que, None, None, None, *[None] * len(COLS_SKILL), cuidado])
lin_t.append([None, "ECMWF AIFS (regime C)", "Falta testar", "Previsão do tempo por IA", "Não",
              "Só baixar o arquivo de previsões (Open-Meteo).", None, None, None, *[None] * len(COLS_SKILL),
              "Não é um modelo de série: troca o IFS pelo AIFS no regime C. Representa GraphCast/Aurora/WeatherNext, "
              "que exigem rodar um modelo global. Depende de haver arquivo histórico."])
TV = pd.DataFrame(lin_t, columns=["Posição", "Modelo", "Situação", "Tipo", "Precisa de GPU?", "Por que (GPU)",
                                  "Posição relativa média (0 = melhor)", "Ranking médio (regime A, 3 casos)",
                                  "Combinações avaliadas", "Skill usinas A", "Skill usinas B", "Skill usinas C",
                                  "Skill FV casas A", "Skill consumo A", "Observação / cuidado"])

# ---------------------------------------------------------------- planilha
wb = Workbook()
AZUL, CINZA_CLARO = "0F5C6E", "F2F5F6"
cab = Font(name="Arial", bold=True, color="FFFFFF", size=10)
txt = Font(name="Arial", size=10)
fino = Side(style="thin", color="D5DCE0")


def grava_tabela(ws, df, nome, larguras, linha0=1):
    for j, c in enumerate(df.columns, start=1):
        cel = ws.cell(row=linha0, column=j, value=c)
        cel.font, cel.fill = cab, PatternFill("solid", fgColor=AZUL)
        cel.alignment = Alignment(wrap_text=True, vertical="center")
    for i, row in enumerate(df.itertuples(index=False), start=linha0 + 1):
        for j, v in enumerate(row, start=1):
            v = None if (isinstance(v, float) and pd.isna(v)) else v
            cel = ws.cell(row=i, column=j, value=v)
            cel.font = txt
            cel.alignment = Alignment(wrap_text=True, vertical="top")
            cel.border = Border(bottom=fino)
            if isinstance(v, str) and v.startswith("http"):
                cel.hyperlink = v; cel.font = Font(name="Arial", size=10, color="1F5FBF", underline="single")
    for j, w in enumerate(larguras, start=1):
        ws.column_dimensions[get_column_letter(j)].width = w
    ref = f"A{linha0}:{get_column_letter(len(df.columns))}{linha0 + len(df)}"
    t = Table(displayName=nome, ref=ref)
    t.tableStyleInfo = TableStyleInfo(name="TableStyleLight1", showRowStripes=True)
    ws.add_table(t)
    ws.freeze_panes = ws.cell(row=linha0 + 1, column=3)


ws = wb.active; ws.title = "Leia-me"
leia = [
    ("Visão geral dos modelos de previsão de geração solar e consumo", True),
    (f"Projeto Edge AI (GRD-ACS-2026-1-21-1). Gerada em {date.today():%d/%m/%Y} por docs/literatura/scripts/gera_visao_geral_modelos.py.", False),
    ("", False),
    ("Esta planilha diz o que existe, o que foi testado e por que o resto ficou de fora. Só a aba Testáveis traz resultados (posição e skill).", True),
    ("Os resultados completos (erros, IC, testes estatísticos) estão em experimentos/testes_previsao/resultados/ e em experimentos/testes_previsao/LEIA-ME.md.", False),
    ("", False),
    ("Abas", True),
    ("Resumo — quantos modelos foram encontrados e testados em cada abordagem (fórmulas sobre a aba Encontrados).", False),
    (f"Testáveis — tudo o que dá para testar com estes dados: os {len(pos_rel)} já testados, do melhor ao pior, e os "
     f"{len(TV) - len(pos_rel)} que faltam (24 do levantamento com código aberto + a previsão do tempo por IA no regime C), "
     "com a indicação de quem precisa de GPU.", False),
    ("   Ordem: em cada caso e regime principal (A, B, C), os modelos são ordenados pelo skill; a posição vira 0 (1º) a 1 (último) "
     "e tira-se a média. Assim quem só rodou com clima (TFT, TSMixerx, linear físico) se compara com quem rodou em tudo. "
     "O 'Ranking médio (regime A, 3 casos)' é o mesmo número do LEIA-ME dos testes.", False),
    ("   GPU: 'Sim' = inviável sem GPU; 'Recomendada' = roda em CPU, mas leva horas; 'Não' = CPU basta. "
     "A máquina do Lactec não tem GPU; a de casa tem (RTX 4070).", False),
    ("Encontrados — os 127 modelos do levantamento de 28/09/2026: o que cada um tem de diferente, onde achar, se foi testado e, se não, por quê.", False),
    (f"Testados — {len(TT)} modelos, variantes e referências presentes nas métricas atuais ({len(metricas)} combinações caso/regime), correspondendo a {len(testados)} entradas do levantamento e 7 referências/combinações.", False),
    ("Bibliotecas — 40 bibliotecas de previsão (versão, licença, situação), conferidas em 28/09/2026.", False),
    ("Benchmarks — 12 benchmarks de referência da área.", False),
    ("", False),
    ("Como ler", True),
    ("Regimes nas usinas: A = só o histórico; B = + clima do próprio dia (NASA, previsão perfeita, é um teto); "
     "C = + previsão do tempo real emitida na véspera (ECMWF). As casas só têm o regime A.", False),
    ("Cobertura extraída de resultados/metricas.csv do protocolo v2, incluindo o lote 2; presença nas métricas não substitui a auditoria de cobertura das previsões. Nenhum regime é marcado apenas por estar planejado.", False),
    ("Diagnósticos das usinas: B-curto = clima NASA com o mesmo período de treino de C; C-gfs = previsão GFS em vez de ECMWF. Redes treinadas usam origem deslizante; fundacionais zero-shot não retreinam.", False),
    ("'?' no levantamento significa que o artigo não deixa claro; nada foi preenchido por suposição.", False),
    ("Parâmetros dos fundacionais: identificação dos checkpoints/levantamento, sem nova medição. Das redes: mínimo e máximo registrados em tempos_redes*.json nas usinas (variam com o regime). 'Aceita clima?' descreve a implementação usada.", False),
    ("Motivos de exclusão preservam decisões do levantamento; não constituem uma nova verificação de disponibilidade, licença ou hardware. Bibliotecas, links e citações mantêm a data de 28/09/2026.", False),
    ("Fonte bibliográfica: Modelos_previsao_geracao_consumo.xlsx, preservada como registro histórico com resultados antigos. O status 'Testado' desta visão é recalculado usando as métricas atuais e os nomes/variantes da aba Testados.", False),
    ("A linha N-BEATS foi representada por N-BEATSx; Timer / Timer-XL foi representada por Timer base (rótulo Timer-XL-84m nos resultados). Toto 2.0 foi testado em dois tamanhos; estas variantes não aumentam o total de entradas bibliográficas.", False),
]
for i, (t, negrito) in enumerate(leia, start=1):
    c = ws.cell(row=i, column=1, value=t)
    c.font = Font(name="Arial", size=12 if i == 1 else 10, bold=negrito, color=AZUL if i == 1 else "1D232A")
    c.alignment = Alignment(wrap_text=True, vertical="top")
ws.column_dimensions["A"].width = 130

# Encontrados
we = wb.create_sheet("Encontrados")
cols = ["Abordagem", "Modelo", "Ano", "Novo (2025-26)", "O que tem de diferente", "Aplicacao testada", "Zero-shot / pre-treinado",
        "Aceita variaveis externas (clima)", "Embarcavel", "Testado neste projeto", "Por que não foi testado", "Onde encontrar",
        "Codigo", "Artigo", "Veiculo", "Citacoes", "Link"]
E = M[cols].rename(columns={"Novo (2025-26)": "Novo (2025–26)", "Aplicacao testada": "Aplicação no artigo",
                            "Zero-shot / pre-treinado": "Zero-shot / pré-treinado",
                            "Aceita variaveis externas (clima)": "Aceita variáveis externas (clima)",
                            "Embarcavel": "Embarcável", "Codigo": "Código", "Veiculo": "Veículo", "Citacoes": "Citações (28/09/2026)"})
E["_ano"] = pd.to_numeric(E["Ano"], errors="coerce").fillna(9999)          # 'no prelo' vai para o topo
E = E.sort_values(["Abordagem", "Testado neste projeto", "_ano"], ascending=[True, False, False]).drop(columns="_ano")
E["Ano"] = [int(a) if isinstance(a, (int, float)) and not pd.isna(a) else a for a in E["Ano"]]
grava_tabela(we, E, "Encontrados", [24, 26, 7, 9, 48, 14, 13, 14, 12, 10, 44, 22, 30, 40, 26, 11, 30])

# Testados
wt = wb.create_sheet("Testados")
grava_tabela(wt, TT, "Testados", [19, 13, 24, 24, 30, 14, 10, 14, 12, 10, 11, 52])

# Resumo (formulas sobre Encontrados)
wr = wb.create_sheet("Resumo", 1)
abord = sorted(M.Abordagem.unique())
cab_r = ["Abordagem", "Encontrados", "Testados", "Não testados", "Novos (2025–26)"]
for j, c in enumerate(cab_r, start=1):
    cel = wr.cell(row=1, column=j, value=c); cel.font, cel.fill = cab, PatternFill("solid", fgColor=AZUL)
n = len(E) + 1
for i, a in enumerate(abord, start=2):
    wr.cell(row=i, column=1, value=a)
    wr.cell(row=i, column=2, value=f"=COUNTIF(Encontrados!$A$2:$A${n},A{i})")
    wr.cell(row=i, column=3, value=f'=COUNTIFS(Encontrados!$A$2:$A${n},A{i},Encontrados!$J$2:$J${n},"Sim")')
    wr.cell(row=i, column=4, value=f"=B{i}-C{i}")
    wr.cell(row=i, column=5, value=f'=COUNTIFS(Encontrados!$A$2:$A${n},A{i},Encontrados!$D$2:$D${n},"Sim")')
k = len(abord) + 2
wr.cell(row=k, column=1, value="Total")
for j in range(2, 6):
    L = get_column_letter(j)
    wr.cell(row=k, column=j, value=f"=SUM({L}2:{L}{k - 1})")
for row in wr.iter_rows(min_row=2, max_row=k):
    for c in row:
        c.font = Font(name="Arial", size=10, bold=(c.row == k)); c.border = Border(bottom=fino)
wr.cell(row=k + 2, column=1, value="Além dos testados do levantamento, os testes incluem 7 linhas de base e combinações "
        "(persistências, linear físico, LightGBM, ensemble): ver aba Testados.").font = Font(name="Arial", size=9, italic=True)
wr.column_dimensions["A"].width = 34
for L in "BCDE":
    wr.column_dimensions[L].width = 14
wr.freeze_panes = "A2"

# Testaveis (logo depois do Resumo)
wv = wb.create_sheet("Testáveis", 2)
grava_tabela(wv, TV, "Testaveis", [8, 26, 13, 24, 12, 40, 12, 12, 11, 9, 9, 9, 9, 9, 60])
COR_GPU = {"Sim": "F8D2BE", "Recomendada": "FFF0C2"}
cinza = Font(name="Arial", size=10, italic=True, color="5A6470")
for i, row in enumerate(TV.itertuples(index=False), start=2):
    g = wv.cell(row=i, column=5)
    if row[4] in COR_GPU:
        g.fill = PatternFill("solid", fgColor=COR_GPU[row[4]])
    g.font = Font(name="Arial", size=10, bold=row[4] == "Sim")
    if row[2] == "Falta testar":
        for j in (2, 3, 4, 6, 15):
            wv.cell(row=i, column=j).font = cinza
    for j in range(10, 15):
        wv.cell(row=i, column=j).number_format = "+0.000;-0.000;0.000"
    wv.cell(row=i, column=7).number_format = "0.000"
    wv.cell(row=i, column=8).number_format = "0.0"
    wv.cell(row=i, column=1).number_format = "0"
    wv.cell(row=i, column=9).number_format = "0"

# Bibliotecas e Benchmarks (como no levantamento)
for aba, larg in [("Bibliotecas", [18, 22, 50, 10, 12, 12, 9, 14, 10, 20, 40]), ("Benchmarks", [16, 60, 7, 30, 40, 11])]:
    w = wb.create_sheet(aba)
    grava_tabela(w, x[aba], aba, larg)
wb.calculation.fullCalcOnLoad = True
wb.save(SAIDA)
print("ok", SAIDA, "| encontrados", len(E), "| testados", len(TT))
