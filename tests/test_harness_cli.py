from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness.py"
DIRECT_GATE = ROOT / "scripts" / "qa" / "check_gates.py"


class HarnessCliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="harness-cli-")
        self.project = Path(self.temp.name) / "project"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLI), *args],
            cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )

    def init(self, competition: str = "cumcm") -> None:
        result = self.run_cli("init", "--project", str(self.project), "--competition", competition, "--preset", "research", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def read(self, name: str) -> dict:
        return json.loads((self.project / name).read_text(encoding="utf-8"))

    def test_init_emits_only_minimal_v2_state(self) -> None:
        self.init()
        names = sorted(path.name for path in self.project.glob("*.json"))
        self.assertEqual(names, ["artifact_dag.json", "competition_profile.json", "run_index.json", "run_manifest.json"])
        manifest = self.read("run_manifest.json")
        profile = self.read("competition_profile.json")
        self.assertEqual(manifest["schema_version"], "2.0")
        self.assertEqual(profile["schema_version"], "2.0")
        self.assertEqual(profile["status"], "seed")
        self.assertEqual(manifest["ai_usage_state"], "unknown")
        self.assertNotIn("commands", manifest)
        self.assertNotIn("gates", manifest)

    def test_init_status_and_check_have_factual_first_blocker_and_json(self) -> None:
        self.init()
        status = self.run_cli("status", "--project", str(self.project), "--json")
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        report = json.loads(status.stdout)
        self.assertEqual(report["schema_version"], "2.0")
        self.assertEqual(report["first_blocked_gate"], "m1")
        self.assertTrue(report["pending_human_checkpoints"])
        self.assertIn("M1", report["next_action"])
        check = self.run_cli("check", "M1", "--project", str(self.project), "--json")
        self.assertEqual(check.returncode, 1)
        check_report = json.loads(check.stdout)
        self.assertFalse(check_report["ok"])
        self.assertTrue(check_report["errors"])

    def test_status_does_not_trust_manifest_gate_or_hide_stale_dag(self) -> None:
        self.init()
        stale = self.project / "stale.txt"
        stale.write_text("v1", encoding="utf-8")
        digest = hashlib.sha256(stale.read_bytes()).hexdigest()
        dag = self.read("artifact_dag.json")
        dag["nodes"].append({
            "artifact_id": "TABLE-1", "role": "table", "path": "stale.txt", "producer_id": "test",
            "dependencies": [], "lifecycle": "immutable", "freshness": "current", "version": "1",
            "created_at": "2026-01-01T00:00:00Z", "digest_owner": "artifact_dag",
            "sha256": digest, "digest_algorithm": "sha256",
        })
        (self.project / "artifact_dag.json").write_text(json.dumps(dag), encoding="utf-8")
        stale.write_text("v2", encoding="utf-8")
        status = self.run_cli("status", "--project", str(self.project), "--json")
        report = json.loads(status.stdout)
        self.assertEqual(report["first_blocked_gate"], "m1")
        self.assertTrue(any(row.get("artifact_id") == "TABLE-1" for row in report["stale_artifacts"]))
        self.assertNotIn("expected_sha256", json.dumps(report))
        self.assertNotIn("actual_sha256", json.dumps(report))

    def test_fake_v2_gate_state_is_rejected_instead_of_trusted(self) -> None:
        self.init()
        manifest = self.read("run_manifest.json")
        manifest["gates"] = {name: {"status": "pass"} for name in ("m1", "p1", "p2", "w1", "w2", "s1")}
        (self.project / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
        status = self.run_cli("status", "--project", str(self.project), "--json")
        report = json.loads(status.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["first_blocked_gate"], "m1")
        self.assertIn("forbidden", report["errors"][0])

    def test_cli_and_direct_checker_preserve_failure_code_and_reason(self) -> None:
        self.init()
        cli = self.run_cli("check", "M1", "--project", str(self.project))
        direct = subprocess.run(
            [sys.executable, str(DIRECT_GATE), "--manifest", "run_manifest.json", "--project-root", str(self.project), "--gate", "m1"],
            cwd=str(self.project), text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        self.assertEqual(cli.returncode, direct.returncode)
        self.assertIn("model_contract", cli.stdout)
        self.assertIn("model_contract", direct.stdout)

    def test_check_profile_alias_asserts_but_cannot_override_manifest_preset(self) -> None:
        self.init()
        matching = self.run_cli("check", "M1", "--project", str(self.project), "--profile", "research")
        direct = self.run_cli("check", "M1", "--project", str(self.project))
        self.assertEqual(matching.returncode, direct.returncode)

        conflict = self.run_cli("check", "M1", "--project", str(self.project), "--profile", "submission")
        self.assertNotEqual(conflict.returncode, 0)
        self.assertIn("conflicts with the manifest-owned preset", conflict.stdout)

    def test_run_error_is_not_swallowed_and_migration_dispatches(self) -> None:
        self.init()
        run = self.run_cli("run", "--project", str(self.project), "--stage", "smoke", "--", sys.executable, "-c", "import sys; sys.exit(7)")
        self.assertEqual(run.returncode, 7)
        self.assertIn('"ok": false', run.stdout)
        legacy = Path(self.temp.name) / "legacy"
        legacy.mkdir()
        legacy_profile = {
            "profile_id": "legacy", "competition_family": "cumcm", "competition_name": "legacy",
            "season": "2026", "language": "zh-CN", "base_template": "template",
            "rules": {"page_limit": 25}, "ai_disclosure": {}, "submission": {},
        }
        legacy_manifest = {
            "schema_version": "1.2", "project_id": "legacy", "run_id": "run-1", "status": "active", "phase": "analysis",
            "competition_profile": legacy_profile, "safety": {}, "ai_usage": [], "human_checkpoints": [],
            "model_contract": {"path": "model.json"}, "enhanced_integrity_profile": False, "integrity_mode": "research",
            "gates": {}, "commands": [], "artifacts": [], "revision": {"loop": 0, "cap": 2, "open_issue_ids": []},
            "reviewer": {"profile": "sprint", "deterministic_qa": {}, "semantic_critic": {}, "blind_reviewers": []},
        }
        (legacy / "run_manifest.json").write_text(json.dumps(legacy_manifest), encoding="utf-8")
        migration = self.run_cli("migrate", "--project", str(legacy), "--no-write", "--json")
        self.assertIn("manual_review_required", migration.stdout)
        self.assertNotEqual(migration.returncode, 0)

    def test_ai_usage_tri_state_requires_explicit_human_declaration(self) -> None:
        self.init()
        status = self.run_cli("ai", "status", "--project", str(self.project), "--json")
        self.assertEqual(json.loads(status.stdout)["ai_usage_state"], "unknown")

        confirmed = self.run_cli(
            "ai", "confirm-none", "--project", str(self.project),
            "--confirmed-by", "team-lead", "--reason", "Reviewed team tool log",
            "--confirmed-at", "2026-08-21T00:00:00Z", "--json",
        )
        self.assertEqual(confirmed.returncode, 0, confirmed.stdout + confirmed.stderr)
        manifest = self.read("run_manifest.json")
        self.assertEqual(manifest["ai_usage_state"], "none")
        self.assertEqual(manifest["ai_usage_declaration"]["confirmed_by"], "team-lead")
        self.assertIn("Declaration state: `none`", (self.project / "AI_USAGE_LEDGER.md").read_text(encoding="utf-8"))

        interaction = self.project / "ai_interaction.md"
        interaction.write_text("prompt and response summary\n", encoding="utf-8")
        recorded = self.run_cli(
            "ai", "record", "--project", str(self.project), "--usage-id", "AI-TEST-1",
            "--tool-name", "Codex", "--model", "fixture-model", "--provider", "OpenAI",
            "--stage", "coding", "--purpose", "review implementation",
            "--prompt-summary", "inspect deterministic renderer", "--output-use", "adopted bounded patch",
            "--human-changes", "reviewed and edited", "--interaction-record", interaction.name,
            "--checked-by-role", "team-lead", "--verification-method", "manual diff and tests",
            "--used-at", "2026-08-21T01:00:00Z", "--checked-at", "2026-08-21T02:00:00Z", "--json",
        )
        self.assertEqual(recorded.returncode, 0, recorded.stdout + recorded.stderr)
        manifest = self.read("run_manifest.json")
        self.assertEqual(manifest["ai_usage_state"], "used")
        self.assertNotIn("ai_usage_declaration", manifest)
        self.assertEqual(manifest["ai_usage"][0]["interaction_record"]["sha256"], hashlib.sha256(interaction.read_bytes()).hexdigest())
        self.assertIn("AI-TEST-1", (self.project / "AI_USAGE_LEDGER.md").read_text(encoding="utf-8"))

    def test_ai_record_is_serialized_and_rejects_external_evidence(self) -> None:
        self.init()
        outside = Path(self.temp.name) / "outside.md"
        outside.write_text("not portable\n", encoding="utf-8")
        rejected = self.run_cli(
            "ai", "record", "--project", str(self.project), "--usage-id", "AI-OUTSIDE",
            "--tool-name", "Codex", "--model", "fixture", "--provider", "OpenAI",
            "--stage", "coding", "--purpose", "fixture", "--prompt-summary", "fixture",
            "--output-use", "fixture", "--human-changes", "reviewed",
            "--interaction-record", str(outside), "--checked-by-role", "team",
            "--verification-method", "manual review", "--json",
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("inside the project root", rejected.stdout)

        processes: list[subprocess.Popen[str]] = []
        for index in range(2):
            interaction = self.project / f"interaction-{index}.md"
            interaction.write_text(f"interaction {index}\n", encoding="utf-8")
            command = [
                sys.executable, str(CLI), "ai", "record", "--project", str(self.project),
                "--usage-id", f"AI-CONCURRENT-{index}", "--tool-name", "Codex",
                "--model", "fixture", "--provider", "OpenAI", "--stage", "coding",
                "--purpose", "fixture", "--prompt-summary", "fixture",
                "--output-use", "fixture", "--human-changes", "reviewed",
                "--interaction-record", interaction.name, "--checked-by-role", "team",
                "--verification-method", "manual review", "--json",
            ]
            processes.append(subprocess.Popen(
                command, cwd=str(ROOT), text=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, encoding="utf-8", errors="replace",
            ))
        completed = [process.communicate(timeout=30) + (process.returncode,) for process in processes]
        self.assertTrue(all(row[2] == 0 for row in completed), completed)
        manifest = self.read("run_manifest.json")
        self.assertEqual(
            {row["usage_id"] for row in manifest["ai_usage"]},
            {"AI-CONCURRENT-0", "AI-CONCURRENT-1"},
        )

    def test_prepare_projections_are_safe_idempotent_and_do_not_promote(self) -> None:
        self.init()
        first = self.run_cli("prepare", "M1", "--project", str(self.project), "--json")
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        plan = (self.project / "MODELING_PLAN.md").read_text(encoding="utf-8")
        self.assertIn("Generated projection", plan)
        self.assertIn("model_contract` is missing", plan)
        first_bytes = (self.project / "PROJECT_BRIEF.md").read_bytes()
        second = self.run_cli("prepare", "M1", "--project", str(self.project), "--json")
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)
        self.assertEqual(first_bytes, (self.project / "PROJECT_BRIEF.md").read_bytes())

        s1 = self.run_cli("prepare", "S1", "--project", str(self.project), "--json")
        self.assertEqual(s1.returncode, 0, s1.stdout + s1.stderr)
        report = json.loads(s1.stdout)
        self.assertFalse(report["submission_ready"])
        self.assertTrue((self.project / "submission" / "staging" / "ai_disclosure" / "AI工具使用详情.md").is_file())
        self.assertTrue((self.project / "submission" / "final").is_dir())
        self.assertFalse(any((self.project / "submission" / "final").iterdir()))
        checklist = (self.project / "SUBMISSION_CHECKLIST.md").read_text(encoding="utf-8")
        self.assertIn("AI usage is explicitly and consistently declared (current: `unknown`)", checklist)
        self.assertIn("does not assert submission readiness", checklist)


if __name__ == "__main__":
    unittest.main()
