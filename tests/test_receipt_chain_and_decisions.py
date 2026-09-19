from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa.validate_contracts import _validate_document  # noqa: E402

RUN_AND_RECORD = ROOT / "scripts" / "run_and_record.py"
HARNESS = ROOT / "scripts" / "harness.py"
RECEIPT_SCHEMA = ROOT / "schemas" / "command_receipt.schema.json"
DECISION_SCHEMA = ROOT / "schemas" / "human_decision.schema.json"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


class ReceiptChainTest(unittest.TestCase):
    def _record(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUN_AND_RECORD), *args],
            cwd=str(cwd), text=True, capture_output=True, encoding="utf-8", check=False,
        )

    def _record_pair(self, project: Path) -> tuple[Path, Path]:
        (project / "reports").mkdir(parents=True, exist_ok=True)
        for name, script in (("r1.json", "print('a')"), ("r2.json", "print('b')")):
            result = self._record(
                "--v2", "--run-id", "run-001", "--stage", "full",
                "--receipt", f"reports/{name}", "--index", "reports/run_index.json",
                "--", sys.executable, "-c", script,
                cwd=project,
            )
            self.assertEqual(result.returncode, 0, result.stderr[-800:])
        return project / "reports" / "r1.json", project / "reports" / "r2.json"

    def test_consecutive_receipts_are_chained_and_schema_valid(self) -> None:
        with tempfile.TemporaryDirectory(prefix="receipt-chain-") as temp:
            first, second = self._record_pair(Path(temp))
            document_first = json.loads(first.read_text(encoding="utf-8"))
            document_second = json.loads(second.read_text(encoding="utf-8"))
            self.assertNotIn("previous_receipt_hash", document_first)
            self.assertEqual(
                document_second["previous_receipt_hash"], sha256_file(first)
            )
            for document in (document_first, document_second):
                self.assertEqual(
                    set(document["execution_host_identity"]), {"hostname", "platform"}
                )
                self.assertTrue(document["execution_host_identity"]["hostname"])
                self.assertTrue(document["execution_host_identity"]["platform"])
            for path in (first, second):
                _, errors, _ = _validate_document(path, RECEIPT_SCHEMA)
                self.assertEqual(errors, [])

    def test_verify_chain_accepts_intact_history(self) -> None:
        with tempfile.TemporaryDirectory(prefix="receipt-chain-ok-") as temp:
            self._record_pair(Path(temp))
            result = self._record("--verify-chain", "--index", "reports/run_index.json", cwd=Path(temp))
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout)["errors"], [])

    def test_verify_chain_detects_modified_history(self) -> None:
        with tempfile.TemporaryDirectory(prefix="receipt-chain-edit-") as temp:
            first, _ = self._record_pair(Path(temp))
            document = json.loads(first.read_text(encoding="utf-8"))
            document["argv"] = [sys.executable, "forged.py"]
            first.write_text(json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            result = self._record("--verify-chain", "--index", "reports/run_index.json", cwd=Path(temp))
            self.assertEqual(result.returncode, 1)
            errors = json.loads(result.stdout)["errors"]
            self.assertTrue(any("previous_receipt_hash does not match" in error for error in errors), errors)

    def test_verify_chain_detects_deleted_history(self) -> None:
        with tempfile.TemporaryDirectory(prefix="receipt-chain-del-") as temp:
            first, _ = self._record_pair(Path(temp))
            first.unlink()
            result = self._record("--verify-chain", "--index", "reports/run_index.json", cwd=Path(temp))
            self.assertEqual(result.returncode, 1)
            errors = json.loads(result.stdout)["errors"]
            self.assertTrue(any("receipt file is missing" in error for error in errors), errors)

    def test_verify_chain_requires_index(self) -> None:
        with tempfile.TemporaryDirectory(prefix="receipt-chain-arg-") as temp:
            result = self._record("--verify-chain", cwd=Path(temp))
            self.assertEqual(result.returncode, 2)
            self.assertIn("--verify-chain requires --index", result.stdout)

    def test_verify_chain_reports_corrupt_history_as_an_error_not_a_traceback(self) -> None:
        for break_which in ("index", "receipt"):
            with self.subTest(broken=break_which), tempfile.TemporaryDirectory(prefix="receipt-chain-corrupt-") as temp:
                project = Path(temp)
                self._record_pair(project)
                target = project / "reports/run_index.json" if break_which == "index" else project / "reports/r1.json"
                target.write_text("{ not json\n", encoding="utf-8")
                result = self._record("--verify-chain", "--index", "reports/run_index.json", cwd=project)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertIn('"ok": false', result.stdout)
                self.assertNotIn("Traceback", result.stdout + result.stderr)


class HumanCheckpointApproveTest(unittest.TestCase):
    def _approve(self, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HARNESS), "checkpoint", "approve", *args],
            cwd=str(cwd), text=True, capture_output=True, encoding="utf-8", check=False,
        )

    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory(prefix="checkpoint-approve-")
        self.project = Path(self._temp.name)
        (self.project / "run_manifest.json").write_text(
            json.dumps({"schema_version": "2.0", "human_checkpoints": []}, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self._temp.cleanup()

    def test_approve_appends_manifest_row_and_chains_decision_artifacts(self) -> None:
        first = self._approve("w1", "--role", "team lead", "--decision", "approve", "--json", cwd=self.project)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        payload = json.loads(first.stdout)
        self.assertEqual(payload["decision"], "approve")

        second = self._approve("w1", "--role", "team lead", "--decision", "reject", cwd=self.project)
        self.assertEqual(second.returncode, 0, second.stdout + second.stderr)

        artifacts = sorted((self.project / ".harness" / "human_decisions").glob("*.json"))
        self.assertEqual(len(artifacts), 2)
        document_first = json.loads(artifacts[0].read_text(encoding="utf-8"))
        document_second = json.loads(artifacts[1].read_text(encoding="utf-8"))
        self.assertEqual(document_first["checkpoint"], "w1")
        self.assertEqual(document_first["decision"], "approve")
        self.assertEqual(document_first["role"], "team lead")
        self.assertNotIn("previous_decision_sha256", document_first)
        self.assertEqual(
            document_second["previous_decision_sha256"], sha256_file(artifacts[0])
        )
        for artifact in artifacts:
            _, errors, _ = _validate_document(artifact, DECISION_SCHEMA)
            self.assertEqual(errors, [])

        manifest = json.loads((self.project / "run_manifest.json").read_text(encoding="utf-8"))
        rows = manifest["human_checkpoints"]
        self.assertEqual([row["decision"] for row in rows], ["pass", "reject"])
        self.assertEqual([row["stage"] for row in rows], ["w1", "w1"])
        for row, artifact in zip(rows, artifacts):
            self.assertEqual(row["decision_artifact"], artifact.relative_to(self.project).as_posix())
            self.assertEqual(row["decision_sha256"], sha256_file(artifact))
            self.assertTrue(row["decided_at"])

    def test_approve_is_append_only_across_stages(self) -> None:
        self._approve("m1", "--role", "modeler", "--decision", "approve", cwd=self.project)
        self._approve("p2", "--role", "modeler", "--decision", "approve", cwd=self.project)
        manifest = json.loads((self.project / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [(row["stage"], row["decision"]) for row in manifest["human_checkpoints"]],
            [("m1", "pass"), ("p2", "pass")],
        )
        self.assertEqual(len(list((self.project / ".harness" / "human_decisions").glob("*.json"))), 2)

    def test_approve_records_who_made_the_call(self) -> None:
        agent = self._approve("w1", "--role", "orchestrator", "--decision", "approve", "--actor", "agent", cwd=self.project)
        self.assertEqual(agent.returncode, 0, agent.stdout + agent.stderr)
        self.assertIn("actor=agent", agent.stdout)
        self.assertIn("does not clear the Gate", agent.stdout)

        human = self._approve("w1", "--role", "team lead", "--decision", "approve", "--json", cwd=self.project)
        self.assertEqual(human.returncode, 0, human.stdout + human.stderr)
        self.assertEqual(json.loads(human.stdout)["actor_class"], "human")

        artifacts = sorted((self.project / ".harness" / "human_decisions").glob("*.json"))
        self.assertEqual(
            [json.loads(path.read_text(encoding="utf-8"))["actor_class"] for path in artifacts],
            ["agent", "human"],
        )
        manifest = json.loads((self.project / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(
            [(row["decided_by"], row["actor_class"]) for row in manifest["human_checkpoints"]],
            [("orchestrator", "agent"), ("team lead", "human")],
        )
        for artifact in artifacts:
            _, errors, _ = _validate_document(artifact, DECISION_SCHEMA)
            self.assertEqual(errors, [])

    def test_approve_rejects_an_unknown_actor_class(self) -> None:
        result = self._approve("w1", "--role", "r", "--decision", "approve", "--actor", "manager", cwd=self.project)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stdout + result.stderr)
        manifest = json.loads((self.project / "run_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["human_checkpoints"], [])
        self.assertFalse((self.project / ".harness" / "human_decisions").exists())

    def test_approve_rejects_invalid_stage_and_non_v2_manifest(self) -> None:
        bad_stage = self._approve("W1", "--role", "r", "--decision", "approve", cwd=self.project)
        self.assertEqual(bad_stage.returncode, 2)

        legacy = Path(self._temp.name) / "legacy"
        legacy.mkdir()
        (legacy / "run_manifest.json").write_text(
            json.dumps({"schema_version": "1.0", "human_checkpoints": []}) + "\n", encoding="utf-8"
        )
        bad_manifest = self._approve("w1", "--role", "r", "--decision", "approve", cwd=legacy)
        self.assertEqual(bad_manifest.returncode, 2)

    def test_approve_requires_manifest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="checkpoint-approve-empty-") as temp:
            result = self._approve("w1", "--role", "r", "--decision", "approve", cwd=Path(temp))
            self.assertEqual(result.returncode, 2)
            self.assertIn("ok", json.loads(result.stdout))


if __name__ == "__main__":
    unittest.main()
