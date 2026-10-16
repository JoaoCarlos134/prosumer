"""prosumer.io.pvdaq on a real excerpt of NREL PVDAQ system 50 (CC BY 4.0) and a fake bucket (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from prosumer.io import pvdaq

FIX = Path(__file__).parent / "fixtures"
DAY = FIX / "pvdaq_50_2023-01-10_excerpt.csv"
META = FIX / "pvdaq_50_system_metadata.json"
S3_NS = "http://s3.amazonaws.com/doc/2006-03-01/"


def test_zone_reads_names_and_fixed_offsets() -> None:
    assert pvdaq.zone("America/New_York") == "America/New_York"
    assert pvdaq.zone("7") == "Etc/GMT+7"  # Golden, CO: UTC-7 all year
    assert pvdaq.zone(5) == "Etc/GMT+5"
    assert pvdaq.zone("0") == "Etc/GMT"
    with pytest.raises(ValueError):
        pvdaq.zone("7.5")


def test_label_of_time_interval() -> None:
    assert pvdaq.label_of("L") == "start" and pvdaq.label_of("r") == "end"
    assert pvdaq.label_of("C") is None and pvdaq.label_of("") is None and pvdaq.label_of(None) is None


def test_real_day_file_becomes_hourly_kwh() -> None:
    s = pvdaq.read_days([DAY], tz="Etc/GMT+7", name="pvdaq_50")
    assert s.freq == "h" and s.unit == "kWh" and s.series == ["pvdaq_50"]
    f = s.frame.set_index("ds")
    raw = pd.read_csv(DAY, parse_dates=["measured_on"]).set_index("measured_on")["ac_power__752"]
    for hour in (11, 12):  # 60 one-minute averages of W -> kWh
        t = pd.Timestamp(f"2023-01-10 {hour}:00", tz="Etc/GMT+7")
        expected = raw[raw.index.hour == hour].sum() / 60 / 1000
        assert f.loc[t, "y"] == pytest.approx(expected) and f.loc[t, "valid"]
    night = f.loc[pd.Timestamp("2023-01-10 00:00", tz="Etc/GMT+7")]
    assert not night["valid"]  # 10 of 60 minutes in the excerpt: not an hour
    assert s.provenance is not None and s.provenance.license == "CC-BY-4.0"
    assert "doi:10.25984/1846021" in s.provenance.citation
    assert "ac_power__752" in s.provenance.notes


def test_column_must_be_named_once() -> None:
    with pytest.raises(ValueError, match=r"No PVDAQ column.*'ac_energy'"):
        pvdaq.read_days([DAY], tz="Etc/GMT+7", column="ac_energy")
    with pytest.raises(ValueError, match="no `measured_on`"):
        pvdaq.read_days(
            [pd.DataFrame({"Unnamed: 0": ["2024-01-01"], "ac_energy_inv_1_daily_sum": [1.5]})], tz="UTC"
        )


def test_site_of_the_metadata() -> None:
    site = pvdaq.site_of(json.loads(META.read_text(encoding="utf-8")))
    assert site["latitude"] == pytest.approx(39.742) and site["longitude"] == pytest.approx(-105.1727)
    assert (site["tilt"], site["azimuth"], site["kw"], site["tracking"]) == (45.0, 158.0, 6.0, False)


class FakeBucket:
    """Serves the listing XML, the metadata and the systems list, and the day file, counting requests."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        if url.endswith("_system_metadata.json"):
            return META.read_bytes()
        if url.endswith("/pvdaq/csv/systems_20250729.csv"):
            return b"system_id,timezone_or_utc_offset\n50,7\n"
        if (
            "list-type=2" in url and "systems_" in url
        ):  # the newest dated list wins (the undated is from 2022)
            names = ("systems_20241231.csv", "systems_20250729.csv", "systems_20250624.csv", "systems.csv")
            keys = "".join(f"<Contents><Key>pvdaq/csv/{n}</Key></Contents>" for n in names)
            return f'<ListBucketResult xmlns="{S3_NS}">{keys}</ListBucketResult>'.encode()
        if "list-type=2" in url:
            key = "pvdaq/csv/pvdata/system_id=50/year=2023/month=1/day=10/system_50__date_2023_01_10.csv"
            other = "pvdaq/csv/pvdata/system_id=50/year=2023/month=1/day=11/system_50__date_2023_01_11.csv"
            body = (
                '<?xml version="1.0" encoding="UTF-8"?><ListBucketResult '
                'xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
                f"<IsTruncated>false</IsTruncated><Contents><Key>{key}</Key></Contents>"
                f"<Contents><Key>{other}</Key></Contents></ListBucketResult>"
            )
            return body.encode()
        if url.endswith("system_50__date_2023_01_10.csv"):
            return DAY.read_bytes()
        raise AssertionError(f"unexpected request {url}")


def test_fetch_downloads_only_the_days_asked_once(tmp_path: Path) -> None:
    bucket = FakeBucket()
    s = pvdaq.fetch(50, "2023-01-10", "2023-01-10", cache_dir=tmp_path, get=bucket)
    assert s.tz == "Etc/GMT+7" and s.series == ["pvdaq_50"]  # zone from the systems list (none in metadata)
    assert s.provenance is not None and "Golden, CO" in s.provenance.source
    assert "stamps taken as the START" in s.provenance.notes  # system 50's inverter has no time_interval
    assert not any(c.endswith("2023_01_11.csv") for c in bucket.calls)  # outside the dates: not downloaded
    again = FakeBucket()
    pvdaq.fetch(50, "2023-01-10", "2023-01-10", cache_dir=tmp_path, get=again)
    assert not any(c.endswith(".csv") and "date_" in c for c in again.calls)  # from the cache
    with pytest.raises(ValueError, match="no day files"):
        pvdaq.fetch(50, "2023-02-01", "2023-02-02", cache_dir=tmp_path, get=FakeBucket())
