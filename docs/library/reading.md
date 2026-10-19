# Reading data

Everything in the library works on an `EnergySeries`: a validated long frame (`unique_id`, `ds`, `y`, `valid`)
with a unit, a quantity (`generation` or `consumption`), a time zone and a step. A gap and a zero are not the
same thing: an inverter logs zero at night (valid) and nothing when it is down (invalid), so validity is a
column, never a convention.

## A file of unknown layout

```python
from prosumer.io import read_energy, sniff

path = "tests/fixtures/growatt_inverter_telemetry_2026-03-13_14.csv"  # a real Growatt export (CC BY 4.0)
print(sniff(path).why)
pv = read_energy(path, tz="Asia/Kolkata", quantity="generation")
daily = pv.frame.groupby(pv.frame["ds"].dt.date)["y"].sum()
assert 13 < daily.iloc[0] < 16  # kWh of a 3 kW rooftop on a sunny day
```

`read_energy` never picks a column by its position. A known export format goes to its own reader (today
Fronius Solar.web); any other table is read by what its columns say: the time column is the one whose cells
parse as times, the energy column is the one with an energy unit (kWh, Wh) or, failing that, a power unit (kW,
W), never current, voltage, power factor, frequency, temperature or irradiance. An ambiguous file is an error
that lists the candidates, never a guess. What was chosen goes into `pv.provenance.notes`.

**Counters.** An energy column can be the energy of each row, or a counter: a lifetime register, or an
inverter's "energy today" that restarts at midnight (Growatt's `E-Today`). The values decide, never the name:
a column that never falls within a day (small dips aside) and grows in at least a fifth of the steps is read
as a counter, each step being the difference of two readings. Readings are taken as they come (loggers drift a
second per step), a single reading that jumps away and straight back is dropped, and a drop across midnight
is a restart from zero. Read as the energy of each row, the Growatt counter above gave ~1,000 kWh a day.

## Known formats and meters

```python
import pandas as pd
from prosumer.io import read_table

t = pd.date_range("2025-08-01", periods=8, freq="15min")
meter = pd.DataFrame({"Data/Hora": t.strftime("%d/%m/%Y %H:%M"), "Consumo (kWh)": ["1,5"] * 8})
s = read_table(meter, time_column="Data/Hora", value_columns="Consumo (kWh)", tz="America/Sao_Paulo",
               unit="kWh", freq="h")
assert s.frame["y"].tolist() == [6.0, 6.0]
```

- `io.fronius.read_solarweb`: Fronius Solar.web exports (5-minute, one series per inverter).
- `io.meter.read_table`: any CSV/Excel table: `kind="interval"` (energy per row), `"cumulative"` (a counter,
  `resets="invalid"` or `"restart"`) or `"power"` (average power per row); `label="end"` when stamps mark
  the end of their interval; `;` separators and decimal commas are guessed.
- `io.pvdaq`: NREL PVDAQ systems (USA, CC BY 4.0), with their orientation in the metadata. The column names
  do not say the unit reliably, so the unit is inferred from the nameplate.
- `data.dingle_houses`: the 20 Dingle houses (Ireland, CC0), downloaded once and cached.
- Weather: `io.open_meteo` (the archive of day-ahead runs and the live forecast, several models),
  `io.nasa_power` (the day's own weather, a ceiling, never an operational input).

## Time zones and daylight saving

`tz` is the zone of the result and, by default, of the file's naive times. A logger that writes UTC (no gap or
repeat at the daylight saving changes) is read with `source_tz="UTC"`. A file in local time with the repeated
autumn hour merged into one row cannot be placed: `dst="raise"` (default) says so, `dst="drop"` removes those
rows with a warning. Never assume the zone of a file: with a site, `analyze` checks the clock against the sun
([Diagnostics](diagnostics.md)).

## Steps

`analyze` and `forecast_ahead` work hourly. A 15-minute meter or a 1-minute logger is summed into hours on its
own (an hour counts when at least 11/12 of it was measured), with a note; `EnergySeries.resample("h")` does it
explicitly.

```python
from prosumer import data

quarter = data.example_house(n_series=1, days=3, freq="15min")
hourly = quarter.resample("h")
assert hourly.freq == "h" and abs(hourly.frame["y"].sum() - quarter.frame["y"].sum()) < 1e-9
```
