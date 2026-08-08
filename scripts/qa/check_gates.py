#!/usr/bin/env python3
"""Check gate ordering, required artifacts, reviewer strength, and revision bounds."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file  # noqa: E402


GATE_ORDER = ("m1", "p1", "p2", "w1", "w2")
ALLOWED_GATE_STATUS = {"pending", "pass", "fail", "blocked"}


def gate_status(manifest: dict[str, Any], name: str) -> str:
    gate = manifest.get("gates", {}).get(name, {})
    return gate.get("status", "missing") if isinstance(gate, dict) else "invalid"


def successful_commands(commands: list[Any], stage: str) -> list[dict[str, Any]]:
    return [row for row in commands if isinstance(row, dict) and row.get("stage") == stage and row.get("exit_code") == 0]


def artifacts_for_role(manifest: dict[str, Any], role: str) -> list[dict[str, Any]]:
    return [row for row in manifest.get("artifacts", []) if isinstance(row, dict) and row.get("role") == role]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    manifest_path = resolve_path(args.manifest, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = load_structured(manifest_path)
    except (OSError, ValueError, TypeError) as exc:
        report = {"ok": False, "manifest": rel_path(manifest_path, root), "errors": [str(exc)], "warnings": []}
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1
    if not isinstance(manifest, dict):
        errors.append("run_manifest must be an object")
        manifest = {}

    gates = manifest.get("gates", {})
    if not isinstance(gates, dict):
        errors.append("run_manifest.gates must be an object")
        gates = {}
    statuses: dict[str, str] = {}
    for name in GATE_ORDER:
        status = gate_status(manifest, name)
        statuses[name] = status
        if status not in ALLOWED_GATE_STATUS:
            errors.append(f"gate {name} has invalid status {status!r}")

    for index, name in enumerate(GATE_ORDER):
        if statuses[name] == "pass" and any(statuses[previous] != "pass" for previous in GATE_ORDER[:index]):
            errors.append(f"gate {name} cannot pass before all earlier gates pass")

    commands = manifest.get("commands", [])
    if not isinstance(commands, list):
        errors.append("run_manifest.commands must be an array")
        commands = []
    artifacts = manifest.get("artifacts", [])
    if not isinstance(artifacts, list):
        errors.append("run_manifest.artifacts must be an array")
        artifacts = []

    enforce_file_hashes = manifest.get("status") in {"frozen", "released"} or any(status == "pass" for status in statuses.values())

    def verify_file_ref(owner: str, ref: Any, *, path_key: str = "path", hash_key: str = "sha256") -> Path | None:
        if not isinstance(ref, dict):
            errors.append(f"{owner} must be an object with path and sha256")
            return None
        raw_path = ref.get(path_key)
        expected_hash = ref.get(hash_key)
        if not isinstance(raw_path, str) or not raw_path:
            errors.append(f"{owner}.{path_key} must be non-empty")
            return None
        if raw_path.startswith(("http://", "https://", "s3://", "artifact://")):
            warnings.append(f"{owner} uses an external path; local hash verification skipped")
            return None
        path = resolve_path(raw_path, root).resolve()
        if not path.is_file():
            message = f"{owner} path does not exist: {raw_path}"
            (errors if enforce_file_hashes else warnings).append(message)
            return None
        actual_hash = sha256_file(path)
        if expected_hash != actual_hash:
            errors.append(f"{owner} sha256 drift: expected {expected_hash}, actual {actual_hash}")
        return path

    model_contract_path = verify_file_ref("model_contract", manifest.get("model_contract"))
    for index, artifact in enumerate(artifacts):
        verify_file_ref(f"artifacts[{index}]", artifact)

    for name in GATE_ORDER:
        gate = gates.get(name, {}) if isinstance(gates, dict) else {}
        if statuses[name] == "pass" and not gate.get("evidence"):
            errors.append(f"gate {name} pass requires non-empty evidence")
        checked_at = gate.get("checked_at") if isinstance(gate, dict) else None
        if isinstance(checked_at, str):
            try:
                datetime.fromisoformat(checked_at.replace("Z", "+00:00"))
            except ValueError:
                errors.append(f"gate {name}.checked_at must be ISO-8601")

    def single_artifact(role: str) -> tuple[dict[str, Any] | None, Path | None]:
        rows = artifacts_for_role(manifest, role)
        if len(rows) != 1:
            errors.append(f"exactly one {role} artifact is required, found {len(rows)}")
            return None, None
        raw_path = rows[0].get("path")
        path = resolve_path(raw_path, root).resolve() if isinstance(raw_path, str) else None
        return rows[0], path if path and path.is_file() else None

    def verify_review(owner: str, row: dict[str, Any], *, deterministic: bool = False) -> None:
        path = verify_file_ref(owner, row, path_key="report", hash_key="report_sha256")
        if path is None:
            errors.append(f"{owner} requires a current report")
            return
        try:
            report = load_structured(path)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"cannot inspect {owner} report: {exc}")
            return
        if not isinstance(report, dict):
            errors.append(f"{owner} report must be an object")
            return
        if deterministic:
            if report.get("ok") is not True:
                errors.append(f"{owner} report does not have ok=true")
            checks = report.get("checks", [])
            labels = {check.get("label") for check in checks if isinstance(check, dict) and check.get("ok") is True}
            if not {"contracts", "consistency", "citations"}.issubset(labels):
                errors.append(f"{owner} report does not contain passing contracts/consistency/citations checks")
            inputs = report.get("inputs", [])
            if not isinstance(inputs, list) or not inputs:
                errors.append(f"{owner} report has no hashed inputs")
            else:
                input_roles = {ref.get("role") for ref in inputs if isinstance(ref, dict)}
                required_roles = {"model_contract", "frozen_results", "evidence_registry", "paper_plan", "abstract", "paper", "conclusion"}
                if not required_roles.issubset(input_roles):
                    errors.append(f"{owner} report is missing required hashed input roles")
                for index, ref in enumerate(inputs):
                    verify_file_ref(f"{owner}.inputs[{index}]", ref)
        else:
            if report.get("verdict") != "pass":
                errors.append(f"{owner} report does not have verdict=pass")
            blocking = [
                issue for issue in report.get("issues", [])
                if isinstance(issue, dict) and issue.get("severity") in {"blocker", "high"}
            ]
            if blocking:
                errors.append(f"{owner} report still contains blocker/high issue(s)")

    if statuses["m1"] == "pass":
        if model_contract_path is None:
            errors.append("M1 pass requires a valid model_contract file and hash")
        else:
            try:
                model_contract = load_structured(model_contract_path)
                if not isinstance(model_contract, dict) or model_contract.get("status") != "ready":
                    errors.append("M1 pass requires model_contract.status=ready")
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"cannot inspect model_contract for M1: {exc}")
    if statuses["p1"] == "pass":
        if statuses["m1"] != "pass":
            errors.append("P1 pass requires M1 pass")
        smoke_passes = successful_commands(commands, "smoke")
        if len(smoke_passes) != 1:
            errors.append(f"P1 pass requires exactly one successful smoke command, found {len(smoke_passes)}")
    if statuses["p2"] == "pass":
        if statuses["p1"] != "pass":
            errors.append("P2 pass requires P1 pass")
        if not successful_commands(commands, "full"):
            errors.append("P2 pass requires a successful full command")
        if not successful_commands(commands, "freeze"):
            errors.append("P2 pass requires a successful freeze command")
        _, frozen_path = single_artifact("frozen_results")
        if frozen_path:
            try:
                frozen = load_structured(frozen_path)
                if not isinstance(frozen, dict) or frozen.get("status") != "frozen":
                    errors.append("P2 pass requires frozen_results.status=frozen")
                elif frozen.get("run_id") != manifest.get("run_id"):
                    errors.append("frozen_results.run_id does not match run_manifest.run_id")
                if not frozen.get("code_snapshot") or not frozen.get("validation_snapshot"):
                    errors.append("P2 pass requires code_snapshot and validation_snapshot")
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"cannot inspect frozen_results for P2: {exc}")
    if statuses["w1"] == "pass":
        if statuses["p2"] != "pass":
            errors.append("W1 pass requires P2 pass")
        _, registry_path = single_artifact("evidence_registry")
        _, plan_path = single_artifact("paper_plan")
        if registry_path and plan_path:
            try:
                registry = load_structured(registry_path)
                plan = load_structured(plan_path)
                if not isinstance(registry, dict) or not isinstance(plan, dict):
                    raise ValueError("registry and plan must be objects")
                if plan.get("status") != "ready" or not plan.get("requirements") or not plan.get("claims"):
                    errors.append("W1 pass requires a ready, non-empty paper_plan")
                evidence_by_id = {
                    row.get("evidence_id"): row
                    for row in registry.get("evidence", [])
                    if isinstance(row, dict) and isinstance(row.get("evidence_id"), str)
                }
                for claim in plan.get("claims", []):
                    for evidence_id in claim.get("evidence_ids", []):
                        evidence = evidence_by_id.get(evidence_id)
                        if evidence is None:
                            errors.append(f"W1 claim {claim.get('claim_id')} references missing evidence {evidence_id}")
                        elif evidence.get("verification_status") != "verified":
                            errors.append(f"W1 claim {claim.get('claim_id')} references unverified evidence {evidence_id}")
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"cannot inspect W1 artifacts: {exc}")
    if statuses["w2"] == "pass":
        if statuses["w1"] != "pass":
            errors.append("W2 pass requires W1 pass")
        single_artifact("paper")
        reviewer = manifest.get("reviewer", {})
        deterministic = reviewer.get("deterministic_qa", {}) if isinstance(reviewer, dict) else {}
        critic = reviewer.get("semantic_critic", {}) if isinstance(reviewer, dict) else {}
        if not isinstance(deterministic, dict) or deterministic.get("status") != "pass":
            errors.append("W2 pass requires deterministic_qa status=pass")
        else:
            verify_review("reviewer.deterministic_qa", deterministic, deterministic=True)
        if not isinstance(critic, dict) or critic.get("status") != "pass":
            errors.append("W2 pass requires semantic_critic status=pass")
        else:
            verify_review("reviewer.semantic_critic", critic)
        profile = reviewer.get("profile", "sprint") if isinstance(reviewer, dict) else "sprint"
        blind = reviewer.get("blind_reviewers", []) if isinstance(reviewer, dict) else []
        if not isinstance(blind, list):
            errors.append("reviewer.blind_reviewers must be an array")
            blind = []
        blind_passes = [row for row in blind if isinstance(row, dict) and row.get("status") == "pass"]
        required_blind = {"sprint": 0, "final_submission": 1, "award_max": 3}.get(profile)
        if required_blind is None:
            errors.append(f"unknown reviewer profile: {profile!r}")
        elif len(blind_passes) < required_blind:
            errors.append(f"reviewer profile {profile} requires {required_blind} passing blind reviewer(s), found {len(blind_passes)}")
        reviewer_ids = [row.get("reviewer_id") for row in blind_passes]
        if len(reviewer_ids) != len(set(reviewer_ids)) or any(not reviewer_id for reviewer_id in reviewer_ids):
            errors.append("passing blind reviewers must have distinct non-empty reviewer_id values")
        for index, row in enumerate(blind_passes):
            verify_review(f"reviewer.blind_reviewers[{index}]", row)

    revision = manifest.get("revision", {})
    if not isinstance(revision, dict):
        errors.append("revision must be an object")
    else:
        loop = revision.get("loop")
        cap = revision.get("cap")
        if not isinstance(loop, int) or not isinstance(cap, int):
            errors.append("revision.loop and revision.cap must be integers")
        else:
            if cap < 0 or cap > 2:
                errors.append("revision.cap must be between 0 and 2 for P0")
            if loop < 0 or loop > cap:
                errors.append("revision.loop must be between 0 and revision.cap")

    if manifest.get("status") == "released" and statuses["w2"] != "pass":
        errors.append("status=released requires W2 pass")
    if manifest.get("status") == "released" and manifest.get("phase") != "release":
        errors.append("status=released requires phase=release")
    if manifest.get("status") == "released" and isinstance(revision, dict) and revision.get("open_issue_ids"):
        errors.append("status=released requires revision.open_issue_ids to be empty")

    ok = not errors and (not args.strict or not warnings)
    report = {
        "ok": ok,
        "manifest": rel_path(manifest_path, root),
        "gate_status": statuses,
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
