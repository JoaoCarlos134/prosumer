"""Economics for the app: `analyze(economics=...)`, `Plan`, `brazil.Setup`, `TariffBook.from_aneel` and
`windows_by_cost`, on synthetic sites whose bill can be worked out by hand (no network: ANEEL answers from the
fixture of 2026-10-12)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from aneel_fake import from_fixture
from prosumer import EnergySeries, analysis, analyze, data, economics
from prosumer.economics import Plan, Tariff, brazil
from prosumer.outlook import Outlook

TZ = "Etc/GMT+3"
LEGACY = Path(__file__).resolve().parents[1] / "legado" / "ia_solar" / "analise" / "tarifas" / "dados"
TOU = Tariff(
    prices={"peak": 0.40, "day": 0.20, "night": 0.10},
    weekday={h: "peak" if 17 <= h < 21 else "day" if 7 <= h < 17 else "night" for h in range(24)},
    weekend=dict.fromkeys(range(24), "night"),
    export_price=0.05,
    fixed=10.0,
)
GROSS = 1 / (1 - 0.19 - 0.0925)  # the typed ICMS and PIS/COFINS of the Brazilian tests


def _series(values: np.ndarray, start: str, quantity: str) -> EnergySeries:
    ds = pd.date_range(start, periods=len(values), freq="h", tz=TZ)
    return EnergySeries.from_dataframe(
        pd.DataFrame({"unique_id": "site", "ds": ds, "y": values}),
        unit="kWh",
        quantity=quantity,  # type: ignore[arg-type]
        tz=TZ,
        freq="h",
    )


def _site(days: int, start: str, pv_kwh: float = 3.0) -> tuple[EnergySeries, EnergySeries]:
    """1 kWh of load every hour; `pv_kwh` of PV in each of the hours 10-13."""
    hours = days * 24
    pv = np.where(np.isin(np.arange(hours) % 24, [10, 11, 12, 13]), pv_kwh, 0.0)
    return _series(np.ones(hours), start, "consumption"), _series(pv, start, "generation")


# ---------------------------------------------------------------------- analyze, core tariffs
def test_time_of_use_bill_of_a_consumption_series_by_hand() -> None:
    """January 2025: 23 weekdays (4 h peak at 0.40, 10 h day at 0.20, 10 h night at 0.10 = 4.60 a day) and
    8 weekend days (24 h at 0.10 = 2.40): 23 x 4.60 + 8 x 2.40 + 10 fixed = 135.00. Too short for the
    forecast check, which is skipped: the bill does not depend on it."""
    load, _ = _site(31, "2025-01-01")
    r = analyze(load, economics=TOU)
    assert r.forecast is None and r.economics is not None
    e = r.economics
    assert e.monthly["total"].tolist() == pytest.approx([135.0])
    blocks = e.by_block.set_index("block")["grid_import"]
    assert blocks.to_dict() == pytest.approx({"day": 230.0, "night": 422.0, "peak": 92.0})
    t = e.totals.iloc[0]
    assert (t["months"], t["complete_months"]) == (1, 1)
    assert t["mean_month"] == pytest.approx(135.0) and t["savings"] == pytest.approx(0.0)
    assert e.currency == "EUR" and "3 time-of-use blocks" in e.tariff
    assert r.pending["economics"] == analysis.ECONOMICS_LEFT
    assert r.provenance is not None
    row = r.provenance.set_index("role").loc["tariff"]
    assert row["license"] == "n/a" and "typed by the user" in row["source"]
    md = r.to_markdown()
    assert "## Economics" in md and "### By tariff block" in md and "| site | 2025-01 |" in md
    json.dumps(r.to_dict())


def test_generation_with_consumption_gives_the_savings_by_hand() -> None:
    """Net billing, 3 kWh of PV in hours 10-13 against 1 kWh of load: each weekday the PV saves 4 day-block
    kWh (0.80), each weekend day 4 night kWh (0.40), so 23 x 0.80 + 8 x 0.40 = 21.60 less import; the 8 kWh
    exported each day earn 31 x 8 x 0.05 = 12.40. Bill 135.00 - 21.60 - 12.40 = 101.00, savings 34.00."""
    load, pv = _site(31, "2025-01-01")
    plan = Plan(TOU, scheme="net_billing")
    r = analyze(pv, economics=plan, consumption=load)
    assert r.economics is not None
    m = r.economics.monthly.iloc[0]
    assert (m["total"], m["without_pv"], m["savings"]) == pytest.approx((101.0, 135.0, 34.0))
    assert m["export"] == pytest.approx(31 * 8)
    # the same from the consumption side, PV as `generation=`
    r2 = analyze(load, economics=plan, generation=pv)
    assert r2.economics is not None
    assert r2.economics.monthly["total"].tolist() == pytest.approx([101.0])
    # the second series and the tariff are listed as inputs
    assert r.provenance is not None
    assert list(r.provenance["role"]) == ["series", "series", "tariff"]


def test_generation_alone_cannot_be_billed() -> None:
    _, pv = _site(31, "2025-01-01")
    r = analyze(pv, economics=TOU)
    assert r.economics is None
    assert any("needs the household's consumption" in n for n in r.notes)
    assert r.pending["economics"].startswith("Economics left out")
    with pytest.raises(ValueError, match="consumption="):
        analyze(pv, economics=TOU, generation=pv)
    # without economics the extra series is ignored, and said so
    r0 = analyze(_site(31, "2025-01-01")[0], generation=pv)
    assert r0.economics is None and any("ignored" in n for n in r0.notes)


def test_months_with_gaps_and_partial_months_are_not_the_expected_bill() -> None:
    """Data from 10 January to 31 March, with a day missing in March: January starts late (coverage 1, but
    not a whole month) and March has a gap, so only February is a complete month: its bill, 28 x 24 x 0.25 +
    5, is the expected monthly bill."""
    days = 22 + 28 + 31
    y = np.ones(days * 24)
    y[(22 + 28 + 10) * 24 : (22 + 28 + 11) * 24] = np.nan  # 11 March
    r = analyze(_series(y, "2025-01-10", "consumption"), test_days=80, economics=Tariff.flat(0.25, fixed=5.0))
    assert r.economics is not None
    t = r.economics.totals.iloc[0]
    assert (t["months"], t["complete_months"]) == (3, 1)
    assert t["mean_month"] == pytest.approx(28 * 24 * 0.25 + 5.0)
    m = r.economics.monthly.set_index(r.economics.monthly["month"].dt.month)
    assert m.loc[3, "consumption"] == pytest.approx(30 * 24) and m.loc[3, "coverage"] < 1
    assert any("missing hours" in n for n in r.economics.notes)


def test_no_complete_month_says_so() -> None:
    r = analyze(_series(np.ones(20 * 24), "2025-01-05", "consumption"), economics=Tariff.flat(0.2))
    assert r.economics is not None and np.isnan(r.economics.totals["mean_month"].iloc[0])
    assert any("No month with every hour" in n for n in r.economics.notes)


def test_house_report_with_economics_keeps_every_other_section() -> None:
    r = analyze(data.example_house(n_series=2, days=60), test_days=21, economics=Tariff.flat(0.3))
    assert r.forecast is not None and r.economics is not None
    assert list(r.economics.totals["unique_id"]) == ["house_1", "house_2"]
    assert set(r.pending) == set(analysis.PENDING)


# ---------------------------------------------------------------------- analyze, Brazil
def _copel(**kw: object) -> brazil.TariffBook:
    return brazil.TariffBook.from_aneel(
        "COPEL-DIS", icms=0.19, pis_cofins=0.0925, fio_b_years=[2026], get=from_fixture(), **kw
    )


def test_from_aneel_builds_a_book_with_its_licence() -> None:
    book = _copel()
    assert book.distributor == "COPEL-DIS"
    assert book.fio_b_value("2026-08-01") == pytest.approx(214.5356, abs=1e-4)
    licences = {p.license for p in book.provenance}
    assert "ODbL-1.0" in licences and "n/a" in licences  # ANEEL data and the typed taxes
    assert any("typed by the user" in p.source and "19.00%" in p.notes for p in book.provenance)
    with pytest.raises(ValueError, match="ICMS"):
        brazil.TariffBook.from_aneel("COPEL-DIS", icms=0.8, pis_cofins=0.3, get=from_fixture())


def test_brazilian_conventional_bill_in_analyze_by_hand() -> None:
    """Copel B1 conventional from 24/6/2026 (TUSD 457.17 + TE 310.85 R$/MWh), August 2026 yellow flag (18.85),
    ICMS 19% and PIS/COFINS 9.25% typed: 744 kWh x 0.78687 / 0.7175 R$/kWh."""
    load, _ = _site(31, "2026-08-01")
    r = analyze(load, economics=brazil.Setup(book=_copel()))
    assert r.economics is not None
    total = 744 * (457.17 + 310.85 + 18.85) / 1000 * GROSS
    assert r.economics.monthly["total"].tolist() == pytest.approx([total])
    assert r.economics.totals["mean_month"].tolist() == pytest.approx([total])
    assert r.economics.currency == "BRL" and "COPEL-DIS B1 Convencional" in r.economics.tariff
    assert any("COSIP" in n for n in r.economics.notes)
    assert r.provenance is not None
    tariff_rows = r.provenance[r.provenance["role"] == "tariff"]
    assert "ODbL-1.0" in set(tariff_rows["license"])
    assert r.economics.provenance is not None and len(r.economics.provenance) == len(tariff_rows)
    assert "ODbL-1.0" in r.to_markdown()


def test_brazilian_gd_ii_in_analyze_is_brazil_bill() -> None:
    """GD II with PV: the section is `brazil.bill` with the same arguments, and the defaults decided by the
    author (after_2028 'tusd', gd2_minimum 'ren_655I', ICMS exempt 'all') are the setup's."""
    load, pv = _site(61, "2026-07-01", pv_kwh=4.0)
    setup = brazil.Setup(book=_copel(), gd="GD II", connection="monofasico")
    assert (setup.after_2028, setup.gd2_minimum, setup.icms_exempt_compensated) == ("tusd", "ren_655I", "all")
    r = analyze(pv, economics=setup, consumption=load, test_days=90)
    assert r.economics is not None
    direct = brazil.bill(load, pv, book=_copel(), gd="GD II", connection="monofasico")
    pd.testing.assert_frame_equal(r.economics.monthly, direct.monthly)
    assert (r.economics.monthly["savings"] > 0).all()
    assert (r.economics.monthly["charge_share"] == 0.6).all()  # 2026: 60% of the Fio B
    assert r.economics.scheme == "SCEE (Lei 14.300)"


def test_brazilian_cases_that_cannot_be_billed_leave_a_note() -> None:
    load, pv = _site(31, "2026-08-01")
    branca = brazil.Setup(book=_copel(), modality="Branca", peak_start="18:00", gd="GD II")
    r = analyze(pv, economics=branca, consumption=load)
    assert r.economics is None and any("Tarifa branca with micro-generation" in n for n in r.notes)
    early, _ = _site(31, "2025-01-01")  # before the fixture's vigencia
    r2 = analyze(early, economics=brazil.Setup(book=_copel()))
    assert r2.economics is None and any("Economics left out" in n for n in r2.notes)


@pytest.mark.skipif(not (LEGACY / "copel_tarifas_historico.csv").exists(), reason="legacy tariff CSVs absent")
def test_legacy_book_in_analyze() -> None:
    load, _ = _site(59, "2018-01-01")
    book = brazil.TariffBook.from_legacy(LEGACY)
    r = analyze(load, economics=brazil.Setup(book=book), test_days=90)
    assert r.economics is not None
    direct = brazil.bill(load, book=brazil.TariffBook.from_legacy(LEGACY))
    assert r.economics.monthly["total"].tolist() == pytest.approx(direct.monthly["total"].tolist())


# ---------------------------------------------------------------------- windows by cost
def _outlook(quantity: str, values: np.ndarray, start: str, confidence: str = "high") -> Outlook:
    ds = pd.date_range(start, periods=len(values), freq="h", tz=TZ)
    hourly = pd.DataFrame({"unique_id": "site", "ds": ds, "y_hat": values})
    daily = pd.DataFrame(
        {
            "unique_id": "site",
            "date": pd.date_range(start, periods=len(values) // 24, freq="D"),
            "confidence": confidence,
        }
    )
    return Outlook(hourly=hourly, daily=daily, quantity=quantity)


def test_windows_by_cost_is_cheapest_windows_month_by_month() -> None:
    """Over a month boundary with one tariff, the same rows as `cheapest_windows`, plus the currency and the
    tariff's name; the outlook's confidence label rides along."""
    load = _outlook("consumption", np.full(4 * 24, 0.5), "2025-01-30", confidence="typical week")
    w = economics.windows_by_cost(TOU, consumption=load, hours=2, kw=2.0)
    direct = economics.cheapest_windows(TOU, consumption=load, hours=2, kw=2.0, scheme="net_metering")
    pd.testing.assert_frame_equal(w.drop(columns=["currency", "tariff"]), direct)
    assert set(w["confidence"]) == {"typical week"} and set(w["currency"]) == {"EUR"}
    first = w[w["rank"] == 1].iloc[0]  # Thursday 30 January: the night block at 0.10, 2 h x 2 kW
    assert first["cost"] == pytest.approx(0.4) and first["start"].hour == 0
    assert w.attrs["notes"] == []
    with pytest.raises(ValueError, match="outlook"):
        economics.windows_by_cost(TOU)
    with pytest.raises(TypeError, match="Tariff"):
        economics.windows_by_cost("0.30", consumption=load)  # type: ignore[arg-type]


def test_windows_by_cost_with_a_brazilian_setup() -> None:
    """October 2026 (green flag, published) and November (not yet in the fixture: the last flag is assumed,
    with a note). GD II with PV: a kWh of PV is worth its credit value, less than the full price, so the
    sunny hours are the cheapest."""
    sun = np.where(np.isin(np.arange(24 * 4) % 24, [10, 11, 12]), 3.0, 0.0)
    gen = _outlook("generation", sun, "2026-10-30")
    setup = brazil.Setup(book=_copel(), gd="GD II")
    w = economics.windows_by_cost(setup, generation=gen, hours=3, kw=2.0, top=1)
    assert len(w) == 4 and (w["start"].dt.hour == 10).all() and set(w["currency"]) == {"BRL"}
    assert any("No bandeira published for 2026-11" in n for n in w.attrs["notes"])
    october = brazil.tariff(_copel(), "2026-10", gd="GD II")
    assert w["cost"].iloc[0] == pytest.approx(6 * float(october.export_price))  # type: ignore[arg-type]
    # no generation: the full price, no export value; the GD class is not needed
    flat = economics.windows_by_cost(brazil.Setup(book=_copel()), consumption=gen_to_load(gen), hours=1)
    assert flat["cost"].iloc[0] == pytest.approx(october.prices["flat"])
    with pytest.raises(ValueError, match="connection date"):
        economics.windows_by_cost(brazil.Setup(book=_copel()), generation=gen)


def gen_to_load(o: Outlook) -> Outlook:
    return Outlook(hourly=o.hourly.assign(y_hat=1.0), daily=o.daily, quantity="consumption")
