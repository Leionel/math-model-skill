from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evaluation" / "recovery" / "fixtures" / "slim_v2"
HARNESS = ROOT / "scripts" / "harness.py"
SCHEMAS = ROOT / "schemas"

sys.path.insert(0, str(ROOT / "scripts"))

from qa.validate_contracts import _validate_document  # noqa: E402


@unittest.skipUnless(FIXTURE.is_dir(), "slim fixture has not been generated yet")
class RecoveryFixtureTest(unittest.TestCase):
    """The recovery benchmark's pinned baseline: the fixture must be a fully
    green v2 project so that every fault injection is an attributable delta."""

    def test_control_files_are_schema_valid(self) -> None:
        cases = {
            "run_manifest.json": "run_manifest.schema.json",
            "run_index.json": "run_index.schema.json",
            "artifact_dag.json": "artifact_dag.schema.json",
            "frozen_results.json": "frozen_results.schema.json",
            "model_contract.json": "model_contract.schema.json",
            "evidence_registry.json": "evidence_registry.schema.json",
        }
        for name, schema in cases.items():
            with self.subTest(file=name):
                _, errors, _ = _validate_document(FIXTURE / name, SCHEMAS / schema)
                self.assertEqual(errors, [])

    def test_receipts_are_schema_valid(self) -> None:
        receipts = sorted((FIXTURE / "receipts").glob("*.json"))
        self.assertTrue(receipts)
        for receipt in receipts:
            with self.subTest(receipt=receipt.name):
                _, errors, _ = _validate_document(receipt, SCHEMAS / "command_receipt.schema.json")
                self.assertEqual(errors, [])

    def _check(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HARNESS), *args, "--project", str(FIXTURE), "--json"],
            cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", check=False,
        )

    def test_fixture_is_fully_green(self) -> None:
        for gate in ("M1", "P1", "P2"):
            with self.subTest(gate=gate):
                result = self._check("check", gate)
                self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])
        status = self._check("status")
        self.assertEqual(status.returncode, 0, status.stdout[-2000:])
        self.assertTrue(json_payload(status.stdout)["ok"])

    def test_validate_passes(self) -> None:
        result = self._check("validate")
        self.assertEqual(result.returncode, 0, result.stdout[-2000:] + result.stderr[-2000:])


def json_payload(stdout: str) -> dict:
    import json

    return json.loads(stdout)


if __name__ == "__main__":
    unittest.main()
