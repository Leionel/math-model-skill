#!/usr/bin/env python3
"""Create the immutable F1 submission manifest after a passing S1 report."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_structured, rel_path, resolve_path, sha256_file, sha256_json, write_json  # noqa: E402


def submission_file(path: Path, root: Path, *, pages: int | None = None, method: str | None = None) -> dict[str, Any]:
    return {
        "path": rel_path(path, root),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        **({"pages": pages, "page_count_method": method} if pages is not None or method is not None else {}),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--s1-report", required=True)
    parser.add_argument("--paper", required=True)
    parser.add_argument("--support", action="append", default=[])
    parser.add_argument("--ai-disclosure")
    parser.add_argument("--deadline", required=True)
    parser.add_argument("--timezone", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    manifest_path = resolve_path(args.run_manifest, root).resolve()
    report_path = resolve_path(args.s1_report, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        manifest = load_structured(manifest_path)
        report = load_structured(report_path)
        if not isinstance(manifest, dict) or not isinstance(report, dict):
            raise ValueError("run manifest and S1 report must be objects")
        gate_check = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIR / "qa" / "check_gates.py"),
                "--project-root", str(root),
                "--manifest", str(manifest_path),
                "--strict",
            ],
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        if gate_check.returncode != 0:
            raise ValueError(f"current run manifest does not pass all gates: {gate_check.stdout.strip()}")
        if manifest.get("status") != "submission_ready" or manifest.get("phase") != "submission":
            raise ValueError("F1 requires run_manifest status=submission_ready and phase=submission")
        gates = manifest.get("gates", {})
        if gates.get("w2", {}).get("status") != "pass" or gates.get("s1", {}).get("status") != "pass":
            raise ValueError("F1 requires W2 and S1 pass")
        if report.get("ok") is not True:
            raise ValueError("S1 report does not have ok=true")
        submission_reports = [
            row for row in manifest.get("artifacts", [])
            if isinstance(row, dict) and row.get("role") == "submission_qa"
        ]
        if len(submission_reports) != 1:
            raise ValueError("run manifest must register exactly one submission_qa artifact")
        expected_report = submission_reports[0]
        if (
            resolve_path(expected_report.get("path", ""), root).resolve() != report_path
            or expected_report.get("sha256") != sha256_file(report_path)
        ):
            raise ValueError("supplied S1 report is not the current submission_qa artifact")
        profile = manifest.get("competition_profile")
        if not isinstance(profile, dict):
            raise ValueError("run manifest has no competition profile")
        if report.get("competition_profile_sha256") != sha256_json(profile):
            raise ValueError("S1 report competition profile hash is stale")

        paper_path = resolve_path(args.paper, root).resolve()
        support_paths = [resolve_path(value, root).resolve() for value in args.support]
        ai_path = resolve_path(args.ai_disclosure, root).resolve() if args.ai_disclosure else None
        for path in [paper_path, *support_paths, *([ai_path] if ai_path else [])]:
            if path is None or not path.is_file():
                raise ValueError(f"final submission artifact does not exist: {path}")
        report_inputs = {
            (row.get("role"), row.get("path")): row.get("sha256")
            for row in report.get("inputs", [])
            if isinstance(row, dict)
        }
        expected = [
            ("paper", paper_path),
            *(("support", path) for path in support_paths),
            *(("ai_disclosure", ai_path) for _ in [0] if ai_path is not None),
        ]
        for role, path in expected:
            key = (role, rel_path(path, root))
            if report_inputs.get(key) != sha256_file(path):
                raise ValueError(f"S1 report does not cover current {role} artifact: {key[1]}")

        paper_input = next(row for row in report["inputs"] if row.get("role") == "paper")
        paper_record = submission_file(
            paper_path,
            root,
            pages=paper_input.get("pages"),
            method=paper_input.get("page_count_method"),
        )
        support_records = [submission_file(path, root) for path in support_paths]
        ai_record = submission_file(ai_path, root) if ai_path else None
        package_hash = sha256_json({
            "paper": paper_record,
            "support_files": support_records,
            "ai_disclosure": ai_record,
        })
        try:
            datetime.fromisoformat(args.deadline.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("--deadline must be ISO-8601") from exc
        if not args.timezone.strip():
            raise ValueError("--timezone must be non-empty")
        submission = {
            "schema_version": "1.0",
            "project_id": manifest["project_id"],
            "run_id": manifest["run_id"],
            "status": "final_frozen",
            "frozen_at": datetime.now(timezone.utc).isoformat(),
            "competition": {
                "profile_id": profile["profile_id"],
                "competition": profile["competition"],
                "season": profile["season"],
                "profile_sha256": sha256_json(profile),
                "rule_snapshots": [rule["snapshot"] for rule in profile["official_rules"]],
            },
            "deadline": {"closes_at": args.deadline, "timezone": args.timezone},
            "paper": paper_record,
            "support_files": support_records,
            "ai_disclosure": ai_record,
            "s1_report": {"path": rel_path(report_path, root), "sha256": sha256_file(report_path)},
            "human_checkpoint": {"path": rel_path(manifest_path, root), "sha256": sha256_file(manifest_path)},
            "package_sha256": package_hash,
            "builder": {"name": "freeze_submission.py", "version": "1.0"},
        }
        write_json(output_path, submission)
    except (OSError, ValueError, KeyError, StopIteration, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "final_frozen", "output": rel_path(output_path, root), "package_sha256": package_hash}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
