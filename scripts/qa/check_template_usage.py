#!/usr/bin/env python3
"""Verify that LaTeX sources actually use their declared competition template."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path  # noqa: E402
from latex.template_usage import validate_template_usage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-contract", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--engine", choices=("xelatex", "lualatex", "pdflatex"), default="xelatex")
    parser.add_argument("--integrity-mode", choices=("dev", "research", "submission"), default="research")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    contract_path = resolve_path(args.template_contract, root).resolve()
    source_root = resolve_path(args.source_root, root).resolve()
    entrypoint = Path(args.entrypoint)
    errors: list[str] = []
    warnings: list[str] = []
    if entrypoint.is_absolute() or ".." in entrypoint.parts or entrypoint.suffix.lower() != ".tex":
        errors.append("entrypoint must be a relative .tex path without parent traversal")
        contract = None
    else:
        try:
            contract, usage_errors, usage_warnings = validate_template_usage(
                contract_path,
                source_root,
                entrypoint,
                args.engine,
                require_verified=args.integrity_mode in {"research", "submission"},
            )
            errors.extend(usage_errors)
            warnings.extend(usage_warnings)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            contract = None
            errors.append(str(exc))
    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "template_contract": rel_path(contract_path, root),
        "template_id": contract.get("template_id") if isinstance(contract, dict) else None,
        "source_root": rel_path(source_root, root),
        "entrypoint": entrypoint.as_posix(),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
