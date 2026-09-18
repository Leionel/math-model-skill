#!/usr/bin/env python3
"""Inject F01: edit the model contract in place (bytes change, schema stays valid)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ORIGINAL = "SI counts with CNY for cost"
EDITED = "SI counts with CNY for cost (edited)"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    path = Path(args.project_root) / "model_contract.json"
    if not path.is_file():
        print(json.dumps({"ok": False, "fault_id": "F01", "errors": ["model_contract.json missing; wrong fixture?"]}, ensure_ascii=False))
        return 2
    text = path.read_text(encoding="utf-8")
    if ORIGINAL not in text:
        print(json.dumps({"ok": False, "fault_id": "F01", "errors": ["expected unit_system text not found; wrong fixture?"]}, ensure_ascii=False))
        return 2
    path.write_text(text.replace(ORIGINAL, EDITED), encoding="utf-8")
    print(json.dumps({"ok": True, "fault_id": "F01", "mutations": [{"path": "model_contract.json", "field": "unit_system"}]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
