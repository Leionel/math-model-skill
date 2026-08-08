#!/usr/bin/env python3
"""Create an evidence registry from frozen results without depending on a paper plan."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_structured, rel_path, resolve_path, sha256_file, write_json  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", help="optional registry containing non-result evidence")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    frozen_path = resolve_path(args.frozen_results, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        frozen = load_structured(frozen_path)
        if not isinstance(frozen, dict) or frozen.get("status") != "frozen":
            raise ValueError("frozen-results must have status=frozen")
        results = frozen.get("results", [])
        if not isinstance(results, list) or not results:
            raise ValueError("frozen-results must contain a non-empty results array")

        evidence: dict[str, dict[str, Any]] = {}
        result_ids: set[str] = set()
        for index, result in enumerate(results):
            if not isinstance(result, dict) or not isinstance(result.get("result_id"), str):
                raise ValueError(f"results[{index}] must contain result_id")
            result_id = result["result_id"]
            if result_id in result_ids:
                raise ValueError(f"duplicate frozen result_id: {result_id}")
            result_ids.add(result_id)
            source_artifact = result.get("source_artifact")
            if not isinstance(source_artifact, str) or not source_artifact:
                raise ValueError(f"result {result_id} has no source_artifact")
            source_path = resolve_path(source_artifact, root).resolve()
            if not source_path.is_file():
                raise ValueError(f"result {result_id} source artifact does not exist: {source_artifact}")
            evidence_id = f"E-{result_id}"
            evidence[evidence_id] = {
                "evidence_id": evidence_id,
                "type": "result",
                "result_ids": [result_id],
                "artifacts": [{"path": rel_path(source_path, root), "sha256": sha256_file(source_path)}],
                "supports": f"{result['name']} = {result['display_value']} {result['unit']}",
                "boundary": result["boundary"],
                "verification_status": "verified",
            }

        if args.seed:
            seed_path = resolve_path(args.seed, root).resolve()
            seed = load_structured(seed_path)
            if not isinstance(seed, dict):
                raise ValueError("seed registry must be an object")
            if seed.get("run_id") not in {None, frozen.get("run_id")}:
                raise ValueError("seed registry run_id does not match frozen results")
            for index, row in enumerate(seed.get("evidence", [])):
                if not isinstance(row, dict) or not isinstance(row.get("evidence_id"), str):
                    raise ValueError(f"seed evidence[{index}] must contain evidence_id")
                evidence_id = row["evidence_id"]
                if evidence_id in evidence:
                    raise ValueError(f"seed evidence_id conflicts with generated evidence: {evidence_id}")
                evidence[evidence_id] = row

        registry = {
            "schema_version": "1.0",
            "run_id": frozen["run_id"],
            "generated_from": {
                "frozen_results_path": rel_path(frozen_path, root),
                "frozen_results_sha256": sha256_file(frozen_path),
            },
            "evidence": sorted(evidence.values(), key=lambda row: row["evidence_id"]),
        }
        write_json(output_path, registry, overwrite=args.force)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "registered", "output": rel_path(output_path, root), "evidence": len(registry["evidence"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
