"""Record how much of a run an agent was allowed to drive unattended.

A mode is a declaration about agent behaviour made outside the Harness, so the
Harness cannot observe whether it was honoured.  What it can do is keep the
declaration in the control plane with who set it and when, so a run driven
unattended end to end cannot later be presented as one a human supervised, and
a mode flipped mid-run leaves a record behind.

The mode never relaxes a Gate.  A Gate that requires a human checkpoint counts
only rows whose ``actor_class`` is human, in every mode.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_structured, write_json_atomic  # noqa: E402
from project_layout import resolve_manifest_path  # noqa: E402

OPERATOR_MODES = ("auto", "accept-edits")


def declared_mode(manifest: Any) -> str | None:
    """The mode a run declared for itself, or None when it never said."""

    control = manifest.get("control") if isinstance(manifest, dict) else None
    if not isinstance(control, dict):
        return None
    value = control.get("operator_mode")
    return value if value in OPERATOR_MODES else None


def set_operator_mode(root: Path, mode: str, *, set_by: str) -> dict[str, Any]:
    if mode not in OPERATOR_MODES:
        raise ValueError("operator mode must be auto or accept-edits")
    if not set_by.strip():
        raise ValueError(
            "--set-by must name who changed the mode; it is recorded as a declaration, not a verified identity"
        )
    manifest_path = resolve_manifest_path(root)
    manifest = load_structured(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("run manifest must be an object")
    if manifest.get("schema_version") != "2.0":
        raise ValueError("mode requires a v2 run manifest")
    control = manifest.get("control")
    if not isinstance(control, dict):
        control = {}
        manifest["control"] = control
    history = control.setdefault("operator_mode_history", [])
    if not isinstance(history, list):
        raise ValueError("run_manifest.control.operator_mode_history must be an array")
    previous = control.get("operator_mode")
    recorded_at = datetime.now(timezone.utc).isoformat()
    history.append({"mode": mode, "set_by": set_by.strip(), "set_at": recorded_at})
    control["operator_mode"] = mode
    write_json_atomic(manifest_path, manifest)
    return {
        "operator_mode": mode,
        "previous_mode": previous,
        "set_by": set_by.strip(),
        "set_at": recorded_at,
        "mode_changes": len(history),
    }
