"""Resolve the active location of small v2 control documents.

The authoring surface deliberately lives at the project root.  Control files
started there for v2 compatibility, while a later explicit migration may move
only those four files into ``.harness/state``.  This module is the one place
that chooses between the layouts so a partially completed migration cannot be
silently treated as a current project.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from _common import load_structured, resolve_path, write_json_atomic


CONTROL_FILENAMES = (
    "competition_profile.json",
    "run_manifest.json",
    "artifact_dag.json",
    "run_index.json",
)
HIDDEN_STATE_RELATIVE = Path(".harness") / "state"
LAYOUT_MARKER_RELATIVE = Path(".harness") / "state_layout.json"
LAYOUT_SCHEMA_VERSION = "1.0"


class StateLayoutError(ValueError):
    """The project has no unambiguous active control-document layout."""


def _root(root: Path | str) -> Path:
    return Path(root).resolve()


def _require_control_name(name: str) -> None:
    if name not in CONTROL_FILENAMES:
        raise StateLayoutError(f"unknown control document: {name}")


def flat_control_path(root: Path | str, name: str) -> Path:
    """Return a root-level control path without asserting it is active."""

    _require_control_name(name)
    return _root(root) / name


def hidden_state_dir(root: Path | str) -> Path:
    return _root(root) / HIDDEN_STATE_RELATIVE


def hidden_control_path(root: Path | str, name: str) -> Path:
    """Return a hidden control path without asserting it is active."""

    _require_control_name(name)
    return hidden_state_dir(root) / name


def layout_marker_path(root: Path | str) -> Path:
    return _root(root) / LAYOUT_MARKER_RELATIVE


def control_paths(root: Path | str, layout: str) -> dict[str, Path]:
    """Return all expected control paths for a named layout."""

    if layout == "flat":
        return {name: flat_control_path(root, name) for name in CONTROL_FILENAMES}
    if layout == "hidden":
        return {name: hidden_control_path(root, name) for name in CONTROL_FILENAMES}
    raise StateLayoutError("layout must be flat or hidden")


def existing_control_paths(root: Path | str) -> dict[str, list[Path]]:
    """List known control files without selecting a current layout."""

    return {
        layout: [path for path in control_paths(root, layout).values() if path.is_file()]
        for layout in ("flat", "hidden")
    }


def _read_hidden_marker(root: Path) -> Mapping[str, Any] | None:
    marker = layout_marker_path(root)
    if not marker.exists():
        return None
    if not marker.is_file():
        raise StateLayoutError(f"state layout marker is not a file: {marker}")
    value = load_structured(marker)
    if not isinstance(value, Mapping):
        raise StateLayoutError("state layout marker must be an object")
    required = {
        "schema_version": LAYOUT_SCHEMA_VERSION,
        "active_layout": "hidden",
        "control_directory": HIDDEN_STATE_RELATIVE.as_posix(),
    }
    for key, expected in required.items():
        if value.get(key) != expected:
            raise StateLayoutError(f"state layout marker has invalid {key!r}")
    files = value.get("control_files")
    if not isinstance(files, list) or tuple(files) != CONTROL_FILENAMES:
        raise StateLayoutError("state layout marker must declare the four v2 control files in canonical order")
    return value


def active_state_layout(root: Path | str) -> str:
    """Return ``flat`` or ``hidden`` only when the project is unambiguous."""

    resolved_root = _root(root)
    marker = _read_hidden_marker(resolved_root)
    existing = existing_control_paths(resolved_root)
    flat = existing["flat"]
    hidden = existing["hidden"]
    if marker is not None:
        if flat:
            names = ", ".join(path.name for path in flat)
            raise StateLayoutError(
                "active hidden state layout conflicts with root-level control files "
                f"({names}); repair the incomplete migration before continuing"
            )
        expected = control_paths(resolved_root, "hidden")
        missing = [name for name, path in expected.items() if not path.is_file()]
        if missing:
            raise StateLayoutError(
                "active hidden state layout is incomplete; missing " + ", ".join(missing)
            )
        return "hidden"
    if hidden:
        names = ", ".join(path.name for path in hidden)
        raise StateLayoutError(
            "hidden control files exist without an active state-layout marker "
            f"({names}); finish or roll back the migration before continuing"
        )
    return "flat"


def resolve_control_path(root: Path | str, name: str) -> Path:
    """Resolve one active control path while rejecting layout ambiguity."""

    layout = active_state_layout(root)
    return control_paths(root, layout)[name]


def resolve_manifest_path(root: Path | str, raw: str | None = None) -> Path:
    """Resolve an explicit manifest, or the manifest in the active layout."""

    resolved_root = _root(root)
    if raw:
        return resolve_path(raw, resolved_root).resolve()
    return resolve_control_path(resolved_root, "run_manifest.json")


def manifest_policy_ref(root: Path | str, manifest_path: Path | None = None) -> str:
    """Return the project-relative policy pointer for a v2 run index."""

    resolved_root = _root(root)
    path = manifest_path.resolve() if manifest_path is not None else resolve_manifest_path(resolved_root)
    try:
        relative = path.relative_to(resolved_root).as_posix()
    except ValueError:
        relative = path.as_posix()
    return f"{relative}#/control/selection_policy"


def write_hidden_layout_marker(root: Path | str) -> Path:
    """Mark a complete hidden control layout as active.

    The caller must verify the control files first.  The marker intentionally
    contains only location metadata; it is not a Gate, receipt, or provenance
    record.
    """

    marker = layout_marker_path(root)
    value = {
        "schema_version": LAYOUT_SCHEMA_VERSION,
        "active_layout": "hidden",
        "control_directory": HIDDEN_STATE_RELATIVE.as_posix(),
        "control_files": list(CONTROL_FILENAMES),
    }
    write_json_atomic(marker, value)
    return marker


__all__ = [
    "CONTROL_FILENAMES",
    "HIDDEN_STATE_RELATIVE",
    "LAYOUT_MARKER_RELATIVE",
    "StateLayoutError",
    "active_state_layout",
    "control_paths",
    "existing_control_paths",
    "flat_control_path",
    "hidden_control_path",
    "hidden_state_dir",
    "layout_marker_path",
    "manifest_policy_ref",
    "resolve_control_path",
    "resolve_manifest_path",
    "write_hidden_layout_marker",
]
