# -*- coding: utf-8 -*-
"""Retoma a extracao Graphify e constroi a rede auditavel deste repositorio.

Executar com o Python registrado em graphify-out/.graphify_python. Nao executa
scripts legados nem envia dados a servicos externos. Chunks semanticos sao
preservados; novas extracoes devem ser feitas quando seu conteudo mudar.
"""
import ast
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import networkx as nx
from graphify.analyze import god_nodes, surprising_connections, suggest_questions
from graphify.build import build_from_json
from graphify.cache import save_semantic_cache
from graphify.cluster import cluster, score_all
from graphify.detect import detect, save_manifest
from graphify.diagnostics import diagnose_extraction
from graphify.export import to_html, to_json
from graphify.extract import extract

RAIZ = Path(__file__).resolve().parents[3]
OUT = RAIZ / "graphify-out"
SPEC = Path.home() / ".claude/skills/graphify/references/extraction-spec.md"


def grava(nome, valor):
    (OUT / nome).write_text(json.dumps(valor, ensure_ascii=False, indent=2), encoding="utf-8")


def relativo(nome):
    p = Path(nome)
    return p.relative_to(RAIZ).as_posix() if p.is_absolute() else p.as_posix()


def chave(nome):
    return re.sub(r"[^a-z0-9]+", "_", str(nome).lower()).strip("_")


def inventario():
    proc = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
                          cwd=RAIZ, check=True, stdout=subprocess.PIPE)
    return sorted({p for p in proc.stdout.decode("utf-8").split("\0")
                   if p and not p.startswith("graphify-out/") and (RAIZ / p).is_file()})


def camada(p):
    if "resultados_v1" in p:
        return "Referência histórica v1"
    if p.startswith("experimentos/"):
        if "/ambientes/" in p:
            return "Ambientes de execução"
        if "/dados/" in p:
            return "Dados horários e clima"
        return "Previsão e avaliação v2"
    if p.startswith("docs/literatura") or "/converted/" in p:
        return "Literatura e modelos"
    if "embarcado" in p or "verifica_tflite" in p:
        return "Modelos embarcados TFLite"
    if "base_modelagem" in p:
        return "Regressão e modelagem legada"
    if "/tarifas/" in p:
        return "Tarifas e faturamento"
    if "/curitiba/" in p or "/comparativo/" in p:
        return "Curitiba e comparação solar"
    if "/cascavel/" in p:
        return "Análise solar de Cascavel"
    if "irradiancia_inversa" in p:
        return "Irradiância e física solar"
    if "analise_rede" in p:
        return "Linhagem e rede histórica"
    if p.startswith("legado/"):
        return "Ferramentas solares comuns"
    return "Planejamento e revisão"


def carregar_semantica():
    arquivos = sorted(OUT.glob(".graphify_chunk_*.json"))
    if not arquivos:
        arquivos = sorted((OUT / "extracao").glob("chunk_*.json"))
    if not arquivos:
        raise RuntimeError("Nenhum chunk semantico recuperado; executar a extracao primeiro.")
    partes = [(p, json.loads(p.read_text(encoding="utf-8-sig"))) for p in arquivos]
    for p, d in partes:
        if not isinstance(d.get("nodes"), list) or not isinstance(d.get("edges"), list):
            raise ValueError(f"Chunk invalido: {p}")
    # Um chunk novo pode substituir arquivos inteiros de um chunk recuperado.
    substituidos = {}
    for p, d in partes:
        for fonte in d.get("replaces_sources", []):
            substituidos[relativo(fonte)] = p
    nos, arestas, hiper = [], [], []
    for p, d in partes:
        for k, destino in (("nodes", nos), ("edges", arestas), ("hyperedges", hiper)):
            destino.extend(x for x in d.get(k, [])
                           if substituidos.get(relativo(x.get("source_file", "")), p) == p)
    return dict(nodes=nos, edges=arestas, hyperedges=hiper, input_tokens=0, output_tokens=0), partes


def completar(extracao, arquivos):
    nos = {n["id"]: dict(n) for n in extracao["nodes"]}
    arestas = extracao["edges"]
    por_fonte = defaultdict(list)
    for n in nos.values():
        n["source_file"] = relativo(n.get("source_file", ""))
        n["camada"] = camada(n["source_file"])
        if n["source_file"]:
            por_fonte[n["source_file"]].append(n["id"])
    ids_arquivo = {}
    for p in sorted(set(arquivos) | set(por_fonte)):
        candidato = chave(str(Path(p).with_suffix("")))
        if candidato in nos and nos[candidato].get("_origin") == "ast":
            i = candidato
        else:
            i = candidato + "_arquivo"
            sufixo = Path(p).suffix.lower()
            ft = "code" if sufixo == ".py" else "image" if sufixo in (".png", ".jpg") else "paper" if sufixo == ".pdf" else "document"
            nos[i] = dict(id=i, label=Path(p).name, file_type=ft, source_file=p,
                          source_location=None, camada=camada(p), tipo_artefato=sufixo[1:],
                          presente=(RAIZ / p).is_file(), _origin="inventory")
        ids_arquivo[p] = i
        for membro in por_fonte[p]:
            if membro != i:
                arestas.append(dict(source=i, target=membro, relation="contains",
                                    confidence="EXTRACTED", confidence_score=1.0, source_file=p,
                                    source_location=nos[membro].get("source_location"), weight=1.0))

    def liga(a, b, rel, fonte, local=None, confianca="EXTRACTED", score=1.0):
        arestas.append(dict(source=a, target=b, relation=rel, confidence=confianca,
                            confidence_score=score, source_file=fonte, source_location=local, weight=1.0))

    # Imports locais do legado usam sys.path; resolver somente nomes unicos.
    modulos = defaultdict(list)
    for p, i in ids_arquivo.items():
        if p.endswith(".py"):
            modulos[chave(Path(p).stem)].append(i)
    externos = Counter()
    for e in arestas:
        e["source_file"] = relativo(e.get("source_file", ""))
        e.setdefault("confidence_score", {"EXTRACTED": 1.0, "INFERRED": 0.75, "AMBIGUOUS": 0.2}.get(e.get("confidence"), 0.2))
        for lado in ("source", "target"):
            if e[lado] not in nos:
                i = e[lado]
                if lado == "target" and len(modulos.get(i, [])) == 1 and e["relation"] in ("imports", "imports_from"):
                    e[lado] = modulos[i][0]
                elif lado == "target" and e["relation"] in ("imports", "imports_from"):
                    externos[i] += 1
                    nos[i] = dict(id=i, label=i, file_type="code", source_file="", source_location=None,
                                  external=True, camada="Dependências Python", _origin="ast")
                else:
                    raise ValueError(f"Endpoint sem origem: {e}")

    # Citacoes literais sao referencias, nao prova de que um script le um arquivo.
    basenames = defaultdict(list)
    for p in ids_arquivo:
        basenames[Path(p).name].append(p)
    ambiguas = []
    extensoes = r"(?:py|md|parquet|csv|json|xlsx|docx|pdf|tflite|png|html|txt)"
    padrao = re.compile(r"[\w.\-/]+\." + extensoes + r"\b", re.IGNORECASE)
    for p in arquivos:
        if Path(p).suffix.lower() not in (".py", ".md", ".txt"):
            continue
        for ln, linha in enumerate((RAIZ / p).read_text(encoding="utf-8-sig").splitlines(), 1):
            for nome in set(padrao.findall(linha.replace("\\", "/"))):
                candidatos = basenames.get(Path(nome).name, [])
                exatos = [q for q in candidatos if q == nome or q.endswith("/" + nome)]
                resolvido = (RAIZ / p).parent / nome
                if resolvido.is_file() and resolvido.is_relative_to(RAIZ):
                    exatos = [resolvido.relative_to(RAIZ).as_posix()]
                alvos = exatos or candidatos
                if len(alvos) == 1 and alvos[0] in ids_arquivo and alvos[0] != p:
                    liga(ids_arquivo[p], ids_arquivo[alvos[0]], "references", p, f"L{ln}")
                elif len(alvos) > 1:
                    ambiguas.append(dict(source_file=p, source_location=f"L{ln}", referencia=nome, candidatos=alvos))

    # Linhagem verificavel do benchmark: os artefatos declaram modelo/caso/regime
    # no nome; metricas.csv identifica cada resultado com as mesmas tres chaves.
    base = "experimentos/testes_previsao/"
    metricas = base + "resultados/metricas.csv"
    if metricas in ids_arquivo:
        with (RAIZ / metricas).open(encoding="utf-8-sig", newline="") as f:
            for ln, row in enumerate(csv.DictReader(f, delimiter=";"), 2):
                nome = f"{row['modelo']}__{row['caso']}__{row['regime']}.parquet".replace(" ", "_").replace("/", "-")
                p = base + "resultados/previsoes/" + nome
                if p not in ids_arquivo:
                    raise ValueError(f"Metrica sem previsao: {p}")
                i = ids_arquivo[p]
                nos[i].update(modelo=row["modelo"], caso=row["caso"], regime=row["regime"],
                              skill=float(row["skill"].replace(",", ".")))
                liga(i, ids_arquivo[metricas], "evaluated_in", metricas, f"L{ln}")
                dado = base + "dados/" + ("usinas_horario.parquet" if row["caso"] == "usinas" else "casas_horario.parquet")
                liga(ids_arquivo[dado], i, "shares_data_with", metricas, f"L{ln}", "INFERRED", 0.95)
                if row["regime"] in ("C", "C-gfs"):
                    clima = base + "dados/previsao_tempo.parquet"
                    liga(ids_arquivo[clima], i, "shares_data_with", base + "scripts/comum.py", "exog_previsao", "INFERRED", 0.95)
    # Cada par TFLite/JSON e documentado pelo verificador, sem executar TensorFlow.
    embarcado = "legado/ia_solar/base_modelagem/embarcado/"
    verificador = "legado/ia_solar/base_modelagem/referencia/verifica_tflite.py"
    for p in arquivos:
        if p.startswith(embarcado) and Path(p).suffix in (".tflite", ".json"):
            liga(ids_arquivo[verificador], ids_arquivo[p], "references", verificador,
                 "main: verifica arquivos e salva preprocessamento", "INFERRED", 0.95)

    # Preservar arestas com relacoes ou evidencias diferentes; remover so iguais.
    unicas = {}
    for e in arestas:
        k = tuple(e.get(a) for a in ("source", "target", "relation", "source_file", "source_location", "confidence"))
        unicas.setdefault(k, e)
    extracao.update(nodes=list(nos.values()), edges=list(unicas.values()))
    grava("referencias_ambiguas.json", ambiguas)
    return ids_arquivo


def relatorio(g, comunidades, labels, coesao, saude, cobertura, gods, surpresas, perguntas, arestas):
    cont = Counter(e["confidence"] for e in arestas)
    linhas = ["# Rede auditável do prossumidor", "",
              f"Gerada em {datetime.now(timezone.utc).isoformat()}. Escopo: exportação privada presente neste repositório.", "",
              f"**{g.number_of_nodes()} nós · {len(arestas)} relações com evidência · {g.number_of_edges()} pares na visualização · {len(comunidades)} comunidades.**", "",
              "[Abrir rede interativa](graph.html) · [Dados GraphRAG](graph.json) · [Revisão passo a passo](../docs/projeto/REVISAO_ATUAL.md)", "",
              "## Método e limites", "",
              "AST reextraída do código atual; extrações semânticas recuperadas da sessão interrompida e completadas; inventário Git e referências literais conferidos localmente. Dados tabulares e modelos binários entram como artefatos, sem expor linhas das séries. Presença no inventário não equivale à validação científica de todo o conteúdo.", "",
              "Relações `EXTRACTED` têm evidência explícita; `INFERRED` são interpretações identificadas. Referências com vários candidatos estão em `referencias_ambiguas.json`, sem escolher um destino arbitrário. Imports externos são nós identificados como externos. O legado depende de dados mantidos no Lactec; ausência local não prova perda no projeto original.", "",
              f"Confiança das relações: {dict(cont)}. O JSON preserva todas as relações e suas fontes; a visualização e as métricas de centralidade usam uma projeção simples com um par por conexão. Há {saude['self_loop_edges']} autorrelações (incluindo recursão real), {saude['dangling_endpoint_edges']} arestas com destino ausente e {saude['missing_endpoint_edges']} sem endpoint. A projeção comprime {saude['undirected_same_endpoint_collapsed_edges']} relações paralelas, preservadas no JSON.", "",
              f"Cobertura: {len(cobertura['files'])} arquivos inventariados; {len(cobertura['semantic_covered'])} fontes semânticas; {len(cobertura['semantic_missing'])} fontes semânticas pendentes. Consulte `cobertura.json` para nomes, hashes e modalidade de revisão.", "",
              "Custo de tokens: indisponível. Os chunks recuperados registravam zero e a ferramenta de agentes não fornece contagem de uso; zero não significa extração gratuita. Nenhuma estimativa é apresentada como medição.", "",
              "O HTML contém os dados localmente e carrega apenas a biblioteca vis-network por CDN. As conclusões do benchmark e seu estado de reexecução estão na revisão, não são inferidas da centralidade.", "",
              "## Comunidades", "", "| Comunidade | Nós | Coesão |", "|---|---:|---:|"]
    for c, ns in comunidades.items():
        linhas.append(f"| {labels[c]} | {len(ns)} | {coesao[c]:.4f} |")
    linhas += ["", "## Nós centrais", ""]
    internos = [x for x in sorted(g.degree, key=lambda x: x[1], reverse=True) if not g.nodes[x[0]].get("external")][:10]
    for i, grau in internos:
        n = g.nodes[i]
        linhas.append(f"- **{n.get('label', i)}** — grau {grau}; `{n.get('source_file', '')}`.")
    linhas += ["", "## Conexões entre frentes", ""]
    for item in surpresas[:5]:
        linhas.append("- " + json.dumps(item, ensure_ascii=False))
    linhas += ["", "## Perguntas sugeridas", "",
               "- Como o protocolo em comum.py liga as entradas de clima, as previsões e a avaliação?",
               "- Quais artefatos do legado permitem iniciar E1 e quais dependem de dados do Lactec?",
               "- Como os resultados se ligam ao levantamento de modelos e aos planos dos artigos?", "",
               "## Reprodução", "", "```powershell",
               "& (Get-Content graphify-out/.graphify_python) docs/projeto/scripts/constroi_rede.py", "```", "",
               "O comando verifica hashes das extrações preservadas e avisa sobre fontes alteradas. Faça nova extração semântica dessas fontes antes de interpretar o grafo como atualizado. As métricas do benchmark são lidas novamente em cada construção."]
    (OUT / "GRAPH_REPORT.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")


def main():
    OUT.mkdir(exist_ok=True)
    arquivos = inventario()
    det = detect(RAIZ)
    grava(".graphify_detect.json", det)
    sem, partes = carregar_semantica()
    codigo = [RAIZ / p for p in arquivos if p.endswith(".py")]
    estrutura = extract(codigo, cache_root=RAIZ)
    if estrutura.get("failed_sources"):
        raise RuntimeError(f"Falha AST: {estrutura['failed_sources']}")
    grava(".graphify_ast.json", estrutura)
    extracao = dict(nodes=estrutura["nodes"] + sem["nodes"], edges=estrutura["edges"] + sem["edges"],
                    hyperedges=sem["hyperedges"], input_tokens=0, output_tokens=0)
    ids = completar(extracao, arquivos)
    # Manter a extracao original com todas as evidencias, antes da projecao simples.
    grava(".graphify_extract.json", extracao)
    saude = diagnose_extraction(extracao, directed=False, root=RAIZ)
    if saude["dangling_endpoint_edges"] or saude["missing_endpoint_edges"]:
        raise ValueError("Grafo com endpoints ausentes; veja a extracao.")
    g = build_from_json(extracao, root=RAIZ, dedup=False)
    if not g:
        raise ValueError("Extracao vazia")
    links = extracao["edges"]
    # O build pode reconciliar ids. Nenhuma evidencia pode desaparecer na exportacao.
    perdidas = [e for e in links if e["source"] not in g or e["target"] not in g]
    if perdidas:
        grava("endpoints_reconciliar.json", perdidas)
        raise ValueError(f"{len(perdidas)} relacoes perderiam endpoint apos o build")
    for e in links:
        e["source_file"] = relativo(e.get("source_file", ""))
    comunidades = cluster(g)
    coesao = score_all(g, comunidades)
    labels = {}
    usados = Counter()
    for c, ns in comunidades.items():
        votos = Counter(g.nodes[n].get("camada", "Planejamento e revisão") for n in ns if not g.nodes[n].get("external"))
        titulo = votos.most_common(1)[0][0] if votos else "Dependências Python"
        usados[titulo] += 1
        labels[c] = titulo if usados[titulo] == 1 else f"{titulo} ({usados[titulo]})"
    if not to_json(g, comunidades, str(OUT / "graph.json"), community_labels=labels, original_links=links):
        raise RuntimeError("Graphify recusou reduzir grafo existente; verificar cobertura")
    if not to_html(g, comunidades, str(OUT / "graph.html"), community_labels=labels, node_limit=5000):
        raise RuntimeError("HTML nao foi escrito")
    gods = god_nodes(g)
    surpresas = surprising_connections(g, comunidades)
    perguntas = suggest_questions(g, comunidades, labels)
    grava(".graphify_analysis.json", dict(communities=comunidades, cohesion=coesao, gods=gods,
                                          surprises=surpresas, questions=perguntas))
    grava(".graphify_labels.json", labels)
    grava("integridade.json", saude)
    fontes_sem = {relativo(n["source_file"]) for n in sem["nodes"]}
    fontes_prev = {relativo(p) for cat in ("document", "paper", "image") for p in det["files"][cat]}
    hashes = {p: hashlib.sha256((RAIZ / p).read_bytes()).hexdigest() for p in fontes_sem if (RAIZ / p).is_file()}
    arq_hash = OUT / "extracao/fontes_sha256.json"
    antigos = json.loads(arq_hash.read_text(encoding="utf-8")) if arq_hash.exists() else {}
    desatualizadas = [p for p, h in hashes.items() if p in antigos and antigos[p] != h]
    cobertura = dict(files=[dict(path=p, node=ids[p], sha256=hashlib.sha256((RAIZ / p).read_bytes()).hexdigest(),
                                review="AST" if p.endswith(".py") else "semantic" if p in fontes_sem else "inventory") for p in arquivos],
                     semantic_covered=sorted(fontes_sem), semantic_missing=sorted(fontes_prev-fontes_sem),
                     semantic_changed=desatualizadas, raw_data_exported=False)
    grava("cobertura.json", cobertura)
    relatorio(g, comunidades, labels, coesao, saude, cobertura, gods, surpresas, perguntas, links)
    # Guardar chunks recuperados, sem remover a unica copia da sessao anterior.
    (OUT / "extracao").mkdir(exist_ok=True)
    for p, d in partes:
        destino = OUT / "extracao" / p.name.replace(".graphify_", "")
        if destino != p:
            destino.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    if not arq_hash.exists():
        arq_hash.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")
    if SPEC.exists():
        save_semantic_cache(sem["nodes"], sem["edges"], sem["hyperedges"], root=RAIZ,
                            allowed_source_files=[str(RAIZ / p) for p in fontes_sem], prompt_file=SPEC)
    from graphify.cli import _stamped_manifest_files
    estampados = _stamped_manifest_files(det["files"], extracao, RAIZ)
    save_manifest(estampados, root=RAIZ, scan_corpus={p for fs in det["files"].values() for p in fs})
    grava("cost.json", dict(input_tokens=None, output_tokens=None, status="unknown",
                             reason="Contagens indisponiveis na sessao recuperada e na ferramenta de agentes"))
    print(json.dumps(dict(nodes=len(g), relations=len(links), visual_edges=g.number_of_edges(),
                          communities=len(comunidades), files=len(arquivos), semantic_missing=cobertura["semantic_missing"],
                          semantic_changed=desatualizadas), ensure_ascii=False))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
