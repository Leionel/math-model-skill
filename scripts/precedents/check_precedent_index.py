#!/usr/bin/env python3
"""Check one or both precedent indexes for quarantine and integrity violations.

Fails on: schema violations, paths escaping the quarantine root, hash drift
against the local file, duplicate sources (same sha256 or paper_id), unknown
rights status, or rows pointing outside the two committed competition indexes.
Missing local files are reported (the row stays readable after the PDF is
deleted) but re-verification must be explicit, never assumed.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path, sha256_file  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402

QUARANTINE_ROOT = "references/precedents/local-sources"
HARNESS_ROOT = SCRIPT_DIR.parent.parent


def check_index(index_path: Path, root: Path) -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    warnings: list[str] = []
    value, schema_errors, _ = _validate_document(
        index_path, HARNESS_ROOT / "schemas" / "precedent_index.schema.json"
    )
    errors.extend(f"schema: {message}" for message in schema_errors)
    if not isinstance(value, dict):
        errors.append("index must be an object")
        return errors, warnings, 0
    papers = value.get("papers", [])
    if not isinstance(papers, list):
        errors.append("index.papers must be an array")
        return errors, warnings, 0
    seen_hashes: dict[str, str] = {}
    seen_ids: set[str] = set()
    for index, row in enumerate(papers):
        if not isinstance(row, dict):
            errors.append(f"papers[{index}] must be an object")
            continue
        paper_id = row.get("paper_id")
        label = f"papers[{index}] ({paper_id})"
        local_path = row.get("local_path")
        if not isinstance(local_path, str) or not local_path.startswith(f"{QUARANTINE_ROOT}/"):
            errors.append(f"{label}.local_path must stay under {QUARANTINE_ROOT}/")
            continue
        digest = row.get("sha256")
        if digest in seen_hashes:
            errors.append(f"{label} duplicates sha256 of {seen_hashes[digest]} (same source registered twice)")
        elif isinstance(digest, str):
            seen_hashes[digest] = str(paper_id)
        if paper_id in seen_ids:
            errors.append(f"{label} duplicates paper_id")
        seen_ids.add(str(paper_id))
        if row.get("rights_status") == "unknown":
            errors.append(f"{label} has rights_status=unknown; clarify rights before extracting mechanisms")
        if row.get("rights_status") == "authorized_public_download" and row.get("official_or_authorized") is not True:
            errors.append(
                f"{label} claims authorized_public_download without official_or_authorized=true"
            )
        resolved = resolve_path(local_path, root).resolve()
        if not resolved.is_file():
            warnings.append(f"{label} local file is absent; row kept for provenance but do not claim re-verification")
            continue
        actual = sha256_file(resolved)
        if actual != digest:
            errors.append(f"{label} sha256 drift: expected {digest}, actual {actual}")
    return errors, warnings, len(papers)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", action="append", required=True, help="index json path(s) to check")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    total = 0
    for index_arg in args.index:
        index_path = resolve_path(index_arg, root).resolve()
        if not index_path.is_file():
            errors.append(f"index does not exist: {index_arg}")
            continue
        index_errors, index_warnings, count = check_index(index_path, root)
        errors.extend(f"{rel_path(index_path, root)}: {message}" for message in index_errors)
        warnings.extend(f"{rel_path(index_path, root)}: {message}" for message in index_warnings)
        total += count
    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "indexes": [rel_path(resolve_path(index_arg, root).resolve(), root) for index_arg in args.index],
        "papers_total": total,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
