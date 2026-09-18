#!/usr/bin/env python3
"""Inject F03: delete the frozen results file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    path = Path(args.project_root) / "frozen_results.json"
    if not path.is_file():
        print(json.dumps({"ok": False, "fault_id": "F03", "errors": ["frozen_results.json already absent; wrong fixture?"]}, ensure_ascii=False))
        return 2
    path.unlink()
    print(json.dumps({"ok": True, "fault_id": "F03", "mutations": [{"path": "frozen_results.json", "action": "deleted"}]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
