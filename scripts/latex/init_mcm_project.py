#!/usr/bin/env python3
"""Create a sanitized MCM/ICM LaTeX project that uses mcmthesis."""

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

PINNED_COMMIT = "8ac05e2c3a9ef5880a15e3a3a18762a546c10b69"


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
    parser.add_argument("--control-number", default="2600000", help="MCM/ICM Control Number")
    parser.add_argument("--keywords", required=True, help="Comma- or semicolon-separated keywords")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--vendor-root", default="vendor/upstream/mcmthesis")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    destination = resolve_path(args.destination, root).resolve()
    vendor_root = resolve_path(args.vendor_root, root).resolve()
    skeleton_root = Path(__file__).resolve().parents[2] / "assets" / "templates" / "mcm-icm-2026"
    errors: list[str] = []

    try:
        destination.relative_to(root)
    except ValueError:
        errors.append("destination must stay inside project_root")

    cls_file = vendor_root / "mcmthesis.cls"
    if not cls_file.is_file():
        # Try generating from dtx if present
        dtx_file = vendor_root / "mcmthesis.dtx"
        if dtx_file.is_file():
            subprocess.run(["xetex", "mcmthesis.dtx"], cwd=vendor_root, capture_output=True, text=True, check=False)
        if not cls_file.is_file():
            errors.append("vendor mcmthesis class is unavailable; run vendor/clone_templates.ps1 first")

    if cls_file.is_file():
        result = subprocess.run(
            ["git", "-C", str(vendor_root), "rev-parse", "HEAD"],
            text=True,
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0 or result.stdout.strip() != PINNED_COMMIT:
            errors.append(
                f"vendor mcmthesis must be pinned to {PINNED_COMMIT}; got {result.stdout.strip() or 'unverified'}"
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

        class_target = destination / "mcmthesis.cls"
        if class_target.exists() and not args.force:
            raise FileExistsError(f"refusing to overwrite existing file: {class_target}; pass --force")
        shutil.copy2(cls_file, class_target)

        raw_kws = [item.strip() for item in args.keywords.replace(";", ",").split(",") if item.strip()]
        keyword_text = ", ".join(latex_escape(k) for k in raw_kws)

        metadata = (
            f"\\title{{{latex_escape(args.title)}}}\n"
            "\\author{}\n"
            f"\\newcommand{{\\ProblemLetter}}{{{args.problem.strip().upper()}}}\n"
            f"\\newcommand{{\\ControlNumber}}{{{latex_escape(args.control_number)}}}\n"
            f"\\newcommand{{\\PaperKeywords}}{{{keyword_text}}}\n"
        )
        write_new(destination / "metadata.tex", metadata, force=args.force)
        write_new(
            destination / "sections" / "abstract.tex",
            "% MCM/ICM Summary Sheet Abstract.\n"
            "% Generated only after paper_plan reaches technical_draft readiness.\n",
            force=args.force,
        )
        write_new(
            destination / "sections" / "body.tex",
            "% Main Paper Body (Introduction, Assumptions, Models, Results, Sensitivity, Strengths & Weaknesses).\n",
            force=args.force,
        )
        write_new(
            destination / "sections" / "ai_report.tex",
            "\\section*{Report on Use of AI}\n"
            "% Required for MCM/ICM when AI tools are used. Does not count toward the 25-page limit.\n",
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
