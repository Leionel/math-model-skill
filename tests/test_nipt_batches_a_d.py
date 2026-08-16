from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_p0_harness as p0  # noqa: E402


class NiptBatchADTest(unittest.TestCase):
    """Exact negative regressions for the remaining Batch A-D audit gaps."""

    def run_script(self, project: Path, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_t_nipt_05_assumed_high_parameter_must_bind_sensitivity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nipt-t05-") as temp:
            project = Path(temp)
            paths = p0.P0HarnessTest().build_fixture(project)
            model = p0.read_json(paths["model"])
            model["models"][0]["plan_details"]["parameter_plan"].extend([
                {
                    "parameter": "lambda",
                    "parameter_id": "P-LAMBDA",
                    "provenance": {
                        "type": "ASSUMED",
                        "reason": "baseline regularization choice",
                        "range": "0.5 to 2",
                        "sensitivity": "rerun over declared lambda grid",
                    },
                    "impact_class": "high",
                    "unit": "dimensionless",
                    "uncertainty_or_range": "0.5 to 2",
                },
                {
                    "parameter": "sigma",
                    "parameter_id": "P-SIGMA",
                    "sensitivity_experiment_ids": ["S-SIGMA"],
                    "provenance": {
                        "type": "ASSUMED",
                        "reason": "measurement noise scale",
                        "range": "0.1 to 0.3",
                        "sensitivity": "rerun over declared sigma grid",
                    },
                    "impact_class": "low",
                    "unit": "dimensionless",
                    "uncertainty_or_range": "0.1 to 0.3",
                },
            ])
            p0.write_json(paths["model"], model)
            result = self.run_script(
                project,
                "qa/check_modeling_plan.py",
                "--project-root", str(project),
                "--model-contract", paths["model"].name,
                "--evidence-registry", paths["evidence"].name,
                "--formal", "--require-critical-sensitivity", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires sensitivity_experiment_ids", result.stdout)

    def test_t_nipt_09_same_claim_cannot_use_two_current_sources(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nipt-t09-") as temp:
            project = Path(temp)
            paths = p0.P0HarnessTest().build_fixture(project)
            (project / "corr_v1.csv").write_text("r\n0.1\n", encoding="utf-8")
            (project / "corr_v2.csv").write_text("r\n0.2\n", encoding="utf-8")
            plan = p0.read_json(paths["plan"])
            plan["figures"] = [{
                "figure_id": "FIG-CORR",
                "kind": "data",
                "semantic_type": "result_comparison",
                "claim_ids": ["C1"],
                "evidence_ids": ["E-R-Q1-01"],
                "purpose": "show the Pearson result",
                "why_figure": "the claim needs a visual comparison",
                "message": "Pearson result",
                "comparison": "v1",
                "visual_encoding": "bar",
                "selection_rule": "the declared result",
                "data_artifacts": ["corr_v1.csv"],
                "canonical_source_id": "NODE-CORR-V1",
                "panel_map": {"A": "Pearson result"},
                "statistical_definition": "Pearson correlation",
                "paper_location": "results",
                "caption_claim": "Pearson result",
                "accessibility": {"grayscale_safe": True, "colorblind_safe": True, "dual_axis": False, "dual_axis_justification": None},
                "qa_status": "pending",
            }]
            plan["tables"] = [{
                "table_id": "TAB-CORR",
                "claim_ids": ["C1"],
                "evidence_ids": ["E-R-Q1-01"],
                "purpose": "report the Pearson result",
                "why_table": "the numeric value must be auditable",
                "data_artifacts": ["corr_v2.csv"],
                "canonical_source_id": "NODE-CORR-V2",
                "columns": [{"name": "r", "meaning": "Pearson correlation", "unit": "correlation", "source_result_ids": ["R-Q1-01"]}],
                "statistical_definition": "Pearson correlation",
                "paper_location": "results",
                "caption_claim": "Pearson result",
                "qa_status": "pending",
            }]
            p0.write_json(paths["plan"], plan)
            dag = project / "artifact_dag.json"
            p0.write_json(dag, {
                "schema_version": "1.0",
                "run_id": "demo-run",
                "nodes": [
                    {"node_id": "NODE-CORR-V1", "status": "current", "outputs": [{"path": "corr_v1.csv"}]},
                    {"node_id": "NODE-CORR-V2", "status": "current", "outputs": [{"path": "corr_v2.csv"}]},
                ],
            })
            result = self.run_script(
                project,
                "qa/check_consistency.py",
                "--project-root", str(project),
                "--paper-plan", paths["plan"].name,
                "--frozen-results", paths["frozen"].name,
                "--evidence-registry", paths["evidence"].name,
                "--abstract", paths["abstract"].name,
                "--artifact-dag", dag.name,
                "--require-canonical-source", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("claim C1 is rendered from multiple canonical sources", result.stdout)

    def test_t_nipt_13_raw_count_cannot_be_called_valid_count(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nipt-t13-") as temp:
            project = Path(temp)
            paths = p0.P0HarnessTest().build_fixture(project)
            frozen = p0.read_json(paths["frozen"])
            frozen["results"][0].update({
                "name": "record count",
                "value": 1082,
                "unit": "records",
                "precision": 0,
                "display_value": "1082",
                "metric_semantics": {"metric_type": "record_count", "population": "raw_records", "validity_rule": "before row-level validity filtering"},
            })
            p0.write_json(paths["frozen"], frozen)
            registry = p0.read_json(paths["evidence"])
            for snapshot in registry["source_snapshots"]:
                if snapshot.get("kind") == "frozen_results":
                    snapshot["sha256"] = p0.sha256(paths["frozen"])
            p0.write_json(paths["evidence"], registry)
            paths["abstract"].write_text("The dataset contains 1082 valid records.\n", encoding="utf-8")
            result = self.run_script(
                project,
                "qa/check_consistency.py",
                "--project-root", str(project),
                "--paper-plan", paths["plan"].name,
                "--frozen-results", paths["frozen"].name,
                "--evidence-registry", paths["evidence"].name,
                "--abstract", paths["abstract"].name,
                "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("METRIC_SEMANTIC_MISMATCH", result.stdout)

    def test_t_nipt_14_writer_cannot_reverse_primary_inference_role(self) -> None:
        with tempfile.TemporaryDirectory(prefix="nipt-t14-") as temp:
            project = Path(temp)
            paths = p0.P0HarnessTest().build_fixture(project)
            model = p0.read_json(paths["model"])
            model["models"][0].update({
                "problem_type": "statistical_inference",
                "statistical_design": {
                    "role": "primary_inference",
                    "methods": ["mixed_effects"],
                    "unit_of_inference": "subject",
                    "waiver_reason": None,
                },
            })
            p0.write_json(paths["model"], model)
            paths["paper"].write_text(
                "Ordinary OLS p-values are the primary inference. The mixed-effects model is only a sensitivity analysis.\n",
                encoding="utf-8",
            )
            result = self.run_script(
                project,
                "qa/check_consistency.py",
                "--project-root", str(project),
                "--paper-plan", paths["plan"].name,
                "--model-contract", paths["model"].name,
                "--frozen-results", paths["frozen"].name,
                "--evidence-registry", paths["evidence"].name,
                "--abstract", paths["abstract"].name,
                "--paper", paths["paper"].name,
                "--require-inference-role-consistency", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("PRIMARY_INFERENCE_ROLE_DRIFT", result.stdout)


if __name__ == "__main__":
    unittest.main()
