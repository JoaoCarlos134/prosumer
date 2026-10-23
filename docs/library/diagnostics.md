# Diagnostics

All from the AC energy and the site alone: no irradiance sensor, no DC data.

## The clock of the data

A PV series carries its own clock check: the panels produce only while the sun is up, and the sun's position is
known for any place and time. `quality.clock_offset(series, site)` compares the mean daily profile, shifted
step by step, with the clear-sky profile of the same days at the site (on a set of plane orientations, since
the roof is unknown) and says how many hours the labels are late, for the whole series and per month, with a
confidence from the share of days that agree.

```python
import pandas as pd
from prosumer import EnergySeries, data, quality

pv, _ = data.example_plant(n_series=1, days=60)
late = pv.frame.assign(ds=pv.frame["ds"] + pd.Timedelta(hours=1))  # stamps one hour late
s = EnergySeries.from_dataframe(late, unit="kWh", quantity="generation", tz=pv.tz, freq="h")
t = quality.clock_offset(s, (-25.43, -49.27))
assert t.loc[t["period"] == "all", "offset_h"].iloc[0] == 1
print(quality.clock_notes(t))
```

Typical causes: a file in UTC read as local time, a logger that ignores daylight saving (0 in part of the year,
+-1 h in the other), stamps that mark the END of the interval (+1 step). `quality.clock_offset_weather` lines
up the clouds instead of the daily shape, against a measured or forecast irradiance: it resolves fractions of
an hour and ignores the roof's orientation.

## Roof, performance and its steps

```python
from prosumer import data, diagnostics

pv, _ = data.example_plant(n_series=1, days=400)
d = diagnostics.diagnose(pv, (-25.43, -49.27), kwp=3.0)
print(d.orientation)  # tilt, azimuth (compass bearing, 180 = south), fit R2, on the edge, reliable
print(d.notes)
assert {"tilt", "azimuth", "r2", "reliable"} <= set(d.orientation.columns)
assert {"trend_reported", "loss_reported"} <= set(d.segments.columns)
```

`diagnose` finds the clear days in the series itself, fits the roof's orientation on them, computes a
clear-day performance index (energy / clear-sky irradiation on the panel plane; a performance ratio with
`kwp`), and splits it into straight segments with change points (dynamic programming, BIC penalty): a step
up is usually a cleaning, a step down a fault or a lost string, a slope soiling or degradation. With a poor
fit or a roof on the edge of the search grid, steps are reported as uncertain and no trend is drawn.
The tables say what the notes report, for a page that shows numbers: `orientation.reliable` (given, or a
good fit not on the edge) and, on a series' last segment, `trend_reported` (a fall of at least
`trend_note_pct` a year over at least a year) and `loss_reported` (`step_note_pct` below the best level). A
known roof goes in as `diagnose(orientation=(tilt, azimuth))`, `analyze(orientation=...)` or the app's
`tilt`/`azimuth`.

Every threshold is an argument (`analyze(diagnostics_options={...})` passes them by name); the change-point
penalty and the clear-day rule were chosen on the project's own sites, and a note says so when their defaults
are used. See [Tuning](tuning.md).

Not available yet: telling soiling from shading or a string fault, which needs DC or 5-minute data.
