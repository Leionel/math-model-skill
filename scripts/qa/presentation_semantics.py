"""Shared, deterministic presentation checks.

These helpers extend the existing model/paper contracts.  They intentionally do
not invent a second writing database, assign a paper score, or impose quotas.
Advisory figure issues are returned as review items; only an explicit semantic
contradiction becomes a gate error when the corresponding strict option is used.
"""

from __future__ import annotations

import re
from typing import Any


ANSWER_REQUIRED_FIELDS = (
    "answer_type",
    "quantity",
    "unit",
    "scope",
    "must_satisfy",
    "reporting_semantics",
)

FACT_CHECK_FIELDS = {
    "question_id",
    "model_identity",
    "display_value",
    "unit",
    "comparison",
    "validation",
    "boundary",
}

HARD_FIGURE_CARDS = {
    "unordered_categories_connected_by_line",
    "diverging_colormap_without_semantic_center",
    "correlation_heatmap_used_as_mechanism",
    "grid_extremum_visualized_as_continuous_optimum",
}


def normalize_label(value: Any) -> str:
    """Normalize human labels without treating them as hashes or identifiers."""

    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", str(value).casefold()).strip()


def label_matches(left: Any, right: Any) -> bool:
    """Match a planned quantity to an output/result name conservatively."""

    a = normalize_label(left)
    b = normalize_label(right)
    if not a or not b:
        return False
    if a == b:
        return True
    # Allow ``optimal cost`` ↔ ``optimal_cost`` and a clearly qualified name,
    # but do not match arbitrary one-word substrings.
    return len(a.split()) >= 2 and (a in b or b in a)


def _question_rows(model_contract: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        row["question_id"]: row
        for row in model_contract.get("questions", [])
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }


def _model_rows(model_contract: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in model_contract.get("models", []) if isinstance(row, dict)]


def evaluate_required_answer_declarations(
    model_contract: dict[str, Any],
    *,
    require: bool = False,
) -> tuple[list[str], dict[str, Any]]:
    """Validate the pre-computation side of the required-answer contract."""

    errors: list[str] = []
    declared: dict[str, Any] = {}
    models = _model_rows(model_contract)
    for question_id, question in sorted(_question_rows(model_contract).items()):
        required_answer = question.get("required_answer")
        if not isinstance(required_answer, dict):
            if require:
                errors.append(f"question {question_id} requires required_answer in this profile")
            continue
        missing = [
            field
            for field in ANSWER_REQUIRED_FIELDS
            if field not in required_answer or required_answer.get(field) in (None, "", [])
        ]
        if missing:
            errors.append(f"question {question_id}.required_answer is missing {missing}")
            continue
        output_names = [*question.get("outputs", []), *required_answer.get("output_names", [])]
        output_names.extend(
            output
            for model in models
            if model.get("question_id") == question_id
            for output in model.get("outputs", [])
            if isinstance(output, str)
        )
        if not any(label_matches(required_answer["quantity"], output) for output in output_names):
            errors.append(
                f"question {question_id}.required_answer.quantity {required_answer['quantity']!r} "
                "does not bind to a declared question/model output"
            )
        declared[question_id] = {
            "answer_type": required_answer.get("answer_type"),
            "quantity": required_answer.get("quantity"),
            "unit": required_answer.get("unit"),
        }
    return errors, {"declared": declared, "required": require}


def evaluate_required_answer_coverage(
    model_contract: dict[str, Any],
    paper_plan: dict[str, Any],
    frozen_results: dict[str, Any],
    *,
    abstract_text: str | None = None,
    require: bool = False,
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    """Check question → required answer → output → frozen result → abstract.

    The contract remains optional for backward compatibility.  ``require=True``
    is reserved for a stricter profile or a deliberate release command.
    """

    errors: list[str] = []
    issues: list[dict[str, Any]] = []
    details: dict[str, Any] = {"questions": {}, "required": require}
    questions = _question_rows(model_contract)
    models = _model_rows(model_contract)
    results = [row for row in frozen_results.get("results", []) if isinstance(row, dict)]
    result_by_id = {
        row.get("result_id"): row
        for row in results
        if isinstance(row.get("result_id"), str)
    }
    abstract_rows = [row for row in paper_plan.get("abstract_results", []) if isinstance(row, dict)]
    abstract_by_result = {
        row.get("result_id"): row
        for row in abstract_rows
        if isinstance(row.get("result_id"), str)
    }

    if require and abstract_text is None:
        errors.append("required answer coverage needs the final abstract text")

    for question_id, question in sorted(questions.items()):
        required_answer = question.get("required_answer")
        q_detail: dict[str, Any] = {"status": "not_declared", "question_id": question_id}
        details["questions"][question_id] = q_detail
        if not isinstance(required_answer, dict):
            if require:
                errors.append(f"question {question_id} requires required_answer in this profile")
            continue

        missing = [
            field
            for field in ANSWER_REQUIRED_FIELDS
            if field not in required_answer
            or required_answer.get(field) in (None, "", [])
        ]
        if missing:
            errors.append(f"question {question_id}.required_answer is missing {missing}")
            q_detail["status"] = "invalid"
            continue

        quantity = required_answer["quantity"]
        q_output_names = [*question.get("outputs", []), *required_answer.get("output_names", [])]
        q_models = [row for row in models if row.get("question_id") == question_id]
        model_output_names = [
            output
            for row in q_models
            for output in row.get("outputs", [])
            if isinstance(output, str)
        ]
        output_names = q_output_names + model_output_names
        output_match = any(label_matches(quantity, name) for name in output_names)
        if not output_match:
            errors.append(
                f"question {question_id}.required_answer.quantity {quantity!r} does not bind to a question/model output"
            )

        matching_results = [
            row
            for row in results
            if row.get("question_id") == question_id
            and (
                label_matches(quantity, row.get("name"))
                or any(label_matches(name, row.get("name")) for name in required_answer.get("output_names", []))
            )
        ]
        if not matching_results:
            errors.append(
                f"question {question_id}.required_answer.quantity {quantity!r} has no matching frozen result"
            )
        for result in matching_results:
            result_id = result.get("result_id")
            result_unit = normalize_label(result.get("unit"))
            required_unit = normalize_label(required_answer.get("unit"))
            if required_unit and required_unit != result_unit:
                errors.append(
                    f"required answer {question_id} unit {required_answer.get('unit')!r} "
                    f"does not match frozen result {result_id} unit {result.get('unit')!r}"
                )
            abstract_row = abstract_by_result.get(result_id)
            if abstract_row is None:
                errors.append(
                    f"required answer {question_id} result {result_id} is not selected in paper_plan.abstract_results"
                )
                continue
            row_question = abstract_row.get("question_id")
            if row_question is not None and row_question != question_id:
                errors.append(
                    f"abstract result {result_id} is assigned to {row_question}, not {question_id}"
                )
            for model_id in abstract_row.get("method_ids", []):
                if not any(row.get("model_id") == model_id and row.get("question_id") == question_id for row in q_models):
                    errors.append(
                        f"abstract result {result_id} method_id {model_id!r} is not a model for {question_id}"
                    )
            if abstract_text is not None:
                display = str(result.get("display_value", ""))
                if display and display not in abstract_text:
                    errors.append(
                        f"abstract answer for {question_id} is missing frozen display_value {display!r}"
                    )
                span = abstract_row.get("abstract_span")
                if span and span not in abstract_text:
                    errors.append(f"abstract_span for result {result_id} is not present in the abstract")
            fact_check = abstract_row.get("fact_check")
            if require:
                if not isinstance(fact_check, dict) or fact_check.get("status") != "passed":
                    errors.append(f"abstract result {result_id} has no passed fact_check")
                else:
                    checked = set(fact_check.get("checked_fields", []))
                    required_fields = {"question_id", "model_identity", "display_value", "unit", "boundary"}
                    if not required_fields.issubset(checked):
                        errors.append(
                            f"abstract result {result_id} fact_check must cover {sorted(required_fields)}"
                        )
                    if result_id not in set(fact_check.get("source_ids", [])):
                        errors.append(f"abstract result {result_id} fact_check must cite its frozen result source")

        q_detail.update({
            "status": "checked" if matching_results else "missing_result",
            "quantity": quantity,
            "matched_result_ids": [row.get("result_id") for row in matching_results],
            "output_match": output_match,
        })

    return errors, issues, details


def evaluate_terminology_consistency(
    model_contract: dict[str, Any] | None,
    paper_plan: dict[str, Any],
    texts: dict[str, str] | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Check semantic metadata without creating a second glossary."""

    errors: list[str] = []
    model_terms = [row for row in (model_contract or {}).get("terminology", []) if isinstance(row, dict)]
    plan_terms = [row for row in paper_plan.get("terminology", []) if isinstance(row, dict)]
    by_semantic: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, str] = {}
    for source, rows in (("model_contract", model_terms), ("paper_plan", plan_terms)):
        for term in rows:
            semantic_id = term.get("semantic_id")
            if isinstance(semantic_id, str):
                prior = by_semantic.get(semantic_id)
                if prior:
                    for field in ("canonical_zh", "canonical_en", "symbol", "unit"):
                        if term.get(field) and prior.get(field) and term.get(field) != prior.get(field):
                            errors.append(
                                f"semantic term {semantic_id} has conflicting {field}: "
                                f"{prior.get(field)!r} vs {term.get(field)!r} ({source})"
                            )
                else:
                    by_semantic[semantic_id] = term
            symbol = term.get("symbol")
            if isinstance(symbol, str) and isinstance(semantic_id, str):
                prior_id = by_symbol.get(symbol)
                if prior_id and prior_id != semantic_id:
                    errors.append(f"symbol {symbol!r} is assigned to semantic_ids {prior_id!r} and {semantic_id!r}")
                by_symbol[symbol] = semantic_id

    for label, text in (texts or {}).items():
        for term in [*model_terms, *plan_terms]:
            canonical = term.get("canonical") or term.get("canonical_zh") or term.get("canonical_en")
            for variant in term.get("forbidden_variants", []):
                if isinstance(variant, str) and variant and variant.casefold() in text.casefold():
                    errors.append(
                        f"{label} contains forbidden terminology variant {variant!r}; "
                        f"use {canonical!r}"
                    )
    return errors, {"semantic_terms": len(by_semantic), "symbols": len(by_symbol)}


def _selected_display(figure: dict[str, Any]) -> tuple[str, str]:
    selected = figure.get("selected_display")
    candidates = {
        row.get("display_id"): row
        for row in figure.get("candidate_displays", [])
        if isinstance(row, dict) and isinstance(row.get("display_id"), str)
    }
    if isinstance(selected, str) and selected in candidates:
        return selected, str(candidates[selected].get("display_type", ""))
    if isinstance(selected, str):
        return selected, selected
    return "", str(figure.get("visual_encoding", ""))


def _has_token(value: Any, *tokens: str) -> bool:
    text = normalize_label(value)
    return any(normalize_label(token) in text for token in tokens)


def evaluate_figure_semantics(
    paper_plan: dict[str, Any],
    *,
    require: bool = False,
) -> tuple[list[str], list[dict[str, Any]], dict[str, Any]]:
    """Apply a small set of claim-first figure semantic failure cards."""

    errors: list[str] = []
    issues: list[dict[str, Any]] = []
    details: dict[str, Any] = {"figures": {}}
    required_fields = ("data_shape", "argument_intent", "sample_regime", "uncertainty_semantics")
    for figure in paper_plan.get("figures", []):
        if not isinstance(figure, dict):
            continue
        figure_id = str(figure.get("figure_id", "figure"))
        selected_id, display_type = _selected_display(figure)
        shape = figure.get("data_shape")
        intent = figure.get("argument_intent")
        regime = figure.get("sample_regime") if isinstance(figure.get("sample_regime"), dict) else {}
        figure_issues: list[dict[str, Any]] = []

        if require and figure.get("kind") == "data":
            for field in required_fields:
                if field not in figure:
                    errors.append(f"data figure {figure_id} requires figure semantic field {field}")
            if figure.get("candidate_displays") and not selected_id:
                errors.append(f"figure {figure_id} declares candidate_displays but no selected_display")
            if figure.get("candidate_displays") and not figure.get("selection_reason"):
                errors.append(f"figure {figure_id} declares candidate_displays but no selection_reason")
            final_size = figure.get("final_size_qa")
            if not isinstance(final_size, dict) or final_size.get("status") != "reviewed":
                errors.append(f"figure {figure_id} requires reviewed final_size_qa in this profile")

        def add(card: str, severity: str, message: str) -> None:
            row = {"figure_id": figure_id, "card": card, "severity": severity, "message": message}
            figure_issues.append(row)
            if severity == "error":
                errors.append(message)
            else:
                issues.append(row)

        display = normalize_label(display_type)
        n_total = regime.get("n_total")
        per_group = [value for value in regime.get("n_per_group", {}).values() if isinstance(value, int)]
        min_group = min(per_group) if per_group else None

        if shape == "unordered_categories" and _has_token(display, "line", "connected"):
            add("unordered_categories_connected_by_line", "error", f"figure {figure_id} connects unordered categories with a line")
        if shape in {"distribution", "grouped_distribution"} and (
            (isinstance(n_total, int) and n_total < 15) or (isinstance(min_group, int) and min_group < 10)
        ):
            if _has_token(display, "kde", "violin", "box", "density", "distribution"):
                add("small_sample_distribution_overclaim", "advisory", f"figure {figure_id} uses a distribution display in a small-sample regime; show raw observations and qualify the claim")
        if shape == "grouped_distribution" and _has_token(display, "bar", "mean"):
            if isinstance(min_group, int) and min_group < 10:
                add("mean_bar_hides_distribution", "error", f"figure {figure_id} uses a mean/bar display that hides a small-group distribution")
            else:
                add("mean_bar_hides_distribution", "advisory", f"figure {figure_id} should expose the underlying distribution rather than relying on a mean bar")
        if shape == "diverging_matrix" and _has_token(display, "heatmap", "colormap", "color") and figure.get("color_semantic_center") in (None, ""):
            add("diverging_colormap_without_semantic_center", "error", f"figure {figure_id} uses a diverging color map without declaring its semantic center")
        if shape == "correlation_matrix" and (intent == "mechanism" or _has_token(figure.get("message"), "causal", "mechanism")):
            add("correlation_heatmap_used_as_mechanism", "error", f"figure {figure_id} uses a correlation heatmap to support a mechanism/causal claim")
        if not intent or not str(figure.get("message", "")).strip():
            add("figure_has_no_primary_argument", "error" if require else "advisory", f"figure {figure_id} has no explicit primary argument")
        if shape == "grid_search" and regime.get("grid_is_discrete") is True and intent == "optimization_landscape":
            if _has_token(display, "surface", "continuous", "smooth", "line", "contour"):
                add("grid_extremum_visualized_as_continuous_optimum", "error", f"figure {figure_id} visualizes a discrete grid extremum as a continuous optimum")

        final_size = figure.get("final_size_qa")
        if isinstance(final_size, dict):
            if final_size.get("raster_dpi", 0) < 300:
                add("final_size_raster_resolution", "error", f"figure {figure_id} declares raster_dpi below 300")
            if final_size.get("readability") == "fail" or final_size.get("cropping") == "fail":
                add("final_size_readability", "error", f"figure {figure_id} final-size QA reports unreadable text or cropping")

        details["figures"][figure_id] = {
            "selected_display": selected_id or None,
            "display_type": display_type,
            "data_shape": shape,
            "argument_intent": intent,
            "issues": figure_issues,
        }

    return errors, issues, details
