#!/usr/bin/env python3
"""Verify an artifact DAG is acyclic and node digests match current file identities."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path, sha256_file, sha256_json  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dag", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    dag_path = resolve_path(args.dag, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    dag, schema_errors, _ = _validate_document(
        dag_path, Path(__file__).resolve().parents[2] / "schemas" / "artifact_dag.schema.json"
    )
    errors.extend(f"artifact_dag schema: {message}" for message in schema_errors)
    if not isinstance(dag, dict):
        dag = {}
    nodes = [row for row in dag.get("nodes", []) if isinstance(row, dict)]
    node_ids = [row.get("node_id") for row in nodes]
    if len(node_ids) != len(set(node_ids)):
        errors.append("artifact DAG node_id values must be unique")

    producer: dict[str, str] = {}
    dependencies: dict[str, set[str]] = {str(node_id): set() for node_id in node_ids}

    def verify_ref(owner: str, ref: Any) -> None:
        if not isinstance(ref, dict):
            errors.append(f"{owner} must be a file_ref")
            return
        path = resolve_path(str(ref.get("path", "")), root).resolve()
        try:
            path.relative_to(root)
        except ValueError:
            errors.append(f"{owner} escapes project root: {ref.get('path')}")
            return
        if not path.is_file():
            errors.append(f"{owner} does not exist: {ref.get('path')}")
        elif ref.get("sha256") != sha256_file(path):
            errors.append(f"{owner} hash drift: {ref.get('path')}")

    for node in nodes:
        node_id = str(node.get("node_id"))
        for index, ref in enumerate(node.get("outputs", [])):
            verify_ref(f"node {node_id} outputs[{index}]", ref)
            if isinstance(ref, dict):
                path = str(ref.get("path"))
                if path in producer:
                    errors.append(f"artifact {path} has multiple producers: {producer[path]}, {node_id}")
                producer[path] = node_id
        verify_ref(f"node {node_id} receipt", node.get("receipt"))

    for node in nodes:
        node_id = str(node.get("node_id"))
        digest_rows = []
        for index, ref in enumerate(node.get("inputs", [])):
            verify_ref(f"node {node_id} inputs[{index}]", ref)
            if isinstance(ref, dict):
                digest_rows.append({"path": ref.get("path"), "sha256": ref.get("sha256")})
                owner = producer.get(str(ref.get("path")))
                if owner:
                    dependencies[node_id].add(owner)
        expected_digest = sha256_json(sorted(digest_rows, key=lambda row: str(row.get("path"))))
        if node.get("upstream_digest") != expected_digest:
            errors.append(f"node {node_id} upstream_digest drift")
        if node.get("status") != "current":
            errors.append(f"node {node_id} is not current: {node.get('status')}")

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node_id: str) -> None:
        if node_id in visiting:
            errors.append(f"artifact DAG contains a cycle at node {node_id}")
            return
        if node_id in visited:
            return
        visiting.add(node_id)
        for parent in dependencies.get(node_id, set()):
            visit(parent)
        visiting.remove(node_id)
        visited.add(node_id)

    for node_id in dependencies:
        visit(node_id)

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "dag": rel_path(dag_path, root),
        "run_id": dag.get("run_id"),
        "nodes": len(nodes),
        "edges": sum(len(value) for value in dependencies.values()),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
