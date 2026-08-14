#!/usr/bin/env python3
"""Check that diagnostic failure evidence is bound to a failed frozen run."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    artifact_path = resolve_path(args.artifact, root).resolve()
    frozen_path = resolve_path(args.frozen_results, root).resolve()
    errors: list[str] = []
    try:
        artifact, schema_errors, _ = _validate_document(
            artifact_path, Path(__file__).resolve().parents[2] / "schemas" / "failure_evidence.schema.json"
        )
        errors.extend(f"failure evidence schema: {message}" for message in schema_errors)
        frozen = load_structured(frozen_path)
        if not isinstance(artifact, dict) or not isinstance(frozen, dict):
            errors.append("failure evidence and frozen_results must be objects")
        else:
            if args.run_id is not None and artifact.get("run_id") != args.run_id:
                errors.append("failure_evidence.run_id does not match the expected run_id")
            if artifact.get("run_id") != frozen.get("run_id"):
                errors.append("failure_evidence.run_id does not match frozen_results.run_id")
            if frozen.get("validation_verdict") not in {"FAIL", "ERROR"} or frozen.get("claimable") is not False:
                errors.append("source frozen_results must be a non-claimable FAIL or ERROR run")
            source = artifact.get("source_frozen_results")
            if not isinstance(source, dict) or source.get("path") != rel_path(frozen_path, root):
                errors.append("failure_evidence.source_frozen_results does not point to the supplied frozen_results")
            elif source.get("sha256") is not None and source.get("sha256") != sha256_file(frozen_path):
                errors.append("failure_evidence.source_frozen_results sha256 drift")
            failed_ids = {
                row.get("obligation_id")
                for row in frozen.get("validation_obligations", [])
                if isinstance(row, dict) and row.get("status") in {"FAIL", "ERROR"}
            }
            evidence_ids = {
                row.get("obligation_id")
                for row in artifact.get("failed_obligations", [])
                if isinstance(row, dict)
            }
            if failed_ids != evidence_ids:
                errors.append(f"failure evidence obligations do not match frozen failures: expected={sorted(failed_ids)}, got={sorted(evidence_ids)}")
            if any(
                not isinstance(row, dict) or row.get("claimable") is not False or row.get("support_level") != "diagnostic"
                for row in artifact.get("diagnostic_claims", [])
            ):
                errors.append("diagnostic_claims must remain support_level=diagnostic and claimable=false")
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    ok = not errors
    print(json.dumps({"ok": ok, "artifact": rel_path(artifact_path, root), "errors": errors, "warnings": []}, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
