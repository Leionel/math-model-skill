#!/usr/bin/env python3
"""Compile the paper plan (plus writer package when available) into writing views.

Two regenerable views are produced, both under `.harness/views/`:
- `WRITING_SPINE.md` — the whole-paper argument chain: central thesis, ordered
  sections with their argument units, cross-question handoffs, a deterministic
  drafting order, and the abstract evidence budget.
- `sections/<section>_brief.md` — a section-scoped Writer Brief: only the
  ordered units, claims, frozen values, established facts, handoffs, and
  must-not-claim boundary the writer needs for that one section.

The paper plan remains the only planning truth source; the writer package
remains the only fact source for claim numbers.  These views never overwrite
author Markdown under `paper/`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, write_json  # noqa: E402

# Deterministic drafting phases: decisive evidence first, mechanism second,
# synthesis and framing last.  The abstract is compiled after the body from
# the evidence registry and is never part of this order.
_ROLE_PHASE = {
    "result_observation": 1,
    "comparison": 1,
    "validation": 1,
    "mechanism_derivation": 2,
    "model_choice": 2,
    "parameter_evidence": 2,
    "problem_tension": 3,
    "interpretation": 3,
    "boundary": 3,
    "recommendation": 3,
}
_PLAN_ROLE_PHASE = 2  # plan-level units without a role default to mechanism phase

# Evidence-allocation discipline: every argument unit declares where its result
# evidence lives (body / caption / appendix) instead of piling into prose.
_ALLOCATION_BY_ROLE = {
    "result_observation": {"allocation_class": "core_finding", "default_destination": "body"},
    "comparison": {"allocation_class": "comparison", "default_destination": "body"},
    "validation": {"allocation_class": "validation", "default_destination": "body"},
    "mechanism_derivation": {"allocation_class": "mechanism_derivation", "default_destination": "body"},
    "model_choice": {"allocation_class": "method_choice", "default_destination": "body"},
    "parameter_evidence": {"allocation_class": "parameter_evidence", "default_destination": "appendix"},
    "problem_tension": {"allocation_class": "framing", "default_destination": "body"},
    "interpretation": {"allocation_class": "synthesis", "default_destination": "body"},
    "boundary": {"allocation_class": "boundary", "default_destination": "body"},
    "recommendation": {"allocation_class": "recommendation", "default_destination": "body"},
}
_DEFAULT_ALLOCATION = {"allocation_class": "mechanism_derivation", "default_destination": "body"}
_ALLOCATION_RULE = (
    "Before adding evidence anywhere, check whether one piece can be removed elsewhere; "
    "supporting detail belongs in figure captions or the appendix, body prose keeps only "
    "the shortest sufficient evidence chain."
)


def _evidence_allocation(units: list[dict[str, Any]]) -> dict[str, Any]:
    rows = []
    for unit in units:
        allocation = _ALLOCATION_BY_ROLE.get(str(unit.get("rhetorical_role")), _DEFAULT_ALLOCATION)
        rows.append({
            "unit_id": unit.get("unit_id"),
            "rhetorical_role": unit.get("rhetorical_role"),
            "allocation_class": allocation["allocation_class"],
            "destination": allocation["default_destination"],
            "word_budget": unit.get("target_words"),
            "result_ids": unit.get("result_ids", []),
        })
    return {"rows": rows, "rule": _ALLOCATION_RULE}


def _ordered_units_for_section(plan: dict[str, Any], section_id: str) -> list[dict[str, Any]]:
    return [
        row for row in plan.get("argument_units", [])
        if isinstance(row, dict) and row.get("section_id") == section_id
    ]


def _section_phase(units: list[dict[str, Any]]) -> int:
    phases = [
        _ROLE_PHASE.get(str(unit.get("rhetorical_role")), _PLAN_ROLE_PHASE)
        for unit in units
    ]
    return min(phases) if phases else _PLAN_ROLE_PHASE


def build_writing_spine(plan: dict[str, Any], package: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValueError("paper plan must be an object")
    sections = [
        row for row in plan.get("sections", [])
        if isinstance(row, dict) and isinstance(row.get("section_id"), str)
    ]
    if not sections:
        raise ValueError("paper plan has no sections to project")
    section_rows = []
    for section in sections:
        units = _ordered_units_for_section(plan, section["section_id"])
        section_rows.append({
            "section_id": section["section_id"],
            "purpose": section.get("purpose"),
            "claim_ids": section.get("claim_ids", []),
            "phase": _section_phase(units),
            "units": [
                {
                    "unit_id": unit.get("unit_id"),
                    "rhetorical_role": unit.get("rhetorical_role"),
                    "claim_ids": unit.get("claim_ids", []),
                    "evidence_ids": unit.get("evidence_ids", []),
                    "prerequisite_unit_ids": unit.get("prerequisite_unit_ids", []),
                    "expected_reader_judgment": unit.get("expected_reader_judgment"),
                }
                for unit in units
            ],
        })
    unit_section = {
        unit.get("unit_id"): section["section_id"]
        for section in section_rows
        for unit in section["units"]
    }
    handoffs = []
    for section in section_rows:
        for unit in section["units"]:
            for prerequisite in unit["prerequisite_unit_ids"]:
                source_section = unit_section.get(prerequisite)
                if source_section is not None and source_section != section["section_id"]:
                    handoffs.append({
                        "from_unit": prerequisite,
                        "from_section": source_section,
                        "to_unit": unit["unit_id"],
                        "to_section": section["section_id"],
                    })
    depth = plan.get("depth_allocation") or plan.get("depth_budget") or []
    abstract_rows = [
        row for row in plan.get("abstract_results", [])
        if isinstance(row, dict)
    ]
    return {
        "schema_version": "1.0",
        "run_id": plan.get("run_id"),
        "projection": "writing_spine",
        "source": "paper_plan" + ("+writer_package" if package else ""),
        "central_thesis": plan.get("central_thesis"),
        "sections": section_rows,
        "cross_question_handoffs": handoffs,
        "depth": depth,
        "recommended_writing_order": [
            row["section_id"] for row in sorted(section_rows, key=lambda row: (row["phase"],))
        ],
        "abstract_evidence_budget": {
            "result_ids": [row.get("result_id") for row in abstract_rows],
            "word_budgets": [row.get("word_budget") for row in abstract_rows],
            "note": "The abstract is compiled last from the evidence registry; never draft it from memory.",
        },
        "boundary": "Derived view only; it creates no gate, claim, or new contract.",
    }


def render_spine_markdown(spine: dict[str, Any]) -> str:
    thesis = spine.get("central_thesis") or {}
    lines = [
        "# Writing Spine",
        "",
        "> Derived projection of `paper_plan.json` (plus the writer package when present).",
        "> Do not edit; regenerate with `harness paper write <section>` or",
        "> `python scripts/views/writing_spine.py`.  Not a truth source.",
        "",
        f"- run_id: {spine.get('run_id')}",
        f"- central thesis: {thesis.get('text')}",
        f"- thesis boundary: {thesis.get('boundary')}",
        "",
        "## Section order and argument units",
        "",
    ]
    for section in spine["sections"]:
        lines.append(f"### {section['section_id']} (phase {section['phase']})")
        lines.append("")
        lines.append(f"- purpose: {section.get('purpose')}")
        if section.get("claim_ids"):
            lines.append(f"- claims: {', '.join(section['claim_ids'])}")
        lines.append("- units:")
        for unit in section["units"]:
            lines.append(
                f"  - `{unit['unit_id']}` [{unit.get('rhetorical_role')}] claims={','.join(unit.get('claim_ids', []))}"
                f" prereq={','.join(unit.get('prerequisite_unit_ids', [])) or 'none'}"
            )
        lines.append("")
    lines.extend(["## Cross-question handoffs", ""])
    for handoff in spine.get("cross_question_handoffs", []):
        lines.append(
            f"- `{handoff['from_unit']}` ({handoff['from_section']}) -> `{handoff['to_unit']}` ({handoff['to_section']})"
        )
    if not spine.get("cross_question_handoffs"):
        lines.append("- (none)")
    lines.extend([
        "",
        "## Recommended drafting order (decisive evidence -> mechanism -> synthesis)",
        "",
    ])
    lines.append(" -> ".join(spine["recommended_writing_order"]))
    lines.extend([
        "",
        "## Abstract evidence budget",
        "",
        f"- results: {', '.join(row for row in spine['abstract_evidence_budget']['result_ids'] if row)}",
        f"- word budgets: {spine['abstract_evidence_budget']['word_budgets']}",
        f"- {spine['abstract_evidence_budget']['note']}",
        "",
    ])
    return "\n".join(lines) + "\n"


def _claim_row(package: dict[str, Any] | None, claim_id: str) -> dict[str, Any] | None:
    if not package:
        return None
    for row in package.get("claims", []):
        if isinstance(row, dict) and row.get("claim_id") == claim_id:
            return row
    return None


def _display_ids_for_section(plan: dict[str, Any], section_id: str, claims: set[str]) -> tuple[list[str], list[str]]:
    figures = [
        row.get("figure_id") for row in plan.get("figures", [])
        if isinstance(row, dict) and row.get("paper_location") == section_id
        or isinstance(row, dict) and claims.intersection(row.get("claim_ids", []))
    ]
    tables = [
        row.get("table_id") for row in plan.get("tables", [])
        if isinstance(row, dict) and row.get("paper_location") == section_id
        or isinstance(row, dict) and claims.intersection(row.get("claim_ids", []))
    ]
    return [row for row in figures if row], [row for row in tables if row]


def build_section_brief(plan: dict[str, Any], package: dict[str, Any] | None, section_id: str) -> dict[str, Any]:
    sections = {
        row.get("section_id"): row
        for row in plan.get("sections", [])
        if isinstance(row, dict)
    }
    if section_id not in sections:
        raise ValueError(f"unknown section_id {section_id!r}; plan sections: {sorted(sections)}")
    units = _ordered_units_for_section(plan, section_id)
    section = sections[section_id]
    claim_ids = {
        claim_id
        for unit in units
        for claim_id in unit.get("claim_ids", [])
        if isinstance(claim_id, str)
    } | {row for row in section.get("claim_ids", []) if isinstance(row, str)}
    all_units = {
        row.get("unit_id"): row
        for row in plan.get("argument_units", [])
        if isinstance(row, dict)
    }
    established = []
    for unit in units:
        for prerequisite in unit.get("prerequisite_unit_ids", []):
            source = all_units.get(prerequisite)
            if source is not None and source.get("section_id") != section_id:
                established.append({
                    "unit_id": prerequisite,
                    "section_id": source.get("section_id"),
                    "reader_judgment": source.get("expected_reader_judgment"),
                })
    dependents = []
    for other in all_units.values():
        if other.get("section_id") == section_id:
            continue
        for prerequisite in other.get("prerequisite_unit_ids", []):
            if prerequisite in {unit.get("unit_id") for unit in units}:
                dependents.append({
                    "unit_id": other.get("unit_id"),
                    "section_id": other.get("section_id"),
                    "reader_judgment": other.get("expected_reader_judgment"),
                })
    claims_detail = []
    plan_claims = {
        row.get("claim_id"): row
        for row in plan.get("claims", [])
        if isinstance(row, dict)
    }
    for claim_id in sorted(claim_ids):
        packaged = _claim_row(package, claim_id)
        planned = plan_claims.get(claim_id, {})
        claims_detail.append({
            "claim_id": claim_id,
            "approved_text": (packaged or {}).get("approved_text") or planned.get("text"),
            "boundary": (packaged or {}).get("boundary") or planned.get("boundary"),
            "support_level": (packaged or {}).get("support_level") or planned.get("support_level"),
            "inference_strength": (packaged or {}).get("inference_strength") or planned.get("inference_strength"),
            "comparison": planned.get("comparison"),
            "results": (packaged or {}).get("results", []),
        })
    figures, tables = _display_ids_for_section(plan, section_id, claim_ids)
    return {
        "schema_version": "1.0",
        "run_id": plan.get("run_id"),
        "projection": "section_writer_brief",
        "section_id": section_id,
        "purpose": section.get("purpose"),
        "ordered_units": [
            {
                "unit_id": unit.get("unit_id"),
                "rhetorical_role": unit.get("rhetorical_role"),
                "claim_ids": unit.get("claim_ids", []),
                "evidence_ids": unit.get("evidence_ids", []),
                "prerequisite_unit_ids": unit.get("prerequisite_unit_ids", []),
                "expected_reader_judgment": unit.get("expected_reader_judgment"),
                "boundary": unit.get("boundary"),
                "math_locators": unit.get("math_locators", []),
                "target_words": unit.get("target_words"),
                "result_ids": unit.get("result_ids", []),
            }
            for unit in units
        ],
        "claims": claims_detail,
        "established_facts": established,
        "next_handoffs": dependents,
        "figures": figures,
        "tables": tables,
        "evidence_allocation": _evidence_allocation(units),
        "terminology": plan.get("terminology", []),
        "canonical_recommendation": plan.get("canonical_recommendation"),
        "must_not_claim": {
            "claim_boundaries": [row.get("boundary") for row in claims_detail if row.get("boundary")],
            "forbidden_variants": [
                variant
                for term in plan.get("terminology", [])
                if isinstance(term, dict)
                for variant in term.get("forbidden_variants", [])
            ],
            "rule": "No new research numbers, comparators, causal mechanisms, scenarios, or stronger conclusions outside this brief.",
        },
        "boundary": "Derived view only; it creates no gate, claim, or new contract.",
    }


def render_brief_markdown(brief: dict[str, Any]) -> str:
    lines = [
        f"# Writer Brief — {brief['section_id']}",
        "",
        "> Derived projection of `paper_plan.json` (+ writer package).  Do not edit;",
        "> regenerate with `harness paper write <section>`.  Not a truth source.",
        "> Unit/claim IDs and locators are authoring metadata. Never print `ANCHOR-*`,",
        "> `LOC-*`, or similar internal tokens in reader-facing prose.",
        "",
        f"- run_id: {brief.get('run_id')}",
        f"- purpose: {brief.get('purpose')}",
        "",
        "## Ordered argument units",
        "",
    ]
    for unit in brief["ordered_units"]:
        lines.append(f"### {unit['unit_id']} [{unit.get('rhetorical_role')}]")
        lines.append("")
        lines.append(f"- claims: {', '.join(unit.get('claim_ids', []))}")
        lines.append(f"- evidence: {', '.join(unit.get('evidence_ids', []))}")
        if unit.get("prerequisite_unit_ids"):
            lines.append(f"- prerequisites: {', '.join(unit['prerequisite_unit_ids'])}")
        lines.append(f"- expected reader judgment: {unit.get('expected_reader_judgment')}")
        lines.append(f"- boundary: {unit.get('boundary')}")
        if unit.get("math_locators"):
            lines.append(
                "- invisible LaTeX locators to insert (never prose): "
                + ", ".join(unit["math_locators"])
            )
        if unit.get("target_words") is not None:
            lines.append(f"- target words: {unit['target_words']}")
        if unit.get("result_ids"):
            lines.append(f"- frozen results: {', '.join(unit['result_ids'])}")
        lines.append("")
    lines.extend(["## Claims and frozen values", ""])
    for claim in brief["claims"]:
        lines.append(f"### {claim['claim_id']}")
        lines.append("")
        lines.append(f"- approved text: {claim.get('approved_text')}")
        lines.append(f"- boundary: {claim.get('boundary')}")
        lines.append(f"- support: {claim.get('support_level')} / strength: {claim.get('inference_strength')}")
        if claim.get("comparison"):
            comparison = claim["comparison"]
            lines.append(
                f"- comparison: {comparison.get('comparator')} on {comparison.get('metric')} "
                f"({comparison.get('direction')}, scenario={comparison.get('scenario')})"
            )
        for result in claim.get("results", []):
            lines.append(f"- result `{result.get('result_id')}`: {result.get('display_value')} {result.get('unit') or ''}".rstrip())
        lines.append("")
    lines.extend(["## Established facts from earlier sections", ""])
    for fact in brief["established_facts"]:
        lines.append(f"- `{fact['unit_id']}` ({fact['section_id']}): {fact['reader_judgment']}")
    if not brief["established_facts"]:
        lines.append("- (none)")
    lines.extend(["", "## Handoff to later sections", ""])
    for handoff in brief["next_handoffs"]:
        lines.append(f"- `{handoff['unit_id']}` ({handoff['section_id']}) will rely on this section: {handoff['reader_judgment']}")
    if not brief["next_handoffs"]:
        lines.append("- (none)")
    lines.extend(["", "## Displays in this section", ""])
    lines.append(f"- figures: {', '.join(brief['figures']) or 'none'}")
    lines.append(f"- tables: {', '.join(brief['tables']) or 'none'}")
    lines.extend([
        "",
        "## Evidence allocation (class -> destination)",
        "",
        "| unit | class | destination | word budget | frozen results |",
        "|---|---|---|---|---|",
    ])
    for row in brief["evidence_allocation"]["rows"]:
        lines.append(
            f"| `{row['unit_id']}` | {row['allocation_class']} | {row['destination']} "
            f"| {row.get('word_budget') if row.get('word_budget') is not None else '—'} "
            f"| {', '.join(row.get('result_ids', [])) or '—'} |"
        )
    lines.extend(["", f"- rule: {brief['evidence_allocation']['rule']}"])
    if brief.get("canonical_recommendation"):
        lines.extend([
            "",
            "## Canonical recommendation (only wording allowed)",
            "",
            f"- {brief['canonical_recommendation'].get('text')}",
        ])
    lines.extend([
        "",
        "## Must not claim",
        "",
    ])
    for boundary in brief["must_not_claim"]["claim_boundaries"]:
        lines.append(f"- {boundary}")
    for variant in brief["must_not_claim"]["forbidden_variants"]:
        lines.append(f"- forbidden term variant: {variant}")
    lines.append(f"- {brief['must_not_claim']['rule']}")
    lines.append("")
    return "\n".join(lines) + "\n"


def compile_writing_spine(
    root: Path,
    *,
    paper_plan: str,
    writer_package: str | None = None,
    output: str | None = None,
    json_output: str | None = None,
) -> dict[str, Any]:
    plan_path = resolve_path(paper_plan, root).resolve()
    plan = load_structured(plan_path)
    package = None
    if writer_package:
        package = load_structured(resolve_path(writer_package, root).resolve())
    spine = build_writing_spine(plan, package)
    json_path = resolve_path(json_output or ".harness/views/writing_spine.json", root).resolve()
    write_json(json_path, spine)
    md_path = resolve_path(output or ".harness/views/WRITING_SPINE.md", root).resolve()
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_spine_markdown(spine), encoding="utf-8")
    return {
        "ok": True,
        "paper_plan": rel_path(plan_path, root),
        "writer_package": rel_path(resolve_path(writer_package, root).resolve(), root) if writer_package else None,
        "json": rel_path(json_path, root),
        "markdown": rel_path(md_path, root),
        "sections": len(spine["sections"]),
        "handoffs": len(spine["cross_question_handoffs"]),
        "boundary": "Derived view only; it creates no gate, receipt, or new contract.",
    }


def compile_section_brief(
    root: Path,
    *,
    paper_plan: str,
    section_id: str,
    writer_package: str | None = None,
    output: str | None = None,
    json_output: str | None = None,
) -> dict[str, Any]:
    plan_path = resolve_path(paper_plan, root).resolve()
    plan = load_structured(plan_path)
    package = None
    if writer_package:
        package = load_structured(resolve_path(writer_package, root).resolve())
    brief = build_section_brief(plan, package, section_id)
    json_path = resolve_path(json_output or f".harness/views/sections/{section_id}_brief.json", root).resolve()
    write_json(json_path, brief)
    md_path = resolve_path(output or f".harness/views/sections/{section_id}_brief.md", root).resolve()
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(render_brief_markdown(brief), encoding="utf-8")
    return {
        "ok": True,
        "section": section_id,
        "paper_plan": rel_path(plan_path, root),
        "writer_package": rel_path(resolve_path(writer_package, root).resolve(), root) if writer_package else None,
        "json": rel_path(json_path, root),
        "markdown": rel_path(md_path, root),
        "units": len(brief["ordered_units"]),
        "boundary": "Derived view only; it creates no gate, receipt, or new contract.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--writer-package")
    parser.add_argument("--section", help="compile one section brief instead of the whole-paper spine")
    parser.add_argument("--output")
    parser.add_argument("--json-output")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    try:
        if args.section:
            result = compile_section_brief(
                root,
                paper_plan=args.paper_plan,
                section_id=args.section,
                writer_package=args.writer_package,
                output=args.output,
                json_output=args.json_output,
            )
        else:
            result = compile_writing_spine(
                root,
                paper_plan=args.paper_plan,
                writer_package=args.writer_package,
                output=args.output,
                json_output=args.json_output,
            )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
