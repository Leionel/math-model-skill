"""Load and validate verifier declarations against ``schemas/verifier.schema.json``.

A declaration is metadata about a check the harness already ships: the script
that performs it, the canonical inputs it consumes, and the gate runtime that
invokes it. The registry is read-only and deterministic — it never runs a
declaration and never writes a projection — and an invalid declaration set is an
error, not a silently smaller registry.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent
REPO_ROOT = SCRIPTS_DIR.parent
for _directory in (SCRIPTS_DIR, SCRIPTS_DIR / "qa"):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))

from _common import load_structured  # noqa: E402
from gate_order import GATE_ORDER as _GATE_ORDER  # noqa: E402

# The canonical input vocabulary. ``schemas/verifier.schema.json`` mirrors it,
# and tests/test_verifier_registry.py fails if the two ever disagree.
CONSUMES = (
    "ai_ledger",
    "artifact_dag",
    "competition_profile",
    "derived_results",
    "evidence_registry",
    "frozen_results",
    "implementation_map",
    "model_contract",
    "paper",
    "receipts",
    "review_evidence",
    "run_index",
    "run_manifest",
    "validation_report",
)
GATES = _GATE_ORDER
DEFAULT_DECLARATIONS_DIR = SCRIPT_DIR / "declarations"


class VerifierContractError(ValueError):
    """Every error in a declaration set, sorted, so one run is reproducible."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = sorted(errors)
        super().__init__("; ".join(self.errors))


def load_registry(
    declarations_dir: Path | str | None = None,
    *,
    repo_root: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    """Return ``{verifier_id: declaration}`` for one declaration set.

    ``repo_root`` is the tree the declarations are resolved against: it supplies
    the schema and the entrypoint scripts, so a caller can validate a fixture
    tree without touching the checkout.
    """

    root = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT
    if declarations_dir is not None:
        directory = Path(declarations_dir).resolve()
    elif repo_root is None:
        directory = DEFAULT_DECLARATIONS_DIR
    else:
        directory = root / "scripts" / "verifiers" / "declarations"
    schema_path = root / "schemas" / "verifier.schema.json"
    schema = load_structured(schema_path)
    if not isinstance(schema, Mapping):
        raise VerifierContractError([f"{schema_path}: schema must be an object"])
    files = sorted(path for path in directory.glob("*.yaml"))
    if not files:
        raise VerifierContractError([f"{directory}: no verifier declarations found"])

    registry: dict[str, dict[str, Any]] = {}
    errors: list[str] = []
    for path in files:
        label = path.name
        try:
            declaration = load_structured(path)
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"{label}: cannot read declaration: {exc}")
            continue
        if not isinstance(declaration, Mapping):
            errors.append(f"{label}: declaration must be an object")
            continue
        errors.extend(f"{label}: {message}" for message in _schema_errors(dict(declaration), schema))
        verifier_id = declaration.get("verifier_id")
        if not isinstance(verifier_id, str):
            continue
        if verifier_id in registry:
            errors.append(f"{label}: duplicate verifier_id {verifier_id}")
            continue
        errors.extend(f"{label}: {message}" for message in _entrypoint_errors(root, declaration))
        registry[verifier_id] = dict(declaration)
    if errors:
        raise VerifierContractError(errors)
    return dict(sorted(registry.items()))


def registry_for_gate(registry: Mapping[str, Mapping[str, Any]], gate: str) -> list[str]:
    """Return the sorted verifier ids that declare the given gate."""

    selected = gate.lower()
    if selected not in GATES:
        raise ValueError(f"gate must be one of {', '.join(GATES)}")
    return sorted(
        verifier_id
        for verifier_id, declaration in registry.items()
        if selected in declaration.get("gates", [])
    )


def _schema_errors(instance: dict[str, Any], schema: Mapping[str, Any]) -> list[str]:
    import jsonschema  # noqa: PLC0415 - already a Harness dependency

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in errors
    ]


def _entrypoint_errors(root: Path, declaration: Mapping[str, Any]) -> list[str]:
    entrypoint = declaration.get("entrypoint")
    script = entrypoint.get("script") if isinstance(entrypoint, Mapping) else None
    if not isinstance(script, str):
        return []
    resolved = (root / script).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return [f"entrypoint script escapes the repository root: {script}"]
    if not resolved.is_file():
        return [f"entrypoint script does not exist: {script}"]
    return []