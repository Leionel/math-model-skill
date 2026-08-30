#!/usr/bin/env python3
"""Audit textual schema-file references across scripts and tests.

For every schemas/*.schema.json, find the scripts and tests that reference
the schema file by name. This is a static inventory: a reference does not
prove that a runtime path executes the validator. The report identifies
schemas that need a deliberate dynamic-consumption review without claiming
call-graph coverage.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path  # noqa: E402

GATE_SURFACE = {
    "scripts/qa/check_gates.py",
    "scripts/v2_gate_runtime.py",
    "scripts/qa/run_deterministic_qa.py",
    "scripts/qa/validate_contracts.py",
}


def _read_sources(root: Path, pattern: str) -> dict[str, str]:
    sources: dict[str, str] = {}
    for path in sorted(root.glob(pattern)):
        sources[rel_path(path, root).replace("\\", "/")] = path.read_text(encoding="utf-8", errors="replace")
    return sources


def audit_contract_consumption(root: Path) -> dict[str, object]:
    schema_dir = root / "schemas"
    if not schema_dir.is_dir():
        return {"ok": False, "errors": [f"schema directory does not exist: {rel_path(schema_dir, root)}"], "warnings": [], "schemas": []}
    scripts = _read_sources(root, "scripts/**/*.py")
    tests = _read_sources(root, "tests/**/*.py")
    warnings: list[str] = []
    rows = []
    for schema_path in sorted(schema_dir.glob("*.schema.json")):
        name = schema_path.name
        script_consumers = sorted(path for path, text in scripts.items() if name in text)
        test_consumers = sorted(path for path, text in tests.items() if name in text)
        orphan = not script_consumers and not test_consumers
        test_only = bool(test_consumers) and not script_consumers
        gate_surface_referenced = any(consumer in GATE_SURFACE for consumer in script_consumers)
        if orphan:
            warnings.append(f"schemas/{name} has no textual consumer reference; inspect, wire, or delete it deliberately")
        elif test_only:
            warnings.append(
                f"schemas/{name} is referenced only in tests ({', '.join(test_consumers)}); no script names it"
            )
        rows.append(
            {
                "schema": f"schemas/{name}",
                "script_consumers": script_consumers,
                "test_consumers": test_consumers,
                "gate_surface_referenced": gate_surface_referenced,
                "gate_wired": gate_surface_referenced,
                "orphan": orphan,
                "test_only": test_only,
            }
        )
    summary = {
        "total": len(rows),
        "orphan": sum(1 for row in rows if row["orphan"]),
        "test_only": sum(1 for row in rows if row["test_only"]),
        "gate_wired": sum(1 for row in rows if row["gate_wired"]),
    }
    return {
        "ok": True,
        "errors": [],
        "warnings": warnings,
        "method": "textual_schema_filename_reference",
        "boundary": "References are not dynamic execution or call-graph evidence.",
        "summary": summary,
        "schemas": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--strict", action="store_true", help="treat orphan/test-only schemas as failures")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    report = audit_contract_consumption(root)
    ok = bool(report["ok"]) and not report["errors"] and (not args.strict or not report["warnings"])
    report["ok"] = ok
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
