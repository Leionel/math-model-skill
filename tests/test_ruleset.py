from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.ruleset import ruleset_fingerprint


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness.py"


class RulesetFingerprintTest(unittest.TestCase):
    def _checkout(self, target: Path) -> None:
        shutil.copy2(ROOT / "SKILL.md", target / "SKILL.md")
        for name in ("schemas", "competition_profiles", "references"):
            shutil.copytree(ROOT / name, target / name, ignore=shutil.ignore_patterns("local-sources", "*.pdf", "*.png", "*.doc", "*.docx", "*.zip", "*.rar"))

    def test_scope_is_explicit_and_core_changes_invalidate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ruleset-core-") as temp:
            checkout = Path(temp) / "checkout"
            clean_checkout = Path(temp) / "clean-checkout"
            checkout.mkdir()
            clean_checkout.mkdir()
            self._checkout(checkout)
            self._checkout(clean_checkout)

            first = ruleset_fingerprint(checkout)
            self.assertEqual(first["ruleset_id"], ruleset_fingerprint(clean_checkout)["ruleset_id"])
            self.assertEqual(len(first["ruleset_id"]), 64)
            self.assertIn("SKILL.md", first["ruleset_files"])
            self.assertIn("schemas/run_manifest.schema.json", first["ruleset_files"])
            self.assertIn("references/contracts/artifact_contracts.md", first["ruleset_files"])
            self.assertNotIn("references/cards/methods/milp.md", first["ruleset_files"])
            self.assertNotIn("references/precedents/pattern-cards/example.md", first["ruleset_files"])

            core = checkout / "references" / "workflow" / "gate_policy.md"
            core.write_text(core.read_text(encoding="utf-8") + "\n\nCore ruleset regression fixture.\n", encoding="utf-8")
            second = ruleset_fingerprint(checkout)
            self.assertNotEqual(first["ruleset_id"], second["ruleset_id"])

    def test_quarantined_and_generated_material_does_not_invalidate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ruleset-excluded-") as temp:
            checkout = Path(temp) / "checkout"
            checkout.mkdir()
            self._checkout(checkout)
            first = ruleset_fingerprint(checkout)

            for relative in (
                "references/cards/methods/fixture.md",
                "references/precedents/pattern-cards/fixture.md",
                "references/precedents/local-sources/fixture.md",
                ".harness/views/fixture.md",
                "receipts/fixture.json",
            ):
                path = checkout / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("excluded v1\n", encoding="utf-8")
            second = ruleset_fingerprint(checkout)
            self.assertEqual(first["ruleset_id"], second["ruleset_id"])
            self.assertEqual(first["ruleset_scope"], second["ruleset_scope"])

            (checkout / "references" / "precedents" / "pattern-cards" / "fixture.md").write_text("excluded v2\n", encoding="utf-8")
            (checkout / ".harness" / "views" / "fixture.md").write_text("excluded v2\n", encoding="utf-8")
            self.assertEqual(first["ruleset_id"], ruleset_fingerprint(checkout)["ruleset_id"])

    def test_status_and_context_expose_same_ruleset_scope(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ruleset-cli-") as temp:
            project = Path(temp) / "project"
            init = subprocess.run(
                [sys.executable, str(CLI), "init", "--project", str(project), "--competition", "cumcm", "--preset", "research", "--json"],
                cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
            )
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
            status = subprocess.run(
                [sys.executable, str(CLI), "status", "--project", str(project), "--json"],
                cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
            )
            context = subprocess.run(
                [sys.executable, str(CLI), "context", "--stage", "research", "--project", str(project), "--json"],
                cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
            )
            self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
            self.assertEqual(context.returncode, 0, context.stdout + context.stderr)
            status_value = json.loads(status.stdout)
            context_value = json.loads(context.stdout)
            self.assertEqual(status_value["ruleset_id"], context_value["ruleset_id"])
            self.assertEqual(status_value["ruleset_scope"], context_value["ruleset_scope"])

    def test_execute_is_the_public_receipt_capturing_alias(self) -> None:
        with tempfile.TemporaryDirectory(prefix="ruleset-execute-") as temp:
            project = Path(temp) / "project"
            init = subprocess.run(
                [sys.executable, str(CLI), "init", "--project", str(project), "--competition", "cumcm", "--preset", "sprint", "--json"],
                cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
            )
            self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
            execute = subprocess.run(
                [sys.executable, str(CLI), "execute", "--project", str(project), "--stage", "smoke", "--json", "--", sys.executable, "-c", "print('smoke')"],
                cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
            )
            self.assertEqual(execute.returncode, 0, execute.stdout + execute.stderr)
            self.assertTrue(list((project / "receipts").glob("smoke-*.json")))


if __name__ == "__main__":
    unittest.main()
