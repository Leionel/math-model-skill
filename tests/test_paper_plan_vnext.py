"""Focused regression coverage for Paper Plan v1.3 and shared scopes."""

from __future__ import annotations

import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from qa.check_paper_readiness import evaluate_readiness  # noqa: E402
from qa.validate_contracts import _cross_references, _validate_document  # noqa: E402
import test_p0_harness as p0_harness  # noqa: E402


PAPER_PLAN_SCHEMA = ROOT / "schemas" / "paper_plan.schema.json"


class PaperPlanVNextTest(unittest.TestCase):
    """Pin the v1.2 compatibility boundary while exercising v1.3 semantics."""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.temp_dir = tempfile.TemporaryDirectory(prefix="math-paper-plan-vnext-")
        cls.project = Path(cls.temp_dir.name)
        cls.fixture = p0_harness.P0HarnessTest(methodName="runTest")
        cls.paths = cls.fixture.build_fixture(cls.project)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp_dir.cleanup()
        super().tearDownClass()

    def legacy_plan(self) -> dict[str, Any]:
        return p0_harness.read_json(self.paths["plan"])

    def v13_plan(self) -> dict[str, Any]:
        plan = deepcopy(self.legacy_plan())
        plan["schema_version"] = "1.3"
        plan.pop("depth_budget", None)
        for index, unit in enumerate(plan["argument_units"]):
            unit.pop("target_words", None)
            unit["depth_priority"] = {
                "level": "core" if index == 0 else "supporting",
                "rationale": "The unit supports the tested argument chain.",
            }
        return plan

    def schema_errors(self, plan: dict[str, Any]) -> tuple[list[str], str]:
        plan_path = self.project / "paper_plan_vnext_test.json"
        p0_harness.write_json(plan_path, plan)
        _, errors, validator = _validate_document(plan_path, PAPER_PLAN_SCHEMA)
        return errors, validator

    def test_v12_fixture_remains_compatible_with_fallback_schema_validation(self) -> None:
        errors, validator = self.schema_errors(self.legacy_plan())

        self.assertEqual(validator, "fallback")
        self.assertEqual(errors, [])

    def test_v13_plan_accepts_depth_priority_without_pre_draft_word_quotas(self) -> None:
        plan = self.v13_plan()
        errors, validator = self.schema_errors(plan)

        self.assertEqual(validator, "fallback")
        self.assertEqual(errors, [])
        self.assertNotIn("depth_budget", plan)
        self.assertTrue(all("target_words" not in unit for unit in plan["argument_units"]))

    def test_v13_plan_requires_depth_priority(self) -> None:
        plan = self.v13_plan()
        del plan["argument_units"][0]["depth_priority"]

        errors, validator = self.schema_errors(plan)

        self.assertEqual(validator, "fallback")
        self.assertTrue(errors)
        self.assertTrue(any("oneOf" in error for error in errors), errors)

    def test_v13_figure_requires_audience_but_v12_remains_compatible(self) -> None:
        figure = {
            "figure_id": "FIG-1", "kind": "data", "claim_ids": ["C1"],
            "evidence_ids": ["E1"], "purpose": "Compare outcomes", "why_figure": "Shows scale",
            "message": "A is lower", "comparison": "A versus B", "visual_encoding": "bars",
            "selection_rule": "All scenarios", "data_artifacts": ["figures/a.png"],
            "panel_map": {"A": "Comparison"}, "statistical_definition": "Frozen values",
            "paper_location": "results", "caption_claim": "A is lower", "accessibility": {
                "grayscale_safe": True, "colorblind_safe": True, "dual_axis": False,
                "dual_axis_justification": None,
            }, "qa_status": "pending",
        }
        legacy = self.legacy_plan()
        legacy["figures"] = [deepcopy(figure)]
        legacy_errors, _ = self.schema_errors(legacy)
        self.assertEqual(legacy_errors, [])

        current = self.v13_plan()
        current["figures"] = [deepcopy(figure)]
        missing_errors, _ = self.schema_errors(current)
        self.assertTrue(missing_errors)

        current["figures"][0]["audience"] = "scientific_argument"
        current_errors, _ = self.schema_errors(current)
        self.assertEqual(current_errors, [])

    def test_scope_cardinality_is_rejected_by_fallback_schema_validation(self) -> None:
        plan = self.v13_plan()
        plan["argument_units"][0]["scope"] = {
            "type": "cross_question",
            "question_ids": ["q1"],
        }

        errors, validator = self.schema_errors(plan)

        self.assertEqual(validator, "fallback")
        self.assertTrue(any("oneOf" in error for error in errors), errors)

    def test_unknown_cross_question_scope_is_rejected_by_cross_references(self) -> None:
        plan = self.v13_plan()
        plan["argument_units"][0]["scope"] = {
            "type": "cross_question",
            "question_ids": ["q1", "q2"],
        }
        paths = {
            "model_contract": self.paths["model"],
            "run_manifest": self.paths["manifest"],
            "frozen_results": self.paths["frozen"],
            "evidence_registry": self.paths["evidence"],
            "paper_plan": self.paths["plan"],
        }

        errors, _ = _cross_references(
            p0_harness.read_json(self.paths["model"]),
            p0_harness.read_json(self.paths["manifest"]),
            p0_harness.read_json(self.paths["frozen"]),
            p0_harness.read_json(self.paths["evidence"]),
            plan,
            root=self.project,
            paths=paths,
        )

        self.assertTrue(
            any("scope references unknown question_id values: ['q2']" in error for error in errors),
            errors,
        )

    def test_cross_and_global_units_do_not_raise_unused_readiness_warnings(self) -> None:
        evidence = {"evidence": [{"evidence_id": "E1", "verification_status": "verified"}]}

        def unit(unit_id: str, role: str, claim_id: str) -> dict[str, Any]:
            return {
                "unit_id": unit_id,
                "rhetorical_role": role,
                "claim_ids": [claim_id],
                "evidence_ids": ["E1"],
            }

        units = [
            unit("AU-Q1-FORM", "mechanism_derivation", "C1"),
            unit("AU-Q1-RESULT", "result_observation", "C1"),
            unit("AU-Q1-VALID", "validation", "C1"),
            unit("AU-Q1-BOUNDARY", "boundary", "C1"),
            unit("AU-Q2-FORM", "mechanism_derivation", "C2"),
            unit("AU-Q2-RESULT", "result_observation", "C2"),
            unit("AU-Q2-VALID", "validation", "C2"),
            unit("AU-Q2-BOUNDARY", "boundary", "C2"),
            {
                **unit("AU-CROSS", "comparison", "C1"),
                "scope": {"type": "cross_question", "question_ids": ["q1", "q2"]},
            },
            {**unit("AU-GLOBAL", "boundary", "C1"), "scope": {"type": "global"}},
        ]
        plan = {
            "claims": [
                {"claim_id": "C1", "question_id": "q1"},
                {"claim_id": "C2", "question_id": "q2"},
            ],
            "argument_units": units,
            "figures": [],
            "tables": [],
            "readiness": {
                "stage": "technical_draft",
                "question_coverage": [
                    {
                        "question_id": "q1",
                        "formulation_unit_ids": ["AU-Q1-FORM"],
                        "result_unit_ids": ["AU-Q1-RESULT"],
                        "validation_unit_ids": ["AU-Q1-VALID"],
                        "interpretation_unit_ids": ["AU-Q1-BOUNDARY"],
                        "display_ids": [],
                    },
                    {
                        "question_id": "q2",
                        "formulation_unit_ids": ["AU-Q2-FORM"],
                        "result_unit_ids": ["AU-Q2-RESULT"],
                        "validation_unit_ids": ["AU-Q2-VALID"],
                        "interpretation_unit_ids": ["AU-Q2-BOUNDARY"],
                        "display_ids": [],
                    },
                ],
            },
        }

        errors, warnings, details = evaluate_readiness(plan, evidence)

        self.assertEqual(errors, [])
        self.assertFalse(any("argument units not assigned" in warning for warning in warnings), warnings)
        self.assertEqual(details["shared_scope_units"], ["AU-CROSS", "AU-GLOBAL"])


if __name__ == "__main__":
    unittest.main()
