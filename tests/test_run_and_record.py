from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa.validate_contracts import _validate_document  # noqa: E402


class RunAndRecordTest(unittest.TestCase):
    def _run(self, *args: str, cwd: Path):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "run_and_record.py"), *args],
            cwd=str(cwd), text=True, capture_output=True, encoding="utf-8", check=False,
        )

    def test_success_and_failure_receipts_with_index(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-run-record-") as temp:
            project = Path(temp)
            (project / "input.txt").write_text("demand\n", encoding="utf-8")

            ok = self._run(
                "--run-id", "run-001", "--stage", "full",
                "--receipt", "reports/receipt_ok.json", "--index", "reports/run_index.json",
                "--selected", "--selection-policy", "first successful full run is selected",
                "--input", "input.txt", "--output-artifact", "results/out.txt", "--note", "baseline full run",
                "--", sys.executable, "-c",
                "from pathlib import Path; Path('results').mkdir(exist_ok=True); Path('results/out.txt').write_text('42\\n', encoding='utf-8')",
                cwd=project,
            )
            self.assertEqual(ok.returncode, 0, ok.stderr[-800:])
            receipt = json.loads((project / "reports" / "receipt_ok.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["exit_code"], 0)
            self.assertEqual(receipt["argv"][0], sys.executable)
            self.assertEqual(receipt["output_refs"][0]["existed_before"], False)
            _, schema_errors, _ = _validate_document(
                project / "reports" / "receipt_ok.json", ROOT / "schemas" / "command_receipt.schema.json"
            )
            self.assertEqual(schema_errors, [])

            fail = self._run(
                "--run-id", "run-001", "--stage", "full",
                "--receipt", "reports/receipt_fail.json", "--index", "reports/run_index.json",
                "--selection-policy", "first successful full run is selected",
                "--note", "failed tuning run, kept for audit",
                "--", sys.executable, "-c", "import sys; sys.exit(3)",
                cwd=project,
            )
            self.assertEqual(fail.returncode, 3)
            failed_receipt = json.loads((project / "reports" / "receipt_fail.json").read_text(encoding="utf-8"))
            self.assertEqual(failed_receipt["exit_code"], 3)

            index = json.loads((project / "reports" / "run_index.json").read_text(encoding="utf-8"))
            self.assertEqual(len(index["runs"]), 2)
            self.assertEqual([r["exit_code"] for r in index["runs"]], [0, 3])
            self.assertEqual([r["selected"] for r in index["runs"]], [True, False])
            _, index_errors, _ = _validate_document(
                project / "reports" / "run_index.json", ROOT / "schemas" / "run_index.schema.json"
            )
            self.assertEqual(index_errors, [])

    def test_missing_declared_output_is_reported_not_swallowed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-run-record-missing-") as temp:
            project = Path(temp)
            result = self._run(
                "--run-id", "run-002", "--stage", "smoke",
                "--receipt", "reports/receipt.json",
                "--output-artifact", "results/never_created.txt",
                "--", sys.executable, "-c", "print('ran fine')",
                cwd=project,
            )
            self.assertEqual(result.returncode, 3)
            self.assertIn("was not produced", result.stdout)


if __name__ == "__main__":
    unittest.main()
