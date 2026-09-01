#!/usr/bin/env python3
"""Check that the rendered PDF carries the current scoped math anchors."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402
from qa.check_formula_replay import evaluate_formula_replay  # noqa: E402
from qa.check_scope_consistency import evaluate_scope_consistency  # noqa: E402
from qa.reader_integrity import collect_registered_internal_ids, exposed_identifiers  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


MODEL_SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "model_contract.schema.json"


def _extract_text(pdf_path: Path) -> tuple[str, str | None]:
    executable = shutil.which("pdftotext")
    if executable is None:
        return "", "pdftotext is unavailable"
    result = subprocess.run(
        [executable, "-layout", str(pdf_path), "-"],
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        return "", result.stderr.strip() or result.stdout.strip() or "pdftotext failed"
    return result.stdout, None


def _source_files(source_path: Path) -> list[Path]:
    if source_path.is_file():
        return [source_path]
    if not source_path.is_dir():
        return []
    return [path for path in source_path.rglob("*") if path.is_file() and path.suffix.casefold() in {".tex", ".bib", ".md"}]


def check_numeric_presence(frozen_results: dict[str, Any], pdf_text: str) -> tuple[list[str], list[str], dict[str, Any]]:
    """Verify every frozen display value is present in the extracted PDF text.

    Whitespace is stripped on both sides so line-wrapped numbers still match.
    The canonical display string is the contract: a frozen "13.00" must appear
    as "13.00" (or wrapped); a bare "13" does not satisfy it.
    """

    import re

    if not isinstance(frozen_results, dict):
        return (["frozen-results must be an object"], [], {"checked": 0})
    normalized = re.sub(r"\s+", "", pdf_text)
    missing: list[str] = []
    checked = 0
    for result in frozen_results.get("results", []):
        if not isinstance(result, dict):
            continue
        display = result.get("display_value")
        if not isinstance(display, str) or not display.strip():
            continue
        checked += 1
        needle = re.sub(r"\s+", "", display)
        if needle not in normalized:
            missing.append(f"{result.get('result_id')}: display value '{display}' not found in PDF text")
    return missing, [], {"checked": checked, "missing": missing}


def check_pdf_math_consistency(
    model_contract: dict[str, Any],
    pdf_text: str,
    *,
    require_scope_contract: bool = False,
    require_formula_replay: bool = False,
) -> tuple[list[str], list[str], dict[str, Any]]:
    scope_errors, scope_warnings, scope_details = evaluate_scope_consistency(
        model_contract,
        pdf_text,
        require_contract=require_scope_contract,
    )
    formula_errors, formula_warnings, formula_details = evaluate_formula_replay(
        model_contract,
        pdf_text,
        require_replay=require_formula_replay,
    )
    details = {
        "scope": scope_details,
        "formula_replay": formula_details,
        "pdf_text_chars": len(pdf_text),
    }
    return scope_errors + formula_errors, scope_warnings + formula_warnings, details


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--model-contract", required=True)
    parser.add_argument("--source")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--require-scope-contract", action="store_true")
    parser.add_argument("--require-formula-replay", action="store_true")
    parser.add_argument("--frozen-results", help="Frozen results whose display values must appear in the PDF text.")
    parser.add_argument("--paper-plan", help="Paper plan used to resolve registered internal IDs.")
    parser.add_argument("--writer-package", help="Writer package used to resolve registered internal IDs.")
    parser.add_argument("--require-numeric-presence", action="store_true", help="Promote missing frozen display values from warnings to errors.")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    pdf_path = resolve_path(args.pdf, root).resolve()
    model_path = resolve_path(args.model_contract, root).resolve()
    source_path = resolve_path(args.source, root).resolve() if args.source else None
    errors: list[str] = []
    warnings: list[str] = []
    details: dict[str, Any] = {}
    try:
        if not pdf_path.is_file():
            errors.append(f"PDF does not exist: {args.pdf}")
        model, schema_errors, _ = _validate_document(model_path, MODEL_SCHEMA)
        errors.extend(f"model_contract schema: {message}" for message in schema_errors)
        if not isinstance(model, dict):
            raise ValueError("model_contract must be an object")
        integrity_documents: list[dict[str, Any]] = []
        for label, raw_path in (("paper_plan", args.paper_plan), ("writer_package", args.writer_package)):
            if not raw_path:
                continue
            document = load_structured(resolve_path(raw_path, root).resolve())
            if not isinstance(document, dict):
                raise ValueError(f"{label} must be an object")
            integrity_documents.append(document)
        registered_internal_ids = collect_registered_internal_ids(*integrity_documents)
        if source_path is not None:
            files = _source_files(source_path)
            if not files:
                errors.append(f"source does not contain a readable .tex/.bib/.md file: {args.source}")
            elif pdf_path.is_file():
                newest_source = max(path.stat().st_mtime for path in files)
                pdf_mtime = pdf_path.stat().st_mtime
                if newest_source > pdf_mtime + 1.0:
                    errors.append("PDF predates the current source tree; rebuild the PDF before W2/F1")
                details["freshness"] = {
                    "source_files": len(files),
                    "newest_source_mtime": newest_source,
                    "pdf_mtime": pdf_mtime,
                    "source_not_newer_than_pdf": newest_source <= pdf_mtime + 1.0,
                }
        if pdf_path.is_file():
            pdf_text, extraction_error = _extract_text(pdf_path)
            if extraction_error:
                errors.append(extraction_error)
            else:
                check_errors, check_warnings, math_details = check_pdf_math_consistency(
                    model,
                    pdf_text,
                    require_scope_contract=args.require_scope_contract,
                    require_formula_replay=args.require_formula_replay,
                )
                errors.extend(check_errors)
                warnings.extend(check_warnings)
                details.update(math_details)
                pdf_exposed = exposed_identifiers(pdf_text, registered_internal_ids)
                details["reader_integrity"] = {
                    "registered_internal_id_count": len(registered_internal_ids),
                    "exposed_identifiers": pdf_exposed,
                }
                if pdf_exposed:
                    errors.append(
                        "final PDF exposes internal authoring marker(s): " + ", ".join(pdf_exposed),
                    )
                if args.frozen_results:
                    frozen_path = resolve_path(args.frozen_results, root).resolve()
                    frozen = load_structured(frozen_path)
                    missing, _nwarn, numeric_details = check_numeric_presence(frozen, pdf_text)
                    details["numeric_presence"] = numeric_details
                    if args.require_numeric_presence:
                        errors.extend(f"frozen display value missing from PDF: {m}" for m in missing)
                    else:
                        warnings.extend(f"frozen display value missing from PDF: {m}" for m in missing)
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        errors.append(str(exc))

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "pdf": rel_path(pdf_path, root),
        "model_contract": rel_path(model_path, root),
        "source": rel_path(source_path, root) if source_path else None,
        "details": details,
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
