"""Illustration execution protocol: only illustration routes may generate;
requests are provider-neutral; collection binds hash and review duties."""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from figures.illustration_execution import (  # noqa: E402
    build_image_generation_request,
    collect_illustration_output,
)
from figures.tool_router import route_figure  # noqa: E402

BRIEF = """# FIG-MECH

## Purpose

show the mechanism

## Main message

load shifts to cheap regions

## Reader should understand

why cost drops

## Required elements

two regions, one arrow

## Required relations

price gap drives flow

## Primary reading order

left to right

## Visual references

## Source evidence

## Must not include

numeric results
"""


def _write_brief(root: Path, figure_id: str) -> Path:
    path = root / "figures" / figure_id / "brief.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(BRIEF, encoding="utf-8")
    return path


class IllustrationRequestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="illustration-")
        self.root = Path(self.temp.name)
        self.brief_path = _write_brief(self.root, "FIG-MECH")
        self.route = route_figure("illustration", "physical mechanism")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _request(self, **overrides):
        kwargs = dict(
            figure_id="FIG-MECH",
            brief_path=self.brief_path,
            root=self.root,
            route=self.route,
            capability="available",
            ai_policy="allowed",
        )
        kwargs.update(overrides)
        return build_image_generation_request(**kwargs)

    def test_illustration_route_builds_prompt_from_brief(self) -> None:
        request = self._request()
        self.assertTrue(request["ok"])
        self.assertEqual(request["status"], "requested")
        self.assertIn("load shifts to cheap regions", request["prompt"])
        self.assertIn("no numeric results", " ".join(request["negative_constraints"]))
        self.assertEqual(request["parameters"]["raster_dpi"], 300)

    def test_data_route_is_rejected(self) -> None:
        request = self._request(route=route_figure("data", "trend"))
        self.assertFalse(request["ok"])
        self.assertEqual(request["status"], "route_rejected")
        self.assertIn("deterministic", request["message"])

    def test_diagram_route_is_rejected(self) -> None:
        request = self._request(route=route_figure("diagram", "workflow"))
        self.assertFalse(request["ok"])
        self.assertEqual(request["status"], "route_rejected")

    def test_forbidden_profile_blocks_generation(self) -> None:
        request = self._request(ai_policy="forbidden")
        self.assertFalse(request["ok"])
        self.assertEqual(request["status"], "forbidden_by_profile")

    def test_missing_capability_is_reported_not_faked(self) -> None:
        request = self._request(capability="missing")
        self.assertTrue(request["ok"])
        self.assertEqual(request["status"], "missing")
        self.assertIn("prompt", request)

    def test_unknown_policy_blocks_generation(self) -> None:
        request = self._request(ai_policy="unknown")
        self.assertFalse(request["ok"])
        self.assertEqual(request["status"], "policy_unresolved")

    def test_unknown_capability_blocks_generation(self) -> None:
        request = self._request(capability="unknown")
        self.assertFalse(request["ok"])
        self.assertEqual(request["status"], "unknown_capability")

    def test_incomplete_brief_is_rejected(self) -> None:
        empty = self.brief_path.with_name("brief.md")
        empty.write_text("# FIG-MECH\n\n## Purpose\n\nonly purpose\n", encoding="utf-8")
        request = self._request()
        self.assertFalse(request["ok"])
        self.assertEqual(request["status"], "incomplete_brief")
        self.assertIn("missing sections", request["message"])


class IllustrationCollectTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="illustration-collect-")
        self.root = Path(self.temp.name)
        self.request_path = self.root / ".harness" / "views" / "figures" / "FIG-MECH_image_generation_request.json"
        self.request_path.parent.mkdir(parents=True, exist_ok=True)
        self.request_path.write_text(json.dumps({
            "ok": True,
            "schema_version": "1.0",
            "figure_id": "FIG-MECH",
            "kind": "illustration",
            "status": "requested",
        }), encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _collect(self, path: Path):
        return collect_illustration_output(
            figure_id="FIG-MECH",
            generated_path=path,
            root=self.root,
            request_path=self.request_path,
        )

    def test_collects_png_with_hash_and_pending_review(self) -> None:
        png = self.root / "figures" / "FIG-MECH" / "generated.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        record = self._collect(png)
        self.assertTrue(record["ok"])
        self.assertEqual(record["review_status"], "pending")
        self.assertEqual(record["generated"]["sha256"], hashlib.sha256(png.read_bytes()).hexdigest())
        self.assertEqual(record["generated"]["path"], "figures/FIG-MECH/generated.png")
        self.assertEqual(len(record["review_requirements"]), 3)

    def test_missing_artifact_is_reported(self) -> None:
        record = self._collect(self.root / "figures" / "FIG-MECH" / "ghost.png")
        self.assertFalse(record["ok"])
        self.assertEqual(record["status"], "missing_artifact")

    def test_non_raster_artifact_is_rejected(self) -> None:
        txt = self.root / "figures" / "FIG-MECH" / "generated.txt"
        txt.parent.mkdir(parents=True, exist_ok=True)
        txt.write_text("not an image", encoding="utf-8")
        record = self._collect(txt)
        self.assertFalse(record["ok"])
        self.assertEqual(record["status"], "unsupported_artifact")

    def test_missing_request_is_rejected(self) -> None:
        self.request_path.unlink()
        png = self.root / "figures" / "FIG-MECH" / "generated.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        png.write_bytes(b"\x89PNG\r\n\x1a\n")
        record = self._collect(png)
        self.assertFalse(record["ok"])
        self.assertEqual(record["status"], "missing_request")

    def test_mismatched_request_is_rejected(self) -> None:
        request = json.loads(self.request_path.read_text(encoding="utf-8"))
        request["figure_id"] = "FIG-OTHER"
        self.request_path.write_text(json.dumps(request), encoding="utf-8")
        png = self.root / "figures" / "FIG-MECH" / "generated.png"
        png.parent.mkdir(parents=True, exist_ok=True)
        png.write_bytes(b"\x89PNG\r\n\x1a\n")
        record = self._collect(png)
        self.assertFalse(record["ok"])
        self.assertEqual(record["status"], "request_mismatch")

    def test_path_escape_is_rejected(self) -> None:
        outside = Path(self.temp.name) / ".." / "escape.png"
        record = self._collect(self.root / "figures" / "FIG-MECH" / "generated.png") if not outside.is_file() else None
        # direct escape: a file outside the project root
        external = Path(tempfile.gettempdir()) / "escape-test-illustration.png"
        external.write_bytes(b"\x89PNG\r\n\x1a\n")
        try:
            record = collect_illustration_output(
                figure_id="FIG-MECH",
                generated_path=external,
                root=self.root,
                request_path=self.request_path,
            )
            self.assertFalse(record["ok"])
            self.assertEqual(record["status"], "path_escape")
        finally:
            external.unlink(missing_ok=True)
        self.assertIsNotNone(record)


if __name__ == "__main__":
    unittest.main()
