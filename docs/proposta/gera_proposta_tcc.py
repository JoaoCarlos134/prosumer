"""Gera a proposta acadêmica da biblioteca prossumidor em PDF."""
import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
from reportlab.platypus import (BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer,
                                Table, TableStyle, PageBreak, Preformatted, KeepTogether,
                                NextPageTemplate)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping

F = "C:/Windows/Fonts/"
pdfmetrics.registerFont(TTFont("Arial", F + "arial.ttf"))
pdfmetrics.registerFont(TTFont("Arial-B", F + "arialbd.ttf"))
pdfmetrics.registerFont(TTFont("Arial-I", F + "ariali.ttf"))
pdfmetrics.registerFont(TTFont("Arial-BI", F + "arialbi.ttf"))
pdfmetrics.registerFont(TTFont("Consolas", F + "consola.ttf"))
addMapping("Arial", 0, 0, "Arial"); addMapping("Arial", 1, 0, "Arial-B")
addMapping("Arial", 0, 1, "Arial-I"); addMapping("Arial", 1, 1, "Arial-BI")

SAIDA = sys.argv[1]
ACENTO = colors.HexColor("#0F5C6E")
CLARO = colors.HexColor("#E8F1F3")
CINZA = colors.HexColor("#5A6470")
LINHA = colors.HexColor("#C9D3D8")

base = dict(fontName="Arial", fontSize=10, leading=14.2, textColor=colors.HexColor("#1D232A"))
S = {
    "corpo": ParagraphStyle("corpo", alignment=TA_JUSTIFY, spaceAfter=6, **base),
    "lista": ParagraphStyle("lista", leftIndent=14, bulletIndent=3, spaceAfter=3, **base),
    "h1": ParagraphStyle("h1", fontName="Arial-B", fontSize=15, leading=19, textColor=ACENTO,
                         spaceBefore=14, spaceAfter=8),
    "h2": ParagraphStyle("h2", fontName="Arial-B", fontSize=11.5, leading=15, textColor=ACENTO,
                         spaceBefore=10, spaceAfter=5),
    "cel": ParagraphStyle("cel", fontName="Arial", fontSize=8.6, leading=11.2),
    "celb": ParagraphStyle("celb", fontName="Arial-B", fontSize=8.6, leading=11.2, textColor=colors.white),
    "nota": ParagraphStyle("nota", fontName="Arial-I", fontSize=8.6, leading=11.5, textColor=CINZA,
                           spaceAfter=6),
    "caixa": ParagraphStyle("caixa", fontName="Arial", fontSize=10, leading=14.2, alignment=TA_LEFT),
    "codigo": ParagraphStyle("codigo", fontName="Consolas", fontSize=7.9, leading=10.2,
                             backColor=colors.HexColor("#F4F6F7"), borderPadding=6,
                             leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=10),
}

story = []
P = lambda t, s="corpo": story.append(Paragraph(t, S[s]))
H1 = lambda t: story.append(Paragraph(t, S["h1"]))
H2 = lambda t: story.append(Paragraph(t, S["h2"]))


def itens(lst):
    for t in lst:
        story.append(Paragraph(t, S["lista"], bulletText="•"))
    story.append(Spacer(1, 4))


def tabela(cab, linhas, larg, zebra=True):
    dados = [[Paragraph(c, S["celb"]) for c in cab]]
    dados += [[Paragraph(str(c), S["cel"]) for c in l] for l in linhas]
    t = Table(dados, colWidths=[w * cm for w in larg], repeatRows=1)
    est = [("BACKGROUND", (0, 0), (-1, 0), ACENTO),
           ("VALIGN", (0, 0), (-1, -1), "TOP"),
           ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINHA),
           ("TOPPADDING", (0, 0), (-1, -1), 3.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
           ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if zebra:
        for i in range(2, len(dados), 2):
            est.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F8F9")))
    t.setStyle(TableStyle(est))
    story.append(t)
    story.append(Spacer(1, 8))


def tabela_inteira(*a, **k):
    ini = len(story)
    tabela(*a, **k)
    bloco = story[ini - 1:]
    del story[ini - 1:]
    story.append(KeepTogether(bloco))


def caixa(texto):
    t = Table([[Paragraph(texto, S["caixa"])]], colWidths=[16.4 * cm])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), CLARO),
                           ("LINEBEFORE", (0, 0), (0, -1), 3, ACENTO),
                           ("LEFTPADDING", (0, 0), (-1, -1), 10), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                           ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story.append(t)
    story.append(Spacer(1, 10))


# ---------------------------------------------------------------- capa
story.append(Spacer(1, 4.2 * cm))
story.append(Paragraph("PROPOSTA DE DESENVOLVIMENTO ACADÊMICO", ParagraphStyle(
    "k", fontName="Arial-B", fontSize=10, textColor=ACENTO, leading=14)))
story.append(Spacer(1, 6))
story.append(Paragraph("Biblioteca <i>prossumidor</i>", ParagraphStyle(
    "t", fontName="Arial-B", fontSize=30, leading=36, textColor=colors.HexColor("#14202A"))))
story.append(Spacer(1, 4))
story.append(Paragraph("Previsão e diagnóstico de prossumidores de energia, do medidor ao "
                       "modelo embarcado", ParagraphStyle(
    "st", fontName="Arial", fontSize=15, leading=20, textColor=CINZA)))
story.append(Spacer(1, 1.4 * cm))
capa = [
    ["Projeto de origem", "GRD-ACS-2026-1-21-1 — Edge AI: plataforma de hardware com inteligência "
                          "artificial embarcada para smart buildings (CC EMBRAPII Lactec)"],
    ["Uso acadêmico proposto", "Trabalho de Conclusão de Curso (TCC), com continuidade possível "
                               "em dissertação de mestrado"],
    ["Autor", "João Jachenski Junior"],
    ["Data", "05 de outubro de 2026"],
    ["Situação", "Rascunho para discussão com a gestão — depende de autorização (seção 11)"],
]
t = Table([[Paragraph(a, S["celb"].clone("x", textColor=ACENTO)), Paragraph(b, S["cel"])]
           for a, b in capa], colWidths=[4.2 * cm, 12.2 * cm])
t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.4, LINHA), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                       ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
story.append(t)
story.append(NextPageTemplate("normal"))
story.append(PageBreak())

# ---------------------------------------------------------------- resumo
H1("Resumo")
P("Ao longo do projeto Edge AI foram escritos cerca de 80 scripts Python (≈ 11.800 linhas) para "
  "tratar os dados das usinas fotovoltaicas de Cascavel e Curitiba e das 20 residências, diagnosticar "
  "falhas, modelar a geração e testar 33 modelos de previsão do dia seguinte. Grande parte desse "
  "código foi produzida além do escopo pedido, aproveitando os dados disponíveis. A análise de rede "
  "do projeto (02/10/2026) mostrou que essa base, embora produtiva, é frágil: a mesma lógica aparece "
  "repetida em até 19 scripts, um arquivo intermediário de que 19 scripts dependem não existe no "
  "disco e os números chegam aos relatórios por transcrição manual.")
P("Esta proposta é transformar esse código em uma biblioteca Python organizada, testada e "
  "documentada — <b>prossumidor</b> — e usar o seu desenvolvimento e validação como Trabalho de "
  "Conclusão de Curso do autor. A biblioteca é uma camada de domínio fina sobre ferramentas "
  "consolidadas (pvlib, NeuralForecast, modelos fundacionais), e reúne o que nenhuma delas faz: "
  "diagnóstico só com dados do inversor, um protocolo único de comparação de modelos, o contexto "
  "tarifário brasileiro e o caminho até o hardware embarcado.")
caixa("<b>O que se pede à gestão:</b> autorização para o uso acadêmico do código e dos resultados "
      "agregados; definição de titularidade, autoria e licença; e, se fizer sentido, o enquadramento da "
      "biblioteca como o <b>registro de software previsto no Marco 3</b> do projeto. A lista completa "
      "de decisões está na seção 11.")

# ---------------------------------------------------------------- 1 contexto
H1("1. Contexto")
P("O projeto Edge AI (TRL 2 → 4) prevê, entre seus marcos, a implementação de modelos de IA em "
  "computadores com adaptação para plataformas de baixo desempenho e o <b>registro de software</b> "
  "(Marco 3), seguido da validação dos modelos na plataforma embarcada (Marco 4). Nas frentes de "
  "previsão de geração e consumo, o trabalho já realizado inclui:")
itens([
    "<b>Usinas FV (set/2026):</b> séries de 5 min unificadas (694 mil e 490 mil linhas), base de "
    "modelagem com 620 mil linhas, diagnóstico de sujeira e falha de string, base tarifária "
    "Copel/ANEEL e 32 modelos exportados para TensorFlow Lite. Pipeline reprodutível: 42 etapas "
    "refeitas a partir dos dados brutos com 80 saídas idênticas byte a byte.",
    "<b>Testes de previsão (30/09–02/10/2026):</b> 33 modelos e referências — árvores, redes "
    "recorrentes, convolucionais e transformers, e 7 modelos fundacionais sem treino — em 3 casos "
    "(usinas, geração FV e consumo de residências), com intervalos de confiança por bootstrap.",
    "<b>Análise de rede (02/10/2026):</b> grafo de 1.342 nós e 2.570 arestas ligando código, dados, "
    "documentos e literatura, que identificou os problemas estruturais abaixo.",
])
H2("1.1 Problemas que motivam a biblioteca")
tabela(["Sintoma encontrado", "Medida", "Consequência"], [
    ["Data de corte do teste escrita à mão", "16 scripts", "mudar o teste exige editar 16 arquivos"],
    ["Métricas (R², MAE, …) reimplementadas", "19 scripts", "definições podem divergir entre relatórios"],
    ["Agregação horária reescrita", "7 scripts", "cada uma com sua regra para buracos e noite"],
    ["Semente aleatória fixada separadamente", "12 scripts", "reprodutibilidade depende de disciplina"],
    ["Nó mais conectado do projeto", "frame5.parquet", "19 scripts dependem de um arquivo que não existe no disco"],
    ["Cadeia de dados mais longa", "14 etapas", "mudar o kWp (4,00 → 3,96) afetou ~110 arquivos, refeitos à mão"],
    ["Saídas que nenhum código lê", "27 resultados", "números transcritos à mão para os relatórios"],
    ["Modelos TFLite nunca recarregados", "32 de 32", "o caminho até o embarcado nunca foi testado"],
    ["Quebras de ambiente em um dia de testes", "3", "APIs dos modelos fundacionais mudam a cada trimestre"],
], [5.6, 2.8, 8.0])

# ---------------------------------------------------------------- 2 o que resolve
H1("2. O que a biblioteca resolve")
H2("2.1 Para o projeto")
itens([
    "<b>Um protocolo, um lugar:</b> datas de corte, sementes, métricas e janelas de previsão "
    "definidas uma vez, na tarefa — nunca no script.",
    "<b>Pipeline declarado:</b> cada etapa declara o que lê e escreve; só o que mudou é refeito "
    "(Snakemake ou DVC por cima, sem executor próprio).",
    "<b>Resultados lidos por código:</b> relatórios e figuras gerados a partir das saídas, sem "
    "transcrição manual.",
    "<b>Isolamento das dependências instáveis:</b> cada modelo fundacional entra como adaptador "
    "opcional com versão travada; uma mudança de API quebra um adaptador, não o projeto.",
    "<b>Embarcado testado a partir do artefato:</b> o modelo exportado é recarregado e medido "
    "(tamanho, acurácia, latência) — insumo direto para o Marco 4.",
])
H2("2.2 Para a área: a lacuna que justifica a biblioteca")
P("As bibliotecas existentes resolvem bem a física solar (pvlib), as redes neurais "
  "(NeuralForecast, Darts), a previsão de carga em produção (OpenSTEF) e a degradação (RdTools). "
  "Nenhuma delas faz:")
tabela(["Contribuição", "Por que importa", "Origem no projeto"], [
    ["Diagnóstico só com dados do inversor", "a maioria das instalações pequenas não tem sensor de "
     "irradiância; separação corrente × tensão CC para sujeira e MPPTs como controle mútuo para falha "
     "de string", "a2_fault.py, a3_shading.py, changepoint.py, curitiba_analysis2.py"],
    ["Protocolo de previsão congelado", "compara referências, árvores, redes e fundacionais na mesma "
     "tarefa, com regimes explícitos e IC 95% por bootstrap", "testes_modelos/scripts/comum.py, 05_avalia.py"],
    ["Formatos reais de entrada", "Fronius Solar.web, medidores de 1 min, faturas; detecção de série "
     "sem sinal, minuto corrompido e horário de verão", "merge_5min.py, merge_curitiba.py, 01_prepara_dados.py"],
    ["Contexto tarifário brasileiro", "TUSD/TE da ANEEL, bandeiras, ICMS, Lei 14.300 e créditos que "
     "expiram", "tarifas/, billing.py, aplica_tarifas.py"],
    ["Caminho até o embarcado", "exportação e medição iguais para todas as famílias de modelo",
     "compara_modelos_embarcado.py"],
], [4.0, 7.4, 5.0])
P("O que a biblioteca <b>não</b> faz: reimplementar geometria solar, redes neurais ou modelos "
  "fundacionais. Esses entram como dependências ou adaptadores. Isso mantém o escopo viável para "
  "uma pessoa e a manutenção baixa.", "corpo")

# ---------------------------------------------------------------- 3 objetivos
H1("3. Objetivos")
H2("3.1 Objetivo geral")
P("Desenvolver e validar uma biblioteca Python de código organizado, testado e documentado para "
  "previsão do dia seguinte e diagnóstico de prossumidores fotovoltaicos, do dado bruto do medidor "
  "ao modelo embarcado, a partir do código e dos resultados do projeto Edge AI.")
H2("3.2 Objetivos específicos")
itens([
    "OE1 — Reunir num pacote único, com contratos de dados (unidade, fuso, taxa, máscara de "
    "validade), as rotinas de leitura, qualidade de dados, física solar e protocolo de previsão.",
    "OE2 — Reproduzir com a biblioteca os resultados já obtidos: o pipeline de Cascavel e o "
    "benchmark dos 33 modelos, com métricas equivalentes às originais.",
    "OE3 — Reduzir a duplicação de lógica: cada regra (data de corte, métricas, agregação, semente) "
    "definida em um único lugar.",
    "OE4 — Medir os modelos candidatos ao embarcado (TTM, SparseTSF, TFLite) em hardware real — "
    "Raspberry Pi 5 e ESP32 — a partir do artefato exportado.",
    "OE5 — Documentar e publicar a biblioteca (PyPI ou repositório interno, conforme decisão de "
    "licença) com exemplos baseados em dados sintéticos.",
])

# ---------------------------------------------------------------- 4 arquitetura
H1("4. Arquitetura")
tabela(["Módulo", "Função", "Código existente que será reaproveitado"], [
    ["prossumidor.io", "lê Fronius, medidores, faturas e ANEEL; clima via pvlib (NASA alinhada em "
     "−55 min, CAMS, ERA5)", "merge_5min.py, merge_curitiba.py, build_merge.py, billing.py, "
     "baixa_tarifas_aneel.py, h1_align.py"],
    ["prossumidor.qualidade", "buracos, noite, pontas do dia, vazamento, séries sem sinal, horário "
     "de verão; relatório de qualidade", "01_prepara_dados.py, dq1–dq3, dq_curitiba.py"],
    ["prossumidor.fisica", "irradiância no plano (POA) de céu claro, ajuste de geometria, kWp "
     "estimado, irradiância inversa", "solar.py, a1_geometry.py, build_curitiba2.py, estima_irradiancia.py"],
    ["prossumidor.diagnostico", "sujeira, falha de string, eventos de limpeza, PR corrigido",
     "a2_fault.py, a3_shading.py, changepoint.py, curitiba_analysis2.py"],
    ["prossumidor.previsao", "interface única ajusta/preve e adaptadores para cada família",
     "02_referencias.py, 03_fundacionais.py, 04_redes_treinadas.py"],
    ["prossumidor.protocolo", "janelas do dia seguinte, regimes, métricas, bootstrap, "
     "Diebold–Mariano, relatório", "comum.py, 05_avalia.py"],
    ["prossumidor.embarcado", "exporta (TFLite int8, ONNX, emlearn), recarrega e mede",
     "compara_modelos_embarcado.py"],
    ["prossumidor.economia", "tarifa cheia, créditos, Lei 14.300, exportação para o HOMER",
     "aplica_tarifas.py, monta_planilha_tarifas.py"],
], [4.0, 6.1, 6.3])
H2("4.1 Princípios de projeto")
itens([
    "<b>Instalação mínima:</b> <font face='Consolas'>pip install prossumidor</font> traz só pandas, "
    "numpy, pvlib e LightGBM; cada modelo fundacional é um extra opcional "
    "(<font face='Consolas'>prossumidor[chronos]</font>, <font face='Consolas'>[ttm]</font>…).",
    "<b>Contratos de dados:</b> nenhuma função aceita uma tabela \"crua\"; toda série carrega "
    "unidade, fuso, taxa de amostragem e máscara de validade.",
    "<b>Erros impossíveis por construção:</b> por exemplo, a normalização por janela com "
    "covariáveis — que nos testes fez redes preverem 2.400 kWh/h numa usina de 4 kW — é bloqueada, "
    "não apenas documentada.",
    "<b>Anonimização por padrão:</b> nomes de proprietários nunca entram em nomes de arquivo ou "
    "colunas; os exemplos usam dados sintéticos.",
])
H2("4.2 Como seria o uso")
codigo = """import prossumidor as ps

usina = ps.io.fronius("dados_brutos/usina_x/", kwp=3.96, lat=-24.8, lon=-53.6,
                      inclinacao=13, azimute=155)
clima = ps.io.clima(usina, fonte="cams")          # ou "nasa", "era5"
serie = ps.qualidade.limpa(usina, clima)          # com relatorio de qualidade

tarefa = ps.protocolo.DiaSeguinte(serie, teste_de="2025-08-01",
                                  regimes=["historico", "clima"])
resultado = tarefa.compara([
    ps.previsao.PersistenciaCeuClaro(),
    ps.previsao.LinearFisico(),
    ps.previsao.LightGBM(),
    ps.previsao.fundacional("ttm"),               # 3 M de parametros, sem treino
])                                                # + mediana de todos, sempre incluida
resultado.tabela()                                # skill com IC 95%, nMAE, vies, R2
ps.embarcado.exporta(resultado.melhor(max_kb=64), formato="tflite-int8")
ps.diagnostico.sujeira(serie)                     # eventos de limpeza, perda acumulada"""
story.append(Preformatted(codigo, S["codigo"]))

# ---------------------------------------------------------------- 5 decisões dos testes
H1("5. Decisões já fundamentadas pelos testes")
P("Os testes de 30/09–02/10/2026 transformam-se em escolhas concretas de projeto, o que reduz o "
  "risco de a biblioteca ser desenhada por suposição:")
tabela(["Decisão", "Evidência"], [
    ["Conjunto padrão de comparação: persistência de céu claro, linear físico, LightGBM, TTM, Chronos-2",
     "cobre o teto com clima (≈ +0,48 a +0,50), o fundacional mais consistente (TTM, ranking médio 3,3) "
     "e o híbrido físico (+0,42 com uma variável), em segundos e sem GPU"],
    ["Saída padrão = mediana dos modelos, com correção de viés no consumo", "1º lugar nas usinas (com e "
     "sem clima), 2º na geração FV das residências e 5º no consumo, a 0,012 do 1º (empate "
     "estatístico) — mas herdando o viés de −20% dos fundacionais; escolher o vencedor pelo próprio "
     "teste seria vazamento"],
    ["Regime explícito (só histórico × clima conhecido)", "o vão entre regimes (~0,40) é dez vezes a "
     "diferença entre algoritmos (~0,03); misturar os dois numa tabela engana"],
    ["Viés reportado junto com o erro", "os fundacionais subestimam o consumo em ~20%, escondido por um "
     "RMSE bom"],
    ["Detecção de série sem sinal", "10 das 20 residências não têm FV; sem a checagem, o erro "
     "normalizado dobra"],
    ["Embarcado começa por TTM e SparseTSF", "SparseTSF (32 parâmetros) empata com os melhores no "
     "consumo; TTM é o mais estável sem treino"],
    ["Cada fundacional em ambiente isolado", "três quebras de dependência (torch, transformers, "
     "huggingface_hub) num único dia de testes"],
], [6.2, 10.2])

# ---------------------------------------------------------------- 6 etapas
H1("6. Etapas de desenvolvimento")
P("Cada etapa tem uma entrega verificável e um critério objetivo de conclusão. As horas supõem "
  "uma pessoa; a estimativa da proposta técnica original (≈ 11 semanas em tempo integral para as "
  "versões 0.1 a 0.3) corresponde às etapas E1 a E6.")
etapas = [
    ["E0", "Alinhamento e autorização", "decisões da seção 11 registradas por escrito; orientador "
     "acadêmico e coorientador do Lactec definidos", "autorização assinada", "—"],
    ["E1", "Fundação", "estrutura do pacote, contratos de dados, gerador de dados sintéticos, "
     "integração contínua (testes automáticos a cada alteração)", "pacote instala e passa nos testes "
     "em ambiente limpo", "40 h"],
    ["E2", "Versão 0.1 — núcleo", "módulos io, qualidade, fisica e protocolo; adaptadores de "
     "referências, linear físico, LightGBM, Chronos-2 e TTM", "cobertura de testes ≥ 80% nos "
     "módulos do núcleo", "120 h"],
    ["E3", "Validação 1 — reprodução", "refazer com a biblioteca o pipeline de Cascavel e o benchmark "
     "dos testes (usinas e residências)", "métricas iguais às de metricas.csv (diferença ≤ 0,005 de "
     "skill); saídas do pipeline idênticas", "60 h"],
    ["E4", "Versão 0.2 — diagnóstico e embarcado", "módulos diagnostico e embarcado; adaptadores "
     "NeuralForecast e demais fundacionais", "diagnóstico de Cascavel e Curitiba reproduzido; "
     "modelos exportados e recarregados", "120 h"],
    ["E5", "Validação 2 — hardware real", "medir tamanho, acurácia, latência e energia de TTM, "
     "SparseTSF e TFLite no Raspberry Pi 5 e no ESP32", "tabela comparativa medida no hardware "
     "(insumo do Marco 4)", "50 h"],
    ["E6", "Versão 0.3 — economia e publicação", "módulo economia (ANEEL, Lei 14.300, HOMER), "
     "documentação com tutoriais, publicação conforme a licença decidida", "documentação completa; "
     "versão publicada", "80 h"],
    ["E7", "Escrita do TCC", "monografia com fundamentação, arquitetura, validação e discussão",
     "texto aprovado pelo orientador", "80 h"],
    ["E8", "Artigo de software (opcional)", "submissão ao Journal of Open Source Software ou "
     "SoftwareX", "artigo submetido", "30 h"],
]
tabela(["", "Etapa", "Conteúdo", "Critério de conclusão", "Esforço"], etapas, [0.8, 2.9, 6.2, 4.7, 1.8])
P("<b>Total estimado:</b> ≈ 580 horas (≈ 470 h de desenvolvimento e validação + ≈ 110 h de "
  "escrita).")

# ---------------------------------------------------------------- 7 cronograma
story.append(PageBreak())
H1("7. Cronograma")
P("Proposta com dedicação de ~15 horas semanais, em cerca de 9 meses a partir da autorização (M1). "
  "Se parte do trabalho for enquadrada no projeto (Marcos 3 e 4), o prazo encurta.")
meses = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9"]
plano = [
    ("E0 Alinhamento", [1]), ("E1 Fundação", [1, 2]), ("E2 Versão 0.1", [2, 3, 4]),
    ("E3 Reprodução", [4, 5]), ("E4 Versão 0.2", [5, 6]), ("E5 Hardware real", [6, 7]),
    ("E6 Versão 0.3", [7, 8]), ("E7 Escrita do TCC", [6, 7, 8, 9]), ("E8 Artigo de software", [9]),
]
dados = [[Paragraph("Etapa", S["celb"])] + [Paragraph(m, S["celb"]) for m in meses]]
for nome, ms in plano:
    dados.append([Paragraph(nome, S["cel"])] + ["" for _ in meses])
g = Table(dados, colWidths=[4.6 * cm] + [1.31 * cm] * 9)
est = [("BACKGROUND", (0, 0), (-1, 0), ACENTO), ("GRID", (0, 0), (-1, -1), 0.4, LINHA),
       ("ALIGN", (1, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
       ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]
for i, (_, ms) in enumerate(plano, start=1):
    for m in ms:
        est.append(("BACKGROUND", (m, i), (m, i), colors.HexColor("#3E8A9C")))
g.setStyle(TableStyle(est))
story.append(KeepTogether([g, Spacer(1, 6)]))
P("Marcos intermediários para acompanhamento da gestão: <b>fim de M4</b> — versão 0.1 e reprodução "
  "do benchmark; <b>fim de M7</b> — medições em hardware real; <b>fim de M9</b> — versão 0.3 e TCC "
  "concluído.", "nota")

# ---------------------------------------------------------------- 8 uso acadêmico
H1("8. Uso acadêmico")
H2("8.1 TCC")
tabela(["Item", "Proposta"], [
    ["Título provisório", "prossumidor: uma biblioteca reprodutível para previsão do dia seguinte e "
     "diagnóstico de prossumidores fotovoltaicos, do medidor ao embarcado"],
    ["Questão central", "Um protocolo único e empacotado consegue reproduzir os resultados de um "
     "projeto real com menos código duplicado e permitir comparar, em condições iguais, modelos "
     "clássicos, redes neurais e modelos fundacionais em dados brasileiros — inclusive no hardware "
     "embarcado?"],
    ["Método", "engenharia de software orientada a testes sobre o código existente; validação por "
     "reprodução (E3) e por medição em hardware (E5)"],
    ["Critérios de avaliação", "fidelidade da reprodução (métricas e saídas), redução da duplicação "
     "(ex.: data de corte 16 → 1 lugar; métricas 19 → 1), cobertura de testes, esforço para analisar "
     "uma usina nova, latência e memória no embarcado"],
    ["Dados", "resultados agregados e anonimizados; nenhum dado bruto de terceiros no texto ou no "
     "repositório público; exemplos com dados sintéticos"],
    ["Entregas", "biblioteca versionada, documentação, monografia e, opcionalmente, artigo de software"],
], [3.6, 12.8])
H2("8.2 Continuidade em mestrado")
P("No mestrado, a biblioteca deixa de ser o resultado e passa a ser o instrumento. As linhas de "
  "pesquisa abaixo já têm evidência preliminar no projeto:")
tabela(["Linha", "Questão", "Ponto de partida"], [
    ["L1 — Clima real × oráculo", "Uma previsão do tempo disponível às 00:00 (CAMS, Open-Meteo, ERA5) "
     "fecha quanto do vão de ~0,40 entre os regimes?", "experimento de maior valor apontado nos testes"],
    ["L2 — Diagnóstico sem sensor", "O diagnóstico só com inversor generaliza para mais usinas e "
     "fabricantes?", "Artigo B (Cascavel e Curitiba)"],
    ["L3 — Modelos compactos na borda", "Modelos compactos (o fundacional TTM e o SparseTSF, de 32 "
     "parâmetros) mantêm a acurácia em microcontroladores? Com que energia e latência?", "etapa E5; Marco 4 do projeto"],
    ["L4 — Usinas sem metadados", "É possível estimar geometria e potência de uma usina só pela "
     "série de geração?", "pendência de Curitiba, a mais estratégica da análise de rede"],
], [3.6, 8.0, 4.8])
P("Uma dissertação coerente reuniria a biblioteca, os artigos A e B já planejados e uma das linhas "
  "acima.")

# ---------------------------------------------------------------- 9 benefícios
H1("9. Benefícios para o projeto e para o Lactec")
itens([
    "<b>Marco 3:</b> a biblioteca pode ser o registro de software previsto, com escopo, código e "
    "documentação já organizados.",
    "<b>Marco 4:</b> as medições em hardware real (E5) alimentam diretamente a avaliação dos modelos "
    "na plataforma embarcada.",
    "<b>Artigos:</b> o protocolo congelado é pré-requisito dos artigos A e B; a biblioteca também "
    "pode render um artigo de software.",
    "<b>Reprodutibilidade:</b> elimina a classe de erros que já ocorreu (relatório com kWp antigo "
    "por meses, fatura que não entrou na análise).",
    "<b>Transferência de tecnologia:</b> um pacote documentado é mais fácil de apresentar e "
    "transferir aos associados do Future Grid interessados no tema.",
    "<b>Formação:</b> TCC e eventual mestrado vinculados ao projeto, com coorientação do Lactec.",
])

# ---------------------------------------------------------------- 10 PI e dados
H1("10. Propriedade intelectual e dados")
P("O código foi desenvolvido no âmbito do projeto, com dados e recursos do projeto. Por isso, esta "
  "proposta parte do princípio de que a titularidade segue os termos do projeto e a política do "
  "Lactec, e pede que autoria e uso acadêmico sejam definidos por escrito antes do início.")
tabela(["Tema", "Proposta"], [
    ["Titularidade", "conforme os termos do projeto GRD-ACS-2026-1-21-1 e a política de inovação do "
     "Lactec"],
    ["Autoria", "o autor desta proposta registrado como autor do software e dos artigos derivados"],
    ["Uso acadêmico", "autorização escrita para usar código, métodos e resultados agregados no TCC "
     "e numa eventual dissertação"],
    ["Licença (a decidir)", "(a) código aberto (MIT, BSD-3 ou Apache-2.0): permite artigo de software "
     "e citações, e exige licença aprovada pela OSI; (b) uso interno com registro no INPI. É possível "
     "combinar: registro no INPI e publicação aberta"],
    ["Dados das usinas", "não distribuídos; apenas resultados agregados e anonimizados"],
    ["Dados das residências", "origem e licença a confirmar antes de qualquer citação"],
    ["Exemplos", "gerados sinteticamente pela própria biblioteca"],
], [3.6, 12.8])
P("Esta seção descreve uma proposta de arranjo e não substitui a análise do núcleo de inovação "
  "tecnológica ou do jurídico do Lactec.", "nota")

# ---------------------------------------------------------------- riscos
H1("11. Decisões pedidas à gestão")
tabela_inteira(["#", "Decisão"], [
    ["1", "Autorizar o uso acadêmico (TCC e eventual mestrado) do código, dos métodos e dos "
     "resultados agregados."],
    ["2", "Definir titularidade e autoria, e se a biblioteca será o registro de software do Marco 3."],
    ["3", "Escolher a licença: código aberto, uso interno ou ambos."],
    ["4", "Definir quanto do trabalho pode ser feito dentro das horas do projeto."],
    ["5", "Indicar um coorientador do Lactec."],
    ["6", "Autorizar o uso do Raspberry Pi 5 e de um ESP32 do projeto para as medições da etapa E5."],
], [0.9, 15.5])

H1("12. Riscos e mitigação")
tabela(["Risco", "Impacto", "Mitigação"], [
    ["Mudanças de API dos modelos fundacionais", "adaptadores quebram",
     "poucos modelos no padrão; versões travadas; testes de contrato por adaptador"],
    ["Escopo cresce além do TCC", "atraso", "versão 0.1 já é suficiente para o TCC; 0.2 e 0.3 "
     "podem migrar para o mestrado"],
    ["Autorização demora ou é parcial", "início adiado", "E0 antes de tudo; versão restrita "
     "(uso interno, dados sintéticos) como alternativa"],
    ["Dados de terceiros", "impede publicação", "anonimização e dados sintéticos desde a E1"],
    ["Sobreposição com o OpenSTEF no consumo", "esforço duplicado", "foco em FV e diagnóstico; "
     "exportar para o OpenSTEF em vez de competir"],
    ["Conciliação com as entregas do projeto", "conflito de prioridade", "etapas E3 e E5 coincidem "
     "com os Marcos 3 e 4; o restante fora do projeto, se necessário"],
], [4.6, 3.0, 8.8])

# ---------------------------------------------------------------- anexo
story.append(PageBreak())
H1("Anexo A — Resultados dos testes de previsão")
P("Previsão das 24 horas do dia seguinte, emitida às 00:00, em CPU. <i>Skill</i> = 1 − RMSE / RMSE "
  "da referência (persistência de céu claro nas usinas; \"igual a ontem\" nas residências). Detalhes "
  "em <font face='Consolas'>testes_modelos/LEIA-ME.md</font>.")
tabela(["Caso", "Melhor resultado", "Observação"], [
    ["Usinas, com o clima do dia (teto)", "mediana de todos +0,51; TFT +0,50",
     "8 modelos empatam entre +0,47 e +0,51; linear com uma variável física: +0,42"],
    ["Usinas, só histórico", "mediana de todos +0,11; ResNet-1D +0,10",
     "LSTM e GRU perdem da referência (−0,14 e −0,13)"],
    ["Geração FV de 10 residências", "KAN +0,17", "LightGBM só +0,06, com viés de +40% no inverno"],
    ["Consumo de 20 residências", "LightGBM +0,20", "TTM, SparseTSF e Chronos-Bolt +0,19 (empate); "
     "mediana +0,19 (5º); fundacionais com viés de ~−20%"],
], [4.6, 5.0, 6.8])
H2("Arquivos de referência")
tabela(["Arquivo", "Conteúdo"], [
    ["biblioteca_tcc/PROPOSTA_BIBLIOTECA.md", "proposta técnica da biblioteca (30/09/2026)"],
    ["analise_rede/REDE_PROJETO.md", "análise de rede do projeto"],
    ["testes_modelos/LEIA-ME.md", "protocolo e resultados dos 33 modelos"],
    ["ia_solar/ESTADO_DO_PROJETO.md", "estado das análises das usinas"],
    ["ia_solar/PLANO_ARTIGO.md", "plano dos artigos A e B"],
], [6.4, 10.0])


# ---------------------------------------------------------------- layout
def capa_fundo(c, doc):
    c.saveState()
    c.setFillColor(ACENTO)
    c.rect(0, A4[1] - 1.1 * cm, A4[0], 1.1 * cm, fill=1, stroke=0)
    c.setFillColor(CINZA)
    c.setFont("Arial", 8)
    c.drawString(2.3 * cm, 1.5 * cm, "Projeto Edge AI — CC EMBRAPII Lactec · documento para discussão interna")
    c.restoreState()


def pagina(c, doc):
    c.saveState()
    c.setStrokeColor(LINHA)
    c.line(2.3 * cm, A4[1] - 1.6 * cm, A4[0] - 2.3 * cm, A4[1] - 1.6 * cm)
    c.setFont("Arial", 8)
    c.setFillColor(CINZA)
    c.drawString(2.3 * cm, A4[1] - 1.4 * cm, "Proposta acadêmica — biblioteca prossumidor")
    c.drawRightString(A4[0] - 2.3 * cm, A4[1] - 1.4 * cm, "Rascunho · 05/10/2026")
    c.drawRightString(A4[0] - 2.3 * cm, 1.3 * cm, f"{doc.page}")
    c.restoreState()


doc = BaseDocTemplate(SAIDA, pagesize=A4, leftMargin=2.3 * cm, rightMargin=2.3 * cm,
                      topMargin=2.2 * cm, bottomMargin=2.0 * cm,
                      title="Proposta acadêmica — biblioteca prossumidor",
                      author="João Jachenski Junior",
                      subject="Proposta de TCC no âmbito do projeto GRD-ACS-2026-1-21-1")
fr = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")
doc.addPageTemplates([PageTemplate("capa", [fr], onPage=capa_fundo),
                      PageTemplate("normal", [fr], onPage=pagina)])
doc.build(story)
print("ok", SAIDA)
