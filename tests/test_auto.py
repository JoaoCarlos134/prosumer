"""`prosumer.io.auto`: a file of unknown layout is recognised and its energy column chosen by name and unit.

The layouts are synthetic; the Solar.web one copies the header of a real export (seen 2026-10-16: the AC
current comes before the energy, units in brackets, a site-total column without a device)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prosumer.io import auto, read_energy, sniff

TZ = "America/Sao_Paulo"
T = pd.date_range("2025-08-01", periods=72, freq="h")
SUN = np.clip(np.sin((T.hour.to_numpy() - 6) / 12 * np.pi), 0, None)


def _csv(path: Path, frame: pd.DataFrame, **kw: object) -> Path:
    frame.to_csv(path, index=False, **kw)  # type: ignore[arg-type]
    return path


def test_solarweb_export_reads_the_energy_not_the_current(tmp_path: Path) -> None:
    dev = "Symo 12.0-3 208-240 (1)"
    t5 = pd.date_range("2025-08-01 10:00", periods=24, freq="5min")
    lines = [
        f"Data e horário,Corrente CA L1 | {dev},Energia | {dev},Energia MPP1 | {dev},Produção fotovoltaica",
        "[dd.MM.yyyy HH:mm],[A],[Wh],[Wh],[Wh]",
        *[f"{t:%d.%m.%Y %H:%M},17.5,250,125,250" for t in t5],
    ]
    f = tmp_path / "export.csv"
    f.write_text("\n".join(lines), encoding="utf-8")
    assert sniff(f).format == "solarweb"
    s = read_energy(f, tz=TZ)
    assert s.series == [dev]
    assert s.frame["y"].iloc[0] == pytest.approx(12 * 0.25)  # kWh of the hour, not amperes
    assert s.provenance is not None and "Solar.web" in s.provenance.notes


@pytest.mark.parametrize(
    ("frame", "column", "total"),
    [
        (pd.DataFrame({"time": T, "value": SUN}), "value", SUN.sum()),
        (
            pd.DataFrame({"Timestamp": T, "Voltage (V)": 230.0, "Energy (kWh)": SUN}),
            "Energy (kWh)",
            SUN.sum(),
        ),
        (pd.DataFrame({"datetime": T, "PV power [W]": SUN * 3000}), "PV power [W]", SUN.sum() * 3),
    ],
)
def test_generic_tables(tmp_path: Path, frame: pd.DataFrame, column: str, total: float) -> None:
    f = _csv(tmp_path / "t.csv", frame)
    found = sniff(f)
    assert found.format == "table" and found.value_column == column
    assert read_energy(f, tz=TZ).frame["y"].sum() == pytest.approx(total)


def test_units_row_and_brazilian_numbers(tmp_path: Path) -> None:
    units = pd.DataFrame({"Zeit": ["[dd.MM.yyyy]"], "Ertrag": ["[kWh]"], "Strom": ["[A]"]})
    body = pd.DataFrame({"Zeit": T.strftime("%d.%m.%Y %H:%M"), "Ertrag": SUN, "Strom": 9.0})
    f = _csv(tmp_path / "u.csv", pd.concat([units, body]))
    found = sniff(f)
    assert found.units_row and found.value_column == "Ertrag" and found.unit == "kWh"
    assert read_energy(f, tz=TZ).frame["y"].sum() == pytest.approx(SUN.sum())
    br = tmp_path / "br.csv"
    br.write_text(
        "Data;Consumo (kWh)\n"
        + "\n".join(f"{t:%d/%m/%Y %H:%M};{v:.3f}".replace(".", ",") for t, v in zip(T, SUN, strict=True)),
        encoding="utf-8",
    )
    assert read_energy(br, tz=TZ, quantity="consumption").frame["y"].sum() == pytest.approx(
        SUN.sum(), abs=0.01
    )


def test_ambiguous_or_missing_energy_is_an_error_with_the_columns(tmp_path: Path) -> None:
    f = _csv(tmp_path / "a.csv", pd.DataFrame({"time": T, "import_kWh": SUN, "export_kWh": SUN}))
    with pytest.raises(ValueError, match="Several columns could be the energy"):
        sniff(f)
    assert read_energy(f, tz=TZ, value_column="export_kWh").series == ["export_kWh"]  # the person says which
    g = _csv(tmp_path / "b.csv", pd.DataFrame({"time": T, "Current (A)": 9.0, "Voltage (V)": 230.0}))
    with pytest.raises(ValueError, match="No energy column recognised"):
        sniff(g)


def test_daily_export_says_to_export_the_detailed_data(tmp_path: Path) -> None:
    days = pd.date_range("2025-08-01", periods=10, freq="D")
    lines = [
        "Data e horário,Energia por retificador alternado | Primo 4.0-1 (1),Instalação total",
        "[dd.MM.yyyy],[kWh],[kWh]",
        *[f"{d:%d.%m.%Y},16.3,16.3" for d in days],
    ]
    f = tmp_path / "daily.csv"
    f.write_text("\n".join(lines), encoding="utf-8")
    with pytest.raises(ValueError, match="one value per day"):
        read_energy(f, tz=TZ)


def test_formats_registry_is_public() -> None:
    assert [name for name, _ in auto.FORMATS] == ["solarweb"]


# ---------------------------------------------------------------- counters (a real Growatt export)
GROWATT = Path(__file__).parent / "fixtures" / "growatt_inverter_telemetry_2026-03-13_14.csv"


def test_growatt_daily_counter_is_read_as_a_counter_not_as_interval_energy() -> None:
    """Regression (2026-10-17): on a real Growatt export (3 kW, India, CC BY 4.0) the only column with an
    energy unit is `E-Today (kWh)`, a counter that restarts every day. It was read as the energy of each
    5-minute row: ~1,000 kWh a day from a 3 kW system, without any error. Each day must add up to its last
    reading."""
    raw = pd.read_csv(GROWATT, parse_dates=["Timestamp"])
    last = raw.groupby(raw["Timestamp"].dt.date)["E-Today (kWh)"].max()
    s = read_energy(GROWATT, tz="Asia/Kolkata", quantity="generation")
    f = s.frame
    daily = f.groupby(f["ds"].dt.date)["y"].sum()
    for day, total in last.items():
        assert daily[day] == pytest.approx(total, abs=0.15)  # 0.1 kWh counter resolution
    assert f["y"].max() < 3.5  # never more than the system can make in an hour
    assert s.provenance is not None and "counter" in s.provenance.notes
    # it agrees with the AC power the inverter logged, integrated over its own steps (within 5% a day)
    dt = raw["Timestamp"].diff().dt.total_seconds().clip(upper=600).fillna(300)
    ac = (raw["AC Power (W)"] * dt).groupby(raw["Timestamp"].dt.date).sum() / 3.6e6
    for day in last.index:
        assert daily[day] == pytest.approx(ac[day], rel=0.05)


def test_interval_energy_is_not_mistaken_for_a_counter(tmp_path: Path) -> None:
    """The counter test looks at the values: energy per interval rises and falls with the sun."""
    t = pd.date_range("2025-06-01 05:00", "2025-06-03 19:00", freq="15min")
    sun = np.clip(np.sin((t.hour.to_numpy() + t.minute.to_numpy() / 60 - 6) / 12 * np.pi), 0, None)
    path = tmp_path / "pv.csv"
    pd.DataFrame({"time": t, "Energy (kWh)": np.round(0.5 * sun, 3)}).to_csv(path, index=False)
    s = read_energy(path, tz="UTC", quantity="generation")
    assert s.provenance is not None and "kind interval" in s.provenance.notes
    assert s.frame["y"].sum() == pytest.approx(np.round(0.5 * sun, 3).sum())


def test_a_lifetime_register_is_differenced(tmp_path: Path) -> None:
    t = pd.date_range("2025-06-01 00:00", periods=96, freq="15min")
    load = 0.2 + 0.1 * (t.hour.to_numpy() >= 18)
    path = tmp_path / "meter.csv"
    pd.DataFrame({"time": t, "Total import (kWh)": 1500.0 + np.cumsum(load)}).to_csv(path, index=False)
    s = read_energy(path, tz="UTC", quantity="consumption", freq=None)
    assert s.frame["y"].sum() == pytest.approx(load[1:].sum())  # the first reading opens the first interval
    assert s.provenance is not None and "register" in s.provenance.notes
    hourly = read_energy(path, tz="UTC", quantity="consumption")  # the last hour has 3 of its 4 quarters
    assert hourly.frame["valid"].sum() == 23 and not hourly.frame["valid"].iloc[-1]
