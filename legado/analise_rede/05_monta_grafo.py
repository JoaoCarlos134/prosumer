# -*- coding: utf-8 -*-
"""Junta as cinco camadas num unico grafo no formato do Graphify (graph.json).

  codigo      Graphify (AST): arquivos, funcoes, chamadas, imports, docstrings      EXTRACTED
  linhagem    01_linhagem.py: script le / escreve arquivo                           EXTRACTED
  documentos  02_documentos.py: documento cita arquivo / cita o que nao existe      EXTRACTED
  literatura  03_literatura.py: documento cita artigo; artigo propoe modelo         EXTRACTED
  conceitos   04_conceitos.py: achados, entregas, fontes, pendencias; resultados    INFERRED

Saida: analise_rede/grafo_projeto/graph.json
"""
import json, re, hashlib
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
AR = RAIZ / "analise_rede"
OUT = AR / "grafo_projeto"; OUT.mkdir(exist_ok=True)
g = json.load(open(AR / "graphify-out" / "graph.json", encoding="utf-8"))
lin = json.load(open(AR / "linhagem.json", encoding="utf-8"))
docs = json.load(open(AR / "documentos.json", encoding="utf-8"))
lit = json.load(open(AR / "literatura.json", encoding="utf-8"))
con = json.load(open(AR / "conceitos.json", encoding="utf-8"))

nos, arestas = {}, []


def no(i, label, tipo, fonte="", camada="", **kw):
    if i not in nos:
        nos[i] = dict(id=i, label=label, file_type=tipo, source_file=fonte, camada=camada, **kw)
    return i


def aresta(a, b, rel, conf="EXTRACTED", fonte="", peso=1.0, **kw):
    arestas.append(dict(source=a, target=b, relation=rel, confidence=conf, source_file=fonte, weight=peso, **kw))


def frente(p):
    p = p or ""
    for k, v in [("ia_solar/analise/tarifas", "tarifas"), ("ia_solar/analise", "analise_usinas"), ("ia_solar/base_modelagem", "base_modelagem"),
                 ("ia_solar/dados_brutos", "dados_brutos_usinas"), ("ia_solar", "ia_solar"), ("testes_modelos", "testes_modelos"),
                 ("ocr_paper", "ocr"), ("revisao_edge_ai", "revisao_edge_ai"), ("dados_casas", "dados_casas"), ("consumption", "dados_casas"),
                 ("analise_rede", "analise_rede")]:
        if p.startswith(k):
            return v
    return "raiz"


# ---- 1. codigo (Graphify) ----
arquivo_para_no = {}
for n in g["nodes"]:
    no(n["id"], n["label"], n["file_type"], n.get("source_file", ""), "codigo", frente=frente(n.get("source_file")))
    sf = n.get("source_file", "")
    if sf and n["label"] == Path(sf).name:
        arquivo_para_no[sf] = n["id"]
for e in g["edges"]:
    if e["source"] in nos and e["target"] in nos:
        aresta(e["source"], e["target"], e["relation"], e.get("confidence", "EXTRACTED"), e.get("source_file", ""), e.get("weight", 1.0))
    elif e["source"] in nos:                        # alvo externo (biblioteca importada)
        alvo = "lib:" + e["target"]
        no(alvo, e["target"], "biblioteca", "", "codigo", frente="externo")
        aresta(e["source"], alvo, e["relation"], "EXTRACTED", e.get("source_file", ""))


def no_script(r):
    if r in arquivo_para_no:
        return arquivo_para_no[r]
    return no("script:" + r, Path(r).name, "code", r, "codigo", frente=frente(r))


# ---- 2. linhagem ----
def no_dado(r):
    if r.startswith("AUSENTE:"):
        return no("ausente:" + r[8:], Path(r[8:]).name + " (nao existe)", "ausente", r[8:], "linhagem", frente=frente(r[8:]))
    p = RAIZ / r
    tipo = "pasta" if p.is_dir() else ("figura" if p.suffix == ".png" else "dado")
    return no("dado:" + r, p.name, tipo, r, "linhagem", frente=frente(r),
              tamanho_kb=round(p.stat().st_size / 1024) if p.is_file() else None)


for r in lin["arquivos"]:
    if not r.endswith((".pdf", ".docx")):
        no_dado(r)
for a in lin["arestas"]:
    aresta(no_script(a["script"]), no_dado(a["arquivo"]), a["relacao"], "EXTRACTED", a["script"])

# scripts com conteudo identico (copias)
hashes = {}
for r in {a["script"] for a in lin["arestas"]} | set(arquivo_para_no):
    if r.endswith(".py") and (RAIZ / r).exists():
        hashes.setdefault(hashlib.md5((RAIZ / r).read_bytes()).hexdigest(), []).append(r)
for grupo in hashes.values():
    for x in grupo[1:]:
        aresta(no_script(x), no_script(grupo[0]), "copia_identica", "EXTRACTED", x)

# ---- 3. documentos ----
def no_doc(r):
    return no("doc:" + r, Path(r).name, "document", r, "documentos", frente=frente(r))


for d in docs:
    dn = no_doc(d["documento"])
    for c in d["cita"]:
        alvo = c["alvo"]
        if alvo.endswith(".py"):
            t = no_script(alvo)
        elif alvo.endswith((".md", ".tex", ".docx", ".pdf")):
            t = no_doc(alvo)
        else:
            t = no_dado(alvo)
        if t != dn:
            aresta(dn, t, "documenta", "EXTRACTED", d["documento"])
    if not d["documento"].startswith("outros/guias/"):
        for o in d["obsoletas"]:
            aresta(dn, no("ausente:" + o, o + " (nao existe)", "ausente", "", "documentos", frente="ausente"), "cita_inexistente",
                   "EXTRACTED", d["documento"])

# ---- 4. literatura ----
DONO = {"revisao_edge_ai": "revisao_edge_ai/smart_buildings.docx", "previsao_consumo_embarcado": "revisao_edge_ai/Referencias_previsao_consumo_embarcado.xlsx",
        "artigo_ocr": "ocr_paper/paper/main.tex", "levantamento_modelos": "revisao_edge_ai/Modelos_previsao_geracao_consumo.xlsx"}
for k, v in lit.items():
    rn = no("ref:" + k, v["titulo"][:70], "paper", v.get("doi") or "", "literatura", frente="literatura", ano=v.get("ano"),
            colecoes="+".join(v["colecoes"]))
    for c in v["colecoes"]:
        aresta(no_doc(DONO[c]), rn, "cita", "EXTRACTED", DONO[c])
    ex = v.get("extra", {})
    if ex.get("modelo"):
        mn = no("modelo:" + ex["modelo"], ex["modelo"], "modelo", "", "literatura", frente="modelos", abordagem=ex.get("abordagem"),
                aplicacao=ex.get("aplicacao"))
        aresta(rn, mn, "propoe", "EXTRACTED")
        an = no("abordagem:" + str(ex.get("abordagem")), str(ex.get("abordagem")), "abordagem", "", "literatura", frente="modelos")
        aresta(mn, an, "pertence_a", "EXTRACTED")

# ---- 5. conceitos ----
for e, d in con["entregas"].items():
    en = no("entrega:" + e, e, "entrega", d["doc"], "conceitos", frente="entregas", subtipo=d["tipo"])
    aresta(en, no_doc(d["doc"]) if d["doc"].endswith((".md", ".tex", ".docx", ".pdf")) else no_dado(d["doc"]), "descrito_em", "INFERRED")
for a, b in con["parte_de"]:
    aresta("entrega:" + a, "entrega:" + b, "parte_de", "INFERRED")
for f, lst in con["fontes"].items():
    fn = no("fonte:" + f, f, "fonte_externa", "", "conceitos", frente="fontes")
    for rel, alvo in lst:
        t = no_script(alvo) if alvo.endswith(".py") else no_dado(alvo)
        aresta(fn, t, rel, "INFERRED")
for a, d in con["achados"].items():
    an = no("achado:" + a, a, "achado", "", "conceitos", frente="achados")
    for ev in d["evid"]:
        aresta(an, no_script(ev) if ev.endswith(".py") else no_dado(ev), "evidenciado_por", "INFERRED")
    for doc in d["docs"]:
        aresta(an, no_doc(doc), "relatado_em", "INFERRED")
    for s in d.get("sustenta", []):
        aresta(an, "entrega:" + s, "sustenta", "INFERRED")
for a, b in con["explica"]:
    aresta("achado:" + a, "achado:" + b, "explica", "INFERRED")
for p, d in con["pendencias"].items():
    pn = no("pendencia:" + p, p, "pendencia", "", "conceitos", frente="pendencias")
    for doc in d["docs"]:
        aresta(pn, no_doc(doc), "registrada_em", "INFERRED")
    for b in d["bloqueia"]:
        aresta(pn, "entrega:" + b, "bloqueia", "INFERRED")
    for ev in d["evid"]:
        aresta(pn, no_script(ev) if ev.endswith(".py") else no_dado(ev), "envolve", "INFERRED")
for m, p in con["resolve"]:
    alvo = ("pendencia:" + p) if ("pendencia:" + p) in nos else ("achado:" + p)
    aresta(no("modelo:" + m, m, "modelo", "", "literatura", frente="modelos"), alvo, "pode_resolver", "INFERRED")

# ---- 6. resultados dos testes: modelo testado -> caso, ligado ao modelo do levantamento ----
ALIAS = {"TimesFM-2.5": "TimesFM", "TTM-r2": "Tiny Time Mixers (TTM)", "Moirai-2.0-small": "Moirai 2.0", "Chronos-Bolt-small": "Chronos",
         "ResNet-1D": "ResNet", "NHITS": "N-HiTS", "DLinear": "DLinear / NLinear", "TFT": "Temporal Fusion Transformer (TFT)",
         "TSMixerx": "TSMixer"}
met = RAIZ / "testes_modelos" / "resultados" / "metricas.csv"
if met.exists():
    M = pd.read_csv(met, sep=";", decimal=",")
    for caso in M.caso.unique():
        no("caso:" + caso, {"usinas": "Teste: usinas", "casas_prod": "Teste: FV das casas", "casas_cons": "Teste: consumo das casas"}[caso],
           "caso_teste", "testes_modelos/resultados/metricas.csv", "conceitos", frente="testes_modelos")
        aresta("caso:" + caso, "entrega:Testes de modelos de previsao (dia seguinte)", "parte_de", "INFERRED")
    for _, r in M.iterrows():
        nome = ALIAS.get(r.modelo, r.modelo)
        mn = no("modelo:" + nome, nome, "modelo", "", "testes", frente="modelos")
        aresta(mn, "caso:" + r.caso, "testado_em", "EXTRACTED", "testes_modelos/resultados/metricas.csv",
               peso=1.0, regime=r.regime, skill=round(float(r.skill), 3))

grafo = dict(directed=True, multigraph=False, graph={"projeto": "Projeto_IA", "camadas": 5}, nodes=list(nos.values()),
             links=[a for a in arestas if a["source"] in nos and a["target"] in nos])
json.dump(grafo, open(OUT / "graph.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
tipos = pd.Series([n["file_type"] for n in nos.values()]).value_counts()
rels = pd.Series([a["relation"] for a in grafo["links"]]).value_counts()
print("%d nos, %d arestas" % (len(nos), len(grafo["links"])))
print(tipos.to_string()); print(rels.to_string())
