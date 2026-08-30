"""Regression tests for the P1 review evidence-scope boundary."""

from __future__ import annotations

import copy
import unittest

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa.review_evidence import validate_review_report  # noqa: E402


def _report(*, finding: dict | None = None, available: str | None = None) -> dict:
    value: dict = {
        "schema_version": "1.0",
        "report_id": "REV-semantic_critic-scope",
        "run_id": "run-1",
        "project_id": "project-1",
        "perspective": "semantic_critic",
        "review_mode": "self_critic",
        "independence_level": "L0_same_context",
        "reviewed_at": "2026-08-28T00:00:00+00:00",
        "reviewed_artifacts": [
            {"role": "model_contract", "path": "model.json", "sha256": "a" * 64},
            {"role": "frozen_results", "path": "frozen.json", "sha256": "b" * 64},
            {"role": "evidence_registry", "path": "evidence.json", "sha256": "c" * 64},
            {"role": "paper", "path": "paper.txt", "sha256": "d" * 64},
        ],
        "findings": [finding] if finding else [],
        "verdict": "fail" if finding and finding.get("status") == "open" else "pass",
    }
    if available is not None:
        value["available_evidence_scope"] = available
    return value


def _finding(**overrides: object) -> dict:
    value = {
        "finding_id": "REV-SCOPE-001",
        "perspective": "semantic_critic",
        "severity": "high",
        "summary": "The result needs a rerunnable check.",
        "evidence_locator": "paper.txt:12",
        "affected_artifact": "paper.txt",
        "affected_claim_id": None,
        "required_fix": "Run the declared command and bind its receipt.",
        "confidence": "high",
        "status": "open",
        "required_evidence_scope": "rerunnable",
    }
    value.update(overrides)
    return value


class ReviewEvidenceScopeTest(unittest.TestCase):
    def test_high_finding_cannot_self_upgrade_from_paper_only(self) -> None:
        errors = validate_review_report(_report(finding=_finding(), available="paper_only"))
        self.assertTrue(any("requires rerunnable evidence" in error for error in errors))
        self.assertTrue(any("requires_external_check=true" in error for error in errors))

    def test_external_check_marker_allows_scope_limited_finding(self) -> None:
        finding = _finding(requires_external_check=True)
        report = _report(finding=finding, available="paper_only")
        self.assertEqual(validate_review_report(report), [])

    def test_free_text_locator_cannot_upgrade_results_to_rerunnable(self) -> None:
        finding = _finding(
            evidence_locator="model_receipt REC-test-1; command run_model.py",
            requires_external_check=True,
        )
        report = _report(finding=finding)
        self.assertEqual(validate_review_report(report), [])
        report["available_evidence_scope"] = "rerunnable"
        errors = validate_review_report(report)
        self.assertTrue(any("cannot self-upgrade" in error for error in errors))

    def test_declared_scope_cannot_exceed_bound_roles(self) -> None:
        report = _report(available="rerunnable")
        report["reviewed_artifacts"] = [
            {"role": "paper", "path": "paper.txt", "sha256": "d" * 64},
        ]
        errors = validate_review_report(report)
        self.assertTrue(any("cannot self-upgrade" in error for error in errors))

    def test_legacy_report_without_scope_fields_remains_valid(self) -> None:
        report = _report()
        self.assertEqual(validate_review_report(copy.deepcopy(report)), [])


if __name__ == "__main__":
    unittest.main()
