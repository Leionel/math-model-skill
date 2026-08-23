"""Regression tests for PPTX concept-figure routing and safe staging."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from figures.pptx_router import PPTX_REFERENCE_CATALOG, select_pptx_reference, stage_pptx_reference  # noqa: E402


class PptxRouterTest(unittest.TestCase):
    def test_catalog_references_all_resolve_to_local_pptx_assets(self) -> None:
        self.assertGreaterEqual(len(PPTX_REFERENCE_CATALOG), 8)
        for row in PPTX_REFERENCE_CATALOG:
            with self.subTest(reference_id=row["reference_id"]):
                selected = select_pptx_reference(None, reference_id=row["reference_id"])
                self.assertEqual(selected["reference_id"], row["reference_id"])
                self.assertTrue((ROOT / selected["source_pptx"]).is_file())
                self.assertGreater(int(selected["source_slide"]), 0)

    def test_staging_copies_once_and_preserves_an_existing_edit(self) -> None:
        reference = select_pptx_reference("workflow")
        with tempfile.TemporaryDirectory(prefix="harness-pptx-router-") as temp:
            root = Path(temp)
            first = stage_pptx_reference(root, "FIG-01", reference)
            target = root / first["path"]
            source = ROOT / first["source_pptx"]
            self.assertTrue(first["created"])
            self.assertEqual(target.read_bytes(), source.read_bytes())
            target.write_bytes(b"edited")
            second = stage_pptx_reference(root, "FIG-01", reference)
            self.assertFalse(second["created"])
            self.assertTrue(second["existing_copy_preserved"])
            self.assertEqual(target.read_bytes(), b"edited")


if __name__ == "__main__":
    unittest.main()
