"""Capability composition: which verifiers, schemas, roles and gates a profile carries.

Named ``capability_composition`` rather than ``capabilities`` because
``scripts/profiles/capabilities.py`` is imported bare by ``profile_engine`` and
a same-named package would shadow it. See
``references/contracts/capability_composition.md``.
"""

from __future__ import annotations

from .composition import (
    COMPOSITIONS_PATH,
    DECLARATIONS_DIR,
    CapabilityCompositionError,
    compose,
    load_compositions,
    load_declarations,
    profile_ids,
    resolve_capabilities,
)

__all__ = [
    "COMPOSITIONS_PATH",
    "DECLARATIONS_DIR",
    "CapabilityCompositionError",
    "compose",
    "load_compositions",
    "load_declarations",
    "profile_ids",
    "resolve_capabilities",
]