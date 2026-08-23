"""Route a figure brief to its evidence-appropriate production tool."""

from __future__ import annotations

from typing import Any


from .pptx_router import select_pptx_reference

DATA_TYPES = {"trend", "comparison", "distribution", "sensitivity", "heatmap", "residual", "pareto", "map"}
DIAGRAM_TYPES = {"workflow", "research framework", "model architecture", "algorithm pipeline", "optimization loop", "decision process", "methodology overview", "data flow", "model structure"}
ILLUSTRATION_TYPES = {"physical mechanism", "system concept", "scenario illustration", "energy flow concept"}


def route_figure(
    kind: str = "auto",
    semantic_type: str | None = None,
    fallback_reason: str | None = None,
    diagram_backend: str = "auto",
    pptx_reference: str | None = None,
) -> dict[str, Any]:
    """Choose Python, PPTX, Draw.io, or illustration without drawing the figure."""

    normalized_kind = kind.casefold().strip()
    semantic = (semantic_type or "").casefold().strip()
    if normalized_kind == "auto":
        if semantic in DATA_TYPES:
            normalized_kind = "data"
        elif semantic in ILLUSTRATION_TYPES:
            normalized_kind = "illustration"
        else:
            normalized_kind = "diagram"
    if normalized_kind == "data":
        return {
            "kind": "data",
            "machine_kind": "data",
            "default_tool": "python_plotting",
            "required_outputs": ["source data or frozen result", "deterministic plotting script", "figure export"],
            "rule": "Use deterministic plotting for numeric data and result figures.",
        }
    if normalized_kind == "illustration":
        return {
            "kind": "illustration",
            "machine_kind": "illustration",
            "default_tool": "image_generation",
            "required_outputs": ["prompt record", "visual review", "high-DPI preview"],
            "rule": "Illustrations cannot carry quantitative claims; retain an editable source if a formal diagram is required.",
        }
    if normalized_kind == "diagram":
        backend = diagram_backend.casefold().strip()
        if backend == "auto":
            backend = "pptx"
        if backend == "pptx":
            reference = select_pptx_reference(semantic_type, reference_id=pptx_reference)
            return {
                "kind": "diagram",
                "machine_kind": "concept",
                "default_tool": "pptx_template",
                "reference": reference,
                "required_outputs": ["brief.md", "editable .pptx copy", "PPTX export (PDF/SVG/PNG)", "final-size review"],
                "rule": "Use an inspected PPTX reference and edit a copied source deck; Draw.io remains an explicit fallback when its native XML contract is needed.",
            }
        if backend == "drawio":
            route = {
                "kind": "diagram",
                "machine_kind": "concept",
                "default_tool": "drawio",
                "selection": "explicit_drawio",
                "required_outputs": ["brief.md", "editable .drawio source", "SVG or PDF", "preview PNG", "final-size review"],
                "rule": "Do not default to matplotlib rectangles, networkx, PIL, or manually positioned Python boxes for a formal diagram.",
            }
            if fallback_reason:
                route["fallback"] = {"used": True, "reason": fallback_reason}
            return route
        raise ValueError("diagram backend must be auto, pptx, or drawio")
    raise ValueError("figure kind must be auto, data, diagram, or illustration")
