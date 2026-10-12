"""Embedded models: export a fitted linear, tree or small network, WITH its preprocessing, to one C header.

Why a module of its own (step E4, pilot `piloto_embarcado.py`, study `docs/projeto/ESTUDO_EMBARCADO.md`):

- The legacy lesson (`legado/ia_solar/base_modelagem/embarcado/`): a `.tflite` file holds only the network;
  the device also needs the imputation and the scaling, which had to be rebuilt afterwards. Here the header
  carries everything between the meter readings and the forecast: the benchmark's day-ahead features computed
  from the last 168 hourly values, the fill values of the gaps, the model, the day and tariff-block totals.
- An ESP32 (520 KB SRAM, 4 MB flash) cannot run the benchmark's full-size trees, but it runs a Ridge
  (23 floats: fill values, weights, intercept) or a small forest (tens of KB). The pilot measured what that
  costs in skill: on house consumption the small models tie with the full-size ones.
- The benchmark's two small networks, SparseTSF (32 parameters) and CycleNet with the linear backbone
  (~4-7 thousand), are plain arrays too: `SparseTSF` and `CycleNet` hold them as numpy (`from_torch` reads a
  trained module's state dict without importing torch) and the header runs them on the raw 168 h with the
  benchmark's causal gap fill and per-window normalization (pilot `piloto_embarcado_redes.py`).
- No dependency besides numpy: the model is read from the fitted object (scikit-learn `coef_`/`tree_`,
  LightGBM `dump_model`), and the C is plain C99 (`math.h`, `stdint.h`), single-precision float, as the ESP32
  FPU.

Exactness. Tree thresholds are stored as the largest float32 not above scikit-learn's float64 threshold:
scikit-learn casts the features to float32 and compares them with a float64 threshold, and for any float32 x,
`x <= t64` exactly when `x <= rounddown32(t64)`. Rounding to the nearest float32 instead (what a plain cast
does) can send a value equal to the rounded threshold the wrong way. With this, the C forest takes the same
path as scikit-learn on every row; the output differs only by the float32 sum of the leaves. `predict` with
`dtype=np.float32` reproduces the C arithmetic in numpy.

The day-ahead features are the benchmark's (`02_referencias.py`, ported in `forecast.lightgbm`), regime A:
hour, day of week, day of year (sine, cosine), series code, the same hour 1, 2 and 7 days before, their 7-day
mean, yesterday's total (needs 20 of its 24 hours) and the mean of the last 7 totals (needs 5 of them).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .forecast.lightgbm import CALENDAR, LAGS
from .protocol import H

FEATURES: tuple[str, ...] = (*CALENDAR, *LAGS)
HISTORY = 7 * H  # hours of history the day-ahead features need


# ---------------------------------------------------------------------- features
def day_ahead_features(history: np.ndarray, day: pd.Timestamp, series_code: float = 0.0) -> np.ndarray:
    """The 24 feature rows (order of `FEATURES`) of `day`, from the 168 hourly values before it (NaN = gap).

    Same arithmetic as the benchmark's feature table, so the rows equal the training rows of the model.
    """
    y = np.asarray(history, dtype=float)
    if y.shape != (HISTORY,):
        raise ValueError(f"history must have {HISTORY} hourly values (7 days), not {y.shape}")
    days = y.reshape(7, H)[::-1]  # days[k] = the day k+1 days before `day`
    acc = days[0].copy()
    for k in range(1, 7):  # same order of additions as the benchmark: NaN in any day gives NaN
        acc = acc + days[k]
    totals = np.array([np.nansum(d) if np.isfinite(d).sum() >= 20 else np.nan for d in days])
    known = totals[np.isfinite(totals)]
    tot_mean7 = float(known.mean()) if len(known) >= 5 else np.nan
    day = pd.Timestamp(day)
    doy = 2 * np.pi * day.dayofyear / 365.25
    out = np.empty((H, len(FEATURES)))
    out[:, 0] = np.arange(H)
    out[:, 1] = day.dayofweek
    out[:, 2], out[:, 3] = np.sin(doy), np.cos(doy)
    out[:, 4] = series_code
    out[:, 5], out[:, 6], out[:, 7] = days[0], days[1], days[6]
    out[:, 8] = acc / 7
    out[:, 9] = totals[0]
    out[:, 10] = tot_mean7
    return out


def block_totals(forecast: np.ndarray, blocks: dict[int, str]) -> dict[str, float]:
    """Sum of a day's 24 hourly values per tariff block (`blocks`: hour -> block name, every hour)."""
    f = np.asarray(forecast, dtype=float)
    if f.shape != (H,) or set(blocks) != set(range(H)):
        raise ValueError("block_totals needs 24 hourly values and a block for every hour 0-23")
    out: dict[str, float] = {}
    for h in range(H):
        out[blocks[h]] = out.get(blocks[h], 0.0) + float(f[h])
    return out


# ---------------------------------------------------------------------- models
@dataclass(frozen=True)
class Linear:
    """y = bias + sum_j weights[j] * x_j, with x_j = fill[j] where x_j is NaN (scaling already folded in)."""

    features: tuple[str, ...]
    weights: np.ndarray
    bias: float
    fill: np.ndarray

    @classmethod
    def from_sklearn(
        cls, model: Any, features: list[str] | tuple[str, ...], *, imputer: Any = None, scaler: Any = None
    ) -> Linear:
        """From a fitted linear estimator (`coef_`, `intercept_`: Ridge, LinearRegression, Lasso...) and the
        optional SimpleImputer and StandardScaler applied before it, in that order."""
        coef = np.asarray(model.coef_, dtype=float).ravel()
        if len(coef) != len(features):
            raise ValueError(f"{len(coef)} coefficients for {len(features)} features")
        mean = np.zeros(len(coef)) if scaler is None or scaler.mean_ is None else np.asarray(scaler.mean_)
        scale = np.ones(len(coef)) if scaler is None or scaler.scale_ is None else np.asarray(scaler.scale_)
        w = coef / scale
        bias = float(np.asarray(model.intercept_).ravel()[0]) - float(np.sum(w * mean))
        fill = _fill(imputer, len(coef))
        return cls(tuple(features), w, bias, fill)

    def fix(self, values: dict[str, float]) -> Linear:
        """Fold features that are constant on the device (the series code, one-hot columns) into the bias."""
        keep = [j for j, f in enumerate(self.features) if f not in values]
        _check_names(values, self.features)
        bias = self.bias + sum(float(self.weights[self.features.index(f)]) * v for f, v in values.items())
        return Linear(tuple(self.features[j] for j in keep), self.weights[keep], bias, self.fill[keep])

    def predict(self, X: np.ndarray, dtype: Any = np.float64) -> np.ndarray:
        """`dtype=np.float32` reproduces the C arithmetic (sum in feature order, single precision)."""
        x = _impute(np.asarray(X, dtype=float), self.fill).astype(dtype)
        w = self.weights.astype(dtype)
        acc = np.full(len(x), self.bias, dtype=dtype)
        for j in range(len(w)):
            acc = (acc + w[j] * x[:, j]).astype(dtype)
        return acc.astype(float)


@dataclass(frozen=True)
class Trees:
    """A forest (or one tree) as flat arrays, children of a node stored side by side.

    `feature[i]` < 0 marks a leaf; `split[i]` is the threshold of an internal node (go right when
    x > split) or the value of a leaf; `left[i]` is the left child, the right one is `left[i] + 1`.
    The prediction is the mean of the trees' leaves (scikit-learn forests) or their sum (`mean=False`,
    gradient boosting). `missing` (LightGBM, or a scikit-learn forest without imputer) says where a gap goes
    at each node: 0 = a NaN counts as 0.0; 1/2 = a NaN goes left/right; 3/4 = a NaN or a zero goes left/right.
    """

    features: tuple[str, ...]
    feature: np.ndarray  # int, -1 at leaves
    split: np.ndarray  # float32
    left: np.ndarray  # int
    roots: np.ndarray  # int, one per tree
    fill: np.ndarray
    missing: np.ndarray | None = None  # uint8 per node, see above
    mean: bool = True

    @classmethod
    def from_sklearn(cls, model: Any, features: list[str] | tuple[str, ...], *, imputer: Any = None) -> Trees:
        """From a fitted single-output DecisionTreeRegressor, RandomForestRegressor or ExtraTreesRegressor.

        With an `imputer` (the benchmark's pipelines) gaps are filled before the forest. Without one, a gap
        follows scikit-learn's own routing (`tree_.missing_go_to_left`, learned per node since 1.3), exported
        as the left/right codes of `missing`."""
        estimators = list(getattr(model, "estimators_", [model]))
        trees: list[_Tree] = []
        for e in estimators:
            t = e.tree_
            if t.n_outputs != 1 or t.value.shape[2] != 1:
                raise NotImplementedError("only single-output regression trees")
            trees.append(
                (
                    t.children_left,
                    t.children_right,
                    t.feature,
                    t.threshold,
                    t.value[:, 0, 0].astype(float),
                    _sklearn_missing(t) if imputer is None else None,
                )
            )
        if any(int(tr[2].max(initial=-1)) >= len(features) for tr in trees):
            raise ValueError("the trees use more features than were named")
        return _layout(tuple(features), trees, _fill(imputer, len(features)), mean=True)

    @classmethod
    def from_lightgbm(
        cls, model: Any, features: list[str] | tuple[str, ...], *, fixed: dict[str, float] | None = None
    ) -> Trees:
        """From a fitted LightGBM regressor (LGBMRegressor or Booster) with an identity output (regression,
        L1, Huber, quantile objectives). Gaps are routed as LightGBM does (no imputation).

        A categorical feature (the benchmark's series code) must be `fixed`: its splits are resolved here,
        which also prunes the branches of the other series. Fixed numerical features are pruned the same way.
        """
        booster = getattr(model, "booster_", model)
        dump = booster.dump_model()
        if dump.get("num_tree_per_iteration", 1) != 1:
            raise NotImplementedError("only single-output boosters")
        objective = str(dump.get("objective", "regression")).split()[0]
        if objective not in ("regression", "regression_l1", "huber", "fair", "quantile", "mape"):
            raise NotImplementedError(f"objective {objective!r} transforms the output; not exported")
        names = list(dump["feature_names"])
        if [str(f) for f in features] != names:
            raise ValueError(f"features {list(features)} differ from the booster's {names}")
        fixed = dict(fixed or {})
        _check_names(fixed, tuple(features))
        fx = {names.index(f): float(v) for f, v in fixed.items()}
        trees = [_from_lgb_node(t["tree_structure"], fx) for t in dump["tree_info"]]
        return _layout(tuple(features), trees, np.full(len(features), np.nan), mean=False)

    @property
    def n_trees(self) -> int:
        return len(self.roots)

    @property
    def n_nodes(self) -> int:
        return len(self.feature)

    def fix(self, values: dict[str, float]) -> Trees:
        """Prune the branches a constant feature (e.g. the series code on a device that serves one house)
        never takes. The feature stays in the input, so the feature order does not change."""
        _check_names(values, self.features)
        fixed = {self.features.index(f): float(v) for f, v in values.items()}
        trees = [_prune(self, int(r), fixed) for r in self.roots]
        # thresholds are float32 already: `_layout` keeps them (rounding down an exact float32 is a no-op)
        return _layout(self.features, trees, self.fill, mean=self.mean)

    def predict(self, X: np.ndarray, dtype: Any = np.float64) -> np.ndarray:
        """Paths as in C (float32 inputs); `dtype=np.float32` also sums the leaves as the C does."""
        x = _impute(np.asarray(X, dtype=float), self.fill).astype(np.float32)
        n = len(x)
        acc = np.zeros(n, dtype=dtype)
        rows = np.arange(n)
        for r in self.roots:
            i = np.full(n, int(r))
            active = self.feature[i] >= 0
            while active.any():
                at = i[active]
                v = x[rows[active], self.feature[at]]
                m = None if self.missing is None else self.missing[at]
                i[active] = self.left[at] + _goes_right(v, self.split[at], m)
                active = self.feature[i] >= 0
            acc = (acc + self.split[i].astype(dtype)).astype(dtype)
        return (acc / dtype(self.n_trees) if self.mean else acc).astype(float)


_Tree = tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]
ZERO = 1e-35  # LightGBM's kZeroThreshold


def _sklearn_missing(t: Any) -> np.ndarray | None:
    """scikit-learn's per-node NaN direction as `Trees.missing` codes (1 = left, 2 = right)."""
    go_left = getattr(t, "missing_go_to_left", None)
    if go_left is None:  # scikit-learn < 1.3: NaN is not accepted at all
        return None
    return np.where(np.asarray(go_left, dtype=bool), 1, 2).astype(np.uint8)


def _goes_right(v: Any, split: Any, missing: Any) -> np.ndarray:
    """1 where the node sends the value right. Vectorised; scalars work too."""
    v = np.asarray(v, dtype=np.float32)
    if missing is None:
        return (v > split).astype(int)
    m = np.asarray(missing)
    nan = np.isnan(v)
    v0 = np.where(nan & (m == 0), np.float32(0), v)
    default = (nan & (m != 0)) | ((m >= 3) & (np.abs(v0) <= ZERO))
    return np.where(default, (m == 2) | (m == 4), v0 > split).astype(int)


def _from_lgb_node(root: dict[str, Any], fixed: dict[int, float]) -> _Tree:
    """One LightGBM tree (dump_model form) in array form, splits on fixed features resolved."""
    cl: list[int] = []
    cr: list[int] = []
    ft: list[int] = []
    th: list[float] = []
    val: list[float] = []
    ms: list[int] = []

    def walk(node: dict[str, Any]) -> int:
        while "leaf_value" not in node and int(node["split_feature"]) in fixed:
            node = (
                node["left_child"]
                if _lgb_left(node, fixed[int(node["split_feature"])])
                else node["right_child"]
            )
        k = len(ft)
        cl.append(-1)
        cr.append(-1)
        if "leaf_value" in node:
            ft.append(-1)
            th.append(0.0)
            val.append(float(node["leaf_value"]))
            ms.append(0)
            return k
        if node["decision_type"] != "<=":
            raise NotImplementedError("categorical split on a feature that is not fixed")
        mt = node.get("missing_type", "None")
        code = {"None": 0, "NaN": 1, "Zero": 3}[mt]
        if code and not node.get("default_left", True):
            code += 1
        ft.append(int(node["split_feature"]))
        th.append(float(node["threshold"]))
        val.append(0.0)
        ms.append(code)
        a = walk(node["left_child"])
        b = walk(node["right_child"])
        cl[k], cr[k] = a, b
        return k

    walk(root)
    return np.array(cl), np.array(cr), np.array(ft), np.array(th), np.array(val), np.array(ms, dtype=np.uint8)


def _lgb_left(node: dict[str, Any], v: float) -> bool:
    """LightGBM's decision for a known value (NumericalDecision / CategoricalDecision)."""
    mt = node.get("missing_type", "None")
    if node["decision_type"] == "==":
        if math.isnan(v) or v < 0:
            return False
        return str(int(v)) in str(node["threshold"]).split("||")
    if math.isnan(v) and mt != "NaN":
        v = 0.0
    if (mt == "Zero" and abs(v) <= ZERO) or (mt == "NaN" and math.isnan(v)):
        return bool(node.get("default_left", True))
    return v <= float(node["threshold"])


# ---------------------------------------------------------------------- neural linear models
# The benchmark's two small networks (`experimentos/testes_previsao/scripts/redes_proprias.py`), regime A:
# both read the 168 hours before the day, causally filled, and normalize the window by its own mean and
# population standard deviation plus 1e-3 (`treina_proprio`). Their weights are a few plain arrays, so the
# library holds them as numpy and never imports torch; `from_torch` only reads a module's state dict.

EPS = 1e-3  # added to the window's standard deviation, as `treina_proprio`


def causal_fill(history: np.ndarray) -> np.ndarray:
    """The gaps (NaN) of each history row filled as the benchmark windows are (`protocol.DayAhead`, pandas
    `interpolate(limit_direction="both")`): linear between the valid neighbours, the ends repeat the nearest
    valid value, a row with no valid value becomes 0. Float64; `history` is (168,) or (n, 168)."""
    y = np.array(history, dtype=float)
    rows = y.reshape(-1, y.shape[-1])
    i = np.arange(rows.shape[1])
    for r in rows:
        ok = ~np.isnan(r)
        if ok.all():
            continue
        r[~ok] = np.interp(i[~ok], i[ok], r[ok]) if ok.any() else 0.0
    return y


def _fill32(history: np.ndarray) -> np.ndarray:
    """`causal_fill` in the C's float32 arithmetic: slope = (y_q - y_p) / (q - p); slope * (t - p) + y_p."""
    h = np.asarray(history, dtype=np.float32)
    out = h.copy()
    for r, x in zip(h, out, strict=True):
        ok = np.flatnonzero(~np.isnan(r))
        if len(ok) == len(r):
            continue
        if len(ok) == 0:
            x[:] = 0.0
            continue
        x[: ok[0]] = r[ok[0]]
        x[ok[-1] + 1 :] = r[ok[-1]]
        for t in np.flatnonzero(np.isnan(r[ok[0] : ok[-1]])) + ok[0]:
            p = ok[ok < t][-1]
            q = ok[ok > t][0]
            slope = (r[q] - r[p]) / np.float32(q - p)
            x[t] = slope * np.float32(t - p) + r[p]
    return out


def _window(history: np.ndarray, dtype: Any) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Filled, normalized windows (n, 168), their mean and deviation (n, 1); in `dtype` (float32: C order)."""
    h = np.asarray(history, dtype=float)
    if h.shape[-1] != HISTORY or h.ndim > 2:
        raise ValueError(f"history must be (168,) or (n, 168) hourly values, not {h.shape}")
    h = h.reshape(-1, HISTORY)
    if np.dtype(dtype) == np.float64:
        x = causal_fill(h)
        mu = x.mean(axis=1, keepdims=True)
        sd = x.std(axis=1, keepdims=True) + EPS
        return (x - mu) / sd, mu, sd
    x = _fill32(h)
    s = np.zeros(len(x), dtype=np.float32)
    for t in range(HISTORY):  # sequential sums, as the C loop
        s = s + x[:, t]
    m = s / np.float32(HISTORY)
    v = np.zeros(len(x), dtype=np.float32)
    for t in range(HISTORY):
        d = x[:, t] - m
        v = v + d * d
    sd = np.sqrt(v / np.float32(HISTORY)) + np.float32(EPS)
    return (x - m[:, None]) / sd[:, None], m[:, None], sd[:, None]


def _state(module: Any) -> dict[str, np.ndarray]:
    """A torch module's parameters as float64 numpy arrays (duck-typed: no torch import here)."""
    return {k: np.asarray(v.detach().cpu().numpy(), dtype=float) for k, v in module.state_dict().items()}


def _out(y: np.ndarray, single: bool) -> np.ndarray:
    y = np.asarray(y, dtype=float)
    return y[0] if single else y


@dataclass(frozen=True)
class SparseTSF:
    """SparseTSF (Lin et al., 2024) as in the benchmark: on the normalized window x, z = conv(x) + x (kernel
    `2 * (period // 2) + 1`, zero padding, no bias), then each of the `period` phases is forecast by a linear
    map shared by all phases from the window's values at that phase: out[o * period + ph] =
    sum_j linear[o, j] * z[j * period + ph]. 32 parameters for period 24. Series-independent."""

    conv: np.ndarray  # (kernel,)
    linear: np.ndarray  # (24 // period, 168 // period)
    period: int = 24

    def __post_init__(self) -> None:
        p = self.period
        if p < 1 or HISTORY % p or H % p:
            raise ValueError(f"period {p} must divide {HISTORY} and {H}")
        if np.shape(self.conv) != (1 + 2 * (p // 2),):
            raise ValueError(f"conv must have {1 + 2 * (p // 2)} weights, not {np.shape(self.conv)}")
        if np.shape(self.linear) != (H // p, HISTORY // p):
            raise ValueError(f"linear must be {(H // p, HISTORY // p)}, not {np.shape(self.linear)}")

    @classmethod
    def from_torch(cls, module: Any) -> SparseTSF:
        """From the benchmark's `SparseTSF` module (`conv.weight`, `lin.weight`, attribute `p`)."""
        s = _state(module)
        if set(s) != {"conv.weight", "lin.weight"}:
            raise NotImplementedError(f"expected conv.weight and lin.weight without bias, got {sorted(s)}")
        return cls(s["conv.weight"].reshape(-1), s["lin.weight"], int(getattr(module, "p", 24)))

    @property
    def n_parameters(self) -> int:
        return int(self.conv.size + self.linear.size)

    def predict(self, history: np.ndarray, dtype: Any = np.float64) -> np.ndarray:
        """The 24 values after each 168 h history (NaN = gap, filled causally). `dtype=np.float32` reproduces
        the C arithmetic. Not clipped (see `forecast_day`)."""
        single = np.ndim(history) == 1
        x, mu, sd = _window(history, dtype)
        w = np.asarray(self.conv, dtype=dtype)
        lin = np.asarray(self.linear, dtype=dtype)
        pad = len(w) // 2
        xp = np.pad(x, ((0, 0), (pad, pad)))
        c = np.zeros_like(x)
        for k in range(len(w)):  # c[t] = sum_k w[k] x[t + k - pad], in the C order
            c = c + w[k] * xp[:, k : k + HISTORY]
        z = c + x
        p = self.period
        out = np.zeros((len(x), H), dtype=dtype)
        for o in range(H // p):
            acc = np.zeros((len(x), p), dtype=dtype)
            for j in range(HISTORY // p):
                acc = acc + lin[o, j] * z[:, j * p : (j + 1) * p]
            out[:, o * p : (o + 1) * p] = acc
        return _out(out * sd + mu, single)

    def forecast_day(self, history: np.ndarray, day: Any = None, dtype: Any = np.float64) -> np.ndarray:
        """What the header's `<name>_forecast_day` returns: `predict`, negatives cut. `day` is not used."""
        return np.clip(self.predict(history, dtype), 0.0, None)


@dataclass(frozen=True)
class CycleNet:
    """CycleNet (Lin et al., NeurIPS 2024) with the linear backbone, as in the benchmark: a learned cycle Q of
    W points per series (24 or 168) is removed from the normalized window and its continuation added back to
    a linear map 168 -> 24 of the residual. The phase is the position in the cycle of the window's first hour:
    hour of day (W = 24) or weekday * 24 + hour (W = 168, Monday = 0). For a day-ahead window issued at
    midnight the first hour is 00:00 of the same weekday a week before, so the phase is 0 (W = 24) or
    weekday(day) * 24 (`day_phase`).

    The clock is the training's: the benchmark used fixed offsets (`Etc/GMT` for the houses, `Etc/GMT+3`
    for the plants) and Q was learnt on those hours. A device that feeds local daylight-saving time is one
    hour off all summer (in Europe/Dublin the window of 2020-04-01 starts at 23:00 local: phase 47, not
    48); give it the history and the weekday on the fixed-offset clock."""

    cycle: np.ndarray  # (n_series, W)
    weight: np.ndarray  # (24, 168)
    bias: np.ndarray  # (24,)

    def __post_init__(self) -> None:
        if np.ndim(self.cycle) != 2 or np.shape(self.cycle)[1] not in (H, HISTORY):
            raise ValueError(f"cycle must be (n_series, 24 or 168), not {np.shape(self.cycle)}")
        if np.shape(self.weight) != (H, HISTORY) or np.shape(self.bias) != (H,):
            raise ValueError("weight must be (24, 168) and bias (24,): only the linear backbone is exported")

    @classmethod
    def from_torch(cls, module: Any) -> CycleNet:
        """From the benchmark's `CycleNet` module with the linear backbone (`Q`, `f.weight`, `f.bias`)."""
        s = _state(module)
        if set(s) != {"Q", "f.weight", "f.bias"}:
            raise NotImplementedError(f"only the linear backbone (Q, f.weight, f.bias), got {sorted(s)}")
        return cls(s["Q"], s["f.weight"], s["f.bias"])

    @property
    def period(self) -> int:
        return int(self.cycle.shape[1])

    @property
    def n_series(self) -> int:
        return int(self.cycle.shape[0])

    @property
    def n_parameters(self) -> int:
        return int(self.cycle.size + self.weight.size + self.bias.size)

    def fix(self, series: int) -> CycleNet:
        """Keep the cycle of one series (index in the training order: sorted series ids), as a device that
        serves one house needs. Required before `to_c`."""
        if not 0 <= series < self.n_series:
            raise ValueError(f"series {series} outside 0-{self.n_series - 1}")
        return CycleNet(self.cycle[series : series + 1], self.weight, self.bias)

    def day_phase(self, day: Any) -> int:
        """Phase of the window of the day `day` (issued at its midnight)."""
        return 0 if self.period == H else int(pd.Timestamp(day).dayofweek) * H

    def predict(
        self, history: np.ndarray, phase: Any = 0, series: Any = 0, dtype: Any = np.float64
    ) -> np.ndarray:
        """The 24 values after each 168 h history (NaN = gap, filled causally); `phase` and `series` are
        scalars or one per row. `dtype=np.float32` reproduces the C arithmetic. Not clipped."""
        single = np.ndim(history) == 1
        x, mu, sd = _window(history, dtype)
        n = len(x)
        ph = np.broadcast_to(np.asarray(phase, dtype=int), (n,))
        se = np.broadcast_to(np.asarray(series, dtype=int), (n,))
        if (se < 0).any() or (se >= self.n_series).any():
            raise ValueError(f"series outside 0-{self.n_series - 1}")
        q = np.asarray(self.cycle, dtype=dtype)
        w = np.asarray(self.weight, dtype=dtype)
        W = self.period
        r = x - q[se[:, None], (ph[:, None] + np.arange(HISTORY)[None, :]) % W]
        acc = np.broadcast_to(np.asarray(self.bias, dtype=dtype), (n, H)).copy()
        for t in range(HISTORY):  # in the C order
            acc = acc + w[:, t][None, :] * r[:, t][:, None]
        acc = acc + q[se[:, None], (ph[:, None] + HISTORY + np.arange(H)[None, :]) % W]
        return _out(acc * sd + mu, single)

    def forecast_day(
        self, history: np.ndarray, day: Any, series: int = 0, dtype: Any = np.float64
    ) -> np.ndarray:
        """What the header's `<name>_forecast_day` returns for `day`: `predict` at the day's phase, negatives
        cut."""
        return np.clip(self.predict(history, self.day_phase(day), series, dtype), 0.0, None)


Network = SparseTSF | CycleNet

Model = Linear | Trees | SparseTSF | CycleNet


# ---------------------------------------------------------------------- sizes
@dataclass(frozen=True)
class Footprint:
    """Bytes of the model's constant arrays (flash) and of the working buffers of one day's forecast (RAM)."""

    flash: int
    ram: int

    def fits(self, flash: int = 4 * 1024 * 1024, ram: int = 320 * 1024) -> bool:
        """Default: an ESP32 with 4 MB flash and ~320 KB of its 520 KB SRAM free for data."""
        return self.flash <= flash and self.ram <= ram


def footprint(model: Model, *, day_ahead: bool = True) -> Footprint:
    """Flash and RAM of the exported header. For the networks the RAM is always that of `forecast_day`
    (history, filled/normalized window, SparseTSF's conv output, 24 outputs); `day_ahead` is ignored."""
    if isinstance(model, SparseTSF):
        return Footprint(4 * model.n_parameters, 4 * (3 * HISTORY + H))
    if isinstance(model, CycleNet):
        return Footprint(4 * model.n_parameters, 4 * (2 * HISTORY + H))
    n = len(model.features)
    flash = 4 * n  # fill values
    if isinstance(model, Linear):
        flash += 4 * n + 4
    else:
        per_node = 1 + 4 + _index_bytes(model.n_nodes) + (0 if model.missing is None else 1)
        flash += model.n_nodes * per_node + model.roots.size * 4
    ram = 4 * n  # imputed copy of one row
    if day_ahead:
        ram += 4 * (HISTORY + H * n + H)  # history, 24 feature rows, 24 outputs
    return Footprint(flash, ram)


# ---------------------------------------------------------------------- C
def to_c(model: Model, name: str, *, day_ahead: bool = True, clip_negative: bool = True) -> str:
    """A self-contained C99 header: `<name>_predict(const float *x)` for one feature row and, with
    `day_ahead`, `<name>_features(hist, dow, doy, series_code, out)` and
    `<name>_forecast_day(hist, dow, doy, series_code, out24)` (dow: Monday = 0; doy: 1-366; hist: the 168
    hourly values before the day, oldest first, NAN for a gap), plus `prosumer_block_totals`.

    A `SparseTSF` or a one-series `CycleNet` (see `CycleNet.fix`) gives only `<name>_forecast_day` with the
    same arguments (the networks do not use `doy` and `series_code`; SparseTSF not `dow` either): the gaps
    are filled as the benchmark windows (`causal_fill`), not imputed per feature as the other models do.
    `hist` and `dow` must be on the training's clock (fixed offset in the benchmark, see `CycleNet`).
    """
    if not name.isidentifier():
        raise ValueError(f"{name!r} is not a C identifier")
    if isinstance(model, SparseTSF | CycleNet):
        if not day_ahead:
            raise ValueError(
                "a network header is always the day-ahead forecast; day_ahead=False is for trees"
            )
        return _c_network(model, name, clip_negative)
    if day_ahead and model.features != FEATURES:
        raise ValueError(f"day_ahead needs the features {FEATURES}; fix() drops nothing for trees")
    n = len(model.features)
    up = name.upper()
    lines = [
        f"/* {name}: generated by prosumer.embedded. Features: {', '.join(model.features)}. */",
        "/* Gaps are NaN and are tested with isnan(): do not compile with -ffast-math (it removes them). */",
        f"#ifndef {up}_H",
        f"#define {up}_H",
        "#include <math.h>",
        "#include <stdint.h>",
        "",
        f"#define {up}_N_FEATURES {n}",
        f"static const float {name}_fill[{n}] = {{{_floats(model.fill)}}};",
    ]
    if isinstance(model, Linear):
        lines += [
            f"static const float {name}_weights[{n}] = {{{_floats(model.weights)}}};",
            f"static const float {name}_bias = {_float(model.bias)};",
            "",
            f"static inline float {name}_predict(const float *x) {{",
            f"    float acc = {name}_bias;",
            f"    for (int j = 0; j < {n}; j++) {{",
            f"        const float v = isnan(x[j]) ? {name}_fill[j] : x[j];",
            f"        acc = acc + {name}_weights[j] * v;",
            "    }",
            "    return acc;",
            "}",
        ]
    else:
        idx = "int16_t" if _index_bytes(model.n_nodes) == 2 else "int32_t"
        nn = model.n_nodes
        if model.missing is None:
            go = f"(v[{name}_feature[i]] > {name}_split[i])"
            extra: list[str] = []
        else:
            go = f"{name}_right(v[{name}_feature[i]], {name}_split[i], {name}_missing[i])"
            extra = [
                f"static const uint8_t {name}_missing[{nn}] = {{{_ints(model.missing)}}};",
                "/* LightGBM's routing: 0 NaN counts as 0; 1/2 NaN left/right; 3/4 NaN or zero left/right */",
                f"static inline int {name}_right(float v, float s, uint8_t m) {{",
                "    if (m == 0) { if (isnan(v)) v = 0.0f; return v > s; }",
                f"    if (isnan(v) || (m >= 3 && fabsf(v) <= {ZERO:g}f)) return m == 2 || m == 4;",
                "    return v > s;",
                "}",
            ]
        lines += [
            f"#define {up}_N_TREES {model.n_trees}",
            f"#define {up}_N_NODES {model.n_nodes}",
            f"static const int8_t {name}_feature[{model.n_nodes}] = {{{_ints(model.feature)}}};",
            f"static const float {name}_split[{model.n_nodes}] = {{{_floats(model.split)}}};",
            f"static const {idx} {name}_left[{model.n_nodes}] = {{{_ints(model.left)}}};",
            f"static const int32_t {name}_roots[{model.n_trees}] = {{{_ints(model.roots)}}};",
            *extra,
            "",
            f"static inline float {name}_predict(const float *x) {{",
            f"    float v[{n}];",
            f"    for (int j = 0; j < {n}; j++) v[j] = isnan(x[j]) ? {name}_fill[j] : x[j];",
            "    float acc = 0.0f;",
            f"    for (int t = 0; t < {model.n_trees}; t++) {{",
            f"        int32_t i = {name}_roots[t];",
            f"        while ({name}_feature[i] >= 0)",
            f"            i = (int32_t){name}_left[i] + {go};",
            f"        acc = acc + {name}_split[i];",
            "    }",
            f"    return acc / (float){model.n_trees};" if model.mean else "    return acc;",
            "}",
        ]
    if day_ahead:
        lines += _c_day_ahead(name, n, clip_negative)
    lines += ["", f"#endif /* {up}_H */", ""]
    return "\n".join(lines)


def _c_day_ahead(name: str, n: int, clip: bool) -> list[str]:
    out = "out[h] = y < 0.0f ? 0.0f : y;" if clip else "out[h] = y;"
    return [
        "",
        "/* The benchmark's day-ahead features of the 24 hours of a day, from the 168 hours before it. */",
        f"static inline void {name}_features(const float hist[{HISTORY}], int dow, int doy,",
        f"                                     float series_code, float out[{H}][{n}]) {{",
        "    float tot[7];",
        "    for (int k = 0; k < 7; k++) {  /* tot[k]: total of the day k+1 days before; 20 of 24 hours */",
        f"        const float *d = hist + {HISTORY} - {H} * (k + 1);",
        "        float s = 0.0f; int c = 0;",
        f"        for (int h = 0; h < {H}; h++) if (!isnan(d[h])) {{ s += d[h]; c++; }}",
        "        tot[k] = c >= 20 ? s : NAN;",
        "    }",
        "    float s7 = 0.0f; int c7 = 0;",
        "    for (int k = 0; k < 7; k++) if (!isnan(tot[k])) { s7 += tot[k]; c7++; }",
        "    const float tot_mean7 = c7 >= 5 ? s7 / (float)c7 : NAN;",
        "    const float a = 6.283185307179586f * (float)doy / 365.25f;",
        "    const float ds = sinf(a), dc = cosf(a);",
        f"    for (int h = 0; h < {H}; h++) {{",
        f"        float m = hist[{HISTORY - H} + h];",
        f"        for (int k = 2; k <= 7; k++) m = m + hist[{HISTORY} - {H} * k + h];",
        "        out[h][0] = (float)h; out[h][1] = (float)dow; out[h][2] = ds; out[h][3] = dc;",
        "        out[h][4] = series_code;",
        f"        out[h][5] = hist[{HISTORY - H} + h]; out[h][6] = hist[{HISTORY - 2 * H} + h];",
        "        out[h][7] = hist[h];",
        "        out[h][8] = m / 7.0f; out[h][9] = tot[0]; out[h][10] = tot_mean7;",
        "    }",
        "}",
        "",
        f"static inline void {name}_forecast_day(const float hist[{HISTORY}], int dow, int doy,",
        f"                                         float series_code, float out[{H}]) {{",
        f"    float x[{H}][{n}];",
        f"    {name}_features(hist, dow, doy, series_code, x);",
        f"    for (int h = 0; h < {H}; h++) {{",
        f"        const float y = {name}_predict(x[h]);",
        f"        {out}",
        "    }",
        "}",
        *_C_BLOCK_TOTALS,
    ]


_C_BLOCK_TOTALS = [
    "",
    "#ifndef PROSUMER_BLOCK_TOTALS",
    "#define PROSUMER_BLOCK_TOTALS",
    "/* Day total and tariff blocks: block[h] is the block of hour h (0..n_blocks-1). */",
    "static inline void prosumer_block_totals(const float y[24], const uint8_t block[24], int n_blocks,",
    "                                         float *totals) {",
    "    for (int b = 0; b < n_blocks; b++) totals[b] = 0.0f;",
    "    for (int h = 0; h < 24; h++) totals[block[h]] += y[h];",
    "}",
    "#endif",
]

# Shared by every network header: the benchmark's causal fill of the window and its mean and population
# deviation (+1e-3), single precision, sums in index order (`_fill32` and `_window` mirror them in numpy).
_C_WINDOW = [
    "",
    "#ifndef PROSUMER_WINDOW",
    "#define PROSUMER_WINDOW",
    "/* Gaps (NAN) filled as the benchmark windows: linear between the valid neighbours, the ends repeat the",
    "   nearest valid value, no valid value gives 0. */",
    "static inline void prosumer_causal_fill(const float *h, int n, float *x) {",
    "    int first = -1, last = -1;",
    "    for (int t = 0; t < n; t++) if (!isnan(h[t])) { if (first < 0) first = t; last = t; }",
    "    if (first < 0) { for (int t = 0; t < n; t++) x[t] = 0.0f; return; }",
    "    int p = first;",
    "    for (int t = 0; t < n; t++) {",
    "        if (t < first) x[t] = h[first];",
    "        else if (t > last) x[t] = h[last];",
    "        else if (!isnan(h[t])) { x[t] = h[t]; p = t; }",
    "        else {",
    "            int q = t + 1;",
    "            while (isnan(h[q])) q++;",
    "            const float slope = (h[q] - h[p]) / (float)(q - p);",
    "            x[t] = slope * (float)(t - p) + h[p];",
    "        }",
    "    }",
    "}",
    "",
    "/* Normalizes x in place by its mean and population standard deviation + 1e-3. */",
    "static inline void prosumer_normalize(float *x, int n, float *mu, float *sd) {",
    "    float s = 0.0f;",
    "    for (int t = 0; t < n; t++) s = s + x[t];",
    "    const float m = s / (float)n;",
    "    float v = 0.0f;",
    "    for (int t = 0; t < n; t++) { const float d = x[t] - m; v = v + d * d; }",
    "    const float sdev = sqrtf(v / (float)n) + 1e-3f;",
    "    for (int t = 0; t < n; t++) x[t] = (x[t] - m) / sdev;",
    "    *mu = m;",
    "    *sd = sdev;",
    "}",
    "#endif",
]


def _c_network(model: SparseTSF | CycleNet, name: str, clip: bool) -> str:
    up = name.upper()
    out = "out[h] = y < 0.0f ? 0.0f : y;" if clip else "out[h] = y;"
    kind = "SparseTSF" if isinstance(model, SparseTSF) else f"CycleNet (linear, cycle of {model.period} h)"
    lines = [
        f"/* {name}: {kind}, generated by prosumer.embedded. {model.n_parameters} parameters. */",
        "/* Gaps are NaN and are tested with isnan(): do not compile with -ffast-math (it removes them). */",
        f"#ifndef {up}_H",
        f"#define {up}_H",
        "#include <math.h>",
        "#include <stdint.h>",
        *_C_WINDOW,
        "",
    ]
    sig = [
        f"/* The 24 hours of a day from the {HISTORY} hours before it (oldest first, NAN for a gap);",
        "   dow: weekday of the day, Monday = 0. */",
        f"static inline void {name}_forecast_day(const float hist[{HISTORY}], int dow, int doy,",
        f"                                         float series_code, float out[{H}]) {{",
    ]
    if isinstance(model, SparseTSF):
        if model.conv.size > HISTORY:
            raise ValueError("kernel longer than the window")
        p, k = model.period, model.conv.size
        lines += [
            f"static const float {name}_conv[{k}] = {{{_floats(model.conv)}}};",
            f"static const float {name}_linear[{model.linear.size}] = {{{_floats(model.linear.ravel())}}};",
            "",
            *sig,
            "    (void)dow; (void)doy; (void)series_code;",
            f"    float x[{HISTORY}], z[{HISTORY}], mu, sd;",
            f"    prosumer_causal_fill(hist, {HISTORY}, x);",
            f"    prosumer_normalize(x, {HISTORY}, &mu, &sd);",
            f"    for (int t = 0; t < {HISTORY}; t++) {{",
            "        float c = 0.0f;",
            f"        for (int k = 0; k < {k}; k++) {{",
            f"            const int i = t + k - {k // 2};",
            f"            if (i >= 0 && i < {HISTORY}) c = c + {name}_conv[k] * x[i];",
            "        }",
            "        z[t] = c + x[t];",
            "    }",
            f"    for (int o = 0; o < {H // p}; o++) {{",
            f"        for (int ph = 0; ph < {p}; ph++) {{",
            "            float acc = 0.0f;",
            f"            for (int j = 0; j < {HISTORY // p}; j++)",
            f"                acc = acc + {name}_linear[o * {HISTORY // p} + j] * z[j * {p} + ph];",
            f"            const int h = o * {p} + ph;",
            "            const float y = acc * sd + mu;",
            f"            {out}",
            "        }",
            "    }",
            "}",
        ]
    else:
        if model.n_series != 1:
            raise ValueError(f"CycleNet has {model.n_series} series: fix(series) one per header")
        w = model.period
        phase = "0" if w == H else "(((dow % 7) + 7) % 7) * 24"
        lines += [
            f"#define {up}_PERIOD {w}",
            f"static const float {name}_cycle[{w}] = {{{_floats(model.cycle[0])}}};",
            f"static const float {name}_weight[{H * HISTORY}] = {{{_floats(model.weight.ravel())}}};",
            f"static const float {name}_bias[{H}] = {{{_floats(model.bias)}}};",
            "",
            *sig,
            "    (void)dow; (void)doy; (void)series_code;" if w == H else "    (void)doy; (void)series_code;",
            f"    const int phase = {phase};",
            f"    float x[{HISTORY}], mu, sd;",
            f"    prosumer_causal_fill(hist, {HISTORY}, x);",
            f"    prosumer_normalize(x, {HISTORY}, &mu, &sd);",
            f"    for (int t = 0; t < {HISTORY}; t++) x[t] = x[t] - {name}_cycle[(phase + t) % {w}];",
            f"    for (int h = 0; h < {H}; h++) {{",
            f"        float acc = {name}_bias[h];",
            f"        for (int t = 0; t < {HISTORY}; t++)",
            f"            acc = acc + {name}_weight[h * {HISTORY} + t] * x[t];",
            f"        acc = acc + {name}_cycle[(phase + {HISTORY} + h) % {w}];",
            "        const float y = acc * sd + mu;",
            f"        {out}",
            "    }",
            "}",
        ]
    lines += [*_C_BLOCK_TOTALS, "", f"#endif /* {up}_H */", ""]
    return "\n".join(lines)


# ---------------------------------------------------------------------- helpers
def _fill(imputer: Any, n: int) -> np.ndarray:
    if imputer is None:
        return np.full(n, np.nan)
    s = np.asarray(imputer.statistics_, dtype=float)
    if len(s) != n:
        raise ValueError(f"imputer has {len(s)} statistics for {n} features")
    return s


def _impute(x: np.ndarray, fill: np.ndarray) -> np.ndarray:
    return np.where(np.isnan(x), fill[None, :], x)


def _check_names(values: dict[str, float], features: tuple[str, ...]) -> None:
    unknown = set(values) - set(features)
    if unknown:
        raise ValueError(f"unknown features {sorted(unknown)}")


def _round_down32(t: np.ndarray) -> np.ndarray:
    """Largest float32 <= t, element-wise."""
    big = float(np.finfo(np.float32).max)
    # above the float32 range every finite float32 is below t: FLT_MAX is exact (LightGBM's 1e300 thresholds)
    t = np.minimum(np.asarray(t, dtype=float), big)
    with np.errstate(over="ignore"):  # below -FLT_MAX: -inf, no finite float32 is below t either
        r = t.astype(np.float32)
    over = r.astype(float) > t
    r[over] = np.nextafter(r[over], np.float32(-np.inf))
    return r


def _prune(t: Trees, root: int, fixed: dict[int, float]) -> _Tree:
    """One tree of `t` in array form, skipping the decisions on fixed features."""
    cl: list[int] = []
    cr: list[int] = []
    ft: list[int] = []
    sp: list[float] = []
    ms: list[int] = []

    def walk(i: int) -> int:
        while t.feature[i] >= 0 and int(t.feature[i]) in fixed:
            m = None if t.missing is None else t.missing[i]
            i = int(t.left[i]) + int(_goes_right(np.float32(fixed[int(t.feature[i])]), t.split[i], m))
        k = len(ft)
        cl.append(-1)
        cr.append(-1)
        ft.append(int(t.feature[i]))
        sp.append(float(t.split[i]))
        ms.append(0 if t.missing is None else int(t.missing[i]))
        if t.feature[i] >= 0:
            a = walk(int(t.left[i]))
            b = walk(int(t.left[i]) + 1)
            cl[k], cr[k] = a, b
        return k

    walk(root)
    s = np.array(sp)
    miss = None if t.missing is None else np.array(ms, dtype=np.uint8)
    return np.array(cl), np.array(cr), np.array(ft), s, s, miss


def _layout(features: tuple[str, ...], trees: list[_Tree], fill: np.ndarray, *, mean: bool) -> Trees:
    """Flatten trees breadth-first so that the two children of a node are adjacent."""
    if len(features) > 127:
        raise ValueError("at most 127 features (int8 feature index)")
    feat: list[int] = []
    split: list[float] = []
    left: list[int] = []
    miss: list[int] = []
    roots: list[int] = []
    has_missing = any(tr[5] is not None for tr in trees)
    for cl, cr, ft, th, val, ms in trees:
        thr32 = _round_down32(th)
        roots.append(len(feat))
        queue = [(0, len(feat))]
        feat.append(0)
        split.append(0.0)
        left.append(-1)
        miss.append(0)
        while queue:
            node, pos = queue.pop(0)
            if cl[node] < 0:  # leaf
                feat[pos], split[pos], left[pos] = -1, float(np.float32(val[node])), -1
                continue
            feat[pos], split[pos] = int(ft[node]), float(thr32[node])
            miss[pos] = 0 if ms is None else int(ms[node])
            left[pos] = len(feat)
            for child in (int(cl[node]), int(cr[node])):
                queue.append((child, len(feat)))
                feat.append(0)
                split.append(0.0)
                left.append(-1)
                miss.append(0)
    return Trees(
        features,
        np.asarray(feat, dtype=np.int16),
        np.asarray(split, dtype=np.float32),
        np.asarray(left, dtype=np.int64),
        np.asarray(roots, dtype=np.int64),
        fill,
        np.asarray(miss, dtype=np.uint8) if has_missing else None,
        mean,
    )


def _index_bytes(n_nodes: int) -> int:
    return 2 if n_nodes < 32768 else 4


def _float(v: float) -> str:
    v = float(np.float32(v))
    if math.isnan(v):
        return "NAN"
    if math.isinf(v):
        return "INFINITY" if v > 0 else "-INFINITY"
    return f"{v:.9g}f" if ("e" in f"{v:.9g}" or "." in f"{v:.9g}") else f"{v:.9g}.0f"


def _floats(a: np.ndarray) -> str:
    return ", ".join(_float(v) for v in np.asarray(a, dtype=float))


def _ints(a: np.ndarray) -> str:
    return ", ".join(str(int(v)) for v in np.asarray(a))


__all__ = [
    "FEATURES",
    "HISTORY",
    "CycleNet",
    "Footprint",
    "Linear",
    "Model",
    "SparseTSF",
    "Trees",
    "block_totals",
    "causal_fill",
    "day_ahead_features",
    "footprint",
    "to_c",
]
