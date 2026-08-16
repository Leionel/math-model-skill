from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa.check_math_semantics import evaluate_contract_semantics  # noqa: E402


def model(objective: dict | None) -> dict:
    row = {
        "model_id": "M1",
        "problem_type": "optimization",
        "objective": "minimize cost",
        "algorithm": "enumeration",
    }
    if objective is not None:
        row["objective_contract"] = objective
    return row


class ObjectiveSemanticsTest(unittest.TestCase):
    def test_unique_claim_with_flat_objective_is_rejected(self) -> None:
        errors, _ = evaluate_contract_semantics({"models": [model({
            "objective_id": "OBJ-1", "direction": "minimize", "declared_form": "min f(x)", "implemented_form": "min f(x)",
            "equivalence_status": "verified", "recompute_test_ids": ["T1"], "uniqueness_claim": "unique",
            "objective_diagnostics": {"method": "grid", "tolerance": 1e-9, "candidate_count": 3, "objective_spread": 0.0, "status": "verified"},
        })]}, require_objective_contract=True)
        self.assertTrue(any("tied candidates" in error for error in errors), errors)

    def test_declared_and_implemented_objective_must_be_equivalent(self) -> None:
        errors, _ = evaluate_contract_semantics({"models": [model({
            "objective_id": "OBJ-1", "direction": "minimize", "declared_form": "clinical risk", "implemented_form": "SSE",
            "equivalence_status": "unverified", "recompute_test_ids": ["T1"], "uniqueness_claim": "not_claimed",
        })]}, require_objective_contract=True)
        self.assertTrue(any("equivalence is not verified" in error for error in errors), errors)

    def test_piecewise_model_requires_domain_coverage(self) -> None:
        errors, _ = evaluate_contract_semantics({"models": [model({
            "objective_id": "OBJ-1", "direction": "minimize", "declared_form": "piecewise", "implemented_form": "piecewise",
            "equivalence_status": "verified", "recompute_test_ids": ["T1"], "uniqueness_claim": "not_claimed",
            "piecewise_partitions": [{"partition_id": "P1", "condition": "x <= 0", "boundary_status": "verified", "status": "verified"}],
            "piecewise_coverage": {"domain": "all real x", "partition_ids": ["P1"], "coverage_status": "failed", "overlap_status": "verified"},
        })]}, require_objective_contract=True)
        self.assertTrue(any("coverage/overlap" in error for error in errors), errors)

    def test_comparison_is_not_an_ensemble_by_label(self) -> None:
        row = model({
            "objective_id": "OBJ-1", "direction": "feasibility_only", "declared_form": "compare models", "implemented_form": "compare models",
            "equivalence_status": "verified", "recompute_test_ids": ["T1"], "uniqueness_claim": "not_claimed",
        })
        row["identity"] = {
            "canonical_name": "Logistic and RF comparison", "mathematical_class": "model comparison", "objective_form": "comparison",
            "forbidden_aliases": [], "composition_type": "ensemble",
        }
        row["algorithm"] = "fit Logistic Regression and Random Forest separately"
        errors, _ = evaluate_contract_semantics({"models": [row]}, require_objective_contract=True)
        self.assertTrue(any("labeled ensemble" in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
