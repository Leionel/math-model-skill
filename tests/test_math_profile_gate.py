import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_p0_harness as p0


ROOT = Path(__file__).resolve().parents[1]


class MathProfileGateTest(unittest.TestCase):
    def test_strict_math_profile_is_opt_in_and_blocks_unmigrated_fixture(self) -> None:
        harness = p0.P0HarnessTest()
        with tempfile.TemporaryDirectory(prefix="math-harness-strict-profile-") as temp:
            project = Path(temp)
            paths = harness.build_fixture(project)
            manifest = p0.read_json(paths["manifest"])
            manifest["math_correctness_profile"] = "strict"
            p0.write_json(paths["manifest"], manifest)

            result = harness.run_script(
                "qa/check_gates.py",
                "--project-root", str(project),
                "--manifest", paths["manifest"].name,
                "--strict",
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("scope_contract", result.stdout)
            self.assertIn("presentation_contract", result.stdout)


if __name__ == "__main__":
    unittest.main()
