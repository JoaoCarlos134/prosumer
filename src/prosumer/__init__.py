"""prosumer: day-ahead forecasting of energy prosumers' generation and consumption.

Status: step E2 of the proposal (`docs/proposta/PROPOSTA_BIBLIOTECA.md`). So far there are
`analysis` (the app's single call, `analyze(series) -> Report`), `contracts`, `protocol`, `metrics`
(including metrics at several resolutions and bands), `postprocessing` (consumption bias correction),
`physics` (sun position, clear sky, plane-of-array), `quality` (the clock of a generation series checked
against the sun), `forecast`, `io` (Open-Meteo forecasts, NASA POWER weather) and `data` (synthetic series
and the real Dingle houses); the `diagnostics`, `embedded` and `economics` modules are not written yet.

The protocol and metrics were ported from the frozen v2 benchmark
(`experimentos/testes_previsao/scripts/comum.py` and `05_avalia.py`), which produced the reported
results. The benchmark numbers live in the CSVs of that directory; they are not recomputed from the
example data.
"""

from __future__ import annotations

from . import analysis, contracts, data, metrics, physics, postprocessing, protocol, quality
from .analysis import Report, analyze
from .contracts import ContractError, EnergySeries
from .protocol import DayAhead, Fold, Regime, SupportError, Window

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
    "Regime",
    "Report",
    "SupportError",
    "Window",
    "__version__",
    "analysis",
    "analyze",
    "contracts",
    "data",
    "metrics",
    "physics",
    "postprocessing",
    "protocol",
    "quality",
]
