"""Verifier declarations: the contract behind every gate-bound check.

A declaration is metadata about a check the harness already ships — it never
replaces the checker's verdict. See ``references/contracts/verifier_registry.md``.
"""

from __future__ import annotations

from .registry import (
    CONSUMES,
    DEFAULT_DECLARATIONS_DIR,
    GATES,
    VerifierContractError,
    load_registry,
    registry_for_gate,
)

__all__ = [
    "CONSUMES",
    "DEFAULT_DECLARATIONS_DIR",
    "GATES",
    "VerifierContractError",
    "load_registry",
    "registry_for_gate",
]