"""Regression tests for fail-closed figure classification and topology-aware backends."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from figures.tool_router import route_figure  # noqa: E402


class FigureRoutingTest(unittest.TestCase):
    def test_simple_workflow_uses_ranked_pptx_composition(self) -> None:
        route = route_figure(
            "auto",
            "workflow",
            topology={
                "node_count": 5,
                "dag_depth": 3,
                "branch_count": 1,
                "feedback_edges": 0,
                "parallel_lanes": 1,
                "density": "medium",
                "target_aspect_ratio": "wide",
                "reading_order": "left_to_right",
            },
        )

        self.assertEqual(route["default_tool"], "pptx_template")
        self.assertEqual(route["backend_selection"]["selection"], "reference_guided_pptx")
        self.assertEqual(route["reference"]["reference_id"], "paper_staged_method")
        self.assertEqual(len(route["reference_candidates"]), 3)
        self.assertTrue(route["reference_candidates"][0]["reasons"])
        self.assertEqual(
            [row["card_id"] for row in route["figure_reference_cards"]],
            ["FC-MECH-01"],
        )

    def test_complex_dag_uses_drawio(self) -> None:
        route = route_figure(
            "auto",
            "workflow",
            topology={
                "node_count": 14,
                "dag_depth": 5,
                "branch_count": 4,
                "feedback_edges": 0,
                "parallel_lanes": 3,
                "density": "high",
                "target_aspect_ratio": "wide",
            },
        )

        self.assertEqual(route["default_tool"], "drawio")
        self.assertEqual(route["selection"], "complex_dag")
        self.assertIn("multiple complex topology signals", route["backend_selection"]["reasons"][0])

    def test_feedback_optimization_loop_uses_drawio(self) -> None:
        route = route_figure(
            "auto",
            "optimization_loop",
            topology={"node_count": 5, "feedback_edges": 1, "parallel_lanes": 1},
        )

        self.assertEqual(route["default_tool"], "drawio")
        self.assertEqual(route["selection"], "feedback_sensitive_topology")
        self.assertIn("feedback_edges=1", route["backend_selection"]["reasons"][0])

    def test_data_trend_uses_deterministic_plotting(self) -> None:
        route = route_figure("auto", "trend")

        self.assertEqual(route["kind"], "data")
        self.assertEqual(route["default_tool"], "python_plotting")
        self.assertIn("FC-COMPARE-01", [row["card_id"] for row in route["figure_reference_cards"]])

    def test_sensitivity_route_loads_sensitivity_mechanism_card(self) -> None:
        route = route_figure("auto", "sensitivity_curve")

        self.assertEqual(route["default_tool"], "python_plotting")
        self.assertEqual(
            [row["card_id"] for row in route["figure_reference_cards"]],
            ["FC-SENS-01"],
        )

    def test_unknown_semantic_type_fails_closed(self) -> None:
        route = route_figure("auto", "unmapped visual grammar")

        self.assertEqual(route["kind"], "unresolved_figure_type")
        self.assertIsNone(route["default_tool"])
        self.assertEqual(route["message"], "cannot confidently classify figure")
        self.assertEqual(route["suggested_candidates"], ["data", "diagram", "illustration"])
        self.assertNotIn("reference", route)

    def test_illustration_uses_illustration_channel(self) -> None:
        route = route_figure("auto", "physical_mechanism")

        self.assertEqual(route["kind"], "illustration")
        self.assertEqual(route["default_tool"], "image_generation")


if __name__ == "__main__":
    unittest.main()
