"""Compose a competition profile from capability declarations.

A capability bundles verifiers (looked up in the verifier registry), schemas,
artifact roles and the gates it serves; profiles compose capability ids and
``requires`` expands transitively. Cross-checks are fail-closed: a bundled
verifier must exist in the registry and serve at least one of the capability's
gates, a named schema must exist under ``schemas/``, and every key in
``compositions.yaml`` must be a profile id a competition profile really declares.

The package is named ``capability_composition``, not ``capabilities``, because
``profile_engine`` imports its sibling ``capabilities`` module by bare name.
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

import verifiers  # noqa: E402
from _common import load_structured  # noqa: E402

DECLARATIONS_DIR = SCRIPT_DIR / "declarations"
COMPOSITIONS_PATH = SCRIPT_DIR / "compositions.yaml"
PROFILES_DIR = REPO_ROOT / "competition_profiles"


class CapabilityCompositionError(ValueError):
    """Every error in a capability set or composition, sorted."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = sorted(errors)
        super().__init__("; ".join(self.errors))


def profile_ids(*, repo_root: Path | str | None = None) -> set[str]:
    """Every profile_id the competition profiles really declare."""

    root = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT
    found: set[str] = set()
    for path in sorted((root / "competition_profiles").glob("*.yaml")):
        try:
            document = load_structured(path)
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(document, Mapping) and isinstance(document.get("profile_id"), str):
            found.add(str(document["profile_id"]))
    return found


def load_declarations(
    directory: Path | str | None = None,
    *,
    repo_root: Path | str | None = None,
) -> dict[str, dict[str, Any]]:
    """Return ``{capability_id: declaration}`` for one declaration set."""

    root = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT
    # Both defaults follow the tree being loaded, the way the verifier registry
    # already does, so a fixture tree can be validated without touching the checkout.
    declarations_dir = (
        Path(directory).resolve()
        if directory is not None
        else root / "scripts" / "capability_composition" / "declarations"
    )
    schema_path = root / "schemas" / "capability.schema.json"
    schema = load_structured(schema_path)
    if not isinstance(schema, Mapping):
        raise CapabilityCompositionError([f"{schema_path}: schema must be an object"])
    files = sorted(path for path in declarations_dir.glob("*.yaml"))
    if not files:
        raise CapabilityCompositionError([f"{declarations_dir}: no capability declarations found"])
    verifier_registry = verifiers.load_registry(repo_root=root)
    declarations: dict[str, dict[str, Any]] = {}
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
        capability_id = declaration.get("capability_id")
        if not isinstance(capability_id, str):
            continue
        if capability_id in declarations:
            errors.append(f"{label}: duplicate capability_id {capability_id}")
            continue
        declared_gates = {str(gate) for gate in declaration.get("gates", []) if isinstance(gate, str)}
        for verifier_id in declaration.get("verifiers", []):
            entry = verifier_registry.get(str(verifier_id))
            if entry is None:
                errors.append(f"{label}: unknown verifier_id {verifier_id}")
                continue
            served = {str(gate) for gate in entry.get("gates", [])}
            if not served & declared_gates:
                errors.append(
                    f"{label}: verifier {verifier_id} serves {sorted(served)} but the capability only claims {sorted(declared_gates)}"
                )
        for schema_name in declaration.get("schemas", []):
            if not (root / "schemas" / str(schema_name)).is_file():
                errors.append(f"{label}: schema does not exist: {schema_name}")
        declarations[capability_id] = dict(declaration)
    for capability_id, declaration in declarations.items():
        for required in declaration.get("requires", []):
            if str(required) not in declarations:
                errors.append(f"{capability_id}: unknown required capability {required}")
    if errors:
        raise CapabilityCompositionError(errors)
    return dict(sorted(declarations.items()))


def load_compositions(
    path: Path | str | None = None,
    *,
    repo_root: Path | str | None = None,
) -> dict[str, list[str]]:
    """Return ``{profile_id: [capability_id, ...]}`` with every key grounded."""

    root = Path(repo_root).resolve() if repo_root is not None else REPO_ROOT
    source = (
        Path(path).resolve()
        if path is not None
        else root / "scripts" / "capability_composition" / "compositions.yaml"
    )
    document = load_structured(source)
    if not isinstance(document, Mapping) or not isinstance(document.get("profiles"), Mapping):
        raise CapabilityCompositionError([f"{source}: compositions must map profiles to capability ids"])
    known_profiles = profile_ids(repo_root=root)
    compositions: dict[str, list[str]] = {}
    errors: list[str] = []
    for profile_id, capability_ids in sorted(document["profiles"].items()):
        if str(profile_id) not in known_profiles:
            errors.append(f"composition names an unknown profile_id: {profile_id}")
            continue
        if not isinstance(capability_ids, list) or not all(isinstance(value, str) for value in capability_ids):
            errors.append(f"composition for {profile_id} must be an array of capability ids")
            continue
        compositions[str(profile_id)] = [str(value) for value in capability_ids]
    if errors:
        raise CapabilityCompositionError(errors)
    return compositions


def resolve_capabilities(
    profile_id: str,
    declarations: Mapping[str, Mapping[str, Any]],
    compositions: Mapping[str, list[str]],
) -> list[str]:
    """Expand ``requires`` transitively; a cycle is a contract error."""

    if profile_id not in compositions:
        raise CapabilityCompositionError([f"no composition is declared for profile {profile_id}"])
    resolved: list[str] = []
    visiting: set[str] = set()

    def visit(capability_id: str, trail: list[str]) -> None:
        if capability_id in visiting:
            raise CapabilityCompositionError([f"capability requires form a cycle: {' -> '.join([*trail, capability_id])}"])
        if capability_id in resolved:
            return
        declaration = declarations.get(capability_id)
        if declaration is None:
            raise CapabilityCompositionError([f"unknown capability_id in composition: {capability_id}"])
        visiting.add(capability_id)
        for required in declaration.get("requires", []):
            visit(str(required), [*trail, capability_id])
        visiting.discard(capability_id)
        if capability_id not in resolved:
            resolved.append(capability_id)

    for capability_id in compositions[profile_id]:
        visit(capability_id, [])
    return sorted(resolved)


def compose(
    profile_id: str,
    *,
    repo_root: Path | str | None = None,
    declarations: Mapping[str, Mapping[str, Any]] | None = None,
    compositions: Mapping[str, list[str]] | None = None,
) -> dict[str, Any]:
    """Return the concrete resources one profile composes."""

    loaded = dict(declarations) if declarations is not None else load_declarations(repo_root=repo_root)
    declared = dict(compositions) if compositions is not None else load_compositions(repo_root=repo_root)
    capability_ids = resolve_capabilities(profile_id, loaded, declared)
    verifier_ids: set[str] = set()
    schemas: set[str] = set()
    roles: set[str] = set()
    gates: set[str] = set()
    for capability_id in capability_ids:
        declaration = loaded[capability_id]
        verifier_ids.update(str(value) for value in declaration.get("verifiers", []))
        schemas.update(str(value) for value in declaration.get("schemas", []))
        roles.update(str(value) for value in declaration.get("artifact_roles", []))
        gates.update(str(value) for value in declaration.get("gates", []))
    return {
        "schema_version": "1.0",
        "profile_id": profile_id,
        "capabilities": capability_ids,
        "verifiers": sorted(verifier_ids),
        "schemas": sorted(schemas),
        "artifact_roles": sorted(roles),
        "gates": [gate for gate in verifiers.GATES if gate in gates],
    }


def _schema_errors(instance: dict[str, Any], schema: Mapping[str, Any]) -> list[str]:
    import jsonschema  # noqa: PLC0415 - already a Harness dependency

    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda error: list(error.absolute_path))
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}"
        for error in errors
    ]