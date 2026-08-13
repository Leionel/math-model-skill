#!/usr/bin/env python3
"""Inventory numbers and research-strength language not covered by registered claims."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file, write_json  # noqa: E402


NUMBER_RE = re.compile(r"(?<![A-Za-z0-9_])[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?(?![A-Za-z0-9_])")
CLAIM_MARKER_RE = re.compile(r"(?:CLAIM|claim|主张)\s*[:#：]?\s*([A-Za-z][A-Za-z0-9_-]+)")
CITATION_RE = re.compile(r"\\cite[a-zA-Z]*\s*(?:\[[^\]]*\]\s*){0,2}\{[^}]+\}|\[[0-9,;\-\s]+\]")
COMMENT_RE = re.compile(r"(?<!\\)%.*$")
CATEGORIES = {
    "comparative": ("优于", "劣于", "提高", "降低", "改善", "more than", "less than", "outperform", "improve"),
    "causal": ("导致", "造成", "使得", "证明", "because", "therefore", "causes", "demonstrates"),
    "optimality": ("最优", "最佳", "全局最优", "optimal", "best"),
    "significance": ("显著", "显著性", "significant", "statistically"),
    "generalization": ("泛化", "广泛适用", "推广到", "generalize", "broadly applicable"),
    "external_fact": ("据报道", "研究表明", "文献表明", "according to", "studies show"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    plan_path = resolve_path(args.paper_plan, root).resolve()
    frozen_path = resolve_path(args.frozen_results, root).resolve()
    draft_path = resolve_path(args.draft, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        plan = load_structured(plan_path)
        frozen = load_structured(frozen_path)
        draft = draft_path.read_text(encoding="utf-8")
        if not isinstance(plan, dict) or not isinstance(frozen, dict):
            raise ValueError("paper_plan and frozen_results must be objects")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1

    claims = {
        row.get("claim_id"): row
        for row in plan.get("claims", [])
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str)
    }
    allowed_numbers = {
        str(row.get("display_value"))
        for row in frozen.get("results", [])
        if isinstance(row, dict) and row.get("display_value") is not None
    }
    allowed_numbers.update(
        str(row.get("token"))
        for row in plan.get("nonresearch_numeric_literals", [])
        if isinstance(row, dict) and row.get("token") is not None and str(row.get("reason", "")).strip()
    )
    finding_rows: list[dict[str, object]] = []
    counters = {
        "registered_claim_markers": 0,
        "numeric_tokens": 0,
        "comparative_markers": 0,
        "causal_markers": 0,
        "external_fact_markers": 0,
    }

    def add(line_number: int, category: str, line: str, token: str, claim_id: str | None, reason: str) -> None:
        finding_rows.append({
            "finding_id": f"CI-{len(finding_rows) + 1:04d}",
            "line": line_number,
            "category": category,
            "text": line.strip() or "<empty>",
            "token": token,
            "claim_id": claim_id,
            "status": "review_required",
            "reason": reason,
        })

    current_claim: str | None = None
    for line_number, line in enumerate(draft.splitlines(), start=1):
        line_for_numbers = CITATION_RE.sub("", COMMENT_RE.sub("", line))
        marker_ids = CLAIM_MARKER_RE.findall(line)
        valid_markers = [claim_id for claim_id in marker_ids if claim_id in claims]
        counters["registered_claim_markers"] += len(valid_markers)
        if len(valid_markers) == 1:
            current_claim = valid_markers[0]
        active_claim = current_claim
        if marker_ids and not valid_markers:
            add(line_number, "missing_claim_marker", line, marker_ids[0], None, "claim marker is not registered in paper_plan")
        for match in NUMBER_RE.finditer(line_for_numbers):
            counters["numeric_tokens"] += 1
            token = match.group(0)
            if token not in allowed_numbers:
                add(line_number, "unregistered_number", line, token, active_claim, "numeric token is absent from frozen result display values")
        lowered = line.casefold()
        for category, markers in CATEGORIES.items():
            for marker in markers:
                if marker.casefold() not in lowered:
                    continue
                if category == "comparative":
                    counters["comparative_markers"] += 1
                elif category == "causal":
                    counters["causal_markers"] += 1
                elif category == "external_fact":
                    counters["external_fact_markers"] += 1
                claim = claims.get(active_claim) if active_claim else None
                supported = False
                if isinstance(claim, dict):
                    if category in {"comparative", "optimality", "significance"}:
                        supported = isinstance(claim.get("comparison"), dict)
                    elif category == "causal":
                        supported = claim.get("claim_type") in {"inference", "recommendation"}
                    elif category == "generalization":
                        supported = claim.get("support_level") == "qualified" and bool(claim.get("boundary"))
                    elif category == "external_fact":
                        supported = bool(claim.get("evidence_ids"))
                if not supported:
                    add(line_number, category, line, marker, active_claim, "research-strength language has no locally marked supporting claim contract")

    unresolved = len(finding_rows)
    report = {
        "schema_version": "1.0",
        "run_id": plan.get("run_id", "unknown"),
        "draft": {"path": rel_path(draft_path, root), "sha256": sha256_file(draft_path)},
        "paper_plan": {"path": rel_path(plan_path, root), "sha256": sha256_file(plan_path)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "findings": finding_rows,
        "summary": {**counters, "unresolved_findings": unresolved},
        "ok": unresolved == 0,
    }
    try:
        write_json(output_path, report, overwrite=args.force)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": report["ok"], "output": rel_path(output_path, root), "unresolved": unresolved}, ensure_ascii=False))
    return 0 if report["ok"] or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
