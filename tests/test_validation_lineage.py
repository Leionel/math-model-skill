"""Regression tests for real sensitivity execution receipts."""

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
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa.check_sensitivity_experiment import evaluate_experiment  # noqa: E402
from qa.validate_contracts import _validate  # noqa: E402
import test_p0_harness as p0  # noqa: E402


class ValidationLineageTest(unittest.TestCase):
    def experiment(self) -> dict[str, Any]:
        return {
            "schema_version": "1.0",
            "experiment_id": "SENS-REAL-01",
            "run_id": "run-1",
            "question_id": "q1",
            "status": "completed",
            "parameter": "lambda",
            "baseline": 0.5,
            "grid": [0.2, 0.5],
            "rerun_policy": "full_reoptimization",
            "metrics": [{"metric_id": "score", "unit": "unit", "definition": "solver score", "direction": "higher_is_better"}],
            "results_artifact": {"path": "sensitivity.json"},
            "runs": [
                self.run_row(0.2, "run_02.json", "receipt_02.json"),
                self.run_row(0.5, "run_05.json", "receipt_05.json"),
            ],
            "generated_at": "2026-08-14T00:00:00Z",
        }

    @staticmethod
    def run_row(value: float, artifact: str, receipt: str) -> dict[str, Any]:
        return {
            "grid_value": value,
            "status": "PASS",
            "artifact": {"path": artifact},
            "execution": {
                "status": "completed",
                "command": ["python", "solve.py", "--lambda", str(value)],
                "exit_code": 0,
                "started_at": "2026-08-14T00:00:00Z",
                "finished_at": "2026-08-14T00:00:01Z",
                "input_parameter": "lambda",
                "input_value": value,
                "runner": "subprocess",
                "receipt": {"path": receipt},
            },
        }

    def test_schema_accepts_execution_receipt_extension(self) -> None:
        schema = json.loads((ROOT / "schemas" / "sensitivity_experiment.schema.json").read_text(encoding="utf-8"))
        errors: list[str] = []
        _validate(self.experiment(), schema, schema, "$", errors)
        self.assertEqual(errors, [])

    def test_execution_receipts_bind_parameter_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="sensitivity-lineage-") as temp:
            root = Path(temp)
            for name in ("run_02.json", "run_05.json", "receipt_02.json", "receipt_05.json", "sensitivity.json"):
                (root / name).write_text(name + "\n", encoding="utf-8")
            errors, warnings = evaluate_experiment(self.experiment(), root, "run-1", require_execution_receipts=True)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

    def test_missing_or_misbound_execution_receipt_is_rejected(self) -> None:
        experiment = deepcopy(self.experiment())
        experiment["runs"][0].pop("execution")
        experiment["runs"][1]["execution"]["input_value"] = 0.7
        with tempfile.TemporaryDirectory(prefix="sensitivity-lineage-fail-") as temp:
            root = Path(temp)
            for name in ("run_02.json", "run_05.json", "receipt_02.json", "receipt_05.json", "sensitivity.json"):
                (root / name).write_text(name + "\n", encoding="utf-8")
            errors, _ = evaluate_experiment(experiment, root, "run-1", require_execution_receipts=True)
        self.assertTrue(any("execution is required" in error for error in errors))
        self.assertTrue(any("input_value must match" in error for error in errors))

    def test_formal_data_figure_requires_real_lineage(self) -> None:
        with tempfile.TemporaryDirectory(prefix="figure-lineage-") as temp:
            project = Path(temp)
            harness = p0.P0HarnessTest()
            paths = harness.build_fixture(project)
            plan = p0.read_json(paths["plan"])
            plan["figures"] = [{
                "figure_id": "FIG-LINEAGE-01",
                "kind": "data",
                "semantic_type": "result_comparison",
                "claim_ids": ["C1"],
                "evidence_ids": ["E-R-Q1-01"],
                "purpose": "show the frozen result",
                "why_figure": "the comparison is clearer visually",
                "message": "the frozen result is the source",
                "comparison": "solver output versus baseline",
                "visual_encoding": "bar",
                "selection_rule": "all solver outputs",
                "data_artifacts": ["raw_results.json"],
                "panel_map": {"A": "result_comparison"},
                "statistical_definition": "frozen result output",
                "paper_location": "results.q1",
                "caption_claim": "frozen result",
                "accessibility": {"grayscale_safe": True, "colorblind_safe": True, "dual_axis": False, "dual_axis_justification": None},
                "data_lineage": {
                    "source_kind": "solver_output",
                    "generator_command": ["python", "model.py"],
                    "input_artifacts": ["input.json"],
                    "output_artifact": "raw_results.json",
                    "synthetic": False,
                    "status": "verified",
                },
                "qa_status": "passed",
            }]
            p0.write_json(paths["plan"], plan)
            result = harness.run_script(
                "qa/check_consistency.py", "--project-root", str(project),
                "--paper-plan", paths["plan"].name, "--frozen-results", paths["frozen"].name,
                "--evidence-registry", paths["evidence"].name, "--abstract", paths["abstract"].name,
                "--require-figure-lineage", "--strict",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan["figures"][0].pop("data_lineage")
            p0.write_json(paths["plan"], plan)
            result = harness.run_script(
                "qa/check_consistency.py", "--project-root", str(project),
                "--paper-plan", paths["plan"].name, "--frozen-results", paths["frozen"].name,
                "--evidence-registry", paths["evidence"].name, "--abstract", paths["abstract"].name,
                "--require-figure-lineage", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires data_lineage", result.stdout)


if __name__ == "__main__":
    unittest.main()
