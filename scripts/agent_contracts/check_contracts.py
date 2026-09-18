"""Check every ``agents/*/agent.yaml`` against the real Harness surface.

This is the difference between a role diagram and an auditable multi-agent
system: a contract that names a tool, artifact role, output schema, reference
file, or Gate that does not exist in this repository is an error here, not a
plausible-looking document.

The check grants no authority and writes no project state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent_contracts import policy as policy_module  # noqa: E402
from agent_contracts.contract import (  # noqa: E402
    AGENT_CONTRACTS_DIR,
    AGENT_CONTRACT_SCHEMA,
    FORBIDDEN_ACTION_FABRICATION,
    FORBIDDEN_ACTION_FLOOR,
    SAFE_INVARIANTS,
    agent_tool_surface,
    artifact_roles,
    cli_command_surface,
    gate_names,
    load_contract,
    mcp_mutating_tools,
    repo_path,
    schema_names,
    stale_truth_mutating_names,
    truth_mutating_commands,
)

# The control plane stays Harness-owned: no agent may declare write authority
# over it, because that is exactly where a forged Gate PASS would live.
CONTROL_PLANE_ROLES = frozenset({
    "run_manifest", "competition_profile", "artifact_dag", "run_index",
})
# Author-plane roles the reviewer must never touch: reading them is the
# bundle's job, changing them is the writer's.
AUTHOR_ROLES = frozenset({
    "model_contract", "paper", "paper_plan", "abstract", "conclusion",
    "paper_section", "writer_package", "figure", "table",
})
ALL_STAGES = ("S0", "M1", "P1", "P2", "W1", "W2", "S1", "F1")
# SKILL.md principle 12: "no AI was used" is a human declaration. An agent that
# can confirm it can launder an unrecorded model call, so no contract holds it.
HUMAN_ONLY_COMMANDS = frozenset({"ai confirm-none"})


def _schema_errors(contract: Mapping[str, Any]) -> list[str]:
    import jsonschema  # noqa: PLC0415 - already a Harness dependency

    schema = json.loads(AGENT_CONTRACT_SCHEMA.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{error.json_path}: {error.message}"
        for error in sorted(validator.iter_errors(contract), key=lambda row: str(row.json_path))
    ]


def _forbidden_floor() -> set[str]:
    return {FORBIDDEN_ACTION_FLOOR[name] for name in SAFE_INVARIANTS} | set(FORBIDDEN_ACTION_FABRICATION)


def check_contract(
    path: Path,
    *,
    surface: set[str],
    roles: set[str],
    schemas: set[str],
    gates: set[str],
    mutating: set[str],
) -> dict[str, Any]:
    name = path.parent.name
    report: dict[str, Any] = {
        "name": name,
        "path": path.relative_to(path.parents[2]).as_posix(),
        "errors": [],
        "stage_authority": [],
    }
    errors: list[str] = report["errors"]
    try:
        contract = load_contract(path)
    except (OSError, ValueError) as exc:
        errors.append(f"cannot load contract: {exc}")
        return report

    errors.extend(_schema_errors(contract))
    if contract.get("name") != name:
        errors.append(f"contract name {contract.get('name')!r} must match directory {name!r}")

    tools = [str(item) for item in contract.get("allowed_tools", []) if isinstance(item, str)]
    for tool in sorted(set(tools) - surface):
        errors.append(f"allowed tool is not a harness command: {tool}")
    for tool in sorted(set(tools) & HUMAN_ONLY_COMMANDS):
        errors.append(f"{tool} is a human-only declaration and may not be an agent tool")

    artifacts = contract.get("allowed_artifacts") or {}
    read = {str(item) for item in artifacts.get("read", []) if isinstance(item, str)}
    write = {str(item) for item in artifacts.get("write", []) if isinstance(item, str)}
    for role in sorted((read | write) - roles):
        errors.append(f"unknown artifact role: {role}")
    for role in sorted(write & CONTROL_PLANE_ROLES):
        errors.append(f"{name} may not write control-plane role {role}")

    for output in contract.get("outputs", []) or []:
        if not isinstance(output, dict):
            continue
        persists = output.get("persists") is True
        schema = output.get("schema")
        if persists and not isinstance(schema, str):
            errors.append(f"output {output.get('name')!r} persists but names no schema")
        elif not persists and schema is not None:
            errors.append(f"output {output.get('name')!r} does not persist but names a schema")
        elif isinstance(schema, str) and schema not in schemas:
            errors.append(f"output schema does not exist: {schema}")

    for reference in contract.get("references", []) or []:
        if not repo_path(str(reference)).is_file():
            errors.append(f"reference file does not exist: {reference}")

    missing = sorted(_forbidden_floor() - {str(item) for item in contract.get("forbidden_actions", [])})
    for action in missing:
        errors.append(f"missing mandatory prohibition: {action}")

    stages = {str(item) for item in contract.get("stages", []) if isinstance(item, str)}
    for stage in sorted(stages - set(ALL_STAGES)):
        errors.append(f"unknown stage: {stage}")
    if name == "orchestrator":
        for tool in sorted(set(tools) & mutating):
            errors.append(f"orchestrator may not hold a truth-mutating command: {tool}")
        if write:
            errors.append("orchestrator may not write any artifact")
    else:
        for stage in sorted(stages - gates - {"S0", "F1"}):
            errors.append(f"stage has no Gate to consume: {stage}")
    if name == "reviewer":
        if not {"review", "mcp:request_review"} & set(tools):
            errors.append("reviewer must execute through the harness review command")
        for role in sorted(write & AUTHOR_ROLES):
            errors.append(f"reviewer may not write author-plane role {role}")
        if set(tools) & mutating - {"review", "mcp:request_review"}:
            errors.append("reviewer may not hold any truth-mutating command except the review plane")

    report["stage_authority"] = sorted(stages)
    report["writes"] = sorted(write)
    report["reads"] = sorted(read)
    return report


def check_all(contracts_dir: Path = AGENT_CONTRACTS_DIR, *, agents_dir: Path | None = None) -> dict[str, Any]:
    surface = agent_tool_surface()
    mutating = truth_mutating_commands(cli_command_surface()) | mcp_mutating_tools()
    roles = artifact_roles()
    schemas = schema_names()
    gates = gate_names()
    paths = sorted(contracts_dir.glob("*/agent.yaml"))
    reports = [
        check_contract(
            path, surface=surface, roles=roles, schemas=schemas, gates=gates, mutating=mutating,
        )
        for path in paths
    ]

    ownership: dict[str, list[str]] = {}
    stage_owner: dict[str, list[str]] = {}
    for row in reports:
        for role in row.get("writes", []):
            ownership.setdefault(role, []).append(row["name"])
        for stage in row["stage_authority"]:
            if row["name"] == "orchestrator":
                continue
            stage_owner.setdefault(stage, []).append(row["name"])

    errors = [f"{row['name']}: {message}" for row in reports for message in row["errors"]]
    errors.extend(
        f"artifact role {role} has {len(owners)} writers ({owners}); one owner per role"
        for role, owners in sorted(ownership.items()) if len(owners) > 1
    )
    errors.extend(
        f"stage {stage} has {len(owners)} owners ({owners}); dispatch must be unambiguous"
        for stage, owners in sorted(stage_owner.items()) if len(owners) > 1
    )
    uncovered = sorted(set(ALL_STAGES) - set(stage_owner))
    if uncovered:
        errors.append(f"stages with no owning agent: {uncovered}")
    stale = stale_truth_mutating_names(surface)
    if stale:
        errors.append(f"mutating-command list names missing commands: {sorted(stale)}")
    if not reports:
        errors.append("no agent contracts found")

    # The compiled policy is what the MCP boundary enforces; a contract that
    # cannot compile is a scope claim the runtime would have to guess at.
    policy_errors: list[str] = []
    policies: dict[str, Any] = {}
    try:
        policies = policy_module.compile_all(agents_dir=agents_dir or contracts_dir)
    except policy_module.AgentPolicyError as exc:
        policy_errors = exc.errors
    errors.extend(f"policy: {message}" for message in policy_errors)

    return {
        "ok": not errors,
        "errors": errors,
        "agents": reports,
        "policies": {
            role: {
                "cli_commands": row["cli_commands"],
                "mcp_tools": row["mcp_tools"],
                "mutating_tools": row["mutating_tools"],
            }
            for role, row in sorted(policies.items())
        },
        "ground_truth": {
            "agent_tools": len(surface),
            "truth_mutating_commands": sorted(mutating),
            "schemas": len(schemas),
            "artifact_roles": len(roles),
            "gates": sorted(gates),
            "contracts": len(reports),
        },
        "boundary": (
            "Contract scope check only: it grants no Gate authority, executes no model, "
            "and writes no project state. Gate PASS remains a recomputed fact."
        ),
    }


def render_human(result: Mapping[str, Any]) -> str:
    lines = [f"agent contracts: {'PASS' if result['ok'] else 'FAIL'} ({result['ground_truth']['contracts']} roles)"]
    for row in result["agents"]:
        status = "ok" if not row["errors"] else f"{len(row['errors'])} error(s)"
        lines.append(f"  {row['name']:<16} stages={','.join(row['stage_authority']) or '-'} writes={','.join(row.get('writes', [])) or '-'} {status}")
        for message in row["errors"]:
            lines.append(f"    - {message}")
    for message in result["errors"]:
        if ": " in message and not any(message.startswith(row["name"] + ": ") for row in result["agents"]):
            lines.append(f"  {message}")
    lines.append(f"  boundary: {result['boundary']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)
    result = check_all()
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render_human(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
