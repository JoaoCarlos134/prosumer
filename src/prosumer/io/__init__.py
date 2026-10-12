"""Reading data from outside: weather forecasts (Open-Meteo), the weather of the day itself (NASA POWER),
inverter exports (Fronius Solar.web) and meter tables (any CSV/Excel of energy or power readings).

Every reader returns data in the library's conventions: `ds` time-zone aware, interval values labelled by
the START of the interval, one column (weather) or one series (`EnergySeries`, kWh) per variable or device.
"""

from __future__ import annotations

from . import fronius, meter, nasa_power, open_meteo
from .fronius import read_solarweb, read_solarweb_raw
from .meter import read_table

__all__ = ["fronius", "meter", "nasa_power", "open_meteo", "read_solarweb", "read_solarweb_raw", "read_table"]
