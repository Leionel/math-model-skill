"""Derived writing and implementation views: regenerable projections of the
model contract and paper plan (never new truth sources)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from views.implementation_tasks import build_implementation_tasks, render_markdown  # noqa: E402
from views.writing_spine import (  # noqa: E402
    build_section_brief,
    build_writing_spine,
    compile_section_brief,
    compile_writing_spine,
    render_brief_markdown,
    render_spine_markdown,
)

CONTRACT = {
    "schema_version": "1.3",
    "run_id": "run-1",
    "status": "ready",
    "questions": [{"question_id": "q1", "task": "minimize cost", "conclusion_type": "numeric optimum", "inputs": ["demand"], "outputs": ["cost"]}],
    "models": [{
        "model_id": "M-Q1",
        "question_id": "q1",
        "name": "cost model",
        "problem_type": "optimization",
        "characteristics": ["deterministic"],
        "algorithm": "MILP",
        "constraints": [{"constraint_id": "C1", "expression": "x >= 0", "meaning": "nonnegative"}],
        "inputs": ["demand"],
        "outputs": ["cost"],
        "validation": [{"check_id": "V1", "stage": "smoke", "method": "recompute constraints", "acceptance": "zero violations"}],
        "validation_obligations": [{"obligation_id": "VAL-FEAS", "category": "feasibility", "method": "recompute", "required_stage": "both",
                                    "acceptance": {"left_metric_id": "max_violation", "operator": "<=", "right": {"kind": "literal", "value": 0}, "unit": "item"}}],
        "plan_details": {
            "mechanism": "feasible region with additive cost",
            "equation_plan": [{"equation_id": "EQ-OBJ", "purpose": "objective", "expression_or_derivation": "min C(x)", "equation_type": "objective", "math_risk": "medium"}],
            "parameter_plan": [{"parameter": "demand", "provenance": {"type": "GIVEN", "source_locator": "input.csv"}, "unit": "item", "uncertainty_or_range": "+-10%"}],
            "implementation_steps": ["validate input", "solve", "recompute"],
            "failure_modes": ["demand not fixed"],
            "scaffold_entry": "scripts/scaffold/opt_milp.py",
        },
    }],
}

PLAN = {
    "schema_version": "1.2",
    "run_id": "run-1",
    "central_thesis": {"text": "plan B wins under frozen demand", "claim_ids": ["C-1"], "boundary": "frozen-base only"},
    "sections": [
        {"section_id": "model.q1", "purpose": "derive the model", "claim_ids": ["C-1"]},
        {"section_id": "results.q1", "purpose": "report and validate the result", "claim_ids": ["C-1"]},
    ],
    "argument_units": [
        {"unit_id": "AU-FORM", "section_id": "model.q1", "rhetorical_role": "mechanism_derivation", "claim_ids": ["C-1"], "evidence_ids": ["E-1"], "prerequisite_unit_ids": [], "expected_reader_judgment": "mechanism matches the task", "boundary": "additive cost", "math_locators": ["\\label{eq:EQ-OBJ}"]},
        {"unit_id": "AU-RESULT", "section_id": "results.q1", "rhetorical_role": "result_observation", "claim_ids": ["C-1"], "evidence_ids": ["E-1"], "prerequisite_unit_ids": ["AU-FORM"], "expected_reader_judgment": "number is reproducible", "boundary": "frozen-base", "result_ids": ["R-1"]},
        {"unit_id": "AU-VALID", "section_id": "results.q1", "rhetorical_role": "validation", "claim_ids": ["C-1"], "evidence_ids": ["E-1"], "prerequisite_unit_ids": ["AU-RESULT"], "expected_reader_judgment": "constraints recomputed", "boundary": "declared constraints only"},
    ],
    "depth_budget": [{"question_id": "q1", "target_words": 260, "rationale": "core decision"}],
    "claims": [{"claim_id": "C-1", "claim_type": "observation", "text": "plan B is cheapest", "question_id": "q1", "evidence_ids": ["E-1"], "section": "results.q1", "boundary": "frozen-base", "support_level": "direct"}],
    "terminology": [{"canonical": "可行域", "forbidden_variants": ["可行区域"]}],
    "abstract_results": [{"result_id": "R-1", "priority": "primary", "selection_reason": "decisive", "claim_ids": ["C-1"], "word_budget": 28}],
    "canonical_recommendation": {"text": "采用方案 B", "evidence_ids": ["E-1"]},
}

PACKAGE = {
    "schema_version": "1.0",
    "run_id": "run-1",
    "claims": [{
        "claim_id": "C-1",
        "approved_text": "plan B is cheapest",
        "boundary": "frozen-base",
        "support_level": "direct",
        "inference_strength": "descriptive",
        "results": [{"result_id": "R-1", "display_value": "90.0", "unit": "CNY"}],
    }],
}


class ImplementationTaskViewTest(unittest.TestCase):
    def test_projects_contract_items_steps_and_escalation(self) -> None:
        view = build_implementation_tasks(CONTRACT)
        self.assertEqual(view["schema_version"], "1.0")
        task = view["tasks"][0]
        self.assertEqual(task["task_id"], "IMPL-M-Q1")
        self.assertEqual(task["equations"][0]["equation_id"], "EQ-OBJ")
        self.assertEqual(task["constraints"][0]["constraint_id"], "C1")
        self.assertEqual(task["test_obligations"][0]["obligation_id"], "VAL-FEAS")
        self.assertEqual(task["smoke_acceptance"][0]["check_id"], "V1")
        self.assertIn("return to M1", task["escalation_route"])
        self.assertEqual(task["scaffold_entry"], "scripts/scaffold/opt_milp.py")

    def test_rejects_non_ready_contract(self) -> None:
        with self.assertRaises(ValueError):
            build_implementation_tasks({**CONTRACT, "status": "draft"})

    def test_markdown_contains_all_sections(self) -> None:
        markdown = render_markdown(build_implementation_tasks(CONTRACT))
        for heading in ("# Implementation Task View", "## IMPL-M-Q1", "### Equations to implement", "### Test obligations", "### Failure handling"):
            self.assertIn(heading, markdown)

    def test_robustness_checklist_is_keyed_by_problem_type(self) -> None:
        task = build_implementation_tasks(CONTRACT)["tasks"][0]
        ids = [row["protocol_id"] for row in task["robustness_checklist"]]
        # base set plus the optimization solver protocols, in stable order
        self.assertEqual(ids, [
            "CP-DATA-01", "CP-DATA-03", "CP-UNIT-01", "CP-OUT-01", "CP-EVID-01",
            "CP-NUM-02", "CP-SOLVE-01", "CP-SOLVE-02", "CP-SOLVE-03",
        ])
        self.assertTrue(all(row["check"] for row in task["robustness_checklist"]))

    def test_robustness_checklist_adds_leakage_and_seed_protocols(self) -> None:
        contract = {
            **CONTRACT,
            "models": [{
                **CONTRACT["models"][0],
                "problem_type": "time_series",
                "characteristics": ["stochastic", "time_dependent"],
            }],
        }
        task = build_implementation_tasks(contract)["tasks"][0]
        ids = [row["protocol_id"] for row in task["robustness_checklist"]]
        self.assertIn("CP-LEAK-01", ids)
        self.assertIn("CP-LEAK-02", ids)
        self.assertIn("CP-RAND-01", ids)
        self.assertNotIn("CP-SOLVE-02", ids)
        # stochastic and time_dependent each map onto shared protocols; no duplicates
        self.assertEqual(len(ids), len(set(ids)))

    def test_markdown_renders_robustness_checklist(self) -> None:
        markdown = render_markdown(build_implementation_tasks(CONTRACT))
        self.assertIn("### Robustness checklist (operational protocols)", markdown)
        self.assertIn("`CP-SOLVE-02`", markdown)
        self.assertIn("references/research/coding_protocols.md", markdown)


class WritingSpineTest(unittest.TestCase):
    def test_spine_orders_decisive_sections_first_and_reports_handoffs(self) -> None:
        spine = build_writing_spine(PLAN, None)
        self.assertEqual([row["section_id"] for row in spine["sections"]], ["model.q1", "results.q1"])
        # results section carries result_observation (phase 1) and must be drafted first
        self.assertEqual(spine["recommended_writing_order"][0], "results.q1")
        handoffs = {(row["from_unit"], row["to_unit"]) for row in spine["cross_question_handoffs"]}
        self.assertIn(("AU-FORM", "AU-RESULT"), handoffs)
        self.assertEqual(spine["abstract_evidence_budget"]["word_budgets"], [28])

    def test_spine_markdown_renders_thesis_and_order(self) -> None:
        markdown = render_spine_markdown(build_writing_spine(PLAN, None))
        self.assertIn("plan B wins under frozen demand", markdown)
        self.assertIn("results.q1 -> model.q1", markdown)

    def test_section_brief_uses_package_values_and_reports_handoff(self) -> None:
        brief = build_section_brief(PLAN, PACKAGE, "results.q1")
        self.assertEqual([row["unit_id"] for row in brief["ordered_units"]], ["AU-RESULT", "AU-VALID"])
        claim = brief["claims"][0]
        self.assertEqual(claim["approved_text"], "plan B is cheapest")
        self.assertEqual(claim["results"][0]["display_value"], "90.0")
        # AU-FORM is established earlier (model.q1) and nothing later depends on this section
        self.assertEqual(brief["established_facts"][0]["unit_id"], "AU-FORM")
        self.assertEqual(brief["must_not_claim"]["forbidden_variants"], ["可行区域"])
        self.assertEqual(brief["canonical_recommendation"]["text"], "采用方案 B")

    def test_section_brief_rejects_unknown_section(self) -> None:
        with self.assertRaises(ValueError):
            build_section_brief(PLAN, None, "nope")

    def test_section_brief_projects_evidence_allocation(self) -> None:
        brief = build_section_brief(PLAN, PACKAGE, "results.q1")
        rows = {row["unit_id"]: row for row in brief["evidence_allocation"]["rows"]}
        self.assertEqual(rows["AU-RESULT"]["allocation_class"], "core_finding")
        self.assertEqual(rows["AU-RESULT"]["destination"], "body")
        self.assertEqual(rows["AU-RESULT"]["result_ids"], ["R-1"])
        self.assertEqual(rows["AU-VALID"]["allocation_class"], "validation")
        self.assertIn("removed elsewhere", brief["evidence_allocation"]["rule"])

    def test_evidence_allocation_defaults_parameter_evidence_to_appendix(self) -> None:
        plan = {
            **PLAN,
            "argument_units": [
                *PLAN["argument_units"],
                {"unit_id": "AU-PARAM", "section_id": "model.q1", "rhetorical_role": "parameter_evidence",
                 "claim_ids": ["C-1"], "evidence_ids": ["E-1"], "prerequisite_unit_ids": [],
                 "expected_reader_judgment": "parameters are sourced", "boundary": "declared parameters"},
            ],
        }
        brief = build_section_brief(plan, None, "model.q1")
        rows = {row["unit_id"]: row for row in brief["evidence_allocation"]["rows"]}
        self.assertEqual(rows["AU-PARAM"]["allocation_class"], "parameter_evidence")
        self.assertEqual(rows["AU-PARAM"]["destination"], "appendix")

    def test_section_brief_markdown_renders_allocation_table(self) -> None:
        markdown = render_brief_markdown(build_section_brief(PLAN, PACKAGE, "results.q1"))
        self.assertIn("## Evidence allocation (class -> destination)", markdown)
        self.assertIn("core_finding", markdown)
        self.assertIn("shortest sufficient evidence chain", markdown)

    def test_compile_writes_json_and_markdown_views(self) -> None:
        with tempfile.TemporaryDirectory(prefix="views-") as temp:
            root = Path(temp)
            plan_path = root / "plan.json"
            plan_path.write_text(json.dumps(PLAN, ensure_ascii=False), encoding="utf-8")
            package_path = root / "package.json"
            package_path.write_text(json.dumps(PACKAGE, ensure_ascii=False), encoding="utf-8")
            result = compile_writing_spine(root, paper_plan=str(plan_path), writer_package=str(package_path))
            self.assertTrue((root / ".harness/views/WRITING_SPINE.md").is_file())
            self.assertTrue((root / ".harness/views/writing_spine.json").is_file())
            self.assertEqual(result["sections"], 2)
            brief = compile_section_brief(root, paper_plan=str(plan_path), section_id="results.q1", writer_package=str(package_path))
            self.assertTrue((root / ".harness/views/sections/results.q1_brief.md").is_file())
            self.assertEqual(brief["units"], 2)
            markdown = (root / ".harness/views/sections/results.q1_brief.md").read_text(encoding="utf-8")
            self.assertIn("90.0", markdown)
            self.assertIn("Never print `ANCHOR-*`", markdown)


class PaperWriteSurfaceTest(unittest.TestCase):
    def test_harness_paper_write_compiles_section_brief_view(self) -> None:
        with tempfile.TemporaryDirectory(prefix="paper-write-") as temp:
            root = Path(temp)
            contract_dir = root / ".harness" / "contracts"
            contract_dir.mkdir(parents=True, exist_ok=True)
            (contract_dir / "paper_plan.json").write_text(json.dumps(PLAN, ensure_ascii=False), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "harness.py"),
                 "paper", "write", "results.q1", "--project", str(root), "--json"],
                text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["writer_view"]["units"], 2)
            self.assertTrue((root / ".harness/views/sections/results.q1_brief.md").is_file())
            self.assertTrue((root / ".harness/views/WRITING_SPINE.md").is_file())
            # author Markdown is scaffolded but never overwritten by the view
            self.assertTrue((root / "paper/sections/results.q1/draft.md").is_file())


REVERSE_PLAN = {
    **PLAN,
    "draft_coverage": {
        "status": "planned",
        "anchors": [
            {"anchor_id": "A-FORM", "unit_id": "AU-FORM", "question_id": "q1", "patterns": ["\\label{harness:AU-FORM}"], "minimum_words": 20},
            {"anchor_id": "A-RESULT", "unit_id": "AU-RESULT", "question_id": "q1", "patterns": ["\\label{harness:AU-RESULT}"], "minimum_words": 20},
        ],
    },
}

DRAFT_ORDERED = (
    "before anything we derive the model. \\label{harness:AU-FORM}\n"
    "the additive cost mechanism defines a feasible region and a single objective.\n"
    "\\label{harness:AU-RESULT}\n"
    "the additive cost mechanism defines a feasible region and a single objective restated. "
    "the frozen run reports the objective value and recomputes every constraint.\n"
)
DRAFT_REVERSED = (
    "\\label{harness:AU-RESULT}\n"
    "results first, which is wrong because the premise is not established yet.\n"
    "\\label{harness:AU-FORM}\n"
    "the model derivation appears too late in this draft.\n"
)


class ReverseOutlineTest(unittest.TestCase):
    def _run(self, plan: dict, draft: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="reverse-") as temp:
            root = Path(temp)
            (root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            (root / "main.tex").write_text(draft, encoding="utf-8")
            return subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "qa" / "check_reverse_outline.py"),
                 "--project-root", str(root), "--paper-plan", "plan.json", "--draft", "main.tex"],
                text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
            )

    def test_ordered_draft_passes_with_outline(self) -> None:
        result = self._run(REVERSE_PLAN, DRAFT_ORDERED)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["errors"], [])
        self.assertEqual(payload["claims_located"], 1)
        # the duplicated long CJK passage is flagged for human compression
        self.assertTrue(any("repeat the same long passage" in warning for warning in payload["warnings"]))
        self.assertEqual(payload["reverse_outline"][0]["unit_id"], "AU-FORM")

    def test_reversed_handoff_is_blocked(self) -> None:
        # anchors declared in document order (RESULT before FORM) so both are
        # locatable; the prerequisite AU-FORM then lands after its dependent
        # and the cross-section handoff is flagged as reversed
        plan = {
            **REVERSE_PLAN,
            "draft_coverage": {"status": "planned", "anchors": [
                {"anchor_id": "A-RESULT", "unit_id": "AU-RESULT", "question_id": "q1", "patterns": ["\\label{harness:AU-RESULT}"]},
                {"anchor_id": "A-FORM", "unit_id": "AU-FORM", "question_id": "q1", "patterns": ["\\label{harness:AU-FORM}"]},
            ]},
        }
        result = self._run(plan, DRAFT_REVERSED)
        payload = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any("reversed" in message for message in payload["errors"]))

    def test_draft_order_conflicting_with_declaration_is_reported(self) -> None:
        # declaration order says FORM first; the draft puts RESULT first, so the
        # ordered scan cannot locate A-RESULT anymore and the draft is blocked
        result = self._run(REVERSE_PLAN, DRAFT_REVERSED)
        payload = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any("A-RESULT" in message and "cannot be located" in message for message in payload["errors"]))

    def test_missing_anchor_leaves_anchor_unlocatable(self) -> None:
        result = self._run(REVERSE_PLAN, "\\label{harness:AU-FORM}\nsome derivation text.\n")
        payload = json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(any("cannot be located" in message for message in payload["errors"]))
        # the claim is still anchored through AU-FORM; the failure is the missing span
        self.assertEqual(payload["claims_located"], 1)


if __name__ == "__main__":
    unittest.main()
