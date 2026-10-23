# prosumer site (the TCC's app)

A local web app on top of the library: the person's inverter/meter files in, a report out, laid out like a
business-intelligence dashboard (a grey canvas of white visual tiles, KPI cards, page tabs along the bottom,
a collapsible Inputs pane on the right, focus mode / show as a table / export data on every visual,
cross-filtering by day) with animations. English and Portuguese, light and dark.

- `server/` - FastAPI, a thin shell over `prosumer.app.run` (all the work is the library's). `api.py`:
  `GET /api/info`, `POST /api/run` (multipart: `request` = the JSON of `prosumer.app.Request`, `lang`,
  `generation`/`consumption` files), `POST /api/demo`, `GET /api/demo/{generation|consumption}.csv`,
  `GET /api/result/{id}?lang=` (the last 8 results are kept in memory: a language switch re-renders without
  running again), then the built page (`web/dist`) for every other path. A `ValueError` of the library is a
  400 with `i18n.message(e, lang)`; anything else a 500 with its text. `SERVICES` replaces the outside calls
  (tests).
- `server/demo.py` - the demo: house H1 of the Dingle dataset (Khadem et al. 2024, CC0; `demo/dingle_H1_2020.csv`
  is the benchmark's hourly version), each day moved by whole 52-week steps to the 365 days before today
  (same weekday, season within ~a week), written on a UTC clock; example time-of-use price in EUR.
- `server/launch.py` - the standalone folder's entry point (`prosumer.exe`; also `python -m server.launch`):
  first free port from 8080, uvicorn in-process, the browser opened when the server answers.
- `web/` - React 19 + Vite 7 + TypeScript 5.9 + Tailwind 4; Apache ECharts 5 (charts and their animations),
  Framer Motion (page/tile/number animations), Leaflet + OpenStreetMap tiles (the site map), lucide-react
  (icons), zustand (state). All open source, no account or API key.

No licence file: the project is private (all rights reserved), like the library.

## Run it

Windows: double-click `run.cmd` (first time: makes `.venv`, installs the library `..[lightgbm,net,fronius]`
and `requirements.txt`, builds the page when `npm` is there; then opens http://127.0.0.1:8080). `dev.cmd`:
the API with `--reload` and the page with hot reload on :5173. Linux/macOS: `./run.sh`. By hand:

    # from webapp/, with the library installed in the environment (pip install -e ..[lightgbm,net,fronius])
    pip install -r requirements.txt
    cd web && npm install && npm run build && cd ..
    python -m uvicorn server.api:app --port 8080      # then open http://127.0.0.1:8080

Tests (no network; the library's fakes from `../tests/test_app.py`): `python -m pytest tests` from `webapp/`.

## The standalone folder (nothing installed)

`build_exe.cmd` on Windows (Python 3.12 + Node.js 20+): `.venv-build`, the library and the server,
`npm ci && npm run build`, `pyinstaller prosumer_site.spec` -> `dist/prosumer/prosumer.exe` (one folder: Python,
the library, LightGBM, the page, the demo) and `dist/prosumer-site.zip`. Double-click `prosumer.exe`: a console
window says the address and opens the browser; closing it stops the site. torch and the foundation models are
left out (gigabytes): `models: "all"` notes them as not installed. PyInstaller does not cross-compile: the
Windows exe is built and tested on the Windows machine. The cloud built the same spec on Linux on 2026-10-23
(465 MB folder; `/api/info`, the page and the port fallback 8080 -> 8081 checked). The home machine's Smart App
Control blocks unsigned, locally built exes: expect it not to run there (signing would fix it).

## State (2026-10-23, cloud)

Done: every page (Overview, Next days, History, Forecast check, PV system, Bill, Notes & sources), `npm run
build` clean (tsc strict), `tests/test_api.py` (10 tests), the launchers, the PyInstaller spec, and a browser
check with Playwright (fake weather): every page in en/pt, light/dark, 1440 px and a 390 px phone; focus mode,
show as a table, export CSV, the cross-filter by day (Overview -> Next days) and by month (Bill), the language
switch on a kept result. Look (asked on 23/10): rounded tiles with layered shadows that lift on hover, KPI cards
that tilt toward the pointer, a floating pill tab bar; legends one scrolling row clear of the axis names.

Choices the page makes on its own (the library gives no flag for them):
- PV page: a trend/loss is shown only when the library would report one: the roof given, or fitted with
  `r2 >= diagnostics.GOOD_FIT_R2` (from `/api/info`) and not on the edge (`diagnostics.py`, `reliable`).
- Next days per day: the axis follows the bars; a range whisker past the top is cut with an arrow (the
  consumption profile's daily `high` is the sum of the hourly highs, up to ~13x the day on Dingle H1).

Left:
1. The Windows build and its test on the Lactec machine (`build_exe.cmd`, then double-click
   `dist/prosumer/prosumer.exe`; check the demo and a real Fronius file).
2. A browser pass there with the live services (Open-Meteo, the Brazilian price with live ANEEL).
3. Library: the consumption outlook's daily range (`outlook.forecast_ahead`, profile rule) sums the hourly
   lows/highs; a daily quantile of daily totals would be the honest range.
