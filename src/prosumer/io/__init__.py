"""Reading data from outside: weather forecasts (Open-Meteo) and the weather of the day itself (NASA POWER);
inverters and meters later (step E2).

Every reader returns frames in the library's conventions: `ds` time-zone aware, interval values labelled by
the START of the interval, one column per variable.
"""

from __future__ import annotations

from . import nasa_power, open_meteo

__all__ = ["nasa_power", "open_meteo"]
