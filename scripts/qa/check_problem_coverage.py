#!/usr/bin/env python3
"""Verify official problem requirements are mapped through model and paper artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem-snapshot", required=True)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    snapshot_path = resolve_path(args.problem_snapshot, root).resolve()
    model_path = resolve_path(args.model_contract, root).resolve()
    plan_path = resolve_path(args.paper_plan, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    snapshot, schema_errors, _ = _validate_document(
        snapshot_path, Path(__file__).resolve().parents[2] / "schemas" / "problem_snapshot.schema.json"
    )
    errors.extend(f"problem_snapshot schema: {message}" for message in schema_errors)
    try:
        model = load_structured(model_path)
        plan = load_structured(plan_path)
    except (OSError, ValueError, TypeError) as exc:
        errors.append(str(exc))
        model, plan = {}, {}
    if not isinstance(snapshot, dict):
        snapshot = {}
    if not isinstance(model, dict):
        errors.append("model_contract must be an object")
        model = {}
    if not isinstance(plan, dict):
        errors.append("paper_plan must be an object")
        plan = {}

    def unique(label: str, values: list[Any]) -> set[Any]:
        if len(values) != len(set(values)):
            errors.append(f"{label} values must be unique")
        return set(values)

    for owner in ("problem_files", "attachment_files"):
        for index, ref in enumerate(snapshot.get(owner, [])):
            if not isinstance(ref, dict):
                continue
            path = resolve_path(str(ref.get("path", "")), root).resolve()
            if not path.is_file():
                errors.append(f"{owner}[{index}] does not exist: {ref.get('path')}")
            elif ref.get("sha256") != sha256_file(path):
                errors.append(f"{owner}[{index}] hash drift: {ref.get('path')}")

    selection = snapshot.get("selection", {})
    candidates = selection.get("candidates", []) if isinstance(selection, dict) else []
    selected_problem_id = selection.get("selected_problem_id") if isinstance(selection, dict) else None
    selected = [row for row in candidates if isinstance(row, dict) and row.get("decision") == "selected"]
    if len(selected) != 1 or selected[0].get("problem_id") != selected_problem_id:
        errors.append("selection must contain exactly one selected candidate matching selected_problem_id")
    if snapshot.get("status") != "confirmed":
        errors.append("problem_snapshot.status must be confirmed")

    snapshot_requirements = [row for row in snapshot.get("requirements", []) if isinstance(row, dict)]
    snapshot_requirement_ids = unique(
        "problem_snapshot requirement_id", [row.get("requirement_id") for row in snapshot_requirements]
    )
    snapshot_question_ids = {row.get("question_id") for row in snapshot_requirements}
    model_questions = [row for row in model.get("questions", []) if isinstance(row, dict)]
    model_question_ids = unique("model_contract question_id", [row.get("question_id") for row in model_questions])
    plan_requirements = [row for row in plan.get("requirements", []) if isinstance(row, dict)]
    plan_requirement_ids = unique("paper_plan requirement_id", [row.get("requirement_id") for row in plan_requirements])
    plan_requirement_by_id = {row.get("requirement_id"): row for row in plan_requirements}
    claim_ids = {
        row.get("claim_id") for row in plan.get("claims", [])
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str)
    }

    if snapshot_question_ids != model_question_ids:
        errors.append(
            "problem_snapshot question coverage differs from model_contract: "
            f"snapshot={sorted(snapshot_question_ids)}, model={sorted(model_question_ids)}"
        )
    if snapshot_requirement_ids != plan_requirement_ids:
        errors.append(
            "paper_plan requirements do not exactly cover problem_snapshot requirements: "
            f"missing={sorted(snapshot_requirement_ids - plan_requirement_ids)}, "
            f"extra={sorted(plan_requirement_ids - snapshot_requirement_ids)}"
        )
    question_by_id = {row.get("question_id"): row for row in model_questions}
    for requirement in snapshot_requirements:
        question = question_by_id.get(requirement.get("question_id"))
        if question is None:
            continue
        missing_outputs = set(requirement.get("required_outputs", [])) - set(question.get("outputs", []))
        if missing_outputs:
            errors.append(
                f"requirement {requirement.get('requirement_id')} output(s) are absent from model_contract: "
                f"{sorted(missing_outputs)}"
            )
        if plan.get("status") == "ready" and requirement.get("status") != "answered":
            errors.append(
                f"ready paper_plan requires requirement {requirement.get('requirement_id')} status=answered"
            )
        planned = plan_requirement_by_id.get(requirement.get("requirement_id"))
        if planned is not None:
            mapped_claims = set(planned.get("claim_ids", []))
            if not mapped_claims:
                errors.append(f"requirement {requirement.get('requirement_id')} has no paper claim")
            unknown_claims = mapped_claims - claim_ids
            if unknown_claims:
                errors.append(
                    f"requirement {requirement.get('requirement_id')} references unknown claim(s): {sorted(unknown_claims)}"
                )
    if plan.get("status") != "ready":
        warnings.append("paper_plan is not ready; final answer coverage has not been promoted")

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "files": {
            "problem_snapshot": rel_path(snapshot_path, root),
            "model_contract": rel_path(model_path, root),
            "paper_plan": rel_path(plan_path, root),
        },
        "requirements": len(snapshot_requirements),
        "questions": len(model_question_ids),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
