#!/usr/bin/env python3
"""Create a sanitized CUMCM LaTeX project that really uses cumcmthesis."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path  # noqa: E402


PINNED_COMMIT = "90d3e854534ae7dc605dfe9296785f8c17e56e22"


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def write_new(path: Path, text: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--problem", required=True, help="Problem letter, for example C")
    parser.add_argument("--keywords", required=True, help="Semicolon-separated paper keywords")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--month", type=int, required=True)
    parser.add_argument("--day", type=int, required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--vendor-root", default="vendor/upstream/CUMCMThesis")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    destination = resolve_path(args.destination, root).resolve()
    vendor_root = resolve_path(args.vendor_root, root).resolve()
    skeleton_root = Path(__file__).resolve().parents[2] / "assets" / "templates" / "cumcm-2026-electronic"
    errors: list[str] = []
    try:
        destination.relative_to(root)
    except ValueError:
        errors.append("destination must stay inside project_root")
    if not (vendor_root / "cumcmthesis.cls").is_file():
        errors.append("vendor CUMCMThesis class is unavailable; run vendor/clone_templates.ps1 first")
    else:
        result = subprocess.run(
            ["git", "-C", str(vendor_root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != PINNED_COMMIT:
            errors.append(
                f"vendor CUMCMThesis must be pinned to {PINNED_COMMIT}; got {result.stdout.strip() or 'unverified'}"
            )
    if args.problem.strip().upper() not in set("ABCDEF"):
        errors.append("problem must be one letter A-F")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    try:
        destination.mkdir(parents=True, exist_ok=True)
        for name in ("main.tex", "template_contract.json"):
            source = skeleton_root / name
            target = destination / name
            if target.exists() and not args.force:
                raise FileExistsError(f"refusing to overwrite existing file: {target}; pass --force")
            shutil.copy2(source, target)
        class_target = destination / "cumcmthesis.cls"
        if class_target.exists() and not args.force:
            raise FileExistsError(f"refusing to overwrite existing file: {class_target}; pass --force")
        shutil.copy2(vendor_root / "cumcmthesis.cls", class_target)
        keyword_text = r"\quad ".join(
            latex_escape(item.strip()) for item in args.keywords.split(";") if item.strip()
        )
        metadata = (
            f"\\title{{{latex_escape(args.title)}}}\n"
            f"\\tihao{{{args.problem.strip().upper()}}}\n"
            "\\baominghao{}\n\\schoolname{}\n\\membera{}\n\\memberb{}\n\\memberc{}\n\\supervisor{}\n"
            f"\\yearinput{{{args.year}}}\n\\monthinput{{{args.month}}}\n\\dayinput{{{args.day}}}\n"
            f"\\newcommand{{\\PaperKeywords}}{{{keyword_text}}}\n"
        )
        write_new(destination / "metadata.tex", metadata, force=args.force)
        write_new(
            destination / "sections" / "abstract.tex",
            "% Generated only after paper_plan reaches technical_draft readiness.\n",
            force=args.force,
        )
        write_new(
            destination / "sections" / "body.tex",
            "% Writer package content is inserted here; do not bypass the evidence package.\n",
            force=args.force,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        "ok": True,
        "destination": rel_path(destination, root),
        "entrypoint": rel_path(destination / "main.tex", root),
        "template_contract": rel_path(destination / "template_contract.json", root),
        "source_commit": PINNED_COMMIT,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
