from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAULTS = ROOT / "evaluation" / "recovery" / "faults"
HARNESS = ROOT / "scripts" / "harness.py"
STUB_REVIEWER = ROOT / "tests" / "fixtures" / "review_stub" / "stub_reviewer.py"

sys.path.insert(0, str(ROOT / "tests"))

from _recovery_baseline import built_fixture  # noqa: E402


class RecoveryFaultDetectionTest(unittest.TestCase):
    """Every declared fault must be detected after injection: the fault.json
    expected_detection anchor must appear in the detector's error list.  A fault
    that silently passes is a detection gap and must be recorded in
    docs/RECOVERY_BENCHMARK_DESIGN_2026-09-21.md §6, never papered over here."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = built_fixture()

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
                    shutil.copytree(self.fixture, project)
                    # Anti-vacuity lock: the detector's own baseline must be
                    # green on this clone before injecting, or a "detected"
                    # blocker could just be relocation noise.  W2 is the
                    # relocation-sensitive gate (review evidence binds absolute
                    # paths), so it is re-established with a fresh scripted
                    # review first — the same move run_demo's claim probe makes.
                    if fault["expected_detection"]["tool"] == "harness validate":
                        self._re_review(project)
                    for gate in ("M1", "P1", "P2"):
                        baseline = self._run(["check", gate], project)
                        self.assertEqual(
                            baseline.returncode, 0,
                            f"{fault['fault_id']} baseline clone is not green at {gate}: "
                            f"{baseline.stdout[-1500:]}",
                        )
                    if fault["expected_detection"]["tool"] == "harness validate":
                        baseline = self._run(["validate"], project)
                        self.assertEqual(
                            baseline.returncode, 0,
                            f"{fault['fault_id']} baseline clone is not green at W2: "
                            f"{baseline.stdout[-1500:]}",
                        )
                    injected = subprocess.run(
                        [sys.executable, str(fault_dir / "inject.py"), "--project-root", str(project)],
                        text=True, capture_output=True, encoding="utf-8", check=False,
                    )
                    self.assertEqual(injected.returncode, 0, injected.stdout + injected.stderr)

                    detection = fault["expected_detection"]
                    detector_args = detection["tool"].split(" ")[1:]
                    if detection["tool"] == "harness check":
                        detector_args.append(detection["gate"])
                    detector = self._run(detector_args, project)
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

    @staticmethod
    def _run(args: list[str], project: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HARNESS), *args, "--project", str(project), "--json"],
            cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", check=False,
        )

    @staticmethod
    def _re_review(project: Path) -> None:
        reviewed = subprocess.run(
            [sys.executable, str(HARNESS), "review", "--project", str(project), "--fresh",
             "--backend-cmd", f'"{sys.executable}" "{STUB_REVIEWER}"', "--backend-kind", "non_ai", "--json"],
            cwd=str(ROOT), text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )
        assert reviewed.returncode == 0, reviewed.stdout[-1500:] + reviewed.stderr[-1500:]

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
