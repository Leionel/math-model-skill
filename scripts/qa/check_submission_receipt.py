#!/usr/bin/env python3
"""Validate a human portal receipt against the frozen submission package."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, require_within, resolve_path, sha256_file  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402
from runtime_state import RuntimeStateError, load_runtime_state  # noqa: E402


def _timestamp(value: Any, owner: str, errors: list[str]) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{owner} must be ISO-8601 with a timezone")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        errors.append(f"{owner} must be ISO-8601 with a timezone")
        return None
    return parsed


def check_submission_receipt(receipt_path: Path, root: Path, schema_dir: Path) -> dict[str, Any]:
    root = root.resolve()
    receipt_path = require_within(receipt_path.resolve(), root, label="submission receipt")
    value, errors, engine = _validate_document(receipt_path, schema_dir / "submission_receipt.schema.json")
    warnings: list[str] = []
    if not isinstance(value, dict):
        value = {}

    def verify_ref(owner: str, ref: Any) -> Path | None:
        if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
            return None
        try:
            path = require_within(resolve_path(ref["path"], root).resolve(), root, label=owner)
        except ValueError as exc:
            errors.append(str(exc))
            return None
        if not path.is_file():
            errors.append(f"{owner} does not exist: {ref['path']}")
            return None
        if ref.get("sha256") != sha256_file(path):
            errors.append(f"{owner} sha256 drift: {ref['path']}")
        return path

    manifest_path = verify_ref("submission_manifest", value.get("submission_manifest"))
    submitted_path = verify_ref("submitted_file", value.get("submitted_file"))
    for index, evidence_ref in enumerate(value.get("evidence", [])):
        verify_ref(f"evidence[{index}]", evidence_ref)

    manifest: dict[str, Any] = {}
    if manifest_path is not None:
        loaded, manifest_errors, _ = _validate_document(
            manifest_path,
            schema_dir / "submission_manifest.schema.json",
        )
        errors.extend(f"submission_manifest: {message}" for message in manifest_errors)
        if isinstance(loaded, dict):
            manifest = loaded

    if manifest and submitted_path is not None:
        candidates = [manifest.get("paper"), *manifest.get("support_files", [])]
        if manifest.get("ai_disclosure") is not None:
            candidates.append(manifest["ai_disclosure"])
        submitted_ref = value.get("submitted_file", {})
        submitted_identity = (rel_path(submitted_path, root), submitted_ref.get("sha256"))
        candidate_identities = {
            (ref.get("path"), ref.get("sha256"))
            for ref in candidates
            if isinstance(ref, dict)
        }
        if submitted_identity not in candidate_identities:
            errors.append("submitted_file is not one of the immutable files in submission_manifest")

    if manifest:
        run_manifest_ref = manifest.get("run_manifest")
        run_manifest_path = verify_ref("submission_manifest.run_manifest", run_manifest_ref)
        if run_manifest_path is not None:
            try:
                state = load_runtime_state(run_manifest_path, project_root=root, allow_legacy=False)
            except (OSError, ValueError, TypeError, RuntimeStateError) as exc:
                errors.append(f"cannot resolve official submission endpoints: {exc}")
            else:
                endpoints = state.profile.get("official_submission_endpoints", [])
                portal = value.get("portal")
                if not isinstance(portal, str) or not any(
                    portal.rstrip("/") == str(endpoint).rstrip("/")
                    or portal.rstrip("/").startswith(str(endpoint).rstrip("/") + "/")
                    for endpoint in endpoints
                    if isinstance(endpoint, str)
                ):
                    errors.append("portal is not covered by the canonical official_submission_endpoints")

    submitted_at = _timestamp(value.get("submitted_at"), "submitted_at", errors)
    confirmed_at = _timestamp(value.get("confirmed_at"), "confirmed_at", errors)
    if submitted_at is not None and confirmed_at is not None and confirmed_at < submitted_at:
        errors.append("confirmed_at cannot precede submitted_at")
    portal_status = value.get("portal_status")
    if portal_status != "accepted":
        errors.append(f"portal_status={portal_status!r} does not prove an accepted submission")

    return {
        "ok": not errors,
        "engine": engine,
        "method": "human_portal_receipt_binding",
        "receipt": rel_path(receipt_path, root),
        "submission_accepted": portal_status == "accepted",
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--schema-dir")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    receipt_path = resolve_path(args.receipt, root).resolve()
    schema_dir = (
        Path(args.schema_dir).resolve()
        if args.schema_dir
        else Path(__file__).resolve().parents[2] / "schemas"
    )
    try:
        report = check_submission_receipt(receipt_path, root, schema_dir)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        report = {"ok": False, "errors": [str(exc)], "warnings": []}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
