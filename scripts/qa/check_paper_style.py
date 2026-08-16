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


def judge_scan(
    plan: dict,
    draft: str,
    *,
    abstract: str | None = None,
    model_contract: dict | None = None,
    frozen_results: dict | None = None,
) -> dict:
    """Return issues a human reviewer should inspect; deliberately no score."""

    issues: list[dict[str, str]] = []
    model_rows = [row for row in (model_contract or {}).get("models", []) if isinstance(row, dict)]
    result_by_id = {
        row.get("result_id"): row
        for row in (frozen_results or {}).get("results", [])
        if isinstance(row, dict) and isinstance(row.get("result_id"), str)
    }
    if not abstract:
        issues.append({"check": "abstract_30_second_scan", "severity": "missing", "message": "abstract text was not supplied"})
    else:
        abstract_rows = [row for row in plan.get("abstract_results", []) if isinstance(row, dict)]
        for row in abstract_rows:
            result_id = row.get("result_id")
            result = result_by_id.get(result_id)
            if result and result.get("display_value") and str(result["display_value"]) not in abstract:
                issues.append({"check": "decisive_number_visibility", "severity": "issue", "message": f"abstract does not visibly report {result_id}"})
            if isinstance(row.get("fact_check"), dict) and row["fact_check"].get("status") != "passed":
                issues.append({"check": "abstract_fact_backcheck", "severity": "issue", "message": f"abstract result {result_id} has not passed fact backcheck"})
        question_ids = sorted({
            claim.get("question_id")
            for claim in plan.get("claims", [])
            if isinstance(claim, dict) and isinstance(claim.get("question_id"), str)
        })
        for question_id in question_ids:
            q_rows = [row for row in abstract_rows if row.get("question_id") == question_id]
            q_result_ids = {row.get("result_id") for row in q_rows}
            inferred = {
                result_id
                for result_id, result in result_by_id.items()
                if result.get("question_id") == question_id
            }
            if not (q_result_ids or (inferred and any(str(result_by_id[r].get("display_value", "")) in abstract for r in inferred))):
                issues.append({"check": "question_answer_visibility", "severity": "issue", "message": f"abstract has no readily visible answer for {question_id}"})
            q_model_names = [
                str(model.get("name"))
                for model in model_rows
                if model.get("question_id") == question_id and model.get("name")
            ]
            if q_model_names and not any(name.casefold() in abstract.casefold() for name in q_model_names):
                issues.append({"check": "model_identity_visibility", "severity": "issue", "message": f"abstract does not name the selected model for {question_id}"})
            if not re.search(r"验证|检验|误差|灵敏度|稳定|回代|validation|error|sensitivity|stability", abstract, flags=re.IGNORECASE):
                issues.append({"check": "validation_discoverability", "severity": "issue", "message": "abstract does not make a validation result discoverable"})

    for figure in plan.get("figures", []):
        if not isinstance(figure, dict):
            continue
        figure_id = str(figure.get("figure_id", ""))
        if not figure_id:
            continue
        position = draft.find(figure_id)
        if position < 0:
            continue
        following = draft[position + len(figure_id): position + len(figure_id) + 1200]
        claim_text = " ".join(
            str(claim.get("text", ""))
            for claim in plan.get("claims", [])
            if isinstance(claim, dict) and claim.get("claim_id") in figure.get("claim_ids", [])
        )
        caption = str(figure.get("caption_claim", ""))
        if not following.strip() or not any(token and token.casefold() in following.casefold() for token in (claim_text, caption, str(figure.get("message", "")))):
            issues.append({"check": "figure_placement", "severity": "issue", "message": f"figure {figure_id} is not followed by an identifiable primary claim/explanation"})

    return {
        "status": "issues_found" if issues else "no_structural_issues",
        "issues": issues,
        "manual_checks_required": [
            "30-second abstract scan: method, decisive numbers, question answers and validation",
            "3-minute rendered-page scan: figure placement, readability, cropping and visual hierarchy",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--abstract")
    parser.add_argument("--conclusion")
    parser.add_argument("--model-contract")
    parser.add_argument("--frozen-results")
    parser.add_argument("--judge-scan", action="store_true", help="Run an issue-only reviewer scan; it never assigns a score.")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    plan_path = resolve_path(args.paper_plan, root).resolve()
    draft_path = resolve_path(args.draft, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    judge_report = None
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

    if args.judge_scan:
        model_contract = None
        frozen_results = None
        try:
            if args.model_contract:
                loaded = load_structured(resolve_path(args.model_contract, root).resolve())
                model_contract = loaded if isinstance(loaded, dict) else None
            if args.frozen_results:
                loaded = load_structured(resolve_path(args.frozen_results, root).resolve())
                frozen_results = loaded if isinstance(loaded, dict) else None
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            warnings.append(f"judge_scan input could not be loaded: {exc}")
        abstract_text = None
        if args.abstract:
            try:
                abstract_text = resolve_path(args.abstract, root).resolve().read_text(encoding="utf-8")
            except OSError as exc:
                warnings.append(f"judge_scan abstract could not be read: {exc}")
        judge_report = judge_scan(
            plan,
            draft,
            abstract=abstract_text,
            model_contract=model_contract,
            frozen_results=frozen_results,
        )
        warnings.extend(item["message"] for item in judge_report["issues"])

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "paper_plan": rel_path(plan_path, root),
        "draft": rel_path(draft_path, root),
        "sentences": len(sentence_rows),
        "abstract_conclusion_overlap": overlap,
        "errors": errors,
        "warnings": warnings,
        "judge_scan": judge_report,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
