"""Regression tests for grid-plus-continuous extremum certificates."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa.check_extremum_certificate import evaluate_extremum_certificate  # noqa: E402
from qa.validate_contracts import _validate  # noqa: E402


class ExtremumCertificateTest(unittest.TestCase):
    def certificate(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "certificate_id": "EXT-Q1-01",
            "run_id": "run-1",
            "question_id": "q1",
            "status": "completed",
            "objective": "max",
            "variables": ["x"],
            "domain": {"x": {"lower": 0.0, "upper": 10.0}},
            "grid": {
                "points": [{"x": 0.0}, {"x": 2.0}, {"x": 4.0}, {"x": 6.0}, {"x": 8.0}, {"x": 10.0}],
                "values": [0.0, 3.0, 5.0, 4.0, 1.0, 0.0],
                "best_index": 2,
                "best_point": {"x": 4.0},
                "best_value": 5.0,
                "source_artifact": "grid.json",
                "method": "uniform_grid",
            },
            "refinement": {
                "status": "completed",
                "intervals": {"x": {"lower": 3.0, "upper": 5.0}},
                "point": {"x": 4.2},
                "value": 5.1,
                "evaluations": 20,
                "source_artifact": "refinement.json",
                "method": "bounded_brent",
            },
            "tolerance": {"abs": 1e-9, "rel": 1e-6},
            "claim_level": "refined_candidate",
        }

    def test_schema_accepts_certificate(self) -> None:
        schema = json.loads((ROOT / "schemas" / "extremum_certificate.schema.json").read_text(encoding="utf-8"))
        errors: list[str] = []
        _validate(self.certificate(), schema, schema, "$", errors)
        self.assertEqual(errors, [])

    def test_grid_and_refinement_pass_with_existing_receipts(self) -> None:
        with tempfile.TemporaryDirectory(prefix="extremum-certificate-") as temp:
            root = Path(temp)
            (root / "grid.json").write_text("grid receipt\n", encoding="utf-8")
            (root / "refinement.json").write_text("refinement receipt\n", encoding="utf-8")
            errors, warnings, details = evaluate_extremum_certificate(self.certificate(), root)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(details["certificate_level"], "grid_plus_continuous_candidate")
        self.assertEqual(details["global_optimum_proof"], "not_automated")

    def test_grid_best_and_refinement_candidate_are_rechecked(self) -> None:
        contract = self.certificate()
        contract["grid"]["best_index"] = 1
        contract["refinement"]["point"] = {"x": 8.0}
        with tempfile.TemporaryDirectory(prefix="extremum-certificate-fail-") as temp:
            root = Path(temp)
            (root / "grid.json").write_text("grid receipt\n", encoding="utf-8")
            (root / "refinement.json").write_text("refinement receipt\n", encoding="utf-8")
            errors, _, _ = evaluate_extremum_certificate(contract, root)
        self.assertTrue(any("best_index" in error for error in errors))
        self.assertTrue(any("outside its refinement interval" in error for error in errors))

    def test_global_claim_is_not_accepted_as_a_self_attested_fact(self) -> None:
        contract = deepcopy(self.certificate())
        contract["claim_level"] = "global"
        with tempfile.TemporaryDirectory(prefix="extremum-certificate-global-") as temp:
            root = Path(temp)
            (root / "grid.json").write_text("grid receipt\n", encoding="utf-8")
            (root / "refinement.json").write_text("refinement receipt\n", encoding="utf-8")
            errors, _, _ = evaluate_extremum_certificate(contract, root)
        self.assertTrue(any("global claim is not accepted" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
