#!/usr/bin/env python3
"""Validate an independent train/test scenario artifact."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path, sha256_file  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


def _check_ref(ref: Any, root: Path, label: str, errors: list[str]) -> None:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref["path"]:
        errors.append(f"{label} must contain a non-empty path")
        return
    path = resolve_path(ref["path"], root).resolve()
    if not path.is_file():
        errors.append(f"{label} does not exist: {ref['path']}")
        return
    supplied = ref.get("sha256")
    if supplied is not None and supplied != sha256_file(path):
        errors.append(f"{label} sha256 drift")


def evaluate_oos(artifact: dict[str, Any], root: Path, expected_run_id: str | None = None) -> list[str]:
    errors: list[str] = []
    if expected_run_id is not None and artifact.get("run_id") != expected_run_id:
        errors.append(f"oos artifact run_id {artifact.get('run_id')!r} does not match {expected_run_id!r}")
    train = artifact.get("train_scenarios", {})
    test = artifact.get("test_scenarios", {})
    if train.get("hash") == test.get("hash"):
        errors.append("train_scenarios.hash and test_scenarios.hash must differ")
    if train.get("seed") == test.get("seed"):
        errors.append("train_scenarios.seed and test_scenarios.seed must differ")
    if artifact.get("disjoint_check") != "PASS":
        errors.append("disjoint_check must be PASS")
    if artifact.get("leakage_check") != "PASS":
        errors.append("leakage_check must be PASS")
    _check_ref(artifact.get("metrics_artifact"), root, "metrics_artifact", errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    artifact_path = resolve_path(args.artifact, root).resolve()
    errors: list[str] = []
    try:
        artifact, schema_errors, _ = _validate_document(
            artifact_path, Path(__file__).resolve().parents[2] / "schemas" / "oos_artifact.schema.json"
        )
        errors.extend(f"OOS artifact schema: {message}" for message in schema_errors)
        if isinstance(artifact, dict):
            errors.extend(evaluate_oos(artifact, root, args.run_id))
        else:
            errors.append("OOS artifact must be an object")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    ok = not errors
    print(json.dumps({"ok": ok, "artifact": rel_path(artifact_path, root), "errors": errors, "warnings": []}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
