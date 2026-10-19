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
    29%, PIS/COFINS 9.25%), the mean over the 12 months of the daily full price.

    A PORT REGRESSION (the new code reproduces the legacy computation), not an independent validation: the
    real 2018 bills averaged 0.8457 R$/kWh, the 0.0395 gap attributed there to COSIP."""
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
    assert m["minimum_applied"]  # the minimum stopped the compensation (bill == minimum exactly)
    assert m["credit_new"] == pytest.approx(1116 - 570)
    assert m["without_pv"] == pytest.approx(744 * P)
    small, pv4 = _site(31, 4.0)  # export 372 < 570: all used, bill on the rest
    s = brazil.bill(small, pv4, book=_book(), gd="GD I").monthly.iloc[0]
    assert s["compensated"] == pytest.approx(372) and s["credit_new"] == pytest.approx(0)
    assert s["energy_bill"] == pytest.approx((620 - 372) * P)
    assert not s["minimum_applied"]


def test_gd_ii_pays_the_fio_b_share_on_compensated_energy() -> None:
    load, pv = _site(31, 10.0)
    m = brazil.bill(load, pv, book=_book(), connected="2024-05-01").monthly.iloc[0]  # 2026: 60%
    c = 0.60 * 0.200 / (1 - 0.19)  # default: ICMS on the charge, no PIS/COFINS
    assert m["gd_class"] == "GD II" and m["charge_share"] == 0.60
    # with the charge the bill passes the minimum before all is compensated: all 620 kWh compensated
    assert m["compensated"] == pytest.approx(620)
    assert m["compensation_charge"] == pytest.approx(620 * c)
    assert m["energy_bill"] == pytest.approx(620 * c)
    # without taxes on the charge, and in 2029 with the whole TUSD (the default reading)
    no_tax = brazil.bill(load, pv, book=_book(), gd="GD II", icms_on_charge=False).monthly.iloc[0]
    assert no_tax["compensation_charge"] == pytest.approx(620 * 0.6 * 0.2)
    later, pv_later = _site(31, 10.0, start="2029-01-01")
    b29 = brazil.bill(later, pv_later, book=_book(), gd="GD II")
    r = b29.monthly.iloc[0]
    c29 = 0.5 / (1 - 0.19)  # TUSD 500 R$/MWh
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


# ---------------------------------------------------------------------- tarifa branca with generation
def _branca_day(ponta: float = 0.0, intermediario: float = 0.0, night: float = 0.0, pv: float = 0.0):
    """One Monday (2026-03-02, peak 18-21 h): load per hour in ponta (18-20), intermediario (17, 21) and the
    night (0-5, fora ponta); PV per hour at 10-13 (fora ponta)."""
    h = np.arange(24)
    load = np.select(
        [np.isin(h, [18, 19, 20]), np.isin(h, [17, 21]), h < 6], [ponta, intermediario, night], 0.0
    )
    gen = np.where(np.isin(h, [10, 11, 12, 13]), pv, 0.0)
    return _series(load, "2026-03-02", "consumption"), _series(gen, "2026-03-02", "generation")


def _branca(load: EnergySeries, pv: EnergySeries, **kw: object) -> pd.Series:
    b = brazil.bill(load, pv, book=_book(), modality="Branca", peak_start="18:00", gd="GD I", **kw)
    return b.monthly.iloc[0]


def test_branca_excess_moves_to_the_peak_by_the_te_ratio() -> None:
    """REN 1.000 art. 655-G §§3 and 5: 100 kWh injected in fora ponta (TE 250) used in ponta (TE 500) are
    50 kWh there. GD I with the default readings: a compensated kWh costs nothing."""
    m = _branca(*_branca_day(ponta=100.0, pv=25.0))
    assert m["compensated"] == pytest.approx(50.0)
    assert m["energy_bill"] == pytest.approx(250 * 1.5 * GROSS)
    assert m["credit_new"] == pytest.approx(0.0) and m["credit_balance"] == pytest.approx(0.0)
    # the exact TE Energia component, when the person has it, sets the ratio instead (100 / 400 = 0.25)
    exact = _branca(
        *_branca_day(ponta=100.0, pv=25.0), te_energy={"ponta": 400, "intermediario": 250, "fora_ponta": 100}
    )
    assert exact["compensated"] == pytest.approx(25.0)


def test_branca_own_posto_first_then_the_others() -> None:
    """60 kWh of night load (fora ponta) take 60 of the 100 kWh injected in fora ponta, one for one; the 40
    left are 20 kWh in ponta."""
    m = _branca(*_branca_day(ponta=100.0, night=10.0, pv=25.0))
    assert m["compensated"] == pytest.approx(60.0 + 20.0)
    assert m["energy_bill"] == pytest.approx(280 * 1.5 * GROSS)
    blocks = brazil.bill(
        *_branca_day(ponta=100.0, night=10.0, pv=25.0),
        book=_book(),
        modality="Branca",
        peak_start="18:00",
        gd="GD I",
    ).by_block.set_index("block")
    assert blocks.loc["fora_ponta", "compensated"] == pytest.approx(60.0)
    assert blocks.loc["ponta", "compensated"] == pytest.approx(20.0)
    assert blocks.loc["ponta", "grid_import"] == pytest.approx(300.0)


def test_branca_credit_serves_its_own_posto_first() -> None:
    """A credit keeps its posto (§9) and, like the month's injection, offsets that posto one for one before
    any other: 100 kWh banked in fora ponta (`initial_credit`) take the 60 kWh of night load, and the 40 left
    are 20 kWh in ponta. (Spent in `posto_order` first, the whole credit went to ponta as 50 kWh.)"""
    load, pv = _branca_day(ponta=100.0, night=10.0)
    m = _branca(load, pv, initial_credit=100.0)
    assert m["credit_used"] == pytest.approx(100.0)
    assert m["compensated"] == pytest.approx(60.0 + 20.0)
    blocks = brazil.bill(
        load, pv, book=_book(), modality="Branca", peak_start="18:00", gd="GD I", initial_credit=100.0
    ).by_block.set_index("block")
    assert blocks.loc["fora_ponta", "compensated"] == pytest.approx(60.0)
    assert blocks.loc["ponta", "compensated"] == pytest.approx(20.0)


def test_branca_order_of_the_other_postos_is_a_reading() -> None:
    """The text names no order; the default serves the dearest posto first. With intermediario first the
    100 kWh of fora ponta are 100 x 250 / 300 = 83.3 kWh there."""
    day = _branca_day(ponta=100.0, intermediario=100.0, pv=25.0)
    dearest = _branca(*day)
    assert dearest["compensated"] == pytest.approx(50.0)  # all into ponta
    other = _branca(*day, posto_order=("intermediario", "ponta", "fora_ponta"))
    assert other["compensated"] == pytest.approx(100 * 250 / 300)
    with pytest.raises(ValueError, match="posto_order"):
        _branca(*day, posto_order=("ponta", "ponta", "fora_ponta"))
    with pytest.raises(ValueError, match="te_energy"):
        _branca(*day, te_energy={"ponta": 1.0})


def test_branca_minimum_stops_the_compensation_and_banks_credits_with_their_posto() -> None:
    """30 kWh of ponta load: the compensation stops where the bill reaches the minimum (50 kWh at the
    conventional 0.8): (45 - 40) / 1.5 = 3.33 kWh of ponta, from 6.67 kWh of fora ponta; the other 93.3 kWh
    are a fora ponta credit, used next month in ponta at the same ratio."""
    load, pv = _branca_day(ponta=10.0, pv=25.0)
    m = _branca(load, pv)
    assert m["minimum_applied"] and m["energy_bill"] == pytest.approx(50 * P)
    assert m["compensated"] == pytest.approx(5 / 1.5)
    assert m["credit_new"] == pytest.approx(100 - 2 * 5 / 1.5)
    # next month: 300 kWh in ponta, no PV; the credit (fora ponta) is worth half as much in ponta
    april = np.where(np.isin(np.arange(24), [18, 19, 20]), 100.0, 0.0)
    loads = pd.concat([load.frame, _series(april, "2026-04-06", "consumption").frame])  # a Monday
    gens = pd.concat([pv.frame, _series(np.zeros(24), "2026-04-06", "generation").frame])
    two = brazil.bill(
        EnergySeries.from_dataframe(loads, unit="kWh", quantity="consumption", tz=TZ, freq="h"),
        EnergySeries.from_dataframe(gens, unit="kWh", quantity="generation", tz=TZ, freq="h"),
        book=_book(),
        modality="Branca",
        peak_start="18:00",
        gd="GD I",
    ).monthly.sort_values("month")
    apr = two.iloc[1]
    banked = 100 - 2 * 5 / 1.5
    assert apr["credit_used"] == pytest.approx(banked)
    assert apr["compensated"] == pytest.approx(banked / 2)
    assert apr["energy_bill"] == pytest.approx((300 - banked / 2) * 1.5 * GROSS)


def test_tariff_for_cheapest_windows_values_a_credit() -> None:
    book = _book()
    gd1 = brazil.tariff(book, "2026-03", gd="GD I")
    assert gd1.prices["flat"] == pytest.approx(P) and gd1.export_price == pytest.approx(P)
    gd2 = brazil.tariff(book, "2026-03", gd="GD II")
    assert gd2.export_price == pytest.approx(P - 0.6 * 0.2 / 0.81)
    assert gd2.currency == "BRL"
    none = brazil.tariff(book, "2026-03")
    assert none.export_price == 0.0
    with pytest.raises(ValueError, match="bandeira"):
        brazil.tariff(book, "2040-01")
    with pytest.raises(ValueError, match="vigencia ended"):
        brazil.tariff(book, "2040-01", assume_bandeira=0.0)
    book.extend_last = True
    with pytest.warns(UserWarning, match="extend_last"):  # a Tariff has no notes: the assumption is a warning
        assert brazil.tariff(book, "2040-01", assume_bandeira=0.0).prices["flat"] == pytest.approx(P)
    assert any("extend_last" in n for n in book.notes)
    assert isinstance(gd2, economics.Tariff)
    # `requested` reaches the share: the deferred group keeps 90% of Fio B in 2030
    deferred = brazil.tariff(book, "2030-03", gd="GD II", requested="2023-03-01")
    assert deferred.export_price == pytest.approx(P - 0.9 * 0.2 / 0.81)
    assert brazil.tariff(book, "2030-03", gd="GD II").export_price == pytest.approx(P - 0.5 / 0.81)


def _night_load_june_2023() -> tuple[EnergySeries, EnergySeries]:
    """June 2023: 600 kWh, all imported at night (none during the 4 PV hours), 1200 kWh exported."""
    hours = 30 * 24
    pv_hours = np.isin(np.arange(hours) % 24, [10, 11, 12, 13])
    load = np.where(pv_hours, 0.0, 1.0)
    pv = np.where(pv_hours, 10.0, 0.0)
    return _series(load, "2023-06-01", "consumption"), _series(pv, "2023-06-01", "generation")


def test_gd_ii_minimum_by_regulation_or_by_law() -> None:
    """Lei 14.300 art. 16 §1 against REN 1.000 art. 655-I: GD II, 2023 (15% Fio B), 600 kWh measured."""
    load, pv = _night_load_june_2023()
    c = 0.15 * 0.2 / 0.81
    ren = brazil.bill(load, pv, book=_book(), gd="GD II").monthly.iloc[0]
    assert ren["energy_bill"] == pytest.approx(50 * P)  # R$ 55.75: compensation stops at the minimum
    assert ren["energy_bill"] == pytest.approx(55.75, abs=0.01)
    assert ren["compensated"] == pytest.approx((600 * P - 50 * P) / (P - c))
    assert ren["minimum_applied"]
    law = brazil.bill(load, pv, book=_book(), gd="GD II", gd2_minimum="law_16_par1").monthly.iloc[0]
    assert law["compensated"] == pytest.approx(600)
    assert law["energy_bill"] == pytest.approx(600 * c)  # R$ 22.22 (25.09 with PIS/COFINS on the charge)
    assert not law["minimum_applied"]
    with_pis = brazil.bill(
        load, pv, book=_book(), gd="GD II", gd2_minimum="law_16_par1", pis_cofins_on_charge=True
    ).monthly.iloc[0]
    assert with_pis["energy_bill"] == pytest.approx(25.09, abs=0.01)
    # GD I is never affected by the law reading
    gd1 = brazil.bill(load, pv, book=_book(), gd="GD I", gd2_minimum="law_16_par1").monthly.iloc[0]
    assert gd1["energy_bill"] == pytest.approx(50 * P)
    with pytest.raises(ValueError, match="gd2_minimum"):
        brazil.bill(load, pv, book=_book(), gd="GD II", gd2_minimum="other")  # type: ignore[arg-type]


def test_icms_on_compensated_energy_readings() -> None:
    load, pv = _night_load_june_2023()
    kw = {"gd": "GD I", "gd2_minimum": "law_16_par1"}  # GD I: no charge; isolate the taxes
    te_only = brazil.bill(load, pv, book=_book(), icms_exempt_compensated="te_only", **kw).monthly.iloc[0]  # type: ignore[arg-type]
    # each compensated kWh pays ICMS on its TUSD, 0.5 x 0.19 / 0.81 R$/kWh; with that cost the bill stays
    # above the minimum even with all 600 kWh compensated
    t = 0.5 * (1 / 0.81 - 1)
    assert te_only["compensated"] == pytest.approx(min(600.0, (600 * P - 50 * P) / (P - t)))
    assert te_only["compensated"] == pytest.approx(600)
    assert te_only["energy_bill"] == pytest.approx(600 * t) and 600 * t > 50 * P
    assert te_only["compensation_charge"] == pytest.approx(te_only["compensated"] * t)
    none = brazil.bill(load, pv, book=_book(), icms_exempt_compensated="none", **kw).monthly.iloc[0]  # type: ignore[arg-type]
    t_all = 0.8 * (1 / 0.81 - 1)
    assert none["compensation_charge"] == pytest.approx(none["compensated"] * t_all)
    pis = brazil.bill(load, pv, book=_book(), pis_cofins_exempt_compensated=False, **kw).monthly.iloc[0]  # type: ignore[arg-type]
    assert pis["compensation_charge"] == pytest.approx(pis["compensated"] * 0.8 * (1 / (1 - 0.0925) - 1))
    with pytest.raises(ValueError, match="icms_exempt_compensated"):
        brazil.bill(load, pv, book=_book(), icms_exempt_compensated="half", **kw)  # type: ignore[arg-type]


def test_missing_fio_b_and_late_pv_are_not_silent() -> None:
    book = _book()
    book.fio_b = pd.DataFrame({"start": [pd.Timestamp("2026-06-24")], "value": [214.5]})
    load, pv = _site(31, 10.0, start="2025-01-01")
    with pytest.raises(ValueError, match="No Fio B"):
        brazil.bill(load, pv, book=book, gd="GD II")
    book.fio_b_backfill = True
    b = brazil.bill(load, pv, book=book, gd="GD II")
    assert any("fio_b_backfill" in n for n in b.notes)
    # a PV series that starts on the 11th: the first ten days are unknown, and the bill says so
    late = EnergySeries.from_dataframe(
        pv.frame[pv.frame["ds"] >= pd.Timestamp("2025-01-11", tz=TZ)],
        unit="kWh",
        quantity="generation",
        tz=TZ,
        freq="h",
    )
    m = brazil.bill(load, late, book=_book(), gd="GD I")
    assert m.monthly.iloc[0]["coverage"] == pytest.approx(21 / 31)
    assert any("no generation row" in n for n in m.notes)


def test_review_2026_10_13_notes_do_not_leak_and_pis_is_not_doubled() -> None:
    """Follow-up review: a book's assumption notes leaked into later bills; with PIS/COFINS not exempt on the
    compensated kWh AND on the charge, the GD II charge paid it twice."""
    book = _book()
    book.fio_b = pd.DataFrame({"start": [pd.Timestamp("2024-01-01")], "value": [200.0]})
    book.fio_b_backfill = True
    load, pv = _night_load_june_2023()
    first = brazil.bill(load, pv, book=book, gd="GD II")
    assert any("fio_b_backfill" in n for n in first.notes)
    later_load, later_pv = _site(31, 10.0, start="2026-01-01")
    second = brazil.bill(later_load, later_pv, book=book, gd="GD II")
    assert not any("fio_b_backfill" in n for n in second.notes)  # 2026 needs no backfill
    with pytest.warns(UserWarning, match="fio_b_backfill"):
        brazil.tariff(book, "2023-06", gd="GD II")
    # PIS once: TUSD 0.5 and TE 0.3 R$/kWh, charge 0.03, ICMS 19%, PIS/COFINS 9.25%
    ct = brazil._CompensationTaxes("all", False, True, True)
    want = 0.03 / (1 - 0.19) + 0.5 * (1 / (1 - 0.0925) - 1) + 0.3 * (1 / (1 - 0.0925) - 1)
    assert ct.per_kwh(0.03, 0.5, 0.3, 0.19, 0.0925) == pytest.approx(want)
    # "te_only" on a GD II charge: the TUSD already pays ICMS, the charge does not pay it again
    te_only = brazil._CompensationTaxes("te_only", True, True, False)
    assert te_only.per_kwh(0.03, 0.5, 0.3, 0.19, 0.0925) == pytest.approx(0.03 + 0.5 * 0.19 / 0.81)
