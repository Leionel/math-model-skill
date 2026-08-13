#!/usr/bin/env python3
"""Compute nondominance for finite multi-objective candidates without trusting labels."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, write_json  # noqa: E402


def dominates(left: dict[str, float], right: dict[str, float], directions: dict[str, str], tolerance: float) -> bool:
    weakly_better = True
    strictly_better = False
    for metric, direction in directions.items():
        a, b = left[metric], right[metric]
        if direction == "minimize":
            weakly_better &= a <= b + tolerance
            strictly_better |= a < b - tolerance
        else:
            weakly_better &= a >= b - tolerance
            strictly_better |= a > b + tolerance
    return weakly_better and strictly_better


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--tolerance", type=float, default=0.0)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    input_path = resolve_path(args.input, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        payload = load_structured(input_path)
        if not isinstance(payload, dict):
            raise ValueError("Pareto input must be an object")
        metrics = payload.get("metrics")
        candidates = payload.get("candidates")
        if not isinstance(metrics, list) or not metrics or not isinstance(candidates, list) or not candidates:
            raise ValueError("Pareto input requires non-empty metrics and candidates arrays")
        directions: dict[str, str] = {}
        for metric in metrics:
            if not isinstance(metric, dict) or metric.get("direction") not in {"minimize", "maximize"}:
                raise ValueError("each metric requires metric_id and direction=minimize|maximize")
            metric_id = metric.get("metric_id")
            if not isinstance(metric_id, str) or not metric_id or metric_id in directions:
                raise ValueError("metric_id values must be non-empty and unique")
            directions[metric_id] = metric["direction"]
        values: dict[str, dict[str, float]] = {}
        claimed: dict[str, bool | None] = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise ValueError("candidate rows must be objects")
            candidate_id = candidate.get("candidate_id")
            raw_values = candidate.get("values")
            if not isinstance(candidate_id, str) or not candidate_id or candidate_id in values:
                raise ValueError("candidate_id values must be non-empty and unique")
            if not isinstance(raw_values, dict) or set(raw_values) != set(directions):
                raise ValueError(f"candidate {candidate_id} values must exactly cover declared metrics")
            converted = {key: float(value) for key, value in raw_values.items()}
            if not all(math.isfinite(value) for value in converted.values()):
                raise ValueError(f"candidate {candidate_id} has non-finite value")
            values[candidate_id] = converted
            claimed[candidate_id] = candidate.get("claimed_nondominated")
        rows = []
        errors = []
        for candidate_id, candidate_values in values.items():
            dominators = sorted(
                other_id for other_id, other_values in values.items()
                if other_id != candidate_id and dominates(other_values, candidate_values, directions, args.tolerance)
            )
            nondominated = not dominators
            if claimed[candidate_id] is not None and claimed[candidate_id] is not nondominated:
                errors.append(
                    f"candidate {candidate_id} claimed_nondominated={claimed[candidate_id]} but computed={nondominated}"
                )
            rows.append({
                "candidate_id": candidate_id,
                "values": candidate_values,
                "nondominated": nondominated,
                "dominated_by": dominators,
            })
        report = {
            "schema_version": "1.0",
            "run_id": payload.get("run_id"),
            "metrics": metrics,
            "tolerance": args.tolerance,
            "candidates": rows,
            "nondominated_ids": [row["candidate_id"] for row in rows if row["nondominated"]],
            "errors": errors,
            "ok": not errors,
        }
        write_json(output_path, report, overwrite=args.force)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": report["ok"], "output": rel_path(output_path, root), "nondominated": report["nondominated_ids"]}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
