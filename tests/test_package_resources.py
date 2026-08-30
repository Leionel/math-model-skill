"""R10 distribution integrity: checkout roots are verified, and a wheel must
carry every on-disk resource file (.gitkeep placeholders excluded)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "qa" / "check_package_resources.py"


def _run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
    )


class CheckoutModeTest(unittest.TestCase):
    def test_committed_repo_roots_are_complete(self) -> None:
        result = _run_cli("--repo-root", str(ROOT))
        self.assertEqual(result.returncode, 0, result.stdout[-2000:])
        payload = json.loads(result.stdout)
        self.assertEqual(sorted(payload["resources"]), ["assets", "competition_profiles", "references", "schemas"])
        self.assertGreater(payload["resources"]["schemas"]["files"], 0)


class WheelModeTest(unittest.TestCase):
    def _make_repo(self, root: Path) -> list[str]:
        files = {
            "schemas/a.schema.json": "{}",
            "references/router.md": "# router",
            "competition_profiles/cumcm.yaml": "seed: true",
            "assets/styles/probe.mplstyle": "axes.grid: True",
            "references/precedents/.gitkeep": "",
        }
        for rel, text in files.items():
            target = root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return [rel for rel in files if not rel.endswith(".gitkeep")]

    def _build_wheel(self, root: Path, entries: list[str]) -> Path:
        wheel = root / "fake.whl"
        with zipfile.ZipFile(wheel, "w") as archive:
            for rel in entries:
                archive.write(root / rel, rel)
        return wheel

    def test_complete_wheel_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pkgres-") as temp:
            root = Path(temp)
            entries = self._make_repo(root)
            wheel = self._build_wheel(root, entries)
            result = _run_cli("--repo-root", str(root), "--wheel", str(wheel))
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])
            payload = json.loads(result.stdout)
            self.assertTrue(all(row.get("in_wheel") for row in payload["resources"].values()))

    def test_missing_resource_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pkgres-") as temp:
            root = Path(temp)
            entries = self._make_repo(root)
            entries.remove("assets/styles/probe.mplstyle")
            wheel = self._build_wheel(root, entries)
            result = _run_cli("--repo-root", str(root), "--wheel", str(wheel))
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertTrue(any("assets/ file(s) absent from wheel" in err for err in payload["errors"]), payload["errors"])

    def test_invalid_wheel_reports_a_clean_error(self) -> None:
        with tempfile.TemporaryDirectory(prefix="pkgres-") as temp:
            root = Path(temp)
            self._make_repo(root)
            wheel = root / "broken.whl"
            wheel.write_text("not a zip archive", encoding="utf-8")
            result = _run_cli("--repo-root", str(root), "--wheel", str(wheel))
            self.assertEqual(result.returncode, 1)
            payload = json.loads(result.stdout)
            self.assertTrue(any("cannot be read" in err for err in payload["errors"]), payload)


if __name__ == "__main__":
    unittest.main()
