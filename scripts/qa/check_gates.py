#!/usr/bin/env python3
"""Check gate ordering, required artifacts, reviewer strength, and revision bounds."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file  # noqa: E402
from validate_contracts import REQUIRED_VALIDATION_CATEGORIES, _validate_document  # noqa: E402
from validation.obligations import file_ref, verify_validation_report  # noqa: E402


GATE_ORDER = ("m1", "p1", "p2", "w1", "w2", "s1")
ALLOWED_GATE_STATUS = {"pending", "pass", "fail", "blocked"}


def gate_status(manifest: dict[str, Any], name: str) -> str:
    gate = manifest.get("gates", {}).get(name, {})
    return gate.get("status", "missing") if isinstance(gate, dict) else "invalid"


def successful_commands(commands: list[Any], stage: str) -> list[dict[str, Any]]:
    return [row for row in commands if isinstance(row, dict) and row.get("stage") == stage and row.get("exit_code") == 0]


def artifacts_for_role(manifest: dict[str, Any], role: str) -> list[dict[str, Any]]:
    return [row for row in manifest.get("artifacts", []) if isinstance(row, dict) and row.get("role") == role]


def checkpoint_is_confirmed(row: dict[str, Any]) -> bool:
    """Accept the new explicit action and the schema-1.1 legacy spelling."""

    return row.get("decision") in {"confirm", "pass"}


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
    _, manifest_schema_errors, _ = _validate_document(
        manifest_path, Path(__file__).resolve().parents[2] / "schemas" / "run_manifest.schema.json"
    )
    errors.extend(f"run_manifest schema: {message}" for message in manifest_schema_errors)

    safety_check = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "check_contest_safety.py"),
            "--project-root", str(root),
            "--manifest", str(manifest_path),
            "--strict",
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    if safety_check.returncode != 0:
        try:
            safety_report = json.loads(safety_check.stdout)
            errors.extend(f"contest safety: {message}" for message in safety_report.get("errors", []))
            warnings.extend(f"contest safety: {message}" for message in safety_report.get("warnings", []))
        except json.JSONDecodeError:
            errors.append("contest safety check failed without a JSON report")

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

    integrity_mode = manifest.get("integrity_mode", "dev")
    enforce_file_existence = manifest.get("status") == "frozen" or any(
        status == "pass" for status in statuses.values()
    )
    require_hashes = integrity_mode == "submission"

    def verify_file_ref(owner: str, ref: Any, *, path_key: str = "path", hash_key: str = "sha256") -> Path | None:
        if not isinstance(ref, dict):
            errors.append(f"{owner} must be an object with path")
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
            (errors if enforce_file_existence else warnings).append(message)
            return None
        if expected_hash is None:
            if require_hashes:
                errors.append(f"{owner}.{hash_key} is required in submission integrity mode")
            return path
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

    def require_structured_artifact(
        role: str,
        *,
        schema_name: str,
        status_field: str | None = None,
        accepted_statuses: set[Any] | None = None,
    ) -> dict[str, Any] | None:
        _, path = single_artifact(role)
        if path is None:
            return None
        value, schema_errors, _ = _validate_document(
            path, Path(__file__).resolve().parents[2] / "schemas" / schema_name
        )
        errors.extend(f"{role} schema: {message}" for message in schema_errors)
        if not isinstance(value, dict):
            errors.append(f"{role} must be an object")
            return None
        if status_field and accepted_statuses is not None and value.get(status_field) not in accepted_statuses:
            errors.append(
                f"{role}.{status_field} must be one of {sorted(accepted_statuses, key=str)}, "
                f"got {value.get(status_field)!r}"
            )
        return value

    def require_structured_artifacts(
        role: str,
        *,
        schema_name: str,
        status_field: str | None = None,
        accepted_statuses: set[Any] | None = None,
    ) -> list[tuple[dict[str, Any], Path]]:
        rows = artifacts_for_role(manifest, role)
        if not rows:
            errors.append(f"at least one {role} artifact is required")
            return []
        values: list[tuple[dict[str, Any], Path]] = []
        for index, row in enumerate(rows):
            raw_path = row.get("path")
            path = resolve_path(raw_path, root).resolve() if isinstance(raw_path, str) else None
            if path is None or not path.is_file():
                continue
            value, schema_errors, _ = _validate_document(
                path, Path(__file__).resolve().parents[2] / "schemas" / schema_name
            )
            errors.extend(f"{role}[{index}] schema: {message}" for message in schema_errors)
            if not isinstance(value, dict):
                errors.append(f"{role}[{index}] must be an object")
                continue
            if status_field and accepted_statuses is not None and value.get(status_field) not in accepted_statuses:
                errors.append(
                    f"{role}[{index}].{status_field} must be one of "
                    f"{sorted(accepted_statuses, key=str)}, got {value.get(status_field)!r}"
                )
            values.append((value, path))
        return values

    def run_json_checker(label: str, argv: list[str]) -> None:
        check = subprocess.run(
            [sys.executable, *argv],
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        if check.returncode == 0:
            return
        try:
            report = json.loads(check.stdout)
            report_errors = report.get("errors", []) if isinstance(report, dict) else []
            if report_errors:
                errors.extend(f"{label}: {message}" for message in report_errors)
            else:
                errors.append(f"{label} failed without reported errors")
        except json.JSONDecodeError:
            errors.append(f"{label} failed without a JSON report")

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
            if not {"contracts", "contest_safety", "consistency", "citations"}.issubset(labels):
                errors.append(
                    f"{owner} report does not contain passing contracts/contest_safety/consistency/citations checks"
                )
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

    checkpoints = manifest.get("human_checkpoints", [])
    if not isinstance(checkpoints, list):
        errors.append("human_checkpoints must be an array")
        checkpoints = []

    def require_human_checkpoint(stage: str) -> dict[str, Any] | None:
        rows = [
            row for row in checkpoints
            if isinstance(row, dict) and row.get("stage") == stage and checkpoint_is_confirmed(row)
        ]
        if not rows:
            errors.append(f"gate {stage.upper()} pass requires a passing human checkpoint")
            return None
        checkpoint = rows[-1]
        checkpoint_refs: set[tuple[Any, Any]] = set()
        for index, ref in enumerate(checkpoint.get("artifacts", [])):
            verify_file_ref(f"human_checkpoints[{stage}].artifacts[{index}]", ref)
            if isinstance(ref, dict):
                checkpoint_refs.add((ref.get("path"), ref.get("sha256")))
        required_refs: list[dict[str, Any]] = []
        if stage == "m1" and isinstance(manifest.get("model_contract"), dict):
            required_refs.append(manifest["model_contract"])
            if integrity_mode in {"research", "submission"}:
                required_refs.extend(artifacts_for_role(manifest, "evidence_registry"))
        if stage == "p2":
            required_refs.extend(artifacts_for_role(manifest, "frozen_results"))
        if stage == "w2":
            required_refs.extend(artifacts_for_role(manifest, "paper"))
        for ref in required_refs:
            key = (ref.get("path"), ref.get("sha256"))
            if key not in checkpoint_refs:
                errors.append(f"human checkpoint {stage.upper()} does not cover current artifact: {ref.get('path')}")
        return checkpoint

    if statuses["m1"] == "pass":
        m1_checkpoint = require_human_checkpoint("m1")
        if integrity_mode in {"research", "submission"}:
            required_manual_checks = {
                "problem_mechanism_fit",
                "candidate_comparison_fairness",
                "data_sufficiency",
                "mathematical_consistency",
                "literature_support_fit",
                "validation_can_falsify",
            }
            completed_manual_checks = set(
                m1_checkpoint.get("manual_checks", []) if isinstance(m1_checkpoint, dict) else []
            )
            missing_manual_checks = sorted(required_manual_checks - completed_manual_checks)
            if missing_manual_checks:
                errors.append(
                    "research/submission M1 checkpoint is missing reasonableness review checks: "
                    f"{missing_manual_checks}"
                )
            research_registry_rows = artifacts_for_role(manifest, "evidence_registry")
            if len(research_registry_rows) != 1:
                errors.append(
                    "research/submission M1 requires exactly one evidence_registry artifact for literature support"
                )
            elif model_contract_path is not None:
                research_registry_path = resolve_path(
                    str(research_registry_rows[0].get("path", "")), root
                ).resolve()
                if research_registry_path.is_file():
                    run_json_checker(
                        "M1 research-first modeling plan",
                        [
                            str(SCRIPT_DIR / "check_modeling_plan.py"),
                            "--project-root", str(root),
                            "--model-contract", str(model_contract_path),
                            "--evidence-registry", str(research_registry_path),
                        ],
                    )
        if manifest.get("enhanced_integrity_profile") is True:
            problem_snapshot = require_structured_artifact(
                "problem_snapshot",
                schema_name="problem_snapshot.schema.json",
                status_field="status",
                accepted_statuses={"confirmed"},
            )
            data_contracts = require_structured_artifacts(
                "data_contract",
                schema_name="data_contract.schema.json",
                status_field="status",
                accepted_statuses={"validated"},
            )
            implementation_map = require_structured_artifact(
                "implementation_map",
                schema_name="implementation_map.schema.json",
                status_field="status",
                accepted_statuses={"verified"},
            )
            artifact_dag = require_structured_artifact(
                "artifact_dag",
                schema_name="artifact_dag.schema.json",
            )
            if isinstance(problem_snapshot, dict) and problem_snapshot.get("project_id") != manifest.get("project_id"):
                errors.append("problem_snapshot.project_id does not match run_manifest.project_id")
            for index, (value, _) in enumerate(data_contracts):
                if value.get("run_id") != manifest.get("run_id"):
                    errors.append(f"data_contract[{index}].run_id does not match run_manifest.run_id")
            if isinstance(implementation_map, dict) and implementation_map.get("run_id") != manifest.get("run_id"):
                errors.append("implementation_map.run_id does not match run_manifest.run_id")
            if isinstance(artifact_dag, dict) and artifact_dag.get("run_id") != manifest.get("run_id"):
                errors.append("artifact_dag.run_id does not match run_manifest.run_id")
            if model_contract_path is not None:
                for index, (_, data_path) in enumerate(data_contracts):
                    run_json_checker(
                        f"M1 data_contract[{index}] check",
                        [
                            str(SCRIPT_DIR / "check_data_contract.py"),
                            "--project-root", str(root),
                            "--data-contract", str(data_path),
                            "--model-contract", str(model_contract_path),
                        ],
                    )
                implementation_rows = artifacts_for_role(manifest, "implementation_map")
                if implementation_rows:
                    implementation_path = resolve_path(str(implementation_rows[0].get("path", "")), root).resolve()
                    if implementation_path.is_file():
                        run_json_checker(
                            "M1 implementation_map check",
                            [
                                str(SCRIPT_DIR / "check_implementation_map.py"),
                                "--project-root", str(root),
                                "--implementation-map", str(implementation_path),
                                "--model-contract", str(model_contract_path),
                            ],
                        )
            dag_rows = artifacts_for_role(manifest, "artifact_dag")
            if dag_rows:
                dag_path = resolve_path(str(dag_rows[0].get("path", "")), root).resolve()
                if dag_path.is_file():
                    run_json_checker(
                        "M1 artifact_dag check",
                        [
                            str(SCRIPT_DIR / "check_artifact_dag.py"),
                            "--project-root", str(root),
                            "--dag", str(dag_path),
                        ],
                    )
        if model_contract_path is None:
            errors.append("M1 pass requires a valid model_contract file")
        else:
            try:
                model_contract = load_structured(model_contract_path)
                if not isinstance(model_contract, dict) or model_contract.get("status") != "ready":
                    errors.append("M1 pass requires model_contract.status=ready")
                _, schema_errors, _ = _validate_document(
                    model_contract_path,
                    Path(__file__).resolve().parents[2] / "schemas" / "model_contract.schema.json",
                )
                errors.extend(f"M1 model contract schema: {message}" for message in schema_errors)
                if isinstance(model_contract, dict):
                    for model in model_contract.get("models", []):
                        if not isinstance(model, dict):
                            continue
                        categories = {
                            row.get("category")
                            for row in model.get("validation_obligations", [])
                            if isinstance(row, dict)
                        }
                        missing = sorted(
                            REQUIRED_VALIDATION_CATEGORIES.get(model.get("problem_type"), set()) - categories
                        )
                        if missing:
                            errors.append(
                                f"M1 model {model.get('model_id')} is missing triggered validation categories: {missing}"
                            )
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"cannot inspect model_contract for M1: {exc}")
    if statuses["p1"] == "pass":
        if statuses["m1"] != "pass":
            errors.append("P1 pass requires M1 pass")
        smoke_passes = successful_commands(commands, "smoke")
        if len(smoke_passes) != 1:
            errors.append(f"P1 pass requires exactly one successful smoke command, found {len(smoke_passes)}")
    if statuses["p2"] == "pass":
        require_human_checkpoint("p2")
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
                _, schema_errors, _ = _validate_document(
                    frozen_path,
                    Path(__file__).resolve().parents[2] / "schemas" / "frozen_results.schema.json",
                )
                errors.extend(f"P2 frozen results schema: {message}" for message in schema_errors)
                if not isinstance(frozen, dict) or frozen.get("status") != "frozen":
                    errors.append("P2 pass requires frozen_results.status=frozen")
                elif frozen.get("run_id") != manifest.get("run_id"):
                    errors.append("frozen_results.run_id does not match run_manifest.run_id")
                elif frozen.get("claimable") is not True or frozen.get("validation_verdict") != "PASS":
                    errors.append("P2 pass requires frozen_results.claimable=true and validation_verdict=PASS")
                if not frozen.get("code_snapshot") or not frozen.get("validation_snapshot"):
                    errors.append("P2 pass requires code_snapshot and validation_snapshot")
                if not frozen.get("validation_obligations"):
                    errors.append("P2 pass requires passed validation obligations")
                if model_contract_path is None:
                    errors.append("P2 pass requires a current model contract")
                else:
                    model_contract = load_structured(model_contract_path)
                    if not isinstance(model_contract, dict):
                        raise ValueError("model contract must be an object")
                    for index, report_ref in enumerate(frozen.get("validation_snapshot", [])):
                        report_path = verify_file_ref(f"P2 validation_snapshot[{index}]", report_ref)
                        if report_path is None:
                            continue
                        report = load_structured(report_path)
                        if not isinstance(report, dict):
                            raise ValueError(f"validation report {report_ref.get('path')} must be an object")
                        measurement_ref = report.get("measurement_snapshot")
                        measurement_path = verify_file_ref(
                            f"P2 validation report {report_ref.get('path')}.measurement_snapshot", measurement_ref
                        )
                        if measurement_path is None:
                            continue
                        measurements = load_structured(measurement_path)
                        if not isinstance(measurements, dict):
                            raise ValueError("P2 measurement snapshot must be an object")
                        verify_validation_report(
                            report,
                            model_contract,
                            measurements,
                            file_ref(model_contract_path, root),
                            file_ref(measurement_path, root),
                        )
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"cannot inspect frozen_results for P2: {exc}")
    if statuses["w1"] == "pass":
        if statuses["p2"] != "pass":
            errors.append("W1 pass requires P2 pass")
        _, frozen_path = single_artifact("frozen_results")
        if frozen_path:
            try:
                frozen = load_structured(frozen_path)
                if not isinstance(frozen, dict) or frozen.get("claimable") is not True:
                    errors.append("W1 pass requires a claimable frozen_results artifact")
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"cannot inspect frozen_results for W1: {exc}")
        _, registry_path = single_artifact("evidence_registry")
        _, plan_path = single_artifact("paper_plan")
        if integrity_mode in {"research", "submission"} and registry_path and plan_path:
            run_json_checker(
                "W1 technical-first-draft readiness",
                [
                    str(SCRIPT_DIR / "check_paper_readiness.py"),
                    "--project-root", str(root),
                    "--paper-plan", str(plan_path),
                    "--evidence-registry", str(registry_path),
                    "--minimum-stage", "technical_draft",
                ],
            )
        if manifest.get("enhanced_integrity_profile") is True:
            presentation_contract = require_structured_artifact(
                "presentation_contract",
                schema_name="presentation_contract.schema.json",
                status_field="status",
                accepted_statuses={"ready"},
            )
            if isinstance(presentation_contract, dict) and presentation_contract.get("run_id") != manifest.get("run_id"):
                errors.append("presentation_contract.run_id does not match run_manifest.run_id")
        if registry_path and plan_path:
            try:
                registry = load_structured(registry_path)
                plan = load_structured(plan_path)
                for label, artifact_path, schema_name in (
                    ("evidence registry", registry_path, "evidence_registry.schema.json"),
                    ("paper plan", plan_path, "paper_plan.schema.json"),
                ):
                    _, schema_errors, _ = _validate_document(
                        artifact_path, Path(__file__).resolve().parents[2] / "schemas" / schema_name
                    )
                    errors.extend(f"W1 {label} schema: {message}" for message in schema_errors)
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
                if manifest.get("enhanced_integrity_profile") is True and model_contract_path is not None:
                    problem_rows = artifacts_for_role(manifest, "problem_snapshot")
                    if problem_rows:
                        problem_path = resolve_path(str(problem_rows[0].get("path", "")), root).resolve()
                        if problem_path.is_file():
                            run_json_checker(
                                "W1 problem coverage check",
                                [
                                    str(SCRIPT_DIR / "check_problem_coverage.py"),
                                    "--project-root", str(root),
                                    "--problem-snapshot", str(problem_path),
                                    "--model-contract", str(model_contract_path),
                                    "--paper-plan", str(plan_path),
                                ],
                            )
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"cannot inspect W1 artifacts: {exc}")
    if statuses["w2"] == "pass":
        require_human_checkpoint("w2")
        if statuses["w1"] != "pass":
            errors.append("W2 pass requires W1 pass")
        single_artifact("paper")
        build_receipt: dict[str, Any] | None = None
        if integrity_mode in {"research", "submission"}:
            template_contract = require_structured_artifact(
                "template_contract",
                schema_name="template_contract.schema.json",
                status_field="status",
                accepted_statuses={"verified"},
            )
            build_receipt = require_structured_artifact(
                "build_receipt",
                schema_name="build_receipt.schema.json",
                status_field="ok",
                accepted_statuses={True},
            )
            profile_id = manifest.get("competition_profile", {}).get("profile_id")
            if (
                isinstance(template_contract, dict)
                and template_contract.get("competition_profile_id") != profile_id
            ):
                errors.append("template_contract.competition_profile_id does not match run_manifest profile_id")
            if isinstance(build_receipt, dict):
                if build_receipt.get("integrity_mode") != integrity_mode:
                    errors.append("build_receipt.integrity_mode does not match run_manifest.integrity_mode")
                if build_receipt.get("source_unchanged") is not True:
                    errors.append("W2 requires build_receipt.source_unchanged=true")
                paper_rows = artifacts_for_role(manifest, "paper")
                current_paper = paper_rows[0] if len(paper_rows) == 1 else None
                built_output = build_receipt.get("output")
                if isinstance(current_paper, dict) and (
                    not isinstance(built_output, dict)
                    or built_output.get("path") != current_paper.get("path")
                    or (
                        integrity_mode == "submission"
                        and built_output.get("sha256") != current_paper.get("sha256")
                    )
                ):
                    errors.append("build_receipt does not bind the current paper artifact")
                template_ref = build_receipt.get("template")
                template_rows = artifacts_for_role(manifest, "template_contract")
                if (
                    not isinstance(template_ref, dict)
                    or template_ref.get("verified") is not True
                    or not template_rows
                    or template_ref.get("contract") != template_rows[0].get("path")
                ):
                    errors.append("build_receipt does not bind a verified current template_contract")
                if isinstance(template_contract, dict) and isinstance(template_ref, dict):
                    if template_ref.get("template_id") != template_contract.get("template_id"):
                        errors.append("build_receipt template_id does not match template_contract")
                    if template_ref.get("document_class") != template_contract.get("document_class"):
                        errors.append("build_receipt document_class does not match template_contract")
                if template_rows:
                    template_path = resolve_path(str(template_rows[0].get("path", "")), root).resolve()
                    run_json_checker(
                        "W2 actual template usage",
                        [
                            str(SCRIPT_DIR / "check_template_usage.py"),
                            "--project-root", str(root),
                            "--template-contract", str(template_path),
                            "--source-root", str(build_receipt.get("source_root", "")),
                            "--entrypoint", str(build_receipt.get("entrypoint", "")),
                            "--engine", str(build_receipt.get("engine", "xelatex")),
                            "--integrity-mode", integrity_mode,
                        ],
                    )
        reviewer = manifest.get("reviewer", {})
        deterministic = reviewer.get("deterministic_qa", {}) if isinstance(reviewer, dict) else {}
        critic = reviewer.get("semantic_critic", {}) if isinstance(reviewer, dict) else {}
        if not isinstance(deterministic, dict) or deterministic.get("status") != "pass":
            errors.append("W2 pass requires deterministic_qa status=pass")
        else:
            verify_review("reviewer.deterministic_qa", deterministic, deterministic=True)
        if manifest.get("enhanced_integrity_profile") is True:
            claim_inventory = require_structured_artifact(
                "claim_inventory",
                schema_name="claim_inventory.schema.json",
                status_field="ok",
                accepted_statuses={True},
            )
            if build_receipt is None:
                build_receipt = require_structured_artifact(
                    "build_receipt",
                    schema_name="build_receipt.schema.json",
                    status_field="ok",
                    accepted_statuses={True},
                )
            pdf_visual = require_structured_artifact(
                "pdf_visual_qa",
                schema_name="pdf_visual_qa.schema.json",
                status_field="formal_ok",
                accepted_statuses={True},
            )
            visual_review = require_structured_artifact(
                "visual_review_receipt",
                schema_name="visual_review_receipt.schema.json",
                status_field="verdict",
                accepted_statuses={"pass"},
            )
            if isinstance(claim_inventory, dict) and claim_inventory.get("run_id") != manifest.get("run_id"):
                errors.append("claim_inventory.run_id does not match run_manifest.run_id")
            if isinstance(build_receipt, dict) and build_receipt.get("source_unchanged") is not True:
                errors.append("W2 requires build_receipt.source_unchanged=true")
            paper_rows = artifacts_for_role(manifest, "paper")
            current_paper = paper_rows[0] if len(paper_rows) == 1 else None
            if isinstance(build_receipt, dict) and isinstance(current_paper, dict):
                built_output = build_receipt.get("output")
                if (
                    not isinstance(built_output, dict)
                    or built_output.get("path") != current_paper.get("path")
                    or (
                        integrity_mode == "submission"
                        and built_output.get("sha256") != current_paper.get("sha256")
                    )
                ):
                    errors.append("build_receipt does not bind the current paper artifact")
            if isinstance(pdf_visual, dict) and isinstance(current_paper, dict):
                pdf_ref = pdf_visual.get("pdf")
                if (
                    not isinstance(pdf_ref, dict)
                    or pdf_ref.get("path") != current_paper.get("path")
                    or pdf_ref.get("sha256") != current_paper.get("sha256")
                ):
                    errors.append("pdf_visual_qa does not bind the current paper artifact")
            if isinstance(pdf_visual, dict) and isinstance(visual_review, dict):
                visual_ref = visual_review.get("pdf_visual_qa", {})
                visual_rows = artifacts_for_role(manifest, "pdf_visual_qa")
                if visual_rows and (
                    not isinstance(visual_ref, dict)
                    or visual_ref.get("path") != visual_rows[0].get("path")
                    or visual_ref.get("sha256") != visual_rows[0].get("sha256")
                ):
                    errors.append("visual_review_receipt does not bind the current pdf_visual_qa artifact")
                visual_pdf = visual_review.get("pdf")
                if isinstance(current_paper, dict) and (
                    not isinstance(visual_pdf, dict)
                    or visual_pdf.get("path") != current_paper.get("path")
                    or visual_pdf.get("sha256") != current_paper.get("sha256")
                ):
                    errors.append("visual_review_receipt does not bind the current paper artifact")
                unresolved_visual = [
                    issue for issue in visual_review.get("issues", [])
                    if isinstance(issue, dict)
                    and issue.get("severity") in {"blocker", "high"}
                    and issue.get("status") == "open"
                ]
                if unresolved_visual:
                    errors.append("visual_review_receipt contains open blocker/high issues")
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

    if statuses["s1"] == "pass":
        if integrity_mode != "submission":
            errors.append("S1 pass requires integrity_mode=submission")
        if statuses["w2"] != "pass":
            errors.append("S1 pass requires W2 pass")
        require_human_checkpoint("s1")
        _, submission_report_path = single_artifact("submission_qa")
        if submission_report_path:
            try:
                submission_report = load_structured(submission_report_path)
                if not isinstance(submission_report, dict) or submission_report.get("ok") is not True:
                    errors.append("S1 pass requires submission QA report with ok=true")
            except (OSError, ValueError, TypeError) as exc:
                errors.append(f"cannot inspect submission QA report: {exc}")

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

    if manifest.get("status") == "content_ready" and statuses["w2"] != "pass":
        errors.append("status=content_ready requires W2 pass")
    if manifest.get("status") == "submission_ready" and statuses["s1"] != "pass":
        errors.append("status=submission_ready requires S1 pass")
    if manifest.get("status") == "submission_ready" and manifest.get("phase") != "submission":
        errors.append("status=submission_ready requires phase=submission")
    if manifest.get("status") in {"content_ready", "submission_ready"} and isinstance(revision, dict) and revision.get("open_issue_ids"):
        errors.append(f"status={manifest.get('status')} requires revision.open_issue_ids to be empty")

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
