"""R7.1 rendered-level figure QA: clipped content and blank canvases are
blocked with a non-zero exit code; clean figures record rendered metrics."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

try:
    import matplotlib.image  # noqa: F401
    import numpy  # noqa: F401

    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_profile(project: Path) -> Path:
    rule = project / "rule.txt"
    rule.write_text("fixture visual rule", encoding="utf-8")
    profile = {
        "schema_version": "1.0",
        "profile_id": "fixture",
        "competition_profile_id": "fixture",
        "sources": [
            {
                "kind": "local_policy",
                "title": "fixture",
                "url": "https://example.org/fixture",
                "retrieved_at": "2026-08-28",
                "snapshot": {"path": "rule.txt", "sha256": _sha256(rule)},
            }
        ],
        "page": {"width_mm": 210, "height_mm": 297, "size_tolerance_mm": 1, "min_margin_mm": 10, "max_body_pages": 5},
        "typography": {
            "min_body_font_pt": 9,
            "min_figure_font_pt": 7,
            "embedded_fonts_required": True,
            "cjk_render_review_required": False,
            "allowed_engines": ["xelatex"],
        },
        "figures": {"raster_min_dpi": 60, "grayscale_review_required": False, "colorblind_review_required": False, "dual_axis_default": "deny"},
        "tables": {"allow_vertical_rules": False, "require_units_in_header_or_caption": True},
        "severity_policy": {
            "official_rule_violation": "error",
            "unreadable_or_clipped": "error",
            "font_embedding": "warning",
            "low_resolution": "warning",
            "density_or_style": "warning",
        },
    }
    path = project / "visual_profile.json"
    path.write_text(json.dumps(profile), encoding="utf-8")
    return path


def _write_png(path: Path, canvas: object) -> None:
    import matplotlib.image as mpimg

    mpimg.imsave(str(path), canvas)


def _canvas(rect: tuple[int, int, int, int] | None, size: tuple[int, int] = (120, 160)) -> object:
    import numpy as np

    height, width = size
    image = np.ones((height, width, 3), dtype=float)
    if rect is not None:
        top, bottom, left, right = rect
        image[top:bottom, left:right, :] = 0.0
    return image


def _transparent_canvas(size: tuple[int, int] = (120, 160)) -> object:
    import numpy as np

    height, width = size
    image = np.zeros((height, width, 4), dtype=float)
    image[..., :3] = np.random.default_rng(7).random((height, width, 3))
    return image


def _run_check(project: Path, figure: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "figures" / "check_figure.py"),
            "--figure-id", "fig-1",
            "--figure", figure,
            "--profile", "visual_profile.json",
            "--output", "figure_qa.json",
            "--project-root", str(project),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


@unittest.skipUnless(PLOTTING_AVAILABLE, "numpy/matplotlib unavailable")
class RenderedFigureQaTest(unittest.TestCase):
    def test_clean_figure_passes_and_records_rendered_metrics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="figqa-") as temp:
            project = Path(temp)
            _write_profile(project)
            _write_png(project / "figure.png", _canvas((20, 100, 30, 130)))
            result = _run_check(project, "figure.png")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            report = json.loads((project / "figure_qa.json").read_text(encoding="utf-8"))
            rendered = report["automated"]["rendered"]
            self.assertTrue(rendered["checked"])
            self.assertEqual(rendered["content_bbox"], [30, 20, 129, 99])
            self.assertTrue(report["ok"])

    def test_clipped_figure_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="figqa-") as temp:
            project = Path(temp)
            _write_profile(project)
            _write_png(project / "figure.png", _canvas((0, 120, 30, 160)))
            result = _run_check(project, "figure.png")
            self.assertEqual(result.returncode, 1)
            report = json.loads((project / "figure_qa.json").read_text(encoding="utf-8"))
            self.assertFalse(report["ok"])
            self.assertTrue(any("touches the" in row for row in report["automated"]["errors"]))

    def test_blank_figure_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="figqa-") as temp:
            project = Path(temp)
            _write_profile(project)
            _write_png(project / "figure.png", _canvas(None))
            result = _run_check(project, "figure.png")
            self.assertEqual(result.returncode, 1)
            report = json.loads((project / "figure_qa.json").read_text(encoding="utf-8"))
            self.assertTrue(any("blank" in row for row in report["automated"]["errors"]))

    def test_fully_transparent_rgb_noise_is_still_blank(self) -> None:
        with tempfile.TemporaryDirectory(prefix="figqa-") as temp:
            project = Path(temp)
            _write_profile(project)
            _write_png(project / "figure.png", _transparent_canvas())
            result = _run_check(project, "figure.png")
            self.assertEqual(result.returncode, 1)
            report = json.loads((project / "figure_qa.json").read_text(encoding="utf-8"))
            self.assertTrue(any("blank" in row for row in report["automated"]["errors"]))


if __name__ == "__main__":
    unittest.main()
