from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from views.writing_spine import (  # noqa: E402
    build_bounded_revision_package,
    build_section_brief,
    build_writer_context,
    compile_revision_package,
)
from qa.check_reverse_outline import _map_outline_rows  # noqa: E402


PLAN = {
    "run_id": "run-s4",
    "central_thesis": {"text": "The tested allocation reduces cost.", "boundary": "tested demand"},
    "sections": [
        {"section_id": "results.q1", "purpose": "Establish the tested result."},
        {"section_id": "conclusion", "purpose": "Turn evidence into a bounded decision."},
    ],
    "claims": [
        {"claim_id": "C1", "section": "results.q1", "text": "cost is lower", "boundary": "tested demand"}
    ],
    "argument_units": [
        {
            "unit_id": "U1",
            "section_id": "results.q1",
            "rhetorical_role": "result_observation",
            "claim_ids": ["C1"],
            "evidence_ids": ["E1"],
            "result_ids": ["R1"],
            "prerequisite_unit_ids": [],
            "expected_reader_judgment": "The value is reproducible.",
            "boundary": "tested demand",
        },
        {
            "unit_id": "U2",
            "section_id": "conclusion",
            "rhetorical_role": "recommendation",
            "claim_ids": ["C1"],
            "evidence_ids": ["E1"],
            "prerequisite_unit_ids": ["U1"],
            "expected_reader_judgment": "The option follows from the result.",
            "boundary": "tested demand",
        },
    ],
    "terminology": [],
    "canonical_recommendation": {"text": "Use option A.", "evidence_ids": ["E1"]},
}


def report(*findings: dict) -> dict:
    return {"report_id": "REV-s4", "perspective": "semantic_critic", "findings": list(findings)}


def finding(finding_id: str, *, status: str = "open", section: str = "results.q1") -> dict:
    return {
        "finding_id": finding_id,
        "perspective": "semantic_critic",
        "severity": "high",
        "summary": "The result boundary is unclear.",
        "evidence_locator": section,
        "affected_artifact": f"paper/sections/{section}/draft.md",
        "affected_claim_id": "C1",
        "required_fix": "State the tested-demand boundary after the result.",
        "confidence": "high",
        "status": status,
    }


class S4WriterTest(unittest.TestCase):
    def test_argument_envelope_exposes_reasoned_move_and_next_relation(self) -> None:
        brief = build_section_brief(PLAN, None, "results.q1")
        unit = brief["ordered_units"][0]
        self.assertEqual(unit["purpose"], "result observation")
        self.assertEqual(unit["premise"]["unit_ids"], [])
        self.assertEqual(unit["evidence_detail"]["evidence_ids"], ["E1"])
        self.assertIn("explanation", unit["argument"])
        self.assertEqual(unit["next_relation"]["unit_ids"], ["U2"])
        self.assertEqual(unit["boundary"], "tested demand")

    def test_context_loads_only_current_writing_inputs_by_default(self) -> None:
        context = build_writer_context(PLAN, "results.q1")
        self.assertEqual(
            [row["kind"] for row in context["default_context"]],
            ["writing_spine", "section_brief", "current_draft", "micro_guideline"],
        )
        self.assertNotIn(".harness/results/frozen_results.json", context["default_files"])
        self.assertTrue(any(row["path"] == ".harness/results/frozen_results.json" for row in context["on_demand"]))
        self.assertTrue(context["explicit_locator_required"])

    def test_canonical_recommendation_is_content_only(self) -> None:
        recommendation = build_section_brief(PLAN, None, "conclusion")["canonical_recommendation"]
        self.assertEqual(recommendation["wording_policy"], "content_only")
        self.assertFalse(recommendation["verbatim_required"])

    def test_reverse_outline_maps_claim_chain_and_surfaces_unmapped_prose(self) -> None:
        draft = "Unplanned prose needs a decision.\n\nThe tested result is lower."
        rows, unmapped = _map_outline_rows(
            PLAN,
            [{
                "anchor_id": "ANCHOR-U1",
                "unit_id": "U1",
                "position": draft.index("The tested result"),
                "content": "The tested result is lower.",
            }],
            draft,
        )
        self.assertEqual(rows[0]["paragraph_claims"], ["C1"])
        self.assertEqual(rows[0]["section_thesis"], "Establish the tested result.")
        self.assertEqual(rows[0]["central_thesis"], PLAN["central_thesis"]["text"])
        self.assertEqual(unmapped[0]["mapping_status"], "unmapped")
        self.assertIn("delete, move", unmapped[0]["action"])

    def test_revision_package_has_one_round_in_normal_mode(self) -> None:
        packet = build_bounded_revision_package(PLAN, report(finding("REV-S4-001")))
        self.assertEqual(packet["status"], "ready")
        self.assertEqual(packet["max_rounds"], 1)
        action = packet["findings"][0]
        self.assertEqual(action["section_id"], "results.q1")
        self.assertEqual(action["existing_views"], [
            ".harness/views/WRITING_SPINE.md",
            ".harness/views/sections/results.q1_brief.md",
        ])
        self.assertEqual(action["recheck"]["finding_id"], "REV-S4-001")

    def test_revision_stops_when_findings_do_not_decrease_and_award_cap_is_two(self) -> None:
        previous = build_bounded_revision_package(PLAN, report(finding("REV-S4-001")), mode="award")
        current = build_bounded_revision_package(
            PLAN,
            report(finding("REV-S4-001")),
            mode="award",
            round_number=2,
            previous=previous,
        )
        self.assertEqual(current["max_rounds"], 2)
        self.assertEqual(current["status"], "stopped")
        self.assertEqual(current["decision"], "stop_and_request_human_decision")
        self.assertEqual(current["stop_reason"], "finding_count_not_decreased")

    def test_revision_view_is_written_outside_the_writer_package(self) -> None:
        with tempfile.TemporaryDirectory(prefix="s4-revision-") as temp:
            root = Path(temp)
            (root / "plan.json").write_text(json.dumps(PLAN), encoding="utf-8")
            (root / "review.json").write_text(
                json.dumps(report(finding("REV-S4-002"))), encoding="utf-8",
            )
            result = compile_revision_package(
                root,
                paper_plan="plan.json",
                review_reports=["review.json"],
            )
            self.assertTrue(result["ok"])
            self.assertTrue((root / ".harness/views/revision_package.json").is_file())


if __name__ == "__main__":
    unittest.main()
