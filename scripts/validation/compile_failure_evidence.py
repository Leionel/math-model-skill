#!/usr/bin/env python3
"""Compile a non-claimable diagnostic artifact from a failed frozen run."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file, sha256_json, write_json  # noqa: E402


def _report_summary(report: dict[str, Any], obligation_id: str, status: str) -> str:
    errors = report.get("errors")
    if isinstance(errors, list) and errors and isinstance(errors[0], str) and errors[0].strip():
        return errors[0].strip()
    message = report.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return f"Validation obligation {obligation_id} returned {status}."


def _verify_ref(ref: Any, root: Path, label: str) -> tuple[dict[str, str] | None, Path | None, str | None]:
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str) or not ref["path"]:
        return None, None, f"{label} must contain a non-empty path"
    path = resolve_path(ref["path"], root).resolve()
    if not path.is_file():
        return None, None, f"{label} does not exist: {ref['path']}"
    supplied_hash = ref.get("sha256")
    if supplied_hash is not None and supplied_hash != sha256_file(path):
        return None, None, f"{label} sha256 does not match the current file"
    normalized = {"path": rel_path(path, root)}
    if isinstance(supplied_hash, str):
        normalized["sha256"] = supplied_hash
    return normalized, path, None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-results", required=True)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    frozen_path = resolve_path(args.frozen_results, root).resolve()
    model_path = resolve_path(args.model_contract, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    try:
        frozen = load_structured(frozen_path)
        model = load_structured(model_path)
        if not isinstance(frozen, dict) or not isinstance(model, dict):
            raise ValueError("frozen_results and model_contract must be objects")
        if frozen.get("status") != "frozen":
            raise ValueError("frozen_results.status must be frozen")
        verdict = frozen.get("validation_verdict")
        if verdict not in {"FAIL", "ERROR"} or frozen.get("claimable") is not False:
            raise ValueError("failure evidence requires a non-claimable FAIL or ERROR frozen run")

        obligation_to_question = {
            str(obligation.get("obligation_id")): model_id.get("question_id")
            for model_id in model.get("models", [])
            if isinstance(model_id, dict)
            for obligation in model_id.get("validation_obligations", [])
            if isinstance(obligation, dict) and isinstance(obligation.get("obligation_id"), str)
        }
        fallback_question = next(
            (
                row.get("question_id")
                for row in frozen.get("results", [])
                if isinstance(row, dict) and isinstance(row.get("question_id"), str)
            ),
            None,
        )
        if not fallback_question:
            raise ValueError("frozen_results must contain at least one question_id for diagnostic claims")

        failed_rows = [
            row for row in frozen.get("validation_obligations", [])
            if isinstance(row, dict) and row.get("status") in {"FAIL", "ERROR"}
        ]
        if not failed_rows:
            raise ValueError("frozen_results contains no failed validation obligation")

        failed_obligations: list[dict[str, Any]] = []
        diagnostic_claims: list[dict[str, Any]] = []
        for row in failed_rows:
            obligation_id = str(row.get("obligation_id"))
            status = str(row.get("status"))
            report_ref, report_path, error = _verify_ref(row.get("report"), root, f"validation report {obligation_id}")
            if error or report_ref is None or report_path is None:
                raise ValueError(error or f"validation report {obligation_id} is invalid")
            report = load_structured(report_path)
            if not isinstance(report, dict):
                raise ValueError(f"validation report {obligation_id} must be an object")
            summary = _report_summary(report, obligation_id, status)
            failed_obligations.append({
                "obligation_id": obligation_id,
                "status": status,
                "report": report_ref,
                "summary": summary,
                "implication": "This run is diagnostic only and cannot support a positive numerical claim until the obligation is resolved.",
            })
            question_id = obligation_to_question.get(obligation_id) or fallback_question
            diagnostic_claims.append({
                "claim_id": f"DIAG-{obligation_id}",
                "question_id": question_id,
                "text": f"The run failed validation obligation {obligation_id}: {summary}",
                "support_level": "diagnostic",
                "claimable": False,
            })

        source_ref = {"path": rel_path(frozen_path, root), "sha256": sha256_file(frozen_path)}
        payload: dict[str, Any] = {
            "schema_version": "1.0",
            "failure_evidence_id": f"FE-{frozen.get('run_id')}-{verdict}",
            "run_id": frozen.get("run_id"),
            "status": "diagnostic",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_frozen_results": source_ref,
            "validation_verdict": verdict,
            "failed_obligations": failed_obligations,
            "diagnostic_claims": diagnostic_claims,
        }
        payload["evidence_sha256"] = sha256_json(payload)
        write_json(output_path, payload, overwrite=args.force)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"status": "diagnostic", "output": rel_path(output_path, root), "failed_obligations": len(failed_obligations)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
