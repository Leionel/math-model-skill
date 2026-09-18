#!/usr/bin/env python3
"""Diff two v2 run roots as facts, never as a verdict.

``diff_runs`` answers "what changed between these two states?" with identities,
root-level leaf changes, artifact freshness, receipt outcomes, gate outcomes and
review verdicts.  ``compare_runs`` adds the scientific-branching question: are
the checkpoints each side recorded still true?  Neither function ranks a branch
or names a better model.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import checkpoints  # noqa: E402
import runtime  # noqa: E402
from _common import load_structured, rel_path, sha256_file  # noqa: E402
from project_layout import resolve_manifest_path  # noqa: E402
from runtime_state import RuntimeStateError, load_runtime_state  # noqa: E402

LEAF_DIFF_CAP = 40


def _leaf_diff(
    a: Any,
    b: Any,
    path: str,
    added: list[str],
    removed: list[str],
    changed: list[dict[str, Any]],
) -> None:
    if isinstance(a, Mapping) and isinstance(b, Mapping):
        for key in sorted(set(a) | set(b)):
            child = f"{path}.{key}"
            if key not in a:
                added.append(child)
            elif key not in b:
                removed.append(child)
            else:
                _leaf_diff(a[key], b[key], child, added, removed, changed)
        return
    if isinstance(a, list) and isinstance(b, list):
        for index in range(max(len(a), len(b))):
            child = f"{path}[{index}]"
            if index >= len(a):
                added.append(child)
            elif index >= len(b):
                removed.append(child)
            else:
                _leaf_diff(a[index], b[index], child, added, removed, changed)
        return
    if a != b:
        changed.append({"path": path, "a": a, "b": b})


def _root_documents(root: Path, manifest: Mapping[str, Any]) -> dict[str, Any]:
    documents: dict[str, Any] = {}
    roots = manifest.get("roots")
    for name in sorted(roots) if isinstance(roots, Mapping) else []:
        reference = roots.get(name)
        raw = reference.get("path") if isinstance(reference, Mapping) else None
        if not isinstance(raw, str):
            continue
        path = (root / raw).resolve()
        if not path.is_file():
            documents[name] = {"path": rel_path(path, root), "absent": True}
            continue
        try:
            documents[name] = {
                "path": rel_path(path, root),
                "sha256": sha256_file(path),
                "document": load_structured(path),
            }
        except (OSError, ValueError, TypeError) as exc:
            documents[name] = {"path": rel_path(path, root), "error": str(exc)}
    return documents


def project_facts(root: Path) -> dict[str, Any]:
    """Read one side of the comparison without writing anything."""

    try:
        manifest_path = resolve_manifest_path(root)
        manifest = load_structured(manifest_path)
    except (OSError, ValueError, TypeError) as exc:
        return {"root": str(root), "ok": False, "errors": [f"cannot read manifest: {exc}"]}
    if not isinstance(manifest, Mapping):
        return {"root": str(root), "ok": False, "errors": ["run_manifest must be an object"]}
    facts: dict[str, Any] = {
        "root": str(root),
        "ok": True,
        "manifest": {"path": rel_path(manifest_path, root), "sha256": sha256_file(manifest_path)},
        "run": {
            "project_id": manifest.get("project_id"),
            "run_id": manifest.get("run_id"),
            "schema_version": manifest.get("schema_version"),
            "preset": manifest.get("preset"),
            "stage": manifest.get("stage"),
            "status": manifest.get("status"),
        },
        "errors": [],
    }
    state = None
    try:
        state = load_runtime_state(manifest_path, project_root=root, allow_legacy=False)
    except (OSError, ValueError, TypeError, RuntimeStateError) as exc:
        facts["errors"].append(str(exc))
    state_view = runtime.get_state(root)
    payload = state_view.payload
    gates = payload.get("gates", {}) if isinstance(payload.get("gates"), Mapping) else {}
    receipts = payload.get("receipts", {}) if isinstance(payload.get("receipts"), Mapping) else {}
    dag = payload.get("dag", {}) if isinstance(payload.get("dag"), Mapping) else {}
    review = payload.get("review", {}) if isinstance(payload.get("review"), Mapping) else {}
    facts["gates"] = {
        "statuses": {name: view.get("status") for name, view in sorted(gates.items()) if isinstance(view, Mapping)},
        "first_blocked_gate": payload.get("first_blocked_gate"),
    }
    artifacts = dag.get("artifacts", []) if isinstance(dag.get("artifacts"), list) else []
    digests: dict[str, str] = {}
    for row in artifacts:
        if not isinstance(row, Mapping) or not isinstance(row.get("artifact_id"), str):
            continue
        raw = row.get("path")
        if not isinstance(raw, str):
            continue
        path = (root / raw).resolve()
        if path.is_file():
            digests[str(row["artifact_id"])] = sha256_file(path)
    facts["artifacts"] = {
        "ids": sorted(str(row.get("artifact_id")) for row in artifacts if isinstance(row, Mapping)),
        "stale": sorted(str(row.get("artifact_id")) for row in artifacts if isinstance(row, Mapping) and row.get("freshness") != "current"),
        "digests": dict(sorted(digests.items())),
    }
    facts["receipts"] = {
        "count": receipts.get("count", 0),
        "failed_ids": sorted(str(value) for value in receipts.get("failed_receipt_ids", [])),
        "successful_stages": sorted(str(value) for value in receipts.get("successful_stages", [])),
    }
    perspectives = review.get("perspectives", {}) if isinstance(review.get("perspectives"), Mapping) else {}
    facts["review"] = {
        "verdicts": {
            name: view.get("verdict") if isinstance(view, Mapping) else None
            for name, view in sorted(perspectives.items())
        }
    }
    fork_record = root / checkpoints.FORK_RECORD
    if fork_record.is_file():
        try:
            fork = load_structured(fork_record)
        except (OSError, ValueError, TypeError):
            fork = None
        if isinstance(fork, Mapping):
            facts["fork"] = {
                "fork_id": fork.get("fork_id"),
                "parent_root": fork.get("parent_root"),
                "parent_checkpoint": fork.get("parent_checkpoint"),
            }
    facts["checkpoints"] = [row["name"] for row in checkpoints.list_checkpoints(root)]
    if state is None:
        facts["ok"] = False
    return facts


def diff_runs(root_a: Path | str, root_b: Path | str) -> dict[str, Any]:
    """Return the factual difference between two run roots."""

    a = Path(root_a).resolve()
    b = Path(root_b).resolve()
    facts_a = project_facts(a)
    facts_b = project_facts(b)
    documents_a = _root_documents(a, {}) if not facts_a.get("ok") else _root_documents(a, load_structured(resolve_manifest_path(a)))
    documents_b = _root_documents(b, {}) if not facts_b.get("ok") else _root_documents(b, load_structured(resolve_manifest_path(b)))
    roots: dict[str, Any] = {}
    for name in sorted(set(documents_a) | set(documents_b)):
        entry_a = documents_a.get(name, {})
        entry_b = documents_b.get(name, {})
        added: list[str] = []
        removed: list[str] = []
        changed: list[dict[str, Any]] = []
        if "document" in entry_a and "document" in entry_b:
            _leaf_diff(entry_a["document"], entry_b["document"], "$", added, removed, changed)
        roots[name] = {
            "a": {key: entry_a[key] for key in ("path", "sha256", "absent", "error") if key in entry_a},
            "b": {key: entry_b[key] for key in ("path", "sha256", "absent", "error") if key in entry_b},
            "sha256_equal": entry_a.get("sha256") == entry_b.get("sha256"),
            "added": added[:LEAF_DIFF_CAP],
            "removed": removed[:LEAF_DIFF_CAP],
            "changed": changed[:LEAF_DIFF_CAP],
            "truncated": any(len(items) > LEAF_DIFF_CAP for items in (added, removed, changed)),
        }
    digests_a = facts_a.get("artifacts", {}).get("digests", {})
    digests_b = facts_b.get("artifacts", {}).get("digests", {})
    artifact_ids_a = set(facts_a.get("artifacts", {}).get("ids", []))
    artifact_ids_b = set(facts_b.get("artifacts", {}).get("ids", []))
    stale_a = set(facts_a.get("artifacts", {}).get("stale", []))
    stale_b = set(facts_b.get("artifacts", {}).get("stale", []))
    gate_status_a = facts_a.get("gates", {}).get("statuses", {})
    gate_status_b = facts_b.get("gates", {}).get("statuses", {})
    review_a = facts_a.get("review", {}).get("verdicts", {})
    review_b = facts_b.get("review", {}).get("verdicts", {})
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "ok": bool(facts_a.get("ok")) and bool(facts_b.get("ok")),
        "a": facts_a,
        "b": facts_b,
        "roots": roots,
        "artifacts": {
            "added": sorted(artifact_ids_b - artifact_ids_a),
            "removed": sorted(artifact_ids_a - artifact_ids_b),
            "stale_only_in_a": sorted(stale_a - stale_b),
            "stale_only_in_b": sorted(stale_b - stale_a),
            "content_changed": [
                {"artifact_id": artifact_id, "a": digests_a[artifact_id], "b": digests_b[artifact_id]}
                for artifact_id in sorted(set(digests_a) & set(digests_b))
                if digests_a[artifact_id] != digests_b[artifact_id]
            ],
        },
        "gates": {
            "changed": {
                name: {"a": gate_status_a.get(name), "b": gate_status_b.get(name)}
                for name in sorted(set(gate_status_a) | set(gate_status_b))
                if gate_status_a.get(name) != gate_status_b.get(name)
            }
        },
        "receipts": {
            "count_a": facts_a.get("receipts", {}).get("count"),
            "count_b": facts_b.get("receipts", {}).get("count"),
            "failed_only_in_a": sorted(set(facts_a.get("receipts", {}).get("failed_ids", [])) - set(facts_b.get("receipts", {}).get("failed_ids", []))),
            "failed_only_in_b": sorted(set(facts_b.get("receipts", {}).get("failed_ids", [])) - set(facts_a.get("receipts", {}).get("failed_ids", []))),
        },
        "review": {
            "changed": {
                name: {"a": review_a.get(name), "b": review_b.get(name)}
                for name in sorted(set(review_a) | set(review_b))
                if review_a.get(name) != review_b.get(name)
            }
        },
    }


def compare_runs(root_a: Path | str, root_b: Path | str) -> tuple[dict[str, Any], int]:
    """Return the diff plus each side's checkpoint truth, and an exit code."""

    a = Path(root_a).resolve()
    b = Path(root_b).resolve()
    document = diff_runs(a, b)
    problems: list[str] = []
    for side, root in (("a", a), ("b", b)):
        statuses: list[dict[str, Any]] = []
        for row in checkpoints.list_checkpoints(root):
            ok, errors = checkpoints.verify_checkpoint(root, str(row["name"]))
            statuses.append({"name": row["name"], "ok": ok, "errors": errors})
            if not ok:
                problems.extend(f"{side}: {error}" for error in errors)
        document[side]["checkpoints"] = statuses
    document["ok"] = bool(document["ok"]) and not problems
    document["checkpoint_problems"] = sorted(problems)
    return document, (0 if document["ok"] else 1)


def human_summary(document: Mapping[str, Any]) -> str:
    """Render the fact table the way both CLIs print it."""

    lines = [
        f"a: {document['a'].get('run', {}).get('run_id')}  b: {document['b'].get('run', {}).get('run_id')}",
    ]
    for name, entry in document["roots"].items():
        lines.append(f"root {name}: sha256_equal={entry['sha256_equal']} changed={len(entry['changed'])}")
        for change in entry["changed"][:10]:
            lines.append(f"  {change['path']}: {change['a']!r} -> {change['b']!r}")
    content_changed = document["artifacts"]["content_changed"]
    if content_changed:
        lines.append(f"artifact content changed: {len(content_changed)}")
        for row in content_changed[:10]:
            lines.append(f"  {row['artifact_id']}: {row['a'][:12]} -> {row['b'][:12]}")
    lines.append(f"gates changed: {len(document['gates']['changed'])}")
    for name, entry in document["gates"]["changed"].items():
        lines.append(f"  {name}: {entry['a']} -> {entry['b']}")
    if "checkpoint_problems" in document:
        lines.append(f"checkpoint problems: {len(document['checkpoint_problems'])}")
        for problem in document["checkpoint_problems"][:10]:
            lines.append(f"  {problem}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_a")
    parser.add_argument("run_b")
    parser.add_argument("--compare", action="store_true", help="also verify each side's checkpoints")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if args.compare:
        document, code = compare_runs(args.run_a, args.run_b)
    else:
        document = diff_runs(args.run_a, args.run_b)
        code = 0 if document["ok"] else 1
    print(json.dumps(document, ensure_ascii=False) if args.json else human_summary(document))
    return code


if __name__ == "__main__":
    raise SystemExit(main())