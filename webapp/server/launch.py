"""Start the site in this process: the standalone folder's entry point (`prosumer.exe`), also `python -m
server.launch` from `webapp/`.

Takes the first free port from 8080, serves `server.api.app` with uvicorn and opens the browser once the
server answers. The window stays open while the site runs: closing it stops the site.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import urllib.request
import webbrowser

import uvicorn

from server.api import app

HOST = "127.0.0.1"
FIRST_PORT = 8080


def free_port(first: int = FIRST_PORT, tries: int = 50) -> int:
    """The first port from `first` nobody listens on."""
    for port in range(first, first + tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((HOST, port))
            except OSError:
                continue
            return port
    raise SystemExit(f"No free port between {first} and {first + tries - 1}.")


def _open_when_up(url: str, timeout: float = 60.0) -> None:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            with urllib.request.urlopen(f"{url}/api/info", timeout=2):
                break
        except OSError:
            time.sleep(0.3)
    webbrowser.open(url)


def main() -> None:
    port = free_port()
    url = f"http://{HOST}:{port}"
    print(f"prosumer site: {url}\nClose this window to stop it.", flush=True)
    if "--no-browser" not in sys.argv:
        threading.Thread(target=_open_when_up, args=(url,), daemon=True).start()
    uvicorn.run(app, host=HOST, port=port, log_level="warning")


if __name__ == "__main__":
    main()
