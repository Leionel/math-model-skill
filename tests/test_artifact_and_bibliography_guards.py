from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_p0_harness as p0  # noqa: E402


class ArtifactAndBibliographyGuardsTest(unittest.TestCase):
    def run_script(self, root: Path, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

    def test_canonical_source_must_be_current_and_produce_the_listed_artifact(self) -> None:
        with tempfile.TemporaryDirectory(prefix="canonical-source-") as temp:
            project = Path(temp)
            paths = p0.P0HarnessTest().build_fixture(project)
            plan = p0.read_json(paths["plan"])
            plan["figures"] = [{
                "figure_id": "FIG-1", "kind": "data", "semantic_type": "result_comparison", "claim_ids": ["C1"], "evidence_ids": ["E-R-Q1-01"],
                "purpose": "show result", "why_figure": "comparison", "message": "result", "comparison": "solver versus baseline", "visual_encoding": "bar", "selection_rule": "all",
                "data_artifacts": ["raw_results.json"], "canonical_source_id": "NODE-RAW", "panel_map": {"A": "result"}, "statistical_definition": "frozen result",
                "paper_location": "results", "caption_claim": "result", "accessibility": {"grayscale_safe": True, "colorblind_safe": True, "dual_axis": False, "dual_axis_justification": None}, "qa_status": "pending",
            }]
            p0.write_json(paths["plan"], plan)
            dag = project / "artifact_dag.json"
            p0.write_json(dag, {"schema_version": "1.0", "run_id": "demo-run", "nodes": [{"node_id": "NODE-RAW", "kind": "validation", "inputs": [], "outputs": [{"path": "raw_results.json", "sha256": p0.sha256(paths["raw"])}], "command": ["python", "model.py"], "receipt": {"path": "build.log", "sha256": p0.sha256(paths["build_log"])}, "upstream_digest": "0" * 64, "status": "current"}]})
            result = self.run_script(
                project, "qa/check_consistency.py", "--project-root", str(project), "--paper-plan", paths["plan"].name,
                "--frozen-results", paths["frozen"].name, "--evidence-registry", paths["evidence"].name,
                "--abstract", paths["abstract"].name, "--artifact-dag", dag.name, "--require-canonical-source", "--strict",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            plan["figures"][0]["canonical_source_id"] = "NODE-MISSING"
            p0.write_json(paths["plan"], plan)
            result = self.run_script(
                project, "qa/check_consistency.py", "--project-root", str(project), "--paper-plan", paths["plan"].name,
                "--frozen-results", paths["frozen"].name, "--evidence-registry", paths["evidence"].name,
                "--abstract", paths["abstract"].name, "--artifact-dag", dag.name, "--require-canonical-source", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("absent from artifact DAG", result.stdout)

    def test_verified_bibliography_bridge_rejects_placeholder_entry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="verified-bib-") as temp:
            project = Path(temp)
            paths = p0.P0HarnessTest().build_fixture(project)
            tex = project / "main.tex"
            bib = project / "refs.bib"
            tex.write_text("\\documentclass{article}\\begin{document}\\cite{fixture2026}\\end{document}\n", encoding="utf-8")
            bib.write_text("@article{fixture2026, author={A. Author}, title={A real fixture study}, year={2026}}\n", encoding="utf-8")
            result = self.run_script(
                project, "qa/check_citations.py", "--project-root", str(project), "--tex", tex.name, "--bib", bib.name,
                "--evidence-registry", paths["evidence"].name, "--require-verified-bibliography",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            bib.write_text("@article{fixture2026, author={赵某某}, title={placeholder}, year={2026}}\n", encoding="utf-8")
            result = self.run_script(
                project, "qa/check_citations.py", "--project-root", str(project), "--tex", tex.name, "--bib", bib.name,
                "--evidence-registry", paths["evidence"].name, "--require-verified-bibliography",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("placeholder", result.stdout)


if __name__ == "__main__":
    unittest.main()
