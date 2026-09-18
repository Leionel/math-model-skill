from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness.py"
sys.path.insert(0, str(ROOT / "scripts"))

import capability_composition  # noqa: E402
from capability_composition import composition as composition_module  # noqa: E402

COPIED_SCHEMAS = (
    "capability.schema.json",
    "verifier.schema.json",
    "model_contract.schema.json",
    "frozen_results.schema.json",
    "validation_report.schema.json",
    "competition_profile.schema.json",
    "submission_manifest.schema.json",
)

DECLARATION = """\
schema_version: "1.0"
capability_id: {capability_id}
verifiers: {verifiers}
schemas: {schemas}
artifact_roles: [model_contract]
gates: {gates}
requires: {requires}
"""


class CompositionFixture(unittest.TestCase):
    """A throwaway repository tree: real schemas, real verifier registry, test capability set."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="capability-composition-")
        self.root = Path(self.temp.name) / "repo"
        (self.root / "schemas").mkdir(parents=True)
        for name in COPIED_SCHEMAS:
            shutil.copy2(ROOT / "schemas" / name, self.root / "schemas" / name)
        shutil.copytree(ROOT / "scripts" / "verifiers", self.root / "scripts" / "verifiers")
        for stub in ("scripts/qa/check_artifact_dag.py", "scripts/qa/check_units.py"):
            path = self.root / stub
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("def main():\n    return 0\n", encoding="utf-8")
        (self.root / "competition_profiles").mkdir()
        shutil.copy2(ROOT / "competition_profiles" / "cumcm.yaml", self.root / "competition_profiles" / "cumcm.yaml")
        self.declarations = self.root / "scripts" / "capability_composition" / "declarations"
        self.declarations.mkdir(parents=True)
        self.compositions = self.root / "scripts" / "capability_composition" / "compositions.yaml"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_capability(self, capability_id: str, **fields: str) -> None:
        body = DECLARATION.format(
            capability_id=capability_id,
            verifiers=fields.get("verifiers", "[]"),
            schemas=fields.get("schemas", "[]"),
            gates=fields.get("gates", "[m1]"),
            requires=fields.get("requires", "[]"),
        )
        (self.declarations / f"{capability_id}.yaml").write_text(body, encoding="utf-8")

    def write_compositions(self, mapping: dict[str, list[str]]) -> None:
        lines = ["schema_version: \"1.0\"", "profiles:"]
        for profile_id, capability_ids in mapping.items():
            lines.append(f"  {profile_id}: [{', '.join(capability_ids)}]")
        self.compositions.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def load(self) -> dict[str, dict[str, object]]:
        return capability_composition.load_declarations(repo_root=self.root)


class CommittedCapabilityTest(unittest.TestCase):
    def test_declarations_cross_check_against_the_registry(self) -> None:
        declarations = capability_composition.load_declarations()
        self.assertEqual(sorted(declarations), ["base-modeling", "contest-compliance", "numerical-validation"])
        self.assertEqual(
            declarations["base-modeling"]["verifiers"],
            ["artifact-freshness", "unit-consistency"],
        )
        self.assertEqual(declarations["numerical-validation"]["requires"], ["base-modeling"])

    def test_every_composition_names_a_real_profile(self) -> None:
        compositions = capability_composition.load_compositions()
        self.assertEqual(set(compositions), capability_composition.profile_ids())

    def test_compose_expands_requires_and_collects_resources(self) -> None:
        composed = capability_composition.compose("cumcm-2026-electronic")
        self.assertEqual(composed["capabilities"], ["base-modeling", "contest-compliance", "numerical-validation"])
        self.assertEqual(composed["verifiers"], ["artifact-freshness", "unit-consistency"])
        self.assertEqual(composed["gates"], ["m1", "p2"])
        self.assertIn("frozen_results.schema.json", composed["schemas"])
        self.assertIn("competition_profile.schema.json", composed["schemas"])
        self.assertEqual(composed["artifact_roles"], ["competition_profile", "frozen_results", "model_contract"])
        self.assertEqual(capability_composition.compose("apmcm"), composed | {"profile_id": "apmcm"})

    def test_unknown_profile_is_refused(self) -> None:
        with self.assertRaises(capability_composition.CapabilityCompositionError):
            capability_composition.compose("no-such-profile")

    def test_cli_compose_for_a_named_profile(self) -> None:
        result = subprocess.run(
            [sys.executable, str(CLI), "profile", "--compose", "--profile-id", "mcm_icm", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["composition"]["profile_id"], "mcm_icm")
        self.assertEqual(payload["composition"]["verifiers"], ["artifact-freshness", "unit-consistency"])
        refused = subprocess.run(
            [sys.executable, str(CLI), "profile", "--compose", "--profile-id", "nope", "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(refused.returncode, 2, refused.stdout + refused.stderr)


class BrokenCapabilityTest(CompositionFixture):
    def test_a_valid_fixture_tree_composes(self) -> None:
        self.write_capability("base-modeling", verifiers="[artifact-freshness]", schemas="[model_contract.schema.json]")
        self.write_capability("extra", requires="[base-modeling]", gates="[p2]", schemas="[frozen_results.schema.json]")
        self.write_compositions({"cumcm-2026-electronic": ["base-modeling", "extra"]})
        composed = capability_composition.compose(
            "cumcm-2026-electronic",
            repo_root=self.root,
            declarations=self.load(),
            compositions=capability_composition.load_compositions(repo_root=self.root),
        )
        self.assertEqual(composed["capabilities"], ["base-modeling", "extra"])

    def test_unknown_verifier_is_rejected(self) -> None:
        self.write_capability("base-modeling", verifiers="[no-such-verifier]")
        with self.assertRaises(capability_composition.CapabilityCompositionError) as caught:
            self.load()
        self.assertIn("unknown verifier_id no-such-verifier", " ".join(caught.exception.errors))

    def test_verifier_that_serves_no_claimed_gate_is_rejected(self) -> None:
        self.write_capability("base-modeling", verifiers="[artifact-freshness]", gates="[p2]")
        with self.assertRaises(capability_composition.CapabilityCompositionError) as caught:
            self.load()
        self.assertIn("artifact-freshness serves ['m1']", " ".join(caught.exception.errors))

    def test_unknown_schema_is_rejected(self) -> None:
        self.write_capability("base-modeling", schemas="[no_such.schema.json]")
        with self.assertRaises(capability_composition.CapabilityCompositionError) as caught:
            self.load()
        self.assertIn("schema does not exist: no_such.schema.json", " ".join(caught.exception.errors))

    def test_unknown_requirement_is_rejected(self) -> None:
        self.write_capability("base-modeling", requires="[ghost]")
        with self.assertRaises(capability_composition.CapabilityCompositionError) as caught:
            self.load()
        self.assertIn("unknown required capability ghost", " ".join(caught.exception.errors))

    def test_requirement_cycles_are_rejected(self) -> None:
        self.write_capability("alpha", requires="[beta]")
        self.write_capability("beta", requires="[alpha]")
        self.write_compositions({"cumcm-2026-electronic": ["alpha"]})
        with self.assertRaises(capability_composition.CapabilityCompositionError) as caught:
            capability_composition.compose(
                "cumcm-2026-electronic",
                repo_root=self.root,
                declarations=self.load(),
                compositions=capability_composition.load_compositions(repo_root=self.root),
            )
        self.assertIn("cycle", " ".join(caught.exception.errors))

    def test_unknown_composition_targets_are_rejected(self) -> None:
        self.write_capability("base-modeling", verifiers="[artifact-freshness]")
        self.write_compositions({"cumcm-2026-electronic": ["ghost"]})
        with self.assertRaises(capability_composition.CapabilityCompositionError) as caught:
            capability_composition.compose(
                "cumcm-2026-electronic",
                repo_root=self.root,
                declarations=self.load(),
                compositions=capability_composition.load_compositions(repo_root=self.root),
            )
        self.assertIn("unknown capability_id in composition: ghost", " ".join(caught.exception.errors))

    def test_composition_naming_an_unknown_profile_is_rejected(self) -> None:
        self.write_compositions({"no-such-profile": []})
        with self.assertRaises(capability_composition.CapabilityCompositionError) as caught:
            capability_composition.load_compositions(repo_root=self.root)
        self.assertIn("unknown profile_id: no-such-profile", " ".join(caught.exception.errors))

    def test_empty_declaration_directory_is_an_error(self) -> None:
        with self.assertRaises(capability_composition.CapabilityCompositionError) as caught:
            self.load()
        self.assertIn("no capability declarations found", " ".join(caught.exception.errors))

    def test_declarations_are_deterministic_and_read_only(self) -> None:
        self.write_capability("base-modeling", verifiers="[artifact-freshness]")
        before = {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in sorted(self.declarations.glob("*.yaml"))
        }
        first = self.load()
        self.assertEqual(first, self.load())
        after = {
            str(path.relative_to(self.root)): path.read_bytes()
            for path in sorted(self.declarations.glob("*.yaml"))
        }
        self.assertEqual(before, after)


class ModuleWiringTest(unittest.TestCase):
    def test_the_package_is_not_named_capabilities(self) -> None:
        # profile_engine imports its sibling `capabilities` module by bare name;
        # a same-named package under scripts/ would shadow it for callers that
        # put scripts/ on sys.path first.
        self.assertFalse((ROOT / "scripts" / "capabilities").exists())
        self.assertTrue((ROOT / "scripts" / "profiles" / "capabilities.py").is_file())
        self.assertTrue((ROOT / "scripts" / "capability_composition" / "composition.py").is_file())

    def test_declared_schema_directory_matches_the_schema_files(self) -> None:
        schema_dir = ROOT / "schemas"
        for declaration in capability_composition.load_declarations().values():
            for name in declaration["schemas"]:
                self.assertTrue((schema_dir / name).is_file(), name)
        self.assertTrue(composition_module.DECLARATIONS_DIR.is_dir())


if __name__ == "__main__":
    unittest.main()