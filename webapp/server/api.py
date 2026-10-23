"""Backend of the prosumer site: a thin FastAPI shell over `prosumer.app.run`, serving the React build.

All the work is the library's (`prosumer.app.run`: where, read, weather, the next days, the best hours, the
analysis, the charts); this file only takes the page's form and files in and gives the `Result` back as strict
JSON, in English or Portuguese. Results are kept in memory (the last `KEEP`) so a language switch re-renders
without running again. A local tool for one person: no accounts, no database, files never stored.

Run:  python -m uvicorn server.api:app --port 8080   (or run.cmd, which also builds the page)
"""

from __future__ import annotations

import json
import sys
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from importlib.util import find_spec
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

import prosumer
from prosumer import app as backend
from prosumer import i18n
from prosumer.economics import SCHEMES, brazil
from prosumer.outlook import MAX_DAYS

from . import demo

# the standalone folder (PyInstaller, prosumer_site.spec) unpacks the page beside the code, in sys._MEIPASS
ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
DIST = ROOT / "web" / "dist"
LANGS = ("en", "pt")
KEEP = 8  # results kept for a language switch
SERVICES: backend.Services | None = None  # the outside calls of `run`; the tests put fakes here

app = FastAPI(title="prosumer site")
app.add_middleware(  # the Vite dev server (npm run dev) calls this API from another port
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_results: OrderedDict[str, dict[str, Any]] = OrderedDict()
_lock = threading.Lock()


class PageError(Exception):
    """An error for the person, already in their language."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status, self.message = status, message


@app.exception_handler(PageError)
def _page_error(_: Any, e: PageError) -> JSONResponse:
    return JSONResponse({"error": e.message}, status_code=e.status)


def _lang(lang: str | None) -> str:
    return lang if lang in LANGS else "en"


def _run(
    request: dict[str, Any], files: dict[str, tuple[bytes, str]], lang: str, meta: dict[str, Any]
) -> dict:
    """`app.run`, kept for a language switch; a `ValueError` is a message for the person (400), anything else
    a bug shown as it is (500: a local tool)."""
    t0 = time.perf_counter()
    try:
        result = backend.run(request, files, services=SERVICES)
    except ValueError as e:
        raise PageError(400, i18n.message(e, lang)) from e
    except Exception as e:
        traceback.print_exc()
        raise PageError(500, f"{type(e).__name__}: {e}") from e
    rid = uuid.uuid4().hex[:12]
    meta = {**meta, "seconds": round(time.perf_counter() - t0, 1), "request": request}
    with _lock:
        _results[rid] = {"result": result, "meta": meta}
        while len(_results) > KEEP:
            _results.popitem(last=False)
    return _payload(rid, lang)


def _payload(rid: str, lang: str) -> dict[str, Any]:
    with _lock:
        kept = _results.get(rid)
    if kept is None:
        raise PageError(404, "That result is no longer kept: run the analysis again.")
    return {"id": rid, "lang": lang, "meta": kept["meta"], "result": kept["result"].to_dict(lang)}


# ---------------------------------------------------------------------- the API
@app.get("/api/info")
def info() -> dict[str, Any]:
    """What the form offers: the library's version, its limits and choices, the models installed."""
    foundation = [name for name, module, _ in backend.FOUNDATION if find_spec(module)]
    return {
        "version": prosumer.__version__,
        "languages": list(LANGS),
        "max_days": MAX_DAYS,
        "models": {
            "sets": list(backend.MODEL_SETS),
            "lightgbm": bool(find_spec("lightgbm") and find_spec("sklearn")),
            "foundation": foundation,
        },
        "price_kinds": list(backend.PRICE_KINDS),
        "schemes": list(SCHEMES),
        "brazil": {
            "connections": list(brazil.MINIMUM_KWH),
            "gd": list(backend.GD_CLASSES),
            "modalities": [brazil.CONVENTIONAL, brazil.BRANCA],
            "gd_i_requested_by": brazil.GD_I_REQUESTED_BY.isoformat(),
        },
        "read_kinds": list(backend.READ_KINDS),
        "demo": demo.INFO,
    }


@app.post("/api/run")
async def run(
    request: str = Form("{}"),
    lang: str = Form("en"),
    generation: UploadFile | None = File(None),  # noqa: B008 - FastAPI's way of declaring an upload
    consumption: UploadFile | None = File(None),  # noqa: B008
) -> dict[str, Any]:
    """The page's form: `request` (the JSON of `prosumer.app.Request`) and one or both files."""
    lang = _lang(lang)
    try:
        req = json.loads(request or "{}")
    except json.JSONDecodeError as e:
        raise PageError(400, f"The request is not JSON: {e}") from e
    if not isinstance(req, dict):
        raise PageError(400, "The request must be a JSON object.")
    files: dict[str, tuple[bytes, str]] = {}
    for quantity, upload in (("generation", generation), ("consumption", consumption)):
        if upload is not None and upload.filename:
            files[quantity] = (await upload.read(), upload.filename)
    names = {q: name for q, (_, name) in files.items()}
    return await _in_thread(req, files, lang, {"demo": False, "files": names})


async def _in_thread(req: dict, files: dict, lang: str, meta: dict) -> dict[str, Any]:
    """`app.run` takes seconds of CPU: off the event loop, so the page keeps its other calls."""
    from starlette.concurrency import run_in_threadpool

    return await run_in_threadpool(_run, req, files, lang, meta)


@app.post("/api/demo")
async def run_demo(lang: str = Form("en"), models: str = Form("lightgbm")) -> dict[str, Any]:
    """The demo house (`server/demo.py`), with the example price."""
    lang = _lang(lang)
    files = demo.files()
    req = {**demo.REQUEST, "models": models}
    meta = {"demo": True, "files": {q: name for q, (_, name) in files.items()}, "source": demo.INFO}
    return await _in_thread(req, files, lang, meta)


@app.get("/api/demo/{quantity}.csv")
def demo_file(quantity: str) -> Response:
    """A demo file, to see what a file the site reads looks like."""
    if quantity not in demo.COLUMNS:
        raise PageError(404, f"No demo file {quantity!r}: generation or consumption")
    return Response(
        demo.csv(quantity),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="dingle_H1_{quantity}.csv"'},
    )


@app.get("/api/result/{rid}")
def result(rid: str, lang: str = "en") -> dict[str, Any]:
    """A kept result again, in another language."""
    return _payload(rid, _lang(lang))


# ---------------------------------------------------------------------- the page (last: /api/* wins)
if (DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")


@app.get("/{path:path}", response_model=None)
def page(path: str) -> Response:
    file = (DIST / path).resolve()
    if path and file.is_file() and DIST.resolve() in file.parents:  # favicon and the like
        return FileResponse(file)
    index = DIST / "index.html"
    if not index.exists():
        return HTMLResponse(
            "<h1>The page is not built</h1><p>Run <code>npm run build</code> in <code>web/</code> "
            "(or use <code>run.cmd</code>).</p>",
            status_code=503,
        )
    # no-store: index.html names hashed assets; a cached old index would keep the old page after a build
    return FileResponse(index, headers={"Cache-Control": "no-store"})
