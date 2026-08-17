#!/usr/bin/env python3
"""Explicit, non-destructive v1 -> v2 migration command.

Examples:
    python scripts/migrate_v1_to_v2.py --project path/to/project
    python scripts/migrate_v1_to_v2.py --project path/to/project --output-dir path/to/project/migration_v2 --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from profiles.normalization import NormalizationError, migrate_project  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, help="Legacy project root")
    parser.add_argument("--manifest", default=None, help="Manifest path relative to --project (default: run_manifest.json)")
    parser.add_argument("--output-dir", default=None, help="Separate output directory (default: <project>/migration_v2)")
    parser.add_argument("--no-write", action="store_true", help="Only print the migration report; do not write v2 files")
    parser.add_argument("--json", action="store_true", help="Emit the complete machine-readable migration bundle")
    args = parser.parse_args(argv)
    try:
        bundle = migrate_project(
            args.project,
            manifest_path=args.manifest,
            output_dir=args.output_dir,
            write=not args.no_write,
        )
    except (OSError, ValueError, NormalizationError, json.JSONDecodeError) as exc:
        payload = {"status": "error", "errors": [str(exc)]}
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 2
    if args.json:
        print(json.dumps(bundle, ensure_ascii=False, indent=2))
    else:
        report = bundle["report"]
        print(json.dumps(report, ensure_ascii=False, indent=2))
        if bundle.get("output_paths"):
            print("Wrote v2 documents:")
            for name, path in sorted(bundle["output_paths"].items()):
                print(f"  {name}: {path}")
    return 0 if report.get("status") == "migrated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
