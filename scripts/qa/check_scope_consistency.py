#!/usr/bin/env python3
"""Check question-scoped parameters, events, model bindings, and paper text.

The scope contract is intentionally an optional extension of model_contract
1.3.  Existing development runs remain valid until they opt into the
contract; a formal profile can pass ``--require-scope-contract`` to make the
absence of that contract a hard failure.  No file hash is required here:
local consistency is checked from the current contract and text, while
submission integrity remains the responsibility of the submission gate.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


MODEL_SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "model_contract.schema.json"


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _contains(text: str, token: str) -> bool:
    return _normalise(token) in _normalise(text)


def _unique_strings(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []
    return [value for value in values if isinstance(value, str) and value.strip()]


def _find_marker(text: str, markers: list[str]) -> tuple[int, str] | None:
    folded = text.casefold()
    hits = [
        (folded.find(marker.casefold()), marker)
        for marker in markers
        if marker and folded.find(marker.casefold()) >= 0
    ]
    return min(hits, key=lambda item: item[0]) if hits else None


def _section_spans(text: str, definitions: list[tuple[str, dict[str, Any]]]) -> tuple[dict[str, str], list[str]]:
    """Return marker-delimited text sections and report ambiguous markers."""

    errors: list[str] = []
    starts: list[tuple[int, str, str]] = []
    owners_by_marker: dict[str, set[str]] = {}
    for owner_id, definition in definitions:
        markers = _unique_strings(definition.get("paper_section_markers"))
        marker_hit = _find_marker(text, markers)
        if marker_hit is None:
            errors.append(f"{owner_id} has no matching paper_section_markers")
            continue
        position, marker = marker_hit
        marker_key = _normalise(marker)
        owners_by_marker.setdefault(marker_key, set()).add(owner_id)
        starts.append((position, owner_id, marker))

    for marker, owners in owners_by_marker.items():
        if len(owners) > 1:
            errors.append(f"paper section marker {marker!r} is assigned to multiple definitions: {sorted(owners)}")

    starts.sort(key=lambda item: (item[0], -len(item[2])))
    spans: dict[str, str] = {}
    for index, (_, owner_id, _) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(text)
        spans[owner_id] = text[starts[index][0]:end]
    return spans, errors


def _check_text_tokens(
    owner_id: str,
    definition: dict[str, Any],
    section: str,
    errors: list[str],
) -> dict[str, int]:
    required = _unique_strings(definition.get("required_tokens"))
    forbidden = _unique_strings(definition.get("forbidden_tokens"))
    for token in required:
        if not _contains(section, token):
            errors.append(f"{owner_id} paper section is missing required token {token!r}")
    for token in forbidden:
        if _contains(section, token):
            errors.append(f"{owner_id} paper section contains forbidden token {token!r}")
    return {"required_tokens": len(required), "forbidden_tokens": len(forbidden)}


def evaluate_scope_consistency(
    model_contract: dict[str, Any],
    paper_text: str | None = None,
    *,
    require_contract: bool = False,
) -> tuple[list[str], list[str], dict[str, Any]]:
    """Return errors, warnings, and coverage for the optional scope contract."""

    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {"status": "NOT_DECLARED", "paper_check": "not_run"}
    raw_contract = model_contract.get("scope_contract")
    if raw_contract is None:
        if require_contract:
            errors.append("model_contract.scope_contract is required for this profile")
            details["status"] = "MISSING_REQUIRED"
        else:
            details["status"] = "NOT_DECLARED"
        return errors, warnings, details
    if not isinstance(raw_contract, dict):
        errors.append("model_contract.scope_contract must be an object")
        details["status"] = "INVALID"
        return errors, warnings, details

    status = raw_contract.get("status")
    details["status"] = status
    if status == "superseded":
        errors.append("model_contract.scope_contract.status must not be superseded")
    elif status != "ready":
        message = "model_contract.scope_contract.status must be ready before consistency can be promoted"
        if require_contract:
            errors.append(message)
        else:
            warnings.append(message)

    questions = {
        row.get("question_id")
        for row in model_contract.get("questions", [])
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }
    scopes = [row for row in raw_contract.get("scopes", []) if isinstance(row, dict)]
    events = [row for row in raw_contract.get("events", []) if isinstance(row, dict)]
    scope_by_id: dict[str, dict[str, Any]] = {}
    event_by_id: dict[str, dict[str, Any]] = {}
    for scope in scopes:
        scope_id = scope.get("scope_id")
        if not isinstance(scope_id, str):
            continue
        if scope_id in scope_by_id:
            errors.append(f"scope_contract.scopes contains duplicate scope_id {scope_id}")
        scope_by_id[scope_id] = scope
        question_id = scope.get("question_id")
        if question_id not in questions:
            errors.append(f"scope {scope_id} references unknown question_id {question_id}")
        parameter_ids: set[str] = set()
        symbols: set[str] = set()
        for parameter in scope.get("parameters", []):
            if not isinstance(parameter, dict):
                continue
            parameter_id = parameter.get("parameter_id")
            symbol = parameter.get("symbol")
            if isinstance(parameter_id, str):
                if parameter_id in parameter_ids:
                    errors.append(f"scope {scope_id} contains duplicate parameter_id {parameter_id}")
                parameter_ids.add(parameter_id)
            if isinstance(symbol, str):
                if symbol in symbols:
                    errors.append(f"scope {scope_id} contains duplicate parameter symbol {symbol}")
                symbols.add(symbol)
    for event in events:
        event_id = event.get("event_id")
        if not isinstance(event_id, str):
            continue
        if event_id in event_by_id:
            errors.append(f"scope_contract.events contains duplicate event_id {event_id}")
        event_by_id[event_id] = event
        if event.get("question_id") not in questions:
            errors.append(f"event {event_id} references unknown question_id {event.get('question_id')}")

    for scope_id, scope in scope_by_id.items():
        scope_question = scope.get("question_id")
        for event_id in _unique_strings(scope.get("event_ids")):
            event = event_by_id.get(event_id)
            if event is None:
                errors.append(f"scope {scope_id} references unknown event_id {event_id}")
            elif event.get("question_id") != scope_question:
                errors.append(
                    f"scope {scope_id} event {event_id} belongs to {event.get('question_id')}, "
                    f"not {scope_question}"
                )

    models = [row for row in model_contract.get("models", []) if isinstance(row, dict)]
    referenced_scope_ids: set[str] = set()
    for model in models:
        model_id = model.get("model_id", "<unknown>")
        model_question = model.get("question_id")
        scope_ids = _unique_strings(model.get("scope_ids"))
        event_ids = _unique_strings(model.get("event_ids"))
        if status == "ready" and not scope_ids:
            errors.append(f"model {model_id} must declare scope_ids when scope_contract is ready")
        for scope_id in scope_ids:
            referenced_scope_ids.add(scope_id)
            scope = scope_by_id.get(scope_id)
            if scope is None:
                errors.append(f"model {model_id} references unknown scope_id {scope_id}")
            elif scope.get("question_id") != model_question:
                errors.append(
                    f"model {model_id} binds scope {scope_id} for {scope.get('question_id')}, "
                    f"but model question_id is {model_question}"
                )
        for event_id in event_ids:
            event = event_by_id.get(event_id)
            if event is None:
                errors.append(f"model {model_id} references unknown event_id {event_id}")
            elif event.get("question_id") != model_question:
                errors.append(
                    f"model {model_id} binds event {event_id} for {event.get('question_id')}, "
                    f"but model question_id is {model_question}"
                )

    if status == "ready":
        for scope_id in scope_by_id:
            if scope_id not in referenced_scope_ids:
                errors.append(f"ready scope {scope_id} is not bound to any model")

    text_details: dict[str, Any] = {"status": "not_run"}
    if paper_text is not None:
        scope_definitions = [(scope_id, scope) for scope_id, scope in scope_by_id.items()]
        event_definitions = [(event_id, event) for event_id, event in event_by_id.items()]
        scope_spans, scope_span_errors = _section_spans(paper_text, scope_definitions)
        event_spans, event_span_errors = _section_spans(paper_text, event_definitions)
        errors.extend(scope_span_errors)
        errors.extend(event_span_errors)
        token_counts: dict[str, dict[str, int]] = {}
        for scope_id, scope in scope_by_id.items():
            section = scope_spans.get(scope_id)
            if section is None:
                continue
            counts = _check_text_tokens(scope_id, scope, section, errors)
            for parameter in scope.get("parameters", []):
                if not isinstance(parameter, dict):
                    continue
                parameter_id = parameter.get("parameter_id", "<unknown>")
                counts_for_parameter = _check_text_tokens(
                    f"scope {scope_id} parameter {parameter_id}", parameter, section, errors
                )
                for key, value in counts_for_parameter.items():
                    counts[key] = counts.get(key, 0) + value
            token_counts[scope_id] = counts
        for event_id, event in event_by_id.items():
            section = event_spans.get(event_id)
            if section is not None:
                token_counts[event_id] = _check_text_tokens(event_id, event, section, errors)
        text_details = {
            "status": "checked",
            "scopes_found": len(scope_spans),
            "events_found": len(event_spans),
            "token_counts": token_counts,
        }

    details.update({
        "scope_count": len(scope_by_id),
        "event_count": len(event_by_id),
        "bound_scope_count": len(referenced_scope_ids),
        "paper_check": text_details,
    })
    return errors, warnings, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--paper")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument(
        "--require-scope-contract",
        action="store_true",
        help="Fail when model_contract has no ready scope_contract.",
    )
    parser.add_argument(
        "--skip-if-absent",
        action="store_true",
        help="Treat an absent optional scope_contract as not_applicable.",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    model_path = resolve_path(args.model_contract, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        model, schema_errors, _ = _validate_document(model_path, MODEL_SCHEMA)
        errors.extend(f"model_contract schema: {message}" for message in schema_errors)
        if not isinstance(model, dict):
            raise ValueError("model_contract must be an object")
        if model.get("scope_contract") is None and args.skip_if_absent and not args.require_scope_contract:
            details = {"status": "NOT_APPLICABLE", "paper_check": "not_run"}
        else:
            paper_text = None
            if args.paper:
                paper_path = resolve_path(args.paper, root).resolve()
                paper_text = paper_path.read_text(encoding="utf-8")
            scope_errors, scope_warnings, details = evaluate_scope_consistency(
                model,
                paper_text,
                require_contract=args.require_scope_contract,
            )
            errors.extend(scope_errors)
            warnings.extend(scope_warnings)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "model_contract": rel_path(model_path, root),
        "paper": rel_path(resolve_path(args.paper, root).resolve(), root) if args.paper else None,
        "details": details,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
