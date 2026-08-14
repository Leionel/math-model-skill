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
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*")
CJK_CHAR_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
CAUSAL_MARKERS = ("导致", "造成", "使得", "证明", "表明", "because", "therefore", "causes", "demonstrates")
STRONG_CAUSAL_MARKERS = ("导致", "造成", "使得", "causes", "because")
STRENGTH_MARKERS = ("最优", "显著", "稳健", "提升", "optimal", "significant", "robust", "improve")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--writer-package", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument(
        "--require-first-draft-coverage",
        action="store_true",
        help="Require the draft to contain every planned argument anchor and its minimum content span.",
    )
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
    declared_strengths = {
        claim.get("inference_strength")
        for claim in claims
        if isinstance(claim.get("inference_strength"), str)
    }
    if any(marker.casefold() in draft.casefold() for marker in STRONG_CAUSAL_MARKERS) and "causal" not in declared_strengths:
        errors.append("draft uses strong causal language without an approved causal inference_strength")
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
    if args.require_first_draft_coverage:
        coverage = package.get("draft_coverage")
        if not isinstance(coverage, dict):
            errors.append("formal first-draft QA requires writer_package.draft_coverage")
        else:
            anchors = [row for row in coverage.get("anchors", []) if isinstance(row, dict)]
            if coverage.get("status") not in {"planned", "verified"} or not anchors:
                errors.append("writer_package.draft_coverage must contain planned or verified anchors")
            else:
                folded_draft = draft.casefold()
                matches: list[tuple[int, int] | None] = []
                cursor = 0
                for anchor in anchors:
                    patterns = [pattern for pattern in anchor.get("patterns", []) if isinstance(pattern, str) and pattern]
                    candidates = [
                        (folded_draft.find(pattern.casefold(), cursor), len(pattern))
                        for pattern in patterns
                    ]
                    candidates = [candidate for candidate in candidates if candidate[0] >= 0]
                    if not candidates:
                        errors.append(
                            f"draft is missing first-draft anchor {anchor.get('anchor_id')} for unit {anchor.get('unit_id')}"
                        )
                        matches.append(None)
                        continue
                    position, length = min(candidates, key=lambda item: item[0])
                    matches.append((position, length))
                    cursor = position + length
                for index, match in enumerate(matches):
                    if match is None:
                        continue
                    anchor = anchors[index]
                    next_positions = [row[0] for row in matches[index + 1:] if row is not None]
                    end = min(next_positions) if next_positions else len(draft)
                    content = draft[match[0] + match[1]:end]
                    word_count = len(WORD_RE.findall(content)) + len(CJK_CHAR_RE.findall(content))
                    minimum_words = anchor.get("minimum_words", 0)
                    if word_count < minimum_words:
                        errors.append(
                            f"draft span for anchor {anchor.get('anchor_id')} has {word_count} words, "
                            f"below minimum_words={minimum_words}"
                        )
    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "writer_package": rel_path(package_path, root),
        "draft": rel_path(draft_path, root),
        "first_draft_coverage_required": args.require_first_draft_coverage,
        "first_draft_coverage_verified": args.require_first_draft_coverage and ok,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
