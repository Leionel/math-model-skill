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


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


STAGE_RANK = {"outline": 0, "technical_draft": 1, "content_ready": 2}
ROLE_GROUPS = {
    "formulation_unit_ids": {"model_choice", "mechanism_derivation", "parameter_evidence"},
    "result_unit_ids": {"result_observation", "comparison"},
    "validation_unit_ids": {"validation"},
    "interpretation_unit_ids": {"interpretation", "boundary", "recommendation"},
}


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.casefold()
    return any(needle.casefold() in lowered for needle in needles)


def _completeness_item(status: str, evidence: list[str], action: str) -> dict[str, Any]:
    return {"status": status, "evidence": evidence, "action": action}


def presentation_completeness(plan: dict[str, Any]) -> dict[str, Any]:
    """Give a soft, explainable presentation checklist without adding a gate.

    This is intentionally plan-level: it can recommend a missing rhetorical move,
    but it cannot prove that the rendered prose actually contains that move.  The
    strict readiness checks remain the source of truth for technical coverage.
    """

    sections = [row for row in plan.get("sections", []) if isinstance(row, dict)]
    units = [row for row in plan.get("argument_units", []) if isinstance(row, dict)]
    coverage = [row for row in (plan.get("readiness") or {}).get("question_coverage", []) if isinstance(row, dict)]
    question_ids = sorted({row.get("question_id") for row in coverage if isinstance(row.get("question_id"), str)})
    purposes = " ".join(str(row.get("purpose", "")) for row in sections)
    roles = {row.get("rhetorical_role") for row in units}

    def all_nonempty(field: str) -> bool:
        return bool(question_ids) and all(bool(row.get(field)) for row in coverage)

    validation_units = [row for row in units if row.get("rhetorical_role") == "validation"]
    validation_locators = [
        str(locator)
        for row in validation_units
        for locator in row.get("math_locators", [])
        if locator
    ]
    model_sections = [
        str(row.get("purpose", ""))
        for row in sections
        if _contains_any(str(row.get("purpose", "")), ("评价", "评估", "检验", "模型性能", "evaluation", "validation"))
    ]

    checks = {
        "problem_analysis": _completeness_item(
            "RECOMMENDED" if "problem_tension" in roles or _contains_any(purposes, ("问题", "题意", "背景", "problem", "question")) else "MISSING",
            ["argument role problem_tension" if "problem_tension" in roles else "section purpose keyword scan"],
            "在正式模型前补一段题意、决策对象、约束和待回答输出的分析。",
        ),
        "assumptions_before_model": _completeness_item(
            "RECOMMENDED" if "parameter_evidence" in roles or _contains_any(purposes, ("假设", "assumption", "参数来源")) else "MISSING",
            ["parameter_evidence argument unit" if "parameter_evidence" in roles else "section purpose keyword scan"],
            "在模型公式前显式列出关键假设、参数来源、单位和失效边界。",
        ),
        "symbols": _completeness_item(
            "RECOMMENDED" if any(row.get("equation_ids") for row in units) or any(row.get("symbol") for row in plan.get("terminology", []) if isinstance(row, dict)) else "MISSING",
            ["equation_ids or symbol-bearing terminology"],
            "建立符号表，并让符号、含义、单位和定义域在模型前可定位。",
        ),
        "question_formulation": _completeness_item(
            "RECOMMENDED" if all_nonempty("formulation_unit_ids") else "MISSING",
            [f"questions={question_ids}"],
            "为每个子问题先写清数学化目标、变量、约束和输出。",
        ),
        "question_solution": _completeness_item(
            "RECOMMENDED" if all_nonempty("result_unit_ids") else "MISSING",
            [f"questions={question_ids}"],
            "为每个子问题登记求解方法及其与模型输出的对应关系。",
        ),
        "question_result": _completeness_item(
            "RECOMMENDED" if all_nonempty("result_unit_ids") else "MISSING",
            [f"questions={question_ids}"],
            "为每个子问题给出可追溯的冻结结果、单位、比较口径和解释。",
        ),
        "question_interpretation": _completeness_item(
            "RECOMMENDED" if all_nonempty("interpretation_unit_ids") else "MISSING",
            [f"questions={question_ids}"],
            "结果之后补充机理解释、适用边界和对题目决策的含义。",
        ),
        "validation_locator": _completeness_item(
            "RECOMMENDED" if validation_units and len(validation_locators) >= len(validation_units) else "MISSING",
            [f"validation_units={len(validation_units)}", f"math_locators={len(validation_locators)}"],
            "把验证方法、验收标准和结果定位器紧跟在对应模型结果之后。",
        ),
        "model_evaluation": _completeness_item(
            "RECOMMENDED" if model_sections else "NOT_APPLICABLE",
            model_sections or ["没有显式模型评价章节；这不是默认硬性要求"],
            "若模型比较或验证需要集中讨论，可增加模型评价小节；否则在各问中就地呈现。",
        ),
    }
    return {
        "status_vocabulary": ["RECOMMENDED", "MISSING", "NOT_APPLICABLE"],
        "checks": checks,
        "note": "这是软性呈现完整性审阅，不替代正文渲染后的人工阅读，也不因缺少模型评价章节而失败。",
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

    units_by_question: dict[str, list[str]] = {}
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
                unit_scope = unit.get("scope")
                # A declared global/cross-question scope expands the normal claim scope below.
                if isinstance(unit_scope, dict):
                    if unit_scope.get("type") == "global":
                        unit_questions = set(question_ids)
                    elif unit_scope.get("type") in {"question", "cross_question"}:
                        scoped_question_ids = unit_scope.get("question_ids")
                        if isinstance(scoped_question_ids, list):
                            unit_questions.update(item for item in scoped_question_ids if isinstance(item, str))
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
        units_by_question[qid] = sorted(question_units)

    shared_scope_units = {
        unit_id
        for unit_id, unit in units.items()
        if isinstance(unit.get("scope"), dict)
        and unit["scope"].get("type") in {"cross_question", "global"}
    }

    unused = sorted(set(units) - used_units - shared_scope_units)
    if unused:
        warnings.append(f"argument units not assigned to question readiness coverage: {unused}")

    details = {
        "stage": stage,
        "questions": sorted(question_ids),
        "units_by_question": units_by_question,
        "shared_scope_units": sorted(shared_scope_units),
        "used_units": sorted(used_units),
        "presentation_completeness": presentation_completeness(plan),
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
