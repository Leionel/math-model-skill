from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

from tests import test_p0_harness as p0_harness


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / "scripts" / "qa" / "check_modeling_plan.py"
HARNESS = ROOT / "scripts" / "harness.py"


class S5ResearchCoverageTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="math-s5-research-")
        self.project = Path(self.temp.name)
        fixture = p0_harness.P0HarnessTest(methodName="runTest")
        self.paths = fixture.build_fixture(self.project)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_checker(self, *, strict: bool = True) -> subprocess.CompletedProcess[str]:
        args = [
            sys.executable,
            str(CHECKER),
            "--project-root",
            str(self.project),
            "--model-contract",
            self.paths["model"].name,
            "--evidence-registry",
            self.paths["evidence"].name,
            "--formal",
        ]
        if strict:
            args.append("--strict")
        return subprocess.run(
            args,
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def run_harness(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(HARNESS), *args, "--project", str(self.project), "--json"],
            cwd=str(ROOT),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

    def add_coverage(self) -> dict:
        model = p0_harness.read_json(self.paths["model"])
        model["schema_version"] = "1.4"
        basis = model["research_basis"]
        basis.update({
            "research_scope": {
                "in_scope": ["the stated fixed-demand optimization question"],
                "out_of_scope": ["claims about unseen demand regimes"],
            },
            "discovery_candidates": [{
                "source_id": "SRC-DISC",
                "source_role": "review",
                "title": "A review used for discovery",
                "evidence_ids": [],
            }],
            "full_text_core": [{
                "source_id": "SRC-CORE",
                "source_role": "original_method",
                "title": "A full-text method source",
                "inclusion_reason": "The methods section states the formulation used for comparison.",
                "evidence_ids": ["E-CITE-PLAN"],
            }],
            "excluded_items": [{
                "source_id": "SRC-EXCLUDED",
                "source_role": "application_research",
                "title": "An out-of-scope application",
                "evidence_ids": [],
                "exclusion_reason": "Its population and outcome do not match this question.",
            }],
            "research_obligations": [{
                "obligation_id": "RO-MECHANISM",
                "category": "mechanism",
                "status": "covered",
                "critical": True,
                "evidence_ids": ["E-CITE-PLAN"],
            }],
            "stop_reason": {
                "kind": "coverage_satisfied",
                "reason": "All critical obligations are covered.",
                "residual_risk": None,
            },
        })
        p0_harness.write_json(self.paths["model"], model)
        return model

    def test_v14_coverage_with_one_core_source_passes_without_quantity_quotas(self) -> None:
        model = self.add_coverage()
        model["research_basis"]["status"] = "ready"
        p0_harness.write_json(self.paths["model"], model)
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["coverage"]["research_coverage"]["full_text_core"], 1)

    def test_research_authoring_compiler_preserves_coverage_fields(self) -> None:
        model = self.add_coverage()
        source = self.project / "research_basis.yaml"
        source.write_text(
            yaml.safe_dump({"research_basis": model["research_basis"]}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        result = self.run_harness(
            "research",
            "--compile",
            "--source",
            source.name,
            "--output",
            "compiled_research_basis.json",
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        compiled = p0_harness.read_json(self.project / "compiled_research_basis.json")
        self.assertEqual(compiled["full_text_core"], model["research_basis"]["full_text_core"])
        self.assertEqual(compiled["research_obligations"], model["research_basis"]["research_obligations"])

    def test_metadata_verified_but_content_unverified_cannot_enter_full_text_core(self) -> None:
        model = self.add_coverage()
        registry = p0_harness.read_json(self.paths["evidence"])
        registry["evidence"].append({
            "evidence_id": "E-METADATA-ONLY",
            "type": "citation",
            "result_ids": [],
            "artifacts": [],
            "supports": "metadata only",
            "boundary": "content not read",
            "verification_status": "verified",
            "citation": {
                "bib_key": "metadata_only",
                "title": "Metadata-only source",
                "authors": ["A. Author"],
                "year": 2026,
                "canonical_url": "https://example.org/metadata-only",
                "source_tier": "trusted_index",
                "metadata_sources": ["https://example.org/metadata-only"],
                "access_level": "metadata_only",
                "locator": "metadata record",
                "metadata_verified": True,
                "content_verified": False,
                "publication_status_checked": False,
                "verified_at": "2026-08-30T00:00:00Z",
            },
        })
        p0_harness.write_json(self.paths["evidence"], registry)
        model["research_basis"]["full_text_core"][0]["evidence_ids"] = ["E-METADATA-ONLY"]
        p0_harness.write_json(self.paths["model"], model)
        result = self.run_checker()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("full_text_core", result.stdout)
        self.assertIn("content/publication verification", result.stdout)

    def test_critical_obligation_gap_blocks_but_noncritical_gap_is_advisory(self) -> None:
        model = self.add_coverage()
        model["research_basis"]["research_obligations"][0].update({
            "status": "gap",
            "reason": "No source explains the mechanism under the supplied boundary.",
        })
        p0_harness.write_json(self.paths["model"], model)
        blocked = self.run_checker()
        self.assertNotEqual(blocked.returncode, 0)
        self.assertIn("critical research obligation RO-MECHANISM remains a gap", blocked.stdout)

        model["research_basis"]["research_obligations"][0]["critical"] = False
        p0_harness.write_json(self.paths["model"], model)
        advisory = self.run_checker()
        self.assertEqual(advisory.returncode, 0, advisory.stdout + advisory.stderr)
        self.assertIn("non-critical research obligation RO-MECHANISM", advisory.stdout)

    def test_search_diversity_and_zero_result_are_advisories_in_coverage_mode(self) -> None:
        model = self.add_coverage()
        model["research_basis"]["searches"] = [{
            "search_id": "S-ONE",
            "research_ids": ["RES-Q1"],
            "query": "fixed demand cost optimization",
            "language": "en",
            "source": "openalex",
            "searched_at": "2026-08-30T00:00:00Z",
            "candidate_count": 0,
        }]
        p0_harness.write_json(self.paths["model"], model)
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("no recorded LLM-knowledge reconnaissance", result.stdout)
        self.assertIn("candidate_count=0", result.stdout)

    def test_precedent_pattern_cannot_support_selected_model(self) -> None:
        model = self.add_coverage()
        model["research_basis"]["full_text_core"][0]["source_role"] = "precedent_pattern"
        p0_harness.write_json(self.paths["model"], model)
        result = self.run_checker()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("precedent-pattern evidence E-CITE-PLAN", result.stdout)

    def test_verified_evidence_outside_full_text_core_cannot_support_candidate(self) -> None:
        model = self.add_coverage()
        registry = p0_harness.read_json(self.paths["evidence"])
        outside = next(row for row in registry["evidence"] if row["evidence_id"] == "E-CITE-PLAN").copy()
        outside["evidence_id"] = "E-OUTSIDE-CORE"
        registry["evidence"].append(outside)
        p0_harness.write_json(self.paths["evidence"], registry)

        selected_id = model["research_basis"]["decisions"][0]["selected_candidate_id"]
        selected = next(
            row for row in model["research_basis"]["candidate_models"]
            if row["candidate_id"] == selected_id
        )
        selected["evidence_ids"] = ["E-OUTSIDE-CORE"]
        model["research_basis"]["decisions"][0]["decisive_evidence_ids"] = ["E-OUTSIDE-CORE"]
        p0_harness.write_json(self.paths["model"], model)

        result = self.run_checker()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside full_text_core", result.stdout)

    def test_legacy_v13_contract_remains_compatible(self) -> None:
        result = self.run_checker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["coverage"]["research_coverage"]["mode"], "legacy_compatibility")


if __name__ == "__main__":
    unittest.main()
