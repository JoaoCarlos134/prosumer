"""Brazilian tariffs from ANEEL's open data (CKAN datastore API): homologated TUSD/TE, bandeiras, components.

Port of the project's `legado/ia_solar/analise/tarifas/scripts/baixa_tarifas_aneel.py`. ANEEL's PDFs of the
homologation resolutions sit behind Cloudflare and refuse scripts (403); this API is the same source and the
only automatable route. Datasets (https://dadosabertos.aneel.gov.br, checked on 2026-10-12):

- `tarifas-distribuidoras-energia-eletrica`: TUSD and TE (R$/MWh, no tax) per distributor, vigencia,
  subgroup, modality, class, subclass, detail ("Não se aplica" = the full tariff; "SCEE" = what is charged
  on compensated energy before the GD discounts of each homologation resolution) and posto;
- `bandeiras-tarifarias`: the flag of each month ("Acionamento") and the values of each flag by vigencia;
- `componentes-tarifarias`: the breakdown of TUSD and TE (e.g. `TUSD_FioB`, the base of the GD II charge of
  Lei 14.300 art. 27), one resource per year.

**Licence**: the three datasets declare the Open Data Commons Open Database License (ODbL 1.0) in their
CKAN metadata (`license_id = odc-odbl`, checked 2026-10-12): use is free, with attribution, and a database
derived from them that is redistributed must stay under ODbL (share-alike). The functions attach that
provenance to their result.

**Distributors** (`SigAgente`): any of the ~116 in the dataset works; tested on a fixture of live records
(2026-10-12, `tests/fixtures/aneel_distributors.json`): "COPEL-DIS", "CEMIG-D", "ELETROPAULO" (Enel SP keeps
its old name in this dataset) and "LIGHT SESA". The fixture checks the reading and the arithmetic; there was
no real bill of those distributors to check the result against.

Numbers come as Brazilian text ("1.013,36", ",00") or scientific notation ("3,06E-3"); `number` reads both.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from typing import Any

import pandas as pd

from ..provenance import Provenance, attach, today
from . import _http

API = "https://dadosabertos.aneel.gov.br/api/3/action/"
TARIFFS = "fcf2906c-7c32-4b9b-a637-054e7a5234f4"
BANDEIRAS_MONTHLY = "0591b8f6-fe54-437b-b72b-1aa2efd46e42"
BANDEIRAS_VALUES = "5879ca80-b3bd-45b1-a135-d9b77c1d5b36"
COMPONENTS_PACKAGE = "componentes-tarifarias"
PAGE = 1000

Getter = Callable[[str, dict[str, Any]], dict[str, Any]]


def number(s: Any) -> float:
    """'1.013,36' -> 1013.36; ',00' -> 0.0; '3,06E-3' -> 0.00306; numbers pass through."""
    if isinstance(s, int | float):
        return float(s)
    t = str(s).strip()
    if "e" in t.lower():
        return float(t.replace(",", "."))
    return float(t.replace(".", "").replace(",", ".")) if t else float("nan")


def search(
    resource_id: str, filters: dict[str, Any] | None = None, *, get: Getter | None = None, page: int = PAGE
) -> list[dict[str, Any]]:
    """All records of a datastore resource matching `filters` (exact match per field), page by page.

    Records identical in everything but the datastore's `_id` are kept once: on 2026-10-16 the tariff
    dataset returned every record twice (8,844 records, 4,422 distinct), and the book, which adds rows of the
    same key, billed TUSD and TE at double (found by the real-bill pilot).
    """
    get = get or _http.get_json
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    offset = 0
    while True:
        params: dict[str, Any] = {"resource_id": resource_id, "limit": page, "offset": offset}
        if filters:
            params["filters"] = json.dumps(filters, ensure_ascii=False)
        r = get(API + "datastore_search", params)
        if not r.get("success", True):
            raise RuntimeError(f"ANEEL API error: {r.get('error')}")
        res = r["result"]
        for rec in res["records"]:
            key = json.dumps({k: v for k, v in rec.items() if k != "_id"}, sort_keys=True, default=str)
            if key not in seen:
                seen.add(key)
                out.append(rec)
        offset += page
        if offset >= int(res["total"]) or not res["records"]:
            return out


def fetch_tariffs(
    distributor: str = "COPEL-DIS",
    *,
    subgroups: Iterable[str] = ("B1",),
    modalities: Iterable[str] = ("Convencional", "Branca"),
    subclass: str = "Residencial",
    detail: str = "Não se aplica",
    base: str = "Tarifa de Aplicação",
    get: Getter | None = None,
) -> pd.DataFrame:
    """Homologated TUSD/TE of one distributor (`SigAgente`, e.g. "COPEL-DIS"), as `TariffBook.tariffs`:
    `start, end, subgroup, modality, posto, tusd, te, resolution` (R$/MWh, no tax).

    Default filters reproduce the legacy download: the applied tariff (`base`), the full tariff without SCEE
    (`detail`), residential subclass (rows whose subclass is "Não se aplica" are kept too, as the legacy
    script did: older vigencias have no subclass).
    """
    recs = search(TARIFFS, {"SigAgente": distributor, "DscBaseTarifaria": base}, get=get)
    if not recs:
        raise ValueError(f"No tariff records for {distributor!r} (check SigAgente, e.g. 'COPEL-DIS')")
    d = pd.DataFrame(recs)
    d = d[d["DscSubGrupo"].isin(list(subgroups)) & d["DscModalidadeTarifaria"].isin(list(modalities))]
    d = d[(d["DscDetalhe"] == detail) & d["DscSubClasse"].isin([subclass, "Não se aplica"])]
    out = pd.DataFrame(
        {
            "start": pd.to_datetime(d["DatInicioVigencia"]),
            "end": pd.to_datetime(d["DatFimVigencia"]),
            "subgroup": d["DscSubGrupo"],
            "modality": d["DscModalidadeTarifaria"],
            "posto": d["NomPostoTarifario"],
            "tusd": d["VlrTUSD"].map(number),
            "te": d["VlrTE"].map(number),
            "resolution": d["DscREH"],
        }
    ).sort_values(["start", "subgroup", "modality", "posto"], kind="stable")
    return attach(out.reset_index(drop=True), provenance("tarifas-distribuidoras-energia-eletrica"))


def fetch_bandeiras(*, get: Getter | None = None) -> pd.DataFrame:
    """The flag of each month, as `TariffBook.bandeiras`: `month` ("YYYY-MM"), `flag`, `add` (R$/MWh)."""
    d = pd.DataFrame(search(BANDEIRAS_MONTHLY, get=get, page=200))
    out = pd.DataFrame(
        {
            "month": d["DatCompetencia"].astype(str).str[:7],
            "flag": d["NomBandeiraAcionada"],
            "add": d["VlrAdicionalBandeira"].map(number),
        }
    ).sort_values("month")
    return attach(out.reset_index(drop=True), provenance("bandeiras-tarifarias"))


def fetch_bandeira_values(*, get: Getter | None = None) -> pd.DataFrame:
    """The surcharge of each flag by vigencia: `start, flag, add` (R$/MWh), `resolution`."""
    d = pd.DataFrame(search(BANDEIRAS_VALUES, get=get, page=200))
    out = pd.DataFrame(
        {
            "start": pd.to_datetime(d["DatVigencia"]),
            "flag": d["NomBandeiraAcionada"],
            "add": d["VlrAdicionalBandeiraRSMWh"].map(number),
            "resolution": d["DscResolucao"],
        }
    ).sort_values(["start", "flag"])
    return attach(out.reset_index(drop=True), provenance("bandeiras-tarifarias"))


def fetch_components(
    distributor: str = "COPEL-DIS",
    year: int = 2026,
    *,
    subgroup: str = "B1",
    modality: str = "Convencional",
    subclass: str = "Residencial",
    detail: str = "Não se aplica",
    get: Getter | None = None,
) -> pd.DataFrame:
    """Breakdown of the applied TUSD and TE of one year's vigencias: `start, component, value` (R$/MWh),
    `resolution`. The component `TUSD_FioB` is what `TariffBook.fio_b` needs (GD II). The resource of each
    year is found in the package listing (`package_show`)."""
    get = get or _http.get_json
    pkg = get(API + "package_show", {"id": COMPONENTS_PACKAGE})["result"]
    want = f"componentes-tarifarias-{year}.csv"
    ids = [r["id"] for r in pkg["resources"] if r.get("name") == want]
    if not ids:
        raise ValueError(f"No components resource for {year} ({want})")
    f = {
        "SigNomeAgente": distributor,
        "DscSubGrupoTarifario": subgroup,
        "DscBaseTarifaria": "Tarifa de Aplicação",
        "DscModalidadeTarifaria": modality,
        "DscSubClasseConsumidor": subclass,
        "DscDetalheConsumidor": detail,
    }
    d = pd.DataFrame(search(ids[0], f, get=get, page=500))
    if d.empty:
        raise ValueError(f"No components for {distributor} {subgroup} {modality} in {year}")
    out = pd.DataFrame(
        {
            "start": pd.to_datetime(d["DatInicioVigencia"]),
            "component": d["DscComponenteTarifario"],
            "value": d["VlrComponenteTarifario"].map(number),
            "resolution": d["DscResolucaoHomologatoria"],
        }
    )
    out = out[out["value"] != 0].sort_values(["start", "component"]).reset_index(drop=True)
    return attach(out, provenance(COMPONENTS_PACKAGE))


def fio_b(components: pd.DataFrame) -> pd.DataFrame:
    """`start, value` of `TUSD_FioB` from `fetch_components` (for `TariffBook.fio_b`)."""
    c = components[components["component"] == "TUSD_FioB"]
    return c[["start", "value"]].reset_index(drop=True)


def provenance(dataset: str, retrieved: str | None = None) -> Provenance:
    """ANEEL open data, ODbL 1.0 (declared in the dataset's CKAN metadata, checked 2026-10-12)."""
    return Provenance(
        source=f"ANEEL open data, dataset {dataset}",
        license="ODbL-1.0",
        citation="Agência Nacional de Energia Elétrica (ANEEL), Dados Abertos, https://dadosabertos.aneel.gov.br/",
        url=f"https://dadosabertos.aneel.gov.br/dataset/{dataset}",
        retrieved=retrieved or today(),
        notes="ODbL: attribute ANEEL; a redistributed derived database must stay under ODbL (share-alike)",
    )


__all__ = [
    "API",
    "BANDEIRAS_MONTHLY",
    "BANDEIRAS_VALUES",
    "TARIFFS",
    "fetch_bandeira_values",
    "fetch_bandeiras",
    "fetch_components",
    "fetch_tariffs",
    "fio_b",
    "number",
    "provenance",
    "search",
]
