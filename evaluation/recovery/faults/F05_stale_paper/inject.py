#!/usr/bin/env python3
"""Inject F05: append a section to the paper without re-reviewing it."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    path = Path(args.project_root) / "paper.txt"
    if not path.is_file():
        print(json.dumps({"ok": False, "fault_id": "F05", "errors": ["paper.txt missing; wrong fixture?"]}, ensure_ascii=False))
        return 2
    path.write_text(path.read_text(encoding="utf-8") + "Extra section appended without re-review.\n", encoding="utf-8")
    print(json.dumps({"ok": True, "fault_id": "F05", "mutations": [{"path": "paper.txt", "action": "appended section"}]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
