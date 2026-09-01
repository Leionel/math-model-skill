from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TEST_PYTHON = Path(sys.executable)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_ref(path: Path) -> dict[str, str]:
    return {"path": path.name, "sha256": sha256(path)}


def canonical_sha256(value: object) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class EditorialIntegrityTest(unittest.TestCase):
    def run_script(self, script: str, *args: str, python: Path | None = None) -> subprocess.CompletedProcess[str]:
        child_environment = os.environ.copy()
        if python is not None:
            # The plotting smoke test deliberately selects a separate Python
            # runtime.  Do not leak a parent test runner's PYTHONPATH into a
            # different ABI (for example cp312 wheels into Anaconda cp313).
            child_environment.pop("PYTHONPATH", None)
        child_environment["PYTHONUTF8"] = "1"
        return subprocess.run(
            [str(python or Path(sys.executable)), str(ROOT / "scripts" / script), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=child_environment,
            check=False,
        )

    def test_problem_coverage_rejects_missing_requirement(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-problem-") as temp:
            project = Path(temp)
            problem = project / "problem.txt"
            problem.write_text("Q1 and Q2", encoding="utf-8")
            write_json(project / "problem_snapshot.json", {
                "schema_version": "1.0", "project_id": "p", "competition_profile_id": "demo",
                "captured_at": "2026-08-13T00:00:00Z",
                "problem_files": [{**file_ref(problem), "source": "official"}], "attachment_files": [],
                "selection": {
                    "selected_problem_id": "C", "candidates": [{
                        "problem_id": "C", "fit": "matched", "data_risk": "low", "validation_risk": "medium",
                        "delivery_risk": "low", "decision": "selected", "reason": "best evidence fit",
                    }], "confirmed_by_role": "team", "confirmed_at": "2026-08-13T00:00:00Z",
                },
                "requirements": [
                    {"requirement_id": "RQ1", "question_id": "q1", "source_locator": "p1", "official_text": "Q1", "mathematical_task": "solve q1", "required_outputs": ["y1"], "required_metrics": [], "special_constraints": [], "delivery_items": [], "status": "answered"},
                    {"requirement_id": "RQ2", "question_id": "q2", "source_locator": "p1", "official_text": "Q2", "mathematical_task": "solve q2", "required_outputs": ["y2"], "required_metrics": [], "special_constraints": [], "delivery_items": [], "status": "answered"},
                ], "status": "confirmed",
            })
            write_json(project / "model.json", {"questions": [
                {"question_id": "q1", "outputs": ["y1"]}, {"question_id": "q2", "outputs": ["y2"]},
            ]})
            write_json(project / "plan.json", {"requirements": [{"requirement_id": "RQ1", "claim_ids": ["C1"]}], "claims": [{"claim_id": "C1"}], "status": "ready"})
            result = self.run_script(
                "qa/check_problem_coverage.py", "--project-root", str(project),
                "--problem-snapshot", "problem_snapshot.json", "--model-contract", "model.json",
                "--paper-plan", "plan.json", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("do not exactly cover", result.stdout)

    def test_data_contract_rejects_leakage_failure(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-data-") as temp:
            project = Path(temp)
            data = project / "data.csv"
            data.write_text("id,target\n1,2\n", encoding="utf-8")
            contract = {
                "schema_version": "1.0", "run_id": "r", "data_id": "d", "source": file_ref(data), "layer": "raw",
                "table": {"format": "csv", "row_count": 1, "column_count": 2, "primary_key": ["id"], "duplicate_key_count": 0, "encoding": "utf-8", "timezone": None},
                "columns": [
                    {"name": "id", "dtype": "integer", "semantic_type": "identifier", "unit": None, "nullable": False, "missing_count": 0, "unique": True, "role": "identifier", "allowed": {"minimum": 1}},
                    {"name": "target", "dtype": "number", "semantic_type": "target", "unit": "unit", "nullable": False, "missing_count": 0, "unique": False, "role": "target", "allowed": {}},
                ],
                "invariants": [{"invariant_id": "I1", "description": "positive id", "check": "id>0", "status": "pass", "observed": True}],
                "leakage_policy": {"target_columns": ["target"], "split_keys": ["id"], "time_boundary": None, "forbidden_features": ["target"], "status": "fail"},
                "profile": {"row_count": 1, "missing_cells": 0, "duplicate_rows": 0, "time_min": None, "time_max": None},
                "status": "validated",
            }
            write_json(project / "data_contract.json", contract)
            write_json(project / "model.json", {"data_sources": [{"data_id": "d", **file_ref(data)}]})
            result = self.run_script(
                "qa/check_data_contract.py", "--project-root", str(project),
                "--data-contract", "data_contract.json", "--model-contract", "model.json",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not promotable", result.stdout)

    def test_implementation_map_rejects_code_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-map-") as temp:
            project = Path(temp)
            code = project / "model.py"
            test_file = project / "test_model.py"
            model = project / "model.json"
            code.write_text("def objective(x): return x\n", encoding="utf-8")
            test_file.write_text("# passed test receipt fixture\n", encoding="utf-8")
            write_json(model, {"run_id": "r", "questions": [{"question_id": "q1"}], "models": [{"model_id": "M1"}]})
            mapping = {
                "schema_version": "1.0", "run_id": "r", "model_contract": file_ref(model),
                "symbols": [{"symbol_id": "S-X", "latex": "x", "meaning": "decision", "unit": "item", "scope": "q1", "model_id": "M1"}],
                "equations": [{
                    "equation_id": "EQ1", "model_id": "M1", "question_id": "q1", "kind": "objective", "latex": "f(x)=x",
                    "symbol_ids": ["S-X"], "contract_item_ids": ["objective"],
                    "code_refs": [{"path": code.name, "sha256": "0" * 64, "symbol": "objective"}],
                    "tests": [{"test_id": "T1", **file_ref(test_file), "purpose": "unit", "status": "pass"}], "status": "verified",
                }], "status": "verified",
            }
            write_json(project / "map.json", mapping)
            result = self.run_script(
                "qa/check_implementation_map.py", "--project-root", str(project),
                "--implementation-map", "map.json", "--model-contract", "model.json",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hash drift", result.stdout)

    def test_claim_inventory_rejects_unregistered_claim(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-claims-") as temp:
            project = Path(temp)
            write_json(project / "plan.json", {
                "run_id": "r", "claims": [{"claim_id": "C1", "claim_type": "observation", "text": "cost is observed", "evidence_ids": ["E1"]}],
            })
            write_json(project / "frozen.json", {"results": [{"result_id": "R1", "display_value": "12.30"}]})
            (project / "draft.tex").write_text("% claim:C1\nThe cost is 12.30. It therefore improves by 99.\n", encoding="utf-8")
            result = self.run_script(
                "claims/inventory_claims.py", "--project-root", str(project), "--paper-plan", "plan.json",
                "--frozen-results", "frozen.json", "--draft", "draft.tex", "--output", "inventory.json", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            report = read_json(project / "inventory.json")
            categories = {row["category"] for row in report["findings"]}
            self.assertIn("unregistered_number", categories)
            self.assertIn("causal", categories)

    def test_pareto_checker_rejects_dominated_label(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-pareto-") as temp:
            project = Path(temp)
            write_json(project / "pareto.json", {
                "run_id": "r",
                "metrics": [{"metric_id": "cost", "direction": "minimize"}, {"metric_id": "carbon", "direction": "minimize"}],
                "candidates": [
                    {"candidate_id": "A", "values": {"cost": 1, "carbon": 1}, "claimed_nondominated": True},
                    {"candidate_id": "B", "values": {"cost": 2, "carbon": 2}, "claimed_nondominated": True},
                ],
            })
            result = self.run_script(
                "validation/check_pareto.py", "--project-root", str(project),
                "--input", "pareto.json", "--output", "pareto_report.json",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("claimed_nondominated", read_json(project / "pareto_report.json")["errors"][0])

    def test_artifact_dag_rejects_upstream_hash_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-dag-") as temp:
            project = Path(temp)
            source = project / "source.json"
            output = project / "output.json"
            receipt = project / "receipt.json"
            source.write_text('{"value": 1}\n', encoding="utf-8")
            output.write_text('{"result": 2}\n', encoding="utf-8")
            receipt.write_text('{"ok": true}\n', encoding="utf-8")
            input_ref = file_ref(source)
            write_json(project / "dag.json", {
                "schema_version": "1.0", "run_id": "r",
                "nodes": [{
                    "node_id": "N1", "kind": "model", "inputs": [input_ref],
                    "outputs": [file_ref(output)], "command": ["python", "model.py"],
                    "receipt": file_ref(receipt),
                    "upstream_digest": canonical_sha256([input_ref]), "status": "current",
                }],
            })
            source.write_text('{"value": 9}\n', encoding="utf-8")
            result = self.run_script(
                "qa/check_artifact_dag.py", "--project-root", str(project),
                "--dag", "dag.json", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hash drift", result.stdout)

    def test_generate_values_tex_uses_frozen_display(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-values-") as temp:
            project = Path(temp)
            frozen = project / "frozen.json"
            write_json(frozen, {"run_id": "r", "claimable": True, "results": [{"result_id": "R1", "value": 12.345, "precision": 2, "display_value": "12.35"}]})
            write_json(project / "presentation.json", {
                "schema_version": "1.0", "run_id": "r", "frozen_results": file_ref(frozen),
                "entries": [{"presentation_id": "P1", "result_id": "R1", "macro": "BestCost", "format": "number", "unit_display": "~CNY", "rounding": "frozen_display_value", "locations": ["abstract"]}],
                "status": "ready",
            })
            result = self.run_script(
                "latex/generate_values_tex.py", "--project-root", str(project), "--presentation-contract", "presentation.json",
                "--frozen-results", "frozen.json", "--output", "results.tex", "--provenance", "provenance.json",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn(r"\newcommand{\BestCost}{12.35~CNY}", (project / "results.tex").read_text(encoding="utf-8"))

    def test_safe_build_blocks_shell_escape(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-tex-unsafe-") as temp:
            project = Path(temp)
            paper = project / "paper"
            paper.mkdir()
            (paper / "main.tex").write_text(r"\documentclass{article}\begin{document}\immediate\write18{bad}\end{document}", encoding="utf-8")
            result = self.run_script(
                "latex/safe_build.py", "--project-root", str(project), "--source-root", "paper",
                "--entrypoint", "main.tex", "--output", "out.pdf", "--receipt", "build.json",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("blocked LaTeX token", result.stdout)

    def test_template_usage_rejects_declared_template_that_is_not_used(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-template-usage-") as temp:
            project = Path(temp)
            paper = project / "paper"
            paper.mkdir()
            (paper / "main.tex").write_text(
                r"\documentclass{ctexart}\begin{document}x\end{document}", encoding="utf-8"
            )
            (paper / "cumcmthesis.cls").write_text("% fixture class\n", encoding="utf-8")
            write_json(project / "template.json", {
                "schema_version": "1.0", "template_id": "cumcm-fixture", "competition_profile_id": "fixture",
                "source_kind": "local", "source_locator": "fixture", "status": "verified",
                "document_class": "cumcmthesis", "entrypoint": "main.tex",
                "required_files": ["main.tex", "cumcmthesis.cls"],
                "required_commands": ["\\begin{document}"],
                "forbidden_document_classes": ["ctexart"], "allowed_engines": ["xelatex"]
            })
            result = self.run_script(
                "qa/check_template_usage.py", "--project-root", str(project),
                "--template-contract", "template.json", "--source-root", "paper",
                "--entrypoint", "main.tex", "--integrity-mode", "research",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("template contract requires 'cumcmthesis'", result.stdout)

    def test_cumcm_initializer_creates_a_real_template_bound_project(self) -> None:
        vendor = ROOT / "vendor" / "upstream" / "CUMCMThesis"
        if not (vendor / "cumcmthesis.cls").is_file():
            self.skipTest("pinned CUMCMThesis vendor snapshot is unavailable")
        with tempfile.TemporaryDirectory(prefix="math-cumcm-init-") as temp:
            project = Path(temp)
            initialized = self.run_script(
                "latex/init_cumcm_project.py", "--project-root", str(project),
                "--vendor-root", str(vendor), "--destination", "paper",
                "--title", "Fixture Paper", "--problem", "C",
                "--keywords", "optimization;validation", "--year", "2026",
                "--month", "9", "--day", "4",
            )
            self.assertEqual(initialized.returncode, 0, initialized.stdout + initialized.stderr)
            checked = self.run_script(
                "qa/check_template_usage.py", "--project-root", str(project),
                "--template-contract", "paper/template_contract.json", "--source-root", "paper",
                "--entrypoint", "main.tex", "--engine", "xelatex", "--integrity-mode", "research",
                "--strict",
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn(r"\documentclass[withoutpreface,bwprint]{cumcmthesis}", (project / "paper" / "main.tex").read_text(encoding="utf-8"))
            built = self.run_script(
                "latex/safe_build.py", "--project-root", str(project), "--source-root", "paper",
                "--entrypoint", "main.tex", "--template-contract", "paper/template_contract.json",
                "--integrity-mode", "research", "--engine", "xelatex",
                "--output", "solution.pdf", "--receipt", "build_receipt.json",
            )
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            receipt = read_json(project / "build_receipt.json")
            self.assertEqual(receipt["template"]["document_class"], "cumcmthesis")
            self.assertTrue(receipt["template"]["verified"])

    def test_research_build_requires_template_contract(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-template-required-") as temp:
            project = Path(temp)
            paper = project / "paper"
            paper.mkdir()
            (paper / "main.tex").write_text(
                r"\documentclass{article}\begin{document}x\end{document}", encoding="utf-8"
            )
            result = self.run_script(
                "latex/safe_build.py", "--project-root", str(project), "--source-root", "paper",
                "--entrypoint", "main.tex", "--output", "out.pdf", "--receipt", "build.json",
                "--integrity-mode", "research",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("requires --template-contract", result.stdout)

    def test_safe_build_blocks_parent_path_input(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-tex-path-") as temp:
            project = Path(temp)
            paper = project / "paper"
            paper.mkdir()
            (paper / "main.tex").write_text(r"\documentclass{article}\input{../secret}\begin{document}x\end{document}", encoding="utf-8")
            result = self.run_script(
                "latex/safe_build.py", "--project-root", str(project), "--source-root", "paper",
                "--entrypoint", "main.tex", "--output", "out.pdf", "--receipt", "build.json",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("escapes source root", result.stdout)

    def test_safe_build_and_pdf_visual_qa(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-pdf-") as temp:
            project = Path(temp)
            paper = project / "paper"
            paper.mkdir()
            (paper / "main.tex").write_text(
                "\\documentclass[a4paper,11pt]{article}\n\\usepackage[margin=2.5cm]{geometry}\n\\begin{document}\nVerified fixture.\n\\end{document}\n",
                encoding="utf-8",
            )
            build = self.run_script(
                "latex/safe_build.py", "--project-root", str(project), "--source-root", "paper",
                "--entrypoint", "main.tex", "--output", "solution.pdf", "--receipt", "build.json",
                "--integrity-mode", "dev",
            )
            self.assertEqual(build.returncode, 0, build.stdout + build.stderr)
            self.assertTrue(read_json(project / "build.json")["source_unchanged"])
            self.assertNotIn("sha256", read_json(project / "build.json")["output"])
            rule = project / "rule.txt"
            rule.write_text("fixture visual rule", encoding="utf-8")
            write_json(project / "visual_profile.json", {
                "schema_version": "1.0", "profile_id": "fixture", "competition_profile_id": "fixture",
                "sources": [{"kind": "local_policy", "title": "fixture", "url": "https://example.org/fixture", "retrieved_at": "2026-08-13", "snapshot": file_ref(rule)}],
                "page": {"width_mm": 210, "height_mm": 297, "size_tolerance_mm": 1, "min_margin_mm": 10, "max_body_pages": 5},
                "typography": {"min_body_font_pt": 9, "min_figure_font_pt": 7, "embedded_fonts_required": True, "cjk_render_review_required": False, "allowed_engines": ["xelatex"]},
                "figures": {"raster_min_dpi": 180, "grayscale_review_required": True, "colorblind_review_required": True, "dual_axis_default": "allow_with_justification"},
                "tables": {"allow_vertical_rules": False, "require_units_in_header_or_caption": True},
                "severity_policy": {"official_rule_violation": "error", "unreadable_or_clipped": "error", "font_embedding": "error", "low_resolution": "warning", "density_or_style": "warning"},
            })
            check = self.run_script(
                "pdf/check_pdf.py", "--project-root", str(project), "--pdf", "solution.pdf", "--profile", "visual_profile.json",
                "--source", "paper/main.tex", "--render-dir", "rendered", "--contact-sheet", "contact.jpg", "--output", "pdf_qa.json",
                python=TEST_PYTHON,
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            report = read_json(project / "pdf_qa.json")
            self.assertTrue(report["formal_ok"])
            self.assertEqual(report["render"]["pages_rendered"], 1)
            self.assertTrue((project / "contact.jpg").is_file())

    def test_plot_templates_render_core_chart_families(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-plots-") as temp:
            project = Path(temp)
            rows = [
                {"time": "t1", "value": 2, "low": 1.5, "high": 2.5, "group": "A", "category": "x", "parameter": "p1", "effect": -1, "cost": 3, "carbon": 4, "front": True, "label": "A", "xcat": "a", "ycat": "u", "heat": 0.2, "source": "n1", "target": "n2", "weight": 1},
                {"time": "t2", "value": 3, "low": 2.5, "high": 3.5, "group": "A", "category": "y", "parameter": "p2", "effect": 2, "cost": 4, "carbon": 3, "front": True, "label": "B", "xcat": "b", "ycat": "u", "heat": 0.7, "source": "n2", "target": "n3", "weight": 2},
            ]
            write_json(project / "rows.json", rows)
            cases = [
                ("line", ["--x", "time", "--y", "value", "--low", "low", "--high", "high", "--group", "group"]),
                ("comparison", ["--category", "category", "--y", "value"]),
                ("distribution", ["--x", "value", "--mode", "ecdf"]),
                ("scatter", ["--x", "cost", "--y", "carbon"]),
                ("sensitivity", ["--category", "parameter", "--y", "effect"]),
                ("pareto", ["--x", "cost", "--y", "carbon", "--pareto-flag", "front", "--label", "label"]),
                ("heatmap", ["--x", "xcat", "--y", "ycat", "--value", "heat", "--annotate"]),
                ("network", ["--source", "source", "--target", "target", "--weight", "weight"]),
            ]
            for template, extra in cases:
                with self.subTest(template=template):
                    result = self.run_script(
                        "figures/plot_templates.py", "--project-root", str(project), "--template", template,
                        "--input", "rows.json", "--output", f"{template}.pdf", "--receipt", f"{template}.json",
                        "--style", str(ROOT / "assets" / "styles" / "mathmodel.mplstyle"), *extra,
                        python=TEST_PYTHON,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertTrue((project / f"{template}.pdf").is_file())
                    self.assertEqual(read_json(project / f"{template}.json")["template"], template)

            first_line_hash = sha256(project / "line.pdf")
            (project / "line.pdf").unlink()
            (project / "line.json").unlink()
            repeated = self.run_script(
                "figures/plot_templates.py", "--project-root", str(project), "--template", "line",
                "--input", "rows.json", "--output", "line.pdf", "--receipt", "line.json",
                "--style", str(ROOT / "assets" / "styles" / "mathmodel.mplstyle"),
                "--x", "time", "--y", "value", "--low", "low", "--high", "high", "--group", "group",
                python=TEST_PYTHON,
            )
            self.assertEqual(repeated.returncode, 0, repeated.stdout + repeated.stderr)
            self.assertEqual(first_line_hash, sha256(project / "line.pdf"))


    def test_plot_templates_render_distribution_and_facet_recipes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-plots-distribution-") as temp:
            project = Path(temp)
            rows = []
            for series_index, series in enumerate(("North", "South")):
                for period in range(1, 7):
                    rows.append({
                        "period": period,
                        "value": 10 + series_index * 2 + period * 0.7 + (0.35 if period % 2 else -0.15),
                        "series": series,
                        "condition": "Baseline" if period % 2 else "Proposed",
                    })
            write_json(project / "distribution_rows.json", rows)
            cases = [
                (
                    "small_multiples",
                    [
                        "--x", "period", "--y", "value", "--group", "series",
                        "--facet-columns", "2", "--paper-placement", "full_width",
                    ],
                    False,
                ),
                (
                    "violin",
                    [
                        "--category", "condition", "--y", "value", "--show-points",
                        "--paper-placement", "single_column",
                    ],
                    True,
                ),
                (
                    "box",
                    [
                        "--category", "condition", "--y", "value", "--raw-points",
                        "--paper-placement", "single_column",
                    ],
                    True,
                ),
                (
                    "beeswarm",
                    [
                        "--category", "condition", "--y", "value",
                        "--paper-placement", "single_column",
                    ],
                    False,
                ),
                (
                    "strip",
                    [
                        "--category", "condition", "--y", "value", "--seed", "11",
                        "--paper-placement", "single_column",
                    ],
                    False,
                ),
            ]
            for template, extra, shows_points in cases:
                with self.subTest(template=template):
                    result = self.run_script(
                        "figures/plot_templates.py", "--project-root", str(project), "--template", template,
                        "--input", "distribution_rows.json", "--output", f"{template}.pdf",
                        "--receipt", f"{template}.json",
                        "--style", str(ROOT / "assets" / "styles" / "mathmodel.mplstyle"), *extra,
                        python=TEST_PYTHON,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    self.assertTrue((project / f"{template}.pdf").is_file())
                    receipt = read_json(project / f"{template}.json")
                    self.assertEqual(receipt["template"], template)
                    self.assertEqual(receipt["render"]["sizing_mode"], "placement")
                    self.assertEqual(receipt["arguments"]["show_points"], shows_points)

    def test_plot_templates_render_wp7_recipes_at_declared_paper_sizes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-plots-wp7-") as temp:
            project = Path(temp)
            rows = [
                {
                    "category": "A",
                    "baseline": 100,
                    "candidate": 92,
                    "fitted": 0.2,
                    "residual": -0.04,
                    "observed": 0.2,
                    "predicted": 0.22,
                    "estimate": 92,
                    "interval_low": 86,
                    "interval_high": 98,
                    "period": 1,
                    "value": 92,
                    "low": 86,
                    "high": 98,
                    "group": "central",
                    "cost": 4,
                    "carbon": 7,
                    "front": True,
                    "selected": False,
                    "label": "A",
                },
                {
                    "category": "B",
                    "baseline": 80,
                    "candidate": 86,
                    "fitted": 0.5,
                    "residual": 0.02,
                    "observed": 0.5,
                    "predicted": 0.48,
                    "estimate": 86,
                    "interval_low": 80,
                    "interval_high": 92,
                    "period": 2,
                    "value": 86,
                    "low": 80,
                    "high": 92,
                    "group": "central",
                    "cost": 5,
                    "carbon": 5,
                    "front": True,
                    "selected": True,
                    "label": "B",
                },
                {
                    "category": "C",
                    "baseline": 70,
                    "candidate": 65,
                    "fitted": 0.8,
                    "residual": 0.07,
                    "observed": 0.8,
                    "predicted": 0.75,
                    "estimate": 65,
                    "interval_low": 59,
                    "interval_high": 71,
                    "period": 3,
                    "value": 65,
                    "low": 59,
                    "high": 71,
                    "group": "central",
                    "cost": 6,
                    "carbon": 4,
                    "front": False,
                    "selected": False,
                    "label": "C",
                },
            ]
            write_json(project / "wp7_rows.json", rows)
            cases = [
                (
                    "dumbbell",
                    [
                        "--category", "category", "--x", "baseline", "--y", "candidate",
                        "--left-label", "Baseline", "--right-label", "Proposed", "--annotate",
                        "--paper-placement", "single_column", "--baseline", "0",
                    ],
                    "placement",
                ),
                (
                    "slope",
                    [
                        "--category", "category", "--x", "baseline", "--y", "candidate",
                        "--left-label", "Baseline", "--right-label", "Proposed", "--annotate",
                        "--placement", "half_width",
                    ],
                    "placement",
                ),
                (
                    "residual",
                    ["--x", "fitted", "--y", "residual", "--target-width-mm", "152"],
                    "target_width_mm",
                ),
                (
                    "calibration",
                    [
                        "--x", "observed", "--y", "predicted", "--annotate",
                        "--paper-placement", "full_width",
                    ],
                    "placement",
                ),
                (
                    "interval_comparison",
                    [
                        "--category", "category", "--y", "estimate", "--low", "interval_low",
                        "--high", "interval_high", "--annotate", "--paper-placement", "full_width",
                    ],
                    "placement",
                ),
                (
                    "scenario_envelope",
                    [
                        "--x", "period", "--y", "value", "--low", "low", "--high", "high",
                        "--group", "group", "--train-test-boundary", "2",
                        "--uncertainty-label", "Scenario range", "--paper-placement", "full_page",
                    ],
                    "placement",
                ),
                (
                    "pareto",
                    [
                        "--x", "cost", "--y", "carbon", "--pareto-flag", "front",
                        "--selected-flag", "selected", "--label", "label", "--paper-placement",
                        "half_width",
                    ],
                    "placement",
                ),
            ]
            for template, extra, sizing_mode in cases:
                with self.subTest(template=template):
                    result = self.run_script(
                        "figures/plot_templates.py", "--project-root", str(project), "--template", template,
                        "--input", "wp7_rows.json", "--output", f"{template}.pdf",
                        "--receipt", f"{template}.json",
                        "--style", str(ROOT / "assets" / "styles" / "mathmodel.mplstyle"), *extra,
                        python=TEST_PYTHON,
                    )
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    receipt = read_json(project / f"{template}.json")
                    self.assertEqual(receipt["render"]["sizing_mode"], sizing_mode)
                    self.assertGreater(receipt["render"]["width_in"], 0)
                    self.assertTrue((project / f"{template}.pdf").is_file())

            custom = read_json(project / "residual.json")["render"]
            self.assertEqual(custom["target_width_mm"], 152)
            self.assertIsNone(custom["paper_placement"])

            single_column = read_json(project / "dumbbell.json")["render"]
            self.assertEqual(single_column["paper_placement"], "single_column")
            self.assertEqual(single_column["target_width_mm"], 85.0)
            self.assertEqual(single_column["target_height_mm"], 58.0)
            self.assertGreater(single_column["font_size_pt"], 0)
            self.assertGreater(single_column["annotation_limit"], 0)




if __name__ == "__main__":
    unittest.main()
