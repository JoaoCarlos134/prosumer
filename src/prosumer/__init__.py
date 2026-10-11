"""prosumer: day-ahead forecasting of energy prosumers' generation and consumption.

Status: skeleton of step E1 of the proposal (`docs/proposta/PROPOSTA_BIBLIOTECA.md`). So far there are
`contracts`, `protocol`, `metrics` (including metrics at several resolutions), `postprocessing`
(consumption bias correction), `physics` (sun position, clear sky, plane-of-array) and `data`; the `io`,
`quality`, `diagnostics`, `forecast`, `embedded` and `economics` modules are not written yet.

The protocol and metrics were ported from the frozen v2 benchmark
(`experimentos/testes_previsao/scripts/comum.py` and `05_avalia.py`), which produced the reported
results. The benchmark numbers live in the CSVs of that directory; they are not recomputed from the
example data.
"""

from __future__ import annotations

from . import contracts, data, metrics, physics, postprocessing, protocol
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
    "SupportError",
    "Window",
    "__version__",
    "contracts",
    "data",
    "metrics",
    "physics",
    "postprocessing",
    "protocol",
]
