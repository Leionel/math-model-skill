"""Explicit migration of v2 control files from the root into ``.harness``.

This is deliberately narrower than the existing v1-to-v2 adapter.  It moves
only the four mutable v2 control documents after verifying that all normal
readers can resolve the hidden layout.  Receipts, frozen artifacts and other
historical evidence are neither copied nor rewritten.
"""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any, Mapping

from _common import exclusive_path_lock, load_structured, rel_path, resolve_path, write_json_atomic
from profiles.normalization import NormalizationError, normalize_manifest
from project_layout import (
    CONTROL_FILENAMES,
    StateLayoutError,
    active_state_layout,
    control_paths,
    hidden_state_dir,
    layout_marker_path,
    resolve_control_path,
    write_hidden_layout_marker,
)
from runtime_state import RuntimeStateError, load_runtime_state


REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_BY_FILE = {
    "competition_profile.json": "competition_profile.schema.json",
    "run_manifest.json": "run_manifest.schema.json",
    "artifact_dag.json": "artifact_dag.schema.json",
    "run_index.json": "run_index.schema.json",
}


class StateLayoutMigrationError(ValueError):
    """The v2 control state cannot safely be relocated."""


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _load_json_object(path: Path, name: str) -> dict[str, Any]:
    try:
        value = load_structured(path)
    except (OSError, ValueError, TypeError) as exc:
        raise StateLayoutMigrationError(f"cannot read {name}: {exc}") from exc
    if not isinstance(value, Mapping):
        raise StateLayoutMigrationError(f"{name} must be a JSON object")
    return copy.deepcopy(dict(value))


def _path_from_ref(value: Any, root: Path, owner: str) -> Path:
    raw = value.get("path") if isinstance(value, Mapping) else value
    if not isinstance(raw, str) or not raw.strip():
        raise StateLayoutMigrationError(f"{owner}.path must be a non-empty path")
    return resolve_path(raw, root).resolve()


def _policy_target(value: Any, root: Path) -> tuple[Path, str]:
    if not isinstance(value, Mapping):
        raise StateLayoutMigrationError("run_index.selection.policy_ref must be an object")
    raw = value.get("path")
    if not isinstance(raw, str) or "#" not in raw:
        raise StateLayoutMigrationError("run_index.selection.policy_ref.path must include a manifest JSON pointer")
    source, fragment = raw.split("#", 1)
    if fragment != "/control/selection_policy":
        raise StateLayoutMigrationError("run_index.selection.policy_ref must point to /control/selection_policy")
    return resolve_path(source, root).resolve(), fragment


def _schema_errors(name: str, value: Mapping[str, Any]) -> list[str]:
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - doctor marks jsonschema required
        raise RuntimeError("state-layout migration requires jsonschema; install requirements-dev.txt") from exc
    schema_path = REPO_ROOT / "schemas" / SCHEMA_BY_FILE[name]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [error.message for error in sorted(validator.iter_errors(dict(value)), key=lambda error: list(error.absolute_path))]


def _require_v2_source(root: Path) -> tuple[dict[str, Path], dict[str, dict[str, Any]], dict[str, bytes]]:
    try:
        layout = active_state_layout(root)
    except StateLayoutError as exc:
        raise StateLayoutMigrationError(str(exc)) from exc
    if layout != "flat":
        raise StateLayoutMigrationError("state-layout migration requires an active root-level v2 control layout")
    sources = control_paths(root, "flat")
    missing = [name for name, path in sources.items() if not path.is_file()]
    if missing:
        raise StateLayoutMigrationError("root-level v2 control layout is incomplete; missing " + ", ".join(missing))
    values = {name: _load_json_object(path, name) for name, path in sources.items()}
    if any(value.get("schema_version") != "2.0" for value in values.values()):
        raise StateLayoutMigrationError(
            "state-layout migration accepts only v2 control files; run the existing v1-to-v2 migration first"
        )
    for name, value in values.items():
        errors = _schema_errors(name, value)
        if errors:
            raise StateLayoutMigrationError(f"{name} fails its schema before relocation: {errors[0]}")
    try:
        state = load_runtime_state(sources["run_manifest.json"], project_root=root, allow_legacy=False)
    except (OSError, ValueError, TypeError, RuntimeStateError) as exc:
        raise StateLayoutMigrationError(f"flat v2 runtime boundary is not valid: {exc}") from exc
    if state.profile_path != sources["competition_profile.json"]:
        raise StateLayoutMigrationError("migration requires competition_profile_ref to resolve to root-level competition_profile.json")
    for root_name, filename in (("artifact_dag", "artifact_dag.json"), ("run_index", "run_index.json")):
        if state.root_path(root_name, required=True) != sources[filename]:
            raise StateLayoutMigrationError(
                f"migration requires run_manifest.roots.{root_name} to resolve to root-level {filename}"
            )
    raw_bytes = {name: path.read_bytes() for name, path in sources.items()}
    return sources, values, raw_bytes


def _relocate_documents(root: Path, sources: Mapping[str, Path], values: Mapping[str, Mapping[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Return target documents and an auditable list of rewritten pointers."""

    targets = control_paths(root, "hidden")
    manifest = copy.deepcopy(dict(values["run_manifest.json"]))
    profile_ref = manifest.get("competition_profile_ref")
    if _path_from_ref(profile_ref, root, "run_manifest.competition_profile_ref") != sources["competition_profile.json"]:
        raise StateLayoutMigrationError("competition_profile_ref does not bind the root-level profile")
    assert isinstance(profile_ref, dict)
    profile_ref["path"] = rel_path(targets["competition_profile.json"], root)

    roots = manifest.get("roots")
    if not isinstance(roots, dict):
        raise StateLayoutMigrationError("run_manifest.roots must be an object")
    rewritten = ["run_manifest.competition_profile_ref.path"]
    for root_name, filename in (("artifact_dag", "artifact_dag.json"), ("run_index", "run_index.json")):
        reference = roots.get(root_name)
        if _path_from_ref(reference, root, f"run_manifest.roots.{root_name}") != sources[filename]:
            raise StateLayoutMigrationError(f"run_manifest.roots.{root_name} does not bind {filename}")
        assert isinstance(reference, dict)
        reference["path"] = rel_path(targets[filename], root)
        rewritten.append(f"run_manifest.roots.{root_name}.path")
    try:
        normalize_manifest(manifest, project_root=root)
    except (NormalizationError, ValueError, TypeError) as exc:
        raise StateLayoutMigrationError(f"relocated run_manifest is not a valid v2 control document: {exc}") from exc

    dag = copy.deepcopy(dict(values["artifact_dag.json"]))
    nodes = dag.get("nodes")
    if not isinstance(nodes, list):
        raise StateLayoutMigrationError("artifact_dag.nodes must be an array")
    for index, node in enumerate(nodes):
        if not isinstance(node, dict) or not isinstance(node.get("path"), str):
            continue
        if resolve_path(node["path"], root).resolve() == sources["competition_profile.json"]:
            node["path"] = rel_path(targets["competition_profile.json"], root)
            rewritten.append(f"artifact_dag.nodes[{index}].path")

    index = copy.deepcopy(dict(values["run_index.json"]))
    selection = index.get("selection")
    if not isinstance(selection, dict):
        raise StateLayoutMigrationError("run_index.selection must be an object")
    policy = selection.get("policy_ref")
    policy_path, fragment = _policy_target(policy, root)
    if policy_path != sources["run_manifest.json"]:
        raise StateLayoutMigrationError("run_index.selection.policy_ref does not bind root-level run_manifest.json")
    assert isinstance(policy, dict)
    policy["path"] = f"{rel_path(targets['run_manifest.json'], root)}#{fragment}"
    rewritten.append("run_index.selection.policy_ref.path")

    documents: dict[str, Any] = {
        "competition_profile.json": copy.deepcopy(dict(values["competition_profile.json"])),
        "run_manifest.json": manifest,
        "artifact_dag.json": dag,
        "run_index.json": index,
    }
    for name, value in documents.items():
        errors = _schema_errors(name, value)
        if errors:
            raise StateLayoutMigrationError(f"relocated {name} fails its schema: {errors[0]}")
    return documents, rewritten


def _migration_report(
    root: Path,
    *,
    sources: Mapping[str, Path],
    raw_bytes: Mapping[str, bytes],
    documents: Mapping[str, Any],
    rewritten: list[str],
    status: str,
) -> dict[str, Any]:
    targets = control_paths(root, "hidden")
    rows = []
    for name in CONTROL_FILENAMES:
        target_bytes = raw_bytes[name] if name == "competition_profile.json" else _json_bytes(documents[name])
        rows.append({
            "name": name,
            "from": rel_path(sources[name], root),
            "to": rel_path(targets[name], root),
            "source_sha256": hashlib.sha256(raw_bytes[name]).hexdigest(),
            "target_sha256": hashlib.sha256(target_bytes).hexdigest(),
        })
    return {
        "schema_version": "1.0",
        "kind": "v2_control_state_layout",
        "status": status,
        "source_layout": "flat",
        "target_layout": "hidden",
        "control_documents": rows,
        "rewritten_references": rewritten,
        "preserved": [
            "receipts, frozen artifacts, evidence, results, reports, and author documents were not moved or rewritten",
            "the profile bytes are preserved exactly so any existing profile digest remains valid",
        ],
        "gate_note": "This migration changes control-file locations only. It creates no Gate PASS, receipt, freshness value, or frozen result.",
    }


def _rollback(root: Path, state_dir: Path, source_bytes: Mapping[str, bytes]) -> None:
    """Restore the flat layout after a failed post-staging commit."""

    marker = layout_marker_path(root)
    marker.unlink(missing_ok=True)
    for name, payload in source_bytes.items():
        path = control_paths(root, "flat")[name]
        if not path.exists():
            path.write_bytes(payload)
    if state_dir.exists():
        shutil.rmtree(state_dir)


def migrate_flat_control_state_to_hidden(root: Path | str, *, apply: bool = False) -> dict[str, Any]:
    """Plan or apply the explicit flat-v2 to hidden-control layout move.

    Planning is read-only.  Applying requires the caller to opt in and uses a
    staging directory plus rollback so a failed file operation does not leave
    a silently ambiguous active layout.
    """

    project = Path(root).resolve()
    with exclusive_path_lock(layout_marker_path(project)):
        sources, values, raw_bytes = _require_v2_source(project)
        documents, rewritten = _relocate_documents(project, sources, values)
        report = _migration_report(
            project,
            sources=sources,
            raw_bytes=raw_bytes,
            documents=documents,
            rewritten=rewritten,
            status="ready" if not apply else "migrated",
        )
        if not apply:
            report["apply_required"] = True
            return report

        state_dir = hidden_state_dir(project)
        if state_dir.exists():
            raise StateLayoutMigrationError(f"refusing to overwrite existing hidden state directory: {state_dir}")
        staging = state_dir.parent / f".state-layout-{uuid.uuid4().hex}.tmp"
        staging.mkdir(parents=True, exist_ok=False)
        try:
            for name in CONTROL_FILENAMES:
                payload = raw_bytes[name] if name == "competition_profile.json" else _json_bytes(documents[name])
                (staging / name).write_bytes(payload)
            staging.replace(state_dir)
            try:
                target_manifest = state_dir / "run_manifest.json"
                load_runtime_state(target_manifest, project_root=project, allow_legacy=False)
                for path in sources.values():
                    path.unlink()
                write_hidden_layout_marker(project)
                active_manifest = resolve_control_path(project, "run_manifest.json")
                load_runtime_state(active_manifest, project_root=project, allow_legacy=False)
            except Exception:
                _rollback(project, state_dir, raw_bytes)
                raise
        finally:
            if staging.exists():
                shutil.rmtree(staging)

        report["apply_required"] = False
        report_path = project / ".harness" / "reports" / "state_layout_migration.json"
        report["report_path"] = rel_path(report_path, project)
        write_json_atomic(report_path, report)
        return report


__all__ = ["StateLayoutMigrationError", "migrate_flat_control_state_to_hidden"]
