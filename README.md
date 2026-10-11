# prosumer

Day-ahead forecasting of energy prosumers' generation and consumption (PV plants, houses with PV and
batteries), from meter data to embedded models. It is the basis of João Carlos Jachenski Junior's
undergraduate thesis (TCC) and later master's work, and grew out of the Edge AI R&D project at Lactec.

The package (and, since 2026-10-11, the GitHub repository) was called `prossumidor` until 2026-10-09; the old
repository URL redirects here. The code and main docs are now in English; a
Brazilian layer (ANEEL tariffs, tarifa branca, Lei 14.300) and a Portuguese guide are planned. Most
project and benchmark documents under `docs/` and `experimentos/` are still in Portuguese.

The whole analysis is one call (it is what the thesis app will use):

```python
from prosumer import EnergySeries, analyze
from prosumer.io import open_meteo

series = EnergySeries.from_dataframe(df, unit="kWh", quantity="generation", tz="America/Sao_Paulo", freq="h")
site = (-24.83, -53.65)  # rounded: the coordinates are sent to Open-Meteo
raw = open_meteo.fetch_previous_runs(*site, start="2024-03-07", end="2026-05-31", tz="America/Sao_Paulo")
report = analyze(series, site=site, test_days=60, weather=open_meteo.wide(raw))
print(report.to_markdown())  # quality, forecast check by regime and resolution, weather coverage, what is missing
```

Or the protocol directly, to test a model of your own:

```python
from prosumer import DayAhead

task = DayAhead(series, test_start="2020-10-01", refit_days=31)  # issue_hour=12: issued at noon
for window in task.windows():
    ...  # forecast window.timestamps from window.history (and window.future_covariates)
```

**Private repository.** The plant series came from third parties and are not cleared for publication.
Owner names were replaced by the plant's city, and coordinates were rounded to ~1 km (the same grid point in
the weather datasets). Do not reintroduce any of this. The 20 houses are the public CC0 dataset of Khadem
et al. (2024), doi:10.1038/s41597-024-03454-2.

| Folder | What it is |
|---|---|
| `src/prosumer/` | the library: `analysis` (`analyze`), `contracts`, `protocol`, `metrics`, `physics`, `io.open_meteo`, `postprocessing`, `data` |
| `docs/proposta/` | thesis proposal (PDF and generator), library feasibility study, plan |
| `docs/projeto/` | state of the analyses, plan for papers A and B, network analysis, summaries |
| `docs/literatura/` | Edge AI review, references, survey and overview of 127 models |
| `experimentos/testes_previsao/` | day-ahead forecasting benchmark: scripts, hourly data, environments, results |
| `legado/` | the project's original code that will become library modules (does not run from here: the raw data stayed at Lactec) |

To pick up the work with Claude Code, start with `CLAUDE.md`.
