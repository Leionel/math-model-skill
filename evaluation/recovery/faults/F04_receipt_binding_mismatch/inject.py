#!/usr/bin/env python3
"""Inject F04: repoint the frozen result's receipt binding at the smoke receipt."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    root = Path(args.project_root)
    frozen_path = root / "frozen_results.json"
    index_path = root / "run_index.json"
    if not frozen_path.is_file() or not index_path.is_file():
        print(json.dumps({"ok": False, "fault_id": "F04", "errors": ["frozen_results.json or run_index.json missing; wrong fixture?"]}, ensure_ascii=False))
        return 2
    frozen = json.loads(frozen_path.read_text(encoding="utf-8"))
    index = json.loads(index_path.read_text(encoding="utf-8"))
    smoke = next((row["receipt_id"] for row in index.get("receipts", []) if row.get("stage") == "smoke"), None)
    if smoke is None:
        print(json.dumps({"ok": False, "fault_id": "F04", "errors": ["no smoke receipt in run_index"]}, ensure_ascii=False))
        return 2
    if not str(frozen.get("command", "")).startswith("receipt:"):
        print(json.dumps({"ok": False, "fault_id": "F04", "errors": ["frozen_results.command is not a receipt binding"]}, ensure_ascii=False))
        return 2
    frozen["command"] = f"receipt:{smoke}"
    frozen_path.write_text(json.dumps(frozen, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "fault_id": "F04", "mutations": [{"path": "frozen_results.json", "field": "command", "value": f"receipt:{smoke}"}]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
