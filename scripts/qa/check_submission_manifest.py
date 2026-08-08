#!/usr/bin/env python3
"""Validate an F1 submission manifest and all locally referenced final files."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file, sha256_json  # noqa: E402
from validate_contracts import _validate_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--submission-manifest", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--schema-dir")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    path = resolve_path(args.submission_manifest, root).resolve()
    schema_dir = Path(args.schema_dir).resolve() if args.schema_dir else Path(__file__).resolve().parents[2] / "schemas"
    value, errors, engine = _validate_document(path, schema_dir / "submission_manifest.schema.json")
    warnings: list[str] = []
    if not isinstance(value, dict):
        value = {}

    def verify_ref(owner: str, ref: Any, *, sized: bool = False) -> None:
        if not isinstance(ref, dict):
            errors.append(f"{owner} must be a file reference")
            return
        raw_path = ref.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            errors.append(f"{owner}.path must be non-empty")
            return
        file_path = resolve_path(raw_path, root).resolve()
        if not file_path.is_file():
            errors.append(f"{owner} does not exist: {raw_path}")
            return
        if ref.get("sha256") != sha256_file(file_path):
            errors.append(f"{owner} sha256 drift: {raw_path}")
        if sized and ref.get("bytes") != file_path.stat().st_size:
            errors.append(f"{owner} byte size drift: {raw_path}")

    paper = value.get("paper")
    support = value.get("support_files", [])
    ai = value.get("ai_disclosure")
    verify_ref("paper", paper, sized=True)
    for index, ref in enumerate(support if isinstance(support, list) else []):
        verify_ref(f"support_files[{index}]", ref, sized=True)
    if ai is not None:
        verify_ref("ai_disclosure", ai, sized=True)
    verify_ref("s1_report", value.get("s1_report"))
    verify_ref("human_checkpoint", value.get("human_checkpoint"))
    for index, ref in enumerate(value.get("competition", {}).get("rule_snapshots", [])):
        verify_ref(f"competition.rule_snapshots[{index}]", ref)

    if isinstance(paper, dict) and isinstance(support, list):
        expected_package = sha256_json({"paper": paper, "support_files": support, "ai_disclosure": ai})
        if value.get("package_sha256") != expected_package:
            errors.append("package_sha256 does not match final file records")
    try:
        report_path = resolve_path(value["s1_report"]["path"], root).resolve()
        report = load_structured(report_path)
        if not isinstance(report, dict) or report.get("ok") is not True:
            errors.append("referenced S1 report does not have ok=true")
        elif report.get("competition_profile_sha256") != value.get("competition", {}).get("profile_sha256"):
            errors.append("S1 report profile hash does not match submission manifest")
    except (OSError, ValueError, TypeError, KeyError) as exc:
        errors.append(f"cannot inspect S1 report: {exc}")
    closes_at = value.get("deadline", {}).get("closes_at")
    try:
        datetime.fromisoformat(str(closes_at).replace("Z", "+00:00"))
    except ValueError:
        errors.append("deadline.closes_at must be ISO-8601")

    ok = not errors
    print(json.dumps({
        "ok": ok,
        "engine": engine,
        "submission_manifest": rel_path(path, root),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
