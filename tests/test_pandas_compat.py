"""Names pandas has deprecated, kept out of the library's code.

pandas 3.1 deprecates `dayofweek` and `dayofyear` (Series.dt, DatetimeIndex, Timestamp) for `day_of_week` and
`day_of_year` (both there since pandas 1.1). Found on 2026-10-23: the site's tests ran `app.run` on pandas 3.1
and the warning, an error under this suite's `filterwarnings`, came out of `outlook`, `lightgbm`, `physics`...
A scan of the source catches them on any pandas, not only the one that warns (the tests and the site's server
too: their warnings are not errors here, but pandas 4 removes the names).
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEPRECATED = re.compile(r"\.(dayofweek|dayofyear|weekofyear|daysinmonth)\b")


def test_the_library_uses_no_pandas_name_deprecated_in_pandas_3_1() -> None:
    hits = [
        f"{p.relative_to(ROOT)}:{n}: {line.strip()}"
        for folder in ("src", "examples", "tests", "webapp/server", "webapp/tests")
        for p in sorted((ROOT / folder).rglob("*.py"))
        if p.name != "test_pandas_compat.py"
        for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if DEPRECATED.search(line)
    ]
    assert not hits, "\n".join(hits)
