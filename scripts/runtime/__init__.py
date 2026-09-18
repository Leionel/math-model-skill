"""In-process read-only runtime API for the v2 control plane.

The CLI, the MCP façade and this module must never disagree about the same
project state. Each read delegates to the module that owns the logic
(``harness_status`` for state and artifact views, ``check_gates`` for a gate
report) and returns the exact payload the CLI prints plus the exit code it
would return, so parity is assertable mechanically
(``tests/test_runtime_api.py``). Consumers use this instead of spawning a
harness subprocess or re-implementing a projection.
"""

from __future__ import annotations

from .read_api import RuntimeView, check_gate, get_state, verify_artifact

__all__ = ["RuntimeView", "check_gate", "get_state", "verify_artifact"]