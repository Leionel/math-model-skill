import unittest

from scripts.qa.check_paper_readiness import presentation_completeness
from scripts.qa.check_gates import strict_editorial_profile
from scripts.qa.presentation_semantics import (
    evaluate_figure_semantics,
    evaluate_required_answer_coverage,
    evaluate_required_answer_declarations,
    evaluate_terminology_consistency,
)


def required_answer() -> dict:
    return {
        "answer_type": "quantity",
        "quantity": "optimal_cost",
        "unit": "CNY",
        "scope": "frozen base demand",
        "must_satisfy": "all declared constraints",
        "reporting_semantics": "report the independently recomputed cost",
    }


class CumcmReviewUpgradeTest(unittest.TestCase):
    def test_editorial_profile_is_opt_in(self) -> None:
        self.assertFalse(strict_editorial_profile({}))
        self.assertTrue(strict_editorial_profile({"editorial_semantics_profile": "strict"}))

    def test_required_answer_binds_to_model_output(self) -> None:
        model = {
            "questions": [{"question_id": "q1", "outputs": ["optimal_cost"], "required_answer": required_answer()}],
            "models": [{"model_id": "M1", "question_id": "q1", "outputs": ["optimal_cost"]}],
        }
        errors, details = evaluate_required_answer_declarations(model, require=True)
        self.assertEqual(errors, [])
        self.assertEqual(details["declared"]["q1"]["quantity"], "optimal_cost")

        model["questions"][0]["required_answer"]["quantity"] = "unregistered_quantity"
        errors, _ = evaluate_required_answer_declarations(model, require=True)
        self.assertTrue(any("does not bind" in error for error in errors))

    def test_required_answer_coverage_reaches_abstract(self) -> None:
        model = {
            "questions": [{"question_id": "q1", "outputs": ["optimal_cost"], "required_answer": required_answer()}],
            "models": [{"model_id": "M1", "question_id": "q1", "outputs": ["optimal_cost"]}],
        }
        frozen = {
            "results": [{
                "result_id": "R1",
                "question_id": "q1",
                "name": "optimal_cost",
                "display_value": "123.45",
                "unit": "CNY",
            }]
        }
        plan = {
            "abstract_results": [{
                "result_id": "R1",
                "question_id": "q1",
                "method_ids": ["M1"],
                "validation_ids": ["V1"],
                "abstract_span": "optimal cost is 123.45 CNY",
                "fact_check": {
                    "status": "passed",
                    "checked_fields": ["question_id", "model_identity", "display_value", "unit", "boundary"],
                    "source_ids": ["R1"],
                },
            }],
            "figures": [],
        }
        errors, _, details = evaluate_required_answer_coverage(
            model, plan, frozen, abstract_text="The optimal cost is 123.45 CNY.", require=True
        )
        self.assertEqual(errors, [])
        self.assertEqual(details["questions"]["q1"]["matched_result_ids"], ["R1"])

        plan["abstract_results"][0]["fact_check"]["status"] = "needs_revision"
        errors, _, _ = evaluate_required_answer_coverage(
            model, plan, frozen, abstract_text="The optimal cost is 123.45 CNY.", require=True
        )
        self.assertTrue(any("passed fact_check" in error for error in errors))

    def test_figure_failure_cards_distinguish_advisory_and_error(self) -> None:
        unordered = {
            "figures": [{
                "figure_id": "F1",
                "kind": "data",
                "data_shape": "unordered_categories",
                "argument_intent": "comparison",
                "message": "compare categories",
                "visual_encoding": "line chart",
            }]
        }
        errors, _, _ = evaluate_figure_semantics(unordered)
        self.assertTrue(any("unordered categories" in error for error in errors))

        small_sample = {
            "figures": [{
                "figure_id": "F2",
                "kind": "data",
                "data_shape": "distribution",
                "argument_intent": "distribution",
                "sample_regime": {"n_total": 8},
                "message": "show observations",
                "visual_encoding": "violin plot",
            }]
        }
        errors, issues, _ = evaluate_figure_semantics(small_sample)
        self.assertEqual(errors, [])
        self.assertTrue(any(item["card"] == "small_sample_distribution_overclaim" for item in issues))

        correlation = {
            "figures": [{
                "figure_id": "F3",
                "kind": "data",
                "data_shape": "correlation_matrix",
                "argument_intent": "mechanism",
                "message": "causal mechanism",
                "visual_encoding": "heatmap",
            }]
        }
        errors, _, _ = evaluate_figure_semantics(correlation)
        self.assertTrue(any("correlation heatmap" in error for error in errors))

        low_dpi = {
            "figures": [{
                "figure_id": "F4",
                "kind": "data",
                "data_shape": "comparison",
                "argument_intent": "comparison",
                "message": "compare results",
                "visual_encoding": "dot plot",
                "final_size_qa": {
                    "raster_dpi": 200,
                    "readability": "pass",
                    "cropping": "pass",
                },
            }]
        }
        errors, _, _ = evaluate_figure_semantics(low_dpi)
        self.assertTrue(any("raster_dpi" in error for error in errors))

    def test_terminology_semantic_conflict_is_detected(self) -> None:
        model = {"terminology": [{"canonical": "profit", "semantic_id": "money", "canonical_en": "profit", "symbol": "P", "unit": "CNY"}]}
        plan = {"terminology": [{"canonical": "revenue", "semantic_id": "money", "canonical_en": "revenue", "symbol": "P", "unit": "CNY"}]}
        errors, details = evaluate_terminology_consistency(model, plan, {"abstract": "profit"})
        self.assertTrue(any("conflicting canonical_en" in error for error in errors))
        self.assertEqual(details["semantic_terms"], 1)

    def test_presentation_completeness_is_soft_and_explicit(self) -> None:
        plan = {
            "sections": [{"purpose": "problem analysis", "claim_ids": []}],
            "argument_units": [{
                "rhetorical_role": "problem_tension",
                "equation_ids": [],
                "math_locators": [],
            }],
            "terminology": [],
            "readiness": {"question_coverage": [{
                "question_id": "q1",
                "formulation_unit_ids": ["A"],
                "result_unit_ids": ["B"],
                "validation_unit_ids": ["C"],
                "interpretation_unit_ids": ["D"],
            }]},
        }
        report = presentation_completeness(plan)
        self.assertEqual(report["checks"]["problem_analysis"]["status"], "RECOMMENDED")
        self.assertEqual(report["checks"]["model_evaluation"]["status"], "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
