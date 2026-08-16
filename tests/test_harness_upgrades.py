from __future__ import annotations

import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pdf.check_math_pdf_consistency import check_numeric_presence  # noqa: E402
from qa.run_deterministic_qa import apply_profile  # noqa: E402
from test_p0_harness import P0HarnessTest, read_json, write_json  # noqa: E402


class ApplyProfileTest(unittest.TestCase):
    def _args(self, profile: str) -> argparse.Namespace:
        return argparse.Namespace(
            profile=profile,
            require_first_draft_coverage=False,
            require_math_writing_coverage=False,
            require_derivation_integrity=False,
            require_scope_contract=False,
            require_formula_replay=False,
            require_replay_bindings=False,
            require_pdf_math_consistency=False,
            require_objective_contract=False,
            require_inference_role_consistency=False,
        )

    def test_baseline_turns_nothing_on(self) -> None:
        args = apply_profile(self._args("baseline"))
        self.assertFalse(any([args.require_formula_replay, args.require_scope_contract]))

    def test_enabled_and_strict_levels(self) -> None:
        enhanced = apply_profile(self._args("enhanced"))
        self.assertTrue(enhanced.require_first_draft_coverage)
        self.assertFalse(enhanced.require_formula_replay)
        strict = apply_profile(self._args("strict"))
        for name in (
            "require_first_draft_coverage", "require_math_writing_coverage", "require_derivation_integrity",
            "require_scope_contract", "require_formula_replay", "require_replay_bindings",
            "require_pdf_math_consistency", "require_objective_contract", "require_inference_role_consistency",
        ):
            self.assertTrue(getattr(strict, name), name)


class NumericPresenceTest(unittest.TestCase):
    def _frozen(self, display: str) -> dict:
        return {"results": [{"result_id": "R-Q1-01", "display_value": display}]}

    def test_present_wrapped_and_missing(self) -> None:
        pdf_text = "策略总遮蔽时长为 4.59 s，另一项为 1.39 s。\n表格里还有 13.00。"
        errors, _, details = check_numeric_presence(self._frozen("4.59"), pdf_text)
        self.assertEqual(errors, [])
        self.assertEqual(details["checked"], 1)

        errors, _, _ = check_numeric_presence(self._frozen("4.5\n9"), pdf_text.replace("4.59", "4.5\n9"))
        self.assertEqual(errors, [])

        errors, _, _ = check_numeric_presence(self._frozen("99.99"), pdf_text)
        self.assertEqual(len(errors), 1)
        self.assertIn("99.99", errors[0])

    def test_display_string_is_the_contract(self) -> None:
        errors, _, _ = check_numeric_presence(self._frozen("13.00"), "正文只写了 13")
        self.assertEqual(len(errors), 1)


class GateLagWarningTest(unittest.TestCase):
    """Artifacts-before-gate warnings were tried and deliberately withdrawn:
    the documented flow stages artifacts first and flips gates after check
    passes, so "artifact exists while gate pending" is normal, not a violation.
    The ordering rule (later gate pass requires earlier pass) already covers
    the dangerous case. Kept here as a tombstone so the idea is not retried
    blindly."""

    def test_no_gate_lag_warnings_on_normal_staged_flow(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-gatelag-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            manifest = read_json(paths["manifest"])
            manifest["status"] = "active"
            for gate in manifest.get("gates", {}).values():
                gate["status"] = "pending"
            roles = {row.get("role") for row in manifest.get("artifacts", [])}
            if "frozen_results" not in roles:
                manifest.setdefault("artifacts", []).append(
                    {"role": "frozen_results", "path": "frozen_results.json"}
                )
            write_json(paths["manifest"], manifest)
            result = harness.run_script(
                "qa/check_gates.py", "--project-root", str(project),
                "--manifest", paths["manifest"].name, "--strict",
            )
            report = json.loads(result.stdout)
            self.assertEqual(report.get("errors"), [])
            self.assertFalse(
                any("run ahead of gates" in w for w in report.get("warnings", [])),
                report.get("warnings"),
            )


if __name__ == "__main__":
    unittest.main()
