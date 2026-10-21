"""Forecast metrics and significance tests.

Ported from `experimentos/testes_previsao/scripts/05_avalia.py` (v2 protocol). Deterministic solar
verification convention of Yang et al. (2020): errors normalised by the mean of the actual values over
the evaluated hours, and skill against a declared reference.

Two decisions came from the results and are built in on purpose:

- **Bias next to error.** Foundation models underestimate consumption by ~20% because they forecast the
  median; a good RMSE was hiding it. `metrics()` always returns MBE.
- **Common support.** Model, target and reference are paired on the SAME finite hours before any
  computation. Without that, two models evaluated on different hours look comparable and are not.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pandas as pd

KEYS = ["unique_id", "ds"]


def align(
    forecast: pd.DataFrame, actual: pd.DataFrame, reference: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pair target, model and reference on the hours where all three are finite.

    Returns (model, reference) with the same index and order, ready for a paired comparison. Raises if
    nothing is left: silently comparing empty sets is worse than failing.
    """
    r = reference[[*KEYS, "yhat"]].rename(columns={"yhat": "yhat_ref"})
    m = forecast.merge(actual, on=KEYS, validate="one_to_one").merge(r, on=KEYS, validate="one_to_one")
    m = m.loc[m[["y", "yhat", "yhat_ref"]].abs().lt(np.inf).all(axis=1)]  # finite: NaN and inf drop out
    m = m.sort_values(KEYS, kind="stable").reset_index(drop=True)
    if m.empty:
        raise ValueError("No finite hours in common between model, target and reference")
    ref = m[[*KEYS, "y", "yhat_ref"]].rename(columns={"yhat_ref": "yhat"})
    return m.drop(columns="yhat_ref"), ref


def metrics(df: pd.DataFrame) -> dict[str, float]:
    """nMAE, nRMSE, MBE, RMSE and R2, hourly and on daily energy.

    `df` needs the columns `y`, `yhat`, `unique_id` and `ds`, already restricted to the evaluated hours.
    """
    e = df["yhat"] - df["y"]
    mu = df["y"].mean()
    if not np.isfinite(mu) or mu == 0:
        raise ValueError("Mean of the actual values is zero or not finite: normalised metrics make no sense")
    day = df.assign(day=df["ds"].dt.normalize()).groupby(["unique_id", "day"])[["y", "yhat"]].sum()
    ed = day["yhat"] - day["y"]
    return {
        "nMAE": float(e.abs().mean() / mu),
        "nRMSE": float(np.sqrt((e**2).mean()) / mu),
        "MBE": float(e.mean() / mu),
        "RMSE": float(np.sqrt((e**2).mean())),
        "nMAE_daily": float(ed.abs().mean() / day["y"].mean()),
        "R2": float(1 - (e**2).sum() / ((df["y"] - mu) ** 2).sum()),
        "R2_daily": _r2(ed, day["y"]),
    }


def _r2(error: pd.Series, actual: pd.Series) -> float:
    """R2 that returns NaN when the actual values do not vary, instead of dividing by zero.

    This really happens with a single test day (or identical daily totals): R2 is then undefined, and an
    explicit NaN is more honest than a -inf coming from a swallowed warning.
    """
    var = float(((actual - actual.mean()) ** 2).sum())
    if var == 0.0:
        return float("nan")
    return float(1 - (error**2).sum() / var)


def skill(df: pd.DataFrame, reference: pd.DataFrame) -> float:
    """1 - RMSE/RMSE_reference. Zero = same as the reference; negative = worse than it."""
    e = df["yhat"].to_numpy() - df["y"].to_numpy()
    er = reference["yhat"].to_numpy() - reference["y"].to_numpy()
    base = np.sqrt((er**2).mean())
    if base == 0:
        raise ValueError("Reference with zero error: skill would be infinite")
    return float(1 - np.sqrt((e**2).mean()) / base)


def skill_ci95(
    df: pd.DataFrame, reference: pd.DataFrame, *, resamples: int = 1000, seed: int = 42
) -> tuple[float, float]:
    """95% CI of the skill, resampling WHOLE DAYS, not hours.

    Resampling hours would treat hours of the same day as independent, which they are not (cloudiness
    and error last the whole day). The day bootstrap is what gives an honest CI.
    """
    rng = np.random.default_rng(seed)
    k = df["unique_id"].astype(str) + "|" + df["ds"].dt.normalize().astype(str)
    se = ((df["yhat"] - df["y"]) ** 2).groupby(k.values).agg(["sum", "count"])
    sr = (
        pd.Series(((reference["yhat"].to_numpy() - df["y"].to_numpy()) ** 2), index=df.index)
        .groupby(k.values)
        .sum()
    )
    n = len(se)
    if n < 2:
        raise ValueError("Fewer than two days: cannot estimate a CI by day bootstrap")
    idx = rng.integers(0, n, size=(resamples, n))
    a, c, r = se["sum"].to_numpy(), se["count"].to_numpy(), sr.to_numpy()
    # a resample whose reference error is zero (e.g. test days that are all zero) has no skill: NaN, quietly
    with np.errstate(divide="ignore", invalid="ignore"):
        s = 1 - np.sqrt(a[idx].sum(1) / c[idx].sum(1)) / np.sqrt(r[idx].sum(1) / c[idx].sum(1))
        lo, hi = np.percentile(s, [2.5, 97.5])
    return float(lo), float(hi)


def diebold_mariano(e1: pd.Series, e2: pd.Series) -> tuple[float, float, float]:
    """Daily Diebold-Mariano between two models. Returns (relative extra loss, statistic, p).

    `e1` and `e2` are squared errors indexed by (unique_id, ds). Mean loss per day, Newey-West variance
    with lag floor(T^(1/3)), Harvey-Leybourne-Newbold correction and Student's t with T-1 degrees of
    freedom. A positive difference = the first one errs more.

    Not rejecting does NOT prove equivalence, and the "best" is usually picked on the same test: this is
    a reading filter, not a superiority test.
    """
    j = pd.concat([e1.rename("a"), e2.rename("b")], axis=1, join="inner").dropna()
    if j.empty:
        raise ValueError("No hours in common between the two models")
    days = pd.DatetimeIndex(j.index.get_level_values("ds")).normalize()
    d = (j["a"] - j["b"]).groupby(days).mean().sort_index().to_numpy()
    T = len(d)
    if T < 10 or np.allclose(d, 0):
        return 0.0, 0.0, 1.0
    db = float(d.mean())
    x = d - db
    L = int(np.floor(T ** (1 / 3)))
    # Newey-West: long-run variance of the loss difference, with lag floor(T^(1/3)).
    v = float(x @ x / T + 2 * sum((1 - lag / (L + 1)) * (x[lag:] @ x[:-lag]) / T for lag in range(1, L + 1)))
    stat = db / np.sqrt(max(v, 1e-30) / T) * np.sqrt((T - 1) / T)
    # here, not at the top: the benchmark's environments import the protocol without scipy
    from scipy import stats

    return float(db / j["b"].mean()), float(stat), float(2 * stats.t.sf(abs(stat), T - 1))


def holm(p: list[float] | np.ndarray) -> np.ndarray:
    """Holm-adjusted p-values, in input order. Without it, comparing N models inflates false positives."""
    p = np.asarray(p, dtype=float)
    if p.size == 0:
        return p
    o = np.argsort(p)
    m = len(p)
    adj = np.maximum.accumulate((m - np.arange(m)) * p[o]).clip(max=1.0)
    out = np.empty(m)
    out[o] = adj
    return out


def ranking(skills: dict[str, float], errors: dict[str, pd.Series], *, alpha: float = 0.05) -> pd.DataFrame:
    """Rank models of ONE comparison (same case, same regime, same hours) and flag who ties with the best.

    `skills`: model -> skill; `errors`: model -> squared errors (`squared_errors`). The best is the highest
    skill; every other model gets a daily Diebold-Mariano against it, Holm-adjusted over the family, and ties
    with the best when the adjusted p >= `alpha`. Rows keep the input order; `position` is 1 for the best.

    This is the benchmark's reading rule ("how many tie with the best"): the best is chosen on the same test,
    so a tie is not a proof of equivalence, and "choosing the best model" is not what the library recommends
    (the pilot of 2026-10-09 found that picking the previous fold's winner made every case worse).
    """
    if not skills:
        raise ValueError("No models to rank")
    order = pd.Series(skills, dtype=float)
    best = str(order.sort_values(ascending=False).index[0])
    rows = []
    for model, sk in skills.items():
        row = {"model": model, "skill": float(sk), "position": int((order > sk).sum()) + 1, "best": best}
        if model != best:
            row["extra_loss"], row["dm"], row["p"] = diebold_mariano(errors[model], errors[best])
        rows.append(row)
    out = pd.DataFrame(rows)
    others = out["model"] != best
    out["p_holm"] = np.nan
    if others.any():
        out.loc[others, "p_holm"] = holm(out.loc[others, "p"].to_numpy())
    out["ties_with_best"] = (~others) | (out["p_holm"] >= alpha)
    return out


def ties_with_best(
    skills: dict[str, float], errors: dict[str, pd.Series], *, alpha: float = 0.05
) -> list[str]:
    """Models statistically tied with the best (the best included), best first, by skill."""
    r = ranking(skills, errors, alpha=alpha)
    return r[r["ties_with_best"]].sort_values("skill", ascending=False)["model"].tolist()


def squared_errors(df: pd.DataFrame) -> pd.Series:
    """Squared errors indexed by (unique_id, ds), in the shape `diebold_mariano` expects."""
    return pd.Series(
        ((df["yhat"] - df["y"]) ** 2).to_numpy(),
        index=pd.MultiIndex.from_arrays([df["unique_id"], df["ds"]], names=KEYS),
    )


# ---------------------------------------------------------------------- bands (quantile forecasts)
# Pilot F2(c): a band such as "tomorrow between 8 and 12 kWh" is only useful if it is calibrated. Two numbers
# decide: coverage (how often the actual value falls inside the central interval, against its nominal level)
# and CRPS (sharpness and calibration together, lower is better), against a naive causal band.


def quantile_loss(y: np.ndarray, q: np.ndarray, level: float) -> np.ndarray:
    """Pinball loss of the quantile `q` at `level` (0-1), element by element."""
    e = np.asarray(y, float) - np.asarray(q, float)
    return np.maximum(level * e, (level - 1) * e)


def band_scores(y: np.ndarray, quantiles: np.ndarray, levels: list[float] | np.ndarray) -> dict[str, float]:
    """Coverage, width and CRPS of a quantile forecast.

    `quantiles`: shape (n, len(levels)), levels increasing. Crossed quantiles (q20 < q10) are sorted row by
    row first, as is done in practice. CRPS is approximated by 2 x the mean pinball loss over the levels. For
    each symmetric pair (level, 1 - level) with level < 0.5 the result has `coverage_<k>` and `width_<k>`,
    where k is the nominal percentage of the central interval (0.1 and 0.9 -> `coverage_80`).
    """
    lv = np.asarray(levels, float)
    if np.any(np.diff(lv) <= 0) or lv.min() <= 0 or lv.max() >= 1:
        raise ValueError("levels must be strictly increasing and inside (0, 1)")
    y = np.asarray(y, float)
    m = np.sort(np.asarray(quantiles, float), axis=1)
    if m.shape != (len(y), len(lv)):
        raise ValueError(f"quantiles must have shape ({len(y)}, {len(lv)}), not {m.shape}")
    ok = np.isfinite(y) & np.isfinite(m).all(axis=1)
    if not ok.any():
        raise ValueError("No finite rows to score")
    y, m = y[ok], m[ok]
    out = {"CRPS": float(2 * np.mean([quantile_loss(y, m[:, k], a).mean() for k, a in enumerate(lv)]))}
    for k, a in enumerate(lv):
        j = np.flatnonzero(np.isclose(lv, 1 - a))
        if a < 0.5 and j.size:
            lo, hi = m[:, k], m[:, j[0]]
            pct = round((1 - 2 * a) * 100)
            out[f"coverage_{pct}"] = float(np.mean((y >= lo) & (y <= hi)))
            out[f"width_{pct}"] = float(np.mean(hi - lo))
    out["n"] = float(len(y))
    return out


# ---------------------------------------------------------------------- which hours count
def evaluated_mask(
    frame: pd.DataFrame,
    how: str = "all",
    *,
    sun_column: str = "poa_ceu_claro",
    profile: pd.DataFrame | None = None,
    threshold: float = 0.01,
) -> pd.Series:
    """Boolean mask of the hours that enter the metrics. Every model of a comparison must use the same mask.

    - "all": every hour (consumption);
    - "sun": hours where the clear-sky irradiance in `sun_column` is positive (generation with a known site);
    - "profile": hours of the day whose mean of `y` over `profile` exceeds `threshold` x its maximum
      (generation without geometry, e.g. the houses). Night hours are ~0 for every model and only inflate
      the skill.

    `profile` is the frame the hourly profile comes from; default: `frame` itself. The v2 benchmark used the
    test period (same mask for every model, never a model input); for new work prefer the training period, so
    the mask is known before the test.
    """
    if how == "all":
        return pd.Series(True, index=frame.index)
    if how == "sun":
        return (frame[sun_column] > 0).astype(bool)
    if how == "profile":
        src = frame if profile is None else profile
        mean_by_hour = src.groupby(src["ds"].dt.hour)["y"].mean()
        return (
            frame["ds"].dt.hour.map(mean_by_hour > threshold * mean_by_hour.max()).fillna(False).astype(bool)
        )
    raise ValueError(f"how must be 'all', 'sun' or 'profile', not {how!r}")


# ---------------------------------------------------------------------- several resolutions
# Why: a house's hourly consumption is largely unpredictable (R2 0.37 in the benchmark), but the daily
# total is not (0.58), and the user's decision is rarely hourly: the bill is monthly, the battery looks at
# the evening peak, the tariff is by block. Each use picks the resolution of its decision. A level is a
# function that maps the timestamp (`ds`) to the block key; NaN removes the hour from the level (e.g.
# outside the peak window).
Level = Callable[[pd.Series], pd.Series] | None


def daily(ds: pd.Series) -> pd.Series:
    """One block per day (the day's energy)."""
    return ds.dt.strftime("%Y-%m-%d")


def by_blocks(blocks: dict[int, str]) -> Callable[[pd.Series], pd.Series]:
    """Tariff blocks: `blocks` maps the hour (0-23) to the block name. Each day has its own blocks."""
    missing = set(range(24)) - set(blocks)
    if missing:
        raise ValueError(f"Blocks missing hours {sorted(missing)}: every hour needs a block")

    def f(ds: pd.Series) -> pd.Series:
        return ds.dt.strftime("%Y-%m-%d") + "_" + ds.dt.hour.map(blocks)

    return f


def hour_window(hours: range | list[int]) -> Callable[[pd.Series], pd.Series]:
    """Only the hours in the window, summed per day (e.g. the evening peak). Other hours leave the level."""
    inside = set(hours)

    def f(ds: pd.Series) -> pd.Series:
        return daily(ds).where(ds.dt.hour.isin(inside))

    return f


# Default: day/night tariff as in Ireland (day 08-23 h). For the Brazilian tarifa branca, pass by_blocks
# with the distributor's peak, intermediate and off-peak hours.
DAY_NIGHT_BLOCKS: dict[int, str] = {h: ("day" if 8 <= h < 23 else "night") for h in range(24)}
DEFAULT_LEVELS: dict[str, Level] = {
    "hour": None,
    "day_night": by_blocks(DAY_NIGHT_BLOCKS),
    "peak_17_21": hour_window(range(17, 21)),
    "day": daily,
}


def aggregate(df: pd.DataFrame, level: Level) -> pd.DataFrame:
    """Sum, per series and block, the numeric forecast columns (`y`, `yhat`, and `yhat_ref` if present)."""
    if level is None:
        return df
    cols = [c for c in ("y", "yhat", "yhat_ref") if c in df.columns]
    key = level(df["ds"])
    x = df.assign(_block=key).dropna(subset=["_block"])
    return x.groupby(["unique_id", "_block"], sort=True)[cols].sum().reset_index()


def by_resolution(
    forecast: pd.DataFrame, reference: pd.DataFrame, levels: dict[str, Level] | None = None
) -> pd.DataFrame:
    """Skill, R2, nRMSE and bias at each level. Inputs: the output of `align` (same hours, same order).

    The skill is against the reference summed at the SAME level: per day, "same as yesterday" becomes
    "yesterday's total". That is why skill drops when aggregating even as relative error drops: the
    reference improves too.
    """
    levels = DEFAULT_LEVELS if levels is None else levels
    base = forecast[[*KEYS, "y", "yhat"]].assign(yhat_ref=reference["yhat"].to_numpy())
    rows = []
    for name, level in levels.items():
        g = aggregate(base, level)
        e, er = g["yhat"] - g["y"], g["yhat_ref"] - g["y"]
        mu = float(g["y"].mean())
        rmse, rmse_ref = float(np.sqrt((e**2).mean())), float(np.sqrt((er**2).mean()))
        rows.append(
            {
                "level": name,
                "blocks": len(g),
                "skill": 1 - rmse / rmse_ref if rmse_ref > 0 else float("nan"),
                "R2": _r2(e, g["y"]),
                "R2_reference": _r2(er, g["y"]),
                "nRMSE": rmse / mu if mu else float("nan"),
                "MBE": float(e.mean()) / mu if mu else float("nan"),
            }
        )
    return pd.DataFrame(rows)
