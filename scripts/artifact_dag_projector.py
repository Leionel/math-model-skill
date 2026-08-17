"""Recompute v2 artifact freshness from the canonical DAG and local files.

This is a projector, not a registry: it never invents a second artifact
record and it never writes the projection.  ``check_artifact_dag.py`` uses it
as the factual view of current/stale/invalidation state.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Mapping

from _common import resolve_path, sha256_file


def _node_path(node: Mapping[str, Any], root: Path) -> Path | None:
    raw = node.get("path")
    if not isinstance(raw, str) or not raw:
        return None
    return resolve_path(raw, root).resolve()


def project_artifact_dag(
    dag: Mapping[str, Any],
    *,
    project_root: str | Path,
    receipts: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    """Return a factual freshness projection, errors and invalidation events."""

    root = Path(project_root).resolve()
    projection = copy.deepcopy(dict(dag))
    nodes = projection.get("nodes")
    errors: list[str] = []
    events: list[dict[str, Any]] = []
    if not isinstance(nodes, list):
        return projection, ["artifact DAG v2 requires a nodes array"], events

    by_id = {
        str(node.get("artifact_id")): node
        for node in nodes
        if isinstance(node, Mapping) and isinstance(node.get("artifact_id"), str)
    }
    visiting: set[str] = set()
    done: dict[str, str] = {}

    def visit(node_id: str) -> str:
        if node_id in done:
            return done[node_id]
        if node_id in visiting:
            errors.append(f"artifact DAG contains a cycle at artifact_id {node_id}")
            done[node_id] = "stale"
            return "stale"
        node = by_id.get(node_id)
        if node is None:
            errors.append(f"dependency references unknown artifact_id: {node_id}")
            done[node_id] = "stale"
            return "stale"
        visiting.add(node_id)
        path = _node_path(node, root)
        lifecycle = str(node.get("lifecycle", "mutable"))
        current = True
        if path is not None:
            try:
                path.relative_to(root)
            except ValueError:
                current = False
                errors.append(f"artifact {node_id} path escapes project root: {node.get('path')}")
        if path is None or not path.is_file():
            current = False
            if path is None or path.is_relative_to(root):
                errors.append(f"artifact {node_id} path does not exist: {node.get('path')}")
        expected = node.get("sha256") or node.get("digest")
        actual: str | None = None
        if current and expected is not None:
            actual = sha256_file(path)  # type: ignore[arg-type]
            if str(expected).lower() != actual:
                current = False
                event = {
                    "artifact_id": node_id,
                    "lifecycle": lifecycle,
                    "reason": "immutable_digest_drift" if lifecycle in {"immutable", "frozen", "submission"} else "digest_drift",
                    "expected_sha256": str(expected).lower(),
                    "actual_sha256": actual,
                    "invalidates_downstream": lifecycle in {"immutable", "frozen", "submission"},
                }
                events.append(event)
        dependencies = node.get("dependencies", [])
        if not isinstance(dependencies, list):
            errors.append(f"artifact {node_id}.dependencies must be an array")
            dependencies = []
        for dependency in dependencies:
            if not isinstance(dependency, Mapping) or not isinstance(dependency.get("artifact_id"), str):
                errors.append(f"artifact {node_id} has an invalid dependency")
                current = False
                continue
            if visit(str(dependency["artifact_id"])) != "current":
                current = False
        if receipts is not None and isinstance(node.get("producer_receipt_id"), str):
            receipt = receipts.get(str(node["producer_receipt_id"]))
            if receipt is None:
                current = False
                errors.append(f"artifact {node_id} producer receipt is missing: {node['producer_receipt_id']}")
            elif receipt.get("exit_code") != 0:
                current = False
                errors.append(f"artifact {node_id} producer receipt failed: {node['producer_receipt_id']}")
        status = "current" if current else ("not_run" if path is None or not path.is_file() else "stale")
        node["freshness"] = status
        if actual is not None and expected is None and node.get("digest_owner"):
            # The projector reports a digest only when the DAG already named
            # itself as owner; it does not promote a projection into an owner.
            node["metadata"] = {**(node.get("metadata") if isinstance(node.get("metadata"), Mapping) else {}), "observed_sha256": actual}
        visiting.remove(node_id)
        done[node_id] = status
        return status

    for node_id in by_id:
        visit(node_id)
    return projection, errors, events


__all__ = ["project_artifact_dag"]
