"""Gate timing regressions: enhanced M1 no longer requires a verified
implementation map; enhanced P1 requires a smoke-coverage declaration bound
to the real receipt; the verified map lands at P2."""

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
FIXTURE = ROOT / "tests" / "fixtures" / "wp2_runtime"

MODEL_CONTRACT = {
    "schema_version": "1.3",
    "project_id": "wp2-project",
    "run_id": "run-1",
    "status": "ready",
    "questions": [{"question_id": "q1", "task": "minimize cost", "conclusion_type": "numeric optimum", "inputs": ["demand"], "outputs": ["cost"]}],
    "models": [{
        "model_id": "M-Q1",
        "question_id": "q1",
        "name": "cost model",
        "plan_details": {"equation_plan": [{"equation_id": "EQ-Q1-OBJ", "purpose": "objective"}]},
        "constraints": [{"constraint_id": "C1", "expression": "x >= 0", "meaning": "nonnegative"}],
        "validation_obligations": [{"obligation_id": "VAL-FEAS", "category": "feasibility"}],
    }],
}


class GateTimingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="gate-timing-")
        self.project = Path(self.temp.name)
        shutil.copy2(FIXTURE / "competition_profile.json", self.project / "competition_profile.json")
        shutil.copy2(FIXTURE / "rules.txt", self.project / "rules.txt")
        (self.project / "model.json").write_text(json.dumps(MODEL_CONTRACT, ensure_ascii=False), encoding="utf-8")
        self._write_manifest()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_manifest(self) -> None:
        manifest = {
            "schema_version": "2.0", "project_id": "wp2-project", "run_id": "run-1", "status": "active",
            "stage": "results", "preset": "research", "profile_overrides": {},
            "competition_profile_ref": {"path": "competition_profile.json", "profile_id": "wp2-fixture"},
            "roots": {"model_contract": {"path": "model.json"}, "run_index": {"path": "run_index.json"}, "artifact_dag": {"path": "artifact_dag.json"}},
            "control": {"selection_policy": {"owner": "run_manifest.control", "rule": "exactly one selected receipt", "version": "2.0"}},
            "safety": {}, "ai_usage": [], "human_checkpoints": [],
        }
        (self.project / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def _manifest(self) -> dict:
        return json.loads((self.project / "run_manifest.json").read_text(encoding="utf-8"))

    def _set_manifest(self, value: dict) -> None:
        (self.project / "run_manifest.json").write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")

    def gate(self, name: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "qa" / "check_gates.py"),
             "--manifest", "run_manifest.json", "--project-root", str(self.project), "--gate", name],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )

    def _record_smoke(
        self,
        *,
        receipt: str = "smoke.json",
        model_ids: list[str] | None = None,
        question_ids: list[str] | None = None,
        contract_item_ids: list[str] | None = None,
    ) -> str:
        coverage_args: list[str] = []
        for value in model_ids or []:
            coverage_args.extend(["--covers-model", value])
        for value in question_ids or []:
            coverage_args.extend(["--covers-question", value])
        for value in contract_item_ids or []:
            coverage_args.extend(["--covers-contract-item", value])
        run = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_and_record.py"),
             "--v2", "--integrity-mode", "research", "--run-id", "run-1", "--stage", "smoke",
             "--receipt", receipt, "--index", "run_index.json", "--project-root", str(self.project),
             *coverage_args,
             "--", sys.executable, "-c", "print('ok')"],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        return str(json.loads(run.stdout)["receipt_id"])

    def test_enhanced_p1_requires_smoke_coverage_declaration(self) -> None:
        self._record_smoke()
        result = self.gate("p1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("smoke_coverage", result.stdout)

    def test_enhanced_p1_ignores_mutable_manifest_coverage(self) -> None:
        self._record_smoke()
        manifest = self._manifest()
        manifest["control"]["smoke_coverage"] = {
            "model_ids": ["M-Q1"],
            "question_ids": ["q1"],
            "covered_contract_item_ids": ["EQ-Q1-OBJ"],
        }
        self._set_manifest(manifest)
        result = self.gate("p1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("smoke_coverage", result.stdout)

    def test_enhanced_p1_rejects_unknown_model_and_missing_item(self) -> None:
        self._record_smoke(
            model_ids=["M-Q1", "M-GHOST"],
            question_ids=["q1", "q9"],
            contract_item_ids=["NOT-A-CONTRACT-ITEM"],
        )
        result = self.gate("p1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown model_ids", result.stdout)
        self.assertIn("unknown question_ids", result.stdout)
        self.assertIn("unknown contract item ids", result.stdout)
        self.assertIn("no equation/constraint/obligation item for model M-Q1", result.stdout)

    def test_enhanced_p1_accepts_complete_coverage(self) -> None:
        self._record_smoke(
            model_ids=["M-Q1"],
            question_ids=["q1"],
            contract_item_ids=["EQ-Q1-OBJ", "C1", "VAL-FEAS"],
        )
        result = self.gate("p1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_enhanced_p1_allows_history_when_one_receipt_has_complete_coverage(self) -> None:
        self._record_smoke(receipt="exploratory.json")
        self._record_smoke(
            receipt="qualified.json",
            model_ids=["M-Q1"],
            question_ids=["q1"],
            contract_item_ids=["EQ-Q1-OBJ", "C1", "VAL-FEAS"],
        )
        result = self.gate("p1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_sprint_p1_still_passes_without_coverage_declaration(self) -> None:
        manifest = self._manifest()
        manifest["preset"] = "sprint"
        self._set_manifest(manifest)
        self._record_smoke()
        result = self.gate("p1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("smoke_coverage", result.stdout)

    def test_enhanced_m1_never_requires_implementation_map(self) -> None:
        # A verified implementation map attests equation->code bindings, which
        # cannot exist before solve; M1 checks a plan, so even the full
        # evidence-chain capability must not demand the map here (it lands at
        # P2 instead).  v2 re-derives every gate from facts, no claimed status.
        result = self.gate("m1")
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertTrue(report["evidence"]["capabilities"]["capabilities"]["require_full_evidence_chain"])
        self.assertTrue(report["errors"])
        self.assertFalse(any("implementation_map" in message for message in report["errors"]))

    def test_enhanced_p2_requires_verified_implementation_map(self) -> None:
        result = self.gate("p2")
        self.assertNotEqual(result.returncode, 0)
        report = json.loads(result.stdout)
        self.assertIn(
            "implementation_map canonical artifact is not declared in roots or artifact DAG",
            report["errors"],
        )


if __name__ == "__main__":
    unittest.main()
