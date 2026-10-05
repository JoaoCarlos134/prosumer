# -*- coding: utf-8 -*-
"""Camada de literatura: cada artigo citado em cada frente, unificado por DOI (ou titulo).

Colecoes: revisao Edge AI (1Referencias_projetoIA.xlsx), previsao de consumo embarcada (15 artigos),
artigo OCR (refs.bib) e levantamento de modelos (Modelos_previsao_geracao_consumo.xlsx).
Saida: analise_rede/literatura.json
"""
import json, re
from pathlib import Path
import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]
REV = RAIZ / "revisao_edge_ai"


def doi_de(s):
    m = re.search(r"10\.\d{4,9}/[^\s\"'<>]+", str(s or ""))
    return m.group(0).rstrip(".,;)}").lower() if m else None


def chave(doi, titulo):
    return "doi:" + doi if doi else "tit:" + re.sub(r"[^a-z0-9]", "", str(titulo).lower())[:80]


itens = {}


def adiciona(colecao, titulo, doi=None, ano=None, autores=None, extra=None):
    if not isinstance(titulo, str) or not titulo.strip():
        return
    k = chave(doi, titulo)
    # mesmo titulo com e sem DOI: junta
    kt = chave(None, titulo)
    if doi and kt in itens:
        itens[k] = itens.pop(kt)
    elif not doi:
        for kk, v in itens.items():
            if chave(None, v["titulo"]) == kt:
                k = kk; break
    it = itens.setdefault(k, dict(titulo=titulo.strip(), doi=doi, ano=ano, autores=autores, colecoes=[], extra={}))
    if colecao not in it["colecoes"]:
        it["colecoes"].append(colecao)
    if extra:
        it["extra"].update(extra)


r = pd.read_excel(REV / "1Referencias_projetoIA.xlsx")
for _, x in r.iterrows():
    adiciona("revisao_edge_ai", x["Título"], doi_de(x["Link"]), x["Ano"], x["Autor"])

e = pd.read_excel(REV / "Referencias_previsao_consumo_embarcado.xlsx")
for _, x in e.iterrows():
    adiciona("previsao_consumo_embarcado", x["Título"], doi_de(x["Link"]), x["Ano"], x["Autor"])

bib = (RAIZ / "ocr_paper" / "paper" / "refs.bib").read_text(encoding="utf-8", errors="replace")
for m in re.finditer(r"@\w+\{([^,]+),(.*?)\n\}", bib, re.S):
    corpo = m.group(2)
    t = re.search(r"title\s*=\s*[{\"](.+?)[}\"],?\s*\n", corpo, re.S)
    d = re.search(r"doi\s*=\s*[{\"](.+?)[}\"]", corpo)
    a = re.search(r"year\s*=\s*[{\"]?(\d{4})", corpo)
    if t:
        adiciona("artigo_ocr", re.sub(r"[{}\s]+", " ", t.group(1)).strip(), (d.group(1).lower() if d else None),
                 int(a.group(1)) if a else None, extra=dict(bibkey=m.group(1).strip()))

mo = pd.read_excel(REV / "Modelos_previsao_geracao_consumo.xlsx", sheet_name="Modelos")
for _, x in mo.iterrows():
    tit = x["Artigo"] if isinstance(x["Artigo"], str) and x["Artigo"] != "anuncio oficial" else None
    if tit:
        adiciona("levantamento_modelos", tit, doi_de(x["Link"]), x["Ano"],
                 extra=dict(modelo=x["Modelo"], abordagem=x["Abordagem"], aplicacao=x["Aplicacao testada"]))

json.dump(itens, open(RAIZ / "analise_rede" / "literatura.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
cont = pd.Series([c for v in itens.values() for c in v["colecoes"]]).value_counts()
print("%d artigos unicos" % len(itens)); print(cont.to_string())
multi = {k: v for k, v in itens.items() if len(v["colecoes"]) > 1}
print("\nArtigos em mais de uma frente (%d):" % len(multi))
for v in multi.values():
    print("  [%s] %s" % (" + ".join(v["colecoes"]), v["titulo"][:95]))
