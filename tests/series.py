"""Test helper: an hourly `EnergySeries` from an array of values (the economics tests' synthetic sites)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from prosumer import EnergySeries

TZ = "Etc/GMT+3"  # a fixed offset: no clock change in the bills worked out by hand


def hourly(values: np.ndarray, start: str, quantity: str, uid: str = "site", tz: str = TZ) -> EnergySeries:
    ds = pd.date_range(start, periods=len(values), freq="h", tz=tz)
    return EnergySeries.from_dataframe(
        pd.DataFrame({"unique_id": uid, "ds": ds, "y": values}),
        unit="kWh",
        quantity=quantity,  # type: ignore[arg-type]
        tz=tz,
        freq="h",
    )
