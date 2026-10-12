"""prosumer.embedded: export with the preprocessing, exact tree paths, features equal to the benchmark's."""

from __future__ import annotations

import contextlib
import importlib.util

import numpy as np
import pandas as pd
import pytest

import wasm_c
from prosumer import embedded as E
from prosumer.forecast.lightgbm import LightGBM

# On the home Windows machine, fitting LightGBM after `sklearn.ensemble` was imported (with LightGBM not yet
# loaded) crashes with an access violation in `set_field`; loading LightGBM first avoids it (2026-10-12).
with contextlib.suppress(ImportError):  # the tests that need it skip
    import lightgbm  # noqa: F401


def _series(days: int = 40, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ds = pd.date_range("2020-03-01", periods=days * 24, freq="h")
    y = 0.4 + 0.3 * np.sin(2 * np.pi * (ds.hour.to_numpy() - 7) / 24) + rng.gamma(2.0, 0.1, len(ds))
    y[rng.random(len(ds)) < 0.03] = np.nan  # scattered gaps
    y[24 * 20 + 3 : 24 * 20 + 9] = np.nan  # a day with 18 valid hours: no total
    return pd.DataFrame({"ds": ds, "y": y})


def _table(g: pd.DataFrame, code: int = 3) -> pd.DataFrame:
    m = LightGBM()
    m._codes = {"S": code}
    return m._features(g, "S")


def _sklearn() -> None:
    pytest.importorskip("sklearn")  # CI installs only the dev extra; the export itself needs only numpy


def _xy(seed: int = 1) -> tuple[np.ndarray, np.ndarray]:
    t = pd.concat([_table(_series(60, s), s) for s in range(seed, seed + 3)], ignore_index=True)
    t = t[t["y"].notna()]
    x = t[list(E.FEATURES)].to_numpy()
    x = np.round(x, 1)  # coarse values: many ties, thresholds between neighbouring float32 values
    x = x.astype(np.float32).astype(float)  # exact in float32: Python and C see the same numbers
    return x, t["y"].to_numpy()


def test_features_equal_the_benchmark_table() -> None:
    g = _series()
    t = _table(g)
    y = g["y"].to_numpy()
    for k in (7, 8, 21, 22, 30, 39):
        day = pd.Timestamp("2020-03-01") + pd.Timedelta(days=k)
        got = E.day_ahead_features(y[24 * (k - 7) : 24 * k], day, series_code=3)
        want = t[t["dia"] == day][list(E.FEATURES)].to_numpy()
        np.testing.assert_allclose(got, want, rtol=1e-12, atol=1e-12, equal_nan=True)


def test_linear_folds_imputer_and_scaler() -> None:
    _sklearn()
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    x, y = _xy()
    x[::17, 6] = np.nan
    pipe = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1.0)).fit(x, y)
    imp, sc, r = pipe.steps[0][1], pipe.steps[1][1], pipe.steps[2][1]
    m = E.Linear.from_sklearn(r, E.FEATURES, imputer=imp, scaler=sc)
    np.testing.assert_allclose(m.predict(x), pipe.predict(x), rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(m.predict(x, np.float32), pipe.predict(x), rtol=1e-5, atol=1e-5)
    fixed = m.fix({"serie_cod": 2.0})
    x2 = x.copy()
    x2[:, 4] = 2.0
    np.testing.assert_allclose(fixed.predict(np.delete(x2, 4, axis=1)), m.predict(x2), rtol=1e-10, atol=1e-10)


def test_forest_paths_are_exact_and_fix_prunes() -> None:
    _sklearn()
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.impute import SimpleImputer

    x, y = _xy()
    x32 = SimpleImputer(strategy="median").fit_transform(x).astype(np.float32).astype(float)
    rf = RandomForestRegressor(n_estimators=8, max_depth=9, min_samples_leaf=3, random_state=0).fit(x32, y)
    m = E.Trees.from_sklearn(rf, E.FEATURES)
    assert m.n_trees == 8
    np.testing.assert_allclose(m.predict(x32), rf.predict(x32), rtol=1e-6, atol=1e-6)
    # the path, not only the value: each tree alone, float64 leaves
    for t, est in zip(range(m.n_trees), rf.estimators_, strict=True):
        one = E.Trees(m.features, m.feature, m.split, m.left, m.roots[t : t + 1], m.fill)
        np.testing.assert_allclose(one.predict(x32), est.predict(x32), rtol=1e-6, atol=1e-7)
    p = m.fix({"serie_cod": 2.0})
    assert p.n_nodes < m.n_nodes
    rows = x32[:, 4] == 2.0
    np.testing.assert_array_equal(p.predict(x32[rows]), m.predict(x32[rows]))


def test_threshold_rounding_down_is_what_sklearn_compares() -> None:
    a = np.float32(0.1)
    b = np.nextafter(a, np.float32(1))
    t64 = (float(a) + float(b)) / 2  # sklearn puts the threshold half way
    r = E._round_down32(np.array([t64]))[0]
    assert r == a  # x = a goes left, x = b goes right, as float32(x) <= t64 does
    big = E._round_down32(np.array([1e300, -1e300]))  # LightGBM's open-ended thresholds
    assert big[0] == np.finfo(np.float32).max
    assert big[1] == -np.inf


def test_block_totals_and_footprint() -> None:
    blocks = {h: ("peak" if 18 <= h < 21 else "off") for h in range(24)}
    t = E.block_totals(np.ones(24), blocks)
    assert t == {"off": 21.0, "peak": 3.0}
    m = E.Linear(E.FEATURES, np.ones(11), 0.0, np.zeros(11))
    fp = E.footprint(m)
    assert fp.flash == 4 * 11 * 2 + 4
    assert fp.fits()
    with pytest.raises(ValueError):
        E.block_totals(np.ones(24), {0: "a"})


def _lightgbm(x: np.ndarray, y: np.ndarray) -> object:
    lgb = pytest.importorskip("lightgbm")
    f = pd.DataFrame(x, columns=list(E.FEATURES)).astype({"serie_cod": int})
    params = {"n_estimators": 40, "num_leaves": 15, "min_child_samples": 20, "verbose": -1, "random_state": 0}
    return lgb.LGBMRegressor(**params).fit(f, y, categorical_feature=["serie_cod"])


def test_lightgbm_with_gaps_and_a_fixed_series() -> None:
    x, y = _xy()
    model = _lightgbm(x, y)  # x keeps its NaN: LightGBM routes them itself
    t = E.Trees.from_lightgbm(model, E.FEATURES, fixed={"serie_cod": 2})
    assert not t.mean and t.missing is not None
    rows = x[x[:, 4] == 2]
    assert np.isnan(rows).any()
    want = model.predict(pd.DataFrame(rows, columns=list(E.FEATURES)).astype({"serie_cod": int}))
    np.testing.assert_allclose(t.predict(rows), want, rtol=1e-6, atol=1e-6)
    with pytest.raises(NotImplementedError):
        E.Trees.from_lightgbm(model, E.FEATURES)  # the categorical series code must be fixed


@pytest.mark.skipif(not wasm_c.available(), reason="needs zig (pip install ziglang) and node")
def test_c_header_reproduces_python() -> None:
    _sklearn()
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler

    x, y = _xy()
    x[::13, 9] = np.nan
    gb = None
    if importlib.util.find_spec("lightgbm"):
        gb = E.Trees.from_lightgbm(_lightgbm(x, y), E.FEATURES, fixed={"serie_cod": 3})
    imp = SimpleImputer(strategy="median").fit(x)
    xi = imp.transform(x)
    rf = RandomForestRegressor(n_estimators=6, max_depth=8, min_samples_leaf=4, random_state=0).fit(xi, y)
    sc = StandardScaler().fit(xi)
    ridge = Ridge(alpha=1.0).fit(sc.transform(xi), y)
    models = {
        "lin": E.Linear.from_sklearn(ridge, E.FEATURES, imputer=imp, scaler=sc),
        "rf": E.Trees.from_sklearn(rf, E.FEATURES, imputer=imp),
    }
    if gb is not None:
        models["gb"] = gb
    g = _series(30, 7)
    hist = g["y"].to_numpy()[24 * 10 : 24 * 17]
    day = pd.Timestamp("2020-03-18")
    for name, m in models.items():
        src = (
            f'#include "{name}.h"\n'
            "void run(const float *in, long n, float *out) {\n"
            f"    long rows = (n - {E.HISTORY}) / 11;\n"
            f"    for (long i = 0; i < rows; i++) out[i] = {name}_predict(in + {E.HISTORY} + 11 * i);\n"
            f"    {name}_forecast_day(in, {day.dayofweek}, {day.dayofyear}, 3.0f, out + rows);\n"
            "}\n"
        )
        rows = x[:500]
        got = wasm_c.run(
            src, np.r_[hist, rows.ravel()], len(rows) + 24, headers={f"{name}.h": E.to_c(m, name)}
        )
        np.testing.assert_allclose(got[:500], m.predict(rows, np.float32), rtol=2e-6, atol=2e-6)
        day_py = np.clip(m.predict(E.day_ahead_features(hist, day, 3.0), np.float32), 0, None)
        np.testing.assert_allclose(got[500:], day_py, rtol=1e-5, atol=1e-5)


def test_forest_without_imputer_routes_gaps_as_sklearn() -> None:
    """Review finding (2026-10-12): without an imputer the export sent every NaN left (up to 0.45 kWh off)."""
    _sklearn()
    from sklearn.ensemble import RandomForestRegressor

    x, y = _xy()
    gaps = np.random.default_rng(5).random(x.shape) < 0.05
    gaps[:, 4] = False  # keep the series code
    xn = np.where(gaps, np.nan, x)
    for train in (xn, x):  # NaN seen in training, and NaN only at prediction time
        rf = RandomForestRegressor(n_estimators=8, max_depth=7, random_state=0).fit(train, y)
        m = E.Trees.from_sklearn(rf, E.FEATURES)
        assert m.missing is not None
        rows = np.isnan(xn).any(axis=1)
        np.testing.assert_allclose(m.predict(xn[rows]), rf.predict(xn[rows]), rtol=1e-6, atol=1e-6)
        p = m.fix({"serie_cod": 2.0})
        sel = rows & (xn[:, 4] == 2.0)
        np.testing.assert_allclose(p.predict(xn[sel]), rf.predict(xn[sel]), rtol=1e-6, atol=1e-6)
