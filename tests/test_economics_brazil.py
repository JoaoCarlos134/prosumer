"""prosumer.economics.brazil: the legacy 2018 check on ANEEL data, and hand-worked bills on a made-up book."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prosumer import EnergySeries, economics
from prosumer.economics import brazil

TZ = "Etc/GMT+3"
LEGACY = Path(__file__).resolve().parents[1] / "legado" / "ia_solar" / "analise" / "tarifas" / "dados"
GROSS = 1.0 / (1.0 - 0.19 - 0.0925)
P = 0.8 * GROSS  # conventional full price of the made-up book, green flag
P_FEB = 0.85 * GROSS  # February 2025: red flag, 50 R$/MWh


def _book() -> brazil.TariffBook:
    rows = [("Convencional", "Não se aplica", 500.0, 300.0)]
    rows += [("Branca", "Ponta", 1000.0, 500.0), ("Branca", "Intermediário", 600.0, 300.0)]
    rows += [("Branca", "Fora ponta", 300.0, 250.0)]
    tariffs = pd.DataFrame(
        [("2020-01-01", "2035-12-31", "B1", m, p, tusd, te) for m, p, tusd, te in rows],
        columns=["start", "end", "subgroup", "modality", "posto", "tusd", "te"],
    )
    months = pd.period_range("2020-01", "2035-12", freq="M").astype(str)
    band = pd.DataFrame({"month": months, "flag": "Verde", "add": 0.0})
    band.loc[band["month"] == "2025-02", ["flag", "add"]] = ["Vermelha P1", 50.0]
    taxes = pd.DataFrame({"start": ["2020-01-01"], "icms": [0.19], "pis_cofins": [0.0925]})
    fio_b = pd.DataFrame({"start": ["2020-01-01"], "value": [200.0]})
    return brazil.TariffBook(tariffs, band, taxes, fio_b, distributor="TEST")


def _series(values: np.ndarray, start: str, quantity: str) -> EnergySeries:
    ds = pd.date_range(start, periods=len(values), freq="h", tz=TZ)
    return EnergySeries.from_dataframe(
        pd.DataFrame({"unique_id": "uc", "ds": ds, "y": values}),
        unit="kWh",
        quantity=quantity,  # type: ignore[arg-type]
        tz=TZ,
        freq="h",
    )


def _site(days: int, pv_kwh: float, start: str = "2026-01-01", load: float = 1.0) -> tuple[EnergySeries, ...]:
    hours = days * 24
    pv = np.where(np.isin(np.arange(hours) % 24, [10, 11, 12, 13]), pv_kwh, 0.0)
    return _series(np.full(hours, load), start, "consumption"), _series(pv, start, "generation")


# ---------------------------------------------------------------------- legacy validation
@pytest.mark.skipif(not (LEGACY / "copel_tarifas_historico.csv").exists(), reason="legacy tariff CSVs absent")
def test_legacy_2018_retail_price_is_reproduced() -> None:
    """LEIA-ME.md: Cascavel 2018, model 0.8062 R$/kWh (B1 conventional TUSD+TE + the month's bandeira, ICMS
    29%, PIS/COFINS 9.25%), the mean over the 12 months of the daily full price."""
    book = brazil.TariffBook.from_legacy(LEGACY)
    m = brazil.retail_price_by_month(book, "2018-01-01", "2018-12-31")
    assert len(m) == 12
    assert m.mean() == pytest.approx(0.8062, abs=5e-5)
    # January: 440.56 R$/MWh, green flag -> 0.44056 / (1 - 0.29 - 0.0925)
    assert m.iloc[0] == pytest.approx(0.44056 / (1 - 0.29 - 0.0925), rel=1e-12)
    # tarifa branca 2017/18 is published in two rows for the intermediario (TUSD-only, TE-only): added
    assert book.base("2018-01-15", modality="Branca", posto="Intermediário") == (292.73, 238.81)


# ---------------------------------------------------------------------- rules
def test_full_price_and_minimum_table() -> None:
    assert brazil.full_price(440.56, 50.0, 0.29, 0.0925) == pytest.approx(0.49056 / 0.6175)
    assert brazil.MINIMUM_KWH == {"monofasico": 30, "bifasico_2": 30, "bifasico_3": 50, "trifasico": 100}
    with pytest.raises(ValueError):
        brazil.gross_up(0.6, 0.5)


def test_holidays_follow_easter_and_ren_1101() -> None:
    assert brazil.easter(2024) == date(2024, 3, 31) and brazil.easter(2026) == date(2026, 4, 5)
    h = brazil.holidays([2026])
    assert {date(2026, 2, 17), date(2026, 4, 3), date(2026, 6, 4), date(2026, 11, 20)} <= h
    assert date(2023, 11, 20) not in brazil.holidays([2023])
    assert len(h) == 12


def test_branca_postos() -> None:
    whole = brazil.branca_blocks("18:00")
    assert [whole[h] for h in (16, 17, 18, 20, 21, 22)] == [
        "fora_ponta",
        "intermediario",
        "ponta",
        "ponta",
        "intermediario",
        "fora_ponta",
    ]
    half = brazil.branca_blocks("17:30")
    assert half[17] == {"intermediario": 0.5, "ponta": 0.5}
    assert half[21] == {"intermediario": 0.5, "fora_ponta": 0.5}
    t = brazil.tariff(_book(), "2026-03", modality="Branca", peak_start="18:00")
    ds = pd.DatetimeIndex(
        [
            pd.Timestamp("2026-03-02 19:00", tz=TZ),  # Monday: ponta
            pd.Timestamp("2026-03-07 19:00", tz=TZ),  # Saturday: fora de ponta
            pd.Timestamp("2026-04-03 19:00", tz=TZ),  # Good Friday: fora de ponta
        ]
    )
    assert t.price(ds) == pytest.approx([1.5 * GROSS, 0.55 * GROSS, 0.55 * GROSS])


def test_gd_class_and_charge_share() -> None:
    assert brazil.gd_class("2019-07-01") == "GD I"
    assert brazil.gd_class("2023-03-01", requested="2023-01-05") == "GD I"
    assert brazil.gd_class("2023-03-01") == "GD II"
    assert brazil.compensation_charge_share(2045, "GD I") == (0.0, "fio_b")
    assert brazil.compensation_charge_share(2046, "GD I") == (1.0, "tusd")
    shares = [brazil.compensation_charge_share(y, "GD II")[0] for y in range(2023, 2029)]
    assert shares == [0.15, 0.30, 0.45, 0.60, 0.75, 0.90]
    assert brazil.compensation_charge_share(2029, "GD II") == (1.0, "tusd")
    assert brazil.compensation_charge_share(2029, "GD II", after_2028="fio_b") == (1.0, "fio_b")
    deferred = brazil.compensation_charge_share(2030, "GD II", requested="2023-03-01")
    assert deferred == (0.90, "fio_b")
    assert brazil.compensation_charge_share(2031, "GD II", requested="2023-03-01") == (1.0, "tusd")


# ---------------------------------------------------------------------- bills
def test_no_generation_bill_is_energy_or_minimum() -> None:
    load, _ = _site(31, 0, load=1.0)
    m = brazil.bill(load, book=_book(), cosip=10.0).monthly.iloc[0]
    assert m["energy_bill"] == pytest.approx(744 * P)
    assert m["total"] == pytest.approx(744 * P + 10.0) and not m["minimum_applied"]
    tiny, _ = _site(31, 0, load=0.05)  # 37.2 kWh < 50 kWh
    t = brazil.bill(tiny, book=_book()).monthly.iloc[0]
    assert t["minimum_applied"] and t["energy_bill"] == pytest.approx(50 * P)
    tri = brazil.bill(tiny, book=_book(), connection="trifasico").monthly.iloc[0]
    assert tri["energy_bill"] == pytest.approx(100 * P)


def test_gd_i_compensates_down_to_the_minimum_and_banks_the_rest() -> None:
    load, pv = _site(31, 10.0)  # import 620 kWh, export 1116 kWh
    b = brazil.bill(load, pv, book=_book(), connected="2019-07-01")
    m = b.monthly.iloc[0]
    assert m["gd_class"] == "GD I" and m["charge_share"] == 0
    assert m["compensated"] == pytest.approx(620 - 50)
    assert m["energy_bill"] == pytest.approx(50 * P)
    assert m["credit_new"] == pytest.approx(1116 - 570)
    assert m["without_pv"] == pytest.approx(744 * P)
    small, pv4 = _site(31, 4.0)  # export 372 < 570: all used, bill on the rest
    s = brazil.bill(small, pv4, book=_book(), gd="GD I").monthly.iloc[0]
    assert s["compensated"] == pytest.approx(372) and s["credit_new"] == pytest.approx(0)
    assert s["energy_bill"] == pytest.approx((620 - 372) * P)


def test_gd_ii_pays_the_fio_b_share_on_compensated_energy() -> None:
    load, pv = _site(31, 10.0)
    m = brazil.bill(load, pv, book=_book(), connected="2024-05-01").monthly.iloc[0]  # 2026: 60%
    c = 0.60 * 0.200 * GROSS
    assert m["gd_class"] == "GD II" and m["charge_share"] == 0.60
    # with the charge the bill passes the minimum before all is compensated: all 620 kWh compensated
    assert m["compensated"] == pytest.approx(620)
    assert m["compensation_charge"] == pytest.approx(620 * c)
    assert m["energy_bill"] == pytest.approx(620 * c)
    # without taxes on the charge, and in 2029 with the whole TUSD (the default reading)
    no_tax = brazil.bill(load, pv, book=_book(), gd="GD II", taxes_on_fio_b=False).monthly.iloc[0]
    assert no_tax["compensation_charge"] == pytest.approx(620 * 0.6 * 0.2)
    later, pv_later = _site(31, 10.0, start="2029-01-01")
    b29 = brazil.bill(later, pv_later, book=_book(), gd="GD II")
    r = b29.monthly.iloc[0]
    c29 = 0.5 * GROSS  # TUSD 500 R$/MWh
    expected = min(620.0, (620 * P - 50 * P) / (P - c29))
    assert r["compensated"] == pytest.approx(expected)
    assert r["energy_bill"] == pytest.approx((620 - expected) * P + expected * c29)
    assert r["energy_bill"] >= 50 * P - 1e-9
    assert any("art. 17" in n for n in b29.notes)


def test_bandeira_only_on_billed_energy_and_credits_used_oldest_first() -> None:
    load, pv = _site(59, 4.0, start="2025-01-01")
    b = brazil.bill(load, pv, book=_book(), gd="GD I", initial_credit=100.0, credit_months=2)
    jan, feb = b.monthly.iloc[0], b.monthly.iloc[1]
    # January: own export 372 then 100 banked kWh; bill on 620 - 472
    assert jan["compensated"] == pytest.approx(472) and jan["credit_used"] == pytest.approx(100)
    assert jan["energy_bill"] == pytest.approx(148 * P)
    # February, red flag: the surcharge applies to the 560 - 336 kWh billed, not to the compensated
    assert feb["flag"] == "Vermelha P1"
    assert feb["energy_bill"] == pytest.approx((560 - 336) * P_FEB)


def test_credits_expire() -> None:
    load, pv = _site(31, 0.0)
    b = brazil.bill(load, pv, book=_book(), gd="GD I", initial_credit=500.0, credit_months=1)
    m = b.monthly.iloc[0]
    assert m["credit_expired"] == pytest.approx(500) and m["compensated"] == 0
    assert any("expired" in n for n in b.notes)


def test_tarifa_branca_without_generation() -> None:
    load = _series(np.full(24, 10.0), "2026-03-02", "consumption")  # a Monday
    m = brazil.bill(load, book=_book(), modality="Branca", peak_start="18:00").monthly.iloc[0]
    energy = 10 * (3 * 1.5 + 2 * 0.9 + 19 * 0.55) * GROSS
    assert m["energy_bill"] == pytest.approx(energy)
    small = _series(np.full(24, 1.0), "2026-03-02", "consumption")
    s = brazil.bill(small, book=_book(), modality="Branca", peak_start="18:00").monthly.iloc[0]
    assert s["minimum_applied"] and s["energy_bill"] == pytest.approx(50 * P)  # conventional (art. 290 §4)
    _, pv = _site(1, 3.0, start="2026-03-02")
    with pytest.raises(NotImplementedError):
        brazil.bill(load, pv, book=_book(), modality="Branca", peak_start="18:00", gd="GD I")


def test_tariff_for_cheapest_windows_values_a_credit() -> None:
    book = _book()
    gd1 = brazil.tariff(book, "2026-03", gd="GD I")
    assert gd1.prices["flat"] == pytest.approx(P) and gd1.export_price == pytest.approx(P)
    gd2 = brazil.tariff(book, "2026-03", gd="GD II")
    assert gd2.export_price == pytest.approx(P - 0.6 * 0.2 * GROSS)
    assert gd2.currency == "BRL"
    none = brazil.tariff(book, "2026-03")
    assert none.export_price == 0.0
    with pytest.raises(ValueError, match="bandeira"):
        brazil.tariff(book, "2040-01")
    assert brazil.tariff(book, "2040-01", assume_bandeira=0.0).prices["flat"] == pytest.approx(P)
    assert isinstance(gd2, economics.Tariff)
