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

from _common import rel_path, resolve_path, sha256_file, write_json  # noqa: E402


def run_check(label: str, command: list[str]) -> dict[str, Any]:
    result = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", check=False)
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--evidence-registry", required=True)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--abstract", required=True)
    parser.add_argument("--paper", required=True)
    parser.add_argument("--conclusion", required=True)
    parser.add_argument("--tex")
    parser.add_argument("--bib")
    parser.add_argument("--check-figures", action="store_true")
    parser.add_argument("--figures-dir")
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    if bool(args.tex) != bool(args.bib):
        print("ERROR: --tex and --bib must be supplied together", file=sys.stderr)
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
    checks = [
        run_check("contracts", [sys.executable, str(SCRIPT_DIR / "validate_contracts.py"), *contract_args]),
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
    if args.tex and args.bib:
        citation_args = ["--project-root", str(root), "--tex", args.tex, "--bib", args.bib]
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
