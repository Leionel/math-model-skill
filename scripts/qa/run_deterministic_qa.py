#!/usr/bin/env python3
"""Run release-time deterministic checks and persist one hashable QA report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import child_env, load_structured, rel_path, resolve_path, sha256_file, write_json  # noqa: E402
from runtime_state import RuntimeStateError, load_runtime_state  # noqa: E402
from v2_gate_runtime import _v2_role_path  # noqa: E402


def run_check(label: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", env=child_env(), check=False)
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        report = {"ok": False, "errors": ["check did not emit a JSON report"], "stdout": result.stdout}
    return {
        "label": label,
        "ok": result.returncode == 0 and report.get("ok") is True,
        "exit_code": result.returncode,
        "report": report,
        "stderr": result.stderr,
    }


def _run_id_from_manifest(raw_path: str, root: Path) -> str:
    manifest = load_structured(resolve_path(raw_path, root).resolve())
    if not isinstance(manifest, dict) or not isinstance(manifest.get("run_id"), str):
        raise ValueError("run_manifest must contain a string run_id")
    return manifest["run_id"]


PROFILE_FLAG_LEVELS = {
    "baseline": [],
    "enhanced": [
        "require_first_draft_coverage",
        "require_math_writing_coverage",
        "require_derivation_integrity",
    ],
    "strict": [
        "require_first_draft_coverage",
        "require_math_writing_coverage",
        "require_derivation_integrity",
        "require_scope_contract",
        "require_formula_replay",
        "require_replay_bindings",
        "require_pdf_math_consistency",
        "require_objective_contract",
        "require_inference_role_consistency",
    ],
}


def apply_profile(args: argparse.Namespace) -> argparse.Namespace:
    """Expand --profile into the individual require-flags it implies.

    Individual flags can only add checks on top of the profile; the profile
    mirrors the flag sets that check_gates.py uses for its independent reruns.
    """

    for name in PROFILE_FLAG_LEVELS.get(args.profile, []):
        setattr(args, name, True)
    return args


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract")
    parser.add_argument("--run-manifest")
    parser.add_argument("--manifest", help="v2 manifest; resolve canonical QA inputs from roots/DAG")
    parser.add_argument("--frozen-results")
    parser.add_argument("--derived-results")
    parser.add_argument("--evidence-registry")
    parser.add_argument("--paper-plan")
    parser.add_argument("--abstract")
    parser.add_argument("--paper")
    parser.add_argument("--conclusion")
    parser.add_argument("--pdf")
    parser.add_argument("--pdf-source")
    parser.add_argument("--require-pdf-math-consistency", action="store_true")
    parser.add_argument("--presentation-contract")
    parser.add_argument("--tex")
    parser.add_argument("--bib")
    parser.add_argument("--require-verified-bibliography", action="store_true")
    parser.add_argument("--check-figures", action="store_true")
    parser.add_argument("--figures-dir")
    parser.add_argument("--require-figure-lineage", action="store_true")
    parser.add_argument("--require-canonical-source", action="store_true")
    parser.add_argument("--require-answer-contract", action="store_true")
    parser.add_argument("--require-abstract-backcheck", action="store_true")
    parser.add_argument("--require-figure-semantics", action="store_true")
    parser.add_argument(
        "--require-inference-role-consistency",
        action="store_true",
        help="Reject prose that reverses a declared primary repeated-measure inference method.",
    )
    parser.add_argument("--diagram-spec", action="append", default=[], help="Structured concept-diagram spec; repeat for multiple formal diagrams.")
    parser.add_argument("--problem-snapshot")
    parser.add_argument("--data-contract", action="append", default=[])
    parser.add_argument("--require-observation-structure", action="store_true")
    parser.add_argument("--require-decision-context", action="store_true")
    parser.add_argument("--require-statistical-design", action="store_true")
    parser.add_argument("--implementation-map")
    parser.add_argument("--artifact-dag")
    parser.add_argument("--sensitivity-experiment")
    parser.add_argument("--require-sensitivity-execution", action="store_true")
    parser.add_argument("--require-parameter-binding", action="store_true")
    parser.add_argument("--extremum-certificate", action="append", default=[])
    parser.add_argument("--oos-artifact")
    parser.add_argument("--require-oos-design", action="store_true")
    parser.add_argument("--failure-evidence")
    parser.add_argument("--writer-package")
    parser.add_argument(
        "--require-first-draft-coverage",
        action="store_true",
        help="Require every planned formulation/result/validation/interpretation anchor in the writer package draft.",
    )
    parser.add_argument(
        "--require-math-writing-coverage",
        action="store_true",
        help="Require model/equation/constraint/validation traceability, acyclic argument order, and draft locators.",
    )
    parser.add_argument(
        "--require-replay-bindings",
        action="store_true",
        help="Require mechanism argument units to bind declared numeric replay cases.",
    )
    parser.add_argument(
        "--require-derivation-integrity",
        action="store_true",
        help="Require equation metadata and derivation-graph integrity checks.",
    )
    parser.add_argument(
        "--require-scope-contract",
        action="store_true",
        help="Require question-scoped parameter/event bindings and paper-section checks.",
    )
    parser.add_argument(
        "--require-formula-replay",
        action="store_true",
        help="Require declared scalar equation back-substitution cases and replay them.",
    )
    parser.add_argument(
        "--require-objective-contract",
        action="store_true",
        help="Require objective identity/equivalence and degeneracy evidence for optimization-like models.",
    )
    parser.add_argument(
        "--require-objective-binding",
        action="store_true",
        help="Require implementation-map objective bindings when an implementation map is supplied.",
    )
    parser.add_argument("--claim-inventory-output")
    parser.add_argument("--style-check", action="store_true")
    parser.add_argument(
        "--judge-scan",
        action="store_true",
        help="Run the issue-only editorial scan; it never assigns a paper score.",
    )
    parser.add_argument("--output")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    parser.add_argument(
        "--profile",
        choices=("baseline", "enhanced", "strict"),
        default=None,
        help="Aggregate switch that turns on the require-flags implied by the profile (mirrors check_gates rerun sets); individual flags can add more on top.",
    )
    parser.add_argument(
        "--require-pdf-numeric-presence",
        action="store_true",
        help="Require every frozen display value to appear in the extracted PDF text (forwarded to check_math_pdf_consistency).",
    )
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    if args.manifest:
        manifest_path = resolve_path(args.manifest, root).resolve()
        try:
            state = load_runtime_state(manifest_path, project_root=root, allow_legacy=False)
        except (OSError, ValueError, TypeError, RuntimeStateError) as exc:
            print(json.dumps({"ok": False, "errors": [f"v2 manifest resolution failed: {exc}"]}, ensure_ascii=False))
            return 2

        def resolve_role(role: str) -> str | None:
            _, path = _v2_role_path(state, role)
            return str(path) if path is not None and path.is_file() else None

        args.run_manifest = args.run_manifest or str(manifest_path)
        for attribute, role in (
            ("model_contract", "model_contract"), ("frozen_results", "frozen_results"),
            ("evidence_registry", "evidence_registry"), ("paper_plan", "paper_plan"),
            ("abstract", "abstract"), ("paper", "paper"), ("conclusion", "conclusion"),
        ):
            if getattr(args, attribute) is None:
                setattr(args, attribute, resolve_role(role))
        for attribute, role in (
            ("writer_package", "writer_package"), ("pdf", "pdf"), ("pdf_source", "pdf_source"),
            ("presentation_contract", "presentation_contract"), ("tex", "tex"), ("bib", "bib"),
            ("artifact_dag", "artifact_dag"), ("oos_artifact", "oos_artifact"),
            ("failure_evidence", "failure_evidence"), ("sensitivity_experiment", "sensitivity_experiment"),
        ):
            if getattr(args, attribute) is None:
                setattr(args, attribute, resolve_role(role))
        if args.profile is None:
            args.profile = "strict" if state.capabilities.require_strict_math else ("enhanced" if state.capabilities.require_full_evidence_chain else "baseline")
        if args.output is None:
            args.output = "reports/deterministic_qa.json"
    else:
        if args.profile is None:
            args.profile = "baseline"
    required_args = ("model_contract", "run_manifest", "frozen_results", "evidence_registry", "paper_plan", "abstract", "paper", "conclusion", "output")
    missing = [name for name in required_args if not getattr(args, name)]
    if missing:
        print(json.dumps({"ok": False, "errors": [f"missing required QA arguments: {missing}; pass --manifest for v2 path resolution"]}, ensure_ascii=False))
        return 2
    args = apply_profile(args)

    if bool(args.tex) != bool(args.bib):
        print("ERROR: --tex and --bib must be supplied together", file=sys.stderr)
        return 2
    if args.require_verified_bibliography and not (args.tex and args.bib):
        print("ERROR: --require-verified-bibliography requires --tex and --bib", file=sys.stderr)
        return 2
    if args.require_sensitivity_execution and not args.sensitivity_experiment:
        print("ERROR: --require-sensitivity-execution requires --sensitivity-experiment", file=sys.stderr)
        return 2
    if args.require_pdf_math_consistency and not args.pdf:
        print("ERROR: --require-pdf-math-consistency requires --pdf", file=sys.stderr)
        return 2
    if args.pdf_source and not args.pdf:
        print("ERROR: --pdf-source requires --pdf", file=sys.stderr)
        return 2
    if args.require_first_draft_coverage and not args.writer_package:
        print("ERROR: --require-first-draft-coverage requires --writer-package", file=sys.stderr)
        return 2
    if args.require_math_writing_coverage and not args.writer_package:
        print("ERROR: --require-math-writing-coverage requires --writer-package", file=sys.stderr)
        return 2
    if args.require_replay_bindings and not args.require_math_writing_coverage:
        print("ERROR: --require-replay-bindings requires --require-math-writing-coverage", file=sys.stderr)
        return 2
    if args.require_observation_structure and not args.data_contract:
        print("ERROR: --require-observation-structure requires --data-contract", file=sys.stderr)
        return 2
    if args.require_oos_design and not args.oos_artifact:
        print("ERROR: --require-oos-design requires --oos-artifact", file=sys.stderr)
        return 2

    contract_args = [
        "--project-root", str(root),
        "--model-contract", args.model_contract,
        "--run-manifest", args.run_manifest,
        "--frozen-results", args.frozen_results,
        "--evidence-registry", args.evidence_registry,
        "--paper-plan", args.paper_plan,
        "--strict",
    ]
    consistency_args = [
        "--project-root", str(root),
        "--paper-plan", args.paper_plan,
        "--frozen-results", args.frozen_results,
        "--evidence-registry", args.evidence_registry,
        "--abstract", args.abstract,
        "--paper", args.paper,
        "--conclusion", args.conclusion,
        "--strict",
    ]
    if args.derived_results:
        consistency_args.extend(["--derived-results", args.derived_results])
    if args.figures_dir:
        consistency_args.extend(["--figures-dir", args.figures_dir])
    if args.require_figure_lineage:
        consistency_args.append("--require-figure-lineage")
    if args.artifact_dag:
        consistency_args.extend(["--artifact-dag", args.artifact_dag])
    if args.require_canonical_source:
        consistency_args.append("--require-canonical-source")
    consistency_args.extend(["--model-contract", args.model_contract])
    if args.require_answer_contract:
        consistency_args.append("--require-answer-contract")
    if args.require_abstract_backcheck:
        consistency_args.append("--require-abstract-backcheck")
    if args.require_figure_semantics:
        consistency_args.append("--require-figure-semantics")
    if args.require_inference_role_consistency:
        consistency_args.append("--require-inference-role-consistency")
    math_semantics_args = [
        "--project-root", str(root),
        "--model-contract", args.model_contract,
        "--frozen-results", args.frozen_results,
        "--abstract", args.abstract,
        "--paper", args.paper,
        "--conclusion", args.conclusion,
        "--strict",
    ]
    if args.require_objective_contract:
        math_semantics_args.append("--require-objective-contract")
    scope_args = [
        "--project-root", str(root),
        "--model-contract", args.model_contract,
        "--paper", args.paper,
        "--strict",
    ]
    if args.require_scope_contract:
        scope_args.append("--require-scope-contract")
    else:
        scope_args.append("--skip-if-absent")
    formula_replay_args = [
        "--project-root", str(root),
        "--model-contract", args.model_contract,
        "--paper", args.paper,
        "--strict",
    ]
    if args.require_formula_replay:
        formula_replay_args.append("--require-formula-replay")
    else:
        formula_replay_args.append("--skip-if-absent")
    units_args = [
        "--project-root", str(root),
        "--model-contract", args.model_contract,
        "--strict",
    ]
    checks = [
        run_check("contracts", [sys.executable, str(SCRIPT_DIR / "validate_contracts.py"), *contract_args]),
        run_check("scope_consistency", [sys.executable, str(SCRIPT_DIR / "check_scope_consistency.py"), *scope_args]),
        run_check("formula_replay", [sys.executable, str(SCRIPT_DIR / "check_formula_replay.py"), *formula_replay_args]),
        run_check("math_semantics", [sys.executable, str(SCRIPT_DIR / "check_math_semantics.py"), *math_semantics_args]),
        run_check("units", [sys.executable, str(SCRIPT_DIR / "check_units.py"), *units_args]),
        run_check(
            "contest_safety",
            [
                sys.executable,
                str(SCRIPT_DIR / "check_contest_safety.py"),
                "--project-root", str(root),
                "--manifest", args.run_manifest,
                "--strict",
            ],
        ),
        run_check("consistency", [sys.executable, str(SCRIPT_DIR / "check_consistency.py"), *consistency_args]),
    ]
    if args.pdf:
        pdf_math_args = [
            sys.executable, str(SCRIPT_DIR.parent / "pdf" / "check_math_pdf_consistency.py"),
            "--project-root", str(root),
            "--pdf", args.pdf,
            "--model-contract", args.model_contract,
            "--source", args.pdf_source or args.paper,
            "--frozen-results", args.frozen_results,
            "--paper-plan", args.paper_plan,
            "--strict",
        ]
        if args.writer_package:
            pdf_math_args.extend(["--writer-package", args.writer_package])
        if args.require_scope_contract:
            pdf_math_args.append("--require-scope-contract")
        if args.require_formula_replay:
            pdf_math_args.append("--require-formula-replay")
        if args.require_pdf_numeric_presence:
            pdf_math_args.append("--require-numeric-presence")
        checks.append(run_check("pdf_math_consistency", pdf_math_args))
    if args.presentation_contract:
        checks.append(run_check(
            "presentation_safety",
            [
                sys.executable, str(SCRIPT_DIR / "check_presentation_safety.py"),
                "--project-root", str(root),
                "--presentation-contract", args.presentation_contract,
                "--frozen-results", args.frozen_results,
                "--strict",
            ],
        ))
    if args.require_derivation_integrity or args.require_math_writing_coverage:
        derivation_args = [
            "--project-root", str(root),
            "--model-contract", args.model_contract,
            "--strict",
        ]
        if args.require_derivation_integrity or args.require_math_writing_coverage:
            derivation_args.append("--require-metadata")
        checks.append(run_check(
            "derivation_integrity",
            [sys.executable, str(SCRIPT_DIR / "check_derivation_integrity.py"), *derivation_args],
        ))
    if args.problem_snapshot:
        checks.append(run_check(
            "problem_coverage",
            [
                sys.executable, str(SCRIPT_DIR / "check_problem_coverage.py"),
                "--project-root", str(root),
                "--problem-snapshot", args.problem_snapshot,
                "--model-contract", args.model_contract,
                "--paper-plan", args.paper_plan,
                "--strict",
            ],
        ))
    for index, data_contract in enumerate(args.data_contract, start=1):
        data_contract_args = [
            "--project-root", str(root),
            "--data-contract", data_contract,
            "--model-contract", args.model_contract,
            "--strict",
        ]
        if args.require_observation_structure:
            data_contract_args.append("--require-observation-structure")
        if args.require_decision_context:
            data_contract_args.append("--require-decision-context")
        if args.require_statistical_design:
            data_contract_args.append("--require-statistical-design")
        checks.append(run_check(
            f"data_contract_{index}",
            [
                sys.executable, str(SCRIPT_DIR / "check_data_contract.py"),
                *data_contract_args,
            ],
        ))
    for index, diagram_spec in enumerate(args.diagram_spec, start=1):
        checks.append(run_check(
            f"diagram_spec_{index}",
            [
                sys.executable, str(SCRIPT_DIR.parent / "figures" / "check_diagram_spec.py"),
                "--project-root", str(root),
                "--spec", diagram_spec,
                "--strict",
                "--require-reviewed",
            ],
        ))
    if args.implementation_map:
        implementation_args = [
            "--project-root", str(root),
            "--implementation-map", args.implementation_map,
            "--model-contract", args.model_contract,
            "--strict",
        ]
        if args.require_objective_binding:
            implementation_args.append("--require-objective-binding")
        checks.append(run_check(
            "implementation_map",
            [
                sys.executable, str(SCRIPT_DIR / "check_implementation_map.py"),
                *implementation_args,
            ],
        ))
    if args.artifact_dag:
        checks.append(run_check(
            "artifact_dag",
            [
                sys.executable, str(SCRIPT_DIR / "check_artifact_dag.py"),
                "--project-root", str(root),
                "--dag", args.artifact_dag,
                "--strict",
            ],
        ))
    if args.sensitivity_experiment:
        sensitivity_args = [
            sys.executable, str(SCRIPT_DIR / "check_sensitivity_experiment.py"),
            "--project-root", str(root),
            "--experiment", args.sensitivity_experiment,
            "--run-id", _run_id_from_manifest(args.run_manifest, root),
            "--strict",
        ]
        if args.require_parameter_binding:
            sensitivity_args.extend([
                "--model-contract", args.model_contract,
                "--require-parameter-binding",
            ])
        if args.require_sensitivity_execution:
            sensitivity_args.append("--require-execution-receipts")
        checks.append(run_check(
            "sensitivity_experiment",
            sensitivity_args,
        ))
    for index, certificate in enumerate(args.extremum_certificate, start=1):
        checks.append(run_check(
            f"extremum_certificate_{index}",
            [
                sys.executable, str(SCRIPT_DIR / "check_extremum_certificate.py"),
                "--project-root", str(root),
                "--certificate", certificate,
                "--run-id", _run_id_from_manifest(args.run_manifest, root),
                "--strict",
            ],
        ))
    if args.oos_artifact:
        checks.append(run_check(
            "oos_artifact",
            [
                sys.executable, str(SCRIPT_DIR / "check_oos_artifact.py"),
                "--project-root", str(root),
                "--artifact", args.oos_artifact,
                "--run-id", _run_id_from_manifest(args.run_manifest, root),
                "--strict",
                *( ["--require-design"] if args.require_oos_design else [] ),
            ],
        ))
    if args.failure_evidence:
        checks.append(run_check(
            "failure_evidence",
            [
                sys.executable, str(SCRIPT_DIR / "check_failure_evidence.py"),
                "--project-root", str(root),
                "--artifact", args.failure_evidence,
                "--frozen-results", args.frozen_results,
                "--run-id", _run_id_from_manifest(args.run_manifest, root),
                "--strict",
            ],
        ))
    if args.writer_package:
        writer_check_args = [
            "--project-root", str(root),
            "--writer-package", args.writer_package,
            "--draft", args.paper,
            "--strict",
        ]
        if args.require_first_draft_coverage:
            writer_check_args.append("--require-first-draft-coverage")
        checks.append(run_check(
            "writer_package",
            [
                sys.executable, str(SCRIPT_DIR / "check_writer_package.py"),
                *writer_check_args,
            ],
        ))
        if args.require_first_draft_coverage and args.paper_plan:
            checks.append(run_check(
                "reverse_outline",
                [
                    sys.executable, str(SCRIPT_DIR / "check_reverse_outline.py"),
                    "--project-root", str(root),
                    "--paper-plan", args.paper_plan,
                    "--writer-package", args.writer_package,
                    "--draft", args.paper,
                ],
            ))
    if args.require_math_writing_coverage:
        math_writing_args = [
            "--project-root", str(root),
            "--model-contract", args.model_contract,
            "--paper-plan", args.paper_plan,
            "--frozen-results", args.frozen_results,
            "--writer-package", args.writer_package,
            "--draft", args.paper,
            "--require-coverage",
            "--strict",
        ]
        if args.derived_results:
            math_writing_args.extend(["--derived-results", args.derived_results])
        if args.require_replay_bindings:
            math_writing_args.append("--require-replay-bindings")
        checks.append(run_check(
            "math_writing",
            [sys.executable, str(SCRIPT_DIR / "check_math_writing.py"), *math_writing_args],
        ))
    if args.claim_inventory_output:
        checks.append(run_check(
            "claim_inventory",
            [
                sys.executable, str(SCRIPT_DIR.parent / "claims" / "inventory_claims.py"),
                "--project-root", str(root),
                "--paper-plan", args.paper_plan,
                "--frozen-results", args.frozen_results,
                "--draft", args.paper,
                "--output", args.claim_inventory_output,
                "--strict",
                *( ["--force"] if args.force else [] ),
            ],
        ))
    if args.style_check:
        style_args = [
            sys.executable,
            str(SCRIPT_DIR / "check_paper_style.py"),
            "--project-root", str(root),
            "--paper-plan", args.paper_plan,
            "--draft", args.paper,
            "--abstract", args.abstract,
            "--conclusion", args.conclusion,
        ]
        if args.judge_scan:
            style_args.append("--judge-scan")
            style_args.extend(["--model-contract", args.model_contract, "--frozen-results", args.frozen_results])
        checks.append(run_check(
            "paper_style",
            style_args,
        ))
    if args.tex and args.bib:
        citation_args = ["--project-root", str(root), "--tex", args.tex, "--bib", args.bib]
        if args.require_verified_bibliography:
            citation_args.extend([
                "--evidence-registry", args.evidence_registry,
                "--require-verified-bibliography",
            ])
        if args.check_figures:
            citation_args.append("--check-figures")
        if args.figures_dir:
            citation_args.extend(["--figures-dir", args.figures_dir])
        checks.append(run_check("citations", [sys.executable, str(SCRIPT_DIR / "check_citations.py"), *citation_args]))
    else:
        checks.append({"label": "citations", "ok": True, "status": "not_applicable"})

    input_paths = {
        "model_contract": args.model_contract,
        "frozen_results": args.frozen_results,
        "evidence_registry": args.evidence_registry,
        "paper_plan": args.paper_plan,
        "abstract": args.abstract,
        "paper": args.paper,
        "conclusion": args.conclusion,
    }
    if args.tex:
        input_paths["tex"] = args.tex
        input_paths["bib"] = args.bib
    if args.pdf:
        input_paths["pdf"] = args.pdf
        input_paths["pdf_source"] = args.pdf_source or args.paper
    if args.presentation_contract:
        input_paths["presentation_contract"] = args.presentation_contract
    if args.derived_results:
        input_paths["derived_results"] = args.derived_results
    if args.problem_snapshot:
        input_paths["problem_snapshot"] = args.problem_snapshot
    for index, data_contract in enumerate(args.data_contract, start=1):
        input_paths[f"data_contract_{index}"] = data_contract
    for index, diagram_spec in enumerate(args.diagram_spec, start=1):
        input_paths[f"diagram_spec_{index}"] = diagram_spec
    if args.implementation_map:
        input_paths["implementation_map"] = args.implementation_map
    if args.artifact_dag:
        input_paths["artifact_dag"] = args.artifact_dag
    if args.sensitivity_experiment:
        input_paths["sensitivity_experiment"] = args.sensitivity_experiment
    for index, certificate in enumerate(args.extremum_certificate, start=1):
        input_paths[f"extremum_certificate_{index}"] = certificate
    if args.oos_artifact:
        input_paths["oos_artifact"] = args.oos_artifact
    if args.failure_evidence:
        input_paths["failure_evidence"] = args.failure_evidence
    if args.writer_package:
        input_paths["writer_package"] = args.writer_package
    inputs: list[dict[str, str]] = []
    try:
        for role, raw_path in input_paths.items():
            path = resolve_path(raw_path, root).resolve()
            if not path.is_file():
                raise ValueError(f"QA input does not exist: {raw_path}")
            inputs.append({"role": role, "path": rel_path(path, root), "sha256": sha256_file(path)})
        output_path = resolve_path(args.output, root).resolve()
        report = {
            "schema_version": "1.0",
            "ok": all(check.get("ok") is True for check in checks),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "inputs": inputs,
            "checks": checks,
        }
        write_json(output_path, report, overwrite=args.force)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": report["ok"], "output": rel_path(output_path, root)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
