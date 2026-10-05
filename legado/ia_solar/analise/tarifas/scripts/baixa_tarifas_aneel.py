# -*- coding: utf-8 -*-
"""Baixa a base tarifária oficial da ANEEL (dados abertos) e monta as tabelas
de referência das duas usinas, que são atendidas pela Copel-DIS.

Fontes (API CKAN de https://dadosabertos.aneel.gov.br):
  - Tarifas de aplicação das distribuidoras   -> TUSD e TE homologadas por vigência
  - Componentes tarifárias                    -> abertura da TUSD (Fio B etc.)
  - Bandeiras tarifárias                      -> acionamento mês a mês e adicionais

Roda com o sandbox de rede desligado. Gera os CSV em ../dados/.
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
DADOS = RAIZ / "dados"
CACHE = RAIZ / "dados" / "_cache"

RES_TARIFAS = "fcf2906c-7c32-4b9b-a637-054e7a5234f4"
RES_COMPONENTES_2026 = "e8717aa8-2521-453f-bf16-fbb9a16eea39"
RES_BAND_ACION = "0591b8f6-fe54-437b-b72b-1aa2efd46e42"
RES_BAND_ADIC = "5879ca80-b3bd-45b1-a135-d9b77c1d5b36"

API = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search?"


def busca(resource_id, filtros=None, pagina=1000):
    """Paginação da API do CKAN, com repetição — o proxy da Lactec derruba."""
    recs, off = [], 0
    while True:
        p = {"resource_id": resource_id, "limit": pagina, "offset": off}
        if filtros:
            p["filters"] = json.dumps(filtros)
        url = API + urllib.parse.urlencode(p)
        for tentativa in range(5):
            try:
                r = json.load(urllib.request.urlopen(url, timeout=150))["result"]
                break
            except Exception:
                if tentativa == 4:
                    raise
                time.sleep(4)
        recs += r["records"]
        off += pagina
        if off >= r["total"]:
            return recs


def cacheado(nome, fn):
    CACHE.mkdir(parents=True, exist_ok=True)
    alvo = CACHE / f"{nome}.json"
    if alvo.exists():
        return json.loads(alvo.read_text(encoding="utf-8"))
    dados = fn()
    alvo.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
    return dados


def num(s):
    """'1.013,36' -> 1013.36 ; ',00' -> 0.0"""
    return float(str(s).replace(".", "").replace(",", "."))


def tarifas_copel():
    recs = cacheado("copel_tarifas", lambda: busca(RES_TARIFAS, {"SigAgente": "COPEL-DIS"}))
    d = pd.DataFrame(recs)
    d = d[(d.DscBaseTarifaria == "Tarifa de Aplicação") & (d.DscSubGrupo.isin(["B1", "B3"]))]
    d = d[d.DscModalidadeTarifaria.isin(["Convencional", "Branca"])]
    d = d[d.DscDetalhe == "Não se aplica"]          # sem SCEE: tarifa cheia de consumo
    d = d[d.DscSubClasse.isin(["Residencial", "Não se aplica"])]
    for c in ("VlrTUSD", "VlrTE"):
        d[c] = d[c].map(num)
    d = d.rename(columns={
        "DscREH": "resolucao", "DatInicioVigencia": "vigencia_ini",
        "DatFimVigencia": "vigencia_fim", "DscSubGrupo": "subgrupo",
        "DscModalidadeTarifaria": "modalidade", "NomPostoTarifario": "posto",
        "VlrTUSD": "tusd_RS_MWh", "VlrTE": "te_RS_MWh"})
    d["total_RS_MWh"] = (d.tusd_RS_MWh + d.te_RS_MWh).round(2)
    cols = ["vigencia_ini", "vigencia_fim", "subgrupo", "modalidade", "posto",
            "tusd_RS_MWh", "te_RS_MWh", "total_RS_MWh", "resolucao"]
    return d[cols].sort_values(["vigencia_ini", "subgrupo", "modalidade", "posto"])


def componentes_b1():
    f = {"SigNomeAgente": "COPEL-DIS", "DscSubGrupoTarifario": "B1",
         "DscBaseTarifaria": "Tarifa de Aplicação", "DscModalidadeTarifaria": "Convencional",
         "DscSubClasseConsumidor": "Residencial", "DscDetalheConsumidor": "Não se aplica"}
    recs = cacheado("copel_componentes_2026", lambda: busca(RES_COMPONENTES_2026, f, 500))
    d = pd.DataFrame(recs)
    d["valor_RS_MWh"] = d.VlrComponenteTarifario.map(num).round(4)
    d = d[d.valor_RS_MWh != 0]
    d = d.rename(columns={"DscComponenteTarifario": "componente",
                          "DatInicioVigencia": "vigencia_ini",
                          "DscResolucaoHomologatoria": "resolucao"})
    return d[["vigencia_ini", "componente", "valor_RS_MWh", "resolucao"]].sort_values(
        ["vigencia_ini", "componente"])


def bandeiras():
    acion = pd.DataFrame(cacheado("bandeiras_acionamento", lambda: busca(RES_BAND_ACION, None, 200)))
    acion["adicional_RS_MWh"] = acion.VlrAdicionalBandeira.map(num)
    acion = acion.rename(columns={"DatCompetencia": "competencia",
                                  "NomBandeiraAcionada": "bandeira"})
    acion["competencia"] = acion.competencia.str[:7]
    acion = acion[["competencia", "bandeira", "adicional_RS_MWh"]].sort_values("competencia")

    adic = pd.DataFrame(cacheado("bandeiras_adicional", lambda: busca(RES_BAND_ADIC, None, 100)))
    adic["adicional_RS_MWh"] = adic.VlrAdicionalBandeiraRSMWh.map(num)
    adic = adic.rename(columns={"DatVigencia": "vigencia_ini",
                                "NomBandeiraAcionada": "bandeira",
                                "DscResolucao": "resolucao"})
    adic = adic[["vigencia_ini", "bandeira", "adicional_RS_MWh", "resolucao"]].sort_values(
        ["vigencia_ini", "bandeira"])
    return acion, adic


if __name__ == "__main__":
    DADOS.mkdir(parents=True, exist_ok=True)
    t = tarifas_copel()
    t.to_csv(DADOS / "copel_tarifas_historico.csv", index=False, encoding="utf-8-sig")
    print(f"copel_tarifas_historico.csv      {len(t):5d} linhas  "
          f"{t.vigencia_ini.min()} -> {t.vigencia_fim.max()}")

    c = componentes_b1()
    c.to_csv(DADOS / "copel_componentes_b1.csv", index=False, encoding="utf-8-sig")
    print(f"copel_componentes_b1.csv         {len(c):5d} linhas")

    acion, adic = bandeiras()
    acion.to_csv(DADOS / "bandeiras_mensal.csv", index=False, encoding="utf-8-sig")
    adic.to_csv(DADOS / "bandeiras_adicional.csv", index=False, encoding="utf-8-sig")
    print(f"bandeiras_mensal.csv             {len(acion):5d} meses   "
          f"{acion.competencia.min()} -> {acion.competencia.max()}")
    print(f"bandeiras_adicional.csv          {len(adic):5d} linhas")
