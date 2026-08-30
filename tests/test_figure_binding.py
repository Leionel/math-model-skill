"""R7 GAP-05/GAP-13 closures: every includegraphics binds to a DAG-registered
digest, and caption numeric claims must be registered in frozen/derived results."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_p0_harness as p0  # noqa: E402


PNG_BYTES = b"\x89PNG\r\n\x1a\nfixture-render-bytes\n"
SUBSTITUTED_BYTES = b"\x89PNG\r\n\x1a\nswapped-bitmap-bytes\n"


class FigureBindingHarness(unittest.TestCase):
    def _prepare(self, project: Path, *, caption: str, digest: str | None, omit_digest: bool = False):
        harness = p0.P0HarnessTest()
        harness.maxDiff = None
        paths = harness.build_fixture(project)
        plan = p0.read_json(paths["plan"])
        plan["figures"] = [{
            "figure_id": "FIG-01", "kind": "data", "semantic_type": "result_comparison",
            "claim_ids": ["C1"], "evidence_ids": ["E-R-Q1-01"],
            "purpose": "show result", "why_figure": "comparison", "message": "result",
            "comparison": "solver versus baseline", "visual_encoding": "bar", "selection_rule": "all",
            "data_artifacts": ["figures/result_plot.png"],
            "panel_map": {"A": "result"}, "statistical_definition": "frozen result",
            "paper_location": "results", "caption_claim": caption,
            "accessibility": {"grayscale_safe": True, "colorblind_safe": True, "dual_axis": False, "dual_axis_justification": None},
            "qa_status": "pending",
        }]
        p0.write_json(paths["plan"], plan)
        (project / "figures").mkdir(exist_ok=True)
        (project / "figures" / "result_plot.png").write_bytes(PNG_BYTES)
        render_dir = paths["tex"].parent / "figures"
        render_dir.mkdir(parents=True, exist_ok=True)
        (render_dir / "result_plot.png").write_bytes(PNG_BYTES)
        tex = paths["tex"].read_text(encoding="utf-8").replace(
            "\\end{document}",
            "See FIG-01.\n\\includegraphics{figures/result_plot.png}\n\\end{document}",
        )
        paths["tex"].write_text(tex, encoding="utf-8")
        node = {"node_id": "NODE-FIG", "path": "figures/result_plot.png"}
        if not omit_digest:
            node["sha256"] = digest if digest is not None else p0.sha256(render_dir / "result_plot.png")
        dag = project / "artifact_dag.json"
        p0.write_json(dag, {"schema_version": "1.0", "run_id": "demo-run", "nodes": [node]})
        return harness, paths, dag

    def _run(self, harness, paths, project: Path, dag: Path, *extra: str):
        return harness.run_script(
            "qa/check_consistency.py", "--project-root", str(project),
            "--paper-plan", paths["plan"].name, "--frozen-results", paths["frozen"].name,
            "--evidence-registry", paths["evidence"].name, "--abstract", paths["abstract"].name,
            "--paper", str(paths["tex"]), "--artifact-dag", dag.name, *extra,
        )


class GapDigestBindingTest(FigureBindingHarness):
    def test_matching_digest_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gap05-ok-") as temp:
            project = Path(temp)
            harness, paths, dag = self._prepare(project, caption="solver versus baseline comparison", digest=None)
            result = self._run(harness, paths, project, dag, "--strict")
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])

    def test_substituted_bitmap_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gap05-drift-") as temp:
            project = Path(temp)
            harness, paths, dag = self._prepare(project, caption="solver versus baseline comparison", digest=None)
            (paths["tex"].parent / "figures" / "result_plot.png").write_bytes(SUBSTITUTED_BYTES)
            result = self._run(harness, paths, project, dag, "--strict")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match the registered digest", result.stdout)

    def test_same_include_text_in_two_tex_directories_checks_both_files(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gap05-multi-source-") as temp:
            project = Path(temp)
            harness, paths, dag = self._prepare(project, caption="solver versus baseline comparison", digest=None)
            section_dir = paths["tex"].parent / "section"
            (section_dir / "figures").mkdir(parents=True)
            (section_dir / "figures" / "result_plot.png").write_bytes(SUBSTITUTED_BYTES)
            (section_dir / "extra.tex").write_text(
                "\\includegraphics{figures/result_plot.png}\n",
                encoding="utf-8",
            )
            tex = paths["tex"].read_text(encoding="utf-8").replace(
                "\\end{document}",
                "\\input{section/extra}\n\\end{document}",
            )
            paths["tex"].write_text(tex, encoding="utf-8")
            result = self._run(harness, paths, project, dag, "--strict")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match the registered digest", result.stdout)

    def test_registered_without_digest_warns_and_strict_blocks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gap05-nodigest-") as temp:
            project = Path(temp)
            harness, paths, dag = self._prepare(project, caption="solver versus baseline comparison", digest=None, omit_digest=True)
            result = self._run(harness, paths, project, dag)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])
            self.assertIn("no digest", result.stdout)
            result = self._run(harness, paths, project, dag, "--strict")
            self.assertNotEqual(result.returncode, 0)


class GapCaptionNumberTest(FigureBindingHarness):
    def test_caption_number_missing_from_body_blocks_under_strict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gap13-missing-") as temp:
            project = Path(temp)
            harness, paths, dag = self._prepare(project, caption="reduces the cost to 98.76 CNY", digest=None)
            result = self._run(harness, paths, project, dag)
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])
            self.assertIn("caption claims 98.76", result.stdout)
            result = self._run(harness, paths, project, dag, "--strict")
            self.assertNotEqual(result.returncode, 0)

    def test_caption_number_backed_by_frozen_result_passes_strict(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gap13-ok-") as temp:
            project = Path(temp)
            harness, paths, dag = self._prepare(project, caption="the optimal cost is 123.45 CNY", digest=None)
            result = self._run(harness, paths, project, dag, "--strict")
            self.assertEqual(result.returncode, 0, result.stdout[-2000:])

    def test_body_repetition_does_not_legitimize_unregistered_caption_number(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gap13-body-only-") as temp:
            project = Path(temp)
            harness, paths, dag = self._prepare(project, caption="the cost is 98.76 CNY", digest=None)
            tex = paths["tex"].read_text(encoding="utf-8").replace("See FIG-01.", "See FIG-01. The cost is 98.76 CNY.")
            paths["tex"].write_text(tex, encoding="utf-8")
            result = self._run(harness, paths, project, dag, "--strict")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("body-text repetition alone is not evidence", result.stdout)

    def test_integer_caption_value_is_checked(self) -> None:
        with tempfile.TemporaryDirectory(prefix="gap13-integer-") as temp:
            project = Path(temp)
            harness, paths, dag = self._prepare(project, caption="the selected count is 9876", digest=None)
            result = self._run(harness, paths, project, dag, "--strict")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("caption claims 9876", result.stdout)


if __name__ == "__main__":
    unittest.main()
