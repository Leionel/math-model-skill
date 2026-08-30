"""R9 living-architecture: design-doc claims are reconciled against code, and
a drifted claim (or a doc missing its verified_against marker) is surfaced."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa.check_doc_claims import check_doc_claims, scan_verified_against  # noqa: E402


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "qa" / "check_doc_claims.py"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )


class CommittedManifestTest(unittest.TestCase):
    def test_committed_claims_all_pass(self) -> None:
        result = _run_cli("--repo-root", str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(len(payload["results"]), 6)
        for row in payload["results"]:
            self.assertTrue(row["ok"], row)

    def test_review_docs_carry_verified_against(self) -> None:
        result = _run_cli(
            "--repo-root", str(ROOT),
            "--doc-dir", "docs/architecture_review_2026-08-28",
        )
        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["warnings"], [], payload["warnings"])


class DriftDetectionTest(unittest.TestCase):
    def test_drifted_claim_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docclaims-") as temp:
            root = Path(temp)
            manifest = {
                "schema_version": "1.0",
                "claims": [
                    {
                        "claim_id": "X-1",
                        "doc": "some_doc.md",
                        "doc_pattern": "projection exists",
                        "statement": "a projection exists",
                        "check": {"type": "file_contains", "path": "scripts/views/does_not_exist.py", "pattern": "def build"},
                    }
                ],
            }
            (root / "some_doc.md").write_text("a projection exists\n", encoding="utf-8")
            claims_path = root / "DOC_CLAIMS.json"
            claims_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = check_doc_claims(root, claims_path)
            self.assertFalse(report["ok"])
            self.assertTrue(any("X-1" in e for e in report["errors"]))

    def test_unsupported_check_type_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docclaims-") as temp:
            root = Path(temp)
            manifest = {"schema_version": "1.0", "claims": [
                {"claim_id": "X-2", "doc": "d.md", "doc_pattern": "s", "statement": "s", "check": {"type": "nope"}}
            ]}
            claims_path = root / "DOC_CLAIMS.json"
            claims_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = check_doc_claims(root, claims_path)
            self.assertFalse(report["ok"])
            self.assertTrue(any("unsupported check type" in e for e in report["errors"]))

    def test_code_presence_does_not_pass_when_named_doc_lacks_the_claim(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docclaims-") as temp:
            root = Path(temp)
            (root / "code.py").write_text("def build():\n    pass\n", encoding="utf-8")
            (root / "design.md").write_text("# Design\nNo implementation assertion here.\n", encoding="utf-8")
            manifest = {
                "schema_version": "1.0",
                "claims": [
                    {
                        "claim_id": "X-3",
                        "doc": "design.md",
                        "doc_pattern": "projection is implemented",
                        "statement": "projection is implemented",
                        "check": {"type": "file_contains", "path": "code.py", "pattern": "def build"},
                    }
                ],
            }
            claims_path = root / "DOC_CLAIMS.json"
            claims_path.write_text(json.dumps(manifest), encoding="utf-8")
            report = check_doc_claims(root, claims_path)
            self.assertFalse(report["ok"])
            self.assertFalse(report["results"][0]["document_ok"])
            self.assertTrue(report["results"][0]["code_ok"])

    def test_missing_verified_against_marker_warns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docclaims-") as temp:
            root = Path(temp)
            doc_dir = root / "docs"
            doc_dir.mkdir()
            (doc_dir / "design.md").write_text("# design\nno marker here\n", encoding="utf-8")
            errors, warnings = scan_verified_against(root, doc_dir, None)
            self.assertEqual(errors, [])
            self.assertTrue(any("verified_against" in w for w in warnings))

    def test_stale_verified_against_warns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docclaims-") as temp:
            root = Path(temp)
            doc_dir = root / "docs"
            doc_dir.mkdir()
            (doc_dir / "design.md").write_text("# design\nverified_against: 2020-01-01@abc\n", encoding="utf-8")
            errors, warnings = scan_verified_against(root, doc_dir, 30)
            self.assertEqual(errors, [])
            self.assertTrue(any("re-reconcile" in w for w in warnings))

    def test_verified_against_without_revision_warns(self) -> None:
        with tempfile.TemporaryDirectory(prefix="docclaims-") as temp:
            root = Path(temp)
            doc_dir = root / "docs"
            doc_dir.mkdir()
            (doc_dir / "design.md").write_text("verified_against: 2026-08-28\n", encoding="utf-8")
            errors, warnings = scan_verified_against(root, doc_dir, None)
            self.assertEqual(errors, [])
            self.assertTrue(any("revision" in warning for warning in warnings))


if __name__ == "__main__":
    unittest.main()
