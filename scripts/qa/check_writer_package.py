#!/usr/bin/env python3
"""Reject draft text that introduces research facts absent from a writer package."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402


NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])")
CAUSAL_MARKERS = ("导致", "造成", "使得", "证明", "表明", "because", "therefore", "causes", "demonstrates")
STRENGTH_MARKERS = ("最优", "显著", "稳健", "提升", "optimal", "significant", "robust", "improve")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writer-package", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    package_path = resolve_path(args.writer_package, root).resolve()
    draft_path = resolve_path(args.draft, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        package = load_structured(package_path)
        draft = draft_path.read_text(encoding="utf-8")
        if not isinstance(package, dict) or package.get("schema_version") != "1.0":
            raise ValueError("writer package must have schema_version=1.0")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 1
    allowed_numbers = {
        str(result.get("display_value"))
        for claim in package.get("claims", [])
        if isinstance(claim, dict)
        for result in claim.get("results", [])
        if isinstance(result, dict) and result.get("display_value") is not None
    }
    unregistered = sorted({match.group(0) for match in NUMBER_RE.finditer(draft) if match.group(0) not in allowed_numbers})
    if unregistered:
        errors.append(f"draft contains research numeric token(s) absent from writer package: {', '.join(unregistered)}")
    claims = [claim for claim in package.get("claims", []) if isinstance(claim, dict)]
    has_non_observation = any(claim.get("claim_type") != "observation" for claim in claims)
    if not has_non_observation and any(marker.casefold() in draft.casefold() for marker in CAUSAL_MARKERS):
        errors.append("draft uses causal/explanatory language without an approved inference or recommendation claim")
    approved_strength = {
        marker
        for claim in claims
        if isinstance(claim.get("comparison"), dict)
        for marker in STRENGTH_MARKERS
        if marker.casefold() in str(claim.get("approved_text", "")).casefold()
    }
    for marker in STRENGTH_MARKERS:
        if marker.casefold() in draft.casefold() and marker not in approved_strength:
            warnings.append(f"draft uses strength marker {marker!r} without an approved comparative claim")
    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "writer_package": rel_path(package_path, root),
        "draft": rel_path(draft_path, root),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
