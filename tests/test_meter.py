"""Generic meter table reader, on synthetic CSV/Excel files and frames: each kind of value (interval energy,
cumulative register, average power), Brazilian `;` + decimal comma, a counter reset, a gap."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prosumer.io import meter, read_table

TZ = "America/Sao_Paulo"


def at(s: str) -> pd.Timestamp:
    return pd.Timestamp(s, tz=TZ)


def by_ds(series: object, uid: str | None = None) -> pd.DataFrame:
    f = series.frame  # type: ignore[attr-defined]
    if uid is not None:
        f = f[f["unique_id"] == uid]
    return f.set_index("ds")


def test_interval_energy_semicolon_decimal_comma_dayfirst(tmp_path: Path) -> None:
    # 15-minute load profile, Brazilian style: dd/mm/yyyy, ';' and '1,5'; the 13th makes day-first certain
    lines = ["Data/Hora;Consumo (kWh)"]
    for t in pd.date_range("2025-03-13 00:00", periods=8, freq="15min"):
        lines.append(f"{t:%d/%m/%Y %H:%M};1,5")
    f = tmp_path / "medidor.csv"
    f.write_text("\n".join(lines), encoding="cp1252")
    s = read_table(f, time_column="Data/Hora", value_columns="Consumo (kWh)", tz=TZ, unit="kWh", freq="h")
    assert s.unit == "kWh" and s.quantity == "consumption" and s.freq == "h"
    assert s.frame["y"].tolist() == [6.0, 6.0]
    assert s.series == ["Consumo (kWh)"]
    assert s.provenance is not None and s.provenance.source == "meter table: medidor.csv"
    assert s.provenance.license == "unknown"


def test_dayfirst_ambiguous_dates_follow_file_order(tmp_path: Path) -> None:
    # 01/02 ... 12/02 daily: only day-first reading moves forwards one day at a time
    lines = ["date;kwh"] + [f"{d:02d}/02/2025 00:00;{d},0" for d in range(1, 13)]
    f = tmp_path / "d.csv"
    f.write_text("\n".join(lines))
    s = read_table(f, time_column="date", value_columns="kwh", tz=TZ, unit="kWh")
    assert s.freq == "D" or s.freq == "24h"
    assert s.frame["ds"].iloc[1] == at("2025-02-02")
    month_first = read_table(f, time_column="date", value_columns="kwh", tz=TZ, unit="kWh", dayfirst=False)
    assert month_first.frame["ds"].iloc[0] == at("2025-01-02")


def test_interval_with_gap_and_coverage() -> None:
    t = pd.date_range("2025-08-01 00:00", periods=12, freq="15min")
    df = pd.DataFrame({"time": t, "a": 250.0}).drop(index=[5, 9, 10])  # hour 1 loses one, hour 2 two
    s = read_table(df, time_column="time", value_columns="a", tz=TZ, unit="Wh", freq="h", min_coverage=0.75)
    h = by_ds(s)
    assert h.loc[at("2025-08-01 00:00"), "y"] == pytest.approx(1.0)
    assert (
        h.loc[at("2025-08-01 01:00"), "y"] == pytest.approx(0.75) and h.loc[at("2025-08-01 01:00"), "valid"]
    )
    assert not h.loc[at("2025-08-01 02:00"), "valid"] and np.isnan(h.loc[at("2025-08-01 02:00"), "y"])
    native = read_table(df, time_column="time", value_columns="a", tz=TZ, unit="Wh")
    assert native.freq == "15min" and len(native) == 12  # the gaps are rows, invalid
    assert int((~native.frame["valid"]).sum()) == 3


def test_label_end() -> None:
    t = pd.date_range("2025-08-01 00:15", periods=4, freq="15min")  # 00:15 ... 01:00 = the hour 00:00
    df = pd.DataFrame({"t": t.strftime("%Y-%m-%d %H:%M"), "e": [1.0, 1.0, 1.0, 1.0]})
    end = read_table(df, time_column="t", value_columns="e", tz=TZ, unit="kWh", freq="h", label="end")
    assert by_ds(end).loc[at("2025-08-01 00:00"), "y"] == 4.0 and len(end) == 1
    start = read_table(df, time_column="t", value_columns="e", tz=TZ, unit="kWh", freq="h")
    assert not by_ds(start).loc[at("2025-08-01 00:00"), "valid"]


def test_cumulative_register_with_reset_and_gap() -> None:
    t = pd.date_range("2025-08-01 00:00", periods=8, freq="h")
    reading = [100.0, 101.0, 103.0, 0.5, 1.5, np.nan, 4.5, 5.0]  # reset after 103; 05:00 missing
    df = pd.DataFrame({"t": t, "kwh": reading})
    s = read_table(df, time_column="t", value_columns="kwh", tz=TZ, unit="kWh", kind="cumulative")
    h = by_ds(s)["y"]
    assert h[at("2025-08-01 00:00")] == 1.0 and h[at("2025-08-01 01:00")] == 2.0
    assert np.isnan(h[at("2025-08-01 02:00")])  # 103 -> 0.5: reset, invalid
    assert h[at("2025-08-01 03:00")] == 1.0
    assert np.isnan(h[at("2025-08-01 04:00")]) and np.isnan(h[at("2025-08-01 05:00")])  # around the gap
    assert h[at("2025-08-01 06:00")] == 0.5
    assert len(h) == 7  # the last reading closes the last interval
    assert s.provenance is not None and "1 negative register difference" in s.provenance.notes
    # Wh register summed to 2-hour steps
    wh = read_table(
        df.assign(kwh=df["kwh"] * 1000),
        time_column="t",
        value_columns="kwh",
        tz=TZ,
        unit="Wh",
        kind="cumulative",
        freq="2h",
        min_coverage=0.5,
    )
    assert by_ds(wh).loc[at("2025-08-01 00:00"), "y"] == pytest.approx(3.0)


def test_average_power_to_energy() -> None:
    t = pd.date_range("2025-08-01 00:00", periods=8, freq="15min")
    df = pd.DataFrame({"t": t, "p": 1000.0, "q": 2.0})
    s = read_table(df, time_column="t", value_columns=["p"], tz=TZ, unit="W", kind="power", freq="h")
    assert s.frame["y"].tolist() == [1.0, 1.0]
    kw = read_table(df, time_column="t", value_columns="q", tz=TZ, unit="kW", kind="power")
    assert kw.frame["y"].iloc[0] == pytest.approx(0.5)


def test_several_columns_and_names(tmp_path: Path) -> None:
    lines = ["time,import,export"] + [
        f"{t:%Y-%m-%dT%H:%M:%S},1.25,0.5" for t in pd.date_range("2025-08-01", periods=4, freq="h")
    ]
    f = tmp_path / "m.csv"
    f.write_text("\n".join(lines))
    s = read_table(f, time_column="time", value_columns=["import", "export"], tz=TZ, unit="kWh")
    assert s.series == ["export", "import"] and s.freq == "h"
    assert by_ds(s, "import")["y"].iloc[0] == 1.25
    named = read_table(
        f, time_column="time", value_columns=["import", "export"], tz=TZ, unit="kWh", names=["imp", "exp"]
    )
    assert named.series == ["exp", "imp"]


def test_times_with_offset_are_converted() -> None:
    df = pd.DataFrame({"t": ["2025-08-01T03:00:00Z", "2025-08-01T04:00:00Z"], "e": [1.0, 2.0]})
    s = read_table(df, time_column="t", value_columns="e", tz=TZ, unit="kWh")
    assert s.frame["ds"].iloc[0] == at("2025-08-01 00:00")


def test_duplicates_dropped_and_counted() -> None:
    t = list(pd.date_range("2025-08-01", periods=3, freq="h"))
    df = pd.DataFrame({"t": [*t, t[1]], "e": [1.0, 2.0, 3.0, 9.0]})
    s = read_table(df, time_column="t", value_columns="e", tz=TZ, unit="kWh")
    assert s.frame["y"].tolist() == [1.0, 2.0, 3.0]
    assert s.provenance is not None and "1 duplicate timestamp" in s.provenance.notes


def test_excel_input(tmp_path: Path) -> None:
    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["export of meter 123"])
    ws.append(["Timestamp", "kWh"])
    for t in pd.date_range("2025-08-01", periods=4, freq="30min"):
        ws.append([t.to_pydatetime(), 0.5])
    f = tmp_path / "m.xlsx"
    wb.save(f)
    s = read_table(f, time_column="Timestamp", value_columns="kWh", tz=TZ, unit="kWh", skiprows=1, freq="h")
    assert s.frame["y"].tolist() == [1.0, 1.0]


def test_unit_and_column_errors() -> None:
    df = pd.DataFrame({"t": pd.date_range("2025-08-01", periods=2, freq="h"), "e": [1.0, 2.0]})
    with pytest.raises(ValueError, match="kind='power'"):
        read_table(df, time_column="t", value_columns="e", tz=TZ, unit="kW")
    with pytest.raises(ValueError, match="power unit"):
        read_table(df, time_column="t", value_columns="e", tz=TZ, unit="kWh", kind="power")
    with pytest.raises(ValueError, match="not in the table"):
        read_table(df, time_column="t", value_columns="x", tz=TZ, unit="kWh")
    with pytest.raises(ValueError, match="shorter"):
        read_table(df, time_column="t", value_columns="e", tz=TZ, unit="kWh", freq="15min")


def test_module_exports() -> None:
    assert meter.read_table is read_table
