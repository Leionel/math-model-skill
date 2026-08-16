"""Regression tests for question-scoped parameter and event consistency."""

from __future__ import annotations

import unittest
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa.check_scope_consistency import evaluate_scope_consistency
from qa.validate_contracts import _validate
from test_competition_upgrades import base_contract


class ScopeConsistencyTest(unittest.TestCase):
    def scoped_contract(self) -> dict[str, Any]:
        contract = base_contract()
        # These values mirror the 814 regression: Q4 uses p=1.7 and the
        # corrected time origin is T1; the generated Markdown/PDF contained
        # the Q1 value p=0.55 and the old origin Tc.
        contract["questions"][0]["question_id"] = "q4"
        contract["models"][0]["question_id"] = "q4"
        contract["models"][0]["scope_ids"] = ["S-Q4"]
        contract["models"][0]["event_ids"] = ["E-Q4-ORIGIN"]
        contract["scope_contract"] = {
            "schema_version": "1.0",
            "status": "ready",
            "scopes": [
                {
                    "scope_id": "S-Q4",
                    "question_id": "q4",
                    "title": "Question 4 official parameters",
                    "parameters": [
                        {
                            "parameter_id": "P-PITCH",
                            "symbol": "p",
                            "meaning": "pitch",
                            "unit": "m",
                            "value": 1.7,
                            "source_locator": "814 source body.tex:27",
                            "aliases": ["pitch"],
                            "required_tokens": ["p=1.7"],
                            "forbidden_tokens": ["p=0.55"],
                        }
                    ],
                    "event_ids": ["E-Q4-ORIGIN"],
                    "paper_section_markers": ["Q4 scope"],
                    "required_tokens": ["p=1.7"],
                    "forbidden_tokens": ["pitch=0.55"],
                    "source_locator": "814 source body.tex:27",
                }
            ],
            "events": [
                {
                    "event_id": "E-Q4-ORIGIN",
                    "question_id": "q4",
                    "title": "Time origin",
                    "definition": "t=0 is T1",
                    "event_type": "reference_event",
                    "coordinate_frame": "global frame",
                    "time_origin": "T1",
                    "paper_section_markers": ["Q4 event"],
                    "required_tokens": ["t=0 is T1"],
                    "forbidden_tokens": ["t=0 is Tc"],
                    "source_locator": "814 source body.tex:530",
                }
            ],
        }
        return contract

    def test_schema_accepts_scope_extension(self) -> None:
        contract = self.scoped_contract()
        schema = json.loads(self._schema_path().read_text(encoding="utf-8"))
        errors: list[str] = []
        _validate(contract, schema, schema, "$", errors)
        self.assertEqual(errors, [])

    def test_correct_scoped_paper_passes(self) -> None:
        errors, warnings, details = evaluate_scope_consistency(
            self.scoped_contract(),
            "Q4 scope\np=1.7\nQ4 event\nt=0 is T1\n",
            require_contract=True,
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(details["paper_check"]["status"], "checked")

    def test_wrong_parameter_and_time_origin_are_rejected(self) -> None:
        errors, _, _ = evaluate_scope_consistency(
            self.scoped_contract(),
            "Q4 scope\np=0.55\nQ4 event\nt=0 is Tc\n",
            require_contract=True,
        )
        self.assertTrue(any("p=1.7" in error for error in errors))
        self.assertTrue(any("p=0.55" in error for error in errors))
        self.assertTrue(any("t=0 is T1" in error for error in errors))
        self.assertTrue(any("t=0 is Tc" in error for error in errors))

    def test_model_scope_question_mismatch_is_rejected(self) -> None:
        contract = self.scoped_contract()
        contract["models"][0]["question_id"] = "q2"
        errors, _, _ = evaluate_scope_consistency(contract, require_contract=True)
        self.assertTrue(any("scope S-Q4" in error and "q2" in error for error in errors))

    def test_missing_contract_is_optional_or_required_by_profile(self) -> None:
        contract = base_contract()
        errors, warnings, details = evaluate_scope_consistency(contract)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(details["status"], "NOT_DECLARED")

        errors, _, details = evaluate_scope_consistency(contract, require_contract=True)
        self.assertTrue(any("scope_contract is required" in error for error in errors))
        self.assertEqual(details["status"], "MISSING_REQUIRED")

    def test_scope_contract_does_not_mutate_source_contract(self) -> None:
        contract = self.scoped_contract()
        original = deepcopy(contract)
        evaluate_scope_consistency(contract, "Q4 scope\np=1.7\nQ4 event\nt=0 is T1\n")
        self.assertEqual(contract, original)

    @staticmethod
    def _schema_path() -> Path:
        return ROOT / "schemas" / "model_contract.schema.json"


if __name__ == "__main__":
    unittest.main()
