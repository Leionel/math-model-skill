#!/usr/bin/env python3
"""Focused regression tests for the native draw.io diagram backend."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from figures.generate_drawio import PALETTES, _find_drawio_cli, _layout_nodes, _role_style, build_drawio_tree, resolve_archetype, write_drawio  # noqa: E402
from figures.check_diagram_spec import audit_diagram_spec  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


def sample_spec(style_profile: str = "academic-minimal") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "diagram_id": "FIG-DRAWIO-01",
        "title": "Evidence-to-claim workflow",
        "kind": "overview",
        "message": "Evidence is transformed into a validated claim through a declared model.",
        "layout": "left_to_right",
        "style_profile": style_profile,
        "source_format": "drawio",
        "delivery_mode": "vector_preferred",
        "output_formats": ["svg"],
        "text_policy": "native_text",
        "source_editability": "editable_source",
        "human_review_required": True,
        "status": "draft",
        "nodes": [
            {"node_id": "input", "label": "Input evidence", "role": "input", "source_refs": ["input"], "emphasis": "core"},
            {"node_id": "model", "label": "Declared model", "role": "model", "source_refs": ["M1"], "emphasis": "core"},
            {"node_id": "decision", "label": "Validation passed?", "role": "decision", "source_refs": ["VAL-1"], "emphasis": "neutral"},
            {"node_id": "result", "label": "Claimable result", "role": "result", "source_refs": ["R1"], "emphasis": "core"},
            {"node_id": "note", "label": "Human review", "role": "annotation", "source_refs": ["W2"], "emphasis": "secondary"},
        ],
        "edges": [
            {"edge_id": "e1", "from": "input", "to": "model", "relation": "data", "source_refs": ["input"]},
            {"edge_id": "e2", "from": "model", "to": "decision", "relation": "dependency", "source_refs": ["M1"]},
            {"edge_id": "e3", "from": "decision", "to": "result", "relation": "control", "source_refs": ["VAL-1"]},
            {"edge_id": "e4", "from": "result", "to": "note", "relation": "annotation", "source_refs": ["W2"]},
        ],
    }


def archetype_spec(archetype: str, style_profile: str = "academic_minimal") -> dict[str, object]:
    spec = sample_spec(style_profile)
    spec["archetype"] = archetype
    spec["title_mode"] = "none"
    if archetype == "parallel_integration":
        spec["nodes"] = [
            {"node_id": "a", "label": "Economic data", "role": "input", "source_refs": ["D1"], "emphasis": "neutral"},
            {"node_id": "b", "label": "Weather data", "role": "input", "source_refs": ["D2"], "emphasis": "neutral"},
            {"node_id": "ma", "label": "Model A", "role": "model", "source_refs": ["M1"], "emphasis": "core"},
            {"node_id": "mb", "label": "Model B", "role": "model", "source_refs": ["M2"], "emphasis": "core"},
            {"node_id": "fusion", "label": "Fusion", "role": "process", "source_refs": ["M3"], "emphasis": "core"},
            {"node_id": "result", "label": "Final strategy", "role": "result", "source_refs": ["R1"], "emphasis": "core"},
        ]
        spec["edges"] = [
            {"edge_id": "e1", "from": "a", "to": "ma", "relation": "data", "source_refs": ["D1"]},
            {"edge_id": "e2", "from": "b", "to": "mb", "relation": "data", "source_refs": ["D2"]},
            {"edge_id": "e3", "from": "ma", "to": "fusion", "relation": "dependency", "source_refs": ["M1"]},
            {"edge_id": "e4", "from": "mb", "to": "fusion", "relation": "dependency", "source_refs": ["M2"]},
            {"edge_id": "e5", "from": "fusion", "to": "result", "relation": "control", "source_refs": ["R1"]},
        ]
    elif archetype == "iterative_optimization":
        spec["nodes"] = [
            {"node_id": "init", "label": "Initialize", "role": "input", "source_refs": ["A1"], "emphasis": "neutral"},
            {"node_id": "search", "label": "Destroy / repair", "role": "model", "source_refs": ["M1"], "emphasis": "core"},
            {"node_id": "accept", "label": "Accept?", "role": "decision", "source_refs": ["V1"], "emphasis": "neutral"},
            {"node_id": "result", "label": "Final solution", "role": "result", "source_refs": ["R1"], "emphasis": "core"},
        ]
        spec["edges"] = [
            {"edge_id": "e1", "from": "init", "to": "search", "relation": "control", "source_refs": ["A1"]},
            {"edge_id": "e2", "from": "search", "to": "accept", "relation": "dependency", "source_refs": ["M1"]},
            {"edge_id": "e3", "from": "accept", "to": "search", "relation": "feedback", "source_refs": ["V1"]},
            {"edge_id": "e4", "from": "accept", "to": "result", "relation": "control", "source_refs": ["R1"]},
        ]
    return spec


def semantic_cell_snapshot(path: Path) -> set[tuple[str | None, ...]]:
    """Keep editable geometry out of the source-versus-spec contract."""
    return {
        tuple(cell.get(key) for key in ("id", "value", "source", "target", "tags"))
        for cell in ET.parse(path).getroot().findall(".//mxCell")
        if cell.get("tags", "").startswith("harness-")
    }


class DrawioBackendTest(unittest.TestCase):
    def test_drawio_cli_honors_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory(prefix="drawio-cli-") as temp:
            executable = Path(temp) / "draw.io.exe"
            executable.write_bytes(b"fixture")
            with patch.dict(os.environ, {"DRAWIO_CLI": str(executable)}, clear=False):
                self.assertEqual(_find_drawio_cli(), str(executable))

    def test_profiles_are_explicit_and_hyphen_alias_is_supported(self) -> None:
        self.assertGreaterEqual(len(PALETTES), 7)
        tree = build_drawio_tree(sample_spec())
        self.assertEqual(tree.tag, "mxfile")
        with self.assertRaisesRegex(ValueError, "unknown style_profile"):
            build_drawio_tree(sample_spec("not-a-palette"))

    def test_role_styles_are_valid_drawio_style_tokens(self) -> None:
        palette = PALETTES["academic_minimal"]
        task_style = _role_style("task", palette, "Arial", 16, "neutral")
        self.assertIn("rounded=1;", task_style)
        self.assertNotIn("shape=rounded=1", task_style)
        self.assertIn("shape=rhombus;", _role_style("decision", palette, "Arial", 16, "neutral"))
        self.assertIn("shape=note;", _role_style("annotation", palette, "Arial", 16, "neutral"))

    def test_native_drawio_output_contains_graph_and_edges(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-drawio-") as temp:
            output = Path(temp) / "overview.drawio"
            write_drawio(sample_spec(), output)
            tree = ET.parse(output)
            root = tree.getroot()
            self.assertEqual(root.tag, "mxfile")
            cells = root.findall(".//mxCell")
            self.assertGreaterEqual(len(cells), 11)
            self.assertTrue(any(cell.get("edge") == "1" for cell in cells))
            self.assertTrue(any(cell.get("id") == "0" for cell in cells))
            self.assertTrue(any(cell.get("id") == "1" and cell.get("parent") == "0" for cell in cells))

    def test_five_archetypes_have_native_nonuniform_geometry(self) -> None:
        archetypes = (
            "research_framework",
            "computational_pipeline",
            "parallel_integration",
            "method_architecture",
            "iterative_optimization",
        )
        for archetype in archetypes:
            with self.subTest(archetype=archetype):
                spec = archetype_spec(archetype)
                self.assertEqual(resolve_archetype(spec), archetype)
                positions, _, _ = _layout_nodes(spec)
                self.assertEqual(set(positions), {str(row["node_id"]) for row in spec["nodes"]})
                self.assertGreater(len({(box[2], box[3]) for box in positions.values()}), 1)
                tree = build_drawio_tree(spec)
                tags = [cell.get("tags", "") for cell in tree.findall(".//mxCell")]
                self.assertTrue(any(f"archetype:{archetype}" in value for value in tags))

    def test_archetype_geometry_is_independent_of_palette(self) -> None:
        for archetype in (
            "research_framework", "computational_pipeline", "parallel_integration",
            "method_architecture", "iterative_optimization",
        ):
            with self.subTest(archetype=archetype):
                first = archetype_spec(archetype, "slate_violet")
                second = archetype_spec(archetype, "minimal_gray_blue")
                self.assertEqual(_layout_nodes(first), _layout_nodes(second))
                first_styles = " ".join(cell.get("style", "") for cell in build_drawio_tree(first).findall(".//mxCell"))
                second_styles = " ".join(cell.get("style", "") for cell in build_drawio_tree(second).findall(".//mxCell"))
                self.assertIn(PALETTES["slate_violet"]["model_stroke"], first_styles)
                self.assertIn(PALETTES["minimal_gray_blue"]["model_stroke"], second_styles)

    def test_paper_default_uses_compact_caption_strip_not_banner(self) -> None:
        tree = build_drawio_tree(sample_spec())
        cells = tree.findall(".//mxCell")
        self.assertFalse(any(cell.get("id") == "title" for cell in cells))
        self.assertTrue(any(cell.get("id") == "message" for cell in cells))

    def test_research_framework_uses_topology_and_core_grouping(self) -> None:
        spec = archetype_spec("research_framework")
        spec["nodes"] = list(reversed(spec["nodes"]))
        positions, _, _ = _layout_nodes(spec)
        self.assertLess(positions["model"][0], positions["decision"][0])
        tree = build_drawio_tree(spec)
        tags = [cell.get("tags", "") for cell in tree.findall(".//mxCell")]
        self.assertTrue(any("harness-panel;__research_core__" in value for value in tags))

    def test_generator_rejects_unknown_edge_endpoint_and_preserves_relation(self) -> None:
        spec = sample_spec()
        spec["edges"][0]["to"] = "missing-node"
        with self.assertRaisesRegex(ValueError, "unknown endpoint"):
            build_drawio_tree(spec)

        valid = sample_spec()
        tags = [cell.get("tags", "") for cell in build_drawio_tree(valid).findall(".//mxCell")]
        self.assertTrue(any("relation:data" in value for value in tags))

    def test_composition_qa_emits_stable_warning_codes(self) -> None:
        spec = archetype_spec("computational_pipeline")
        spec["title_mode"] = "banner"
        report = audit_diagram_spec(spec, root=ROOT)
        codes = {row["code"] for row in report["composition_warnings"]}
        self.assertIn("PPT_TITLE_BANNER_RISK", codes)

        custom = sample_spec()
        custom["archetype"] = "custom"
        custom["nodes"] = [
            {"node_id": f"n{index}", "label": f"Stage {index}", "role": "process", "source_refs": [f"S{index}"], "emphasis": "neutral"}
            for index in range(6)
        ]
        custom["edges"] = [
            {"edge_id": f"e{index}", "from": f"n{index}", "to": f"n{index + 1}", "relation": "control", "source_refs": [f"S{index}"]}
            for index in range(5)
        ]
        custom_report = audit_diagram_spec(custom, root=ROOT)
        custom_codes = {row["code"] for row in custom_report["composition_warnings"]}
        self.assertIn("CARD_WALL_RISK", custom_codes)
        self.assertIn("WEAK_HIERARCHY", custom_codes)

    def test_section_16_archetype_assets_are_schema_valid_native_sources(self) -> None:
        schema = ROOT / "schemas" / "diagram_spec.schema.json"
        asset_root = ROOT / "assets" / "drawio" / "archetypes"
        expected = {
            "research_framework", "computational_pipeline", "parallel_integration",
            "method_architecture", "iterative_optimization",
        }
        self.assertEqual({path.name for path in asset_root.iterdir() if path.is_dir()}, expected)
        for name in expected:
            with self.subTest(archetype=name):
                spec_path = asset_root / name / "example_spec.json"
                drawio_path = asset_root / name / "example.drawio"
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                _, errors, _ = _validate_document(spec_path, schema)
                self.assertFalse(errors, errors)
                self.assertEqual(spec["archetype"], name)
                cells = ET.parse(drawio_path).getroot().findall(".//mxCell")
                tags = " ".join(cell.get("tags", "") for cell in cells)
                self.assertIn(f"archetype:{name}", tags)
                for node in spec["nodes"]:
                    self.assertIn(str(node["node_id"]), tags)
                with tempfile.TemporaryDirectory(prefix=f"drawio-{name}-") as temp:
                    regenerated = Path(temp) / "example.drawio"
                    regenerated_again = Path(temp) / "example-again.drawio"
                    write_drawio(spec, regenerated)
                    write_drawio(spec, regenerated_again)
                    self.assertEqual(regenerated.read_bytes(), regenerated_again.read_bytes())
                    self.assertEqual(
                        semantic_cell_snapshot(drawio_path),
                        semantic_cell_snapshot(regenerated),
                    )



if __name__ == "__main__":
    unittest.main()
