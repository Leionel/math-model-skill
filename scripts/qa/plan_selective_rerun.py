#!/usr/bin/env python3
"""Selective rerun planning: compute the minimal rerun set after a change.

Reads the canonical v2 artifact DAG, recomputes freshness with the same
projector that ``check_artifact_dag.py`` consumes, then derives:

1. Change roots: artifacts named via ``--changed`` plus artifacts whose
   declared identity actually drifted (invalidation events).
2. Affected set: the downstream closure over dependency edges.
3. Minimal rerun set: affected nodes in topological order, each bound to its
   declared producer and producer receipt when the DAG carries one.
4. Pending gates: the gates that consume an affected artifact role and must
   be re-evaluated after regeneration.

This is a projection, not an executor: it writes a plan JSON and the
``.harness/views/RERUN_PLAN.md`` view, runs no command, flips no Gate, and
never rewrites an artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, require_within, resolve_path, write_json  # noqa: E402
from artifact_dag_projector import project_artifact_dag  # noqa: E402
from project_layout import StateLayoutError, resolve_control_path  # noqa: E402

# Derived from v2_gate_runtime consumption: m1 requires model_contract /
# evidence_registry / artifact_dag; p2 requires frozen_results plus the
# enhanced implementation_map and model_contract checks; w1/w2 re-derive from
# the four contract roles; w2 additionally dispatches deterministic QA over
# abstract/paper/conclusion; s1 verifies the submission pdf chain.
_ROLE_GATES: dict[str, tuple[str, ...]] = {
    "artifact_dag": ("m1",),
    "model_contract": ("m1", "p1", "p2", "w1", "w2"),
    "evidence_registry": ("m1", "w1", "w2"),
    "paper_plan": ("w1", "w2"),
    "frozen_results": ("p2", "w1", "w2"),
    "implementation_map": ("p2",),
    "abstract": ("w2",),
    "paper": ("w2",),
    "conclusion": ("w2",),
    "pdf": ("w2", "s1"),
}


def _downstream_closure(roots: set[str], dependents: dict[str, set[str]]) -> set[str]:
    affected = set(roots)
    stack = list(roots)
    while stack:
        node_id = stack.pop()
        for child in dependents.get(node_id, set()):
            if child not in affected:
                affected.add(child)
                stack.append(child)
    return affected


def _topological_order(affected: set[str], node_by_id: dict[str, dict[str, Any]]) -> list[str]:
    dependencies = {
        node_id: {
            str(dep.get("artifact_id"))
            for dep in node_by_id[node_id].get("dependencies", [])
            if isinstance(dep, dict) and str(dep.get("artifact_id")) in affected
        }
        for node_id in affected
    }
    ordered: list[str] = []
    ready = sorted(node_id for node_id, deps in dependencies.items() if not deps)
    remaining = {node_id: set(deps) for node_id, deps in dependencies.items() if deps}
    while ready:
        node_id = ready.pop(0)
        ordered.append(node_id)
        for dependent, deps in sorted(remaining.items()):
            deps.discard(node_id)
        newly_ready = sorted(node_id for node_id, deps in remaining.items() if not deps)
        for node_id in newly_ready:
            remaining.pop(node_id)
        ready.extend(newly_ready)
    # A cycle among affected nodes leaves remainders; surface them instead of
    # silently dropping work from the plan.
    ordered.extend(sorted(remaining))
    return ordered


def build_rerun_plan(dag: dict[str, Any], root: Path, changed: list[str]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    if dag.get("schema_version") != "2.0":
        return {
            "ok": False,
            "errors": ["selective rerun planning requires a schema_version=2.0 artifact DAG"],
            "warnings": [],
        }
    nodes = [row for row in dag.get("nodes", []) if isinstance(row, dict)]
    node_by_id: dict[str, dict[str, Any]] = {}
    for node in nodes:
        artifact_id = node.get("artifact_id")
        if isinstance(artifact_id, str) and artifact_id:
            node_by_id[artifact_id] = node
    dependents: dict[str, set[str]] = {}
    for node_id, node in node_by_id.items():
        for dependency in node.get("dependencies", []) if isinstance(node.get("dependencies"), list) else []:
            if isinstance(dependency, dict) and isinstance(dependency.get("artifact_id"), str):
                dependents.setdefault(dependency["artifact_id"], set()).add(node_id)

    projection, projection_errors, events = project_artifact_dag(dag, project_root=root)
    errors.extend(projection_errors)
    freshness = {
        str(node.get("artifact_id")): node.get("freshness")
        for node in projection.get("nodes", [])
        if isinstance(node, dict)
    }

    roots: set[str] = set()
    for raw in changed:
        if raw in node_by_id:
            roots.add(raw)
            continue
        match = [
            node_id for node_id, node in node_by_id.items()
            if resolve_path(str(node.get("path", "")), root).resolve() == resolve_path(raw, root).resolve()
        ]
        if match:
            roots.update(match)
        else:
            errors.append(f"changed artifact is not a node of the artifact DAG: {raw}")
    for event in events:
        artifact_id = event.get("artifact_id")
        if isinstance(artifact_id, str) and event.get("invalidates_downstream") is True:
            roots.add(artifact_id)
    for node_id, status in freshness.items():
        if status == "not_run":
            roots.add(node_id)

    affected = _downstream_closure(roots, dependents)
    ordered = _topological_order(affected, node_by_id)
    rerun_steps = []
    for node_id in ordered:
        node = node_by_id.get(node_id, {})
        rerun_steps.append({
            "artifact_id": node_id,
            "role": node.get("role"),
            "path": node.get("path"),
            "producer_id": node.get("producer_id"),
            "producer_receipt_id": node.get("producer_receipt_id"),
            "freshness": freshness.get(node_id),
            "changed_root": node_id in roots,
        })
    pending_gates: dict[str, list[str]] = {}
    for node_id in sorted(affected):
        role = str(node_by_id.get(node_id, {}).get("role", ""))
        for gate in _ROLE_GATES.get(role, ()):
            pending_gates.setdefault(gate, [])
            if role not in pending_gates[gate]:
                pending_gates[gate].append(role)
    if not roots:
        warnings.append("no changed or drifted artifact was found; the rerun set is empty")
    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "run_id": dag.get("run_id"),
        "change_roots": sorted(roots),
        "affected_artifact_ids": sorted(affected),
        "rerun_steps": rerun_steps,
        "pending_gates": {gate: sorted(roles) for gate, roles in sorted(pending_gates.items())},
        "boundary": "Projection only: no command was executed, no Gate state was written, no artifact was modified.",
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Selective Rerun Plan",
        "",
        "> Projection only — nothing below was executed. No command ran, no Gate",
        "> state was written, and no artifact was modified. Regenerate this view",
        "> after every rerun.",
        "",
        f"- run: `{plan.get('run_id')}`",
        f"- change roots: {', '.join(f'`{value}`' for value in plan.get('change_roots', [])) or 'none detected'}",
        f"- affected artifacts: {len(plan.get('affected_artifact_ids', []))}",
        f"- gates to re-evaluate: {', '.join(plan.get('pending_gates', {})) or 'none'}",
        "",
    ]
    steps = plan.get("rerun_steps", [])
    if steps:
        lines.append("## Minimal rerun set (topological order)")
        lines.append("")
        for index, step in enumerate(steps, start=1):
            marker = " **(change root)**" if step.get("changed_root") else ""
            producer = step.get("producer_id") or "unknown producer"
            receipt = step.get("producer_receipt_id")
            receipt_note = f", receipt `{receipt}`" if receipt else ""
            lines.append(
                f"{index}. `{step.get('artifact_id')}` ({step.get('role')}){marker} — producer `{producer}`"
                f"{receipt_note}; regenerate `{step.get('path')}`"
            )
        lines.append("")
    pending = plan.get("pending_gates", {})
    if pending:
        lines.append("## Pending gates")
        lines.append("")
        lines.append("These gates consume an affected artifact role and must be")
        lines.append("re-derived after the rerun set above completes:")
        lines.append("")
        for gate, roles in pending.items():
            lines.append(f"- `{gate}`: {', '.join(roles)}")
        lines.append("")
    if plan.get("warnings"):
        lines.append("## Warnings")
        lines.append("")
        for warning in plan["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def plan_selective_rerun(
    root: Path,
    *,
    dag: str | None = None,
    changed: list[str] | None = None,
    output: str | None = None,
    json_output: str | None = None,
) -> dict[str, Any]:
    if dag is not None:
        dag_path = require_within(resolve_path(dag, root), root, label="--dag")
    else:
        try:
            dag_path = resolve_control_path(root, "artifact_dag.json")
        except StateLayoutError as exc:
            return {"ok": False, "errors": [str(exc)], "warnings": []}
    document = load_structured(dag_path)
    if not isinstance(document, dict):
        return {"ok": False, "errors": ["artifact DAG must be a JSON object"], "warnings": []}
    plan = build_rerun_plan(document, root, list(changed or []))
    plan["dag"] = rel_path(dag_path, root)
    if plan["ok"]:
        json_path = require_within(
            resolve_path(json_output or ".harness/views/rerun_plan.json", root), root, label="--json-output"
        )
        write_json(json_path, plan, overwrite=True)
        md_path = require_within(
            resolve_path(output or ".harness/views/RERUN_PLAN.md", root), root, label="--output"
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(render_markdown(plan), encoding="utf-8")
        plan["json"] = rel_path(json_path, root)
        plan["markdown"] = rel_path(md_path, root)
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--dag", help="artifact DAG path; defaults to the active control layout")
    parser.add_argument("--changed", action="append", default=[], help="artifact_id or path treated as changed; repeatable")
    parser.add_argument("--output", help="markdown output path; defaults to .harness/views/RERUN_PLAN.md")
    parser.add_argument("--json-output", help="json output path; defaults to .harness/views/rerun_plan.json")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    try:
        plan = plan_selective_rerun(root, dag=args.dag, changed=args.changed, output=args.output, json_output=args.json_output)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0 if plan.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
