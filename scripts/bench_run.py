#!/usr/bin/env python3
"""Re-run one declared task against a harness revision and record engineering facts.

This is a harness-version regression lab, not a capability benchmark: a report
holds the exit code, wall time, gate outcomes and freshness of whatever the task
produced, so two revisions can be compared on the same task.  It never scores a
model, and a failing run is a recorded fact (``exit_code``) rather than an
exception.  The task declaration contract is ``schemas/bench_task.schema.json``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

import runtime  # noqa: E402
from _common import child_env, load_structured  # noqa: E402


def load_task(task_dir: Path | str) -> dict[str, Any]:
    """Read and validate one bench task declaration."""

    directory = Path(task_dir).resolve()
    declaration_path = directory / "bench_task.json"
    if not declaration_path.is_file():
        raise ValueError(f"bench task declaration is missing: {declaration_path}")
    task = load_structured(declaration_path)
    if not isinstance(task, Mapping):
        raise ValueError("bench_task.json must be an object")
    for key in ("schema_version", "task_id", "entry", "arguments", "timeout_seconds"):
        if key not in task:
            raise ValueError(f"bench_task.json is missing {key}")
    entry = (directory / str(task["entry"])).resolve()
    if not entry.is_file():
        raise ValueError(f"bench task entry does not exist: {task['entry']}")
    return {**dict(task), "directory": str(directory), "entry_path": str(entry)}


def harness_revision(harness_root: Path) -> str | None:
    result = subprocess.run(
        ["git", "-C", str(harness_root), "rev-parse", "HEAD"],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    revision = result.stdout.strip()
    return revision or None


def resolve_ref(repo_root: Path, ref: str) -> str:
    """Resolve one git revision to its object name for the report identity."""

    result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", ref],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    revision = result.stdout.strip()
    if result.returncode != 0 or not revision:
        raise ValueError(f"cannot resolve harness ref {ref}: {result.stderr.strip()}")
    return revision


def extract_harness_ref(repo_root: Path, ref: str, destination: Path) -> Path:
    """Materialize one git revision as a harness checkout without touching the work tree."""

    archive = destination / "harness.tar"
    destination.mkdir(parents=True, exist_ok=True)
    archived = subprocess.run(
        ["git", "-C", str(repo_root), "archive", "--format=tar", f"--output={archive}", ref],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if archived.returncode != 0:
        raise ValueError(f"cannot archive harness ref {ref}: {archived.stderr.strip() or archived.stdout.strip()}")
    checkout = destination / "checkout"
    checkout.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive) as bundle:
        bundle.extractall(checkout)
    return checkout


def _project_facts(workdir: Path) -> dict[str, Any]:
    if not (workdir / "run_manifest.json").is_file() and not (workdir / ".harness").is_dir():
        return {"present": False}
    view = runtime.get_state(workdir)
    payload = view.payload
    gates = payload.get("gates", {}) if isinstance(payload.get("gates"), Mapping) else {}
    receipts = payload.get("receipts", {}) if isinstance(payload.get("receipts"), Mapping) else {}
    dag = payload.get("dag", {}) if isinstance(payload.get("dag"), Mapping) else {}
    artifacts = dag.get("artifacts", []) if isinstance(dag.get("artifacts"), list) else []
    return {
        "present": True,
        "exit_code": view.exit_code,
        "gates": {name: view_row.get("status") for name, view_row in sorted(gates.items()) if isinstance(view_row, Mapping)},
        "first_blocked_gate": payload.get("first_blocked_gate"),
        "stale_artifacts": sorted(
            str(row.get("artifact_id")) for row in artifacts if isinstance(row, Mapping) and row.get("freshness") != "current"
        ),
        "receipts": {
            "count": receipts.get("count", 0),
            "failed": sorted(str(value) for value in receipts.get("failed_receipt_ids", [])),
        },
    }


def run_bench(
    task_dir: Path | str,
    *,
    harness_root: Path | str = REPO_ROOT,
    harness_ref: str | None = None,
    repo_root: Path | str = REPO_ROOT,
    output_path: Path | str,
    label: str | None = None,
    keep_workdir: bool = False,
    timeout: int | None = None,
) -> dict[str, Any]:
    """Run one declared task and write its engineering report.

    ``harness_ref`` materializes a git revision into a scratch checkout, which is
    how two harness versions are compared on the same task.
    """

    resolved_repo = Path(repo_root).resolve()
    scratch: tempfile.TemporaryDirectory[str] | None = None
    ref_identity: str | None = None
    if harness_ref:
        # The task is re-read from the extracted revision: a version regression
        # must run that revision's entry script, not the working tree's.
        try:
            relative_task = Path(task_dir).resolve().relative_to(resolved_repo)
        except ValueError as exc:
            raise ValueError("--harness-ref requires --task to live inside the harness repository") from exc
        ref_identity = resolve_ref(resolved_repo, harness_ref)
        scratch = tempfile.TemporaryDirectory(prefix="bench-harness-")
        harness = extract_harness_ref(resolved_repo, harness_ref, Path(scratch.name))
        task = load_task(harness / relative_task)
    else:
        harness = Path(harness_root).resolve()
        task = load_task(task_dir)
    limit = int(timeout or task["timeout_seconds"])
    workdir = Path(tempfile.mkdtemp(prefix="bench-workdir-"))
    arguments = [str(argument).replace("{workdir}", str(workdir)) for argument in task["arguments"]]
    started = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            [sys.executable, str(task["entry_path"]), *arguments],
            cwd=str(harness),
            text=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            env=child_env(),
            timeout=limit,
            check=False,
        )
        exit_code = completed.returncode
        stdout_tail = "\n".join((completed.stdout or "").strip().splitlines()[-5:])
        stderr_tail = "\n".join((completed.stderr or "").strip().splitlines()[-5:])
    except subprocess.TimeoutExpired:
        timed_out = True
        exit_code = None
        stdout_tail = ""
        stderr_tail = f"timed out after {limit}s"
    wall_seconds = round(time.monotonic() - started, 3)
    report = {
        "schema_version": "1.0",
        "label": label or task["task_id"],
        "task": {
            "task_id": task["task_id"],
            "directory": task["directory"],
            "entry": task["entry"],
            "arguments": task["arguments"],
        },
        "harness": {
            "root": str(harness),
            "ref": harness_ref,
            "revision": ref_identity or harness_revision(harness),
            "python": sys.version.split()[0],
        },
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "exit_code": exit_code,
        "timed_out": timed_out,
        "timeout_seconds": limit,
        "wall_seconds": wall_seconds,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
        "project": _project_facts(workdir),
        "workdir": str(workdir) if keep_workdir else None,
        "scope": "harness-version regression evidence; not a capability benchmark",
    }
    target = Path(output_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if scratch is not None:
        scratch.cleanup()
    return report


def compare_bench(report_a: Path | str, report_b: Path | str) -> dict[str, Any]:
    """Compare two bench reports as deltas, without ranking them."""

    a = load_structured(Path(report_a))
    b = load_structured(Path(report_b))
    if not isinstance(a, Mapping) or not isinstance(b, Mapping):
        raise ValueError("bench reports must be objects")
    gates_a = a.get("project", {}).get("gates", {}) if isinstance(a.get("project"), Mapping) else {}
    gates_b = b.get("project", {}).get("gates", {}) if isinstance(b.get("project"), Mapping) else {}
    return {
        "schema_version": "1.0",
        "ok": True,
        "a": {"label": a.get("label"), "revision": a.get("harness", {}).get("revision"), "exit_code": a.get("exit_code")},
        "b": {"label": b.get("label"), "revision": b.get("harness", {}).get("revision"), "exit_code": b.get("exit_code")},
        "task_equal": a.get("task", {}).get("task_id") == b.get("task", {}).get("task_id"),
        "deltas": {
            "exit_code": {"a": a.get("exit_code"), "b": b.get("exit_code")},
            "wall_seconds": {"a": a.get("wall_seconds"), "b": b.get("wall_seconds")},
            "timed_out": {"a": a.get("timed_out"), "b": b.get("timed_out")},
        },
        "gates_changed": {
            name: {"a": gates_a.get(name), "b": gates_b.get(name)}
            for name in sorted(set(gates_a) | set(gates_b))
            if gates_a.get(name) != gates_b.get(name)
        },
        "stale_artifacts": {
            "a": a.get("project", {}).get("stale_artifacts", []) if isinstance(a.get("project"), Mapping) else [],
            "b": b.get("project", {}).get("stale_artifacts", []) if isinstance(b.get("project"), Mapping) else [],
        },
        "scope": "engineering deltas for the same task; no capability claim",
    }


def human_summary(report: Mapping[str, Any]) -> str:
    project = report.get("project", {}) if isinstance(report.get("project"), Mapping) else {}
    gates = project.get("gates", {}) if isinstance(project.get("gates"), Mapping) else {}
    return "\n".join([
        f"task {report.get('task', {}).get('task_id')}  revision {report.get('harness', {}).get('revision')}",
        f"exit {report.get('exit_code')}  wall {report.get('wall_seconds')}s  timed_out {report.get('timed_out')}",
        "gates: " + "  ".join(f"{name}:{value}" for name, value in sorted(gates.items())),
    ])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    run = sub.add_parser("run")
    run.add_argument("--task", required=True)
    run.add_argument("--harness-root", default=str(REPO_ROOT))
    run.add_argument("--harness-ref", help="git revision to extract and use as the harness under test")
    run.add_argument("--output", required=True)
    run.add_argument("--label")
    run.add_argument("--timeout", type=int)
    run.add_argument("--keep-workdir", action="store_true")
    run.add_argument("--json", action="store_true")
    compare = sub.add_parser("compare")
    compare.add_argument("report_a")
    compare.add_argument("report_b")
    compare.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.action == "run":
            report = run_bench(
                args.task,
                harness_root=args.harness_root,
                harness_ref=args.harness_ref,
                output_path=args.output,
                label=args.label,
                keep_workdir=args.keep_workdir,
                timeout=args.timeout,
            )
            print(json.dumps(report, ensure_ascii=False) if args.json else human_summary(report))
            return 0
        document = compare_bench(args.report_a, args.report_b)
        print(json.dumps(document, ensure_ascii=False, indent=2) if args.json else json.dumps(document["deltas"], ensure_ascii=False))
        return 0
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())