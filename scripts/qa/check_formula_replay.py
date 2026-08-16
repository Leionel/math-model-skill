#!/usr/bin/env python3
"""Replay declared equations with numeric substitutions and check paper anchors.

This is a deliberately small, safe evaluator for scalar back-substitution.
The expression is supplied as an ASCII-like right-hand side in the contract;
it is never executed with Python ``eval``.  Solver reruns and global-optimum
claims remain separate validation obligations.
"""

from __future__ import annotations

import argparse
import ast
import json
import math
import operator
import sys
from pathlib import Path
from typing import Any, Callable

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


MODEL_SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "model_contract.schema.json"

_BINARY_OPERATORS: dict[type[ast.operator], Callable[[float, float], float]] = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
}
_UNARY_OPERATORS: dict[type[ast.unaryop], Callable[[float], float]] = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}
_FUNCTIONS: dict[str, Callable[..., float]] = {
    "abs": abs,
    "cos": math.cos,
    "exp": math.exp,
    "fabs": math.fabs,
    "log": math.log,
    "log10": math.log10,
    "max": max,
    "min": min,
    "sin": math.sin,
    "sqrt": math.sqrt,
    "tan": math.tan,
}
_CONSTANTS = {"e": math.e, "pi": math.pi}


class UnsafeExpression(ValueError):
    """Raised when a replay expression uses unsupported syntax."""


def _eval_node(node: ast.AST, values: dict[str, float]) -> float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id in values:
            return float(values[node.id])
        if node.id in _CONSTANTS:
            return float(_CONSTANTS[node.id])
        raise UnsafeExpression(f"unknown symbol {node.id!r}")
    if isinstance(node, ast.UnaryOp):
        function = _UNARY_OPERATORS.get(type(node.op))
        if function is None:
            raise UnsafeExpression(f"unsupported unary operator {type(node.op).__name__}")
        return float(function(_eval_node(node.operand, values)))
    if isinstance(node, ast.BinOp):
        function = _BINARY_OPERATORS.get(type(node.op))
        if function is None:
            raise UnsafeExpression(f"unsupported binary operator {type(node.op).__name__}")
        return float(function(_eval_node(node.left, values), _eval_node(node.right, values)))
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        function = _FUNCTIONS.get(node.func.id)
        if function is None or node.keywords:
            raise UnsafeExpression(f"unsupported function call {ast.unparse(node.func)}")
        return float(function(*[_eval_node(argument, values) for argument in node.args]))
    raise UnsafeExpression(f"unsupported expression node {type(node).__name__}")


def evaluate_numeric_expression(expression: str, substitutions: dict[str, float]) -> float:
    """Evaluate a finite scalar expression without invoking Python eval."""

    normalised = expression.replace("^", "**").strip()
    if not normalised:
        raise UnsafeExpression("expression is empty")
    try:
        tree = ast.parse(normalised, mode="eval")
        result = _eval_node(tree.body, substitutions)
    except (SyntaxError, TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
        if isinstance(exc, UnsafeExpression):
            raise
        raise UnsafeExpression(str(exc)) from exc
    if not math.isfinite(result):
        raise UnsafeExpression("expression result is not finite")
    return result


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item.strip()]


def _normalise_text(value: str) -> str:
    return " ".join(value.casefold().split())


def _paper_section(text: str, markers: list[str], all_markers: list[str]) -> str | None:
    folded = text.casefold()
    hits = [(folded.find(marker.casefold()), marker) for marker in markers if folded.find(marker.casefold()) >= 0]
    if not hits:
        return None
    start, _ = min(hits, key=lambda item: item[0])
    later_starts = [
        folded.find(marker.casefold(), start + 1)
        for marker in all_markers
        if marker and folded.find(marker.casefold(), start + 1) >= 0
    ]
    end = min(later_starts) if later_starts else len(text)
    return text[start:end]


def evaluate_formula_replay(
    model_contract: dict[str, Any],
    paper_text: str | None = None,
    *,
    require_replay: bool = False,
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    equations_total = 0
    cases_total = 0
    failed_cases = 0
    case_ids: set[str] = set()
    cases_with_paper_tokens: list[tuple[dict[str, Any], str]] = []
    all_markers: list[str] = []

    equations: list[tuple[str, dict[str, Any]]] = []
    for model in model_contract.get("models", []):
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("model_id", "<unknown-model>"))
        details = model.get("plan_details")
        if not isinstance(details, dict):
            continue
        for equation in details.get("equation_plan", []):
            if isinstance(equation, dict):
                equations.append((model_id, equation))
                equations_total += 1
                all_markers.extend(
                    marker
                    for case in (
                        (equation.get("verification") or {}).get("numeric_replay", [])
                        if isinstance(equation.get("verification"), dict)
                        else []
                    )
                    if isinstance(case, dict)
                    for marker in _strings(case.get("paper_section_markers"))
                )

    replayed_equations = 0
    for model_id, equation in equations:
        equation_id = str(equation.get("equation_id", "<unknown-equation>"))
        verification = equation.get("verification")
        cases = verification.get("numeric_replay", []) if isinstance(verification, dict) else []
        if not isinstance(cases, list):
            continue
        if cases:
            replayed_equations += 1
        for case in cases:
            if not isinstance(case, dict):
                continue
            cases_total += 1
            case_id = str(case.get("case_id", "<unknown-case>"))
            if case_id in case_ids:
                errors.append(f"numeric replay case_id must be globally unique: {case_id}")
            case_ids.add(case_id)
            substitutions = case.get("substitutions", {})
            if not isinstance(substitutions, dict):
                errors.append(f"{equation_id}/{case_id}: substitutions must be an object")
                continue
            try:
                values = {
                    str(symbol): float(value)
                    for symbol, value in substitutions.items()
                    if isinstance(value, (int, float)) and not isinstance(value, bool)
                }
                actual = evaluate_numeric_expression(str(case.get("expression", "")), values)
                expected = float(case.get("expected"))
                abs_tolerance = float(case.get("abs_tolerance"))
                rel_tolerance = float(case.get("rel_tolerance"))
                if not all(math.isfinite(value) for value in (expected, abs_tolerance, rel_tolerance)):
                    raise ValueError("expected values and tolerances must be finite")
                difference = abs(actual - expected)
                limit = abs_tolerance + rel_tolerance * abs(expected)
                if difference > limit:
                    failed_cases += 1
                    errors.append(
                        f"{equation_id}/{case_id}: replay mismatch actual={actual:.15g}, "
                        f"expected={expected:.15g}, difference={difference:.15g}, limit={limit:.15g}, "
                        f"unit={case.get('unit')}"
                    )
            except (TypeError, ValueError, OverflowError, UnsafeExpression) as exc:
                failed_cases += 1
                errors.append(f"{equation_id}/{case_id}: replay failed: {exc}")
            if _strings(case.get("paper_tokens")) or _strings(case.get("forbidden_tokens")):
                cases_with_paper_tokens.append((case, case_id))

    missing_equations = equations_total - replayed_equations
    if require_replay and missing_equations:
        errors.append(
            f"numeric replay is required for every equation; missing for {missing_equations} of {equations_total} equation(s)"
        )
    elif missing_equations and replayed_equations:
        warnings.append(
            f"numeric replay is partial: {missing_equations} of {equations_total} equation(s) have no replay case"
        )

    paper_details: dict[str, Any] = {"status": "not_run", "cases_checked": 0}
    if paper_text is not None:
        for case, case_id in cases_with_paper_tokens:
            markers = _strings(case.get("paper_section_markers"))
            section = _paper_section(paper_text, markers, all_markers) if markers else paper_text
            if section is None:
                errors.append(f"{case_id}: no paper section matched paper_section_markers")
                continue
            normalised_section = _normalise_text(section)
            for token in _strings(case.get("paper_tokens")):
                if _normalise_text(token) not in normalised_section:
                    errors.append(f"{case_id}: paper section is missing required token {token!r}")
            for token in _strings(case.get("forbidden_tokens")):
                if _normalise_text(token) in normalised_section:
                    errors.append(f"{case_id}: paper section contains forbidden token {token!r}")
            paper_details["cases_checked"] += 1
        paper_details["status"] = "checked"

    details = {
        "status": "PASS" if not errors else "FAIL",
        "equations_total": equations_total,
        "equations_replayed": replayed_equations,
        "cases_total": cases_total,
        "failed_cases": failed_cases,
        "paper_check": paper_details,
    }
    return errors, warnings, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--paper")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-formula-replay", action="store_true")
    parser.add_argument("--skip-if-absent", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    model_path = resolve_path(args.model_contract, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        model, schema_errors, _ = _validate_document(model_path, MODEL_SCHEMA)
        errors.extend(f"model_contract schema: {message}" for message in schema_errors)
        if not isinstance(model, dict):
            raise ValueError("model_contract must be an object")
        has_replay = any(
            isinstance(model_row, dict)
            and isinstance(model_row.get("plan_details"), dict)
            and any(
                isinstance(equation, dict)
                and isinstance(equation.get("verification"), dict)
                and equation["verification"].get("numeric_replay")
                for equation in model_row["plan_details"].get("equation_plan", [])
            )
            for model_row in model.get("models", [])
        )
        if not has_replay and args.skip_if_absent and not args.require_formula_replay:
            details = {"status": "NOT_APPLICABLE", "paper_check": {"status": "not_run"}}
        else:
            paper_text = None
            if args.paper:
                paper_text = resolve_path(args.paper, root).resolve().read_text(encoding="utf-8")
            replay_errors, replay_warnings, details = evaluate_formula_replay(
                model,
                paper_text,
                require_replay=args.require_formula_replay,
            )
            errors.extend(replay_errors)
            warnings.extend(replay_warnings)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "model_contract": rel_path(model_path, root),
        "paper": rel_path(resolve_path(args.paper, root).resolve(), root) if args.paper else None,
        "details": details,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
