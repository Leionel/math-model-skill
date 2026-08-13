"""Evaluate finite, declared validation comparisons without executing expressions."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from _common import rel_path, sha256_file


REPORT_SCHEMA_VERSION = "1.0"
EVALUATOR_VERSION = "p0-comparator-v1"
ALLOWED_OPERATORS = {"<=", "<", ">=", ">", "==", "!="}


def file_ref(path: Path, root: Path) -> dict[str, str]:
    """Create a content-addressed local file reference."""

    return {"path": rel_path(path, root), "sha256": sha256_file(path)}


def declared_obligations(model_contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return every declared obligation, rejecting ambiguous contract structure."""

    if model_contract.get("status") != "ready":
        raise ValueError("model contract must have status=ready before validation")
    obligations: dict[str, dict[str, Any]] = {}
    models = model_contract.get("models")
    if not isinstance(models, list) or not models:
        raise ValueError("model contract must contain a non-empty models array")
    for model_index, model in enumerate(models):
        if not isinstance(model, dict):
            raise ValueError(f"model_contract.models[{model_index}] must be an object")
        rows = model.get("validation_obligations")
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"model {model.get('model_id', model_index)} has no validation_obligations")
        for row_index, row in enumerate(rows):
            if not isinstance(row, dict):
                raise ValueError(
                    f"model_contract.models[{model_index}].validation_obligations[{row_index}] must be an object"
                )
            obligation_id = row.get("obligation_id")
            if not isinstance(obligation_id, str) or not obligation_id:
                raise ValueError(
                    f"model_contract.models[{model_index}].validation_obligations[{row_index}] has no obligation_id"
                )
            if obligation_id in obligations:
                raise ValueError(f"duplicate validation obligation_id: {obligation_id}")
            obligations[obligation_id] = row
    return obligations


def validation_verdict(statuses: list[str]) -> str:
    """Summarize per-obligation verdicts with ERROR taking precedence over FAIL."""

    if not statuses:
        raise ValueError("validation statuses must not be empty")
    if any(status == "ERROR" for status in statuses):
        return "ERROR"
    if any(status == "FAIL" for status in statuses):
        return "FAIL"
    if all(status == "PASS" for status in statuses):
        return "PASS"
    raise ValueError(f"unknown validation status(es): {statuses!r}")


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a finite number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{label} must be a finite number")
    return numeric


def _metric_map(observation: dict[str, Any], obligation_id: str) -> dict[str, dict[str, Any]]:
    metrics = observation.get("metrics")
    if not isinstance(metrics, list) or not metrics:
        raise ValueError(f"measurement for {obligation_id} must contain a non-empty metrics array")
    indexed: dict[str, dict[str, Any]] = {}
    for index, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            raise ValueError(f"measurement {obligation_id}.metrics[{index}] must be an object")
        metric_id = metric.get("metric_id")
        unit = metric.get("unit")
        locator = metric.get("locator")
        if not isinstance(metric_id, str) or not metric_id:
            raise ValueError(f"measurement {obligation_id}.metrics[{index}] has no metric_id")
        if metric_id in indexed:
            raise ValueError(f"measurement {obligation_id} repeats metric_id {metric_id}")
        if not isinstance(unit, str) or not unit:
            raise ValueError(f"measurement {obligation_id}.{metric_id} has no unit")
        if not isinstance(locator, str) or not locator:
            raise ValueError(f"measurement {obligation_id}.{metric_id} has no locator")
        _number(metric.get("value"), f"measurement {obligation_id}.{metric_id}.value")
        indexed[metric_id] = metric
    return indexed


def _metric(metric_map: dict[str, dict[str, Any]], metric_id: Any, unit: str) -> dict[str, Any]:
    if not isinstance(metric_id, str) or not metric_id:
        raise ValueError("acceptance metric_id must be a non-empty string")
    metric = metric_map.get(metric_id)
    if metric is None:
        raise ValueError(f"measurement does not provide required metric {metric_id}")
    if metric.get("unit") != unit:
        raise ValueError(
            f"metric {metric_id} uses unit {metric.get('unit')!r}, expected acceptance unit {unit!r}"
        )
    return {
        "metric_id": metric_id,
        "value": _number(metric.get("value"), f"metric {metric_id}.value"),
        "unit": unit,
        "locator": metric["locator"],
    }


def _compare(left: float, operator: str, right: float, tolerance: float) -> bool:
    if operator == "<=":
        return left <= right + tolerance
    if operator == "<":
        return left < right + tolerance
    if operator == ">=":
        return left + tolerance >= right
    if operator == ">":
        return left + tolerance > right
    if operator == "==":
        return abs(left - right) <= tolerance
    if operator == "!=":
        return abs(left - right) > tolerance
    raise ValueError(f"unsupported validation operator {operator!r}")


def _error_row(obligation_id: str, acceptance: Any, message: str) -> dict[str, Any]:
    operator = acceptance.get("operator") if isinstance(acceptance, dict) else None
    unit = acceptance.get("unit") if isinstance(acceptance, dict) else None
    return {
        "obligation_id": obligation_id,
        "status": "ERROR",
        "operator": operator if isinstance(operator, str) else "invalid",
        "observed": None,
        "threshold": None,
        "unit": unit if isinstance(unit, str) else None,
        "locator": None,
        "message": message,
    }


def _evaluate_one(obligation_id: str, obligation: dict[str, Any], observation: dict[str, Any] | None) -> dict[str, Any]:
    acceptance = obligation.get("acceptance")
    if observation is None:
        return _error_row(obligation_id, acceptance, "no measurement was provided for this declared obligation")
    try:
        if not isinstance(acceptance, dict):
            raise ValueError("acceptance must be an object")
        operator = acceptance.get("operator")
        unit = acceptance.get("unit")
        if operator not in ALLOWED_OPERATORS:
            raise ValueError(f"operator must be one of {sorted(ALLOWED_OPERATORS)}")
        if not isinstance(unit, str) or not unit:
            raise ValueError("acceptance.unit must be a non-empty string")
        tolerance = _number(acceptance.get("tolerance", 0), "acceptance.tolerance")
        if tolerance < 0:
            raise ValueError("acceptance.tolerance must be non-negative")
        metrics = _metric_map(observation, obligation_id)
        observed = _metric(metrics, acceptance.get("left_metric_id"), unit)
        right = acceptance.get("right")
        if not isinstance(right, dict):
            raise ValueError("acceptance.right must be an object")
        kind = right.get("kind")
        if kind == "literal":
            threshold = {"kind": "literal", "value": _number(right.get("value"), "acceptance.right.value")}
            right_value = threshold["value"]
            threshold_locator = observed["locator"]
        elif kind == "metric":
            threshold_metric = _metric(metrics, right.get("metric_id"), unit)
            threshold = {"kind": "metric", **threshold_metric}
            right_value = threshold_metric["value"]
            threshold_locator = threshold_metric["locator"]
        else:
            raise ValueError("acceptance.right.kind must be literal or metric")
        passed = _compare(observed["value"], operator, right_value, tolerance)
        tolerance_note = f" (tolerance {tolerance:g})" if tolerance else ""
        return {
            "obligation_id": obligation_id,
            "status": "PASS" if passed else "FAIL",
            "operator": operator,
            "observed": observed,
            "threshold": threshold,
            "unit": unit,
            "locator": observed["locator"] if kind == "literal" else f"{observed['locator']} | {threshold_locator}",
            "message": f"{observed['value']:g} {unit} {operator} {right_value:g} {unit}{tolerance_note}",
        }
    except ValueError as exc:
        return _error_row(obligation_id, acceptance, str(exc))


def evaluate_obligations(model_contract: dict[str, Any], measurements: dict[str, Any]) -> list[dict[str, Any]]:
    """Compute every declared verdict from measurements and the finite comparison DSL."""

    obligations = declared_obligations(model_contract)
    if measurements.get("schema_version") != "1.0":
        raise ValueError("measurements.schema_version must be '1.0'")
    if measurements.get("run_id") != model_contract.get("run_id"):
        raise ValueError("measurements.run_id does not match model contract run_id")
    rows = measurements.get("observations")
    if not isinstance(rows, list):
        raise ValueError("measurements.observations must be an array")
    observed: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"measurements.observations[{index}] must be an object")
        obligation_id = row.get("obligation_id")
        if not isinstance(obligation_id, str) or not obligation_id:
            raise ValueError(f"measurements.observations[{index}] has no obligation_id")
        if obligation_id not in obligations:
            raise ValueError(f"measurement declares unknown obligation_id {obligation_id}")
        if obligation_id in observed:
            raise ValueError(f"measurement repeats obligation_id {obligation_id}")
        observed[obligation_id] = row
    return [
        _evaluate_one(obligation_id, obligation, observed.get(obligation_id))
        for obligation_id, obligation in sorted(obligations.items())
    ]


def build_validation_report(
    model_contract: dict[str, Any],
    measurements: dict[str, Any],
    model_contract_ref: dict[str, str],
    measurement_ref: dict[str, str],
) -> dict[str, Any]:
    """Build a fully derived report that can be recomputed during result freezing."""

    obligations = evaluate_obligations(model_contract, measurements)
    verdict = validation_verdict([row["status"] for row in obligations])
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": model_contract["run_id"],
        "evaluator_version": EVALUATOR_VERSION,
        "model_contract_snapshot": model_contract_ref,
        "measurement_snapshot": measurement_ref,
        "ok": verdict == "PASS",
        "verdict": verdict,
        "obligations": obligations,
    }


def verify_validation_report(
    report: Any,
    model_contract: dict[str, Any],
    measurements: dict[str, Any],
    model_contract_ref: dict[str, str],
    measurement_ref: dict[str, str],
) -> dict[str, Any]:
    """Reject hand-edited verdicts by requiring the report to equal a recomputation."""

    if not isinstance(report, dict):
        raise ValueError("validation report must be an object")
    expected = build_validation_report(
        model_contract,
        measurements,
        model_contract_ref,
        measurement_ref,
    )
    for field in ("schema_version", "run_id", "evaluator_version", "model_contract_snapshot", "measurement_snapshot", "ok", "verdict", "obligations"):
        if report.get(field) != expected[field]:
            raise ValueError(
                f"validation report field {field!r} does not match independent recomputation from the contract and measurements"
            )
    return expected
