"""Read-only runtime reads: the verdicts the CLI prints, without a subprocess."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = RUNTIME_DIR.parent
for _directory in (SCRIPTS_DIR, SCRIPTS_DIR / "qa"):
    if str(_directory) not in sys.path:
        sys.path.insert(0, str(_directory))

import check_gates  # noqa: E402
import harness_status  # noqa: E402
from project_layout import resolve_manifest_path  # noqa: E402


@dataclass(frozen=True)
class RuntimeView:
    """One read-only verdict: the CLI payload and the exit code it returns."""

    payload: dict[str, Any]
    exit_code: int


def get_state(root: str | Path, *, manifest_path: str | Path | None = None) -> RuntimeView:
    """Return the factual project state (``harness status``)."""

    project_root = Path(root).resolve()
    # The CLI always hands harness_status a resolved manifest path; mirror that
    # so the error branches report the same ``manifest`` field.
    manifest = resolve_manifest_path(project_root, _manifest_raw(manifest_path))
    payload, code = harness_status.status_result(project_root, str(manifest))
    return RuntimeView(payload, code)


def verify_artifact(root: str | Path, artifact_id: str, *, manifest_path: str | Path | None = None) -> RuntimeView:
    """Return one artifact's DAG identity and freshness, or a negative verdict."""

    project_root = Path(root).resolve()
    manifest = resolve_manifest_path(project_root, _manifest_raw(manifest_path))
    payload, code = harness_status.artifact_view(project_root, artifact_id, str(manifest))
    return RuntimeView(payload, code)


def check_gate(
    root: str | Path,
    gate: str,
    *,
    strict: bool = False,
    manifest_path: str | Path | None = None,
) -> RuntimeView:
    """Return one gate report (``harness check <GATE>``)."""

    project_root = Path(root).resolve()
    selected = gate.lower()
    if selected not in check_gates.GATE_ORDER:
        raise ValueError(f"gate must be one of {', '.join(check_gates.GATE_ORDER)}")
    manifest = resolve_manifest_path(project_root, _manifest_raw(manifest_path))
    payload, code = check_gates.v2_gate_result(project_root, manifest, selected, strict=strict)
    return RuntimeView(payload, code)


def _manifest_raw(manifest_path: str | Path | None) -> str | None:
    return None if manifest_path is None else str(manifest_path)