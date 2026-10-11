"""Global LightGBM, the benchmark's tree model (`02_referencias.py`), ported to the library.

One model for all the series (the series is a categorical feature), retrained at each fold. Features, all
known at 00:00 of the forecast day:

- calendar: hour, day of week, day of year (sine and cosine), series code;
- lags of the series by whole days, from the RAW values (a gap stays NaN, LightGBM handles it; no
  interpolation): same hour 1, 2 and 7 days before, their 7-day mean, yesterday's total and the mean of the
  last 7 totals (a day's total needs 20 of its 24 hours);
- regimes B and C: the covariates at the target hour and, with `clear_sky`, the clear-sky persistence
  (yesterday's clear-sky index x today's clear sky).

The hyperparameters, the column order, the series codes and the order of the training rows are the
benchmark's: LightGBM subsamples rows and columns, so any of them changes the forecast.
`tests/test_forecast_parity.py` checks the result against the saved benchmark forecasts.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from ..contracts import EnergySeries
from ..protocol import H, Regime, Window
from .base import ModelCard

CALENDAR = ["h", "dow", "doy_sin", "doy_cos", "serie_cod"]
LAGS = ["y_d1", "y_d2", "y_d7", "y_media7", "tot_d1", "tot_media7"]
PARAMS: dict[str, Any] = {
    "n_estimators": 600,
    "learning_rate": 0.03,
    "num_leaves": 63,
    "min_child_samples": 40,
    "subsample": 0.8,
    "subsample_freq": 1,
    "colsample_bytree": 0.8,
    "random_state": 42,
    "verbose": -1,
}


class LightGBM:
    """`covariates`: columns of the covariate frame used at the target hour (regimes B and C), in this order.
    `clear_sky`: the covariate holding the clear-sky irradiance, to add the clear-sky persistence feature."""

    def __init__(
        self,
        covariates: list[str] | None = None,
        *,
        clear_sky: str | None = None,
        params: dict[str, Any] | None = None,
        name: str = "LightGBM",
    ) -> None:
        self.covariates = list(covariates or [])
        self.clear_sky = clear_sky
        self.params = {**PARAMS, **(params or {})}
        uses_weather = bool(self.covariates or clear_sky)
        self.card = ModelCard(
            name=name,
            family="tree",
            license="MIT",
            device="cpu",
            sends_data=False,
            regimes=(Regime.KNOWN_WEATHER, Regime.REAL_FORECAST) if uses_weather else (Regime.HISTORY,),
            trains=True,
            source="Ke et al. (2017); features of the prosumer v2 benchmark",
        )
        self.columns = (
            CALENDAR + LAGS + (["persist_ceu_claro"] if clear_sky else []) + [c for c in self.covariates]
        )
        self._model: Any = None
        self._codes: dict[str, int] = {}

    # ------------------------------------------------------------------ interface
    def fit(self, series: EnergySeries, cutoff: pd.Timestamp, covariates: pd.DataFrame | None = None) -> None:
        import lightgbm as lgb

        train = self._training_table(series, cutoff, covariates)
        self._model = lgb.LGBMRegressor(**self.params)
        self._model.fit(train[self.columns], train["y"], categorical_feature=["serie_cod"])

    def predict(self, windows: list[Window]) -> np.ndarray:
        if self._model is None:
            raise RuntimeError("fit before predict")
        x = self._design(windows)
        return np.asarray(self._model.predict(x[self.columns]), dtype=float).reshape(len(windows), H)

    # ------------------------------------------------------------------ tables
    def _training_table(
        self, series: EnergySeries, cutoff: pd.Timestamp, covariates: pd.DataFrame | None
    ) -> pd.DataFrame:
        self._codes = {u: k for k, u in enumerate(natural_order(series.series))}
        long = _long(series.frame, covariates, self._needed())
        table = pd.concat(
            [self._features(g, uid) for uid, g in _in_order(long, self._codes)], ignore_index=True
        )
        return table[(table["dia"] < cutoff.normalize()) & table["y"].notna()]

    def _design(self, windows: list[Window]) -> pd.DataFrame:
        """The feature rows of the windows' target hours, window by window, hour by hour."""
        rows = []
        for w in windows:
            if len(w.timestamps) != H:
                raise NotImplementedError("LightGBM forecasts whole days (issue_hour=0)")
            hist_ds = pd.date_range(end=w.day - pd.Timedelta(hours=1), periods=len(w.history), freq="h")
            raw = np.where(_valid(w), w.history, np.nan)
            g = pd.DataFrame({"ds": hist_ds.append(w.timestamps), "y": np.r_[raw, np.full(H, np.nan)]})
            for c in self._needed():
                past = w.past_covariates.get(c)
                fut = w.future_covariates.get(c)
                if past is None or fut is None:
                    raise ValueError(f"window without covariate {c!r}: pass covariates to DayAhead")
                g[c] = np.r_[past, fut]
            t = self._features(g, w.unique_id)
            rows.append(t[t["dia"] == w.day])
        return pd.concat(rows, ignore_index=True)

    # ------------------------------------------------------------------ features
    def _needed(self) -> list[str]:
        return list(dict.fromkeys(([self.clear_sky] if self.clear_sky else []) + self.covariates))

    def _features(self, g: pd.DataFrame, uid: str) -> pd.DataFrame:
        """One row per (day, hour) of one series: what is known at 00:00 of the day. Port of
        `02_referencias.tabela_features`."""
        Y = _matrix(g, "y")
        f: dict[str, pd.DataFrame] = {f"y_d{lag}": Y.shift(lag) for lag in (1, 2, 7)}
        acc = Y.shift(1)
        for i in range(2, 8):  # same order of additions as the benchmark's sum(): bit-identical
            acc = acc + Y.shift(i)
        f["y_media7"] = acc / 7
        tot = Y.sum(axis=1, min_count=20)
        f["tot_d1"] = _per_day(tot.shift(1), Y)
        f["tot_media7"] = _per_day(tot.shift(1).rolling(7, min_periods=5).mean(), Y)
        X = {c: _matrix(g, c) for c in self._needed()}
        if self.clear_sky:
            cs = X[self.clear_sky]
            k_yesterday = (tot.shift(1) / cs.sum(axis=1).shift(1)).replace([np.inf, -np.inf], np.nan)
            f["persist_ceu_claro"] = cs.mul(k_yesterday, axis=0)
        for c in self.covariates:
            f[c] = X[c]
        # stack, not melt: the row order (day, hour) is the benchmark's, and LightGBM's bagging depends on it
        long = pd.concat({n: m.stack(future_stack=True) for n, m in f.items()}, axis=1)  # noqa: PD013
        long["y"] = Y.stack(future_stack=True)  # noqa: PD013
        long.index.names = ["dia", "h"]
        t = long.reset_index()
        t["unique_id"], t["serie_cod"] = uid, self._codes.get(uid, -1)
        t["dow"] = t["dia"].dt.dayofweek
        doy = t["dia"].dt.dayofyear
        t["doy_sin"], t["doy_cos"] = np.sin(2 * np.pi * doy / 365.25), np.cos(2 * np.pi * doy / 365.25)
        return t


class LightGBMQuantile(LightGBM):
    """One LightGBM per quantile level (pinball loss), same features and protocol: the band source of pilot
    F2(c). Calibrated in regime A on the houses' consumption and on the plants (80% band covered 0.77 of the
    hours); too narrow on the houses' PV (0.65) and in regime C (0.74): read the coverage before trusting it,
    or recalibrate with `postprocessing.conformal_quantiles` (calibrated in both, as `analyze` does).

    `predict` gives the 0.5 level (the median, a point forecast in its own right, not the mean LightGBM's).
    """

    def __init__(
        self,
        covariates: list[str] | None = None,
        *,
        levels: tuple[float, ...] = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9),
        clear_sky: str | None = None,
        params: dict[str, Any] | None = None,
        name: str = "LightGBM-quantile",
    ) -> None:
        super().__init__(covariates, clear_sky=clear_sky, params=params, name=name)
        if 0.5 not in levels or sorted(levels) != list(levels):
            raise ValueError("levels must be increasing and include 0.5")
        self.levels = tuple(levels)
        self._models: list[Any] = []

    def fit(self, series: EnergySeries, cutoff: pd.Timestamp, covariates: pd.DataFrame | None = None) -> None:
        import lightgbm as lgb

        train = self._training_table(series, cutoff, covariates)
        self._models = []
        for a in self.levels:
            m = lgb.LGBMRegressor(objective="quantile", alpha=a, **self.params)
            m.fit(train[self.columns], train["y"], categorical_feature=["serie_cod"])
            self._models.append(m)
        self._model = self._models[self.levels.index(0.5)]

    def predict_quantiles(self, windows: list[Window]) -> np.ndarray:
        """Shape (windows, levels, 24), in the order of `levels`; crossed quantiles are left as they come."""
        if not self._models:
            raise RuntimeError("fit before predict")
        x = self._design(windows)[self.columns]
        q = np.stack([np.asarray(m.predict(x), dtype=float) for m in self._models])  # (levels, rows)
        return q.reshape(len(self.levels), len(windows), H).transpose(1, 0, 2)


# ---------------------------------------------------------------------- helpers
def natural_order(ids: list[str]) -> list[str]:
    """H2 before H10: the benchmark's series codes follow the number in the id, then the id."""

    def key(u: str) -> tuple[float, str]:
        m = re.search(r"H(\d+)", u)
        return (float(m.group(1)) if m else 0.0, u)

    return sorted(ids, key=key)


def _in_order(long: pd.DataFrame, codes: dict[str, int]) -> list[tuple[str, pd.DataFrame]]:
    groups = {str(u): g for u, g in long.groupby("unique_id", sort=False)}
    return [(u, groups[u]) for u in sorted(groups, key=lambda u: codes[u])]


def _long(frame: pd.DataFrame, covariates: pd.DataFrame | None, needed: list[str]) -> pd.DataFrame:
    x = frame.assign(y=frame["y"].where(frame["valid"]))[["unique_id", "ds", "y"]]
    if needed:
        if covariates is None:
            raise ValueError(f"LightGBM needs the covariates {needed}")
        x = x.merge(covariates[["unique_id", "ds", *needed]], on=["unique_id", "ds"], how="left")
    return x


def _valid(w: Window) -> np.ndarray:
    return np.ones(len(w.history), bool) if w.history_valid is None else w.history_valid


def _matrix(g: pd.DataFrame, col: str) -> pd.DataFrame:
    """day x hour (24 columns), every calendar day between the first and the last."""
    m = g.assign(dia=g["ds"].dt.normalize(), h=g["ds"].dt.hour).pivot_table(
        index="dia", columns="h", values=col, dropna=False
    )
    m = m.reindex(columns=range(H))
    return m.reindex(pd.date_range(m.index.min(), m.index.max(), freq="D"))


def _per_day(v: pd.Series, like: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(np.repeat(v.to_numpy()[:, None], H, 1), index=like.index, columns=like.columns)
