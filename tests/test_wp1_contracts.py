from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from profiles.normalization import (  # noqa: E402
    UnsafeOverrideError,
    canonicalize_competition_profile,
    migrate_manifest,
    migrate_project,
    invalidate_downstream,
    validate_artifact_dag_ownership,
    normalize_manifest,
    resolve_profile,
)


def legacy_profile(page_limit: int = 25) -> dict:
    return {
        "profile_id": "legacy-cumcm",
        "competition_family": "cumcm",
        "competition_name": "Legacy CUMCM",
        "season": "2026",
        "language": "zh-CN",
        "base_template": "cumcm-2026-electronic",
        "rules": {"page_limit": page_limit, "anonymous_mode": True},
        "ai_disclosure": {"policy": "required_when_used", "format": "support_material_pdf", "manual_checks": {"when_used": ["ai_report"], "when_not_used": []}},
        "submission": {"required_files": [{"role": "paper", "format": "pdf"}], "support_zip": {"policy": "optional"}},
    }


def legacy_manifest(*, page_limit: int = 25, commands: list[dict] | None = None, artifacts: list[dict] | None = None) -> dict:
    return {
        "schema_version": "1.2",
        "project_id": "project-1",
        "run_id": "run-1",
        "status": "active",
        "phase": "results",
        "competition_profile": legacy_profile(page_limit),
        "safety": {},
        "ai_usage": [],
        "human_checkpoints": [],
        "model_contract": {"path": "model_contract.json"},
        "enhanced_integrity_profile": False,
        "integrity_mode": "research",
        "gates": {},
        "commands": commands or [],
        "artifacts": artifacts or [],
        "revision": {"loop": 0, "cap": 2, "open_issue_ids": []},
        "reviewer": {"profile": "sprint", "deterministic_qa": {"status": "pending"}, "semantic_critic": {"status": "pending"}, "blind_reviewers": []},
    }


class WP1ContractsTest(unittest.TestCase):
    def test_three_presets_and_non_bypassable_overrides(self) -> None:
        sprint = resolve_profile("sprint")
        research = resolve_profile("research")
        submission = resolve_profile("submission")
        self.assertFalse(sprint.require_final_pdf_hash)
        self.assertTrue(research.require_selected_io_hash)
        self.assertTrue(submission.require_final_pdf_hash)
        for key in ("require_contest_safety", "require_human_checkpoints", "require_independent_validation", "require_result_freeze", "require_submission_immutability"):
            self.assertTrue(sprint[key])
            with self.assertRaises(UnsafeOverrideError):
                resolve_profile("research", {key: False})

    def test_canonical_profile_is_standalone_v2_and_reports_missing_official_facts(self) -> None:
        profile, notes = canonicalize_competition_profile(legacy_profile())
        self.assertEqual(profile["schema_version"], "2.0")
        self.assertNotIn("rules", profile)
        self.assertNotIn("ai_disclosure", profile)
        self.assertEqual(profile["submission"]["max_pages"], 25)
        self.assertIsNone(profile["submission"]["max_paper_bytes"])
        self.assertEqual(profile["status"], "unresolved")
        self.assertTrue(any("max_paper_bytes" in item for item in notes["unresolved"]))
        self.assertTrue(any("not an official verified fact" in item for item in notes["inferred"]))
        self.assertTrue(notes["manual_review_required"])

    def test_manifest_normalization_has_no_duplicate_state(self) -> None:
        normalized = normalize_manifest(legacy_manifest())
        self.assertEqual(normalized["schema_version"], "2.0")
        for forbidden in ("competition_profile", "commands", "artifacts", "gates", "reviewer"):
            self.assertNotIn(forbidden, normalized)
        self.assertEqual(normalized["competition_profile_ref"]["path"], "competition_profile.json")
        self.assertNotIn("capabilities", normalized["metadata"])
        self.assertEqual(normalized["metadata"]["normalization_boundary"], "v1_adapter")
        self.assertEqual(normalized["control"]["selection_policy"]["owner"], "run_manifest.control")
        self.assertEqual(normalize_manifest(normalized), normalized)

    def test_migration_report_keeps_missing_submission_limit_unresolved(self) -> None:
        bundle = migrate_manifest(legacy_manifest())
        self.assertIsNone(bundle["competition_profile"]["submission"]["max_paper_bytes"])
        self.assertTrue(any("max_paper_bytes" in item for item in bundle["report"]["unresolved"]))
        self.assertTrue(any("maximum paper bytes" in item for item in bundle["report"]["manual_review_required"]))

    def test_manifest_requires_unique_profile_reference_and_rejects_v1_alias(self) -> None:
        v2 = {
            "schema_version": "2.0",
            "project_id": "p",
            "run_id": "r",
            "status": "active",
            "stage": "analysis",
            "preset": "sprint",
            "profile_overrides": {},
            "competition_profile_ref": {"path": "competition_profile.json", "profile_id": "p1"},
            "roots": {},
            "control": {"selection_policy": {"owner": "run_manifest.control", "rule": "first successful run"}},
            "safety": {},
            "ai_usage": [],
            "human_checkpoints": [],
        }
        self.assertEqual(normalize_manifest(v2)["competition_profile_ref"]["profile_id"], "p1")
        v2.pop("competition_profile_ref")
        v2["competition_profile"] = {"path": "competition_profile.json", "profile_id": "p1"}
        with self.assertRaises(ValueError):
            normalize_manifest(v2)

    def test_manifest_refs_and_metadata_cannot_own_digest_or_capabilities(self) -> None:
        manifest = {
            "schema_version": "2.0", "project_id": "p", "run_id": "r", "status": "active", "stage": "analysis",
            "preset": "sprint", "profile_overrides": {},
            "competition_profile_ref": {"path": "competition_profile.json", "profile_id": "p1", "sha256": "a" * 64},
            "roots": {}, "control": {"selection_policy": {"owner": "run_manifest.control", "rule": "first"}},
            "safety": {}, "ai_usage": [], "human_checkpoints": [],
        }
        with self.assertRaises(ValueError):
            normalize_manifest(manifest)
        manifest["competition_profile_ref"].pop("sha256")
        manifest["metadata"] = {"capabilities": {"require_result_freeze": True}}
        with self.assertRaises(ValueError):
            normalize_manifest(manifest)

    def test_migration_does_not_copy_model_contract_digest(self) -> None:
        manifest = legacy_manifest()
        manifest["model_contract"] = {"path": "model_contract.json", "artifact_id": "MODEL-1", "sha256": "a" * 64}
        normalized = normalize_manifest(manifest)
        self.assertEqual(normalized["roots"]["model_contract"], {"path": "model_contract.json", "artifact_id": "MODEL-1"})

    def test_profile_and_index_contracts_keep_digest_ownership_separate(self) -> None:
        profile_schema = json.loads((ROOT / "schemas" / "competition_profile.schema.json").read_text(encoding="utf-8"))
        manifest_schema = json.loads((ROOT / "schemas" / "run_manifest.schema.json").read_text(encoding="utf-8"))
        index_schema = json.loads((ROOT / "schemas" / "run_index.schema.json").read_text(encoding="utf-8"))
        self.assertNotIn("sha256", profile_schema["$defs"]["file_ref"]["properties"])
        self.assertNotIn("sha256", manifest_schema["$defs"]["file_ref"]["properties"])
        self.assertNotIn("sha256", manifest_schema["$defs"]["v2"]["properties"]["competition_profile_ref"]["properties"])
        self.assertIn("projected_from", index_schema["$defs"]["receipt_projection"]["required"])

    def test_legacy_profile_snapshot_digest_is_not_emitted_in_v2_profile(self) -> None:
        profile = legacy_profile()
        profile["official_rules"] = [{
            "rule_id": "RULE-1", "title": "legacy", "url": "https://example.invalid/rule",
            "retrieved_at": "legacy", "snapshot": {"path": "rule.html", "sha256": "a" * 64},
        }]
        bundle = migrate_manifest({**legacy_manifest(), "competition_profile": profile})
        snapshot = bundle["competition_profile"]["official_rules"][0]["snapshot"]
        self.assertNotIn("sha256", snapshot)
        self.assertTrue(any("digest ownership" in item for item in bundle["report"]["unresolved"]))

    def test_conflicting_page_limit_is_not_guessed(self) -> None:
        manifest = legacy_manifest(page_limit=20)
        manifest["submission"] = {"max_pages": 25}
        bundle = migrate_manifest(manifest)
        self.assertEqual(bundle["report"]["status"], "manual_review_required")
        self.assertTrue(any("page limits" in item for item in bundle["report"]["unresolved"]))
        self.assertTrue(bundle["report"]["manual_review_required"])

    def test_legacy_commands_without_receipt_remain_unresolved(self) -> None:
        manifest = legacy_manifest(commands=[{"command_id": "CMD-1", "stage": "full", "command": "python model.py", "exit_code": 0}])
        bundle = migrate_manifest(manifest)
        self.assertTrue(any("immutable command receipt" in item for item in bundle["report"]["unresolved"]))
        self.assertNotIn("commands", bundle["manifest"])

    def test_artifact_digest_conflict_and_multiple_selected_are_reported(self) -> None:
        manifest = legacy_manifest(artifacts=[
            {"role": "frozen_results", "path": "results.json", "sha256": "a" * 64},
            {"role": "other", "path": "results.json", "sha256": "b" * 64},
        ])
        index = {
            "schema_version": "1.0",
            "run_id_scope": "run-1",
            "selection_policy": "highest score",
            "runs": [
                {"command_id": "c1", "run_id": "run-1", "stage": "full", "argv": ["python", "a.py"], "exit_code": 0, "receipt_path": "r1.json", "selected": True, "recorded_at": "now"},
                {"command_id": "c2", "run_id": "run-1", "stage": "full", "argv": ["python", "b.py"], "exit_code": 0, "receipt_path": "r2.json", "selected": True, "recorded_at": "now"},
            ],
        }
        bundle = migrate_manifest(manifest, legacy_index=index)
        self.assertEqual(bundle["report"]["status"], "manual_review_required")
        self.assertTrue(any("conflicting digests" in item for item in bundle["report"]["unresolved"]))
        self.assertTrue(any("multiple selected" in item for item in bundle["report"]["unresolved"]))
        self.assertNotIn("argv", bundle["run_index"]["receipts"][0])

    def test_legacy_index_without_selected_receipt_requires_review(self) -> None:
        index = {
            "schema_version": "1.0",
            "run_id_scope": "run-1",
            "selection_policy": "first successful full run",
            "runs": [{"command_id": "c1", "run_id": "run-1", "stage": "full", "argv": ["python", "a.py"], "exit_code": 0, "receipt_path": "r1.json", "selected": False, "recorded_at": "now"}],
        }
        bundle = migrate_manifest(legacy_manifest(), legacy_index=index)
        self.assertTrue(any("no selected receipt" in item for item in bundle["report"]["unresolved"]))

    def test_legacy_dag_dependencies_are_projected_by_artifact_id(self) -> None:
        manifest = legacy_manifest(artifacts=[])
        dag = {
            "schema_version": "1.0",
            "run_id": "run-1",
            "nodes": [{
                "node_id": "N1",
                "kind": "model",
                "inputs": [{"path": "data.json", "sha256": "a" * 64}],
                "outputs": [{"path": "result.json", "sha256": "b" * 64}],
                "command": ["python", "model.py"],
                "receipt": {"path": "receipt.json", "sha256": "c" * 64},
                "upstream_digest": "d" * 64,
                "status": "current",
            }],
        }
        bundle = migrate_manifest(manifest, legacy_dag=dag)
        result_nodes = [node for node in bundle["artifact_dag"]["nodes"] if node["path"] == "result.json"]
        self.assertEqual(len(result_nodes), 1)
        self.assertEqual(len(result_nodes[0]["dependencies"]), 1)

    def test_selected_receipt_and_frozen_run_mismatch_requires_review(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wp1-selected-freeze-") as temp:
            root = Path(temp)
            frozen = root / "frozen.json"
            frozen.write_text(json.dumps({"schema_version": "1.0", "run_id": "run-frozen"}), encoding="utf-8")
            manifest = legacy_manifest(artifacts=[{"role": "frozen_results", "path": "frozen.json"}])
            index = {
                "schema_version": "1.0",
                "run_id_scope": "run-selected",
                "selection_policy": "first successful full run",
                "runs": [{"command_id": "c1", "run_id": "run-selected", "stage": "full", "argv": ["python", "a.py"], "exit_code": 0, "receipt_path": "r1.json", "selected": True, "recorded_at": "now"}],
            }
            bundle = migrate_manifest(manifest, project_root=root, legacy_index=index)
            self.assertTrue(any("does not match selected receipt" in item for item in bundle["report"]["unresolved"]))

    def test_immutable_artifact_update_creates_version_and_invalidates_dependents(self) -> None:
        dag = {
            "schema_version": "2.0",
            "run_id": "run-1",
            "nodes": [
                {"artifact_id": "RESULT-1", "role": "frozen_results", "path": "frozen.json", "producer_id": "freeze", "dependencies": [], "lifecycle": "frozen", "freshness": "current", "digest_owner": "artifact_dag", "version": "1", "sha256": "a" * 64, "digest_algorithm": "sha256"},
                {"artifact_id": "TABLE-1", "role": "table", "path": "table.csv", "producer_id": "export", "dependencies": [{"artifact_id": "RESULT-1", "relation": "source"}], "lifecycle": "immutable", "freshness": "current", "digest_owner": "artifact_dag", "version": "1", "sha256": "b" * 64, "digest_algorithm": "sha256"},
            ],
        }
        updated, event = invalidate_downstream(dag, "RESULT-1", new_sha256="c" * 64)
        self.assertEqual(event["changed_artifact_id"], "RESULT-1-v2")
        self.assertTrue(event["immutable_history_preserved"])
        self.assertEqual(len(updated["nodes"]), 3)
        self.assertEqual(updated["nodes"][1]["freshness"], "stale")

    def test_mutable_artifact_update_does_not_claim_immutable_history_preserved(self) -> None:
        dag = {
            "schema_version": "2.0", "nodes": [
                {"artifact_id": "CACHE-1", "role": "cache", "path": "cache.json", "producer_id": "run", "dependencies": [], "lifecycle": "mutable", "freshness": "current", "digest_owner": "artifact_dag", "version": "1"},
                {"artifact_id": "TABLE-1", "role": "table", "path": "table.csv", "producer_id": "export", "dependencies": [{"artifact_id": "CACHE-1", "relation": "source"}], "lifecycle": "mutable", "freshness": "current", "digest_owner": "artifact_dag", "version": "1"},
            ],
        }
        _, event = invalidate_downstream(dag, "CACHE-1", new_path="cache-v2.json")
        self.assertFalse(event["immutable_history_preserved"])

    def test_duplicate_digest_owners_are_rejected_by_contract_helper(self) -> None:
        dag = {
            "schema_version": "2.0",
            "nodes": [
                {"artifact_id": "A", "path": "x", "digest_owner": "artifact_dag", "sha256": "a" * 64},
                {"artifact_id": "B", "path": "x", "digest_owner": "submission_manifest", "sha256": "b" * 64},
            ],
        }
        errors = validate_artifact_dag_ownership(dag)
        self.assertTrue(any("multiple digest owners" in error for error in errors))

    def test_project_migration_writes_separate_outputs_and_preserves_frozen_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wp1-migration-") as temp:
            root = Path(temp)
            frozen = root / "frozen_results.json"
            frozen.write_text("historical-bytes\n", encoding="utf-8")
            (root / "run_manifest.json").write_text(json.dumps(legacy_manifest(artifacts=[{"role": "frozen_results", "path": "frozen_results.json"}]), ensure_ascii=False), encoding="utf-8")
            bundle = migrate_project(root)
            self.assertEqual(frozen.read_text(encoding="utf-8"), "historical-bytes\n")
            self.assertIn("run_manifest.json", bundle["output_paths"])
            self.assertTrue((root / "migration_v2" / "competition_profile.json").is_file())
            migrated = json.loads((root / "migration_v2" / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(migrated["schema_version"], "2.0")

    def test_all_schema_files_are_json(self) -> None:
        paths = sorted((ROOT / "schemas").glob("*.schema.json"))
        # 29 contract schemas + review_report.schema.json (Review Execution Plane).
        self.assertEqual(len(paths), 30)
        for path in paths:
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8"))

    def test_profile_cli_default_writer_emits_v2(self) -> None:
        with tempfile.TemporaryDirectory(prefix="wp1-profile-cli-") as temp:
            seed = Path(temp) / "seed.json"
            seed.write_text(json.dumps(legacy_profile(), ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "profiles" / "profile_engine.py"), "--profile", str(seed)],
                cwd=str(ROOT), capture_output=True, check=False,
            )
            stderr = (result.stderr or b"").decode("utf-8", errors="replace")
            self.assertEqual(result.returncode, 0, stderr)
            output = (result.stdout or b"").decode("utf-8")
            self.assertEqual(json.loads(output)["schema_version"], "2.0")


if __name__ == "__main__":
    unittest.main()
