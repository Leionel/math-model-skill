"""Small runtime boundary for WP2 consumers.

The v2 control document is intentionally boring: it contains only the preset,
profile reference and root references.  This module is the single read edge
used by WP2 scripts.  Legacy documents are normalized once through the WP1
adapter; callers never need to grow another v1/v2 branch.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from _common import load_structured, resolve_path
from profiles.normalization import NormalizationError, normalize_manifest, resolve_profile

V2 = "2.0"


class RuntimeStateError(ValueError):
    """The runtime boundary cannot establish a canonical v2 fact."""


def _as_path(raw: Any, root: Path, owner: str) -> Path:
    if isinstance(raw, Mapping):
        raw = raw.get("path")
    if not isinstance(raw, str) or not raw.strip():
        raise RuntimeStateError(f"{owner}.path must be a non-empty path")
    return resolve_path(raw, root).resolve()


@dataclass(frozen=True)
class RuntimeState:
    """Normalized control state and dereferenced canonical profile."""

    root: Path
    manifest_path: Path
    manifest: dict[str, Any]
    profile: dict[str, Any]
    profile_path: Path
    capabilities: Any
    legacy: bool = False

    def root_path(self, name: str, *, required: bool = False) -> Path | None:
        roots = self.manifest.get("roots", {})
        ref = roots.get(name) if isinstance(roots, Mapping) else None
        if ref is None:
            if required:
                raise RuntimeStateError(f"run_manifest.roots.{name} is required")
            return None
        path = _as_path(ref, self.root, f"run_manifest.roots.{name}")
        if required and not path.is_file():
            raise RuntimeStateError(f"run_manifest.roots.{name} does not exist: {path}")
        return path

    @property
    def preset(self) -> str:
        return str(self.manifest.get("preset", "research"))

    @property
    def run_id(self) -> str:
        return str(self.manifest.get("run_id", ""))


def _load_raw(path: Path) -> dict[str, Any]:
    value = load_structured(path)
    if not isinstance(value, Mapping):
        raise RuntimeStateError("run_manifest must be an object")
    return dict(value)


def load_runtime_state(
    manifest_path: str | Path,
    *,
    project_root: str | Path | None = None,
    allow_legacy: bool = True,
) -> RuntimeState:
    """Load a normalized v2 state and dereference its standalone profile.

    For v1, ``normalize_manifest`` is the only compatibility edge.  The v1
    embedded profile is not returned as a v2 source of truth; callers that need
    full historical v1 semantics should remain in their legacy checker path.
    """

    path = Path(manifest_path).resolve()
    root = Path(project_root).resolve() if project_root is not None else path.parent
    raw = _load_raw(path)
    legacy = raw.get("schema_version") != V2
    if legacy and not allow_legacy:
        raise RuntimeStateError("v1 run_manifest is only accepted by the WP1 adapter")
    if legacy:
        try:
            # Supplying legacy projections here is harmless and keeps the
            # adapter's conflict reporting intact when a caller needs it.
            normalized = normalize_manifest(raw, project_root=root)
        except (NormalizationError, ValueError, TypeError) as exc:
            raise RuntimeStateError(str(exc)) from exc
    else:
        try:
            normalized = normalize_manifest(raw, project_root=root)
        except (NormalizationError, ValueError, TypeError) as exc:
            raise RuntimeStateError(str(exc)) from exc

    if normalized.get("schema_version") != V2:
        raise RuntimeStateError("runtime normalization did not produce a v2 manifest")
    profile_ref = normalized.get("competition_profile_ref")
    profile_path = _as_path(profile_ref, root, "run_manifest.competition_profile_ref")
    if not profile_path.is_file():
        raise RuntimeStateError(f"standalone competition profile does not exist: {profile_path}")
    profile_value = load_structured(profile_path)
    if not isinstance(profile_value, Mapping):
        raise RuntimeStateError("standalone competition profile must be an object")
    profile = copy.deepcopy(dict(profile_value))
    if profile.get("schema_version") != V2:
        raise RuntimeStateError("competition_profile_ref must resolve to a v2 profile")
    expected_id = profile_ref.get("profile_id") if isinstance(profile_ref, Mapping) else None
    if profile.get("profile_id") != expected_id:
        raise RuntimeStateError(
            "competition_profile_ref.profile_id conflicts with standalone competition profile.profile_id"
        )
    overrides = normalized.get("profile_overrides", {})
    if not isinstance(overrides, Mapping):
        raise RuntimeStateError("run_manifest.profile_overrides must be an object")
    try:
        capabilities = resolve_profile(str(normalized.get("preset", "")), overrides)
    except (ValueError, TypeError) as exc:
        raise RuntimeStateError(str(exc)) from exc
    return RuntimeState(
        root=root,
        manifest_path=path,
        manifest=copy.deepcopy(dict(normalized)),
        profile=profile,
        profile_path=profile_path,
        capabilities=capabilities,
        legacy=legacy,
    )


def load_json(path: str | Path, *, root: str | Path | None = None) -> Any:
    """Load one project-relative structured file through the same boundary."""

    base = Path(root).resolve() if root is not None else Path.cwd().resolve()
    return load_structured(resolve_path(str(path), base).resolve())


def resolve_profile_ref(state: RuntimeState, ref: Any, owner: str = "profile reference") -> Path:
    """Resolve a path-only v2 ref; artifact IDs remain identifiers, not paths."""

    return _as_path(ref, state.root, owner)


__all__ = ["V2", "RuntimeState", "RuntimeStateError", "load_runtime_state", "load_json", "resolve_profile_ref"]
