from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "evaluation" / "recovery" / "fixtures" / "slim_v2"
FAULTS = ROOT / "evaluation" / "recovery" / "faults"
HARNESS = ROOT / "scripts" / "harness.py"


@unittest.skipUnless(FIXTURE.is_dir(), "slim fixture has not been generated yet")
class RecoveryFaultDetectionTest(unittest.TestCase):
    """Every declared fault must be detected after injection: the fault.json
    expected_detection anchor must appear in the detector's error list.  A fault
    that silently passes is a detection gap and must be recorded in
    docs/RECOVERY_BENCHMARK_DESIGN_2026-09-21.md §6, never papered over here."""

    def test_fault_directories_exist(self) -> None:
        declared = sorted(path.name for path in FAULTS.iterdir() if path.is_dir())
        self.assertTrue(declared, "no fault directories found")
        for name in declared:
            with self.subTest(fault=name):
                self.assertTrue((FAULTS / name / "fault.json").is_file(), "fault.json missing")
                self.assertTrue((FAULTS / name / "inject.py").is_file(), "inject.py missing")

    def test_every_declared_fault_is_detected(self) -> None:
        for fault_dir in sorted(path for path in FAULTS.iterdir() if path.is_dir()):
            with self.subTest(fault=fault_dir.name):
                fault = json.loads((fault_dir / "fault.json").read_text(encoding="utf-8"))
                with tempfile.TemporaryDirectory(prefix=f"recovery-{fault['fault_id']}-") as temp:
                    project = Path(temp) / "project"
                    shutil.copytree(FIXTURE, project)
                    injected = subprocess.run(
                        [sys.executable, str(fault_dir / "inject.py"), "--project-root", str(project)],
                        text=True, capture_output=True, encoding="utf-8", check=False,
                    )
                    self.assertEqual(injected.returncode, 0, injected.stdout + injected.stderr)

                    detection = fault["expected_detection"]
                    argv = [sys.executable, str(HARNESS)]
                    argv.extend(detection["tool"].split(" ")[1:])
                    if detection["tool"] == "harness check":
                        argv.append(detection["gate"])
                    argv.extend(["--project", str(project), "--json"])
                    detector = subprocess.run(
                        argv, text=True, capture_output=True, encoding="utf-8", check=False,
                    )
                    self.assertNotEqual(
                        detector.returncode, 0,
                        f"{fault['fault_id']} was NOT detected by {detection['tool']} "
                        f"{detection['gate']}: a detection gap; record it in the design doc §6 "
                        "instead of loosening this assertion",
                    )
                    errors = self._errors(detector.stdout)
                    self.assertTrue(
                        any(detection["error_substring"] in error for error in errors),
                        f"{fault['fault_id']} expected substring {detection['error_substring']!r} "
                        f"in {detection['tool']} {detection['gate']} errors, got: {errors[:4]}",
                    )

    def test_injection_on_green_fixture_refuses_wrong_shape(self) -> None:
        for fault_dir in sorted(path for path in FAULTS.iterdir() if path.is_dir()):
            with self.subTest(fault=fault_dir.name):
                fault = json.loads((fault_dir / "fault.json").read_text(encoding="utf-8"))
                with tempfile.TemporaryDirectory(prefix=f"recovery-neg-{fault['fault_id']}-") as temp:
                    project = Path(temp) / "project"
                    project.mkdir()
                    result = subprocess.run(
                        [sys.executable, str(fault_dir / "inject.py"), "--project-root", str(project)],
                        text=True, capture_output=True, encoding="utf-8", check=False,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertFalse(json.loads(result.stdout)["ok"])

    @staticmethod
    def _errors(stdout: str) -> list[str]:
        try:
            payload = json.loads(stdout)
        except json.JSONDecodeError:
            return [stdout]
        errors = list(payload.get("errors") or [])
        for gate in payload.get("gates") or []:
            errors.extend(gate.get("errors") or [])
        return errors


if __name__ == "__main__":
    unittest.main()
