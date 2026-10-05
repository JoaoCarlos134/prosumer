# -*- coding: utf-8 -*-
"""Camada de documentos: que arquivos cada documento cita, e quais citacoes apontam para o nada.

Le .md, .tex, .docx e os PDF proprios do projeto (nao os artigos de terceiros). Uma mencao a um
nome de arquivo que existe no projeto vira aresta 'documenta'; um nome que nao existe em lugar
nenhum vira 'citacao obsoleta'.

Saida: analise_rede/documentos.json
"""
import json, re, zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
IGNORA = ("referencias_pdf", "prev_consumo_embarcado_refs", "ocr_paper/references/pdfs", "graphify-out", ".git/",
          "ocr_paper/template", "IEEEtran")
PDF_PROPRIOS = ["projeto/Síntese do Projeto de PD&I - IA_Borda_rev02.pdf", "outros/guias/Guide1_Claude_App_Setup.pdf",
                "outros/guias/Guide2_VSCode_Claude_Code_Setup.pdf", "ocr_paper/paper/main.pdf",
                "ocr_paper/references/Solo___UPEC_2026.pdf", "outros/Paper_Solo_UPEC_2026.pdf"]
NOME = re.compile(r"[\w\-\.&]+\.(?:py|csv|parquet|xlsx|json|md|html|png|tflite|tex|bib|docx|pdf|ipynb|zip)\b", re.I)


def texto(p):
    s = p.suffix.lower()
    if s in (".md", ".tex", ".bib", ".txt"):
        return p.read_text(encoding="utf-8", errors="replace")
    if s == ".docx":
        x = zipfile.ZipFile(p).read("word/document.xml").decode("utf-8", "replace")
        return re.sub(r"<[^>]+>", " ", x)
    if s == ".pdf":
        from pypdf import PdfReader
        return " ".join((pg.extract_text() or "") for pg in PdfReader(str(p)).pages)
    return ""


existentes = {}
for p in RAIZ.rglob("*"):
    r = p.relative_to(RAIZ).as_posix()
    if p.is_file() and ".git/" not in r:
        existentes.setdefault(p.name.lower(), []).append(r)

docs = [p for p in RAIZ.rglob("*") if p.suffix.lower() in (".md", ".tex", ".docx")
        and not any(i in p.relative_to(RAIZ).as_posix() for i in IGNORA)]
docs += [RAIZ / f for f in PDF_PROPRIOS if (RAIZ / f).exists()]
saida = []
for p in docs:
    r = p.relative_to(RAIZ).as_posix()
    try:
        t = texto(p)
    except Exception as e:
        print("nao li", r, e); continue
    mencoes = sorted(set(m.group(0) for m in NOME.finditer(t)))
    cita, obsoletas = [], []
    for m in mencoes:
        alvos = existentes.get(m.lower())
        if alvos:
            alvos = sorted(alvos, key=lambda a: -len(Path(a).parts) if Path(a).parent == p.parent else 0)
            cita.append(dict(nome=m, alvo=alvos[0], n_alvos=len(alvos)))
        elif any(n.endswith(m.lower()) for n in existentes):
            # pedaco de um nome com espacos ("Fatura de energia.xlsx") ou sufixo de padrao ("base_<Usina>_5min.csv")
            continue
        elif not m.lower().startswith(("www.", "http")) and len(m) > 5:
            obsoletas.append(m)
    saida.append(dict(documento=r, caracteres=len(t), cita=cita, obsoletas=obsoletas))
    print("%-72s %4d citacoes  %3d obsoletas" % (r[:72], len(cita), len(obsoletas)))
json.dump(saida, open(RAIZ / "analise_rede" / "documentos.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print("\nCitacoes obsoletas (nome citado que nao existe no projeto):")
for d in saida:
    if d["obsoletas"]:
        print("  %s: %s" % (d["documento"], ", ".join(d["obsoletas"][:12]) + (" ..." if len(d["obsoletas"]) > 12 else "")))
