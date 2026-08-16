"""Small stdlib helpers shared by the P0 contract tools."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def child_env() -> dict[str, str]:
    """Environment for child Python checkers.

    Windows children default to a legacy console encoding for piped stdout,
    which turns non-ASCII report text into UnicodeEncodeError inside the child.
    Forcing UTF-8 on both ends keeps parent/child JSON round-trips stable.
    """

    env = dict(os.environ)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_json(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_structured(path: Path) -> Any:
    """Load JSON, or YAML when PyYAML is available.

    P0 uses JSON so no parser dependency is required. Existing YAML files are
    accepted only when PyYAML is available in the runtime.
    """

    text = path.read_text(encoding="utf-8")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise ValueError(
                f"{path} is not JSON and PyYAML is unavailable; use JSON-compatible YAML or install PyYAML"
            ) from exc
        try:
            value = yaml.safe_load(text)
        except Exception as yaml_error:  # pragma: no cover - parser-specific
            raise ValueError(f"cannot parse structured file {path}: {yaml_error}") from yaml_error
        if value is None:
            raise ValueError(f"structured file {path} is empty")
        return value


def write_json(path: Path, value: Any, *, overwrite: bool = False) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(f"refusing to overwrite existing file: {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def rel_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def resolve_path(raw: str, root: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path
