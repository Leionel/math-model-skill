"""A/B/C ablation runner skeleton.

Pre-registered in ``evaluation/PREREGISTRATION.md`` before any result existed.
This file can launch the three conditions and score their outputs, but it
refuses to publish a number it did not observe: without real backend runs,
interaction logs and a filled budget manifest, ``run()`` returns
``status: NOT_RUN`` and writes no results file.

That refusal is the point. The repository rule is that a plan, a demo or a
green regression suite must never be presented as a capability benchmark, so
the ablation surface ships as machinery, not as a result.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

EVALUATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALUATION_DIR.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

CONDITIONS = {
    "A_single_llm_prompt": {
        "harness": False,
        "agents": 1,
        "note": "one model, one prompt, no Gate and no receipt seam",
    },
    "B_multi_agent_no_harness": {
        "harness": False,
        "agents": 7,
        "note": "the same seven roles and contracts, but no deterministic control plane",
    },
    "C_multi_agent_with_harness": {
        "harness": True,
        "agents": 7,
        "note": "roles plus contracts plus the Gate/Receipt/DAG/Freeze plane",
    },
}

METRICS = (
    "gate_bypass_rate",
    "fabricated_evidence_rate",
    "stale_artifact_acceptance_rate",
    "unsupported_claim_rate",
    "reviewer_independence_violation_rate",
    "stage_completion_rate",
    "recovery_after_failure_rate",
    "valid_artifact_rate",
    "end_to_end_completion_rate",
    "tool_calls",
    "wall_clock_seconds",
    "input_tokens",
    "output_tokens",
    "repeated_work_ratio",
)


def budget_manifest() -> dict[str, object]:
    """The frozen run budget, declared before any condition is executed."""

    return {
        "tasks": ["examples/end_to_end depot allocation", "3 further synthetic tasks (TBD)"],
        "repeats_per_task": 3,
        "max_turns_per_condition": 40,
        "max_wall_clock_seconds_per_run": 900,
        "temperature": 0,
        "shared_prompt_text": "agents/<role>/agent.yaml is the only role specification",
        "scoring": {
            "reliability": "evaluation/redteam.py probes applied to the produced project",
            "completion": "harness status first_blocker is null for the target stage",
            "efficiency": "counted from backend logs, not estimated",
        },
        "excluded_from_claim": [
            "award probability",
            "mathematical correctness beyond what a Gate can establish",
        ],
    }


def score(condition_dir: Path) -> dict[str, object]:
    """Score one condition run from its own logs and final project state."""

    manifest_path = condition_dir / "run_log.json"
    if not manifest_path.is_file():
        raise SystemExit(f"missing run log: {manifest_path}")
    log = json.loads(manifest_path.read_text(encoding="utf-8"))
    timings = [float(row.get("wall_clock_seconds", 0.0)) for row in log.get("runs", [])]
    return {
        "condition": condition_dir.name,
        "runs": len(log.get("runs", [])),
        "end_to_end_completion_rate": (
            sum(1 for row in log.get("runs", []) if row.get("reached_stage") == log.get("target_stage"))
            / max(len(log.get("runs", [])), 1)
        ),
        "wall_clock_seconds": statistics.fmean(timings) if timings else 0.0,
        "input_tokens": sum(int(row.get("input_tokens", 0)) for row in log.get("runs", [])),
        "output_tokens": sum(int(row.get("output_tokens", 0)) for row in log.get("runs", [])),
        "tool_calls": sum(int(row.get("tool_calls", 0)) for row in log.get("runs", [])),
    }


def run(results_dir: Path | None) -> dict[str, object]:
    pre = {
        "status": "NOT_RUN",
        "reason": (
            "no real backend runs were executed against all three conditions with the "
            "pre-registered budget"
        ),
        "conditions": CONDITIONS,
        "metrics": list(METRICS),
        "budget": budget_manifest(),
        "preregistration": "evaluation/PREREGISTRATION.md",
        "how_to_run": (
            "execute each condition against the task set, write <results_dir>/<condition>/run_log.json, "
            "then call: python evaluation/ablation.py score --results-dir <results_dir>"
        ),
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    if results_dir is None:
        return pre
    conditions = {}
    for child in sorted(path for path in results_dir.iterdir() if path.is_dir()):
        conditions[child.name] = score(child)
    missing = sorted(set(CONDITIONS) - set(conditions))
    if missing:
        raise SystemExit(f"ablation results are incomplete; missing conditions: {missing}")
    return {
        "status": "RUN",
        "conditions": conditions,
        "budget": budget_manifest(),
        "recorded_at": pre["recorded_at"],
        "honesty_note": (
            "reliability rates must come from evaluation/redteam.py probes applied to each "
            "condition's produced project, not from the model's own summary"
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="print the pre-registered design without running anything")
    plan.add_argument("--json", action="store_true")
    score_cmd = sub.add_parser("score", help="score executed condition runs")
    score_cmd.add_argument("--results-dir", required=True, type=Path)
    score_cmd.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "plan":
        report = run(None)
    else:
        report = run(args.results_dir)
    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"ablation status: {report['status']}")
        if report["status"] == "NOT_RUN":
            print(f"  reason: {report['reason']}")
            for name, condition in report["conditions"].items():
                print(f"  {name}: {condition['note']}")
            print(f"  metrics: {', '.join(report['metrics'])}")
            print(f"  {report['how_to_run']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
