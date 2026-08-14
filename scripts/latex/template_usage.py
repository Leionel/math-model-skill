"""Shared checks proving that a declared LaTeX template is actually in use."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from qa.validate_contracts import _validate_document


DOCUMENT_CLASS_RE = re.compile(r"\\documentclass\s*(?:\[[^\]]*\]\s*)?\{([^}]+)\}")
BUILTIN_CLASSES = {"article", "report", "book", "letter", "slides", "ctexart", "ctexrep", "ctexbook"}


def validate_template_usage(
    contract_path: Path,
    source_root: Path,
    entrypoint: Path,
    engine: str,
    *,
    require_verified: bool,
) -> tuple[dict[str, Any] | None, list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "template_contract.schema.json"
    contract, schema_errors, _ = _validate_document(contract_path, schema_path)
    errors.extend(f"template contract schema: {message}" for message in schema_errors)
    if not isinstance(contract, dict):
        return None, errors or ["template contract must be an object"], warnings

    if require_verified and contract.get("status") != "verified":
        errors.append("formal build requires template_contract.status=verified")
    if contract.get("entrypoint") != entrypoint.as_posix():
        errors.append(
            f"template entrypoint {contract.get('entrypoint')!r} does not match build entrypoint {entrypoint.as_posix()!r}"
        )
    if engine not in contract.get("allowed_engines", []):
        errors.append(f"engine {engine!r} is not allowed by the template contract")

    entrypoint_path = source_root / entrypoint
    if not entrypoint_path.is_file():
        errors.append(f"template entrypoint does not exist: {entrypoint.as_posix()}")
        return contract, errors, warnings
    entrypoint_text = entrypoint_path.read_text(encoding="utf-8", errors="replace")
    match = DOCUMENT_CLASS_RE.search(entrypoint_text)
    actual_class = match.group(1).strip() if match else None
    expected_class = contract.get("document_class")
    if actual_class is None:
        errors.append("entrypoint has no detectable \\documentclass declaration")
    elif actual_class != expected_class:
        errors.append(
            f"entrypoint uses document class {actual_class!r}, but template contract requires {expected_class!r}"
        )
    if actual_class in set(contract.get("forbidden_document_classes", [])):
        errors.append(f"entrypoint uses forbidden document class {actual_class!r}")

    adapter = contract.get("adapter")
    if isinstance(adapter, dict):
        for field in ("metadata_input", "body_input"):
            target = adapter.get(field)
            if not isinstance(target, str) or not target:
                errors.append(f"template adapter has no valid {field}")
                continue
            marker = rf"\input{{{target}}}"
            if marker not in entrypoint_text:
                errors.append(f"entrypoint does not include adapter {field}: {target}")

    snapshot = contract.get("template_snapshot")
    if isinstance(snapshot, dict):
        asset_hashes = snapshot.get("asset_hashes")
        if not isinstance(asset_hashes, dict):
            errors.append("template snapshot asset_hashes must be an object")
        else:
            for raw_path, expected_hash in asset_hashes.items():
                relative = Path(str(raw_path))
                if relative.is_absolute() or ".." in relative.parts:
                    errors.append(f"template asset must stay inside source root: {raw_path}")
                    continue
                path = source_root / relative
                if not path.is_file():
                    errors.append(f"retained template asset is missing: {relative.as_posix()}")
                    continue
                actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                if actual_hash != expected_hash:
                    errors.append(f"retained template asset changed: {relative.as_posix()}")

    for raw_path in contract.get("required_files", []):
        relative = Path(str(raw_path))
        if relative.is_absolute() or ".." in relative.parts:
            errors.append(f"template required file must stay inside source root: {raw_path}")
            continue
        path = source_root / relative
        if not path.is_file():
            errors.append(f"template required file is missing: {relative.as_posix()}")
    if (
        isinstance(expected_class, str)
        and expected_class not in BUILTIN_CLASSES
        and not (source_root / f"{expected_class}.cls").is_file()
    ):
        errors.append(f"custom document class file is missing: {expected_class}.cls")

    tex_corpus = "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in source_root.rglob("*.tex")
        if path.is_file()
    )
    for command in contract.get("required_commands", []):
        if command not in tex_corpus:
            errors.append(f"template required command is not used: {command}")

    if not contract.get("required_commands"):
        warnings.append("template contract declares no required commands beyond document class")
    return contract, errors, warnings
