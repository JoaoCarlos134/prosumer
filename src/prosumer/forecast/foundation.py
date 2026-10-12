"""Zero-shot foundation models that run on CPU: the benchmark's leaders, behind the library interface.

Nothing is fitted (`fit` only stores the covariate names); each window's history goes to the model as it is
(1024 hours in the benchmark, `DayAhead(context=1024)`), and the point forecast is the model's median. The
calls copy the benchmark's (`03_fundacionais.py`, `03c_fundacionais_lote2.py`): batch sizes, float32 inputs,
the median quantile. Each vendor's package is imported only when its model is used, and each one is an
optional extra, because their dependencies conflict (Toto-2.0 and TiRex-2 need a newer torch than Chronos-2's
environment).

Benchmark rank (v2, rolling origin): TiRex-2 is the best single model on the plants in all three regimes;
Toto-2.0-313m is first on the houses' PV; Chronos-2 is among the leaders with covariates. All three run on
CPU, which is why the library and the app are CPU only.

Licences (checked 2026-10-11 on the Hugging Face model cards and the GitHub repos of the code): weights and
code of all three are Apache-2.0, commercial use allowed. Redistributing the weights must keep the licence and
any NOTICE file (TiRex-2 ships one). NX-AI's INTENDED_USE.md (TiRex-2) excludes high-risk uses under the EU AI
Act and use as a safety component; it says it does not change the licence.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import Any

import numpy as np
import pandas as pd

from ..contracts import EnergySeries
from ..protocol import H, Regime, Window
from .base import ModelCard

_ALL = (Regime.HISTORY, Regime.KNOWN_WEATHER, Regime.REAL_FORECAST)
LEVELS = (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9)


class _ZeroShot:
    """Common part: covariate names, batching and the checks on the windows."""

    batch = 64
    card: ModelCard

    def __init__(self, covariates: Sequence[str] | None = None) -> None:
        self.covariates = list(covariates or [])
        self._model: Any = None

    def fit(self, series: EnergySeries, cutoff: pd.Timestamp, covariates: pd.DataFrame | None = None) -> None:
        """Zero-shot: nothing is fitted. The model is loaded once, on the first `predict`."""

    def predict(self, windows: list[Window]) -> np.ndarray:
        self._ready(windows)
        out = [p for chunk in _batches(windows, self.batch) for p in self._forecast(chunk)]
        return np.asarray(out, dtype=float)[:, :H]

    def predict_quantiles(self, windows: list[Window]) -> np.ndarray:
        """Shape (windows, 9 levels 0.1-0.9, 24); only for the models that give quantiles."""
        self._ready(windows)
        out = [q for chunk in _batches(windows, self.batch) for q in self._quantiles(chunk)]
        return np.asarray(out, dtype=float)[:, :, :H]

    def _quantiles(self, windows: list[Window]) -> list[np.ndarray]:  # pragma: no cover
        raise NotImplementedError(f"{self.card.name} gives no quantiles here")

    def _ready(self, windows: list[Window]) -> None:
        for w in windows:
            if len(w.timestamps) != H:
                raise NotImplementedError(f"{self.card.name} forecasts whole days (issue_hour=0)")
            for c in self.covariates:
                if c not in w.future_covariates:
                    raise ValueError(f"window without covariate {c!r}: pass covariates to DayAhead")
        if self._model is None:
            self._model = self._load()

    def _past(self, w: Window, c: str) -> np.ndarray:
        return np.asarray(w.past_covariates[c], dtype=np.float32)

    def _future(self, w: Window, c: str) -> np.ndarray:
        return np.asarray(w.future_covariates[c], dtype=np.float32)

    def _load(self) -> Any:  # pragma: no cover - needs the vendor package
        raise NotImplementedError

    def _forecast(self, windows: list[Window]) -> list[np.ndarray]:  # pragma: no cover
        raise NotImplementedError


class Chronos2(_ZeroShot):
    """Chronos-2 (Amazon, 2025): past and future covariates, 21 quantiles; the forecast is the median.
    Extra `chronos` (`chronos-forecasting`)."""

    levels = LEVELS
    card = ModelCard(
        name="Chronos-2",
        family="foundation",
        license="Apache-2.0",
        device="cpu or gpu",
        sends_data=False,
        regimes=_ALL,
        trains=False,
        source="Ansari et al. (2025), amazon/chronos-2",
    )

    def _load(self) -> Any:  # pragma: no cover - needs chronos-forecasting
        from chronos import BaseChronosPipeline

        p = BaseChronosPipeline.from_pretrained("amazon/chronos-2", device_map="cpu")
        self._i50 = int(np.argmin(np.abs(np.asarray(p.quantiles) - 0.5)))
        qs = [round(float(x), 4) for x in p.quantiles]
        self._i9 = [qs.index(a) for a in LEVELS]  # fails if one of the 9 levels is not among its 21
        return p

    def _forecast(self, windows: list[Window]) -> list[np.ndarray]:  # pragma: no cover
        return [x[0, self._i50].numpy() for x in self._raw(windows)]

    def _quantiles(self, windows: list[Window]) -> list[np.ndarray]:  # pragma: no cover
        return [x[0, self._i9].numpy() for x in self._raw(windows)]

    def _raw(self, windows: list[Window]) -> Any:  # pragma: no cover
        inputs = []
        for w in windows:
            e: dict[str, Any] = {"target": w.history.astype(np.float32)}
            if self.covariates:
                e["past_covariates"] = {c: self._past(w, c) for c in self.covariates}
                e["future_covariates"] = {c: self._future(w, c) for c in self.covariates}
            inputs.append(e)
        return self._model.predict(inputs, prediction_length=H)


class TiRex2(_ZeroShot):
    """TiRex-2 (NX-AI): xLSTM, future covariates; the forecast is the median of 9 quantiles. Runs on CPU with
    the GPU hidden from the process (its sLSTM kernel would otherwise need nvcc at import). Extra `tirex2`."""

    levels = LEVELS
    card = ModelCard(
        name="TiRex-2",
        family="foundation",
        license="Apache-2.0",
        device="cpu",
        sends_data=False,
        regimes=_ALL,
        trains=False,
        source="NX-AI, NX-AI/TiRex-2",
    )

    def _load(self) -> Any:  # pragma: no cover - needs tirex2
        import os

        os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
        import torch._dynamo
        from tirex2 import load_model

        torch._dynamo.config.disable = True  # no C++ compiler: no torch.compile, no FlexAttention
        return load_model("NX-AI/TiRex-2", device="cpu", use_flex_attention=False, compile=False)

    def _forecast(self, windows: list[Window]) -> list[np.ndarray]:  # pragma: no cover
        return [q[4] for q in self._quantiles(windows)]  # level 0.5

    def _quantiles(self, windows: list[Window]) -> list[np.ndarray]:  # pragma: no cover
        import torch
        from tirex2 import TimeseriesType

        ts = []
        for w in windows:
            fut = None
            if self.covariates:  # known over the whole horizon: future covariates [V, T + H]
                fut = torch.tensor(
                    np.stack([np.r_[self._past(w, c), self._future(w, c)] for c in self.covariates]),
                    dtype=torch.float32,
                )
            target = torch.tensor(w.history.astype(np.float32))[None]
            ts.append(TimeseriesType(target=target, past_covariates=None, future_covariates=fut))
        r = self._model.forecast(ts, prediction_length=H, output_type="numpy", batch_size=self.batch)
        return [np.asarray(x)[0, :, :H] for x in r]  # (V, 9 quantiles 0.1-0.9, H) -> the target's


class Toto2(_ZeroShot):
    """Toto-2.0 (Datadog), 22m or 313m parameters, history only; the forecast is the 0.5 quantile.
    Extra `toto2`."""

    batch = 32

    def __init__(self, size: str = "313m") -> None:
        super().__init__(None)
        if size not in ("22m", "313m"):
            raise ValueError("size must be '22m' or '313m'")
        self.hf = f"Datadog/Toto-2.0-{size}"
        self.card = ModelCard(
            name=f"Toto-2.0-{size}",
            family="foundation",
            license="Apache-2.0",
            device="cpu or gpu",
            sends_data=False,
            regimes=(Regime.HISTORY,),
            trains=False,
            source=f"Datadog, {self.hf}",
        )

    def _load(self) -> Any:  # pragma: no cover - needs toto2
        from toto2 import Toto2Model

        return Toto2Model.from_pretrained(self.hf).eval()

    def _forecast(self, windows: list[Window]) -> list[np.ndarray]:  # pragma: no cover
        import torch

        x = torch.tensor(np.stack([w.history.astype(np.float32) for w in windows]))[:, None, :]
        with torch.no_grad():
            q = self._model.forecast(
                {
                    "target": x,
                    "target_mask": torch.ones_like(x, dtype=torch.bool),
                    "series_ids": torch.zeros(x.shape[0], 1, dtype=torch.long),
                },
                horizon=H,
                decode_block_size=768,
                has_missing_values=False,
            )
        return list(np.asarray(q[4, :, 0, :H], dtype=float))


def _batches(xs: list[Window], n: int) -> Iterator[list[Window]]:
    for i in range(0, len(xs), n):
        yield xs[i : i + n]
