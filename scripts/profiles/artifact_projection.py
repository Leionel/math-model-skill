"""Rebuildable v2 artifact/DAG/index projections and integrity helpers."""

from __future__ import annotations

import copy
import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, MutableMapping

V2 = "2.0"
ROLE_LIFECYCLE = {
    "frozen_results": "frozen", "submission_manifest": "submission", "submission_receipt": "submission",
    "paper": "immutable", "figure": "immutable", "table": "immutable", "pdf_visual_qa": "immutable", "support_package": "submission",
}
ROLE_KIND = {
    "problem": "problem_snapshot", "data": "data_contract", "preprocessing": "data_contract", "model": "model_output",
    "validation": "validation_report", "freeze": "frozen_results", "evidence": "evidence", "paper_plan": "paper_plan",
    "figure": "figure", "table": "table", "latex": "paper_source", "pdf_qa": "pdf_visual_qa", "submission": "submission_manifest",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    payload = __import__("json").dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _artifact_id(role: str, path: str, digest: str | None = None) -> str:
    token = hashlib.sha256(f"{role}|{path}|{digest or 'identity'}".encode("utf-8")).hexdigest()[:20].upper()
    return f"ART-{token}"


def _relpath(value: str | Path, root: Path | None) -> str:
    path = Path(value)
    if root is None or not path.is_absolute():
        return str(path).replace("\\", "/")
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _legacy_rows(manifest: Mapping[str, Any], dag: Mapping[str, Any] | None) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    conflicts: list[str] = []
    by_path: dict[str, set[str]] = {}

    def add(path: Any, role: Any, digest: Any, source: str) -> None:
        if not isinstance(path, str) or not path.strip():
            return
        normalized = path.replace("\\", "/")
        digest_value = str(digest).lower() if isinstance(digest, str) and re.fullmatch(r"[0-9a-fA-F]{64}", digest) else None
        if digest_value:
            by_path.setdefault(normalized, set()).add(digest_value)
        rows.append({"path": normalized, "role": str(role or "other"), "sha256": digest_value, "source": source})

    for index, row in enumerate(manifest.get("artifacts", []) if isinstance(manifest.get("artifacts"), list) else []):
        if isinstance(row, Mapping):
            add(row.get("path"), row.get("role"), row.get("sha256"), f"manifest.artifacts[{index}]")
    if isinstance(dag, Mapping) and isinstance(dag.get("nodes"), list):
        for index, node in enumerate(dag["nodes"]):
            if not isinstance(node, Mapping):
                continue
            role = ROLE_KIND.get(str(node.get("kind")), str(node.get("kind") or "other"))
            for field in ("inputs", "outputs"):
                for ref_index, ref in enumerate(node.get(field, []) if isinstance(node.get(field), list) else []):
                    if isinstance(ref, Mapping):
                        add(ref.get("path"), role, ref.get("sha256"), f"artifact_dag.nodes[{index}].{field}[{ref_index}]")
    for path, digests in by_path.items():
        if len(digests) > 1:
            conflicts.append(f"artifact path {path} has conflicting digests: {sorted(digests)}")
    critical_families = {"result", "frozen_results", "submission_manifest", "submission_package", "paper"}
    role_paths: dict[str, set[str]] = {}
    for row in rows:
        family = re.sub(r"_v[0-9]+$", "", str(row["role"]))
        if family in critical_families:
            role_paths.setdefault(family, set()).add(str(row["path"]))
    for family, paths in role_paths.items():
        if len(paths) > 1:
            conflicts.append(f"artifact role family {family} has multiple candidate paths: {sorted(paths)}")
    return rows, conflicts


def build_artifact_dag_v2(manifest: Mapping[str, Any], *, legacy_dag: Mapping[str, Any] | None = None, project_root: Path | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    """Project legacy manifest/DAG records into the existing DAG contract."""

    if isinstance(legacy_dag, Mapping) and legacy_dag.get("schema_version") == V2:
        return copy.deepcopy(dict(legacy_dag)), []
    rows, conflicts = _legacy_rows(manifest, legacy_dag)
    if not rows:
        return None, conflicts
    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["role"]), str(row["path"]))
        old = grouped.get(key)
        if old is None:
            grouped[key] = row
        elif old.get("sha256") and row.get("sha256") and old["sha256"] != row["sha256"]:
            conflicts.append(f"artifact role/path {key} has multiple canonical digests")
    path_ids = {path: _artifact_id(role, path, row.get("sha256")) for (role, path), row in grouped.items()}
    dependency_paths: dict[str, set[str]] = {}
    if isinstance(legacy_dag, Mapping) and isinstance(legacy_dag.get("nodes"), list):
        for node in legacy_dag["nodes"]:
            if not isinstance(node, Mapping):
                continue
            inputs = {str(ref["path"]).replace("\\", "/") for ref in node.get("inputs", []) if isinstance(ref, Mapping) and isinstance(ref.get("path"), str)}
            for ref in node.get("outputs", []):
                if isinstance(ref, Mapping) and isinstance(ref.get("path"), str):
                    dependency_paths.setdefault(str(ref["path"]).replace("\\", "/"), set()).update(inputs)
    nodes: list[dict[str, Any]] = []
    for (role, path), row in sorted(grouped.items()):
        digest = row.get("sha256")
        lifecycle = ROLE_LIFECYCLE.get(role, "mutable")
        node = {
            "artifact_id": _artifact_id(role, path, digest), "role": role, "path": _relpath(path, project_root),
            "producer_id": str(row.get("source") or "legacy-migration"), "dependencies": [
                {"artifact_id": path_ids[input_path], "relation": "legacy_input"}
                for input_path in sorted(dependency_paths.get(path, set())) if input_path in path_ids and path_ids[input_path] != _artifact_id(role, path, digest)
            ],
            "lifecycle": lifecycle,
            "freshness": "stale" if any(path in conflict for conflict in conflicts) else "unknown",
            "critical": lifecycle in ("frozen", "submission") or role in {"data_contract", "frozen_results", "paper", "figure", "table"},
            "version": "1", "created_at": _now(), "digest_owner": "artifact_dag",
        }
        if digest:
            node.update({"sha256": digest, "digest_algorithm": "sha256"})
        nodes.append(node)
    return {"schema_version": V2, "run_id": str(manifest.get("run_id") or "migrated-run"), "projection": "artifact_identity_dependency", "generated_at": _now(), "nodes": nodes}, conflicts


def normalize_run_index(legacy_index: Mapping[str, Any] | None, *, control_path: str = "run_manifest.json#/control/selection_policy") -> tuple[dict[str, Any] | None, dict[str, list[str]]]:
    notes = {"inferred": [], "unresolved": [], "manual_review_required": []}
    if not isinstance(legacy_index, Mapping):
        notes["unresolved"].append("legacy run_index is absent")
        notes["manual_review_required"].append("declare selection policy and register command receipts")
        return None, notes
    if legacy_index.get("schema_version") == V2:
        return copy.deepcopy(dict(legacy_index)), notes
    policy = legacy_index.get("selection_policy")
    if not isinstance(policy, str) or not policy.strip():
        notes["unresolved"].append("run_index.selection_policy is absent")
        notes["manual_review_required"].append("human must declare the selected-run rule")
    rows = legacy_index.get("runs") if isinstance(legacy_index.get("runs"), list) else []
    if not rows:
        notes["unresolved"].append("run_index.runs is absent or empty")
    projections: list[dict[str, Any]] = []
    selected: list[str] = []
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            notes["unresolved"].append(f"run_index.runs[{index}] is not an object")
            continue
        path = row.get("receipt_path")
        if not isinstance(path, str) or not path:
            notes["unresolved"].append(f"run_index.runs[{index}] has no receipt_path")
            continue
        receipt_id = str(row.get("command_id") or _artifact_id("receipt", path))
        is_selected = bool(row.get("selected", False))
        if is_selected:
            selected.append(receipt_id)
        projection = {
            "receipt_id": receipt_id, "receipt_path": path.replace("\\", "/"), "run_id": str(row.get("run_id") or "migrated-run"),
            "stage": str(row.get("stage") or "unknown"), "selected": is_selected, "recorded_at": str(row.get("recorded_at") or "legacy-unknown"),
            "projected_from": f"legacy.run_index.runs[{index}]",
        }
        if isinstance(row.get("exit_code"), int):
            projection["exit_code"] = row["exit_code"]
        projections.append(projection)
    if len(selected) > 1:
        notes["unresolved"].append(f"multiple selected legacy receipts: {selected}")
        notes["manual_review_required"].append("choose exactly one selected receipt or update the policy")
    elif not selected and projections:
        notes["unresolved"].append("legacy run_index has no selected receipt")
        notes["manual_review_required"].append("select exactly one receipt under the declared policy")
    return {
        "schema_version": V2, "projection": "receipt_selection", "run_id_scope": str(legacy_index.get("run_id_scope") or "migrated-run"),
        "receipts": projections, "selection": {"policy_ref": {"owner": "run_manifest.control", "path": control_path, "version": V2}, "selected_receipt_ids": selected}, "generated_at": _now(),
    }, notes


def invalidate_downstream(dag: Mapping[str, Any], artifact_id: str, *, new_sha256: str | None = None, new_path: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a version for immutable updates and mark dependent nodes stale."""

    result = copy.deepcopy(dict(dag))
    nodes = result.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("artifact DAG must contain a nodes array")
    source = next((node for node in nodes if isinstance(node, Mapping) and node.get("artifact_id") == artifact_id), None)
    if source is None:
        raise ValueError(f"artifact_id not found in DAG: {artifact_id}")
    old_lifecycle, old_version = str(source.get("lifecycle") or "mutable"), str(source.get("version") or "1")
    try:
        version = str(int(old_version) + 1)
    except ValueError:
        version = f"{old_version}.2"
    changed_id = artifact_id
    if old_lifecycle in ("immutable", "frozen", "submission"):
        changed_id = f"{artifact_id}-v{version}"
        updated = copy.deepcopy(dict(source)); updated.update({"artifact_id": changed_id, "version": version, "freshness": "current", "created_at": _now()})
        if new_path is not None:
            updated["path"] = new_path
        if new_sha256 is not None:
            updated.update({"sha256": new_sha256, "digest_algorithm": "sha256"})
        nodes.append(updated)
    else:
        source["version"], source["freshness"] = version, "current"
        if new_path is not None:
            source["path"] = new_path
        if new_sha256 is not None:
            source.update({"sha256": new_sha256, "digest_algorithm": "sha256"})
    stale: set[str] = set()
    changed = True
    while changed:
        changed = False
        for node in nodes:
            if not isinstance(node, Mapping):
                continue
            deps = node.get("dependencies") if isinstance(node.get("dependencies"), list) else []
            dep_ids = {dep.get("artifact_id") for dep in deps if isinstance(dep, Mapping)}
            if dep_ids.intersection({artifact_id, changed_id, *stale}) and node.get("artifact_id") not in stale:
                stale.add(str(node.get("artifact_id"))); changed = True
    for node in nodes:
        if isinstance(node, MutableMapping) and node.get("artifact_id") in stale:
            node["freshness"] = "stale"
    return result, {"changed_artifact_id": changed_id, "historical_artifact_id": artifact_id if changed_id != artifact_id else None, "invalidated_artifact_ids": sorted(stale), "immutable_history_preserved": changed_id != artifact_id}


def validate_artifact_dag_ownership(dag: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    if not isinstance(dag, Mapping) or dag.get("schema_version") != V2:
        return ["artifact DAG ownership validation requires schema_version=2.0"]
    nodes = dag.get("nodes")
    if not isinstance(nodes, list):
        return ["artifact DAG nodes must be an array"]
    ids: set[str] = set(); owners: dict[str, set[str]] = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, Mapping):
            errors.append(f"nodes[{index}] is not an object"); continue
        artifact_id, path, owner = str(node.get("artifact_id") or ""), str(node.get("path") or ""), str(node.get("digest_owner") or "")
        if not artifact_id:
            errors.append(f"nodes[{index}] has no artifact_id")
        elif artifact_id in ids:
            errors.append(f"duplicate artifact_id: {artifact_id}")
        ids.add(artifact_id)
        if not owner:
            errors.append(f"nodes[{index}] has no digest_owner")
        if isinstance(node.get("sha256"), str) and isinstance(node.get("digest"), str):
            errors.append(f"nodes[{index}] records both sha256 and digest; choose one canonical field")
        if (isinstance(node.get("sha256"), str) or isinstance(node.get("digest"), str)) and path:
            owners.setdefault(path, set()).add(owner)
    for path, values in owners.items():
        if len(values) > 1:
            errors.append(f"artifact path {path} has multiple digest owners: {sorted(values)}")
    return errors


__all__ = ["sha256_file", "sha256_json", "build_artifact_dag_v2", "normalize_run_index", "invalidate_downstream", "validate_artifact_dag_ownership"]
