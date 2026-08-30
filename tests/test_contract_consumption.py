"""R8 contract-consumption audit: every schema reports its consumers, and
orphan/test-only schemas are surfaced instead of accumulating silently."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa.audit_contract_consumption import audit_contract_consumption  # noqa: E402


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "qa" / "audit_contract_consumption.py"), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )


class CommittedRepoTest(unittest.TestCase):
    def test_every_schema_is_listed(self) -> None:
        result = _run_cli("--repo-root", str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout[-3000:])
        payload = json.loads(result.stdout)
        self.assertEqual(payload["method"], "textual_schema_filename_reference")
        self.assertIn("not dynamic execution", payload["boundary"])
        expected = len(list((ROOT / "schemas").glob("*.schema.json")))
        self.assertEqual(payload["summary"]["total"], expected)
        self.assertEqual(len(payload["schemas"]), expected)

    def test_figure_qa_schema_has_runtime_consumer(self) -> None:
        report = audit_contract_consumption(ROOT)
        row = next(item for item in report["schemas"] if item["schema"] == "schemas/figure_qa.schema.json")
        self.assertFalse(row["orphan"], row)
        self.assertIn("scripts/figures/check_figure.py", row["script_consumers"])


class OrphanDetectionTest(unittest.TestCase):
    def _make_repo(self, root: Path) -> None:
        (root / "schemas").mkdir()
        (root / "schemas" / "alive.schema.json").write_text("{}", encoding="utf-8")
        (root / "schemas" / "dead.schema.json").write_text("{}", encoding="utf-8")
        (root / "schemas" / "test_only.schema.json").write_text("{}", encoding="utf-8")
        scripts = root / "scripts" / "qa"
        scripts.mkdir(parents=True)
        (scripts / "consumer.py").write_text("SCHEMA = 'alive.schema.json'\n", encoding="utf-8")
        tests = root / "tests"
        tests.mkdir()
        (tests / "test_consumer.py").write_text("SCHEMA = 'test_only.schema.json'\n", encoding="utf-8")

    def test_orphan_and_test_only_are_flagged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="consumption-") as temp:
            root = Path(temp)
            self._make_repo(root)
            result = _run_cli("--repo-root", str(root))
            self.assertEqual(result.returncode, 0, result.stdout[-3000:])
            payload = json.loads(result.stdout)
            self.assertEqual(payload["summary"], {"total": 3, "orphan": 1, "test_only": 1, "gate_wired": 0})
            joined = "\n".join(payload["warnings"])
            self.assertIn("dead.schema.json has no textual consumer", joined)
            self.assertIn("test_only.schema.json is referenced only in tests", joined)
            self.assertNotIn("alive.schema.json", joined)

    def test_strict_mode_fails_on_orphans(self) -> None:
        with tempfile.TemporaryDirectory(prefix="consumption-") as temp:
            root = Path(temp)
            self._make_repo(root)
            result = _run_cli("--repo-root", str(root), "--strict")
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["ok"])


if __name__ == "__main__":
    unittest.main()
