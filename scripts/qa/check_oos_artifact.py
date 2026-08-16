#!/usr/bin/env python3
"""Validate an independent train/test scenario artifact."""

from __future__ import annotations

import argparse
import csv
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


def _load_membership_rows(ref: dict[str, Any], root: Path, label: str, errors: list[str]) -> list[dict[str, Any]]:
    """Load a small, reviewable membership artifact without trusting summary fields."""

    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        errors.append(f"{label} must contain a path")
        return []
    path = resolve_path(ref["path"], root).resolve()
    if not path.is_file():
        errors.append(f"{label} does not exist: {ref['path']}")
        return []
    supplied = ref.get("sha256")
    if supplied is not None and supplied != sha256_file(path):
        errors.append(f"{label} sha256 drift")
    try:
        if path.suffix.casefold() == ".csv":
            with path.open("r", encoding="utf-8-sig", newline="") as handle:
                return [dict(row) for row in csv.DictReader(handle)]
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(f"{label} cannot be parsed as CSV/JSON: {exc}")
        return []
    if isinstance(payload, dict):
        rows = payload.get("rows", payload.get("keys", []))
    else:
        rows = payload
    if not isinstance(rows, list):
        errors.append(f"{label} must contain a list or an object with rows/keys")
        return []
    normalized: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            normalized.append(row)
        elif isinstance(row, list):
            normalized.append({str(index): value for index, value in enumerate(row)})
        else:
            normalized.append({"value": row})
    return normalized


def _membership_key(row: dict[str, Any], columns: list[str]) -> tuple[str, ...] | None:
    values = []
    for column in columns:
        if column not in row:
            return None
        values.append(str(row[column]))
    return tuple(values)


def _time_key(row: dict[str, Any], column: str) -> tuple[int, object]:
    value = row.get(column)
    text = str(value)
    try:
        return (0, float(text))
    except (TypeError, ValueError):
        return (1, text)


def _check_membership(artifact: dict[str, Any], root: Path, errors: list[str]) -> None:
    mode = artifact.get("split_mode", "scenario")
    membership = artifact.get("membership")
    if mode == "scenario":
        return
    if not isinstance(membership, dict):
        errors.append(f"split_mode={mode} requires a membership artifact")
        return
    key_columns = membership.get("key_columns", [])
    if not isinstance(key_columns, list) or not key_columns:
        errors.append("membership.key_columns must be non-empty")
        return
    train_rows = _load_membership_rows(membership.get("train"), root, "membership.train", errors)
    test_rows = _load_membership_rows(membership.get("test"), root, "membership.test", errors)
    if isinstance(membership.get("train_count"), int) and membership["train_count"] != len(train_rows):
        errors.append("membership.train_count does not match the loaded train membership")
    if isinstance(membership.get("test_count"), int) and membership["test_count"] != len(test_rows):
        errors.append("membership.test_count does not match the loaded test membership")
    train_keys = set()
    test_keys = set()
    for label, rows, target in (("train", train_rows, train_keys), ("test", test_rows, test_keys)):
        for index, row in enumerate(rows):
            key = _membership_key(row, key_columns)
            if key is None:
                errors.append(f"membership.{label}[{index}] is missing one of key_columns {key_columns}")
            else:
                target.add(key)
    if train_keys & test_keys:
        errors.append(f"membership train/test key overlap detected: {len(train_keys & test_keys)}")

    time_column = membership.get("time_column")
    if mode in {"time", "entity_time"} and not isinstance(time_column, str):
        errors.append(f"split_mode={mode} requires membership.time_column")
    if isinstance(time_column, str) and time_column:
        missing = [label for label, rows in (("train", train_rows), ("test", test_rows)) if any(time_column not in row for row in rows)]
        if missing:
            errors.append(f"membership time_column {time_column!r} is missing from {missing}")
        elif train_rows and test_rows:
            train_max = max(_time_key(row, time_column) for row in train_rows)
            test_min = min(_time_key(row, time_column) for row in test_rows)
            if train_max >= test_min:
                errors.append("membership time order is invalid: max(train_time) must be before min(test_time)")


def evaluate_oos(
    artifact: dict[str, Any],
    root: Path,
    expected_run_id: str | None = None,
    require_design: bool = False,
) -> list[str]:
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
    if require_design and not isinstance(artifact.get("split_mode"), str):
        errors.append("split_mode must be explicitly declared for formal OOS QA")
    _check_ref(artifact.get("metrics_artifact"), root, "metrics_artifact", errors)
    _check_membership(artifact, root, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-design", action="store_true")
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
            errors.extend(evaluate_oos(artifact, root, args.run_id, args.require_design))
        else:
            errors.append("OOS artifact must be an object")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    ok = not errors
    print(json.dumps({"ok": ok, "artifact": rel_path(artifact_path, root), "errors": errors, "warnings": []}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
