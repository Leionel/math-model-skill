"""Review Execution Plane E2E tests (prompt v4 §23).

These tests drive the real CLI (``harness review``) end to end on a minimal
sprint project: deterministic QA runs, the allow-listed bundle is materialized,
a backend reviewer executes through the process-captured receipt seam, reports
are validated/registered, and the W2 gate consumes the real evidence.

- E2E-A  a semantic finding makes W2 fail (reviewer actually executes)
- E2E-B  revision resolves the finding; re-review allows the review plane to pass
- E2E-C  a paper change after a passing review makes the review stale
- E2E-D  the fresh-context bundle enforces the information boundary

The stub reviewer proves the Execution Plane, not LLM review quality.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "wp2_runtime"
STUB = ROOT / "tests" / "fixtures" / "review_stub" / "stub_reviewer.py"
SCRIPTS = ROOT / "scripts"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


OVERCLAIM = "Our plan dominates all possible plans."
ABSTRACT_V1 = f"The optimal cost is 123.45 CNY. {OVERCLAIM}"
ABSTRACT_V2 = "The optimal cost is 123.45 CNY, superior to the tested baseline plan."
PAPER_V1 = (
    "The selected plan yields the optimal cost of 123.45 CNY under the frozen demand. "
    f"{OVERCLAIM} The optimum is feasible and independently recomputed."
)
PAPER_V2 = (
    "The selected plan yields the optimal cost of 123.45 CNY under the frozen demand. "
    "The plan is superior to the tested baseline plan. The optimum is feasible and independently recomputed."
)


class ReviewE2ETest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="review-e2e-")
        self.project = Path(self.temp.name)
        self._build_project()

    def tearDown(self) -> None:
        self.temp.cleanup()

    # -- fixture -----------------------------------------------------------

    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPTS / script), *args], cwd=self.project,
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )

    def _build_project(self) -> None:
        project = self.project
        shutil.copy2(FIXTURE / "competition_profile.json", project / "competition_profile.json")
        shutil.copy2(FIXTURE / "rules.txt", project / "rules.txt")
        (project / "input.json").write_text('{"demand": [10, 20, 30]}\n', encoding="utf-8")
        (project / "model.py").write_text("# deterministic fixture\n", encoding="utf-8")
        write_json(project / "model_contract.json", {
            "schema_version": "1.3", "project_id": "review-e2e", "run_id": "run-1",
            "unit_system": "SI with CNY for cost",
            "questions": [
                {"question_id": "q1", "task": "minimize cost", "conclusion_type": "numeric optimum", "inputs": ["demand"], "outputs": ["optimal_cost"]}
            ],
            "data_sources": [{
                "data_id": "demand", "path": "input.json", "read_only": True, "sha256": sha256(project / "input.json"),
                "origin": "contest attachment", "license_or_terms": "competition use", "transformations": [],
                "quality_checks": ["schema, missing values, range and unit checks"],
            }],
            "assumptions": [
                {"assumption_id": "A1", "text": "demand is fixed during the run", "basis": "problem statement", "sensitivity_plan": "rerun with +/-10% demand"}
            ],
            "research_basis": {
                "status": "verified",
                "research_questions": [{
                    "research_id": "RES-Q1", "question_ids": ["q1"],
                    "purpose": "compare transparent optimization formulations for fixed demand",
                    "chinese_keywords": ["固定需求 成本优化"], "english_keywords": ["fixed demand cost optimization"],
                }],
                "searches": [
                    {"search_id": "S-LLM", "research_ids": ["RES-Q1"], "query": "candidate formulations for fixed-demand cost optimization", "language": "en", "source": "llm_knowledge", "searched_at": "2026-08-08T00:00:00Z", "candidate_count": 2},
                    {"search_id": "S-WEB", "research_ids": ["RES-Q1"], "query": "fixed demand cost minimization linear optimization", "language": "en", "source": "openalex", "searched_at": "2026-08-08T00:01:00Z", "candidate_count": 4, "evidence_ids": ["E-CITE-PLAN"]},
                ],
                "candidate_models": [
                    {"candidate_id": "CM-LP", "question_id": "q1", "name": "enumerated linear cost model", "mechanism_fit": "directly represents the fixed demand and non-negativity constraints", "assumptions": ["cost is additive"], "data_requirements": ["demand and unit cost"], "strengths": ["transparent optimum"], "weaknesses": ["does not represent stochastic demand"], "evidence_ids": ["E-CITE-PLAN"], "rejection_conditions": ["nonlinear path dependence is material"], "decision": "selected", "model_id": "M1"},
                    {"candidate_id": "CM-SIM", "question_id": "q1", "name": "stochastic simulation", "mechanism_fit": "can represent uncertain demand", "assumptions": ["a demand distribution is identifiable"], "data_requirements": ["repeated demand observations"], "strengths": ["represents uncertainty"], "weaknesses": ["unsupported by the fixed fixture data"], "evidence_ids": ["E-CITE-PLAN"], "rejection_conditions": ["no repeated observations are available"], "decision": "rejected"},
                ],
                "decisions": [{"question_id": "q1", "selected_candidate_id": "CM-LP", "alternatives_considered": ["CM-SIM"], "selection_criteria": ["mechanism fit", "data sufficiency", "auditability"], "rationale": "CM-LP matches the supplied data while retaining exact feasibility and objective checks.", "decisive_evidence_ids": ["E-CITE-PLAN"], "unresolved_risks": ["demand misspecification"]}],
                "unresolved_questions": [],
            },
            "models": [{
                "model_id": "M1", "question_id": "q1", "name": "baseline optimization", "problem_type": "optimization",
                "characteristics": ["deterministic"], "rationale": "matches the stated objective",
                "variables": [{"symbol": "x", "meaning": "selected production amount", "unit": "item", "domain": "x >= 0", "role": "decision"}],
                "objective": "minimize total cost",
                "constraints": [{"constraint_id": "C1", "expression": "x >= 0", "meaning": "non-negative production"}],
                "algorithm": "enumeration", "inputs": ["demand"], "outputs": ["optimal_cost"],
                "validation": [{"check_id": "V1", "stage": "both", "method": "check feasibility and objective", "acceptance": "all constraints pass"}],
                "validation_obligations": [
                    {"obligation_id": "VAL-FEASIBILITY", "category": "feasibility", "method": "recompute all constraints",
                     "acceptance": {"left_metric_id": "max_violation", "operator": "<=", "right": {"kind": "literal", "value": 0}, "unit": "item"}, "required_stage": "both"},
                    {"obligation_id": "VAL-OBJECTIVE", "category": "objective_recomputation", "method": "independent objective function",
                     "acceptance": {"left_metric_id": "solver_objective", "operator": "==", "right": {"kind": "metric", "metric_id": "independent_objective"}, "unit": "CNY", "tolerance": 0.000001}, "required_stage": "full"},
                ],
                "risks": ["fixed-demand assumption"], "fallback": "use the best feasible enumerated solution",
                "plan_details": {
                    "selected_candidate_id": "CM-LP",
                    "mechanism": "Choose a non-negative production decision that covers fixed demand while minimizing additive cost.",
                    "equation_plan": [{"equation_id": "EQ-Q1-OBJ", "purpose": "define the optimization objective", "expression_or_derivation": "min C(x) subject to x >= demand", "variables": ["x", "demand"], "assumptions": ["additive cost"]}],
                    "parameter_plan": [{"parameter": "demand", "provenance": {"type": "GIVEN", "source_locator": "contest attachment input.json demand field"}, "unit": "item", "uncertainty_or_range": "+/-10% sensitivity"}],
                    "implementation_steps": ["load and validate demand", "enumerate feasible decisions", "recompute objective and constraints independently"],
                    "output_artifacts": ["raw_results.json", "validation_measurements.json"],
                    "validation_strategy": ["feasibility and independent objective recomputation"],
                    "failure_modes": ["fixed demand is misspecified"],
                },
            }],
            "terminology": [{"canonical": "optimal cost", "forbidden_variants": ["optimium cost"]}],
            "status": "ready",
        })
        write_json(project / "validation_measurements.json", {
            "schema_version": "1.0", "run_id": "run-1",
            "observations": [
                {"obligation_id": "VAL-FEASIBILITY", "metrics": [{"metric_id": "max_violation", "value": 0, "unit": "item", "locator": "checks/constraints.max_violation"}]},
                {"obligation_id": "VAL-OBJECTIVE", "metrics": [
                    {"metric_id": "solver_objective", "value": 123.45, "unit": "CNY", "locator": "solver.objective"},
                    {"metric_id": "independent_objective", "value": 123.45, "unit": "CNY", "locator": "recompute.objective"},
                ]},
            ],
        })
        validation = self.run_script(
            "validation/evaluate_obligations.py", "--project-root", str(project),
            "--model-contract", "model_contract.json", "--measurements", "validation_measurements.json",
            "--output", "full_validation.json",
        )
        self.assertEqual(validation.returncode, 0, validation.stdout + validation.stderr)
        write_json(project / "raw_results.json", {"results": [{
            "result_id": "R-Q1-01", "question_id": "q1", "name": "optimal_cost", "value": 123.45,
            "unit": "CNY", "precision": 2, "statistical_definition": "objective at selected optimum",
            "boundary": "fixed demand and declared constraints", "validation_status": "passed",
        }]})
        freeze = self.run_script(
            "freeze_results.py", "--project-root", str(project),
            "--source", "raw_results.json", "--output", "frozen_results.json", "--run-id", "run-1",
            "--model-contract", "model_contract.json", "--command", "python model.py --seed 7", "--seed", "7",
            "--input", "input.json", "--code", "model.py", "--validation", "full_validation.json",
        )
        self.assertEqual(freeze.returncode, 0, freeze.stdout + freeze.stderr)
        register = self.run_script(
            "register_evidence.py", "--project-root", str(project),
            "--frozen-results", "frozen_results.json", "--output", "evidence_registry.json",
        )
        self.assertEqual(register.returncode, 0, register.stdout + register.stderr)
        registry = json.loads((project / "evidence_registry.json").read_text(encoding="utf-8"))
        registry["evidence"].append({
            "evidence_id": "E-CITE-PLAN", "type": "citation", "result_ids": [], "artifacts": [],
            "supports": "transparent optimization formulation and explicit assumptions",
            "boundary": "method choice only; it does not validate this run's numerical result",
            "verification_status": "verified",
            "citation": {
                "bib_key": "fixture2026", "title": "Fixture optimization method", "authors": ["A. Author"], "year": 2026,
                "canonical_url": "https://example.org/fulltext", "venue": "Fixture Journal", "source_tier": "publisher",
                "metadata_sources": ["https://example.org/metadata"], "access_level": "full_text",
                "locator": "Methods, section 2", "metadata_verified": True, "content_verified": True,
                "publication_status_checked": True, "verified_at": "2026-08-08T00:02:00Z",
            },
        })
        write_json(project / "evidence_registry.json", registry)
        write_json(project / "paper_plan.json", {
            "schema_version": "1.2", "run_id": "run-1",
            "central_thesis": {"text": "The selected feasible plan minimizes cost under the frozen demand.", "claim_ids": ["C1"], "boundary": "Under the frozen demand and declared constraints."},
            "requirements": [{"requirement_id": "RQ1", "text": "answer question 1", "claim_ids": ["C1"]}],
            "claims": [{"claim_id": "C1", "claim_type": "observation", "text": "the selected plan has the minimum cost", "question_id": "q1", "evidence_ids": ["E-R-Q1-01"], "result_ids": ["R-Q1-01"], "section": "results.q1", "boundary": "under the frozen run", "support_level": "direct"}],
            "sections": [{"section_id": "results.q1", "purpose": "answer question 1", "claim_ids": ["C1"]}],
            "argument_units": [
                {"unit_id": "AU-Q1-FORM", "section_id": "results.q1", "rhetorical_role": "mechanism_derivation", "claim_ids": ["C1"], "evidence_ids": ["E-CITE-PLAN"], "prerequisite_unit_ids": [], "expected_reader_judgment": "The formulation matches the fixed-demand mechanism.", "boundary": "Additive cost and fixed demand.", "target_words": 70},
                {"unit_id": "AU-Q1-RESULT", "section_id": "results.q1", "rhetorical_role": "result_observation", "claim_ids": ["C1"], "evidence_ids": ["E-R-Q1-01"], "prerequisite_unit_ids": ["AU-Q1-FORM"], "expected_reader_judgment": "The reported value is directly supported by the frozen run.", "boundary": "Under the frozen run.", "target_words": 70},
                {"unit_id": "AU-Q1-VALID", "section_id": "results.q1", "rhetorical_role": "validation", "claim_ids": ["C1"], "evidence_ids": ["E-R-Q1-01"], "prerequisite_unit_ids": ["AU-Q1-RESULT"], "expected_reader_judgment": "The optimum is feasible and independently recomputed.", "boundary": "Declared constraints only.", "target_words": 70},
                {"unit_id": "AU-Q1-INTERP", "section_id": "results.q1", "rhetorical_role": "boundary", "claim_ids": ["C1"], "evidence_ids": ["E-R-Q1-01"], "prerequisite_unit_ids": ["AU-Q1-VALID"], "expected_reader_judgment": "The result is not extrapolated beyond fixed demand.", "boundary": "No stochastic-demand claim.", "target_words": 70},
            ],
            "depth_budget": [{"question_id": "q1", "target_words": 180, "rationale": "One validated optimization result."}],
            "precision_policy": {"audit_source": "frozen_display_value", "prose_source": "frozen_display_value", "table_source": "frozen_display_value", "abstract_max_numeric_claims": 2},
            "abstract_results": [{"result_id": "R-Q1-01", "priority": "primary", "selection_reason": "The decision-defining validated result.", "claim_ids": ["C1"], "word_budget": 24}],
            "terminology": [{"canonical": "optimal cost", "forbidden_variants": ["optimium cost"]}],
            "figures": [], "tables": [],
            "readiness": {"stage": "technical_draft", "question_coverage": [{"question_id": "q1", "formulation_unit_ids": ["AU-Q1-FORM"], "result_unit_ids": ["AU-Q1-RESULT"], "validation_unit_ids": ["AU-Q1-VALID"], "interpretation_unit_ids": ["AU-Q1-INTERP"], "display_ids": [], "display_waiver": "One scalar result; prose is clearer than a display."}]},
            "status": "ready",
        })
        (project / "abstract.txt").write_text(ABSTRACT_V1 + "\n", encoding="utf-8")
        (project / "paper.txt").write_text(PAPER_V1 + "\n", encoding="utf-8")
        (project / "conclusion.txt").write_text("The optimal cost is 123.45 CNY.\n", encoding="utf-8")
        (project / "run_index.json").write_text(json.dumps({
            "schema_version": "2.0", "projection": "receipt_selection", "run_id_scope": "run-1",
            "receipts": [], "selection": {"policy_ref": {}, "selected_receipt_ids": []},
        }), encoding="utf-8")
        self._write_dag_and_manifest()

    def _write_dag_and_manifest(self) -> None:
        roles = {
            "model_contract": "model_contract.json", "frozen_results": "frozen_results.json",
            "evidence_registry": "evidence_registry.json", "paper_plan": "paper_plan.json",
            "abstract": "abstract.txt", "paper": "paper.txt", "conclusion": "conclusion.txt",
        }
        nodes = []
        for index, (role, path) in enumerate(roles.items(), start=1):
            nodes.append({
                "artifact_id": f"ART-{role.upper().replace('_', '-')}-{index}",
                "role": role, "path": path, "producer_id": f"producer-{role}",
                "dependencies": [], "lifecycle": "frozen" if role == "frozen_results" else "mutable",
                "freshness": "current", "digest_owner": "artifact_dag",
                "digest_algorithm": "sha256", "sha256": sha256(self.project / path),
                "version": "1", "created_at": "2026-08-17T00:00:00Z",
            })
        write_json(self.project / "artifact_dag.json", {
            "schema_version": "2.0", "run_id": "run-1", "projection": "artifact_identity_dependency", "nodes": nodes,
        })
        policy = {
            "interactive_human_help": "allow", "current_problem_discussion": "allow",
            "public_posting": "allow", "external_write": "allow",
            "static_reference_search": "allow", "ai_tool_use": "allow",
        }
        # v2 roots keep only the schema-allow-listed references; working
        # artifacts (paper/abstract/frozen/...) are declared in the DAG above.
        write_json(self.project / "run_manifest.json", {
            "schema_version": "2.0", "project_id": "review-e2e", "run_id": "run-1", "status": "active",
            "stage": "paper", "preset": "sprint", "profile_overrides": {},
            "competition_profile_ref": {"path": "competition_profile.json", "profile_id": "wp2-fixture"},
            "roots": {
                "model_contract": {"path": "model_contract.json"},
                "evidence_registry": {"path": "evidence_registry.json"},
                "paper_plan": {"path": "paper_plan.json"},
                "run_index": {"path": "run_index.json"},
                "artifact_dag": {"path": "artifact_dag.json"},
            },
            "control": {"selection_policy": {"owner": "run_manifest.control", "rule": "exactly one", "version": "2.0"}},
            "safety": {"official_rule": policy, "local_conservative_policy": policy, "events": []},
            "ai_usage": [], "human_checkpoints": [],
        })

    # -- driver ------------------------------------------------------------

    def run_review(self, *flags: str, env_extra: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        if env_extra:
            env.update(env_extra)
        backend = f'"{sys.executable}" "{STUB}"'
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "harness.py"), "review", "--project", str(self.project),
             "--backend-cmd", backend, "--json", *flags],
            text=True, capture_output=True, encoding="utf-8", errors="replace", env=env, check=False,
        )

    def latest_report(self, perspective: str) -> Path:
        paths = sorted((self.project / "reports" / "review").glob(f"{perspective}-run-1-*.json"))
        self.assertTrue(paths, f"no {perspective} report produced")
        return paths[-1]

    # -- E2E-A: semantic finding makes W2 fail -----------------------------

    def test_E2E_A_semantic_finding_blocks_w2(self) -> None:
        result = self.run_review("--fresh", env_extra={"MATH_REVIEW_STUB_FINDING": "semantic_critic:REV-E2E-001"})
        payload = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        semantic = payload["review"]["perspectives"]["semantic_critic"]
        self.assertTrue(semantic["executed"])
        self.assertEqual(semantic["severity_counts"]["high"], 1)
        self.assertEqual(semantic["independence_level"], "L1_fresh_context")
        self.assertEqual(semantic["freshness"], "current")
        self.assertTrue(any("REV-E2E-001" in error for error in payload["errors"]), payload["errors"])
        # Real execution evidence: receipt, bundle, report artifact, DAG node.
        self.assertTrue(list((self.project / "receipts").glob("review-*.json")))
        bundles = list((self.project / "reports" / "review" / "bundle").glob("*/bundle_manifest.json"))
        self.assertTrue(bundles)
        self.assertTrue(self.latest_report("semantic_critic").is_file())
        dag = json.loads((self.project / "artifact_dag.json").read_text(encoding="utf-8"))
        self.assertIn("review_report", {node["role"] for node in dag["nodes"]})
        # The W2 gate consumes the same evidence.
        gate = self.run_script("qa/check_gates.py", "--manifest", "run_manifest.json", "--project-root", str(self.project), "--gate", "w2")
        self.assertNotEqual(gate.returncode, 0)
        self.assertIn("REV-E2E-001", gate.stdout)

    # -- E2E-B: revision resolves the finding; re-review passes ------------

    def test_E2E_B_revision_and_recheck_pass_review_plane(self) -> None:
        self.run_review("--fresh", env_extra={"MATH_REVIEW_STUB_FINDING": "semantic_critic:REV-E2E-001"})
        # Author-side targeted revision: remove the overclaim.
        (self.project / "abstract.txt").write_text(ABSTRACT_V2 + "\n", encoding="utf-8")
        (self.project / "paper.txt").write_text(PAPER_V2 + "\n", encoding="utf-8")
        self._write_dag_and_manifest()  # refresh DAG digests for the revised artifacts
        result = self.run_review("--fresh", env_extra={
            "MATH_REVIEW_STUB_FINDING": "semantic_critic:REV-E2E-001", "MATH_REVIEW_STUB_RESOLVE": "1",
        })
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["errors"], payload["errors"])
        self.assertTrue(payload["w2_preview"])
        semantic = payload["review"]["perspectives"]["semantic_critic"]
        self.assertEqual(semantic["freshness"], "current")
        self.assertEqual(semantic["verdict"], "pass")
        report = json.loads(self.latest_report("semantic_critic").read_text(encoding="utf-8"))
        self.assertEqual(report["findings"][0]["status"], "resolved")

    # -- E2E-C: paper change after pass makes the review stale -------------

    def test_E2E_C_stale_review_after_paper_change(self) -> None:
        result = self.run_review("--fresh")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.project / "paper.txt").write_text(PAPER_V2 + "\n", encoding="utf-8")
        gate = self.run_script("qa/check_gates.py", "--manifest", "run_manifest.json", "--project-root", str(self.project), "--gate", "w2")
        self.assertNotEqual(gate.returncode, 0)
        self.assertIn("changed since review", gate.stdout)
        self.assertIn("stale", gate.stdout)

    # -- E2E-D: fresh bundle enforces the information boundary -------------

    def test_E2E_D_fresh_bundle_boundary(self) -> None:
        result = self.run_review("--fresh", env_extra={"MATH_REVIEW_STUB_FINDING": "semantic_critic:REV-E2E-001"})
        payload = json.loads(result.stdout)
        bundle_rel = payload["bundle"]["path"]
        bundle_path = self.project / bundle_rel
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        roles = {row["role"] for row in bundle["files"]}
        self.assertFalse(roles & {"review_report", "previous_verdict", "writer_reasoning", "revision_discussion", "session_log"})
        self.assertIn("paper", roles)
        report = json.loads(self.latest_report("semantic_critic").read_text(encoding="utf-8"))
        receipt = json.loads((self.project / report["execution_receipt_ref"]["path"]).read_text(encoding="utf-8"))
        self.assertEqual(Path(receipt["cwd"]).resolve(), bundle_path.parent.resolve())
        # A poisoned bundle voids the independence claim (deterministic recheck).
        poisoned = bundle_path.parent / "previous_verdict.json"
        poisoned.write_text('{"verdict": "pass"}\n', encoding="utf-8")
        bundle["files"].append({"role": "previous_verdict", "artifact_id": None, "source_path": "reports/review/old.json", "path": poisoned.name, "sha256": sha256(poisoned)})
        write_json(bundle_path, bundle)
        report_path = self.latest_report("semantic_critic")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["bundle_ref"]["sha256"] = sha256(bundle_path)
        write_json(report_path, report)
        sys.path.insert(0, str(SCRIPTS))
        from qa.review_evidence import validate_bundle_boundary

        errors = validate_bundle_boundary(report, self.project)
        self.assertTrue(any("denied input role" in error for error in errors), errors)

    def test_backend_cannot_self_promote_independence(self) -> None:
        result = self.run_review("--fresh", env_extra={
            "MATH_REVIEW_STUB_MODE_OVERRIDE": "independent_model",
            "MATH_REVIEW_STUB_LEVEL_OVERRIDE": "L2_independent_model",
        })
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any("does not match orchestrator-bound" in error for error in payload["errors"]), payload)
        rejected = payload["executions"]["semantic_critic"].get("rejected_report_path")
        self.assertTrue(rejected and (self.project / rejected).is_file(), payload)

        # A rejected output is diagnostic material, not discoverable evidence;
        # a subsequent conforming reviewer can recover without deleting history.
        recovered = self.run_review("--fresh")
        self.assertEqual(recovered.returncode, 0, recovered.stdout + recovered.stderr)

    def test_backend_author_mutation_is_detected_and_blocked(self) -> None:
        result = self.run_review("--fresh", env_extra={
            "MATH_REVIEW_STUB_MUTATE_AUTHOR": str(self.project / "paper.txt"),
        })
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any("mutated protected" in error for error in payload["errors"]), payload)

    def test_backend_cannot_rewrite_its_bundle_input_evidence(self) -> None:
        result = self.run_review("--fresh", env_extra={"MATH_REVIEW_STUB_MUTATE_BUNDLE": "1"})
        self.assertNotEqual(result.returncode, 0)
        payload = json.loads(result.stdout)
        self.assertTrue(any("exact review bundle input" in error for error in payload["errors"]), payload)

    def test_human_mode_streams_phase_progress_to_stderr(self) -> None:
        backend = f'"{sys.executable}" "{STUB}"'
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "harness.py"), "review", "--project", str(self.project),
             "--backend-cmd", backend, "--fresh"],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertIn("Running deterministic QA", result.stderr)
        self.assertIn("Running semantic_critic", result.stderr)


if __name__ == "__main__":
    unittest.main()
