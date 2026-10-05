# -*- coding: utf-8 -*-
"""Linhagem de dados: quem le e quem escreve cada arquivo.

Percorre a arvore sintatica (AST) de cada script .py do projeto e acha as chamadas de leitura
(read_csv, read_parquet, read_excel, open, glob, json.load...) e de escrita (to_csv, to_parquet,
savefig, open(..., "w")...). Os nomes de arquivo sao resolvidos contra os arquivos que existem
no disco; nomes curtos dos scripts de analise passam por caminho(). Um nome que nao existe no
disco vira no 'arquivo ausente'.

Saida: analise_rede/linhagem.json
"""
import ast, fnmatch, json, os, re, sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]                      # Projeto_IA/
sys.path.insert(0, str(RAIZ / "ia_solar" / "analise" / "comum" / "scripts"))
from caminhos import caminho                                     # noqa: E402

EXT_DADOS = (".csv", ".parquet", ".xlsx", ".json", ".png", ".html", ".tflite", ".txt", ".pkl", ".pdf", ".docx")
IGNORA = ("referencias_pdf", "prev_consumo_embarcado_refs", "ocr_paper/references/pdfs", "graphify-out", "__pycache__", ".git/")
LEITURA = {"read_csv", "read_parquet", "read_excel", "ExcelFile", "load_workbook", "read_text", "read_json", "glob",
           "load", "read_bytes", "from_pretrained", "Image.open", "imread"}
ESCRITA = {"to_csv", "to_parquet", "to_excel", "savefig", "write_text", "write_bytes", "dump", "save", "ParquetWriter",
           "grava", "to_json", "write"}


def rel(p):
    return Path(p).resolve().relative_to(RAIZ).as_posix()


# indice de arquivos de dados existentes
arquivos = {}
for p in RAIZ.rglob("*"):
    r = p.relative_to(RAIZ).as_posix()
    if p.is_file() and p.suffix.lower() in EXT_DADOS and not any(i in r for i in IGNORA):
        arquivos.setdefault(p.name, []).append(r)


def nome_chamada(f):
    if isinstance(f, ast.Attribute):
        base = f.value.id if isinstance(f.value, ast.Name) else ""
        return f"{base}.{f.attr}" if base == "Image" else f.attr
    return f.id if isinstance(f, ast.Name) else ""


def padrao(n):
    """f-string ou 'x%d.csv' % i -> padrao com curinga ('H*_Wh.csv')."""
    if isinstance(n, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "*" for v in n.values)
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and isinstance(n.left, ast.Constant) and isinstance(n.left.value, str):
        return re.sub(r"%[-0-9.]*[sdif]", "*", n.left.value)
    return None


def literais(no, variaveis):
    """Strings (e padroes) dentro de um no; caminho('x') e resolvido; variaveis ja atribuidas sao seguidas."""
    pulados = set()
    for n in ast.walk(no):
        if isinstance(n, ast.Call) and nome_chamada(n.func) in ("caminho", "P") and n.args:
            pulados.update(id(x) for x in ast.walk(n.args[0]))
            arg = n.args[0]
            s = arg.value if isinstance(arg, ast.Constant) else padrao(arg)
            if isinstance(s, str):
                try:
                    yield ("caminho", caminho(s))
                except Exception:
                    pass
        p = padrao(n)
        if p:
            pulados.update(id(x) for x in ast.walk(n))
            yield ("literal", p)
        if isinstance(n, ast.Name) and n.id in variaveis:
            yield from variaveis[n.id]
    for n in ast.walk(no):
        if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in pulados:
            if Path(n.value).stem and not n.value.startswith("."):
                yield ("literal", n.value)


def resolve(tipo, s, script):
    if tipo == "caminho":
        p = Path(s)
        if "*" in p.name or "[" in p.name:
            return [rel(x) for x in p.parent.glob(p.name)] or [rel(p.parent)]
        return [rel(p)] if p.exists() else ["AUSENTE:" + rel(p)]
    nome = Path(s.replace("\\", "/")).name
    if not nome.lower().endswith(EXT_DADOS) and "*" not in nome:
        return []
    if "*" in nome:
        fixo = re.sub(r"\*|\.[a-z]+$", "", nome.lower())
        if not nome.lower().endswith(EXT_DADOS) or (nome.startswith("*") and len(fixo) < 2):
            return []
        topo = script.split("/")[0]
        casam = [a for k, v in arquivos.items() if fnmatch.fnmatch(k, nome) for a in v]
        perto = [a for a in casam if a.split("/")[0] == topo] or casam
        return perto[:200]
    achados = arquivos.get(nome, [])
    if not achados:
        return ["AUSENTE:" + nome]
    # prefere o arquivo mais proximo do script (mesma arvore)
    achados = sorted(achados, key=lambda a: -len(os.path.commonprefix([a, script])))
    return achados[:1]


arestas = []
for py in sorted(RAIZ.rglob("*.py")):
    r = py.relative_to(RAIZ).as_posix()
    if any(i in r for i in IGNORA):
        continue
    try:
        arv = ast.parse(py.read_text(encoding="utf-8", errors="replace"))
    except SyntaxError:
        continue
    # variaveis que guardam caminhos (OUT = caminho("x.csv"); pq = os.path.join(dst, "base_%s.parquet" % u))
    variaveis = {}
    def e_caminho(v):
        """So guarda variaveis que SAO caminhos (nao o resultado de ler um arquivo)."""
        if isinstance(v, (ast.Constant, ast.JoinedStr)):
            return True
        if isinstance(v, ast.BinOp):
            return e_caminho(v.left) or e_caminho(v.right)
        if isinstance(v, ast.Call):
            return nome_chamada(v.func) in ("caminho", "P", "join", "Path", "with_name", "with_suffix", "str", "replace", "lower", "strip")
        return isinstance(v, ast.Name)

    for n in ast.walk(arv):
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name) and e_caminho(n.value):
            achado = [x for x in literais(n.value, variaveis) if x[0] == "caminho" or Path(x[1]).name.lower().endswith(EXT_DADOS)]
            if achado:
                variaveis[n.targets[0].id] = achado
    # figuras salvas por nome sem extensao (save(fig, "21_azimuth_resolved"))
    if "savefig" in py.read_text(encoding="utf-8", errors="replace"):
        hastes = {}
        for v in arquivos.values():
            for a in v:
                if a.endswith(".png") and a.split("/")[0] == r.split("/")[0] and "/_temp/" not in a:
                    hastes.setdefault(Path(a).stem, []).append(a)
        for n in ast.walk(arv):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value in hastes:
                alvo = max(hastes[n.value], key=lambda a: len(os.path.commonprefix([a, r])))
                arestas.append(dict(script=r, arquivo=alvo, relacao="escreve", linha=n.lineno))
    for n in ast.walk(arv):
        if not isinstance(n, ast.Call):
            continue
        f = nome_chamada(n.func)
        modo = None
        if f == "open":
            m = [a.value for a in n.args[1:2] if isinstance(a, ast.Constant)] + \
                [k.value.value for k in n.keywords if k.arg == "mode" and isinstance(k.value, ast.Constant)]
            modo = "escreve" if m and any(c in m[0] for c in "wa") else "le"
        elif f in LEITURA:
            modo = "le"
        elif f in ESCRITA:
            modo = "escreve"
        if not modo:
            continue
        alvo = list(n.args) + [k.value for k in n.keywords]
        if isinstance(n.func, ast.Attribute) and f in ("write_bytes", "write_text", "read_text", "read_bytes", "open") \
                and isinstance(n.func.value, ast.Name) and n.func.value.id in variaveis:
            alvo = [n.func.value]                  # arq.write_bytes(...): o caminho e o proprio objeto
        elif f in ("dump", "write", "write_table"):
            alvo = alvo[1:2]                       # dump(objeto, arquivo): o objeto nao e caminho
        elif isinstance(n.func, ast.Attribute) and f in ESCRITA | {"load"}:
            alvo = alvo[:2]
        for no in alvo:
            for tipo, s in literais(no, variaveis):
                for a in resolve(tipo, s, r):
                    arestas.append(dict(script=r, arquivo=a, relacao=modo, linha=n.lineno))

# remove duplicatas
vistos, uni = set(), []
for a in arestas:
    k = (a["script"], a["arquivo"], a["relacao"])
    if k not in vistos:
        vistos.add(k); uni.append(a)
todos = sorted({a for v in arquivos.values() for a in v})
json.dump(dict(arestas=uni, arquivos=todos), open(RAIZ / "analise_rede" / "linhagem.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
aus = sorted({a["arquivo"] for a in uni if a["arquivo"].startswith("AUSENTE:")})
print("%d arestas (%d leituras, %d escritas) | %d arquivos de dados no disco | %d nomes sem arquivo"
      % (len(uni), sum(a["relacao"] == "le" for a in uni), sum(a["relacao"] == "escreve" for a in uni), len(todos), len(aus)))
for a in aus:
    quem = sorted({x["script"].split("/")[-1] for x in uni if x["arquivo"] == a})
    print("   ", a, "<-", ", ".join(quem)[:120])
