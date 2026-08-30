"""R5.2 selective rerun planning: changed inputs yield the minimal rerun
set and pending gates, projected to .harness/views/RERUN_PLAN.md without
executing anything."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa.plan_selective_rerun import _ROLE_GATES, build_rerun_plan, plan_selective_rerun, render_markdown  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_dag_project(project: Path, *, freeze_digest: bool = True) -> dict:
    (project / "data").mkdir(exist_ok=True)
    input_path = project / "data" / "input.json"
    input_path.write_text(json.dumps({"rows": 3}), encoding="utf-8")
    results_path = project / "results.json"
    results_path.write_text(json.dumps({"score": 1.0}), encoding="utf-8")
    frozen_path = project / "frozen.json"
    frozen_path.write_text(json.dumps({"status": "frozen"}), encoding="utf-8")
    paper_path = project / "paper.md"
    paper_path.write_text("# paper\n", encoding="utf-8")
    frozen_node = {
        "artifact_id": "A3",
        "role": "frozen_results",
        "path": "frozen.json",
        "producer_id": "freeze_cmd",
        "producer_receipt_id": "rcpt-freeze",
        "dependencies": [{"artifact_id": "A2", "relation": "consumes"}],
        "lifecycle": "frozen",
        "freshness": "current",
        "digest_owner": "artifact_dag",
        "digest_algorithm": "sha256",
    }
    if freeze_digest:
        frozen_node["sha256"] = _sha256(frozen_path)
    dag = {
        "schema_version": "2.0",
        "run_id": "run-1",
        "nodes": [
            {
                "artifact_id": "A1",
                "role": "input_data",
                "path": "data/input.json",
                "producer_id": "manual",
                "dependencies": [],
                "lifecycle": "mutable",
                "freshness": "current",
                "digest_owner": "artifact_dag",
            },
            {
                "artifact_id": "A2",
                "role": "results",
                "path": "results.json",
                "producer_id": "solve_cmd",
                "dependencies": [{"artifact_id": "A1", "relation": "consumes"}],
                "lifecycle": "mutable",
                "freshness": "current",
                "digest_owner": "artifact_dag",
            },
            frozen_node,
            {
                "artifact_id": "A4",
                "role": "paper",
                "path": "paper.md",
                "producer_id": "writer",
                "dependencies": [{"artifact_id": "A3", "relation": "consumes"}],
                "lifecycle": "mutable",
                "freshness": "current",
                "digest_owner": "artifact_dag",
            },
        ],
    }
    (project / "artifact_dag.json").write_text(json.dumps(dag, ensure_ascii=False, indent=2), encoding="utf-8")
    return dag


class BuildRerunPlanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rerun-plan-")
        self.project = Path(self.temp.name)
        self.dag = _write_dag_project(self.project)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_clean_project_has_empty_rerun_set(self) -> None:
        plan = build_rerun_plan(self.dag, self.project, [])
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertEqual(plan["change_roots"], [])
        self.assertEqual(plan["rerun_steps"], [])
        self.assertEqual(plan["pending_gates"], {})
        self.assertTrue(plan["warnings"])

    def test_changed_input_yields_full_downstream_closure(self) -> None:
        plan = build_rerun_plan(self.dag, self.project, ["A1"])
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertEqual(plan["change_roots"], ["A1"])
        self.assertEqual(plan["affected_artifact_ids"], ["A1", "A2", "A3", "A4"])
        order = [step["artifact_id"] for step in plan["rerun_steps"]]
        self.assertEqual(order, ["A1", "A2", "A3", "A4"])
        self.assertEqual(plan["rerun_steps"][2]["producer_receipt_id"], "rcpt-freeze")
        self.assertEqual(
            plan["pending_gates"],
            {"p2": ["frozen_results"], "w1": ["frozen_results"], "w2": ["frozen_results", "paper"]},
        )

    def test_changed_leaf_limits_rerun_set(self) -> None:
        plan = build_rerun_plan(self.dag, self.project, ["A3"])
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertEqual(plan["affected_artifact_ids"], ["A3", "A4"])
        self.assertEqual(plan["pending_gates"]["p2"], ["frozen_results"])

    def test_changed_accepts_paths(self) -> None:
        plan = build_rerun_plan(self.dag, self.project, ["data/input.json"])
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertEqual(plan["change_roots"], ["A1"])

    def test_unknown_changed_artifact_is_an_error(self) -> None:
        plan = build_rerun_plan(self.dag, self.project, ["GHOST"])
        self.assertFalse(plan["ok"])
        self.assertTrue(any("GHOST" in message for message in plan["errors"]))

    def test_frozen_digest_drift_becomes_change_root_without_flag(self) -> None:
        (self.project / "frozen.json").write_text(json.dumps({"status": "tampered"}), encoding="utf-8")
        plan = build_rerun_plan(self.dag, self.project, [])
        self.assertTrue(plan["ok"], plan["errors"])
        self.assertEqual(plan["change_roots"], ["A3"])
        self.assertEqual(plan["affected_artifact_ids"], ["A3", "A4"])
        self.assertIn("p2", plan["pending_gates"])

    def test_v1_dag_is_rejected(self) -> None:
        plan = build_rerun_plan({"schema_version": "1.0", "run_id": "r", "nodes": []}, self.project, [])
        self.assertFalse(plan["ok"])
        self.assertTrue(any("schema_version=2.0" in message for message in plan["errors"]))

    def test_markdown_states_projection_boundary(self) -> None:
        plan = build_rerun_plan(self.dag, self.project, ["A1"])
        text = render_markdown(plan)
        self.assertIn("Selective Rerun Plan", text)
        self.assertIn("Projection only", text)
        self.assertIn("`A3` (frozen_results)", text)
        self.assertIn("receipt `rcpt-freeze`", text)

    def test_gate_mapping_includes_smoke_and_pre_pdf_checks(self) -> None:
        self.assertIn("p1", _ROLE_GATES["model_contract"])
        self.assertIn("w2", _ROLE_GATES["pdf"])


class RerunPlanCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="rerun-cli-")
        self.project = Path(self.temp.name)
        _write_dag_project(self.project)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _solve(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "harness.py"), "solve",
             "--project", str(self.project), *extra],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )

    def test_cli_writes_rerun_plan_view(self) -> None:
        result = self._solve("--rerun-plan", "--changed", "A1", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["affected_artifact_ids"], ["A1", "A2", "A3", "A4"])
        view = self.project / ".harness" / "views" / "RERUN_PLAN.md"
        self.assertTrue(view.is_file())
        text = view.read_text(encoding="utf-8")
        self.assertIn("Minimal rerun set", text)
        self.assertIn("Projection only", text)
        plan_json = self.project / ".harness" / "views" / "rerun_plan.json"
        self.assertEqual(json.loads(plan_json.read_text(encoding="utf-8"))["pending_gates"]["p2"], ["frozen_results"])

    def test_cli_human_output_names_projection_boundary(self) -> None:
        result = self._solve("--rerun-plan", "--changed", "A1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("rerun plan projected", result.stdout)
        self.assertIn("no command was executed", result.stdout)

    def test_cli_rejects_combination_with_command(self) -> None:
        result = self._solve("--rerun-plan", "--", sys.executable, "-c", "print('x')")
        self.assertNotEqual(result.returncode, 0)

    def test_cli_refreshes_existing_derived_views(self) -> None:
        first = self._solve("--rerun-plan", "--changed", "A1", "--json")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        second = self._solve("--rerun-plan", "--changed", "A3", "--json")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        plan = json.loads((self.project / ".harness" / "views" / "rerun_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(plan["change_roots"], ["A3"])

    def test_derived_view_outputs_cannot_escape_project_root(self) -> None:
        outside = self.project.parent / "outside-rerun-plan.json"
        with self.assertRaisesRegex(ValueError, "inside the project root"):
            plan_selective_rerun(
                self.project,
                dag="artifact_dag.json",
                changed=["A1"],
                json_output=str(outside),
            )
        self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
