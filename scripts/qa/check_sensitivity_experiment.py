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


def evaluate_experiment(
    experiment: dict[str, Any],
    root: Path,
    expected_run_id: str | None = None,
    *,
    require_execution_receipts: bool = False,
    model_contract: dict[str, Any] | None = None,
    require_parameter_binding: bool = False,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if expected_run_id is not None and experiment.get("run_id") != expected_run_id:
        errors.append(f"experiment run_id {experiment.get('run_id')!r} does not match {expected_run_id!r}")
    if experiment.get("status") != "completed":
        errors.append("sensitivity experiment must have status=completed before it supports a claim")
    parameter_id = experiment.get("parameter_id")
    if require_parameter_binding:
        if not isinstance(parameter_id, str) or not parameter_id:
            errors.append("sensitivity experiment requires parameter_id for formal parameter binding")
        if not isinstance(model_contract, dict):
            errors.append("formal parameter binding requires model_contract")
    if isinstance(model_contract, dict) and isinstance(parameter_id, str):
        model_rows = {
            row.get("model_id"): row
            for row in model_contract.get("models", [])
            if isinstance(row, dict) and isinstance(row.get("model_id"), str)
        }
        model_id = experiment.get("model_id")
        if model_id not in model_rows:
            errors.append(f"sensitivity experiment model_id {model_id!r} is absent from model_contract")
        else:
            parameter_rows = []
            details = model_rows[model_id].get("plan_details")
            if isinstance(details, dict):
                parameter_rows = [row for row in details.get("parameter_plan", []) if isinstance(row, dict)]
            matches = [row for row in parameter_rows if row.get("parameter_id") == parameter_id]
            if len(matches) != 1:
                errors.append(f"sensitivity parameter_id {parameter_id!r} does not uniquely match model parameter_plan")
            else:
                parameter = matches[0]
                if parameter.get("parameter") != experiment.get("parameter"):
                    errors.append("sensitivity experiment.parameter differs from the bound model parameter")
                linked = parameter.get("sensitivity_experiment_ids", [])
                if experiment.get("experiment_id") not in linked:
                    errors.append("bound model parameter does not list this sensitivity experiment_id")
                if experiment.get("impact_class") and parameter.get("impact_class") != experiment.get("impact_class"):
                    errors.append("sensitivity impact_class differs from the bound model parameter")
    if experiment.get("rerun_policy") == "other" and not experiment.get("rerun_policy_detail"):
        errors.append("rerun_policy=other requires rerun_policy_detail")
    grid = experiment.get("grid", [])
    runs = experiment.get("runs", [])
    grid_values = {float(value) for value in grid if isinstance(value, (int, float)) and not isinstance(value, bool)}
    run_values = {float(row.get("grid_value")) for row in runs if isinstance(row, dict) and isinstance(row.get("grid_value"), (int, float))}
    if grid_values != run_values:
        errors.append(f"sensitivity grid values and run receipts differ: grid={sorted(grid_values)}, runs={sorted(run_values)}")
    artifact_paths: set[str] = set()
    receipt_paths: set[str] = set()
    for index, row in enumerate(runs):
        if not isinstance(row, dict):
            continue
        _check_ref(row.get("artifact"), root, f"runs[{index}].artifact", errors)
        artifact = row.get("artifact")
        if isinstance(artifact, dict) and isinstance(artifact.get("path"), str):
            if artifact["path"] in artifact_paths:
                errors.append(f"runs[{index}].artifact path is reused; each grid point needs its own output artifact")
            artifact_paths.add(artifact["path"])
        if require_execution_receipts:
            execution = row.get("execution")
            if not isinstance(execution, dict):
                errors.append(f"runs[{index}].execution is required for a real rerun claim")
                continue
            if row.get("status") != "PASS":
                errors.append(f"runs[{index}] must have status=PASS before a sensitivity claim is promoted")
            if execution.get("status") != "completed":
                errors.append(f"runs[{index}].execution.status must be completed")
            if execution.get("exit_code") != 0:
                errors.append(f"runs[{index}].execution.exit_code must be 0 for a PASS run")
            if not isinstance(execution.get("command"), list) or not execution.get("command"):
                errors.append(f"runs[{index}].execution.command must be a non-empty command vector")
            if execution.get("input_parameter") != experiment.get("parameter"):
                errors.append(f"runs[{index}].execution.input_parameter must match experiment.parameter")
            try:
                if abs(float(execution.get("input_value")) - float(row.get("grid_value"))) > 1e-12:
                    errors.append(f"runs[{index}].execution.input_value must match grid_value")
            except (TypeError, ValueError):
                errors.append(f"runs[{index}].execution.input_value must be numeric")
            if not isinstance(execution.get("started_at"), str) or not isinstance(execution.get("finished_at"), str):
                errors.append(f"runs[{index}].execution must record started_at and finished_at")
            receipt = execution.get("receipt")
            _check_ref(receipt, root, f"runs[{index}].execution.receipt", errors)
            if isinstance(receipt, dict) and isinstance(receipt.get("path"), str):
                if receipt["path"] in receipt_paths:
                    errors.append(f"runs[{index}].execution.receipt path is reused")
                receipt_paths.add(receipt["path"])
            if isinstance(artifact, dict) and isinstance(artifact.get("path"), str) and isinstance(receipt, dict) and artifact.get("path") == receipt.get("path"):
                errors.append(f"runs[{index}] execution receipt must be separate from the result artifact")
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
    parser.add_argument("--require-execution-receipts", action="store_true")
    parser.add_argument("--model-contract")
    parser.add_argument("--require-parameter-binding", action="store_true")
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
            model_contract = None
            if args.model_contract:
                model_contract = json.loads(resolve_path(args.model_contract, root).resolve().read_text(encoding="utf-8"))
            semantic_errors, semantic_warnings = evaluate_experiment(
                experiment,
                root,
                args.run_id,
                require_execution_receipts=args.require_execution_receipts,
                model_contract=model_contract,
                require_parameter_binding=args.require_parameter_binding,
            )
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
