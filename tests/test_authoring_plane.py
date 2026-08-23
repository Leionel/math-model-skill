from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness.py"
SAFETY = ROOT / "scripts" / "qa" / "check_contest_safety.py"


class AuthoringPlaneTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="authoring-plane-")
        self.project = Path(self.temp.name) / "project"
        result = self.run_cli("init", "--project", str(self.project), "--competition", "cumcm", "--preset", "research", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args], cwd=str(ROOT), text=True,
            capture_output=True, encoding="utf-8", errors="replace", check=False,
        )

    def register_root(self, role: str, filename: str) -> None:
        path = self.project / "run_manifest.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["roots"][role] = {"path": filename}
        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def test_m1_projection_exposes_unresolved_fork_and_acceptance_rule(self) -> None:
        contract = {
            "status": "draft", "unit_system": "SI", "problem_statement": "Plan capacity under uncertain demand.",
            "questions": [{
                "question_id": "q1", "task": "Find feasible capacity", "conclusion_type": "minimum",
                "inputs": ["demand"], "outputs": ["capacity"],
                "required_answer": {"answer_type": "minimum_feasible_parameter", "quantity": "capacity", "unit": "unit", "scope": "all scenarios", "must_satisfy": ["service >= 0.95"], "reporting_semantics": "smallest tested feasible value"},
            }],
            "data_sources": [{"data_id": "D1", "path": "data.csv", "origin": "official attachment", "quality_checks": ["range", "missingness"]}],
            "assumptions": [{"assumption_id": "A1", "text": "Demand scenarios are representative", "basis": "official data", "sensitivity_plan": "perturb weights"}],
            "assumption_forks": [{
                "fork_id": "F1", "phrase": "annual demand", "question_id": "q1",
                "interpretations": [{"id": "monthly_sum", "meaning": "sum months", "mathematical_effect": "aggregate"}, {"id": "annual_peak", "meaning": "peak month", "mathematical_effect": "max"}],
                "checks": ["read statement context"], "unresolved_risk": "changes capacity definition",
            }],
            "research_basis": {
                "candidate_models": [{"candidate_id": "C1", "question_id": "q1", "name": "MILP", "mechanism_fit": "capacity constraints", "strengths": ["exact"], "weaknesses": ["scenario size"], "decision": "selected"}],
                "unresolved_questions": ["scenario probability source"],
            },
            "models": [{
                "model_id": "M1", "question_id": "q1", "name": "Capacity MILP", "problem_family": "optimization", "problem_type": "optimization",
                "rationale": "direct feasibility representation", "objective": "min C", "algorithm": "branch-and-bound", "inputs": ["demand"], "outputs": ["capacity"],
                "risks": ["probability misspecification"], "fallback": "enumeration",
                "validation_obligations": [{"obligation_id": "V1", "category": "feasibility", "method": "recompute service", "required_stage": "full", "acceptance": {"left_metric_id": "service", "operator": ">=", "right": {"kind": "literal", "value": 0.95}, "unit": "ratio"}}],
                "plan_details": {"implementation_steps": ["load data", "build model", "solve", "recompute"], "output_artifacts": ["solution.json"]},
            }],
        }
        path = self.project / "model_contract.json"
        path.write_text(json.dumps(contract, ensure_ascii=False, indent=2), encoding="utf-8")
        self.register_root("model_contract", path.name)

        result = self.run_cli("prepare", "M1", "--project", str(self.project), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        projection = (self.project / ".harness" / "views" / "M1_STATE.md").read_text(encoding="utf-8")
        self.assertIn("**UNRESOLVED**", projection)
        self.assertIn("service >= 0.95 ratio", projection)
        self.assertIn("Candidate comparison", projection)
        self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), projection)

    def test_w1_projection_preserves_missing_evidence_and_deliverables(self) -> None:
        plan = {
            "central_thesis": {"text": "Robust capacity reduces shortfall.", "boundary": "tested scenarios only"},
            "claims": [{"claim_id": "C1", "text": "Capacity is robust", "evidence_ids": [], "boundary": "tested scenarios"}],
            "sections": [{"section_id": "results", "purpose": "answer q1"}],
            "argument_units": [{"unit_id": "U1", "section_id": "results", "rhetorical_role": "result_observation", "claim_ids": ["C1"], "evidence_ids": [], "expected_reader_judgment": "see the evidence gap"}],
            "figures": [{"figure_id": "F1", "title": "Scenario comparison", "evidence_ids": []}],
            "tables": [{"table_id": "T1", "title": "Capacity results", "evidence_ids": []}],
            "abstract_results": [{"abstract_id": "A1", "text": "Result pending", "evidence_ids": []}],
            "deliverables": [{"deliverable_id": "D-AI", "type": "ai_report", "title": "AI disclosure", "required_by_profile": True, "target_path": "submission/ai.pdf", "source_refs": ["run_manifest.json"], "status": "planned"}],
        }
        path = self.project / "paper_plan.json"
        path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
        self.register_root("paper_plan", path.name)

        result = self.run_cli("prepare", "W1", "--project", str(self.project), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        outline = (self.project / ".harness" / "views" / "W1_STATE.md").read_text(encoding="utf-8")
        appendix = (self.project / ".harness" / "views" / "APPENDIX_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("MISSING EVIDENCE", outline)
        self.assertIn("D-AI", outline)
        self.assertIn("Remaining evidence gaps", outline)
        self.assertIn("AI disclosure", appendix)
        self.assertIn("Generated projection", outline)

    def test_ai_none_declaration_cannot_coexist_with_used_state(self) -> None:
        interaction = self.project / "ai_interaction.md"
        interaction.write_text("auditable interaction\n", encoding="utf-8")
        recorded = self.run_cli(
            "ai", "record", "--project", str(self.project), "--usage-id", "AI-CONFLICT-1",
            "--tool-name", "Codex", "--model", "fixture-model", "--provider", "OpenAI",
            "--stage", "coding", "--purpose", "fixture", "--prompt-summary", "fixture",
            "--output-use", "fixture", "--human-changes", "reviewed",
            "--interaction-record", interaction.name, "--checked-by-role", "team-lead",
            "--verification-method", "manual review", "--used-at", "2026-08-21T01:00:00Z",
            "--checked-at", "2026-08-21T02:00:00Z", "--json",
        )
        self.assertEqual(recorded.returncode, 0, recorded.stdout + recorded.stderr)
        manifest_path = self.project / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["ai_usage_declaration"] = {
            "status": "none", "confirmed_by": "team-lead",
            "confirmed_at": "2026-08-21T03:00:00Z", "reason": "invalid stale declaration",
        }
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        safety = subprocess.run(
            [sys.executable, str(SAFETY), "--project-root", str(self.project),
             "--manifest", "run_manifest.json", "--strict"],
            cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8",
            errors="replace", check=False,
        )
        self.assertNotEqual(safety.returncode, 0)
        self.assertIn("ai_usage_declaration conflicts with ai_usage_state=used", safety.stdout)

    def test_s1_projection_blocks_invalid_declaration_and_nonempty_final(self) -> None:
        manifest_path = self.project / "run_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["ai_usage_state"] = "none"
        manifest.pop("ai_usage_declaration", None)
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        final_dir = self.project / "submission" / "final"
        final_dir.mkdir(parents=True)
        (final_dir / "untracked-final.pdf").write_bytes(b"not frozen")

        result = self.run_cli("prepare", "S1", "--project", str(self.project), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report["warnings"])
        disclosure = self.project / "submission" / "staging" / "ai_disclosure" / "AI工具使用详情.md"
        self.assertIn("DRAFT BLOCKED", disclosure.read_text(encoding="utf-8"))
        checklist = (self.project / ".harness" / "views" / "SUBMISSION_STATE.md").read_text(encoding="utf-8")
        self.assertIn("[ ] AI usage is explicitly and consistently declared", checklist)
        self.assertIn("submission/final/` is already non-empty", checklist)

    def test_w1_projection_refuses_stale_dag_artifact(self) -> None:
        plan_path = self.project / "stale-paper-plan.json"
        plan_path.write_text(json.dumps({"central_thesis": {"text": "stale"}}), encoding="utf-8")
        self.register_root("paper_plan", plan_path.name)
        dag_path = self.project / "artifact_dag.json"
        dag = json.loads(dag_path.read_text(encoding="utf-8"))
        dag["nodes"].append({
            "artifact_id": "PLAN-STALE", "role": "paper_plan", "path": plan_path.name,
            "producer_id": "fixture", "dependencies": [], "lifecycle": "mutable",
            "freshness": "stale", "version": "1", "created_at": "2026-08-21T00:00:00Z",
            "digest_owner": "artifact_dag", "sha256": hashlib.sha256(plan_path.read_bytes()).hexdigest(),
            "digest_algorithm": "sha256",
        })
        dag_path.write_text(json.dumps(dag, ensure_ascii=False, indent=2), encoding="utf-8")

        result = self.run_cli("prepare", "W1", "--project", str(self.project), "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        outline = (self.project / ".harness" / "views" / "W1_STATE.md").read_text(encoding="utf-8")
        self.assertIn("paper_plan` is missing or unreadable", outline)
        self.assertNotIn("stale-paper-plan.json", outline)


if __name__ == "__main__":
    unittest.main()
