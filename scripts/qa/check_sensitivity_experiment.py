#!/usr/bin/env python3
"""Validate that a sensitivity claim is backed by a real rerun artifact."""

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


def evaluate_experiment(experiment: dict[str, Any], root: Path, expected_run_id: str | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if expected_run_id is not None and experiment.get("run_id") != expected_run_id:
        errors.append(f"experiment run_id {experiment.get('run_id')!r} does not match {expected_run_id!r}")
    if experiment.get("status") != "completed":
        errors.append("sensitivity experiment must have status=completed before it supports a claim")
    if experiment.get("rerun_policy") == "other" and not experiment.get("rerun_policy_detail"):
        errors.append("rerun_policy=other requires rerun_policy_detail")
    grid = experiment.get("grid", [])
    runs = experiment.get("runs", [])
    grid_values = {float(value) for value in grid if isinstance(value, (int, float)) and not isinstance(value, bool)}
    run_values = {float(row.get("grid_value")) for row in runs if isinstance(row, dict) and isinstance(row.get("grid_value"), (int, float))}
    if grid_values != run_values:
        errors.append(f"sensitivity grid values and run receipts differ: grid={sorted(grid_values)}, runs={sorted(run_values)}")
    for index, row in enumerate(runs):
        if not isinstance(row, dict):
            continue
        _check_ref(row.get("artifact"), root, f"runs[{index}].artifact", errors)
    _check_ref(experiment.get("results_artifact"), root, "results_artifact", errors)
    for metric in experiment.get("metrics", []):
        if isinstance(metric, dict) and metric.get("metric_id") == "solution_similarity" and not metric.get("similarity_definition"):
            errors.append("solution_similarity requires similarity_definition")
    if len(grid_values) < 2:
        errors.append("sensitivity experiment requires at least two distinct grid values")
    if experiment.get("baseline") not in grid:
        warnings.append("baseline is not one of the declared grid values; confirm this is intentional")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    experiment_path = resolve_path(args.experiment, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        experiment, schema_errors, _ = _validate_document(
            experiment_path, Path(__file__).resolve().parents[2] / "schemas" / "sensitivity_experiment.schema.json"
        )
        errors.extend(f"sensitivity experiment schema: {message}" for message in schema_errors)
        if isinstance(experiment, dict):
            semantic_errors, semantic_warnings = evaluate_experiment(experiment, root, args.run_id)
            errors.extend(semantic_errors)
            warnings.extend(semantic_warnings)
        else:
            errors.append("sensitivity experiment must be an object")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({"ok": ok, "experiment": rel_path(experiment_path, root), "errors": errors, "warnings": warnings}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
