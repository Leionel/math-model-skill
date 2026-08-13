#!/usr/bin/env python3
"""Run deterministic checks over frozen numbers, evidence, and paper references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file  # noqa: E402


def canonical_display(value: Any, precision: int) -> str | None:
    try:
        decimal = Decimal(str(value))
        quantum = Decimal(1).scaleb(-precision)
        rounded = decimal.quantize(quantum, rounding=ROUND_HALF_UP)
        return f"{rounded:.{precision}f}"
    except (InvalidOperation, ValueError, TypeError):
        return None


def read_text(path: Path, label: str, errors: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        errors.append(f"{label} cannot be read: {exc}")
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--evidence-registry", required=True)
    parser.add_argument("--abstract")
    parser.add_argument("--paper")
    parser.add_argument("--conclusion")
    parser.add_argument("--figures-dir")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    plan_path = resolve_path(args.paper_plan, root).resolve()
    frozen_path = resolve_path(args.frozen_results, root).resolve()
    registry_path = resolve_path(args.evidence_registry, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        plan = load_structured(plan_path)
        frozen = load_structured(frozen_path)
        registry = load_structured(registry_path)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 1

    if not isinstance(plan, dict) or not isinstance(frozen, dict) or not isinstance(registry, dict):
        errors.append("paper-plan, frozen-results, and evidence-registry must all be objects")
        plan = plan if isinstance(plan, dict) else {}
        frozen = frozen if isinstance(frozen, dict) else {}
        registry = registry if isinstance(registry, dict) else {}

    if frozen.get("status") != "frozen":
        errors.append("frozen_results.status must be frozen")
    if frozen.get("claimable") is not True or frozen.get("validation_verdict") != "PASS":
        errors.append("frozen_results must be claimable with validation_verdict=PASS before consistency/W1")
    results = frozen.get("results", [])
    if not isinstance(results, list) or not results:
        errors.append("frozen_results.results must be a non-empty array")
        results = []
    result_by_id: dict[str, dict[str, Any]] = {}
    for index, result in enumerate(results):
        if not isinstance(result, dict):
            errors.append(f"frozen_results.results[{index}] must be an object")
            continue
        result_id = result.get("result_id")
        if not isinstance(result_id, str) or not result_id:
            errors.append(f"frozen_results.results[{index}] has no result_id")
            continue
        if result_id in result_by_id:
            errors.append(f"duplicate result_id: {result_id}")
        result_by_id[result_id] = result
        if result.get("validation_status") != "passed" or result.get("claimable") is not True:
            errors.append(f"result {result_id} is not validated")
        precision = result.get("precision")
        if isinstance(precision, int) and precision >= 0:
            expected = canonical_display(result.get("value"), precision)
            if expected is not None and result.get("display_value") != expected:
                errors.append(f"result {result_id} display_value drift: expected {expected!r}, got {result.get('display_value')!r}")
        else:
            errors.append(f"result {result_id} precision must be a non-negative integer")
        if not isinstance(result.get("unit"), str) or not result["unit"].strip():
            errors.append(f"result {result_id} unit must be non-empty")

    registry_evidence = registry.get("evidence", [])
    if not isinstance(registry_evidence, list):
        errors.append("evidence_registry.evidence must be an array")
        registry_evidence = []
    evidence_by_id: dict[str, dict[str, Any]] = {}
    for index, evidence in enumerate(registry_evidence):
        if not isinstance(evidence, dict) or not isinstance(evidence.get("evidence_id"), str):
            errors.append(f"evidence_registry.evidence[{index}] must contain evidence_id")
            continue
        evidence_id = evidence["evidence_id"]
        if evidence_id in evidence_by_id:
            errors.append(f"duplicate evidence_id: {evidence_id}")
        evidence_by_id[evidence_id] = evidence
        for result_id in evidence.get("result_ids", []):
            if result_id not in result_by_id:
                errors.append(f"evidence {evidence_id} references unknown result_id {result_id}")
        for artifact_index, artifact in enumerate(evidence.get("artifacts", [])):
            if not isinstance(artifact, dict):
                errors.append(f"evidence {evidence_id} artifact[{artifact_index}] must be an object")
                continue
            artifact_path = artifact.get("path")
            if not isinstance(artifact_path, str):
                errors.append(f"evidence {evidence_id} artifact[{artifact_index}].path must be a string")
                continue
            if artifact_path.startswith(("http://", "https://", "s3://", "artifact://")):
                warnings.append(f"evidence {evidence_id} uses external artifact path {artifact_path}")
                continue
            artifact_file = resolve_path(artifact_path, root).resolve()
            if not artifact_file.is_file():
                errors.append(f"evidence {evidence_id} artifact does not exist: {artifact_path}")
            elif artifact.get("sha256") != sha256_file(artifact_file):
                errors.append(f"evidence {evidence_id} artifact hash drift: {artifact_path}")

    matching_frozen_snapshot = False
    for snapshot in registry.get("source_snapshots", []):
        if not isinstance(snapshot, dict) or snapshot.get("kind") != "frozen_results":
            continue
        snapshot_path = resolve_path(str(snapshot.get("path", "")), root).resolve()
        if snapshot_path == frozen_path and snapshot.get("sha256") == sha256_file(frozen_path):
            matching_frozen_snapshot = True
    if not matching_frozen_snapshot:
        errors.append("evidence_registry has no current snapshot of the supplied frozen_results file")

    claims = plan.get("claims", [])
    claim_by_id = {claim.get("claim_id"): claim for claim in claims if isinstance(claim, dict)}
    if len(claim_by_id) != len([claim for claim in claims if isinstance(claim, dict)]):
        errors.append("paper_plan claim_id values must be unique")
    for claim in claims:
        if not isinstance(claim, dict):
            continue
        for evidence_id in claim.get("evidence_ids", []):
            if evidence_id not in evidence_by_id:
                errors.append(f"claim {claim.get('claim_id')} references unknown evidence_id {evidence_id}")
            elif evidence_by_id[evidence_id].get("verification_status") != "verified":
                errors.append(f"claim {claim.get('claim_id')} references unverified evidence_id {evidence_id}")
    for requirement in plan.get("requirements", []):
        if isinstance(requirement, dict):
            for claim_id in requirement.get("claim_ids", []):
                if claim_id not in claim_by_id:
                    errors.append(f"requirement {requirement.get('requirement_id')} references unknown claim_id {claim_id}")
    abstract_results = [row for row in plan.get("abstract_results", []) if isinstance(row, dict)]
    abstract_result_ids = [row.get("result_id") for row in abstract_results]
    if len(abstract_result_ids) != len(set(abstract_result_ids)):
        errors.append("abstract_results result_id values must be unique")
    for row in abstract_results:
        result_id = row.get("result_id")
        if result_id not in result_by_id:
            errors.append(f"abstract_results references unknown result_id {result_id}")
        for claim_id in row.get("claim_ids", []):
            if claim_id not in claim_by_id:
                errors.append(f"abstract result {result_id} references unknown claim_id {claim_id}")
        if not str(row.get("selection_reason", "")).strip():
            errors.append(f"abstract result {result_id} has no selection_reason")
    maximum_abstract_results = plan.get("precision_policy", {}).get("abstract_max_numeric_claims")
    if isinstance(maximum_abstract_results, int) and len(abstract_results) > maximum_abstract_results:
        errors.append(
            f"abstract_results has {len(abstract_results)} entries; precision_policy allows {maximum_abstract_results}"
        )
    section_by_id = {section.get("section_id"): section for section in plan.get("sections", []) if isinstance(section, dict)}
    for claim in claims:
        if isinstance(claim, dict) and claim.get("section") not in section_by_id:
            errors.append(f"claim {claim.get('claim_id')} references unknown section {claim.get('section')}")
    for section_id, section in section_by_id.items():
        for claim_id in section.get("claim_ids", []):
            if claim_id not in claim_by_id:
                errors.append(f"section {section_id} references unknown claim_id {claim_id}")
    for collection_name in ("figures", "tables"):
        for item in plan.get(collection_name, []):
            if not isinstance(item, dict):
                continue
            item_id = item.get("figure_id", item.get("table_id", collection_name[:-1]))
            for claim_id in item.get("claim_ids", []):
                if claim_id not in claim_by_id:
                    errors.append(f"{collection_name[:-1]} {item_id} references unknown claim_id {claim_id}")
            for evidence_id in item.get("evidence_ids", []):
                if evidence_id not in evidence_by_id:
                    errors.append(f"{collection_name[:-1]} {item_id} references unknown evidence_id {evidence_id}")

    text_sources: dict[str, str] = {}
    for label, raw_path in (("abstract", args.abstract), ("paper", args.paper), ("conclusion", args.conclusion)):
        if raw_path:
            path = resolve_path(raw_path, root).resolve()
            content = read_text(path, label, errors)
            if content is not None:
                text_sources[label] = content
    if args.abstract is None and abstract_results:
        warnings.append("abstract was not supplied; Abstract Gate numeric coverage was not checked")

    terminology = plan.get("terminology", [])
    for label, text in text_sources.items():
        for term in terminology:
            if not isinstance(term, dict):
                continue
            for variant in term.get("forbidden_variants", []):
                if isinstance(variant, str) and variant and variant.casefold() in text.casefold():
                    errors.append(f"{label} contains forbidden terminology variant {variant!r}; use {term.get('canonical')!r}")
        for result_id, result in result_by_id.items():
            display = str(result.get("display_value", ""))
            if result_id in text and display and display not in text:
                errors.append(f"{label} mentions result {result_id} without canonical display_value {display}")

    if "abstract" in text_sources:
        abstract = text_sources["abstract"]
        for row in abstract_results:
            result_id = row.get("result_id")
            result = result_by_id.get(result_id)
            if result is None:
                continue
            display = str(result.get("display_value", ""))
            if display and display not in abstract:
                errors.append(f"abstract is missing frozen result {result_id} display_value {display}")
                continue
            unit = str(result.get("unit", ""))
            if display and unit and unit != "dimensionless":
                position = abstract.find(display)
                context = abstract[max(0, position - 32):position + len(display) + 32]
                if unit not in context:
                    errors.append(f"abstract result {result_id} is missing unit {unit!r} near {display}")

    registered_numbers = {str(result.get("display_value")) for result in result_by_id.values()}
    number_pattern = re.compile(r"(?<![A-Za-z0-9_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])")
    for label in ("abstract", "conclusion"):
        if label not in text_sources:
            continue
        unregistered = sorted({match.group(0) for match in number_pattern.finditer(text_sources[label]) if match.group(0) not in registered_numbers})
        if unregistered:
            warnings.append(f"{label} contains numeric token(s) not registered in frozen_results: {', '.join(unregistered)}")

    if "paper" in text_sources:
        paper_text = text_sources["paper"]
        for figure in plan.get("figures", []):
            figure_id = figure.get("figure_id")
            if figure_id and figure_id not in paper_text:
                warnings.append(f"paper does not reference planned figure_id {figure_id}")
        for table in plan.get("tables", []):
            table_id = table.get("table_id")
            if table_id and table_id not in paper_text:
                warnings.append(f"paper does not reference planned table_id {table_id}")

    figure_dir = resolve_path(args.figures_dir, root).resolve() if args.figures_dir else None
    for figure in plan.get("figures", []):
        if not isinstance(figure, dict):
            continue
        figure_id = figure.get("figure_id", "figure")
        for artifact in figure.get("data_artifacts", []):
            if not isinstance(artifact, str) or artifact.startswith(("http://", "https://", "s3://", "artifact://")):
                continue
            candidates = [root / artifact]
            if figure_dir:
                candidates.append(figure_dir / artifact)
            if not any(candidate.is_file() for candidate in candidates):
                message = f"figure {figure_id} data artifact does not exist: {artifact}"
                if figure.get("qa_status") == "passed":
                    errors.append(message)
                else:
                    warnings.append(message)

    for table in plan.get("tables", []):
        if not isinstance(table, dict):
            continue
        table_id = table.get("table_id", "table")
        for artifact in table.get("data_artifacts", []):
            if not isinstance(artifact, str) or artifact.startswith(("http://", "https://", "s3://", "artifact://")):
                continue
            if not resolve_path(artifact, root).resolve().is_file():
                message = f"table {table_id} data artifact does not exist: {artifact}"
                if table.get("qa_status") == "passed":
                    errors.append(message)
                else:
                    warnings.append(message)

    ok = not errors and (not args.strict or not warnings)
    report = {
        "ok": ok,
        "files": {
            "paper_plan": rel_path(plan_path, root),
            "frozen_results": rel_path(frozen_path, root),
            "evidence_registry": rel_path(registry_path, root),
        },
        "errors": errors,
        "warnings": warnings,
        "checked_texts": sorted(text_sources),
        "checked_results": len(result_by_id),
        "checked_evidence": len(evidence_by_id),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
