#!/usr/bin/env python3
"""Compute declared validation verdicts from a model contract and measurement snapshot."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, write_json  # noqa: E402
from validation.obligations import build_validation_report, file_ref  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--measurements", required=True, help="JSON observations keyed by declared obligation")
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    model_path = resolve_path(args.model_contract, root).resolve()
    measurements_path = resolve_path(args.measurements, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        if not model_path.is_file():
            raise ValueError(f"model contract does not exist: {model_path}")
        if not measurements_path.is_file():
            raise ValueError(f"measurement snapshot does not exist: {measurements_path}")
        model_contract = load_structured(model_path)
        measurements = load_structured(measurements_path)
        if not isinstance(model_contract, dict) or not isinstance(measurements, dict):
            raise ValueError("model contract and measurements must both be JSON objects")
        report = build_validation_report(
            model_contract,
            measurements,
            file_ref(model_path, root),
            file_ref(measurements_path, root),
        )
        write_json(output_path, report)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "output": rel_path(output_path, root),
                "obligations": len(report["obligations"]),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
