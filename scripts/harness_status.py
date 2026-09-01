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
from project_layout import resolve_manifest_path  # noqa: E402
from runtime_state import RuntimeStateError, load_runtime_state  # noqa: E402
from v2_gate_runtime import _v2_gate  # noqa: E402
from redaction import redact_text  # noqa: E402
from ruleset import ruleset_fingerprint  # noqa: E402

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


def _review_view(state: Any) -> dict[str, Any]:
    """Project review state through the same evidence boundary as the W2 gate."""

    try:
        from qa.review_evidence import summarize_review  # type: ignore
    except ImportError:  # pragma: no cover - direct-script import edge
        from review_evidence import summarize_review  # type: ignore
    try:
        return summarize_review(state.root, state.preset, run_id=state.run_id, require_registration=True)
    except (OSError, ValueError, TypeError) as exc:
        return {"error": f"cannot summarize review evidence: {exc}", "perspectives": {}}


def _next_action(first_blocked: Any, pending: list[dict[str, Any]], stale: list[dict[str, Any]], review: dict[str, Any] | None = None) -> str:
    # The gate order keeps priority; review guidance is appended so an open
    # finding stays visible without outranking an earlier blocked gate.
    primary: str | None = None
    if pending:
        stage = pending[0].get("stage") or "required"
        primary = f"human review pending on stage {str(stage).upper()}"
    elif stale:
        primary = "refresh or rerun stale artifacts, then recheck the first blocked Gate"
    elif first_blocked:
        gate = first_blocked[0] if isinstance(first_blocked, (tuple, list)) else first_blocked
        primary = f"produce the missing evidence for {str(gate).upper()} and rerun `harness check {str(gate).upper()}`"
    suffix = ""
    if isinstance(review, dict):
        blocked_name = first_blocked[0] if isinstance(first_blocked, (tuple, list)) else first_blocked
        if blocked_name is None or blocked_name == "w2":
            finding = review.get("next_finding")
            if isinstance(finding, dict) and finding.get("finding_id"):
                return f"fix {finding['finding_id']}: {finding.get('summary', '')}"
            unexecuted = [
                name for name, view in (review.get("perspectives") or {}).items()
                if isinstance(view, dict) and view.get("required") and not view.get("executed")
            ]
            if unexecuted and (primary is None or blocked_name == "w2"):
                return f"run `harness review` to produce missing review evidence: {', '.join(unexecuted)}"
        finding = review.get("next_finding")
        if isinstance(finding, dict) and finding.get("finding_id"):
            suffix = f"; open review finding {finding['finding_id']}"
    if primary is not None:
        return primary + suffix
    return "all observed gates pass; continue with the next human checkpoint or submission freeze" + suffix


def _failures_summary(
    gates: Mapping[str, Mapping[str, Any]],
    pending: list[dict[str, Any]],
    receipts: Mapping[str, Any],
    dag: Mapping[str, Any],
    review: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Derive one repair-oriented view without creating another artifact."""

    items: list[dict[str, Any]] = []

    def add(source: str, message: Any, *, severity: str = "error", identifier: Any = None, next_action: str | None = None) -> None:
        items.append({
            "source": source,
            "id": str(identifier) if identifier is not None else None,
            "severity": severity,
            "message": redact_text(str(message)),
            "next_action": next_action or "inspect the referenced source and rerun the read-only status check",
        })

    for gate, view in gates.items():
        if not isinstance(view, Mapping):
            continue
        if view.get("status") != "pass":
            for error in view.get("errors", []) if isinstance(view.get("errors"), list) else []:
                add("gate", error, identifier=gate, next_action=f"repair {str(gate).upper()} evidence and rerun `harness check {str(gate).upper()}`")
            for warning in view.get("warnings", []) if isinstance(view.get("warnings"), list) else []:
                add("gate", warning, severity="warning", identifier=gate)
    for error in receipts.get("errors", []) if isinstance(receipts.get("errors"), list) else []:
        add("receipt", error, next_action="repair the run-index/receipt binding, then rerun status")
    for receipt_id in receipts.get("failed_receipt_ids", []) if isinstance(receipts.get("failed_receipt_ids"), list) else []:
        add("receipt", "receipt recorded a failed command", identifier=receipt_id, next_action="inspect the receipt and rerun the failed command only after fixing its cause")
    for row in dag.get("stale_artifacts", []) if isinstance(dag.get("stale_artifacts"), list) else []:
        if isinstance(row, Mapping):
            add("artifact", row.get("reason", "artifact is stale"), identifier=row.get("artifact_id"), next_action="refresh the producer output and rerun the downstream Gate")
    for row in pending:
        if isinstance(row, Mapping):
            add("checkpoint", f"human checkpoint pending for stage {row.get('stage', 'unknown')}", severity="pending", identifier=row.get("checkpoint_id"), next_action="obtain the required human decision before continuing")
    if isinstance(review, Mapping):
        perspectives = review.get("perspectives", {})
        if isinstance(perspectives, Mapping):
            for name, view in perspectives.items():
                if not isinstance(view, Mapping):
                    continue
                for error in view.get("errors", []) if isinstance(view.get("errors"), list) else []:
                    add("review", error, identifier=name, next_action="repair or rerun the review evidence before W2")
                for finding_id in view.get("scope_limited_ids", []) if isinstance(view.get("scope_limited_ids"), list) else []:
                    add("review", "finding requires evidence outside the current review scope", severity="external_check", identifier=finding_id, next_action="perform the required external evidence check before accepting the review")
    return {"count": len(items), "items": items}


def _v2_status(state: Any, *, ruleset: Mapping[str, Any] | None = None) -> dict[str, Any]:
    ruleset = ruleset or ruleset_fingerprint(SCRIPT_DIR.parent)
    pending = _pending_checkpoints(state.manifest)
    receipts = _receipt_view(state)
    dag = _dag_view(state)
    review = _review_view(state)
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
        "ruleset_id": ruleset["ruleset_id"],
        "ruleset_scope": ruleset["ruleset_scope"],
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
        "review": review,
        "failures_summary": _failures_summary(gate_reports, pending, receipts, dag, review),
        "next_action": _next_action(first_blocked, pending, dag["stale_artifacts"], review),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def _v1_status(
    manifest: Mapping[str, Any],
    root: Path,
    manifest_path: Path,
    *,
    ruleset: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    ruleset = ruleset or ruleset_fingerprint(SCRIPT_DIR.parent)
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
        "ruleset_id": ruleset["ruleset_id"],
        "ruleset_scope": ruleset["ruleset_scope"],
        "gates": statuses,
        "first_blocked_gate": first,
        "pending_human_checkpoints": pending,
        "missing_registered_files": missing,
        "next_action": _next_action(first, pending, [{"path": path} for path in missing]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def status_report(manifest: dict[str, Any], root: Path, manifest_path: Path | None = None) -> dict[str, Any]:
    """Return a read-only status report for a loaded manifest."""

    path = manifest_path or resolve_manifest_path(root)
    ruleset = ruleset_fingerprint(SCRIPT_DIR.parent)
    if manifest.get("schema_version") == "2.0":
        try:
            return _v2_status(load_runtime_state(path, project_root=root, allow_legacy=False), ruleset=ruleset)
        except (OSError, ValueError, TypeError, RuntimeStateError) as exc:
            return {
                "ok": False,
                "deprecated": False,
                "schema_version": "2.0",
                "manifest": rel_path(path, root),
                "ruleset_id": ruleset["ruleset_id"],
                "ruleset_scope": ruleset["ruleset_scope"],
                "errors": [str(exc)],
                "first_blocked_gate": "m1",
                "next_action": "repair the v2 control/profile boundary before running a Gate",
            }
    return _v1_status(manifest, root, path, ruleset=ruleset)


def _human(report: Mapping[str, Any]) -> str:
    lines = [
        f"project: {report.get('project_id')}  run: {report.get('run_id')}  status: {report.get('status')}",
        f"schema: {report.get('schema_version')}  preset: {report.get('preset', report.get('phase', 'legacy'))}",
        f"ruleset: {report.get('ruleset_id')}  files: {((report.get('ruleset_scope') or {}).get('file_count', '?') if isinstance(report.get('ruleset_scope'), Mapping) else '?')}",
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
    review = report.get("review")
    if isinstance(review, dict) and review.get("perspectives"):
        lines.append("review:")
        for name, view in (review.get("perspectives") or {}).items():
            if not isinstance(view, dict):
                continue
            counts = view.get("severity_counts", {})
            state_label = view.get("freshness", "missing")
            lines.append(
                f"  {str(name)}: {str(view.get('verdict') or 'not_run')} ({state_label})"
                f"  blocker: {counts.get('blocker', 0)}  high: {counts.get('high', 0)}"
                f"  medium: {counts.get('medium', 0)}"
            )
            if view.get("independence_level"):
                degraded = " (degraded)" if view.get("degraded_independence") else ""
                lines.append(f"    independence: {view.get('independence_level')}{degraded}")
            for error in view.get("errors", [])[:3]:
                lines.append(f"    error: {redact_text(str(error))}")
    if report.get("errors"):
        lines.append("errors:")
        lines.extend(f"  - {redact_text(str(error))}" for error in report["errors"])
    failures = report.get("failures_summary")
    if isinstance(failures, Mapping) and failures.get("count"):
        lines.append(f"failures summary: {failures['count']} actionable item(s)")
        for item in failures.get("items", [])[:8]:
            if isinstance(item, Mapping):
                lines.append(f"  - [{item.get('severity')}] {item.get('source')}: {item.get('message')}")
    lines.append(f"next action: {report.get('next_action')}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    ruleset = ruleset_fingerprint(SCRIPT_DIR.parent)
    try:
        manifest_path = resolve_manifest_path(root, args.manifest)
        manifest = load_structured(manifest_path)
    except (OSError, ValueError, TypeError) as exc:
        report = {
            "ok": False,
            "errors": [f"cannot read manifest: {exc}"],
            "manifest": args.manifest or "active state layout",
            "ruleset_id": ruleset["ruleset_id"],
            "ruleset_scope": ruleset["ruleset_scope"],
        }
        print(json.dumps(report, ensure_ascii=False) if args.json else _human(report))
        return 2
    if not isinstance(manifest, dict):
        report = {
            "ok": False,
            "errors": ["run_manifest must be an object"],
            "ruleset_id": ruleset["ruleset_id"],
            "ruleset_scope": ruleset["ruleset_scope"],
        }
        print(json.dumps(report, ensure_ascii=False) if args.json else _human(report))
        return 2
    report = status_report(manifest, root, manifest_path)
    print(json.dumps(report, ensure_ascii=False) if args.json else _human(report))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
