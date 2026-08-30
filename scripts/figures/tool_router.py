"""Route a figure brief to its evidence-appropriate production tool."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from precedents.select_reference_cards import select_cards

from .pptx_router import (
    analyze_pptx_references,
    normalize_label,
    normalize_topology,
    select_pptx_reference,
)

DATA_TYPES = frozenset({
    "trend",
    "comparison",
    "result comparison",
    "bar comparison",
    "line comparison",
    "distribution",
    "data distribution",
    "sensitivity",
    "sensitivity curve",
    "tornado",
    "heatmap",
    "residual",
    "pareto",
    "map",
    "validation",
    "diagnostic",
    "validation curve",
    "calibration",
    "interval comparison",
    "scenario envelope",
    "dumbbell",
    "slope",
    "small multiples",
    "violin",
    "box",
    "beeswarm",
    "strip",
})
DIAGRAM_TYPES = frozenset({
    "workflow",
    "research framework",
    "model architecture",
    "algorithm pipeline",
    "optimization loop",
    "decision process",
    "methodology overview",
    "data flow",
    "model structure",
    "validation flow",
    "multi question overview",
    "three phase overview",
    "model flow",
    "optimization structure",
    "pipeline",
    "data overview",
    "decision boundary",
})
ILLUSTRATION_TYPES = frozenset({
    "physical mechanism",
    "system concept",
    "scenario illustration",
    "energy flow concept",
})


def classify_figure_semantic(semantic_type: str | None) -> str | None:
    """Classify a known semantic label without guessing an unknown figure family."""

    semantic = normalize_label(semantic_type)
    if semantic in DATA_TYPES:
        return "data"
    if semantic in DIAGRAM_TYPES:
        return "diagram"
    if semantic in ILLUSTRATION_TYPES:
        return "illustration"
    return None


def _unresolved_route(semantic_type: str | None) -> dict[str, Any]:
    return {
        "kind": "unresolved_figure_type",
        "machine_kind": "unresolved_figure_type",
        "default_tool": None,
        "semantic_type": normalize_label(semantic_type) or None,
        "selection": "human_or_agent_resolution_required",
        "message": "cannot confidently classify figure",
        "suggested_candidates": ["data", "diagram", "illustration"],
        "required_outputs": ["explicit figure kind decision before production routing"],
        "rule": "Unknown semantic types must not silently enter a PPTX, Draw.io, plotting, or illustration route.",
    }


def select_diagram_backend(
    semantic_type: str | None,
    *,
    topology: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Select a concept backend from the declared topology, not a permanent default."""

    normalized = normalize_topology(topology)
    reasons: list[str] = []
    if normalized["native_topology_qa"]:
        return {
            "backend": "drawio",
            "selection": "native_topology_qa",
            "reasons": ["native topology QA requires an editable XML graph"],
            "topology": normalized,
        }
    if normalized["feedback_edges"] is not None and normalized["feedback_edges"] > 0:
        return {
            "backend": "drawio",
            "selection": "feedback_sensitive_topology",
            "reasons": [f"feedback_edges={normalized['feedback_edges']} requires topology-safe connectors"],
            "topology": normalized,
        }

    complexity_signals: list[str] = []
    if normalized["node_count"] is not None and normalized["node_count"] >= 12:
        complexity_signals.append(f"node_count={normalized['node_count']}")
    if normalized["dag_depth"] is not None and normalized["dag_depth"] >= 5:
        complexity_signals.append(f"dag_depth={normalized['dag_depth']}")
    if normalized["branch_count"] is not None and normalized["branch_count"] >= 3:
        complexity_signals.append(f"branch_count={normalized['branch_count']}")
    if normalized["parallel_lanes"] is not None and normalized["parallel_lanes"] >= 3:
        complexity_signals.append(f"parallel_lanes={normalized['parallel_lanes']}")
    if normalized["density"] == "high":
        complexity_signals.append("density=high")
    if len(complexity_signals) >= 2:
        return {
            "backend": "drawio",
            "selection": "complex_dag",
            "reasons": ["multiple complex topology signals: " + ", ".join(complexity_signals)],
            "topology": normalized,
        }

    if complexity_signals:
        reasons.append("one complexity signal is present but does not require native topology QA")
    else:
        reasons.append("brief is simple or conventional enough for an inspected PPTX composition")
    if normalize_label(semantic_type):
        reasons.append(f"semantic type '{normalize_label(semantic_type)}' is retained for reference matching")
    return {
        "backend": "pptx",
        "selection": "reference_guided_pptx",
        "reasons": reasons,
        "topology": normalized,
    }


def _reference_candidates(
    semantic_type: str | None,
    topology: Mapping[str, object] | None,
    reference_id: str | None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    analysis = analyze_pptx_references(semantic_type, topology=topology)
    candidates = list(analysis["candidates"])
    if reference_id is None:
        return candidates, list(analysis["rejected"])

    selected = select_pptx_reference(semantic_type, reference_id=reference_id, topology=topology)
    explicit = {
        "reference_id": selected["reference_id"],
        "source_pptx": selected["source_pptx"],
        "source_slide": selected["source_slide"],
        "description": selected["description"],
        "score": None,
        "reasons": ["explicit PPTX reference selected by the caller"],
        "fit": "candidate",
        "rejection_reasons": [],
    }
    return [explicit, *[row for row in candidates if row["reference_id"] != reference_id]][:3], list(analysis["rejected"])


def route_figure(
    kind: str = "auto",
    semantic_type: str | None = None,
    fallback_reason: str | None = None,
    diagram_backend: str = "auto",
    pptx_reference: str | None = None,
    topology: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Choose Python, a topology-matched concept backend, or illustration without drawing."""

    normalized_kind = normalize_label(kind)
    if normalized_kind not in {"auto", "data", "diagram", "illustration"}:
        raise ValueError("figure kind must be auto, data, diagram, or illustration")
    if normalized_kind == "auto":
        classified = classify_figure_semantic(semantic_type)
        if classified is None:
            return _unresolved_route(semantic_type)
        normalized_kind = classified

    if normalized_kind == "data":
        figure_cards = select_cards(card_kind="figure", semantic_type=semantic_type, limit=3)["selected"]
        return {
            "kind": "data",
            "machine_kind": "data",
            "default_tool": "python_plotting",
            "figure_reference_cards": figure_cards,
            "required_outputs": ["source data or frozen result", "deterministic plotting script", "figure export"],
            "rule": "Use deterministic plotting for numeric data and result figures.",
        }
    if normalized_kind == "illustration":
        figure_cards = select_cards(card_kind="figure", semantic_type=semantic_type, limit=3)["selected"]
        return {
            "kind": "illustration",
            "machine_kind": "illustration",
            "default_tool": "image_generation",
            "figure_reference_cards": figure_cards,
            "required_outputs": ["prompt record", "visual review", "high-DPI preview"],
            "rule": "Illustrations cannot carry quantitative claims; retain an editable source if a formal diagram is required.",
        }

    requested_backend = normalize_label(diagram_backend)
    if requested_backend not in {"auto", "pptx", "drawio"}:
        raise ValueError("diagram backend must be auto, pptx, or drawio")
    backend_selection = select_diagram_backend(semantic_type, topology=topology)
    if requested_backend == "pptx":
        backend_selection = {
            "backend": "pptx",
            "selection": "explicit_pptx",
            "reasons": ["PPTX backend explicitly selected by the caller."],
            "topology": normalize_topology(topology),
        }
    elif requested_backend == "drawio":
        backend_selection = {
            "backend": "drawio",
            "selection": "explicit_drawio",
            "reasons": ["Draw.io backend explicitly selected by the caller."],
            "topology": normalize_topology(topology),
        }

    candidates, rejected = _reference_candidates(semantic_type, topology, pptx_reference)
    figure_cards = select_cards(card_kind="figure", semantic_type=semantic_type, limit=3)["selected"]
    if backend_selection["backend"] == "pptx":
        reference = select_pptx_reference(
            semantic_type,
            reference_id=pptx_reference,
            topology=topology,
        )
        route = {
            "kind": "diagram",
            "machine_kind": "concept",
            "default_tool": "pptx_template",
            "backend_selection": backend_selection,
            "reference": reference,
            "reference_candidates": candidates,
            "figure_reference_cards": figure_cards,
            "required_outputs": ["brief.md", "editable .pptx copy", "PPTX export (PDF/SVG/PNG)", "final-size review"],
            "rule": "Use an inspected PPTX reference for simple or conventional composition; topology-sensitive briefs route to Draw.io.",
        }
    else:
        route = {
            "kind": "diagram",
            "machine_kind": "concept",
            "default_tool": "drawio",
            "selection": backend_selection["selection"],
            "backend_selection": backend_selection,
            "reference_candidates": candidates,
            "figure_reference_cards": figure_cards,
            "required_outputs": ["brief.md", "editable .drawio source", "SVG or PDF", "preview PNG", "final-size review"],
            "rule": "Use Draw.io for complex DAGs, feedback, or native topology QA; do not replace it with manually positioned Python boxes.",
        }
        if fallback_reason:
            route["fallback"] = {"used": True, "reason": fallback_reason}
    if rejected:
        route["reference_rejections"] = rejected
    return route
