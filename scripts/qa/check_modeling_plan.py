#!/usr/bin/env python3
"""Reject shallow modeling plans before implementation starts."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path  # noqa: E402
from qa.check_derivation_integrity import evaluate_derivation_integrity  # noqa: E402
from qa.check_math_semantics import evaluate_contract_semantics  # noqa: E402
from qa.check_scope_consistency import evaluate_scope_consistency  # noqa: E402
from qa.presentation_semantics import evaluate_required_answer_declarations  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


EXTERNAL_RESEARCH_SOURCES = {
    "web_search",
    "google_scholar",
    "openalex",
    "crossref",
    "cnki",
    "publisher",
    "official_repository",
}
RESEARCH_OBLIGATION_STATUSES = {"covered", "gap", "waived", "not_applicable"}
RESEARCH_ADVISORY_PREFIX = "research advisory: "
CHARACTERISTIC_VALIDATION_REQUIREMENTS = {
    "stochastic": {"uncertainty"},
    "scenario_based": {"scenario_generalization"},
    "correlated_inputs": {"correlation_validity"},
    "multi_stage": {"nonanticipativity"},
    "time_dependent": {"stability"},
    "multiobjective": {"sensitivity"},
    "machine_learning": {"out_of_sample", "leakage", "baseline"},
}


def _coverage_mode(model_contract: dict[str, Any]) -> bool:
    """Apply the new coverage contract only to schema v1.4."""

    return model_contract.get("schema_version") == "1.4"


def _evidence_ids(row: dict[str, Any]) -> list[str]:
    values = row.get("evidence_ids", [])
    return [value for value in values if isinstance(value, str)] if isinstance(values, list) else []


def _is_full_text_verified_evidence(evidence: dict[str, Any] | None) -> bool:
    if not isinstance(evidence, dict):
        return False
    citation = evidence.get("citation")
    return bool(
        evidence.get("type") == "citation"
        and evidence.get("verification_status") == "verified"
        and isinstance(citation, dict)
        and citation.get("metadata_verified") is True
        and citation.get("content_verified") is True
        and citation.get("publication_status_checked") is True
        and citation.get("access_level") == "full_text"
        and isinstance(citation.get("locator"), str)
        and citation.get("locator").strip()
    )


def _evaluate_research_coverage(
    model_contract: dict[str, Any],
    research: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str], dict[str, Any], set[str]]:
    """Validate the exact v1.4 research source and obligation vocabulary."""

    errors: list[str] = []
    warnings: list[str] = []
    discovery = [row for row in research.get("discovery_candidates", []) if isinstance(row, dict)]
    core = [row for row in research.get("full_text_core", []) if isinstance(row, dict)]
    excluded = [row for row in research.get("excluded_items", []) if isinstance(row, dict)]
    obligations = [row for row in research.get("research_obligations", []) if isinstance(row, dict)]

    if not research.get("research_scope"):
        errors.append("research_basis requires a non-empty research_scope")

    source_rows = [("discovery_candidate", row) for row in discovery]
    source_rows += [("full_text_core", row) for row in core]
    source_rows += [("excluded", row) for row in excluded]
    source_ids = [row.get("source_id") for _, row in source_rows]
    if any(not isinstance(source_id, str) or not source_id for source_id in source_ids):
        errors.append("every research source item requires source_id")
    elif len(source_ids) != len(set(source_ids)):
        errors.append("research source_id values must be unique")

    precedent_evidence_ids: set[str] = set()
    non_core_evidence_ids: set[str] = set()
    for state, row in source_rows:
        source_id = row.get("source_id", state)
        evidence_ids = _evidence_ids(row)
        if row.get("source_role") == "precedent_pattern":
            precedent_evidence_ids.update(evidence_ids)
        if state != "full_text_core":
            non_core_evidence_ids.update(evidence_ids)
        if state == "full_text_core":
            if not row.get("inclusion_reason"):
                errors.append(f"full_text_core {source_id} requires inclusion_reason")
            if not evidence_ids:
                errors.append(f"full_text_core {source_id} requires evidence_ids")
            for evidence_id in evidence_ids:
                if not _is_full_text_verified_evidence(evidence_by_id.get(evidence_id)):
                    errors.append(
                        f"full_text_core {source_id} evidence {evidence_id} must have metadata/content/publication verification and full_text access"
                    )
        elif state == "excluded" and not row.get("exclusion_reason"):
            errors.append(f"excluded source {source_id} requires exclusion_reason")
        for evidence_id in evidence_ids:
            if evidence_id not in evidence_by_id:
                errors.append(f"{state} {source_id} references missing evidence {evidence_id}")

    core_evidence_ids = {evidence_id for row in core for evidence_id in _evidence_ids(row)}
    seen_obligations: set[str] = set()
    obligation_summary: list[dict[str, Any]] = []
    critical_gap = False
    for row in obligations:
        obligation_id = row.get("obligation_id")
        if not isinstance(obligation_id, str) or not obligation_id:
            errors.append("research obligation requires obligation_id")
            continue
        if obligation_id in seen_obligations:
            errors.append(f"duplicate research obligation {obligation_id}")
        seen_obligations.add(obligation_id)
        status = row.get("status")
        evidence_ids = _evidence_ids(row)
        reason = row.get("reason")
        critical = row.get("critical")
        if status not in RESEARCH_OBLIGATION_STATUSES:
            errors.append(f"research obligation {obligation_id} has invalid status {status!r}")
        if not isinstance(critical, bool):
            errors.append(f"research obligation {obligation_id} requires critical=true/false")
        if status == "covered" and not evidence_ids and not reason:
            errors.append(f"covered research obligation {obligation_id} requires evidence_ids or reason")
        if status in {"gap", "waived", "not_applicable"} and not reason:
            errors.append(f"research obligation {obligation_id} with status={status} requires reason")
        for evidence_id in evidence_ids:
            if evidence_id not in evidence_by_id:
                errors.append(f"research obligation {obligation_id} references missing evidence {evidence_id}")
            elif evidence_id in precedent_evidence_ids:
                errors.append(f"research obligation {obligation_id} cannot use precedent-pattern evidence {evidence_id}")
            elif status == "covered" and (
                evidence_id not in core_evidence_ids
                or not _is_full_text_verified_evidence(evidence_by_id[evidence_id])
            ):
                errors.append(f"covered research obligation {obligation_id} requires verified full_text_core evidence")
        if status == "gap":
            if critical is True:
                critical_gap = True
                errors.append(f"critical research obligation {obligation_id} remains a gap: {reason}")
            else:
                warnings.append(RESEARCH_ADVISORY_PREFIX + f"non-critical research obligation {obligation_id} remains a gap")
        obligation_summary.append({
            "obligation_id": obligation_id,
            "category": row.get("category"),
            "status": status,
            "critical": critical,
            "evidence_ids": evidence_ids,
        })

    if model_contract.get("status") == "ready" or research.get("status") == "ready":
        stop = research.get("stop_reason")
        if not isinstance(stop, dict) or not stop.get("kind") or not stop.get("reason"):
            errors.append("ready research_basis requires a structured stop_reason")
        elif stop["kind"] in {"time_box", "waiver"} and not stop.get("residual_risk"):
            errors.append("time-box/waiver stop_reason requires residual_risk")

    details = {
        "mode": "coverage_driven",
        "discovery_candidates": len(discovery),
        "full_text_core": len(core),
        "excluded_items": len(excluded),
        "research_obligations": obligation_summary,
        "critical_gap": critical_gap,
        "precedent_evidence_ids": sorted(precedent_evidence_ids),
        "core_evidence_ids": sorted(core_evidence_ids),
        "non_core_evidence_ids": sorted(non_core_evidence_ids),
    }
    return errors, warnings, details, precedent_evidence_ids

ARTIFACT_REQUIRED_BY_CATEGORY = {
    "sensitivity": "sensitivity_experiment",
    "out_of_sample": "oos_artifact",
}


def evaluate_modeling_plan(
    model_contract: dict[str, Any],
    evidence_registry: dict[str, Any],
    *,
    require_reasonableness: bool = False,
    require_scope_contract: bool = False,
    require_critical_sensitivity: bool = False,
    require_answer_contract: bool = False,
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Return errors, warnings, and coverage details for the research-to-plan chain."""

    errors: list[str] = []
    warnings: list[str] = []
    question_ids = {
        row.get("question_id")
        for row in model_contract.get("questions", [])
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }
    answer_errors, answer_details = evaluate_required_answer_declarations(
        model_contract,
        require=require_answer_contract,
    )
    errors.extend(answer_errors)
    research = model_contract.get("research_basis")
    if not isinstance(research, dict):
        return ["model_contract.research_basis is required before M1 can pass"], [], {}
    if research.get("status") not in {"verified", "ready"}:
        errors.append("research_basis.status must be verified or ready")

    research_rows = [row for row in research.get("research_questions", []) if isinstance(row, dict)]
    research_by_id = {
        row.get("research_id"): row
        for row in research_rows
        if isinstance(row.get("research_id"), str)
    }
    covered_by_research: set[str] = set()
    for row in research_rows:
        covered_by_research.update(qid for qid in row.get("question_ids", []) if isinstance(qid, str))
    if covered_by_research != question_ids:
        errors.append(
            "research_questions must cover exactly the modeled questions; "
            f"missing={sorted(question_ids - covered_by_research)}, extra={sorted(covered_by_research - question_ids)}"
        )

    evidence_by_id = {
        row.get("evidence_id"): row
        for row in evidence_registry.get("evidence", [])
        if isinstance(row, dict) and isinstance(row.get("evidence_id"), str)
    }

    coverage_mode = _coverage_mode(model_contract)
    research_coverage_details: dict[str, Any] = {}
    precedent_evidence_ids: set[str] = set()
    if coverage_mode:
        coverage_errors, coverage_warnings, research_coverage_details, precedent_evidence_ids = _evaluate_research_coverage(
            model_contract,
            research,
            evidence_by_id,
        )
        errors.extend(coverage_errors)
        warnings.extend(coverage_warnings)

    searches_by_research: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for search in research.get("searches", []):
        if not isinstance(search, dict):
            continue
        for research_id in search.get("research_ids", []):
            if research_id not in research_by_id:
                errors.append(f"search {search.get('search_id')} references unknown research_id {research_id}")
            else:
                searches_by_research[research_id].append(search)
    for research_id in research_by_id:
        rows = searches_by_research.get(research_id, [])
        if not any(row.get("source") == "llm_knowledge" for row in rows):
            message = f"research {research_id} has no recorded LLM-knowledge reconnaissance"
            if coverage_mode:
                message = RESEARCH_ADVISORY_PREFIX + message
            (errors if not coverage_mode else warnings).append(message)
        if not any(row.get("source") in EXTERNAL_RESEARCH_SOURCES for row in rows):
            message = f"research {research_id} has no recorded external literature/web search"
            if coverage_mode:
                message = RESEARCH_ADVISORY_PREFIX + message
            (errors if not coverage_mode else warnings).append(message)
        if require_reasonableness:
            for search in rows:
                if search.get("candidate_count", 0) < 1:
                    message = (
                        f"formal M1 search {search.get('search_id')} has candidate_count=0; "
                        "a zero-result search cannot support model selection"
                    )
                    if coverage_mode:
                        message = RESEARCH_ADVISORY_PREFIX + message
                    (errors if not coverage_mode else warnings).append(message)
                if search.get("source") in EXTERNAL_RESEARCH_SOURCES:
                    search_evidence_ids = search.get("evidence_ids", [])
                    if not search_evidence_ids:
                        message = (
                            f"formal M1 external search {search.get('search_id')} must bind evidence_ids"
                        )
                        if coverage_mode:
                            message = RESEARCH_ADVISORY_PREFIX + message
                        (errors if not coverage_mode else warnings).append(message)
                    for evidence_id in search_evidence_ids:
                        evidence = evidence_by_id.get(evidence_id)
                        if evidence is None:
                            message = (
                                f"formal M1 search {search.get('search_id')} references missing evidence {evidence_id}"
                            )
                            if coverage_mode:
                                message = RESEARCH_ADVISORY_PREFIX + message
                            (errors if not coverage_mode else warnings).append(message)
                        elif evidence.get("verification_status") != "verified":
                            message = (
                                f"formal M1 search {search.get('search_id')} references unverified evidence {evidence_id}"
                            )
                            if coverage_mode:
                                message = RESEARCH_ADVISORY_PREFIX + message
                            (errors if not coverage_mode else warnings).append(message)

    candidates = [row for row in research.get("candidate_models", []) if isinstance(row, dict)]
    core_evidence_ids = set(research_coverage_details.get("core_evidence_ids", []))
    candidates_by_question: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        qid = candidate.get("question_id")
        if qid not in question_ids:
            errors.append(f"candidate {candidate.get('candidate_id')} references unknown question {qid}")
        else:
            candidates_by_question[qid].append(candidate)
        for evidence_id in candidate.get("evidence_ids", []):
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                errors.append(f"candidate {candidate.get('candidate_id')} references missing evidence {evidence_id}")
            elif evidence.get("verification_status") != "verified":
                errors.append(f"candidate {candidate.get('candidate_id')} references unverified evidence {evidence_id}")
            elif coverage_mode and not _is_full_text_verified_evidence(evidence):
                errors.append(
                    f"candidate {candidate.get('candidate_id')} references evidence {evidence_id} that is not full-text verified"
                )
            if coverage_mode and evidence_id in precedent_evidence_ids:
                errors.append(
                    f"candidate {candidate.get('candidate_id')} cannot use precedent-pattern evidence {evidence_id} as scientific support"
                )
            elif coverage_mode and evidence_id not in core_evidence_ids:
                errors.append(
                    f"candidate {candidate.get('candidate_id')} references evidence {evidence_id} outside full_text_core"
                )

    decisions = [row for row in research.get("decisions", []) if isinstance(row, dict)]
    decisions_by_question: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for decision in decisions:
        decisions_by_question[decision.get("question_id")].append(decision)

    models_by_id = {
        row.get("model_id"): row
        for row in model_contract.get("models", [])
        if isinstance(row, dict) and isinstance(row.get("model_id"), str)
    }
    models_by_question: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for model in models_by_id.values():
        models_by_question[model.get("question_id")].append(model)
        characteristics = model.get("characteristics", [])
        if not characteristics:
            errors.append(f"model {model.get('model_id')} must declare model characteristics")
            continue
        required_categories: set[str] = set()
        for characteristic in characteristics:
            required_categories.update(CHARACTERISTIC_VALIDATION_REQUIREMENTS.get(characteristic, set()))
        actual_categories = {
            row.get("category")
            for row in model.get("validation_obligations", [])
            if isinstance(row, dict)
        }
        missing_categories = sorted(required_categories - actual_categories)
        if missing_categories:
            errors.append(
                f"model {model.get('model_id')} characteristics trigger missing validation categories: {missing_categories}"
            )
        details = model.get("plan_details")
        if isinstance(details, dict):
            parameter_names = {
                row.get("parameter")
                for row in details.get("parameter_plan", [])
                if isinstance(row, dict) and isinstance(row.get("parameter"), str)
            }
            uncovered_inputs = sorted(
                input_name for input_name in model.get("inputs", [])
                if isinstance(input_name, str) and input_name not in parameter_names
            )
            if uncovered_inputs:
                errors.append(
                    f"model {model.get('model_id')} inputs lack typed parameter provenance: {uncovered_inputs}"
                )
            for parameter in details.get("parameter_plan", []):
                if not isinstance(parameter, dict):
                    continue
                provenance = parameter.get("provenance") if isinstance(parameter.get("provenance"), dict) else {}
                impact_class = parameter.get("impact_class")
                assumed_high = provenance.get("type") == "ASSUMED" and impact_class in {"high", "critical"}
                if require_critical_sensitivity and (impact_class in {"high", "critical"} or assumed_high):
                    if not isinstance(parameter.get("parameter_id"), str) or not parameter.get("parameter_id"):
                        errors.append(
                            f"model {model.get('model_id')} high-impact parameter {parameter.get('parameter')} requires parameter_id"
                        )
                    if not parameter.get("sensitivity_experiment_ids"):
                        errors.append(
                            f"model {model.get('model_id')} high-impact parameter {parameter.get('parameter')} requires sensitivity_experiment_ids"
                        )
        for obligation in model.get("validation_obligations", []):
            if not isinstance(obligation, dict):
                continue
            category = obligation.get("category")
            expected_role = ARTIFACT_REQUIRED_BY_CATEGORY.get(category)
            if expected_role and obligation.get("artifact_role") != expected_role:
                errors.append(
                    f"model {model.get('model_id')} obligation {obligation.get('obligation_id')} "
                    f"category={category} requires artifact_role={expected_role}"
                )

    selected_map: dict[str, str] = {}
    for qid in sorted(question_ids):
        q_candidates = candidates_by_question.get(qid, [])
        q_decisions = decisions_by_question.get(qid, [])
        if len(q_decisions) != 1:
            errors.append(f"question {qid} requires exactly one model-selection decision, found {len(q_decisions)}")
            continue
        decision = q_decisions[0]
        if len(q_candidates) < 2 and not decision.get("single_candidate_waiver"):
            errors.append(f"question {qid} requires at least two candidate models or a single_candidate_waiver")
        selected = [row for row in q_candidates if row.get("decision") == "selected"]
        if len(selected) != 1:
            errors.append(f"question {qid} requires exactly one selected candidate, found {len(selected)}")
            continue
        candidate = selected[0]
        candidate_id = candidate.get("candidate_id")
        selected_map[qid] = str(candidate_id)
        if decision.get("selected_candidate_id") != candidate_id:
            errors.append(f"question {qid} decision does not name its selected candidate")
        alternative_ids = {
            row.get("candidate_id") for row in q_candidates if row.get("candidate_id") != candidate_id
        }
        considered = set(decision.get("alternatives_considered", []))
        if alternative_ids and not alternative_ids.issubset(considered):
            errors.append(
                f"question {qid} decision omits alternatives {sorted(alternative_ids - considered)}"
            )
        if not set(decision.get("decisive_evidence_ids", [])).issubset(set(candidate.get("evidence_ids", []))):
            errors.append(f"question {qid} decisive evidence must be attached to the selected candidate")
        if coverage_mode:
            forbidden_decisive = sorted(
                set(decision.get("decisive_evidence_ids", [])) & precedent_evidence_ids
            )
            if forbidden_decisive:
                errors.append(
                    f"question {qid} decision cannot use precedent-pattern evidence as scientific support: {forbidden_decisive}"
                )

        if require_reasonableness:
            rationale = str(decision.get("rationale", "")).casefold()
            candidate_name = str(candidate.get("name", "")).casefold()
            candidate_token = str(candidate_id).casefold()
            if candidate_name not in rationale and candidate_token not in rationale:
                errors.append(
                    f"question {qid} decision rationale must name the selected candidate or candidate_id"
                )
            if not decision.get("unresolved_risks") and not str(decision.get("risk_disposition", "")).strip():
                errors.append(
                    f"question {qid} must record unresolved_risks or an explicit risk_disposition"
                )

        verified_literature = []
        for evidence_id in candidate.get("evidence_ids", []):
            evidence = evidence_by_id.get(evidence_id, {})
            citation = evidence.get("citation") if isinstance(evidence, dict) else None
            if (
                evidence.get("type") == "citation"
                and evidence.get("verification_status") == "verified"
                and isinstance(citation, dict)
                and citation.get("metadata_verified") is True
                and citation.get("content_verified") is True
                and citation.get("publication_status_checked") is True
                and citation.get("access_level") == "full_text"
                and citation.get("locator")
            ):
                verified_literature.append(evidence_id)
        if not verified_literature:
            errors.append(
                f"selected candidate {candidate_id} needs at least one full-text, locator-backed verified citation"
            )
        if require_reasonableness:
            decisive_literature = [
                evidence_id for evidence_id in decision.get("decisive_evidence_ids", [])
                if evidence_id in verified_literature
            ]
            if not decisive_literature:
                errors.append(
                    f"question {qid} decisive_evidence_ids must include a full-text locator-backed verified citation"
                )

        model_id = candidate.get("model_id")
        model = models_by_id.get(model_id)
        if model is None or model.get("question_id") != qid:
            errors.append(f"selected candidate {candidate_id} must map to a model for question {qid}")
            continue
        details = model.get("plan_details")
        if not isinstance(details, dict):
            errors.append(f"model {model_id} requires detailed implementation plan_details")
            continue
        if details.get("selected_candidate_id") != candidate_id:
            errors.append(f"model {model_id}.plan_details does not bind selected candidate {candidate_id}")

    for qid in sorted(question_ids):
        if not models_by_question.get(qid):
            errors.append(f"question {qid} has no implementable model")

    unresolved = research.get("unresolved_questions", [])
    if unresolved:
        warnings.append(f"research_basis retains {len(unresolved)} unresolved question(s)")

    semantic_errors, semantic_warnings = evaluate_contract_semantics(model_contract)
    errors.extend(semantic_errors)
    warnings.extend(semantic_warnings)
    derivation_requested = any(
        isinstance(model.get("plan_details"), dict)
        and (
            isinstance(model["plan_details"].get("derivation_graph"), dict)
            or any(
                isinstance(equation, dict)
                and any(field in equation for field in ("equation_type", "math_risk", "verification"))
                for equation in model["plan_details"].get("equation_plan", [])
            )
        )
        for model in model_contract.get("models", [])
        if isinstance(model, dict)
    )
    if derivation_requested:
        derivation_errors, derivation_warnings, derivation_details = evaluate_derivation_integrity(
            model_contract, require_metadata=require_reasonableness
        )
        errors.extend(derivation_errors)
        warnings.extend(derivation_warnings)
    else:
        derivation_details = {"status": "NOT_APPLICABLE", "reason": "no enhanced equation contract requested"}

    scope_errors, scope_warnings, scope_details = evaluate_scope_consistency(
        model_contract,
        require_contract=require_scope_contract,
    )
    errors.extend(scope_errors)
    warnings.extend(scope_warnings)

    coverage = {
        "reasonableness_check": (
            "L1_completeness_evidence_linkage" if require_reasonableness else "L0_standard_contract_check"
        ),
        "research_coverage": research_coverage_details if coverage_mode else {
            "mode": "legacy_compatibility",
            "note": "S5 coverage fields are absent; legacy research checks remain active.",
        },
        "questions": sorted(question_ids),
        "research_questions": sorted(research_by_id),
        "selected_candidates": selected_map,
        "verified_evidence": len(
            [row for row in evidence_by_id.values() if row.get("verification_status") == "verified"]
        ),
        "derivation_integrity": derivation_details,
        "scope_contract": scope_details,
        "required_answers": answer_details,
    }
    return errors, warnings, coverage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--evidence-registry", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--formal",
        action="store_true",
        help="Enable formal M1 completeness/evidence-linkage checks; this is still not a semantic proof of model validity.",
    )
    parser.add_argument(
        "--require-scope-contract",
        action="store_true",
        help="Require a ready question-scoped parameter/event contract in addition to the standard M1 checks.",
    )
    parser.add_argument(
        "--require-critical-sensitivity",
        action="store_true",
        help="Require high/critical or assumed-high parameters to bind a sensitivity experiment.",
    )
    parser.add_argument(
        "--require-answer-contract",
        action="store_true",
        help="Require each modeled question to declare a structured required_answer before M1.",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    contract_path = resolve_path(args.model_contract, root).resolve()
    registry_path = resolve_path(args.evidence_registry, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    coverage: dict[str, Any] = {}
    try:
        contract, contract_schema_errors, _ = _validate_document(
            contract_path, Path(__file__).resolve().parents[2] / "schemas" / "model_contract.schema.json"
        )
        registry, registry_schema_errors, _ = _validate_document(
            registry_path, Path(__file__).resolve().parents[2] / "schemas" / "evidence_registry.schema.json"
        )
        errors.extend(f"model_contract schema: {message}" for message in contract_schema_errors)
        errors.extend(f"evidence_registry schema: {message}" for message in registry_schema_errors)
        if not isinstance(contract, dict) or not isinstance(registry, dict):
            raise ValueError("model contract and evidence registry must be objects")
        if contract.get("run_id") != registry.get("run_id"):
            errors.append("model_contract and evidence_registry must share one run_id")
        plan_errors, plan_warnings, coverage = evaluate_modeling_plan(
            contract,
            registry,
            require_reasonableness=args.formal,
            require_scope_contract=args.require_scope_contract,
            require_critical_sensitivity=args.require_critical_sensitivity,
            require_answer_contract=args.require_answer_contract,
        )
        errors.extend(plan_errors)
        warnings.extend(plan_warnings)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    # S5 advisories are deliberately visible but do not become a hidden
    # literature/query quota when the formal checker is run with --strict.
    blocking_warnings = [warning for warning in warnings if not warning.startswith(RESEARCH_ADVISORY_PREFIX)]
    ok = not errors and (not args.strict or not blocking_warnings)
    print(json.dumps({
        "ok": ok,
        "model_contract": rel_path(contract_path, root),
        "evidence_registry": rel_path(registry_path, root),
        "formal": args.formal,
        "coverage": coverage,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
