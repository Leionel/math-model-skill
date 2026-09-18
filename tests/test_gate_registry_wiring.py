from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gate_order  # noqa: E402
import v2_gate_runtime  # noqa: E402
import verifiers  # noqa: E402
from verifiers.registry import VerifierContractError  # noqa: E402


class GateOrderSingleSourceTest(unittest.TestCase):
    def test_all_surfaces_share_one_tuple_object(self) -> None:
        import check_gates
        import harness
        import harness_status
        from mcp_tools import state as mcp_state

        for surface in (check_gates.GATE_ORDER, harness.GATE_ORDER, harness_status.GATE_ORDER, mcp_state._GATE_ORDER, verifiers.GATES):
            with self.subTest(surface=getattr(surface, "__module__", "verifiers")):
                self.assertIs(surface, gate_order.GATE_ORDER)


class M1RegistryWiringTest(unittest.TestCase):
    def test_resolved_entrypoints_match_the_legacy_hardcoded_paths(self) -> None:
        errors: list[str] = []
        scripts = v2_gate_runtime._v2_registry_entry_scripts(errors)
        self.assertEqual(errors, [])
        self.assertEqual(
            scripts,
            {
                "unit-consistency": str((ROOT / "scripts" / "qa" / "check_units.py").resolve()),
                "artifact-freshness": str((ROOT / "scripts" / "qa" / "check_artifact_dag.py").resolve()),
            },
        )

    def test_broken_registry_fails_closed(self) -> None:
        with mock.patch.object(verifiers.registry, "load_registry", side_effect=VerifierContractError(["boom"])):
            errors: list[str] = []
            scripts = v2_gate_runtime._v2_registry_entry_scripts(errors)
        self.assertEqual(scripts, {})
        self.assertTrue(any("verifier registry" in error and "boom" in error for error in errors), errors)

    def test_missing_declaration_fails_closed(self) -> None:
        with mock.patch.object(verifiers.registry, "load_registry", return_value={}):
            errors: list[str] = []
            scripts = v2_gate_runtime._v2_registry_entry_scripts(errors)
        self.assertEqual(scripts, {})
        self.assertEqual(
            sorted(error for error in errors if "no declaration for" in error),
            ["verifier registry: no declaration for artifact-freshness", "verifier registry: no declaration for unit-consistency"],
        )


if __name__ == "__main__":
    unittest.main()
