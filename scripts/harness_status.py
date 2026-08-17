#!/usr/bin/env python3
"""Derive a read-only status view from the v2 control plane.

This module deliberately does not update a manifest, write a receipt, or
create a digest. Gate truth comes from the existing v2 gate runtime; the
status command is only a projection for humans and agents. v1 is shown with
an explicit deprecation marker and is never presented as a v2 status view.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_structured, rel_path, resolve_path  # noqa: E402
from runtime_state import RuntimeStateError, load_runtime_state  # noqa: E402
from v2_gate_runtime import _v2_gate  # noqa: E402

GATE_ORDER = ("m1", "p1", "p2", "w1", "w2", "s1")
CONFIRMED = {"pass", "confirm"}


def _checkpoint_view(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "checkpoint_id": row.get("checkpoint_id"),
        "stage": row.get("stage"),
        "scope": row.get("scope"),
        "decision": row.get("decision"),
        "manual_checks": row.get("manual_checks", []),
        "reviewed_by_role": row.get("reviewed_by_role"),
    }


def _pending_checkpoints(manifest: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = manifest.get("human_checkpoints", [])
    if not isinstance(rows, list):
        rows = []
    by_stage: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        if isinstance(row, Mapping) and isinstance(row.get("stage"), str):
            by_stage.setdefault(str(row["stage"]), []).append(row)
    control = manifest.get("control")
    required = control.get("required_human_stages", []) if isinstance(control, Mapping) else []
    if not isinstance(required, list):
        required = []
    pending: list[dict[str, Any]] = []
    for stage in required:
        if not isinstance(stage, str):
            continue
        candidates = by_stage.get(stage, [])
        if not any(row.get("decision") in CONFIRMED for row in candidates):
            pending.append(_checkpoint_view(candidates[-1]) if candidates else {"stage": stage, "decision": None})
    # Keep explicitly requested checkpoints even when a v2 control document
    # comes from an older adapter without required_human_stages.
    for stage, candidates in by_stage.items():
        if candidates and not any(row.get("decision") in CONFIRMED for row in candidates):
            if not any(item.get("stage") == stage for item in pending):
                pending.append(_checkpoint_view(candidates[-1]))
    return pending


def _receipt_view(state: Any) -> dict[str, Any]:
    index_path = state.root_path("run_index")
    result: dict[str, Any] = {
        "index": rel_path(index_path, state.root) if index_path is not None else None,
        "count": 0,
        "selected_receipt_ids": [],
        "successful_stages": [],
        "failed_receipt_ids": [],
        "errors": [],
    }
    if index_path is None or not index_path.is_file():
        result["errors"].append("v2 run_index root is missing")
        return result
    try:
        index = load_structured(index_path)
    except (OSError, ValueError, TypeError) as exc:
        result["errors"].append(f"cannot read run_index: {exc}")
        return result
    if not isinstance(index, Mapping):
        result["errors"].append("run_index must be an object")
        return result
    rows = index.get("receipts", [])
    if not isinstance(rows, list):
        result["errors"].append("run_index.receipts must be an array")
        return result
    selected = index.get("selection", {})
    selected_ids = selected.get("selected_receipt_ids", []) if isinstance(selected, Mapping) else []
    if isinstance(selected_ids, list):
        result["selected_receipt_ids"] = [str(value) for value in selected_ids]
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("receipt_id"), str):
            result["errors"].append("run_index contains an invalid receipt projection")
            continue
        result["count"] += 1
        receipt_id = str(row["receipt_id"])
        raw_path = row.get("receipt_path")
        if not isinstance(raw_path, str):
            result["errors"].append(f"receipt {receipt_id} has no receipt_path")
            continue
        receipt_path = resolve_path(raw_path, state.root).resolve()
        if not receipt_path.is_file():
            result["errors"].append(f"receipt {receipt_id} does not exist: {raw_path}")
            continue
        try:
            receipt = load_structured(receipt_path)
        except (OSError, ValueError, TypeError) as exc:
            result["errors"].append(f"cannot read receipt {receipt_id}: {exc}")
            continue
        if not isinstance(receipt, Mapping) or receipt.get("receipt_id") != receipt_id:
            result["errors"].append(f"receipt identity mismatch for {receipt_id}")
            continue
        metadata = receipt.get("metadata")
        outcome = metadata.get("outcome") if isinstance(metadata, Mapping) else None
        if receipt.get("exit_code") == 0 and outcome != "failed":
            stage = str(receipt.get("stage", row.get("stage", "unknown")))
            if stage not in result["successful_stages"]:
                result["successful_stages"].append(stage)
        else:
            result["failed_receipt_ids"].append(receipt_id)
    return result


def _dag_view(state: Any) -> dict[str, Any]:
    """Return current/stale information without writing a projection."""

    dag_path = state.root_path("artifact_dag")
    result: dict[str, Any] = {
        "path": rel_path(dag_path, state.root) if dag_path is not None else None,
        "artifacts": [],
        "stale_artifacts": [],
        "errors": [],
    }
    if dag_path is None or not dag_path.is_file():
        result["errors"].append("v2 artifact DAG root is missing")
        return result
    try:
        dag = load_structured(dag_path)
    except (OSError, ValueError, TypeError) as exc:
        result["errors"].append(f"cannot read artifact DAG: {exc}")
        return result
    if not isinstance(dag, Mapping):
        result["errors"].append("artifact DAG must be an object")
        return result
    try:
        from artifact_dag_projector import project_artifact_dag

        projection, errors, events = project_artifact_dag(dag, project_root=state.root)
    except (ImportError, OSError, ValueError, TypeError) as exc:
        result["errors"].append(f"cannot project artifact DAG: {exc}")
        return result
    result["errors"].extend(str(item) for item in errors)
    nodes = projection.get("nodes", []) if isinstance(projection, Mapping) else []
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, Mapping):
            continue
        item = {
            "artifact_id": node.get("artifact_id"),
            "role": node.get("role"),
            "path": node.get("path"),
            "lifecycle": node.get("lifecycle"),
            "freshness": node.get("freshness"),
        }
        result["artifacts"].append(item)
        if item["freshness"] != "current":
            result["stale_artifacts"].append(item)
    # Events contain expected/actual hashes. Keep only causal identity in the
    # status view; status is not an integrity registry.
    for event in events:
        if isinstance(event, Mapping):
            result["stale_artifacts"].append({
                "artifact_id": event.get("artifact_id"),
                "lifecycle": event.get("lifecycle"),
                "reason": event.get("reason"),
            })
    return result


def _next_action(first_blocked: Any, pending: list[dict[str, Any]], stale: list[dict[str, Any]]) -> str:
    if pending:
        stage = pending[0].get("stage") or "required"
        return f"human review pending on stage {str(stage).upper()}"
    if stale:
        return "refresh or rerun stale artifacts, then recheck the first blocked Gate"
    if first_blocked:
        gate = first_blocked[0] if isinstance(first_blocked, (tuple, list)) else first_blocked
        return f"produce the missing evidence for {str(gate).upper()} and rerun `harness check {str(gate).upper()}`"
    return "all observed gates pass; continue with the next human checkpoint or submission freeze"


def _v2_status(state: Any) -> dict[str, Any]:
    pending = _pending_checkpoints(state.manifest)
    receipts = _receipt_view(state)
    dag = _dag_view(state)
    gate_reports: dict[str, dict[str, Any]] = {}
    first_blocked: str | None = None
    for gate in GATE_ORDER:
        try:
            ok, errors, warnings, evidence = _v2_gate(state, gate)
        except (OSError, ValueError, TypeError, RuntimeStateError) as exc:
            ok, errors, warnings, evidence = False, [str(exc)], [], {}
        gate_reports[gate] = {
            "status": "pass" if ok else "blocked",
            "ok": bool(ok),
            "errors": list(errors),
            "warnings": list(warnings),
            "evidence_keys": sorted(str(key) for key in evidence),
        }
        if not ok and first_blocked is None:
            first_blocked = gate
            break
    return {
        "ok": True,
        "schema_version": "2.0",
        "deprecated": False,
        "source_of_truth": ["normalized run_manifest control", "command receipts", "run_index projection", "artifact DAG freshness", "fact gate runtime"],
        "project_id": state.manifest.get("project_id"),
        "run_id": state.manifest.get("run_id"),
        "status": state.manifest.get("status"),
        "stage": state.manifest.get("stage"),
        "preset": state.preset,
        "profile": {
            "path": rel_path(state.profile_path, state.root),
            "profile_id": state.profile.get("profile_id"),
            "status": state.profile.get("status"),
        },
        "capabilities": state.capabilities.to_dict(),
        "gates": gate_reports,
        "first_blocked_gate": first_blocked,
        "pending_human_checkpoints": pending,
        "receipts": receipts,
        "dag": dag,
        "stale_artifacts": dag["stale_artifacts"],
        "next_action": _next_action(first_blocked, pending, dag["stale_artifacts"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _v1_status(manifest: Mapping[str, Any], root: Path, manifest_path: Path) -> dict[str, Any]:
    gates = manifest.get("gates", {})
    statuses: dict[str, str] = {}
    for name in GATE_ORDER:
        gate = gates.get(name, {}) if isinstance(gates, Mapping) else {}
        statuses[name] = str(gate.get("status", "missing")) if isinstance(gate, Mapping) else "invalid"
    first_name = next((name for name in GATE_ORDER if statuses[name] != "pass"), None)
    first = (first_name, statuses[first_name]) if first_name is not None else None
    rows = manifest.get("human_checkpoints", [])
    pending = [
        _checkpoint_view(row)
        for row in rows
        if isinstance(row, Mapping) and row.get("decision") in {"ask", None}
    ] if isinstance(rows, list) else []
    artifacts = manifest.get("artifacts", [])
    missing: list[str] = []
    if isinstance(artifacts, list):
        for row in artifacts:
            if not isinstance(row, Mapping) or not isinstance(row.get("path"), str):
                continue
            path = str(row["path"])
            if not path.startswith(("http://", "https://")) and not resolve_path(path, root).is_file():
                missing.append(path)
    return {
        "ok": True,
        "schema_version": str(manifest.get("schema_version", "v1")),
        "deprecated": True,
        "deprecation": "v1 manifest status is read-only; run `harness migrate --project <path>` before promotion",
        "source_of_truth": ["legacy run_manifest.gates (deprecated view only)"],
        "manifest": rel_path(manifest_path, root),
        "project_id": manifest.get("project_id"),
        "run_id": manifest.get("run_id"),
        "status": manifest.get("status"),
        "phase": manifest.get("phase"),
        "gates": statuses,
        "first_blocked_gate": first,
        "pending_human_checkpoints": pending,
        "missing_registered_files": missing,
        "next_action": _next_action(first, pending, [{"path": path} for path in missing]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def status_report(manifest: dict[str, Any], root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    """Return a read-only status report for a loaded manifest."""

    path = manifest_path or (root / "run_manifest.json")
    if manifest.get("schema_version") == "2.0":
        try:
            return _v2_status(load_runtime_state(path, project_root=root, allow_legacy=False))
        except (OSError, ValueError, TypeError, RuntimeStateError) as exc:
            return {
                "ok": False,
                "deprecated": False,
                "schema_version": "2.0",
                "manifest": rel_path(path, root),
                "errors": [str(exc)],
                "first_blocked_gate": "m1",
                "next_action": "repair the v2 control/profile boundary before running a Gate",
            }
    return _v1_status(manifest, root, path)


def _human(report: Mapping[str, Any]) -> str:
    lines = [
        f"project: {report.get('project_id')}  run: {report.get('run_id')}  status: {report.get('status')}",
        f"schema: {report.get('schema_version')}  preset: {report.get('preset', report.get('phase', 'legacy'))}",
        "gates: " + "  ".join(
            f"{name.upper()}:{value.get('status', value) if isinstance(value, Mapping) else value}"
            for name, value in (report.get("gates", {}) or {}).items()
        ),
    ]
    if report.get("deprecated"):
        lines.append("DEPRECATED: this is a v1 manifest view; migrate before promotion")
    if report.get("first_blocked_gate"):
        blocked = report["first_blocked_gate"]
        blocked_name = blocked[0] if isinstance(blocked, (tuple, list)) else blocked
        lines.append(f"first blocked gate: {str(blocked_name).upper()}")
    pending = report.get("pending_human_checkpoints", [])
    if pending:
        lines.append(f"pending human checkpoints: {len(pending)}")
        for row in pending:
            lines.append(f"  - {str(row.get('stage', 'unknown')).upper()} [{row.get('decision') or 'unset'}]")
    stale = report.get("stale_artifacts", [])
    if stale:
        lines.append(f"stale artifacts: {len(stale)}")
        for row in stale[:10]:
            lines.append(f"  - {row.get('artifact_id')}: {row.get('path', row.get('reason', 'stale'))}")
    if report.get("errors"):
        lines.append("errors:")
        lines.extend(f"  - {error}" for error in report["errors"])
    lines.append(f"next action: {report.get('next_action')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default="run_manifest.json")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    manifest_path = resolve_path(args.manifest, root).resolve()
    try:
        manifest = load_structured(manifest_path)
    except (OSError, ValueError, TypeError) as exc:
        report = {"ok": False, "errors": [f"cannot read manifest: {exc}"], "manifest": rel_path(manifest_path, root)}
        print(json.dumps(report, ensure_ascii=False) if args.json else _human(report))
        return 2
    if not isinstance(manifest, dict):
        report = {"ok": False, "errors": ["run_manifest must be an object"]}
        print(json.dumps(report, ensure_ascii=False) if args.json else _human(report))
        return 2
    report = status_report(manifest, root, manifest_path)
    print(json.dumps(report, ensure_ascii=False) if args.json else _human(report))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
