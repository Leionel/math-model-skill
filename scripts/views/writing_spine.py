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

# These are projections, not additions to the paper-plan contract.  A plan
# already records the machine-facing references (role, prerequisites, claims,
# evidence and boundaries); the Writer needs the same information grouped as
_WRITING_REFERENCES = (
    "references/writing/manuscript_logic.md",
    "references/writing/abstract_guidelines.md",
    "references/writing/consistency_guidelines.md",
    "references/writing/cumcm_empirical_style.md",
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
            "derived_result_ids": unit.get("derived_result_ids", []),
            "rationale": (
                "Keep the decisive result and minimum explanation in body prose."
                if allocation["default_destination"] == "body"
                else (
                    "Keep the compact result interpretation with the associated figure or table caption."
                    if allocation["default_destination"] == "caption"
                    else "Keep supporting parameter detail out of the main argument unless it changes the decision."
                )
            ),
        })
    return {
        "rows": rows,
        "rule": _ALLOCATION_RULE,
        "principle": "Allocate each result to body, caption, or appendix by its role and decision value; no fixed figure or paragraph quota.",
    }


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


def _string_list(value: Any) -> list[str]:
    """Return non-empty strings in declaration order without inventing IDs."""

    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _section_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row for row in plan.get("sections", [])
        if isinstance(row, dict) and isinstance(row.get("section_id"), str)
    ]


def _unit_rows(plan: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        row for row in plan.get("argument_units", [])
        if isinstance(row, dict) and isinstance(row.get("unit_id"), str)
    ]


def _unit_dependents(plan: dict[str, Any]) -> dict[str, list[str]]:
    """Build the forward view of the existing prerequisite graph."""

    dependents: dict[str, list[str]] = {unit["unit_id"]: [] for unit in _unit_rows(plan)}
    for unit in _unit_rows(plan):
        for prerequisite in _string_list(unit.get("prerequisite_unit_ids")):
            if prerequisite in dependents and unit["unit_id"] not in dependents[prerequisite]:
                dependents[prerequisite].append(unit["unit_id"])
    return dependents


def _section_thesis(section: dict[str, Any]) -> str | None:
    value = section.get("purpose")
    return value.strip() if isinstance(value, str) and value.strip() else None


def _unit_argument_projection(
    unit: dict[str, Any],
    *,
    dependents: list[str] | None = None,
) -> dict[str, Any]:
    """Project one declared unit into an argument-first Writer envelope."""

    prerequisites = _string_list(unit.get("prerequisite_unit_ids"))
    evidence_ids = _string_list(unit.get("evidence_ids"))
    dependent_ids = list(dependents or [])
    purpose = str(unit.get("rhetorical_role", "argument move")).replace("_", " ")
    explanation = unit.get("expected_reader_judgment")
    evidence_detail = {
        "evidence_ids": evidence_ids,
        "result_ids": _string_list(unit.get("result_ids")),
        "derived_result_ids": _string_list(unit.get("derived_result_ids")),
        "model_ids": _string_list(unit.get("model_ids")),
        "equation_ids": _string_list(unit.get("equation_ids")),
        "validation_obligation_ids": _string_list(unit.get("validation_obligation_ids")),
    }
    premise = {
        "unit_ids": prerequisites,
        "text": (
            "No earlier argument unit is required."
            if not prerequisites
            else "Builds on: " + ", ".join(prerequisites) + "."
        ),
    }
    next_relation = {
        "unit_ids": dependent_ids,
        "relation": "Feeds the listed unit(s)." if dependent_ids else "Terminal unit.",
    }
    argument = {
        "purpose": purpose,
        "premise": premise,
        "evidence": evidence_detail,
        "explanation": explanation,
        "boundary": unit.get("boundary"),
        "next_relation": next_relation,
    }
    projected = dict(unit)
    projected.update({
        "purpose": purpose,
        "premise": premise,
        "evidence_detail": evidence_detail,
        "explanation": explanation,
        "next_relation": next_relation,
        "argument": argument,
    })
    return projected


def _micro_guideline_for_section(section: dict[str, Any], units: list[dict[str, Any]]) -> str:
    """Select one existing writing reference for the current drafting task."""

    haystack = " ".join(str(section.get(field, "")) for field in ("section_id", "role", "purpose")).casefold()
    roles = {str(unit.get("rhetorical_role")) for unit in units}
    if "abstract" in haystack:
        return "references/writing/abstract_guidelines.md"
    if roles.intersection({"result_observation", "comparison", "validation", "interpretation", "recommendation"}):
        return "references/writing/consistency_guidelines.md"
    if roles.intersection({"problem_tension", "model_choice", "mechanism_derivation", "parameter_evidence"}):
        return "references/writing/manuscript_logic.md"
    return "references/writing/cumcm_empirical_style.md"


def build_writer_context(
    plan: dict[str, Any],
    section_id: str,
    *,
    draft_path: str | None = None,
    spine_path: str = ".harness/views/WRITING_SPINE.md",
    brief_path: str | None = None,
    package_path: str = ".harness/reports/writer_package.json",
    micro_guideline: str | None = None,
) -> dict[str, Any]:
    """Build the bounded default context for one Writer task.

    This manifest deliberately names paths and locator policies rather than
    loading a second copy of the contracts.  The caller may resolve a listed
    path on demand; the default set contains only the spine, current brief,
    current draft, and one task-specific existing writing reference.
    """

    sections = {row["section_id"]: row for row in _section_rows(plan)}
    if section_id not in sections:
        raise ValueError(f"unknown section_id {section_id!r}; plan sections: {sorted(sections)}")
    section = sections[section_id]
    units = _ordered_units_for_section(plan, section_id)
    brief_path = brief_path or f".harness/views/sections/{section_id}_brief.md"
    draft_path = draft_path or f"paper/sections/{section_id}/draft.md"
    guideline = micro_guideline or _micro_guideline_for_section(section, units)
    default_context = [
        {"path": spine_path, "kind": "writing_spine", "required": True, "mutable": False},
        {"path": brief_path, "kind": "section_brief", "required": True, "mutable": False},
        {"path": draft_path, "kind": "current_draft", "required": True, "mutable": True},
        {"path": guideline, "kind": "micro_guideline", "required": True, "mutable": False},
    ]
    claim_ids = sorted({
        claim_id
        for unit in units
        for claim_id in _string_list(unit.get("claim_ids"))
    })
    result_ids = sorted({
        result_id
        for unit in units
        for result_id in _string_list(unit.get("result_ids")) + _string_list(unit.get("derived_result_ids"))
    })
    on_demand = [
        {
            "path": package_path,
            "kind": "writer_package",
            "locator": [f"claim:{claim_id}" for claim_id in claim_ids] + [f"result:{result_id}" for result_id in result_ids],
        },
        {
            "path": ".harness/contracts/paper_plan.json",
            "kind": "paper_plan",
            "locator": [f"argument_unit:{unit_id}" for unit_id in [unit.get("unit_id") for unit in units] if unit_id],
        },
        {
            "path": ".harness/results/frozen_results.json",
            "kind": "frozen_results",
            "locator": [f"result_id:{result_id}" for result_id in result_ids],
        },
    ]
    for reference in _WRITING_REFERENCES:
        if reference != guideline:
            on_demand.append({
                "path": reference,
                "kind": "writing_reference",
                "locator": "requested section or heading",
            })
    return {
        "schema_version": "1.0",
        "mode": "argument_first",
        "section_id": section_id,
        "default_context": default_context,
        "default_files": [row["path"] for row in default_context],
        "on_demand": on_demand,
        "explicit_locator_required": True,
        "excluded_by_default": [
            "full model contract",
            "all frozen results",
            "other paper sections",
            "reviewer reasoning and previous verdicts",
            "unrelated writing references",
        ],
        "boundary": "Derived context only; facts still come from explicit locators.",
    }


def _review_report_rows(review_reports: Any) -> list[dict[str, Any]]:
    """Accept one canonical review report or a list of canonical reports."""

    if isinstance(review_reports, dict) and isinstance(review_reports.get("findings"), list):
        return [review_reports]
    if isinstance(review_reports, list):
        return [row for row in review_reports if isinstance(row, dict)]
    return []


def _open_finding_rows(review_reports: Any) -> list[dict[str, Any]]:
    """Keep only actionable open findings and merge duplicate stable IDs."""

    merged: dict[str, dict[str, Any]] = {}
    for report in _review_report_rows(review_reports):
        for raw in report.get("findings", []):
            if not isinstance(raw, dict) or raw.get("status") != "open":
                continue
            finding_id = raw.get("finding_id")
            if not isinstance(finding_id, str) or not finding_id:
                continue
            merged.setdefault(finding_id, dict(raw))
    return [merged[key] for key in sorted(merged)]


def _open_finding_count(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, dict) and "revision_package" in value:
        value = value.get("revision_package")
    if isinstance(value, dict) and isinstance(value.get("finding_counts"), dict):
        raw = value["finding_counts"].get("open")
        if isinstance(raw, int):
            return raw
    if isinstance(value, dict) and isinstance(value.get("findings"), list):
        return len([row for row in value["findings"] if isinstance(row, dict) and row.get("status") == "open"])
    if isinstance(value, list):
        return len(_open_finding_rows(value))
    return None


def _finding_section(finding: dict[str, Any], plan: dict[str, Any]) -> tuple[str | None, str]:
    """Resolve a finding to the existing plan section when evidence permits."""

    sections = [row for row in _section_rows(plan)]
    section_ids = {row["section_id"] for row in sections}
    claims = {
        row.get("claim_id"): row
        for row in plan.get("claims", [])
        if isinstance(row, dict) and isinstance(row.get("claim_id"), str)
    }
    claim_id = finding.get("affected_claim_id")
    if isinstance(claim_id, str) and isinstance(claims.get(claim_id), dict):
        section = claims[claim_id].get("section")
        if isinstance(section, str) and section in section_ids:
            return section, "affected_claim_id"
    text = " ".join(
        str(finding.get(field, ""))
        for field in ("affected_artifact", "evidence_locator")
    )
    for section_id in sorted(section_ids, key=lambda item: (-len(item), item)):
        if section_id.casefold() in text.casefold():
            return section_id, "artifact_or_locator"
    return None, "unresolved"


def build_bounded_revision_package(
    plan: dict[str, Any],
    review_reports: Any,
    *,
    mode: str = "normal",
    round_number: int = 1,
    previous: dict[str, Any] | list[dict[str, Any]] | None = None,
    review_report_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Derive a finite, finding-scoped revision packet from review evidence.

    The packet is a regenerable projection.  It never edits a report or author
    artifact, invents evidence, or creates a second outline.  A subsequent
    review should be supplied as ``previous`` so the stop rule can compare the
    number of still-open stable findings.
    """

    if not isinstance(plan, dict):
        raise ValueError("paper plan must be an object")
    if not isinstance(round_number, int) or isinstance(round_number, bool) or round_number < 1:
        raise ValueError("round_number must be a positive integer")
    if mode not in {"normal", "award"}:
        raise ValueError("revision mode must be normal or award")
    max_rounds = 2 if mode == "award" else 1
    findings = _open_finding_rows(review_reports)
    previous_open = _open_finding_count(previous)
    actions: list[dict[str, Any]] = []
    for finding in findings:
        section_id, resolution = _finding_section(finding, plan)
        required_scope = finding.get("required_evidence_scope")
        if not isinstance(required_scope, str) or not required_scope:
            required_scope = "paper_only"
        action = {
            "finding_id": finding["finding_id"],
            "severity": finding.get("severity"),
            "section_id": section_id,
            "section_resolution": resolution,
            "summary": finding.get("summary"),
            "action": finding.get("required_fix"),
            "required_evidence_scope": required_scope,
            "requires_external_check": finding.get("requires_external_check") is True,
            "recheck": {
                "checks": ["deterministic QA", "fresh semantic review"],
                "finding_id": finding["finding_id"],
            },
        }
        if isinstance(finding.get("required_experiment"), str) and finding["required_experiment"].strip():
            action["required_experiment"] = finding["required_experiment"].strip()
        if section_id is not None:
            action["existing_views"] = [
                ".harness/views/WRITING_SPINE.md",
                f".harness/views/sections/{section_id}_brief.md",
            ]
        else:
            action["existing_views"] = [".harness/views/WRITING_SPINE.md"]
            action["triage"] = "Map the finding to an existing section before editing; do not create an outline."
        actions.append(action)

    current_open = len(findings)
    stop_reason = None
    if current_open == 0:
        stop_reason = None
    elif round_number > max_rounds:
        stop_reason = "revision_budget_exhausted"
    elif previous_open is not None and current_open >= previous_open:
        stop_reason = "finding_count_not_decreased"
    status = "complete" if current_open == 0 else ("stopped" if stop_reason else "ready")
    decision = "complete" if status == "complete" else ("stop_and_request_human_decision" if stop_reason else "proceed")
    result = {
        "schema_version": "1.0",
        "projection": "bounded_revision_package",
        "run_id": plan.get("run_id"),
        "mode": mode,
        "round": round_number,
        "max_rounds": max_rounds,
        "status": status,
        "decision": decision,
        "finding_counts": {
            "open": current_open,
            "previous_open": previous_open,
            "decreased": previous_open is not None and current_open < previous_open,
        },
        "findings": actions,
        "source_reports": list(review_report_paths or []),
        "stop_reason": stop_reason,
        "boundary": (
            "Derived from stable open review findings; apply only listed actions, then rerun the listed checks. "
            "No finding reduction permits another round, and the normal/award round cap remains in force."
        ),
    }
    return result


def build_writing_spine(plan: dict[str, Any], package: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(plan, dict):
        raise ValueError("paper plan must be an object")
    sections = _section_rows(plan)
    if not sections:
        raise ValueError("paper plan has no sections to project")
    dependents = _unit_dependents(plan)
    all_units = {row["unit_id"]: row for row in _unit_rows(plan)}
    section_rows = []
    for section in sections:
        units = _ordered_units_for_section(plan, section["section_id"])
        projected_units = [
            _unit_argument_projection(unit, dependents=dependents.get(str(unit.get("unit_id")), []))
            for unit in units
        ]
        section_rows.append({
            "section_id": section["section_id"],
            "purpose": section.get("purpose"),
            "section_thesis": _section_thesis(section),
            "claim_ids": section.get("claim_ids", []),
            "phase": _section_phase(units),
            "reader_exit": [
                unit.get("expected_reader_judgment")
                for unit in units
                if isinstance(unit.get("expected_reader_judgment"), str)
            ],
            "units": [
                projected
                for projected in projected_units
            ],
        })
    unit_section = {
        unit_id: unit.get("section_id")
        for unit_id, unit in all_units.items()
    }
    handoffs = []
    for section in section_rows:
        for unit in section["units"]:
            for prerequisite in _string_list(unit.get("prerequisite_unit_ids")):
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
        if section.get("section_thesis"):
            lines.append(f"- section thesis: {section['section_thesis']}")
        if section.get("claim_ids"):
            lines.append(f"- claims: {', '.join(section['claim_ids'])}")
        if section.get("reader_exit"):
            lines.append("- reader exit: " + " | ".join(section["reader_exit"]))
        lines.append("- units:")
        for unit in section["units"]:
            lines.append(
                f"  - `{unit['unit_id']}` [{unit.get('rhetorical_role')}] claims={','.join(unit.get('claim_ids', []))}"
                f" prereq={','.join(unit.get('prerequisite_unit_ids', [])) or 'none'}"
            )
            lines.append(f"    purpose: {unit.get('purpose')}")
            lines.append(f"    explanation: {unit.get('explanation')}")
            next_relation = unit.get("next_relation")
            if isinstance(next_relation, dict):
                lines.append(
                    f"    next: {', '.join(next_relation.get('unit_ids', [])) or 'terminal'}"
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
    def include(row: Any) -> bool:
        return (
            isinstance(row, dict)
            and (
                row.get("paper_location") == section_id
                or bool(claims.intersection(_string_list(row.get("claim_ids"))))
            )
        )

    figures = [row.get("figure_id") for row in plan.get("figures", []) if include(row)]
    tables = [row.get("table_id") for row in plan.get("tables", []) if include(row)]
    return (
        list(dict.fromkeys(row for row in figures if isinstance(row, str) and row)),
        list(dict.fromkeys(row for row in tables if isinstance(row, str) and row)),
    )


def build_section_brief(plan: dict[str, Any], package: dict[str, Any] | None, section_id: str) -> dict[str, Any]:
    sections = {row["section_id"]: row for row in _section_rows(plan)}
    if section_id not in sections:
        raise ValueError(f"unknown section_id {section_id!r}; plan sections: {sorted(sections)}")
    units = _ordered_units_for_section(plan, section_id)
    section = sections[section_id]
    dependents = _unit_dependents(plan)
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
    next_handoffs = []
    for other in all_units.values():
        if other.get("section_id") == section_id:
            continue
        for prerequisite in other.get("prerequisite_unit_ids", []):
            if prerequisite in {unit.get("unit_id") for unit in units}:
                next_handoffs.append({
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
    projected_units = [
        _unit_argument_projection(unit, dependents=dependents.get(str(unit.get("unit_id")), []))
        for unit in units
    ]
    reader_exit = [
        unit.get("expected_reader_judgment")
        for unit in units
        if isinstance(unit.get("expected_reader_judgment"), str)
    ]
    canonical = plan.get("canonical_recommendation")
    canonical_projection = None
    if isinstance(canonical, dict):
        canonical_projection = {
            **canonical,
            "wording_policy": "content_only",
            "verbatim_required": False,
        }
    allocation = _evidence_allocation(units)
    return {
        "schema_version": "1.0",
        "run_id": plan.get("run_id"),
        "projection": "section_writer_brief",
        "section_id": section_id,
        "purpose": section.get("purpose"),
        "section_thesis": _section_thesis(section),
        "reader_exit": reader_exit,
        "ordered_units": [
            projected
            for projected in projected_units
        ],
        "claims": claims_detail,
        "established_facts": established,
        "next_handoffs": next_handoffs,
        "figures": figures,
        "tables": tables,
        "evidence_allocation": allocation,
        "terminology": plan.get("terminology", []),
        "canonical_recommendation": canonical_projection,
        "writer_context": build_writer_context(plan, section_id),
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
        f"- section thesis: {brief.get('section_thesis')}",
        f"- reader exit: {' | '.join(brief.get('reader_exit', [])) or '—'}",
        "",
        "## Ordered argument units",
        "",
    ]
    for unit in brief["ordered_units"]:
        lines.append(f"### {unit['unit_id']} [{unit.get('rhetorical_role')}]")
        lines.append("")
        lines.append(f"- purpose: {unit.get('purpose')}")
        premise = unit.get("premise")
        if isinstance(premise, dict):
            lines.append(f"- premise: {premise.get('text')}")
        lines.append(f"- claims: {', '.join(unit.get('claim_ids', []))}")
        lines.append(f"- evidence: {', '.join(unit.get('evidence_ids', []))}")
        if unit.get("prerequisite_unit_ids"):
            lines.append(f"- prerequisites: {', '.join(unit['prerequisite_unit_ids'])}")
        lines.append(f"- expected reader judgment: {unit.get('expected_reader_judgment')}")
        lines.append(f"- explanation: {unit.get('explanation')}")
        lines.append(f"- boundary: {unit.get('boundary')}")
        next_relation = unit.get("next_relation")
        if isinstance(next_relation, dict):
            lines.append(
                f"- next relation: {', '.join(next_relation.get('unit_ids', [])) or 'terminal'} — "
                f"{next_relation.get('relation')}"
            )
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
            "## Canonical recommendation (content constraint; wording may vary)",
            "",
            f"- {brief['canonical_recommendation'].get('text')}",
            f"- evidence: {', '.join(brief['canonical_recommendation'].get('evidence_ids', []))}",
            "- preserve the option, declared values, evidence, and boundary; verbatim sentence copying is not required.",
        ])
    context = brief.get("writer_context")
    if isinstance(context, dict):
        lines.extend([
            "",
            "## Writer default context",
            "",
            "- default: " + ", ".join(context.get("default_files", [])),
            "- on demand: use only the listed claim/result/unit locators; do not load the full contract or all frozen results.",
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


def compile_revision_package(
    root: Path,
    *,
    paper_plan: str,
    review_reports: list[str],
    mode: str = "normal",
    round_number: int = 1,
    previous: str | None = None,
    output: str | None = None,
) -> dict[str, Any]:
    """Write one hidden, regenerable revision view from canonical reports."""

    plan = load_structured(resolve_path(paper_plan, root).resolve())
    reports = [load_structured(resolve_path(path, root).resolve()) for path in review_reports]
    if not isinstance(plan, dict) or not all(isinstance(report, dict) for report in reports):
        raise ValueError("paper plan and review reports must be objects")
    previous_value = load_structured(resolve_path(previous, root).resolve()) if previous else None
    if previous_value is not None and not isinstance(previous_value, dict):
        raise ValueError("previous revision package must be an object")
    package = build_bounded_revision_package(
        plan,
        reports,
        mode=mode,
        round_number=round_number,
        previous=previous_value,
        review_report_paths=[rel_path(resolve_path(path, root).resolve(), root) for path in review_reports],
    )
    output_path = resolve_path(output or ".harness/views/revision_package.json", root).resolve()
    write_json(output_path, package)
    return {
        "ok": package["status"] != "stopped",
        "output": rel_path(output_path, root),
        "status": package["status"],
        "open_findings": package["finding_counts"]["open"],
        "boundary": "Derived view only; it does not modify review reports, author drafts, or Gate state.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--paper-plan", required=True)
    parser.add_argument("--writer-package")
    parser.add_argument("--section", help="compile one section brief instead of the whole-paper spine")
    parser.add_argument("--revision-report", action="append", default=[], help="compile a bounded revision view from a canonical review report")
    parser.add_argument("--revision-mode", choices=("normal", "award"), default="normal")
    parser.add_argument("--revision-round", type=int, default=1)
    parser.add_argument("--previous-revision")
    parser.add_argument("--output")
    parser.add_argument("--json-output")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    try:
        if args.revision_report:
            if args.section:
                raise ValueError("choose either --section or --revision-report")
            result = compile_revision_package(
                root,
                paper_plan=args.paper_plan,
                review_reports=args.revision_report,
                mode=args.revision_mode,
                round_number=args.revision_round,
                previous=args.previous_revision,
                output=args.json_output,
            )
        elif args.section:
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
