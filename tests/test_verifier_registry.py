from __future__ import annotations

import hashlib
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import verifiers  # noqa: E402

GATE_RUNTIME = ROOT / "scripts" / "v2_gate_runtime.py"
VALID_DECLARATION = """\
schema_version: "1.0"
verifier_id: fixture-check
entrypoint:
  script: scripts/qa/check_units.py
consumes: [model_contract]
gates: [m1]
severity: error
deterministic: true
repair_hint: "repair the fixture input, then rerun the gate"
"""


def gate_runtime_body(gate: str) -> str:
    """Return the source of ``_v2_gate_<gate>``.

    A declaration claims a gate runtime invokes its entrypoint; this is the
    source text that claim is checked against.
    """

    text = GATE_RUNTIME.read_text(encoding="utf-8")
    match = re.search(rf"^def _v2_gate_{gate}\(.*?(?=^def )", text, flags=re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError(f"no _v2_gate_{gate} function in {GATE_RUNTIME}")
    return match.group(0)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class CommittedDeclarationsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = verifiers.load_registry()

    def test_committed_declarations_load(self) -> None:
        self.assertEqual(sorted(self.registry), ["artifact-freshness", "unit-consistency"])

    def test_each_declaration_names_an_existing_script(self) -> None:
        for verifier_id, declaration in self.registry.items():
            script = ROOT / declaration["entrypoint"]["script"]
            self.assertTrue(script.is_file(), f"{verifier_id} names {script}")

    def test_declared_gate_runtime_invokes_the_entrypoint(self) -> None:
        for verifier_id, declaration in self.registry.items():
            basename = Path(declaration["entrypoint"]["script"]).name
            for gate in declaration["gates"]:
                self.assertIn(basename, gate_runtime_body(gate), f"{verifier_id} claims gate {gate}")

    def test_schema_vocabulary_matches_the_registry(self) -> None:
        schema = json.loads((ROOT / "schemas" / "verifier.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["gates"]["items"]["enum"], list(verifiers.GATES))
        self.assertEqual(schema["properties"]["consumes"]["items"]["enum"], list(verifiers.CONSUMES))

    def test_registry_for_gate_selects_and_rejects(self) -> None:
        self.assertEqual(
            verifiers.registry_for_gate(self.registry, "m1"),
            ["artifact-freshness", "unit-consistency"],
        )
        self.assertEqual(verifiers.registry_for_gate(self.registry, "S1"), [])
        with self.assertRaises(ValueError):
            verifiers.registry_for_gate(self.registry, "zz")

    def test_load_is_deterministic_and_read_only(self) -> None:
        before = self.snapshot()
        self.assertEqual(verifiers.load_registry(), verifiers.load_registry())
        self.assertEqual(before, self.snapshot())

    def snapshot(self) -> dict[str, str]:
        return {
            str(path.relative_to(ROOT)): sha256(path)
            for path in sorted((ROOT / "scripts" / "verifiers").rglob("*"))
            if path.is_file()
        }


class BrokenDeclarationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="verifier-registry-")
        self.root = Path(self.temp.name)
        (self.root / "schemas").mkdir()
        shutil.copy2(ROOT / "schemas" / "verifier.schema.json", self.root / "schemas" / "verifier.schema.json")
        self.declarations = self.root / "scripts" / "verifiers" / "declarations"
        self.declarations.mkdir(parents=True)
        self.script = self.root / "scripts" / "qa" / "check_units.py"
        self.script.parent.mkdir(parents=True)
        self.script.write_text("def main():\n    return 0\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, name: str, text: str) -> None:
        (self.declarations / name).write_text(text, encoding="utf-8")

    def load(self) -> dict[str, dict[str, object]]:
        return verifiers.load_registry(repo_root=self.root)

    def test_a_valid_fixture_tree_loads(self) -> None:
        self.write("fixture.yaml", VALID_DECLARATION)
        self.assertEqual(sorted(self.load()), ["fixture-check"])

    def test_duplicate_verifier_id_is_rejected(self) -> None:
        self.write("a.yaml", VALID_DECLARATION)
        self.write("b.yaml", VALID_DECLARATION)
        with self.assertRaises(verifiers.VerifierContractError) as caught:
            self.load()
        self.assertIn("duplicate verifier_id fixture-check", " ".join(caught.exception.errors))

    def test_unknown_gate_is_rejected(self) -> None:
        self.write("fixture.yaml", VALID_DECLARATION.replace("gates: [m1]", "gates: [zz]"))
        with self.assertRaises(verifiers.VerifierContractError) as caught:
            self.load()
        self.assertIn("zz", " ".join(caught.exception.errors))

    def test_unknown_consume_is_rejected(self) -> None:
        self.write("fixture.yaml", VALID_DECLARATION.replace("consumes: [model_contract]", "consumes: [vibes]"))
        with self.assertRaises(verifiers.VerifierContractError) as caught:
            self.load()
        self.assertIn("vibes", " ".join(caught.exception.errors))

    def test_missing_entrypoint_script_is_rejected(self) -> None:
        self.write("fixture.yaml", VALID_DECLARATION.replace("check_units.py", "check_missing.py"))
        with self.assertRaises(verifiers.VerifierContractError) as caught:
            self.load()
        self.assertIn("entrypoint script does not exist", " ".join(caught.exception.errors))

    def test_entrypoint_escape_is_rejected(self) -> None:
        self.write(
            "fixture.yaml",
            VALID_DECLARATION.replace("script: scripts/qa/check_units.py", "script: scripts/../../outside.py"),
        )
        with self.assertRaises(verifiers.VerifierContractError) as caught:
            self.load()
        joined = " ".join(caught.exception.errors)
        self.assertTrue("escapes the repository root" in joined or "pattern" in joined, joined)

    def test_empty_declaration_directory_is_an_error(self) -> None:
        with self.assertRaises(verifiers.VerifierContractError) as caught:
            self.load()
        self.assertIn("no verifier declarations found", " ".join(caught.exception.errors))

    def test_reported_errors_are_sorted(self) -> None:
        self.write("b.yaml", VALID_DECLARATION.replace("gates: [m1]", "gates: [zz]"))
        self.write("a.yaml", VALID_DECLARATION.replace("severity: error", "severity: fatal"))
        with self.assertRaises(verifiers.VerifierContractError) as caught:
            self.load()
        self.assertEqual(caught.exception.errors, sorted(caught.exception.errors))
        self.assertTrue(all(error.startswith(("a.yaml", "b.yaml")) for error in caught.exception.errors))


if __name__ == "__main__":
    unittest.main()