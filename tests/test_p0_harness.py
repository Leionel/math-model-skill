from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_ref(path: Path) -> dict[str, str]:
    return {"path": path.name, "sha256": sha256(path)}


class P0HarnessTest(unittest.TestCase):
    def run_script(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def build_fixture(self, project: Path) -> dict[str, Path]:
        names = {
            "input": "input.json",
            "code": "model.py",
            "rule": "official_rules.html",
            "ai_record": "ai_interaction.md",
            "validation": "full_validation.json",
            "raw": "raw_results.json",
            "frozen": "frozen_results.json",
            "evidence": "evidence_registry.json",
            "model": "model_contract.json",
            "plan": "paper_plan.json",
            "paper": "solution.pdf",
            "abstract": "abstract.txt",
            "conclusion": "conclusion.txt",
            "support": "support.zip",
            "ai_disclosure": "AI_use_report.pdf",
            "qa_report": "deterministic_qa.json",
            "critic_report": "semantic_critic.json",
            "blind_report": "blind_a.json",
            "submission_report": "submission_qa.json",
            "submission_manifest": "submission_manifest.json",
            "manifest": "run_manifest.json",
        }
        paths = {key: project / value for key, value in names.items()}
        paths["input"].write_text('{"demand": [10, 20, 30]}\n', encoding="utf-8")
        paths["code"].write_text("# deterministic fixture\n", encoding="utf-8")
        paths["rule"].write_text("official rule snapshot\n", encoding="utf-8")
        paths["ai_record"].write_text("prompt summary and checked response\n", encoding="utf-8")
        paths["paper"].write_bytes(b"%PDF-1.4\n% fixture solution\n")
        paths["support"].write_bytes(b"PK fixture support\n")
        paths["ai_disclosure"].write_bytes(b"%PDF-1.4\n% AI use report\n")

        write_json(
            paths["model"],
            {
                "schema_version": "1.1",
                "project_id": "demo",
                "run_id": "demo-run",
                "unit_system": "SI with CNY for cost",
                "questions": [
                    {"question_id": "q1", "task": "minimize cost", "conclusion_type": "numeric optimum", "inputs": ["demand"], "outputs": ["optimal_cost"]}
                ],
                "data_sources": [
                    {
                        "data_id": "demand",
                        "path": "input.json",
                        "read_only": True,
                        "sha256": sha256(paths["input"]),
                        "origin": "contest attachment",
                        "license_or_terms": "competition use",
                        "transformations": [],
                        "quality_checks": ["schema, missing values, range and unit checks"],
                    }
                ],
                "assumptions": [
                    {"assumption_id": "A1", "text": "demand is fixed during the run", "basis": "problem statement", "sensitivity_plan": "rerun with +/-10% demand"}
                ],
                "models": [
                    {
                        "model_id": "M1",
                        "question_id": "q1",
                        "name": "baseline optimization",
                        "problem_type": "optimization",
                        "rationale": "matches the stated objective",
                        "variables": [
                            {"symbol": "x", "meaning": "selected production amount", "unit": "item", "domain": "x >= 0", "role": "decision"}
                        ],
                        "objective": "minimize total cost",
                        "constraints": [{"constraint_id": "C1", "expression": "x >= 0", "meaning": "non-negative production"}],
                        "algorithm": "enumeration",
                        "inputs": ["demand"],
                        "outputs": ["optimal_cost"],
                        "validation": [{"check_id": "V1", "stage": "both", "method": "check feasibility and objective", "acceptance": "all constraints pass"}],
                        "validation_obligations": [
                            {"obligation_id": "VAL-FEASIBILITY", "category": "feasibility", "method": "recompute all constraints", "acceptance": "maximum violation is zero", "required_stage": "both"},
                            {"obligation_id": "VAL-OBJECTIVE", "category": "objective_recomputation", "method": "independent objective function", "acceptance": "exact match", "required_stage": "full"},
                        ],
                        "risks": ["fixed-demand assumption"],
                        "fallback": "use the best feasible enumerated solution",
                    }
                ],
                "terminology": [{"canonical": "optimal cost", "forbidden_variants": ["optimium cost"]}],
                "status": "ready",
            },
        )
        write_json(
            paths["validation"],
            {
                "ok": True,
                "obligations": [
                    {"obligation_id": "VAL-FEASIBILITY", "status": "pass", "observed": "maximum violation = 0"},
                    {"obligation_id": "VAL-OBJECTIVE", "status": "pass", "observed": "independent objective = 123.45"},
                ],
            },
        )
        write_json(
            paths["raw"],
            {"results": [{
                "result_id": "R-Q1-01", "question_id": "q1", "name": "optimal_cost", "value": 123.45,
                "unit": "CNY", "precision": 2, "statistical_definition": "objective at selected optimum",
                "boundary": "fixed demand and declared constraints", "validation_status": "passed",
            }]},
        )
        freeze = self.run_script(
            "freeze_results.py",
            "--project-root", str(project),
            "--source", "raw_results.json",
            "--output", "frozen_results.json",
            "--run-id", "demo-run",
            "--model-contract", "model_contract.json",
            "--command", "python model.py --seed 7",
            "--seed", "7",
            "--input", "input.json",
            "--code", "model.py",
            "--validation", "full_validation.json",
        )
        self.assertEqual(freeze.returncode, 0, freeze.stdout + freeze.stderr)

        register = self.run_script(
            "register_evidence.py",
            "--project-root", str(project),
            "--frozen-results", "frozen_results.json",
            "--output", "evidence_registry.json",
        )
        self.assertEqual(register.returncode, 0, register.stdout + register.stderr)
        write_json(
            paths["plan"],
            {
                "schema_version": "1.0",
                "run_id": "demo-run",
                "requirements": [{"requirement_id": "RQ1", "text": "answer question 1", "claim_ids": ["C1"]}],
                "claims": [{"claim_id": "C1", "text": "the selected plan has the minimum cost", "question_id": "q1", "evidence_ids": ["E-R-Q1-01"], "section": "results.q1", "boundary": "under the frozen run"}],
                "sections": [{"section_id": "results.q1", "purpose": "answer question 1", "claim_ids": ["C1"]}],
                "abstract_result_ids": ["R-Q1-01"],
                "terminology": [{"canonical": "optimal cost", "forbidden_variants": ["optimium cost"]}],
                "figures": [], "tables": [], "status": "ready",
            },
        )
        paths["abstract"].write_text("The optimal cost is 123.45 CNY.\n", encoding="utf-8")
        paths["conclusion"].write_text("The optimal cost is 123.45 CNY.\n", encoding="utf-8")
        qa_inputs = [
            {"role": role, "path": path.name, "sha256": sha256(path)}
            for role, path in (
                ("model_contract", paths["model"]), ("frozen_results", paths["frozen"]),
                ("evidence_registry", paths["evidence"]), ("paper_plan", paths["plan"]),
                ("abstract", paths["abstract"]), ("paper", paths["paper"]), ("conclusion", paths["conclusion"]),
            )
        ]
        write_json(paths["qa_report"], {"ok": True, "inputs": qa_inputs, "checks": [
            {"label": "contracts", "ok": True}, {"label": "contest_safety", "ok": True},
            {"label": "consistency", "ok": True}, {"label": "citations", "ok": True, "status": "not_applicable"},
        ]})
        write_json(paths["critic_report"], {"verdict": "pass", "issues": []})
        write_json(paths["blind_report"], {"reviewer_id": "blind-a", "verdict": "pass", "issues": []})

        policy = {
            "interactive_human_help": "allow", "current_problem_discussion": "allow",
            "public_posting": "allow", "external_write": "allow",
            "static_reference_search": "allow", "ai_tool_use": "allow",
        }
        checkpoints = [
            {"checkpoint_id": "HC-M1", "stage": "m1", "scope": "model and obligations", "artifacts": [file_ref(paths["model"])], "manual_checks": ["problem interpretation"], "reviewed_by_role": "team", "decision": "pass", "checked_at": "2026-08-08T00:00:00Z"},
            {"checkpoint_id": "HC-P2", "stage": "p2", "scope": "code validation and results", "artifacts": [file_ref(paths["frozen"])], "manual_checks": ["result plausibility"], "reviewed_by_role": "team", "decision": "pass", "checked_at": "2026-08-08T00:00:00Z"},
            {"checkpoint_id": "HC-W2", "stage": "w2", "scope": "claims citations figures and AI", "artifacts": [file_ref(paths["paper"])], "manual_checks": ["claim boundary"], "reviewed_by_role": "team", "decision": "pass", "checked_at": "2026-08-08T00:00:00Z"},
            {"checkpoint_id": "HC-S1", "stage": "s1", "scope": "final package", "artifacts": [file_ref(paths["paper"]), file_ref(paths["support"]), file_ref(paths["ai_disclosure"])], "manual_checks": ["anonymity", "final_render", "support_contents", "page_count"], "reviewed_by_role": "team", "decision": "pass", "checked_at": "2026-08-08T00:00:00Z"},
        ]
        gate_evidence = {
            "m1": ["model_contract.json"], "p1": ["command:smoke"], "p2": ["frozen_results.json"],
            "w1": ["evidence_registry.json", "paper_plan.json"],
            "w2": ["solution.pdf", "deterministic_qa.json", "semantic_critic.json"], "s1": [],
        }
        manifest = {
            "schema_version": "1.1", "project_id": "demo", "run_id": "demo-run",
            "status": "content_ready", "phase": "review",
            "competition_profile": {
                "profile_id": "demo-2026", "competition": "other", "season": "2026", "mode": "pre_contest",
                "retrieved_at": "2026-08-08T00:00:00Z",
                "official_rules": [{"rule_id": "RULE-1", "title": "Demo rules", "url": "https://example.org/rules", "retrieved_at": "2026-08-08T00:00:00Z", "snapshot": file_ref(paths["rule"])}],
                "official_submission_endpoints": ["https://submit.example.org/"],
                "submission": {
                    "paper_extensions": [".pdf"], "max_paper_bytes": 1000000, "max_pages": 25,
                    "page_count_scope": "entire PDF", "support_policy": "required", "max_support_bytes": 1000000,
                    "ai_disclosure_policy": "required_when_used",
                    "required_manual_checks": ["anonymity", "final_render", "support_contents", "page_count"],
                },
            },
            "safety": {"official_rule": policy, "local_conservative_policy": policy, "events": []},
            "ai_usage": [{
                "usage_id": "AI-1", "tool_name": "Codex", "model": "fixture-model", "provider": "OpenAI",
                "used_at": "2026-08-08T00:00:00Z", "stage": "coding", "purpose": "fixture assistance",
                "prompt_summary": "review fixture", "output_use": "suggestion adopted", "human_changes": "manually checked",
                "interaction_record": file_ref(paths["ai_record"]),
                "verification": {"status": "verified", "checked_by_role": "team", "method": "manual rerun", "checked_at": "2026-08-08T00:00:00Z"},
            }],
            "human_checkpoints": checkpoints,
            "model_contract": file_ref(paths["model"]),
            "commands": [
                {"command_id": "smoke", "stage": "smoke", "command": "python model.py --smoke", "exit_code": 0},
                {"command_id": "full", "stage": "full", "command": "python model.py --full", "exit_code": 0},
                {"command_id": "freeze", "stage": "freeze", "command": "freeze_results.py", "exit_code": 0},
            ],
            "artifacts": [
                {**file_ref(paths["frozen"]), "role": "frozen_results"},
                {**file_ref(paths["evidence"]), "role": "evidence_registry"},
                {**file_ref(paths["plan"]), "role": "paper_plan"},
                {**file_ref(paths["paper"]), "role": "paper"},
            ],
            "gates": {name: {"status": ("pending" if name == "s1" else "pass"), "checked_at": "2026-08-08T00:00:00Z", "evidence": gate_evidence[name]} for name in ("m1", "p1", "p2", "w1", "w2", "s1")},
            "revision": {"loop": 0, "cap": 2, "open_issue_ids": []},
            "reviewer": {
                "profile": "final_submission",
                "deterministic_qa": {"status": "pass", "report": paths["qa_report"].name, "report_sha256": sha256(paths["qa_report"])},
                "semantic_critic": {"status": "pass", "report": paths["critic_report"].name, "report_sha256": sha256(paths["critic_report"])},
                "blind_reviewers": [{"status": "pass", "reviewer_id": "blind-a", "report": paths["blind_report"].name, "report_sha256": sha256(paths["blind_report"])}],
            },
        }
        write_json(paths["manifest"], manifest)
        submission = self.run_script(
            "qa/check_submission.py", "--project-root", str(project), "--run-manifest", paths["manifest"].name,
            "--paper", paths["paper"].name, "--paper-pages", "12", "--page-count-method", "manual_verified",
            "--support", paths["support"].name, "--ai-disclosure", paths["ai_disclosure"].name,
            "--output", paths["submission_report"].name,
        )
        self.assertEqual(submission.returncode, 0, submission.stdout + submission.stderr)
        manifest = read_json(paths["manifest"])
        manifest["status"] = "submission_ready"
        manifest["phase"] = "submission"
        manifest["gates"]["s1"] = {"status": "pass", "checked_at": "2026-08-08T00:00:00Z", "evidence": [paths["submission_report"].name]}
        manifest["artifacts"].append({**file_ref(paths["submission_report"]), "role": "submission_qa"})
        write_json(paths["manifest"], manifest)
        return paths

    def validate_fixture(self, project: Path) -> subprocess.CompletedProcess[str]:
        return self.run_script(
            "qa/validate_contracts.py", "--project-root", str(project),
            "--model-contract", "model_contract.json", "--run-manifest", "run_manifest.json",
            "--frozen-results", "frozen_results.json", "--evidence-registry", "evidence_registry.json",
            "--paper-plan", "paper_plan.json", "--strict",
        )

    def test_happy_path_contracts_safety_and_gates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-p0-") as temp:
            project = Path(temp)
            self.build_fixture(project)
            validate = self.validate_fixture(project)
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)
            safety = self.run_script("qa/check_contest_safety.py", "--project-root", str(project), "--manifest", "run_manifest.json", "--strict")
            self.assertEqual(safety.returncode, 0, safety.stdout + safety.stderr)
            gates = self.run_script("qa/check_gates.py", "--project-root", str(project), "--manifest", "run_manifest.json", "--strict")
            self.assertEqual(gates.returncode, 0, gates.stdout + gates.stderr)

    def test_freeze_rejects_placeholder_validation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-validation-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            paths["frozen"].unlink()
            write_json(paths["validation"], {"ok": True})
            result = self.run_script(
                "freeze_results.py", "--project-root", str(project), "--source", paths["raw"].name,
                "--output", paths["frozen"].name, "--run-id", "demo-run", "--model-contract", paths["model"].name,
                "--command", "python model.py", "--code", paths["code"].name, "--validation", paths["validation"].name,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("non-empty obligations", result.stderr)

    def test_verified_citation_requires_full_content_and_status_checks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-literature-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            registry = read_json(paths["evidence"])
            registry["evidence"].append({
                "evidence_id": "E-CITE-1", "type": "citation", "result_ids": [], "artifacts": [],
                "supports": "a method choice", "boundary": "abstract only", "verification_status": "verified",
                "citation": {
                    "bib_key": "demo2026", "title": "Demo", "authors": ["A. Author"], "year": 2026,
                    "canonical_url": "https://example.org/paper", "source_tier": "trusted_index",
                    "metadata_sources": ["https://api.crossref.org/works/demo"], "access_level": "metadata_only",
                    "locator": "metadata record", "metadata_verified": True, "content_verified": False,
                    "publication_status_checked": False, "verified_at": "2026-08-08T00:00:00Z",
                },
            })
            write_json(paths["evidence"], registry)
            manifest = read_json(paths["manifest"])
            next(row for row in manifest["artifacts"] if row["role"] == "evidence_registry")["sha256"] = sha256(paths["evidence"])
            write_json(paths["manifest"], manifest)
            validate = self.validate_fixture(project)
            self.assertNotEqual(validate.returncode, 0)
            self.assertIn("content_verified", validate.stdout)

    def test_live_contest_blocks_public_write(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-safety-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            manifest = read_json(paths["manifest"])
            manifest["competition_profile"]["mode"] = "live_contest"
            for policy_name in ("official_rule", "local_conservative_policy"):
                for action in ("interactive_human_help", "current_problem_discussion", "public_posting", "external_write"):
                    manifest["safety"][policy_name][action] = "deny"
            manifest["safety"]["events"] = [{
                "event_id": "EV-1", "action": "public_posting", "direction": "write", "channel": "github",
                "target": "https://github.com/example/repo", "decision": "executed",
                "recorded_at": "2026-08-08T00:00:00Z", "reason": "test",
            }]
            write_json(paths["manifest"], manifest)
            safety = self.run_script("qa/check_contest_safety.py", "--project-root", str(project), "--manifest", paths["manifest"].name, "--strict")
            self.assertNotEqual(safety.returncode, 0)
            self.assertIn("not permitted", safety.stdout)

    def test_submission_freeze_is_immutable_and_hashes_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-submission-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            freeze = self.run_script(
                "freeze_submission.py", "--project-root", str(project), "--run-manifest", paths["manifest"].name,
                "--s1-report", paths["submission_report"].name, "--paper", paths["paper"].name,
                "--support", paths["support"].name, "--ai-disclosure", paths["ai_disclosure"].name,
                "--deadline", "2026-09-01T20:00:00+08:00", "--timezone", "Asia/Hong_Kong",
                "--output", paths["submission_manifest"].name,
            )
            self.assertEqual(freeze.returncode, 0, freeze.stdout + freeze.stderr)
            submission = read_json(paths["submission_manifest"])
            self.assertEqual(submission["status"], "final_frozen")
            final_check = self.run_script(
                "qa/check_submission_manifest.py", "--project-root", str(project),
                "--submission-manifest", paths["submission_manifest"].name,
            )
            self.assertEqual(final_check.returncode, 0, final_check.stdout + final_check.stderr)
            overwrite = self.run_script(
                "freeze_submission.py", "--project-root", str(project), "--run-manifest", paths["manifest"].name,
                "--s1-report", paths["submission_report"].name, "--paper", paths["paper"].name,
                "--support", paths["support"].name, "--ai-disclosure", paths["ai_disclosure"].name,
                "--deadline", "2026-09-01T20:00:00+08:00", "--timezone", "Asia/Hong_Kong",
                "--output", paths["submission_manifest"].name,
            )
            self.assertNotEqual(overwrite.returncode, 0)

    def test_deterministic_qa_includes_contest_safety(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-qa-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            paths["qa_report"].unlink()
            qa = self.run_script(
                "qa/run_deterministic_qa.py", "--project-root", str(project),
                "--model-contract", paths["model"].name, "--run-manifest", paths["manifest"].name,
                "--frozen-results", paths["frozen"].name, "--evidence-registry", paths["evidence"].name,
                "--paper-plan", paths["plan"].name, "--abstract", paths["abstract"].name,
                "--paper", paths["paper"].name, "--conclusion", paths["conclusion"].name,
                "--output", paths["qa_report"].name,
            )
            self.assertEqual(qa.returncode, 0, qa.stdout + qa.stderr)
            labels = {row["label"] for row in read_json(paths["qa_report"])["checks"]}
            self.assertEqual(labels, {"contracts", "contest_safety", "consistency", "citations"})

    def test_s1_rejects_missing_manual_check(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-s1-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            manifest = read_json(paths["manifest"])
            checkpoint = next(row for row in manifest["human_checkpoints"] if row["stage"] == "s1")
            checkpoint["manual_checks"].remove("anonymity")
            write_json(paths["manifest"], manifest)
            report = self.run_script(
                "qa/check_submission.py", "--project-root", str(project), "--run-manifest", paths["manifest"].name,
                "--paper", paths["paper"].name, "--paper-pages", "12", "--page-count-method", "manual_verified",
                "--support", paths["support"].name, "--ai-disclosure", paths["ai_disclosure"].name,
                "--output", "submission_qa_2.json",
            )
            self.assertNotEqual(report.returncode, 0)
            self.assertIn("missing manual", read_json(project / "submission_qa_2.json")["errors"][0].lower())

    def test_strict_abstract_gate_rejects_unregistered_number(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-abstract-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            paths["abstract"].write_text("The optimal cost is 123.45 CNY with score 999.\n", encoding="utf-8")
            consistency = self.run_script(
                "qa/check_consistency.py", "--project-root", str(project), "--paper-plan", paths["plan"].name,
                "--frozen-results", paths["frozen"].name, "--evidence-registry", paths["evidence"].name,
                "--abstract", paths["abstract"].name, "--strict",
            )
            self.assertNotEqual(consistency.returncode, 0)
            self.assertIn("not registered", consistency.stdout)

    def test_citation_checker_ignores_comments(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-cite-") as temp:
            project = Path(temp)
            (project / "main.tex").write_text("% \\cite{missing}\nA citation \\citep{demo2026}.\n", encoding="utf-8")
            (project / "references.bib").write_text("@article{demo2026, title={Demo}, year={2026}}\n", encoding="utf-8")
            result = self.run_script("qa/check_citations.py", "--project-root", str(project), "--tex", "main.tex", "--bib", "references.bib")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
