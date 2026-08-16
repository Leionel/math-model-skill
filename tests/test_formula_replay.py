"""Regression tests for numeric equation back-substitution."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa.check_formula_replay import evaluate_formula_replay  # noqa: E402
from qa.check_math_writing import evaluate_math_writing  # noqa: E402
from pdf.check_math_pdf_consistency import check_pdf_math_consistency  # noqa: E402
from qa.validate_contracts import _validate  # noqa: E402
from test_competition_upgrades import base_contract  # noqa: E402


class FormulaReplayTest(unittest.TestCase):
    def replay_contract(self) -> dict[str, Any]:
        contract = base_contract()
        equation = contract["models"][0]["plan_details"]["equation_plan"][0]
        equation.update({
            "expression_or_derivation": "demand + fixed_cost",
            "variables": ["demand", "fixed_cost"],
            "verification": {
                "symbol_check": "PASS",
                "domain_check": "PASS",
                "unit_check": "PASS",
                "numeric_replay": [
                    {
                        "case_id": "REPLAY-Q1-COST-01",
                        "expression": "demand + fixed_cost",
                        "substitutions": {"demand": 12.0, "fixed_cost": 5.0},
                        "expected": 17.0,
                        "unit": "CNY",
                        "abs_tolerance": 1e-12,
                        "rel_tolerance": 1e-9,
                        "source_locator": "results/raw_results.json:cost",
                        "paper_section_markers": ["Formula q1"],
                        "paper_tokens": ["Total cost = 17.0"],
                        "forbidden_tokens": ["Total cost = 16.5"],
                    }
                ],
            },
        })
        return contract

    def test_schema_accepts_numeric_replay_case(self) -> None:
        schema_path = ROOT / "schemas" / "model_contract.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        errors: list[str] = []
        _validate(self.replay_contract(), schema, schema, "$", errors)
        self.assertEqual(errors, [])

    def test_back_substitution_and_paper_anchor_pass(self) -> None:
        errors, warnings, details = evaluate_formula_replay(
            self.replay_contract(),
            "Formula q1\nTotal cost = 17.0 CNY\n",
            require_replay=True,
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(details["cases_total"], 1)
        self.assertEqual(details["paper_check"]["status"], "checked")

    def test_numeric_mismatch_is_rejected(self) -> None:
        contract = self.replay_contract()
        contract["models"][0]["plan_details"]["equation_plan"][0]["verification"]["numeric_replay"][0]["expected"] = 16.5
        errors, _, details = evaluate_formula_replay(contract, require_replay=True)
        self.assertTrue(any("replay mismatch" in error for error in errors))
        self.assertEqual(details["failed_cases"], 1)

    def test_paper_anchor_drift_is_rejected(self) -> None:
        errors, _, _ = evaluate_formula_replay(
            self.replay_contract(),
            "Formula q1\nTotal cost = 16.5 CNY\n",
            require_replay=True,
        )
        self.assertTrue(any("missing required token" in error for error in errors))
        self.assertTrue(any("forbidden token" in error for error in errors))

    def test_partial_or_missing_replay_is_not_silently_promoted(self) -> None:
        errors, warnings, _ = evaluate_formula_replay(base_contract(), require_replay=True)
        self.assertTrue(any("numeric replay is required" in error for error in errors))
        self.assertEqual(warnings, [])

    def test_unsafe_expression_is_rejected(self) -> None:
        contract = self.replay_contract()
        case = contract["models"][0]["plan_details"]["equation_plan"][0]["verification"]["numeric_replay"][0]
        case["expression"] = "__import__('os').system('whoami')"
        errors, _, _ = evaluate_formula_replay(contract, require_replay=True)
        self.assertTrue(any("replay failed" in error for error in errors))

    def test_formal_mechanism_unit_must_bind_replay_case(self) -> None:
        contract = self.replay_contract()
        plan = {
            "claims": [{"claim_id": "C1", "question_id": "q1"}],
            "argument_units": [{
                "unit_id": "U-FORM",
                "section_id": "results.q1",
                "rhetorical_role": "mechanism_derivation",
                "claim_ids": ["C1"],
                "evidence_ids": ["E1"],
                "prerequisite_unit_ids": [],
                "model_ids": ["M1"],
                "equation_ids": ["EQ-OBJ"],
                "math_locators": ["EQ-OBJ"],
                "expected_reader_judgment": "The formula is numerically checked.",
                "boundary": "Declared formula inputs.",
                "target_words": 60,
            }],
        }
        errors, _, _ = evaluate_math_writing(contract, plan, "EQ-OBJ", require_replay_bindings=True)
        self.assertTrue(any("must bind numeric replay case" in error for error in errors))
        plan["argument_units"][0]["replay_case_ids"] = ["REPLAY-Q1-COST-01"]
        errors, _, _ = evaluate_math_writing(contract, plan, "EQ-OBJ", require_replay_bindings=True)
        self.assertEqual(errors, [])

    def test_rendered_pdf_text_reuses_formula_anchor_gate(self) -> None:
        errors, warnings, details = check_pdf_math_consistency(
            self.replay_contract(),
            "Formula q1\nTotal cost = 17.0 CNY\n",
            require_formula_replay=True,
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(details["formula_replay"]["paper_check"]["status"], "checked")

        errors, _, _ = check_pdf_math_consistency(
            self.replay_contract(),
            "Formula q1\nTotal cost = 16.5 CNY\n",
            require_formula_replay=True,
        )
        self.assertTrue(any("paper section is missing" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
