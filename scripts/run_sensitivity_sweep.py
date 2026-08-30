#!/usr/bin/env python3
"""Run one sensitivity sweep and summarize it into a single experiment artifact.

Each grid point runs a real command through ``run_and_record.py`` with
``stage=evidence``, so every point keeps its own process receipt; the runner
then assembles a schema-conforming ``sensitivity_experiment`` artifact plus a
summary artifact, and finally dispatches ``check_sensitivity_experiment.py``
with ``--require-execution-receipts`` so the emitted artifact must pass the
existing checker.

The command template after ``--`` must contain ``{value}`` (the grid value)
and ``{artifact}`` (where the point must write its own result artifact)::

    python run_sensitivity_sweep.py --run-id run-1 --experiment-id SE-ALPHA \
        --question-id q1 --parameter alpha --grid 0.1,0.5,0.9 --baseline 0.5 \
        --metric-id objective --metric-unit kg --metric-definition "total cost" \
        -- python solve.py --alpha {value} --out {artifact}
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import child_env, load_structured, rel_path, require_within, resolve_path, sha256_file, write_json  # noqa: E402


def _parse_grid(raw: str) -> list[float]:
    values: list[float] = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = float(token)
        except ValueError as exc:
            raise ValueError(f"grid value is not numeric: {token!r}") from exc
        if not math.isfinite(value):
            raise ValueError(f"grid value must be finite: {token!r}")
        values.append(value)
    if len(values) != len(set(values)):
        raise ValueError("grid values must be distinct")
    if len(values) < 2:
        raise ValueError("a sweep needs at least two grid values")
    return values


def _template_errors(template: list[str]) -> list[str]:
    errors = []
    joined = " ".join(template)
    if "{value}" not in joined:
        errors.append("command template must contain {value}")
    if "{artifact}" not in joined:
        errors.append("command template must contain {artifact} so each grid point writes its own artifact")
    return errors


def run_sweep(
    root: Path,
    *,
    run_id: str,
    experiment_id: str,
    question_id: str,
    parameter: str,
    grid: list[float],
    baseline: float,
    metric: dict[str, str],
    template: list[str],
    rerun_policy: str,
    rerun_policy_detail: str | None = None,
    parameter_id: str | None = None,
    model_id: str | None = None,
    impact_class: str | None = None,
    index: str = "run_index.json",
    manifest: str | None = None,
    integrity_mode: str = "research",
    output: str | None = None,
    results: str | None = None,
) -> dict[str, Any]:
    errors = _template_errors(template)
    if errors:
        return {"ok": False, "errors": errors}
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", experiment_id) is None:
        raise ValueError("--experiment-id must start with an alphanumeric character and contain only letters, numbers, '.', '_' or '-'")
    root = root.resolve()
    experiment_path = require_within(
        resolve_path(output or f".harness/reports/sensitivity_{experiment_id}.json", root),
        root,
        label="--output",
    )
    point_dir = require_within(root / ".harness" / "results" / "sensitivity" / experiment_id, root, label="sensitivity point directory")
    receipt_dir = root / ".harness" / "receipts"
    summary_path = require_within(
        resolve_path(results or f".harness/results/sensitivity/{experiment_id}/summary.json", root),
        root,
        label="--results",
    )
    raw_index = root / index if not Path(index).is_absolute() else Path(index)
    require_within(raw_index, root, label="--index")

    point_paths = [point_dir / f"point_{position}.json" for position in range(len(grid))]
    receipt_paths = [receipt_dir / f"sensitivity_{experiment_id}_point_{position}.json" for position in range(len(grid))]
    immutable_paths = [experiment_path, summary_path]
    for receipt_path in receipt_paths:
        immutable_paths.extend(
            [
                receipt_path,
                receipt_path.with_suffix(receipt_path.suffix + ".stdout"),
                receipt_path.with_suffix(receipt_path.suffix + ".stderr"),
            ]
        )
    immutable_paths.extend(point_paths)
    occupied = next((path for path in immutable_paths if path.exists()), None)
    if occupied is not None:
        raise FileExistsError(f"refusing to overwrite earlier sensitivity artifact: {occupied}")
    point_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    runs: list[dict[str, Any]] = []
    summary_points: list[dict[str, Any]] = []
    point_errors: list[str] = []
    for position, value in enumerate(grid):
        artifact_path = point_paths[position]
        receipt_path = receipt_paths[position]
        argv = [
            token.replace("{value}", str(value)).replace("{artifact}", rel_path(artifact_path, root))
            for token in template
        ]
        record_args = [
            sys.executable, str(SCRIPT_DIR / "run_and_record.py"),
            "--run-id", run_id,
            "--stage", "evidence",
            "--receipt", rel_path(receipt_path, root),
            "--index", index,
            "--project-root", str(root),
            "--output-artifact", rel_path(artifact_path, root),
            "--note", f"sensitivity sweep {experiment_id} grid point {value}",
        ]
        if manifest:
            record_args.extend(["--manifest", manifest])
        else:
            record_args.extend(["--v2", "--integrity-mode", integrity_mode])
        record_args.extend(["--", *argv])
        record = subprocess.run(
            record_args, text=True, capture_output=True, encoding="utf-8", errors="replace",
            env=child_env(), check=False,
        )
        try:
            record_report = json.loads(record.stdout)
        except json.JSONDecodeError:
            record_report = {}
        receipt: dict[str, Any] = {}
        if receipt_path.is_file():
            try:
                loaded = load_structured(receipt_path)
                receipt = loaded if isinstance(loaded, dict) else {}
            except (OSError, ValueError, TypeError):
                receipt = {}
        exit_code = receipt.get("exit_code", record_report.get("exit_code"))
        artifact_ok = artifact_path.is_file()
        metric_value = None
        metric_error = None
        if artifact_ok:
            try:
                payload = load_structured(artifact_path)
                if not isinstance(payload, dict) or metric["metric_id"] not in payload:
                    metric_error = f"point {position} artifact is missing declared metric {metric['metric_id']!r}"
                else:
                    candidate = payload[metric["metric_id"]]
                    if isinstance(candidate, bool) or not isinstance(candidate, (int, float)):
                        metric_error = f"point {position} metric {metric['metric_id']!r} must be numeric"
                    elif not math.isfinite(float(candidate)):
                        metric_error = f"point {position} metric {metric['metric_id']!r} must be finite"
                    else:
                        metric_value = candidate
            except (OSError, ValueError, TypeError) as exc:
                metric_error = f"point {position} artifact cannot be read: {exc}"
        if not artifact_ok or metric_error is not None:
            status = "ERROR"
        elif exit_code == 0:
            status = "PASS"
        else:
            status = "FAIL"
        if metric_error is not None:
            point_errors.append(metric_error)
        run: dict[str, Any] = {
            "grid_value": value,
            "status": status,
            "artifact": {"path": rel_path(artifact_path, root)},
        }
        if artifact_ok:
            run["artifact"]["sha256"] = sha256_file(artifact_path)
        if receipt:
            run["execution"] = {
                "status": "completed" if receipt.get("exit_code") == 0 else "failed",
                "command": receipt.get("argv", argv),
                "exit_code": receipt.get("exit_code"),
                "started_at": receipt.get("started_at"),
                "finished_at": receipt.get("finished_at"),
                "input_parameter": parameter,
                "input_value": value,
                "runner": "run_and_record.py",
                "receipt": {
                    "path": rel_path(receipt_path, root),
                    "sha256": sha256_file(receipt_path),
                },
            }
        runs.append(run)
        summary_points.append({
            "grid_value": value,
            "status": status,
            "exit_code": exit_code,
            "artifact": rel_path(artifact_path, root),
            "receipt": rel_path(receipt_path, root) if receipt_path.is_file() else None,
            "metric_value": metric_value,
            **({"error": metric_error} if metric_error else {}),
        })

    all_pass = all(row["status"] == "PASS" for row in runs)
    summary = {
        "experiment_id": experiment_id,
        "run_id": run_id,
        "parameter": parameter,
        "grid": grid,
        "baseline": baseline,
        "points": summary_points,
        "verdict": "stable" if all_pass else "incomplete",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(summary_path, summary)
    experiment: dict[str, Any] = {
        "schema_version": "1.0",
        "experiment_id": experiment_id,
        "run_id": run_id,
        "question_id": question_id,
        "status": "completed" if all_pass else "failed",
        "parameter": parameter,
        "baseline": baseline,
        "grid": grid,
        "rerun_policy": rerun_policy,
        "metrics": [metric],
        "results_artifact": {"path": rel_path(summary_path, root), "sha256": sha256_file(summary_path)},
        "runs": runs,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if parameter_id:
        experiment["parameter_id"] = parameter_id
    if model_id:
        experiment["model_id"] = model_id
    if impact_class:
        experiment["impact_class"] = impact_class
    if rerun_policy == "other" and rerun_policy_detail:
        experiment["rerun_policy_detail"] = rerun_policy_detail
    experiment_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(experiment_path, experiment)

    checker_args = [
        sys.executable, str(SCRIPT_DIR / "qa" / "check_sensitivity_experiment.py"),
        "--experiment", str(experiment_path),
        "--project-root", str(root),
        "--run-id", run_id,
        "--strict",
        "--require-execution-receipts",
    ]
    checker = subprocess.run(
        checker_args, text=True, capture_output=True, encoding="utf-8", errors="replace",
        env=child_env(), check=False,
    )
    try:
        checker_report = json.loads(checker.stdout)
    except json.JSONDecodeError:
        checker_report = {"ok": False, "errors": [checker.stdout.strip() or checker.stderr.strip()]}
    ok = bool(checker_report.get("ok")) and all_pass
    checker_errors = checker_report.get("errors", []) if isinstance(checker_report.get("errors"), list) else []
    return {
        "ok": ok,
        "experiment": rel_path(experiment_path, root),
        "summary": rel_path(summary_path, root),
        "runs": len(runs),
        "passed": sum(1 for row in runs if row["status"] == "PASS"),
        "checker": checker_report,
        "errors": [] if ok else [*point_errors, *checker_errors] or ["sensitivity sweep did not complete"],
        "boundary": "Each grid point ran once through run_and_record.py; no receipt was fabricated.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--experiment-id", required=True)
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--parameter", required=True)
    parser.add_argument("--parameter-id")
    parser.add_argument("--model-id")
    parser.add_argument("--impact-class", choices=("low", "medium", "high", "critical"))
    parser.add_argument("--grid", required=True, help="comma-separated numeric grid values")
    parser.add_argument("--baseline", required=True, type=float)
    parser.add_argument("--rerun-policy", choices=("full_reoptimization", "refit", "recompute", "other"), default="recompute")
    parser.add_argument("--rerun-policy-detail")
    parser.add_argument("--metric-id", required=True)
    parser.add_argument("--metric-unit", required=True)
    parser.add_argument("--metric-definition", required=True)
    parser.add_argument("--metric-direction", choices=("higher_is_better", "lower_is_better", "descriptive"))
    parser.add_argument("--index", default="run_index.json")
    parser.add_argument("--manifest", help="v2 run_manifest; forwarded to run_and_record")
    parser.add_argument("--integrity-mode", choices=("sprint", "research", "submission"), default="research")
    parser.add_argument("--output", help="experiment artifact path; defaults to .harness/reports/sensitivity_<experiment-id>.json")
    parser.add_argument("--results", help="summary artifact path; defaults to .harness/results/sensitivity/<experiment-id>/summary.json")
    parser.add_argument("template", nargs=argparse.REMAINDER, help="command template after -- with {value} and {artifact}")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    template = list(args.template)
    if template and template[0] == "--":
        template = template[1:]
    if not template:
        print(json.dumps({"ok": False, "errors": ["a command template after -- is required"]}, ensure_ascii=False, indent=2))
        return 1
    try:
        grid = _parse_grid(args.grid)
    except ValueError as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    if not math.isfinite(args.baseline):
        print(json.dumps({"ok": False, "errors": ["baseline must be finite"]}, ensure_ascii=False, indent=2))
        return 1
    metric: dict[str, str] = {
        "metric_id": args.metric_id,
        "unit": args.metric_unit,
        "definition": args.metric_definition,
    }
    if args.metric_direction:
        metric["direction"] = args.metric_direction
    try:
        result = run_sweep(
            root,
            run_id=args.run_id,
            experiment_id=args.experiment_id,
            question_id=args.question_id,
            parameter=args.parameter,
            grid=grid,
            baseline=args.baseline,
            metric=metric,
            template=template,
            rerun_policy=args.rerun_policy,
            rerun_policy_detail=args.rerun_policy_detail,
            parameter_id=args.parameter_id,
            model_id=args.model_id,
            impact_class=args.impact_class,
            index=args.index,
            manifest=args.manifest,
            integrity_mode=args.integrity_mode,
            output=args.output,
            results=args.results,
        )
    except (OSError, ValueError, TypeError) as exc:
        suffix = "; use a new experiment id or remove the earlier sweep artifacts" if isinstance(exc, FileExistsError) else ""
        print(json.dumps({"ok": False, "errors": [f"{exc}{suffix}"]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
