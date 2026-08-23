"""Small stdlib helpers shared by the P0 contract tools."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping


def child_env() -> dict[str, str]:
    """Environment for child Python checkers.

    Windows children default to a legacy console encoding for piped stdout,
    which turns non-ASCII report text into UnicodeEncodeError inside the child.
    Forcing UTF-8 on both ends keeps parent/child JSON round-trips stable.
    """

    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
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


def resolve_ai_usage_state(manifest: Any) -> str:
    """Resolve the AI-use declaration with a compatibility-safe default.

    v2 treats an empty, undeclared registry as ``unknown``.  Legacy manifests
    predate the tri-state contract, so their existing empty registry retains
    the historical ``none`` interpretation during read-only validation.
    """

    if not isinstance(manifest, dict):
        return "unknown"
    declared = manifest.get("ai_usage_state")
    if declared in {"unknown", "none", "used"}:
        return str(declared)
    rows = manifest.get("ai_usage")
    if isinstance(rows, list) and rows:
        return "used"
    return "unknown" if manifest.get("schema_version") == "2.0" else "none"


def ai_usage_snapshot(manifest: Any) -> dict[str, Any]:
    """Canonical S1/F1 hash payload for both AI state and usage rows."""

    rows = manifest.get("ai_usage", []) if isinstance(manifest, dict) else []
    return {
        "state": resolve_ai_usage_state(manifest),
        "records": rows if isinstance(rows, list) else [],
        "declaration": manifest.get("ai_usage_declaration") if isinstance(manifest, dict) else None,
    }


def ai_usage_hash_matches(value: Any, manifest: Any) -> bool:
    """Accept the current snapshot hash and the historical v1 list hash."""

    if value == sha256_json(ai_usage_snapshot(manifest)):
        return True
    if isinstance(manifest, dict) and manifest.get("schema_version") != "2.0":
        rows = manifest.get("ai_usage", [])
        return value == sha256_json(rows if isinstance(rows, list) else [])
    return False


@contextmanager
def exclusive_path_lock(path: Path) -> Iterator[None]:
    """Serialize small control-file mutations without adding project artifacts."""

    key = hashlib.sha256(str(path.resolve()).casefold().encode("utf-8")).hexdigest()
    lock_path = Path(tempfile.gettempdir()) / f"math-harness-{key}.lock"
    handle = lock_path.open("a+b")
    try:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


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


def write_json_atomic(path: Path, value: Any) -> None:
    """Atomically replace one JSON control file using a same-directory temp."""

    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", delete=False,
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp",
    )
    temporary = Path(handle.name)
    try:
        with handle:
            json.dump(value, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def append_ai_usage_record(manifest_path: Path, record: Mapping[str, Any]) -> int:
    """Append one observable AI use under the same lock as CLI mutations."""

    with exclusive_path_lock(manifest_path):
        manifest = load_structured(manifest_path)
        if not isinstance(manifest, dict) or manifest.get("schema_version") != "2.0":
            raise ValueError("automatic AI logging requires a v2 run manifest")
        rows = manifest.get("ai_usage", [])
        if not isinstance(rows, list):
            raise ValueError("run_manifest.ai_usage must be an array")
        usage_id = record.get("usage_id")
        if not isinstance(usage_id, str) or not usage_id:
            raise ValueError("automatic AI record requires usage_id")
        if any(isinstance(row, Mapping) and row.get("usage_id") == usage_id for row in rows):
            raise ValueError(f"duplicate AI usage_id: {usage_id}")
        manifest["ai_usage"] = [*rows, dict(record)]
        manifest["ai_usage_state"] = "used"
        manifest.pop("ai_usage_declaration", None)
        write_json_atomic(manifest_path, manifest)
        return len(rows) + 1


def rel_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def resolve_path(raw: str, root: Path) -> Path:
    path = Path(raw)
    return path if path.is_absolute() else root / path
