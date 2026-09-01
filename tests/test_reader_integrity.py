"""Reader-visible source, PDF, figure-audience, and visual-scan regressions."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pdf import check_math_pdf_consistency  # noqa: E402
from qa.reader_integrity import (  # noqa: E402
    collect_registered_internal_ids,
    evaluate_figure_reader_bindings,
    exposed_identifiers,
    source_issues,
    visual_opportunity_scan,
)


class ReaderIntegrityTest(unittest.TestCase):
    def test_draft_coverage_headings_are_not_internal_registry_ids(self) -> None:
        document = {
            "draft_coverage": {
                "anchors": [{"anchor_id": "FORMULATION", "patterns": ["Model formulation"]}],
            },
        }
        self.assertEqual(collect_registered_internal_ids(document), set())
        self.assertEqual(exposed_identifiers("FORMULATION", collect_registered_internal_ids(document)), [])

    def test_only_visible_prefixes_and_registered_ids_are_rejected(self) -> None:
        source = r"""
% AU-Q1-FORM and ANCHOR-COMMENT are legal source comments
\label{AU-Q1-FORM}
Normal R-Q2 notation and Harness prose remain legal.
Visible AU-Q1-FORM and LOC-AU-Q1-F.
"""

        self.assertEqual(
            exposed_identifiers(source, {"AU-Q1-FORM"}),
            ["AU-Q1-FORM", "LOC-AU-Q1-F"],
        )

    def test_audit_is_forbidden_outside_comments_even_in_invisible_metadata(self) -> None:
        self.assertEqual(source_issues("% \\audit{legal comment}"), [])
        issues = source_issues(r"\label{\audit{hidden}}")
        self.assertTrue(any("forbidden \\audit" in issue for issue in issues), issues)

    def test_only_scientific_argument_figures_may_enter_body(self) -> None:
        source = r"\includegraphics{figures/mechanism.png}"
        base = {
            "figure_id": "FIG-1",
            "data_artifacts": ["figures/mechanism.png"],
        }
        for audience in (None, "submission_disclosure", "internal_audit"):
            figure = dict(base)
            if audience is not None:
                figure["audience"] = audience
            errors, _ = evaluate_figure_reader_bindings({"figures": [figure]}, source)
            self.assertTrue(errors, audience)

        errors, details = evaluate_figure_reader_bindings(
            {"figures": [{**base, "audience": "scientific_argument"}]},
            source,
        )
        self.assertEqual(errors, [])
        self.assertTrue(details["figures"]["FIG-1"]["used_in_reader_body"])

    def test_visual_scan_reports_every_argument_unit_without_a_figure_quota(self) -> None:
        plan = {
            "argument_units": [
                {"unit_id": "U-M", "rhetorical_role": "mechanism_derivation", "claim_ids": ["C1"]},
                {"unit_id": "U-R", "rhetorical_role": "result_observation", "claim_ids": ["C2"]},
                {"unit_id": "U-B", "rhetorical_role": "boundary", "claim_ids": ["C3"]},
            ],
            "figures": [{"figure_id": "FIG-2", "claim_ids": ["C2"]}],
            "tables": [],
        }

        scan = visual_opportunity_scan(plan)

        self.assertEqual([row["unit_id"] for row in scan["rows"]], ["U-M", "U-R", "U-B"])
        self.assertEqual([row["status"] for row in scan["rows"]], [
            "review_required", "covered", "no_default_visual_need",
        ])
        self.assertIn("does not impose a quota", scan["rule"])

    def test_math_pdf_checker_uses_registered_ids_from_plan(self) -> None:
        with tempfile.TemporaryDirectory(prefix="reader-pdf-") as temp:
            root = Path(temp)
            pdf = root / "main.pdf"
            model = root / "model.json"
            plan = root / "plan.json"
            pdf.write_bytes(b"%PDF-1.4\n")
            model.write_text("{}", encoding="utf-8")
            plan.write_text(json.dumps({"claims": [{"claim_id": "C-REGISTERED"}]}), encoding="utf-8")
            argv = [
                "check_math_pdf_consistency.py",
                "--project-root", str(root),
                "--pdf", str(pdf),
                "--model-contract", str(model),
                "--paper-plan", str(plan),
            ]
            stdout = io.StringIO()
            with (
                patch.object(sys, "argv", argv),
                patch.object(check_math_pdf_consistency, "_validate_document", return_value=({}, [], "test")),
                patch.object(check_math_pdf_consistency, "_extract_text", return_value=("Visible C-REGISTERED", None)),
                contextlib.redirect_stdout(stdout),
            ):
                code = check_math_pdf_consistency.main()

            report = json.loads(stdout.getvalue())
            self.assertEqual(code, 1)
            self.assertEqual(report["details"]["reader_integrity"]["registered_internal_id_count"], 1)
            self.assertEqual(report["details"]["reader_integrity"]["exposed_identifiers"], ["C-REGISTERED"])


if __name__ == "__main__":
    unittest.main()
