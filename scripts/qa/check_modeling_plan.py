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
CHARACTERISTIC_VALIDATION_REQUIREMENTS = {
    "stochastic": {"uncertainty"},
    "scenario_based": {"scenario_generalization"},
    "correlated_inputs": {"correlation_validity"},
    "multi_stage": {"nonanticipativity"},
    "time_dependent": {"stability"},
    "multiobjective": {"sensitivity"},
    "machine_learning": {"out_of_sample", "leakage", "baseline"},
}


def evaluate_modeling_plan(
    model_contract: dict[str, Any],
    evidence_registry: dict[str, Any],
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Return errors, warnings, and coverage details for the research-to-plan chain."""

    errors: list[str] = []
    warnings: list[str] = []
    question_ids = {
        row.get("question_id")
        for row in model_contract.get("questions", [])
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }
    research = model_contract.get("research_basis")
    if not isinstance(research, dict):
        return ["model_contract.research_basis is required before M1 can pass"], [], {}
    if research.get("status") != "verified":
        errors.append("research_basis.status must be verified")

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
            errors.append(f"research {research_id} has no recorded LLM-knowledge reconnaissance")
        if not any(row.get("source") in EXTERNAL_RESEARCH_SOURCES for row in rows):
            errors.append(f"research {research_id} has no recorded external literature/web search")

    evidence_by_id = {
        row.get("evidence_id"): row
        for row in evidence_registry.get("evidence", [])
        if isinstance(row, dict) and isinstance(row.get("evidence_id"), str)
    }

    candidates = [row for row in research.get("candidate_models", []) if isinstance(row, dict)]
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

    coverage = {
        "questions": sorted(question_ids),
        "research_questions": sorted(research_by_id),
        "selected_candidates": selected_map,
        "verified_evidence": len(
            [row for row in evidence_by_id.values() if row.get("verification_status") == "verified"]
        ),
    }
    return errors, warnings, coverage


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--evidence-registry", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
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
        plan_errors, plan_warnings, coverage = evaluate_modeling_plan(contract, registry)
        errors.extend(plan_errors)
        warnings.extend(plan_warnings)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "model_contract": rel_path(contract_path, root),
        "evidence_registry": rel_path(registry_path, root),
        "coverage": coverage,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
