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


# ---------------------------------------------------------------------- SparseTSF and CycleNet
class _Tensor:
    """Stands for a torch tensor in `from_torch` (duck-typed): CI has no torch."""

    def __init__(self, a: np.ndarray) -> None:
        self.a = np.asarray(a, dtype=np.float32)

    def detach(self) -> _Tensor:
        return self

    def cpu(self) -> _Tensor:
        return self

    def numpy(self) -> np.ndarray:
        return self.a


class _Module:
    def __init__(self, state: dict[str, np.ndarray]) -> None:
        self.state = {k: _Tensor(v) for k, v in state.items()}
        self.p = 24

    def state_dict(self) -> dict[str, _Tensor]:
        return self.state


def _nets(seed: int = 0, n_series: int = 3, period: int = 168) -> tuple[E.SparseTSF, E.CycleNet]:
    rng = np.random.default_rng(seed)

    def f32(*shape: int) -> np.ndarray:  # weights exact in float32, as a trained module's
        return rng.normal(0, 0.3, shape).astype(np.float32).astype(float)

    sp = E.SparseTSF(f32(25), f32(1, 7))
    cy = E.CycleNet(f32(n_series, period), f32(24, 168) / 8, f32(24))
    return sp, cy


def _histories(n: int = 12, seed: int = 2) -> np.ndarray:
    rng = np.random.default_rng(seed)
    t = np.arange(168)
    h = 0.5 + 0.4 * np.sin(2 * np.pi * t / 24)[None, :] + rng.gamma(2.0, 0.1, (n, 168))
    h[rng.random(h.shape) < 0.05] = np.nan
    h[0, :5] = np.nan  # leading gap: repeats the first valid value
    h[1, -7:] = np.nan  # trailing gap
    h[2, 40:60] = np.nan  # a long interior gap
    h[3] = 0.8  # constant: standard deviation 0, only the 1e-3 remains
    h[4] = np.nan  # no valid value: 0
    return h


def _ref_window(h: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """`treina_proprio`'s windows: pandas interpolation, then mean and population deviation + 1e-3."""
    x = np.stack([pd.Series(r).interpolate(limit_direction="both").fillna(0.0).to_numpy() for r in h])
    mu, sd = x.mean(1, keepdims=True), x.std(1, keepdims=True) + 1e-3
    return (x - mu) / sd, mu, sd


def _ref_sparsetsf(m: E.SparseTSF, h: np.ndarray) -> np.ndarray:
    """The torch forward written directly: conv1d (cross-correlation, zero padding) + x, reshape by period."""
    x, mu, sd = _ref_window(h)
    z = np.stack([np.correlate(np.pad(r, 12), m.conv, mode="valid") for r in x]) + x
    seg = z.reshape(len(z), 7, 24).transpose(0, 2, 1)  # (B, phase, segment)
    out = (seg @ m.linear.T).transpose(0, 2, 1).reshape(len(z), -1)
    return out * sd + mu


def _ref_cyclenet(m: E.CycleNet, h: np.ndarray, phase: np.ndarray, series: np.ndarray) -> np.ndarray:
    x, mu, sd = _ref_window(h)
    w = m.period
    q_in = np.stack([m.cycle[s, (f + np.arange(168)) % w] for s, f in zip(series, phase, strict=True)])
    q_out = np.stack([m.cycle[s, (f + 168 + np.arange(24)) % w] for s, f in zip(series, phase, strict=True)])
    return ((x - q_in) @ m.weight.T + m.bias + q_out) * sd + mu


def test_causal_fill_is_the_benchmark_interpolation() -> None:
    h = _histories()
    before = h.copy()
    want = np.stack([pd.Series(r).interpolate(limit_direction="both").fillna(0.0).to_numpy() for r in h])
    np.testing.assert_array_equal(E.causal_fill(h), want)
    np.testing.assert_array_equal(E.causal_fill(h[2]), want[2])
    np.testing.assert_allclose(E._fill32(h), want, rtol=1e-6, atol=1e-7)
    np.testing.assert_array_equal(h, before)  # the input is not touched


def test_networks_equal_a_direct_reference() -> None:
    sp, cy = _nets()
    h = _histories()
    np.testing.assert_allclose(sp.predict(h), _ref_sparsetsf(sp, h), rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(sp.predict(h, np.float32), _ref_sparsetsf(sp, h), rtol=1e-5, atol=1e-5)
    phase = np.arange(len(h)) * 24 % 168
    series = np.arange(len(h)) % 3
    want = _ref_cyclenet(cy, h, phase, series)
    np.testing.assert_allclose(cy.predict(h, phase, series), want, rtol=1e-12, atol=1e-12)
    np.testing.assert_allclose(cy.predict(h, phase, series, np.float32), want, rtol=1e-5, atol=1e-5)
    one = cy.fix(2)
    np.testing.assert_allclose(one.predict(h[2], phase[2]), want[2], rtol=1e-12, atol=1e-12)
    assert np.isfinite(sp.predict(h)).all() and np.isfinite(cy.predict(h)).all()  # constant and empty rows
    # constant history: the window normalizes to 0, so SparseTSF gives back the level
    np.testing.assert_allclose(sp.predict(h[3]), 0.8, rtol=0, atol=1e-12)
    day = pd.Timestamp("2020-03-19")  # a Thursday: phase 3 * 24 in a weekly cycle
    assert cy.day_phase(day) == 72 and _nets(period=24)[1].day_phase(day) == 0
    np.testing.assert_array_equal(cy.forecast_day(h[5], day, 1), np.clip(cy.predict(h[5], 72, 1), 0, None))


def test_networks_from_state_dict_and_errors() -> None:
    sp, cy = _nets()
    h = _histories()
    m = E.SparseTSF.from_torch(_Module({"conv.weight": sp.conv.reshape(1, 1, 25), "lin.weight": sp.linear}))
    np.testing.assert_array_equal(m.predict(h), sp.predict(h))
    c = E.CycleNet.from_torch(_Module({"Q": cy.cycle, "f.weight": cy.weight, "f.bias": cy.bias}))
    np.testing.assert_array_equal(c.predict(h, 24, 1), cy.predict(h, 24, 1))
    assert c.n_series == 3 and c.period == 168 and c.n_parameters == 3 * 168 + 24 * 168 + 24
    mlp = {"Q": cy.cycle, "f.0.weight": np.zeros((512, 168)), "f.0.bias": np.zeros(512)}
    with pytest.raises(NotImplementedError):
        E.CycleNet.from_torch(_Module(mlp))
    with pytest.raises(NotImplementedError):
        E.SparseTSF.from_torch(
            _Module(
                {"conv.weight": np.zeros((1, 1, 25)), "lin.weight": np.zeros((1, 7)), "lin.bias": np.zeros(1)}
            )
        )
    with pytest.raises(ValueError):
        E.SparseTSF(np.zeros(5), np.zeros((1, 7)))
    with pytest.raises(ValueError):
        E.CycleNet(np.zeros((1, 48)), cy.weight, cy.bias)
    with pytest.raises(ValueError):
        E.to_c(cy, "cy")  # three series: one header per series
    with pytest.raises(ValueError):
        cy.fix(3)
    with pytest.raises(ValueError):
        cy.predict(h, 0, 3)
    with pytest.raises(ValueError):
        sp.predict(np.zeros(100))
    assert E.footprint(sp) == E.Footprint(4 * 32, 4 * (3 * 168 + 24))
    fp = E.footprint(cy.fix(0))
    assert fp.flash == 4 * (168 + 24 * 168 + 24) and fp.fits()


def test_networks_equal_torch() -> None:
    torch = pytest.importorskip("torch")
    nn = torch.nn

    class SparseTSF(nn.Module):  # copy of experimentos/testes_previsao/scripts/redes_proprias.py
        def __init__(self, L: int = 168, Hh: int = 24, p: int = 24) -> None:
            super().__init__()
            self.p = p
            self.conv = nn.Conv1d(1, 1, kernel_size=1 + 2 * (p // 2), padding=p // 2, bias=False)
            self.lin = nn.Linear(L // p, Hh // p, bias=False)

        def forward(self, x):  # type: ignore[no-untyped-def]
            B, L = x.shape
            x = self.conv(x[:, None, :])[:, 0, :] + x
            x = x.reshape(B, L // self.p, self.p).permute(0, 2, 1)
            return self.lin(x).permute(0, 2, 1).reshape(B, -1)

    class CycleNet(nn.Module):
        def __init__(self, n_series: int, W: int) -> None:
            super().__init__()
            self.W = W
            self.Q = nn.Parameter(torch.randn(n_series, W) * 0.3)
            self.f = nn.Linear(168, 24)

        def ciclo(self, serie, fase, n, desloc=0):  # type: ignore[no-untyped-def]
            idx = (fase[:, None] + desloc + torch.arange(n)[None, :]) % self.W
            return torch.gather(self.Q[serie], 1, idx)

        def forward(self, x, serie, fase):  # type: ignore[no-untyped-def]
            return self.f(x - self.ciclo(serie, fase, 168)) + self.ciclo(serie, fase, 24, desloc=168)

    torch.manual_seed(0)
    h = _histories()
    x, mu, sd = _ref_window(h)
    xt = torch.tensor(x, dtype=torch.float32)
    sp_t = SparseTSF().eval()
    cy_t = CycleNet(3, 168).eval()
    phase = np.arange(len(h)) * 24 % 168
    series = np.arange(len(h)) % 3
    with torch.no_grad():
        want_sp = sp_t(xt).numpy() * sd + mu
        want_cy = cy_t(xt, torch.tensor(series), torch.tensor(phase)).numpy() * sd + mu
    np.testing.assert_allclose(E.SparseTSF.from_torch(sp_t).predict(h), want_sp, rtol=1e-5, atol=1e-5)
    got = E.CycleNet.from_torch(cy_t).predict(h, phase, series)
    np.testing.assert_allclose(got, want_cy, rtol=1e-5, atol=1e-5)


@pytest.mark.skipif(not wasm_c.available(), reason="needs zig (pip install ziglang) and node")
def test_network_headers_reproduce_python() -> None:
    h = _histories()
    days = pd.date_range("2020-03-16", periods=len(h), freq="D")  # from a Monday: every weekday
    src = (
        '#include "{0}.h"\n'
        "void run(const float *in, long n, float *out) {{\n"
        "    for (long i = 0; i < n / 169; i++)\n"
        "        {0}_forecast_day(in + 169 * i, (int)in[169 * i + 168], 0, 0.0f, out + 24 * i);\n"
        "}}\n"
    )
    inputs = np.c_[h, days.dayofweek.to_numpy()].ravel()
    for period in (24, 168):
        sp, cy = _nets(seed=period, period=period)
        for name, m in (("sp", sp), ("cy", cy.fix(1))):
            got = wasm_c.run(src.format(name), inputs, 24 * len(h), headers={f"{name}.h": E.to_c(m, name)})
            got = got.reshape(len(h), 24)
            py32 = np.stack([m.forecast_day(r, d, dtype=np.float32) for r, d in zip(h, days, strict=True)])
            py64 = np.stack([m.forecast_day(r, d) for r, d in zip(h, days, strict=True)])
            np.testing.assert_allclose(got, py32, rtol=1e-6, atol=1e-6)
            np.testing.assert_allclose(got, py64, rtol=1e-5, atol=1e-5)
            assert (got >= 0).all() and (got > 0).any()
