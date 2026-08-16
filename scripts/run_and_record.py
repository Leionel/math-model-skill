#!/usr/bin/env python3
"""Run a real subprocess and emit a process-captured command receipt plus run-index entry.

The exit code, timestamps, stdout/stderr and IO hashes are captured from the
actual process; nothing in the receipt is hand-editable by design (regenerate
by rerunning). Every run -- including failures -- is appended to the run index
so that "best-seed-only reporting" cannot hide candidate/tuning runs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import write_json  # noqa: E402


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Logical run id shared by receipts of the same experiment.")
    parser.add_argument("--stage", required=True, choices=("safety", "smoke", "full", "freeze", "evidence", "qa", "review", "submission"))
    parser.add_argument("--receipt", required=True, help="Output receipt JSON path.")
    parser.add_argument("--index", help="Run-index JSON path; entry is appended (file created if missing).")
    parser.add_argument("--selection-policy", default="first successful run of this stage is selected", help="Pre-declared rule for choosing the selected run.")
    parser.add_argument("--selected", action="store_true", help="Mark this run as selected under the declared policy.")
    parser.add_argument("--note", default="", help="Free-form note recorded in the index entry.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed forwarded to the child (also recorded).")
    parser.add_argument("--input", action="append", default=[], help="Input file to hash before the run (repeatable).")
    parser.add_argument("--output-artifact", action="append", default=[], help="Output file to hash after the run (repeatable).")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("argv", nargs=argparse.REMAINDER, help="Command to execute after '--', e.g. -- python train.py --x 1")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    argv = [part for part in args.argv if part != "--"]
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        print(json.dumps({"ok": False, "errors": ["no command given after '--'"]}, ensure_ascii=False))
        return 2

    receipt_path = (root / args.receipt).resolve() if not Path(args.receipt).is_absolute() else Path(args.receipt)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    command_id = f"CMD-{uuid.uuid4().hex[:12]}"
    stdout_path = receipt_path.with_suffix(receipt_path.suffix + ".stdout")
    stderr_path = receipt_path.with_suffix(receipt_path.suffix + ".stderr")

    input_refs = []
    for raw in args.input:
        path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw)
        if not path.is_file():
            print(json.dumps({"ok": False, "errors": [f"input does not exist: {raw}"]}, ensure_ascii=False))
            return 2
        input_refs.append({"path": str(path), "sha256": sha256_file(path)})

    output_targets = []
    for raw in args.output_artifact:
        path = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw)
        output_targets.append((path, path.is_file()))

    started = datetime.now(timezone.utc)
    result = subprocess.run(
        argv,
        cwd=str(root),
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    finished = datetime.now(timezone.utc)
    stdout_path.write_text(result.stdout or "", encoding="utf-8")
    stderr_path.write_text(result.stderr or "", encoding="utf-8")

    output_refs = []
    for path, existed_before in output_targets:
        if path.is_file():
            output_refs.append({"path": str(path), "sha256": sha256_file(path), "existed_before": existed_before})
        else:
            print(json.dumps({"ok": False, "errors": [f"declared output was not produced: {path}"]}, ensure_ascii=False))
            return 3

    receipt = {
        "schema_version": "1.0",
        "command_id": command_id,
        "run_id": args.run_id,
        "stage": args.stage,
        "argv": argv,
        "cwd": str(root),
        "exit_code": result.returncode,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_s": round((finished - started).total_seconds(), 3),
        "seed": args.seed,
        "stdout_path": str(stdout_path),
        "stderr_path": str(stderr_path),
        "stdout_sha256": sha256_file(stdout_path),
        "stderr_sha256": sha256_file(stderr_path),
        "input_refs": input_refs,
        "output_refs": output_refs,
        "env_note": "environment inherited from parent process; not captured",
    }
    write_json(receipt_path, receipt)

    if args.index:
        index_path = (root / args.index).resolve() if not Path(args.index).is_absolute() else Path(args.index)
        if index_path.is_file():
            index = json.loads(index_path.read_text(encoding="utf-8"))
        else:
            index = {"schema_version": "1.0", "run_id_scope": args.run_id, "selection_policy": args.selection_policy, "runs": []}
        index["runs"].append({
            "command_id": command_id,
            "run_id": args.run_id,
            "stage": args.stage,
            "argv": argv,
            "exit_code": result.returncode,
            "receipt_path": str(receipt_path),
            "selected": bool(args.selected),
            "note": args.note,
            "recorded_at": finished.isoformat(),
        })
        # The run index is an append-style ledger by design: rewriting it after
        # each append is expected, so overwrite is allowed here (receipts are not).
        write_json(index_path, index, overwrite=True)

    print(json.dumps({
        "ok": result.returncode == 0,
        "command_id": command_id,
        "exit_code": result.returncode,
        "receipt": str(receipt_path),
        "index_entry": bool(args.index),
    }, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
