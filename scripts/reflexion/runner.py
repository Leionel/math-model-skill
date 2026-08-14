#!/usr/bin/env python3
"""Bounded Execution Runner for Math Modeling Experiments.

Runs code incrementally per subproblem, measures performance,
captures errors, and enforces bounded reflexion (max 3 rounds).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from error_classifier import ErrorCategory, classify_error

ROOT = Path(__file__).resolve().parents[2]


def run_code_step(
    script_path: Path,
    args: list[str] | None = None,
    cwd: Path | None = None,
    timeout_sec: int = 120,
    round_index: int = 1,
    max_rounds: int = 3,
) -> dict[str, Any]:
    """Execute script step with isolation, timing and error diagnosis."""
    if max_rounds < 1 or round_index < 1 or round_index > max_rounds:
        return {
            "status": "FAIL",
            "category": ErrorCategory.UNKNOWN.value,
            "round": round_index,
            "max_rounds": max_rounds,
            "returncode": -2,
            "stdout": "",
            "stderr": "round_index must satisfy 1 <= round_index <= max_rounds",
            "execution_time_sec": 0.0,
            "diagnosis": {
                "root_cause": "Invalid bounded-reflexion round configuration.",
                "can_auto_fix": False,
                "requires_human_or_m1_review": True,
                "remediation_advice": "Fix the orchestration metadata; do not interpret an invalid round as a model result.",
            },
        }
    if not script_path.exists():
        return {
            "status": "FAIL",
            "category": ErrorCategory.DATA_ERROR.value,
            "round": round_index,
            "max_rounds": max_rounds,
            "returncode": -1,
            "stdout": "",
            "stderr": f"Script not found: {script_path}",
            "execution_time_sec": 0.0,
            "diagnosis": {
                "can_auto_fix": False,
                "remediation_advice": f"File does not exist: {script_path}",
            },
        }

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    cmd = [sys.executable, str(script_path)] + (args or [])
    start_time = time.time()

    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd or ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_sec,
            env=env,
        )
        elapsed = round(time.time() - start_time, 3)
        diag = classify_error(proc.stderr, proc.stdout, proc.returncode)

        return {
            "status": "PASS" if proc.returncode == 0 else "FAIL",
            "category": diag.category.value,
            "round": round_index,
            "max_rounds": max_rounds,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "execution_time_sec": elapsed,
            "diagnosis": {
                "root_cause": diag.root_cause,
                "can_auto_fix": diag.can_auto_fix and (round_index < max_rounds),
                "requires_human_or_m1_review": diag.requires_human_or_m1_review or (round_index >= max_rounds),
                "remediation_advice": diag.remediation_advice,
                "extracted_exception": diag.extracted_exception,
            },
            "reflexion": {
                "mode": "diagnose_only",
                "repair_required": proc.returncode != 0,
                "constraints_may_not_be_relaxed": True,
            },
        }

    except subprocess.TimeoutExpired as exc:
        elapsed = round(time.time() - start_time, 3)
        diag = classify_error(f"Timed out after {timeout_sec}s", exit_code=-9)
        return {
            "status": "TIMEOUT",
            "category": ErrorCategory.TIMEOUT_ERROR.value,
            "round": round_index,
            "max_rounds": max_rounds,
            "returncode": -9,
            "stdout": exc.stdout or "" if isinstance(exc.stdout, str) else "",
            "stderr": f"Execution timed out after {timeout_sec} seconds",
            "execution_time_sec": elapsed,
            "diagnosis": {
                "root_cause": diag.root_cause,
                "can_auto_fix": False,
                "requires_human_or_m1_review": True,
                "remediation_advice": diag.remediation_advice,
            },
            "reflexion": {
                "mode": "diagnose_only",
                "repair_required": True,
                "constraints_may_not_be_relaxed": True,
            },
        }


def run_bounded_reflexion(
    script_path: Path,
    args: list[str] | None = None,
    cwd: Path | None = None,
    timeout_sec: int = 120,
    max_rounds: int = 3,
    repair_callback: Callable[[dict[str, Any], int], bool] | None = None,
) -> dict[str, Any]:
    """Run a bounded diagnostic/repair orchestration without mutating math contracts.

    The runner itself never edits source files or silently retries with changed
    assumptions.  A caller may supply a repair callback that performs one
    explicitly reviewed repair and returns whether a new round should run.
    Without that callback, the first failure is returned as ``blocked_for_repair``.
    """
    if max_rounds < 1:
        return {"status": "FAIL", "termination": "invalid_max_rounds", "rounds": []}
    rounds: list[dict[str, Any]] = []
    for round_index in range(1, max_rounds + 1):
        receipt = run_code_step(
            script_path=script_path,
            args=args,
            cwd=cwd,
            timeout_sec=timeout_sec,
            round_index=round_index,
            max_rounds=max_rounds,
        )
        rounds.append(receipt)
        if receipt.get("status") == "PASS":
            return {
                "status": "PASS",
                "termination": "success",
                "rounds": rounds,
                "max_rounds": max_rounds,
                "constraints_may_not_be_relaxed": True,
            }
        diagnosis = receipt.get("diagnosis", {}) if isinstance(receipt.get("diagnosis"), dict) else {}
        if not diagnosis.get("can_auto_fix"):
            return {
                "status": receipt.get("status", "FAIL"),
                "termination": "blocked_for_human_or_contract_review",
                "rounds": rounds,
                "max_rounds": max_rounds,
                "constraints_may_not_be_relaxed": True,
            }
        if repair_callback is None or not repair_callback(receipt, round_index):
            return {
                "status": "FAIL",
                "termination": "blocked_for_explicit_repair_callback",
                "rounds": rounds,
                "max_rounds": max_rounds,
                "constraints_may_not_be_relaxed": True,
            }
    return {
        "status": "FAIL",
        "termination": "max_rounds_exhausted",
        "rounds": rounds,
        "max_rounds": max_rounds,
        "constraints_may_not_be_relaxed": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run modeling code with bounded reflexion support.")
    parser.add_argument("script", help="Path to Python script to execute")
    parser.add_argument("--timeout", "-t", type=int, default=120, help="Timeout in seconds")
    parser.add_argument("--round", "-r", type=int, default=1, help="Current reflexion round index (1-based)")
    parser.add_argument("--max-rounds", type=int, default=3, help="Maximum allowed reflexion rounds")
    parser.add_argument("--output", "-o", help="Path to write execution receipt JSON")
    parser.add_argument("script_args", nargs="*", help="Arguments to pass to script")

    args = parser.parse_args()
    script_p = Path(args.script)

    result = run_code_step(
        script_path=script_p,
        args=args.script_args,
        timeout_sec=args.timeout,
        round_index=args.round,
        max_rounds=args.max_rounds,
    )

    out_str = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_str + "\n", encoding="utf-8")
        print(f"Wrote execution receipt to: {out_path}")
    else:
        print(out_str)

    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
