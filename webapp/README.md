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
- `web/` - React 19 + Vite 7 + TypeScript 5.9 + Tailwind 4; Apache ECharts 5 (charts and their animations),
  Framer Motion (page/tile/number animations), Leaflet + OpenStreetMap tiles (the site map), lucide-react
  (icons), zustand (state). All open source, no account or API key.

No licence file: the project is private (all rights reserved), like the library.

## Run it

    # from webapp/, with the library installed in the environment (pip install -e ..[lightgbm,net,fronius])
    pip install fastapi uvicorn python-multipart
    cd web && npm install && npm run build && cd ..
    python -m uvicorn server.api:app --port 8080      # then open http://127.0.0.1:8080

`npm run dev` in `web/` serves the page on :5173 with hot reload and sends `/api` to :8080.

## State (2026-10-23, Lactec) and what is left, in order

Written, never type-checked or built yet: `server/api.py`, `server/demo.py`, and in `web/src`: `types.ts`
(the Result JSON), `i18n.ts` (every UI string en/pt + labels of the library's codes), `format.ts` (the site's
wall clock: timestamps read as their wall-clock part and charted with `useUTC`), `theme.ts` (palette + two
ECharts themes), `store.ts`, `api.ts` (form -> request; Brazilian taxes typed in %), `run.ts`, `derive.ts`,
components (`Chart`, `Visual`, `Kpi`, `DataTable`, `SiteMap`, `Header`, `PageTabs`, `InputsPane`, `Loading`,
`Landing`), `App.tsx`, `pages/common.tsx`, `pages/Overview.tsx`, `pages/NextDays.tsx`.

1. **The five missing pages** (App.tsx imports them; each takes `{ payload }`, uses `PageGrid` + `Visual`
   tiles with `col-span-*` classes, `data=` for show-as-table/CSV, `Chart` options built in `useMemo` with
   series `id`s so updates animate):
   - `pages/History.tsx` (`HistoryPage`): quantity chips; ECharts calendar heatmap of the last 365 days
     (`derive.history`); daily line with a 30-day rolling mean (`derive.rolling`) and dataZoom; energy per
     month (`derive.monthly`, both files); hours measured per day; `report.quality` table.
   - `pages/Check.tsx` (`Check`): `report.forecast` null -> the skipped note(s) from `report.notes`. KPIs:
     skill of the median (`summary.output`), nRMSE, R2, test period (`summary.test_start/test_end`).
     Horizontal skill bars per forecast with 95% CI whiskers (custom series, as the error bars in
     Overview) and a 0 line for the reference (`summary.reference`); skill of the median per resolution
     (`report.resolution`: hour, day_night, peak_17_21, day; R2 vs R2_reference); test hours line
     (`charts.check`: measured `y` thick, `median`, the others off in the legend); scatter measured vs median
     (evaluated hours) with y = x; the metrics table.
   - `pages/System.tsx` (`System`, PV only; the tab hides without a generation file): KPIs effective kW
     (`outlooks.generation.method.series[uid].kw_eff`), roof (tilt/azimuth, `diagnostics.orientation` with
     `edge`), trend (`diagnostics.segments.trend_pct_per_year`, `lost_pct`), clock (`report.clock` row
     `period == "all"`). Performance index scatter (`charts.performance`) with the segments as lines and
     `diagnostics.steps` as markLines; `Plant` compass/tilt from NextDays.tsx; clock offset per month bars
     (colour by `confident`); diagnostics notes.
   - `pages/Bill.tsx` (`Bill`): `report.economics` null -> `t("billEmpty")` + the report note that starts
     "Economics left out" (pt "Conta deixada de fora"). KPIs: total, without PV, savings, mean month,
     self-consumption share, export. Monthly bars with vs without PV + savings line; Sankey of the flows
     (PV -> home `self_consumption`, PV -> exported `export`, grid -> home `grid_import`, summed over
     `monthly`); donut of `by_block` grid import (blocks: peak/off_peak or ponta/intermediario/fora_ponta);
     monthly energy (consumption, generation, grid_import, export); the bill table (monthly columns differ:
     a Brazilian bill has energy_charge, compensation_charge, flag, credits...); `economics.notes`, tariff.
   - `pages/Notes.tsx` (`Notes`): `log` as an animated timeline; notes grouped (app `notes`, each outlook's
     notes, `report.notes`, `economics.notes`; diagnostics notes are already in `report.notes`: dedupe);
     `report.pending`; sources and licences table (`credits` + `report.provenance`, links, `sends_data`);
     privacy (`t("privacy")`); about (`info.version`, the demo citation when `meta.demo`).
2. **Type-check and build**: `cd web && npm install && npm run build` (`tsc` then `vite build`); fix what it
   finds. Known: Overview's error-bar `renderItem` has a leftover `...(params ? {} : {})` and an unused
   `params`; lucide-react resolved to v1.x (check the icon names); ECharts typings may need `as any` in the
   custom series.
3. **Backend tests** `tests/test_api.py` (FastAPI `TestClient`, needs `httpx`; fakes as in the library's
   `tests/test_app.py`: `_weather`, `_services`, no network): `/api/info`; `/api/run` consumption-only with
   typed site -> 200, then `/api/result/{id}?lang=pt` has the Portuguese log; `days: 99` -> 400 with
   "days deve estar entre 1 e 35" in pt; `demo.frame(today)` covers the 365 days before today, hourly UTC,
   each hour equal to the 2020 value at the same wall-clock hour 52k weeks earlier (same weekday);
   `/api/demo` with fake services -> 200 with `windows_by_cost` not empty; the page route gives 503 without
   `web/dist`.
4. **Launchers**: `requirements.txt` (fastapi, uvicorn, python-multipart; httpx for the tests);
   `run.cmd` as in `1Projects/Keyword_map/run.cmd` (create `.venv`, `pip install -e ..[lightgbm,net,fronius]`
   and the requirements, `npm install` + `npm run build` when npm exists, open the browser,
   `python -m uvicorn server.api:app --port 8080`); `dev.cmd` (uvicorn --reload + `npm run dev`).
5. **Standalone exe (asked 2026-10-23)**: a folder that runs by itself, nothing installed, double-click
   `prosumer.exe`. Plan: PyInstaller one-folder build.
   - `server/launch.py`: first free port from 8080, `uvicorn.run(server.api.app, ...)` in-process, open
     the browser when it answers, print "close this window to stop"; `api.DIST` and `demo.SOURCE` from
     `sys._MEIPASS` when frozen.
   - `prosumer_site.spec`: onedir, name `prosumer`, console on, datas `web/dist` and
     `server/demo/*.csv`, `copy_metadata("prosumer")` (its version comes from importlib.metadata),
     `collect_all` for pandera, lightgbm, sklearn, scipy as needed, uvicorn hidden imports
     (`uvicorn.logging`, `uvicorn.loops.auto`, `uvicorn.protocols.http.auto`, `uvicorn.lifespan.on`);
     leave torch and the foundation models out (size; `models: "all"` then notes them as not installed).
   - `build_exe.cmd`: `.venv-build`, install the library `..[lightgbm,net,fronius]` + fastapi, uvicorn,
     python-multipart, pyinstaller; `npm ci && npm run build`; `pyinstaller --noconfirm prosumer_site.spec`
     -> `dist/prosumer/prosumer.exe`; zip the folder.
   - PyInstaller does not cross-compile: the cloud (Linux) can write the spec and smoke-test a Linux build;
     the Windows exe is built and tested on the Lactec machine (`build_exe.cmd`). The home machine's Smart
     App Control blocks unsigned, locally built exes: expect it not to run there (signing would fix it).
6. **Visual check in a browser** (Claude in Chrome on the Lactec machine, or Playwright in the cloud): the
   demo, every page in en and pt, light and dark, focus mode, show as a table, export CSV, the day
   cross-filter, a phone-width window; the Brazilian price path (fake ANEEL in the tests; live ANEEL on
   the Lactec machine).
7. Then the `work-reviewer` over the range, and CLAUDE.md "Where to continue".
