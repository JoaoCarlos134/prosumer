"""prosumer.i18n: notes in English or Portuguese, the catalog against the code, and the app's page in pt."""

from __future__ import annotations

import ast
import copy
import datetime as dt
import json
import pickle
from pathlib import Path
from typing import Any

import pytest

from prosumer import app, i18n
from prosumer.i18n import Note
from prosumer.i18n.pt import PT
from test_app import SITE, _consumption_csv, _pv_csv, _services

SRC = Path(__file__).resolve().parents[1] / "src" / "prosumer"


def test_a_note_is_its_english_text_and_renders_in_portuguese() -> None:
    n = Note("The output is biased by {bias:+.0%} of the mean (MBE).", bias=-0.123)
    assert n == "The output is biased by -12% of the mean (MBE)." and isinstance(n, str)
    assert n.text("pt") == "A saída tem um viés de -12% da média (MBE)."
    assert n.text("en") == n and type(n.text("en")) is str
    with pytest.raises(ValueError, match="lang must be one of"):
        n.text("fr")


def test_portuguese_numbers_take_the_decimal_comma_and_dates_are_day_first() -> None:
    n = Note("{kwh:.1f} kWh of credits expired unused.", kwh=1234.56)
    assert (
        n == "1234.6 kWh of credits expired unused."
        and n.text("pt") == "1234,6 kWh de créditos expiraram sem uso."
    )
    d = Note("No tax rate in force on {day}", day=dt.date(2026, 3, 1))
    assert (
        d == "No tax rate in force on 2026-03-01"
        and d.text("pt") == "Nenhuma alíquota de imposto vigente em 01/03/2026"
    )
    grouped = Note(
        "{n} hours have no forecast (never seen in the recent data) and are left out of the daily "
        "totals and of the load windows.",
        n=7,
    )
    assert grouped.text("pt").startswith("7 horas")  # an int stays an int


def test_fragments_lists_errors_and_joins_render_in_the_same_language() -> None:
    later = Note("later")
    n = Note(
        "Series {uid}: the production follows the clouds {hours:.1f} h {side} than the weather data "
        "(90% interval {low:+.1f} to {high:+.1f} h). A fraction of an hour usually means intervals labelled "
        "by their end or a logger clock that drifted; check the source before using the weather as an "
        "input.",
        uid="a",
        hours=0.5,
        side=later,
        low=0.2,
        high=0.8,
    )
    assert "0.5 h later" in n and "0,5 h mais tarde" in n.text("pt") and "+0,2 a +0,8 h" in n.text("pt")
    listed = Note(
        "Weather models left out from the first day their GHI exceeds what the sun can give "
        "(> {factor:g} x clear sky + {offset:.0f} W/m2 in some hour): {models}.",
        factor=1.1,
        offset=50,
        models=[Note("{model} from {day}", model="gfs", day=dt.date(2026, 1, 2))],
    )
    assert listed.endswith("gfs from 2026-01-02.") and listed.text("pt").endswith(
        "gfs a partir de 02/01/2026."
    )
    error = ValueError(Note("No hours to bill"))
    assert str(error) == "No hours to bill" and i18n.message(error, "pt") == "Nenhuma hora a faturar"
    assert i18n.message(KeyError("x"), "pt") == "'x'"  # a plain error: as it is
    wrapped = Note("Economics left out: {error}", error=error)
    assert wrapped.text("pt") == "Conta deixada de fora: Nenhuma hora a faturar"
    joined = Note.join([Note("native step {step}", step="1h"), "plain"])
    assert joined == "native step 1h; plain" and joined.text("pt") == "passo original 1h; plain"
    assert joined.parts == [Note("native step {step}", step="1h"), "plain"] and Note("day").parts == ["day"]


def test_a_note_survives_copy_pickle_replace_and_dict_keys() -> None:
    n = Note(
        "file {file}: {why}, unit {unit}, kind {kind}", file="tmp.csv", why="x", unit="kWh", kind="interval"
    )
    for c in (copy.copy(n), copy.deepcopy(n), pickle.loads(pickle.dumps(n))):
        assert isinstance(c, Note) and c == n and c.text("pt") == n.text("pt")
    r = i18n.replace(n, "tmp.csv", "meter.csv")
    assert (
        isinstance(r, Note)
        and r.startswith("file meter.csv")
        and r.text("pt").startswith("arquivo meter.csv")
    )
    assert i18n.replace("a tmp.csv", "tmp.csv", "b") == "a b"
    pending = {Note("diagnostics"): Note("Uncertain (roof fit, see above).")}
    assert pending["diagnostics"] and i18n.translate(pending, "pt") == {
        "diagnóstico": "Incerto (ajuste do telhado, veja acima)."
    }


def test_a_template_missing_from_the_catalog_falls_back_to_english_unless_strict() -> None:
    n = Note("Not in any catalog: {x}", x=1.5)
    assert n.text("pt") == "Not in any catalog: 1,5"
    with pytest.raises(KeyError, match="No 'pt' translation"):
        n.text("pt", strict=True)
    assert Note("{a}; {b}", a=Note("later"), b=2.5).text("pt", strict=True) == "mais tarde; 2,5"  # neutral


def _templates() -> dict[str, str]:
    """Every `Note("...")` of the library: template -> where (the first argument must be a literal)."""
    found: dict[str, str] = {}
    for path in sorted(SRC.rglob("*.py")):
        if "i18n" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Note":
                arg = node.args[0] if node.args else None
                where = f"{path.relative_to(SRC)}:{node.lineno}"
                assert isinstance(arg, ast.Constant) and isinstance(arg.value, str), f"not a literal: {where}"
                found.setdefault(arg.value, where)
    return found


def test_every_template_in_the_code_is_in_the_catalog_with_the_same_placeholders() -> None:
    code = _templates()
    missing = [f"{w}: {t!r}" for t, w in code.items() if t not in PT and not i18n._neutral(t)]
    assert not missing, "no Portuguese for:\n" + "\n".join(missing)
    stale = [t for t in PT if t not in code]
    assert not stale, "in the catalog, not in the code:\n" + "\n".join(stale)
    for en, pt in PT.items():
        assert i18n.placeholders(en) == i18n.placeholders(pt), en
        pt.format_map({k: 0 for k in i18n.placeholders(pt)})  # a well-formed template


def _prose(d: dict[str, Any]) -> list[tuple[str, Any]]:
    """The texts for the person in `Result.to_dict(lang=None)`: (where, value)."""
    out: list[tuple[str, Any]] = [(f"notes[{i}]", n) for i, n in enumerate(d["notes"])]
    out += [(f"log[{i}]", n) for i, n in enumerate(d["log"])]
    out += [(f"read.{q}.how", r["how"]) for q, r in d["read"].items()]
    for q, o in d["outlooks"].items():
        out += [(f"outlooks.{q}.notes", n) for n in o["notes"]]
    rep = d["report"]
    out += [("report.notes", n) for n in rep["notes"]]
    out += [("report.pending key", k) for k in rep["pending"]] + [
        ("report.pending", v) for v in rep["pending"].values()
    ]
    if rep["diagnostics"]:
        out += [("report.diagnostics.notes", n) for n in rep["diagnostics"]["notes"]]
    if rep["economics"]:
        out += [("report.economics.notes", n) for n in rep["economics"]["notes"]]
        out.append(("report.economics.tariff", rep["economics"]["tariff"]))
    if d["pricing"] is not None:
        out.append(("pricing", d["pricing"]))
    return out


def _check_page(r: app.Result) -> dict[str, Any]:
    raw = r.to_dict(lang=None)
    plain = [w for w, v in _prose(raw) if not isinstance(v, Note)]
    assert not plain, f"texts that are not notes: {plain}"
    pt = i18n.translate(raw, "pt", strict=True)  # raises on a note without Portuguese
    assert json.loads(r.to_json("pt")) == json.loads(json.dumps(pt, allow_nan=False))
    assert r.to_dict() == json.loads(r.to_json())  # English by default, plain text
    return pt


def test_the_app_page_in_portuguese_consumption_with_a_flat_price() -> None:
    files = {"consumption": (_consumption_csv("2024-01-01", 42), "medidor.csv")}
    price = {"kind": "tou", "peak_hours": "18-21", "peak_price": "1,2", "offpeak_price": 0.6}
    r = app.run({**SITE, "days": 3, "models": "naive", "price": price}, files, services=_services())
    pt = _check_page(r)
    assert pt["log"][0].startswith("Local digitado: -25,43; -49,27.")
    assert pt["read"]["consumption"]["how"].startswith("arquivo medidor.csv: coluna 'consumo (kWh)'")
    assert "por horário (ponta das 18:00 às 21:00 nos dias úteis)" in pt["pricing"]
    assert pt["report"]["pending"]["conta de energia"].startswith("Não modelado")  # the bill was made
    assert any(
        n.startswith("A saída (`median`) é a mediana só das 3 previsões ingênuas")
        for n in pt["report"]["notes"]
    )


def test_the_app_page_in_portuguese_pv_and_consumption_with_a_brazilian_price() -> None:
    files = {
        "generation": (_pv_csv("2026-07-01", 60), "inversor.csv"),
        "consumption": (_consumption_csv("2026-07-01", 60), "medidor.csv"),
    }
    price = {"kind": "brazil", "distributor": "COPEL-DIS", "icms": "0,19", "pis_cofins": 0.0925, "gd": "GD I"}
    r = app.run(
        {**SITE, "days": 3, "models": "naive", "price": price}, files, services=_services("2026-08-30")
    )
    pt = _check_page(r)
    assert pt["report"]["diagnostics"] is not None and pt["report"]["economics"] is not None
    assert any(line == "Previsão do tempo baixada: 2 modelos." for line in pt["log"])
    assert any(
        n.startswith("COSIP/CIP (contribuição de iluminação pública)")
        for n in pt["report"]["economics"]["notes"]
    )


def test_errors_of_the_app_are_notes_with_portuguese() -> None:
    files = {"consumption": (_consumption_csv("2024-01-01", 42), "m.csv")}
    cases = [
        ({**SITE, "days": 99}, files, "days deve estar entre 1 e 35"),
        ({**SITE, "load_kw": "dois"}, files, "load_kw: 'dois' não é um número"),
        (
            {**SITE, "price": {"kind": "tou", "peak_hours": "25-3", "peak_price": 1, "offpeak_price": 1}},
            files,
            "Horário de ponta '25-3'",
        ),
        (
            {**SITE, "price": {"kind": "brazil", "icms": 19, "pis_cofins": 0.09}},
            files,
            "ICMS e PIS/COFINS são frações",
        ),
        (SITE, {"consumption": (b"", "m.csv")}, "Nenhum arquivo recebido"),
        (
            SITE,
            {"consumption": (b"when,what\nx,y\nz,w\n", "m.csv")},
            "Nenhuma coluna de datas e horas encontrada",
        ),
    ]
    for request, given, pt in cases:
        with pytest.raises(ValueError) as caught:
            app.run(request, given, services=_services())
        assert isinstance(i18n.as_note(caught.value), Note), caught.value
        assert i18n.message(caught.value, "pt", strict=True).startswith(pt), i18n.message(caught.value, "pt")


def test_a_note_in_a_table_cell_is_kept_and_translated() -> None:
    rows = [{"tariff": Note("{n} time-of-use blocks", n=2), "price": 0.8}]
    kept = i18n.frame(rows)  # pandas 3 makes a text column its string type, which keeps only the English
    assert i18n.translate(kept.to_dict(orient="records"), "pt") == [
        {"tariff": "2 blocos por horário", "price": 0.8}
    ]
    assert kept["price"].dtype == float
