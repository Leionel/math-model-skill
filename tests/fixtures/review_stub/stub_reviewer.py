"""Deterministic stub reviewer used by the Review E2E tests.

It reads the MATH_REVIEW_* environment seam, asserts the fresh-context
information boundary (no denied roles inside the bundle), and writes one
contract-valid review report.  Test scenarios steer it with:

- MATH_REVIEW_STUB_FINDING   emit one open high finding with this id (verdict=fail)
- MATH_REVIEW_STUB_RESOLVE   emit the finding with status=resolved (verdict=pass)
- MATH_REVIEW_STUB_AT        override reviewed_at for ordering scenarios

The stub proves the Execution Plane (receipt seam, bundle boundary, report
contract, registration), not LLM review quality.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

DENIED_ROLES = {"review_report", "previous_verdict", "writer_reasoning", "revision_discussion", "session_log"}
BIND_ROLES = {
    "semantic_critic": ("model_contract", "frozen_results", "evidence_registry", "paper_plan", "abstract", "paper", "conclusion"),
    "judge_lens": ("paper", "abstract", "conclusion"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    try:
        bundle_path = Path(os.environ["MATH_REVIEW_BUNDLE"])
        output = Path(os.environ["MATH_REVIEW_OUTPUT"])
        perspective = os.environ["MATH_REVIEW_PERSPECTIVE"]
        mode = os.environ.get("MATH_REVIEW_STUB_MODE_OVERRIDE") or os.environ.get("MATH_REVIEW_MODE", "self_critic")
        level = os.environ.get("MATH_REVIEW_STUB_LEVEL_OVERRIDE") or os.environ.get("MATH_REVIEW_INDEPENDENCE", "L0_same_context")
        run_id = os.environ.get("MATH_REVIEW_STUB_RUN_ID", "run-1")
    except KeyError as exc:
        print(json.dumps({"ok": False, "errors": [f"missing env: {exc}"]}))
        return 2
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    mutate_author = os.environ.get("MATH_REVIEW_STUB_MUTATE_AUTHOR")
    if mutate_author:
        Path(mutate_author).write_text("mutated by reviewer\n", encoding="utf-8")
    if os.environ.get("MATH_REVIEW_STUB_MUTATE_BUNDLE") == "1":
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n ", encoding="utf-8")
    for row in bundle.get("files", []):
        if row.get("role") in DENIED_ROLES:
            print(json.dumps({"ok": False, "errors": [f"denied role inside bundle: {row['role']}"]}))
            return 3
    by_role = {row.get("role"): row for row in bundle.get("files", [])}
    reviewed = [
        {
            "artifact_id": by_role[role].get("artifact_id"),
            "role": role,
            "path": by_role[role]["source_path"],
            "sha256": by_role[role]["sha256"],
        }
        for role in BIND_ROLES[perspective]
        if role in by_role
    ]
    if not reviewed:
        print(json.dumps({"ok": False, "errors": ["bundle has no bindable artifacts for this perspective"]}))
        return 4
    findings: list[dict] = []
    finding_spec = os.environ.get("MATH_REVIEW_STUB_FINDING", "")
    # Format "perspective:finding_id" scopes the finding to one perspective;
    # a bare "finding_id" applies to every perspective.
    perspective_scoped = finding_spec.startswith(f"{perspective}:")
    finding_id = finding_spec.split(":", 1)[1] if perspective_scoped else finding_spec
    if finding_id:
        status = "resolved" if os.environ.get("MATH_REVIEW_STUB_RESOLVE") == "1" else "open"
        findings.append({
            "finding_id": finding_id,
            "perspective": perspective,
            "severity": "high",
            "summary": "Abstract claims dominance over all possible plans, but current evidence only supports superiority over the tested baseline.",
            "evidence_locator": "abstract.txt:sentence-1",
            "affected_artifact": next(row["path"] for row in reviewed if row["role"] in {"paper", "abstract"}),
            "affected_claim_id": None,
            "required_fix": "Restrict the claim to the tested baseline comparison.",
            "confidence": "high",
            "status": status,
        })
    verdict = "fail" if any(row["status"] == "open" for row in findings) else "pass"
    report = {
        "schema_version": "1.0",
        "report_id": f"REV-{perspective}-{run_id}",
        "run_id": run_id,
        "perspective": perspective,
        "review_mode": mode,
        "independence_level": level,
        "degraded_independence": False,
        "reviewed_at": os.environ.get("MATH_REVIEW_STUB_AT") or datetime.now(timezone.utc).isoformat(),
        "reviewed_artifacts": reviewed,
        "bundle_ref": {"path": os.environ.get("MATH_REVIEW_BUNDLE_REL", str(bundle_path)), "sha256": sha256(bundle_path)},
        "execution_receipt_ref": {
            "receipt_id": os.environ["MATH_REVIEW_RECEIPT_ID"],
            "path": os.environ["MATH_REVIEW_RECEIPT_REL"],
        },
        "rubric_ref": os.environ.get("MATH_REVIEW_RUBRIC", ""),
        "findings": findings,
        "verdict": verdict,
        "superseded_by": None,
        "notes": "deterministic e2e stub reviewer",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "report": str(output), "verdict": verdict, "findings": len(findings)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
