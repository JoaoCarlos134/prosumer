# -*- coding: utf-8 -*-
"""Analise do grafo do projeto: comunidades, nos centrais, pontes entre frentes, auditoria de
linhagem de dados, lacunas de evidencia e cobertura dos modelos. Sem LLM.

Saidas: analise_rede/analise.json e dados para o REDE_PROJETO.md
"""
import json, collections
from pathlib import Path
import networkx as nx, igraph as ig, leidenalg

RAIZ = Path(__file__).resolve().parents[2]
AR = RAIZ / "analise_rede"
G = json.load(open(AR / "grafo_projeto" / "graph.json", encoding="utf-8"))
N = {n["id"]: n for n in G["nodes"]}
D = nx.MultiDiGraph()
for n in G["nodes"]:
    D.add_node(n["id"], **n)
for e in G["links"]:
    D.add_edge(e["source"], e["target"], **e)
res = {}

# ---- nucleo: sem imports de biblioteca nem docstrings (ruido estrutural) ----
nucleo = [n for n, a in D.nodes(data=True) if a["file_type"] not in ("biblioteca", "rationale")]
U = nx.Graph()
for a, b, e in D.edges(data=True):
    if a in nucleo and b in nucleo and a != b:
        w = U[a][b]["weight"] + 1 if U.has_edge(a, b) else 1
        U.add_edge(a, b, weight=w)
U.add_nodes_from(nucleo)

# ---- 1. comunidades (Leiden) ----
idx = {n: i for i, n in enumerate(U.nodes())}
gi = ig.Graph(n=len(idx), edges=[(idx[a], idx[b]) for a, b in U.edges()], directed=False)
gi.es["weight"] = [U[a][b]["weight"] for a, b in U.edges()]
part = leidenalg.find_partition(gi, leidenalg.RBConfigurationVertexPartition, weights="weight", resolution_parameter=1.0, seed=42)
com = {n: part.membership[i] for n, i in idx.items()}
grau = dict(U.degree())
comunidades = []
for c, membros in sorted(collections.defaultdict(list, {k: [] for k in set(com.values())}).items()):
    pass
por_c = collections.defaultdict(list)
for n, c in com.items():
    por_c[c].append(n)
for c, m in sorted(por_c.items(), key=lambda x: -len(x[1])):
    if len(m) < 4:
        continue
    fr = collections.Counter(N[x].get("frente", "?") for x in m).most_common(2)
    tipos = collections.Counter(N[x]["file_type"] for x in m).most_common(3)
    top = sorted(m, key=lambda x: -grau[x])[:5]
    arestas_int = U.subgraph(m).number_of_edges()
    comunidades.append(dict(id=c, n=len(m), frentes=fr, tipos=tipos, principais=[N[x]["label"] for x in top],
                            coesao=round(2 * arestas_int / (len(m) * (len(m) - 1)), 3) if len(m) > 1 else 0))
res["comunidades"] = comunidades
res["n_comunidades"] = len(set(com.values())); res["n_isolados"] = sum(1 for n in U if U.degree(n) == 0)

# ---- 2. nos centrais ----
bet = nx.betweenness_centrality(U, k=min(400, len(U)), seed=42, weight=None)
res["hubs"] = [(N[n]["label"], N[n]["file_type"], grau[n]) for n in sorted(U, key=lambda x: -grau[x])[:15]]
res["pontes"] = [(N[n]["label"], N[n]["file_type"], round(bet[n], 4)) for n in sorted(U, key=lambda x: -bet[x])[:15]]
art = list(nx.articulation_points(U.subgraph(max(nx.connected_components(U), key=len))))
res["pontos_de_articulacao"] = sorted([(N[n]["label"], N[n]["file_type"], grau[n]) for n in art], key=lambda x: -x[2])[:20]

# ---- 3. ligacoes entre frentes ----
mat = collections.Counter()
exemplos = collections.defaultdict(list)
for a, b in U.edges():
    fa, fb = N[a].get("frente", "?"), N[b].get("frente", "?")
    if fa != fb:
        k = tuple(sorted((fa, fb)))
        mat[k] += 1
        if len(exemplos[k]) < 3:
            exemplos[k].append("%s -- %s" % (N[a]["label"][:40], N[b]["label"][:40]))
res["entre_frentes"] = [(k[0], k[1], v, exemplos[k]) for k, v in mat.most_common(25)]
# arestas surpreendentes: entre comunidades pequenas e distantes, ponderadas pelo inverso do tamanho
tam = {c: len(m) for c, m in por_c.items()}
surpresa = []
for a, b in U.edges():
    ca, cb = com[a], com[b]
    if any(N[x].get("source_file", "").startswith("analise_rede/scripts") for x in (a, b)):
        continue                                   # a propria analise nao conta como conexao do projeto
    if ca != cb and N[a].get("frente") != N[b].get("frente"):
        s = 1 / ((tam[ca] * tam[cb]) ** 0.5) * (1 + (N[a]["camada"] != N[b]["camada"]))
        rels = {e["relation"] for e in D.get_edge_data(a, b, default={}).values()} | {e["relation"] for e in D.get_edge_data(b, a, default={}).values()}
        surpresa.append((round(s, 4), N[a]["label"][:55], "/".join(sorted(rels)), N[b]["label"][:55]))
res["surpreendentes"] = sorted(surpresa, reverse=True)[:15]

# ---- 4. auditoria de linhagem ----
F = nx.DiGraph()                               # fluxo: dado -> script (le), script -> dado (escreve)
observador = lambda n: N[n].get("source_file", "").startswith("analise_rede/")   # esta propria analise
for a, b, e in D.edges(data=True):
    if observador(a) or observador(b):
        continue
    if e["relation"] == "le":
        F.add_edge(b, a)
    elif e["relation"] == "escreve":
        F.add_edge(a, b)
citados_por_doc = {b for a, b, e in D.edges(data=True) if e["relation"] == "documenta"}
dados = [n for n in D if N[n]["file_type"] in ("dado", "figura", "pasta")]
brutos = ("ia_solar/dados_brutos", "dados_casas/H", "consumption_all_houses")
escritos = {n for n in dados if F.has_node(n) and F.in_degree(n) > 0}
lidos = {n for n in dados if F.has_node(n) and F.out_degree(n) > 0}
res["saidas_sem_uso"] = sorted(N[n]["source_file"] for n in escritos - lidos - citados_por_doc
                               if N[n]["file_type"] != "figura")
res["entradas_sem_origem"] = sorted(N[n]["source_file"] for n in lidos - escritos
                                    if not N[n]["source_file"].startswith(brutos))
iso = [n for n in dados if D.degree(n) == 0]
res["dados_isolados"] = collections.Counter(str(Path(N[n]["source_file"]).parent) for n in iso).most_common(15)
res["n_dados_isolados"] = len(iso)
scripts = {n for n in D if N[n]["file_type"] == "code" and N[n].get("source_file", "").endswith(".py") and N[n]["label"].endswith(".py")}
res["scripts_sem_documentacao"] = sorted({N[n]["source_file"] for n in scripts if n not in citados_por_doc})
# impacto: quantos arquivos dependem de cada no (descendentes no fluxo)
imp = {n: len(nx.descendants(F, n)) for n in F}
res["maior_impacto"] = [(N[n]["label"], N[n]["file_type"], v) for n, v in sorted(imp.items(), key=lambda x: -x[1])[:12]]
ciclos = [c for c in nx.simple_cycles(F)]
res["arquivos_editados_no_lugar"] = sorted({" <-> ".join(sorted(N[x]["label"] for x in c)) for c in ciclos})[:15]
C = nx.condensation(F)                          # ciclos (leitura e reescrita do mesmo arquivo) viram um no
cam = nx.dag_longest_path(C)
res["cadeia_mais_longa"] = [" / ".join(sorted(N[x]["label"] for x in C.nodes[c]["members"])) for c in cam]
nomes = collections.defaultdict(list)
for n in scripts:
    nomes[N[n]["label"]].append(N[n]["source_file"])
res["scripts_mesmo_nome"] = {k: v for k, v in nomes.items() if len(v) > 1}
res["citacoes_inexistentes"] = sorted({(N[a]["source_file"], N[b]["label"]) for a, b, e in D.edges(data=True) if e["relation"] == "cita_inexistente"})

# ---- 5. conceitos: pendencias, evidencias, literatura ----
res["bloqueios"] = sorted([(N[b]["label"], [N[a]["label"] for a, _, e in D.in_edges(b, data=True) if e["relation"] == "bloqueia"])
                           for b in D if N[b]["file_type"] == "entrega"], key=lambda x: -len(x[1]))
res["achados_sem_codigo"] = [N[n]["label"] for n in D if N[n]["file_type"] == "achado"
                             and not any(e["relation"] == "evidenciado_por" for _, _, e in D.out_edges(n, data=True))]
lit_por_entrega = {}
for n in D:
    if N[n]["file_type"] == "entrega":
        docs = [b for _, b, e in D.out_edges(n, data=True) if e["relation"] == "descrito_em"]
        lit_por_entrega[N[n]["label"]] = sum(1 for d in docs for _, t, e in D.out_edges(d, data=True) if e["relation"] == "cita")
res["literatura_por_entrega"] = lit_por_entrega
col = collections.Counter(N[n].get("colecoes") for n in D if N[n]["file_type"] == "paper")
res["literatura_colecoes"] = col.most_common()

# ---- 6. cobertura dos modelos ----
testados = {n for n in D if N[n]["file_type"] == "modelo" and any(e["relation"] == "testado_em" for _, _, e in D.out_edges(n, data=True))}
abord = collections.defaultdict(lambda: [0, 0])
for n in D:
    if N[n]["file_type"] == "modelo":
        ab = [N[b]["label"] for _, b, e in D.out_edges(n, data=True) if e["relation"] == "pertence_a"]
        for x in ab or ["(fora do levantamento)"]:
            abord[x][0] += 1; abord[x][1] += n in testados
res["cobertura_abordagens"] = sorted([(k, v[0], v[1]) for k, v in abord.items()], key=lambda x: -x[1])
res["testados_fora_do_levantamento"] = sorted(N[n]["label"] for n in testados
                                              if not any(e["relation"] == "pertence_a" for _, _, e in D.out_edges(n, data=True)))
res["totais"] = dict(nos=D.number_of_nodes(), arestas=D.number_of_edges(), nucleo=len(nucleo),
                     por_camada=collections.Counter(N[n]["camada"] for n in D).most_common(),
                     inferidas=sum(1 for *_, e in D.edges(data=True) if e["confidence"] == "INFERRED"))
json.dump(res, open(AR / "analise.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
# grava a comunidade em cada no, para o HTML do Graphify colorir por ela
for n in G["nodes"]:
    n["community"] = com.get(n["id"], -1)
json.dump(G, open(AR / "grafo_projeto" / "graph.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
for k, v in res.items():
    print("\n##", k); print(json.dumps(v, ensure_ascii=False, default=str)[:1500])
