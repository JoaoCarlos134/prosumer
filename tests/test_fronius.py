"""Fronius Solar.web reader, on small synthetic exports with the real layout (two header rows, `n/a` cells,
yearly files that overlap). No plant data."""

from __future__ import annotations

import csv
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from prosumer.io import fronius

TZ = "America/Sao_Paulo"  # no daylight saving since 2019
DEV = "Primo 4.0-1 (1)"

PT = [
    "Data e horário",
    "Energia",
    "Energia MPP1",
    "Corrente CC MPP1",
    "Voltagem CC MPP1",
    "Rendimento específico",
]
EN = ["Date and time", "Energy", "Energy MPP1", "DC current MPP1", "DC voltage MPP1", "Specific yield"]
UNITS = ["dd.MM.yyyy HH:mm", "Wh", "Wh", "A", "V", "kWh/kWp"]


def rows(
    start: str,
    n: int,
    *,
    names: list[str] = PT,
    devices: tuple[str, ...] = (DEV,),
    wh: Any = 10.0,
    na: set[str] = frozenset(),  # type: ignore[assignment]
    skip: set[str] = frozenset(),  # type: ignore[assignment]
    as_datetime: bool = False,
) -> list[list[Any]]:
    """Header, units and `n` 5-minute rows from `start`; `na` stamps get 'n/a', `skip` stamps are absent."""
    header = [names[0]] + [f"{c} | {d}" for d in devices for c in names[1:]]
    units = [UNITS[0]] + [u for _ in devices for u in UNITS[1:]]
    out: list[list[Any]] = [header, units]
    for k, t in enumerate(pd.date_range(start, periods=n, freq="5min")):
        stamp = t.strftime("%d.%m.%Y %H:%M")
        if stamp in skip:
            continue
        cell: Any = t.to_pydatetime() if as_datetime else stamp
        row: list[Any] = [cell]
        for i, _ in enumerate(devices):
            e = wh(k) if callable(wh) else wh
            e = e * (i + 1)
            vals = [e, e, 1.5, 300.0, 0.002] if stamp not in na else ["n/a"] * 5
            row += vals
        out.append(row)
    return out


def write_xlsx(path: Path, sheets: dict[str, list[list[Any]]]) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    for name, data in sheets.items():
        ws = wb.create_sheet(name)
        for r in data:
            ws.append(r)
    wb.save(path)
    return path


def write_csv(path: Path, data: list[list[Any]], *, sep: str = ";", decimal: str = ",") -> Path:
    def fmt(v: Any) -> str:
        if isinstance(v, float):
            return f"{v:g}".replace(".", decimal)
        return str(v)

    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=sep)
        for r in data:
            w.writerow([fmt(v) for v in r])
    return path


def hourly(s: Any) -> pd.DataFrame:
    return s.frame.set_index("ds")


# ---------------------------------------------------------------------- names
def test_canonical_names_in_three_languages() -> None:
    assert fronius.canonical("Data e horário") == "time"
    assert fronius.canonical("Date and time") == "time"
    assert fronius.canonical("Datum und Uhrzeit") == "time"
    assert (
        fronius.canonical("Energia")
        == fronius.canonical("Energy")
        == fronius.canonical("Energie")
        == "energy"
    )
    assert fronius.canonical("Energia MPP2") == "energy_mpp2"
    assert fronius.canonical("Produção fotovoltaica") == "pv_production"
    assert fronius.canonical("PV production") == "pv_production"
    assert fronius.canonical("Corrente CA L1") == "ac_current_l1"
    assert fronius.canonical("AC current L3") == "ac_current_l3"
    assert fronius.canonical("Voltagem CC MPP1") == "dc_voltage_mpp1"
    assert fronius.canonical("DC voltage MPP2") == "dc_voltage_mpp2"
    assert fronius.canonical("Fator de potência") == "power_factor"
    assert fronius.canonical("Potência reativa") == "reactive_power"
    assert fronius.canonical("Rendimento específico") == "specific_yield"
    assert fronius.canonical("Something Else (x)") == "something_else_x"


# ---------------------------------------------------------------------- raw
def test_raw_keeps_every_column_with_units(tmp_path: Path) -> None:
    f = write_xlsx(tmp_path / "2025.xlsx", {"Sheet1": rows("2025-08-01 10:00", 3, na={"01.08.2025 10:05"})})
    raw = fronius.read_solarweb_raw(f)
    assert list(raw.columns) == [
        "time",
        "device",
        "energy_Wh",
        "energy_mpp1_Wh",
        "dc_current_mpp1_A",
        "dc_voltage_mpp1_V",
        "specific_yield_kWh_kWp",
        "file",
        "sheet",
        "row",
        "duplicate",
    ]
    assert raw["device"].unique().tolist() == [DEV]
    assert raw["row"].tolist() == [3, 4, 5]
    assert np.isnan(raw.loc[1, "energy_Wh"]) and raw.loc[2, "energy_Wh"] == 10.0
    assert raw["time"].iloc[0] == pd.Timestamp("2025-08-01 10:00")
    cols = pd.DataFrame(raw.attrs["columns"]).set_index("column")
    assert cols.loc["energy_Wh", "header"] == "Energia" and cols.loc["dc_voltage_mpp1_V", "unit"] == "V"
    raw.to_parquet(tmp_path / "raw.parquet")  # regression 2026-10-17: a DataFrame in attrs broke this


def test_english_header_gives_the_same_columns(tmp_path: Path) -> None:
    pt = fronius.read_solarweb_raw(write_xlsx(tmp_path / "pt.xlsx", {"a": rows("2025-08-01", 2)}))
    en = fronius.read_solarweb_raw(write_xlsx(tmp_path / "en.xlsx", {"a": rows("2025-08-01", 2, names=EN)}))
    assert list(pt.columns) == list(en.columns)


def test_excel_datetime_cells_and_several_sheets(tmp_path: Path) -> None:
    f = write_xlsx(
        tmp_path / "y.xlsx",
        {"jan": rows("2025-01-01 10:00", 12, as_datetime=True), "feb": rows("2025-02-01 10:00", 12)},
    )
    s = fronius.read_solarweb(f, tz=TZ)
    h = hourly(s)
    assert h.loc[pd.Timestamp("2025-01-01 10:00", tz=TZ), "y"] == pytest.approx(0.12)
    assert h.loc[pd.Timestamp("2025-02-01 10:00", tz=TZ), "y"] == pytest.approx(0.12)
    # the month in between is a gap on the complete grid
    assert not h.loc[pd.Timestamp("2025-01-15 10:00", tz=TZ), "valid"]


# ---------------------------------------------------------------------- the series
def test_hourly_sum_and_coverage_rule(tmp_path: Path) -> None:
    data = rows(
        "2025-08-01 10:00",
        36,
        na={"01.08.2025 11:20", "01.08.2025 12:05"},
        skip={"01.08.2025 12:40"},
    )
    s = fronius.read_solarweb(write_xlsx(tmp_path / "a.xlsx", {"s": data}), tz=TZ)
    assert s.unit == "kWh" and s.quantity == "generation" and s.freq == "h" and s.series == [DEV]
    h = hourly(s)
    t = [pd.Timestamp(f"2025-08-01 {x}:00", tz=TZ) for x in (10, 11, 12)]
    assert h.loc[t[0], "y"] == pytest.approx(0.12) and h.loc[t[0], "valid"]
    assert h.loc[t[1], "y"] == pytest.approx(0.11) and h.loc[t[1], "valid"]  # 11 of 12: valid
    assert np.isnan(h.loc[t[2], "y"]) and not h.loc[t[2], "valid"]  # 10 of 12: invalid
    # a looser rule accepts it
    s2 = fronius.read_solarweb(tmp_path / "a.xlsx", tz=TZ, min_coverage=0.8)
    assert hourly(s2).loc[t[2], "y"] == pytest.approx(0.10)


def test_overlapping_yearly_files_keep_one_and_count(tmp_path: Path) -> None:
    a = write_xlsx(tmp_path / "2024.xlsx", {"s": rows("2024-12-31 23:00", 13)})  # ... 2025-01-01 00:00
    b_rows = rows("2025-01-01 00:00", 12, wh=lambda k: 99.0 if k == 0 else 10.0)  # boundary row disagrees
    b = write_xlsx(tmp_path / "2025.xlsx", {"s": b_rows})
    raw = fronius.read_solarweb_raw([a, b])
    assert int(raw["duplicate"].sum()) == 1
    s = fronius.read_solarweb([a, b], tz=TZ)
    h = hourly(s)
    assert h.loc[pd.Timestamp("2025-01-01 00:00", tz=TZ), "y"] == pytest.approx(0.12)  # the first file wins
    assert s.provenance is not None
    assert "1 duplicate timestamp(s) dropped, first kept (1 with a different energy)" in s.provenance.notes
    assert s.provenance.license == "unknown" and "2024.xlsx" in s.provenance.source
    # given in the other order, the other value wins
    s_rev = fronius.read_solarweb([b, a], tz=TZ)
    assert hourly(s_rev).loc[pd.Timestamp("2025-01-01 00:00", tz=TZ), "y"] == pytest.approx(0.099 + 0.11)


def test_label_end_moves_by_one_five_minute_step(tmp_path: Path) -> None:
    f = write_xlsx(tmp_path / "e.xlsx", {"s": rows("2025-08-01 10:05", 12)})  # 10:05 ... 11:00
    t10, t11 = pd.Timestamp("2025-08-01 10:00", tz=TZ), pd.Timestamp("2025-08-01 11:00", tz=TZ)
    end = hourly(fronius.read_solarweb(f, tz=TZ, label="end"))
    assert end.loc[t10, "y"] == pytest.approx(0.12) and end.loc[t10, "valid"]
    assert t11 not in end.index
    start = hourly(fronius.read_solarweb(f, tz=TZ, label="start"))
    assert start.loc[t10, "y"] == pytest.approx(0.11)
    assert not start.loc[t11, "valid"]
    s5 = fronius.read_solarweb(f, tz=TZ, label="end", freq="5min")
    assert s5.frame["ds"].iloc[0] == t10


def test_several_devices_one_series_each(tmp_path: Path) -> None:
    data = rows("2025-08-01 10:00", 12, devices=(DEV, "Symo 12.0-3 (2)"))
    f = write_xlsx(tmp_path / "d.xlsx", {"s": data})
    s = fronius.read_solarweb(f, tz=TZ)
    assert s.series == sorted([DEV, "Symo 12.0-3 (2)"])
    h = s.frame.set_index("unique_id")["y"]
    assert h[DEV] == pytest.approx(0.12) and h["Symo 12.0-3 (2)"] == pytest.approx(0.24)
    named = fronius.read_solarweb(f, tz=TZ, names={DEV: "roof", "Symo 12.0-3 (2)": "garage"})
    assert named.series == ["garage", "roof"]
    assert fronius.read_solarweb(f, tz=TZ, names=["a", "b"]).series == ["a", "b"]
    with pytest.raises(ValueError, match="names="):
        fronius.read_solarweb(f, tz=TZ, names={"nope": "x"})


def test_csv_with_semicolon_and_decimal_comma(tmp_path: Path) -> None:
    f = write_csv(tmp_path / "x.csv", rows("2025-08-01 10:00", 12, wh=2.5, na={"01.08.2025 10:30"}))
    s = fronius.read_solarweb(f, tz=TZ)
    assert hourly(s).loc[pd.Timestamp("2025-08-01 10:00", tz=TZ), "y"] == pytest.approx(11 * 2.5e-3)
    raw = fronius.read_solarweb_raw(f)
    assert raw["dc_current_mpp1_A"].iloc[0] == 1.5 and raw["file"].iloc[0] == "x.csv"


def test_csv_english_comma_separated(tmp_path: Path) -> None:
    f = write_csv(tmp_path / "en.csv", rows("2025-08-01 10:00", 12, names=EN, wh=2.5), sep=",", decimal=".")
    s = fronius.read_solarweb(f, tz=TZ)
    assert s.frame["y"].iloc[0] == pytest.approx(0.03)


def test_energy_column_choice_and_errors(tmp_path: Path) -> None:
    f = write_xlsx(tmp_path / "c.xlsx", {"s": rows("2025-08-01 10:00", 12)})
    for key in ("Energia MPP1", "energy_mpp1", "energy_mpp1_Wh"):
        assert fronius.read_solarweb(f, tz=TZ, energy_column=key).frame["y"].iloc[0] == pytest.approx(0.12)
    with pytest.raises(ValueError, match="not found"):
        fronius.read_solarweb(f, tz=TZ, energy_column="nope")
    with pytest.raises(ValueError, match="not an energy"):
        fronius.read_solarweb(f, tz=TZ, energy_column="Corrente CC MPP1")


def test_daily_step_and_night_zeros(tmp_path: Path) -> None:
    night = {
        t.strftime("%d.%m.%Y %H:%M")
        for t in pd.date_range("2025-08-01", periods=288, freq="5min")
        if t.hour < 5 or t.hour >= 20
    }
    f = write_xlsx(tmp_path / "n.xlsx", {"s": rows("2025-08-01 00:00", 288, na=night)})
    plain = hourly(fronius.read_solarweb(f, tz=TZ))
    t2 = pd.Timestamp("2025-08-01 02:00", tz=TZ)
    assert not plain.loc[t2, "valid"]
    filled = fronius.read_solarweb(f, tz=TZ, site=(-25.0, -50.0))
    h = hourly(filled)
    assert h.loc[t2, "valid"] and h.loc[t2, "y"] == 0.0
    assert h["valid"].all() and len(h) == 24
    assert filled.provenance is not None and "set to zero" in filled.provenance.notes
    day = fronius.read_solarweb(f, tz=TZ, freq="D", min_coverage=0.5)
    assert day.frame["y"].iloc[0] == pytest.approx((288 - len(night)) * 0.01)


def as_exported(data: list[list[Any]]) -> list[list[Any]]:
    """The layout of the real exports (checked at Lactec on 2026-10-16): units in brackets and a site-total
    `Produção fotovoltaica` column without a device suffix, at the end."""
    head, units, *body = data
    return [
        [*head, "Produção fotovoltaica"],
        [f"[{u}]" for u in units] + ["[Wh]"],
        *[[*r, r[1]] for r in body],
    ]


@pytest.mark.parametrize("fmt", ["xlsx", "csv"])
def test_real_export_layout_bracketed_units_and_site_total(tmp_path: Path, fmt: str) -> None:
    # regression: real units read `[Wh]`, so no energy column was recognised; the site-total column then
    # came out as a device named "" and warned on every real file
    data = as_exported(rows("2025-08-01 10:00", 12, wh=2.5))
    f = (
        write_xlsx(tmp_path / "r.xlsx", {"minuto": data})
        if fmt == "xlsx"
        else write_csv(tmp_path / "r.csv", data)
    )
    raw = fronius.read_solarweb_raw(f)
    cols = pd.DataFrame(raw.attrs["columns"]).set_index("column")
    assert cols.loc["energy_Wh", "unit"] == "Wh" and "pv_production_Wh" in cols.index
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        s = fronius.read_solarweb(f, tz=TZ)
    assert s.frame["unique_id"].unique().tolist() == [DEV]
    assert s.frame["y"].iloc[0] == pytest.approx(12 * 2.5e-3)


def test_site_total_alone_is_one_series(tmp_path: Path) -> None:
    # neighbour: an export with only the site-total column still reads, as one series
    data = [[r[0], r[-1]] for r in as_exported(rows("2025-08-01 10:00", 12, wh=2.5))]
    s = fronius.read_solarweb(write_xlsx(tmp_path / "t.xlsx", {"s": data}), tz=TZ, names=["site"])
    assert s.frame["unique_id"].unique().tolist() == ["site"]
    assert s.frame["y"].iloc[0] == pytest.approx(0.03)


def test_not_a_solarweb_file(tmp_path: Path) -> None:
    f = write_csv(tmp_path / "bad.csv", [["a", "b"], ["x", "y"], ["1", "2"]])
    with pytest.raises(ValueError, match="no date/time column"):
        fronius.read_solarweb_raw(f)


def test_no_real_data_needed() -> None:
    # the synthetic builder itself: 5-minute grid, header + units
    r = rows("2025-08-01 10:00", 2)
    assert r[0][1] == f"Energia | {DEV}" and r[1][0] == "dd.MM.yyyy HH:mm" and r[2][0] == "01.08.2025 10:00"
    assert isinstance(rows("2025-08-01", 1, as_datetime=True)[2][0], datetime)
