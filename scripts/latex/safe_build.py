#!/usr/bin/env python3
"""Compile LaTeX in an isolated copy with shell escape disabled and emit a receipt."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path, sha256_file, write_json  # noqa: E402
from latex.template_usage import validate_template_usage  # noqa: E402


BLOCKED_TOKENS = (r"\write18", r"\immediate\write18", r"\input|", r"\openout18", r"\usepackage{shellesc}")
PATH_COMMAND_RE = re.compile(r"\\(?:input|include|includegraphics|bibliography|addbibresource)\s*(?:\[[^\]]*\]\s*)?\{([^}]+)\}")
SOURCE_EXTENSIONS = {
    ".tex", ".bib", ".cls", ".sty", ".bst", ".cfg", ".def",
    ".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg",
    ".py", ".m", ".r", ".jl", ".c", ".cc", ".cpp", ".h", ".hpp", ".java", ".txt",
}


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file() and ".git" not in item.parts):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def scan_sources(root: Path) -> list[str]:
    errors = []
    for path in root.rglob("*.tex"):
        text = path.read_text(encoding="utf-8", errors="replace")
        for token in BLOCKED_TOKENS:
            if token.casefold() in text.casefold():
                errors.append(f"blocked LaTeX token {token!r} in {path.relative_to(root).as_posix()}")
        for match in PATH_COMMAND_RE.finditer(text):
            for raw_target in match.group(1).split(","):
                target = raw_target.strip()
                if not target or target.startswith(("http://", "https://")):
                    continue
                normalized = target.replace("\\", "/")
                drive_like = len(normalized) >= 2 and normalized[1] == ":"
                if normalized.startswith("/") or drive_like or ".." in Path(normalized).parts:
                    errors.append(
                        f"LaTeX path escapes source root in {path.relative_to(root).as_posix()}: {target}"
                    )
    return errors


def copy_project(source: Path, destination: Path) -> None:
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        if ".git" in relative.parts or "build" in relative.parts:
            continue
        target = destination / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.suffix.lower() in SOURCE_EXTENSIONS:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--entrypoint", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--engine", choices=("xelatex", "lualatex", "pdflatex"), default="xelatex")
    parser.add_argument("--integrity-mode", choices=("dev", "research", "submission"), default="research")
    parser.add_argument("--template-contract")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    source_root = resolve_path(args.source_root, project_root).resolve()
    entrypoint = Path(args.entrypoint)
    output_path = resolve_path(args.output, project_root).resolve()
    receipt_path = resolve_path(args.receipt, project_root).resolve()
    errors: list[str] = []
    template_contract = None
    template_contract_path = None
    try:
        source_root.relative_to(project_root)
    except ValueError:
        errors.append("source_root must stay inside project_root")
    if entrypoint.is_absolute() or ".." in entrypoint.parts or entrypoint.suffix.lower() != ".tex":
        errors.append("entrypoint must be a relative .tex path without parent traversal")
    if not (source_root / entrypoint).is_file():
        errors.append(f"entrypoint does not exist: {entrypoint}")
    errors.extend(scan_sources(source_root) if source_root.is_dir() else [])
    if args.template_contract:
        template_contract_path = resolve_path(args.template_contract, project_root).resolve()
        try:
            template_contract, template_errors, template_warnings = validate_template_usage(
                template_contract_path,
                source_root,
                entrypoint,
                args.engine,
                require_verified=args.integrity_mode in {"research", "submission"},
            )
            errors.extend(template_errors)
            if template_warnings and args.integrity_mode in {"research", "submission"}:
                errors.extend(template_warnings)
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            errors.append(f"cannot validate template contract: {exc}")
    elif args.integrity_mode in {"research", "submission"}:
        errors.append("research/submission build requires --template-contract")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    source_before = tree_hash(source_root) if args.integrity_mode == "submission" else None
    command: list[str] = []
    exit_code = 1
    output_ref = log_ref = None
    run_stdout = ""
    run_stderr = ""
    with tempfile.TemporaryDirectory(prefix="mathmodel-latex-") as temporary:
        isolated = Path(temporary) / "source"
        isolated.mkdir(parents=True)
        copy_project(source_root, isolated)
        command = [
            "latexmk", f"-{args.engine}", "-interaction=nonstopmode", "-halt-on-error",
            "-file-line-error", "-no-shell-escape", str(entrypoint.as_posix()),
        ]
        environment = os.environ.copy()
        environment["openin_any"] = "p"
        environment["openout_any"] = "p"
        result = subprocess.run(
            command, cwd=isolated, env=environment, text=True, capture_output=True,
            encoding="utf-8", errors="replace", check=False,
        )
        exit_code = result.returncode
        run_stdout = result.stdout
        run_stderr = result.stderr
        log_path = isolated / entrypoint.with_suffix(".log")
        pdf_path = isolated / entrypoint.with_suffix(".pdf")
        if log_path.is_file():
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            copied_log = receipt_path.with_suffix(".log")
            if copied_log.exists() and not args.force:
                raise FileExistsError(f"refusing to overwrite existing file: {copied_log}; pass --force")
            shutil.copy2(log_path, copied_log)
            log_ref = {"path": rel_path(copied_log, project_root)}
            if args.integrity_mode == "submission":
                log_ref["sha256"] = sha256_file(copied_log)
        else:
            receipt_path.parent.mkdir(parents=True, exist_ok=True)
            copied_log = receipt_path.with_suffix(".log")
            if copied_log.exists() and not args.force:
                raise FileExistsError(f"refusing to overwrite existing file: {copied_log}; pass --force")
            copied_log.write_text(run_stdout + "\n--- STDERR ---\n" + run_stderr, encoding="utf-8")
            log_ref = {"path": rel_path(copied_log, project_root)}
            if args.integrity_mode == "submission":
                log_ref["sha256"] = sha256_file(copied_log)
        if result.returncode == 0 and pdf_path.is_file():
            output_path.parent.mkdir(parents=True, exist_ok=True)
            if output_path.exists() and not args.force:
                raise FileExistsError(f"refusing to overwrite existing file: {output_path}; pass --force")
            shutil.copy2(pdf_path, output_path)
            output_ref = {"path": rel_path(output_path, project_root)}
            if args.integrity_mode == "submission":
                output_ref["sha256"] = sha256_file(output_path)

    source_after = tree_hash(source_root) if args.integrity_mode == "submission" else None
    source_unchanged = source_before == source_after if args.integrity_mode == "submission" else True
    template_ref = None
    if isinstance(template_contract, dict) and template_contract_path is not None:
        template_ref = {
            "contract": rel_path(template_contract_path, project_root),
            "template_id": template_contract["template_id"],
            "document_class": template_contract["document_class"],
            "verified": template_contract.get("status") == "verified",
        }
        if args.integrity_mode == "submission":
            template_ref["sha256"] = sha256_file(template_contract_path)
    receipt = {
        "schema_version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "integrity_mode": args.integrity_mode,
        "engine": args.engine,
        "source_root": rel_path(source_root, project_root),
        "entrypoint": entrypoint.as_posix(),
        "template": template_ref,
        "source_tree_sha256_before": source_before,
        "source_tree_sha256_after": source_after,
        "command": command,
        "shell_escape": False,
        "output": output_ref,
        "log": log_ref,
        "exit_code": exit_code,
        "source_unchanged": source_unchanged,
        "ok": exit_code == 0 and output_ref is not None and source_unchanged,
    }
    try:
        write_json(receipt_path, receipt, overwrite=args.force)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": receipt["ok"], "receipt": rel_path(receipt_path, project_root), "output": output_ref}, ensure_ascii=False))
    return 0 if receipt["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
