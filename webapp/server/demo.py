"""The demo: a real house with PV, moved in time so the forecast follows on from its data.

House H1 of the Dingle Peninsula dataset (Ireland, 2020, hourly kWh): Khadem et al. (2024), Scientific Data,
doi:10.1038/s41597-024-03454-2; files on figshare, doi:10.6084/m9.figshare.c.6829134, licence CC0. The file
`demo/dingle_H1_2020.csv` is the library benchmark's hourly version of it (Dublin wall clock, gap-free grid).

The data are from 2020; a forecast from them would start in 2021. So the demo moves every day by whole
multiples of 52 weeks (364 days) to the last 365 days before today: the same weekday, the season within about
a week. The files are written on a UTC clock (`file_times: "UTC"`), each hour taking the value of the same
wall-clock hour of its 2020 day, as a logger in Dublin would record it.
"""

from __future__ import annotations

import datetime as dt
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# in the standalone folder (PyInstaller) the demo file sits in sys._MEIPASS/server/demo
HERE = Path(sys._MEIPASS) / "server" if hasattr(sys, "_MEIPASS") else Path(__file__).resolve().parent
SOURCE = HERE / "demo" / "dingle_H1_2020.csv"
TZ = "Europe/Dublin"
WEEKS_52 = pd.Timedelta(days=364)
CITATION = (
    "Khadem, S. et al. (2024). Comprehensive Dataset on Electrical Load Profiles for Energy Community in "
    "Ireland. Scientific Data. doi:10.1038/s41597-024-03454-2. Data: figshare, "
    "doi:10.6084/m9.figshare.c.6829134 (CC0)."
)
COLUMNS = {"generation": "production (kWh)", "consumption": "consumption (kWh)"}
_SOURCE_COLUMNS = {"generation": "production_kWh", "consumption": "consumption_kWh"}

# what the demo asks of `prosumer.app.run`: Dingle town (rounded), the files' UTC clock, an example
# time-of-use price (not a real Irish tariff)
REQUEST: dict[str, Any] = {
    "latitude": 52.14,
    "longitude": -10.27,
    "timezone": TZ,
    "file_times": "UTC",
    "days": 7,
    "price": {
        "kind": "tou",
        "peak_hours": "17-19",
        "peak_price": 0.45,
        "offpeak_price": 0.30,
        "export_price": 0.20,
        "currency": "EUR",
        "scheme": "net_billing",
    },
}


@lru_cache(maxsize=1)
def _source() -> pd.DataFrame:
    s = pd.read_csv(SOURCE)
    s["time"] = pd.to_datetime(s["time"], format="%Y-%m-%d %H:%M")
    return s.set_index("time").sort_index()


def frame(today: dt.date | None = None) -> pd.DataFrame:
    """The 365 days before `today` (Dublin), hourly on a UTC clock: `time` (UTC, naive), `production_kWh`,
    `consumption_kWh`."""
    src = _source()
    today = today or pd.Timestamp.now(tz=TZ).date()
    end = pd.Timestamp(today).tz_localize(TZ)  # midnight of today, Dublin
    start = (pd.Timestamp(today) - pd.Timedelta(days=365)).tz_localize(TZ)
    utc = pd.date_range(start.tz_convert("UTC"), end.tz_convert("UTC"), freq="h", inclusive="left")
    wall = utc.tz_convert(TZ).tz_localize(None)
    # the smallest number of 52-week steps that brings each wall-clock hour back into the 2020 data
    k = np.ceil((wall - src.index.max()) / WEEKS_52).astype(int)
    back = wall - WEEKS_52 * k
    back = back.where(back >= src.index.min(), back + WEEKS_52)
    values = src.reindex(back)
    return pd.DataFrame(
        {
            "time": utc.tz_localize(None),
            "production_kWh": values["production_kWh"].to_numpy(),
            "consumption_kWh": values["consumption_kWh"].to_numpy(),
        }
    )


def csv(quantity: str, today: dt.date | None = None) -> bytes:
    """One of the demo's two files, as a logger would export it: `time (UTC)` and the energy column."""
    f = frame(today)
    out = pd.DataFrame(
        {
            "time (UTC)": f["time"].dt.strftime("%Y-%m-%d %H:%M"),
            COLUMNS[quantity]: f[_SOURCE_COLUMNS[quantity]].round(4),
        }
    )
    return out.to_csv(index=False).encode("utf-8")


def files(today: dt.date | None = None) -> dict[str, tuple[bytes, str]]:
    """Both files, keyed as `prosumer.app.run` takes them."""
    return {q: (csv(q, today), f"dingle_H1_{q}.csv") for q in COLUMNS}


INFO = {
    "name": "Dingle H1",
    "place": "Dingle Peninsula, Ireland",
    "license": "CC0-1.0",
    "citation": CITATION,
    "url": "https://doi.org/10.6084/m9.figshare.c.6829134",
}
