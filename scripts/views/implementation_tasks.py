#!/usr/bin/env python3
"""Project a ready model contract into per-model implementation tasks for the coder.

This is a derived view, not a new contract: the only truth source stays
`model_contract.json`.  The view exists so the solve stage starts from an
ordered, per-model task list (entrypoint, I/O, equations, constraints, tests,
smoke acceptance, failure return route) instead of re-decomposing one large
contract by hand.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, write_json  # noqa: E402

ESCALATION_NOTE = (
    "If an execution failure exposes a wrong formula, constraint, parameter, or data "
    "boundary, return to M1 with a minimal reproduction; do not silently rewrite the "
    "mathematics inside code. A new model contract invalidates downstream maps and runs."
)

# Operational coding protocols; full text in references/research/coding_protocols.md.
# Keep ids and wording in sync with that reference when either side changes.
PROTOCOLS = {
    "CP-DATA-01": "read text/CSV with an encoding fallback chain (utf-8 -> gbk/gb18030 -> latin-1) and record the effective encoding",
    "CP-DATA-02": "read >1GB CSV in chunks with downcast dtypes; reconcile one aggregate against a full-sample spot check",
    "CP-DATA-03": "register the missing-value policy (ratio, assumed mechanism, train-only statistics) instead of silent fillna",
    "CP-LEAK-01": "fit every learned preprocessor (scaler/encoder/imputer/PCA) on the training split only; build predictive features with shift(1) or longer lags",
    "CP-LEAK-02": "time series: no two-way smoothing, no global normalization, no random K-fold; split on a monotone time boundary and look back only",
    "CP-NUM-01": "use stable numeric forms (log-sum-exp, expit, log-domain ops); never exp-sum large magnitudes directly",
    "CP-NUM-02": "estimate the condition number before inverting; cond > 1e7 requires pinv or regularization, and the action must be logged",
    "CP-SOLVE-01": "agree a degradation path before solving (shrink scale / relax tolerance / switch heuristic) and log before/after objectives when it fires",
    "CP-RAND-01": "run every stochastic component with >=3 fixed, registered seeds and report mean +/- dispersion, never a single unlabeled run",
    "CP-UNIT-01": "sanity-check units, variable bounds, and result magnitude before and after solving; never mix yuan / 10k-yuan / million-yuan scales",
    "CP-SOLVE-02": "Big-M constants need a tight-bound derivation in the parameter plan; M > 1e5 triggers human review",
    "CP-SOLVE-03": "record solver status and optimality gap; early termination or nonconvex local solutions may never be called globally optimal",
    "CP-OUT-01": "screen outputs for NaN/inf and magnitude anomalies before persisting; investigate, never silently drop",
    "CP-EVID-01": "on failure keep command + stack + expected-vs-actual; classify implementation bug vs contract defect before touching math",
}

_BASE_PROTOCOL_IDS = ("CP-DATA-01", "CP-DATA-03", "CP-UNIT-01", "CP-OUT-01", "CP-EVID-01")

_PROTOCOLS_BY_PROBLEM_TYPE = {
    "prediction": ("CP-LEAK-01", "CP-NUM-01"),
    "classification": ("CP-LEAK-01",),
    "time_series": ("CP-LEAK-01", "CP-LEAK-02"),
    "statistical_inference": ("CP-LEAK-01", "CP-NUM-01"),
    "optimization": ("CP-NUM-02", "CP-SOLVE-01", "CP-SOLVE-02", "CP-SOLVE-03"),
    "simulation": ("CP-RAND-01",),
    "differential_equation": ("CP-NUM-01",),
    "evaluation": ("CP-NUM-02",),
    "graph_network": (),
    "other": (),
}

_PROTOCOLS_BY_CHARACTERISTIC = {
    "stochastic": ("CP-RAND-01",),
    "machine_learning": ("CP-LEAK-01",),
    "time_dependent": ("CP-LEAK-02",),
}


def _robustness_checklist(model: dict[str, Any]) -> list[dict[str, str]]:
    ids: list[str] = list(_BASE_PROTOCOL_IDS)
    ids.extend(_PROTOCOLS_BY_PROBLEM_TYPE.get(model.get("problem_type", ""), ()))
    for characteristic in model.get("characteristics", []):
        ids.extend(_PROTOCOLS_BY_CHARACTERISTIC.get(characteristic, ()))
    selected: list[dict[str, str]] = []
    seen: set[str] = set()
    for protocol_id in ids:
        if protocol_id in seen:
            continue
        seen.add(protocol_id)
        selected.append({"protocol_id": protocol_id, "check": PROTOCOLS[protocol_id]})
    return selected


def _acceptance_summary(obligation: dict[str, Any]) -> dict[str, Any]:
    acceptance = obligation.get("acceptance")
    if not isinstance(acceptance, dict):
        return {"raw": acceptance if acceptance is not None else None}
    right = acceptance.get("right")
    return {
        "left_metric_id": acceptance.get("left_metric_id"),
        "operator": acceptance.get("operator"),
        "right": right.get("value") if isinstance(right, dict) else right,
        "unit": acceptance.get("unit"),
    }


def _model_task(model: dict[str, Any], question: dict[str, Any] | None) -> dict[str, Any]:
    plan = model.get("plan_details") if isinstance(model.get("plan_details"), dict) else {}
    equations = [
        row for row in plan.get("equation_plan", [])
        if isinstance(row, dict)
    ]
    constraints = [
        row for row in model.get("constraints", [])
        if isinstance(row, dict)
    ]
    obligations = [
        row for row in model.get("validation_obligations", [])
        if isinstance(row, dict)
    ]
    parameters = [
        row for row in plan.get("parameter_plan", [])
        if isinstance(row, dict)
    ]
    validations = [
        row for row in model.get("validation", [])
        if isinstance(row, dict)
    ]
    smoke_acceptance = [
        {
            "check_id": row.get("check_id"),
            "method": row.get("method"),
            "acceptance": row.get("acceptance"),
        }
        for row in validations
        if row.get("stage") in {"smoke", "both"}
    ]
    return {
        "task_id": f"IMPL-{model.get('model_id')}",
        "model_id": model.get("model_id"),
        "question_id": model.get("question_id"),
        "question_task": question.get("task") if question else None,
        "conclusion_type": question.get("conclusion_type") if question else None,
        "model_name": model.get("name"),
        "problem_type": model.get("problem_type"),
        "characteristics": model.get("characteristics", []),
        "selected_candidate_id": plan.get("selected_candidate_id"),
        "mechanism": plan.get("mechanism"),
        "algorithm": model.get("algorithm"),
        "scaffold_entry": plan.get("scaffold_entry"),
        "inputs": model.get("inputs", []),
        "outputs": model.get("outputs", []),
        "parameters": [
            {
                "parameter": row.get("parameter"),
                "provenance_type": row.get("provenance", {}).get("type") if isinstance(row.get("provenance"), dict) else None,
                "unit": row.get("unit"),
                "uncertainty_or_range": row.get("uncertainty_or_range"),
            }
            for row in parameters
        ],
        "equations": [
            {
                "equation_id": row.get("equation_id"),
                "purpose": row.get("purpose"),
                "expression_or_derivation": row.get("expression_or_derivation"),
                "equation_type": row.get("equation_type"),
                "math_risk": row.get("math_risk"),
            }
            for row in equations
        ],
        "constraints": [
            {
                "constraint_id": row.get("constraint_id"),
                "expression": row.get("expression"),
                "meaning": row.get("meaning"),
            }
            for row in constraints
        ],
        "test_obligations": [
            {
                "obligation_id": row.get("obligation_id"),
                "category": row.get("category"),
                "method": row.get("method"),
                "acceptance": _acceptance_summary(row),
                "required_stage": row.get("required_stage"),
            }
            for row in obligations
        ],
        "smoke_acceptance": smoke_acceptance,
        "robustness_checklist": _robustness_checklist(model),
        "implementation_steps": plan.get("implementation_steps", []),
        "output_artifacts": plan.get("output_artifacts", []),
        "validation_strategy": plan.get("validation_strategy", []),
        "failure_modes": plan.get("failure_modes", []),
        "fallback": model.get("fallback"),
        "escalation_route": ESCALATION_NOTE,
    }


def build_implementation_tasks(contract: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(contract, dict):
        raise ValueError("model contract must be an object")
    if contract.get("status") != "ready":
        raise ValueError("implementation tasks require model_contract.status=ready")
    questions = {
        row.get("question_id"): row
        for row in contract.get("questions", [])
        if isinstance(row, dict) and isinstance(row.get("question_id"), str)
    }
    tasks = []
    for model in contract.get("models", []):
        if not isinstance(model, dict) or not isinstance(model.get("model_id"), str):
            continue
        task = _model_task(model, questions.get(model.get("question_id")))
        tasks.append(task)
    if not tasks:
        raise ValueError("model contract has no projectable models")
    return {
        "schema_version": "1.0",
        "run_id": contract.get("run_id"),
        "projection": "implementation_task_view",
        "authority_note": "Derived from model_contract.json only; never hand-edited and never a new truth source.",
        "tasks": tasks,
    }


def render_markdown(view: dict[str, Any]) -> str:
    lines = [
        "# Implementation Task View",
        "",
        "> Derived projection of `model_contract.json`.  Do not edit; regenerate with",
        "> `harness solve --tasks`.  The contract remains the only truth source.",
        "",
        f"- run_id: {view.get('run_id')}",
        f"- tasks: {len(view['tasks'])}",
        "",
    ]
    for task in view["tasks"]:
        lines.extend([
            f"## {task['task_id']} — {task.get('model_name')}",
            "",
            f"- question: `{task.get('question_id')}` — {task.get('question_task')}",
            f"- problem_type: `{task.get('problem_type')}` ({', '.join(task.get('characteristics', [])) or 'n/a'})",
            f"- algorithm: {task.get('algorithm')}",
            f"- scaffold entry: {task.get('scaffold_entry') or '(none declared)'}",
            f"- inputs: {', '.join(task.get('inputs', [])) or 'n/a'}",
            f"- outputs: {', '.join(task.get('outputs', [])) or 'n/a'}",
            "",
            "### Equations to implement",
            "",
        ])
        for equation in task.get("equations", []):
            lines.append(f"- `{equation['equation_id']}` ({equation.get('equation_type')}, risk={equation.get('math_risk')}): {equation.get('expression_or_derivation')} — {equation.get('purpose')}")
        if not task.get("equations"):
            lines.append("- (none declared in equation_plan)")
        lines.extend(["", "### Constraints", ""])
        for constraint in task.get("constraints", []):
            lines.append(f"- `{constraint['constraint_id']}`: {constraint.get('expression')} — {constraint.get('meaning')}")
        if not task.get("constraints"):
            lines.append("- (none)")
        lines.extend(["", "### Parameters (typed provenance)", ""])
        for parameter in task.get("parameters", []):
            lines.append(f"- {parameter.get('parameter')} [{parameter.get('provenance_type')}] unit={parameter.get('unit')} range={parameter.get('uncertainty_or_range')}")
        if not task.get("parameters"):
            lines.append("- (none)")
        lines.extend(["", "### Test obligations (oracle for this task)", ""])
        for obligation in task.get("test_obligations", []):
            acceptance = obligation.get("acceptance", {})
            lines.append(
                f"- `{obligation['obligation_id']}` ({obligation.get('category')}, {obligation.get('required_stage')}): "
                f"{obligation.get('method')}; acceptance {acceptance.get('left_metric_id')} {acceptance.get('operator')} {acceptance.get('right')} {acceptance.get('unit') or ''}".rstrip()
            )
        lines.extend(["", "### Smoke acceptance", ""])
        for row in task.get("smoke_acceptance", []):
            lines.append(f"- {row.get('check_id')}: {row.get('method')} -> {row.get('acceptance')}")
        if not task.get("smoke_acceptance", []):
            lines.append("- (no smoke-stage acceptance declared)")
        lines.extend([
            "",
            "### Robustness checklist (operational protocols)",
            "",
            "> Full protocol text: `references/research/coding_protocols.md`; selection is keyed by",
            "> problem_type and characteristics. Checks are a floor, not a ceiling.",
            "",
        ])
        for protocol in task.get("robustness_checklist", []):
            lines.append(f"- `{protocol['protocol_id']}`: {protocol['check']}")
        lines.extend([
            "",
            "### Implementation steps",
            "",
        ])
        for index, step in enumerate(task.get("implementation_steps", []), start=1):
            lines.append(f"{index}. {step}")
        lines.extend([
            "",
            "### Failure handling",
            "",
            f"- failure modes: {'; '.join(task.get('failure_modes', [])) or '(none declared)'}",
            f"- fallback: {task.get('fallback') or '(none declared)'}",
            f"- escalation: {task['escalation_route']}",
            "",
        ])
    return "\n".join(lines) + "\n"


def compile_implementation_tasks(
    root: Path,
    *,
    model_contract: str = ".harness/contracts/model_contract.json",
    output: str | None = None,
    json_output: str | None = None,
) -> dict[str, Any]:
    contract_path = resolve_path(model_contract, root).resolve()
    contract = load_structured(contract_path)
    view = build_implementation_tasks(contract)
    json_path = resolve_path(json_output or ".harness/views/implementation_tasks.json", root).resolve()
    write_json(json_path, view)
    md_path = resolve_path(output or ".harness/views/IMPLEMENTATION_TASKS.md", root).resolve()
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_markdown(view), encoding="utf-8")
    return {
        "ok": True,
        "model_contract": rel_path(contract_path, root),
        "json": rel_path(json_path, root),
        "markdown": rel_path(md_path, root),
        "tasks": len(view["tasks"]),
        "boundary": "Derived view only; it creates no gate, receipt, or new contract.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--model-contract", default=".harness/contracts/model_contract.json")
    parser.add_argument("--output", help="markdown output path; defaults to .harness/views/IMPLEMENTATION_TASKS.md")
    parser.add_argument("--json-output", help="json output path; defaults to .harness/views/implementation_tasks.json")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    try:
        result = compile_implementation_tasks(
            root,
            model_contract=args.model_contract,
            output=args.output,
            json_output=args.json_output,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"implementation tasks compiled: {result['tasks']} tasks -> {result['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
