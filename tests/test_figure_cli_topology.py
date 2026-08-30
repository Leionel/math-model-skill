from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "harness.py"


class FigureCliTopologyTest(unittest.TestCase):
    def test_declared_topology_routes_complex_diagram_to_drawio(self) -> None:
        with tempfile.TemporaryDirectory(prefix="harness-figure-topology-") as temp:
            project = Path(temp)
            result = subprocess.run(
                [
                    sys.executable,
                    str(CLI),
                    "figure",
                    "FIG-COMPLEX",
                    "--semantic-type",
                    "workflow",
                    "--node-count",
                    "14",
                    "--dag-depth",
                    "5",
                    "--branch-count",
                    "4",
                    "--parallel-lanes",
                    "3",
                    "--density",
                    "high",
                    "--project",
                    str(project),
                    "--json",
                ],
                cwd=str(ROOT),
                text=True,
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            route = json.loads(result.stdout)["route"]
            self.assertEqual(route["default_tool"], "drawio")
            self.assertEqual(route["backend_selection"]["selection"], "complex_dag")


if __name__ == "__main__":
    unittest.main()
