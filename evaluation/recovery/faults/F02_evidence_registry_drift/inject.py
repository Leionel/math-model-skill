#!/usr/bin/env python3
"""Inject F02: edit the evidence registry in place (bytes change, schema stays valid)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ORIGINAL = "declared demand, capacities and unit costs only"
EDITED = "declared demand, capacities and unit costs only (edited)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    path = Path(args.project_root) / "evidence_registry.json"
    if not path.is_file():
        print(json.dumps({"ok": False, "fault_id": "F02", "errors": ["evidence_registry.json missing; wrong fixture?"]}, ensure_ascii=False))
        return 2
    text = path.read_text(encoding="utf-8")
    if ORIGINAL not in text:
        print(json.dumps({"ok": False, "fault_id": "F02", "errors": ["expected boundary text not found; wrong fixture?"]}, ensure_ascii=False))
        return 2
    path.write_text(text.replace(ORIGINAL, EDITED), encoding="utf-8")
    print(json.dumps({"ok": True, "fault_id": "F02", "mutations": [{"path": "evidence_registry.json", "field": "evidence[0].boundary"}]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
