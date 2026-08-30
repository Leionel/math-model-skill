"""R8 consumer closure for the human portal submission receipt."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from _common import sha256_file  # noqa: E402
from qa.check_submission_receipt import check_submission_receipt  # noqa: E402


class SubmissionReceiptTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="submission-receipt-")
        self.project = Path(self.temp.name)
        (self.project / "paper.pdf").write_bytes(b"%PDF-1.4\nfinal")
        (self.project / "s1.json").write_text("{}", encoding="utf-8")
        (self.project / "rules.txt").write_text("fixture rule", encoding="utf-8")
        (self.project / "portal.png").write_bytes(b"accepted screenshot")
        profile = {
            "schema_version": "2.0",
            "profile_id": "fixture",
            "status": "verified",
            "competition": {"family": "fixture", "name": "Fixture", "season": "2026", "mode": "pre_contest", "language": "en"},
            "official_rules": [{"rule_id": "R1", "title": "rule", "url": "https://example.invalid/rule", "retrieved_at": "2026-08-29", "snapshot": {"path": "rules.txt"}}],
            "official_submission_endpoints": ["https://example.invalid/submit"],
            "submission": {"paper_extensions": [".pdf"], "page_count_scope": "all", "support_policy": "optional", "ai_disclosure_policy": "optional", "required_manual_checks": ["confirm"]},
            "template_id": "fixture",
        }
        (self.project / "competition_profile.json").write_text(json.dumps(profile), encoding="utf-8")
        run_manifest = {
            "schema_version": "2.0",
            "project_id": "project",
            "run_id": "run-1",
            "status": "active",
            "stage": "submission",
            "preset": "submission",
            "profile_overrides": {},
            "competition_profile_ref": {"path": "competition_profile.json", "profile_id": "fixture"},
            "roots": {},
            "control": {"selection_policy": {"owner": "run_manifest.control", "rule": "exactly one selected receipt", "version": "2.0"}},
            "safety": {},
            "ai_usage": [],
            "human_checkpoints": [],
        }
        (self.project / "run_manifest.json").write_text(json.dumps(run_manifest), encoding="utf-8")
        paper = self.project / "paper.pdf"
        submission = {
            "schema_version": "1.1",
            "project_id": "project",
            "run_id": "run-1",
            "status": "final_frozen",
            "frozen_at": "2026-08-29T00:00:00+08:00",
            "competition": {"profile_id": "fixture", "competition": "Fixture", "season": "2026", "profile_sha256": "0" * 64, "rule_snapshots": [{"path": "rules.txt", "sha256": sha256_file(self.project / "rules.txt")}]},
            "deadline": {"closes_at": "2026-08-30T00:00:00+08:00", "timezone": "Asia/Hong_Kong"},
            "paper": {"path": "paper.pdf", "sha256": sha256_file(paper), "bytes": paper.stat().st_size, "pages": 1, "page_count_method": "manual_verified", "limited_pages": 1, "ai_report_pages": 0},
            "support_files": [],
            "ai_disclosure": None,
            "s1_report": {"path": "s1.json", "sha256": sha256_file(self.project / "s1.json")},
            "run_manifest": {"path": "run_manifest.json", "sha256": sha256_file(self.project / "run_manifest.json")},
            "package_sha256": "1" * 64,
            "builder": {"name": "fixture", "version": "1"},
        }
        (self.project / "submission_manifest.json").write_text(json.dumps(submission), encoding="utf-8")
        self.receipt = {
            "schema_version": "1.0",
            "submission_manifest": {"path": "submission_manifest.json", "sha256": sha256_file(self.project / "submission_manifest.json")},
            "submitted_file": {"path": "paper.pdf", "sha256": sha256_file(paper)},
            "portal": "https://example.invalid/submit/entry",
            "control_id": "CONTROL-123",
            "submitted_at": "2026-08-29T01:00:00+08:00",
            "portal_status": "accepted",
            "evidence": [{"path": "portal.png", "sha256": sha256_file(self.project / "portal.png")}],
            "confirmed_by_role": "team_leader",
            "confirmed_at": "2026-08-29T01:05:00+08:00",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_receipt(self) -> Path:
        path = self.project / "submission_receipt.json"
        path.write_text(json.dumps(self.receipt), encoding="utf-8")
        return path

    def test_accepted_receipt_binds_frozen_file_and_official_portal(self) -> None:
        report = check_submission_receipt(self._write_receipt(), self.project, ROOT / "schemas")
        self.assertTrue(report["ok"], report["errors"])
        self.assertTrue(report["submission_accepted"])

    def test_unfrozen_submitted_file_is_blocked(self) -> None:
        extra = self.project / "other.pdf"
        extra.write_bytes(b"%PDF-1.4\nother")
        self.receipt["submitted_file"] = {"path": "other.pdf", "sha256": sha256_file(extra)}
        report = check_submission_receipt(self._write_receipt(), self.project, ROOT / "schemas")
        self.assertFalse(report["ok"])
        self.assertTrue(any("not one of the immutable files" in message for message in report["errors"]))

    def test_pending_portal_status_does_not_prove_submission(self) -> None:
        self.receipt["portal_status"] = "pending"
        report = check_submission_receipt(self._write_receipt(), self.project, ROOT / "schemas")
        self.assertFalse(report["ok"])
        self.assertFalse(report["submission_accepted"])

    def test_lookalike_portal_prefix_is_not_an_official_endpoint(self) -> None:
        self.receipt["portal"] = "https://example.invalid/submit-evil"
        report = check_submission_receipt(self._write_receipt(), self.project, ROOT / "schemas")
        self.assertFalse(report["ok"])
        self.assertTrue(any("official_submission_endpoints" in message for message in report["errors"]))

    def test_harness_receipt_facade_preserves_checker_exit_code(self) -> None:
        self._write_receipt()
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "harness.py"), "submit", "receipt", "--receipt", "submission_receipt.json", "--project", str(self.project), "--json"],
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])


if __name__ == "__main__":
    unittest.main()
