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
        paths = {
            "input": project / "input.json",
            "code": project / "model.py",
            "validation": project / "full_validation.json",
            "raw": project / "raw_results.json",
            "frozen": project / "frozen_results.json",
            "evidence": project / "evidence_registry.json",
            "model": project / "model_contract.json",
            "plan": project / "paper_plan.json",
            "paper": project / "paper.txt",
            "abstract": project / "abstract.txt",
            "conclusion": project / "conclusion.txt",
            "qa_report": project / "deterministic_qa.json",
            "critic_report": project / "semantic_critic.json",
            "blind_report": project / "blind_a.json",
            "manifest": project / "run_manifest.json",
        }
        paths["input"].write_text('{"demand": [10, 20, 30]}\n', encoding="utf-8")
        paths["code"].write_text("# deterministic fixture\n", encoding="utf-8")
        write_json(paths["validation"], {"ok": True, "checks": ["constraints", "objective"]})
        write_json(
            paths["raw"],
            {
                "results": [
                    {
                        "result_id": "R-Q1-01",
                        "question_id": "q1",
                        "name": "optimal_cost",
                        "value": 123.45,
                        "unit": "CNY",
                        "precision": 2,
                        "statistical_definition": "objective value at the selected optimum",
                        "boundary": "fixed demand and declared constraints",
                        "validation_status": "passed",
                    }
                ]
            },
        )
        freeze = self.run_script(
            "freeze_results.py",
            "--project-root", str(project),
            "--source", "raw_results.json",
            "--output", "frozen_results.json",
            "--run-id", "demo-run",
            "--command", "python model.py --seed 7",
            "--seed", "7",
            "--input", "input.json",
            "--code", "model.py",
            "--validation", "full_validation.json",
        )
        self.assertEqual(freeze.returncode, 0, freeze.stdout + freeze.stderr)

        write_json(
            paths["model"],
            {
                "schema_version": "1.0",
                "project_id": "demo",
                "run_id": "demo-run",
                "unit_system": "SI with CNY for cost",
                "questions": [
                    {"question_id": "q1", "task": "minimize cost", "conclusion_type": "numeric optimum", "inputs": ["demand"], "outputs": ["optimal_cost"]}
                ],
                "data_sources": [
                    {"data_id": "demand", "path": "input.json", "read_only": True, "sha256": sha256(paths["input"])}
                ],
                "assumptions": [
                    {"assumption_id": "A1", "text": "demand is fixed during the run", "basis": "problem statement", "sensitivity_plan": "rerun with +/-10% demand"}
                ],
                "models": [
                    {
                        "model_id": "M1",
                        "question_id": "q1",
                        "name": "baseline optimization",
                        "rationale": "matches the stated objective",
                        "variables": [
                            {"symbol": "x", "meaning": "selected production amount", "unit": "item", "domain": "x >= 0", "role": "decision"}
                        ],
                        "objective": "minimize total cost",
                        "constraints": [
                            {"constraint_id": "C1", "expression": "x >= 0", "meaning": "non-negative production"}
                        ],
                        "algorithm": "enumeration",
                        "inputs": ["demand"],
                        "outputs": ["optimal_cost"],
                        "validation": [
                            {"check_id": "V1", "stage": "both", "method": "check feasibility and objective", "acceptance": "all constraints pass"}
                        ],
                        "risks": ["fixed-demand assumption"],
                        "fallback": "use the best feasible enumerated solution",
                    }
                ],
                "terminology": [{"canonical": "optimal cost", "forbidden_variants": ["optimium cost"]}],
                "status": "ready",
            },
        )

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
                "claims": [
                    {"claim_id": "C1", "text": "the selected plan has the minimum cost", "question_id": "q1", "evidence_ids": ["E-R-Q1-01"], "section": "results.q1", "boundary": "under the frozen run"}
                ],
                "sections": [{"section_id": "results.q1", "purpose": "answer question 1", "claim_ids": ["C1"]}],
                "abstract_result_ids": ["R-Q1-01"],
                "terminology": [{"canonical": "optimal cost", "forbidden_variants": ["optimium cost"]}],
                "figures": [],
                "tables": [],
                "status": "ready",
            },
        )
        paths["paper"].write_text("The optimal cost is 123.45 CNY.\n", encoding="utf-8")
        paths["abstract"].write_text("The optimal cost is 123.45 CNY.\n", encoding="utf-8")
        paths["conclusion"].write_text("The optimal cost is 123.45 CNY.\n", encoding="utf-8")
        qa_inputs = [
            {"role": role, "path": path.name, "sha256": sha256(path)}
            for role, path in (
                ("model_contract", paths["model"]),
                ("frozen_results", paths["frozen"]),
                ("evidence_registry", paths["evidence"]),
                ("paper_plan", paths["plan"]),
                ("abstract", paths["abstract"]),
                ("paper", paths["paper"]),
                ("conclusion", paths["conclusion"]),
            )
        ]
        write_json(
            paths["qa_report"],
            {
                "ok": True,
                "inputs": qa_inputs,
                "checks": [
                    {"label": "contracts", "ok": True},
                    {"label": "consistency", "ok": True},
                    {"label": "citations", "ok": True, "status": "not_applicable"},
                ],
            },
        )
        write_json(paths["critic_report"], {"verdict": "pass", "issues": []})
        write_json(paths["blind_report"], {"reviewer_id": "blind-a", "verdict": "pass", "issues": []})

        gate_evidence = {
            "m1": ["model_contract.json"],
            "p1": ["command:smoke"],
            "p2": ["frozen_results.json"],
            "w1": ["evidence_registry.json", "paper_plan.json"],
            "w2": ["paper.txt", "deterministic_qa.json", "semantic_critic.json"],
        }
        write_json(
            paths["manifest"],
            {
                "schema_version": "1.0",
                "project_id": "demo",
                "run_id": "demo-run",
                "status": "released",
                "phase": "release",
                "model_contract": {"path": "model_contract.json", "sha256": sha256(paths["model"])},
                "commands": [
                    {"command_id": "smoke", "stage": "smoke", "command": "python model.py --smoke", "exit_code": 0},
                    {"command_id": "full", "stage": "full", "command": "python model.py --full", "exit_code": 0},
                    {"command_id": "freeze", "stage": "freeze", "command": "freeze_results.py", "exit_code": 0},
                ],
                "artifacts": [
                    {"path": "frozen_results.json", "sha256": sha256(paths["frozen"]), "role": "frozen_results"},
                    {"path": "evidence_registry.json", "sha256": sha256(paths["evidence"]), "role": "evidence_registry"},
                    {"path": "paper_plan.json", "sha256": sha256(paths["plan"]), "role": "paper_plan"},
                    {"path": "paper.txt", "sha256": sha256(paths["paper"]), "role": "paper"},
                ],
                "gates": {
                    name: {"status": "pass", "checked_at": "2026-08-08T00:00:00Z", "evidence": gate_evidence[name]}
                    for name in ("m1", "p1", "p2", "w1", "w2")
                },
                "revision": {"loop": 0, "cap": 2, "open_issue_ids": []},
                "reviewer": {
                    "profile": "final_submission",
                    "deterministic_qa": {"status": "pass", "report": "deterministic_qa.json", "report_sha256": sha256(paths["qa_report"])},
                    "semantic_critic": {"status": "pass", "report": "semantic_critic.json", "report_sha256": sha256(paths["critic_report"])},
                    "blind_reviewers": [
                        {"status": "pass", "reviewer_id": "blind-a", "report": "blind_a.json", "report_sha256": sha256(paths["blind_report"])}
                    ],
                },
            },
        )
        return paths

    def validate_fixture(self, project: Path) -> subprocess.CompletedProcess[str]:
        return self.run_script(
            "qa/validate_contracts.py",
            "--project-root", str(project),
            "--model-contract", "model_contract.json",
            "--run-manifest", "run_manifest.json",
            "--frozen-results", "frozen_results.json",
            "--evidence-registry", "evidence_registry.json",
            "--paper-plan", "paper_plan.json",
            "--strict",
        )

    def test_happy_path_and_release_gates(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-p0-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            validate = self.validate_fixture(project)
            self.assertEqual(validate.returncode, 0, validate.stdout + validate.stderr)

            consistency = self.run_script(
                "qa/check_consistency.py",
                "--project-root", str(project),
                "--paper-plan", "paper_plan.json",
                "--frozen-results", "frozen_results.json",
                "--evidence-registry", "evidence_registry.json",
                "--abstract", "abstract.txt",
                "--paper", "paper.txt",
                "--conclusion", "conclusion.txt",
                "--strict",
            )
            self.assertEqual(consistency.returncode, 0, consistency.stdout + consistency.stderr)
            gates = self.run_script("qa/check_gates.py", "--project-root", str(project), "--manifest", "run_manifest.json", "--strict")
            self.assertEqual(gates.returncode, 0, gates.stdout + gates.stderr)

            overwrite = self.run_script(
                "freeze_results.py",
                "--project-root", str(project),
                "--source", "raw_results.json",
                "--output", "frozen_results.json",
                "--run-id", "demo-run",
                "--command", "python model.py",
                "--code", "model.py",
                "--validation", "full_validation.json",
            )
            self.assertNotEqual(overwrite.returncode, 0)
            self.assertTrue(paths["evidence"].is_file())

    def test_deterministic_qa_runner_creates_hashable_release_report(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-qa-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            paths["qa_report"].unlink()
            qa = self.run_script(
                "qa/run_deterministic_qa.py",
                "--project-root", str(project),
                "--model-contract", "model_contract.json",
                "--run-manifest", "run_manifest.json",
                "--frozen-results", "frozen_results.json",
                "--evidence-registry", "evidence_registry.json",
                "--paper-plan", "paper_plan.json",
                "--abstract", "abstract.txt",
                "--paper", "paper.txt",
                "--conclusion", "conclusion.txt",
                "--output", "deterministic_qa.json",
            )
            self.assertEqual(qa.returncode, 0, qa.stdout + qa.stderr)
            report = read_json(paths["qa_report"])
            self.assertTrue(report["ok"])
            self.assertEqual({row["label"] for row in report["checks"]}, {"contracts", "consistency", "citations"})
            manifest = read_json(paths["manifest"])
            manifest["reviewer"]["deterministic_qa"]["report_sha256"] = sha256(paths["qa_report"])
            write_json(paths["manifest"], manifest)
            gates = self.run_script("qa/check_gates.py", "--project-root", str(project), "--manifest", "run_manifest.json", "--strict")
            self.assertEqual(gates.returncode, 0, gates.stdout + gates.stderr)

    def test_freeze_rejects_missing_unit_and_display_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-freeze-") as temp:
            project = Path(temp)
            (project / "model.py").write_text("# fixture\n", encoding="utf-8")
            write_json(project / "validation.json", {"ok": True})
            base = {
                "result_id": "R-Q1-01", "question_id": "q1", "name": "cost", "value": 10.0,
                "precision": 2, "statistical_definition": "exact", "boundary": "fixture", "validation_status": "passed",
            }
            write_json(project / "missing_unit.json", {"results": [base]})
            missing = self.run_script(
                "freeze_results.py", "--project-root", str(project), "--source", "missing_unit.json", "--output", "missing.json",
                "--run-id", "run", "--command", "python model.py", "--code", "model.py", "--validation", "validation.json",
            )
            self.assertNotEqual(missing.returncode, 0)
            drift = dict(base, unit="CNY", display_value="10.01")
            write_json(project / "drift.json", {"results": [drift]})
            drift_result = self.run_script(
                "freeze_results.py", "--project-root", str(project), "--source", "drift.json", "--output", "drift_frozen.json",
                "--run-id", "run", "--command", "python model.py", "--code", "model.py", "--validation", "validation.json",
            )
            self.assertNotEqual(drift_result.returncode, 0)

    def test_p2_requires_both_full_and_freeze(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-gate-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            manifest = read_json(paths["manifest"])
            manifest["commands"] = [row for row in manifest["commands"] if row["stage"] != "full"]
            write_json(paths["manifest"], manifest)
            gates = self.run_script("qa/check_gates.py", "--project-root", str(project), "--manifest", "run_manifest.json")
            self.assertNotEqual(gates.returncode, 0)
            self.assertIn("successful full command", gates.stdout)

    def test_malformed_plan_fails_without_validator_crash(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-schema-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            plan = read_json(paths["plan"])
            plan["requirements"] = "not-an-array"
            write_json(paths["plan"], plan)
            manifest = read_json(paths["manifest"])
            for artifact in manifest["artifacts"]:
                if artifact["role"] == "paper_plan":
                    artifact["sha256"] = sha256(paths["plan"])
            write_json(paths["manifest"], manifest)
            validate = self.validate_fixture(project)
            self.assertNotEqual(validate.returncode, 0)
            self.assertNotIn("Traceback", validate.stderr)
            json.loads(validate.stdout)

    def test_w1_rejects_unverified_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-evidence-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            registry = read_json(paths["evidence"])
            registry["evidence"][0]["verification_status"] = "pending"
            write_json(paths["evidence"], registry)
            manifest = read_json(paths["manifest"])
            for artifact in manifest["artifacts"]:
                if artifact["role"] == "evidence_registry":
                    artifact["sha256"] = sha256(paths["evidence"])
            write_json(paths["manifest"], manifest)
            gates = self.run_script("qa/check_gates.py", "--project-root", str(project), "--manifest", "run_manifest.json")
            self.assertNotEqual(gates.returncode, 0)
            self.assertIn("unverified evidence", gates.stdout)

    def test_w2_rejects_report_content_marked_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-review-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            write_json(paths["critic_report"], {"verdict": "fail", "issues": [{"id": "W2-1", "severity": "high"}]})
            manifest = read_json(paths["manifest"])
            manifest["reviewer"]["semantic_critic"]["report_sha256"] = sha256(paths["critic_report"])
            write_json(paths["manifest"], manifest)
            gates = self.run_script("qa/check_gates.py", "--project-root", str(project), "--manifest", "run_manifest.json")
            self.assertNotEqual(gates.returncode, 0)
            self.assertIn("verdict=pass", gates.stdout)

    def test_strict_abstract_gate_rejects_unregistered_number(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-abstract-") as temp:
            project = Path(temp)
            paths = self.build_fixture(project)
            paths["abstract"].write_text("The optimal cost is 123.45 CNY with score 999.\n", encoding="utf-8")
            consistency = self.run_script(
                "qa/check_consistency.py",
                "--project-root", str(project),
                "--paper-plan", "paper_plan.json",
                "--frozen-results", "frozen_results.json",
                "--evidence-registry", "evidence_registry.json",
                "--abstract", "abstract.txt",
                "--strict",
            )
            self.assertNotEqual(consistency.returncode, 0)
            self.assertIn("not registered", consistency.stdout)

    def test_citation_checker_ignores_comments_and_supports_optional_args(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-harness-cite-") as temp:
            project = Path(temp)
            (project / "main.tex").write_text(
                "% \\cite{missing-commented}\nA citation \\citep[see][p. 2]{demo2026}.\n",
                encoding="utf-8",
            )
            (project / "references.bib").write_text("@article{demo2026, title={Demo}, year={2026}}\n", encoding="utf-8")
            citations = self.run_script(
                "qa/check_citations.py", "--project-root", str(project), "--tex", "main.tex", "--bib", "references.bib",
            )
            self.assertEqual(citations.returncode, 0, citations.stdout + citations.stderr)


if __name__ == "__main__":
    unittest.main()
