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

Windows: double-click `prosumer_site.cmd`, the one launcher. The first time it builds the site (Python 3.12
and Node.js 20+ needed; a few minutes) and then starts it; every later run starts the built site at once,
without building. The console window says the address and opens the browser; closing it stops the site.

    prosumer_site.cmd             run (build first only if dist\prosumer\prosumer.exe is missing)
    prosumer_site.cmd rebuild     build again after changing the page, the server or the library, then run
    prosumer_site.cmd dev         development: the API with --reload (library from ../src) + the page with hot reload on :5173

Any other argument goes to the site (`--no-browser`). Linux/macOS, or by hand on any system:

    # from webapp/, with the library installed in the environment (pip install -e ..[lightgbm,net,fronius])
    pip install -r requirements.txt
    cd web && npm install && npm run build && cd ..
    python -m server.launch                           # first free port from 8080, opens the browser

Tests (no network; the library's fakes from `../tests/test_app.py`): `python -m pytest tests` from `webapp/`.

## The standalone folder (nothing installed)

The build (`prosumer_site.cmd` the first time, or `rebuild`): `.venv` with the library `..[lightgbm,net,fronius]`
(installed again each build, so the exe carries the code as it is), `requirements.txt` and PyInstaller;
`npm ci && npm run build` in `web/`; `pyinstaller prosumer_site.spec` (work files in `build/`) ->
`dist/prosumer/prosumer.exe`, one folder with Python, the library, LightGBM, the page and the demo (~325 MB).
That folder runs by itself on another Windows computer (copy or zip it). torch and the foundation models are
left out (gigabytes): `models: "all"` notes them as not installed. PyInstaller does not cross-compile: the
Windows exe is built and tested on the Windows machine. The cloud built the same spec on Linux on 2026-10-23
(465 MB folder; `/api/info`, the page and the port fallback 8080 -> 8081 checked). The home machine's Smart App
Control blocks unsigned, locally built exes: expect it not to run there (signing would fix it).

## State (2026-10-23, cloud)

Done: every page (Overview, Next days, History, Forecast check, PV system, Bill, Notes & sources), `npm run
build` clean (tsc strict), `tests/test_api.py` (13 tests; CI job `site` runs them and the build), the launchers, the PyInstaller spec, and a browser
check with Playwright (fake weather): every page in en/pt, light/dark, 1440 px and a 390 px phone; focus mode,
show as a table, export CSV, the cross-filter by day (Overview -> Next days) and by month (Bill), the language
switch on a kept result. Look (asked on 23/10): rounded tiles with layered shadows that lift on hover, KPI cards
that tilt toward the pointer, a floating pill tab bar; legends one scrolling row clear of the axis names.

The PV page shows a trend or a loss only where the library reports one (`diagnostics.orientation.reliable`,
`segments.trend_reported` / `loss_reported`, added to the library for this; a typed tilt/azimuth now reaches
the diagnostics too). Choices the page makes on its own:
- Next days per day: the axis follows the bars; a range whisker past the top is cut with an arrow (one
  unusual day in the window can still make a wide range: Dingle H1 had a 15.9 kWh weekend day).
- A file with several series (inverters, meters): a day or hour is the file's total only when every series
  has a value (else a gap); hours measured are the mean over the series, complete against the hours of that
  local day (23 or 25 on a clock change).
- The Forecast check and Bill pages show "why it was skipped" from `report.skipped.forecast` / `.economics`
  (the library's note, in the page's language).

### 2026-10-26 (cloud): the Inputs pane

- Full screen: the pane's maximise button, or the landing page's "add your files", slides the Inputs over the
  whole screen (below the header) with the sections as cards side by side; "Back to the side", the cross or Esc
  return. It closes by itself when an analysis starts.
- New there: a map to pick the site (a click or the dragged pin sets the coordinates, "Use my location" asks the
  browser), the browser's IANA time zones as suggestions, a preview under each dropped file (`/api/peek` ->
  `prosumer.app.peek`: the column, unit and kind chosen, hours, share measured, span; or the reader's message),
  the weeks of the consumption profile, the hour the forecast check's forecast is made, and a Brazilian bill's
  credit carried over (`weeks`, `issue_hour`, `price.credit`: new fields of `prosumer.app.Request`).
- The suns turn about their centre (the rays orbited a point off the sun): `components/Sun.tsx` (landing scene,
  loader) sets the ring's SVG `rotate(angle cx cy)` and the disc's scale each frame (28/10; replaced 26/10's
  `Spin.tsx`); the logo's rays stand still; the compass needle is turned the same way, by hand.

What the library can do that the pane still does not offer (each needs a field in `app.Request` first):
- uncertainty bands (`forecast.LightGBMQuantile`: `report.bands`, a band chart on the check page);
- the forecast check against measured weather (regimes B/C: `io.nasa_power` / `io.open_meteo.wide`);
- facade or balcony panels (`diagnostics_options={"tilts": 0-90}` and the same grid for the next days);
- the rest of `brazil.Setup`: GD class from the connection or access-request date (`gd_class`), an assumed
  bandeira for months ANEEL has not published, subgroup, credit expiry, the readings of the tax rules;
- the clock checks' options (`clock_options`, `clock_weather_options`) and the bias/calibration days;
- a demo house other than H1 (`data.dingle_houses`: 20 houses, 10 with PV; a download from figshare);
- out of the page, on the result: the fitted model as a C header for a microcontroller (`embedded.to_c`).

Left:
1. The Windows build and its test on the Lactec machine: first pass on 26/10 (325 MB; up in 17 s cold; the demo
   in 16 s with live Open-Meteo; a real Fronius 5-min year read as Fronius Solar.web, live ANEEL tariff and
   bandeira, 40 s). Redo after the page changes still planned (`prosumer_site.cmd rebuild`).
2. A browser pass there with the live services (Open-Meteo, the Brazilian price with live ANEEL).
3. ~~The `work-reviewer`'s open minors (23/10): pending/notes for library users, English credits in pt~~
   done 26/10: `app.run` rewords them (`app.FOR_PEOPLE`), credits' notes translated; a test fails on code
   in backticks on the tested pages.
4. ~~Library: the consumption outlook's daily range summed the hourly lows/highs~~ done 26/10: the range of
   the past daily totals. The page's cut whisker (Next days) can stay as a guard. Also done: `report.skipped`,
   the Check and Bill pages read it instead of matching the note's first words.
