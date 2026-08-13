#!/usr/bin/env python3
"""Check that a paper plan is deep enough to produce a technical first draft."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


STAGE_RANK = {"outline": 0, "technical_draft": 1, "content_ready": 2}
ROLE_GROUPS = {
    "formulation_unit_ids": {"model_choice", "mechanism_derivation", "parameter_evidence"},
    "result_unit_ids": {"result_observation", "comparison"},
    "validation_unit_ids": {"validation"},
    "interpretation_unit_ids": {"interpretation", "boundary", "recommendation"},
}


def evaluate_readiness(
    plan: dict[str, Any],
    registry: dict[str, Any],
    minimum_stage: str = "technical_draft",
) -> tuple[list[str], list[str], dict[str, Any]]:
    errors: list[str] = []
    warnings: list[str] = []
    readiness = plan.get("readiness")
    if not isinstance(readiness, dict):
        return ["paper_plan.readiness is required for a formal first draft"], [], {}
    stage = readiness.get("stage")
    if STAGE_RANK.get(stage, -1) < STAGE_RANK[minimum_stage]:
        errors.append(f"paper readiness stage {stage!r} is below required {minimum_stage!r}")

    claims = {
        row.get("claim_id"): row
        for row in plan.get("claims", [])
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str)
    }
    question_ids = {
        row.get("question_id") for row in claims.values() if isinstance(row.get("question_id"), str)
    }
    units = {
        row.get("unit_id"): row
        for row in plan.get("argument_units", [])
        if isinstance(row, dict) and isinstance(row.get("unit_id"), str)
    }
    evidence = {
        row.get("evidence_id"): row
        for row in registry.get("evidence", [])
        if isinstance(row, dict) and isinstance(row.get("evidence_id"), str)
    }
    displays: dict[str, dict[str, Any]] = {}
    for row in plan.get("figures", []):
        if isinstance(row, dict) and isinstance(row.get("figure_id"), str):
            displays[row["figure_id"]] = row
    for row in plan.get("tables", []):
        if isinstance(row, dict) and isinstance(row.get("table_id"), str):
            displays[row["table_id"]] = row

    coverage_rows = [row for row in readiness.get("question_coverage", []) if isinstance(row, dict)]
    coverage_by_question = {row.get("question_id"): row for row in coverage_rows}
    if set(coverage_by_question) != question_ids:
        errors.append(
            "readiness.question_coverage must cover exactly all claimed questions; "
            f"missing={sorted(question_ids - set(coverage_by_question))}, "
            f"extra={sorted(set(coverage_by_question) - question_ids)}"
        )

    unit_words_by_question: dict[str, int] = {qid: 0 for qid in question_ids}
    used_units: set[str] = set()
    for qid, coverage in coverage_by_question.items():
        if qid not in question_ids:
            continue
        question_units: set[str] = set()
        for field, allowed_roles in ROLE_GROUPS.items():
            for unit_id in coverage.get(field, []):
                unit = units.get(unit_id)
                if unit is None:
                    errors.append(f"question {qid} {field} references missing unit {unit_id}")
                    continue
                used_units.add(unit_id)
                question_units.add(unit_id)
                if unit.get("rhetorical_role") not in allowed_roles:
                    errors.append(
                        f"question {qid} unit {unit_id} role {unit.get('rhetorical_role')!r} is invalid for {field}"
                    )
                unit_questions = {
                    claims[claim_id].get("question_id")
                    for claim_id in unit.get("claim_ids", [])
                    if claim_id in claims
                }
                if qid not in unit_questions:
                    errors.append(f"unit {unit_id} does not support question {qid}")
                for evidence_id in unit.get("evidence_ids", []):
                    evidence_row = evidence.get(evidence_id)
                    if evidence_row is None:
                        errors.append(f"unit {unit_id} references missing evidence {evidence_id}")
                    elif evidence_row.get("verification_status") != "verified":
                        errors.append(f"unit {unit_id} references unverified evidence {evidence_id}")

        display_ids = coverage.get("display_ids", [])
        for display_id in display_ids:
            display = displays.get(display_id)
            if display is None:
                errors.append(f"question {qid} references missing display {display_id}")
                continue
            display_questions = {
                claims[claim_id].get("question_id")
                for claim_id in display.get("claim_ids", [])
                if claim_id in claims
            }
            if qid not in display_questions:
                errors.append(f"display {display_id} does not support question {qid}")
        unit_words_by_question[qid] = sum(
            int(units[unit_id].get("target_words", 0))
            for unit_id in question_units
            if unit_id in units
        )

    depth_by_question = {
        row.get("question_id"): row
        for row in plan.get("depth_budget", [])
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }
    for qid in sorted(question_ids):
        depth = depth_by_question.get(qid)
        if depth is None:
            errors.append(f"question {qid} has no depth budget")
            continue
        if unit_words_by_question.get(qid, 0) < int(depth.get("target_words", 0)):
            errors.append(
                f"question {qid} argument units plan {unit_words_by_question.get(qid, 0)} words, "
                f"below its depth budget {depth.get('target_words')}"
            )

    unused = sorted(set(units) - used_units)
    if unused:
        warnings.append(f"argument units not assigned to question readiness coverage: {unused}")

    details = {
        "stage": stage,
        "questions": sorted(question_ids),
        "planned_words_by_question": unit_words_by_question,
        "used_units": sorted(used_units),
    }
    return errors, warnings, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--evidence-registry", required=True)
    parser.add_argument("--minimum-stage", choices=tuple(STAGE_RANK), default="technical_draft")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    plan_path = resolve_path(args.paper_plan, root).resolve()
    registry_path = resolve_path(args.evidence_registry, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        plan, plan_schema_errors, _ = _validate_document(
            plan_path, Path(__file__).resolve().parents[2] / "schemas" / "paper_plan.schema.json"
        )
        registry, registry_schema_errors, _ = _validate_document(
            registry_path, Path(__file__).resolve().parents[2] / "schemas" / "evidence_registry.schema.json"
        )
        errors.extend(f"paper_plan schema: {message}" for message in plan_schema_errors)
        errors.extend(f"evidence_registry schema: {message}" for message in registry_schema_errors)
        if not isinstance(plan, dict) or not isinstance(registry, dict):
            raise ValueError("paper plan and evidence registry must be objects")
        if plan.get("run_id") != registry.get("run_id"):
            errors.append("paper_plan and evidence_registry must share one run_id")
        readiness_errors, readiness_warnings, details = evaluate_readiness(
            plan, registry, args.minimum_stage
        )
        errors.extend(readiness_errors)
        warnings.extend(readiness_warnings)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "paper_plan": rel_path(plan_path, root),
        "evidence_registry": rel_path(registry_path, root),
        "details": details,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
