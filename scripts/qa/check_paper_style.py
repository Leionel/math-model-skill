#!/usr/bin/env python3
"""Flag unsupported strong language and repetitive editorial patterns without judging authorship."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402


STRONG_MARKERS = ("证明", "最优", "最佳", "显著", "稳健", "广泛适用", "prove", "optimal", "best", "significant", "robust")
SELF_PRAISE = ("创新性", "先进性", "完整模型链", "严格物理约束", "具有三方面优点", "novel and effective")
TEMPLATE_OPENERS = ("针对", "首先", "其次", "最后", "结果表明", "模型说明", "for question", "firstly", "secondly", "finally")


def sentences(text: str) -> list[str]:
    return [piece.strip() for piece in re.split(r"(?<=[。！？.!?])\s+|[\r\n]+", text) if piece.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--abstract")
    parser.add_argument("--conclusion")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    plan_path = resolve_path(args.paper_plan, root).resolve()
    draft_path = resolve_path(args.draft, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        plan = load_structured(plan_path)
        draft = draft_path.read_text(encoding="utf-8")
        if not isinstance(plan, dict):
            raise ValueError("paper_plan must be an object")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 1

    claims = [row for row in plan.get("claims", []) if isinstance(row, dict)]
    approved_strength = " ".join(str(row.get("text", "")) for row in claims).casefold()
    for marker in STRONG_MARKERS:
        if marker.casefold() in draft.casefold() and marker.casefold() not in approved_strength:
            errors.append(f"draft uses strong marker {marker!r} absent from approved claim text")
    for marker in SELF_PRAISE:
        if marker.casefold() in draft.casefold():
            warnings.append(f"draft contains self-evaluative phrase {marker!r}; replace it with observed validation or boundary evidence")

    sentence_rows = sentences(draft)
    normalized = [re.sub(r"\s+", " ", row.casefold()) for row in sentence_rows]
    duplicates = [row for row, count in Counter(normalized).items() if count >= 2 and len(row) >= 20]
    if duplicates:
        warnings.append(f"draft repeats {len(duplicates)} full sentence pattern(s)")
    opener_counts = Counter(
        opener for sentence in sentence_rows for opener in TEMPLATE_OPENERS if sentence.casefold().startswith(opener.casefold())
    )
    repeated_openers = {key: value for key, value in opener_counts.items() if value >= 3}
    if repeated_openers:
        warnings.append(f"repeated paragraph/sentence openers: {repeated_openers}")

    overlap = None
    if args.abstract and args.conclusion:
        abstract = resolve_path(args.abstract, root).resolve().read_text(encoding="utf-8")
        conclusion = resolve_path(args.conclusion, root).resolve().read_text(encoding="utf-8")
        tokens_a = set(re.findall(r"[\w\u4e00-\u9fff]+", abstract.casefold()))
        tokens_b = set(re.findall(r"[\w\u4e00-\u9fff]+", conclusion.casefold()))
        overlap = len(tokens_a & tokens_b) / max(1, len(tokens_a | tokens_b))
        if overlap >= 0.65:
            warnings.append(f"abstract/conclusion token overlap is high ({overlap:.2f}); ensure conclusion interprets rather than repeats")

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "paper_plan": rel_path(plan_path, root),
        "draft": rel_path(draft_path, root),
        "sentences": len(sentence_rows),
        "abstract_conclusion_overlap": overlap,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
