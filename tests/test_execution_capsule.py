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
DEMO = ROOT / "examples" / "end_to_end" / "run_demo.py"
CAPSULE_SCHEMA = ROOT / "schemas" / "execution_capsule.schema.json"
sys.path.insert(0, str(ROOT / "scripts"))

import jsonschema  # noqa: E402
from runtime import backend as runtime_backend  # noqa: E402


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def project_snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): sha256(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


class ExecutionCapsuleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory(prefix="execution-capsule-")
        cls.demo = (Path(cls.temp.name) / "demo").resolve()
        built = subprocess.run(
            [sys.executable, str(DEMO), "--out", str(cls.demo), "--quiet", "--skip-probes"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if built.returncode != 0:
            raise AssertionError(f"demo build failed: {built.stdout}\n{built.stderr}")
        # A deterministic command captured through the Harness' own receipt seam.
        cls.stable_output = cls.demo / "repro.txt"
        captured = subprocess.run(
            [
                sys.executable, str(CLI), "execute", "--project", str(cls.demo), "--stage", "smoke",
                "--output-artifact", "repro.txt",
                sys.executable, "-c", "open(r'%s', 'w').write('stable')" % cls.stable_output,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if captured.returncode != 0:
            raise AssertionError(f"receipt capture failed: {captured.stdout}\n{captured.stderr}")
        cls.smoke_receipt = sorted((cls.demo / "receipts").glob("smoke-*.json"))[-1]
        cls.freeze_receipt = cls._receipt_with_digests(cls.demo)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    @staticmethod
    def _receipt_with_digests(project: Path) -> Path:
        for path in sorted((project / "receipts").glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            refs = document.get("output_refs") or []
            if document.get("argv") and any(isinstance(ref.get("sha256"), str) for ref in refs):
                return path
        raise AssertionError("the demo produced no receipt with a digest-bound output")

    def test_capsule_is_derived_from_a_receipt(self) -> None:
        capsule = runtime_backend.build_capsule(self.freeze_receipt)
        schema = json.loads(CAPSULE_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(capsule)
        receipt = json.loads(self.freeze_receipt.read_text(encoding="utf-8"))
        self.assertEqual(capsule["command"]["argv"], receipt["argv"])
        self.assertEqual(capsule["expected"]["exit_code"], receipt["exit_code"])
        self.assertEqual(len(capsule["outputs"]), len(receipt["output_refs"]))
        self.assertFalse(capsule["environment"]["variables_captured"])
        self.assertFalse(capsule["randomness"]["captured"])
        self.assertEqual(capsule["environment"]["backend"], "local")

    def test_reproduction_reproduces_the_recorded_outcome_without_touching_the_project(self) -> None:
        before = project_snapshot(self.demo)
        report = runtime_backend.reproduce(self.smoke_receipt)
        self.assertTrue(report["ok"], report)
        self.assertTrue(report["exit_code_matches"])
        self.assertEqual(report["recorded_outcome"], "success")
        # The smoke receipt binds no output digest, so reproduction is at
        # exit-code level here; digest binding is asserted separately below.
        self.assertEqual(report["outputs"], [])
        self.assertEqual(before, project_snapshot(self.demo), "reproduction must not modify the recorded project")

    def test_a_digest_bound_output_is_compared_and_reported(self) -> None:
        # The demo's freeze producer embeds the run root in its output, so a
        # reproduction from a copied root reveals that the artifact is not
        # byte-stable across roots. The capsule is not allowed to pretend
        # otherwise: it reports the mismatch and the reconstructed precondition.
        report = runtime_backend.reproduce(self.freeze_receipt)
        self.assertFalse(report["ok"])
        self.assertTrue(report["exit_code_matches"])
        self.assertEqual(report["removed_before_run"], ["frozen_results.json"])
        self.assertEqual(report["mismatches"], ["frozen_results.json"])
        self.assertFalse(report["outputs"][0]["match"])

    def test_a_tampered_capsule_digest_is_a_mismatch(self) -> None:
        capsule = runtime_backend.build_capsule(self.smoke_receipt)
        capsule["outputs"] = [{"path": "repro.txt", "sha256": "0" * 64}]
        path = Path(self.temp.name) / "tampered-capsule.json"
        path.write_text(json.dumps(capsule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = runtime_backend.reproduce(path)
        self.assertFalse(report["ok"])
        self.assertEqual(report["mismatches"], ["repro.txt"])
        self.assertTrue(report["exit_code_matches"])

    def test_stable_outputs_reproduce_byte_for_byte(self) -> None:
        capsule = runtime_backend.build_capsule(self.smoke_receipt)
        capsule["outputs"] = [{"path": "repro.txt", "sha256": sha256(self.stable_output)}]
        path = Path(self.temp.name) / "stable-capsule.json"
        path.write_text(json.dumps(capsule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report = runtime_backend.reproduce(path)
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["mismatches"], [])
        self.assertEqual(report["removed_before_run"], ["repro.txt"])

    def test_unusable_sources_are_refused(self) -> None:
        with self.assertRaises(runtime_backend.CapsuleError):
            runtime_backend.build_capsule(Path(self.temp.name) / "missing.json")
        broken = Path(self.temp.name) / "broken-receipt.json"
        broken.write_text(json.dumps({"receipt_id": "REC-1", "cwd": str(self.demo), "exit_code": 0}), encoding="utf-8")
        with self.assertRaises(runtime_backend.CapsuleError):
            runtime_backend.build_capsule(broken)

    def test_local_backend_executes_and_snapshots_environment(self) -> None:
        backend = runtime_backend.LocalBackend()
        environment = backend.snapshot_environment()
        self.assertEqual(environment["backend"], "local")
        self.assertIn("python", environment)
        result = backend.execute([sys.executable, "-c", "print('ok')"], self.demo, timeout=60)
        self.assertEqual(result["exit_code"], 0)
        self.assertIn("ok", result["stdout"])
        backend.terminate()

    def test_cli_reproduce_and_capsule_output(self) -> None:
        capsule_out = Path(self.temp.name) / "capsule.json"
        first = subprocess.run(
            [sys.executable, str(CLI), "reproduce", str(self.smoke_receipt), "--capsule-out", str(capsule_out), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        self.assertTrue(json.loads(first.stdout)["ok"])
        schema = json.loads(CAPSULE_SCHEMA.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator(schema).validate(json.loads(capsule_out.read_text(encoding="utf-8")))

        capsule = json.loads(capsule_out.read_text(encoding="utf-8"))
        capsule["expected"]["exit_code"] = 99
        tampered = Path(self.temp.name) / "tampered-exit.json"
        tampered.write_text(json.dumps(capsule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        mismatched = subprocess.run(
            [sys.executable, str(CLI), "reproduce", str(tampered), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(mismatched.returncode, 1, mismatched.stdout + mismatched.stderr)
        self.assertFalse(json.loads(mismatched.stdout)["ok"])

        refused = subprocess.run(
            [sys.executable, str(CLI), "reproduce", str(Path(self.temp.name) / "missing.json"), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)


if __name__ == "__main__":
    unittest.main()