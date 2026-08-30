"""Precedent quarantine subsystem: register, check, and select reference cards."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from precedents.register_paper import register_paper  # noqa: E402
from precedents.check_precedent_index import check_index  # noqa: E402
from precedents.select_reference_cards import select_cards  # noqa: E402

PDF_BYTES = b"%PDF-1.4 fake but registered as a quarantined paper\n"


def _write_paper(root: Path, name: str = "A100.pdf") -> Path:
    path = root / "references" / "precedents" / "local-sources" / "papers" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(PDF_BYTES)
    return path


def _index_path(root: Path, competition: str = "CUMCM") -> Path:
    path = root / "references" / "precedents" / ("cumcm" if competition == "CUMCM" else "mcm-icm") / "index.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": "1.1", "competition": competition, "papers": []}), encoding="utf-8")
    return path


class RegisterPaperTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="precedent-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_registers_paper_with_hash_and_provenance(self) -> None:
        paper = _write_paper(self.root)
        index = _index_path(self.root)
        result = register_paper(
            self.root,
            index_path=str(index),
            paper_path=str(paper),
            source_url="https://example.org/paper",
            rights_status="authorized_public_download",
            problem="A",
            year=2023,
            problem_family="optimization",
            extraction_status="extracted",
            official_or_authorized=True,
        )
        self.assertTrue(result["ok"])
        rows = json.loads(index.read_text(encoding="utf-8"))["papers"]
        self.assertEqual(rows[0]["paper_id"], "A100")
        self.assertEqual(rows[0]["problem"], "A")
        self.assertEqual(rows[0]["competition"], "CUMCM")
        self.assertEqual(rows[0]["sha256"], result["sha256"])

    def test_rejects_duplicate_sha256(self) -> None:
        paper = _write_paper(self.root)
        index = _index_path(self.root)
        register_paper(self.root, index_path=str(index), paper_path=str(paper), source_url="https://x", rights_status="local_study_only", problem="A")
        with self.assertRaises(ValueError):
            register_paper(self.root, index_path=str(index), paper_path=str(paper), source_url="https://x", rights_status="local_study_only", problem="A", paper_id="OTHER")

    def test_rejects_papers_outside_quarantine(self) -> None:
        outside = self.root / "downloads" / "A100.pdf"
        outside.parent.mkdir(parents=True, exist_ok=True)
        outside.write_bytes(PDF_BYTES)
        index = _index_path(self.root)
        with self.assertRaises(ValueError):
            register_paper(self.root, index_path=str(index), paper_path=str(outside), source_url="https://x", rights_status="local_study_only", problem="A")

    def test_rejects_non_pdf_files(self) -> None:
        paper = _write_paper(self.root, "A100.docx")
        index = _index_path(self.root)
        with self.assertRaises(ValueError):
            register_paper(self.root, index_path=str(index), paper_path=str(paper), source_url="https://x", rights_status="local_study_only", problem="A")

    def test_authorized_status_requires_explicit_authorization(self) -> None:
        paper = _write_paper(self.root)
        index = _index_path(self.root)
        with self.assertRaises(ValueError):
            register_paper(
                self.root,
                index_path=str(index),
                paper_path=str(paper),
                source_url="https://x",
                rights_status="authorized_public_download",
                problem="A",
            )


class CheckIndexTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="precedent-check-")
        self.root = Path(self.temp.name)
        self.paper = _write_paper(self.root)
        self.index = _index_path(self.root)
        register_paper(self.root, index_path=str(self.index), paper_path=str(self.paper), source_url="https://x", rights_status="local_study_only", problem="A")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_valid_index_passes_strict(self) -> None:
        errors, warnings, count = check_index(self.index, self.root)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(count, 1)

    def test_path_escape_is_an_error(self) -> None:
        rows = json.loads(self.index.read_text(encoding="utf-8"))
        rows["papers"][0]["local_path"] = "downloads/A100.pdf"
        self.index.write_text(json.dumps(rows), encoding="utf-8")
        errors, _, _ = check_index(self.index, self.root)
        self.assertTrue(any("local_path" in message for message in errors))

    def test_hash_drift_is_an_error(self) -> None:
        self.paper.write_bytes(PDF_BYTES + b"tampered")
        errors, _, _ = check_index(self.index, self.root)
        self.assertTrue(any("sha256 drift" in message for message in errors))

    def test_missing_file_is_a_warning_not_an_error(self) -> None:
        self.paper.unlink()
        errors, warnings, _ = check_index(self.index, self.root)
        self.assertEqual(errors, [])
        self.assertTrue(any("local file is absent" in message for message in warnings))

    def test_unknown_rights_status_is_an_error(self) -> None:
        rows = json.loads(self.index.read_text(encoding="utf-8"))
        rows["papers"][0]["rights_status"] = "unknown"
        rows["papers"][0]["official_or_authorized"] = False
        self.index.write_text(json.dumps(rows), encoding="utf-8")
        errors, _, _ = check_index(self.index, self.root)
        self.assertTrue(any("rights_status=unknown" in message for message in errors))

    def test_duplicate_source_is_an_error(self) -> None:
        _write_paper(self.root, "A200.pdf")
        rows = json.loads(self.index.read_text(encoding="utf-8"))
        rows["papers"].append({**rows["papers"][0], "paper_id": "A200", "local_path": "references/precedents/local-sources/papers/A200.pdf"})
        # simulate a duplicate sha256 registration by pointing A200 at the same digest
        rows["papers"][1]["sha256"] = rows["papers"][0]["sha256"]
        self.index.write_text(json.dumps(rows), encoding="utf-8")
        errors, _, _ = check_index(self.index, self.root)
        self.assertTrue(any("duplicates sha256" in message for message in errors))


class SelectCardsTest(unittest.TestCase):
    def test_all_figure_cards_declare_route_semantic_type(self) -> None:
        result = select_cards(card_kind="figure", limit=100)
        self.assertEqual(len(result["selected"]), result["available"])
        for card in result["selected"]:
            self.assertTrue(card["semantic_type"], card["path"])

    def test_selects_pattern_cards_by_problem_family(self) -> None:
        result = select_cards(problem_family="优化", limit=3)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(len(result["selected"]), 1)
        for card in result["selected"]:
            self.assertTrue(card["card_id"].startswith("PC-"))
            self.assertTrue(card["path"].endswith(".md"))

    def test_selects_figure_cards_by_evidence_role(self) -> None:
        result = select_cards(card_kind="figure", evidence_role="result comparison", limit=3)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(len(result["selected"]), 1)
        for card in result["selected"]:
            self.assertTrue(card["card_id"].startswith("FC-"))

    def test_selects_figure_cards_by_data_shape(self) -> None:
        result = select_cards(card_kind="figure", data_shape="continuous_relationship", limit=10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["filters"]["data_shape"], "continuous_relationship")
        self.assertGreaterEqual(len(result["selected"]), 1)
        for card in result["selected"]:
            self.assertTrue(card["card_id"].startswith("FC-"))
            self.assertIn("continuous_relationship", card["data_shape"])
            self.assertTrue(card["chart_family"])

    def test_selects_figure_cards_by_route_semantic_type(self) -> None:
        result = select_cards(card_kind="figure", semantic_type="sensitivity_curve", limit=10)
        self.assertTrue(result["ok"])
        self.assertEqual(result["filters"]["semantic_type"], "sensitivity_curve")
        self.assertEqual([row["card_id"] for row in result["selected"]], ["FC-SENS-01"])
        self.assertIn("sensitivity curve", result["selected"][0]["semantic_type"])

    def test_competition_filter_uses_registered_source_ids(self) -> None:
        result = select_cards(competition="MCM-ICM", card_kind="figure", limit=10)
        self.assertTrue(result["ok"])
        self.assertGreaterEqual(len(result["selected"]), 1)
        for card in result["selected"]:
            self.assertIn(card["source_ids"], {"2400996", "2424371"})
            self.assertFalse(Path(card["path"]).is_absolute())

    def test_never_returns_local_paper_paths(self) -> None:
        for card_kind in ("pattern", "figure"):
            result = select_cards(card_kind=card_kind, limit=5)
            for card in result["selected"]:
                self.assertNotIn("local-sources", card["path"])

    def test_competition_filter_surfaces_index_last_reviewed(self) -> None:
        result = select_cards(competition="CUMCM", limit=1)
        self.assertEqual(result["competition_index_last_reviewed"], "2026-08-28")
        self.assertIsNone(select_cards(limit=1)["competition_index_last_reviewed"])

    def test_committed_indexes_pass_check_with_last_reviewed(self) -> None:
        for folder in ("cumcm", "mcm-icm"):
            index = ROOT / "references" / "precedents" / folder / "index.json"
            errors, _, count = check_index(index, ROOT)
            self.assertEqual(errors, [])
            self.assertGreaterEqual(count, 1)


class PrecedentsCliTest(unittest.TestCase):
    def _run(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "harness.py"), "precedents", "select", *extra],
            text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
        )

    def test_select_json_reports_cards_and_freshness(self) -> None:
        result = self._run("--competition", "CUMCM", "--limit", "2", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertGreaterEqual(len(payload["selected"]), 1)
        self.assertEqual(payload["competition_index_last_reviewed"], "2026-08-28")
        self.assertIn("quarantined", payload["note"])

    def test_select_human_output_keeps_quarantine_note(self) -> None:
        result = self._run("--competition", "MCM-ICM", "--card-kind", "figure", "--limit", "1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("last reviewed", result.stdout)
        self.assertIn("full papers stay quarantined", result.stdout)
        self.assertNotIn("local-sources", result.stdout)

    def test_select_figure_cards_by_data_shape_via_cli(self) -> None:
        result = self._run("--card-kind", "figure", "--data-shape", "continuous_relationship", "--limit", "5", "--json")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["filters"]["data_shape"], "continuous_relationship")
        self.assertGreaterEqual(len(payload["selected"]), 1)
        for card in payload["selected"]:
            self.assertIn("continuous_relationship", card["data_shape"])

    def test_select_figure_cards_by_semantic_type_via_cli(self) -> None:
        result = self._run(
            "--card-kind", "figure", "--semantic-type", "workflow", "--limit", "5", "--json"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual([row["card_id"] for row in payload["selected"]], ["FC-MECH-01"])


if __name__ == "__main__":
    unittest.main()
