# Embedded

A day-ahead model small enough for a microcontroller, exported as ONE C header: the features, the
preprocessing (gap filling, normalisation) and the model, so the device needs nothing else.

```python
# needs: sklearn
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from prosumer import data, embedded

load = data.example_house(n_series=1, days=60)
y = load.frame["y"].to_numpy()
days = pd.DatetimeIndex(load.frame["ds"]).normalize().unique()
# the benchmark's features of each day (24 rows) from the 168 hours before it: lags, weekly mean, calendar
X = np.vstack([embedded.day_ahead_features(y[(k - 7) * 24 : k * 24], days[k]) for k in range(7, len(days))])
target = y[7 * 24 : len(days) * 24]
ridge = Ridge(alpha=1.0).fit(X, target)

model = embedded.Linear.from_sklearn(ridge, embedded.FEATURES)
header = embedded.to_c(model, "house_load")  # one C header: features, gap filling, weights
print(embedded.footprint(model))  # Footprint(flash=92, ram=...)
np.testing.assert_allclose(model.predict(X), ridge.predict(X), rtol=1e-9, atol=1e-9)
```

- `embedded.Linear` (Ridge, linear regression, with the imputer and scaler of a pipeline), `embedded.Trees`
  (`from_sklearn` for forests, `from_lightgbm`), and the benchmark's `embedded.SparseTSF` and
  `embedded.CycleNet` (numpy arrays; `from_torch` without importing torch). `footprint` gives flash and RAM.
- The C reproduces the Python predictions (checked in the tests by compiling it to WebAssembly).
- Measured on the Dingle houses: a 92-byte Ridge, a ~30 KB forest and a ~17 KB LightGBM per house all tie with
  the best model of the benchmark on consumption with history only. The study is
  `docs/projeto/ESTUDO_EMBARCADO.md` (in Portuguese).
