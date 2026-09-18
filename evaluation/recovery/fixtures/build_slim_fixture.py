"""Rebuild the recovery benchmark's slim v2 fixture from the demo lifecycle.

The fixture is the demo project (S0 init -> M1 -> P1 -> P2 -> W1/W2) generated
through the same ``harness`` CLI steps as ``examples/end_to_end/run_demo.py``,
then pinned under ``evaluation/recovery/fixtures/slim_v2/``.  Nothing here
writes a Gate verdict, receipt or hash by hand; regeneration reruns the real
producers and the committed bytes change only through them.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "examples" / "end_to_end"))

import run_demo  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="target directory for the fixture project (must be empty or absent)")
    args = parser.parse_args()
    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"target is not empty: {out}")
    run_demo.build(run_demo.Demo(out, verbose=True))
    print(f"fixture written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
