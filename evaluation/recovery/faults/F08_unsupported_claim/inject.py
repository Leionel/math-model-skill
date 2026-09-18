#!/usr/bin/env python3
"""Inject F08: add an unevidenced claim, refresh the DAG digest, and re-review.

The DAG refresh and fresh review isolate the deterministic content-QA refusal
from the stale-review refusal that any edit would also trigger; without them
the W2 verdict could not attribute the blocker to the claim itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

FAULT_DIR = Path(__file__).resolve().parent
REPO_ROOT = FAULT_DIR.parents[2]
STUB_REVIEWER = REPO_ROOT / "tests" / "fixtures" / "review_stub" / "stub_reviewer.py"
CLAIM = "The savings reach 40 percent against the industry average.\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True)
    args = parser.parse_args()
    root = Path(args.project_root)
    abstract = root / "abstract.txt"
    dag_path = root / "artifact_dag.json"
    if not abstract.is_file() or not dag_path.is_file():
        print(json.dumps({"ok": False, "fault_id": "F08", "errors": ["abstract.txt or artifact_dag.json missing; wrong fixture?"]}, ensure_ascii=False))
        return 2
    if CLAIM in abstract.read_text(encoding="utf-8"):
        print(json.dumps({"ok": False, "fault_id": "F08", "errors": ["claim already present; inject is not idempotent-safe to repeat"]}, ensure_ascii=False))
        return 2
    abstract.write_text(abstract.read_text(encoding="utf-8") + CLAIM, encoding="utf-8")
    dag = json.loads(dag_path.read_text(encoding="utf-8"))
    refreshed = 0
    for node in dag.get("nodes", []):
        if node.get("role") == "abstract":
            node["sha256"] = hashlib.sha256(abstract.read_bytes()).hexdigest()
            refreshed += 1
    if refreshed != 1:
        print(json.dumps({"ok": False, "fault_id": "F08", "errors": [f"expected exactly one abstract DAG node, found {refreshed}"]}, ensure_ascii=False))
        return 2
    dag_path.write_text(json.dumps(dag, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    review = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "harness.py"), "review", "--project", str(root),
         "--fresh", "--backend-cmd", f'"{sys.executable}" "{STUB_REVIEWER}"', "--backend-kind", "non_ai", "--json"],
        cwd=REPO_ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
    )
    print(json.dumps({"ok": True, "fault_id": "F08",
                      "mutations": [{"path": "abstract.txt", "action": "appended unevidenced claim"},
                                    {"path": "artifact_dag.json", "action": "refreshed abstract digest"},
                                    {"tool": "harness review", "exit_code": review.returncode}]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
