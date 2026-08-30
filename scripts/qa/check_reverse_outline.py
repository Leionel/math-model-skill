#!/usr/bin/env python3
"""Reverse-outline and repetition sweep for a drafted paper section tree.

Deterministic post-draft writing checks that complement numeric provenance QA:
- claim-location: every planned claim is located in the draft through at least
  one anchored argument unit;
- handoff order: every prerequisite anchor appears before its dependent anchor
  (cross-question handoffs included);
- repetition sweep: identical long n-grams repeated across anchor spans are
  reported so a human can compress them;
- reverse outline: the topic sentence and word count of every anchor span,
  emitted as a review artifact.

It finds missing argument wiring; it does not judge style or mathematics.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402
from qa.check_writer_package import CJK_CHAR_RE, WORD_RE, _load_tex_tree  # noqa: E402

# Repetition sweep windows: CJK runs of 12+ chars and English runs of 8+ words
# repeated across distinct anchor spans are flagged for human compression.
_CJK_NGRAM = 12
_WORD_NGRAM = 8
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？.!?\n])\s+")
_CJK_RUN_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]+")


def _norm(text: str) -> str:
    return re.sub(r"\s+", "", text)


def _first_sentence(text: str, limit: int = 120) -> str:
    stripped = text.strip()
    if not stripped:
        return ""
    parts = [part for part in _SENTENCE_SPLIT_RE.split(stripped) if part.strip()]
    sentence = parts[0].strip() if parts else stripped
    return sentence[:limit]


def _count_words(text: str) -> int:
    return len(WORD_RE.findall(text)) + len(CJK_CHAR_RE.findall(text))


def _anchor_spans(draft: str, anchors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Locate each anchor span in document order, mirroring first-draft coverage."""

    folded = draft.casefold()
    cursor = 0
    spans: list[dict[str, Any]] = []
    positions: list[tuple[int, int] | None] = []
    for anchor in anchors:
        patterns = [pattern for pattern in anchor.get("patterns", []) if isinstance(pattern, str) and pattern]
        candidate = next(
            (
                (folded.find(pattern.casefold(), cursor), len(pattern))
                for pattern in patterns
                if folded.find(pattern.casefold(), cursor) >= 0
            ),
            None,
        )
        positions.append(candidate)
        if candidate is not None:
            cursor = candidate[0] + candidate[1]
    for index, anchor in enumerate(anchors):
        match = positions[index]
        if match is None:
            spans.append({**anchor, "position": None, "content": ""})
            continue
        next_positions = [row[0] for row in positions[index + 1:] if row is not None]
        end = min(next_positions) if next_positions else len(draft)
        spans.append({**anchor, "position": match[0], "content": draft[match[0] + match[1]:end]})
    return spans


def _repetition_findings(spans: list[dict[str, Any]]) -> list[str]:
    """Report identical long n-grams that appear in two or more anchor spans."""

    seen: dict[str, str] = {}  # n-gram -> first anchor_id
    findings: dict[str, list[str]] = {}
    for span in spans:
        if span.get("position") is None or not span.get("content"):
            continue
        anchor_id = str(span.get("anchor_id"))
        normalized = _norm(span["content"])
        word_tokens = WORD_RE.findall(span["content"])
        grams: set[str] = set()
        for run in _CJK_RUN_RE.findall(normalized):
            for start in range(0, max(1, len(run) - _CJK_NGRAM + 1)):
                grams.add(run[start:start + _CJK_NGRAM])
        for start in range(0, max(1, len(word_tokens) - _WORD_NGRAM + 1)):
            grams.add(" ".join(word_tokens[start:start + _WORD_NGRAM]).casefold())
        for gram in grams:
            first = seen.get(gram)
            if first is None:
                seen[gram] = anchor_id
            elif first != anchor_id:
                findings.setdefault(first, []).append(anchor_id)
    return [
        f"anchor {first} and anchor {', '.join(sorted(set(others)))} repeat the same long passage; compress instead of restating"
        for first, others in sorted(findings.items())
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--writer-package")
    parser.add_argument("--draft", required=True)
    parser.add_argument("--outline-report", help="optional markdown reverse-outline report path")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        plan = load_structured(resolve_path(args.paper_plan, root).resolve())
        draft = _load_tex_tree(resolve_path(args.draft, root).resolve())
        package = None
        if args.writer_package:
            package = load_structured(resolve_path(args.writer_package, root).resolve())
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 1
    if not isinstance(plan, dict):
        print(json.dumps({"ok": False, "errors": ["paper plan must be an object"], "warnings": []}, ensure_ascii=False, indent=2))
        return 1

    coverage = plan.get("draft_coverage") if isinstance(plan.get("draft_coverage"), dict) else None
    if package is not None and isinstance(package.get("draft_coverage"), dict):
        coverage = package["draft_coverage"]
    if coverage is None:
        print(json.dumps({
            "ok": False,
            "errors": ["reverse outline requires paper_plan.draft_coverage anchors"],
            "warnings": [],
        }, ensure_ascii=False, indent=2))
        return 1
    anchors = [row for row in coverage.get("anchors", []) if isinstance(row, dict)]
    if not anchors:
        print(json.dumps({
            "ok": False,
            "errors": ["draft_coverage.anchors is empty; nothing to reverse-outline"],
            "warnings": [],
        }, ensure_ascii=False, indent=2))
        return 1

    spans = _anchor_spans(draft, anchors)
    for span in spans:
        if span.get("position") is None:
            errors.append(f"anchor {span.get('anchor_id')} (unit {span.get('unit_id')}) cannot be located in the draft")

    units = {
        row.get("unit_id"): row
        for row in plan.get("argument_units", [])
        if isinstance(row, dict)
    }
    span_by_unit = {
        span.get("unit_id"): span
        for span in spans
        if span.get("unit_id") is not None
    }

    # Handoff order: a prerequisite anchor must appear before its dependent.
    for unit in units.values():
        dependent = span_by_unit.get(unit.get("unit_id"))
        if dependent is None or dependent.get("position") is None:
            continue
        for prerequisite in unit.get("prerequisite_unit_ids", []):
            source = span_by_unit.get(prerequisite)
            if source is None or source.get("position") is None:
                continue
            if source["position"] >= dependent["position"]:
                source_section = units.get(prerequisite, {}).get("section_id")
                dependent_section = unit.get("section_id")
                scope = "cross-section handoff" if source_section != dependent_section else "in-section dependency"
                errors.append(
                    f"{scope} reversed: unit {prerequisite} appears at or after dependent unit "
                    f"{unit.get('unit_id')} in the draft"
                )

    # Claim-location: every planned claim must be anchored somewhere.
    for claim in plan.get("claims", []):
        if not isinstance(claim, dict):
            continue
        claim_id = claim.get("claim_id")
        anchored = any(
            isinstance(unit, dict) and claim_id in unit.get("claim_ids", [])
            and span_by_unit.get(unit.get("unit_id"), {}).get("position") is not None
            for unit in units.values()
        )
        if not anchored:
            errors.append(f"claim {claim_id} has no located argument anchor in the draft")

    warnings.extend(_repetition_findings(spans))

    outline = [
        {
            "anchor_id": span.get("anchor_id"),
            "unit_id": span.get("unit_id"),
            "topic_sentence": _first_sentence(span.get("content", "")),
            "words": _count_words(span.get("content", "")),
        }
        for span in spans
    ]
    ok = not errors and (not args.strict or not warnings)
    if args.outline_report:
        report_path = resolve_path(args.outline_report, root).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Reverse Outline", ""]
        for row in outline:
            lines.append(f"- `{row['anchor_id']}` ({row['words']} words): {row['topic_sentence']}")
        lines.append("")
        if warnings:
            lines.append("## Repetition findings")
            lines.append("")
            lines.extend(f"- {warning}" for warning in warnings)
        report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({
        "ok": ok,
        "paper_plan": rel_path(resolve_path(args.paper_plan, root).resolve(), root),
        "draft": rel_path(resolve_path(args.draft, root).resolve(), root),
        "anchors_located": sum(1 for span in spans if span.get("position") is not None),
        "anchors_total": len(spans),
        "claims_located": sum(
            1
            for claim in plan.get("claims", [])
            if isinstance(claim, dict)
            and any(
                isinstance(unit, dict) and claim.get("claim_id") in unit.get("claim_ids", [])
                and span_by_unit.get(unit.get("unit_id"), {}).get("position") is not None
                for unit in units.values()
            )
        ),
        "claims_total": len([row for row in plan.get("claims", []) if isinstance(row, dict)]),
        "reverse_outline": outline,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
