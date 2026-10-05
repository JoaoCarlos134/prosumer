# -*- coding: utf-8 -*-
"""Camada de conceitos (curada a partir dos documentos do projeto e dos testes).

Tudo aqui e INFERIDO: cada no cita o documento de onde saiu e cada aresta aponta para os scripts,
dados e documentos que o sustentam. Caminhos sao relativos a Projeto_IA/.
Saida: analise_rede/conceitos.json
"""
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
A = "ia_solar/analise/"; B = "ia_solar/base_modelagem/"; T = "testes_modelos/"; E = "ia_solar/ESTADO_DO_PROJETO.md"
P = "ia_solar/PLANO_ARTIGO.md"; L = "ia_solar/LEIA-ME.md"

# ---------------- entregas (artigos, relatorios, projeto) ----------------
ENTREGAS = {
 "Projeto PD&I Edge AI (GRD-ACS-2026-1-21-1)": dict(tipo="projeto", doc="projeto/Síntese do Projeto de PD&I - IA_Borda_rev02.pdf"),
 "Revisao Edge AI em smart buildings": dict(tipo="artigo_rascunho", doc="revisao_edge_ai/smart_buildings.docx"),
 "Artigo OCR hidrometro (ICIT 2027)": dict(tipo="artigo_rascunho", doc="ocr_paper/paper/main.tex"),
 "Artigo SOLO/UPEC 2026 (sujeira FV, publicado)": dict(tipo="artigo_publicado", doc="outros/Paper_Solo_UPEC_2026.pdf"),
 "Artigo A: entrada, nao algoritmo, limita a estimativa FV": dict(tipo="artigo_planejado", doc=P),
 "Artigo B: diagnostico de falhas so com o inversor": dict(tipo="artigo_planejado", doc=P),
 "Testes de modelos de previsao (dia seguinte)": dict(tipo="estudo", doc=T + "LEIA-ME.md"),
 "Levantamento de 127 modelos": dict(tipo="estudo", doc="revisao_edge_ai/Modelos_previsao_geracao_consumo.xlsx"),
}
PARTE_DE = [(e, "Projeto PD&I Edge AI (GRD-ACS-2026-1-21-1)") for e in ENTREGAS if not e.startswith("Projeto")]

# ---------------- fontes de dados externas ----------------
FONTES = {
 "Inversor Fronius - Cascavel (Usina Cascavel, 3,96 kWp)": [("gera", "ia_solar/dados_brutos/cascavel/serie_5min")],
 "Inversor Fronius - Curitiba (Usina Curitiba, ~9,6 kWp)": [("gera", "ia_solar/dados_brutos/curitiba/serie_5min")],
 "Fatura Copel - Cascavel": [("gera", "ia_solar/dados_brutos/cascavel/Fatura de energia.xlsx")],
 "NASA POWER (reanalise)": [("baixado_por", A + "cascavel/scripts/fetch_power2.py"), ("baixado_por", A + "cascavel/scripts/fetch_hourly.py"),
                             ("baixado_por", A + "curitiba/scripts/fetch_curitiba.py")],
 "ANEEL dados abertos (tarifas)": [("baixado_por", A + "tarifas/scripts/baixa_tarifas_aneel.py")],
 "20 casas com medicao de 1 min (2020, hemisferio norte)": [("gera", "dados_casas"), ("gera", "consumption_all_houses.csv")],
 "WaterMeters (Toloka, 1.244 imagens)": [],
 "Raspberry Pi 5 + camera IMX500 (codigo fora do projeto)": [],
}

# ---------------- achados ----------------
ACHADOS = {
 "Sujeira progressiva em Cascavel, nao degradacao (13 graus de inclinacao)": dict(
    evid=[A + "cascavel/scripts/a2_fault.py", A + "cascavel/scripts/a3_shading.py", A + "cascavel/scripts/changepoint.py",
          A + "cascavel/scripts/a5_seasonal.py"], docs=[E, L], sustenta=["Artigo B: diagnostico de falhas so com o inversor",
          "Artigo SOLO/UPEC 2026 (sujeira FV, publicado)"]),
 "Falha na string 1 e reconfiguracao em Curitiba (MPPT como controle)": dict(
    evid=[A + "curitiba/scripts/curitiba_analysis2.py", A + "curitiba/scripts/viz_curitiba.py"], docs=[E, L],
    sustenta=["Artigo B: diagnostico de falhas so com o inversor"]),
 "NASA POWER horaria alinha em -55 min": dict(evid=[A + "cascavel/scripts/h1_align.py"], docs=[E, L],
    sustenta=["Artigo A: entrada, nao algoritmo, limita a estimativa FV"]),
 "NASA diaria le 3,2% abaixo em dias claros": dict(evid=[A + "cascavel/scripts/estimate.py"], docs=[E, L]),
 "Azimute nao e recuperavel de totais diarios": dict(evid=[A + "cascavel/scripts/a1_geometry.py", A + "cascavel/scripts/viz_geom.py"],
    docs=[E, L]),
 "Colunas que reescrevem o alvo (vazamento, R2 0,9999)": dict(evid=[A + "cascavel/scripts/dq2_outliers.py", A + "curitiba/scripts/dq_curitiba.py",
    B + "referencia/build_base_modelagem.py"], docs=[L]),
 "poa_estimada sozinha explica 99,6% do R2": dict(evid=[B + "referencia/ablacao_preditores.py", B + "embarcado/ablacao_preditores.csv"],
    docs=[E], sustenta=["Artigo A: entrada, nao algoritmo, limita a estimativa FV"]),
 "Downscaling por inversao da potencia nao melhora o modelo": dict(evid=[A + "irradiancia_inversa/estima_irradiancia.py"],
    docs=[E, A + "irradiancia_inversa/LEIA-ME.md"], sustenta=["Artigo A: entrada, nao algoritmo, limita a estimativa FV"]),
 "Um sensor de irradiancia fecha 99% do vao": dict(evid=[B + "referencia/sensor_irradiancia.py", B + "embarcado/sensor_irradiancia.csv"],
    docs=[E], sustenta=["Artigo A: entrada, nao algoritmo, limita a estimativa FV"]),
 "TFLite de 3,4 KB com R2 0,81": dict(evid=[B + "referencia/compara_modelos_embarcado.py", B + "embarcado/comparacao_embarcado.csv"],
    docs=[E], sustenta=["Artigo A: entrada, nao algoritmo, limita a estimativa FV", "Projeto PD&I Edge AI (GRD-ACS-2026-1-21-1)"]),
 "HistGradientBoosting melhor de 13 algoritmos": dict(evid=[B + "referencia/comparar_modelos.py", B + "ambas_usinas/comparacao_modelos_completa.csv"],
    docs=[E, L]),
 "Tarifa fecha contra a fatura de 2018 (residuo = COSIP)": dict(evid=[A + "tarifas/scripts/aplica_tarifas.py"], docs=[A + "tarifas/dados/LEIA-ME.md"]),
 "Cascavel gera 3x o consumo e perde creditos (2.750 kWh em 2025)": dict(evid=[A + "cascavel/scripts/billing.py", A + "cascavel/dados/billing_annual.csv"],
    docs=[E]),
 "10 das 20 casas nao tem FV": dict(evid=["dados/merged/data_quality_summary.csv", T + "scripts/01_prepara_dados.py"], docs=[]),
 "Clima do dia domina: +50% com clima perfeito, +11% so com historico": dict(evid=[T + "scripts/05_avalia.py", T + "resultados/metricas.csv"],
    docs=[T + "LEIA-ME.md"], sustenta=["Artigo A: entrada, nao algoritmo, limita a estimativa FV", "Testes de modelos de previsao (dia seguinte)"]),
 "Fundacionais zero-shot empatam com LightGBM treinado": dict(evid=[T + "scripts/03_fundacionais.py", T + "resultados/metricas.csv"],
    docs=[T + "LEIA-ME.md"], sustenta=["Testes de modelos de previsao (dia seguinte)"]),
 "TTM (3M parametros) e o mais consistente, 40-70x menor que os grandes": dict(evid=[T + "scripts/03_fundacionais.py"], docs=[T + "LEIA-ME.md"],
    sustenta=["Testes de modelos de previsao (dia seguinte)", "Projeto PD&I Edge AI (GRD-ACS-2026-1-21-1)"]),
 "Mediana de todos os modelos e o resultado mais robusto": dict(evid=[T + "scripts/07_ensemble.py", T + "resultados/metricas.csv"],
    docs=[T + "LEIA-ME.md"], sustenta=["Testes de modelos de previsao (dia seguinte)"]),
 "SparseTSF com 32 parametros empata com os melhores no consumo": dict(evid=[T + "scripts/04_redes_treinadas.py"], docs=[T + "LEIA-ME.md"],
    sustenta=["Testes de modelos de previsao (dia seguinte)", "Projeto PD&I Edge AI (GRD-ACS-2026-1-21-1)"]),
 "Fundacionais subestimam o consumo em ~20% (preveem a mediana)": dict(evid=[T + "scripts/05_avalia.py"], docs=[T + "LEIA-ME.md"],
    sustenta=["Testes de modelos de previsao (dia seguinte)"]),
 "Normalizacao por janela explode com clima futuro (corrigido)": dict(evid=[T + "scripts/04_redes_treinadas.py",
    T + "resultados/metricas_antes_da_correcao_B.csv"], docs=[T + "LEIA-ME.md"], sustenta=["Testes de modelos de previsao (dia seguinte)"]),
 "OCR: 93% do PP-OCR nao e medicao propria": dict(evid=[], docs=["ocr_paper/reports/report_review.md"], sustenta=["Artigo OCR hidrometro (ICIT 2027)"]),
 "OCR: pipeline C validado so no dominio do simulador": dict(evid=[], docs=["ocr_paper/reports/report_review.md"], sustenta=["Artigo OCR hidrometro (ICIT 2027)"]),
}
# conexoes entre achados (um explica o outro)
EXPLICA = [
 ("poa_estimada sozinha explica 99,6% do R2", "Downscaling por inversao da potencia nao melhora o modelo"),
 ("poa_estimada sozinha explica 99,6% do R2", "Um sensor de irradiancia fecha 99% do vao"),
 ("poa_estimada sozinha explica 99,6% do R2", "Clima do dia domina: +50% com clima perfeito, +11% so com historico"),
 ("NASA POWER horaria alinha em -55 min", "poa_estimada sozinha explica 99,6% do R2"),
 ("Sujeira progressiva em Cascavel, nao degradacao (13 graus de inclinacao)", "HistGradientBoosting melhor de 13 algoritmos"),
 ("TFLite de 3,4 KB com R2 0,81", "TTM (3M parametros) e o mais consistente, 40-70x menor que os grandes"),
 ("TFLite de 3,4 KB com R2 0,81", "SparseTSF com 32 parametros empata com os melhores no consumo"),
 ("Clima do dia domina: +50% com clima perfeito, +11% so com historico", "Mediana de todos os modelos e o resultado mais robusto"),
]

# ---------------- pendencias ----------------
PENDENCIAS = {
 "Curitiba: potencia e geometria estimadas (telhado de 2 planos)": dict(docs=[E, L, P], bloqueia=["Artigo A: entrada, nao algoritmo, limita a estimativa FV",
     "Artigo B: diagnostico de falhas so com o inversor"], evid=[A + "curitiba/scripts/build_curitiba2.py"]),
 "Protocolo canonico congelado (protocolo_canonico.py nunca criado)": dict(docs=[E, P], bloqueia=["Artigo A: entrada, nao algoritmo, limita a estimativa FV"],
     evid=[T + "scripts/comum.py"]),
 "Irradiancia medida em solo (INMET) e fonte de satelite": dict(docs=[P], bloqueia=["Artigo A: entrada, nao algoritmo, limita a estimativa FV"], evid=[]),
 "Consentimento e anonimizacao (nomes dos donos nos arquivos)": dict(docs=[P], bloqueia=["Artigo A: entrada, nao algoritmo, limita a estimativa FV",
     "Artigo B: diagnostico de falhas so com o inversor"], evid=["ia_solar/dados_brutos/cascavel/USINA_CASCAVEL_serie_temporal_2019-2026.xlsx"]),
 "Codigo e dados do OCR fora do projeto": dict(docs=["ocr_paper/reports/Relatorio_Validacao_Campo.docx", "ocr_paper/paper/main.tex"],
     bloqueia=["Artigo OCR hidrometro (ICIT 2027)"], evid=[]),
 "Faturas recentes (COSIP, PIS/COFINS efetivo; Curitiba sem fatura)": dict(docs=[E], bloqueia=[], evid=[A + "tarifas/scripts/aplica_tarifas.py"]),
 "Latencia embarcada medida so em x86": dict(docs=[P], bloqueia=["Artigo A: entrada, nao algoritmo, limita a estimativa FV"],
     evid=[B + "referencia/compara_modelos_embarcado.py"]),
}

# ---------------- ligacoes entre levantamento e lacunas (candidatos a resolver pendencias) ----------------
RESOLVE = [
 ("PARA-PV", "Curitiba: potencia e geometria estimadas (telhado de 2 planos)"),
 ("TSFM com historico sintetico fisico (usina nova)", "Curitiba: potencia e geometria estimadas (telhado de 2 planos)"),
 ("SolarSeer", "Irradiancia medida em solo (INMET) e fonte de satelite"),
 ("STARGPT", "Irradiancia medida em solo (INMET) e fonte de satelite"),
 ("Previsao FV nacional por satelite", "Irradiancia medida em solo (INMET) e fonte de satelite"),
 ("Tiny Time Mixers (TTM)", "Latencia embarcada medida so em x86"),
 ("SparseTSF", "Latencia embarcada medida so em x86"),
 ("Revisiting the Generic Transformer", "Clima do dia domina: +50% com clima perfeito, +11% so com historico"),
 ("Chronos-2", "Clima do dia domina: +50% com clima perfeito, +11% so com historico"),
 ("TimesFM", "Clima do dia domina: +50% com clima perfeito, +11% so com historico"),
]

json.dump(dict(entregas=ENTREGAS, parte_de=PARTE_DE, fontes=FONTES, achados=ACHADOS, explica=EXPLICA, pendencias=PENDENCIAS,
               resolve=RESOLVE), open(RAIZ / "analise_rede" / "conceitos.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
faltam = sorted({p for a in list(ACHADOS.values()) + list(PENDENCIAS.values()) for p in a["evid"] + a["docs"]
                 if not (RAIZ / p).exists()})
print("%d entregas, %d fontes, %d achados, %d pendencias, %d ligacoes levantamento->lacuna"
      % (len(ENTREGAS), len(FONTES), len(ACHADOS), len(PENDENCIAS), len(RESOLVE)))
print("referencias a caminhos que ainda nao existem:", faltam)
