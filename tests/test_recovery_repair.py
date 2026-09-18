from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evaluation" / "recovery" / "fixtures" / "slim_v2"
FAULTS = ROOT / "evaluation" / "recovery" / "faults"
REPAIR = ROOT / "evaluation" / "recovery" / "repair.py"
UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

sys.path.insert(0, str(REPAIR.parent))

import repair as repair_module  # noqa: E402


@unittest.skipUnless(FIXTURE.is_dir(), "slim fixture has not been generated yet")
class RecoveryRepairTest(unittest.TestCase):
    def test_freeze_artifact_repair_is_contract_blocked(self) -> None:
        """F03 documents the recovery channel gap: a deleted frozen result has no
        sanctioned repair (P2 requires exactly one successful freeze receipt, so
        re-freezing breaks P2).  The executor must record the step instead of
        executing it, re-check the gate honestly, and exit 1."""
        fault = FAULTS / "F03_frozen_results_deleted"
        with tempfile.TemporaryDirectory(prefix="repair-f03-") as temp:
            project = Path(temp) / "project"
            shutil.copytree(FIXTURE, project)
            injected = subprocess.run(
                [sys.executable, str(fault / "inject.py"), "--project-root", str(project)],
                text=True, capture_output=True, encoding="utf-8", check=False,
            )
            self.assertEqual(injected.returncode, 0, injected.stdout + injected.stderr)

            result = subprocess.run(
                [sys.executable, str(REPAIR), "--project-root", str(project),
                 "--fault-id", "F03", "--gate", "P2", "--changed", "frozen_results.json"],
                text=True, capture_output=True, encoding="utf-8", errors="replace",
                check=False, env=UTF8_ENV,
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])
            frozen_step = next(step for step in payload["steps"] if step["path"] == "frozen_results.json")
            self.assertEqual(frozen_step["status"], "contract_blocked")
            self.assertFalse(frozen_step["executed"])
            self.assertEqual(payload["gate_exit_code"], 1)

            log = json.loads((project / ".harness" / "recovery" / "F03.json").read_text(encoding="utf-8"))
            self.assertFalse(log["repaired"])
            self.assertTrue(any("canonical frozen_results artifact does not exist" in error
                                for error in log["gate_report"].get("errors", [])))
            # The artifact stays absent: no unsanctioned rewrite happened.
            self.assertFalse((project / "frozen_results.json").exists())

    def test_execute_argv_maps_receipt_facts_to_flags(self) -> None:
        receipt = {
            "stage": "smoke",
            "run_id": "run-1",
            "seed": 7,
            "selection": {"selected": False},
            "input_refs": [{"path": "input.json"}],
            "output_refs": [{"path": "smoke_results.json"}],
            "metadata": {"smoke_coverage": {"model_ids": ["M-Q1"], "question_ids": ["q1"],
                                            "covered_contract_item_ids": ["EQ-Q1-OBJ"]}},
            "cwd": "D:\\old\\project",
            "argv": [sys.executable, "D:\\old\\project\\model.py", "--smoke"],
        }
        project = Path("D:\\live\\project")
        argv = repair_module.execute_argv(receipt, project)
        text = " ".join(argv)
        self.assertIn("--stage smoke", text)
        self.assertIn("--run-id run-1", text)
        self.assertIn("--seed 7", text)
        self.assertIn("--input input.json", text)
        self.assertIn("--output-artifact smoke_results.json", text)
        self.assertIn("--covers-model M-Q1", text)
        self.assertIn("--covers-question q1", text)
        self.assertIn("--covers-contract-item EQ-Q1-OBJ", text)
        self.assertNotIn("--selected", text)
        self.assertNotIn("--freeze", text)
        self.assertNotIn("D:\\old\\project", text)
        self.assertIn("D:\\live\\project\\model.py", argv)

    def test_freeze_stage_receives_selected_and_freeze_flags(self) -> None:
        receipt = {
            "stage": "freeze",
            "run_id": "run-1",
            "selection": {"selected": True},
            "input_refs": [], "output_refs": [{"path": "frozen_results.json"}],
            "cwd": "D:\\old\\project",
            "argv": ["python", "freeze.py"],
        }
        argv = repair_module.execute_argv(receipt, Path("D:\\live\\project"))
        text = " ".join(argv)
        self.assertIn("--freeze", text)
        self.assertIn("--selected", text)


if __name__ == "__main__":
    unittest.main()
