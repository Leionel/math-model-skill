#!/usr/bin/env python3
"""Import a complete user-supplied LaTeX template without discarding its assets.

The importer copies the usable template tree, preserves the original preamble and
document class, replaces only the sample document body, and records the retained
assets in ``template_contract.json``. The imported project starts in ``draft``
status: a current competition profile plus a real PDF build/review are still
required before it can be promoted to a formal template.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path, sha256_file, write_json  # noqa: E402


DOCUMENT_CLASS_RE = re.compile(r"\\documentclass\s*(?:\[[^\]]*\]\s*)?\{([^}]+)\}")
BEGIN_DOCUMENT_RE = re.compile(r"\\begin\s*\{document\}")
END_DOCUMENT_RE = re.compile(r"\\end\s*\{document\}")
IGNORED_DIRECTORY_NAMES = {".git", "build", "_build", "__pycache__"}
IGNORED_FILE_SUFFIXES = {".aux", ".bbl", ".blg", ".fdb_latexmk", ".fls", ".log", ".out", ".synctex.gz", ".toc"}
TEMPLATE_SOURCE_EXTENSIONS = {
    ".tex", ".bib", ".cls", ".sty", ".bst", ".bbx", ".cbx", ".lbx", ".cfg", ".def", ".fd",
    ".png", ".jpg", ".jpeg", ".pdf", ".eps", ".svg", ".tikz", ".pgf", ".pgfplots",
    ".ttf", ".otf", ".ttc", ".otc", ".woff", ".woff2",
    ".csv", ".tsv", ".dat", ".txt", ".json", ".yaml", ".yml", ".xml",
    ".py", ".m", ".r", ".jl", ".c", ".cc", ".cpp", ".h", ".hpp", ".java", ".lua",
}


def latex_escape(value: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
        "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(character, character) for character in value)


def _relative_source_path(path: Path, root: Path) -> Path:
    relative = path.relative_to(root)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"template path escapes root: {path}")
    return relative


def _is_usable_source(path: Path, relative: Path) -> bool:
    if any(part in IGNORED_DIRECTORY_NAMES for part in relative.parts):
        return False
    lower_name = path.name.casefold()
    if any(lower_name.endswith(suffix) for suffix in IGNORED_FILE_SUFFIXES):
        return False
    return path.suffix.casefold() in TEMPLATE_SOURCE_EXTENSIONS


def _find_entrypoint(template_root: Path, explicit: str | None) -> Path:
    if explicit:
        relative = Path(explicit)
        if relative.is_absolute() or ".." in relative.parts or relative.suffix.casefold() != ".tex":
            raise ValueError("--entrypoint must be a relative .tex path within --template-root")
        candidate = template_root / relative
        if not candidate.is_file():
            raise ValueError(f"template entrypoint does not exist: {relative.as_posix()}")
        return candidate

    candidates = []
    for path in template_root.rglob("*.tex"):
        relative = _relative_source_path(path, template_root)
        if not _is_usable_source(path, relative):
            continue
        text = path.read_text(encoding="utf-8-sig", errors="replace")
        if DOCUMENT_CLASS_RE.search(text):
            candidates.append(path)
    if not candidates:
        raise ValueError("could not find a .tex entrypoint containing \\documentclass; pass --entrypoint")
    preferred_names = ("main.tex", "template.tex", "mcmthesis.tex", "cumcmthesis.tex")
    for name in preferred_names:
        matches = [candidate for candidate in candidates if candidate.name.casefold() == name]
        if len(matches) == 1:
            return matches[0]
    if len(candidates) != 1:
        rendered = ", ".join(_relative_source_path(path, template_root).as_posix() for path in candidates)
        raise ValueError(f"multiple template entrypoints found ({rendered}); pass --entrypoint")
    return candidates[0]


def _replace_command_argument(text: str, command: str, replacement: str) -> tuple[str, bool]:
    pattern = re.compile(rf"(\\{command}\s*)\{{[^{{}}]*\}}")
    updated, count = pattern.subn(lambda match: f"{match.group(1)}{{{replacement}}}", text, count=1)
    return updated, count == 1


def _replace_key_assignment(text: str, key: str, replacement: str) -> tuple[str, bool]:
    pattern = re.compile(rf"(\b{re.escape(key)}\s*=\s*)([^,\n}}]+)", flags=re.IGNORECASE)
    updated, count = pattern.subn(lambda match: f"{match.group(1)}{replacement}", text, count=1)
    return updated, count == 1


def _adapt_preamble(text: str, family: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if family in {"mcm_icm", "cumcm"}:
        text, title_replaced = _replace_command_argument(text, "title", r"\HarnessTitle")
        if not title_replaced:
            warnings.append("could not replace an existing \\title{...}; check the copied template title manually")
    if family == "mcm_icm":
        text, problem_replaced = _replace_key_assignment(text, "problem", r"\HarnessProblem")
        text, control_replaced = _replace_key_assignment(text, "tcn", r"\HarnessControlNumber")
        if not problem_replaced:
            warnings.append("could not replace mcmsetup problem=...; check the copied template manually")
        if not control_replaced:
            warnings.append("could not replace mcmsetup tcn=...; check the copied template manually")
    if family == "cumcm":
        text, problem_replaced = _replace_command_argument(text, "tihao", r"\HarnessProblem")
        if not problem_replaced:
            warnings.append("could not replace \\tihao{...}; check the copied template manually")
    return text, warnings


def _replace_document_body(text: str) -> str:
    document_class = DOCUMENT_CLASS_RE.search(text)
    begin = BEGIN_DOCUMENT_RE.search(text)
    end_matches = list(END_DOCUMENT_RE.finditer(text))
    if document_class is None or begin is None or len(end_matches) != 1 or end_matches[0].start() <= begin.end():
        raise ValueError("entrypoint must contain one well-ordered \\begin{document} ... \\end{document} block")
    end = end_matches[0]
    metadata = "\n% Harness metadata: generated from trusted inputs.\n\\input{harness/metadata.tex}\n"
    text = text[:document_class.end()] + metadata + text[document_class.end():]
    begin = BEGIN_DOCUMENT_RE.search(text)
    end = END_DOCUMENT_RE.search(text)
    assert begin is not None and end is not None
    body = "\n% Harness body: replaces template demonstration content only.\n\\input{harness/body.tex}\n"
    return text[:begin.end()] + body + text[end.start():]


def _metadata_tex(args: argparse.Namespace) -> str:
    keyword_text = ", ".join(
        latex_escape(item.strip())
        for item in args.keywords.replace(";", ",").split(",")
        if item.strip()
    )
    lines = [
        f"\\newcommand{{\\HarnessTitle}}{{{latex_escape(args.title)}}}",
        f"\\newcommand{{\\HarnessProblem}}{{{latex_escape(args.problem.strip().upper())}}}",
        f"\\newcommand{{\\HarnessControlNumber}}{{{latex_escape(args.control_number)}}}",
        f"\\newcommand{{\\HarnessKeywords}}{{{keyword_text}}}",
        "\\providecommand{\\PaperKeywords}{\\HarnessKeywords}",
        "\\providecommand{\\ProblemLetter}{\\HarnessProblem}",
        "\\providecommand{\\ControlNumber}{\\HarnessControlNumber}",
    ]
    if args.family == "mcm_icm":
        lines.append("\\author{}")
    return "\n".join(lines) + "\n"


def _body_tex(family: str) -> str:
    if family == "mcm_icm":
        return """\\begin{abstract}
\\input{sections/abstract.tex}
\\begin{keywords}
\\HarnessKeywords
\\end{keywords}
\\end{abstract}

\\maketitle
\\input{sections/body.tex}

\\ifdefined\\AImatter
\\AImatter
\\fi
\\input{sections/ai_report.tex}
"""
    if family == "cumcm":
        return """\\maketitle

\\begin{abstract}
\\input{sections/abstract.tex}
\\keywords{\\HarnessKeywords}
\\end{abstract}

\\input{sections/body.tex}
"""
    return "\\input{sections/body.tex}\n"


def _write_new(path: Path, content: str, *, force: bool) -> None:
    if path.exists() and not force:
        raise FileExistsError(f"refusing to overwrite existing file: {path}; pass --force")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy_template_tree(template_root: Path, destination: Path, entrypoint_relative: Path, *, force: bool) -> tuple[dict[str, str], list[str]]:
    asset_hashes: dict[str, str] = {}
    copied: list[str] = []
    for path in sorted(item for item in template_root.rglob("*") if item.is_file()):
        relative = _relative_source_path(path, template_root)
        if not _is_usable_source(path, relative):
            continue
        target = destination / relative
        if target.exists() and not force:
            raise FileExistsError(f"refusing to overwrite existing file: {target}; pass --force")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        copied.append(relative.as_posix())
        if relative != entrypoint_relative:
            asset_hashes[relative.as_posix()] = sha256_file(path)
    return asset_hashes, copied


def _tree_hash(root: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = _relative_source_path(path, root)
        if not _is_usable_source(path, relative):
            continue
        encoded = relative.as_posix().encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(bytes.fromhex(sha256_file(path)))
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--template-root", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--competition-profile", required=True)
    parser.add_argument("--family", choices=("mcm_icm", "cumcm", "generic"), required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--keywords", required=True)
    parser.add_argument("--control-number", default="")
    parser.add_argument("--entrypoint")
    parser.add_argument("--engine", choices=("xelatex", "lualatex", "pdflatex"), default="xelatex")
    parser.add_argument("--allowed-engine", action="append", choices=("xelatex", "lualatex", "pdflatex"))
    parser.add_argument("--source-locator", default="user-supplied local template")
    parser.add_argument("--template-status", choices=("draft", "verified"), default="draft")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    project_root = Path(args.project_root).resolve()
    template_root = Path(args.template_root).resolve()
    destination = resolve_path(args.destination, project_root).resolve()
    errors: list[str] = []
    if not template_root.is_dir():
        errors.append(f"template_root is not a directory: {template_root}")
    try:
        destination.relative_to(project_root)
    except ValueError:
        errors.append("destination must stay inside project_root")
    try:
        destination.relative_to(template_root)
        errors.append("destination must not be inside template_root")
    except ValueError:
        pass
    if not args.problem.strip():
        errors.append("problem must not be blank")
    if errors:
        print(json.dumps({"ok": False, "errors": errors}, ensure_ascii=False, indent=2))
        return 1

    try:
        entrypoint_source = _find_entrypoint(template_root, args.entrypoint)
        entrypoint_relative = _relative_source_path(entrypoint_source, template_root)
        original_text = entrypoint_source.read_text(encoding="utf-8-sig", errors="replace")
        class_match = DOCUMENT_CLASS_RE.search(original_text)
        if class_match is None:
            raise ValueError("entrypoint has no detectable \\documentclass declaration")
        document_class = class_match.group(1).strip()
        adapted_text, warnings = _adapt_preamble(original_text, args.family)
        adapted_text = _replace_document_body(adapted_text)

        destination.mkdir(parents=True, exist_ok=True)
        asset_hashes, copied_files = _copy_template_tree(template_root, destination, entrypoint_relative, force=args.force)
        _write_new(destination / entrypoint_relative, adapted_text, force=True)
        _write_new(destination / "harness" / "metadata.tex", _metadata_tex(args), force=args.force)
        _write_new(destination / "harness" / "body.tex", _body_tex(args.family), force=args.force)
        _write_new(destination / "sections" / "abstract.tex", "% Generated only from the writer package.\n", force=args.force)
        _write_new(destination / "sections" / "body.tex", "% Generated only from the writer package.\n", force=args.force)
        if args.family == "mcm_icm":
            _write_new(
                destination / "sections" / "ai_report.tex",
                "\\section*{Report on Use of AI}\n% Populate from the run manifest and current contest policy.\n",
                force=args.force,
            )

        generated_files = ["harness/metadata.tex", "harness/body.tex", "sections/abstract.tex", "sections/body.tex"]
        if args.family == "mcm_icm":
            generated_files.append("sections/ai_report.tex")
        allowed_engines = args.allowed_engine or (["xelatex", "pdflatex"] if args.family == "mcm_icm" else [args.engine])
        contract: dict[str, Any] = {
            "schema_version": "1.0",
            "template_id": args.template_id,
            "competition_profile_id": args.competition_profile,
            "source_kind": "user_supplied",
            "source_locator": args.source_locator,
            "status": args.template_status,
            "document_class": document_class,
            "entrypoint": entrypoint_relative.as_posix(),
            "required_files": sorted(set(copied_files + generated_files)),
            "required_commands": ["\\documentclass", "\\input{harness/metadata.tex}", "\\input{harness/body.tex}"],
            "forbidden_document_classes": [] if args.family == "generic" else ["article", "ctexart", "report", "book"],
            "allowed_engines": list(dict.fromkeys(allowed_engines)),
            "notes": "User-supplied template: source preamble and compatible assets are retained; only demonstration body content is replaced.",
            "adapter": {
                "family": args.family,
                "body_mode": "replace_demo_body",
                "metadata_input": "harness/metadata.tex",
                "body_input": "harness/body.tex",
            },
            "template_snapshot": {
                "source_file_count": len(copied_files),
                "source_tree_sha256": _tree_hash(template_root),
                "asset_hashes": asset_hashes,
            },
        }
        write_json(destination / "template_contract.json", contract, overwrite=args.force)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        "ok": True,
        "destination": rel_path(destination, project_root),
        "entrypoint": entrypoint_relative.as_posix(),
        "template_contract": rel_path(destination / "template_contract.json", project_root),
        "status": args.template_status,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
