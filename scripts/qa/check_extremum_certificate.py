#!/usr/bin/env python3
"""Validate grid screening and continuous candidate refinement certificates.

The checker certifies internal consistency and refinement coverage.  It does
not accept a self-declared global optimum: a global claim still needs a
separate mathematical certificate and independent W2 review.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


CERTIFICATE_SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "extremum_certificate.schema.json"


def _close(left: float, right: float, abs_tolerance: float, rel_tolerance: float) -> bool:
    return abs(left - right) <= abs_tolerance + rel_tolerance * abs(right)


def _finite(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def evaluate_extremum_certificate(certificate: dict[str, Any], project_root: Path | None = None) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    variables = [item for item in certificate.get("variables", []) if isinstance(item, str)]
    variable_set = set(variables)
    objective = certificate.get("objective")
    tolerance = certificate.get("tolerance", {})
    abs_tolerance = float(tolerance.get("abs", 0)) if _finite(tolerance.get("abs")) else 0.0
    rel_tolerance = float(tolerance.get("rel", 0)) if _finite(tolerance.get("rel")) else 0.0
    if certificate.get("status") != "completed":
        errors.append("extremum certificate status must be completed")
    if not variables:
        errors.append("extremum certificate must declare at least one variable")
    domain = certificate.get("domain", {})
    for variable in variables:
        interval = domain.get(variable) if isinstance(domain, dict) else None
        if not isinstance(interval, dict) or not _finite(interval.get("lower")) or not _finite(interval.get("upper")):
            errors.append(f"domain is missing a finite interval for {variable}")
        elif float(interval["lower"]) >= float(interval["upper"]):
            errors.append(f"domain interval for {variable} must have lower < upper")

    def check_point(label: str, point: Any) -> dict[str, float] | None:
        if not isinstance(point, dict):
            errors.append(f"{label} must be an object")
            return None
        keys = set(point)
        if keys != variable_set:
            errors.append(f"{label} variables differ from certificate: expected={sorted(variable_set)}, got={sorted(keys)}")
            return None
        values: dict[str, float] = {}
        for variable in variables:
            if not _finite(point.get(variable)):
                errors.append(f"{label}.{variable} must be finite")
            else:
                values[variable] = float(point[variable])
        return values

    grid = certificate.get("grid", {})
    points = grid.get("points", []) if isinstance(grid, dict) else []
    values = grid.get("values", []) if isinstance(grid, dict) else []
    checked_points: list[dict[str, float] | None] = [check_point(f"grid.points[{index}]", point) for index, point in enumerate(points)]
    if len(points) != len(values):
        errors.append("grid.points and grid.values must have the same length")
    finite_values = [float(value) for value in values if _finite(value)]
    if len(finite_values) != len(values):
        errors.append("grid.values must contain only finite numbers")
    best_index = grid.get("best_index") if isinstance(grid, dict) else None
    best_value = grid.get("best_value") if isinstance(grid, dict) else None
    if not isinstance(best_index, int) or isinstance(best_index, bool) or not 0 <= best_index < len(values):
        errors.append("grid.best_index must point to an existing grid value")
    else:
        if not _finite(best_value) or not _close(float(best_value), float(values[best_index]), abs_tolerance, rel_tolerance):
            errors.append("grid.best_value does not match values[best_index] within the declared tolerance")
        best_point = check_point("grid.best_point", grid.get("best_point"))
        if best_point is not None and checked_points[best_index] is not None:
            for variable in variables:
                if not _close(best_point[variable], checked_points[best_index][variable], abs_tolerance, rel_tolerance):
                    errors.append("grid.best_point does not match points[best_index]")
        if finite_values:
            expected = max(finite_values) if objective == "max" else min(finite_values)
            if not _close(float(values[best_index]), expected, abs_tolerance, rel_tolerance):
                errors.append("grid.best_index is not an extremum of the recorded grid values")

    def artifact_exists(label: str, value: Any) -> None:
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{label} must name a source artifact")
            return
        if project_root is not None and not resolve_path(value, project_root).resolve().is_file():
            errors.append(f"{label} source artifact does not exist: {value}")

    artifact_exists("grid", grid.get("source_artifact") if isinstance(grid, dict) else None)
    refinement = certificate.get("refinement", {})
    refinement_status = refinement.get("status") if isinstance(refinement, dict) else None
    if refinement_status == "completed":
        intervals = refinement.get("intervals", {})
        if not isinstance(intervals, dict) or set(intervals) != variable_set:
            errors.append("refinement.intervals must cover exactly the declared variables")
        interval_values: dict[str, tuple[float, float]] = {}
        for variable in variables:
            interval = intervals.get(variable) if isinstance(intervals, dict) else None
            domain_interval = domain.get(variable, {}) if isinstance(domain, dict) else {}
            if not isinstance(interval, dict) or not _finite(interval.get("lower")) or not _finite(interval.get("upper")):
                errors.append(f"refinement interval is missing for {variable}")
                continue
            lower, upper = float(interval["lower"]), float(interval["upper"])
            if lower >= upper:
                errors.append(f"refinement interval for {variable} must have lower < upper")
            if not isinstance(domain_interval, dict) or not _finite(domain_interval.get("lower")) or not _finite(domain_interval.get("upper")):
                continue
            if lower < float(domain_interval["lower"]) or upper > float(domain_interval["upper"]):
                errors.append(f"refinement interval for {variable} escapes the declared domain")
            interval_values[variable] = (lower, upper)
        candidate = check_point("refinement.point", refinement.get("point"))
        if candidate is not None:
            for variable, (lower, upper) in interval_values.items():
                if not lower <= candidate[variable] <= upper:
                    errors.append(f"refinement.point.{variable} is outside its refinement interval")
        if isinstance(best_index, int) and 0 <= best_index < len(checked_points) and checked_points[best_index] is not None:
            best = checked_points[best_index]
            for variable, (lower, upper) in interval_values.items():
                if not lower <= best[variable] <= upper:
                    errors.append(f"refinement interval for {variable} does not contain the best grid point")
        if not isinstance(refinement.get("evaluations"), int) or refinement.get("evaluations", 0) < 2:
            errors.append("completed refinement requires at least two evaluations")
        if not _finite(refinement.get("value")) or not finite_values:
            errors.append("refinement.value and grid values must be finite")
        elif objective == "max" and float(refinement["value"]) < max(finite_values) - abs_tolerance - rel_tolerance * abs(max(finite_values)):
            errors.append("refinement candidate is worse than the best grid value for a maximization")
        elif objective == "min" and float(refinement["value"]) > min(finite_values) + abs_tolerance + rel_tolerance * abs(min(finite_values)):
            errors.append("refinement candidate is worse than the best grid value for a minimization")
    elif refinement_status != "not_run":
        errors.append("refinement.status must be completed or not_run")
    artifact_exists("refinement", refinement.get("source_artifact") if isinstance(refinement, dict) else None)

    claim_level = certificate.get("claim_level")
    if claim_level == "refined_candidate" and refinement_status != "completed":
        errors.append("refined_candidate claim requires completed continuous refinement")
    if claim_level == "global":
        errors.append(
            "global claim is not accepted by the automatic extremum checker; provide an independent mathematical certificate and W2 review"
        )

    details = {
        "status": "PASS" if not errors else "FAIL",
        "certificate_level": "grid_plus_continuous_candidate" if refinement_status == "completed" else "grid_screening",
        "global_optimum_proof": "not_automated",
        "variables": variables,
        "grid_points": len(points),
        "refinement_status": refinement_status,
    }
    return errors, warnings, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--certificate", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--run-id")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    certificate_path = resolve_path(args.certificate, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        certificate, schema_errors, _ = _validate_document(certificate_path, CERTIFICATE_SCHEMA)
        errors.extend(f"extremum_certificate schema: {message}" for message in schema_errors)
        if not isinstance(certificate, dict):
            raise ValueError("extremum certificate must be an object")
        if args.run_id and certificate.get("run_id") != args.run_id:
            errors.append("extremum certificate run_id does not match the supplied run_id")
        check_errors, check_warnings, details = evaluate_extremum_certificate(certificate, root)
        errors.extend(check_errors)
        warnings.extend(check_warnings)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "certificate": rel_path(certificate_path, root),
        "details": details,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
