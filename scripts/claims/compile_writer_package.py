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
        results = {
            row.get("result_id"): row
            for row in frozen.get("results", [])
            if isinstance(row, dict) and isinstance(row.get("result_id"), str)
        }
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
                "boundary": claim["boundary"],
                "comparison": claim.get("comparison"),
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
            "claims": claims,
            "source_snapshots": {
                "paper_plan": file_ref(plan_path, root, args.integrity_mode),
                "frozen_results": file_ref(frozen_path, root, args.integrity_mode),
                "evidence_registry": file_ref(registry_path, root, args.integrity_mode),
            },
            "readiness": plan.get("readiness"),
            "package_mode": "preview" if args.preview else "technical_draft",
            "writer_constraints": [
                "Do not create a research number, comparator, causal mechanism, scenario, or stronger conclusion absent from this package.",
                "Use only frozen display_value and unit for result numbers.",
                "Preserve every claim boundary and support_level.",
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
