"""Compile C and run it, on a machine where Smart App Control blocks every locally built .exe.

The C goes to WebAssembly (WASI) with zig (`pip install ziglang`) and runs under Node.js (signed, allowed):
single-precision float in WebAssembly is IEEE 754 binary32, the arithmetic of the ESP32 FPU. Used by
`tests/test_embedded.py` and by the embedded pilot to check that the exported header reproduces Python.
Each program reads `/w/in.bin` (float32) and writes `/w/out.bin` (float32) in a temporary folder.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

RUNNER = """import { readFileSync } from "node:fs";
import { WASI } from "node:wasi";
const wasi = new WASI({ version: "preview1", args: [], env: {}, preopens: { "/w": process.argv[3] } });
const mod = await WebAssembly.compile(readFileSync(process.argv[2]));
const inst = await WebAssembly.instantiate(mod, wasi.getImportObject());
process.exitCode = wasi.start(inst);
"""

# Reads n floats of input and writes m floats of output; the caller writes `void run(const float *in,
# long n_in, float *out)` and says how many outputs.
MAIN = """
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    FILE *f = fopen("/w/in.bin", "rb");
    if (!f) return 2;
    fseek(f, 0, SEEK_END); long n = ftell(f) / 4; fseek(f, 0, SEEK_SET);
    float *in = malloc(n * 4 + 4);
    if (fread(in, 4, n, f) != (size_t)n) return 3;
    fclose(f);
    float *out = malloc(N_OUT * 4 + 4);
    run(in, n, out);
    FILE *g = fopen("/w/out.bin", "wb");
    fwrite(out, 4, N_OUT, g);
    fclose(g);
    return 0;
}
"""


def zig() -> list[str] | None:
    try:
        import ziglang  # noqa: F401
    except ImportError:
        exe = shutil.which("zig")
        return [exe] if exe else None
    return [sys.executable, "-m", "ziglang"]


def available() -> bool:
    return zig() is not None and shutil.which("node") is not None


def run(source: str, inputs: np.ndarray, n_out: int, *, headers: dict[str, str] | None = None) -> np.ndarray:
    """Compile `source` (which defines `run`) with the main above and return its float32 outputs."""
    z = zig()
    node = shutil.which("node")
    if z is None or node is None:
        raise RuntimeError("needs zig (pip install ziglang) and node")
    with tempfile.TemporaryDirectory() as tmp:
        d = Path(tmp)
        for name, text in (headers or {}).items():
            (d / name).write_text(text, encoding="utf-8")
        (d / "prog.c").write_text(f"#define N_OUT {n_out}\n{source}\n{MAIN}", encoding="utf-8")
        (d / "run.mjs").write_text(RUNNER, encoding="utf-8")
        np.asarray(inputs, dtype="<f4").tofile(d / "in.bin")
        cmd = [*z, "cc", "-target", "wasm32-wasi", "-O2", "-std=c99", "-Wall", "-o", str(d / "prog.wasm")]
        subprocess.run([*cmd, str(d / "prog.c"), "-lm"], check=True, capture_output=True, cwd=d)
        r = subprocess.run(
            [node, "--no-warnings", str(d / "run.mjs"), str(d / "prog.wasm"), str(d)],
            capture_output=True,
            text=True,
        )
        if r.returncode != 0:
            raise RuntimeError(f"program failed ({r.returncode}): {r.stderr}")
        return np.fromfile(d / "out.bin", dtype="<f4").astype(float)
