from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from qa.validate_contracts import _validate_document  # noqa: E402
from test_p0_harness import P0HarnessTest, read_json, write_json  # noqa: E402


def illustration_figure(**overrides):
    figure = {
        "figure_id": "FIG-ILL",
        "kind": "illustration",
        "claim_ids": ["C1"],
        "evidence_ids": ["E-R-Q1-01"],
        "purpose": "explain the occlusion mechanism",
        "why_figure": "spatial schematic is clearer than prose",
        "message": "the cloud blocks every sightline",
        "comparison": "not_applicable: illustration",
        "visual_encoding": "schematic shapes",
        "selection_rule": "no data selection",
        "data_artifacts": ["figures/occlusion_schematic.png", "reports/prompts/occlusion.txt"],
        "panel_map": {"A": "mechanism schematic"},
        "statistical_definition": "not_applicable: illustration",
        "paper_location": "model.q1",
        "caption_claim": "遮蔽机理概念示意：非按坐标精确绘制，不承载量化结论。",
        "accessibility": {"grayscale_safe": True, "colorblind_safe": True, "dual_axis": False, "dual_axis_justification": None},
        "qa_status": "pending",
        "illustration": {
            "generator": "nano-banana",
            "prompt_path": "reports/prompts/occlusion.txt",
            "raster_dpi": 320,
            "text_policy": "raster_text",
            "review_status": "reviewed",
        },
    }
    figure.update(overrides)
    return figure


class AIIllustrationTest(unittest.TestCase):
    def _prepare(self, project: Path, figures):
        harness = P0HarnessTest()
        harness.maxDiff = None
        paths = harness.build_fixture(project)
        plan = read_json(paths["plan"])
        plan["figures"] = figures
        (project / "figures").mkdir(exist_ok=True)
        (project / "figures" / "occlusion_schematic.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (project / "reports").mkdir(exist_ok=True)
        (project / "reports" / "prompts").mkdir(parents=True, exist_ok=True)
        (project / "reports" / "prompts" / "occlusion.txt").write_text("prompt text\n", encoding="utf-8")
        write_json(paths["plan"], plan)
        tex = paths["tex"].read_text(encoding="utf-8")
        tex += "\n% figure references\n" + " ".join(f.get("figure_id", "") for f in figures) + "\n"
        for figure in figures:
            for artifact in figure.get("data_artifacts", []):
                if isinstance(artifact, str):
                    tex += f"\\includegraphics{{{artifact}}}\n"
        paths["tex"].write_text(tex, encoding="utf-8")
        return harness, paths

    def _run(self, harness, paths, project: Path):
        return harness.run_script(
            "qa/check_consistency.py", "--project-root", str(project),
            "--paper-plan", paths["plan"].name, "--frozen-results", paths["frozen"].name,
            "--evidence-registry", paths["evidence"].name, "--abstract", paths["abstract"].name,
            "--paper", str(paths["tex"]), "--strict",
        )

    def test_schema_accepts_illustration_kind(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-illust-schema-") as temp:
            project = Path(temp)
            harness, paths = self._prepare(project, [illustration_figure()])
            _, schema_errors, _ = _validate_document(
                paths["plan"], ROOT / "schemas" / "paper_plan.schema.json"
            )
            self.assertEqual(schema_errors, [])

    def test_compliant_illustration_passes_and_low_dpi_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-illust-ok-") as temp:
            project = Path(temp)
            harness, paths = self._prepare(project, [illustration_figure()])
            result = self._run(harness, paths, project)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])

            low = illustration_figure()
            low["illustration"] = dict(low["illustration"], raster_dpi=220)
            plan = read_json(paths["plan"])
            plan["figures"] = [low]
            write_json(paths["plan"], plan)
            result = self._run(harness, paths, project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("raster_dpi must be >= 300", result.stdout)

    def test_missing_block_and_caption_disclaimer_fail(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-illust-missing-") as temp:
            project = Path(temp)
            no_block = illustration_figure()
            no_block.pop("illustration")
            harness, paths = self._prepare(project, [no_block])
            result = self._run(harness, paths, project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires an illustration block", result.stdout)

            plain_caption = illustration_figure(caption_claim="遮蔽机理图")
            plan = read_json(paths["plan"])
            plan["figures"] = [plain_caption]
            write_json(paths["plan"], plan)
            result = self._run(harness, paths, project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("caption must declare", result.stdout)

    def test_concept_figure_with_ai_bitmap_requires_backend_comparison(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-illust-concept-") as temp:
            project = Path(temp)
            concept = illustration_figure(kind="concept", semantic_type="model_structure")
            concept["illustration"] = dict(
                concept["illustration"],
                generator="nano-banana",
            )
            harness, paths = self._prepare(project, [concept])
            result = self._run(harness, paths, project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must keep its editable diagram block", result.stdout)
            self.assertIn("requires backend_comparison", result.stdout)

            concept["diagram"] = {
                "spec_path": "figures/framework_diagram_spec.json",
                "source_format": "drawio",
                "source_editability": "editable_source",
                "text_policy": "raster_text",
                "rendered_paths": ["figures/framework_final.png"],
                "status": "reviewed",
                "human_review_required": True,
            }
            concept["illustration"]["backend_comparison"] = {
                "alternatives": ["drawio vector render", "nano-banana bitmap"],
                "selection_reason": "AI bitmap is more readable at final size; editable drawio source retained for audit",
            }
            plan = read_json(paths["plan"])
            plan["figures"] = [concept]
            write_json(paths["plan"], plan)
            _, schema_errors, _ = _validate_document(
                paths["plan"], ROOT / "schemas" / "paper_plan.schema.json"
            )
            self.assertEqual(schema_errors, [])
            result = self._run(harness, paths, project)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])


if __name__ == "__main__":
    unittest.main()
