"""io.aneel without the network: a fake CKAN datastore answers with records shaped like ANEEL's."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from aneel_fake import FakeCKAN
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


def test_records_repeated_with_a_new_id_are_kept_once() -> None:
    # regression (2026-10-16): ANEEL's datastore started returning every record twice, each with its own
    # `_id`; the book summed the two rows of each key and billed TUSD and TE at double
    row = _tariff("2017-06-24", "B1", "Convencional", "Não se aplica", "191,24", "249,32")
    api = FakeCKAN({aneel.TARIFFS: [{**row, "_id": 1}, {**row, "_id": 2}]})
    t = aneel.fetch_tariffs("COPEL-DIS", get=api)
    assert t[["tusd", "te"]].to_numpy().tolist() == [[191.24, 249.32]]
    bands = pd.DataFrame({"month": ["2018-03"], "flag": ["Verde"], "add": [0.0]})
    taxes = pd.DataFrame({"start": ["1900-01-01"], "icms": [0.29], "pis_cofins": [0.0925]})
    assert brazil.TariffBook(t, bands, taxes).base("2018-03-15") == pytest.approx((191.24, 249.32))
    # neighbour: the same in the monthly bandeiras (a doubled month would double the surcharge)
    month = {
        "DatCompetencia": "2026-09-01",
        "NomBandeiraAcionada": "Amarela",
        "VlrAdicionalBandeira": "18,85",
    }
    api = FakeCKAN({aneel.BANDEIRAS_MONTHLY: [{**month, "_id": 7}, {**month, "_id": 8}]})
    assert aneel.fetch_bandeiras(get=api).to_numpy().tolist() == [["2026-09", "Amarela", 18.85]]
    # records that differ in anything but `_id` are all kept
    other = {**row, "VlrTE": "250,00", "_id": 3}
    api = FakeCKAN({aneel.TARIFFS: [{**row, "_id": 1}, other]})
    assert len(aneel.search(aneel.TARIFFS, get=api)) == 2


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


FIXTURE = Path(__file__).resolve().parent / "fixtures" / "aneel_distributors.json"
# SigAgente in ANEEL's data: Enel SP is still "ELETROPAULO"
DISTRIBUTORS = {"COPEL-DIS": 2026, "CEMIG-D": 2026, "ELETROPAULO": 2026, "LIGHT SESA": 2026}


@pytest.mark.parametrize("agent", list(DISTRIBUTORS))
def test_supported_distributors_from_a_live_fixture(agent: str) -> None:
    """Copel, Cemig, Enel SP and Light: the latest B1 residential vigencia, its TUSD_FioB and the last
    bandeiras, as ANEEL's API returned them on 2026-10-12 (`tests/fixtures/aneel_distributors.json`, an ODbL
    extract). This checks the reader and the price arithmetic on each distributor's real rows; there is no
    real bill of these distributors to check the result against. The tax rates are illustrative user
    inputs (ICMS and PIS/COFINS are not built in)."""
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    comps = [r for r in data["components"] if r["SigNomeAgente"] == agent]
    api = FakeCKAN(
        {aneel.TARIFFS: data["tariffs"], aneel.BANDEIRAS_MONTHLY: data["bandeiras"], "comp": comps},
        package=[{"name": f"componentes-tarifarias-{DISTRIBUTORS[agent]}.csv", "id": "comp"}],
    )
    t = aneel.fetch_tariffs(agent, get=api)
    assert len(t) == 4 and set(t["posto"]) == {"Não se aplica", "Ponta", "Intermediário", "Fora ponta"}
    conv = t[t["modality"] == "Convencional"].iloc[0]
    fio = aneel.fio_b(aneel.fetch_components(agent, DISTRIBUTORS[agent], get=api))
    taxes = pd.DataFrame({"start": ["2020-01-01"], "icms": [0.19], "pis_cofins": [0.0925]})
    book = brazil.TariffBook(t, aneel.fetch_bandeiras(get=api), taxes, fio, agent)
    month = "2026-09"  # inside every vigencia of the fixture; yellow flag, 18.85 R$/MWh
    p = (conv["tusd"] + conv["te"] + 18.85) / 1000 / (1 - 0.2825)
    flat = brazil.tariff(book, month)
    assert flat.prices["flat"] == pytest.approx(p)
    gd2 = brazil.tariff(book, month, gd="GD II")  # 2026: 60% of Fio B, ICMS on the charge
    assert gd2.export_price == pytest.approx(p - 0.6 * float(fio["value"].iloc[0]) / 1000 / 0.81)
    branca = brazil.tariff(book, month, modality="Branca", peak_start="18:00")
    assert branca.prices["ponta"] > branca.prices["intermediario"] > branca.prices["fora_ponta"]
    assert branca.prices["fora_ponta"] < p < branca.prices["ponta"]
