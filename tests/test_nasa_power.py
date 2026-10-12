"""NASA POWER reader, without the network: a fake API answers in the point API's JSON shape (UTC stamps)."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from prosumer.io import nasa_power as npw


class FakePOWER:
    """Answers like the hourly point API with `time-standard=UTC`: value = f(UTC hour), records the calls."""

    def __init__(self, f: Any = None, *, fill: float = -999.0) -> None:
        self.f = f or (lambda key, t: np.arange(len(t), dtype=float) + 1000 * (t.year - 2020))
        self.fill, self.calls = fill, []

    def __call__(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        assert url == npw.URL and params["time-standard"] == "UTC" and params["format"] == "JSON"
        self.calls.append(params)
        t = pd.date_range(
            pd.Timestamp(params["start"]), pd.Timestamp(params["end"]) + pd.Timedelta(hours=23), freq="h"
        )
        block = {}
        for key in params["parameters"].split(","):
            v = np.asarray(self.f(key, t), dtype=float)
            block[key] = {f"{x:%Y%m%d%H}": float(y) for x, y in zip(t, v, strict=True)}
        return {"header": {"fill_value": self.fill}, "properties": {"parameter": block}}


def _utc_hour(key: str, t: pd.DatetimeIndex) -> np.ndarray:
    return t.hour.to_numpy(dtype=float) + (100.0 if key == "T2M" else 0.0)


def test_utc_stamps_are_interval_starts_converted_to_the_local_zone() -> None:
    api = FakePOWER(_utc_hour)
    out = npw.fetch_hourly(-24.83, -53.65, start="2025-08-01", end="2025-08-02", tz="Etc/GMT+3", get=api)
    assert list(out.columns) == ["ds", "ghi", "clear_sky_ghi", "temperature"]
    assert len(out) == 48 and out["ds"].iloc[0] == pd.Timestamp("2025-08-01", tz="Etc/GMT+3")
    # local 00:00 at UTC-3 is 03 UTC: no shift, only the time zone
    assert out["ghi"].iloc[0] == 3.0 and out["temperature"].iloc[0] == 103.0
    p = api.calls[0]
    assert p["parameters"] == "ALLSKY_SFC_SW_DWN,CLRSKY_SFC_SW_DWN,T2M"
    assert (p["start"], p["end"]) == ("20250801", "20250803")  # the last local hours are 01-02 UTC next day
    assert p["community"] == "RE" and (p["latitude"], p["longitude"]) == (-24.83, -53.65)


def test_daylight_saving_neither_duplicates_nor_drops_hours() -> None:
    out = npw.fetch_hourly(
        52.14, -10.27, start="2020-10-24", end="2020-10-26", tz="Europe/Dublin", get=FakePOWER()
    )
    assert out["ds"].is_unique and out["ds"].diff().dropna().eq(pd.Timedelta(hours=1)).all()
    assert len(out) == 3 * 24 + 1  # 25 October 2020 has 25 hours in Dublin
    assert out["ghi"].notna().all()


def test_fill_value_becomes_nan() -> None:
    def holes(key: str, t: pd.DatetimeIndex) -> np.ndarray:
        return np.where(t.hour == 12, -999.0, 5.0)

    out = npw.fetch_hourly(
        0, 0, start="2024-01-01", end="2024-01-01", variables=["ghi"], get=FakePOWER(holes)
    )
    assert out["ghi"].isna().sum() == 1 and out.loc[out["ds"].dt.hour == 12, "ghi"].isna().all()
    other = FakePOWER(lambda k, t: np.where(t.hour == 3, -1.0, 5.0), fill=-1.0)
    assert npw.fetch_hourly(0, 0, start="2024-01-01", end="2024-01-01", get=other)["ghi"].isna().sum() == 1


def test_long_periods_are_split_and_joined_without_repeats() -> None:
    api = FakePOWER()
    out = npw.fetch_hourly(
        0, 0, start="2020-12-20", end="2021-01-10", variables=["ghi"], chunk_days=7, get=api, pause_s=0
    )
    assert len(api.calls) == 4  # 22 UTC days in chunks of 7
    assert len(out) == 22 * 24 and out["ds"].is_unique and out["ghi"].notna().all()
    assert api.calls[1]["start"] == "20201227" and api.calls[-1]["end"] == "20210110"


def test_coverage_finds_where_the_hourly_product_ends() -> None:
    def ends(key: str, t: pd.DatetimeIndex) -> np.ndarray:
        return np.where(t >= pd.Timestamp("2026-05-21"), -999.0, 1.0)

    out = npw.fetch_hourly(0, 0, start="2026-05-01", end="2026-05-31", variables=["ghi"], get=FakePOWER(ends))
    c = npw.coverage(out).set_index("variable")
    assert c.loc["ghi", "last"] == pd.Timestamp("2026-05-20 23:00", tz="UTC")
    assert c.loc["ghi", "fraction"] == pytest.approx(20 / 31)
    assert npw.coverage(out, start="2026-05-01", end="2026-05-10").loc[0, "fraction"] == 1.0


def test_arguments_and_errors() -> None:
    api = FakePOWER()
    with pytest.raises(ValueError, match="Unknown variables"):
        npw.fetch_hourly(0, 0, start="2024-01-01", end="2024-01-01", variables=["snow"], get=api)
    with pytest.raises(ValueError, match="end is before start"):
        npw.fetch_hourly(0, 0, start="2024-01-02", end="2024-01-01", get=api)
    with pytest.raises(RuntimeError, match="did not return"):
        npw.parse_hourly({"properties": {"parameter": {}}}, {"T2M": "temperature"}, tz="UTC")
    with pytest.raises(RuntimeError, match="NASA POWER"):
        npw.parse_hourly({"messages": ["bad request"]}, {"T2M": "temperature"}, tz="UTC")
    assert len(npw.VARIABLES) <= npw.MAX_PARAMETERS
