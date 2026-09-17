"""Ground truth the Agent contracts are checked against.

Every function here reads the live Harness surface: the real argparse tree, the
real Gate tuple, the real artifact-role vocabulary and the real safety
invariants.  ``agents/*/agent.yaml`` is therefore only a claim about scope; if
it names a tool, role, schema or Gate that does not exist, ``check_contracts``
fails instead of shipping a fictional capability.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = SCRIPTS_DIR.parent
SCHEMA_DIR = REPO_ROOT / "schemas"
AGENT_CONTRACT_SCHEMA = SCHEMA_DIR / "agent_contract.schema.json"
AGENT_CONTRACTS_DIR = REPO_ROOT / "agents"


def repo_path(relative: str) -> Path:
    """Resolve a path a contract names relative to the repository root."""

    return REPO_ROOT / relative


if str(REPO_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))

from profiles.capabilities import SAFE_INVARIANTS  # noqa: E402
from qa.plan_selective_rerun import _ROLE_GATES  # noqa: E402
from qa.review_evidence import BUNDLE_ALLOW_ROLES  # noqa: E402


def cli_command_surface() -> set[str]:
    """Every ``harness`` command path an agent could actually invoke."""

    from harness import build_parser  # noqa: PLC0415 - imported late to avoid cycles

    found: set[str] = set()

    def walk(parser: argparse.ArgumentParser, prefix: tuple[str, ...]) -> None:
        for action in parser._actions:  # noqa: SLF001 - introspecting our own parser
            if not isinstance(action, argparse._SubParsersAction):  # noqa: SLF001
                continue
            for name, subparser in action.choices.items():
                path = " ".join((*prefix, name))
                found.add(path)
                walk(subparser, (*prefix, name))

    walk(build_parser(), ())
    return found


def gate_names() -> set[str]:
    from harness import GATE_ORDER  # noqa: PLC0415

    return {str(name).upper() for name in GATE_ORDER}


def mcp_tool_surface() -> set[str]:
    """``mcp:<tool>`` names the MCP server actually advertises by default."""

    import mcp_server  # noqa: PLC0415

    return {f"mcp:{name}" for name in mcp_server.tool_surface()}


def mcp_mutating_tools() -> set[str]:
    """Mutating MCP tools, named in the same ``mcp:`` form contracts use."""

    import mcp_server  # noqa: PLC0415

    return {f"mcp:{name}" for name in sorted(mcp_server.MUTATING_TOOL_NAMES)}


def agent_tool_surface() -> set[str]:
    """Everything a contract may name: CLI command paths and MCP tools."""

    return cli_command_surface() | mcp_tool_surface() | mcp_mutating_tools()


def artifact_roles() -> set[str]:
    """The role vocabulary the Harness itself already recognizes."""

    return set(_ROLE_GATES) | set(BUNDLE_ALLOW_ROLES) | {
        "review_report", "run_manifest", "competition_profile", "artifact_dag", "run_index",
        # Receipts are not DAG nodes, but they are first-class generated
        # evidence: they carry a schema, land in receipts/, and every DAG node
        # that was really produced points at one through producer_receipt_id.
        "command_receipt",
    }


def schema_names() -> set[str]:
    return {path.name for path in SCHEMA_DIR.glob("*.schema.json")}


# Each non-bypassable safety invariant must have a matching prohibition in
# every contract.  Adding an invariant without a prohibition fails the check.
FORBIDDEN_ACTION_FLOOR: Mapping[str, str] = {
    "require_contest_safety": "weaken_contest_safety",
    "require_human_checkpoints": "self_approve_human_checkpoint",
    "require_independent_validation": "self_validate_as_independent",
    "require_result_freeze": "promote_unfrozen_result",
    "require_submission_immutability": "rewrite_frozen_artifact",
}

# Integrity rules from SKILL.md principle 5: these are never a capability.
FORBIDDEN_ACTION_FABRICATION = (
    "forge_gate_status",
    "forge_receipt_or_hash",
    "forge_review_verdict",
)

# Commands that write execution facts, freeze, review evidence, or the AI
# ledger.  Everything else can create author files or derived views but never
# Gate/receipt/hash/freeze truth, so no second table is needed: the authority
# boundary is defined by this list plus the group prefix that reaches it.
TRUTH_MUTATING_LEAVES = frozenset({
    "init", "execute", "run", "freeze", "review", "migrate",
    "ai confirm-none", "ai record", "ai verify",
    "authoring migrate", "submit receipt",
})


def truth_mutating_commands(surface: set[str]) -> set[str]:
    """Truth-mutating leaves plus any command group that can reach one."""

    mutating = set(TRUTH_MUTATING_LEAVES)
    for command in surface:
        if any(leaf == command or leaf.startswith(f"{command} ") for leaf in TRUTH_MUTATING_LEAVES):
            mutating.add(command)
    return mutating & surface


def stale_truth_mutating_names(surface: set[str]) -> set[str]:
    """Declared mutating commands that no longer exist: a renamed CLI fails here."""

    return set(TRUTH_MUTATING_LEAVES) - surface


def load_contract(path: Path) -> dict[str, Any]:
    import yaml  # noqa: PLC0415 - optional dependency, already required by the Harness

    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"agent contract must be a mapping: {path}")
    return value


__all__ = [
    "AGENT_CONTRACTS_DIR",
    "AGENT_CONTRACT_SCHEMA",
    "FORBIDDEN_ACTION_FABRICATION",
    "FORBIDDEN_ACTION_FLOOR",
    "SAFE_INVARIANTS",
    "SCRIPTS_DIR",
    "TRUTH_MUTATING_LEAVES",
    "artifact_roles",
    "cli_command_surface",
    "gate_names",
    "load_contract",
    "repo_path",
    "schema_names",
    "stale_truth_mutating_names",
    "truth_mutating_commands",
]
