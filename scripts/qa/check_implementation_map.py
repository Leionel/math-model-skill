#!/usr/bin/env python3
"""Verify equation/symbol mappings point to current code and passing tests."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--implementation-map", required=True)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-objective-binding", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    map_path = resolve_path(args.implementation_map, root).resolve()
    model_path = resolve_path(args.model_contract, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    mapping, schema_errors, _ = _validate_document(
        map_path, Path(__file__).resolve().parents[2] / "schemas" / "implementation_map.schema.json"
    )
    errors.extend(f"implementation_map schema: {message}" for message in schema_errors)
    try:
        model = load_structured(model_path)
    except (OSError, ValueError, TypeError) as exc:
        errors.append(str(exc))
        model = {}
    if not isinstance(mapping, dict):
        mapping = {}
    if not isinstance(model, dict):
        errors.append("model_contract must be an object")
        model = {}

    model_ref = mapping.get("model_contract", {})
    if not isinstance(model_ref, dict) or resolve_path(str(model_ref.get("path", "")), root).resolve() != model_path:
        errors.append("implementation_map.model_contract does not point to the supplied model contract")
    elif model_ref.get("sha256") != sha256_file(model_path):
        errors.append("implementation_map.model_contract hash drift")
    if mapping.get("run_id") != model.get("run_id"):
        errors.append("implementation_map.run_id differs from model_contract.run_id")

    models = {
        row.get("model_id"): row
        for row in model.get("models", [])
        if isinstance(row, dict) and isinstance(row.get("model_id"), str)
    }
    contract_equations_by_model: dict[str, set[str]] = {}
    objective_by_model: dict[str, dict[str, Any]] = {}
    for model_id, model_row in models.items():
        details = model_row.get("plan_details") if isinstance(model_row.get("plan_details"), dict) else {}
        contract_equations_by_model[model_id] = {
            row.get("equation_id")
            for row in details.get("equation_plan", [])
            if isinstance(row, dict) and isinstance(row.get("equation_id"), str)
        }
        if isinstance(model_row.get("objective_contract"), dict):
            objective_by_model[model_id] = model_row["objective_contract"]
    questions = {row.get("question_id") for row in model.get("questions", []) if isinstance(row, dict)}
    symbols = [row for row in mapping.get("symbols", []) if isinstance(row, dict)]
    symbol_ids = [row.get("symbol_id") for row in symbols]
    if len(symbol_ids) != len(set(symbol_ids)):
        errors.append("implementation_map symbol_id values must be unique")
    symbol_set = set(symbol_ids)
    for symbol in symbols:
        if symbol.get("model_id") not in models:
            errors.append(f"symbol {symbol.get('symbol_id')} references unknown model_id {symbol.get('model_id')}")

    equations = [row for row in mapping.get("equations", []) if isinstance(row, dict)]
    equation_ids = [row.get("equation_id") for row in equations]
    if len(equation_ids) != len(set(equation_ids)):
        errors.append("implementation_map equation_id values must be unique")

    def verify_ref(owner: str, ref: Any) -> None:
        if not isinstance(ref, dict):
            errors.append(f"{owner} must be an object")
            return
        path = resolve_path(str(ref.get("path", "")), root).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"{owner} escapes project root: {ref.get('path')}")
            return
        if not path.is_file():
            errors.append(f"{owner} does not exist: {ref.get('path')}")
        elif ref.get("sha256") != sha256_file(path):
            errors.append(f"{owner} hash drift: {ref.get('path')}")
        elif isinstance(ref.get("symbol"), str):
            try:
                source_text = path.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                errors.append(f"{owner} cannot be read: {exc}")
            else:
                if ref["symbol"] not in source_text:
                    errors.append(
                        f"{owner} declares missing code symbol {ref['symbol']!r} in {ref.get('path')}"
                    )

    for equation in equations:
        equation_id = equation.get("equation_id")
        if equation.get("model_id") not in models:
            errors.append(f"equation {equation_id} references unknown model_id {equation.get('model_id')}")
        elif equation_id not in contract_equations_by_model.get(equation.get("model_id"), set()):
            errors.append(
                f"equation {equation_id} is not declared in model_contract.plan_details.equation_plan "
                f"for model {equation.get('model_id')}"
            )
        if equation.get("question_id") not in questions:
            errors.append(f"equation {equation_id} references unknown question_id {equation.get('question_id')}")
        missing_symbols = set(equation.get("symbol_ids", [])) - symbol_set
        if missing_symbols:
            errors.append(f"equation {equation_id} references unknown symbols: {sorted(missing_symbols)}")
        for index, ref in enumerate(equation.get("code_refs", [])):
            verify_ref(f"equation {equation_id} code_refs[{index}]", ref)
        for index, test in enumerate(equation.get("tests", [])):
            verify_ref(f"equation {equation_id} tests[{index}]", test)
            if isinstance(test, dict) and test.get("status") != "pass":
                errors.append(f"equation {equation_id} test {test.get('test_id')} is not PASS")
        if equation.get("kind") == "objective" and (args.require_objective_binding or equation.get("model_id") in objective_by_model):
            binding = equation.get("objective_binding")
            objective = objective_by_model.get(equation.get("model_id"), {})
            if not isinstance(binding, dict):
                errors.append(f"objective equation {equation_id} requires objective_binding")
            else:
                if binding.get("objective_id") != objective.get("objective_id"):
                    errors.append(f"objective equation {equation_id} objective_binding does not match model objective_id")
                test_by_id = {
                    row.get("test_id"): row
                    for row in equation.get("tests", [])
                    if isinstance(row, dict)
                }
                independent_ids = set(binding.get("independent_test_ids", []))
                if not independent_ids or not independent_ids.issubset(test_by_id):
                    errors.append(f"objective equation {equation_id} objective_binding references unknown tests")
                if not any(test_by_id.get(test_id, {}).get("purpose") in {"oracle", "regression"} for test_id in independent_ids):
                    errors.append(f"objective equation {equation_id} requires an oracle/regression test")
                code_paths = {row.get("path") for row in equation.get("code_refs", []) if isinstance(row, dict)}
                test_paths = {test_by_id.get(test_id, {}).get("path") for test_id in independent_ids}
                if code_paths & test_paths:
                    errors.append(f"objective equation {equation_id} oracle/regression test must be independent of code_refs")
                if binding.get("status") != "verified":
                    errors.append(f"objective equation {equation_id} objective_binding.status must be verified")
        if equation.get("status") != "verified":
            errors.append(f"equation {equation_id} status is not verified")
    if mapping.get("status") != "verified":
        errors.append("implementation_map.status must be verified")
    mapped_models = {row.get("model_id") for row in equations}
    missing_models = set(models) - mapped_models
    if missing_models:
        errors.append(f"model(s) have no mapped equation: {sorted(missing_models)}")
    mapped_equations_by_model: dict[str, set[str]] = {}
    for row in equations:
        if isinstance(row.get("model_id"), str) and isinstance(row.get("equation_id"), str):
            mapped_equations_by_model.setdefault(row["model_id"], set()).add(row["equation_id"])
    for model_id, declared_equations in contract_equations_by_model.items():
        missing_equations = sorted(declared_equations - mapped_equations_by_model.get(model_id, set()))
        if missing_equations:
            errors.append(
                f"model {model_id} has contract equations with no implementation mapping: {missing_equations}"
            )

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "implementation_map": rel_path(map_path, root),
        "model_contract": rel_path(model_path, root),
        "equations": len(equations),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
