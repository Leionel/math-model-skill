#!/usr/bin/env python3
"""Record human checkpoint decisions as append-only evidence.

``record_decision`` writes one decision artifact under
``.harness/human_decisions/`` (chained to the previous artifact's bytes) and
appends one ``run_manifest.human_checkpoints`` row.  The manifest stays the
control truth that gates read; the artifact is only evidence.  The recorded
role is a declaration by whoever invoked the command, never a verified
identity, and nothing here defends against a malicious host.
"""

from __future__ import annotations

import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import load_structured, rel_path, sha256_file, write_json, write_json_atomic  # noqa: E402
from project_layout import resolve_manifest_path  # noqa: E402
from qa.validate_contracts import validate_value  # noqa: E402


DECISION_SCHEMA = SCRIPT_DIR.parent / "schemas" / "human_decision.schema.json"
DECISION_DIR = Path(".harness") / "human_decisions"


def record_decision(root: Path, stage: str, role: str, decision: str, *, note: str = "") -> dict[str, Any]:
    if re.fullmatch(r"[a-z0-9][a-z0-9_-]*", stage) is None:
        raise ValueError("checkpoint stage must match [a-z0-9][a-z0-9_-]* (lowercase)")
    if not role.strip():
        raise ValueError("--role must name the deciding role; it is recorded as a declaration, not a verified identity")
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    manifest_path = resolve_manifest_path(root)
    manifest = load_structured(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError("run manifest must be an object")
    if manifest.get("schema_version") != "2.0":
        raise ValueError("checkpoint approve requires a v2 run manifest")
    decisions_dir = root / DECISION_DIR
    decisions_dir.mkdir(parents=True, exist_ok=True)
    existing = sorted(decisions_dir.glob("*.json"))
    # The zero-padded leading sequence keeps filename order equal to append
    # order even when two decisions land in the same second.
    sequence = 0
    for path in existing:
        match = re.match(r"(\d{6})-", path.name)
        if match:
            sequence = max(sequence, int(match.group(1)))
    previous_hash = sha256_file(existing[-1]) if existing else None
    recorded_at = datetime.now(timezone.utc).isoformat()
    artifact: dict[str, Any] = {
        "schema_version": "1.0",
        "checkpoint": stage,
        "decision": decision,
        "role": role.strip(),
        "recorded_at": recorded_at,
    }
    if note:
        artifact["note"] = note
    if previous_hash is not None:
        artifact["previous_decision_sha256"] = previous_hash
    schema_errors = validate_value(artifact, DECISION_SCHEMA)
    if schema_errors:
        raise ValueError("decision artifact violates schema: " + "; ".join(schema_errors))
    artifact_name = f"{sequence + 1:06d}-{stage}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}.json"
    artifact_path = decisions_dir / artifact_name
    write_json(artifact_path, artifact)
    rows = manifest.setdefault("human_checkpoints", [])
    if not isinstance(rows, list):
        raise ValueError("run_manifest.human_checkpoints must be an array")
    rows.append({
        "checkpoint_id": f"CHK-{stage.upper()}-{len(rows) + 1:03d}",
        "stage": stage,
        "decision": "pass" if decision == "approve" else "reject",
        "decided_by": role.strip(),
        "decided_at": recorded_at,
        "decision_artifact": rel_path(artifact_path, root),
        "decision_sha256": sha256_file(artifact_path),
    })
    write_json_atomic(manifest_path, manifest)
    return {
        "checkpoint": stage,
        "decision": decision,
        "artifact": rel_path(artifact_path, root),
        "previous_decision_sha256": previous_hash,
        "manifest_rows": len(rows),
    }
