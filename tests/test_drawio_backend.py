#!/usr/bin/env python3
"""Focused regression tests for the native draw.io diagram backend."""

from __future__ import annotations

import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from figures.generate_drawio import PALETTES, _role_style, build_drawio_tree, write_drawio


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


class DrawioBackendTest(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
