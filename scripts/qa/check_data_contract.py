#!/usr/bin/env python3
"""Validate dataset semantics, file identity, invariants, and leakage status."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-contract", required=True)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    contract_path = resolve_path(args.data_contract, root).resolve()
    model_path = resolve_path(args.model_contract, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    contract, schema_errors, _ = _validate_document(
        contract_path, Path(__file__).resolve().parents[2] / "schemas" / "data_contract.schema.json"
    )
    errors.extend(f"data_contract schema: {message}" for message in schema_errors)
    try:
        model = load_structured(model_path)
    except (OSError, ValueError, TypeError) as exc:
        errors.append(str(exc))
        model = {}
    if not isinstance(contract, dict):
        contract = {}
    if not isinstance(model, dict):
        errors.append("model_contract must be an object")
        model = {}

    source = contract.get("source", {})
    source_path = resolve_path(str(source.get("path", "")), root).resolve() if isinstance(source, dict) else None
    if source_path is None or not source_path.is_file():
        errors.append(f"data source does not exist: {source.get('path') if isinstance(source, dict) else None}")
    elif source.get("sha256") != sha256_file(source_path):
        errors.append(f"data source hash drift: {source.get('path')}")

    model_sources = {
        row.get("data_id"): row
        for row in model.get("data_sources", [])
        if isinstance(row, dict) and isinstance(row.get("data_id"), str)
    }
    model_source = model_sources.get(contract.get("data_id"))
    if model_source is None:
        errors.append(f"data_id {contract.get('data_id')!r} is absent from model_contract")
    elif isinstance(source, dict):
        if model_source.get("path") != source.get("path") or model_source.get("sha256") != source.get("sha256"):
            errors.append("data_contract source path/hash differs from model_contract data source")

    table = contract.get("table", {}) if isinstance(contract.get("table"), dict) else {}
    profile = contract.get("profile", {}) if isinstance(contract.get("profile"), dict) else {}
    columns = [row for row in contract.get("columns", []) if isinstance(row, dict)]
    names = [row.get("name") for row in columns]
    if len(names) != len(set(names)):
        errors.append("data_contract column names must be unique")
    if table.get("column_count") != len(columns):
        errors.append("table.column_count does not equal the number of column contracts")
    if table.get("row_count") != profile.get("row_count"):
        errors.append("table.row_count differs from profile.row_count")
    row_count = table.get("row_count")
    if isinstance(row_count, int):
        for column in columns:
            missing = column.get("missing_count")
            if isinstance(missing, int) and missing > row_count:
                errors.append(f"column {column.get('name')} missing_count exceeds row_count")

    failed_invariants = [
        row.get("invariant_id") for row in contract.get("invariants", [])
        if isinstance(row, dict) and row.get("status") != "pass"
    ]
    if failed_invariants:
        errors.append(f"data invariants are not PASS: {failed_invariants}")
    leakage = contract.get("leakage_policy", {}) if isinstance(contract.get("leakage_policy"), dict) else {}
    if leakage.get("status") not in {"pass", "not_applicable"}:
        errors.append(f"leakage_policy.status is not promotable: {leakage.get('status')}")
    column_by_name = {row.get("name"): row for row in columns if isinstance(row, dict)}
    target_columns = leakage.get("target_columns", []) if isinstance(leakage.get("target_columns"), list) else []
    for target in target_columns:
        if target not in column_by_name:
            errors.append(f"leakage_policy.target_columns references missing column: {target}")
        elif column_by_name[target].get("role") != "target":
            errors.append(f"leakage_policy.target_columns column is not role=target: {target}")
    forbidden_features = leakage.get("forbidden_features", []) if isinstance(leakage.get("forbidden_features"), list) else []
    for feature in forbidden_features:
        if feature not in column_by_name:
            errors.append(f"leakage_policy.forbidden_features references missing column: {feature}")
        elif feature in target_columns:
            errors.append(f"leakage_policy.forbidden_features must name a feature, not target: {feature}")
    if leakage.get("status") == "pass" and not (leakage.get("split_keys") or leakage.get("time_boundary")):
        errors.append("leakage_policy.status=pass requires split_keys or time_boundary")
    if contract.get("status") != "validated":
        errors.append("data_contract.status must be validated")
    if not table.get("primary_key"):
        warnings.append("no primary key declared; duplicate entity/time joins require manual review")

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "data_contract": rel_path(contract_path, root),
        "model_contract": rel_path(model_path, root),
        "data_id": contract.get("data_id"),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
