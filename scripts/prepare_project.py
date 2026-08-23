#!/usr/bin/env python3
"""Render deterministic human-facing projections for M1, W1, W2, and S1."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_structured, rel_path, resolve_ai_usage_state, resolve_path, sha256_file  # noqa: E402
from harness_status import _v2_status  # noqa: E402
from runtime_state import RuntimeState, RuntimeStateError, load_runtime_state  # noqa: E402
from project_layout import resolve_manifest_path  # noqa: E402


PROJECTION_NOTICE = "Generated projection — factual state remains in Harness contracts/receipts."
STAGES = ("M1", "W1", "W2", "S1")


def _as_rows(value: Any) -> list[dict[str, Any]]:
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _text(value: Any, fallback: str = "not declared") -> str:
    return str(value).strip() if value not in (None, "") else fallback


def _list(value: Any) -> str:
    rows = [str(item) for item in value] if isinstance(value, list) else []
    return ", ".join(rows) if rows else "not declared"


def _load_optional(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.is_file():
        return None
    value = load_structured(path)
    return dict(value) if isinstance(value, Mapping) else None


def _dag_nodes(state: RuntimeState) -> list[dict[str, Any]]:
    dag = _load_optional(state.root_path("artifact_dag"))
    return _as_rows(dag.get("nodes")) if dag else []


def _artifact_path(state: RuntimeState, role: str) -> Path | None:
    candidates = [
        row for row in _dag_nodes(state)
        if row.get("role") == role and isinstance(row.get("path"), str)
    ]
    if candidates:
        current = [row for row in candidates if row.get("freshness") == "current"]
        selected = current[-1] if current else None
        return resolve_path(str(selected["path"]), state.root).resolve() if selected else None
    return state.root_path(role)


def _sources(state: RuntimeState, paths: Iterable[Path | None]) -> list[tuple[str, str]]:
    unique: dict[str, str] = {}
    for path in [state.manifest_path, state.profile_path, *paths]:
        if path is not None and path.is_file():
            unique[rel_path(path, state.root)] = sha256_file(path)
    return sorted(unique.items())


def _header(title: str, sources: list[tuple[str, str]]) -> list[str]:
    lines = [f"# {title}", "", f"> {PROJECTION_NOTICE}", "", "## Projection provenance", ""]
    lines.extend(f"- `{path}` — SHA-256 `{digest}`" for path, digest in sources)
    if not sources:
        lines.append("- No readable canonical source was found.")
    return lines + [""]


def _write_projection(path: Path, lines: list[str]) -> bool:
    content = "\n".join(lines).rstrip() + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True


def _ai_declaration_valid(manifest: Mapping[str, Any]) -> bool:
    state = resolve_ai_usage_state(manifest)
    raw_rows = manifest.get("ai_usage")
    rows = _as_rows(raw_rows)
    declaration = manifest.get("ai_usage_declaration")
    if state == "none":
        return (
            isinstance(declaration, Mapping)
            and declaration.get("status") == "none"
            and all(_text(declaration.get(key), "") for key in ("confirmed_by", "confirmed_at", "reason"))
            and isinstance(raw_rows, list)
            and not raw_rows
        )
    if state == "used":
        required = {
            "usage_id", "tool_name", "model", "provider", "used_at", "stage",
            "purpose", "prompt_summary", "output_use", "human_changes",
            "interaction_record", "verification",
        }
        return (
            isinstance(raw_rows, list)
            and bool(rows)
            and len(rows) == len(raw_rows)
            and declaration is None
            and all(required <= set(row) for row in rows)
        )
    return False


def _acceptance(value: Any) -> str:
    if not isinstance(value, Mapping):
        return _text(value)
    right = value.get("right")
    if isinstance(right, Mapping):
        rhs = right.get("value") if right.get("kind") == "literal" else right.get("metric_id")
    else:
        rhs = right
    return f"{_text(value.get('left_metric_id'))} {_text(value.get('operator'))} {_text(rhs)} {_text(value.get('unit'), '')}".strip()


def render_modeling_plan(state: RuntimeState, contract_path: Path | None) -> list[str]:
    contract = _load_optional(contract_path)
    lines = _header("Modeling Plan", _sources(state, [contract_path]))
    if contract is None:
        return lines + [
            "## Blocking input", "", "- `model_contract` is missing or unreadable.",
            "- This projection does not approve M1; create and validate the contract first.", "",
        ]
    lines += [
        "## Problem scope", "",
        f"- Contract status: **{_text(contract.get('status'))}**",
        f"- Unit system: {_text(contract.get('unit_system'))}",
        f"- Problem statement: {_text(contract.get('problem_statement'))}", "",
        "## Question decomposition", "",
    ]
    for question in _as_rows(contract.get("questions")):
        answer = question.get("required_answer") if isinstance(question.get("required_answer"), Mapping) else {}
        lines += [
            f"### {question.get('question_id')} — {_text(question.get('task'))}", "",
            f"- Required conclusion: {_text(question.get('conclusion_type'))}",
            f"- Inputs: {_list(question.get('inputs'))}",
            f"- Outputs: {_list(question.get('outputs'))}",
            f"- Depends on: {_list(question.get('depends_on'))}",
            f"- Answer contract: {_text(answer.get('answer_type'))}; {_text(answer.get('quantity'))} [{_text(answer.get('unit'), 'unit not declared')}]",
            f"- Scope: {_text(answer.get('scope'))}",
            f"- Must satisfy: {_list(answer.get('must_satisfy'))}",
            f"- Reporting semantics: {_text(answer.get('reporting_semantics'))}", "",
        ]
    lines += ["## Data and quality obligations", ""]
    data_rows = _as_rows(contract.get("data_sources"))
    lines.extend(
        f"- **{row.get('data_id')}** `{_text(row.get('path'))}` — origin: {_text(row.get('origin'))}; checks: {_list(row.get('quality_checks'))}"
        for row in data_rows
    )
    if not data_rows:
        lines.append("- No data source declared; confirm whether the problem is data-free.")
    lines += ["", "## Assumptions and forks", ""]
    assumptions = _as_rows(contract.get("assumptions"))
    lines.extend(
        f"- **{row.get('assumption_id')}** {_text(row.get('text'))} — basis: {_text(row.get('basis'))}; sensitivity: {_text(row.get('sensitivity_plan'))}"
        for row in assumptions
    )
    if not assumptions:
        lines.append("- No assumptions declared.")
    forks = _as_rows(contract.get("assumption_forks"))
    for row in forks:
        state_label = f"selected `{row.get('selected')}`" if row.get("selected") else "**UNRESOLVED**"
        lines.append(f"- **{row.get('fork_id')}** {_text(row.get('phrase'))} — {state_label}; risk: {_text(row.get('unresolved_risk'))}")
        for interpretation in _as_rows(row.get("interpretations")):
            lines.append(f"  - `{interpretation.get('id')}` {_text(interpretation.get('meaning'))} → {_text(interpretation.get('mathematical_effect'))}")
    lines += ["", "## Candidate comparison", ""]
    basis = contract.get("research_basis") if isinstance(contract.get("research_basis"), Mapping) else {}
    candidates = _as_rows(basis.get("candidate_models"))
    if candidates:
        lines += ["| Candidate | Question | Decision | Mechanism fit | Strengths | Weaknesses |", "|---|---|---|---|---|---|"]
        for row in candidates:
            lines.append(f"| {row.get('name')} | {row.get('question_id')} | {row.get('decision')} | {_text(row.get('mechanism_fit'))} | {_list(row.get('strengths'))} | {_list(row.get('weaknesses'))} |")
    else:
        lines.append("- Candidate-model comparison is not declared.")
    lines += ["", "## Selected model contracts", ""]
    for model in _as_rows(contract.get("models")):
        lines += [
            f"### {model.get('model_id')} — {_text(model.get('name'))}", "",
            f"- Question: {model.get('question_id')}; family: {_text(model.get('problem_family'), _text(model.get('problem_type')))}",
            f"- Rationale: {_text(model.get('rationale'))}",
            f"- Objective: `{_text(model.get('objective'))}`",
            f"- Algorithm: {_text(model.get('algorithm'))}",
            f"- Inputs → outputs: {_list(model.get('inputs'))} → {_list(model.get('outputs'))}",
            f"- Risks: {_list(model.get('risks'))}",
            f"- Fallback: {_text(model.get('fallback'))}", "",
            "Validation obligations:", "",
        ]
        obligations = _as_rows(model.get("validation_obligations"))
        lines.extend(
            f"- `{row.get('obligation_id')}` [{row.get('required_stage')}] {row.get('category')}: {_text(row.get('method'))}; accept when {_acceptance(row.get('acceptance'))}"
            for row in obligations
        )
        plan = model.get("plan_details") if isinstance(model.get("plan_details"), Mapping) else {}
        if plan:
            lines += ["", "Implementation sequence:", ""]
            lines.extend(f"1. {step}" for step in plan.get("implementation_steps", []) if isinstance(step, str))
            lines += ["", f"Expected artifacts: {_list(plan.get('output_artifacts'))}", ""]
    unresolved = [str(row.get("fork_id")) for row in forks if not row.get("selected")]
    unresolved.extend(str(item) for item in basis.get("unresolved_questions", []) if isinstance(item, str))
    lines += ["## Unresolved items", ""]
    lines.extend(f"- [ ] {item}" for item in unresolved)
    if not unresolved:
        lines.append("- None declared; this is not proof that no modeling ambiguity remains.")
    lines += ["", "## M1 approval checklist", "", "- [ ] Each question has a testable output contract.", "- [ ] Assumption forks are selected or explicitly left unresolved.", "- [ ] Model choice is compared against credible alternatives.", "- [ ] Every validation obligation has an acceptance rule.", "- [ ] A human has reviewed scope, units, and core modeling responsibility.", ""]
    return lines


def _claim_map(plan: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("claim_id")): row for row in _as_rows(plan.get("claims")) if row.get("claim_id")}


def render_paper_outline(state: RuntimeState, plan_path: Path | None, frozen_path: Path | None) -> list[str]:
    plan = _load_optional(plan_path)
    lines = _header("Paper Outline", _sources(state, [plan_path, frozen_path]))
    if plan is None:
        return lines + ["## Blocking input", "", "- `paper_plan` is missing or unreadable; W1 cannot be projected.", ""]
    thesis = plan.get("central_thesis") if isinstance(plan.get("central_thesis"), Mapping) else {}
    claims = _claim_map(plan)
    lines += [
        "## Central thesis", "", _text(thesis.get("text")), "",
        f"Boundary: {_text(thesis.get('boundary'))}", "",
        "## Argument order", "",
    ]
    units_by_section: dict[str, list[dict[str, Any]]] = {}
    for unit in _as_rows(plan.get("argument_units")):
        units_by_section.setdefault(str(unit.get("section_id")), []).append(unit)
    for section in _as_rows(plan.get("sections")):
        section_id = str(section.get("section_id"))
        lines += [f"### {section_id}", "", f"Purpose: {_text(section.get('purpose'))}", ""]
        for unit in units_by_section.get(section_id, []):
            evidence = [str(item) for item in unit.get("evidence_ids", [])] if isinstance(unit.get("evidence_ids"), list) else []
            marker = "OK" if evidence else "MISSING EVIDENCE"
            unit_claims = [claims.get(str(item), {}) for item in unit.get("claim_ids", []) if str(item) in claims]
            lines.append(f"- **{unit.get('unit_id')} / {unit.get('rhetorical_role')} / {marker}** — {_text(unit.get('expected_reader_judgment'))}")
            for claim in unit_claims:
                claim_evidence = _list(claim.get("evidence_ids"))
                lines.append(f"  - Claim `{claim.get('claim_id')}`: {_text(claim.get('text'))} (evidence: {claim_evidence}; boundary: {_text(claim.get('boundary'))})")
        lines.append("")
    lines += ["## Planned figures and tables", ""]
    for row in _as_rows(plan.get("figures")):
        lines.append(f"- Figure `{row.get('figure_id', row.get('id', '?'))}`: {_text(row.get('title'), _text(row.get('claim_or_purpose')))} — evidence: {_list(row.get('evidence_ids'))}")
    for row in _as_rows(plan.get("tables")):
        lines.append(f"- Table `{row.get('table_id', row.get('id', '?'))}`: {_text(row.get('title'), _text(row.get('purpose')))} — evidence: {_list(row.get('evidence_ids'))}")
    lines += ["", "## Abstract evidence gate", ""]
    for row in _as_rows(plan.get("abstract_results")):
        lines.append(f"- `{row.get('abstract_id', row.get('result_id', '?'))}` {_text(row.get('text'), _text(row.get('claim')))} — evidence: {_list(row.get('evidence_ids'))}")
    lines += ["", "## Deliverables", ""]
    deliverables = _as_rows(plan.get("deliverables"))
    if deliverables:
        lines += ["| ID | Type | Required | Status | Target |", "|---|---|---:|---|---|"]
        for row in deliverables:
            lines.append(f"| {row.get('deliverable_id')} | {row.get('type')} | {'yes' if row.get('required_by_profile') else 'no'} | {row.get('status')} | {_text(row.get('target_path'))} |")
    else:
        lines.append("- No deliverables plan declared; confirm appendices, official outputs, support material, and AI report before W1 approval.")
    missing = [row for row in claims.values() if not row.get("evidence_ids")]
    lines += ["", "## Remaining evidence gaps", ""]
    lines.extend(f"- [ ] `{row.get('claim_id')}` {_text(row.get('text'))}" for row in missing)
    if not missing:
        lines.append("- No structurally empty claim evidence list; semantic support still requires review.")
    return lines + [""]


def render_appendix_plan(state: RuntimeState, plan_path: Path | None) -> list[str]:
    plan = _load_optional(plan_path)
    lines = _header("Appendix and Deliverables Plan", _sources(state, [plan_path]))
    lines += ["## Planned deliverables", ""]
    deliverables = _as_rows(plan.get("deliverables")) if plan else []
    for row in deliverables:
        lines += [
            f"### {row.get('deliverable_id')} — {_text(row.get('title'), str(row.get('type')))}", "",
            f"- Type: {row.get('type')}", f"- Required by profile: {'yes' if row.get('required_by_profile') else 'no'}",
            f"- Status: {row.get('status')}", f"- Target: {_text(row.get('target_path'))}",
            f"- Sources: {_list(row.get('source_refs'))}", f"- Notes: {_text(row.get('notes'))}", "",
        ]
    if not deliverables:
        lines += ["- No deliverables are declared in `paper_plan.json`.", "- [ ] Decide whether appendices, source code, official workbooks, support material, or an AI report are required.", ""]
    return lines


def render_ai_ledger(state: RuntimeState) -> list[str]:
    rows = _as_rows(state.manifest.get("ai_usage"))
    ai_state = resolve_ai_usage_state(state.manifest)
    lines = _header("AI Usage Ledger", _sources(state, []))
    lines += [f"## Declaration state: `{ai_state}`", ""]
    declaration_valid = _ai_declaration_valid(state.manifest)
    if not declaration_valid:
        lines += ["- **BLOCKED:** AI usage declaration is missing or internally inconsistent.", "- Run `harness ai record ...` for each use, or `harness ai confirm-none ...` after a human confirms no AI was used.", ""]
    elif ai_state == "none":
        declaration = state.manifest.get("ai_usage_declaration") if isinstance(state.manifest.get("ai_usage_declaration"), Mapping) else {}
        lines += [f"- Confirmed by: {_text(declaration.get('confirmed_by'))}", f"- Confirmed at: {_text(declaration.get('confirmed_at'))}", f"- Reason: {_text(declaration.get('reason'))}", ""]
    else:
        lines += ["| ID | Tool / model | Stage | Purpose | Output use | Human verification | Record |", "|---|---|---|---|---|---|---|"]
        for row in rows:
            verification = row.get("verification") if isinstance(row.get("verification"), Mapping) else {}
            record = row.get("interaction_record") if isinstance(row.get("interaction_record"), Mapping) else {}
            lines.append(f"| {row.get('usage_id')} | {_text(row.get('tool_name'))} / {_text(row.get('model'))} | {_text(row.get('stage'))} | {_text(row.get('purpose'))} | {_text(row.get('output_use'))} | {_text(verification.get('status'))}: {_text(verification.get('method'))} | `{_text(record.get('path'))}` |")
        lines.append("")
    return lines


def refresh_ai_ledger(state: RuntimeState) -> tuple[Path, bool]:
    """Refresh the one human-facing ledger after an explicit AI mutation."""

    path = state.root / ".harness" / "views" / "AI_USAGE_LEDGER.md"
    return path, _write_projection(path, render_ai_ledger(state))


def render_ai_disclosure(state: RuntimeState) -> tuple[str, list[str]]:
    family = str((state.profile.get("competition") or {}).get("family", "")).casefold()
    title = "AI工具使用详情" if "cumcm" in family else "Report on Use of AI Tools"
    rows = _as_rows(state.manifest.get("ai_usage"))
    ai_state = resolve_ai_usage_state(state.manifest)
    lines = _header(title, _sources(state, []))
    lines += [f"## Declaration state: `{ai_state}`", ""]
    if not _ai_declaration_valid(state.manifest):
        lines += ["**DRAFT BLOCKED — AI usage declaration is missing or inconsistent.**", "", "No AI-use details are inferred or invented by this renderer.", ""]
    elif ai_state == "none":
        lines += ["The team explicitly declared that no AI tool was used for this project.", ""]
    else:
        for index, row in enumerate(rows, start=1):
            verification = row.get("verification") if isinstance(row.get("verification"), Mapping) else {}
            lines += [
                f"## {index}. {_text(row.get('tool_name'))} / {_text(row.get('model'))}", "",
                f"- Provider: {_text(row.get('provider'))}", f"- Stage: {_text(row.get('stage'))}",
                f"- Purpose: {_text(row.get('purpose'))}", f"- Main prompt approach: {_text(row.get('prompt_summary'))}",
                f"- Adopted output: {_text(row.get('output_use'))}", f"- Human modifications: {_text(row.get('human_changes'))}",
                f"- Human verification: {_text(verification.get('status'))}; {_text(verification.get('method'))}", "",
            ]
    return title, lines


def render_project_brief(state: RuntimeState) -> list[str]:
    status = _v2_status(state)
    dag_path = state.root_path("artifact_dag")
    index_path = state.root_path("run_index")
    paper_plan_path = _artifact_path(state, "paper_plan")
    paper_plan = _load_optional(paper_plan_path)
    runtime_paths: list[Path | None] = [dag_path, index_path, paper_plan_path]
    runtime_paths.extend(
        resolve_path(str(row["path"]), state.root).resolve()
        for row in _dag_nodes(state)
        if isinstance(row.get("path"), str)
    )
    runtime_paths.extend(sorted((state.root / "reports" / "review").glob("*.json")))
    lines = _header("Project Brief", _sources(state, runtime_paths))
    ai_state = resolve_ai_usage_state(state.manifest)
    lines += [
        "## Current state", "",
        f"- Project / run: `{state.manifest.get('project_id')}` / `{state.run_id}`",
        f"- Stage / status / preset: `{state.manifest.get('stage')}` / `{state.manifest.get('status')}` / `{state.preset}`",
        f"- Competition profile: `{state.profile.get('profile_id')}` ({state.profile.get('status')})",
        f"- AI usage: `{ai_state}` ({len(_as_rows(state.manifest.get('ai_usage')))} records)", "",
        "## Gate view", "",
    ]
    for name, gate in (status.get("gates") or {}).items():
        if isinstance(gate, Mapping):
            lines.append(f"- **{str(name).upper()}**: {gate.get('status')} — {_list(gate.get('errors'))}")
    lines += ["", f"First blocked gate: **{str(status.get('first_blocked_gate') or 'none').upper()}**", ""]
    pending = _as_rows(status.get("pending_human_checkpoints"))
    lines += ["## Pending human checkpoints", ""]
    lines.extend(f"- [ ] {row.get('stage')} / {row.get('checkpoint_id', 'unidentified')} — {row.get('decision', 'unset')}" for row in pending)
    if not pending:
        lines.append("- None currently registered as pending.")
    index = _load_optional(index_path)
    selection = index.get("selection") if index and isinstance(index.get("selection"), Mapping) else {}
    receipt_view = status.get("receipts") if isinstance(status.get("receipts"), Mapping) else {}
    lines += [
        "", "## Selected execution", "",
        f"- Selected receipt IDs: {_list(selection.get('selected_receipt_ids'))}",
        f"- Successful stages: {_list(receipt_view.get('successful_stages'))}",
        f"- Preserved failed receipt IDs: {_list(receipt_view.get('failed_receipt_ids'))}", "",
    ]
    lines += ["## Artifact freshness", ""]
    artifacts = (status.get("dag") or {}).get("artifacts", []) if isinstance(status.get("dag"), Mapping) else []
    for row in _as_rows(artifacts):
        lines.append(f"- `{row.get('artifact_id')}` {row.get('role')} — {row.get('freshness')} — `{row.get('path')}`")
    if not artifacts:
        lines.append("- No projected artifacts are available.")
    lines += ["", "## Paper coverage", ""]
    if paper_plan:
        readiness = paper_plan.get("readiness") if isinstance(paper_plan.get("readiness"), Mapping) else {}
        draft_coverage = paper_plan.get("draft_coverage") if isinstance(paper_plan.get("draft_coverage"), Mapping) else {}
        lines.append(f"- Plan status / readiness stage: `{paper_plan.get('status', 'not declared')}` / `{readiness.get('stage', 'not declared')}`")
        lines.append(f"- Draft coverage status: `{draft_coverage.get('status', 'not declared')}`")
        for row in _as_rows(readiness.get("question_coverage")):
            lines.append(
                f"- {row.get('question_id')}: formulation={len(row.get('formulation_unit_ids', []))}; "
                f"result={len(row.get('result_unit_ids', []))}; validation={len(row.get('validation_unit_ids', []))}; "
                f"interpretation={len(row.get('interpretation_unit_ids', []))}; displays={len(row.get('display_ids', []))}"
            )
        pending_figures = [str(row.get("figure_id")) for row in _as_rows(paper_plan.get("figures")) if row.get("qa_status") != "passed"]
        lines.append(f"- Figures not QA-passed: {_list(pending_figures)}")
    else:
        lines.append("- Paper plan is missing or unreadable.")
    review = status.get("review") if isinstance(status.get("review"), Mapping) else {}
    lines += ["", "## Review and revision", ""]
    for name, view in (review.get("perspectives") or {}).items():
        if isinstance(view, Mapping):
            lines.append(f"- {name}: executed={view.get('executed')}; freshness={view.get('freshness')}; open blockers={_list(view.get('open_blocking_ids'))}")
    finding = review.get("next_finding") if isinstance(review.get("next_finding"), Mapping) else None
    lines.append(f"- Next targeted finding: `{finding.get('finding_id')}` — {_text(finding.get('summary'))}" if finding else "- No current targeted finding is registered.")
    lines += ["", "## Next action", "", str(status.get("next_action")), ""]
    return lines


def render_submission_checklist(state: RuntimeState) -> list[str]:
    rules = state.profile.get("submission") if isinstance(state.profile.get("submission"), Mapping) else {}
    ai_state = resolve_ai_usage_state(state.manifest)
    ai_declared = _ai_declaration_valid(state.manifest)
    ai_rows = _as_rows(state.manifest.get("ai_usage"))
    ai_verified = ai_state != "used" or (
        bool(ai_rows)
        and all(
            isinstance(row.get("verification"), Mapping)
            and row["verification"].get("status") == "verified"
            for row in ai_rows
        )
    )
    ai_policy = rules.get("ai_disclosure_policy")
    ai_required = ai_policy == "required_always" or (ai_policy == "required_when_used" and ai_state == "used")
    lines = _header("Submission Checklist", _sources(state, []))
    lines += [
        "## Promotion blockers", "",
        f"- [{'x' if state.profile.get('status') == 'verified' else ' '}] Competition profile is verified (current: `{state.profile.get('status')}`).",
        f"- [{'x' if ai_declared else ' '}] AI usage is explicitly and consistently declared (current: `{ai_state}`).",
        f"- [{'x' if ai_verified else ' '}] Every recorded AI use has completed human verification.",
        "- [ ] W2 fact gate passes on current artifacts.", "- [ ] Required S1 human checkpoint is complete.", "",
        "## Pinned submission rules", "",
        f"- Paper formats: {_list(rules.get('paper_extensions'))}", f"- Maximum pages: {_text(rules.get('max_pages'))} ({_text(rules.get('page_count_scope'))})",
        f"- Maximum paper bytes: {_text(rules.get('max_paper_bytes'))}", f"- Support material: {_text(rules.get('support_policy'))}; max bytes: {_text(rules.get('max_support_bytes'))}",
        f"- AI disclosure: {_text(ai_policy)} / {_text(rules.get('ai_disclosure_format'))}; currently required: {'yes' if ai_required else 'no'}", "",
        "## Required files", "",
    ]
    for row in _as_rows(rules.get("required_files")):
        lines.append(f"- [ ] {row.get('role')} — {row.get('format')} — pattern: {_text(row.get('pattern'))}")
    if not _as_rows(rules.get("required_files")):
        lines.append("- [ ] Required-file list is unresolved; do not guess from another competition.")
    manual = list(rules.get("required_manual_checks", [])) if isinstance(rules.get("required_manual_checks"), list) else []
    ai_manual = rules.get("ai_manual_checks") if isinstance(rules.get("ai_manual_checks"), Mapping) else {}
    manual.extend(ai_manual.get("when_used" if ai_state == "used" else "when_not_used", []))
    lines += ["", "## Manual checks", ""]
    lines.extend(f"- [ ] {item}" for item in dict.fromkeys(str(item) for item in manual))
    final_dir = state.root / "submission" / "final"
    final_nonempty = final_dir.is_dir() and any(final_dir.iterdir())
    lines += ["", "## Staging boundary", "", "- `submission/staging/` is mutable preparation space.", "- `submission/final/` must remain empty until a passing F1 freeze writes immutable final artifacts."]
    if final_nonempty:
        lines.append("- **BLOCKED:** `submission/final/` is already non-empty; inspect provenance before preparing or freezing another submission.")
    lines += ["- This checklist does not upload files and does not assert submission readiness.", ""]
    return lines


def prepare(stage: str, state: RuntimeState) -> dict[str, Any]:
    outputs: list[dict[str, Any]] = []
    warnings: list[str] = []
    views = state.root / ".harness" / "views"

    def emit(path: Path, lines: list[str]) -> None:
        changed = _write_projection(path, lines)
        outputs.append({"path": rel_path(path, state.root), "changed": changed})

    model_path = _artifact_path(state, "model_contract")
    paper_plan_path = _artifact_path(state, "paper_plan")
    frozen_path = _artifact_path(state, "frozen_results")
    if stage == "M1":
        emit(views / "M1_STATE.md", render_modeling_plan(state, model_path))
    elif stage == "W1":
        emit(views / "W1_STATE.md", render_paper_outline(state, paper_plan_path, frozen_path))
        emit(views / "APPENDIX_PLAN.md", render_appendix_plan(state, paper_plan_path))
    elif stage == "W2":
        emit(views / "W2_STATE.md", render_project_brief(state))
    elif stage == "S1":
        for path in (
            state.root / "submission" / "staging" / "support",
            state.root / "submission" / "staging" / "ai_disclosure",
            state.root / "submission" / "staging" / "official_outputs",
            state.root / "submission" / "final",
        ):
            path.mkdir(parents=True, exist_ok=True)
        final_dir = state.root / "submission" / "final"
        if any(final_dir.iterdir()):
            warnings.append("submission/final is non-empty; prepare did not modify or validate its contents")
        ledger_path, changed = refresh_ai_ledger(state)
        outputs.append({"path": rel_path(ledger_path, state.root), "changed": changed})
        title, disclosure = render_ai_disclosure(state)
        filename = "AI工具使用详情.md" if title == "AI工具使用详情" else "Report_on_Use_of_AI_Tools.md"
        emit(state.root / "submission" / "staging" / "ai_disclosure" / filename, disclosure)
        emit(views / "SUBMISSION_STATE.md", render_submission_checklist(state))
    emit(views / "PROJECT_BRIEF.md", render_project_brief(state))
    return {"ok": True, "stage": stage, "projection_notice": PROJECTION_NOTICE, "outputs": outputs, "warnings": warnings, "submission_ready": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=STAGES)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--manifest", default=None)
    args = parser.parse_args(argv)
    root = Path(args.project_root).resolve()
    try:
        state = load_runtime_state(resolve_manifest_path(root, args.manifest), project_root=root, allow_legacy=False)
        report = prepare(args.stage, state)
    except (OSError, ValueError, TypeError, RuntimeStateError) as exc:
        report = {"ok": False, "stage": args.stage, "errors": [str(exc)]}
    print(json.dumps(report, ensure_ascii=False))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
