from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.qa.check_paper_style import human_prose_statistics
from scripts.qa.review_evidence import (
    _human_context_freshness,
    required_perspectives,
    summarize_review,
    validate_bundle_boundary,
    validate_review_report,
)
from scripts.qa.run_review import (
    HUMAN_PROSE_BUNDLE_ROLES,
    RUBRICS,
    SECTION_ID,
    _human_prose_context,
    _protected_snapshot,
    _snapshot_mutations,
    _writing_spine_excerpt,
    build_bundle,
    evaluate_selected_review,
)
from scripts.views.writing_spine import build_bounded_revision_package


ROOT = Path(__file__).resolve().parents[1]
DIGEST = "a" * 64
PLAN = {
    "run_id": "run-human-prose",
    "central_thesis": {"text": "模型 A 在已验证场景中成本更低。"},
    "sections": [{"section_id": "results.q1", "purpose": "比较候选方案。"}],
    "claims": [{"claim_id": "C1", "section": "results.q1", "text": "成本下降 4.44%。"}],
    "argument_units": [],
}


def report(*findings: dict) -> dict:
    return {
        "schema_version": "1.0",
        "report_id": "REV-HUMAN-PROSE",
        "run_id": "run-human-prose",
        "perspective": "human_prose",
        "review_mode": "self_critic",
        "independence_level": "L0_same_context",
        "reviewed_at": "2026-09-02T00:00:00+00:00",
        "reviewed_artifacts": [{
            "artifact_id": "ART-PAPER",
            "role": "paper",
            "path": "paper/main.tex",
            "sha256": DIGEST,
        }],
        "bundle_ref": {"path": "reports/review/bundle/manifest.json", "sha256": DIGEST},
        "findings": list(findings),
        "verdict": "fail" if findings else "pass",
    }


def finding(finding_type: str, passage: str, action: str, *, severity: str = "medium") -> dict:
    return {
        "finding_id": f"REV-{finding_type.upper().replace('_', '-')}",
        "perspective": "human_prose",
        "severity": severity,
        "summary": f"{finding_type} obscures the local argument.",
        "evidence_locator": "results.q1 paragraph 3",
        "affected_artifact": "paper/sections/results.q1/draft.md",
        "affected_claim_id": "C1",
        "required_fix": action,
        "confidence": "high",
        "status": "open",
        "finding_type": finding_type,
        "quoted_passage": passage,
        "protected_content": ["numeric_results", "evidence_semantics"],
        "required_recheck": ["section_continuity", "consistency_sweep"],
    }


class HumanProseReviewTest(unittest.TestCase):
    def test_formal_ceel_and_isolated_transition_do_not_create_signal(self) -> None:
        text = (
            "模型在给定约束下得到可行解，并以成本、排放和时延作为评价指标。因此，"
            "方案 A 的成本比基线低 4.44%，该数值来自冻结结果。"
        )
        self.assertEqual(human_prose_statistics(text)["signals"], [])

    def test_repeated_template_paragraphs_emit_only_editorial_signals(self) -> None:
        text = "\n\n".join([
            "结果表明 A 的目标值降低。这说明方案有效，因此采用方案 A。",
            "结果表明 B 的目标值降低。这说明方案有效，因此采用方案 B。",
            "结果表明 C 的目标值降低。这说明方案有效，因此采用方案 C。",
        ])
        statistics = human_prose_statistics(text)
        self.assertIn("repeated_sentence_frame_candidate", statistics["signals"])
        self.assertIn("transition_concentration_candidate", statistics["signals"])
        self.assertIn("over_regular_rhythm_candidate", statistics["signals"])
        self.assertIn("Statistics only", statistics["boundary"])

    def test_editorial_statistics_are_opt_in_for_cli_output(self) -> None:
        with tempfile.TemporaryDirectory(prefix="human-prose-stats-") as temp:
            root = Path(temp)
            plan = root / "paper_plan.json"
            draft = root / "draft.md"
            plan.write_text(json.dumps({"claims": []}), encoding="utf-8")
            draft.write_text("结果表明 A 可行。", encoding="utf-8")
            command = [
                sys.executable,
                str(ROOT / "scripts/qa/check_paper_style.py"),
                "--paper-plan", str(plan),
                "--draft", str(draft),
                "--project-root", str(root),
            ]
            ordinary = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", check=False)
            editorial = subprocess.run(
                [*command, "--human-prose-stats"],
                text=True,
                capture_output=True,
                encoding="utf-8",
                check=False,
            )
        self.assertEqual(ordinary.returncode, 0, ordinary.stderr)
        self.assertNotIn("human_prose_statistics", json.loads(ordinary.stdout))
        self.assertIn("human_prose_statistics", json.loads(editorial.stdout))

    def test_human_prose_finding_requires_quote_type_protection_and_recheck(self) -> None:
        valid = report(finding(
            "low_information_gain",
            "综上所述，该模型能够较好地解决本问题。",
            "Delete the sentence because it adds no new evidence.",
        ))
        self.assertEqual(validate_review_report(valid), [])

        invalid = report(finding(
            "low_information_gain",
            "综上所述，该模型能够较好地解决本问题。",
            "Delete the sentence.",
        ))
        del invalid["findings"][0]["protected_content"]
        self.assertTrue(validate_review_report(invalid))

    def test_generic_decision_finding_uses_existing_comparison_without_invention(self) -> None:
        value = report(finding(
            "generic_decision_rationale",
            "综合考虑准确性、稳定性和效率，我们选择模型 A。",
            "Use the existing candidate comparison to name the deciding validation-window evidence; do not add experiments.",
        ))
        self.assertEqual(validate_review_report(value), [])
        self.assertIn("do not add experiments", value["findings"][0]["required_fix"])

    def test_bounded_revision_preserves_numbers_and_limits_edit_scope(self) -> None:
        value = report(finding(
            "redundant_exposition",
            "成本下降 4.44%，因此该方案具有较好的表现。",
            "Keep 4.44% and delete only the generic praise.",
        ))
        package = build_bounded_revision_package(PLAN, value)
        action = package["findings"][0]
        self.assertEqual(action["rewrite_scope"], "finding_local_only")
        self.assertIn("numeric_results", action["protected_content"])
        self.assertIn("4.44%", action["action"])
        self.assertEqual(action["revision_order"][0], "delete")
        self.assertIn("deterministic_qa", action["recheck"]["checks"])

    def test_human_prose_cannot_emit_blocker(self) -> None:
        value = report(finding(
            "mechanical_ceel",
            "结果表明……这说明……综上……",
            "Compress repeated interpretation.",
            severity="blocker",
        ))
        self.assertTrue(validate_review_report(value))

    def test_human_prose_cannot_claim_review_independence(self) -> None:
        value = report()
        value["review_mode"] = "fresh_context"
        value["independence_level"] = "L1_fresh_context"
        self.assertTrue(validate_review_report(value))

    def test_optional_perspective_does_not_change_w2_or_independence(self) -> None:
        self.assertEqual(required_perspectives("sprint"), ("semantic_critic",))
        self.assertEqual(required_perspectives("research"), ("semantic_critic", "judge_lens"))
        self.assertNotIn("model_contract", HUMAN_PROSE_BUNDLE_ROLES)
        self.assertNotIn("frozen_results", HUMAN_PROSE_BUNDLE_ROLES)
        with tempfile.TemporaryDirectory(prefix="human-prose-status-") as temp:
            summary = summarize_review(Path(temp), "research", require_registration=False)
        self.assertFalse(summary["perspectives"]["human_prose"]["required"])
        self.assertFalse(summary["has_current_l1_review"])

    def test_human_prose_bundle_declares_lean_context_policy(self) -> None:
        with tempfile.TemporaryDirectory(prefix="human-prose-bundle-") as temp:
            root = Path(temp)
            with (
                patch("scripts.qa.run_review._v2_dag_nodes", return_value=[]),
                patch("scripts.qa.run_review._v2_role_entries", return_value=[]),
                patch("scripts.qa.run_review._human_prose_scan", return_value=None),
            ):
                _, manifest = build_bundle(
                    SimpleNamespace(run_id="run-human-prose"),
                    root,
                    "20260902T000000Z",
                    ["human_prose"],
                    focus_section="results.q1",
                )
        policy = manifest["context_policy"]
        self.assertIn("paper_section", policy["default_roles"])
        self.assertEqual(policy["on_demand_roles"], [])
        self.assertIn("frozen_results", policy["excluded_roles"])
        self.assertNotIn("model_contract", [row["role"] for row in manifest["files"]])

    def test_section_context_is_local_and_section_id_cannot_be_a_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="human-prose-context-") as temp:
            root = Path(temp)
            bundle = root / "bundle"
            bundle.mkdir()
            brief = root / ".harness/views/sections/results.q1_brief.md"
            draft = root / "paper/sections/results.q1/draft.md"
            brief.parent.mkdir(parents=True)
            draft.parent.mkdir(parents=True)
            brief.write_text("brief", encoding="utf-8")
            draft.write_text("draft", encoding="utf-8")
            rows = _human_prose_context(root, bundle, focus_section="results.q1")
        self.assertEqual({row["role"] for row in rows}, {"section_brief", "paper_section"})
        self.assertIsNotNone(SECTION_ID.fullmatch("results.q1"))
        self.assertIsNone(SECTION_ID.fullmatch("../results.q1"))
        self.assertIsNone(SECTION_ID.fullmatch("results..q1"))
        self.assertIsNone(SECTION_ID.fullmatch("results."))

    def test_human_context_change_makes_the_report_stale(self) -> None:
        with tempfile.TemporaryDirectory(prefix="human-prose-freshness-") as temp:
            root = Path(temp)
            bundle_dir = root / "reports/review/bundle/run"
            bundle_dir.mkdir(parents=True)
            sources = {
                "paper_section": (root / "paper/sections/results.q1/draft.md", "original"),
                "section_brief": (root / ".harness/views/sections/results.q1_brief.md", "brief"),
                "writing_spine": (root / ".harness/views/WRITING_SPINE.md", "# Spine\n### results.q1 (phase 1)\n"),
            }
            rows = []
            for role, (source, content) in sources.items():
                source.parent.mkdir(parents=True, exist_ok=True)
                source.write_text(content, encoding="utf-8")
                member = bundle_dir / f"{role}.md"
                member.write_text(content, encoding="utf-8")
                rows.append({
                    "role": role,
                    "source_path": source.relative_to(root).as_posix(),
                    "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    "path": member.name,
                    "sha256": hashlib.sha256(member.read_bytes()).hexdigest(),
                })
            bundle = bundle_dir / "bundle_manifest.json"
            manifest = {
                "perspectives": ["human_prose"],
                "focus_section": "results.q1",
                "files": rows,
                "context_policy": {"default_roles": ["paper_section"]},
                "bindings": [{"role": "paper", "artifact_id": "ART-PAPER"}],
            }
            bundle.write_text(json.dumps(manifest), encoding="utf-8")
            value = report()
            value["bundle_ref"] = {
                "path": "reports/review/bundle/run/bundle_manifest.json",
                "sha256": hashlib.sha256(bundle.read_bytes()).hexdigest(),
            }
            self.assertEqual(_human_context_freshness(value, root), [])
            self.assertEqual(validate_bundle_boundary(value, root), [])
            source = sources["paper_section"][0]
            source.write_text("changed", encoding="utf-8")
            self.assertTrue(_human_context_freshness(value, root))

            leaked = bundle_dir / "model_contract.json"
            leaked.write_text("{}", encoding="utf-8")
            manifest["files"].append({
                "role": "model_contract",
                "path": leaked.name,
                "sha256": hashlib.sha256(leaked.read_bytes()).hexdigest(),
            })
            bundle.write_text(json.dumps(manifest), encoding="utf-8")
            value["bundle_ref"]["sha256"] = hashlib.sha256(bundle.read_bytes()).hexdigest()
            self.assertTrue(validate_bundle_boundary(value, root))

    def test_bounded_revision_rejects_whole_section_rewrite(self) -> None:
        value = report(finding(
            "redundant_exposition",
            "成本下降 4.44%。",
            "Rewrite the whole section for a more natural voice.",
        ))
        with self.assertRaises(ValueError):
            build_bounded_revision_package(PLAN, value)

    def test_backend_snapshot_covers_local_human_prose_inputs(self) -> None:
        with tempfile.TemporaryDirectory(prefix="human-prose-protected-") as temp:
            root = Path(temp)
            draft = root / "paper/sections/results.q1/draft.md"
            draft.parent.mkdir(parents=True)
            draft.write_text("original", encoding="utf-8")
            state = SimpleNamespace(manifest_path=root / "run_manifest.json", profile_path=root / "profile.json")
            state.root_path = lambda *_args, **_kwargs: None
            with patch("scripts.qa.run_review._v2_role_entries", return_value=[]):
                before = _protected_snapshot(state, root, focus_section="results.q1")
            draft.write_text("mutated", encoding="utf-8")
            self.assertIn(str(draft.resolve()), _snapshot_mutations(before))

    def test_writing_spine_context_contains_only_the_focused_section(self) -> None:
        spine = """# Writing Spine

- central thesis: bounded result

## Section order and argument units

### model.q1 (phase 1)

- purpose: derive

### results.q1 (phase 2)

- purpose: report

## Cross-question handoffs
"""
        excerpt = _writing_spine_excerpt(spine, "results.q1")
        self.assertIn("central thesis: bounded result", excerpt)
        self.assertIn("### results.q1", excerpt)
        self.assertNotIn("### model.q1", excerpt)
        self.assertNotIn("Cross-question handoffs", excerpt)

    def test_human_prose_result_is_not_adjudicated_as_w2(self) -> None:
        next_finding = {"finding_id": "REV-LOCAL", "summary": "Local repetition."}
        summary = {
            "perspectives": {
                "human_prose": {
                    "executed": True,
                    "freshness": "current",
                    "errors": [],
                    "next_finding": next_finding,
                }
            },
            "next_finding": None,
        }
        with patch("scripts.qa.run_review.summarize_review", return_value=summary):
            result, errors, w2_preview = evaluate_selected_review(
                Path("."), "research", "run-human-prose", ["human_prose"],
            )
        self.assertEqual(errors, [])
        self.assertIsNone(w2_preview)
        self.assertEqual(result["next_finding"], next_finding)

    def test_reference_disables_detector_recreate_and_fabricated_history(self) -> None:
        reference = (ROOT / RUBRICS["human_prose"]).read_text(encoding="utf-8")
        normalized = " ".join(reference.split())
        self.assertIn("not detect authorship", normalized)
        self.assertIn("Full section recreation is disabled by default", normalized)
        self.assertIn("Do not manufacture failed models", normalized)
        self.assertIn("CEEL is not a paragraph template", normalized)


if __name__ == "__main__":
    unittest.main()
