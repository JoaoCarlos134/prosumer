"""Dingle houses loader, without the network: a fake figshare serves 1-minute CSVs in the dataset's format,
and the benchmark's hourly parquet is the reference."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prosumer import data
from prosumer.data import dingle_houses, download_dingle_houses

SAVED = (
    Path(__file__).resolve().parents[1]
    / "experimentos"
    / "testes_previsao"
    / "dados"
    / "casas_horario.parquet"
)
HEADER = (
    "date, Discharge(Wh), Charge(Wh), Production(Wh), Consumption(Wh), Feed-in(Wh), From grid(Wh), "
    "State of Charge(%)"
)


def _csv(days: int = 2, *, drop: slice | None = None, production: float = 0.5) -> bytes:
    """Minute rows stamped by the END of the minute, like the dataset (first row 01:01 on 1 January;
    one minute past the last full hour)."""
    t = pd.date_range("2020-01-01 01:01", periods=days * 1440 + 1, freq="min")
    cons = np.full(len(t), 2.0)
    prod = np.full(len(t), production)
    keep = np.ones(len(t), bool)
    if drop is not None:
        keep[drop] = False
    rows = [
        f"{x:%Y-%m-%d %H:%M:%S},0.0,0.1,{p},{c},0.0,1.0,0.0"
        for x, p, c, k in zip(t, prod, cons, keep, strict=True)
        if k
    ]
    return ("\n".join([HEADER, *rows]) + "\n").encode()


class FakeFigshare:
    def __init__(self, bodies: dict[str, bytes]) -> None:
        self.bodies, self.calls = bodies, []  # file id (as in the URL) -> body

    def __call__(self, url: str) -> bytes:
        self.calls.append(url)
        return self.bodies[url.rsplit("/", 1)[1]]


@pytest.fixture
def fake_files(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    """H1 consumes and generates; H2 has no PV and a 10-minute hole in its first hour."""
    bodies = {"H1": _csv(), "H2": _csv(drop=slice(0, 10), production=0.0)}
    files = {h: (1000 + i, hashlib.md5(b).hexdigest()) for i, (h, b) in enumerate(bodies.items())}
    monkeypatch.setattr(data, "DINGLE_FILES", files)
    return {str(files[h][0]): b for h, b in bodies.items()}


def test_downloads_once_into_the_cache_and_aggregates_by_hour(
    tmp_path: Path, fake_files: dict[str, bytes]
) -> None:
    api = FakeFigshare(fake_files)
    s = dingle_houses(cache_dir=tmp_path, get=api)
    assert len(api.calls) == 2 and api.calls[0] == "https://ndownloader.figshare.com/files/1000"
    assert (tmp_path / "dingle" / "H1_Wh.csv").exists()
    assert s.quantity == "consumption" and s.unit == "kWh" and s.freq == "h" and s.tz == "Etc/GMT"
    h1 = s.frame[s.frame["unique_id"] == "H1"].set_index("ds")
    # 01:01..02:00 -> the hour starting 01:00; 60 minutes x 2 Wh = 0.12 kWh
    assert h1.index[0] == pd.Timestamp("2020-01-01 01:00", tz="Etc/GMT")
    assert h1["y"].iloc[0] == pytest.approx(0.12)
    assert h1.index.to_series().diff().dropna().eq(pd.Timedelta(hours=1)).all()
    # the last hour (01:00 of day 3) has a single minute: invalid, not a small value
    assert not h1["valid"].iloc[-1] and np.isnan(h1["y"].iloc[-1])
    # second call: the MD5 of the cached files matches, nothing is downloaded
    dingle_houses(houses=[1], cache_dir=tmp_path, get=api)
    assert len(api.calls) == 2


def test_hour_with_too_few_minutes_is_invalid(tmp_path: Path, fake_files: dict[str, bytes]) -> None:
    s = dingle_houses(houses=["h2"], cache_dir=tmp_path, get=FakeFigshare(fake_files))
    f = s.frame.set_index("ds")
    assert not f.loc[pd.Timestamp("2020-01-01 01:00", tz="Etc/GMT"), "valid"]  # 50 of 60 minutes
    assert f["valid"].iloc[1]
    looser = dingle_houses(houses=["H2"], cache_dir=tmp_path, get=FakeFigshare(fake_files), min_minutes=50)
    assert looser.frame["y"].iloc[0] == pytest.approx(0.1)


def test_generation_keeps_only_houses_with_pv(tmp_path: Path, fake_files: dict[str, bytes]) -> None:
    api = FakeFigshare(fake_files)
    assert dingle_houses("generation", cache_dir=tmp_path, get=api).series == ["H1"]
    assert dingle_houses("generation", cache_dir=tmp_path, get=api, pv_only=False).series == ["H1", "H2"]
    with pytest.raises(ValueError, match="has PV"):
        dingle_houses("generation", houses=[2], cache_dir=tmp_path, get=api)


def test_bad_download_is_refused_and_not_cached(tmp_path: Path, fake_files: dict[str, bytes]) -> None:
    broken = {k: v[:-10] for k, v in fake_files.items()}
    with pytest.raises(RuntimeError, match="MD5"):
        download_dingle_houses([1], cache_dir=tmp_path, get=FakeFigshare(broken))
    assert not (tmp_path / "dingle" / "H1_Wh.csv").exists()


def test_cache_dir_from_the_environment(
    tmp_path: Path, fake_files: dict[str, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROSUMER_DATA", os.fspath(tmp_path))
    assert download_dingle_houses([1], get=FakeFigshare(fake_files)) == tmp_path / "dingle"


def test_arguments_are_checked(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="H1-H20"):
        dingle_houses(houses=[21], path=tmp_path)
    with pytest.raises(ValueError, match="quantity"):
        dingle_houses("irradiance", path=tmp_path)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="tz"):
        dingle_houses(path=tmp_path, tz="UTC")  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError):
        dingle_houses(houses=[1], path=tmp_path)


def test_the_files_table_covers_the_20_houses() -> None:
    assert list(data.DINGLE_FILES) == [f"H{i}" for i in range(1, 21)]
    assert len({f for f, _ in data.DINGLE_FILES.values()}) == 20
    assert "10.1038/s41597-024-03454-2" in data.DINGLE_CITATION


@pytest.mark.skipif(not SAVED.exists(), reason="benchmark data missing")
def test_reads_the_benchmark_parquet_as_the_benchmark_does() -> None:
    """`comum.carrega`: consumption of the 20 houses; generation of the 10 with PV; clock on Etc/GMT."""
    raw = pd.read_parquet(SAVED)
    cons = dingle_houses(path=SAVED)
    assert len(cons.series) == 20 and len(cons) == len(raw)
    ref = raw.set_index(["casa", "ds"])["cons_kWh"]
    got = cons.frame.assign(ds=cons.frame["ds"].dt.tz_localize(None)).set_index(["unique_id", "ds"])["y"]
    np.testing.assert_array_equal(got.to_numpy(), ref.reindex(got.index).to_numpy())
    prod = dingle_houses("generation", path=SAVED)
    with_pv = raw.groupby("casa")["prod_kWh"].sum()
    assert prod.series == sorted(with_pv[with_pv > 0].index)
    assert len(prod.series) == 10
    # true instants: the two impossible rows of each house are dropped
    with pytest.warns(UserWarning, match="impossible local time"):
        dublin = dingle_houses(houses=[1], path=SAVED, tz="Europe/Dublin")
    assert len(dublin) == (raw["casa"] == "H1").sum() - 2


@pytest.mark.skipif(
    not (SAVED.exists() and (data._cache_root(None) / "dingle" / "H1_Wh.csv").exists()),
    reason="H1_Wh.csv not in the cache (download it with prosumer.data.download_dingle_houses([1]))",
)
def test_the_original_csv_gives_the_benchmark_hours_exactly() -> None:
    """Checked on 2026-10-11 with H1 downloaded from figshare: difference 0.0 in both quantities."""
    folder = data._cache_root(None) / "dingle"
    for q in ("consumption", "generation"):
        a = dingle_houses(q, houses=[1], path=folder).frame  # type: ignore[arg-type]
        b = dingle_houses(q, houses=[1], path=SAVED).frame  # type: ignore[arg-type]
        assert (a["ds"].to_numpy() == b["ds"].to_numpy()).all()
        np.testing.assert_array_equal(a["y"].to_numpy(), b["y"].to_numpy())
