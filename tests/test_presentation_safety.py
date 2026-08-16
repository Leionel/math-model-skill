"""Regression tests for direction-safe result presentation."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from latex.generate_values_tex import format_value  # noqa: E402
from qa.check_presentation_safety import evaluate_presentation_safety  # noqa: E402
from qa.validate_contracts import _validate  # noqa: E402


class PresentationSafetyTest(unittest.TestCase):
    def frozen(self) -> dict[str, Any]:
        return {
            "run_id": "run-1",
            "results": [{
                "result_id": "R1",
                "value": 1.234,
                "unit": "m",
                "precision": 3,
                "display_value": "1.234",
            }],
        }

    def presentation(self, rounding: str = "floor", safe_side: str = "lower_bound") -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "run_id": "run-1",
            "frozen_results": {"path": "frozen.json", "sha256": "0" * 64},
            "entries": [{
                "presentation_id": "P1",
                "result_id": "R1",
                "macro": "Distance",
                "format": "number",
                "unit_display": "~m",
                "rounding": rounding,
                "digits": 1,
                "safe_side": safe_side,
                "feasibility_recheck": {
                    "expression": "x",
                    "display_symbol": "x",
                    "operator": "<=" if safe_side == "lower_bound" else ">=",
                    "limit": 1.2 if safe_side == "lower_bound" else 1.3,
                    "unit": "m",
                    "abs_tolerance": 0.0,
                    "rel_tolerance": 0.0,
                    "source_locator": "constraint C1",
                },
                "locations": ["body"],
            }],
            "status": "ready",
        }

    def test_schema_accepts_safe_presentation_fields(self) -> None:
        schema = json.loads((ROOT / "schemas" / "presentation_contract.schema.json").read_text(encoding="utf-8"))
        errors: list[str] = []
        _validate(self.presentation(), schema, schema, "$", errors)
        self.assertEqual(errors, [])

    def test_floor_lower_bound_and_ceil_upper_bound_pass(self) -> None:
        errors, warnings, details = evaluate_presentation_safety(self.presentation(), self.frozen())
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(details["safe_entries_checked"], 1)

        upper = self.presentation(rounding="ceil", safe_side="upper_bound")
        errors, _, _ = evaluate_presentation_safety(upper, self.frozen())
        self.assertEqual(errors, [])

    def test_half_up_cannot_claim_lower_bound_safety(self) -> None:
        errors, _, _ = evaluate_presentation_safety(self.presentation(rounding="half_up"), self.frozen())
        self.assertTrue(any("requires rounding=floor" in error for error in errors))

    def test_display_value_is_rechecked_after_rounding(self) -> None:
        contract = self.presentation()
        contract["entries"][0]["feasibility_recheck"]["limit"] = 1.1
        errors, _, _ = evaluate_presentation_safety(contract, self.frozen())
        self.assertTrue(any("recheck failed" in error for error in errors))

    def test_generator_uses_directional_decimal_rounding(self) -> None:
        result = self.frozen()["results"][0]
        self.assertIn("1.2", format_value(result, self.presentation()["entries"][0]))
        upper = self.presentation(rounding="ceil", safe_side="upper_bound")
        self.assertIn("1.3", format_value(result, upper["entries"][0]))


if __name__ == "__main__":
    unittest.main()
