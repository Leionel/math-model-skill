"""Build the recovery benchmark's slim v2 fixture from the demo lifecycle.

The fixture is the demo project (S0 init -> M1 -> P1 -> P2 -> W1/W2) generated
through the same ``harness`` CLI steps as ``examples/end_to_end/run_demo.py``.
It is built per evaluation run rather than committed: review evidence binds the
absolute project path and every digest is computed over exact file bytes, so a
checked-in tree would read as stale the moment it lands anywhere else (and
line-ending normalization alone would break it).  This mirrors how
``evaluation/redteam.py`` builds one baseline and clones it for each attack.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "examples" / "end_to_end"))

import run_demo  # noqa: E402


def build(target: Path, *, verbose: bool = False) -> Path:
    """Materialize one green slim fixture at ``target`` and return its root."""

    if target.exists() and any(target.iterdir()):
        raise ValueError(f"fixture target is not empty: {target}")
    run_demo.build(run_demo.Demo(target, verbose=verbose))
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="target directory for the fixture project (must be empty or absent)")
    parser.add_argument("--verbose", action="store_true", help="print every harness step as it runs")
    args = parser.parse_args()
    build(Path(args.out).resolve(), verbose=args.verbose)
    print(f"fixture written to {Path(args.out).resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
