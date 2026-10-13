"""Tariffs as data, the monthly bill of a household with or without PV, and when to run a flexible load.

Three schemes for the energy a PV system sends to the grid (`Scheme`):

- `net_metering`: exported kWh become kWh credits that offset imported kWh, carried to later months (and
  optionally expiring after `credit_months`). Within a month, export first offsets import of the same tariff
  block, then the other blocks from the most expensive down; credits are used oldest first.
- `net_billing`: imports are paid at the import price, exports are paid at the export price; a month whose
  exports are worth more than its imports has a negative energy cost (money owed to the household).
- `self_consumption`: exports are worth nothing; only the PV energy used on site lowers the bill.

**Hourly netting.** Import and export are computed hour by hour from the consumption and the generation of
the same site: import = max(consumption - generation, 0), export = max(generation - consumption, 0). A real
meter nets instant by instant, so within an hour that has both a kettle and a cloud the real import and
export are both larger than the hourly figures (they cancel inside the hour here). With hourly data nothing
better is possible; the error grows with the mismatch between load and PV inside the hour.

The month is the calendar month in the series' time zone, not the meter's reading cycle (a distributor's
cycle can start on any day of the month).

Hours where the consumption or the generation is not valid are left out of every sum (never filled with
zero); `coverage` in the monthly table says how much of each month was counted.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Literal

import numpy as np
import pandas as pd

from ..contracts import EnergySeries
from ..outlook import Outlook, _plain, _table

Scheme = Literal["net_metering", "net_billing", "self_consumption"]
SCHEMES: tuple[str, ...] = ("net_metering", "net_billing", "self_consumption")
# hour of day -> block name, or -> {block: share of the hour} when a block starts inside the hour
Blocks = Mapping[int, str | Mapping[str, float]]
Holidays = Callable[[pd.DatetimeIndex], np.ndarray] | Collection[date] | None


@dataclass(frozen=True)
class Tariff:
    """A tariff as data: named blocks by hour of day (weekdays, and optionally weekends and holidays), an
    import price per kWh for each block, an export price, a fixed charge per month and the currency.

    `weekday` (and `weekend`) map each hour 0-23 to a block name, the convention of `metrics.by_blocks` and
    `embedded.block_totals`; an hour may instead map to `{block: share}` when a block boundary falls inside
    it (the Brazilian tarifa branca starts its peak at 17:30 in some distributors): the hour's energy is then
    split in those shares, as if it were spread evenly within the hour. `holidays` are days billed with the
    `weekend` blocks: a set of dates or a function of the hourly index returning a boolean array.
    `export_price` is one price or one per block. A flat tariff is a single block (`Tariff.flat`).
    """

    prices: Mapping[str, float]
    weekday: Blocks
    weekend: Blocks | None = None
    export_price: float | Mapping[str, float] = 0.0
    fixed: float = 0.0
    currency: str = "EUR"
    holidays: Holidays = None
    name: str = ""

    def __post_init__(self) -> None:
        for label, blocks in (("weekday", self.weekday), ("weekend", self.weekend)):
            if blocks is None:
                continue
            missing = set(range(24)) - set(blocks)
            if missing:
                raise ValueError(f"{label} blocks miss hours {sorted(missing)}: every hour needs a block")
            for h, b in blocks.items():
                shares = {b: 1.0} if isinstance(b, str) else dict(b)
                unknown = set(shares) - set(self.prices)
                if unknown:
                    raise ValueError(f"Hour {h}: block(s) {sorted(unknown)} have no price")
                if not np.isclose(sum(shares.values()), 1.0):
                    raise ValueError(f"Hour {h}: the shares of the blocks must add up to 1")
        if isinstance(self.export_price, Mapping):
            unknown = set(self.export_price) - set(self.prices)
            if unknown:
                raise ValueError(f"Export prices for unknown blocks {sorted(unknown)}")

    # ------------------------------------------------------------------ construction
    @classmethod
    def flat(
        cls,
        price: float,
        *,
        export_price: float = 0.0,
        fixed: float = 0.0,
        currency: str = "EUR",
        name: str = "",
    ) -> Tariff:
        """One price for every hour."""
        return cls(
            {"flat": price}, dict.fromkeys(range(24), "flat"), None, export_price, fixed, currency, None, name
        )

    # ------------------------------------------------------------------ hour by hour
    @property
    def blocks(self) -> list[str]:
        """Block names, in the order of `prices`."""
        return list(self.prices)

    def shares(self, ds: pd.DatetimeIndex | pd.Series) -> np.ndarray:
        """Share of each hour that falls in each block: (hours, blocks), rows add up to 1."""
        t = pd.DatetimeIndex(ds)
        names = self.blocks
        col = {b: j for j, b in enumerate(names)}

        def table(blocks: Blocks) -> np.ndarray:
            m = np.zeros((24, len(names)))
            for h, b in blocks.items():
                for name, s in ({b: 1.0} if isinstance(b, str) else b).items():
                    m[h, col[name]] += s
            return m

        out = table(self.weekday)[t.hour]
        if self.weekend is not None:
            off = self.off_days(t)
            out[off] = table(self.weekend)[t.hour[off]]
        return np.asarray(out)

    def off_days(self, ds: pd.DatetimeIndex | pd.Series) -> np.ndarray:
        """True for hours of Saturdays, Sundays and holidays (billed with the `weekend` blocks)."""
        t = pd.DatetimeIndex(ds)
        off = np.asarray(t.dayofweek >= 5)
        if self.holidays is None:
            return off
        if callable(self.holidays):
            return off | np.asarray(self.holidays(t), dtype=bool)
        days = set(self.holidays)
        return off | np.array([d in days for d in t.date])

    def price(self, ds: pd.DatetimeIndex | pd.Series) -> np.ndarray:
        """Import price of each hour (per kWh): the block prices weighted by the hour's shares."""
        return self.shares(ds) @ np.array([self.prices[b] for b in self.blocks], dtype=float)

    def export(self, ds: pd.DatetimeIndex | pd.Series) -> np.ndarray:
        """Export price of each hour (per kWh)."""
        return self.shares(ds) @ self._export_vector()

    def _export_vector(self) -> np.ndarray:
        e = self.export_price
        if isinstance(e, Mapping):
            return np.array([float(e.get(b, 0.0)) for b in self.blocks])
        return np.full(len(self.blocks), float(e))


# ---------------------------------------------------------------------- flows
def flows(consumption: EnergySeries, generation: EnergySeries | None = None) -> pd.DataFrame:
    """Hourly energy flows of each site: `unique_id, ds, consumption, generation, self_consumption,
    grid_import, export, valid, generation_missing` (kWh). Hourly netting (see the module docstring).

    `consumption` is what the household used (behind the meter), `generation` what its PV produced, both
    hourly. Pairing: by `unique_id`; when each has exactly one series they are paired whatever their names.
    A site without a generation series has zero generation. An hour is valid only when both are: a site
    WITH a generation series but no generation row at an hour (e.g. the PV series starts after the
    consumption) has unknown generation there, not zero; `generation_missing` flags those hours. If the PV
    was simply not installed yet, pass a generation series with zeros for that period.
    """
    c = _hourly_kwh(consumption, "consumption")
    out = c.rename(columns={"y": "consumption"})
    if generation is None:
        out["generation"] = 0.0
        out["valid"] = out["valid_c"]
        out["generation_missing"] = False
    else:
        g = _hourly_kwh(generation, "generation")
        if _single(c["unique_id"]) and _single(g["unique_id"]):
            g = g.assign(unique_id=c["unique_id"].iloc[0])
        unknown = set(g["unique_id"]) - set(c["unique_id"])
        if unknown:
            raise ValueError(f"Generation series without a consumption series: {sorted(unknown)}")
        g = g.rename(columns={"y": "generation", "valid_c": "valid_g"})
        g["ds"] = g["ds"].dt.tz_convert(consumption.tz)
        out = out.merge(g, on=["unique_id", "ds"], how="left")
        has_gen = out["unique_id"].isin(set(g["unique_id"]))
        # a site with a PV series but no row at this hour: unknown generation, not zero
        out["valid"] = out["valid_c"] & np.where(has_gen, out["valid_g"].fillna(False).astype(bool), True)
        out["generation_missing"] = (has_gen & out["valid_g"].isna()).to_numpy()
        out["generation"] = np.where(has_gen, out["generation"], 0.0)
    v = out["valid"].to_numpy(dtype=bool)
    cons = np.where(v, out["consumption"].to_numpy(dtype=float), np.nan)
    gen = np.where(v, out["generation"].to_numpy(dtype=float), np.nan)
    out["consumption"], out["generation"] = cons, gen
    out["self_consumption"] = np.minimum(cons, gen)
    out["grid_import"] = np.clip(cons - gen, 0, None)
    out["export"] = np.clip(gen - cons, 0, None)
    cols = ["unique_id", "ds", "consumption", "generation", "self_consumption", "grid_import", "export"]
    return (
        out[[*cols, "valid", "generation_missing"]]
        .sort_values(["unique_id", "ds"], kind="stable")
        .reset_index(drop=True)
    )


def _hourly_kwh(s: EnergySeries, what: str) -> pd.DataFrame:
    s = s.to_kwh()
    if s.freq != "h":
        raise ValueError(f"The {what} must be hourly, not freq={s.freq!r}; resample first")
    f = s.frame[["unique_id", "ds", "y", "valid"]].rename(columns={"valid": "valid_c"})
    f["valid_c"] = f["valid_c"].astype(bool) & f["y"].notna()
    return f


# ---------------------------------------------------------------------- bill
@dataclass
class Bill:
    """What `bill` returns. `monthly`: one row per site and month (energy flows, credits, money);
    `by_block`: import and export per site, month and tariff block; `hourly`: the flows of `flows`;
    `notes`: what the person should know (hourly netting, missing hours, credits that expired)."""

    monthly: pd.DataFrame
    by_block: pd.DataFrame
    hourly: pd.DataFrame
    scheme: str
    currency: str
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """JSON-friendly version (months as ISO dates)."""

        def records(df: pd.DataFrame) -> list[dict[str, Any]]:
            out = df.copy()
            for c in out.columns:
                if pd.api.types.is_datetime64_any_dtype(out[c]):
                    out[c] = out[c].map(lambda t: t.isoformat())
            return [{str(k): _plain(v) for k, v in r.items()} for r in out.to_dict(orient="records")]

        return {
            "scheme": self.scheme,
            "currency": self.currency,
            "monthly": records(self.monthly),
            "by_block": records(self.by_block),
            "notes": list(self.notes),
        }

    def to_markdown(self) -> str:
        """Readable summary: the monthly table and the notes."""
        m = self.monthly.copy()
        m["month"] = m["month"].dt.strftime("%Y-%m")
        cols = [
            c
            for c in ("unique_id", "month", "grid_import", "export", "compensated", "credit_balance", "total")
            if c in m.columns
        ]
        lines = [f"# Bill ({self.scheme}, {self.currency})", "", _table(m[cols].round(2))]
        if self.notes:
            lines += ["", "## Notes", "", *[f"- {n}" for n in self.notes]]
        return "\n".join(lines) + "\n"


def bill(
    consumption: EnergySeries,
    generation: EnergySeries | None = None,
    *,
    tariff: Tariff,
    scheme: Scheme = "net_metering",
    credit_months: int | None = None,
    initial_credit: float | Mapping[str, float] = 0.0,
) -> Bill:
    """Monthly bill of each site under `tariff` and `scheme` (see the module docstring).

    Monthly columns: `unique_id, month, hours, coverage, consumption, generation, self_consumption,
    grid_import, export, compensated, credit_used, credit_new, credit_expired, credit_balance, energy_cost,
    export_value, fixed, total` (energy in kWh, money in `tariff.currency`). `compensated` is the import
    offset by the month's own export, `credit_used` the import offset by older credits (net metering only).
    `credit_months`: credits expire after that many months (None: never): a credit earned in month m is
    usable through month m + credit_months - 1; `initial_credit`: kWh already banked before the first month
    (one value, or one per site, treated as earned the month before).
    """
    if scheme not in SCHEMES:
        raise ValueError(f"scheme must be one of {SCHEMES}")
    if credit_months is not None and credit_months < 1:
        raise ValueError("credit_months must be >= 1")
    h = flows(consumption, generation)
    sh = tariff.shares(h["ds"])
    names = tariff.blocks
    price = np.array([tariff.prices[b] for b in names], dtype=float)
    export_price = tariff._export_vector()
    h["month"] = h["ds"].dt.tz_localize(None).dt.to_period("M").dt.to_timestamp()
    imp = np.nan_to_num(h["grid_import"].to_numpy())[:, None] * sh
    exp = np.nan_to_num(h["export"].to_numpy())[:, None] * sh
    blk = pd.DataFrame(
        np.hstack([imp, exp]),
        columns=[f"i:{b}" for b in names] + [f"e:{b}" for b in names],
    ).assign(unique_id=h["unique_id"].to_numpy(), month=h["month"].to_numpy())
    per_block = blk.groupby(["unique_id", "month"], sort=True).sum()
    sums = h.groupby(["unique_id", "month"], sort=True).agg(
        hours=("valid", "size"),
        coverage=("valid", "mean"),
        consumption=("consumption", "sum"),
        generation=("generation", "sum"),
        self_consumption=("self_consumption", "sum"),
        grid_import=("grid_import", "sum"),
        export=("export", "sum"),
    )
    notes = [
        "Import and export are netted hour by hour; a real meter nets instant by instant, so within an hour "
        "with both PV and load the real flows are larger than these."
    ]
    rows = []
    order = np.argsort(-price, kind="stable")  # leftover export offsets the dearest blocks first
    for uid in sums.index.get_level_values(0).unique():
        lots: list[tuple[pd.Timestamp, float]] = []  # (month earned, kWh), oldest first
        start = _per(initial_credit, uid)
        months = sums.loc[uid].index
        if start > 0:
            lots.append((months[0] - pd.offsets.MonthBegin(1), start))
        for month in months:
            r = sums.loc[(uid, month)]
            ib = per_block.loc[(uid, month), [f"i:{b}" for b in names]].to_numpy(dtype=float)
            eb = per_block.loc[(uid, month), [f"e:{b}" for b in names]].to_numpy(dtype=float)
            expired = 0.0
            if credit_months is not None:
                limit = month - pd.DateOffset(months=credit_months)
                expired = sum(k for m, k in lots if m <= limit)
                lots = [(m, k) for m, k in lots if m > limit]
            compensated = used = new = 0.0
            if scheme == "net_metering":
                same = np.minimum(ib, eb)
                rest_i, excess = ib - same, float((eb - same).sum())
                compensated = float(same.sum())
                for j in order:  # the month's excess, then the credits, offset the dearest blocks first
                    take = min(rest_i[j], excess)
                    rest_i[j] -= take
                    excess -= take
                    compensated += take
                for j in order:
                    while rest_i[j] > 1e-12 and lots:
                        m0, k0 = lots[0]
                        take = min(rest_i[j], k0)
                        rest_i[j] -= take
                        used += take
                        lots[0] = (m0, k0 - take)
                        if lots[0][1] <= 1e-12:
                            lots.pop(0)
                new = excess
                if new > 0:
                    lots.append((month, new))
                energy_cost = float(rest_i @ price)
                export_value = 0.0
            elif scheme == "net_billing":
                energy_cost = float(ib @ price)
                export_value = float(eb @ export_price)
            else:
                energy_cost, export_value = float(ib @ price), 0.0
            fixed = float(tariff.fixed)
            rows.append(
                {
                    "unique_id": uid,
                    "month": month,
                    **{k: float(r[k]) for k in ("hours", "coverage")},
                    **{
                        k: float(r[k])
                        for k in (
                            "consumption",
                            "generation",
                            "self_consumption",
                            "grid_import",
                            "export",
                        )
                    },
                    "compensated": compensated,
                    "credit_used": used,
                    "credit_new": new,
                    "credit_expired": expired,
                    "credit_balance": float(sum(k for _, k in lots)),
                    "energy_cost": energy_cost,
                    "export_value": export_value,
                    "fixed": fixed,
                    "total": energy_cost - export_value + fixed,
                }
            )
    monthly = pd.DataFrame(rows)
    partial = monthly[monthly["coverage"] < 1.0]
    if len(partial):
        notes.append(
            f"{len(partial)} site-month(s) have missing hours (coverage < 1): their sums cover only the "
            "valid hours, so the bill of those months is too low."
        )
    if monthly["credit_expired"].sum() > 0:
        notes.append(f"{monthly['credit_expired'].sum():.1f} kWh of credits expired unused.")
    if h["generation_missing"].any():
        n = int(h["generation_missing"].sum())
        notes.append(
            f"{n} hour(s) have consumption but no generation row (e.g. the PV series starts later): left "
            "out as unknown. If the PV was not installed yet, pass zeros for that period."
        )
    if scheme == "net_billing" and (monthly["total"] < 0).any():
        notes.append("Some months have a negative total: the exports are worth more than the imports.")
    by_block = _by_block(per_block, names)
    return Bill(
        monthly=monthly,
        by_block=by_block,
        hourly=h.drop(columns="month"),
        scheme=scheme,
        currency=tariff.currency,
        notes=notes,
    )


def _by_block(per_block: pd.DataFrame, names: list[str]) -> pd.DataFrame:
    parts = []
    for b in names:
        p = per_block[[f"i:{b}", f"e:{b}"]].rename(columns={f"i:{b}": "grid_import", f"e:{b}": "export"})
        parts.append(p.reset_index().assign(block=b))
    cols = ["unique_id", "month", "block", "grid_import", "export"]
    return (
        pd.concat(parts, ignore_index=True)[cols]
        .sort_values(["unique_id", "month", "block"])
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------------- flexible loads
def cheapest_windows(
    tariff: Tariff,
    *,
    generation: Outlook | None = None,
    consumption: Outlook | None = None,
    hours: int = 3,
    kw: float = 1.0,
    scheme: Scheme = "net_billing",
    unique_id: str | None = None,
    top: int | None = 3,
) -> pd.DataFrame:
    """Rank the windows of each forecast day for a flexible load of `hours` hours at `kw` kW by expected cost.

    The load needs `kw` kWh in each of its hours. In each hour it takes first the forecast PV surplus
    (generation minus consumption, or all the generation when no consumption outlook is given) and the rest
    from the grid. Its cost is grid kWh x import price plus PV kWh x what that PV energy would otherwise have
    been worth: the export price under `net_billing`, nothing under `self_consumption`, the import price of
    the hour under `net_metering` (a kWh credit is worth a kWh bought). So under 1:1 net metering with a
    flat price the sun does not matter, only the price, for a household that imports more than it exports
    and uses its credits before they expire; it does matter for a net exporter (the PV kWh used would have
    become a credit that expires unused), and under time-of-use netting, where `bill` sends leftover export
    to the dearest block. Under the other schemes cheap hours AND sunny hours win.

    A window is a candidate only if its hours are consecutive (one hour apart) and every one of them has a
    known forecast (the gap rule of `outlook.best_windows`): an unknown hour is not free PV.

    Generalises `outlook.best_windows` (which looks at energy only) to money. Returns `unique_id, date,
    start, end, cost, grid_kwh, pv_kwh, rank, confidence` (rank 1 = cheapest of the day), the `top` cheapest
    windows of each day (None: all). Expected values from point forecasts: a cloudy surprise moves them.
    """
    if not 1 <= hours <= 24:
        raise ValueError("hours must be in 1-24")
    if kw <= 0:
        raise ValueError("kw must be positive")
    if scheme not in SCHEMES:
        raise ValueError(f"scheme must be one of {SCHEMES}")
    if generation is None and consumption is None:
        raise ValueError("Give a generation and/or a consumption outlook (they set the hours to rank)")
    for o, q in ((generation, "generation"), (consumption, "consumption")):
        if o is not None and o.quantity != q:
            raise ValueError(f"The {q} outlook has quantity {o.quantity!r}")
    base = generation if generation is not None else consumption
    assert base is not None
    frame = _pair_outlooks(generation, consumption, unique_id)
    conf = base.daily.set_index(["unique_id", "date"])["confidence"]
    rows = []
    for (uid, day), g in frame.groupby(
        ["unique_id", frame["ds"].dt.tz_localize(None).dt.normalize()], sort=True
    ):
        if len(g) < hours:
            continue
        ds = pd.DatetimeIndex(g["ds"])
        ones = np.ones(hours)
        unknown = ~np.isfinite(g["gen"].to_numpy(dtype=float)) | ~np.isfinite(g["cons"].to_numpy(dtype=float))
        step = np.asarray((ds[1:] - ds[:-1]) == pd.Timedelta(hours=1))  # resolution-safe (ns or us)
        broken = np.concatenate([[False], ~step])  # True at an hour that does not follow the previous one
        bad = np.convolve(unknown, ones, mode="valid") > 0
        if hours > 1:
            bad |= np.convolve(broken[1:], np.ones(hours - 1), mode="valid") > 0
        if bad.all():
            continue
        p_imp = tariff.price(ds)
        if scheme == "net_billing":
            p_pv = tariff.export(ds)
        elif scheme == "net_metering":
            p_pv = p_imp
        else:
            p_pv = np.zeros(len(g))
        surplus = np.clip(np.nan_to_num(g["gen"].to_numpy()) - np.nan_to_num(g["cons"].to_numpy()), 0, None)
        pv = np.minimum(kw, surplus)
        grid = kw - pv
        cost_h = grid * p_imp + pv * p_pv
        cost = np.convolve(cost_h, ones, mode="valid")
        gk, pk = np.convolve(grid, ones, mode="valid"), np.convolve(pv, ones, mode="valid")
        ok = np.flatnonzero(~bad)
        rank = np.empty(len(cost), dtype=int)
        rank[ok] = np.argsort(np.argsort(cost[ok], kind="stable"), kind="stable") + 1
        for i in ok.tolist():
            rows.append(
                {
                    "unique_id": uid,
                    "date": day,
                    "start": g["ds"].iloc[i],
                    "end": g["ds"].iloc[i + hours - 1] + pd.Timedelta(hours=1),
                    "cost": float(cost[i]),
                    "grid_kwh": float(gk[i]),
                    "pv_kwh": float(pk[i]),
                    "rank": int(rank[i]),
                    "confidence": conf.get((uid, day)),
                }
            )
    cols = ["unique_id", "date", "start", "end", "cost", "grid_kwh", "pv_kwh", "rank", "confidence"]
    out = pd.DataFrame(rows, columns=cols)
    if top is not None:
        out = out[out["rank"] <= top]
    return out.sort_values(["unique_id", "date", "rank"], kind="stable").reset_index(drop=True)


def _pair_outlooks(gen: Outlook | None, cons: Outlook | None, unique_id: str | None) -> pd.DataFrame:
    def pick(o: Outlook | None, col: str) -> pd.DataFrame | None:
        if o is None:
            return None
        h = o.hourly[["unique_id", "ds", "y_hat"]].rename(columns={"y_hat": col})
        return h

    g, c = pick(gen, "gen"), pick(cons, "cons")
    if g is not None and c is not None:
        if _single(g["unique_id"]) and _single(c["unique_id"]):
            c = c.assign(unique_id=g["unique_id"].iloc[0])
        f = g.merge(c, on=["unique_id", "ds"], how="inner")
        if f.empty:
            raise ValueError("The generation and consumption outlooks share no site and hour")
    elif g is not None:
        f = g.assign(cons=0.0)
    else:
        assert c is not None
        f = c.assign(gen=0.0)
    if unique_id is not None:
        f = f[f["unique_id"] == unique_id]
    return f.sort_values(["unique_id", "ds"], kind="stable").reset_index(drop=True)


def _single(ids: pd.Series) -> bool:
    a = ids.to_numpy()
    return len(a) > 0 and bool((a == a[0]).all())


def _per(v: float | Mapping[str, float], uid: str) -> float:
    if isinstance(v, Mapping):
        return float(v.get(uid, 0.0))
    return float(v)


__all__ = [
    "SCHEMES",
    "Bill",
    "Blocks",
    "Scheme",
    "Tariff",
    "bill",
    "cheapest_windows",
    "flows",
]
