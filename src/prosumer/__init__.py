"""prosumer: day-ahead forecasting of energy prosumers' generation and consumption.

Status: version 0.1 done (step E2) and step E4 started, of the proposal
(`docs/proposta/PROPOSTA_BIBLIOTECA.md`). So far there are `analysis` (the app's single call,
`analyze(series) -> Report`), `contracts`, `protocol`, `metrics` (including metrics at several resolutions
and bands), `postprocessing` (consumption bias correction), `physics` (sun position, clear sky,
plane-of-array), `provenance` (source and licence of every input), `quality` (the clock of a generation series
checked against the sun), `diagnostics` (clear-day performance of a PV series from its energy alone, and its
change points), `forecast`, `io` (Open-Meteo forecasts, NASA POWER weather, Fronius Solar.web exports,
generic meter tables) and `data` (synthetic series and the real Dingle houses); `embedded` (a fitted linear
or tree model with its preprocessing, or the benchmark's SparseTSF/CycleNet, as one C header for an ESP32)
and `outlook` (`forecast_ahead`: the next days to weeks, hourly and per day, with the weather forecast
trusted less as the lead grows; `best_windows` places a heavy load) and `economics` (step E6: tariffs as
data, the monthly bill under net metering, net billing or self-consumption, `cheapest_windows` for a flexible
load by price and sun; `economics.brazil`: tarifa cheia with taxes, bandeiras, custo de disponibilidade,
tarifa branca and Lei 14.300 GD I/GD II, with ANEEL data from `io.aneel`; `economics.Plan` and
`economics.brazil.Setup` say how a household pays, for `analyze(economics=...)`, whose report then has the
monthly bill and the savings of the PV, and for `economics.windows_by_cost` over an `Outlook`).

The protocol and metrics were ported from the frozen v2 benchmark
(`experimentos/testes_previsao/scripts/comum.py` and `05_avalia.py`), which produced the reported
results. The benchmark numbers live in the CSVs of that directory; they are not recomputed from the
example data.
"""

from __future__ import annotations

from . import (
    analysis,
    contracts,
    data,
    diagnostics,
    economics,
    embedded,
    metrics,
    outlook,
    physics,
    postprocessing,
    protocol,
    provenance,
    quality,
)
from .analysis import Report, analyze
from .contracts import ContractError, EnergySeries
from .outlook import Outlook, best_windows, forecast_ahead
from .protocol import DayAhead, Fold, Regime, SupportError, Window
from .provenance import Provenance

try:  # pragma: no cover - depends on the package being installed
    from importlib.metadata import PackageNotFoundError, version

    __version__ = version("prosumer")
except PackageNotFoundError:  # pragma: no cover - development tree without installation
    __version__ = "0.0.0.dev0"

__all__ = [
    "ContractError",
    "DayAhead",
    "EnergySeries",
    "Fold",
    "Outlook",
    "Provenance",
    "Regime",
    "Report",
    "SupportError",
    "Window",
    "__version__",
    "analysis",
    "analyze",
    "best_windows",
    "contracts",
    "data",
    "diagnostics",
    "economics",
    "embedded",
    "forecast_ahead",
    "metrics",
    "outlook",
    "physics",
    "postprocessing",
    "protocol",
    "provenance",
    "quality",
]
