#!/usr/bin/env python3
"""Generate a polished, editable draw.io XML diagram from diagram_spec.json."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, resolve_path  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "diagram_spec.schema.json"


PALETTES: dict[str, dict[str, str]] = {
    "academic_minimal": {
        "ink": "#243447",
        "muted": "#667085",
        "line": "#7B8794",
        "panel_fill": "#F7F9FC",
        "panel_stroke": "#CBD5E1",
        "input_fill": "#EAF2F8",
        "input_stroke": "#326B9E",
        "task_fill": "#FFFFFF",
        "task_stroke": "#52677D",
        "model_fill": "#E8F4F1",
        "model_stroke": "#2A8176",
        "validation_fill": "#FFF6DF",
        "validation_stroke": "#B07A18",
        "decision_fill": "#F8F0FB",
        "decision_stroke": "#8A5A9D",
        "result_fill": "#EAF6EA",
        "result_stroke": "#3D8550",
        "annotation_fill": "#F3F4F6",
        "annotation_stroke": "#98A2B3",
    },
    "academic_navy_teal": {
        "ink": "#18324B",
        "muted": "#617487",
        "line": "#6D8295",
        "panel_fill": "#F5F8FB",
        "panel_stroke": "#B8C7D4",
        "input_fill": "#E6F0F8",
        "input_stroke": "#28618D",
        "task_fill": "#FFFFFF",
        "task_stroke": "#4A647A",
        "model_fill": "#E4F3F0",
        "model_stroke": "#18766D",
        "validation_fill": "#FFF4D6",
        "validation_stroke": "#A86D08",
        "decision_fill": "#F4ECF8",
        "decision_stroke": "#7A4C8E",
        "result_fill": "#E8F5E9",
        "result_stroke": "#327A45",
        "annotation_fill": "#F1F4F6",
        "annotation_stroke": "#8C9AA7",
    },
    "okabe_ito": {
        "ink": "#333333",
        "muted": "#666666",
        "line": "#4D4D4D",
        "panel_fill": "#F7F7F7",
        "panel_stroke": "#BDBDBD",
        "input_fill": "#E6F0F7",
        "input_stroke": "#0072B2",
        "task_fill": "#FFFFFF",
        "task_stroke": "#666666",
        "model_fill": "#E4F3EE",
        "model_stroke": "#009E73",
        "validation_fill": "#FFF3D6",
        "validation_stroke": "#E69F00",
        "decision_fill": "#F5E7F0",
        "decision_stroke": "#CC79A7",
        "result_fill": "#E4F3EE",
        "result_stroke": "#009E73",
        "annotation_fill": "#F2F2F2",
        "annotation_stroke": "#999999",
    },
    "forest_gold": {
        "ink": "#243226",
        "muted": "#68756A",
        "line": "#6E776F",
        "panel_fill": "#FAF9F2",
        "panel_stroke": "#C9CCB9",
        "input_fill": "#EEF4F0",
        "input_stroke": "#4D8061",
        "task_fill": "#FFFFFF",
        "task_stroke": "#6F786F",
        "model_fill": "#E5F0E5",
        "model_stroke": "#2E7D32",
        "validation_fill": "#FFF5D9",
        "validation_stroke": "#B58900",
        "decision_fill": "#F4EFE3",
        "decision_stroke": "#8A6D3B",
        "result_fill": "#E8F4E8",
        "result_stroke": "#2E7D32",
        "annotation_fill": "#F3F5F1",
        "annotation_stroke": "#9AA69C",
    },
    "slate_violet": {
        "ink": "#263238",
        "muted": "#667085",
        "line": "#718096",
        "panel_fill": "#F8F8FC",
        "panel_stroke": "#D0D2E0",
        "input_fill": "#EDF0FC",
        "input_stroke": "#3F51B5",
        "task_fill": "#FFFFFF",
        "task_stroke": "#697586",
        "model_fill": "#F0EAF8",
        "model_stroke": "#7E57C2",
        "validation_fill": "#EAF7F4",
        "validation_stroke": "#268D80",
        "decision_fill": "#F3EBF8",
        "decision_stroke": "#7E57C2",
        "result_fill": "#EAF7F4",
        "result_stroke": "#268D80",
        "annotation_fill": "#F2F3F5",
        "annotation_stroke": "#98A2B3",
    },
    "navy_coral": {
        "ink": "#203247",
        "muted": "#6B7785",
        "line": "#718096",
        "panel_fill": "#FBF9F5",
        "panel_stroke": "#D6C9B9",
        "input_fill": "#EAF1F7",
        "input_stroke": "#1A3A5C",
        "task_fill": "#FFFFFF",
        "task_stroke": "#6C7885",
        "model_fill": "#FBECE8",
        "model_stroke": "#C95D4A",
        "validation_fill": "#FBF1D9",
        "validation_stroke": "#B38336",
        "decision_fill": "#F3EAF0",
        "decision_stroke": "#9B5A7A",
        "result_fill": "#EAF4EC",
        "result_stroke": "#3C8150",
        "annotation_fill": "#F4F5F6",
        "annotation_stroke": "#9BA5AF",
    },
    "minimal_gray_blue": {
        "ink": "#263238",
        "muted": "#667085",
        "line": "#718096",
        "panel_fill": "#FAFAFA",
        "panel_stroke": "#D0D5DD",
        "input_fill": "#F0F5FA",
        "input_stroke": "#386FA4",
        "task_fill": "#FFFFFF",
        "task_stroke": "#7B8794",
        "model_fill": "#EEF3F7",
        "model_stroke": "#386FA4",
        "validation_fill": "#F6F7F8",
        "validation_stroke": "#667085",
        "decision_fill": "#F2F4F7",
        "decision_stroke": "#667085",
        "result_fill": "#EAF2F8",
        "result_stroke": "#386FA4",
        "annotation_fill": "#F8F9FA",
        "annotation_stroke": "#98A2B3",
    },
}


STYLE_PROFILE_ALIASES = {
    name.replace("_", "-"): name
    for name in PALETTES
}


ROLE_PALETTE_KEYS = {
    "input": ("input_fill", "input_stroke"),
    "task": ("task_fill", "task_stroke"),
    "process": ("task_fill", "task_stroke"),
    "model": ("model_fill", "model_stroke"),
    "validation": ("validation_fill", "validation_stroke"),
    "decision": ("decision_fill", "decision_stroke"),
    "result": ("result_fill", "result_stroke"),
    "annotation": ("annotation_fill", "annotation_stroke"),
    "group": ("panel_fill", "panel_stroke"),
}


ARCHETYPES = {
    "research_framework",
    "computational_pipeline",
    "parallel_integration",
    "method_architecture",
    "iterative_optimization",
    "custom",
}

KIND_ARCHETYPE_DEFAULTS = {
    "overview": "research_framework",
    "task_pipeline": "computational_pipeline",
    "model_framework": "method_architecture",
    "validation_flow": "iterative_optimization",
    "decision_tree": "computational_pipeline",
    "comparison": "parallel_integration",
    "custom": "research_framework",
}

PRIMITIVE_SIZES: dict[str, tuple[int, int]] = {
    "band": (230, 56),
    "stage": (200, 74),
    "hero_container": (280, 108),
    "model_block": (244, 92),
    "input_lane": (176, 60),
    "parallel_lane": (206, 68),
    "merge_hub": (146, 96),
    "validation_rail": (190, 60),
    "output_block": (220, 76),
    "decision_gate": (184, 108),
    "feedback_rail": (192, 56),
    "annotation_strip": (224, 56),
}


def _safe_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index:03d}"


def _html_label(label: str, *, bold: bool = False, align: str = "center") -> str:
    normalised = label.replace("\r\n", "\n").replace("\r", "\n")
    lines = [html.escape(line, quote=False) for line in normalised.split("\n")]
    body = "<br/>".join(lines)
    if bold:
        body = f"<b>{body}</b>"
    return f"<div align=\"{align}\">{body}</div>"


def _style(**values: Any) -> str:
    return ";".join(f"{key}={value}" for key, value in values.items()) + ";"


def _resolve_palette(style_profile: str) -> dict[str, str]:
    normalised = style_profile.strip().casefold().replace(" ", "_")
    canonical_name = STYLE_PROFILE_ALIASES.get(normalised, normalised)
    palette = PALETTES.get(canonical_name)
    if palette is None:
        available = ", ".join(PALETTES)
        raise ValueError(f"unknown style_profile {style_profile!r}; choose one of: {available}")
    return palette


def resolve_archetype(spec: dict[str, Any]) -> str:
    """Resolve composition without changing the semantic graph.

    Older specs did not declare an archetype.  Their ``kind`` is used only as
    a compatibility hint; unknown/missing values fall back to the conservative
    research-framework grammar.
    """

    declared = spec.get("archetype")
    if isinstance(declared, str) and declared in ARCHETYPES:
        return declared
    return KIND_ARCHETYPE_DEFAULTS.get(str(spec.get("kind", "overview")), "research_framework")


def _graph_degrees(spec: dict[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    node_ids = [str(row["node_id"]) for row in spec.get("nodes", []) if isinstance(row, dict)]
    incoming = {node_id: 0 for node_id in node_ids}
    outgoing = {node_id: 0 for node_id in node_ids}
    for edge in spec.get("edges", []):
        if not isinstance(edge, dict) or edge.get("relation") == "feedback":
            continue
        source, target = str(edge.get("from")), str(edge.get("to"))
        if source in outgoing and target in incoming:
            outgoing[source] += 1
            incoming[target] += 1
    return incoming, outgoing


def _primitive_for(node: dict[str, Any], archetype: str, incoming: int = 0, outgoing: int = 0) -> str:
    declared = str(node.get("primitive", "auto"))
    if declared != "auto" and declared in PRIMITIVE_SIZES:
        return declared
    role = str(node.get("role", "process"))
    emphasis = str(node.get("emphasis", "neutral"))
    if role == "input":
        return "band" if archetype == "research_framework" else "input_lane"
    if role == "validation":
        return "validation_rail"
    if role == "result":
        return "output_block"
    if role == "decision":
        return "decision_gate"
    if role == "annotation":
        return "annotation_strip"
    if archetype == "parallel_integration" and incoming >= 2:
        return "merge_hub"
    if archetype == "parallel_integration" and role in {"process", "model", "task"}:
        return "parallel_lane"
    if archetype == "iterative_optimization" and outgoing == 0 and role != "result":
        return "feedback_rail"
    if role == "model":
        return "hero_container" if emphasis == "core" else "model_block"
    if emphasis == "core" and archetype in {"method_architecture", "computational_pipeline"}:
        return "hero_container"
    return "stage"


def _node_size(node: dict[str, Any], primitive: str) -> tuple[int, int]:
    width, height = PRIMITIVE_SIZES.get(primitive, PRIMITIVE_SIZES["stage"])
    # Long labels get one bounded size increase; geometry must not grow without
    # limit and turn the figure into a collection of text cards.
    density = len(re.sub(r"\s+", " ", str(node.get("label", ""))).strip())
    if density > 42:
        width += 28
        height += 14
    elif density > 24:
        width += 16
    return width, height


def _role_style(
    role: str,
    palette: dict[str, str],
    font_family: str,
    font_size: int,
    emphasis: str,
    primitive: str = "auto",
) -> str:
    fill_key, stroke_key = ROLE_PALETTE_KEYS.get(role, ROLE_PALETTE_KEYS["task"])
    stroke_width = "2" if emphasis == "core" else "1.2"
    font_style = "1" if emphasis == "core" or role in {"model", "result"} else "0"
    values: dict[str, Any] = {
        "whiteSpace": "wrap",
        "html": "1",
        "fillColor": palette[fill_key],
        "strokeColor": palette[stroke_key],
        "strokeWidth": stroke_width,
        "fontColor": palette["ink"],
        "fontFamily": font_family,
        "fontSize": font_size,
        "fontStyle": font_style,
        "align": "center",
        "verticalAlign": "middle",
        "spacing": "8",
        "shadow": "0",
        "glass": "0",
    }
    if role == "decision" or primitive == "decision_gate":
        values.update({"shape": "rhombus", "perimeter": "rhombusPerimeter"})
    elif role == "annotation":
        values.update({"shape": "note", "size": "15"})
    else:
        values.update({"rounded": "1", "arcSize": "10"})
        if primitive in {"band", "validation_rail", "feedback_rail", "annotation_strip"}:
            values.update({"arcSize": "6"})
        elif primitive in {"hero_container", "merge_hub"}:
            values.update({"strokeWidth": "2.4", "arcSize": "12"})
        if role == "group":
            values.update({"dashed": "1", "arcSize": "12"})
    return _style(**values)


def _edge_style(relation: str, palette: dict[str, str], font_family: str, font_size: int) -> str:
    values: dict[str, Any] = {
        "edgeStyle": "orthogonalEdgeStyle",
        "rounded": "1",
        "orthogonalLoop": "1",
        "jettySize": "auto",
        "html": "1",
        "endArrow": "block",
        "endFill": "1",
        "strokeColor": palette["line"],
        "strokeWidth": "1.4",
        "fontColor": palette["muted"],
        "fontFamily": font_family,
        "fontSize": max(10, font_size - 3),
        "labelBackgroundColor": "#FFFFFF",
        "labelBorderColor": "none",
        "spacing": "4",
    }
    if relation == "feedback":
        values.update({"dashed": "1", "dashPattern": "6 4", "endArrow": "open", "endFill": "0"})
    elif relation in {"comparison", "annotation"}:
        values.update({"dashed": "1", "dashPattern": "3 3", "endArrow": "open", "endFill": "0"})
    return _style(**values)


def _dag_layers(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> dict[str, int]:
    node_ids = [str(node["node_id"]) for node in nodes]
    outgoing: dict[str, list[str]] = defaultdict(list)
    indegree = {node_id: 0 for node_id in node_ids}
    for edge in edges:
        if edge.get("relation") == "feedback":
            continue
        source = str(edge.get("from"))
        target = str(edge.get("to"))
        if source in indegree and target in indegree:
            outgoing[source].append(target)
            indegree[target] += 1
    queue = deque(node_id for node_id in node_ids if indegree[node_id] == 0)
    layers = {node_id: 0 for node_id in node_ids}
    visited: set[str] = set()
    while queue:
        source = queue.popleft()
        visited.add(source)
        for target in outgoing[source]:
            layers[target] = max(layers[target], layers[source] + 1)
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    # Cycles are allowed for feedback-like model workflows; keep their order stable.
    next_layer = max(layers.values(), default=0) + 1
    for node_id in node_ids:
        if node_id not in visited and indegree[node_id] > 0:
            layers[node_id] = next_layer
            next_layer += 1
    return layers


def _validate_graph_integrity(spec: dict[str, Any]) -> None:
    """Fail before rendering when the semantic graph cannot be preserved."""

    nodes = [row for row in spec.get("nodes", []) if isinstance(row, dict)]
    edges = [row for row in spec.get("edges", []) if isinstance(row, dict)]
    node_ids = [str(row.get("node_id")) for row in nodes]
    edge_ids = [str(row.get("edge_id")) for row in edges]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("diagram node_id values must be unique")
    if len(edge_ids) != len(set(edge_ids)):
        raise ValueError("diagram edge_id values must be unique")
    known = set(node_ids)
    for edge in edges:
        source, target = str(edge.get("from")), str(edge.get("to"))
        if source not in known or target not in known:
            raise ValueError(
                f"edge {edge.get('edge_id')} references unknown endpoint(s): {source} -> {target}"
            )
    for panel in spec.get("panels", []):
        if not isinstance(panel, dict):
            continue
        missing = [str(node_id) for node_id in panel.get("node_ids", []) if str(node_id) not in known]
        if missing:
            raise ValueError(
                f"panel {panel.get('panel_id')} references unknown node(s): {', '.join(missing)}"
            )


def _composition_top(spec: dict[str, Any]) -> int:
    mode = str(spec.get("title_mode", "compact" if spec.get("title") else "none"))
    return 132 if mode == "banner" else 78


def _sized_nodes(spec: dict[str, Any], archetype: str) -> list[tuple[dict[str, Any], str, int, int]]:
    incoming, outgoing = _graph_degrees(spec)
    result: list[tuple[dict[str, Any], str, int, int]] = []
    for node in spec.get("nodes", []):
        if not isinstance(node, dict):
            continue
        node_id = str(node["node_id"])
        primitive = _primitive_for(node, archetype, incoming.get(node_id, 0), outgoing.get(node_id, 0))
        width, height = _node_size(node, primitive)
        result.append((node, primitive, width, height))
    return result


def _finish_layout(
    spec: dict[str, Any],
    positions: dict[str, tuple[float, float, float, float]],
) -> tuple[dict[str, tuple[float, float, float, float]], int, int]:
    canvas = spec.get("canvas") if isinstance(spec.get("canvas"), dict) else {}
    width = int(canvas.get("width", 1400))
    height = int(canvas.get("height", 720))
    max_right = max((box[0] + box[2] for box in positions.values()), default=width - 70)
    max_bottom = max((box[1] + box[3] for box in positions.values()), default=height - 60)
    return positions, max(width, int(max_right + 70)), max(height, int(max_bottom + 76))


def plan_research_framework(spec: dict[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    """Input band -> core scientific chain -> output, with validation as a rail."""

    rows = _sized_nodes(spec, "research_framework")
    layers = _dag_layers(
        [row[0] for row in rows],
        [row for row in spec.get("edges", []) if isinstance(row, dict)],
    )
    source_order = {str(row[0]["node_id"]): index for index, row in enumerate(rows)}

    def reading_order(row: tuple[dict[str, Any], str, int, int]) -> tuple[int, int]:
        node_id = str(row[0]["node_id"])
        return layers.get(node_id, 0), source_order[node_id]

    inputs = sorted((row for row in rows if row[0].get("role") == "input"), key=reading_order)
    validation = sorted((row for row in rows if row[0].get("role") == "validation"), key=reading_order)
    outputs = sorted((row for row in rows if row[0].get("role") == "result"), key=reading_order)
    used = {id(row[0]) for row in inputs + validation + outputs}
    core = sorted((row for row in rows if id(row[0]) not in used), key=reading_order)
    top, left = _composition_top(spec), 70
    positions: dict[str, tuple[float, float, float, float]] = {}
    for index, (node, _, width, height) in enumerate(inputs):
        positions[str(node["node_id"])] = (left, top + 28 + index * (height + 34), width, height)
    core_x = left + (max((row[2] for row in inputs), default=176) + 96 if inputs else 0)
    cursor = core_x
    for node, _, width, height in core:
        positions[str(node["node_id"])] = (cursor, top, width, height)
        cursor += width + 72
    validation_y = top + max((row[3] for row in core), default=92) + 108
    for index, (node, _, width, height) in enumerate(validation):
        positions[str(node["node_id"])] = (core_x + index * (width + 52), validation_y, width, height)
    output_x = cursor + 28 if core else core_x + 240
    for index, (node, _, width, height) in enumerate(outputs):
        positions[str(node["node_id"])] = (output_x, top + 16 + index * (height + 46), width, height)
    return positions


def _layered_plan(spec: dict[str, Any], archetype: str, *, vertical: bool = False) -> dict[str, tuple[float, float, float, float]]:
    rows = _sized_nodes(spec, archetype)
    nodes = [row[0] for row in rows]
    edges = [row for row in spec.get("edges", []) if isinstance(row, dict)]
    layer_map = _dag_layers(nodes, edges)
    by_layer: dict[int, list[tuple[dict[str, Any], str, int, int]]] = defaultdict(list)
    for row in rows:
        by_layer[layer_map.get(str(row[0]["node_id"]), 0)].append(row)
    positions: dict[str, tuple[float, float, float, float]] = {}
    top, left = _composition_top(spec), 70
    if vertical:
        cursor_y = top
        for layer in sorted(by_layer):
            layer_rows = by_layer[layer]
            cursor_x = left
            layer_h = max((row[3] for row in layer_rows), default=74)
            for node, _, width, height in layer_rows:
                positions[str(node["node_id"])] = (cursor_x, cursor_y, width, height)
                cursor_x += width + 64
            cursor_y += layer_h + 84
    else:
        cursor_x = left
        for layer in sorted(by_layer):
            layer_rows = sorted(
                by_layer[layer],
                key=lambda row: (row[0].get("emphasis") != "core", row[0].get("role") not in {"model", "result"}),
            )
            cursor_y = top
            layer_w = max((row[2] for row in layer_rows), default=200)
            for node, _, width, height in layer_rows:
                positions[str(node["node_id"])] = (cursor_x, cursor_y, width, height)
                cursor_y += height + 52
            cursor_x += layer_w + 84
    return positions


def plan_computational_pipeline(spec: dict[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    return _layered_plan(spec, "computational_pipeline", vertical=spec.get("layout") == "top_to_bottom")


def plan_parallel_integration(spec: dict[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    return _layered_plan(spec, "parallel_integration")


def plan_method_architecture(spec: dict[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    rows = _sized_nodes(spec, "method_architecture")
    incoming, outgoing = _graph_degrees(spec)
    core = next((row for row in rows if row[0].get("emphasis") == "core" and row[0].get("role") == "model"), None)
    core = core or next((row for row in rows if row[0].get("role") == "model"), None)
    core = core or max(rows, key=lambda row: incoming.get(str(row[0]["node_id"]), 0) + outgoing.get(str(row[0]["node_id"]), 0))
    core_id = str(core[0]["node_id"])
    edge_rows = [row for row in spec.get("edges", []) if isinstance(row, dict) and row.get("relation") != "feedback"]
    predecessors = {str(edge.get("from")) for edge in edge_rows if str(edge.get("to")) == core_id}
    successors = {str(edge.get("to")) for edge in edge_rows if str(edge.get("from")) == core_id}
    left_rows = [row for row in rows if str(row[0]["node_id"]) in predecessors]
    right_rows = [row for row in rows if str(row[0]["node_id"]) in successors and row[0].get("role") != "validation"]
    validation = [row for row in rows if row[0].get("role") == "validation"]
    allocated = {id(row[0]) for row in left_rows + right_rows + validation + [core]}
    extras = [row for row in rows if id(row[0]) not in allocated]
    top = _composition_top(spec)
    positions: dict[str, tuple[float, float, float, float]] = {}
    core_x, core_y = 500, top + 92
    positions[core_id] = (core_x, core_y, core[2], core[3])
    for index, (node, _, width, height) in enumerate(left_rows):
        positions[str(node["node_id"])] = (70, top + index * (height + 46), width, height)
    right_x = core_x + core[2] + 126
    for index, (node, _, width, height) in enumerate(right_rows):
        positions[str(node["node_id"])] = (right_x, top + index * (height + 46), width, height)
    rail_y = core_y + core[3] + 108
    for index, (node, _, width, height) in enumerate(validation):
        positions[str(node["node_id"])] = (core_x + index * (width + 48), rail_y, width, height)
    for index, (node, _, width, height) in enumerate(extras):
        positions[str(node["node_id"])] = (core_x - 16 + index * (width + 44), top, width, height)
    return positions


def plan_iterative_optimization(spec: dict[str, Any]) -> dict[str, tuple[float, float, float, float]]:
    positions = _layered_plan(spec, "iterative_optimization")
    # Validation is a lower rail; feedback remains an explicit dashed edge and
    # is never invented by the planner.
    validations = [row for row in _sized_nodes(spec, "iterative_optimization") if row[0].get("role") == "validation"]
    if validations:
        bottom = max((box[1] + box[3] for box in positions.values()), default=_composition_top(spec)) + 72
        for index, (node, _, width, height) in enumerate(validations):
            positions[str(node["node_id"])] = (280 + index * (width + 54), bottom, width, height)
    return positions


def _layout_nodes(spec: dict[str, Any]) -> tuple[dict[str, tuple[float, float, float, float]], int, int]:
    archetype = resolve_archetype(spec)
    planner = {
        "research_framework": plan_research_framework,
        "computational_pipeline": plan_computational_pipeline,
        "parallel_integration": plan_parallel_integration,
        "method_architecture": plan_method_architecture,
        "iterative_optimization": plan_iterative_optimization,
        "custom": lambda value: _layered_plan(value, "custom", vertical=value.get("layout") == "top_to_bottom"),
    }[archetype]
    return _finish_layout(spec, planner(spec))


def _panel_bounds(spec: dict[str, Any], positions: dict[str, tuple[float, float, float, float]]) -> list[tuple[dict[str, Any], tuple[float, float, float, float]]]:
    result: list[tuple[dict[str, Any], tuple[float, float, float, float]]] = []
    panels = [dict(panel) for panel in spec.get("panels", []) if isinstance(panel, dict)]
    if resolve_archetype(spec) == "research_framework":
        core_ids = [
            str(node["node_id"])
            for node in spec.get("nodes", [])
            if isinstance(node, dict)
            and node.get("role") not in {"input", "validation", "result", "annotation"}
        ]
        explicitly_grouped = {
            str(node_id)
            for panel in panels
            for node_id in panel.get("node_ids", [])
        }
        ungrouped_core = [node_id for node_id in core_ids if node_id not in explicitly_grouped]
        if len(ungrouped_core) >= 2:
            panels.append({
                "panel_id": "__research_core__",
                "title": "Core modeling framework",
                "node_ids": ungrouped_core,
                "message": "Composition-only academic hierarchy",
            })
    for panel in panels:
        if not isinstance(panel, dict):
            continue
        boxes = [positions[node_id] for node_id in panel.get("node_ids", []) if node_id in positions]
        if not boxes:
            continue
        left = min(box[0] for box in boxes) - 28
        top = min(box[1] for box in boxes) - 48
        right = max(box[0] + box[2] for box in boxes) + 28
        bottom = max(box[1] + box[3] for box in boxes) + 28
        result.append((panel, (left, top, right - left, bottom - top)))
    return result


def build_drawio_tree(spec: dict[str, Any]) -> ET.Element:
    _validate_graph_integrity(spec)
    palette_name = str(spec.get("style_profile", "academic_minimal"))
    palette = _resolve_palette(palette_name)
    archetype = resolve_archetype(spec)
    font_family = str(spec.get("font_family", "Microsoft YaHei"))
    font_size = int(spec.get("font_size", 16))
    positions, width, height = _layout_nodes(spec)
    root = ET.Element("mxfile", {"host": "Electron", "modified": "", "version": "26.0.0"})
    diagram = ET.SubElement(root, "diagram", {"id": "page-1", "name": "Page-1"})
    model = ET.SubElement(
        diagram,
        "mxGraphModel",
        {
            "dx": "1422", "dy": "762", "grid": "1", "gridSize": "10", "guides": "1",
            "tooltips": "1", "connect": "1", "arrows": "1", "fold": "1", "page": "1",
            "pageScale": "1", "pageWidth": str(width), "pageHeight": str(height), "math": "0", "shadow": "0",
        },
    )
    xml_root = ET.SubElement(model, "root")
    ET.SubElement(xml_root, "mxCell", {"id": "0"})
    ET.SubElement(xml_root, "mxCell", {"id": "1", "parent": "0"})

    title_mode = str(spec.get("title_mode", "compact" if spec.get("title") else "none"))
    title = str(spec.get("title", spec.get("diagram_id", "Diagram")))
    if title_mode == "banner":
        title_cell = ET.SubElement(
            xml_root,
            "mxCell",
            {
                "id": "title",
                "value": _html_label(title, bold=True, align="left"),
                "style": _style(
                    shape="text", html="1", align="left", verticalAlign="middle", fontColor=palette["ink"],
                    fontFamily=font_family, fontSize=font_size + 5, fontStyle="1", spacing="0",
                ),
                "vertex": "1", "parent": "1",
            },
        )
        ET.SubElement(title_cell, "mxGeometry", {"x": "70", "y": "24", "width": str(width - 140), "height": "34", "as": "geometry"})
        message_y, message_h = 66, 38
        message_value = str(spec["message"])
    else:
        message_y, message_h = 20, 34
        message_value = f"{title} — {spec['message']}" if title_mode == "compact" and spec.get("title") else str(spec["message"])
    message_cell = ET.SubElement(
        xml_root,
        "mxCell",
        {
            "id": "message",
            "value": _html_label(message_value, align="left"),
            "style": _style(
                shape="text", html="1", align="left", verticalAlign="middle", fontColor=palette["muted"],
                fontFamily=font_family, fontSize=max(11, font_size - (1 if title_mode == "compact" else 2)), spacing="0",
            ),
            "vertex": "1", "parent": "1",
        },
    )
    ET.SubElement(message_cell, "mxGeometry", {"x": "70", "y": str(message_y), "width": str(width - 140), "height": str(message_h), "as": "geometry"})

    for index, (panel, box) in enumerate(_panel_bounds(spec, positions), start=1):
        x, y, panel_w, panel_h = box
        panel_cell = ET.SubElement(
            xml_root,
            "mxCell",
            {
                "id": _safe_id("panel", index),
                "value": _html_label(str(panel.get("title", panel.get("panel_id", "Panel"))), bold=True, align="left"),
                "style": _style(
                    shape="swimlane", startSize="30", rounded="1", collapsible="0", html="1", whiteSpace="wrap",
                    fillColor=palette["panel_fill"], fillOpacity="35", strokeColor=palette["panel_stroke"],
                    strokeWidth="1", dashed="1", fontColor=palette["muted"], fontFamily=font_family,
                    fontSize=max(11, font_size - 2), fontStyle="1", align="left", verticalAlign="middle",
                    spacingLeft="10", shadow="0",
                ),
                "vertex": "1", "parent": "1",
                "tags": f"harness-panel;{panel.get('panel_id')};archetype:{archetype}",
            },
        )
        ET.SubElement(panel_cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(panel_w), "height": str(panel_h), "as": "geometry"})

    node_xml_ids: dict[str, str] = {}
    incoming, outgoing = _graph_degrees(spec)
    node_rows = [row for row in spec["nodes"] if isinstance(row, dict)]
    for index, node in enumerate(node_rows, start=1):
        node_id = str(node["node_id"])
        xml_id = _safe_id("node", index)
        node_xml_ids[node_id] = xml_id
        x, y, node_w, node_h = positions[node_id]
        primitive = _primitive_for(node, archetype, incoming.get(node_id, 0), outgoing.get(node_id, 0))
        source_refs = ",".join(str(value) for value in node.get("source_refs", []))
        cell = ET.SubElement(
            xml_root,
            "mxCell",
            {
                "id": xml_id,
                "value": _html_label(str(node["label"]), bold=node.get("emphasis") == "core"),
                "style": _role_style(str(node.get("role", "process")), palette, font_family, font_size, str(node.get("emphasis", "neutral")), primitive),
                "vertex": "1", "parent": "1",
                "tags": f"harness-node;{node_id};archetype:{archetype};primitive:{primitive};source-refs:{source_refs}",
            },
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(node_w), "height": str(node_h), "as": "geometry"})

    for index, edge in enumerate((row for row in spec.get("edges", []) if isinstance(row, dict)), start=1):
        source = node_xml_ids.get(str(edge.get("from")))
        target = node_xml_ids.get(str(edge.get("to")))
        if source is None or target is None:  # protected by _validate_graph_integrity
            raise ValueError(f"edge {edge.get('edge_id')} could not resolve its endpoints")
        source_refs = ",".join(str(value) for value in edge.get("source_refs", []))
        relation = str(edge.get("relation", "data"))
        attrs = {
            "id": _safe_id("edge", index),
            "value": _html_label(str(edge["label"])) if edge.get("label") else "",
            "style": _edge_style(relation, palette, font_family, font_size),
            "edge": "1", "parent": "1", "source": source, "target": target,
            "tags": f"harness-edge;{edge.get('edge_id')};relation:{relation};source-refs:{source_refs}",
        }
        cell = ET.SubElement(xml_root, "mxCell", attrs)
        ET.SubElement(cell, "mxGeometry", {"relative": "1", "as": "geometry"})
    return root


def write_drawio(spec: dict[str, Any], output_path: Path) -> None:
    root = build_drawio_tree(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    tree = ET.ElementTree(root)
    tree.write(output_path, encoding="utf-8", xml_declaration=True, short_empty_elements=True)


def _find_drawio_cli() -> str | None:
    candidates = [
        os.environ.get("DRAWIO_CLI"),
        shutil.which("drawio"),
        shutil.which("diagrams.net"),
    ]
    program_files = (
        os.environ.get("ProgramFiles"),
        os.environ.get("ProgramW6432"),
        # A common Windows data-drive installation; use DRAWIO_CLI to override
        # discovery for any other non-standard location.
        r"D:\Program Files" if os.name == "nt" else None,
    )
    local_app_data = os.environ.get("LOCALAPPDATA")
    for directory in dict.fromkeys(path for path in program_files if path):
        candidates.append(str(Path(directory) / "draw.io" / "draw.io.exe"))
    if local_app_data:
        candidates.append(str(Path(local_app_data) / "Programs" / "draw.io" / "draw.io.exe"))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


def export_drawio(source_path: Path, output_path: Path, output_format: str) -> tuple[bool, str]:
    executable = _find_drawio_cli()
    if executable is None:
        return False, "draw.io Desktop CLI not found; open the .drawio source in app.diagrams.net and export manually"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [executable, "-x", "-f", output_format, "-e", "-b", "10", "-o", str(output_path), str(source_path)]
    result = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        return False, result.stderr.strip() or result.stdout.strip() or f"draw.io export exited {result.returncode}"
    return True, f"exported {output_format} to {output_path}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec")
    parser.add_argument("--output")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--export-format", choices=["svg", "pdf", "png"])
    parser.add_argument("--export-output")
    parser.add_argument("--list-style-profiles", action="store_true")
    parser.add_argument("--list-archetypes", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.list_style_profiles or args.list_archetypes:
        listing: dict[str, Any] = {}
        if args.list_style_profiles:
            listing["style_profiles"] = list(PALETTES)
        if args.list_archetypes:
            listing["archetypes"] = sorted(ARCHETYPES)
        print(json.dumps(listing, ensure_ascii=False))
        return 0
    if not args.spec or not args.output:
        parser.error("--spec and --output are required unless a --list-* option is used")

    root = Path(args.project_root).resolve()
    spec_path = resolve_path(args.spec, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        spec = load_structured(spec_path)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    if not isinstance(spec, dict):
        print(json.dumps({"ok": False, "errors": ["diagram spec must be an object"]}, ensure_ascii=False))
        return 1
    _, schema_errors, _ = _validate_document(spec_path, SCHEMA_PATH)
    if schema_errors:
        print(json.dumps({"ok": False, "errors": [f"diagram spec schema: {message}" for message in schema_errors]}, ensure_ascii=False))
        return 1
    if output_path.exists() and not args.force:
        print(json.dumps({"ok": False, "errors": [f"output exists: {output_path}; pass --force to replace"]}, ensure_ascii=False))
        return 1
    try:
        write_drawio(spec, output_path)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    report: dict[str, Any] = {"ok": True, "source": str(output_path), "archetype": resolve_archetype(spec), "export": None, "warnings": []}
    if args.export_format:
        export_path = resolve_path(args.export_output, root).resolve() if args.export_output else output_path.with_suffix(output_path.suffix + f".{args.export_format}")
        exported, message = export_drawio(output_path, export_path, args.export_format)
        report["export"] = {"format": args.export_format, "path": str(export_path), "ok": exported, "message": message}
        if not exported:
            report["warnings"].append(message)
            return_code = 2
        else:
            return_code = 0
    else:
        return_code = 0
    print(json.dumps(report, ensure_ascii=False))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
