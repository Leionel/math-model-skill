"""Computed MCP tool handlers, kept out of the transport module.

``mcp_server.py`` owns framing, root allow-listing, timeouts and redaction.
This package owns what each tool actually answers. Nothing here recomputes a
verdict from scratch: the handlers call the same deterministic Harness entry
points that the CLI does, so an MCP answer and a ``harness`` answer cannot drift.
"""

from __future__ import annotations

from typing import Any

from . import artifacts, review, state

COMPUTED_TOOLS: dict[str, dict[str, Any]] = {**state.TOOLS, **artifacts.TOOLS, **review.TOOLS}


def tool_names(include_mutating: bool = False) -> list[str]:
    return sorted(
        name for name, spec in COMPUTED_TOOLS.items()
        if include_mutating or not spec.get("mutating")
    )


__all__ = ["COMPUTED_TOOLS", "artifacts", "review", "state", "tool_names"]
