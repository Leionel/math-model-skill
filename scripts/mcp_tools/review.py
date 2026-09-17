"""Review MCP tool: opt-in, and the backend is never an agent argument.

``harness review`` is the one read-adjacent verb that writes evidence, so the
tool is disabled unless the server operator sets
``MATH_HARNESS_ALLOW_REVIEW_TOOL=1``. The reviewer command itself comes from
``MATH_HARNESS_REVIEW_BACKEND`` on the *server*, never from tool arguments: an
agent that could pass an arbitrary argv would have just gained remote code
execution through a tool named "request review".
"""

from __future__ import annotations

import json
import os
import shlex
import sys
from pathlib import Path
from typing import Any, Mapping

ALLOW_ENV = "MATH_HARNESS_ALLOW_REVIEW_TOOL"
BACKEND_ENV = "MATH_HARNESS_REVIEW_BACKEND"


def review_backend(env: Mapping[str, str] | None = None) -> list[str]:
    source = os.environ if env is None else env
    raw = source.get(BACKEND_ENV, "").strip()
    return shlex.split(raw) if raw else []


def request_review(root: Path, arguments: Mapping[str, Any], module: Mapping[str, Any]) -> dict[str, Any]:
    source = {**os.environ, **dict(module.get("env") or {})}
    if source.get(ALLOW_ENV) != "1":
        raise module["ToolCallError"](
            f"review is disabled: the server must set {ALLOW_ENV}=1, and the reviewer command "
            f"comes from {BACKEND_ENV} on the server, never from tool arguments"
        )
    argv = [sys.executable, str(module["HARNESS_CLI"]), "review", "--project", str(root), "--json"]
    if arguments.get("fresh") is True:
        argv.append("--fresh")
    if arguments.get("perspective") == "semantic":
        argv.append("--semantic")
    elif arguments.get("perspective") == "judge":
        argv.append("--judge")
    backend = review_backend(source)
    if backend:
        argv.extend(["--backend-cmd", " ".join(backend)])
        declared = source.get("MATH_HARNESS_REVIEW_BACKEND_KIND")
        if declared in ("ai", "non_ai"):
            # The tool identity is operator-declared here because the Harness
            # refuses to infer whether a command invokes a model.
            argv.extend(["--backend-kind", declared])
            if declared == "ai":
                argv.extend([
                    "--ai-tool-name", source.get("MATH_HARNESS_REVIEW_TOOL_NAME", "mcp-configured"),
                    "--ai-model", source.get("MATH_HARNESS_REVIEW_MODEL", "unspecified"),
                    "--ai-provider", source.get("MATH_HARNESS_REVIEW_PROVIDER", "unspecified"),
                ])
    exit_code, stdout, stderr = module["run_harness"](argv, root)
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        payload = {"errors": [stdout or stderr or "review returned no JSON"]}
    perspectives = (payload.get("review") or {}).get("perspectives") or {}
    return {
        "status": "passed" if exit_code == 0 else ("blocked" if payload.get("errors") else "pending"),
        "exit_code": exit_code,
        "perspectives": {
            str(name): {
                "executed": bool(row.get("executed")),
                "verdict": row.get("verdict"),
                "independence_level": row.get("independence_level"),
                "freshness": row.get("freshness"),
                "severity_counts": row.get("severity_counts"),
            }
            for name, row in perspectives.items()
            if isinstance(row, Mapping)
        },
        "errors": [str(row) for row in payload.get("errors") or []][:10],
        "w2_preview": payload.get("w2_preview"),
        "backend_configured_on_server": bool(backend),
        "note": "reports are written by the Harness under reports/review/ as generated evidence",
    }


TOOLS: dict[str, dict[str, Any]] = {
    "request_review": {
        "description": (
            "Run the review plane for one project: deterministic QA first, then the required "
            "perspectives against the allow-listed bundle. Opt-in; the reviewer command is "
            "server-configured and cannot be supplied by the caller."
        ),
        "properties": {
            "fresh": {"type": "boolean", "description": "Require fresh-context (L1) execution."},
            "perspective": {"type": "string", "enum": ["semantic", "judge"]},
        },
        "required": [],
        "handler": request_review,
        "mutating": True,
    },
}

__all__ = ["ALLOW_ENV", "BACKEND_ENV", "TOOLS", "request_review", "review_backend"]
