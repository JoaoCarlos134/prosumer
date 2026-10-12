"""io.aneel without the network: a fake CKAN datastore answers with records shaped like ANEEL's."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd
import pytest

from prosumer import provenance
from prosumer.economics import brazil
from prosumer.io import aneel


def _tariff(start: str, sub: str, mod: str, posto: str, tusd: str, te: str, **kw: str) -> dict[str, Any]:
    r = {
        "SigAgente": "COPEL-DIS",
        "DscBaseTarifaria": "Tarifa de Aplicação",
        "DatInicioVigencia": start,
        "DatFimVigencia": "2099-12-31",
        "DscSubGrupo": sub,
        "DscModalidadeTarifaria": mod,
        "DscSubClasse": "Residencial",
        "DscDetalhe": "Não se aplica",
        "NomPostoTarifario": posto,
        "VlrTUSD": tusd,
        "VlrTE": te,
        "DscREH": "REH TEST",
    }
    r.update(kw)
    return r


class FakeCKAN:
    """`datastore_search` with exact-match filters and limit/offset paging; `package_show` for components."""

    def __init__(self, tables: dict[str, list[dict[str, Any]]], package: list[dict[str, str]] | None = None):
        self.tables, self.package, self.calls = tables, package or [], []

    def __call__(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        self.calls.append((url, params))
        if url.endswith("package_show"):
            return {"success": True, "result": {"resources": self.package}}
        assert url == aneel.API + "datastore_search"
        rows = self.tables[params["resource_id"]]
        f = json.loads(params.get("filters", "{}"))
        rows = [r for r in rows if all(r.get(k) == v for k, v in f.items())]
        a, n = int(params["offset"]), int(params["limit"])
        return {"success": True, "result": {"records": rows[a : a + n], "total": len(rows)}}


def test_number_reads_brazilian_text() -> None:
    assert aneel.number("1.013,36") == 1013.36
    assert aneel.number(",00") == 0.0
    assert aneel.number("3,0620790000000001E-3") == pytest.approx(0.003062079)
    assert aneel.number(12) == 12.0


def test_tariffs_are_filtered_paged_and_carry_odbl() -> None:
    rows = [
        _tariff("2026-06-24", "B1", "Convencional", "Não se aplica", "457,17", "310,85"),
        _tariff("2026-06-24", "B1", "Convencional", "Não se aplica", "457,17", "30,20", DscDetalhe="SCEE"),
        _tariff("2026-06-24", "B1", "Branca", "Ponta", "896,95", "475,67"),
        _tariff("2026-06-24", "B1", "Azul", "Ponta", "1,00", "1,00"),
        _tariff("2026-06-24", "A4", "Convencional", "Não se aplica", "1,00", "1,00"),
        _tariff(
            "2026-06-24", "B1", "Convencional", "Não se aplica", "1,00", "1,00", DscSubClasse="Baixa Renda"
        ),
        _tariff("2026-06-24", "B1", "Convencional", "Não se aplica", "1,00", "1,00", SigAgente="CEMIG-D"),
    ]
    api = FakeCKAN({aneel.TARIFFS: rows})
    t = aneel.search(aneel.TARIFFS, {"SigAgente": "COPEL-DIS"}, get=api, page=2)
    assert len(t) == 6 and len(api.calls) == 3  # paged
    out = aneel.fetch_tariffs("COPEL-DIS", get=api)
    assert out[["modality", "posto", "tusd", "te"]].to_numpy().tolist() == [
        ["Branca", "Ponta", 896.95, 475.67],
        ["Convencional", "Não se aplica", 457.17, 310.85],
    ]
    p = provenance.of(out)
    assert p is not None and p.license == "ODbL-1.0" and "share-alike" in p.notes
    with pytest.raises(ValueError, match="No tariff"):
        aneel.fetch_tariffs("NOBODY", get=api)


def test_bandeiras_and_components_feed_a_tariff_book() -> None:
    monthly = [
        {"DatCompetencia": "2026-09-01", "NomBandeiraAcionada": "Amarela", "VlrAdicionalBandeira": "18,85"},
        {"DatCompetencia": "2026-10-01", "NomBandeiraAcionada": "Verde", "VlrAdicionalBandeira": ",00"},
    ]
    values = [
        {
            "DatVigencia": "2024-04-01",
            "NomBandeiraAcionada": "Amarela",
            "VlrAdicionalBandeiraRSMWh": "18,85",
            "DscResolucao": "REH nº 3.306/2024",
        }
    ]
    comp = [
        {
            "SigNomeAgente": "COPEL-DIS",
            "DscSubGrupoTarifario": "B1",
            "DscBaseTarifaria": "Tarifa de Aplicação",
            "DscModalidadeTarifaria": "Convencional",
            "DscSubClasseConsumidor": "Residencial",
            "DscDetalheConsumidor": "Não se aplica",
            "DatInicioVigencia": "2026-06-24",
            "DscComponenteTarifario": c,
            "VlrComponenteTarifario": v,
            "DscResolucaoHomologatoria": "REH 3.592",
        }
        for c, v in (("TUSD_FioB", "214,5356"), ("TE_ENERGIA", "271,6678"), ("TUSD_CCT", ",00"))
    ]
    api = FakeCKAN(
        {
            aneel.BANDEIRAS_MONTHLY: monthly,
            aneel.BANDEIRAS_VALUES: values,
            "comp-2026": comp,
            aneel.TARIFFS: [_tariff("2026-06-24", "B1", "Convencional", "Não se aplica", "457,17", "310,85")],
        },
        package=[{"name": "componentes-tarifarias-2026.csv", "id": "comp-2026"}],
    )
    band = aneel.fetch_bandeiras(get=api)
    assert band.to_numpy().tolist() == [["2026-09", "Amarela", 18.85], ["2026-10", "Verde", 0.0]]
    assert aneel.fetch_bandeira_values(get=api)["add"].tolist() == [18.85]
    c = aneel.fetch_components("COPEL-DIS", 2026, get=api)
    assert set(c["component"]) == {"TUSD_FioB", "TE_ENERGIA"}  # zero values dropped
    with pytest.raises(ValueError, match="resource"):
        aneel.fetch_components("COPEL-DIS", 2019, get=api)
    taxes = pd.DataFrame({"start": ["2024-03-18"], "icms": [0.19], "pis_cofins": [0.0925]})
    book = brazil.TariffBook(aneel.fetch_tariffs(get=api), band, taxes, aneel.fio_b(c), "COPEL-DIS")
    d = book.daily("2026-09-30", "2026-10-01")
    assert d["price"].tolist() == pytest.approx(
        [(457.17 + 310.85 + 18.85) / 1000 / (1 - 0.2825), (457.17 + 310.85) / 1000 / (1 - 0.2825)]
    )
    assert book.fio_b_value("2026-10-01") == pytest.approx(214.5356)
