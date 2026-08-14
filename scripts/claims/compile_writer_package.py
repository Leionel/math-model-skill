#!/usr/bin/env python3
"""Compile a read-only writer package from approved claims and verified evidence."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file, write_json  # noqa: E402
from qa.check_paper_readiness import evaluate_readiness  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


def file_ref(path: Path, root: Path, integrity_mode: str) -> dict[str, str]:
    ref = {"path": rel_path(path, root)}
    if integrity_mode == "submission":
        ref["sha256"] = sha256_file(path)
    return ref


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--evidence-registry", required=True)
    parser.add_argument("--derived-results")
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--integrity-mode", choices=("dev", "research", "submission"), default="research")
    parser.add_argument(
        "--preview",
        action="store_true",
        help="Allow an outline-only package for local inspection; never use this for a formal first draft.",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    plan_path = resolve_path(args.paper_plan, root).resolve()
    frozen_path = resolve_path(args.frozen_results, root).resolve()
    registry_path = resolve_path(args.evidence_registry, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        plan = load_structured(plan_path)
        frozen = load_structured(frozen_path)
        registry = load_structured(registry_path)
        if not all(isinstance(item, dict) for item in (plan, frozen, registry)):
            raise ValueError("paper plan, frozen results, and evidence registry must be objects")
        if plan.get("status") != "ready":
            raise ValueError("paper_plan.status must be ready before compiling a writer package")
        if frozen.get("claimable") is not True or frozen.get("validation_verdict") != "PASS":
            raise ValueError("writer package requires claimable PASS frozen results")
        if len({plan.get("run_id"), frozen.get("run_id"), registry.get("run_id")}) != 1:
            raise ValueError("paper plan, frozen results, and evidence registry must share one run_id")
        if not args.preview:
            readiness_errors, readiness_warnings, _ = evaluate_readiness(
                plan, registry, "technical_draft"
            )
            if readiness_errors:
                raise ValueError("paper plan is not ready for a technical first draft: " + "; ".join(readiness_errors))
            if readiness_warnings:
                raise ValueError("paper plan readiness has unresolved warnings: " + "; ".join(readiness_warnings))
        planned_derived_ids = {
            derived_id
            for claim in plan.get("claims", [])
            if isinstance(claim, dict)
            for derived_id in claim.get("derived_result_ids", [])
            if isinstance(derived_id, str)
        }
        if planned_derived_ids and not args.derived_results:
            raise ValueError(
                "paper plan references derived_result_ids; supply --derived-results so the Writer cannot recompute them"
            )
        results = {
            row.get("result_id"): row
            for row in frozen.get("results", [])
            if isinstance(row, dict) and isinstance(row.get("result_id"), str)
        }
        derived_rows: list[dict[str, Any]] = []
        derived_by_id: dict[str, dict[str, Any]] = {}
        if args.derived_results:
            derived_path = resolve_path(args.derived_results, root).resolve()
            derived_doc = load_structured(derived_path)
            if not isinstance(derived_doc, dict):
                raise ValueError("derived results must be an object")
            _, derived_schema_errors, _ = _validate_document(
                derived_path, Path(__file__).resolve().parents[2] / "schemas" / "derived_results.schema.json"
            )
            if derived_schema_errors:
                raise ValueError("derived results schema is invalid: " + "; ".join(derived_schema_errors))
            if derived_doc.get("run_id") != plan.get("run_id"):
                raise ValueError("derived results run_id does not match the paper plan")
            frozen_ref = derived_doc.get("frozen_results")
            if not isinstance(frozen_ref, dict) or frozen_ref.get("path") != rel_path(frozen_path, root):
                raise ValueError("derived results were not computed from the supplied frozen_results file")
            if frozen_ref.get("sha256") is not None and frozen_ref.get("sha256") != sha256_file(frozen_path):
                raise ValueError("derived results were not computed from the supplied frozen_results file: sha256 drift")
            for row in derived_doc.get("derived", []):
                if not isinstance(row, dict):
                    raise ValueError("derived results rows must be objects")
                for input_id in row.get("inputs", []):
                    if input_id not in results:
                        raise ValueError(f"derived result {row.get('derived_result_id')} uses unknown result {input_id}")
                derived_id = row.get("derived_result_id")
                if not isinstance(derived_id, str) or derived_id in derived_by_id:
                    raise ValueError(f"derived result ids must be unique and non-empty: {derived_id!r}")
                derived_by_id[derived_id] = row
                derived_rows.append({
                    "derived_result_id": derived_id,
                    "question_id": row.get("question_id"),
                    "type": row.get("type"),
                    "formula": row.get("formula"),
                    "display_value": row.get("display_value"),
                    "unit": row.get("unit"),
                    "inputs": row.get("inputs"),
                })
        missing_derived_ids = sorted(planned_derived_ids - set(derived_by_id))
        if missing_derived_ids:
            raise ValueError(f"paper plan references missing derived_result_ids: {missing_derived_ids}")
        evidence = {
            row.get("evidence_id"): row
            for row in registry.get("evidence", [])
            if isinstance(row, dict) and isinstance(row.get("evidence_id"), str)
        }
        claims: list[dict[str, Any]] = []
        for claim in plan.get("claims", []):
            if not isinstance(claim, dict):
                raise ValueError("paper_plan.claims must contain objects")
            claim_evidence = []
            for evidence_id in claim.get("evidence_ids", []):
                evidence_row = evidence.get(evidence_id)
                if evidence_row is None or evidence_row.get("verification_status") != "verified":
                    raise ValueError(f"claim {claim.get('claim_id')} has no verified evidence {evidence_id}")
                claim_evidence.append({"evidence_id": evidence_id, "supports": evidence_row.get("supports"), "boundary": evidence_row.get("boundary")})
            result_values = []
            for result_id in claim.get("result_ids", []):
                result = results.get(result_id)
                if result is None or result.get("claimable") is not True:
                    raise ValueError(f"claim {claim.get('claim_id')} has no claimable result {result_id}")
                result_values.append({
                    "result_id": result_id,
                    "name": result.get("name"),
                    "display_value": result.get("display_value"),
                    "unit": result.get("unit"),
                    "boundary": result.get("boundary"),
                })
            claims.append({
                "claim_id": claim["claim_id"],
                "claim_type": claim["claim_type"],
                "approved_text": claim["text"],
                "support_level": claim["support_level"],
                "inference_strength": claim.get(
                    "inference_strength",
                    "descriptive" if claim.get("claim_type") == "observation" else "mechanistic",
                ),
                "causal_design": claim.get("causal_design"),
                "boundary": claim["boundary"],
                "comparison": claim.get("comparison"),
                "derived_result_ids": claim.get("derived_result_ids", []),
                "precondition_claim_ids": claim.get("precondition_claim_ids", []),
                "evidence": claim_evidence,
                "results": result_values,
            })
        package = {
            "schema_version": "1.0",
            "run_id": plan["run_id"],
            "central_thesis": plan["central_thesis"],
            "precision_policy": plan["precision_policy"],
            "abstract_results": plan["abstract_results"],
            "argument_units": plan["argument_units"],
            "draft_coverage": plan.get("draft_coverage"),
            "claims": claims,
            "derived_results": derived_rows,
            "source_snapshots": {
                "paper_plan": file_ref(plan_path, root, args.integrity_mode),
                "frozen_results": file_ref(frozen_path, root, args.integrity_mode),
                "evidence_registry": file_ref(registry_path, root, args.integrity_mode),
            },
            "readiness": plan.get("readiness"),
            "package_mode": "preview" if args.preview else "technical_draft",
            "writer_constraints": [
                "Do not create a research number, comparator, causal mechanism, scenario, or stronger conclusion absent from this package.",
                "Use only frozen display_value and unit for result numbers; cite derived_results by derived_result_id for any secondary metric and never recompute percentages, changes, or ratios by hand.",
                "Preserve every claim boundary and support_level.",
                "Preserve every claim inference_strength; do not turn descriptive or associational evidence into a mechanistic or causal statement.",
                "Use each argument unit's rhetorical_role as its single primary research action.",
                "For every question, write the formulation, results, validation, and interpretation units before compressing prose.",
                "A short first draft is not acceptable when it omits an equation/derivation, validation evidence, or result boundary planned for that question.",
            ],
        }
        write_json(output_path, package)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "compiled", "output": rel_path(output_path, root), "claims": len(claims)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
