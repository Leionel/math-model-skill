"""Review Execution Plane unit/integration tests (prompt v4 §24 cases A–Q).

These tests prove the deterministic review-evidence boundary: discovery,
contract validation, freshness, the fresh-context bundle boundary, per-preset
W2 adjudication, and status visibility — all without trusting any manifest
self-report.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "wp2_runtime"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from qa.review_evidence import (  # noqa: E402
    evaluate_w2_review,
    required_perspectives,
    summarize_review,
    validate_bundle_boundary,
    validate_review_report,
)
from qa.run_review import _safe_run_component, register_review_report  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


class ReviewExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="review-exec-")
        self.project = Path(self.temp.name)
        shutil.copy2(FIXTURE / "competition_profile.json", self.project / "competition_profile.json")
        shutil.copy2(FIXTURE / "rules.txt", self.project / "rules.txt")
        (self.project / "model.json").write_text("{}\n", encoding="utf-8")
        (self.project / "paper.txt").write_text("draft v1\n", encoding="utf-8")
        (self.project / "abstract.txt").write_text("abstract v1\n", encoding="utf-8")
        (self.project / "conclusion.txt").write_text("conclusion v1\n", encoding="utf-8")
        (self.project / "frozen.json").write_text('{"results": []}\n', encoding="utf-8")
        (self.project / "evidence.json").write_text('{"evidence": []}\n', encoding="utf-8")
        self.report_counter = 0
        self._write_manifest(preset="research")
        (self.project / "run_index.json").write_text(json.dumps({
            "schema_version": "2.0", "projection": "receipt_selection", "run_id_scope": "run-1",
            "receipts": [], "selection": {"policy_ref": {}, "selected_receipt_ids": []},
        }), encoding="utf-8")
        artifact_rows = [
            ("MODEL-1", "model_contract", "model.json"),
            ("PAPER-1", "paper", "paper.txt"),
            ("ABSTRACT-1", "abstract", "abstract.txt"),
            ("CONCLUSION-1", "conclusion", "conclusion.txt"),
            ("FROZEN-1", "frozen_results", "frozen.json"),
            ("EVIDENCE-1", "evidence_registry", "evidence.json"),
        ]
        (self.project / "artifact_dag.json").write_text(json.dumps({
            "schema_version": "2.0", "run_id": "run-1", "projection": "artifact_identity_dependency",
            "nodes": [{
                "artifact_id": artifact_id, "role": role, "path": path,
                "producer_id": "test", "dependencies": [], "lifecycle": "immutable",
                "freshness": "current", "digest_owner": "artifact_dag",
                "digest_algorithm": "sha256", "sha256": sha256(self.project / path),
                "version": "1", "created_at": "2026-08-20T00:00:00Z",
            } for artifact_id, role, path in artifact_rows],
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    # -- helpers ----------------------------------------------------------

    def _write_manifest(self, *, preset: str = "research", extra: dict | None = None) -> None:
        manifest = {
            "schema_version": "2.0", "project_id": "review-project", "run_id": "run-1", "status": "active",
            "stage": "writing", "preset": preset, "profile_overrides": {},
            "competition_profile_ref": {"path": "competition_profile.json", "profile_id": "wp2-fixture"},
            "roots": {
                "model_contract": {"path": "model.json"}, "run_index": {"path": "run_index.json"},
                "artifact_dag": {"path": "artifact_dag.json"},
                "paper": {"path": "paper.txt"}, "abstract": {"path": "abstract.txt"},
                "conclusion": {"path": "conclusion.txt"},
                "frozen_results": {"path": "frozen.json"},
                "evidence_registry": {"path": "evidence.json"},
            },
            "control": {"selection_policy": {"owner": "run_manifest.control", "rule": "exactly one", "version": "2.0"}},
            "safety": {}, "ai_usage": [], "human_checkpoints": [],
        }
        if extra:
            manifest.update(extra)
        write_json(self.project / "run_manifest.json", manifest)

    def _make_bundle(self, *, deny_role: str | None = None) -> Path:
        bundle_dir = self.project / "reports" / "review" / "bundle" / "run-1-test"
        bundle_dir.mkdir(parents=True, exist_ok=True)
        member = bundle_dir / "model_contract.json"
        member.write_text("{}\n", encoding="utf-8")
        files = [{"role": "model_contract", "artifact_id": None, "source_path": "model.json", "path": member.name, "sha256": sha256(member)}]
        if deny_role is not None:
            poisoned = bundle_dir / "previous_verdict.json"
            poisoned.write_text('{"verdict": "pass"}\n', encoding="utf-8")
            files.append({"role": deny_role, "artifact_id": None, "source_path": "reports/review/old.json", "path": poisoned.name, "sha256": sha256(poisoned)})
        manifest = bundle_dir / "bundle_manifest.json"
        write_json(manifest, {
            "schema_version": "1.0", "run_id": "run-1", "created_at": "2026-08-17T00:00:00Z",
            "perspectives": ["semantic_critic"], "files": files,
        })
        return manifest

    def _write_report(
        self,
        perspective: str = "semantic_critic",
        *,
        name: str | None = None,
        findings: list[dict] | None = None,
        verdict: str = "pass",
        review_mode: str = "self_critic",
        independence_level: str = "L0_same_context",
        degraded: bool | None = None,
        bundle_manifest: Path | None = None,
        reviewed: list[dict] | None = None,
        reviewed_at: str | None = None,
        run_id: str = "run-1",
        superseded_by: str | None = None,
        register: bool = True,
    ) -> Path:
        self.report_counter += 1
        reviewed_at = reviewed_at or (
            datetime(2026, 8, 20, tzinfo=timezone.utc) + timedelta(minutes=self.report_counter)
        ).isoformat()
        if reviewed is None:
            role_rows = (
                [("MODEL-1", "model_contract", "model.json"), ("FROZEN-1", "frozen_results", "frozen.json"),
                 ("EVIDENCE-1", "evidence_registry", "evidence.json"), ("PAPER-1", "paper", "paper.txt"),
                 ("ABSTRACT-1", "abstract", "abstract.txt"), ("CONCLUSION-1", "conclusion", "conclusion.txt")]
                if perspective == "semantic_critic"
                else [("PAPER-1", "paper", "paper.txt"), ("ABSTRACT-1", "abstract", "abstract.txt"),
                      ("CONCLUSION-1", "conclusion", "conclusion.txt")]
            )
            reviewed = [
                {"artifact_id": artifact_id, "role": role, "path": path, "sha256": sha256(self.project / path)}
                for artifact_id, role, path in role_rows
            ]
        report: dict = {
            "schema_version": "1.0",
            "report_id": f"REV-{perspective}-001",
            "run_id": run_id,
            "project_id": "review-project",
            "perspective": perspective,
            "review_mode": review_mode,
            "independence_level": independence_level,
            "degraded_independence": degraded if degraded is not None else False,
            "reviewed_at": reviewed_at,
            "reviewed_artifacts": reviewed,
            "rubric_ref": f"references/review/{perspective}.md",
            "findings": findings or [],
            "verdict": verdict,
            "superseded_by": superseded_by,
        }
        if bundle_manifest is not None:
            report["bundle_ref"] = {"path": bundle_manifest.relative_to(self.project).as_posix(), "sha256": sha256(bundle_manifest)}
        receipt_id: str | None = None
        receipt_path: Path | None = None
        if independence_level in {"L1_fresh_context", "L2_independent_model"} and bundle_manifest is not None:
            receipt_id = f"REC-test-{self.report_counter}"
            receipt_path = self.project / "receipts" / f"review-{self.report_counter}.json"
            report["execution_receipt_ref"] = {
                "receipt_id": receipt_id,
                "path": receipt_path.relative_to(self.project).as_posix(),
            }
        path = self.project / "reports" / "review" / (
            name or f"{perspective}-{run_id}-t{self.report_counter}.json"
        )
        write_json(path, report)
        if receipt_id and receipt_path and bundle_manifest is not None:
            write_json(receipt_path, {
                "schema_version": "2.0", "receipt_id": receipt_id, "command_id": f"CMD-{self.report_counter}",
                "run_id": run_id, "stage": "review", "argv": ["test-reviewer"], "cwd": str(bundle_manifest.parent),
                "exit_code": 0, "started_at": reviewed_at, "finished_at": reviewed_at, "duration_s": 0.01,
                "stdout_path": "", "stderr_path": "",
                "input_refs": [{"path": bundle_manifest.relative_to(self.project).as_posix(), "artifact_id": "ART-IN",
                                "critical": True, "sha256": sha256(bundle_manifest), "digest_owner": "command_receipt"}],
                "output_refs": [{"path": path.relative_to(self.project).as_posix(), "artifact_id": "ART-OUT",
                                 "critical": True, "sha256": sha256(path), "digest_owner": "command_receipt"}],
                "selection": {"selected": False},
                "metadata": {"integrity_mode": "submission", "io_hashes_bound": True, "outcome": "success",
                             "note": f"review:{perspective}:{review_mode}:{independence_level}"},
            })
        if register:
            register_review_report(self.project, report, path)
        return path

    def _high_finding(self, *, status: str = "open", perspective: str = "semantic_critic") -> dict:
        return {
            "finding_id": "REV-W2-003", "perspective": perspective, "severity": "high",
            "summary": "Abstract claims global optimality without an optimality certificate.",
            "evidence_locator": "abstract.txt:sentence-1",
            "affected_artifact": "abstract.txt", "affected_claim_id": None,
            "required_fix": "Restrict the claim to the tested baseline comparison.",
            "confidence": "high", "status": status,
        }

    def _medium_finding(self, *, status: str = "open", perspective: str = "semantic_critic") -> dict:
        finding = self._high_finding(status=status, perspective=perspective)
        finding["finding_id"] = "REV-W2-MEDIUM"
        finding["severity"] = "medium"
        return finding

    def test_run_id_is_encoded_as_one_safe_path_component(self) -> None:
        component = _safe_run_component("../国赛/run-1")
        self.assertNotIn("/", component)
        self.assertNotIn("\\", component)
        self.assertNotIn("..", component)

    def test_l3_human_report_binds_artifacts_without_fabricating_a_process_receipt(self) -> None:
        self._write_report(review_mode="human", independence_level="L3_human")
        self._write_report(
            perspective="judge_lens",
            review_mode="self_critic",
            independence_level="L0_same_context",
        )
        summary, errors = evaluate_w2_review(self.project, "submission", run_id="run-1")
        self.assertFalse(errors, errors)
        self.assertTrue(summary["has_current_l1_review"])

    # -- A: research without a semantic report fails W2 -------------------

    def test_A_research_requires_semantic_report(self) -> None:
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("requires a semantic_critic report" in error for error in errors), errors)

    # -- B: open high finding blocks W2 -----------------------------------

    def test_B_open_high_finding_blocks(self) -> None:
        self._write_report(findings=[self._high_finding()], verdict="fail")
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("open blocker/high" in error for error in errors), errors)

    def test_open_medium_requires_resolution_or_accepted_risk(self) -> None:
        self._write_report(findings=[self._medium_finding()], verdict="fail", degraded=True)
        self._write_report("judge_lens", verdict="pass")
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("open medium" in error for error in errors), errors)

    # -- C: resolved finding plus current judge review allows pass ---------

    def test_C_resolved_finding_and_current_reports_allow_pass(self) -> None:
        self._write_report(findings=[self._high_finding(status="resolved")], verdict="pass", degraded=True)
        self._write_report("judge_lens", findings=[], verdict="pass", reviewed_at="2026-08-17T01:05:00Z")
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertFalse(errors, errors)

    # -- D: paper modified after review makes the review stale ------------

    def test_D_paper_change_makes_review_stale(self) -> None:
        self._write_report(verdict="pass")
        self._write_report("judge_lens", verdict="pass", reviewed_at="2026-08-17T01:05:00Z")
        (self.project / "paper.txt").write_text("draft v2 with edits\n", encoding="utf-8")
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("changed since review" in error for error in errors), errors)
        self.assertTrue(any("stale" in error for error in errors), errors)

    # -- E/F: preset derives required perspectives (no review matrix) ------

    def test_E_sprint_does_not_require_judge_lens(self) -> None:
        self.assertEqual(required_perspectives("sprint"), ("semantic_critic",))

    def test_F_research_requires_judge_lens(self) -> None:
        self.assertEqual(required_perspectives("research"), ("semantic_critic", "judge_lens"))
        self._write_manifest(preset="research")
        self._write_report(verdict="pass")  # semantic only
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("requires a judge_lens report" in error for error in errors), errors)

    # -- G: submission requires at least one L1+ current review ------------

    def test_G_submission_requires_l1_independent_review(self) -> None:
        self._write_manifest(preset="submission")
        self._write_report(verdict="pass", degraded=True)
        self._write_report("judge_lens", verdict="pass", reviewed_at="2026-08-17T01:05:00Z")
        _, errors = evaluate_w2_review(self.project, "submission", run_id="run-1")
        self.assertTrue(any("independence_level >= L1" in error for error in errors), errors)
        bundle = self._make_bundle()
        self._write_report(
            review_mode="fresh_context", independence_level="L1_fresh_context",
            bundle_manifest=bundle,
        )
        summary, errors = evaluate_w2_review(self.project, "submission", run_id="run-1")
        self.assertFalse([error for error in errors if "L1" in error], errors)
        self.assertTrue(summary["has_current_l1_review"])

    # -- H: self_critic cannot pose as L1/L2 -------------------------------

    def test_H_self_critic_cannot_claim_independence(self) -> None:
        report = json.loads(self._write_report(
            review_mode="self_critic", independence_level="L1_fresh_context",
        ).read_text(encoding="utf-8"))
        errors = validate_review_report(report)
        self.assertTrue(any("cannot claim independence_level" in error for error in errors), errors)

    # -- I: reviewer mutating a frozen artifact breaks freshness -----------

    def test_I_frozen_artifact_mutation_invalidates_review(self) -> None:
        frozen = self.project / "frozen.json"
        frozen.write_text('{"v": 1}\n', encoding="utf-8")
        self._write_report(reviewed=[
            {"artifact_id": None, "role": "frozen_results", "path": "frozen.json", "sha256": sha256(frozen)},
        ])
        frozen.write_text('{"v": 2}\n', encoding="utf-8")  # reviewer/author edits frozen truth
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("changed since review" in error for error in errors), errors)

    # -- J: hand-edited manifest pass is irrelevant -------------------------

    def test_J_manifest_self_report_is_ignored(self) -> None:
        self._write_manifest(preset="research", extra={"reviewer": {"semantic_critic": {"status": "pass"}}, "semantic_review": "pass"})
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("requires a semantic_critic report" in error for error in errors), errors)

    # -- K: verdict=pass with open blocker/high conflicts -------------------

    def test_K_pass_verdict_with_open_blocking_finding_rejected(self) -> None:
        report = json.loads(self._write_report(findings=[self._high_finding()], verdict="pass").read_text(encoding="utf-8"))
        errors = validate_review_report(report)
        self.assertTrue(any("conflicts with open blocker/high" in error for error in errors), errors)

    # -- L: artifact binding mismatch fails ---------------------------------

    def test_L_binding_digest_mismatch_fails(self) -> None:
        self._write_report(reviewed=[
            {"artifact_id": None, "role": "paper", "path": "paper.txt", "sha256": "0" * 64},
        ])
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("changed since review" in error for error in errors), errors)

    # -- M: bundle containing a previous verdict voids independence ---------

    def test_M_contaminated_bundle_voids_independence(self) -> None:
        bundle = self._make_bundle(deny_role="previous_verdict")
        report = json.loads(self._write_report(
            review_mode="fresh_context", independence_level="L1_fresh_context", bundle_manifest=bundle,
        ).read_text(encoding="utf-8"))
        errors = validate_bundle_boundary(report, self.project)
        self.assertTrue(any("denied input role" in error for error in errors), errors)

    def test_bundle_member_cannot_escape_materialized_bundle(self) -> None:
        bundle = self._make_bundle()
        value = json.loads(bundle.read_text(encoding="utf-8"))
        value["files"].append({
            "role": "paper", "artifact_id": "PAPER-1", "source_path": "paper.txt",
            "path": "../../../paper.txt", "sha256": sha256(self.project / "paper.txt"),
        })
        write_json(bundle, value)
        report_path = self._write_report(
            review_mode="fresh_context", independence_level="L1_fresh_context",
            bundle_manifest=bundle, register=False,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        errors = validate_bundle_boundary(report, self.project)
        self.assertTrue(any("escapes the materialized bundle" in error for error in errors), errors)

    # -- N: same-context reviewer flagged as independent_model fails --------

    def test_N_same_context_cannot_be_independent_model(self) -> None:
        report = json.loads(self._write_report(
            review_mode="independent_model", independence_level="L2_independent_model",
        ).read_text(encoding="utf-8"))
        # The mode/level pair is legal; but an L2 claim without a bundle is not.
        errors = validate_review_report(report)
        self.assertTrue(any("requires a bundle_ref" in error for error in errors), errors)

    # -- O: paper changed after pass → stale (discovery→summary chain) ------

    def test_O_paper_change_invalidates_previous_pass(self) -> None:
        self._write_report(verdict="pass")
        self._write_report("judge_lens", verdict="pass", reviewed_at="2026-08-17T01:05:00Z")
        summary = summarize_review(self.project, "research")
        self.assertEqual(summary["perspectives"]["semantic_critic"]["freshness"], "current")
        (self.project / "paper.txt").write_text("draft v2\n", encoding="utf-8")
        summary = summarize_review(self.project, "research")
        self.assertEqual(summary["perspectives"]["semantic_critic"]["freshness"], "stale")
        self.assertEqual(summary["perspectives"]["judge_lens"]["freshness"], "stale")

    # -- P: harness status exposes the review summary -----------------------

    def test_P_status_exposes_review_summary(self) -> None:
        self._write_report(findings=[self._high_finding()], verdict="fail")
        self._write_report("judge_lens", verdict="pass", reviewed_at="2026-08-17T01:05:00Z")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "harness_status.py"), "--manifest", "run_manifest.json",
             "--project-root", str(self.project), "--json"],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        report = json.loads(result.stdout)
        review = report.get("review", {})
        semantic = review.get("perspectives", {}).get("semantic_critic", {})
        self.assertTrue(semantic.get("executed"))
        self.assertEqual(semantic.get("freshness"), "current")
        self.assertEqual(semantic.get("severity_counts", {}).get("high"), 1)
        self.assertEqual(semantic.get("independence_level"), "L0_same_context")
        self.assertIn("judge_lens", review.get("perspectives", {}))
        self.assertIn("REV-W2-003", report.get("next_action", ""))

    # -- Q: harness review --recheck registers a real review artifact -------

    def test_Q_recheck_validates_and_registers_review_artifact(self) -> None:
        self._write_report(verdict="pass", degraded=True, register=False)
        self._write_report("judge_lens", verdict="pass", reviewed_at="2026-08-17T01:05:00Z", register=False)
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "qa" / "run_review.py"),
             "--manifest", "run_manifest.json", "--project-root", str(self.project), "--recheck", "--json"],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        dag = json.loads((self.project / "artifact_dag.json").read_text(encoding="utf-8"))
        roles = {node["role"] for node in dag["nodes"]}
        self.assertIn("review_report", roles)
        self.assertEqual(len([node for node in dag["nodes"] if node["role"] == "review_report"]), 2)

    # -- degraded L0 fallback must be explicit in research ------------------

    def test_research_l0_fallback_must_be_marked_degraded(self) -> None:
        self._write_report(verdict="pass", degraded=False)  # poses as a real review
        self._write_report("judge_lens", verdict="pass", reviewed_at="2026-08-17T01:05:00Z")
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("degraded_independence" in error for error in errors), errors)
        # With the explicit degraded marker the fallback is acceptable.
        self._write_report(verdict="pass", degraded=True)
        summary, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertFalse([error for error in errors if "degraded" in error], errors)

    # -- run_id mismatch: a report from another run cannot pass W2 ----------

    def test_foreign_run_report_cannot_satisfy_current_run(self) -> None:
        self._write_report(run_id="run-other", verdict="pass")
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("none was found" in error for error in errors), errors)

    def test_foreign_newer_report_does_not_poison_current_run(self) -> None:
        self._write_report(verdict="pass", degraded=True)
        self._write_report("judge_lens", verdict="pass")
        self._write_report(run_id="run-other", verdict="pass", reviewed_at="2099-01-01T00:00:00Z")
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertFalse(errors, errors)

    def test_malformed_current_report_blocks_instead_of_falling_back(self) -> None:
        self._write_report(verdict="pass", degraded=True)
        self._write_report("judge_lens", verdict="pass")
        broken = self.project / "reports" / "review" / "semantic_critic-run-1-broken.json"
        broken.write_text("{not json", encoding="utf-8")
        _, errors = evaluate_w2_review(self.project, "research", run_id="run-1")
        self.assertTrue(any("unreadable" in error for error in errors), errors)

    def test_receipt_bound_report_tamper_blocks_w2(self) -> None:
        bundle = self._make_bundle()
        path = self._write_report(
            review_mode="fresh_context", independence_level="L1_fresh_context",
            bundle_manifest=bundle,
        )
        self._write_report("judge_lens", verdict="pass")
        report = json.loads(path.read_text(encoding="utf-8"))
        report["notes"] = "tampered after receipt"
        write_json(path, report)
        _, errors = evaluate_w2_review(self.project, "submission", run_id="run-1")
        self.assertTrue(any("SHA-256 drift" in error for error in errors), errors)

    def test_fresh_review_receipt_must_run_from_bundle_directory(self) -> None:
        bundle = self._make_bundle()
        report_path = self._write_report(
            review_mode="fresh_context",
            independence_level="L1_fresh_context",
            bundle_manifest=bundle,
        )
        report = json.loads(report_path.read_text(encoding="utf-8"))
        receipt_path = self.project / report["execution_receipt_ref"]["path"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["cwd"] = str(self.project)
        write_json(receipt_path, receipt)
        _, errors = evaluate_w2_review(self.project, "submission", run_id="run-1")
        self.assertTrue(any("bundle directory" in error for error in errors), errors)

    # -- Gate integration: check_gates W2 surfaces review evidence errors ---

    def test_gate_w2_consumes_review_evidence(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "qa" / "check_gates.py"), "--manifest", "run_manifest.json",
             "--project-root", str(self.project), "--gate", "w2"],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires a semantic_critic report", result.stdout)
        self.assertIn("requires a judge_lens report", result.stdout)
        self._write_report(findings=[self._high_finding()], verdict="fail")
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "qa" / "check_gates.py"), "--manifest", "run_manifest.json",
             "--project-root", str(self.project), "--gate", "w2"],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("REV-W2-003", result.stdout)


if __name__ == "__main__":
    unittest.main()
