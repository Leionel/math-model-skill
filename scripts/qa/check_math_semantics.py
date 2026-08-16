#!/usr/bin/env python3
"""Finite mathematical semantic checks for high-frequency fatal contest errors.

This is deliberately NOT a general theorem prover. It only checks the small set
of mistakes that repeatedly kill real competition papers:

- assumption fork integrity (ambiguous wording must be resolved or marked);
- model identity drift (e.g. contract says Mean-CVaR, abstract says Mean-Variance);
- ambiguous CVaR semantics (profit/loss, tail, confidence, direction);
- unsupported correlation matrices (no provenance, not PSD, Cholesky without PD);
- unsupported global-optimum claims in paper text;
- probability/correlation results outside their mathematical domain;
- unit/scale drift between the frozen presentation contract and the paper.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402

CVAR_RE = re.compile(r"cvar|conditional\s+value\s+at\s+risk", re.IGNORECASE)
RISK_FAMILY_RE = re.compile(r"cvar|mean[- ]?variance|markowitz|conditional\s+value\s+at\s+risk", re.IGNORECASE)
CHOLESKY_RE = re.compile(r"cholesky", re.IGNORECASE)
OPTIMALITY_EVIDENCE_RE = re.compile(r"gap|bound|optimal", re.IGNORECASE)
GLOBAL_OPTIMUM_TOKENS = ("全局最优", "全局最优解", "global optimum", "global optimal", "globally optimal")
MONEY_SCALE_TOKENS = ("百万元", "千万元", "万元", "亿元", "元", "million_CNY", "CNY", "RMB")
PSD_TOLERANCE = -1e-9


def _model_text(model: dict[str, Any]) -> str:
    parts = [str(model.get("name", "")), str(model.get("objective", "")), str(model.get("algorithm", ""))]
    details = model.get("plan_details")
    if isinstance(details, dict):
        for equation in details.get("equation_plan", []):
            if isinstance(equation, dict):
                parts.append(str(equation.get("expression_or_derivation", "")))
    return "\n".join(parts)


def _check_objective_semantics(model: dict[str, Any], *, require: bool, errors: list[str]) -> None:
    model_id = str(model.get("model_id", ""))
    objective = model.get("objective_contract")
    optimization_like = model.get("problem_type") == "optimization" or "objective" in str(model.get("objective", "")).casefold()
    if not isinstance(objective, dict):
        if require and optimization_like:
            errors.append(f"model {model_id} requires objective_contract for formal mathematical QA")
        return
    if objective.get("equivalence_status") != "verified":
        errors.append(f"model {model_id} objective declared_form/implemented_form equivalence is not verified")
    if not str(objective.get("declared_form", "")).strip() or not str(objective.get("implemented_form", "")).strip():
        errors.append(f"model {model_id} objective contract must contain declared and implemented forms")
    if objective.get("uniqueness_claim") == "unique":
        diagnostics = objective.get("objective_diagnostics")
        if not isinstance(diagnostics, dict) or diagnostics.get("status") != "verified":
            errors.append(f"model {model_id} claims a unique optimum without a verified degeneracy diagnostic")
        elif diagnostics.get("candidate_count", 0) > 1 and diagnostics.get("objective_spread", 0) <= diagnostics.get("tolerance", 0):
            errors.append(f"model {model_id} claims a unique optimum although multiple tied candidates were diagnosed")
    diagnostics = objective.get("objective_diagnostics")
    if isinstance(diagnostics, dict) and diagnostics.get("candidate_count", 0) > 1 and objective.get("uniqueness_claim") == "unique":
        errors.append(f"model {model_id} uniqueness_claim conflicts with objective_diagnostics.candidate_count")
    partitions = objective.get("piecewise_partitions", [])
    if partitions:
        coverage = objective.get("piecewise_coverage")
        if not isinstance(coverage, dict):
            errors.append(f"model {model_id} piecewise objective requires piecewise_coverage")
        else:
            partition_ids = {str(row.get("partition_id")) for row in partitions if isinstance(row, dict)}
            declared_ids = set(coverage.get("partition_ids", []))
            if partition_ids != declared_ids:
                errors.append(f"model {model_id} piecewise coverage partition_ids do not match declared partitions")
            if coverage.get("coverage_status") != "verified" or coverage.get("overlap_status") != "verified":
                errors.append(f"model {model_id} piecewise domain coverage/overlap is not verified")
            for row in partitions:
                if isinstance(row, dict) and (row.get("status") != "verified" or row.get("boundary_status") not in {"verified", "not_applicable"}):
                    errors.append(f"model {model_id} piecewise partition {row.get('partition_id')} is not boundary-verified")
    identity = model.get("identity")
    if isinstance(identity, dict) and identity.get("composition_type") == "ensemble":
        composition_text = " ".join(str(part) for part in (model.get("algorithm", ""), model.get("rationale", ""), model.get("objective", ""))).casefold()
        if not any(token in composition_text for token in ("ensemble", "blend", "stack", "vote", "集成", "融合", "投票")):
            errors.append(f"model {model_id} is labeled ensemble but no ensemble composition is declared in its mechanism")


def evaluate_contract_semantics(contract: dict[str, Any], *, require_objective_contract: bool = False) -> tuple[list[str], list[str]]:
    """Contract-level semantic obligations; safe to run before any code exists."""

    errors: list[str] = []
    warnings: list[str] = []
    question_ids = {
        row.get("question_id")
        for row in contract.get("questions", [])
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }

    research = contract.get("research_basis") if isinstance(contract.get("research_basis"), dict) else {}
    unresolved_research = [str(item) for item in research.get("unresolved_questions", [])]
    unresolved_decision_risks: dict[str, list[str]] = {}
    for decision in research.get("decisions", []):
        if isinstance(decision, dict) and isinstance(decision.get("question_id"), str):
            unresolved_decision_risks[decision["question_id"]] = [
                str(item) for item in decision.get("unresolved_risks", [])
            ]

    fork_ids: set[str] = set()
    for fork in contract.get("assumption_forks", []):
        if not isinstance(fork, dict):
            errors.append("assumption_forks rows must be objects")
            continue
        fork_id = str(fork.get("fork_id", ""))
        if fork_id in fork_ids:
            errors.append(f"assumption fork {fork_id} is duplicated")
        fork_ids.add(fork_id)
        if fork.get("question_id") not in question_ids:
            errors.append(f"assumption fork {fork_id} references unknown question {fork.get('question_id')}")
        interpretations = [row for row in fork.get("interpretations", []) if isinstance(row, dict)]
        interpretation_ids = [str(row.get("id")) for row in interpretations]
        if len(interpretation_ids) != len(set(interpretation_ids)):
            errors.append(f"assumption fork {fork_id} has duplicate interpretation ids")
        selected = fork.get("selected")
        reason = str(fork.get("selection_reason", "")).strip()
        unresolved_risk = str(fork.get("unresolved_risk", "")).strip()
        if selected is not None:
            if selected not in interpretation_ids:
                errors.append(f"assumption fork {fork_id} selects unknown interpretation {selected!r}")
            if not reason:
                errors.append(f"assumption fork {fork_id} selects {selected!r} without selection_reason")
            if unresolved_risk:
                warnings.append(f"assumption fork {fork_id} is resolved but still carries unresolved_risk")
        else:
            if not unresolved_risk:
                errors.append(f"assumption fork {fork_id} is unresolved and must record unresolved_risk")
            else:
                surfaced = any(
                    fork_id in item or str(fork.get("phrase", "")) in item for item in unresolved_research
                ) or any(
                    fork_id in item or str(fork.get("phrase", "")) in item
                    for item in unresolved_decision_risks.get(str(fork.get("question_id")), [])
                )
                if not surfaced:
                    errors.append(
                        f"assumption fork {fork_id} is unresolved; surface it in research_basis.unresolved_questions "
                        "or the selection decision unresolved_risks instead of silently dropping it"
                    )

    for model in contract.get("models", []):
        if not isinstance(model, dict):
            continue
        model_id = str(model.get("model_id", ""))
        text = _model_text(model)
        _check_objective_semantics(model, require=require_objective_contract, errors=errors)
        identity = model.get("identity")
        if RISK_FAMILY_RE.search(text) and not isinstance(identity, dict):
            errors.append(
                f"model {model_id} uses a risk-measure family name; declare identity "
                "(canonical_name, mathematical_class, objective_form, forbidden_aliases)"
            )
        if isinstance(identity, dict):
            canonical = str(identity.get("canonical_name", ""))
            aliases = [str(alias) for alias in identity.get("forbidden_aliases", [])]
            if canonical and any(alias.casefold() == canonical.casefold() for alias in aliases):
                errors.append(f"model {model_id} identity lists its canonical_name as a forbidden alias")
            details = model.get("plan_details") if isinstance(model.get("plan_details"), dict) else {}
            equation_ids = {
                str(row.get("equation_id"))
                for row in details.get("equation_plan", [])
                if isinstance(row, dict)
            }
            for equation_id in identity.get("defining_equations", []):
                if str(equation_id) not in equation_ids:
                    errors.append(
                        f"model {model_id} identity.defining_equations references unknown equation {equation_id}"
                    )

        risk = model.get("risk_semantics")
        if CVAR_RE.search(text) and not isinstance(risk, dict):
            errors.append(
                f"model {model_id} mentions CVaR; declare risk_semantics "
                "(random_variable, tail, confidence_level, objective_direction)"
            )
        if isinstance(risk, dict):
            confidence = risk.get("confidence_level")
            if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 < confidence < 1:
                errors.append(f"model {model_id} risk_semantics.confidence_level must be strictly between 0 and 1")
            variable = risk.get("random_variable")
            tail = risk.get("tail")
            direction = risk.get("objective_direction")
            if variable == "loss" and tail == "upper" and direction != "minimize":
                errors.append(f"model {model_id} minimizes nothing: upper-tail loss CVaR requires objective_direction=minimize")
            if variable == "profit" and tail == "lower" and direction != "maximize":
                errors.append(f"model {model_id} lower-tail profit CVaR requires objective_direction=maximize")
            if (variable, tail) in {("loss", "lower"), ("profit", "upper")}:
                errors.append(
                    f"model {model_id} uses unconventional CVaR combination {variable}/{tail}; "
                    "use loss+upper or profit+lower, or justify the tail choice explicitly"
                )

        correlation = model.get("correlation_spec")
        characteristics = model.get("characteristics", [])
        if "correlated_inputs" in characteristics and not isinstance(correlation, dict):
            errors.append(
                f"model {model_id} declares correlated_inputs; declare correlation_spec "
                "(source, sample_scope, dimension, min_eigenvalue, checks)"
            )
        if CHOLESKY_RE.search(text):
            if not isinstance(correlation, dict):
                errors.append(f"model {model_id} uses Cholesky; declare correlation_spec with PSD evidence first")
            else:
                eigenvalue = correlation.get("min_eigenvalue")
                if not isinstance(eigenvalue, (int, float)) or isinstance(eigenvalue, bool) or eigenvalue <= 0:
                    errors.append(
                        f"model {model_id} uses Cholesky but min_eigenvalue={eigenvalue!r} does not prove positive definiteness"
                    )
        if isinstance(correlation, dict):
            eigenvalue = correlation.get("min_eigenvalue")
            if not isinstance(eigenvalue, (int, float)) or isinstance(eigenvalue, bool) or eigenvalue < PSD_TOLERANCE:
                errors.append(
                    f"model {model_id} correlation_spec.min_eigenvalue must be recorded and >= {PSD_TOLERANCE}"
                )
            checks = correlation.get("checks") if isinstance(correlation.get("checks"), dict) else {}
            for flag in ("in_unit_interval", "symmetric", "psd_verified"):
                if checks.get(flag) is not True:
                    errors.append(f"model {model_id} correlation_spec.checks.{flag} must be true")

    return errors, warnings


def evaluate_frozen_semantics(frozen: dict[str, Any]) -> list[str]:
    """Domain checks on frozen result values."""

    errors: list[str] = []
    for row in frozen.get("results", []):
        if not isinstance(row, dict):
            continue
        result_id = str(row.get("result_id", ""))
        unit = str(row.get("unit", ""))
        value = row.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            continue
        if unit == "probability" and not 0 <= value <= 1:
            errors.append(f"result {result_id} has unit probability but value {value} outside [0, 1]")
        if unit == "correlation" and not -1 <= value <= 1:
            errors.append(f"result {result_id} has unit correlation but value {value} outside [-1, 1]")
    return errors


def _has_optimality_evidence(contract: dict[str, Any]) -> bool:
    for model in contract.get("models", []):
        if not isinstance(model, dict):
            continue
        for obligation in model.get("validation_obligations", []):
            if not isinstance(obligation, dict):
                continue
            haystack = " ".join(
                str(part)
                for part in (
                    obligation.get("method", ""),
                    obligation.get("acceptance", {}).get("left_metric_id", "")
                    if isinstance(obligation.get("acceptance"), dict)
                    else "",
                )
            )
            if OPTIMALITY_EVIDENCE_RE.search(haystack):
                return True
    return False


def evaluate_text_semantics(
    contract: dict[str, Any],
    frozen: dict[str, Any] | None,
    texts: dict[str, str],
) -> list[str]:
    """Checks that bind the contract and frozen presentation to paper text."""

    errors: list[str] = []
    if not texts:
        return errors

    for model in contract.get("models", []):
        if not isinstance(model, dict):
            continue
        identity = model.get("identity")
        if not isinstance(identity, dict):
            continue
        canonical = str(identity.get("canonical_name", ""))
        for label, text in texts.items():
            folded = text.casefold()
            for alias in identity.get("forbidden_aliases", []):
                if isinstance(alias, str) and alias and alias.casefold() in folded:
                    errors.append(
                        f"{label} uses forbidden model alias {alias!r}; the contract canonical name is {canonical!r}"
                    )

    optimum_hits = [
        (label, token)
        for label, text in texts.items()
        for token in GLOBAL_OPTIMUM_TOKENS
        if token.casefold() in text.casefold()
    ]
    if optimum_hits and not _has_optimality_evidence(contract):
        labels = ", ".join(f"{label} ({token!r})" for label, token in optimum_hits)
        errors.append(
            f"global-optimality language found in {labels} but no validation obligation records "
            "a solver gap, bound, or optimality evidence; downgrade the claim or add the evidence"
        )

    if isinstance(frozen, dict):
        for row in frozen.get("results", []):
            if not isinstance(row, dict):
                continue
            display_label = row.get("display_label") or row.get("display_unit")
            display = str(row.get("display_value", ""))
            if not display_label or not display:
                continue
            declared = str(display_label)
            canonical_unit = str(row.get("unit", ""))
            unit_pattern = re.compile(re.escape(display) + r"\s*([A-Za-z_]+|[一-鿿]{1,4})")
            for label, text in texts.items():
                for match in unit_pattern.finditer(text):
                    token = match.group(1)
                    if token in MONEY_SCALE_TOKENS and token != declared and token != canonical_unit:
                        errors.append(
                            f"{label} presents result {row.get('result_id')} value {display} with {token!r} "
                            f"but the frozen presentation declares {declared!r}"
                        )
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--frozen-results")
    parser.add_argument("--abstract")
    parser.add_argument("--paper")
    parser.add_argument("--conclusion")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--require-objective-contract", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    contract_path = resolve_path(args.model_contract, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        contract = load_structured(contract_path)
        if not isinstance(contract, dict):
            raise ValueError("model contract must be an object")
        contract_errors, contract_warnings = evaluate_contract_semantics(
            contract,
            require_objective_contract=args.require_objective_contract,
        )
        errors.extend(contract_errors)
        warnings.extend(contract_warnings)

        frozen: dict[str, Any] | None = None
        if args.frozen_results:
            frozen_path = resolve_path(args.frozen_results, root).resolve()
            frozen_doc = load_structured(frozen_path)
            if not isinstance(frozen_doc, dict):
                raise ValueError("frozen results must be an object")
            frozen = frozen_doc
            errors.extend(evaluate_frozen_semantics(frozen))

        texts: dict[str, str] = {}
        for label, raw_path in (("abstract", args.abstract), ("paper", args.paper), ("conclusion", args.conclusion)):
            if raw_path:
                path = resolve_path(raw_path, root).resolve()
                texts[label] = path.read_text(encoding="utf-8")
        errors.extend(evaluate_text_semantics(contract, frozen, texts))
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "model_contract": rel_path(contract_path, root),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
