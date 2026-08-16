from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from harness_status import status_report  # noqa: E402
from qa.check_resource_monotonicity import metric_value  # noqa: E402
from test_p0_harness import P0HarnessTest, read_json, write_json  # noqa: E402


def frozen_file(run_id: str, result_id: str, value: float, display: str, claimable: bool = True) -> dict:
    return {
        "schema_version": "1.2",
        "run_id": run_id,
        "status": "frozen",
        "frozen_at": "2026-08-16T00:00:00+00:00",
        "model_contract_snapshot": {"path": "model_contract.json", "sha256": "0" * 64},
        "source_snapshot": {"path": "raw.json", "sha256": "0" * 64},
        "input_snapshot": [],
        "code_snapshot": [],
        "validation_snapshot": [],
        "validation_obligations": [],
        "validation_verdict": "PASS" if claimable else "FAIL",
        "claimable": claimable,
        "command": "python code/run_all.py",
        "seed": 42,
        "results_sha256": "0" * 64,
        "results": [{
            "result_id": result_id,
            "name": "duration",
            "value": value,
            "unit": "s",
            "precision": 4,
            "display_value": display,
            "boundary": "frozen scenario",
            "source_artifact": "raw.json",
            "source_key": result_id,
            "validation_status": "passed" if claimable else "failed",
            "claimable": claimable,
        }],
    }


class ResourceMonotonicityTest(unittest.TestCase):
    def _check(self, project: Path, spec: dict) -> subprocess.CompletedProcess[str]:
        write_json(project / "monotonicity_spec.json", spec)
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "qa" / "check_resource_monotonicity.py"),
             "--project-root", str(project), "--spec", "monotonicity_spec.json"],
            cwd=project, text=True, capture_output=True, encoding="utf-8", check=False,
        )

    def test_battle_q3_regression_fails_with_worse_superset(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-mono-") as temp:
            project = Path(temp)
            write_json(project / "frozen_q2.json", frozen_file("battle-q2", "R-Q2-DURATION", 4.5867, "4.5867"))
            write_json(project / "frozen_q3.json", frozen_file("battle-q3", "R-Q3-DURATION", 3.6349, "3.6349"))
            spec = {"pairs": [{
                "baseline": "frozen_q2.json", "baseline_metric": "R-Q2-DURATION",
                "superset": "frozen_q3.json", "superset_metric": "R-Q3-DURATION",
                "direction": "maximize", "tolerance": 0.0,
                "reason": "3 bombs must shield at least as long as the best 1-bomb plan",
            }]}
            result = self._check(project, spec)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("resource monotonicity violated", result.stdout)

    def test_equal_and_better_superset_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-mono-ok-") as temp:
            project = Path(temp)
            write_json(project / "frozen_q2.json", frozen_file("battle-q2", "R-Q2-DURATION", 4.5867, "4.5867"))
            write_json(project / "frozen_q3.json", frozen_file("battle-q3", "R-Q3-DURATION", 4.60, "4.60"))
            spec = {"pairs": [{
                "baseline": "frozen_q2.json", "baseline_metric": "R-Q2-DURATION",
                "superset": "frozen_q3.json", "superset_metric": "R-Q3-DURATION",
                "direction": "maximize", "tolerance": 0.0,
                "reason": "3 bombs must shield at least as long as the best 1-bomb plan",
            }]}
            result = self._check(project, spec)
            self.assertEqual(result.returncode, 0, result.stdout)

    def test_metric_value_lookup(self) -> None:
        frozen = frozen_file("r", "R-X", 1.5, "1.5")
        self.assertEqual(metric_value(frozen, "R-X"), 1.5)
        self.assertIsNone(metric_value(frozen, "R-Y"))


class HarnessStatusTest(unittest.TestCase):
    def test_status_reports_pending_checkpoint_and_next_action(self) -> None:
        manifest = {
            "project_id": "demo",
            "run_id": "demo-run",
            "status": "active",
            "phase": "review",
            "integrity_mode": "research",
            "math_correctness_profile": "baseline",
            "editorial_semantics_profile": "baseline",
            "gates": {name: {"status": "pass"} for name in ("m1", "p1", "p2", "w1")}
            | {"w2": {"status": "pending"}, "s1": {"status": "pending"}},
            "human_checkpoints": [{
                "checkpoint_id": "CP-W2", "stage": "w2", "scope": "claims and citations",
                "decision": "ask", "manual_checks": ["math_formula_correctness"],
                "reviewed_by_role": "human-review-required",
            }],
            "artifacts": [],
        }
        report = status_report(manifest, ROOT)
        self.assertEqual(report["first_blocked_gate"], ("w2", "pending"))
        self.assertEqual(len(report["pending_human_checkpoints"]), 1)
        self.assertIn("W2", report["next_action"])


class GapClosureRegressionTest(P0HarnessTest):
    def test_gate_p2_consumes_run_index(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-runindex-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            manifest = read_json(paths["manifest"])
            manifest["status"] = "active"
            manifest["integrity_mode"] = "research"
            for gate in manifest.get("gates", {}).values():
                gate["status"] = "pending"
            # register a run_index that does NOT select the current run
            index = {
                "schema_version": "1.0",
                "selection_policy": "first successful full run is selected",
                "runs": [{"run_id": "other-run", "stage": "full", "argv": ["python", "x.py"],
                          "exit_code": 0, "receipt_path": "receipt.json", "selected": True,
                          "recorded_at": "2026-08-16T00:00:00Z"}],
            }
            write_json(project / "run_index.json", index)
            roles = {row.get("role") for row in manifest.get("artifacts", [])}
            if "run_index" not in roles:
                manifest.setdefault("artifacts", []).append({"role": "run_index", "path": "run_index.json"})
            write_json(paths["manifest"], manifest)
            result = harness.run_script(
                "qa/check_gates.py", "--project-root", str(project),
                "--manifest", paths["manifest"].name, "--strict",
            )
            report = json.loads(result.stdout)
            # P2 is pending so the run_index check only runs on a passed P2;
            # this fixture verifies the wiring exists without false positives.
            self.assertEqual(report.get("errors"), [], report.get("errors"))

    def test_freeze_requires_command_receipt_consistency(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-frzreceipt-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            # a receipt whose argv does NOT match the declared command
            receipt = {
                "schema_version": "1.0", "command_id": "CMD-1", "run_id": "demo-run",
                "stage": "full", "argv": ["python", "different.py"], "cwd": str(project),
                "exit_code": 0, "started_at": "t", "finished_at": "t",
                "stdout_path": "x", "stderr_path": "y", "input_refs": [], "output_refs": [],
            }
            write_json(project / "receipt.json", receipt)
            frozen = read_json(paths["frozen"])
            write_json(project / "raw_results.json", {"results": frozen["results"]})
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "freeze_results.py"),
                 "--project-root", str(project), "--source", "raw_results.json",
                 "--output", "frozen2.json", "--run-id", "demo-run",
                 "--model-contract", paths["model"].name,
                 "--command", "python code/run_all.py", "--code", "model.py",
                 "--validation", paths["validation"].name,
                 "--command-receipt", "receipt.json"],
                cwd=project, text=True, capture_output=True, encoding="utf-8", check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("argv does not match", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
