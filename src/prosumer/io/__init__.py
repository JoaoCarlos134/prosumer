"""Reading data from outside: weather forecasts now; inverters, meters and measured weather later (step E2).

Every reader returns frames in the library's conventions: `ds` time-zone aware, interval values labelled by
the START of the interval, one column per variable.
"""

from __future__ import annotations

from . import open_meteo

__all__ = ["open_meteo"]
