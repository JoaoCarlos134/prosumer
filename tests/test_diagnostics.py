"""Diagnostics on synthetic plants built from the library's own physics, with known roof and known events."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from prosumer import EnergySeries, analyze, data, diagnostics, physics
from prosumer.data import example_house

SITE = (-24.83, -53.65)
TZ = "America/Sao_Paulo"


def _plant(
    level: pd.Series | float = 0.8,
    *,
    site: tuple[float, float] = SITE,
    tz: str = TZ,
    tilt: float = 15.0,
    azimuth: float = 20.0,
    days: int = 730,
    kwp: float = 4.0,
    seed: int = 0,
    second_plane: tuple[float, float] | None = None,
    uid: str = "p1",
) -> pd.DataFrame:
    """Hourly energy = kWp x POA x level x the day's clouds; a third of the days are clear."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-01", periods=days * 24, freq="h", tz=tz)
    cs = physics.clear_sky_ghi(idx, *site)
    sun = physics.mean_sun(idx, *site)
    dates = idx.tz_localize(None).normalize()
    uniq = dates.unique()
    clouds = pd.Series(
        np.where(rng.random(len(uniq)) < 1 / 3, 1.0, rng.uniform(0.2, 0.75, len(uniq))), index=uniq
    )
    kc = clouds.reindex(dates).to_numpy()
    poa = physics.poa_isotropic(cs * kc, sun, tilt, azimuth)
    if second_plane is not None:
        poa = 0.5 * poa + 0.5 * physics.poa_isotropic(cs * kc, sun, *second_plane)
    lv = level.reindex(dates).to_numpy() if isinstance(level, pd.Series) else np.full(len(idx), level)
    y = kwp * poa / 1000 * lv * (1 + rng.normal(0, 0.01, len(idx)))
    return pd.DataFrame({"unique_id": uid, "ds": idx, "y": np.clip(y, 0, None)})


def _series(*frames: pd.DataFrame, tz: str = TZ) -> EnergySeries:
    return EnergySeries.from_dataframe(
        pd.concat(frames, ignore_index=True), unit="kWh", quantity="generation", tz=tz, freq="h"
    )


def _sawtooth(cleaning: str, days: int = 730) -> pd.Series:
    """Soiling: 0.85 falling 8% a year, back to 0.85 at the cleaning."""
    dates = pd.date_range("2022-01-01", periods=days, freq="D")
    t0 = pd.Series(dates[0], index=dates).where(dates < pd.Timestamp(cleaning), pd.Timestamp(cleaning))
    years = (dates - pd.DatetimeIndex(t0)).days / 365.25
    return pd.Series(0.85 * (1 - 0.08 * years), index=dates)


def test_finds_the_roof_and_the_level() -> None:
    d = diagnostics.diagnose(_series(_plant(0.8)), SITE, kwp=4.0)
    o = d.orientation.iloc[0]
    assert abs(o["tilt"] - 15) <= 5 and abs(o["azimuth"] - 20) <= 20, o
    assert o["r2"] > 0.95
    assert d.index["index"].median() == pytest.approx(0.8, abs=0.03)
    assert d.steps.empty
    assert not [n for n in d.notes if "stepped" in n or "below the best" in n]


def test_a_cleaning_is_a_step_up_on_its_date() -> None:
    d = diagnostics.diagnose(_series(_plant(_sawtooth("2023-03-01"))), SITE, kwp=4.0)
    assert len(d.steps) == 1, d.steps
    step = d.steps.iloc[0]
    assert abs((step["date"] - pd.Timestamp("2023-03-01")).days) <= 15
    assert step["step_pct"] > 5
    assert len(d.segments) == 2
    assert d.segments["trend_pct_per_year"].iloc[0] < -5
    assert any("stepped +" in n and "cleaning" in n for n in d.notes)


def test_a_fault_is_a_step_down() -> None:
    dates = pd.date_range("2022-01-01", periods=730, freq="D")
    level = pd.Series(np.where(dates < pd.Timestamp("2022-11-15"), 0.8, 0.55), index=dates)
    d = diagnostics.diagnose(_series(_plant(level)), SITE, kwp=4.0)
    # the refits with the level divided out: one pooled fit gives 20 degrees, 5 steps and R2 0.84
    o = d.orientation.iloc[0]
    assert o["tilt"] == 15 and abs(o["azimuth"] - 20) <= 10 and o["r2"] > 0.99
    assert len(d.steps) == 1
    assert abs((d.steps["date"].iloc[0] - pd.Timestamp("2022-11-15")).days) <= 15
    assert d.steps["step_pct"].iloc[0] == pytest.approx(100 * (0.55 / 0.8 - 1), abs=4)
    assert any("fault" in n for n in d.notes)


def test_an_east_west_roof_acts_as_one_flatter_plane() -> None:
    dates = pd.date_range("2022-01-01", periods=730, freq="D")
    level = pd.Series(np.where(dates < pd.Timestamp("2023-02-01"), 0.8, 0.6), index=dates)
    d = diagnostics.diagnose(_series(_plant(level, tilt=30, azimuth=90, second_plane=(30, 270))), SITE)
    assert d.orientation["r2"].iloc[0] > 0.99  # the sum of the two is near a flatter single plane
    events = d.steps[d.steps["event"]]
    assert len(events) == 1
    assert abs((events["date"].iloc[0] - pd.Timestamp("2023-02-01")).days) <= 15
    assert events["step_pct"].iloc[0] == pytest.approx(-25, abs=4)


def test_a_poor_roof_fit_makes_steps_uncertain_and_hides_losses() -> None:
    orientation = pd.DataFrame([dict(unique_id="p1", tilt=20.0, azimuth=320.0, r2=0.79, edge=False)])
    index = pd.DataFrame({"unique_id": "p1", "date": pd.date_range("2022-01-01", periods=400), "index": 0.7})
    segments = pd.DataFrame(
        [
            dict(
                unique_id="p1",
                start=pd.Timestamp("2022-01-01"),
                end=pd.Timestamp("2022-06-30"),
                days=180,
                level_start=0.8,
                level_end=0.8,
                trend_pct_per_year=0.0,
                lost_pct=0.0,
            ),
            dict(
                unique_id="p1",
                start=pd.Timestamp("2022-07-01"),
                end=pd.Timestamp("2023-12-31"),
                days=220,
                level_start=0.6,
                level_end=0.5,
                trend_pct_per_year=-12.0,
                lost_pct=30.0,
            ),
        ]
    )
    steps = pd.DataFrame(
        [dict(unique_id="p1", date=pd.Timestamp("2022-07-01"), before=0.8, after=0.6, step_pct=-25.0)]
    )
    notes = diagnostics._notes(orientation, index, segments, steps, {}, given=False)
    text = " ".join(notes)
    assert "does not describe this roof well" in text
    assert [n for n in notes if "stepped" in n] and all("Uncertain" in n for n in notes if "stepped" in n)
    assert "below the best" not in text and "a year" not in text
    good = orientation.assign(r2=0.95)
    text = " ".join(diagnostics._notes(good, index, segments, steps, {}, given=False))
    assert "below the best" in text and "falls 12% a year" in text and "Uncertain" not in text


def test_known_orientation_and_per_series_kwp() -> None:
    s = _series(_plant(0.8, uid="a"), _plant(0.7, uid="b", kwp=2.0, seed=1))
    d = diagnostics.diagnose(s, SITE, kwp={"a": 4.0, "b": 2.0}, orientation=(15, 20))
    med = d.index.groupby("unique_id")["index"].median()
    assert med["a"] == pytest.approx(0.8, abs=0.03) and med["b"] == pytest.approx(0.7, abs=0.03)
    assert not any("panels fitted" in n for n in d.notes)
    # without kWp the index is the effective peak power
    e = diagnostics.performance_index(s, SITE, orientation=(15, 20))
    assert e.groupby("unique_id")["index"].median()["a"] == pytest.approx(3.2, rel=0.04)


def test_clear_days_are_the_cloudless_ones() -> None:
    c = diagnostics.clear_days(_series(_plant(0.8, days=365)), SITE)
    assert 0.2 < c["clear"].mean() < 0.45


def test_too_little_data_says_so() -> None:
    d = diagnostics.diagnose(_series(_plant(0.8, days=4)), SITE)
    assert d.segments.empty and d.steps.empty
    assert any("too few clear days" in n for n in d.notes)


def test_rejects_consumption_and_subhourly() -> None:
    with pytest.raises(ValueError, match="generation"):
        diagnostics.diagnose(example_house(days=30), SITE)
    f = _plant(0.8, days=3)
    q = EnergySeries.from_dataframe(
        pd.concat([f, f.assign(ds=f["ds"] + pd.Timedelta("30min"))]).sort_values("ds"),
        unit="kWh",
        quantity="generation",
        tz=TZ,
        freq="30min",
    )
    with pytest.raises(ValueError, match="hourly"):
        diagnostics.diagnose(q, SITE)


def test_analyze_has_the_diagnostics_section() -> None:
    s = _series(_plant(_sawtooth("2023-03-01"), days=500))
    r = analyze(s, site=SITE, test_days=14, kwp=4.0)
    assert r.diagnostics is not None and len(r.diagnostics.steps) == 1
    assert "## Diagnostics" in r.to_markdown()
    d = r.to_dict()["diagnostics"]
    assert d["steps"][0]["date"].startswith("2023-0")
    assert "DC or 5-minute" in r.pending["diagnostics"]
    assert any("stepped" in n for n in r.notes)


def test_northern_hemisphere_with_daylight_saving() -> None:
    site, tz = (52.14, -10.27), "Europe/Dublin"
    dates = pd.date_range("2022-01-01", periods=730, freq="D")
    level = pd.Series(np.where(dates < pd.Timestamp("2022-11-15"), 0.8, 0.55), index=dates)
    f = _plant(level, site=site, tz=tz, tilt=35, azimuth=180)
    d = diagnostics.diagnose(_series(f, tz=tz), site, kwp=4.0)
    o = d.orientation.iloc[0]
    assert o["tilt"] == 35 and o["azimuth"] == 180, o
    events = d.steps[d.steps["event"]]
    assert len(events) == 1 and abs((events["date"].iloc[0] - pd.Timestamp("2022-11-15")).days) <= 15


def test_gaps_do_not_make_steps() -> None:
    f = _plant(0.8)
    rng = np.random.default_rng(3)
    f.loc[rng.random(len(f)) < 0.05, "y"] = np.nan
    f.loc[(f["ds"] >= "2022-05-01") & (f["ds"] < "2022-07-20"), "y"] = np.nan
    d = diagnostics.diagnose(_series(f.dropna()), SITE, kwp=4.0)
    assert not d.steps["event"].any()


def test_an_all_zero_series_is_reported_not_crashing() -> None:
    zero = _plant(0.8, uid="dead").assign(y=0.0)
    d = diagnostics.diagnose(_series(_plant(0.8), zero), SITE)
    row = d.orientation.set_index("unique_id").loc["dead"]
    assert np.isnan(row["tilt"])
    assert any("dead" in n and "too few clear days" in n for n in d.notes)
    assert d.orientation.set_index("unique_id").loc["p1", "tilt"] == 15
    r = analyze(_series(_plant(0.8, days=120), zero.iloc[: 24 * 120]), site=SITE, test_days=14)
    assert r.diagnostics is not None


def test_an_inverter_that_dies_keeps_its_roof() -> None:
    dates = pd.date_range("2022-01-01", periods=730, freq="D")
    level = pd.Series(np.where(dates < pd.Timestamp("2022-11-15"), 0.8, 0.0), index=dates)
    d = diagnostics.diagnose(_series(_plant(level)), SITE)
    o = d.orientation.iloc[0]
    assert np.isfinite(o["r2"]) and o["r2"] > 0.9 and abs(o["tilt"] - 15) <= 5, o


def test_kwp_must_cover_every_series() -> None:
    s = _series(_plant(0.8, uid="a"), _plant(0.8, uid="b", seed=1))
    with pytest.raises(ValueError, match="no value for series"):
        diagnostics.diagnose(s, SITE, kwp={"a": 4.0})


def test_analyze_of_an_all_zero_series_says_so() -> None:
    r = analyze(_series(_plant(0.8, days=60).assign(y=0.0)), site=SITE, test_days=14)
    assert r.forecast is None
    assert any("every value is zero" in n for n in r.notes)
    # the reason as a field too (site review 23/10: the page matched the note's first words, in each language)
    assert r.skipped["forecast"] in r.notes and "every value is zero" in r.skipped["forecast"]
    pt = r.to_dict(lang="pt")["skipped"]
    assert set(pt) == {"forecast"} and pt["forecast"].startswith("Conferência da previsão não feita")


# ---------------------------------------------------------------------- tuning arguments
# Fingerprint of `diagnose` with the defaults, saved at 9d3ade0 (before the thresholds became arguments) on
# the synthetic plants above and the ten Dingle PV houses. Rewrite it only for a deliberate change of results.
DEFAULTS = Path(__file__).resolve().parent / "fixtures" / "diagnostics_defaults.json"
DINGLE = (
    Path(__file__).resolve().parents[1]
    / "experimentos"
    / "testes_previsao"
    / "dados"
    / "casas_horario.parquet"
)


def _step(day: str, before: float, after: float) -> pd.Series:
    dates = pd.date_range("2022-01-01", periods=730, freq="D")
    return pd.Series(np.where(dates < pd.Timestamp(day), before, after), index=dates)


def test_the_tables_say_what_the_notes_report() -> None:
    # found 2026-10-23 by the review of the site: the PV page showed a trend of -86%/year and a 31% loss that
    # the notes withheld (a roof on the edge of the search), because the tables carried the numbers but not
    # whether they are reported; the page had to re-derive the rule (and got it wrong)
    orientation = pd.DataFrame([dict(unique_id="p1", tilt=20.0, azimuth=320.0, r2=0.79, edge=False)])
    first = dict(unique_id="p1", start=pd.Timestamp("2022-01-01"), end=pd.Timestamp("2022-06-30"), days=180)
    first |= dict(level_start=0.8, level_end=0.8, trend_pct_per_year=-20.0, lost_pct=0.0)
    last = dict(unique_id="p1", start=pd.Timestamp("2022-07-01"), end=pd.Timestamp("2023-12-31"), days=220)
    last |= dict(level_start=0.6, level_end=0.5, trend_pct_per_year=-12.0, lost_pct=30.0)
    segments = pd.DataFrame([first, last])
    k = diagnostics._DEFAULT

    o, sg = diagnostics._flag(orientation, segments, False, k)  # a poor fit: nothing reported
    assert not o["reliable"].any() and not sg["trend_reported"].any() and not sg["loss_reported"].any()
    for given, r2, edge in ((True, 0.79, False), (False, 0.95, False)):
        o, sg = diagnostics._flag(orientation.assign(r2=r2, edge=edge), segments, given, k)
        assert o["reliable"].all()
        assert sg["trend_reported"].tolist() == [False, True] and sg["loss_reported"].tolist() == [
            False,
            True,
        ]
    o, sg = diagnostics._flag(orientation.assign(r2=0.95, edge=True), segments, False, k)  # on the edge
    assert not o["reliable"].any() and not sg["trend_reported"].any()
    # a last period under a year, or a rise, is no trend; a loss under step_note_pct is no loss
    short = segments.assign(end=[pd.Timestamp("2022-06-30"), pd.Timestamp("2023-03-01")])
    rise = segments.assign(trend_pct_per_year=[0.0, 12.0], lost_pct=[0.0, k.step_note_pct / 2])
    for case in (short, rise):
        sg = diagnostics._flag(orientation.assign(r2=0.95), case, False, k)[1]
        assert not sg["trend_reported"].any()
    assert not diagnostics._flag(orientation.assign(r2=0.95), rise, False, k)[1]["loss_reported"].any()
    # the flags and the notes agree
    good = orientation.assign(r2=0.95)
    index = pd.DataFrame({"unique_id": "p1", "date": pd.date_range("2022-01-01", periods=400), "index": 0.7})
    no_steps = pd.DataFrame(columns=["unique_id", "date", "before", "after", "step_pct"])
    text = " ".join(diagnostics._notes(good, index, short, no_steps, {}, given=False))
    assert "a year" not in text and "below the best" in text


def _fingerprint(d: diagnostics.Diagnosis) -> dict[str, Any]:
    out = d.to_dict()
    # the flags of what the notes report came after the saved output (2026-10-23); the notes they mirror are
    # compared, and `test_the_tables_say_what_the_notes_report` checks the flags
    for r in out["orientation"]:
        r.pop("reliable", None)
    for r in out["segments"]:
        r.pop("trend_reported", None)
        r.pop("loss_reported", None)
    ix = d.index
    out["index_summary"] = {
        "rows": len(ix),
        "energy": float(ix["energy"].sum()),
        "expected": float(ix["expected"].sum()),
        "index": float(ix["index"].sum()),
        "first": str(pd.Timestamp(ix["date"].min()).date()) if len(ix) else None,
        "last": str(pd.Timestamp(ix["date"].max()).date()) if len(ix) else None,
    }
    return json.loads(json.dumps(out, default=float))


def _same(got: Any, want: Any, where: str = "") -> None:
    """Equal, floats to 1e-9 relative (the last bits differ between machines; dates, tilts and notes not)."""
    if isinstance(want, dict):
        assert set(got) == set(want), where
        for key in want:
            _same(got[key], want[key], f"{where}.{key}")
    elif isinstance(want, list):
        assert len(got) == len(want), where
        for i, (g, w) in enumerate(zip(got, want, strict=True)):
            _same(g, w, f"{where}[{i}]")
    elif isinstance(want, float) and not isinstance(got, bool):
        assert got == pytest.approx(want, rel=1e-9, abs=1e-12, nan_ok=True), where
    else:
        assert got == want, where


def test_the_defaults_reproduce_the_output_before_the_arguments() -> None:
    want = json.loads(DEFAULTS.read_text(encoding="utf-8"))
    fault, ew = _step("2022-11-15", 0.8, 0.55), _step("2023-02-01", 0.8, 0.6)
    got = {
        "sawtooth": diagnostics.diagnose(_series(_plant(_sawtooth("2023-03-01"))), SITE, kwp=4.0),
        "fault": diagnostics.diagnose(_series(_plant(fault)), SITE, kwp=4.0),
        "east_west": diagnostics.diagnose(
            _series(_plant(ew, tilt=30, azimuth=90, second_plane=(30, 270))), SITE
        ),
    }
    for name, d in got.items():
        _same(_fingerprint(d), want[name], name)
    c = diagnostics.clear_days(_series(_plant(0.8, days=365)), SITE)
    clear = {"rows": len(c), "clear": int(c["clear"].sum()), "ratio": float(c["ratio"].sum())}
    _same(clear, want["clear_days"], "clear_days")
    roof = diagnostics.roof_orientation(_series(_plant(fault)), SITE).to_dict(orient="records")
    _same(json.loads(json.dumps(roof, default=float)), want["roof_orientation"], "roof_orientation")


@pytest.mark.skipif(not DINGLE.exists(), reason="benchmark data missing")
@pytest.mark.filterwarnings("ignore:.*impossible local time")
def test_the_defaults_reproduce_the_dingle_houses_before_the_arguments() -> None:
    s = data.dingle_houses("generation", path=DINGLE, tz="Europe/Dublin")
    want = json.loads(DEFAULTS.read_text(encoding="utf-8"))["dingle"]
    _same(_fingerprint(diagnostics.diagnose(s, (52.14, -10.27))), want, "dingle")


def test_a_lower_penalty_finds_at_least_as_many_breaks() -> None:
    ew = _step("2023-02-01", 0.8, 0.6)
    d = diagnostics.diagnose(_series(_plant(ew, tilt=30, azimuth=90, second_plane=(30, 270))), SITE)
    counts = [len(diagnostics.changepoints(d.index, penalty=p)[1]) for p in (6.0, 3.0, 2.0, 1.0, 0.5)]
    assert counts == sorted(counts) and counts[-1] > counts[0], counts
    assert counts[1] == len(d.steps)  # the default is 3
    # through the whole chain too (the penalty also steers the roof passes)
    low = diagnostics.diagnose(
        _series(_plant(ew, tilt=30, azimuth=90, second_plane=(30, 270))), SITE, penalty=1.0
    )
    assert len(low.steps) >= len(d.steps)


def test_vertical_panels_are_fitted_only_on_a_grid_that_reaches_90() -> None:
    s = _series(_plant(0.8, tilt=90, azimuth=0))  # a facade facing the equator (north, in the south)
    narrow = diagnostics.diagnose(s, SITE, kwp=4.0)
    o = narrow.orientation.iloc[0]
    assert o["tilt"] == 60 and bool(o["edge"])
    assert any("edge of the grid" in n for n in narrow.notes)
    wide = diagnostics.diagnose(s, SITE, kwp=4.0, tilts=np.arange(0, 91, 5.0))
    o = wide.orientation.iloc[0]
    assert o["tilt"] == 90 and o["azimuth"] == 0 and o["r2"] > 0.99
    assert not o["edge"]  # 90 is a physical limit, like 0: a possible answer
    assert not any("edge of the grid" in n for n in wide.notes)
    assert wide.index["index"].median() == pytest.approx(0.8, abs=0.03)
    # a grid that stops short of the panel still flags its steepest tilt
    short = diagnostics.roof_orientation(s, SITE, tilts=np.arange(0, 76, 5.0))
    assert short["tilt"].iloc[0] == 75 and bool(short["edge"].iloc[0])


def test_options_are_checked_and_analyze_passes_them_through() -> None:
    s = _series(_plant(_sawtooth("2023-03-01"), days=500))
    with pytest.raises(ValueError, match="Unknown diagnostics options"):
        analyze(s, site=SITE, test_days=14, diagnostics_options={"penalt": 2.0})
    with pytest.raises(ValueError, match="tilts must be within 0-90"):
        diagnostics.diagnose(s, SITE, tilts=[0, 45, 120])
    with pytest.raises(ValueError, match="penalty > 0"):
        diagnostics.changepoints(pd.DataFrame(columns=["unique_id", "date", "index"]), penalty=0)
    with pytest.raises(ValueError, match="Unknown diagnostics options"):
        diagnostics.performance_index(s, SITE, tilt=30)
    default = analyze(s, site=SITE, test_days=14, kwp=4.0)
    said = [n for n in default.notes if n.startswith("Diagnostics:")]
    assert len(said) == 1 and "penalty (3 x the BIC's) was chosen on two plants in Parana" in said[0]
    assert "clear-day rule was set by hand on the same plants" in said[0]
    r = analyze(s, site=SITE, test_days=14, kwp=4.0, diagnostics_options={"penalty": 1.0})
    direct = diagnostics.diagnose(s, SITE, kwp=4.0, penalty=1.0)
    assert r.diagnostics is not None
    pd.testing.assert_frame_equal(r.diagnostics.steps, direct.steps)
    said = [n for n in r.notes if n.startswith("Diagnostics:")]
    assert len(said) == 1 and "penalty" not in said[0] and "clear-day rule" in said[0]
    other = {"penalty": 1.0, "clear_ratio": 0.85}
    r = analyze(s, site=SITE, test_days=14, kwp=4.0, diagnostics_options=other)
    assert not [n for n in r.notes if n.startswith("Diagnostics:")]


def test_the_roof_is_fitted_once_for_the_outlook_and_the_diagnosis(monkeypatch: pytest.MonkeyPatch) -> None:
    """The remembered roof fit (`diagnostics._roof`, 2026-10-21): one fit serves `forecast_ahead` and
    `diagnose` on the same series; a changed value is a new fit; what a caller gets is a copy."""
    from collections import OrderedDict

    from prosumer import forecast_ahead

    fits: list[int] = []
    real = diagnostics._fit_roof

    def counted(*a: Any, **k: Any) -> pd.DataFrame:
        fits.append(1)
        return real(*a, **k)

    monkeypatch.setattr(diagnostics, "_fit_roof", counted)
    monkeypatch.setattr(diagnostics, "_ROOFS", OrderedDict())
    f = _plant(days=400)
    s = _series(f)
    forecast_ahead(s, site=SITE, days=2)
    d = diagnostics.diagnose(s, SITE, kwp=4.0)
    assert len(fits) == 1
    assert diagnostics.diagnose(s, SITE, kwp=4.0).orientation.equals(d.orientation)
    assert len(fits) == 1

    changed = f.copy()
    changed.loc[changed["y"].idxmax(), "y"] *= 0.9  # one hour differs: not the same inputs
    diagnostics.diagnose(_series(changed), SITE, kwp=4.0)
    assert len(fits) == 2

    first = diagnostics.roof_orientation(s, SITE)
    first.loc[:, "tilt"] = -99.0  # the caller changes its table...
    assert (diagnostics.roof_orientation(s, SITE)["tilt"] != -99.0).all()  # ...not the remembered one
    assert len(fits) == 2

    for i in range(diagnostics.ROOF_MEMORY):  # the oldest fit is forgotten past ROOF_MEMORY
        other = f.assign(y=f["y"] * (1 - 0.01 * (i + 1)))
        diagnostics.diagnose(_series(other), SITE, kwp=4.0)
    assert len(diagnostics._ROOFS) == diagnostics.ROOF_MEMORY
    n = len(fits)
    diagnostics.diagnose(s, SITE, kwp=4.0)
    assert len(fits) == n + 1


def _segment_reference(
    t: np.ndarray, y: np.ndarray, min_size: int, max_breaks: int, penalty: float
) -> list[int]:
    """`diagnostics._segment` as it was before it was vectorised (2026-10-21): one k, one end at a time."""
    n = len(y)
    cost = diagnostics._line_costs(t, y)
    best: tuple[float, list[int]] | None = None
    for k in range(1, max_breaks + 2):
        if k * min_size > n:
            break
        f = np.full((k + 1, n + 1), np.inf)
        back = np.zeros((k + 1, n + 1), dtype=int)
        f[0, 0] = 0.0
        for j in range(1, k + 1):
            for e in range(j * min_size, n + 1):
                starts = np.arange((j - 1) * min_size, e - min_size + 1)
                v = f[j - 1, starts] + cost[starts, e]
                i = int(np.argmin(v))
                f[j, e], back[j, e] = v[i], starts[i]
        breaks, e = [], n
        for j in range(k, 0, -1):
            e = int(back[j, e])
            breaks.append(e)
        sse = max(float(f[k, n]), 1e-12 * n)
        bic = n * np.log(sse / n) + penalty * (3 * k - 1) * np.log(n)
        if best is None or bic < best[0]:
            best = (bic, sorted(b for b in breaks if b > 0))
    return [] if best is None else best[1]


def test_the_vectorised_segmentation_matches_the_loop_it_replaced() -> None:
    rng = np.random.default_rng(7)
    cases: list[tuple[np.ndarray | None, np.ndarray, int, int, float]] = []
    for n in (0, 1, 14, 15, 29, 30, 31, 47, 120, 333):  # shorter than one segment, exactly one or two, longer
        cases.append((None, rng.normal(1.0, 0.05, n), 15, 11, 3.0))
    steps = np.repeat([0.8, 0.6, 0.75, 0.7, 0.9], 60) + np.linspace(0, -0.05, 300)
    for penalty in (6.0, 3.0, 1.0, 0.1, 0.001):  # from no break to as many as allowed
        cases.append((None, steps + rng.normal(0, 0.01, 300), 15, 11, penalty))
    days = np.arange(80.0)
    cases += [
        (None, np.ones(90), 15, 11, 3.0),  # every segment fits exactly
        (None, np.r_[np.zeros(40), np.ones(40)], 15, 0, 3.0),  # max_breaks 0: a single line
        (None, steps[:200] + rng.normal(0, 0.02, 200), 2, 3, 0.5),  # the smallest segments allowed
        (None, steps[:200] + rng.normal(0, 0.02, 200), 40, 11, 0.5),  # few lines fit: fewer k than max_breaks
        # ties: the kink point lies on both lines (break at 20 or 21), equally good tiles; the earliest wins
        (days[:41], np.abs(days[:41] - 20), 3, 5, 3.0),
        (days[:61], np.minimum(np.abs(days[:61] - 20), 15.0), 2, 5, 3.0),
        (days, np.tile([1.0, 1.0, 2.0, 2.0], 20), 5, 5, 0.001),
    ]
    for t, y, min_size, max_breaks, penalty in cases:
        if t is None:
            t = np.cumsum(rng.integers(1, 4, len(y))) / 365.25  # clear days come with gaps
        got = diagnostics._segment(t, y, min_size, max_breaks, penalty)
        want = _segment_reference(t, y, min_size, max_breaks, penalty)
        assert got == want, (len(y), min_size, max_breaks, penalty)
    assert diagnostics._segment(days[:41], np.abs(days[:41] - 20), 3, 5, 3.0) == [20]
