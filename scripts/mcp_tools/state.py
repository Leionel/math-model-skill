"""Computed MCP tools: run state and Gate decisions.

These are the only MCP handlers that reshape Harness output instead of passing a
child's stdout through. Even so, none of them compute a verdict of their own:
each one calls the existing deterministic entry point and projects what it
returned. ``get_run_state`` and ``check_gate`` therefore cannot disagree with
``harness status`` or ``harness check`` — they are the same computation.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

_GATE_ORDER = ("m1", "p1", "p2", "w1", "w2", "s1")


def _harness_json(module: Mapping[str, Any], argv: list[str], root: Path) -> tuple[dict[str, Any], int]:
    """Reuse the server's child-process seam so timeouts and redaction stay one place."""

    exit_code, stdout, _stderr = module["run_harness"]([sys.executable, *argv], root)
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = {"ok": False, "errors": [stdout or "harness returned no JSON"]}
    return payload, exit_code


def get_run_state(root: Path, arguments: Mapping[str, Any], module: Mapping[str, Any]) -> dict[str, Any]:
    """Project the recomputed run state into the shape an agent plans with."""

    payload, exit_code = _harness_json(module, [
        str(module["HARNESS_CLI"]), "status", "--project", str(root), "--json",
    ], root)
    blocked = payload.get("first_blocked_gate")
    gates = payload.get("gates") or {}
    blockers = [
        {
            "gate": str(row.get("id")),
            "message": str(row.get("message")),
            "next_action": str(row.get("next_action")),
        }
        for row in (payload.get("failures_summary") or {}).get("items", [])
        if isinstance(row, Mapping)
    ]
    pending = [str(row) for row in payload.get("pending_human_checkpoints") or []]
    stale = [str(row) for row in payload.get("stale_artifacts") or []]
    stage = str(payload.get("stage") or "")
    if blocked:
        next_actions = [row["next_action"] for row in blockers if row["gate"] == str(blocked)][:5]
        gate_status = "BLOCKED"
    elif pending:
        next_actions = [f"a human must confirm {name} before the Gate can advance" for name in pending]
        gate_status = "PENDING_HUMAN"
    else:
        next_actions = [str(payload.get("next_action") or "no next action is derivable")]
        gate_status = "READY"
    return {
        "run_id": payload.get("run_id"),
        "stage": stage,
        "preset": payload.get("preset"),
        "gate_status": gate_status,
        "first_blocked_gate": blocked,
        "gates_passed": sorted(name for name, row in gates.items() if isinstance(row, Mapping) and row.get("ok")),
        "blockers": blockers,
        "pending_human_checkpoints": pending,
        "stale_artifacts": stale,
        "next_actions": [row for row in next_actions if row],
        "source": "harness status --json (recomputed; no cached Gate state)",
        "status_exit_code": exit_code,
    }


def check_gate(root: Path, arguments: Mapping[str, Any], module: Mapping[str, Any]) -> dict[str, Any]:
    """Answer the only question an agent should ask before advancing."""

    gate = str(arguments.get("gate") or "")
    argv = [
        str(module["HARNESS_CLI"]), "check", gate.upper(),
        "--project", str(root), "--json",
    ]
    if arguments.get("strict") is True:
        argv.append("--strict")
    payload, exit_code = _harness_json(module, argv, root)
    errors = [str(row) for row in payload.get("errors") or []]
    return {
        "gate": gate,
        "allowed": exit_code == 0 and payload.get("ok") is True,
        "reason": "gate_recomputed_pass" if exit_code == 0 and payload.get("ok") is True else (errors[0] if errors else "gate_report_unavailable"),
        "blockers": errors[:10],
        "warnings": [str(row) for row in payload.get("warnings") or []][:10],
        "note": "verdict is recomputed from files on disk; it is not read from manifest Gate state",
    }


def gate_order(module: Mapping[str, Any]) -> list[str]:
    return list(_GATE_ORDER)


TOOLS: dict[str, dict[str, Any]] = {
    "get_run_state": {
        "description": (
            "Recomputed run state for one project: stage, Gate readiness, blockers with the "
            "repair action, pending human checkpoints and stale artifacts. Read-only."
        ),
        "properties": {},
        "required": [],
        "handler": get_run_state,
        "mutating": False,
    },
    "check_gate": {
        "description": (
            "Ask whether a specific Gate currently passes, and why not. The answer is the "
            "Harness's own recomputed verdict, never a cached status."
        ),
        "properties": {
            "gate": {"type": "string", "enum": [name.upper() for name in _GATE_ORDER]},
            "strict": {"type": "boolean"},
        },
        "required": ["gate"],
        "handler": check_gate,
        "mutating": False,
    },
}

__all__ = ["TOOLS", "check_gate", "gate_order", "get_run_state"]
