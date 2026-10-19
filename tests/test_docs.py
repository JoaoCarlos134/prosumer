"""The user guide's examples run: every ```python block of docs/library, in page order, one namespace per
page.

A block whose first line is `# network` is shown, not run (it downloads); `# needs: <module>` skips the page's
remaining blocks when that module is not installed. Run from the repository root, as the examples' paths are.
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted((ROOT / "docs" / "library").rglob("*.md"))
BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)


def test_there_are_pages_with_examples() -> None:
    assert len(PAGES) >= 8
    assert sum(len(BLOCK.findall(p.read_text(encoding="utf-8"))) for p in PAGES) >= 10


@pytest.mark.parametrize("page", PAGES, ids=lambda p: p.relative_to(ROOT / "docs" / "library").as_posix())
def test_examples_of_the_page_run(page: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(ROOT)
    namespace: dict[str, object] = {"__name__": f"docs_{page.stem}"}
    ran = 0
    for code in BLOCK.findall(page.read_text(encoding="utf-8")):
        first = code.strip().splitlines()[0] if code.strip() else ""
        if first.startswith("# network"):
            compile(code, f"{page.name} (network block)", "exec")  # still valid Python
            continue
        need = re.match(r"# needs: (\w+)", first)
        if need and importlib.util.find_spec(need.group(1)) is None:
            pytest.skip(f"{page.name}: needs {need.group(1)}")
        exec(compile(code, str(page), "exec"), namespace)  # the guide's own examples
        ran += 1
    if not ran:
        pytest.skip(f"{page.name} has no runnable example")
