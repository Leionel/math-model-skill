"""Red-team reliability evaluation.

Every scenario here is a scripted adversary: it performs one concrete attempt
to make the Harness accept something false, then asks the Harness for its
verdict. Nothing is scored by reading prose or by asking a model to self-report,
so the whole suite runs in CI with no API key and no network.

Outcomes are one of three things, and the difference matters:

``blocked``        the attempt was refused;
``verified``       a positive property held when recomputed from bytes;
``documented_gap`` the Harness currently allows it, and the README is not
                   allowed to claim otherwise.

A documented gap that later starts being blocked fails the run as well, because
that means the published boundary description is stale.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

EVALUATION_DIR = Path(__file__).resolve().parent
REPO_ROOT = EVALUATION_DIR.parent
SCRIPTS = REPO_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(REPO_ROOT / "examples" / "end_to_end"))

import run_demo  # noqa: E402 - the demo project is the shared evaluation fixture
from run_demo import Demo, load_json, write_json  # noqa: E402

SUITE_VERSION = "1.0"


def outcome(kind: str, name: str, property_text: str, attempt: str, *, expect: str,
            actual: str, evidence: list[str]) -> dict[str, object]:
    held = actual == expect
    return {
        "class": kind,
        "scenario": name,
        "property": property_text,
        "attempt": attempt,
        "expected": expect,
        "actual": actual,
        "held": held,
        "evidence": evidence,
    }


def built_project(cache: dict[str, object], root: Path) -> Demo:
    """Build the chain once per run and reuse it as the attack baseline."""
    if "demo" not in cache:
        project = root / "baseline"
        project.mkdir(parents=True, exist_ok=True)
        demo = Demo(project, verbose=False)
        run_demo.build(demo)
        cache["demo"] = demo
    return cache["demo"]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Chain scenarios: reuse the demo probes, which already attempt real bypasses.
# ---------------------------------------------------------------------------

# (class, probe, human label, expected outcome)
CHAIN_SCENARIOS = (
    ("gate_bypass", run_demo.probe_gate_field_is_inert, "blocked"),
    ("fabricated_evidence", run_demo.probe_freeze_needs_execution, "blocked"),
    ("stale_artifact_acceptance", run_demo.probe_downstream_goes_stale, "blocked"),
    ("reviewer_independence_violation", run_demo.probe_reviewer_cannot_self_promote, "blocked"),
    ("unsupported_claim", run_demo.probe_unsupported_claim_is_blocked, "blocked"),
    ("traceability", run_demo.positive_checks, "verified"),
)


def _normalize(kind: str, row: dict[str, object], expect: str) -> dict[str, object]:
    """Adopt a demo probe result as an evaluation scenario row."""

    positive = expect == "verified"
    actual = expect if row["held"] else ("failed" if positive else "allowed")
    return outcome(
        kind,
        str(row["property"]),
        str(row["property"]),
        str(row["attempt"]),
        expect=expect,
        actual=actual,
        evidence=[str(item) for item in row["evidence"]],
    )


# ---------------------------------------------------------------------------
# Local scenarios: cheap, targeted attacks that do not need a fresh chain.
# ---------------------------------------------------------------------------

def scenario_projection_copy_is_inert(demo: Demo) -> dict[str, object]:
    """A copied exit code in the projection changes nothing: it is never read."""

    probe = run_demo._clone(demo, "index-exit")
    index = load_json(probe.root / "run_index.json")
    for row in index.get("receipts", []):
        row["exit_code"] = 0
    write_json(probe.root / "run_index.json", index)
    code, errors = run_demo._gate_errors(probe, "P1")
    return outcome(
        "fabricated_evidence", "run_index_copies_exit_code",
        "the run index is a projection, not execution truth",
        "copy exit_code=0 into every run_index receipt row",
        # inert by design: P1 recomputes from the receipt files, so a forged
        # projection field cannot flip the verdict either way.
        expect="inert", actual="inert" if code == 0 else "changed_verdict",
        evidence=[*errors[:2], f"exit={code}", "P1 is computed from receipts/ files"],
    )


def scenario_receipt_provenance_is_not_attested(demo: Demo) -> dict[str, object]:
    """Byte-consistent receipt forgery is the stated limit of this design."""

    probe = run_demo._clone(demo, "forged-receipt")
    index = load_json(probe.root / "run_index.json")
    entry = next(row for row in index["receipts"] if row.get("stage") == "full")
    receipt_path = probe.root / entry["receipt_path"]
    receipt = load_json(receipt_path)
    receipt["argv"] = [sys.executable, "a-different-script.py"]
    write_json(receipt_path, receipt)
    code, errors = run_demo._gate_errors(probe, "P2")
    return outcome(
        "fabricated_evidence", "receipt_argv_is_not_attested",
        "a receipt proves byte identity, not which process ran",
        "rewrite argv inside the bound receipt, keeping every digest valid",
        # No signing or external attestation exists, so a byte-consistent
        # rewrite is accepted. The README may not claim otherwise.
        expect="allowed", actual="allowed" if code == 0 else "blocked",
        evidence=[*errors[:2], f"exit={code}", "receipts carry no signature or external witness"],
    )


def scenario_human_checkpoint_is_unattested(demo: Demo) -> dict[str, object]:
    probe = run_demo._clone(demo, "checkpoint")
    manifest = load_json(probe.root / "run_manifest.json")
    manifest["human_checkpoints"] = [
        row for row in manifest["human_checkpoints"] if row.get("stage") != "w1"
    ]
    write_json(probe.root / "run_manifest.json", manifest)
    missing_code, _ = run_demo._gate_errors(probe, "W1")
    run_demo.add_checkpoint(probe, "w1", "whoever-edited-the-json")
    forged_code, errors = run_demo._gate_errors(probe, "W1")
    return outcome(
        "human_attention", "fabricated_human_checkpoint",
        "a human decision must exist, but its author is not cryptographically attested",
        "drop the W1 checkpoint, then re-add one under an arbitrary role",
        expect="allowed",
        actual="allowed" if missing_code != 0 and forged_code == 0 else "blocked",
        evidence=[*errors[:1], f"missing exit={missing_code} forged exit={forged_code}",
                  "decided_by is free text; identity binding is not implemented"],
    )


def scenario_bound_artifact_deleted(demo: Demo) -> dict[str, object]:
    probe = run_demo._clone(demo, "delete")
    (probe.root / "paper.txt").unlink()
    code, errors = run_demo._validate_errors(probe)
    return outcome(
        "stale_artifact_acceptance", "reviewed_artifact_deleted",
        "removing evidence must fail closed",
        "delete the reviewed paper and re-validate W2",
        expect="blocked", actual="blocked" if code != 0 else "allowed",
        evidence=[*errors[:2], f"exit={code}"],
    )


def scenario_dag_lineage_tampering(demo: Demo) -> dict[str, object]:
    probe = run_demo._clone(demo, "dag")
    dag = load_json(probe.root / "artifact_dag.json")
    dag["nodes"].append({
        "artifact_id": "ART-PHANTOM-99", "role": "frozen_results",
        "path": "unbacked_frozen.json", "producer_id": "whoever",
        "dependencies": [{"artifact_id": "ART-NOPE-00", "relation": "consumes"}],
        "lifecycle": "mutable", "freshness": "current", "digest_owner": "artifact_dag",
    })
    write_json(probe.root / "artifact_dag.json", dag)
    completed = subprocess.run(
        [sys.executable, str(SCRIPTS / "qa" / "check_artifact_dag.py"),
         "--project-root", str(probe.root), "--dag", str(probe.root / "artifact_dag.json"), "--strict"],
        cwd=probe.root, text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
    )
    payload = json.loads(completed.stdout or "{}")
    errors = list(payload.get("errors", []))
    return outcome(
        "lineage_integrity", "dag_names_unknown_dependency_and_second_frozen_owner",
        "the DAG may be hand-authored but must stay structurally consistent",
        "append a node with an unknown dependency and a duplicate frozen_results role",
        expect="blocked", actual="blocked" if completed.returncode != 0 else "allowed",
        evidence=[*errors[:2], f"exit={completed.returncode}"],
    )


def scenario_ai_ledger_entry_without_interaction(demo: Demo) -> dict[str, object]:
    probe = run_demo._clone(demo, "ai-ledger")
    manifest = load_json(probe.root / "run_manifest.json")
    rows = manifest.get("ai_usage") or []
    rows.append({
        "usage_id": "USAGE-forged", "stage": "paper", "tool": "any", "model": "any",
        "provider": "any", "purpose": "claim help that never happened",
        "output_use": "none", "human_changes": "none",
        "interaction_record": {"path": "no/such/transcript.json", "sha256": "0" * 64},
        "verification": {"status": "verified", "checked_by_role": "myself", "method": "trust me"},
    })
    manifest["ai_usage"] = rows
    write_json(probe.root / "run_manifest.json", manifest)
    code, errors = run_demo._gate_errors(probe, "W2")
    return outcome(
        "ai_disclosure", "ai_usage_row_without_a_real_transcript",
        "an AI-use record must point at a stored interaction transcript",
        "append a verified AI usage row referencing a nonexistent transcript",
        expect="blocked", actual="blocked" if code != 0 else "allowed",
        evidence=[*errors[:2], f"exit={code}"],
    )


LOCAL_SCENARIOS = (
    scenario_projection_copy_is_inert,
    scenario_receipt_provenance_is_not_attested,
    scenario_human_checkpoint_is_unattested,
    scenario_bound_artifact_deleted,
    scenario_dag_lineage_tampering,
    scenario_ai_ledger_entry_without_interaction,
)


def run(*, keep: Path | None = None) -> dict[str, object]:
    started = datetime.now(timezone.utc)
    temporary = None if keep else tempfile.TemporaryDirectory(prefix="redteam-")
    root = (keep or Path(temporary.name)).resolve()  # type: ignore[union-attr]
    cache: dict[str, object] = {}
    results: list[dict[str, object]] = []
    try:
        for kind, attack, expect in CHAIN_SCENARIOS:
            demo = built_project(cache, root)
            results.append(_normalize(kind, attack(demo), expect))
        for scenario in LOCAL_SCENARIOS:
            demo = built_project(cache, root)
            results.append(scenario(demo))
    finally:
        if temporary is not None:
            temporary.cleanup()

    metrics: dict[str, dict[str, int]] = {}
    for row in results:
        bucket = metrics.setdefault(str(row["class"]), {"attempts": 0, "blocked": 0, "gaps": 0, "held": 0})
        bucket["attempts"] += 1
        if row["expected"] == "allowed":
            bucket["gaps"] += 1
        elif row["actual"] in {"blocked", "verified", "inert"}:
            bucket["blocked"] += 1
        if row["held"]:
            bucket["held"] += 1

    failures = [row for row in results if not row["held"]]
    return {
        "ok": not failures,
        "suite_version": SUITE_VERSION,
        "started_at": started.isoformat(timespec="seconds"),
        "elapsed_s": round((datetime.now(timezone.utc) - started).total_seconds(), 1),
        "preset": "sprint",
        "metrics": metrics,
        "scenarios": results,
        "not_measured": [
            "LLM task quality: this suite attacks the Harness, not a model",
            "capability benchmark: see evaluation/ablation.py, which is NOT RUN",
        ],
        "boundary": (
            "Outcomes are the Harness's own exit codes and error lists. A scenario whose "
            "expected outcome is 'allowed' documents a real gap; if it starts being blocked, "
            "the run fails so the published boundary text cannot silently go stale."
        ),
    }


def render_human(report: dict[str, object]) -> str:
    lines = [f"red-team reliability eval: {'PASS' if report['ok'] else 'FAIL'}"]
    for name, bucket in sorted(report["metrics"].items()):  # type: ignore[union-attr]
        lines.append(
            f"  {name:<32} attempts={bucket['attempts']} blocked={bucket['blocked']} "
            f"documented_gaps={bucket['gaps']} held={bucket['held']}"
        )
    for row in report["scenarios"]:  # type: ignore[union-attr]
        if not row["held"]:
            lines.append(f"  UNEXPECTED {row['class']}/{row['scenario']}: expected {row['expected']} got {row['actual']}")
            for item in row["evidence"]:
                lines.append(f"    {item}")
    lines.append(f"  not measured: {'; '.join(report['not_measured'])}")  # type: ignore[union-attr]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--output", type=Path, help="write the report JSON here")
    parser.add_argument("--keep", type=Path, help="keep the attack projects under this directory")
    args = parser.parse_args(argv)
    if args.keep:
        shutil.rmtree(args.keep, ignore_errors=True)
        args.keep.mkdir(parents=True, exist_ok=True)
    report = run(keep=args.keep)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2) if args.json else render_human(report))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
