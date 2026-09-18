"""Compile an agent contract into the runtime capability policy the MCP boundary enforces.

``agents/*/agent.yaml`` is a claim about scope; :func:`compile_policy` turns that
claim into machine-readable permissions and refuses to compile a contract that
names a tool or artifact role the live Harness does not have. The facade-tool
mapping is derived from the server's own argv builders, so a renamed command path
shows up as a policy error instead of a silent drift.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
for _directory in (SCRIPTS_DIR, SCRIPTS_DIR / "agent_contracts"):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))

import mcp_server  # noqa: E402
from contract import agent_tool_surface, artifact_roles, cli_command_surface, load_contract  # noqa: E402

AGENTS_DIR = REPO_ROOT / "agents"

# Stub arguments let a builder run far enough to reveal its command path. Only
# builders whose arguments are required appear here.
_BUILDER_STUBS: dict[str, dict[str, Any]] = {
    "research_context": {"stage": "model"},
    "validate_current_stage": {"gate": mcp_server.GATES[0]},
}


class AgentPolicyError(ValueError):
    """Every policy error for a set of roles, sorted."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = sorted(errors)
        super().__init__("; ".join(self.errors))


def facade_command_path(tool_name: str) -> str | None:
    """The CLI command path a facade tool dispatches to, or None when unknown."""

    builder = mcp_server.TOOL_BUILDERS.get(tool_name)
    if builder is None:
        return None
    try:
        argv = builder(_BUILDER_STUBS.get(tool_name, {}))
    except Exception:  # noqa: BLE001 - an unrunnable builder simply has no derivable path
        return None
    # The command path is the longest token prefix that exists in the real CLI
    # surface, so ["check", "M1"] resolves to "check" and ["paper", "plan"] to
    # "paper plan" without a hand-maintained table.
    surface = cli_command_surface()
    candidate = ""
    matched: str | None = None
    for token in argv:
        if str(token).startswith("-"):
            break
        candidate = f"{candidate} {token}".strip()
        if candidate not in surface:
            break
        matched = candidate
    return matched


def contract_paths(agents_dir: Path | str | None = None) -> dict[str, Path]:
    directory = Path(agents_dir).resolve() if agents_dir is not None else AGENTS_DIR
    return {
        path.parent.name: path
        for path in sorted(directory.glob("*/agent.yaml"))
    }


def compile_policy(role: str, *, agents_dir: Path | str | None = None) -> dict[str, Any]:
    """Return the machine policy for one role, or raise with every error."""

    paths = contract_paths(agents_dir)
    path = paths.get(role)
    if path is None:
        raise AgentPolicyError([f"unknown agent role: {role}"])
    contract = load_contract(path)
    surface = agent_tool_surface()
    roles = artifact_roles()
    errors: list[str] = []
    declared = [str(item) for item in contract.get("allowed_tools", []) if isinstance(item, str)]
    for tool in sorted(set(declared) - surface):
        errors.append(f"{role}: contract names a tool the Harness does not have: {tool}")
    declared_mcp = sorted(item[len("mcp:"):] for item in declared if item.startswith("mcp:"))
    facade_paths = {
        name: facade_command_path(name)
        for name in sorted(mcp_server.TOOL_BUILDERS)
    }
    allowed_mcp = set(declared_mcp)
    for name, command_path in facade_paths.items():
        if command_path is not None and command_path in declared:
            allowed_mcp.add(name)
    artifacts = contract.get("allowed_artifacts")
    read = [str(item) for item in artifacts.get("read", [])] if isinstance(artifacts, Mapping) else []
    write = [str(item) for item in artifacts.get("write", [])] if isinstance(artifacts, Mapping) else []
    for role_name, values in (("read", read), ("write", write)):
        for artifact in sorted(set(values) - roles):
            errors.append(f"{role}: contract names an unknown artifact role to {role_name}: {artifact}")
    if errors:
        raise AgentPolicyError(errors)
    mutating = sorted(name for name in allowed_mcp if name in mcp_server.MUTATING_TOOL_NAMES)
    return {
        "schema_version": "1.0",
        "role": role,
        "contract": path.relative_to(path.parents[1]).as_posix(),
        "stages": [str(stage) for stage in contract.get("stages", [])],
        "cli_commands": sorted(item for item in declared if not item.startswith("mcp:")),
        "mcp_tools": sorted(allowed_mcp),
        "declared_mcp_tools": declared_mcp,
        "mutating_tools": mutating,
        "artifact_read": sorted(read),
        "artifact_write": sorted(write),
        "forbidden_actions": sorted(str(item) for item in contract.get("forbidden_actions", [])),
    }


def compile_all(*, agents_dir: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Compile every role; a broken contract fails the whole set."""

    policies: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for role in sorted(contract_paths(agents_dir)):
        try:
            policies[role] = compile_policy(role, agents_dir=agents_dir)
        except AgentPolicyError as exc:
            errors.extend(exc.errors)
    if errors:
        raise AgentPolicyError(errors)
    return policies


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", help="compile one role; defaults to every role")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.role:
            payload: Any = compile_policy(args.role)
        else:
            payload = compile_all()
    except AgentPolicyError as exc:
        print(json.dumps({"ok": False, "errors": exc.errors}, ensure_ascii=False) if args.json else "\n".join(exc.errors))
        return 1
    print(json.dumps(payload, ensure_ascii=False, indent=2) if args.json else json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())