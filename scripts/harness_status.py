#!/usr/bin/env python3
"""Report current harness status and the next blocking action (human or machine).

Thin wrapper over check_gates and the run_manifest; tells the Agent (or the
team) what is blocked, which human checkpoints are pending, which artifacts
are stale-registered, and the next command to run. `--json` for Agent
consumption, human table otherwise.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402

GATE_ORDER = ("m1", "p1", "p2", "w1", "w2", "s1")


def status_report(manifest: dict, root: Path) -> dict:
    gates = manifest.get("gates", {})
    first_blocked = None
    for name in GATE_ORDER:
        gate = gates.get(name, {}) if isinstance(gates, dict) else {}
        status = gate.get("status", "missing")
        if first_blocked is None and status not in ("pass",):
            first_blocked = (name, status)
    # stop at the first non-pass gate even if later ones report pass (stale/flaky)

    checkpoints = manifest.get("human_checkpoints", [])
    pending_checkpoints = [
        {
            "checkpoint_id": row.get("checkpoint_id"),
            "stage": row.get("stage"),
            "scope": row.get("scope"),
            "decision": row.get("decision"),
            "manual_checks": row.get("manual_checks", []),
            "reviewed_by_role": row.get("reviewed_by_role"),
        }
        for row in checkpoints
        if isinstance(row, dict) and row.get("decision") in ("ask", None)
    ]

    artifacts = manifest.get("artifacts", [])
    registered = {
        row.get("role"): row.get("path")
        for row in artifacts
        if isinstance(row, dict) and isinstance(row.get("role"), str) and isinstance(row.get("path"), str)
    }
    missing_files = [
        f"{role}: {path}"
        for role, path in registered.items()
        if path and not path.startswith(("http://", "https://")) and not resolve_path(path, root).is_file()
    ]

    next_action: str
    if pending_checkpoints:
        next_action = f"human review pending on stage {pending_checkpoints[0]['stage'].upper()}"
    elif first_blocked is None:
        next_action = "all gates pass; run S1 submission QA or freeze the submission"
    else:
        name, status = first_blocked
        next_action = f"gate {name.upper()} is '{status}' — produce its evidence and rerun check_gates"
    if first_blocked and first_blocked[1] == "blocked":
        next_action += " (blocked: inspect issue_ids and gate evidence)"

    return {
        "project_id": manifest.get("project_id"),
        "run_id": manifest.get("run_id"),
        "status": manifest.get("status"),
        "phase": manifest.get("phase"),
        "integrity_mode": manifest.get("integrity_mode"),
        "math_correctness_profile": manifest.get("math_correctness_profile"),
        "editorial_semantics_profile": manifest.get("editorial_semantics_profile"),
        "gates": {name: (gates.get(name, {}).get("status", "missing") if isinstance(gates, dict) else "missing") for name in GATE_ORDER},
        "first_blocked_gate": first_blocked,
        "pending_human_checkpoints": pending_checkpoints,
        "registered_artifact_count": len(artifacts),
        "missing_registered_files": missing_files,
        "next_action": next_action,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--json", action="store_true", help="machine-readable single-line output")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    manifest_path = resolve_path(args.manifest, root).resolve()
    try:
        manifest = load_structured(manifest_path)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "errors": [f"cannot read manifest: {exc}"]}, ensure_ascii=False))
        return 2
    if not isinstance(manifest, dict):
        print(json.dumps({"ok": False, "errors": ["run_manifest must be an object"]}, ensure_ascii=False))
        return 2

    report = status_report(manifest, root)
    report["ok"] = True
    report["manifest"] = rel_path(manifest_path, root)
    if args.json:
        print(json.dumps(report, ensure_ascii=False))
        return 0

    print(f"project: {report['project_id']}  run: {report['run_id']}  status: {report['status']}  phase: {report['phase']}")
    print(f"integrity_mode: {report['integrity_mode']}  math: {report['math_correctness_profile']}  editorial: {report['editorial_semantics_profile']}")
    print("gates: " + "  ".join(f"{name.upper()}:{status}" for name, status in report["gates"].items()))
    if report["first_blocked_gate"]:
        print(f"first blocked gate: {report['first_blocked_gate'][0].upper()} ({report['first_blocked_gate'][1]})")
    if report["pending_human_checkpoints"]:
        print(f"pending human checkpoints: {len(report['pending_human_checkpoints'])}")
        for checkpoint in report["pending_human_checkpoints"]:
            print(f"  - {checkpoint['stage'].upper()} [{checkpoint['decision'] or 'unset'}] {checkpoint['scope']}")
            print(f"      manual_checks: {', '.join(checkpoint['manual_checks'])}")
    if report["missing_registered_files"]:
        print(f"missing registered files: {len(report['missing_registered_files'])}")
        for entry in report["missing_registered_files"]:
            print(f"  - {entry}")
    print(f"next action: {report['next_action']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
