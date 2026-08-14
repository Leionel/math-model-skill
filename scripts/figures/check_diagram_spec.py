#!/usr/bin/env python3
"""Check a structured vector-diagram specification and its editable exports."""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, write_json  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "diagram_spec.schema.json"
VECTOR_OUTPUTS = {"svg", "pdf", "emf"}
RASTER_OUTPUTS = {"png"}
DIAGRAM_ROLES = {"overview", "task_pipeline", "model_framework", "validation_flow", "decision_tree", "comparison", "custom"}


def _normalise_text(value: str) -> str:
    text = html.unescape(value)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip().casefold()


def _source_labels(path: Path, source_format: str) -> tuple[str, list[str]]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return "", [f"cannot parse {source_format} source: {exc}"]
    values: list[str] = []
    if source_format == "drawio":
        for element in root.iter():
            value = element.attrib.get("value")
            if value:
                values.append(value)
    elif source_format == "svg":
        for element in root.iter():
            if element.tag.rsplit("}", 1)[-1] in {"text", "title", "desc"} and element.text:
                values.append(element.text)
    return _normalise_text(" ".join(values)), []


def _validate_drawio_structure(path: Path) -> list[str]:
    """Validate the native mxGraph skeleton and references used by the backend."""
    try:
        document_root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return [f"cannot parse drawio XML: {exc}"]
    model = document_root
    if document_root.tag.rsplit("}", 1)[-1] == "mxfile":
        model = next((element for element in document_root.iter() if element.tag.rsplit("}", 1)[-1] == "mxGraphModel"), None)
    if model is None:
        return ["drawio XML has no mxGraphModel"]
    graph_root = next((element for element in model if element.tag.rsplit("}", 1)[-1] == "root"), None)
    if graph_root is None:
        return ["drawio XML has no root cell container"]
    direct_cells = [element for element in graph_root if element.tag.rsplit("}", 1)[-1] == "mxCell"]
    errors: list[str] = []
    if len(direct_cells) < 2 or direct_cells[0].attrib.get("id") != "0" or direct_cells[1].attrib.get("id") != "1":
        errors.append("drawio root must start with mxCell id=0 followed by mxCell id=1")
    if len(direct_cells) >= 2 and direct_cells[1].attrib.get("parent") != "0":
        errors.append("drawio default layer id=1 must have parent=0")
    ids = [cell.attrib.get("id") for cell in direct_cells]
    if any(not cell_id for cell_id in ids):
        errors.append("every drawio mxCell must have an id")
    if len(ids) != len(set(ids)):
        errors.append("drawio mxCell ids must be unique")
    known_ids = {cell_id for cell_id in ids if cell_id}
    for cell in direct_cells[2:]:
        cell_id = cell.attrib.get("id")
        parent = cell.attrib.get("parent")
        if parent not in known_ids:
            errors.append(f"drawio cell {cell_id} has an unknown parent {parent}")
        if cell.attrib.get("vertex") == "1":
            geometry = next((child for child in cell if child.tag.rsplit("}", 1)[-1] == "mxGeometry"), None)
            if geometry is None:
                errors.append(f"drawio vertex {cell_id} has no mxGeometry")
        if cell.attrib.get("edge") == "1":
            source = cell.attrib.get("source")
            target = cell.attrib.get("target")
            if source not in known_ids or target not in known_ids:
                errors.append(f"drawio edge {cell_id} has an unknown source/target")
            geometry = next((child for child in cell if child.tag.rsplit("}", 1)[-1] == "mxGeometry"), None)
            if geometry is None:
                errors.append(f"drawio edge {cell_id} has no mxGeometry")
    return errors


def audit_diagram_spec(
    spec: dict[str, Any],
    *,
    root: Path,
    strict: bool = False,
    require_reviewed: bool = False,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    node_rows = [row for row in spec.get("nodes", []) if isinstance(row, dict)]
    edge_rows = [row for row in spec.get("edges", []) if isinstance(row, dict)]
    node_ids = [row.get("node_id") for row in node_rows]
    edge_ids = [row.get("edge_id") for row in edge_rows]
    known_nodes = {value for value in node_ids if isinstance(value, str)}

    if len(node_ids) != len(set(node_ids)):
        errors.append("diagram node_id values must be unique")
    if len(edge_ids) != len(set(edge_ids)):
        errors.append("diagram edge_id values must be unique")
    for edge in edge_rows:
        if edge.get("from") not in known_nodes or edge.get("to") not in known_nodes:
            errors.append(f"edge {edge.get('edge_id')} references an unknown node")
    for node in node_rows:
        label = str(node.get("label", "")).strip()
        if not label:
            errors.append(f"node {node.get('node_id')} has an empty label")
        if re.search(r"(?:\.\.\.|…|\betc\.?$)", label, flags=re.IGNORECASE):
            errors.append(f"node {node.get('node_id')} contains an omitted-content placeholder")
        if not node.get("source_refs"):
            errors.append(f"node {node.get('node_id')} has no source_refs")
    for edge in edge_rows:
        if not edge.get("source_refs"):
            errors.append(f"edge {edge.get('edge_id')} has no source_refs")

    kind = spec.get("kind")
    roles = {node.get("role") for node in node_rows}
    if kind in {"overview", "task_pipeline", "model_framework"}:
        for required_role in ("process", "model"):
            if required_role not in roles:
                warnings.append(f"{kind} diagram has no node with role={required_role}")
        if "result" not in roles:
            warnings.append(f"{kind} diagram has no result node; verify that the output is explicit")
    if len(node_rows) >= 2 and not edge_rows:
        errors.append("a diagram with multiple nodes must declare at least one edge")

    source_path_value = spec.get("source_artifact")
    source_path = resolve_path(source_path_value, root).resolve() if isinstance(source_path_value, str) else None
    rendered_paths = [
        resolve_path(value, root).resolve()
        for value in spec.get("rendered_artifacts", [])
        if isinstance(value, str)
    ]
    status = spec.get("status")
    if strict:
        if spec.get("source_editability") != "editable_source":
            errors.append("strict diagram QA requires an editable source artifact")
        delivery_mode = spec.get("delivery_mode")
        text_policy = spec.get("text_policy")
        output_formats = set(spec.get("output_formats", []))
        if text_policy not in {"native_text", "outlined_text", "raster_text"}:
            errors.append("strict diagram QA rejects unspecified text rendering")
        if delivery_mode != "raster_only" and not VECTOR_OUTPUTS.intersection(output_formats):
            errors.append("strict diagram QA requires SVG, PDF, or EMF output unless delivery_mode=raster_only")
        if delivery_mode == "raster_only":
            if text_policy != "raster_text":
                errors.append("raster_only delivery requires text_policy=raster_text")
            if not RASTER_OUTPUTS.intersection(output_formats):
                errors.append("raster_only delivery requires a PNG output")
            raster_dpi = spec.get("raster_dpi")
            if not isinstance(raster_dpi, int) or raster_dpi < 300:
                errors.append("raster_only delivery requires raster_dpi >= 300")
            warnings.append("raster-only delivery requires final-size visual review and should not replace the editable source")
        elif text_policy == "raster_text":
            errors.append("text_policy=raster_text is only allowed with delivery_mode=raster_only")
        if spec.get("human_review_required") is not True:
            errors.append("strict diagram QA requires explicit human review")
        if status not in {"rendered", "reviewed"}:
            errors.append("strict diagram QA requires status=rendered or reviewed")
    if require_reviewed and status != "reviewed":
        errors.append("diagram review is required before formal W2")

    if status in {"rendered", "reviewed"} or strict:
        if source_path is None:
            errors.append("rendered/reviewed diagram must declare source_artifact")
        elif not source_path.is_file():
            errors.append(f"diagram source does not exist: {rel_path(source_path, root)}")
        if not rendered_paths:
            errors.append("rendered/reviewed diagram must declare rendered_artifacts")
        for path in rendered_paths:
            if not path.is_file():
                errors.append(f"rendered diagram does not exist: {rel_path(path, root)}")

    source_label_report: dict[str, Any] = {"checked": False, "missing_labels": []}
    if source_path is not None and source_path.is_file() and spec.get("source_format") in {"drawio", "svg"}:
        if spec.get("source_format") == "drawio":
            errors.extend(_validate_drawio_structure(source_path))
        source_text, parse_errors = _source_labels(source_path, spec["source_format"])
        errors.extend(parse_errors)
        source_label_report["checked"] = True
        if spec.get("text_policy") in {"native_text", "raster_text"}:
            missing = [
                node.get("node_id")
                for node in node_rows
                if _normalise_text(str(node.get("label", ""))) not in source_text
            ]
            source_label_report["missing_labels"] = missing
            if missing:
                errors.append(f"source is missing native labels for nodes: {missing}")

    return {
        "schema_version": "1.0",
        "diagram_id": spec.get("diagram_id"),
        "kind": kind if kind in DIAGRAM_ROLES else None,
        "status": status,
        "source_labels": source_label_report,
        "errors": errors,
        "warnings": warnings,
        "manual_review_required": True,
        "ok": not errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-reviewed", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    spec_path = resolve_path(args.spec, root).resolve()
    try:
        spec = load_structured(spec_path)
    except (OSError, ValueError, TypeError) as exc:
        report = {"schema_version": "1.0", "ok": False, "errors": [str(exc)], "warnings": []}
    else:
        if not isinstance(spec, dict):
            report = {"schema_version": "1.0", "ok": False, "errors": ["diagram spec must be an object"], "warnings": []}
        else:
            _, schema_errors, _ = _validate_document(spec_path, SCHEMA_PATH)
            if schema_errors:
                report = {
                    "schema_version": "1.0",
                    "diagram_id": spec.get("diagram_id"),
                    "ok": False,
                    "errors": [f"diagram spec schema: {message}" for message in schema_errors],
                    "warnings": [],
                    "manual_review_required": True,
                }
            else:
                report = audit_diagram_spec(spec, root=root, strict=args.strict, require_reviewed=args.require_reviewed)
                report["spec"] = rel_path(spec_path, root)

    if args.output:
        output_path = resolve_path(args.output, root).resolve()
        try:
            write_json(output_path, report, overwrite=args.force)
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
