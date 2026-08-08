#!/usr/bin/env python3
"""Validate the five durable P0 contracts and their cross-references."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file, sha256_json  # noqa: E402


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    return True


def _resolve_ref(root_schema: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"only local schema refs are supported: {ref}")
    node: Any = root_schema
    for part in ref[2:].split("/"):
        node = node[part.replace("~1", "/").replace("~0", "~")]
    if not isinstance(node, dict):
        raise ValueError(f"schema ref does not resolve to an object: {ref}")
    return node


def _validate(value: Any, schema: dict[str, Any], root_schema: dict[str, Any], path: str, errors: list[str]) -> None:
    if "$ref" in schema:
        _validate(value, _resolve_ref(root_schema, schema["$ref"]), root_schema, path, errors)
        return

    if "allOf" in schema:
        for child in schema["allOf"]:
            _validate(value, child, root_schema, path, errors)
    if "oneOf" in schema:
        branches: list[list[str]] = []
        for child in schema["oneOf"]:
            child_errors: list[str] = []
            _validate(value, child, root_schema, path, child_errors)
            branches.append(child_errors)
        if not any(not branch for branch in branches):
            errors.append(f"{path}: does not match any oneOf branch")
            return

    expected = schema.get("type")
    if expected is not None:
        expected_types = expected if isinstance(expected, list) else [expected]
        if not any(_type_matches(value, item) for item in expected_types):
            errors.append(f"{path}: expected type {expected_types}, got {type(value).__name__}")
            return

    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: expected one of {schema['enum']!r}")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            errors.append(f"{path}: length is below minLength={schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: length exceeds maxLength={schema['maxLength']}")
        if "pattern" in schema:
            try:
                matched = re.search(schema["pattern"], value)
            except re.error as exc:
                errors.append(f"{path}: invalid schema pattern: {exc}")
                matched = True
            if not matched:
                errors.append(f"{path}: does not match pattern {schema['pattern']!r}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: value is below minimum={schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: value exceeds maximum={schema['maximum']}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errors.append(f"{path}: item count is below minItems={schema['minItems']}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: item count exceeds maxItems={schema['maxItems']}")
        if schema.get("uniqueItems"):
            encoded = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate(item, item_schema, root_schema, f"{path}[{index}]", errors)

    if isinstance(value, dict):
        if len(value) < schema.get("minProperties", 0):
            errors.append(f"{path}: property count is below minProperties={schema['minProperties']}")
        if "maxProperties" in schema and len(value) > schema["maxProperties"]:
            errors.append(f"{path}: property count exceeds maxProperties={schema['maxProperties']}")
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{path}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in properties:
                    errors.append(f"{path}: unexpected property {key!r}")
        for key, child_schema in properties.items():
            if key in value:
                _validate(value[key], child_schema, root_schema, f"{path}.{key}", errors)
        additional = schema.get("additionalProperties")
        if isinstance(additional, dict):
            for key, item in value.items():
                if key not in properties:
                    _validate(item, additional, root_schema, f"{path}.{key}", errors)


def _validate_document(path: Path, schema_path: Path) -> tuple[Any | None, list[str], str]:
    try:
        value = load_structured(path)
        schema = load_structured(schema_path)
        if not isinstance(schema, dict):
            return value, [f"{schema_path}: schema must be an object"], "fallback"
        errors: list[str] = []
        _validate(value, schema, schema, "$", errors)
        return value, errors, "fallback"
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return None, [f"{path}: {exc}"], "fallback"


def _cross_references(
    model: dict[str, Any],
    manifest: dict[str, Any],
    frozen: dict[str, Any],
    registry: dict[str, Any],
    plan: dict[str, Any],
    *,
    root: Path,
    paths: dict[str, Path],
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    def unique(label: str, values: list[Any]) -> set[Any]:
        if len(values) != len(set(values)):
            errors.append(f"{label} values must be unique")
        return set(values)

    def verify_file_ref(owner: str, ref: dict[str, Any]) -> Path | None:
        raw_path = ref.get("path")
        if not isinstance(raw_path, str):
            errors.append(f"{owner}.path must be a string")
            return None
        if raw_path.startswith(("http://", "https://", "s3://", "artifact://")):
            warnings.append(f"{owner} uses external path {raw_path}; local hash verification skipped")
            return None
        path = resolve_path(raw_path, root).resolve()
        if not path.is_file():
            errors.append(f"{owner} path does not exist: {raw_path}")
            return None
        actual = sha256_file(path)
        if ref.get("sha256") != actual:
            errors.append(f"{owner} sha256 does not match {raw_path}")
        return path

    run_ids = {
        label: value.get("run_id")
        for label, value in (("model_contract", model), ("run_manifest", manifest), ("frozen_results", frozen), ("evidence_registry", registry), ("paper_plan", plan))
        if isinstance(value, dict) and value.get("run_id") is not None
    }
    if len(set(run_ids.values())) > 1:
        errors.append(f"run_id mismatch across contracts: {run_ids}")

    if manifest.get("project_id") != model.get("project_id"):
        errors.append("run_manifest.project_id does not match model_contract.project_id")
    manifest_model_path = verify_file_ref("run_manifest.model_contract", manifest["model_contract"])
    if manifest_model_path is not None and manifest_model_path != paths["model_contract"].resolve():
        errors.append("run_manifest.model_contract.path is not the supplied model contract")
    for index, artifact in enumerate(manifest.get("artifacts", [])):
        verify_file_ref(f"run_manifest.artifacts[{index}]", artifact)

    question_ids = [row["question_id"] for row in model["questions"]]
    question_set = unique("model_contract question_id", question_ids)
    question_by_id = {row["question_id"]: row for row in model["questions"]}
    data_ids = [row["data_id"] for row in model["data_sources"]]
    unique("model_contract data_id", data_ids)
    assumption_ids = [row["assumption_id"] for row in model["assumptions"]]
    unique("model_contract assumption_id", assumption_ids)
    model_ids = [row["model_id"] for row in model["models"]]
    unique("model_contract model_id", model_ids)
    term_names = [row["canonical"] for row in model["terminology"]]
    unique("model_contract terminology canonical", term_names)
    for index, source in enumerate(model["data_sources"]):
        verify_file_ref(f"model_contract.data_sources[{index}]", source)
    for question in model["questions"]:
        for dependency in question.get("depends_on", []):
            if dependency not in question_set:
                errors.append(f"question {question['question_id']} depends on unknown question_id {dependency}")
            if dependency == question["question_id"]:
                errors.append(f"question {question['question_id']} cannot depend on itself")
    for row in model.get("models", []):
        if row.get("question_id") not in question_set:
            errors.append(f"model {row.get('model_id')} references unknown question_id {row.get('question_id')}")
            continue
        unique(f"model {row['model_id']} variable symbol", [item["symbol"] for item in row["variables"]])
        unique(f"model {row['model_id']} constraint_id", [item["constraint_id"] for item in row["constraints"]])
        unique(f"model {row['model_id']} validation check_id", [item["check_id"] for item in row["validation"]])
        unknown_outputs = set(row["outputs"]) - set(question_by_id[row["question_id"]]["outputs"])
        if unknown_outputs:
            errors.append(f"model {row['model_id']} outputs are not declared by its question: {sorted(unknown_outputs)}")

    frozen_results = frozen.get("results", [])
    result_ids = [row["result_id"] for row in frozen_results]
    result_set = unique("frozen_results result_id", result_ids)
    for result in frozen_results:
        if result["question_id"] not in question_set:
            errors.append(f"result {result['result_id']} references unknown question_id {result['question_id']}")
    if frozen.get("results_sha256") and frozen["results_sha256"] != sha256_json(frozen_results):
        errors.append("frozen_results.results_sha256 does not match the canonical results array")
    for field in ("source_snapshot",):
        verify_file_ref(f"frozen_results.{field}", frozen[field])
    for field in ("input_snapshot", "code_snapshot", "validation_snapshot"):
        for index, ref in enumerate(frozen[field]):
            verify_file_ref(f"frozen_results.{field}[{index}]", ref)
    if paths["frozen_results"].is_file() and registry.get("generated_from", {}).get("frozen_results_sha256"):
        actual_hash = sha256_file(paths["frozen_results"])
        if registry["generated_from"]["frozen_results_sha256"] != actual_hash:
            errors.append("evidence_registry generated_from hash does not match frozen_results file")
    generated_path = resolve_path(registry["generated_from"]["frozen_results_path"], root).resolve()
    if generated_path != paths["frozen_results"].resolve():
        errors.append("evidence_registry generated_from path is not the supplied frozen_results file")

    evidence_rows = registry.get("evidence", [])
    evidence_ids = [row["evidence_id"] for row in evidence_rows]
    evidence_set = unique("evidence_registry evidence_id", evidence_ids)
    evidence_by_id = {row["evidence_id"]: row for row in evidence_rows}
    for evidence in evidence_rows:
        for result_id in evidence["result_ids"]:
            if result_id not in result_set:
                errors.append(f"evidence {evidence['evidence_id']} references unknown result_id {result_id}")
        if evidence["type"] == "result" and not evidence["result_ids"]:
            errors.append(f"result evidence {evidence['evidence_id']} must reference at least one result_id")
        for index, ref in enumerate(evidence["artifacts"]):
            verify_file_ref(f"evidence {evidence['evidence_id']}.artifacts[{index}]", ref)

    requirement_ids = [row["requirement_id"] for row in plan["requirements"]]
    unique("paper_plan requirement_id", requirement_ids)
    claim_ids = [row["claim_id"] for row in plan["claims"]]
    claim_set = unique("paper_plan claim_id", claim_ids)
    section_ids = [row["section_id"] for row in plan["sections"]]
    section_set = unique("paper_plan section_id", section_ids)
    figure_ids = [row["figure_id"] for row in plan["figures"]]
    unique("paper_plan figure_id", figure_ids)
    table_ids = [row["table_id"] for row in plan["tables"]]
    unique("paper_plan table_id", table_ids)
    unique("paper_plan terminology canonical", [row["canonical"] for row in plan["terminology"]])

    def check_claim_refs(owner: str, row: dict[str, Any]) -> None:
        for claim_id in row.get("claim_ids", []):
            if claim_id not in claim_set:
                errors.append(f"{owner} references unknown claim_id {claim_id}")

    def check_evidence_refs(owner: str, row: dict[str, Any]) -> None:
        for evidence_id in row.get("evidence_ids", []):
            if evidence_id not in evidence_set:
                errors.append(f"{owner} references unknown evidence_id {evidence_id}")
            elif evidence_by_id[evidence_id]["verification_status"] != "verified":
                errors.append(f"{owner} references evidence {evidence_id} that is not verified")

    for requirement in plan.get("requirements", []):
        for claim_id in requirement.get("claim_ids", []):
            if claim_id not in claim_set:
                errors.append(f"requirement {requirement.get('requirement_id')} references unknown claim_id {claim_id}")
    for claim in plan.get("claims", []):
        if claim["question_id"] not in question_set:
            errors.append(f"claim {claim['claim_id']} references unknown question_id {claim['question_id']}")
        if claim["section"] not in section_set:
            errors.append(f"claim {claim['claim_id']} references unknown section {claim['section']}")
        else:
            section = next(row for row in plan["sections"] if row["section_id"] == claim["section"])
            if claim["claim_id"] not in section["claim_ids"]:
                errors.append(f"claim {claim['claim_id']} is not listed by section {claim['section']}")
        check_evidence_refs(f"claim {claim.get('claim_id')}", claim)
    for section in plan["sections"]:
        check_claim_refs(f"section {section['section_id']}", section)
    for figure in plan.get("figures", []):
        check_claim_refs(f"figure {figure.get('figure_id')}", figure)
        check_evidence_refs(f"figure {figure.get('figure_id')}", figure)
    for table in plan.get("tables", []):
        check_claim_refs(f"table {table.get('table_id')}", table)
        check_evidence_refs(f"table {table.get('table_id')}", table)
    recommendation = plan.get("canonical_recommendation") or {}
    check_evidence_refs("canonical_recommendation", recommendation)
    for result_id in plan.get("abstract_result_ids", []):
        if result_id not in result_set:
            errors.append(f"abstract_result_ids references unknown result_id {result_id}")
    if plan["status"] == "ready":
        covered_questions = {claim["question_id"] for claim in plan["claims"]}
        uncovered = sorted(question_set - covered_questions)
        if uncovered:
            errors.append(f"ready paper_plan has no claim for question(s): {uncovered}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--evidence-registry", required=True)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--schema-dir")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    schema_dir = Path(args.schema_dir).resolve() if args.schema_dir else Path(__file__).resolve().parents[2] / "schemas"
    inputs = {
        "model_contract": (resolve_path(args.model_contract, root).resolve(), schema_dir / "model_contract.schema.json"),
        "run_manifest": (resolve_path(args.run_manifest, root).resolve(), schema_dir / "run_manifest.schema.json"),
        "frozen_results": (resolve_path(args.frozen_results, root).resolve(), schema_dir / "frozen_results.schema.json"),
        "evidence_registry": (resolve_path(args.evidence_registry, root).resolve(), schema_dir / "evidence_registry.schema.json"),
        "paper_plan": (resolve_path(args.paper_plan, root).resolve(), schema_dir / "paper_plan.schema.json"),
    }
    documents: dict[str, Any] = {}
    errors: list[str] = []
    engines: set[str] = set()
    for label, (path, schema_path) in inputs.items():
        value, file_errors, engine = _validate_document(path, schema_path)
        engines.add(engine)
        if value is not None:
            documents[label] = value
        errors.extend(f"{label}: {error}" for error in file_errors)

    warnings: list[str] = []
    if len(documents) == len(inputs) and not errors:
        cross_errors, cross_warnings = _cross_references(
            documents["model_contract"],
            documents["run_manifest"],
            documents["frozen_results"],
            documents["evidence_registry"],
            documents["paper_plan"],
            root=root,
            paths={label: path for label, (path, _) in inputs.items()},
        )
        errors.extend(cross_errors)
        warnings.extend(cross_warnings)

    ok = not errors and (not args.strict or not warnings)
    report = {
        "ok": ok,
        "engine": "+".join(sorted(engines)) or "fallback",
        "files": {label: rel_path(path, root) for label, (path, _) in inputs.items()},
        "errors": errors,
        "warnings": warnings,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
