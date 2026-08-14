"""Regression tests for the private-competition P0 upgrades.

Each test maps to a real failure pattern from the competition roadmap:
T2 model identity drift, T3 unit scale drift, T5 unsupported correlation,
T6 Cholesky without PSD, T7 ambiguous CVaR, T8 unsupported global optimum,
plus assumption forks, typed parameter provenance, and the derived result engine.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import hashlib
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from qa.validate_contracts import _validate_document  # noqa: E402
from qa.check_math_writing import evaluate_math_writing  # noqa: E402
from test_p0_harness import P0HarnessTest, file_ref, read_json, write_json  # noqa: E402

MODEL_SCHEMA = ROOT / "schemas" / "model_contract.schema.json"


def base_contract() -> dict[str, Any]:
    return {
        "schema_version": "1.3",
        "project_id": "demo",
        "run_id": "run-1",
        "unit_system": "SI",
        "questions": [
            {"question_id": "q1", "task": "minimize cost", "conclusion_type": "numeric optimum", "inputs": ["demand"], "outputs": ["cost"]}
        ],
        "data_sources": [
            {
                "data_id": "demand",
                "path": "input.json",
                "read_only": True,
                "origin": "contest attachment",
                "license_or_terms": "competition use",
                "transformations": [],
                "quality_checks": ["range check"],
            }
        ],
        "assumptions": [
            {"assumption_id": "A1", "text": "demand fixed", "basis": "problem statement", "sensitivity_plan": "+/-10%"}
        ],
        "models": [
            {
                "model_id": "M1",
                "question_id": "q1",
                "name": "baseline optimization",
                "problem_type": "optimization",
                "characteristics": ["deterministic"],
                "rationale": "matches the stated objective",
                "variables": [
                    {"symbol": "x", "meaning": "production", "unit": "item", "domain": "x >= 0", "role": "decision"}
                ],
                "objective": "minimize total cost",
                "constraints": [{"constraint_id": "C1", "expression": "x >= 0", "meaning": "non-negative"}],
                "algorithm": "enumeration",
                "inputs": ["demand"],
                "outputs": ["cost"],
                "validation": [{"check_id": "V1", "stage": "both", "method": "check constraints", "acceptance": "zero violation"}],
                "validation_obligations": [
                    {
                        "obligation_id": "VAL-FEASIBILITY",
                        "category": "feasibility",
                        "method": "recompute all constraints",
                        "acceptance": {"left_metric_id": "max_violation", "operator": "<=", "right": {"kind": "literal", "value": 0}, "unit": "item"},
                        "required_stage": "both",
                    }
                ],
                "risks": ["fixed demand"],
                "fallback": "best feasible solution",
                "plan_details": {
                    "selected_candidate_id": "CM-LP",
                    "mechanism": "minimize additive cost over the feasible region",
                    "equation_plan": [
                        {"equation_id": "EQ-OBJ", "purpose": "objective", "expression_or_derivation": "min C(x)", "variables": ["x"], "assumptions": ["additive cost"]}
                    ],
                    "parameter_plan": [
                        {
                            "parameter": "demand",
                            "provenance": {"type": "GIVEN", "source_locator": "contest attachment demand column"},
                            "unit": "item",
                            "uncertainty_or_range": "+/-10%",
                        }
                    ],
                    "implementation_steps": ["load data", "solve", "recompute"],
                    "output_artifacts": ["raw_results.json"],
                    "validation_strategy": ["feasibility"],
                    "failure_modes": ["demand misspecified"],
                },
            }
        ],
        "terminology": [],
        "status": "ready",
    }


class CompetitionUpgradeTest(unittest.TestCase):
    def run_script(self, script: str, *args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
        import os
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), *args],
            cwd=cwd or ROOT,
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            check=False,
        )

    def run_semantics(self, project: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return self.run_script(
            "qa/check_math_semantics.py",
            "--project-root", str(project),
            "--model-contract", "model_contract.json",
            *extra,
        )

    def write_contract(self, project: Path, contract: dict[str, Any]) -> Path:
        path = project / "model_contract.json"
        write_json(path, contract)
        return path

    def validate_contract_schema(self, path: Path) -> list[str]:
        _, errors, _ = _validate_document(path, MODEL_SCHEMA)
        return errors

    # --- typed parameter provenance -------------------------------------

    def test_provenance_free_text_source_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-provenance-") as temp:
            project = Path(temp)
            contract = base_contract()
            contract["models"][0]["plan_details"]["parameter_plan"] = [
                {"parameter": "demand", "source_or_estimator": "contest attachment", "unit": "item", "uncertainty_or_range": "+/-10%"}
            ]
            errors = self.validate_contract_schema(self.write_contract(project, contract))
            self.assertTrue(errors, "free-text source_or_estimator must be rejected")
            self.assertTrue(any("provenance" in error for error in errors))

    def test_provenance_type_specific_obligations(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-provenance-") as temp:
            project = Path(temp)
            contract = base_contract()
            contract["models"][0]["plan_details"]["parameter_plan"] = [
                {"parameter": "rho", "provenance": {"type": "ESTIMATED", "estimator": "sample correlation"}, "unit": "correlation", "uncertainty_or_range": "unknown"}
            ]
            errors = self.validate_contract_schema(self.write_contract(project, contract))
            self.assertTrue(errors, "ESTIMATED without sample_scope/uncertainty must fail")
            contract["models"][0]["plan_details"]["parameter_plan"] = [
                {
                    "parameter": "rho",
                    "provenance": {"type": "ESTIMATED", "estimator": "sample correlation", "sample_scope": "2020-2024 monthly", "uncertainty": "Fisher CI"},
                    "unit": "correlation",
                    "uncertainty_or_range": "[-0.5, -0.2]",
                }
            ]
            errors = self.validate_contract_schema(self.write_contract(project, contract))
            self.assertEqual(errors, [])

    # --- assumption fork --------------------------------------------------

    def test_unresolved_fork_requires_risk_record(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-fork-") as temp:
            project = Path(temp)
            contract = base_contract()
            contract["assumption_forks"] = [
                {
                    "fork_id": "AF-01",
                    "phrase": "absorb ratio",
                    "question_id": "q1",
                    "interpretations": [
                        {"id": "A", "meaning": "historical average", "mathematical_effect": "descriptive only"},
                        {"id": "B", "meaning": "hourly hard cap", "mathematical_effect": "R_t <= rho * R_available_t"},
                    ],
                    "checks": ["problem wording"],
                }
            ]
            self.write_contract(project, contract)
            result = self.run_semantics(project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unresolved_risk", result.stdout)

    def test_unresolved_fork_must_surface_in_research_or_decision(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-fork-") as temp:
            project = Path(temp)
            contract = base_contract()
            contract["assumption_forks"] = [
                {
                    "fork_id": "AF-01",
                    "phrase": "absorb ratio",
                    "question_id": "q1",
                    "interpretations": [
                        {"id": "A", "meaning": "historical average", "mathematical_effect": "descriptive only"},
                        {"id": "B", "meaning": "hourly hard cap", "mathematical_effect": "hard constraint"},
                    ],
                    "checks": ["problem wording"],
                    "unresolved_risk": "choice changes all downstream answers",
                }
            ]
            self.write_contract(project, contract)
            result = self.run_semantics(project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("surface it", result.stdout)
            contract["research_basis"] = {"status": "draft", "research_questions": [], "searches": [], "candidate_models": [], "decisions": [], "unresolved_questions": ["AF-01 absorb ratio unresolved"]}
            self.write_contract(project, contract)
            result = self.run_semantics(project)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_resolved_fork_passes_with_reason(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-fork-") as temp:
            project = Path(temp)
            contract = base_contract()
            contract["assumption_forks"] = [
                {
                    "fork_id": "AF-01",
                    "phrase": "absorb ratio",
                    "question_id": "q1",
                    "interpretations": [
                        {"id": "A", "meaning": "historical average", "mathematical_effect": "descriptive only"},
                        {"id": "B", "meaning": "hourly hard cap", "mathematical_effect": "hard constraint"},
                    ],
                    "checks": ["problem wording", "attachment semantics"],
                    "selected": "A",
                    "selection_reason": "no hourly-cap wording and no capacity column in the attachment",
                }
            ]
            self.write_contract(project, contract)
            result = self.run_semantics(project)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- T7 ambiguous CVaR -------------------------------------------------

    def cvar_model(self) -> dict[str, Any]:
        model = base_contract()["models"][0]
        model["name"] = "Mean-CVaR planning model"
        model["objective"] = "minimize CVaR of loss minus expected profit"
        return model

    def test_cvar_requires_risk_semantics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-cvar-") as temp:
            project = Path(temp)
            contract = base_contract()
            contract["models"][0] = self.cvar_model()
            self.write_contract(project, contract)
            result = self.run_semantics(project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("risk_semantics", result.stdout)

    def test_cvar_wrong_direction_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-cvar-") as temp:
            project = Path(temp)
            contract = base_contract()
            model = self.cvar_model()
            model["risk_semantics"] = {"random_variable": "loss", "tail": "upper", "confidence_level": 0.95, "objective_direction": "maximize"}
            contract["models"][0] = model
            self.write_contract(project, contract)
            result = self.run_semantics(project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("minimize", result.stdout)

    def test_cvar_declared_semantics_pass(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-cvar-") as temp:
            project = Path(temp)
            contract = base_contract()
            model = self.cvar_model()
            model["risk_semantics"] = {"random_variable": "loss", "tail": "upper", "confidence_level": 0.95, "objective_direction": "minimize"}
            model["identity"] = {
                "canonical_name": "Mean-CVaR stochastic optimization",
                "mathematical_class": "risk-averse stochastic programming",
                "objective_form": "min lambda * CVaR_alpha(loss) - E[profit]",
                "forbidden_aliases": ["Mean-Variance"],
                "defining_equations": ["EQ-OBJ"],
            }
            contract["models"][0] = model
            self.write_contract(project, contract)
            result = self.run_semantics(project)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- T5 / T6 correlation and Cholesky ----------------------------------

    def test_correlated_inputs_require_spec(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-corr-") as temp:
            project = Path(temp)
            contract = base_contract()
            contract["models"][0]["characteristics"] = ["stochastic", "correlated_inputs"]
            self.write_contract(project, contract)
            result = self.run_semantics(project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("correlation_spec", result.stdout)

    def test_cholesky_requires_positive_definite_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-chol-") as temp:
            project = Path(temp)
            contract = base_contract()
            model = contract["models"][0]
            model["algorithm"] = "scenario generation via Cholesky decomposition"
            model["characteristics"] = ["stochastic", "correlated_inputs"]
            model["correlation_spec"] = {
                "source": "estimated from attachment history",
                "sample_scope": "2020-2024",
                "dimension": 3,
                "min_eigenvalue": 0.0,
                "checks": {"in_unit_interval": True, "symmetric": True, "psd_verified": True},
            }
            self.write_contract(project, contract)
            result = self.run_semantics(project)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("positive definiteness", result.stdout)

    # --- T2 model identity drift -------------------------------------------

    def test_identity_alias_in_abstract_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-identity-") as temp:
            project = Path(temp)
            contract = base_contract()
            model = self.cvar_model()
            model["risk_semantics"] = {"random_variable": "loss", "tail": "upper", "confidence_level": 0.95, "objective_direction": "minimize"}
            model["identity"] = {
                "canonical_name": "Mean-CVaR stochastic optimization",
                "mathematical_class": "risk-averse stochastic programming",
                "objective_form": "min lambda * CVaR_alpha(loss) - E[profit]",
                "forbidden_aliases": ["Mean-Variance"],
            }
            contract["models"][0] = model
            self.write_contract(project, contract)
            (project / "abstract.txt").write_text("We build a Mean-Variance model.\n", encoding="utf-8")
            result = self.run_semantics(project, "--abstract", "abstract.txt")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("forbidden model alias", result.stdout)

    # --- T8 unsupported global optimum --------------------------------------

    def test_global_optimum_language_requires_gap_evidence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-optimum-") as temp:
            project = Path(temp)
            self.write_contract(project, base_contract())
            (project / "paper.tex").write_text("The solver reaches the global optimum.\n", encoding="utf-8")
            result = self.run_semantics(project, "--paper", "paper.tex")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("global-optimality", result.stdout)
            contract = base_contract()
            contract["models"][0]["validation_obligations"].append(
                {
                    "obligation_id": "VAL-GAP",
                    "category": "objective_recomputation",
                    "method": "solver optimality gap and best bound receipt",
                    "acceptance": {"left_metric_id": "mip_gap", "operator": "<=", "right": {"kind": "literal", "value": 0.0001}, "unit": "dimensionless"},
                    "required_stage": "full",
                }
            )
            self.write_contract(project, contract)
            result = self.run_semantics(project, "--paper", "paper.tex")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- T3 unit / scale drift ----------------------------------------------

    def frozen_with_scale(self, project: Path) -> None:
        write_json(
            project / "frozen_results.json",
            {
                "schema_version": "1.2",
                "run_id": "run-1",
                "status": "frozen",
                "validation_verdict": "PASS",
                "claimable": True,
                "results": [
                    {
                        "result_id": "R-COST",
                        "question_id": "q1",
                        "name": "total cost",
                        "value": 42350000,
                        "unit": "CNY",
                        "precision": 2,
                        "display_value": "42.35",
                        "display_label": "百万元",
                        "display_scale": 1000000,
                        "statistical_definition": "objective at optimum",
                        "boundary": "declared constraints",
                        "source_artifact": "raw.json",
                        "source_key": "R-COST",
                        "validation_status": "passed",
                        "claimable": True,
                    }
                ],
            },
        )

    def test_unit_scale_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-unit-") as temp:
            project = Path(temp)
            self.write_contract(project, base_contract())
            self.frozen_with_scale(project)
            (project / "abstract.txt").write_text("总成本为 42.35 万元。\n", encoding="utf-8")
            result = self.run_semantics(project, "--frozen-results", "frozen_results.json", "--abstract", "abstract.txt")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("百万元", result.stdout)

    def test_unit_scale_consistent_passes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-unit-") as temp:
            project = Path(temp)
            self.write_contract(project, base_contract())
            self.frozen_with_scale(project)
            (project / "abstract.txt").write_text("总成本为 42.35 百万元。\n", encoding="utf-8")
            result = self.run_semantics(project, "--frozen-results", "frozen_results.json", "--abstract", "abstract.txt")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- frozen value domain -------------------------------------------------

    def test_probability_result_out_of_domain(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-prob-") as temp:
            project = Path(temp)
            self.write_contract(project, base_contract())
            self.frozen_with_scale(project)
            frozen = read_json(project / "frozen_results.json")
            frozen["results"][0]["unit"] = "probability"
            frozen["results"][0]["value"] = 1.2
            write_json(project / "frozen_results.json", frozen)
            result = self.run_semantics(project, "--frozen-results", "frozen_results.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("probability", result.stdout)

    # --- derived result engine ------------------------------------------------

    def test_derived_results_engine_computes_reduction(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-derived-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            frozen = read_json(paths["frozen"])
            frozen["results"].append(
                {
                    "result_id": "R-Q1-BASE",
                    "question_id": "q1",
                    "name": "baseline cost",
                    "value": 129.0,
                    "unit": "CNY",
                    "precision": 2,
                    "display_value": "129.00",
                    "statistical_definition": "baseline objective",
                    "boundary": "same constraints",
                    "source_artifact": "raw_results.json",
                    "source_key": "R-Q1-BASE",
                    "validation_status": "passed",
                    "claimable": True,
                }
            )
            write_json(paths["frozen"], frozen)
            paths["evidence"].unlink()
            register = self.run_script(
                "register_evidence.py",
                "--project-root", str(project),
                "--frozen-results", "frozen_results.json",
                "--output", "evidence_registry.json",
            )
            self.assertEqual(register.returncode, 0, register.stdout + register.stderr)
            write_json(
                project / "derived_spec.json",
                {
                    "derivations": [
                        {
                            "derived_result_id": "DR-Q1-COST-REDUCTION",
                            "question_id": "q1",
                            "type": "relative_change",
                            "direction": "reduction",
                            "inputs": ["R-Q1-BASE", "R-Q1-01"],
                            "unit": "%",
                            "precision": 2,
                        }
                    ]
                },
            )
            derived = self.run_script(
                "derive_results.py",
                "--project-root", str(project),
                "--frozen-results", "frozen_results.json",
                "--spec", "derived_spec.json",
                "--output", "derived_results.json",
            )
            self.assertEqual(derived.returncode, 0, derived.stdout + derived.stderr)
            payload = read_json(project / "derived_results.json")
            row = payload["derived"][0]
            self.assertEqual(row["display_value"], "4.30")
            self.assertEqual(row["unit"], "%")
            self.assertNotIn("sha256", payload["frozen_results"])
            self.assertNotIn("spec_sha256", payload)
            submission_derived = self.run_script(
                "derive_results.py",
                "--project-root", str(project),
                "--frozen-results", "frozen_results.json",
                "--spec", "derived_spec.json",
                "--output", "derived_submission.json",
                "--integrity-mode", "submission",
            )
            self.assertEqual(submission_derived.returncode, 0, submission_derived.stdout + submission_derived.stderr)
            submission_payload = read_json(project / "derived_submission.json")
            self.assertIn("sha256", submission_payload["frozen_results"])
            self.assertIn("spec_sha256", submission_payload)
            consistency = self.run_script(
                "qa/check_consistency.py",
                "--project-root", str(project),
                "--paper-plan", "paper_plan.json",
                "--frozen-results", "frozen_results.json",
                "--evidence-registry", "evidence_registry.json",
                "--derived-results", "derived_results.json",
                "--abstract", "abstract.txt",
            )
            self.assertEqual(consistency.returncode, 0, consistency.stdout + consistency.stderr)
            tampered = read_json(project / "derived_results.json")
            tampered["frozen_results"]["sha256"] = "0" * 64
            write_json(project / "derived_results.json", tampered)
            stale = self.run_script(
                "qa/check_consistency.py",
                "--project-root", str(project),
                "--paper-plan", "paper_plan.json",
                "--frozen-results", "frozen_results.json",
                "--evidence-registry", "evidence_registry.json",
                "--derived-results", "derived_results.json",
                "--abstract", "abstract.txt",
            )
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("not computed from the supplied frozen_results", stale.stdout)

    def test_derived_results_reject_failed_run(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-derived-fail-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            frozen = read_json(paths["frozen"])
            frozen["claimable"] = False
            frozen["validation_verdict"] = "FAIL"
            write_json(paths["frozen"], frozen)
            write_json(
                project / "derived_spec.json",
                {"derivations": [{"derived_result_id": "DR-X", "question_id": "q1", "type": "ratio", "inputs": ["R-Q1-01", "R-Q1-01"], "unit": "dimensionless", "precision": 2}]},
            )
            result = self.run_script(
                "derive_results.py",
                "--project-root", str(project),
                "--frozen-results", "frozen_results.json",
                "--spec", "derived_spec.json",
                "--output", "derived_results.json",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL runs stay diagnostic only", result.stderr)

    # --- freeze-time scale coherence ------------------------------------------

    def test_freeze_binds_display_scale_to_display_value(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-scale-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            paths["frozen"].unlink()
            raw = read_json(paths["raw"])
            raw["results"][0].update({"value": 123450, "display_scale": 1000, "display_label": "kCNY", "display_value": "999.99"})
            write_json(paths["raw"], raw)
            bad = self.run_script(
                "freeze_results.py",
                "--project-root", str(project),
                "--source", "raw_results.json",
                "--output", "frozen_results.json",
                "--run-id", "demo-run",
                "--model-contract", "model_contract.json",
                "--command", "python model.py --seed 7",
                "--seed", "7",
                "--input", "input.json",
                "--code", "model.py",
                "--validation", "full_validation.json",
            )
            self.assertNotEqual(bad.returncode, 0)
            self.assertIn("canonical rounded value", bad.stderr)
            raw["results"][0]["display_value"] = "123.45"
            write_json(paths["raw"], raw)
            good = self.run_script(
                "freeze_results.py",
                "--project-root", str(project),
                "--source", "raw_results.json",
                "--output", "frozen_results.json",
                "--run-id", "demo-run",
                "--model-contract", "model_contract.json",
                "--command", "python model.py --seed 7",
                "--seed", "7",
                "--input", "input.json",
                "--code", "model.py",
                "--validation", "full_validation.json",
            )
            self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
            frozen = read_json(paths["frozen"])
            self.assertEqual(frozen["results"][0]["display_value"], "123.45")
            self.assertEqual(frozen["results"][0]["display_scale"], 1000)

    def test_modeling_plan_enforces_contract_semantics(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-m1-semantics-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            model = read_json(paths["model"])
            model["models"][0]["name"] = "Mean-CVaR planning model"
            write_json(paths["model"], model)
            result = self.run_script(
                "qa/check_modeling_plan.py",
                "--project-root", str(project),
                "--model-contract", paths["model"].name,
                "--evidence-registry", paths["evidence"].name,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("risk_semantics", result.stdout)
            self.assertIn("identity", result.stdout)

    def test_modeling_plan_requires_provenance_for_every_model_input(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-provenance-coverage-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            model = read_json(paths["model"])
            model["models"][0]["plan_details"]["parameter_plan"] = []
            write_json(paths["model"], model)
            result = self.run_script(
                "qa/check_modeling_plan.py",
                "--project-root", str(project),
                "--model-contract", paths["model"].name,
                "--evidence-registry", paths["evidence"].name,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("lack typed parameter provenance", result.stdout)

    def test_formal_modeling_plan_rejects_unbound_external_search(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-m1-formal-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            model = read_json(paths["model"])
            next(search for search in model["research_basis"]["searches"] if search["source"] == "openalex").pop("evidence_ids", None)
            write_json(paths["model"], model)
            result = self.run_script(
                "qa/check_modeling_plan.py",
                "--project-root", str(project),
                "--model-contract", paths["model"].name,
                "--evidence-registry", paths["evidence"].name,
                "--formal", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must bind evidence_ids", result.stdout)

    def test_writer_requires_derived_artifact_when_plan_references_one(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-derived-binding-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            plan = read_json(paths["plan"])
            plan["claims"][0]["derived_result_ids"] = ["DR-MISSING"]
            write_json(paths["plan"], plan)
            result = self.run_script(
                "claims/compile_writer_package.py",
                "--project-root", str(project),
                "--paper-plan", paths["plan"].name,
                "--frozen-results", paths["frozen"].name,
                "--evidence-registry", paths["evidence"].name,
                "--output", "writer_package.json",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("derived_result_ids", result.stderr)

    def test_first_draft_coverage_rejects_a_short_argument_span(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-first-draft-coverage-") as temp:
            project = Path(temp)
            package = {
                "schema_version": "1.0",
                "claims": [],
                "draft_coverage": {
                    "status": "planned",
                    "anchors": [{
                        "anchor_id": "FORMULATION",
                        "unit_id": "AU-FORM",
                        "question_id": "q1",
                        "patterns": ["[[FORMULATION]]"],
                        "minimum_words": 20,
                    }],
                },
            }
            write_json(project / "writer_package.json", package)
            draft = project / "draft.txt"
            draft.write_text("[[FORMULATION]] too short.", encoding="utf-8")
            result = self.run_script(
                "qa/check_writer_package.py", "--project-root", str(project),
                "--writer-package", "writer_package.json", "--draft", "draft.txt",
                "--require-first-draft-coverage", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("minimum_words", result.stdout)
            draft.write_text(
                "[[FORMULATION]] 明确变量、单位、目标函数、约束条件、可行域、算法、实现步骤、独立验证、诊断方法、假设与结论边界。",
                encoding="utf-8",
            )
            passed = self.run_script(
                "qa/check_writer_package.py", "--project-root", str(project),
                "--writer-package", "writer_package.json", "--draft", "draft.txt",
                "--require-first-draft-coverage", "--strict",
            )
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)
            self.assertIn('"first_draft_coverage_verified": true', passed.stdout)

    def test_failure_evidence_compiler_and_checker_preserve_diagnostic_only_status(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-failure-evidence-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            failed_report = harness.make_peak_failure(project, paths, "failure_validation.json")
            raw = read_json(paths["raw"])
            raw["results"][0]["validation_status"] = "failed"
            write_json(paths["raw"], raw)
            frozen = project / "failed_frozen.json"
            freeze = self.run_script(
                "freeze_results.py", "--project-root", str(project),
                "--source", paths["raw"].name, "--output", frozen.name,
                "--run-id", "demo-run", "--model-contract", paths["model"].name,
                "--command", "python model.py", "--code", paths["code"].name,
                "--validation", failed_report.name,
            )
            self.assertEqual(freeze.returncode, 0, freeze.stdout + freeze.stderr)
            compile_result = self.run_script(
                "validation/compile_failure_evidence.py", "--project-root", str(project),
                "--frozen-results", frozen.name, "--model-contract", paths["model"].name,
                "--output", "failure_evidence.json",
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
            check = self.run_script(
                "qa/check_failure_evidence.py", "--project-root", str(project),
                "--artifact", "failure_evidence.json", "--frozen-results", frozen.name,
                "--run-id", "demo-run", "--strict",
            )
            self.assertEqual(check.returncode, 0, check.stdout + check.stderr)
            evidence = read_json(project / "failure_evidence.json")
            self.assertEqual(evidence["status"], "diagnostic")
            self.assertTrue(all(row["claimable"] is False for row in evidence["diagnostic_claims"]))

    def test_failed_p2_requires_diagnostic_artifact_in_gate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-failed-p2-gate-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            failed_report = harness.make_peak_failure(project, paths, "failure_validation.json")
            raw = read_json(paths["raw"])
            raw["results"][0]["validation_status"] = "failed"
            write_json(paths["raw"], raw)
            failed_frozen = project / "failed_frozen.json"
            freeze = self.run_script(
                "freeze_results.py", "--project-root", str(project),
                "--source", paths["raw"].name, "--output", failed_frozen.name,
                "--run-id", "demo-run", "--model-contract", paths["model"].name,
                "--command", "python model.py", "--code", paths["code"].name,
                "--validation", failed_report.name,
            )
            self.assertEqual(freeze.returncode, 0, freeze.stdout + freeze.stderr)
            manifest = read_json(paths["manifest"])
            manifest["model_contract"] = file_ref(paths["model"])
            for artifact in manifest["artifacts"]:
                if artifact.get("role") == "frozen_results":
                    artifact.update({**file_ref(failed_frozen), "role": "frozen_results"})
            manifest["gates"]["p2"]["status"] = "fail"
            manifest["gates"]["w1"]["status"] = "pending"
            manifest["gates"]["w2"]["status"] = "pending"
            manifest["gates"]["s1"]["status"] = "pending"
            manifest["status"] = "active"
            manifest["phase"] = "results"
            next(row for row in manifest["human_checkpoints"] if row["stage"] == "m1")["artifacts"][0] = file_ref(paths["model"])
            write_json(paths["manifest"], manifest)
            missing = self.run_script(
                "qa/check_gates.py", "--project-root", str(project),
                "--manifest", paths["manifest"].name, "--strict",
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("failure_evidence", missing.stdout)
            compile_result = self.run_script(
                "validation/compile_failure_evidence.py", "--project-root", str(project),
                "--frozen-results", failed_frozen.name, "--model-contract", paths["model"].name,
                "--output", "failure_evidence.json",
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stdout + compile_result.stderr)
            manifest["artifacts"].append({**file_ref(project / "failure_evidence.json"), "role": "failure_evidence"})
            write_json(paths["manifest"], manifest)
            passed = self.run_script(
                "qa/check_gates.py", "--project-root", str(project),
                "--manifest", paths["manifest"].name, "--strict",
            )
            self.assertEqual(passed.returncode, 0, passed.stdout + passed.stderr)

    def test_sensitivity_experiment_requires_receipt_for_each_grid_value(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-sensitivity-artifact-") as temp:
            project = Path(temp)
            for name in ("run_02.json", "run_05.json", "sensitivity.csv"):
                (project / name).write_text(name + "\n", encoding="utf-8")
            experiment = {
                "schema_version": "1.0", "experiment_id": "SENS-01", "run_id": "run-1", "question_id": "q1",
                "status": "completed", "parameter": "lambda", "baseline": 0.5, "grid": [0.2, 0.5],
                "rerun_policy": "full_reoptimization",
                "metrics": [{"metric_id": "solution_similarity", "unit": "%", "definition": "share of matching decisions", "similarity_definition": "1 - normalized L1 distance"}],
                "results_artifact": {"path": "sensitivity.csv"},
                "runs": [{"grid_value": 0.2, "status": "PASS", "artifact": {"path": "run_02.json"}}, {"grid_value": 0.5, "status": "PASS", "artifact": {"path": "run_05.json"}}],
                "generated_at": "2026-08-13T00:00:00Z",
            }
            write_json(project / "sensitivity.json", experiment)
            result = self.run_script(
                "qa/check_sensitivity_experiment.py", "--project-root", str(project),
                "--experiment", "sensitivity.json", "--run-id", "run-1", "--strict",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            experiment["runs"] = experiment["runs"][:1]
            write_json(project / "sensitivity.json", experiment)
            result = self.run_script(
                "qa/check_sensitivity_experiment.py", "--project-root", str(project),
                "--experiment", "sensitivity.json", "--run-id", "run-1", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("grid values and run receipts differ", result.stdout)

    def test_oos_artifact_requires_disjoint_scenario_identity(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-oos-artifact-") as temp:
            project = Path(temp)
            (project / "metrics.json").write_text("{}\n", encoding="utf-8")
            def digest(value: str) -> str:
                return hashlib.sha256(value.encode("utf-8")).hexdigest()
            artifact = {
                "schema_version": "1.0", "oos_id": "OOS-01", "run_id": "run-1", "question_id": "q1", "status": "verified",
                "split_rule": "time boundary 2024-01-01", "train_scenarios": {"seed": 1, "hash": digest("train"), "count": 10, "source": "train.json"},
                "test_scenarios": {"seed": 2, "hash": digest("test"), "count": 5, "source": "test.json"},
                "disjoint_check": "PASS", "leakage_check": "PASS", "metrics_artifact": {"path": "metrics.json"},
                "generated_at": "2026-08-13T00:00:00Z",
            }
            write_json(project / "oos.json", artifact)
            result = self.run_script(
                "qa/check_oos_artifact.py", "--project-root", str(project),
                "--artifact", "oos.json", "--run-id", "run-1", "--strict",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            artifact["test_scenarios"]["seed"] = 1
            write_json(project / "oos.json", artifact)
            result = self.run_script(
                "qa/check_oos_artifact.py", "--project-root", str(project),
                "--artifact", "oos.json", "--run-id", "run-1", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("seed", result.stdout)

    def test_figure_reference_role_must_match_semantic_type(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-figure-binding-") as temp:
            project = Path(temp)
            harness = P0HarnessTest()
            paths = harness.build_fixture(project)
            plan = read_json(paths["plan"])
            plan["figures"] = [{
                "figure_id": "FIG-01", "kind": "data", "semantic_type": "sensitivity",
                "claim_ids": ["C1"], "evidence_ids": ["E-R-Q1-01"], "purpose": "show result change",
                "why_figure": "a curve is more informative than a table", "message": "sensitivity changes the result",
                "comparison": "baseline versus perturbation", "visual_encoding": "line", "selection_rule": "all grid values",
                "data_artifacts": ["raw_results.json"], "panel_map": {"A": "sensitivity"},
                "statistical_definition": "frozen result by grid value", "paper_location": "results.q1",
                "caption_claim": "sensitivity result", "accessibility": {"grayscale_safe": True, "colorblind_safe": True, "dual_axis": False, "dual_axis_justification": None},
                "qa_status": "pending",
            }]
            plan["figure_references"] = [{"reference_id": "REF-01", "figure_id": "FIG-01", "reference_role": "methodology_overview", "section_id": "results.q1"}]
            write_json(paths["plan"], plan)
            result = self.run_script(
                "qa/check_consistency.py", "--project-root", str(project),
                "--paper-plan", paths["plan"].name, "--frozen-results", paths["frozen"].name,
                "--evidence-registry", paths["evidence"].name, "--abstract", paths["abstract"].name, "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not match", result.stdout)
            plan["figures"][0]["semantic_type"] = "result_comparison"
            plan["figure_references"] = []
            write_json(paths["plan"], plan)
            validate = harness.validate_fixture(project)
            self.assertNotEqual(validate.returncode, 0)
            self.assertIn("without semantic references", validate.stdout)

    def test_math_writing_binds_formula_validation_and_forward_logic(self) -> None:
        contract = base_contract()
        units = [
            {
                "unit_id": "AU-Q1-MODEL", "section_id": "results.q1", "rhetorical_role": "model_choice",
                "claim_ids": ["C1"], "evidence_ids": ["E-CITE-PLAN"], "prerequisite_unit_ids": [],
                "model_ids": ["M1"], "math_locators": ["MODEL-M1"],
                "expected_reader_judgment": "The selected model fits the mechanism.",
                "boundary": "Fixed demand.", "target_words": 70,
            },
            {
                "unit_id": "AU-Q1-FORM", "section_id": "results.q1", "rhetorical_role": "mechanism_derivation",
                "claim_ids": ["C1"], "evidence_ids": ["E-CITE-PLAN"], "prerequisite_unit_ids": ["AU-Q1-MODEL"],
                "model_ids": ["M1"], "equation_ids": ["EQ-OBJ"], "constraint_ids": ["C1"],
                "math_locators": ["EQ-OBJ"], "expected_reader_judgment": "The equation and feasible region are explicit.",
                "boundary": "Additive cost.", "target_words": 80,
            },
            {
                "unit_id": "AU-Q1-RESULT", "section_id": "results.q1", "rhetorical_role": "result_observation",
                "claim_ids": ["C1"], "evidence_ids": ["E-R-Q1-01"], "prerequisite_unit_ids": ["AU-Q1-FORM"],
                "result_ids": ["R-Q1-01"], "math_locators": ["RESULT-R-Q1-01"],
                "expected_reader_judgment": "The reported value is frozen.", "boundary": "Frozen run.", "target_words": 70,
            },
            {
                "unit_id": "AU-Q1-VALID", "section_id": "results.q1", "rhetorical_role": "validation",
                "claim_ids": ["C1"], "evidence_ids": ["E-R-Q1-01"], "prerequisite_unit_ids": ["AU-Q1-RESULT"],
                "model_ids": ["M1"], "validation_obligation_ids": ["VAL-FEASIBILITY"],
                "math_locators": ["VAL-FEASIBILITY"], "expected_reader_judgment": "Feasibility was independently checked.",
                "boundary": "Declared constraints.", "target_words": 70,
            },
            {
                "unit_id": "AU-Q1-BOUNDARY", "section_id": "results.q1", "rhetorical_role": "boundary",
                "claim_ids": ["C1"], "evidence_ids": ["E-R-Q1-01"], "prerequisite_unit_ids": ["AU-Q1-VALID"],
                "math_locators": ["BOUNDARY-Q1"], "expected_reader_judgment": "The conclusion is not extrapolated.",
                "boundary": "No stochastic-demand claim.", "target_words": 70,
            },
        ]
        plan = {
            "claims": [{"claim_id": "C1", "question_id": "q1"}],
            "argument_units": units,
            "readiness": {"question_coverage": [{
                "question_id": "q1", "formulation_unit_ids": ["AU-Q1-MODEL", "AU-Q1-FORM"],
                "result_unit_ids": ["AU-Q1-RESULT"], "validation_unit_ids": ["AU-Q1-VALID"],
                "interpretation_unit_ids": ["AU-Q1-BOUNDARY"],
            }]},
        }
        frozen = {
            "claimable": True, "validation_verdict": "PASS",
            "results": [{"result_id": "R-Q1-01", "question_id": "q1", "validation_status": "passed", "claimable": True}],
            "validation_obligations": [{"obligation_id": "VAL-FEASIBILITY", "status": "PASS"}],
        }
        package = {"schema_version": "1.0", "argument_units": deepcopy(units)}
        draft = "MODEL-M1\nEQ-OBJ\nC1\nRESULT-R-Q1-01\nVAL-FEASIBILITY\nBOUNDARY-Q1"
        errors, warnings, details = evaluate_math_writing(
            contract, plan, draft, frozen=frozen, writer_package=package, require_coverage=True,
        )
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])
        self.assertEqual(details["algebra_proof"], "not_automated_manual_w2_required")

    def test_math_writing_rejects_cycle_and_missing_formula_locator(self) -> None:
        contract = base_contract()
        plan = {
            "claims": [{"claim_id": "C1", "question_id": "q1"}],
            "argument_units": [
                {
                    "unit_id": "U-FORM", "rhetorical_role": "mechanism_derivation", "claim_ids": ["C1"],
                    "model_ids": ["M1"], "equation_ids": ["EQ-OBJ"], "constraint_ids": ["C1"],
                    "evidence_ids": [], "prerequisite_unit_ids": [], "math_locators": ["MISSING"],
                },
                {
                    "unit_id": "U-RESULT", "rhetorical_role": "result_observation", "claim_ids": ["C1"],
                    "result_ids": ["R-Q1-01"], "evidence_ids": [], "prerequisite_unit_ids": ["U-FORM"],
                    "math_locators": ["RESULT"],
                },
                {
                    "unit_id": "U-VALID", "rhetorical_role": "validation", "claim_ids": ["C1"],
                    "model_ids": ["M1"], "validation_obligation_ids": ["VAL-FEASIBILITY"],
                    "evidence_ids": [], "prerequisite_unit_ids": ["U-RESULT"], "math_locators": ["VALID"],
                },
            ],
            "readiness": {"question_coverage": [{
                "question_id": "q1", "formulation_unit_ids": ["U-FORM"], "result_unit_ids": ["U-RESULT"],
                "validation_unit_ids": ["U-VALID"], "interpretation_unit_ids": [],
            }]},
        }
        plan["argument_units"][0]["prerequisite_unit_ids"] = ["U-VALID"]
        frozen = {
            "claimable": True, "validation_verdict": "PASS",
            "results": [{"result_id": "R-Q1-01", "question_id": "q1", "validation_status": "passed", "claimable": True}],
            "validation_obligations": [{"obligation_id": "VAL-FEASIBILITY", "status": "PASS"}],
        }
        package = {"schema_version": "1.0", "argument_units": deepcopy(plan["argument_units"])}
        errors, _, _ = evaluate_math_writing(
            contract, plan, "EQ-OBJ C1 RESULT VALID", frozen=frozen,
            writer_package=package, require_coverage=True,
        )
        self.assertTrue(any("cycle" in error for error in errors))
        self.assertTrue(any("missing math locator" in error for error in errors))

    def test_derivation_integrity_accepts_a_declared_objective_graph(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-derivation-graph-") as temp:
            project = Path(temp)
            contract = base_contract()
            equation = contract["models"][0]["plan_details"]["equation_plan"][0]
            equation.update({
                "equation_type": "objective", "math_risk": "low", "inputs": ["x"], "outputs": ["cost"],
                "symbols": ["x"], "domains": {"x": "x >= 0"}, "unit_signature": "CNY",
                "verification": {"symbol_check": "PASS", "domain_check": "PASS", "unit_check": "PASS"},
            })
            contract["models"][0]["plan_details"]["derivation_graph"] = {
                "nodes": [{"id": "EQ-OBJ", "equation_id": "EQ-OBJ", "type": "objective", "inputs": ["x"], "outputs": ["cost"]}],
                "edges": [], "source_node_ids": ["EQ-OBJ"], "terminal_node_ids": ["EQ-OBJ"],
            }
            self.write_contract(project, contract)
            result = self.run_script(
                "qa/check_derivation_integrity.py", "--project-root", str(project),
                "--model-contract", "model_contract.json", "--require-metadata", "--strict",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"math_validation_level": "L1_structural"', result.stdout)

    def test_derivation_integrity_rejects_undefined_intermediate(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-derivation-undefined-") as temp:
            project = Path(temp)
            contract = base_contract()
            equation = contract["models"][0]["plan_details"]["equation_plan"][0]
            equation.update({
                "equation_type": "objective", "math_risk": "medium", "inputs": ["missing_rate"], "outputs": ["cost"],
                "symbols": ["missing_rate"], "domains": {"missing_rate": ">=0"}, "unit_signature": "CNY",
                "verification": {"symbol_check": "PASS", "domain_check": "PASS", "unit_check": "PASS", "boundary_check": "PASS"},
            })
            contract["models"][0]["plan_details"]["derivation_graph"] = {
                "nodes": [{"id": "EQ-OBJ", "equation_id": "EQ-OBJ", "type": "objective", "inputs": ["missing_rate"], "outputs": ["cost"]}],
                "edges": [], "source_node_ids": ["EQ-OBJ"], "terminal_node_ids": ["EQ-OBJ"],
            }
            self.write_contract(project, contract)
            result = self.run_script(
                "qa/check_derivation_integrity.py", "--project-root", str(project),
                "--model-contract", "model_contract.json", "--require-metadata", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("UNDEFINED_SYMBOL", result.stdout)

    def test_derivation_integrity_rejects_empty_verification_object(self) -> None:
        with tempfile.TemporaryDirectory(prefix="math-derivation-empty-verification-") as temp:
            project = Path(temp)
            contract = base_contract()
            equation = contract["models"][0]["plan_details"]["equation_plan"][0]
            equation.update({
                "equation_type": "objective", "math_risk": "low", "inputs": ["x"], "outputs": ["cost"],
                "symbols": ["x"], "domains": {"x": "x >= 0"}, "unit_signature": "CNY",
                "verification": {},
            })
            contract["models"][0]["plan_details"]["derivation_graph"] = {
                "nodes": [{"id": "EQ-OBJ", "equation_id": "EQ-OBJ", "type": "objective", "inputs": ["x"], "outputs": ["cost"]}],
                "edges": [], "source_node_ids": ["EQ-OBJ"], "terminal_node_ids": ["EQ-OBJ"],
            }
            self.write_contract(project, contract)
            result = self.run_script(
                "qa/check_derivation_integrity.py", "--project-root", str(project),
                "--model-contract", "model_contract.json", "--require-metadata", "--strict",
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertTrue("minProperties" in result.stdout or "verification" in result.stdout)


if __name__ == "__main__":
    unittest.main()
