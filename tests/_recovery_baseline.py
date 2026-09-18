"""One built slim fixture per test process, cloned by each recovery test.

Building the fixture runs the whole demo lifecycle, so it happens once per
process and every test copies the result — the same baseline-and-clone shape
``evaluation/redteam.py`` uses.  The fixture is never committed: its review
evidence binds absolute paths and its digests are exact-byte facts.
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "evaluation" / "recovery" / "fixtures"))

import build_slim_fixture  # noqa: E402

_CACHE: dict[str, object] = {}


def built_fixture() -> Path:
    if "root" not in _CACHE:
        holder = tempfile.TemporaryDirectory(prefix="recovery-baseline-")
        target = Path(holder.name) / "slim_v2"
        with contextlib.redirect_stdout(io.StringIO()):
            build_slim_fixture.build(target)
        # Keep the TemporaryDirectory referenced so it outlives this call.
        _CACHE["holder"] = holder
        _CACHE["root"] = target
    return _CACHE["root"]  # type: ignore[no-any-return]
