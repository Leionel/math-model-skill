#!/usr/bin/env python3
"""Create or extend the single evidence registry with literature and frozen results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_structured, rel_path, resolve_path, sha256_file, write_json  # noqa: E402


def merge_seed(
    seed_path: Path,
    root: Path,
    expected_run_id: str | None,
) -> tuple[str | None, list[dict[str, str]], dict[str, dict[str, Any]]]:
    seed = load_structured(seed_path)
    if not isinstance(seed, dict):
        raise ValueError("seed registry must be an object")
    seed_run_id = seed.get("run_id")
    if seed_run_id is not None and (not isinstance(seed_run_id, str) or not seed_run_id):
        raise ValueError("seed registry run_id must be a non-empty string")
    if expected_run_id and seed_run_id not in {None, expected_run_id}:
        raise ValueError("seed registry run_id does not match requested run")
    evidence: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(seed.get("evidence", [])):
        if not isinstance(row, dict) or not isinstance(row.get("evidence_id"), str):
            raise ValueError(f"seed evidence[{index}] must contain evidence_id")
        evidence_id = row["evidence_id"]
        if evidence_id in evidence:
            raise ValueError(f"duplicate seed evidence_id: {evidence_id}")
        evidence[evidence_id] = row
    snapshots = seed.get("source_snapshots")
    if isinstance(snapshots, list):
        copied = [dict(row) for row in snapshots if isinstance(row, dict)]
    else:
        copied = [{"kind": "manual_seed", "path": rel_path(seed_path, root), "sha256": sha256_file(seed_path)}]
    return seed_run_id, copied, evidence


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-results")
    parser.add_argument("--seed", help="existing registry or manual evidence seed")
    parser.add_argument("--run-id", help="required when neither input declares a run_id")
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if not args.frozen_results and not args.seed:
        parser.error("at least one of --frozen-results or --seed is required")

    root = Path(args.project_root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        run_id = args.run_id
        source_snapshots: list[dict[str, str]] = []
        evidence: dict[str, dict[str, Any]] = {}

        if args.seed:
            seed_path = resolve_path(args.seed, root).resolve()
            seed_run_id, seed_snapshots, seed_evidence = merge_seed(seed_path, root, run_id)
            run_id = run_id or seed_run_id
            source_snapshots.extend(seed_snapshots)
            evidence.update(seed_evidence)

        if args.frozen_results:
            frozen_path = resolve_path(args.frozen_results, root).resolve()
            frozen = load_structured(frozen_path)
            if not isinstance(frozen, dict) or frozen.get("status") != "frozen":
                raise ValueError("frozen-results must have status=frozen")
            if frozen.get("claimable") is not True or frozen.get("validation_verdict") != "PASS":
                raise ValueError(
                    "frozen-results is not claimable; FAIL/ERROR runs are retained for audit but cannot enter evidence_registry"
                )
            frozen_run_id = frozen.get("run_id")
            if not isinstance(frozen_run_id, str) or not frozen_run_id:
                raise ValueError("frozen-results must declare run_id")
            if run_id and run_id != frozen_run_id:
                raise ValueError("frozen-results run_id does not match registry run_id")
            run_id = frozen_run_id
            results = frozen.get("results", [])
            if not isinstance(results, list) or not results:
                raise ValueError("frozen-results must contain a non-empty results array")
            source_snapshots = [
                row for row in source_snapshots
                if not (row.get("kind") == "frozen_results" and row.get("path") == rel_path(frozen_path, root))
            ]
            source_snapshots.append({
                "kind": "frozen_results",
                "path": rel_path(frozen_path, root),
                "sha256": sha256_file(frozen_path),
            })
            result_ids: set[str] = set()
            for index, result in enumerate(results):
                if not isinstance(result, dict) or not isinstance(result.get("result_id"), str):
                    raise ValueError(f"results[{index}] must contain result_id")
                if result.get("claimable") is not True or result.get("validation_status") != "passed":
                    raise ValueError(f"frozen result {result.get('result_id')} is not claimable")
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
                generated = {
                    "evidence_id": evidence_id,
                    "type": "result",
                    "result_ids": [result_id],
                    "artifacts": [{"path": rel_path(source_path, root), "sha256": sha256_file(source_path)}],
                    "supports": f"{result['name']} = {result['display_value']} {result['unit']}",
                    "boundary": result["boundary"],
                    "verification_status": "verified",
                }
                existing = evidence.get(evidence_id)
                if existing is not None and existing != generated:
                    raise ValueError(f"seed evidence_id conflicts with generated evidence: {evidence_id}")
                evidence[evidence_id] = generated

        if not run_id:
            raise ValueError("run_id is required")
        if not evidence:
            raise ValueError("registry must contain at least one evidence record")
        snapshot_keys = [(row.get("kind"), row.get("path"), row.get("sha256")) for row in source_snapshots]
        if len(snapshot_keys) != len(set(snapshot_keys)):
            raise ValueError("source_snapshots must be unique")
        registry = {
            "schema_version": "1.1",
            "run_id": run_id,
            "source_snapshots": source_snapshots,
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
