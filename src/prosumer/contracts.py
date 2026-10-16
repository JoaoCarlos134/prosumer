"""Data contracts: no function in the library accepts a raw DataFrame.

The principle comes from PROPOSTA_BIBLIOTECA.md (section 6): every series carries a unit, a time zone, a
sampling frequency and a validity mask. `EnergySeries` wraps the DataFrame with those four pieces of
metadata and validates its shape with pandera once, at construction. After that, functions can trust
the structure.

The validity mask exists because, in the project's real data, a gap and a zero are not the same thing:
the inverter logs zero at night (valid) and logs nothing when it goes down (invalid). Keeping only the
NaN loses the difference between "did not generate" and "we don't know"; that is why `valid` is a
column, not a convention.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

import pandas as pd

from .provenance import Provenance

if TYPE_CHECKING:
    import pandera.pandas as pa

# pandera is imported only where a series is VALIDATED (`schema`, `EnergySeries.from_dataframe`). The rest of
# the library (protocol, metrics) needs only pandas and numpy, so the frozen benchmark environments, which do
# not have pandera, can run the same protocol code.

Unit = Literal["kWh", "Wh", "kW", "W"]
Quantity = Literal["generation", "consumption", "irradiance", "temperature"]
DstPolicy = Literal["raise", "drop"]

# Factors to kWh/kW. The library converts to kWh at the boundary and works only in that unit.
_TO_KILO: dict[str, float] = {"kWh": 1.0, "Wh": 1e-3, "kW": 1.0, "W": 1e-3}


def schema(tz: str) -> pa.DataFrameSchema:
    """Schema of the long-format series for a concrete time zone.

    It is a function of the time zone on purpose: pandas' `DatetimeTZDtype` requires a `tz`, and the
    time zone is part of the contract. Validating against the declared zone catches a series that
    arrived in another zone (or naive) instead of letting it through and getting the peak hour wrong
    later.
    """
    import pandera.pandas as pa

    return pa.DataFrameSchema(
        {
            "unique_id": pa.Column(str, nullable=False, description="series identifier"),
            "ds": pa.Column(pd.DatetimeTZDtype(tz=tz), nullable=False, description="start of the interval"),
            "y": pa.Column(float, nullable=True, description="value in the interval, in the declared unit"),
            "valid": pa.Column(bool, nullable=False, description="False where the meter logged nothing"),
        },
        strict=False,
        coerce=True,
        unique=["unique_id", "ds"],
        name="EnergySeries",
        ordered=False,
    )


class ContractError(ValueError):
    """Data contract error: the series does not meet the schema or the required metadata."""


@dataclass(frozen=True, slots=True)
class EnergySeries:
    """Time series with unit, time zone, frequency and validity mask.

    Build it with `EnergySeries.from_dataframe` to validate; the constructor does not revalidate, on
    purpose, so internal operations can reuse `replace()` at no cost.
    """

    frame: pd.DataFrame
    unit: Unit
    quantity: Quantity
    tz: str
    freq: str  # pandas frequency alias: "h", "5min", "D"
    # where the data came from and its licence (see `prosumer.provenance`); None = nobody said
    provenance: Provenance | None = None

    # ------------------------------------------------------------------ construction
    @classmethod
    def from_dataframe(
        cls,
        frame: pd.DataFrame,
        *,
        unit: Unit,
        quantity: Quantity,
        tz: str,
        freq: str,
        value_column: str = "y",
        source_tz: str | None = None,
        dst: DstPolicy = "raise",
        provenance: Provenance | None = None,
    ) -> EnergySeries:
        """Validate and wrap. `value_column` reads a frame whose value column is not called `y`.

        `source_tz` says which time zone the NAIVE timestamps of the frame are in; the default is `tz`
        itself. Use it when the file is in UTC and the series is from a place with daylight saving time:
        `tz="Europe/Dublin", source_tz="UTC"`. Timestamps that already carry a time zone are only
        converted, and `source_tz` is ignored.

        `dst` decides what to do with rows at an impossible local time: the hour that does not exist (the
        clock springs forward) and a repeated hour that appears only once (the clock falls back and the
        file merged both). "raise" (default) raises `ContractError`; "drop" removes those rows and warns
        how many. This is the case of the Dingle houses: Dublin local time on a gap-free grid, with the
        rows of 29/03 01:00 and 25/10 01:00 filled in by the dataset's preprocessing (checked 2026-10-07).

        `provenance`: where the data came from and its licence; `analyze` reports it (and notes when it is
        missing). Operations that derive a series (`to_kwh`, ...) keep it.
        """
        if frame.empty:
            raise ContractError("Empty series: nothing to infer or validate")
        x = frame.rename(columns={value_column: "y"}).copy()
        missing = {"unique_id", "ds", "y"} - set(x.columns)
        if missing:
            raise ContractError(f"Missing required columns: {sorted(missing)}")
        if "valid" not in x.columns:
            # Without an explicit mask, the only defensible default is "NaN is invalid, the rest is valid".
            x["valid"] = x["y"].notna()
        x["unique_id"] = x["unique_id"].astype(str)
        x["ds"] = _localize(x["ds"], tz, source_tz or tz, x["unique_id"], dst)
        if x["ds"].isna().any():  # only happens with dst="drop"
            out = x["ds"].isna()
            n_series = x.loc[out, "unique_id"].nunique()
            warnings.warn(
                f"{int(out.sum())} row(s) at an impossible local time dropped "
                f"(daylight saving change in {source_tz or tz}), in {n_series} series",
                UserWarning,
                stacklevel=2,
            )
            x = x.loc[~out]
        import pandera.pandas as pa

        try:
            validated = schema(tz).validate(x, lazy=True)
        except (pa.errors.SchemaError, pa.errors.SchemaErrors) as e:
            raise ContractError(f"Series breaks the contract: {e}") from e
        ordered = validated.sort_values(["unique_id", "ds"], kind="stable").reset_index(drop=True)
        return cls(frame=ordered, unit=unit, quantity=quantity, tz=tz, freq=freq, provenance=provenance)

    # ------------------------------------------------------------------ metadata
    @property
    def series(self) -> list[str]:
        """Identifiers present, in stable order."""
        return sorted(self.frame["unique_id"].unique().tolist())

    @property
    def hours_per_step(self) -> float:
        """Duration of one step in hours; used to convert power into energy."""
        return step(self.freq).total_seconds() / 3600.0

    def __len__(self) -> int:
        return len(self.frame)

    # ------------------------------------------------------------------ operations
    def to_kwh(self) -> EnergySeries:
        """Convert to kWh. Power (kW, W) is multiplied by the step duration."""
        if self.unit == "kWh":
            return self
        factor = _TO_KILO[self.unit]
        if self.unit in ("kW", "W"):
            factor *= self.hours_per_step
        x = self.frame.copy()
        x["y"] = x["y"] * factor
        return replace(self, frame=x, unit="kWh")

    def resample(self, freq: str = "h", *, min_coverage: float = 11 / 12) -> EnergySeries:
        """The energy in longer steps (kWh), e.g. a 15-minute meter or a 1-minute logger to hourly.

        Each output step is the sum of the steps inside it; it is valid when the valid steps cover at least
        `min_coverage` of it (11/12 as the readers: one 5-minute gap per hour; with 15-minute data every
        quarter must be there), otherwise NaN and invalid. The step must divide the new one. Only energy
        (generation, consumption): an average irradiance or temperature is not a sum.
        """
        if self.quantity not in ("generation", "consumption"):
            raise ContractError(f"resample sums energy; {self.quantity!r} is not energy")
        native, target = step(self.freq), step(freq)
        if target == native:
            return self.to_kwh()
        if target < native or target % native != pd.Timedelta(0):
            raise ContractError(f"Cannot resample steps of {self.freq!r} into {freq!r}: it must divide it")
        from .io._tables import aggregate  # here: io imports this module

        s = self.to_kwh()
        frame = s.frame.assign(y=s.frame["y"].where(s.frame["valid"]))[["unique_id", "ds", "y"]]
        out = aggregate(frame, native=native, freq=freq, min_coverage=min_coverage)
        return EnergySeries.from_dataframe(
            out, unit="kWh", quantity=self.quantity, tz=self.tz, freq=freq, provenance=self.provenance
        )

    def valid_only(self) -> pd.DataFrame:
        """Frame with only the rows the meter logged. Use it when NaN must not become zero."""
        return self.frame.loc[self.frame["valid"]].reset_index(drop=True)

    def coverage(self) -> pd.Series:
        """Fraction of valid steps per series: the number that goes in the quality report."""
        return self.frame.groupby("unique_id")["valid"].mean()

    def end_per_series(self) -> pd.Series:
        """Last valid timestamp of each series.

        It exists because series ending on different dates break validation protocols: that is exactly
        what happened in the benchmark (house H14 ends 20 days before the other 19 and
        `cross_validation` re-emitted days from an earlier fold). Whoever builds folds should look at
        this.
        """
        v = self.valid_only()
        return v.groupby("unique_id")["ds"].max()

    def ends_together(self) -> bool:
        """True if every series ends at the same valid timestamp."""
        ends = self.end_per_series()
        return bool(ends.empty or (ends == ends.iloc[0]).all())


def step(freq: str) -> pd.Timedelta:
    """Duration of one step from the pandas frequency alias ("h", "5min", "D").

    Raises for variable-length frequencies (month, year): there is no "how many hours are in a month",
    and converting power into energy with them would silently give a wrong number.
    """
    offset = pd.tseries.frequencies.to_offset(freq)
    if offset is None:
        raise ContractError(f"Invalid frequency: {freq!r}")
    try:
        return pd.Timedelta(nanoseconds=offset.nanos)
    except (AttributeError, ValueError) as e:
        raise ContractError(f"A variable-length frequency cannot be a step: {freq!r}") from e


def _localize(ds: pd.Series, tz: str, source: str, ids: pd.Series, dst: DstPolicy = "raise") -> pd.Series:
    """Ensure tz-aware datetimes. Naive timestamps are read in `source` and converted to `tz`.

    Daylight saving time, when `source` has it:
    - a repeated hour (clock falls back) that appears twice: resolved by order, series by series; the
      first occurrence is summer time. Requires chronological order, as a meter logs.
    - an hour that does not exist (clock springs forward), or a repeated hour that appears only once: a
      meter on local time does not log like that. Either the file is in UTC (`source_tz='UTC'`) or
      someone filled the grid (`dst='drop'` removes those rows, which come back as NaT). With
      `dst='raise'` it becomes a `ContractError` with both suggestions, never pandas' raw ValueError.
    """
    try:
        d = pd.to_datetime(ds)
    except (ValueError, TypeError) as e:
        raise ContractError(f"Column ds is not datetimes: {e}") from e
    if isinstance(d.dtype, pd.DatetimeTZDtype):
        return d.dt.tz_convert(tz)
    try:
        return d.dt.tz_localize(source).dt.tz_convert(tz)
    except ValueError:
        pass  # some daylight saving hour: resolved series by series below
    nonexistent: Literal["NaT", "raise"] = "NaT" if dst == "drop" else "raise"
    parts = []
    for uid, g in d.groupby(ids, sort=False):
        try:
            parts.append(g.dt.tz_localize(source, ambiguous="infer", nonexistent=nonexistent))
            continue
        except ValueError as e:
            if dst != "drop":
                raise ContractError(
                    f"Series {uid!r}: timestamps impossible in time zone {source!r} because of daylight "
                    f"saving time ({e}). If the file is in UTC, pass source_tz='UTC'. If it is in local "
                    "time with the grid filled in (no gap at the missing hour, a single row at the "
                    "repeated hour), pass dst='drop'."
                ) from e
        # repeated hour that appears only once: there is no way to know which of the two it is
        parts.append(g.dt.tz_localize(source, ambiguous="NaT", nonexistent="NaT"))
    return pd.concat(parts).reindex(d.index).dt.tz_convert(tz)
