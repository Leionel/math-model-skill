"""Artifact MCP tools: list and verify.  There is deliberately no register tool.

An agent may not obtain provenance by asking for it.  ``artifact_id``, SHA-256,
``created_at`` and producer binding exist precisely because a *producer*
command created them: ``harness execute`` captures a real process,
``harness freeze`` binds a validated result, and the authoring compilers write
contract IR.  A ``register_artifact`` tool that minted ids, hashes and
timestamps on request would be a hash-and-receipt forgery endpoint wearing a
friendlier name, so this module exposes verification instead.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

CONTRACT_SCHEMA_BY_ROLE: dict[str, str] = {
    "model_contract": "model_contract.schema.json",
    "frozen_results": "frozen_results.schema.json",
    "evidence_registry": "evidence_registry.schema.json",
    "paper_plan": "paper_plan.schema.json",
    "run_manifest": "run_manifest.schema.json",
    "artifact_dag": "artifact_dag.schema.json",
    "competition_profile": "competition_profile.schema.json",
    "review_report": "review_report.schema.json",
    "command_receipt": "command_receipt.schema.json",
    "data_contract": "data_contract.schema.json",
    "problem_snapshot": "problem_snapshot.schema.json",
    "implementation_map": "implementation_map.schema.json",
    "submission_manifest": "submission_manifest.schema.json",
}


def _nodes(root: Path, module: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    dag_path = module["resolve_control_path"](root, "artifact_dag.json")
    if not dag_path.is_file():
        return [], ["artifact_dag.json is absent; run harness init first"]
    dag = json.loads(dag_path.read_text(encoding="utf-8"))
    nodes = [row for row in dag.get("nodes", []) if isinstance(row, Mapping)]
    return [dict(row) for row in nodes], []


def list_artifacts(root: Path, arguments: Mapping[str, Any], module: Mapping[str, Any]) -> dict[str, Any]:
    """Every DAG node with its recomputed freshness, never its cached claim."""

    nodes, errors = _nodes(root, module)
    projection, projection_errors, events = module["project_artifact_dag"](
        {"nodes": nodes, "schema_version": "2.0", "run_id": arguments.get("run_id") or "-"},
        project_root=root,
    )
    drifted = {str(event.get("artifact_id")): str(event.get("reason")) for event in events}
    return {
        "artifacts": [
            {
                "artifact_id": str(node.get("artifact_id")),
                "role": str(node.get("role")),
                "path": str(node.get("path")),
                "lifecycle": str(node.get("lifecycle")),
                "freshness": node.get("freshness"),
                "producer_id": node.get("producer_id"),
                "producer_receipt_id": node.get("producer_receipt_id"),
                "digest_owner": node.get("digest_owner"),
                "dependencies": [
                    str(dep.get("artifact_id")) for dep in (node.get("dependencies") or [])
                    if isinstance(dep, Mapping) and dep.get("artifact_id")
                ],
                "drift_reason": drifted.get(str(node.get("artifact_id"))),
            }
            for node in projection.get("nodes", [])
            if isinstance(node, Mapping)
        ],
        "errors": [*errors, *projection_errors],
        "note": "freshness is recomputed from bytes on disk, not read from the stored field",
    }


def verify_artifact(root: Path, arguments: Mapping[str, Any], module: Mapping[str, Any]) -> dict[str, Any]:
    """Check one artifact: identity, digest, lineage, dependency state, schema."""

    wanted = str(arguments.get("artifact_id") or arguments.get("path") or "")
    if not wanted:
        raise module["ToolCallError"]("provide artifact_id or path")
    nodes, errors = _nodes(root, module)
    if not nodes:
        return {"verified": False, "errors": errors or ["artifact DAG is empty"]}
    node = next(
        (
            row for row in nodes
            if str(row.get("artifact_id")) == wanted
            or str(row.get("path", "")).replace("\\", "/") == wanted.replace("\\", "/")
        ),
        None,
    )
    if node is None:
        return {"verified": False, "errors": [f"no artifact DAG node matches {wanted!r}"]}
    artifact_id = str(node.get("artifact_id"))
    projection, projection_errors, events = module["project_artifact_dag"](
        {"schema_version": "2.0", "run_id": "-", "nodes": nodes}, project_root=root,
    )
    current = next(
        (row for row in projection.get("nodes", []) if isinstance(row, Mapping) and str(row.get("artifact_id")) == artifact_id),
        {},
    )
    reasons = [*errors, *projection_errors]
    reasons += [str(event.get("reason")) for event in events if str(event.get("artifact_id")) == artifact_id]
    reasons += [str(event.get("reason")) for event in events if str(event.get("artifact_id")) in {
        str(dep.get("artifact_id")) for dep in node.get("dependencies", []) if isinstance(dep, Mapping)
    }]
    freshness = current.get("freshness")
    if freshness != "current":
        reasons.append(f"freshness is {freshness}")
    schema_result = _verify_schema(root, node, module)
    reasons.extend(schema_result["errors"])
    return {
        "artifact_id": artifact_id,
        "role": node.get("role"),
        "path": node.get("path"),
        "verified": freshness == "current" and not reasons,
        "freshness": freshness,
        "lifecycle": node.get("lifecycle"),
        "digest_owner": node.get("digest_owner"),
        "producer_receipt_id": node.get("producer_receipt_id"),
        "dependencies": [str(dep.get("artifact_id")) for dep in node.get("dependencies", []) if isinstance(dep, Mapping)],
        "schema_check": schema_result["detail"],
        "errors": sorted(set(reasons)),
        "note": "identity, lineage and schema are recomputed here; nothing is written",
    }


def _verify_schema(root: Path, node: Mapping[str, Any], module: Mapping[str, Any]) -> dict[str, Any]:
    role = str(node.get("role"))
    schema_name = CONTRACT_SCHEMA_BY_ROLE.get(role)
    if schema_name is None:
        return {"errors": [], "detail": "no schema is defined for this role"}
    path = root / str(node.get("path"))
    schema_path = module["SCHEMA_DIR"] / schema_name
    if not path.is_file() or not schema_path.is_file():
        return {"errors": [f"cannot schema-check {role}: file or schema missing"], "detail": schema_name}
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return {"errors": [f"cannot read {role}: {exc}"], "detail": schema_name}
    import jsonschema  # noqa: PLC0415 - already a Harness dependency

    errors = [
        f"schema {schema_name}: {error.json_path}: {error.message}"
        for error in jsonschema.Draft202012Validator(schema).iter_errors(document)
    ]
    return {"errors": errors, "detail": f"{schema_name} ({len(errors)} violation(s))"}


TOOLS: dict[str, dict[str, Any]] = {
    "list_artifacts": {
        "description": (
            "Every artifact DAG node with recomputed freshness and drift reason. "
            "Read-only; the stored freshness field is never trusted."
        ),
        "properties": {"run_id": {"type": "string"}},
        "required": [],
        "handler": list_artifacts,
        "mutating": False,
    },
    "verify_artifact": {
        "description": (
            "Verify one artifact by id or path: file identity, digest drift, dependency and "
            "producer-receipt state, plus schema validity for contract roles."
        ),
        "properties": {
            "artifact_id": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": [],
        "handler": verify_artifact,
        "mutating": False,
    },
}

__all__ = ["CONTRACT_SCHEMA_BY_ROLE", "TOOLS", "list_artifacts", "verify_artifact"]
