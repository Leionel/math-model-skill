"""R5.3 sensitivity sweep orchestration: one sweep runs each grid point
through run_and_record, emits a checker-valid experiment artifact plus a
summary, and reports failure honestly when a point fails."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SWEEP = ROOT / "scripts" / "run_sensitivity_sweep.py"

PASS_TEMPLATE = [
    sys.executable, "-c",
    "import json; json.dump({'objective': {value} * 2}, open(r'{artifact}', 'w', encoding='utf-8'))",
]
FAIL_TEMPLATE = [
    sys.executable, "-c",
    "import json, sys; json.dump({'objective': {value}}, open(r'{artifact}', 'w', encoding='utf-8')); sys.exit(0 if {value} <= 0.5 else 1)",
]
MISSING_METRIC_TEMPLATE = [
    sys.executable, "-c",
    "import json; json.dump({'other': {value}}, open(r'{artifact}', 'w', encoding='utf-8'))",
]


def _run_sweep(project: Path, template: list[str], experiment_id: str = "SE-1") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SWEEP),
         "--project-root", str(project),
         "--run-id", "run-1",
         "--experiment-id", experiment_id,
         "--question-id", "q1",
         "--parameter", "alpha",
         "--grid", "0.25,0.5,0.75",
         "--baseline", "0.5",
         "--metric-id", "objective",
         "--metric-unit", "kg",
         "--metric-definition", "total cost at the optimum",
         "--metric-direction", "lower_is_better",
         "--", *template],
        text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
    )


class SensitivitySweepTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="sensitivity-sweep-")
        self.project = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_sweep_runs_every_grid_point_with_receipts(self) -> None:
        result = _run_sweep(self.project, PASS_TEMPLATE)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["runs"], 3)
        self.assertEqual(report["passed"], 3)
        self.assertTrue(report["checker"]["ok"], report["checker"])

        experiment = json.loads((self.project / ".harness" / "reports" / "sensitivity_SE-1.json").read_text(encoding="utf-8"))
        self.assertEqual(experiment["status"], "completed")
        self.assertEqual(experiment["grid"], [0.25, 0.5, 0.75])
        self.assertEqual(len(experiment["runs"]), 3)
        for row in experiment["runs"]:
            self.assertEqual(row["status"], "PASS")
            receipt = self.project / row["execution"]["receipt"]["path"]
            self.assertTrue(receipt.is_file())
            artifact = self.project / row["artifact"]["path"]
            self.assertTrue(artifact.is_file())
            self.assertEqual(row["execution"]["input_parameter"], "alpha")
            self.assertEqual(row["execution"]["input_value"], row["grid_value"])

        summary = json.loads((self.project / ".harness" / "results" / "sensitivity" / "SE-1" / "summary.json").read_text(encoding="utf-8"))
        values = {point["grid_value"]: point["metric_value"] for point in summary["points"]}
        self.assertEqual(values, {0.25: 0.5, 0.5: 1.0, 0.75: 1.5})

        index = json.loads((self.project / "run_index.json").read_text(encoding="utf-8"))
        evidence_receipts = [row for row in index["receipts"] if row.get("stage") == "evidence"]
        self.assertEqual(len(evidence_receipts), 3)

    def test_failing_grid_point_is_reported_honestly(self) -> None:
        result = _run_sweep(self.project, FAIL_TEMPLATE)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertFalse(report["ok"])
        self.assertLess(report["passed"], report["runs"])
        experiment = json.loads((self.project / ".harness" / "reports" / "sensitivity_SE-1.json").read_text(encoding="utf-8"))
        self.assertEqual(experiment["status"], "failed")
        statuses = {row["grid_value"]: row["status"] for row in experiment["runs"]}
        self.assertEqual(statuses[0.25], "PASS")
        self.assertIn(statuses[0.75], {"FAIL", "ERROR"})

    def test_template_without_artifact_placeholder_is_rejected_before_running(self) -> None:
        template = [sys.executable, "-c", "print({value})"]
        result = _run_sweep(self.project, template)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertTrue(any("{artifact}" in message for message in report["errors"]))
        self.assertFalse((self.project / "run_index.json").exists())

    def test_single_grid_value_is_rejected(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SWEEP),
             "--project-root", str(self.project), "--run-id", "run-1",
             "--experiment-id", "SE-2", "--question-id", "q1",
             "--parameter", "alpha", "--grid", "0.5", "--baseline", "0.5",
             "--metric-id", "objective", "--metric-unit", "kg",
             "--metric-definition", "cost", "--", *PASS_TEMPLATE],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least two grid values", result.stdout)

    def test_missing_declared_metric_cannot_pass_a_grid_point(self) -> None:
        result = _run_sweep(self.project, MISSING_METRIC_TEMPLATE)
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertTrue(any("missing declared metric" in message for message in report["errors"]), report)
        experiment = json.loads(
            (self.project / ".harness" / "reports" / "sensitivity_SE-1.json").read_text(encoding="utf-8")
        )
        self.assertEqual(experiment["status"], "failed")
        self.assertTrue(all(row["status"] == "ERROR" for row in experiment["runs"]))

    def test_experiment_id_and_output_paths_cannot_escape_project_root(self) -> None:
        traversal = _run_sweep(self.project, PASS_TEMPLATE, experiment_id="../escape")
        self.assertNotEqual(traversal.returncode, 0)
        self.assertIn("experiment-id", traversal.stdout)
        outside = self.project.parent / "outside-sweep.json"
        escaped_output = subprocess.run(
            [
                sys.executable, str(SWEEP), "--project-root", str(self.project),
                "--run-id", "run-1", "--experiment-id", "SE-OUT", "--question-id", "q1",
                "--parameter", "alpha", "--grid", "0.25,0.5", "--baseline", "0.5",
                "--metric-id", "objective", "--metric-unit", "kg", "--metric-definition", "cost",
                "--output", str(outside), "--", *PASS_TEMPLATE,
            ],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertNotEqual(escaped_output.returncode, 0)
        self.assertIn("inside the project root", escaped_output.stdout)
        self.assertFalse(outside.exists())

    def test_repeat_run_is_rejected_before_any_grid_point_executes(self) -> None:
        first = _run_sweep(self.project, PASS_TEMPLATE)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        index_path = self.project / "run_index.json"
        receipts_before = len(json.loads(index_path.read_text(encoding="utf-8"))["receipts"])
        second = _run_sweep(self.project, PASS_TEMPLATE)
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("refusing to overwrite earlier sensitivity artifact", second.stdout)
        receipts_after = len(json.loads(index_path.read_text(encoding="utf-8"))["receipts"])
        self.assertEqual(receipts_after, receipts_before)


if __name__ == "__main__":
    unittest.main()
