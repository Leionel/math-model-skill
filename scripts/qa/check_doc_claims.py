#!/usr/bin/env python3
"""Reconcile design-document claims against the code they describe.

Reads a claims manifest (docs/DOC_CLAIMS.json by default). Each claim names
the document that asserts it and a mechanical check; a failing check means
the document has drifted from the code and must be corrected or re-marked.
Optionally scans design docs for a verified_against marker.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path  # noqa: E402


def _check_file_contains(root: Path, spec: dict[str, Any]) -> tuple[bool, str]:
    path = root / str(spec.get("path", ""))
    pattern = str(spec.get("pattern", ""))
    if not path.is_file():
        return False, f"file does not exist: {rel_path(path, root)}"
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        matched = re.search(pattern, text)
    except re.error as exc:
        return False, f"invalid regex {pattern!r}: {exc}"
    if matched:
        return True, f"pattern found in {rel_path(path, root)}"
    return False, f"pattern {pattern!r} not found in {rel_path(path, root)}"


def _check_json_array_min(root: Path, spec: dict[str, Any]) -> tuple[bool, str]:
    path = root / str(spec.get("path", ""))
    if not path.is_file():
        return False, f"file does not exist: {rel_path(path, root)}"
    try:
        doc = load_structured(path)
    except (OSError, ValueError, TypeError) as exc:
        return False, f"cannot load {rel_path(path, root)}: {exc}"
    node = doc
    for key in spec.get("pointer", []):
        if not isinstance(node, dict) or key not in node:
            return False, f"pointer {'/'.join(spec.get('pointer', []))} missing in {rel_path(path, root)}"
        node = node[key]
    minimum = int(spec.get("min", 1))
    if not isinstance(node, list) or len(node) < minimum:
        return False, f"{rel_path(path, root)} array has fewer than {minimum} entries"
    return True, f"{rel_path(path, root)} has {len(node)} entries"


def _check_cli_help_contains(root: Path, spec: dict[str, Any]) -> tuple[bool, str]:
    argv = [str(root / part) if str(part).startswith("scripts") else str(part) for part in spec.get("argv", [])]
    contains = str(spec.get("contains", ""))
    if not argv or not contains:
        return False, "cli_help_contains requires argv and contains"
    result = subprocess.run(
        [sys.executable, *argv], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False
    )
    output = result.stdout + result.stderr
    if contains in output:
        return True, f"{' '.join(argv)} exposes {contains!r}"
    return False, f"{' '.join(argv)} output does not contain {contains!r}"


_CHECKS = {
    "file_contains": _check_file_contains,
    "json_array_min": _check_json_array_min,
    "cli_help_contains": _check_cli_help_contains,
}


def _check_document_statement(root: Path, claim: dict[str, Any]) -> tuple[bool, str]:
    raw_doc = claim.get("doc")
    pattern = claim.get("doc_pattern")
    if not isinstance(raw_doc, str) or not raw_doc:
        return False, "claim requires a repository-relative doc path"
    if not isinstance(pattern, str) or not pattern:
        return False, "claim requires doc_pattern so the named document is checked"
    doc_path = (root / raw_doc).resolve()
    try:
        doc_path.relative_to(root.resolve())
    except ValueError:
        return False, f"document path escapes repository root: {raw_doc}"
    if not doc_path.is_file():
        return False, f"document does not exist: {raw_doc}"
    try:
        matched = re.search(pattern, doc_path.read_text(encoding="utf-8", errors="replace"))
    except re.error as exc:
        return False, f"invalid doc_pattern {pattern!r}: {exc}"
    if matched is None:
        return False, f"doc_pattern {pattern!r} not found in {raw_doc}"
    return True, f"document assertion found in {raw_doc}"


def check_doc_claims(root: Path, claims_path: Path) -> dict[str, Any]:
    errors: list[str] = []
    try:
        manifest = load_structured(claims_path)
    except (OSError, ValueError, TypeError) as exc:
        return {"ok": False, "errors": [f"claims manifest cannot be loaded: {exc}"], "results": []}
    claims = manifest.get("claims", []) if isinstance(manifest, dict) else []
    if not isinstance(claims, list) or not claims:
        return {"ok": False, "errors": ["claims manifest has no claims"], "results": []}
    results = []
    for claim in claims:
        if not isinstance(claim, dict):
            errors.append("claim entry must be an object")
            continue
        check = claim.get("check")
        check_type = check.get("type") if isinstance(check, dict) else None
        handler = _CHECKS.get(check_type or "")
        if handler is None:
            errors.append(f"claim {claim.get('claim_id', '?')} has unsupported check type: {check_type!r}")
            continue
        doc_ok, doc_detail = _check_document_statement(root, claim)
        check_ok, check_detail = handler(root, check)
        ok = doc_ok and check_ok
        detail = f"{doc_detail}; {check_detail}"
        if not ok:
            errors.append(f"doc claim failed [{claim.get('claim_id', '?')}] ({claim.get('doc', '?')}): {detail}")
        results.append(
            {
                "claim_id": claim.get("claim_id"),
                "doc": claim.get("doc"),
                "statement": claim.get("statement"),
                "ok": ok,
                "document_ok": doc_ok,
                "code_ok": check_ok,
                "detail": detail,
            }
        )
    return {"ok": not errors, "errors": errors, "results": results}


def scan_verified_against(root: Path, doc_dir: Path, max_age_days: int | None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    marker = re.compile(r"^verified_against:\s*(\S+)", flags=re.MULTILINE)
    docs = sorted(doc_dir.glob("*.md"))
    if not docs:
        warnings.append(f"no markdown docs found under {rel_path(doc_dir, root)}")
        return errors, warnings
    for doc in docs:
        text = doc.read_text(encoding="utf-8", errors="replace")
        match = marker.search(text)
        if match is None:
            warnings.append(f"{rel_path(doc, root)} has no verified_against marker")
            continue
        marker_value = match.group(1).strip()
        if "@" not in marker_value or not marker_value.split("@", 1)[1].strip():
            warnings.append(f"{rel_path(doc, root)} verified_against must include a revision after '@'")
            continue
        raw = marker_value.split("@", 1)[0].strip()
        try:
            verified = datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            warnings.append(f"{rel_path(doc, root)} verified_against is not an ISO date: {raw!r}")
            continue
        age = (date.today() - verified).days
        if max_age_days is not None and age > max_age_days:
            warnings.append(
                f"{rel_path(doc, root)} was verified {age} days ago (>{max_age_days}); re-reconcile it against current code"
            )
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--claims", default="docs/DOC_CLAIMS.json")
    parser.add_argument("--doc-dir", help="scan this directory for verified_against markers")
    parser.add_argument("--max-age-days", type=int, default=None)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    report = check_doc_claims(root, (root / args.claims).resolve())
    errors = list(report["errors"])
    warnings: list[str] = []
    if args.doc_dir:
        doc_errors, doc_warnings = scan_verified_against(root, (root / args.doc_dir).resolve(), args.max_age_days)
        errors.extend(doc_errors)
        warnings.extend(doc_warnings)
    ok = not errors and (not args.strict or not warnings)
    report.update({"ok": ok, "errors": errors, "warnings": warnings})
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
