from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness.py"
sys.path.insert(0, str(ROOT / "scripts"))

import runtime  # noqa: E402

VOLATILE_KEYS = {"generated_at", "recorded_at"}


def stable(value: Any) -> Any:
    """Drop timestamp fields so a CLI payload and an API payload compare equal."""

    if isinstance(value, dict):
        return {key: stable(item) for key, item in value.items() if key not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [stable(item) for item in value]
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RuntimeReadApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="runtime-api-")
        self.project = Path(self.temp.name)
        initialized = self.run_cli(
            "init", "--project", str(self.project), "--competition", "cumcm", "--preset", "research", "--json",
        )
        self.assertEqual(initialized.returncode, 0, initialized.stdout + initialized.stderr)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def test_get_state_equals_status_cli_json(self) -> None:
        cli = self.run_cli("status", "--project", str(self.project), "--json")
        view = runtime.get_state(self.project)
        self.assertEqual(view.exit_code, cli.returncode)
        self.assertEqual(stable(view.payload), stable(json.loads(cli.stdout)))

    def test_get_state_equals_status_cli_when_manifest_is_missing(self) -> None:
        empty = self.project / "empty"
        empty.mkdir()
        cli = self.run_cli("status", "--project", str(empty), "--json")
        view = runtime.get_state(empty)
        self.assertEqual(cli.returncode, 2)
        self.assertEqual(view.exit_code, 2)
        self.assertEqual(stable(view.payload), stable(json.loads(cli.stdout)))

    def test_check_gate_equals_check_cli_json(self) -> None:
        cli = self.run_cli("check", "M1", "--project", str(self.project))
        view = runtime.check_gate(self.project, "m1")
        self.assertEqual(view.exit_code, cli.returncode)
        self.assertEqual(view.payload["gate"], "m1")
        self.assertEqual(stable(view.payload), stable(json.loads(cli.stdout)))

    def test_check_gate_strict_equals_check_cli_strict(self) -> None:
        cli = self.run_cli("check", "M1", "--project", str(self.project), "--strict")
        view = runtime.check_gate(self.project, "M1", strict=True)
        self.assertEqual(view.exit_code, cli.returncode)
        self.assertEqual(stable(view.payload), stable(json.loads(cli.stdout)))

    def test_check_gate_rejects_unknown_gate(self) -> None:
        with self.assertRaises(ValueError):
            runtime.check_gate(self.project, "zz")

    def test_verify_artifact_matches_status_dag_view(self) -> None:
        notes = self.project / "notes.txt"
        notes.write_text("fixture notes", encoding="utf-8")
        dag_path = self.project / "artifact_dag.json"
        dag = json.loads(dag_path.read_text(encoding="utf-8"))
        dag["nodes"].append({
            "artifact_id": "NOTES-1",
            "role": "frozen_results",
            "path": "notes.txt",
            "producer_id": "fixture",
            "dependencies": [],
            "lifecycle": "frozen",
            "freshness": "current",
            "critical": False,
            "version": "1",
            "created_at": "2026-09-18T00:00:00+00:00",
            "digest_owner": "artifact_dag",
            "sha256": "0" * 64,
        })
        dag_path.write_text(json.dumps(dag), encoding="utf-8")

        report = json.loads(self.run_cli("status", "--project", str(self.project), "--json").stdout)
        by_id = {row["artifact_id"]: row for row in report["dag"]["artifacts"]}

        current = runtime.verify_artifact(self.project, "PROFILE-CUMCM-2026-ELECTRONIC")
        self.assertEqual(current.exit_code, 0)
        self.assertTrue(current.payload["ok"])
        self.assertEqual(current.payload["freshness"], "current")
        for field in ("role", "path", "lifecycle", "freshness"):
            self.assertEqual(current.payload[field], by_id["PROFILE-CUMCM-2026-ELECTRONIC"][field])

        drifted = runtime.verify_artifact(self.project, "NOTES-1")
        self.assertEqual(drifted.exit_code, 1)
        self.assertFalse(drifted.payload["ok"])
        self.assertEqual(drifted.payload["freshness"], "stale")
        self.assertEqual(drifted.payload["freshness"], by_id["NOTES-1"]["freshness"])
        self.assertTrue(drifted.payload["stale_reasons"])
        self.assertIn("NOTES-1", [row["artifact_id"] for row in report["stale_artifacts"]])

    def test_unknown_artifact_is_a_negative_verdict(self) -> None:
        view = runtime.verify_artifact(self.project, "NOT-REGISTERED")
        self.assertEqual(view.exit_code, 1)
        self.assertFalse(view.payload["ok"])
        self.assertIn("not registered", view.payload["errors"][0])

    def test_reads_do_not_write_project_state(self) -> None:
        before = self.snapshot()
        runtime.get_state(self.project)
        runtime.check_gate(self.project, "m1")
        runtime.verify_artifact(self.project, "PROFILE-CUMCM-2026-ELECTRONIC")
        self.assertEqual(before, self.snapshot())

    def snapshot(self) -> dict[str, str]:
        return {
            str(path.relative_to(self.project)): sha256(path)
            for path in sorted(self.project.rglob("*"))
            if path.is_file()
        }


if __name__ == "__main__":
    unittest.main()