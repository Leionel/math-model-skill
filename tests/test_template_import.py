#!/usr/bin/env python3
"""Regression tests for importing a complete user-provided LaTeX template."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from latex.safe_build import copy_project
from latex.template_usage import validate_template_usage
from latex.import_user_template import _adapt_preamble, _body_tex, _replace_document_body


class TemplateImportTest(unittest.TestCase):
    def test_mcm_adapter_replaces_metadata_and_enters_ai_matter(self) -> None:
        template = (
            "\\documentclass[12pt]{mcmthesis}\n"
            "\\mcmsetup{problem = A, tcn = 1234567, sheet = true}\n"
            "\\title{Template title}\n"
            "\\begin{document}\nDemo body.\n\\end{document}\n"
        )
        adapted, warnings = _adapt_preamble(template, "mcm_icm")
        self.assertEqual(warnings, [])
        self.assertIn("problem = \\HarnessProblem", adapted)
        self.assertIn("tcn = \\HarnessControlNumber", adapted)
        self.assertIn("\\title{\\HarnessTitle}", adapted)
        entrypoint = _replace_document_body(adapted)
        self.assertIn("\\input{harness/metadata.tex}", entrypoint)
        self.assertIn("\\input{harness/body.tex}", entrypoint)
        self.assertNotIn("Demo body", entrypoint)
        self.assertIn("\\AImatter", _body_tex("mcm_icm"))

    def test_complete_template_tree_is_retained_and_demo_body_is_replaced(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-template-import-") as temp:
            root = Path(temp)
            template = root / "user_template"
            project = root / "project"
            template.mkdir()
            (template / "contest.cls").write_text("\\NeedsTeXFormat{LaTeX2e}\n", encoding="utf-8")
            (template / "main.tex").write_text(
                "\\documentclass{contest}\n\\title{Sample title}\n\\begin{document}\n"
                "\\maketitle\nThis is the demonstration body.\n\\end{document}\n",
                encoding="utf-8",
            )
            (template / "ref.bib").write_text("@article{demo,title={Demo}}\n", encoding="utf-8")
            (template / "fonts").mkdir()
            (template / "fonts" / "TemplateFont.otf").write_bytes(b"font")
            (template / "figures").mkdir()
            (template / "figures" / "placeholder.png").write_bytes(b"image")

            result = subprocess.run(
                [
                    sys.executable, str(ROOT / "scripts" / "latex" / "import_user_template.py"),
                    "--project-root", str(project),
                    "--template-root", str(template),
                    "--destination", "paper",
                    "--template-id", "fixture-template",
                    "--competition-profile", "fixture",
                    "--family", "generic",
                    "--title", "Harness title",
                    "--problem", "A",
                    "--keywords", "modeling, validation",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["ok"], payload)

            imported = project / "paper"
            self.assertTrue((imported / "contest.cls").is_file())
            self.assertTrue((imported / "ref.bib").is_file())
            self.assertTrue((imported / "fonts" / "TemplateFont.otf").is_file())
            self.assertTrue((imported / "figures" / "placeholder.png").is_file())
            entrypoint = (imported / "main.tex").read_text(encoding="utf-8")
            self.assertIn("\\input{harness/metadata.tex}", entrypoint)
            self.assertIn("\\input{harness/body.tex}", entrypoint)
            self.assertNotIn("demonstration body", entrypoint)

            contract_path = imported / "template_contract.json"
            contract = json.loads(contract_path.read_text(encoding="utf-8"))
            self.assertEqual(contract["status"], "draft")
            self.assertIn("fonts/TemplateFont.otf", contract["template_snapshot"]["asset_hashes"])
            _, errors, warnings = validate_template_usage(
                contract_path, imported, Path("main.tex"), "xelatex", require_verified=False
            )
            self.assertEqual(errors, [], errors)
            self.assertEqual(warnings, [], warnings)

            isolated = root / "isolated"
            copy_project(imported, isolated)
            self.assertTrue((isolated / "fonts" / "TemplateFont.otf").is_file())


if __name__ == "__main__":
    unittest.main()
