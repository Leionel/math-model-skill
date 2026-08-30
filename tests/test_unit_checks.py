"""R5.1 declared-unit consistency checker: authoring contradictions are
blocked and the checker is wired into the v2 M1 gate."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "qa"))

from check_units import UnitParseError, check_contract, parse_unit  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "wp2_runtime"


def _contract(**overrides) -> dict:
    contract = {
        "schema_version": "1.3",
        "project_id": "unit-test",
        "run_id": "run-1",
        "status": "ready",
        "models": [
            {
                "model_id": "M-1",
                "variables": [{"symbol": "v", "meaning": "speed", "unit": "m/s", "domain": "R+", "role": "state"}],
                "plan_details": {
                    "equation_plan": [
                        {
                            "equation_id": "EQ-1",
                            "purpose": "kinetic energy",
                            "expression_or_derivation": "E = 1/2 m v^2",
                            "variables": ["v"],
                            "assumptions": [],
                        }
                    ],
                    "parameter_plan": [],
                },
                "validation_obligations": [],
            }
        ],
    }
    contract.update(overrides)
    return contract


class CheckContractTest(unittest.TestCase):
    def test_clean_contract_passes(self) -> None:
        report = check_contract(_contract())
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["checked"]["symbols"], 1)
        self.assertEqual(report["checked"]["equations"], 1)

    def test_symbol_unit_conflict_is_blocked(self) -> None:
        contract = _contract()
        contract["models"][0]["plan_details"]["parameter_plan"] = [
            {"parameter": "v", "provenance": "assumed", "unit": "km/h", "uncertainty_or_range": "fixed"}
        ]
        report = check_contract(contract)
        self.assertFalse(report["ok"])
        self.assertTrue(any("unit conflict" in message and "'v'" in message for message in report["errors"]))

    def test_unit_balance_imbalance_is_blocked(self) -> None:
        contract = _contract()
        contract["models"][0]["plan_details"]["equation_plan"][0]["unit_balance"] = {
            "left": "kg*m^2/s^2",
            "right": "kg",
        }
        report = check_contract(contract)
        self.assertFalse(report["ok"])
        self.assertTrue(any("unit imbalance" in message for message in report["errors"]))

    def test_balanced_equation_passes(self) -> None:
        contract = _contract()
        contract["models"][0]["plan_details"]["equation_plan"][0]["unit_balance"] = {
            "left": "J",
            "right": "J",
        }
        report = check_contract(contract)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["checked"]["unit_balances"], 1)

    def test_derived_and_base_unit_expressions_are_dimensionally_equivalent(self) -> None:
        contract = _contract()
        contract["models"][0]["plan_details"]["equation_plan"][0]["unit_balance"] = {
            "left": "J",
            "right": "kg*m^2/s^2",
        }
        report = check_contract(contract)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["method"], "declared_unit_dimension_algebra")

    def test_equivalent_derived_declarations_do_not_conflict(self) -> None:
        contract = _contract()
        contract["models"][0]["variables"] = [
            {"symbol": "E", "meaning": "energy", "unit": "J", "domain": "R+", "role": "state"}
        ]
        contract["models"][0]["plan_details"]["parameter_plan"] = [
            {
                "parameter": "E",
                "provenance": "derived",
                "unit": "kg m² s⁻²",
                "uncertainty_or_range": "fixed",
            }
        ]
        report = check_contract(contract)
        self.assertTrue(report["ok"], report["errors"])

    def test_dimensionally_equal_but_different_scales_require_conversion(self) -> None:
        contract = _contract()
        contract["models"][0]["plan_details"]["equation_plan"][0]["unit_balance"] = {
            "left": "m/s",
            "right": "km/h",
        }
        report = check_contract(contract)
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(any("scales differ" in message for message in report["warnings"]))

    def test_scale_mismatch_for_one_symbol_is_blocked(self) -> None:
        contract = _contract()
        contract["models"][0]["plan_details"]["parameter_plan"] = [
            {"parameter": "v", "provenance": "assumed", "unit": "km/h", "uncertainty_or_range": "fixed"}
        ]
        report = check_contract(contract)
        self.assertFalse(report["ok"])
        self.assertTrue(any("unit conflict" in message for message in report["errors"]))

    def test_custom_composite_unit_is_supported(self) -> None:
        signature = parse_unit("item/day")
        self.assertIsNotNone(signature)
        self.assertIn(("custom:item", 1), signature.dimensions)
        self.assertIn(("time", -1), signature.dimensions)

    def test_malformed_unit_expression_is_blocked(self) -> None:
        contract = _contract()
        contract["models"][0]["variables"][0]["unit"] = "kg*/s"
        report = check_contract(contract)
        self.assertFalse(report["ok"])
        self.assertTrue(any("invalid unit declaration" in message for message in report["errors"]))

    def test_non_integer_exponent_is_rejected(self) -> None:
        with self.assertRaises(UnitParseError):
            parse_unit("m^0.5")

    def test_output_unit_conflict_is_blocked(self) -> None:
        contract = _contract()
        equation = contract["models"][0]["plan_details"]["equation_plan"][0]
        equation["outputs"] = ["v"]
        equation["output_unit"] = "kg"
        report = check_contract(contract)
        self.assertFalse(report["ok"])
        self.assertTrue(any("output_unit" in message for message in report["errors"]))

    def test_acceptance_unit_conflict_is_blocked(self) -> None:
        contract = _contract()
        contract["models"][0]["validation_obligations"] = [
            {
                "obligation_id": "VAL-1",
                "category": "feasibility",
                "acceptance": {"left_metric_id": "v", "operator": "<=", "right": "30", "unit": "kg"},
            }
        ]
        report = check_contract(contract)
        self.assertFalse(report["ok"])
        self.assertTrue(any("acceptance unit" in message for message in report["errors"]))

    def test_high_risk_equation_without_unit_declarations_warns(self) -> None:
        contract = _contract()
        contract["models"][0]["plan_details"]["equation_plan"][0]["math_risk"] = "high"
        report = check_contract(contract)
        self.assertTrue(report["ok"])
        self.assertTrue(any("math_risk=high" in message for message in report["warnings"]))

    def test_same_symbol_may_have_different_units_in_independent_models(self) -> None:
        first = _contract()["models"][0]
        second = json.loads(json.dumps(first))
        second["model_id"] = "M-2"
        second["variables"][0]["unit"] = "km/h"
        report = check_contract(_contract(models=[first, second]))
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["scope"], "within_each_model")
        self.assertIn("does not infer dimensions from equation text", report["boundary"])


class CheckUnitsCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="check-units-")
        self.project = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _run(self, contract: dict) -> subprocess.CompletedProcess[str]:
        path = self.project / "model_contract.json"
        path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "qa" / "check_units.py"),
             "--project-root", str(self.project), "--model-contract", "model_contract.json", "--strict"],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )

    def test_clean_contract_exits_zero(self) -> None:
        result = self._run(_contract())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_wrong_dimension_contract_exits_nonzero(self) -> None:
        contract = _contract()
        contract["models"][0]["plan_details"]["equation_plan"][0]["unit_balance"] = {
            "left": "m/s",
            "right": "kg",
        }
        result = self._run(contract)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertFalse(report["ok"])
        self.assertTrue(any("unit imbalance" in message for message in report["errors"]))


class GateWiringTest(unittest.TestCase):
    """The v2 M1 gate blocks a wrong-dimension model contract."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="unit-gate-")
        self.project = Path(self.temp.name)
        shutil.copy2(FIXTURE / "competition_profile.json", self.project / "competition_profile.json")
        shutil.copy2(FIXTURE / "rules.txt", self.project / "rules.txt")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_project(self, contract: dict) -> None:
        (self.project / "model.json").write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        manifest = {
            "schema_version": "2.0", "project_id": "wp2-project", "run_id": "run-1", "status": "active",
            "stage": "results", "preset": "research", "profile_overrides": {},
            "competition_profile_ref": {"path": "competition_profile.json", "profile_id": "wp2-fixture"},
            "roots": {"model_contract": {"path": "model.json"}},
            "control": {"selection_policy": {"owner": "run_manifest.control", "rule": "exactly one selected receipt", "version": "2.0"}},
            "safety": {}, "ai_usage": [], "human_checkpoints": [],
        }
        (self.project / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def _gate(self, name: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "qa" / "check_gates.py"),
             "--manifest", "run_manifest.json", "--project-root", str(self.project), "--gate", name],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )

    def test_v2_m1_surfaces_unit_conflict_from_model_contract(self) -> None:
        contract = _contract(project_id="wp2-project")
        contract["models"][0]["plan_details"]["parameter_plan"] = [
            {"parameter": "v", "provenance": "assumed", "unit": "km/h", "uncertainty_or_range": "fixed"}
        ]
        self._write_project(contract)
        result = self._gate("m1")
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertTrue(
            any("unit conflict" in message for message in report["errors"]),
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
