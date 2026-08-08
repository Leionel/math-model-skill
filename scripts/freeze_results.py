#!/usr/bin/env python3
"""Freeze a validated result snapshot for the P0 evidence chain."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_structured, rel_path, resolve_path, sha256_file, sha256_json, write_json  # noqa: E402


def numeric_display(value: Any, precision: int) -> str:
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError(f"value {value!r} is not numeric; provide display_value explicitly") from exc
    try:
        quantum = Decimal(1).scaleb(-precision)
        rounded = decimal.quantize(quantum, rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:
        raise ValueError(f"value {value!r} cannot be rounded to precision={precision}") from exc
    return f"{rounded:.{precision}f}"


def normalize_result(row: dict[str, Any], source_path: Path, root: Path, index: int) -> dict[str, Any]:
    required = ("result_id", "question_id", "name", "value", "unit", "precision", "statistical_definition", "boundary", "validation_status")
    missing = [key for key in required if key not in row]
    if missing:
        raise ValueError(f"results[{index}] missing required fields: {', '.join(missing)}")
    if row["validation_status"] not in {"passed", "verified"}:
        raise ValueError(f"results[{index}] must have validation_status=passed|verified before freezing")
    precision = row["precision"]
    if not isinstance(precision, int) or precision < 0:
        raise ValueError(f"results[{index}].precision must be a non-negative integer")
    result = dict(row)
    if not isinstance(result["unit"], str) or not result["unit"].strip():
        raise ValueError(f"results[{index}].unit must be a non-empty string")
    try:
        expected_display = numeric_display(result["value"], precision)
    except ValueError:
        expected_display = None
    if "display_value" not in result:
        if expected_display is None:
            raise ValueError(f"results[{index}].display_value is required for a non-numeric value")
        result["display_value"] = expected_display
    if not isinstance(result["display_value"], str) or not result["display_value"].strip():
        raise ValueError(f"results[{index}].display_value must be a non-empty string")
    if expected_display is not None and result["display_value"] != expected_display:
        raise ValueError(
            f"results[{index}].display_value must equal canonical rounded value {expected_display!r}"
        )
    result.setdefault("source_artifact", rel_path(source_path, root))
    result.setdefault("source_key", str(result["result_id"]))
    for key in ("result_id", "question_id", "name", "statistical_definition", "boundary", "source_artifact", "source_key"):
        if not isinstance(result[key], str) or not result[key].strip():
            raise ValueError(f"results[{index}].{key} must be a non-empty string")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="JSON result file with a top-level results array")
    parser.add_argument("--output", required=True, help="frozen_results.json output path")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--input", action="append", default=[], help="input artifact; repeatable")
    parser.add_argument("--code", action="append", required=True, help="code artifact; repeatable")
    parser.add_argument("--validation", action="append", required=True, help="validation report/log; repeatable")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    source = resolve_path(args.source, root).resolve()
    output = resolve_path(args.output, root).resolve()
    if not source.is_file():
        print(f"ERROR: source result file does not exist: {source}", file=sys.stderr)
        return 2
    if source == output:
        print("ERROR: --source and --output must be different files", file=sys.stderr)
        return 2
    try:
        raw = load_structured(source)
        rows = raw.get("results") if isinstance(raw, dict) else raw
        if not isinstance(rows, list) or not rows:
            raise ValueError("source must be a non-empty list or an object with a non-empty results list")
        results = [normalize_result(row, source, root, index) for index, row in enumerate(rows)]
        ids = [row["result_id"] for row in results]
        if len(ids) != len(set(ids)):
            raise ValueError("result_id values must be unique")

        def refs(raw_paths: list[str]) -> list[dict[str, str]]:
            output_refs: list[dict[str, str]] = []
            for raw_path in raw_paths:
                path = resolve_path(raw_path, root).resolve()
                if not path.is_file():
                    raise ValueError(f"artifact does not exist: {path}")
                output_refs.append({"path": rel_path(path, root), "sha256": sha256_file(path)})
            return output_refs

        frozen = {
            "schema_version": "1.0",
            "run_id": args.run_id,
            "status": "frozen",
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "source_snapshot": {"path": rel_path(source, root), "sha256": sha256_file(source)},
            "input_snapshot": refs(args.input),
            "code_snapshot": refs(args.code),
            "validation_snapshot": refs(args.validation),
            "command": args.command,
            "seed": args.seed,
            "results_sha256": sha256_json(results),
            "results": results,
        }
        write_json(output, frozen)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "frozen", "output": rel_path(output, root), "results": len(results)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
