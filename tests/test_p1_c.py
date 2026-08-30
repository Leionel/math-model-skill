"""Regression tests for P1-C derived views and provider boundaries."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from harness_status import _failures_summary  # noqa: E402
import mcp_server  # noqa: E402
from qa.check_drawio_delivery import check_delivery  # noqa: E402
from redaction import redact_text, redact_value  # noqa: E402
from views.setup_card import build_setup_card  # noqa: E402


class P1CViewsAndBoundaryTest(unittest.TestCase):
    def test_setup_card_is_draft_only_and_does_not_need_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="setup-card-") as temp:
            project = Path(temp)
            card = build_setup_card(project, stage="M1")
            self.assertEqual(card["status"], "draft")
            self.assertTrue(card["requires_user_confirmation"])
            self.assertEqual(card["execution_policy"], "draft_only")
            self.assertTrue((project / ".harness" / "views" / "SETUP_CARD.md").is_file())
            self.assertIn("DRAFT ONLY", (project / ".harness" / "views" / "SETUP_CARD.md").read_text(encoding="utf-8"))

    def test_failures_summary_is_a_derived_repair_view(self) -> None:
        summary = _failures_summary(
            {"m1": {"status": "blocked", "errors": ["model contract missing"], "warnings": []}},
            [],
            {"errors": [], "failed_receipt_ids": ["REC-1"]},
            {"stale_artifacts": [{"artifact_id": "ART-1", "reason": "digest drift"}]},
            None,
        )
        self.assertEqual(summary["count"], 3)
        self.assertTrue(all({"source", "severity", "message", "next_action"} <= item.keys() for item in summary["items"]))

    def test_drawio_delivery_reports_missing_environment_without_claiming_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="drawio-delivery-") as temp:
            project = Path(temp)
            source = project / "diagram.drawio"
            source.write_text("<mxfile />\n", encoding="utf-8")
            report, code = check_delivery(
                project,
                "diagram.drawio",
                drawio=str(project / "missing-drawio.exe"),
                pdfinfo=str(project / "missing-pdfinfo.exe"),
                pdftoppm=str(project / "missing-pdftoppm.exe"),
            )
        self.assertEqual(code, 3)
        self.assertFalse(report["ok"])
        self.assertEqual(report["status"], "not_available")
        self.assertEqual(report["scope"], "delivery_chain_only")
        self.assertIn("environment", report)

    def test_drawio_delivery_rejects_paths_outside_project(self) -> None:
        with tempfile.TemporaryDirectory(prefix="drawio-root-") as temp:
            project = Path(temp) / "project"
            project.mkdir()
            outside = Path(temp) / "outside.drawio"
            outside.write_text("<mxfile />\n", encoding="utf-8")
            report, code = check_delivery(project, str(outside))
        self.assertEqual(code, 1)
        self.assertEqual(report["status"], "failed")
        self.assertTrue(any("project root" in error for error in report["errors"]))

    def test_redaction_preserves_labels_and_removes_credentials(self) -> None:
        secret = "sk-test-abcdefghijklmnop"
        cleaned = redact_text(f"API_KEY={secret}; Bearer abcdefghijklmnop")
        self.assertIn("API_KEY=[REDACTED]", cleaned)
        self.assertNotIn(secret, cleaned)
        self.assertNotIn("Bearer abcdefghijklmnop", cleaned)
        self.assertEqual(redact_value({"api_key": "short", "metric": 0.7}), {"api_key": "[REDACTED]", "metric": 0.7})

    def test_mcp_process_surface_is_redacted(self) -> None:
        with tempfile.TemporaryDirectory(prefix="mcp-redaction-") as temp:
            project = Path(temp)
            secret = "sk-test-abcdefghijklmnop"
            code = "print('API_KEY=" + secret + "')"
            exit_code, stdout, stderr = mcp_server.run_harness(
                [sys.executable, "-c", code], project,
            )
        self.assertEqual(exit_code, 0)
        self.assertNotIn(secret, stdout + stderr)


if __name__ == "__main__":
    unittest.main()
