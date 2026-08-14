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


def _safe_id(prefix: str, index: int) -> str:
    return f"{prefix}-{index:03d}"


def _html_label(label: str, *, bold: bool = False) -> str:
    normalised = label.replace("\r\n", "\n").replace("\r", "\n")
    lines = [html.escape(line, quote=False) for line in normalised.split("\n")]
    body = "<br/>".join(lines)
    if bold:
        body = f"<b>{body}</b>"
    return f"<div align=\"center\">{body}</div>"


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


def _role_style(role: str, palette: dict[str, str], font_family: str, font_size: int, emphasis: str) -> str:
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
    if role == "decision":
        values.update({"shape": "rhombus", "perimeter": "rhombusPerimeter"})
    elif role == "annotation":
        values.update({"shape": "note", "size": "15"})
    else:
        values.update({"rounded": "1", "arcSize": "14"})
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


def _layout_nodes(spec: dict[str, Any]) -> tuple[dict[str, tuple[float, float, float, float]], int, int]:
    nodes = [row for row in spec["nodes"] if isinstance(row, dict)]
    edges = [row for row in spec.get("edges", []) if isinstance(row, dict)]
    layout = spec.get("layout", "left_to_right")
    canvas = spec.get("canvas") if isinstance(spec.get("canvas"), dict) else {}
    width = int(canvas.get("width", 1400))
    height = int(canvas.get("height", 900))
    node_w, node_h = 190, 72
    decision_h = 94
    h_gap, v_gap = 76, 66
    left, top = 70, 128
    layers = _dag_layers(nodes, edges)
    by_layer: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for node in nodes:
        by_layer[layers.get(str(node["node_id"]), 0)].append(node)
    positions: dict[str, tuple[float, float, float, float]] = {}

    if layout == "grid":
        columns = max(1, int(len(nodes) ** 0.5 + 0.999))
        for index, node in enumerate(nodes):
            col, row = divmod(index, columns)
            node_height = decision_h if node.get("role") == "decision" else node_h
            positions[str(node["node_id"])] = (
                left + row * (node_w + h_gap),
                top + col * (node_height + v_gap),
                node_w,
                node_height,
            )
    else:
        max_layer = max(by_layer, default=0)
        for layer in range(max_layer + 1):
            rows = by_layer.get(layer, [])
            for row, node in enumerate(rows):
                node_height = decision_h if node.get("role") == "decision" else node_h
                if layout == "top_to_bottom":
                    x = left + row * (node_w + h_gap)
                    y = top + layer * (node_h + v_gap)
                else:
                    x = left + layer * (node_w + h_gap)
                    y = top + row * (node_height + v_gap)
                positions[str(node["node_id"])] = (x, y, node_w, node_height)
        if layout == "top_to_bottom":
            max_layer_width = max((len(rows) for rows in by_layer.values()), default=1)
            width = max(width, int(left * 2 + max_layer_width * node_w + max(0, max_layer_width - 1) * h_gap))

    max_right = max((box[0] + box[2] for box in positions.values()), default=width - left)
    max_bottom = max((box[1] + box[3] for box in positions.values()), default=height - 60)
    width = max(width, int(max_right + left))
    height = max(height, int(max_bottom + 90))
    return positions, width, height


def _panel_bounds(spec: dict[str, Any], positions: dict[str, tuple[float, float, float, float]]) -> list[tuple[dict[str, Any], tuple[float, float, float, float]]]:
    result: list[tuple[dict[str, Any], tuple[float, float, float, float]]] = []
    for panel in spec.get("panels", []):
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
    palette_name = str(spec.get("style_profile", "academic_minimal"))
    palette = _resolve_palette(palette_name)
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

    title = str(spec.get("title", spec.get("diagram_id", "Diagram")))
    title_cell = ET.SubElement(
        xml_root,
        "mxCell",
        {
            "id": "title",
            "value": _html_label(title, bold=True),
            "style": _style(
                shape="text", html="1", align="left", verticalAlign="middle", fontColor=palette["ink"],
                fontFamily=font_family, fontSize=font_size + 5, fontStyle="1", spacing="0",
            ),
            "vertex": "1", "parent": "1",
        },
    )
    ET.SubElement(title_cell, "mxGeometry", {"x": "70", "y": "24", "width": str(width - 140), "height": "34", "as": "geometry"})
    message_cell = ET.SubElement(
        xml_root,
        "mxCell",
        {
            "id": "message",
            "value": _html_label(str(spec["message"])),
            "style": _style(
                shape="text", html="1", align="left", verticalAlign="middle", fontColor=palette["muted"],
                fontFamily=font_family, fontSize=max(11, font_size - 2), spacing="0",
            ),
            "vertex": "1", "parent": "1",
        },
    )
    ET.SubElement(message_cell, "mxGeometry", {"x": "70", "y": "66", "width": str(width - 140), "height": "38", "as": "geometry"})

    for index, (panel, box) in enumerate(_panel_bounds(spec, positions), start=1):
        x, y, panel_w, panel_h = box
        panel_cell = ET.SubElement(
            xml_root,
            "mxCell",
            {
                "id": _safe_id("panel", index),
                "value": _html_label(str(panel.get("title", panel.get("panel_id", "Panel"))), bold=True),
                "style": _style(
                    shape="swimlane", startSize="30", rounded="1", collapsible="0", html="1", whiteSpace="wrap",
                    fillColor=palette["panel_fill"], fillOpacity="35", strokeColor=palette["panel_stroke"],
                    strokeWidth="1", dashed="1", fontColor=palette["muted"], fontFamily=font_family,
                    fontSize=max(11, font_size - 2), fontStyle="1", align="left", verticalAlign="middle",
                    spacingLeft="10", shadow="0",
                ),
                "vertex": "1", "parent": "1",
            },
        )
        ET.SubElement(panel_cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(panel_w), "height": str(panel_h), "as": "geometry"})

    node_xml_ids: dict[str, str] = {}
    node_rows = [row for row in spec["nodes"] if isinstance(row, dict)]
    for index, node in enumerate(node_rows, start=1):
        node_id = str(node["node_id"])
        xml_id = _safe_id("node", index)
        node_xml_ids[node_id] = xml_id
        x, y, node_w, node_h = positions[node_id]
        source_refs = ",".join(str(value) for value in node.get("source_refs", []))
        cell = ET.SubElement(
            xml_root,
            "mxCell",
            {
                "id": xml_id,
                "value": _html_label(str(node["label"]), bold=node.get("emphasis") == "core"),
                "style": _role_style(str(node.get("role", "process")), palette, font_family, font_size, str(node.get("emphasis", "neutral"))),
                "vertex": "1", "parent": "1",
                "tags": f"harness-node;{node_id};source-refs:{source_refs}",
            },
        )
        ET.SubElement(cell, "mxGeometry", {"x": str(x), "y": str(y), "width": str(node_w), "height": str(node_h), "as": "geometry"})

    for index, edge in enumerate((row for row in spec.get("edges", []) if isinstance(row, dict)), start=1):
        source = node_xml_ids.get(str(edge.get("from")))
        target = node_xml_ids.get(str(edge.get("to")))
        if source is None or target is None:
            continue
        source_refs = ",".join(str(value) for value in edge.get("source_refs", []))
        attrs = {
            "id": _safe_id("edge", index),
            "value": _html_label(str(edge["label"])) if edge.get("label") else "",
            "style": _edge_style(str(edge.get("relation", "data")), palette, font_family, font_size),
            "edge": "1", "parent": "1", "source": source, "target": target,
            "tags": f"harness-edge;{edge.get('edge_id')};source-refs:{source_refs}",
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
    candidates = [shutil.which("drawio"), shutil.which("diagrams.net")]
    program_files = os.environ.get("ProgramFiles")
    local_app_data = os.environ.get("LOCALAPPDATA")
    if program_files:
        candidates.append(str(Path(program_files) / "draw.io" / "draw.io.exe"))
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
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if args.list_style_profiles:
        print(json.dumps({"style_profiles": list(PALETTES)}, ensure_ascii=False))
        return 0
    if not args.spec or not args.output:
        parser.error("--spec and --output are required unless --list-style-profiles is used")

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
    report: dict[str, Any] = {"ok": True, "source": str(output_path), "export": None, "warnings": []}
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
