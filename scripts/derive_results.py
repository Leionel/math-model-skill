#!/usr/bin/env python3
"""Compute secondary metrics from frozen results so the Writer never recomputes them.

Growth rates, relative reductions, ratios, percentage points, means, standard
deviations and similar derived numbers must come from this engine. The Writer
may only cite a derived_result_id, never recompute a percentage by hand.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_structured, rel_path, resolve_path, sha256_file, sha256_json, write_json  # noqa: E402

DERIVATION_TYPES = (
    "relative_change",
    "absolute_change",
    "ratio",
    "percentage_point_change",
    "difference",
    "mean",
    "std",
    "min",
    "max",
)
PAIR_TYPES = {"relative_change", "absolute_change", "ratio", "percentage_point_change", "difference"}


def decimal_of(value: Any, label: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a numeric frozen value, got {value!r}")
    try:
        return Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{label} is not a finite number: {value!r}") from exc


def rounded(value: Decimal, precision: int) -> str:
    quantum = Decimal(1).scaleb(-precision)
    return f"{value.quantize(quantum, rounding=ROUND_HALF_UP):.{precision}f}"


def compute_derivation(spec: dict[str, Any], results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    derivation_id = spec.get("derived_result_id")
    if not isinstance(derivation_id, str) or not derivation_id.strip():
        raise ValueError("each derivation requires a non-empty derived_result_id")
    dtype = spec.get("type")
    if dtype not in DERIVATION_TYPES:
        raise ValueError(f"derivation {derivation_id} has unsupported type {dtype!r}")
    question_id = spec.get("question_id")
    input_ids = spec.get("inputs")
    if not isinstance(input_ids, list) or not input_ids:
        raise ValueError(f"derivation {derivation_id} requires a non-empty inputs list")
    if len(input_ids) != len(set(input_ids)):
        raise ValueError(f"derivation {derivation_id} inputs must be unique")
    precision = spec.get("precision")
    if not isinstance(precision, int) or isinstance(precision, bool) or precision < 0:
        raise ValueError(f"derivation {derivation_id} requires a non-negative integer precision")
    unit = spec.get("unit")
    if not isinstance(unit, str) or not unit.strip():
        raise ValueError(f"derivation {derivation_id} requires a non-empty unit")

    if dtype in PAIR_TYPES and len(input_ids) != 2:
        raise ValueError(f"derivation {derivation_id} type {dtype} requires exactly two inputs [baseline, candidate]")
    if dtype in {"mean", "std", "min", "max"} and len(input_ids) < 2:
        raise ValueError(f"derivation {derivation_id} type {dtype} requires at least two inputs")
    if dtype == "std" and len(input_ids) < 2:
        raise ValueError(f"derivation {derivation_id} type std requires at least two inputs")

    values: list[Decimal] = []
    input_units: list[str] = []
    for result_id in input_ids:
        row = results.get(result_id)
        if row is None:
            raise ValueError(f"derivation {derivation_id} references unknown result_id {result_id}")
        if row.get("claimable") is not True:
            raise ValueError(f"derivation {derivation_id} input {result_id} is not claimable")
        values.append(decimal_of(row.get("value"), f"result {result_id} value"))
        input_units.append(str(row.get("unit", "")))

    if dtype in {"absolute_change", "difference", "mean", "std", "min", "max"} and len(set(input_units)) > 1:
        raise ValueError(
            f"derivation {derivation_id} mixes incompatible units {sorted(set(input_units))}; convert before deriving"
        )

    if dtype == "relative_change":
        direction = spec.get("direction", "increase")
        if direction not in {"increase", "reduction"}:
            raise ValueError(f"derivation {derivation_id} direction must be increase or reduction")
        baseline, candidate = values
        if baseline == 0:
            raise ValueError(f"derivation {derivation_id} baseline is zero; relative_change is undefined")
        if direction == "increase":
            value = (candidate - baseline) / baseline
            formula = "(candidate - baseline) / baseline"
        else:
            value = (baseline - candidate) / baseline
            formula = "(baseline - candidate) / baseline"
    elif dtype == "absolute_change":
        value = values[1] - values[0]
        formula = "candidate - baseline"
    elif dtype == "difference":
        value = values[0] - values[1]
        formula = "first - second"
    elif dtype == "ratio":
        if values[0] == 0:
            raise ValueError(f"derivation {derivation_id} denominator is zero; ratio is undefined")
        value = values[1] / values[0]
        formula = "candidate / baseline"
    elif dtype == "percentage_point_change":
        value = values[1] - values[0]
        formula = "(candidate - baseline) expressed in percentage points"
    elif dtype == "mean":
        value = sum(values) / Decimal(len(values))
        formula = "mean(inputs)"
    elif dtype == "std":
        mean = sum(values) / Decimal(len(values))
        variance = sum((item - mean) ** 2 for item in values) / Decimal(len(values) - 1)
        value = Decimal(str(math.sqrt(float(variance))))
        formula = "sample std(inputs, ddof=1)"
    elif dtype == "min":
        value = min(values)
        formula = "min(inputs)"
    else:
        value = max(values)
        formula = "max(inputs)"

    display_factor = Decimal(100) if unit in {"%", "pp"} else Decimal(1)
    display = rounded(value * display_factor, precision)

    row: dict[str, Any] = {
        "derived_result_id": derivation_id,
        "question_id": question_id,
        "type": dtype,
        "inputs": list(input_ids),
        "formula": formula,
        "value": float(value),
        "precision": precision,
        "display_value": display,
        "unit": unit,
    }
    if isinstance(spec.get("notes"), str) and spec["notes"].strip():
        row["notes"] = spec["notes"]
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--spec", required=True, help="JSON file with a top-level derivations array")
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--integrity-mode", choices=("dev", "research", "submission"), default="research")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    frozen_path = resolve_path(args.frozen_results, root).resolve()
    spec_path = resolve_path(args.spec, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        frozen = load_structured(frozen_path)
        spec = load_structured(spec_path)
        if not isinstance(frozen, dict):
            raise ValueError("frozen results must be an object")
        if frozen.get("status") != "frozen":
            raise ValueError("frozen_results.status must be frozen before deriving results")
        if frozen.get("claimable") is not True or frozen.get("validation_verdict") != "PASS":
            raise ValueError("derived results require claimable PASS frozen results; FAIL runs stay diagnostic only")
        results = {
            row.get("result_id"): row
            for row in frozen.get("results", [])
            if isinstance(row, dict) and isinstance(row.get("result_id"), str)
        }
        if not results:
            raise ValueError("frozen results contain no usable result rows")
        derivations = spec.get("derivations") if isinstance(spec, dict) else None
        if not isinstance(derivations, list) or not derivations:
            raise ValueError("spec must be an object with a non-empty derivations array")
        derived = [compute_derivation(row, results) for row in derivations]
        ids = [row["derived_result_id"] for row in derived]
        if len(ids) != len(set(ids)):
            raise ValueError("derived_result_id values must be unique")
        question_ids = {
            row.get("question_id")
            for row in frozen.get("results", [])
            if isinstance(row, dict) and isinstance(row.get("question_id"), str)
        }
        for row in derived:
            if not isinstance(row.get("question_id"), str) or row["question_id"] not in question_ids:
                raise ValueError(
                    f"derivation {row['derived_result_id']} must declare a question_id present in frozen results"
                )
        payload = {
            "schema_version": "1.0",
            "run_id": frozen.get("run_id"),
            "status": "frozen",
            "derived_at": datetime.now(timezone.utc).isoformat(),
            "frozen_results": {"path": rel_path(frozen_path, root)},
            "derived": derived,
        }
        if args.integrity_mode == "submission":
            payload["frozen_results"]["sha256"] = sha256_file(frozen_path)
            payload["spec_sha256"] = sha256_file(spec_path)
            payload["derived_sha256"] = sha256_json(derived)
        write_json(output_path, payload)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {"status": "frozen", "output": rel_path(output_path, root), "derived": len(derived)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
