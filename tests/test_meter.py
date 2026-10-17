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
    assert s.provenance is not None and "1 counter reset(s) made invalid" in s.provenance.notes
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


def test_counter_read_as_logged_drift_dips_and_daily_restart() -> None:
    """Regression (2026-10-17, a real Growatt export): readings drift a second per step, so the counter path
    must not snap them to a clock grid; small dips are kept (the steps add up to the counter's difference);
    each day adds up to its last reading, a bright one (12 kWh) and a dull one (0.5 kWh)."""
    t0 = pd.Timestamp("2026-03-13 05:00:00")
    times, values = [], []
    for day, total in ((0, 12.0), (1, 0.5)):
        e = 0.0
        for k in range(12 * 14):  # 05:00-19:00, every 5 min + 1 s
            times.append(t0 + pd.Timedelta(days=day) + pd.Timedelta(seconds=301 * k))
            values.append(round(e, 1))
            e += total / (12 * 14)
    values[50] = values[49] - 0.1  # a dip read back
    df = pd.DataFrame({"t": [x.strftime("%Y-%m-%d %H:%M:%S") for x in times], "e": values})
    s = read_table(
        df,
        time_column="t",
        value_columns="e",
        tz=TZ,
        unit="kWh",
        kind="cumulative",
        freq="h",
        resets="restart",
    )
    f = by_ds(s)
    daily = f["y"].groupby(f.index.normalize()).sum()
    assert daily.iloc[0] == pytest.approx(values[12 * 14 - 1], abs=1e-9)  # the day's last reading
    assert daily.iloc[1] == pytest.approx(values[-1], abs=1e-9)
    assert f.loc[at("2026-03-13 10:00"), "valid"]  # drifting readings fill their hours
    assert s.provenance is not None and "1 small decrease(s) kept" in s.provenance.notes
    # the night gap (19:00 -> 05:00) is not energy: its interval is invalid, whatever the reset rule
    assert not f.loc[at("2026-03-13 22:00"), "valid"]
    with pytest.raises(ValueError, match="resets"):
        read_table(df, time_column="t", value_columns="e", tz=TZ, unit="kWh", kind="cumulative", resets="x")


def test_counter_restart_without_a_gap_takes_the_new_reading() -> None:
    t = pd.date_range("2025-08-01 22:00", periods=5, freq="h")  # a logger awake all night
    df = pd.DataFrame({"t": t, "e": [9.0, 9.5, 0.2, 0.4, 0.6]})  # midnight reset between 23:00 and 00:00
    restart = read_table(
        df, time_column="t", value_columns="e", tz=TZ, unit="kWh", kind="cumulative", resets="restart"
    )
    assert by_ds(restart).loc[at("2025-08-01 23:00"), "y"] == pytest.approx(0.2)
    invalid = read_table(df, time_column="t", value_columns="e", tz=TZ, unit="kWh", kind="cumulative")
    assert np.isnan(by_ds(invalid).loc[at("2025-08-01 23:00"), "y"])
    # a dull day: the drop at midnight (0.5) is smaller than ten typical steps, but it is still a restart
    dull = df.assign(e=[0.4, 0.5, 0.0, 0.1, 0.2])
    r = read_table(
        dull, time_column="t", value_columns="e", tz=TZ, unit="kWh", kind="cumulative", resets="restart"
    )
    assert by_ds(r).loc[at("2025-08-01 23:00"), "y"] == pytest.approx(0.0)  # never -0.5


def test_counter_spike_is_dropped_and_a_midday_restart_counts_from_zero() -> None:
    """Both patterns of the real Growatt export (2026-10-17): an extra off-cycle row with a wrong high value
    between two regular readings (07:55:25 13.4 between 0.2 and 0.2), and an inverter restart at midday whose
    `E-Today` starts again from zero (4.9 -> 0.2 -> 0.4 ...)."""
    t = list(pd.date_range("2026-03-30 07:40", periods=6, freq="5min"))
    t.insert(3, pd.Timestamp("2026-03-30 07:53:00"))  # the extra row
    e = [0.1, 0.2, 0.2, 13.4, 0.3, 0.4, 0.5]
    t += list(pd.date_range("2026-03-30 08:10", periods=6, freq="5min"))
    e += [0.6, 0.7, 0.1, 0.2, 0.3, 0.4]  # restart between 08:15 and 08:20
    df = pd.DataFrame({"t": t, "e": e})
    s = read_table(
        df, time_column="t", value_columns="e", tz=TZ, unit="kWh", kind="cumulative", resets="restart"
    )
    y = s.frame["y"]
    assert y.max() < 1.0  # no 13 kWh step
    assert y.sum() == pytest.approx((0.7 - 0.1) + 0.1 + (0.4 - 0.1))  # before, the restart, after
    assert s.provenance is not None and "1 outlier reading(s) dropped" in s.provenance.notes
    assert "1 counter reset(s) taken as a restart" in s.provenance.notes
    # a wobble at the counter's resolution near dawn is not a restart
    dawn = pd.DataFrame(
        {"t": pd.date_range("2026-03-30 06:00", periods=5, freq="5min"), "e": [0.2, 0.3, 0.2, 0.3, 0.4]}
    )
    w = read_table(
        dawn, time_column="t", value_columns="e", tz=TZ, unit="kWh", kind="cumulative", resets="restart"
    )
    assert w.frame["y"].sum() == pytest.approx(0.2) and "0 counter reset(s)" in w.provenance.notes


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


def test_naive_utc_file_across_daylight_saving() -> None:
    # regression (2026-10-16): a logger writing naive UTC across Dublin's October change raised an error
    # that said "pass source_tz='UTC'", but read_table had no such argument
    t = pd.date_range("2020-10-24 22:00", "2020-10-25 04:00", freq="h")  # naive UTC, no repeat
    df = pd.DataFrame({"t": t, "e": np.arange(len(t), dtype=float)})
    with pytest.raises(Exception, match="source_tz"):
        read_table(df, time_column="t", value_columns="e", tz="Europe/Dublin", unit="kWh")
    s = read_table(df, time_column="t", value_columns="e", tz="Europe/Dublin", unit="kWh", source_tz="UTC")
    ds = s.frame["ds"]
    assert len(ds) == len(t) and ds.is_monotonic_increasing
    assert ds.iloc[0] == pd.Timestamp("2020-10-24 23:00", tz="Europe/Dublin")  # IST = UTC+1
    assert (ds.dt.strftime("%H:%M") == "01:00").sum() == 2  # the repeated hour, once per offset
    assert s.frame["y"].tolist() == list(range(len(t)))


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
