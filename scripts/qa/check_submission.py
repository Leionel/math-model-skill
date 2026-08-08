#!/usr/bin/env python3
"""Validate a final package against the pinned competition submission profile."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file, sha256_json, write_json  # noqa: E402


def file_record(path: Path, root: Path, role: str, *, pages: int | None = None, method: str | None = None) -> dict[str, Any]:
    record: dict[str, Any] = {
        "role": role,
        "path": rel_path(path, root),
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
    }
    if role == "paper":
        record["pages"] = pages
        record["page_count_method"] = method
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-manifest", required=True)
    parser.add_argument("--paper", required=True)
    parser.add_argument("--paper-pages", type=int)
    parser.add_argument("--page-count-method", choices=["pdfinfo", "pypdf", "manual_verified", "not_applicable"])
    parser.add_argument("--support", action="append", default=[])
    parser.add_argument("--ai-disclosure")
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    manifest_path = resolve_path(args.run_manifest, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = load_structured(manifest_path)
        if not isinstance(manifest, dict):
            raise ValueError("run_manifest must be an object")
        profile = manifest.get("competition_profile")
        if not isinstance(profile, dict):
            raise ValueError("run_manifest has no competition_profile")
        rules = profile.get("submission")
        if not isinstance(rules, dict):
            raise ValueError("competition_profile has no submission rules")
        if manifest.get("gates", {}).get("w2", {}).get("status") != "pass":
            errors.append("submission QA requires W2 pass")

        paper = resolve_path(args.paper, root).resolve()
        if not paper.is_file():
            raise ValueError(f"paper does not exist: {args.paper}")
        paper_record = file_record(paper, root, "paper", pages=args.paper_pages, method=args.page_count_method)
        allowed_extensions = {str(value).lower() for value in rules.get("paper_extensions", [])}
        if paper.suffix.lower() not in allowed_extensions:
            errors.append(f"paper extension {paper.suffix!r} is not allowed by profile")
        if paper_record["bytes"] > rules.get("max_paper_bytes", 0):
            errors.append(f"paper exceeds max_paper_bytes: {paper_record['bytes']}")
        max_pages = rules.get("max_pages")
        if max_pages is not None:
            if not isinstance(args.paper_pages, int) or args.paper_pages < 1:
                errors.append("paper page count is required by this profile")
            elif args.paper_pages > max_pages:
                errors.append(f"paper has {args.paper_pages} pages; profile maximum is {max_pages}")
            if args.page_count_method not in {"pdfinfo", "pypdf", "manual_verified"}:
                errors.append("page_count_method must describe how the page count was verified")

        support_records: list[dict[str, Any]] = []
        for raw_path in args.support:
            path = resolve_path(raw_path, root).resolve()
            if not path.is_file():
                raise ValueError(f"support file does not exist: {raw_path}")
            support_records.append(file_record(path, root, "support"))
        support_policy = rules.get("support_policy")
        if support_policy == "prohibited" and support_records:
            errors.append("support files are prohibited by this profile")
        if support_policy == "required" and not support_records:
            errors.append("at least one support file is required by this profile")
        max_support = rules.get("max_support_bytes")
        support_bytes = sum(row["bytes"] for row in support_records)
        if max_support is not None and support_bytes > max_support:
            errors.append(f"support files total {support_bytes} bytes; profile maximum is {max_support}")

        ai_record: dict[str, Any] | None = None
        if args.ai_disclosure:
            ai_path = resolve_path(args.ai_disclosure, root).resolve()
            if not ai_path.is_file():
                raise ValueError(f"AI disclosure does not exist: {args.ai_disclosure}")
            ai_record = file_record(ai_path, root, "ai_disclosure")
        ai_policy = rules.get("ai_disclosure_policy")
        ai_used = bool(manifest.get("ai_usage"))
        ai_required = ai_policy == "required_always" or (ai_policy == "required_when_used" and ai_used)
        if ai_required and ai_record is None:
            errors.append("AI disclosure is required by the pinned profile and recorded AI usage")
        if ai_policy == "prohibited" and ai_record is not None:
            errors.append("AI disclosure file is prohibited by this profile")

        checkpoints = [
            row for row in manifest.get("human_checkpoints", [])
            if isinstance(row, dict) and row.get("stage") == "s1" and row.get("decision") == "pass"
        ]
        if not checkpoints:
            errors.append("submission QA requires a passing S1 human checkpoint")
        else:
            checkpoint = checkpoints[-1]
            required_manual = set(rules.get("required_manual_checks", []))
            completed_manual = set(checkpoint.get("manual_checks", []))
            missing_manual = sorted(required_manual - completed_manual)
            if missing_manual:
                errors.append("S1 human checkpoint is missing manual check(s): " + ", ".join(missing_manual))
            checkpoint_refs = {
                (ref.get("path"), ref.get("sha256"))
                for ref in checkpoint.get("artifacts", [])
                if isinstance(ref, dict)
            }
            final_records = [paper_record, *support_records, *([ai_record] if ai_record else [])]
            for record in final_records:
                if (record["path"], record["sha256"]) not in checkpoint_refs:
                    errors.append(f"S1 human checkpoint does not cover final artifact: {record['path']}")

        inputs = [
            paper_record,
            *support_records,
            *([ai_record] if ai_record else []),
        ]
        report = {
            "schema_version": "1.0",
            "ok": not errors,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "competition_profile_id": profile.get("profile_id"),
            "competition_profile_sha256": sha256_json(profile),
            "page_count_scope": rules.get("page_count_scope"),
            "inputs": inputs,
            "errors": errors,
            "warnings": warnings,
        }
        write_json(output_path, report, overwrite=args.force)
    except (OSError, ValueError, TypeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": report["ok"], "output": rel_path(output_path, root)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
