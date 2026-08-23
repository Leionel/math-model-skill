from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests.test_competition_upgrades import base_contract


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness.py"
STATUS = ROOT / "scripts" / "harness_status.py"
CONTROL_FILES = (
    "competition_profile.json",
    "run_manifest.json",
    "artifact_dag.json",
    "run_index.json",
)


class StateLayoutMigrationCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="harness-state-layout-")
        self.project = Path(self.temp.name) / "project"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

    def init(self) -> None:
        result = self.run_cli("init", "--project", str(self.project), "--competition", "cumcm", "--preset", "research", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def apply_hidden_layout(self) -> dict[str, object]:
        result = self.run_cli("migrate", "--project", str(self.project), "--layout", "hidden", "--apply", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_hidden_migration_dry_run_does_not_change_flat_state(self) -> None:
        self.init()
        result = self.run_cli("migrate", "--project", str(self.project), "--layout", "hidden", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["apply_required"])
        self.assertEqual([row["name"] for row in report["control_documents"]], list(CONTROL_FILES))
        self.assertTrue(all((self.project / name).is_file() for name in CONTROL_FILES))
        self.assertFalse((self.project / ".harness" / "state").exists())

    def test_hidden_migration_keeps_normal_cli_paths_operational(self) -> None:
        self.init()
        profile_bytes = (self.project / "competition_profile.json").read_bytes()
        notes = self.project / "01_RESEARCH_NOTES.md"
        notes.write_text("# Preserved author notes\n\nactual finding\n", encoding="utf-8")
        report = self.apply_hidden_layout()
        self.assertEqual(report["status"], "migrated")
        self.assertFalse(report["apply_required"])
        self.assertEqual(report["report_path"], ".harness/reports/state_layout_migration.json")
        self.assertTrue((self.project / report["report_path"]).is_file())
        self.assertFalse(any((self.project / name).exists() for name in CONTROL_FILES))
        hidden = self.project / ".harness" / "state"
        self.assertTrue(all((hidden / name).is_file() for name in CONTROL_FILES))
        self.assertEqual((hidden / "competition_profile.json").read_bytes(), profile_bytes)
        self.assertEqual(notes.read_text(encoding="utf-8"), "# Preserved author notes\n\nactual finding\n")

        status = self.run_cli("status", "--project", str(self.project), "--json")
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        status_report = json.loads(status.stdout)
        self.assertEqual(status_report["profile"]["path"], ".harness/state/competition_profile.json")
        self.assertEqual(status_report["receipts"]["index"], ".harness/state/run_index.json")

        prepared = self.run_cli("prepare", "M1", "--project", str(self.project), "--json")
        self.assertEqual(prepared.returncode, 0, prepared.stdout + prepared.stderr)
        self.assertTrue((self.project / ".harness" / "views" / "M1_STATE.md").is_file())

        contract = yaml.safe_dump({"model_contract": base_contract()}, allow_unicode=True, sort_keys=False)
        (self.project / "02_MODEL_DECISION.md").write_text(
            "# 模型选型报告\n\n## Machine contract source (optional)\n\n```yaml\n" + contract + "```\n",
            encoding="utf-8",
        )
        compiled = self.run_cli("model", "--compile", "--project", str(self.project), "--json")
        self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
        compiled_report = json.loads(compiled.stdout)
        self.assertEqual(compiled_report["manifest"], ".harness/state/run_manifest.json")
        manifest = json.loads((hidden / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["roots"]["model_contract"]["path"], ".harness/contracts/model_contract.json")

        run = self.run_cli("run", "--project", str(self.project), "--stage", "smoke", "--json", "--", sys.executable, "-c", "pass")
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        index = json.loads((hidden / "run_index.json").read_text(encoding="utf-8"))
        self.assertEqual(len(index["receipts"]), 1)
        self.assertEqual(index["selection"]["policy_ref"]["path"], ".harness/state/run_manifest.json#/control/selection_policy")

        direct = subprocess.run(
            [sys.executable, str(STATUS), "--project-root", str(self.project), "--json"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(direct.returncode, 0, direct.stdout + direct.stderr)

    def test_hidden_layout_refuses_reintroduced_flat_control_file(self) -> None:
        self.init()
        self.apply_hidden_layout()
        hidden_manifest = self.project / ".harness" / "state" / "run_manifest.json"
        (self.project / "run_manifest.json").write_bytes(hidden_manifest.read_bytes())
        result = self.run_cli("status", "--project", str(self.project), "--json")
        self.assertEqual(result.returncode, 2)
        self.assertIn("conflicts with root-level control files", result.stdout)

    def test_delegated_child_output_is_utf8_even_when_parent_requests_gbk(self) -> None:
        self.init()
        result = self.run_cli(
            "prepare",
            "M1",
            "--project",
            str(self.project),
            "--json",
            env={**os.environ, "PYTHONIOENCODING": "gbk"},
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Generated projection — factual state remains", result.stdout)


if __name__ == "__main__":
    unittest.main()
