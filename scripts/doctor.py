#!/usr/bin/env python3
"""Check whether the core competition workflow is runnable before going offline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from doctor_core import STAGES, evaluate_capabilities, probe_command  # noqa: E402


REQUIRED_COMMANDS = ("git", "latexmk", "xelatex", "lualatex", "pdfinfo", "pdffonts", "pdftoppm")


def command_version(command: str) -> dict[str, object]:
    row = probe_command(command)
    return {"available": row["status"] == "available", "path": row["path"], "version": row["version"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--template-manifest", default="vendor/template_sources.json")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--stage", choices=STAGES, help="evaluate only the capabilities required by one workflow stage")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    capability_report = evaluate_capabilities(
        root,
        stage=args.stage,
        repo_root=SCRIPT_DIR.parent,
        strict_commands=args.stage is None,
    )
    commands = {name: command_version(name) for name in REQUIRED_COMMANDS}
    errors = list(capability_report["errors"])
    manifest_path = root / args.template_manifest
    templates = []
    if not manifest_path.is_file():
        errors.append(f"template source manifest missing: {args.template_manifest}")
    else:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for source in manifest.get("sources", []):
                raw_clone_path = source.get("clone_path")
                if not raw_clone_path:
                    templates.append({
                        "source_id": source["source_id"],
                        "present": None,
                        "commit": None,
                        "locked": None,
                        "status": "page_only",
                    })
                    continue
                clone_path = root / raw_clone_path
                present = clone_path.is_dir()
                commit = None
                if present:
                    result = subprocess.run(["git", "-C", str(clone_path), "rev-parse", "HEAD"], text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
                    commit = result.stdout.strip() if result.returncode == 0 else None
                locked = present and commit == source["commit"]
                templates.append({
                    "source_id": source["source_id"],
                    "present": present,
                    "commit": commit,
                    "locked": locked,
                    "status": "locked" if locked else "missing_or_unlocked",
                })
                if args.offline and not locked and source.get("license", {}).get("status") != "pending_clone_audit":
                    errors.append(f"offline required clone is missing or unlocked: {source['source_id']}")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"cannot inspect template manifest: {exc}")

    schema_count = len(list((root / "schemas").glob("*.schema.json")))
    if schema_count == 0:
        errors.append("no schemas found")
    report = {
        "ok": not errors,
        "offline": args.offline,
        "python": {"path": sys.executable, "version": sys.version.split()[0]},
        "commands": commands,
        "capabilities": capability_report["capabilities"],
        "stages": capability_report["stages"],
        "stage": args.stage,
        "templates": templates,
        "schema_count": schema_count,
        "warnings": capability_report["warnings"],
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
