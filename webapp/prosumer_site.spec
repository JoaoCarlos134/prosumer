# PyInstaller spec of the standalone site: a folder `dist/prosumer/` that runs by itself (double-click
# `prosumer.exe`), carrying Python, the library, the server and the built page. Build with build_exe.cmd
# (Windows) or `pyinstaller --noconfirm prosumer_site.spec` from webapp/ after `npm run build` in web/.
# PyInstaller does not cross-compile: a Windows exe is built on Windows.
# Left out on purpose: torch and the foundation models (gigabytes); `models: "all"` then notes them as not
# installed, as the library does anywhere they are missing.
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules, copy_metadata

HERE = Path(SPECPATH)
if not (HERE / "web" / "dist" / "index.html").exists():
    raise SystemExit("Build the page first: cd web && npm ci && npm run build")

datas = [
    (str(HERE / "web" / "dist"), "web/dist"),
    (str(HERE / "server" / "demo"), "server/demo"),
]
binaries = []
hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
    "multipart",
    *collect_submodules("prosumer"),  # modules the library imports lazily (readers, forecasters, i18n)
]
datas += copy_metadata("prosumer")  # its __version__ comes from importlib.metadata
for package in ("pandera", "lightgbm", "sklearn", "scipy", "tzdata", "openpyxl", "truststore"):
    try:
        d, b, h = collect_all(package)
    except Exception:  # an optional extra not installed: the library notes it at run time
        continue
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    [str(HERE / "server" / "launch.py")],
    pathex=[str(HERE)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["torch", "tensorflow", "matplotlib", "IPython", "tkinter", "pytest", "chronos", "tirex", "toto", "tsfm_public", "timesfm"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="prosumer",
    console=True,  # the window says where the site is and closing it stops the site
    icon=None,
)
coll = COLLECT(exe, a.binaries, a.datas, name="prosumer")
