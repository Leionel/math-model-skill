#!/usr/bin/env python3
"""Competition Profile Engine.

Resolves inherited YAML/JSON profiles for mathematical modeling competitions,
merges overrides, validates against schema, and produces normalized profile dictionaries.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # Optional dependency; JSON profiles and capability resolution remain usable.
    yaml = None

ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = ROOT / "competition_profiles"
SCHEMA_PATH = ROOT / "schemas" / "competition_profile.schema.json"

# WP1 keeps the legacy inheritance reader above for v1 seed compatibility, but
# exposes the single v2 capability resolver from the focused capabilities
# module.  The import is local-path friendly because existing tests add
# scripts/profiles directly to sys.path.
try:  # direct script/test import
    from capabilities import ResolvedCapabilities, resolve_profile  # type: ignore  # noqa: E402
except ImportError:  # namespace-package import (scripts.profiles.profile_engine)
    from .capabilities import ResolvedCapabilities, resolve_profile  # type: ignore  # noqa: E402


def deep_merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge two dictionaries, with overrides taking precedence."""
    merged = copy.deepcopy(base)
    for key, value in overrides.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_raw_profile(path: Path) -> dict[str, Any]:
    """Load raw YAML or JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Profile file not found: {path}")
    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("PyYAML is required to read YAML competition profile seeds")
        data = yaml.safe_load(content)
    else:
        data = json.loads(content)
    if not isinstance(data, dict):
        raise ValueError(f"Profile root must be a dict: {path}")
    return data


def resolve_profile_chain(
    name_or_path: str | Path,
    profiles_dir: Path | None = None,
    visited: list[str] | None = None,
) -> dict[str, Any]:
    """Recursively load and resolve inherited profiles."""
    if visited is None:
        visited = []

    p_dir = profiles_dir or PROFILES_DIR
    target = Path(name_or_path)
    if not target.is_file():
        # Try finding in profiles directory
        candidates = [
            p_dir / f"{name_or_path}.yaml",
            p_dir / f"{name_or_path}.yml",
            p_dir / f"{name_or_path}.json",
            p_dir / str(name_or_path),
        ]
        found = None
        for c in candidates:
            if c.is_file():
                found = c
                break
        if not found:
            raise FileNotFoundError(
                f"Could not resolve profile '{name_or_path}' in {p_dir}"
            )
        target = found

    profile_id = target.stem
    if profile_id in visited:
        raise ValueError(f"Circular inheritance detected: {' -> '.join(visited + [profile_id])}")
    visited.append(profile_id)

    raw = load_raw_profile(target)
    inherits = raw.get("inherits")

    if inherits:
        base_resolved = resolve_profile_chain(inherits, p_dir, visited)
        overrides = raw.get("overrides", {})
        # Merge top-level metadata fields from current raw profile (excluding inherits/overrides)
        current_top_level = {k: v for k, v in raw.items() if k not in ("inherits", "overrides")}
        resolved = deep_merge(base_resolved, current_top_level)
        resolved = deep_merge(resolved, overrides)
    else:
        resolved = copy.deepcopy(raw)

    # Clean internal flags if any
    resolved.pop("inherits", None)
    resolved.pop("overrides", None)
    # Keep one canonical identifier for cross-artifact binding.  A profile may
    # override the fallback (for example cumcm-2026-electronic), but a resolved
    # profile must never silently emit null and leave template/profile joins to
    # string guessing downstream.
    resolved.setdefault("profile_id", profile_id)
    return resolved


def validate_profile(profile_data: dict[str, Any], schema_path: Path | None = None) -> list[str]:
    """Validate profile against JSON Schema."""
    s_path = schema_path or SCHEMA_PATH
    if not s_path.exists():
        return []
    import jsonschema
    schema = json.loads(s_path.read_text(encoding="utf-8"))
    validator_type = jsonschema.Draft202012Validator if "2020-12" in str(schema.get("$schema", "")) else jsonschema.Draft7Validator
    validator = validator_type(schema)
    errors = []
    for err in sorted(validator.iter_errors(profile_data), key=lambda e: e.path):
        loc = ".".join(str(p) for p in err.path) or "root"
        errors.append(f"[{loc}] {err.message}")
    return errors


def resolve_canonical_profile(
    name_or_path: str | Path,
    profiles_dir: Path | None = None,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Resolve a YAML seed into the standalone v2 profile representation.

    ``resolve_profile_chain`` remains the explicit v1 compatibility reader for
    existing callers.  New writers should call this function and persist the
    returned v2 document only after unresolved official-rule fields are
    completed by the project owner.
    """

    try:
        from normalization import canonicalize_competition_profile
    except ImportError:
        from .normalization import canonicalize_competition_profile

    seed = resolve_profile_chain(name_or_path, profiles_dir or PROFILES_DIR)
    return canonicalize_competition_profile(seed, profile_id=str(seed.get("profile_id") or Path(name_or_path).stem))


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve a competition profile seed. New output is standalone v2 by default.")
    parser.add_argument("--profile", "-p", required=True, help="Profile name (e.g. cumcm, mcm_icm) or file path")
    parser.add_argument("--profiles-dir", "-d", default=str(PROFILES_DIR), help="Directory with profile files")
    parser.add_argument("--output", "-o", help="Path to write resolved JSON profile")
    parser.add_argument("--validate", action="store_true", help="Validate resolved profile against schema")
    parser.add_argument("--legacy-output", action="store_true", help="Deprecated: emit the v1 seed shape for a read-compatibility fixture")

    args = parser.parse_args()

    try:
        if args.legacy_output:
            resolved = resolve_profile_chain(args.profile, Path(args.profiles_dir))
            print("WARNING: --legacy-output is deprecated; new projects must emit competition_profile.json v2.", file=sys.stderr)
        else:
            resolved, _ = resolve_canonical_profile(args.profile, Path(args.profiles_dir))
    except Exception as exc:
        print(f"ERROR: Failed to resolve profile: {exc}", file=sys.stderr)
        return 1

    if args.validate:
        errors = validate_profile(resolved)
        if errors:
            print("ERROR: Profile validation failed:", file=sys.stderr)
            for e in errors:
                print(f"  - {e}", file=sys.stderr)
            return 1

    out_str = json.dumps(resolved, ensure_ascii=False, indent=2)
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(out_str + "\n", encoding="utf-8")
        print(f"Wrote resolved profile to {out_path}")
    else:
        print(out_str)

    return 0


if __name__ == "__main__":
    sys.exit(main())
