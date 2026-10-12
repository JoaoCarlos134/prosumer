"""Shared HTTP transport for the readers that download (standard library only).

`truststore`, when installed (extra `net`), makes the downloads work behind proxies that inspect TLS with the
system certificates (the Lactec network). Every public reader takes an injectable getter, so nothing that
uses this module needs the network to be tested.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


def ssl_context() -> ssl.SSLContext | None:  # pragma: no cover - depends on the machine
    try:
        import truststore
    except ImportError:
        return None
    ctx: ssl.SSLContext = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    return ctx


def get_bytes(url: str, *, tries: int = 3, timeout: float = 300.0) -> bytes:  # pragma: no cover - network
    """GET `url` and return the body, retrying network errors with a growing pause."""
    ctx = ssl_context()
    for k in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout, context=ctx) as r:
                body: bytes = r.read()
            return body
        except urllib.error.HTTPError as e:
            if e.code < 500 or k == tries - 1:  # a bad request does not get better by asking again
                detail = e.read().decode("utf-8", "replace")[:500]
                raise RuntimeError(f"HTTP {e.code} from {url.split('?')[0]}: {detail}") from e
            time.sleep(5 * (k + 1))
        except (OSError, TimeoutError):
            if k == tries - 1:
                raise
            time.sleep(5 * (k + 1))
    raise AssertionError("unreachable")


def get_json(url: str, params: dict[str, Any], **kwargs: Any) -> dict[str, Any]:  # pragma: no cover
    """GET `url?params` and decode the JSON body."""
    data: dict[str, Any] = json.loads(get_bytes(url + "?" + urllib.parse.urlencode(params), **kwargs))
    return data
