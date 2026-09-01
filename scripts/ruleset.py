"""Deterministic fingerprint for the Harness rule surface.

The ruleset is a read-only view of the files an upstream agent needs in order
to understand the Harness contract.  It intentionally does not include
project state, generated views, precedent material, or method cards.  A
fingerprint is therefore a cache hint for rule understanding, not a Gate,
artifact, or replacement for contract freshness checks.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any, Iterable


RULESET_VERSION = "1"

# Keep this list explicit.  Schemas and competition seeds describe executable
# contracts; these references describe the policy, validation, research,
# review, visualization, and authoring boundaries.  Cards and precedent
# material are loaded progressively and do not silently become this cache key.
CORE_REFERENCE_ROOTS = (
    "references/contracts",
    "references/research",
    "references/review",
    "references/safety",
    "references/submission",
    "references/validation",
    "references/visualization",
    "references/workflow",
    "references/writing",
)
CORE_REFERENCE_FILES = ("references/router.md",)

# These names are documented in the scope so callers can explain why changing
# a quarantined/local/generated file does not invalidate an upstream ruleset
# understanding.  The allow-list above already keeps them out of the scan.
EXCLUDED_SCOPE = (
    "references/precedents",
    "references/cards",
    "references/local-sources",
    "generated views",
    "run artifacts",
)

def _normalise_path(path: Path, root: Path) -> str:
    """Return a checkout-independent, slash-separated relative path."""

    relative = path.relative_to(root).as_posix()
    return unicodedata.normalize("NFC", relative)


def _normalise_text(raw: bytes) -> str:
    """Decode UTF-8 text and make line endings/BOM independent of checkout."""

    text = raw.decode("utf-8-sig")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _normalise_file_bytes(path: Path) -> bytes:
    """Normalize UTF-8 BOM and line endings without hiding source edits."""

    return _normalise_text(path.read_bytes()).encode("utf-8")


def _iter_files(root: Path, relative_roots: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for relative_root in relative_roots:
        directory = root / relative_root
        if directory.is_file():
            paths.append(directory)
            continue
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if path.is_file():
                paths.append(path)
    return paths


def ruleset_paths(root: str | Path) -> list[Path]:
    """Return the sorted source paths that participate in the ruleset."""

    base = Path(root).resolve()
    paths: list[Path] = []
    skill = base / "SKILL.md"
    if skill.is_file():
        paths.append(skill)
    paths.extend(_iter_files(base, ("schemas",)))
    paths.extend(_iter_files(base, ("competition_profiles",)))
    paths.extend(_iter_files(base, CORE_REFERENCE_FILES))
    paths.extend(_iter_files(base, CORE_REFERENCE_ROOTS))

    # A file should never be counted twice if a future root overlaps.  Sort on
    # normalized relative paths, not platform-specific absolute paths.
    unique = {_normalise_path(path, base): path for path in paths}
    return [unique[name] for name in sorted(unique)]


def _scope(root: Path, paths: list[Path]) -> dict[str, Any]:
    matched_roots = ["SKILL.md", "schemas", "competition_profiles", *CORE_REFERENCE_FILES, *CORE_REFERENCE_ROOTS]
    return {
        "version": RULESET_VERSION,
        "matched_roots": matched_roots,
        "file_count": len(paths),
        "excluded": list(EXCLUDED_SCOPE),
    }


def ruleset_fingerprint(root: str | Path) -> dict[str, Any]:
    """Compute a stable ruleset ID and its human/agent-readable scope.

    The top-level ``ruleset_id`` is a SHA-256 digest of the ruleset version,
    normalized relative paths, and normalized file bytes.  No timestamps,
    absolute paths, generated files, or self-referential metadata are used.
    """

    base = Path(root).resolve()
    paths = ruleset_paths(base)
    entries: list[dict[str, Any]] = []
    for path in paths:
        normalized = _normalise_file_bytes(path)
        entries.append({
            "path": _normalise_path(path, base),
            "sha256": hashlib.sha256(normalized).hexdigest(),
            "bytes": len(normalized),
        })
    payload = {"version": RULESET_VERSION, "files": entries}
    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    scope = _scope(base, paths)
    return {
        "ruleset_id": digest,
        "ruleset_scope": scope,
        "ruleset_files": [entry["path"] for entry in entries],
    }


__all__ = [
    "CORE_REFERENCE_FILES",
    "CORE_REFERENCE_ROOTS",
    "EXCLUDED_SCOPE",
    "RULESET_VERSION",
    "ruleset_fingerprint",
    "ruleset_paths",
]
