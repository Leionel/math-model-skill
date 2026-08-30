#!/usr/bin/env python3
"""Shared P1 smoke-coverage contract: the smoke receipt declares exercised math.

P1 proves real execution, but a successful command can be an unrelated script.
Enhanced runs therefore bind a coverage declaration to the qualifying smoke
receipt and validate it against the model contract:

- model_ids must cover every contracted model (no extras);
- question_ids must cover every contracted question;
- for every covered model, at least one equation/constraint/obligation id.

The declaration belongs to immutable smoke-receipt metadata. The checker
verifies consistency against the model contract; a mutable control-manifest
row is not execution evidence.
"""

from __future__ import annotations

from typing import Any


def contract_coverage_sets(contract: Any) -> tuple[set[str], set[str], dict[str, set[str]]]:
    """Return (model_ids, question_ids, model -> known item ids) from a contract."""

    model_ids: set[str] = set()
    question_ids: set[str] = set()
    items_by_model: dict[str, set[str]] = {}
    if not isinstance(contract, dict):
        return model_ids, question_ids, items_by_model
    question_ids = {
        str(row.get("question_id"))
        for row in contract.get("questions", [])
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }
    for model in contract.get("models", []):
        if not isinstance(model, dict) or not isinstance(model.get("model_id"), str):
            continue
        model_id = model["model_id"]
        model_ids.add(model_id)
        plan = model.get("plan_details") if isinstance(model.get("plan_details"), dict) else {}
        items: set[str] = set()
        for equation in plan.get("equation_plan", []):
            if isinstance(equation, dict) and isinstance(equation.get("equation_id"), str):
                items.add(equation["equation_id"])
        for constraint in model.get("constraints", []):
            if isinstance(constraint, dict) and isinstance(constraint.get("constraint_id"), str):
                items.add(constraint["constraint_id"])
        for obligation in model.get("validation_obligations", []):
            if isinstance(obligation, dict) and isinstance(obligation.get("obligation_id"), str):
                items.add(obligation["obligation_id"])
        items_by_model[model_id] = items
    return model_ids, question_ids, items_by_model


def _declared_ids(coverage: dict[str, Any], field: str, errors: list[str]) -> set[str]:
    value = coverage.get(field)
    if not isinstance(value, list):
        errors.append(f"smoke_coverage.{field} must be an array of non-empty strings")
        return set()
    if any(not isinstance(row, str) or not row for row in value):
        errors.append(f"smoke_coverage.{field} contains invalid entries")
    return {row for row in value if isinstance(row, str) and row}


def smoke_coverage_errors(
    coverage: Any,
    contract: Any,
    *,
    allowed_receipt_ids: set[str] | None = None,
) -> list[str]:
    """Validate one receipt-bound smoke_coverage block."""

    if not isinstance(coverage, dict):
        return [
            "enhanced P1 requires a smoke_coverage declaration "
            "in the successful smoke receipt metadata "
            "{model_ids, question_ids, covered_contract_item_ids}"
        ]
    errors: list[str] = []
    if not isinstance(contract, dict):
        return ["enhanced P1 cannot validate smoke_coverage without a model contract"]
    contract_model_ids, contract_question_ids, items_by_model = contract_coverage_sets(contract)
    if allowed_receipt_ids is not None:
        declared_receipt = coverage.get("command_receipt_id")
        if not isinstance(declared_receipt, str) or declared_receipt not in allowed_receipt_ids:
            errors.append(
                "smoke_coverage.command_receipt_id must be the receipt id of a successful smoke command"
            )
    declared_models = _declared_ids(coverage, "model_ids", errors)
    missing_models = sorted(contract_model_ids - declared_models)
    unknown_models = sorted(declared_models - contract_model_ids)
    if missing_models:
        errors.append(f"smoke_coverage does not cover every contracted model: {missing_models}")
    if unknown_models:
        errors.append(f"smoke_coverage declares unknown model_ids: {unknown_models}")
    declared_questions = _declared_ids(coverage, "question_ids", errors)
    missing_questions = sorted(contract_question_ids - declared_questions)
    unknown_questions = sorted(declared_questions - contract_question_ids)
    if missing_questions:
        errors.append(f"smoke_coverage does not cover every contracted question: {missing_questions}")
    if unknown_questions:
        errors.append(f"smoke_coverage declares unknown question_ids: {unknown_questions}")
    declared_items = _declared_ids(coverage, "covered_contract_item_ids", errors)
    known_items: set[str] = set()
    for model_id, items in items_by_model.items():
        known_items.update(items)
        if model_id in declared_models and not (declared_items & items):
            errors.append(f"smoke_coverage lists no equation/constraint/obligation item for model {model_id}")
    unknown_items = sorted(declared_items - known_items)
    if unknown_items:
        errors.append(f"smoke_coverage declares unknown contract item ids: {unknown_items}")
    return errors
