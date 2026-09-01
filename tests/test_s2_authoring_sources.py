from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.test_competition_upgrades import base_contract


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness.py"


class AuthoringSourcesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="harness-s2-authoring-")
        self.project = Path(self.temp.name) / "project"
        self.init()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def init(self) -> None:
        result = self.run_cli(
            "init",
            "--project",
            str(self.project),
            "--competition",
            "cumcm",
            "--preset",
            "research",
            "--json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def write_model_source(self, value: dict[str, object]) -> Path:
        source = self.project / ".harness" / "authoring" / "model_contract.yaml"
        source.write_text(
            yaml.safe_dump({"model_contract": value}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        return source

    def test_init_keeps_machine_payload_out_of_author_documents(self) -> None:
        for relative in (
            "01_RESEARCH_NOTES.md",
            "02_MODEL_DECISION.md",
            "03_SOLUTION_REPORT.md",
            "paper/00_PAPER_PLAN.md",
        ):
            text = (self.project / relative).read_text(encoding="utf-8")
            self.assertNotIn("Machine contract source", text)
        for relative in (
            ".harness/authoring/research_basis.yaml",
            ".harness/authoring/model_contract.yaml",
            ".harness/authoring/implementation_map.yaml",
            ".harness/authoring/paper_plan.yaml",
        ):
            self.assertTrue((self.project / relative).is_file(), relative)
        self.assertFalse((self.project / ".harness" / "authoring" / "compile_index.json").exists())

    def test_yaml_compile_records_index_and_detects_source_and_output_drift(self) -> None:
        source = self.write_model_source(base_contract())
        compiled = self.run_cli("model", "--compile", "--project", str(self.project), "--json")
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        report = json.loads(compiled.stdout)
        self.assertEqual(report["source"], ".harness/authoring/model_contract.yaml")
        index_path = self.project / ".harness" / "authoring" / "compile_index.json"
        index = json.loads(index_path.read_text(encoding="utf-8"))
        self.assertEqual(index["schema_version"], "1.0")
        self.assertNotIn("timestamp", json.dumps(index))
        entry = next(row for row in index["entries"] if row["role"] == "model_contract")
        self.assertEqual(entry["source_path"], ".harness/authoring/model_contract.yaml")
        self.assertEqual(entry["output_path"], ".harness/contracts/model_contract.json")
        self.assertEqual(entry["compiler_version"], "authoring-1")

        current = self.run_cli("authoring", "check", "--project", str(self.project), "--json")
        self.assertEqual(current.returncode, 0, current.stdout + current.stderr)
        self.assertEqual(json.loads(current.stdout)["status"], "current")

        source.write_text(source.read_text(encoding="utf-8") + "\n# reviewed\n", encoding="utf-8")
        stale_source = self.run_cli("authoring", "check", "--project", str(self.project), "--json")
        self.assertEqual(stale_source.returncode, 1, stale_source.stdout + stale_source.stderr)
        stale_report = json.loads(stale_source.stdout)
        self.assertIn("source_changed", stale_report["entries"][0]["reasons"][0])

        source.write_text(yaml.safe_dump({"model_contract": base_contract()}, sort_keys=False), encoding="utf-8")
        output = self.project / ".harness" / "contracts" / "model_contract.json"
        output.write_text(output.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        stale_output = self.run_cli("authoring", "check", "--project", str(self.project), "--json")
        self.assertEqual(stale_output.returncode, 1, stale_output.stdout + stale_output.stderr)
        self.assertTrue(
            any(reason.startswith("output_changed:") for reason in json.loads(stale_output.stdout)["entries"][0]["reasons"])
        )

    def test_check_reports_uncompiled_source_and_direct_repair_command(self) -> None:
        source = self.write_model_source(base_contract())

        result = self.run_cli("authoring", "check", "--project", str(self.project), "--json")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "not_compiled")
        self.assertEqual(report["uncompiled_sources"], [".harness/authoring/model_contract.yaml"])
        self.assertEqual(
            report["repair_commands"],
            [{"path": source.relative_to(self.project).as_posix(), "role": "model_contract", "command": "harness model --compile"}],
        )

    def test_check_validates_changed_source_and_exposes_repair_command(self) -> None:
        source = self.write_model_source(base_contract())
        compiled = self.run_cli("model", "--compile", "--project", str(self.project), "--json")
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        source.write_text("model_contract:\n  schema_version: [\n", encoding="utf-8")

        result = self.run_cli("authoring", "check", "--project", str(self.project), "--json")

        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        entry = next(row for row in report["entries"] if row["role"] == "model_contract")
        self.assertTrue(any(reason.startswith("source_changed:") for reason in entry["reasons"]))
        self.assertTrue(any(reason.startswith("source_invalid:") for reason in entry["reasons"]))
        self.assertEqual(entry["repair_command"], "harness model --compile")

    def test_legacy_migration_preserves_semantics_and_is_idempotent(self) -> None:
        contract = base_contract()
        source = self.project / "02_MODEL_DECISION.md"
        source.write_text(
            "# 模型选型报告\n\n## Machine contract source (optional)\n\n```yaml\n"
            + yaml.safe_dump({"model_contract": contract}, allow_unicode=True, sort_keys=False)
            + "```\n",
            encoding="utf-8",
        )
        compiled = self.run_cli("model", "--compile", "--project", str(self.project), "--json")
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        output_before = json.loads(
            (self.project / ".harness" / "contracts" / "model_contract.json").read_text(encoding="utf-8")
        )

        migrated = self.run_cli("authoring", "migrate", "--project", str(self.project), "--json")
        self.assertEqual(migrated.returncode, 0, migrated.stdout + migrated.stderr)
        self.assertFalse("Machine contract source" in source.read_text(encoding="utf-8"))
        hidden = self.project / ".harness" / "authoring" / "model_contract.yaml"
        self.assertEqual(yaml.safe_load(hidden.read_text(encoding="utf-8"))["model_contract"], contract)
        self.assertEqual(
            json.loads((self.project / ".harness" / "contracts" / "model_contract.json").read_text(encoding="utf-8")),
            output_before,
        )
        index = json.loads((self.project / ".harness" / "authoring" / "compile_index.json").read_text(encoding="utf-8"))
        self.assertEqual(next(row for row in index["entries"] if row["role"] == "model_contract")["source_path"], ".harness/authoring/model_contract.yaml")

        hidden_before = hidden.read_bytes()
        second = self.run_cli("authoring", "migrate", "--project", str(self.project), "--json")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(json.loads(second.stdout)["status"], "unchanged")
        self.assertEqual(hidden.read_bytes(), hidden_before)

    def test_migration_refuses_divergent_existing_hidden_source(self) -> None:
        source = self.project / "02_MODEL_DECISION.md"
        source.write_text(
            "## Machine contract source\n\n```yaml\n"
            + yaml.safe_dump({"model_contract": base_contract()}, sort_keys=False)
            + "```\n",
            encoding="utf-8",
        )
        divergent = dict(base_contract())
        divergent["project_id"] = "different"
        self.write_model_source(divergent)
        result = self.run_cli("authoring", "migrate", "--project", str(self.project), "--json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("divergent", result.stdout)
        self.assertIn("Machine contract source", source.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
