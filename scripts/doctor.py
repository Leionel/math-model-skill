#!/usr/bin/env python3
"""Check whether the core competition workflow is runnable before going offline."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


REQUIRED_COMMANDS = ("git", "latexmk", "xelatex", "lualatex", "pdfinfo", "pdffonts", "pdftoppm")


def command_version(command: str) -> dict[str, object]:
    path = shutil.which(command)
    if path is None:
        return {"available": False, "path": None, "version": None}
    attempts = ([command, "--version"], [command, "-version"])
    version = None
    for argv in attempts:
        result = subprocess.run(argv, text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
        if result.returncode == 0:
            version = (result.stdout or result.stderr).splitlines()[0] if (result.stdout or result.stderr) else "available"
            break
    return {"available": True, "path": path, "version": version}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--template-manifest", default="vendor/template_sources.json")
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    commands = {name: command_version(name) for name in REQUIRED_COMMANDS}
    errors = [f"required command missing: {name}" for name, row in commands.items() if not row["available"]]
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
        "templates": templates,
        "schema_count": schema_count,
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
