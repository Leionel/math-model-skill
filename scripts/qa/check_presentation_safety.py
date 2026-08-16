#!/usr/bin/env python3
"""Check direction-safe rounding and feasibility rechecks for displayed results."""

from __future__ import annotations

import argparse
import json
import math
import sys
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402
from latex.generate_values_tex import format_value  # noqa: E402
from qa.check_formula_replay import UnsafeExpression, evaluate_numeric_expression  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


PRESENTATION_SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "presentation_contract.schema.json"


def _display_number(result: dict[str, Any], entry: dict[str, Any]) -> Decimal:
    try:
        value = Decimal(str(result.get("value"))) * Decimal(str(entry.get("scale", 1)))
        digits = int(entry.get("digits", result.get("precision", 0)))
        quantum = Decimal(1).scaleb(-digits)
        rounding = entry.get("rounding")
        if rounding == "floor":
            return value.quantize(quantum, rounding=ROUND_FLOOR)
        if rounding == "ceil":
            return value.quantize(quantum, rounding=ROUND_CEILING)
        if rounding == "frozen_display_value":
            return Decimal(str(result.get("display_value")))
        raise ValueError("safe_side requires rounding=floor, rounding=ceil, or a separately verified exact value")
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise ValueError(f"cannot obtain numeric display value for {result.get('result_id')}") from exc


def _compare(actual: float, operator: str, limit: float, tolerance: float) -> bool:
    if operator == "<":
        return actual < limit + tolerance
    if operator == "<=":
        return actual <= limit + tolerance
    if operator == ">":
        return actual > limit - tolerance
    if operator == ">=":
        return actual >= limit - tolerance
    return abs(actual - limit) <= tolerance


def evaluate_presentation_safety(
    presentation_contract: dict[str, Any],
    frozen_results: dict[str, Any],
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    results = {
        row.get("result_id"): row
        for row in frozen_results.get("results", [])
        if isinstance(row, dict) and isinstance(row.get("result_id"), str)
    }
    checked = 0
    for entry in presentation_contract.get("entries", []):
        if not isinstance(entry, dict) or entry.get("safe_side") in {None, "none"}:
            continue
        checked += 1
        presentation_id = entry.get("presentation_id", "<unknown-presentation>")
        result_id = entry.get("result_id")
        result = results.get(result_id)
        if result is None:
            errors.append(f"{presentation_id}: unknown result_id {result_id}")
            continue
        safe_side = entry.get("safe_side")
        rounding = entry.get("rounding")
        expected_rounding = {
            "lower_bound": "floor",
            "upper_bound": "ceil",
        }.get(safe_side)
        if expected_rounding and rounding != expected_rounding:
            errors.append(
                f"{presentation_id}: safe_side={safe_side} requires rounding={expected_rounding}, got {rounding}"
            )
        try:
            raw = Decimal(str(result.get("value"))) * Decimal(str(entry.get("scale", 1)))
            displayed = _display_number(result, entry)
            if not all(value.is_finite() for value in (raw, displayed)):
                raise ValueError("raw and displayed values must be finite")
            if safe_side == "lower_bound" and displayed > raw:
                errors.append(f"{presentation_id}: displayed value {displayed} exceeds lower-bound raw value {raw}")
            if safe_side == "upper_bound" and displayed < raw:
                errors.append(f"{presentation_id}: displayed value {displayed} is below upper-bound raw value {raw}")
            if safe_side == "exact" and displayed != raw:
                errors.append(f"{presentation_id}: exact display {displayed} differs from raw value {raw}")
        except (InvalidOperation, TypeError, ValueError) as exc:
            errors.append(f"{presentation_id}: {exc}")
            continue

        recheck = entry.get("feasibility_recheck")
        if not isinstance(recheck, dict):
            errors.append(f"{presentation_id}: safe_side requires feasibility_recheck")
            continue
        symbol = recheck.get("display_symbol")
        substitutions = recheck.get("substitutions", {})
        if not isinstance(symbol, str) or not isinstance(substitutions, dict):
            errors.append(f"{presentation_id}: feasibility_recheck has invalid display_symbol or substitutions")
            continue
        try:
            values = {
                str(key): float(value)
                for key, value in substitutions.items()
                if isinstance(value, (int, float)) and not isinstance(value, bool)
            }
            values[symbol] = float(displayed)
            actual = evaluate_numeric_expression(str(recheck.get("expression", "")), values)
            limit = float(recheck.get("limit"))
            abs_tolerance = float(recheck.get("abs_tolerance"))
            rel_tolerance = float(recheck.get("rel_tolerance"))
            tolerance = abs_tolerance + rel_tolerance * abs(limit)
            if not all(math.isfinite(value) for value in (actual, limit, tolerance)):
                raise ValueError("feasibility recheck values must be finite")
            if not _compare(actual, str(recheck.get("operator")), limit, tolerance):
                errors.append(
                    f"{presentation_id}: displayed-value feasibility recheck failed; "
                    f"actual={actual:.15g} {recheck.get('operator')} limit={limit:.15g}, "
                    f"unit={recheck.get('unit')}"
                )
        except (TypeError, ValueError, OverflowError, UnsafeExpression) as exc:
            errors.append(f"{presentation_id}: feasibility recheck failed: {exc}")

    details = {
        "status": "PASS" if not errors else "FAIL",
        "safe_entries_checked": checked,
        "claim": "direction_safe_rounding_and_display_recheck_only",
    }
    return errors, warnings, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--presentation-contract", required=True)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    presentation_path = resolve_path(args.presentation_contract, root).resolve()
    frozen_path = resolve_path(args.frozen_results, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        presentation, schema_errors, _ = _validate_document(presentation_path, PRESENTATION_SCHEMA)
        errors.extend(f"presentation_contract schema: {message}" for message in schema_errors)
        frozen = load_structured(frozen_path)
        if not isinstance(presentation, dict) or not isinstance(frozen, dict):
            raise ValueError("presentation contract and frozen results must be objects")
        if presentation.get("run_id") != frozen.get("run_id"):
            errors.append("presentation contract and frozen results must share one run_id")
        check_errors, check_warnings, details = evaluate_presentation_safety(presentation, frozen)
        errors.extend(check_errors)
        warnings.extend(check_warnings)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "presentation_contract": rel_path(presentation_path, root),
        "frozen_results": rel_path(frozen_path, root),
        "details": details,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
