#!/usr/bin/env python3
"""Check actual PDF page geometry, font embedding, and a completed page render."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path, sha256_file, write_json  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]")


def command_output(command: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(command, text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
    return result.returncode, result.stdout, result.stderr


def parse_font_rows(output: str) -> tuple[int, list[str]]:
    rows = []
    for line in output.splitlines()[2:]:
        if not line.strip():
            continue
        parts = line.split()
        if len(parts) < 8:
            continue
        rows.append(parts)
    unembedded = [row[0] for row in rows if row[-5].casefold() == "no"]
    return len(rows), unembedded


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--render-dir", required=True)
    parser.add_argument("--contact-sheet", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--source")
    parser.add_argument("--render-dpi", type=int, default=144)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    pdf_path = resolve_path(args.pdf, root).resolve()
    profile_path = resolve_path(args.profile, root).resolve()
    render_dir = resolve_path(args.render_dir, root).resolve()
    contact_path = resolve_path(args.contact_sheet, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    profile, schema_errors, _ = _validate_document(
        profile_path, Path(__file__).resolve().parents[2] / "schemas" / "visual_profile.schema.json"
    )
    errors.extend(f"visual_profile schema: {message}" for message in schema_errors)
    if not isinstance(profile, dict):
        profile = {}
    if not pdf_path.is_file():
        errors.append(f"PDF does not exist: {args.pdf}")

    page_count = 0
    observed_width_mm = observed_height_mm = 0.0
    if not errors:
        code, info, info_error = command_output(["pdfinfo", str(pdf_path)])
        if code != 0:
            errors.append(f"pdfinfo failed: {info_error.strip()}")
        else:
            page_match = re.search(r"^Pages:\s+(\d+)", info, flags=re.MULTILINE)
            size_match = re.search(r"^Page size:\s+([0-9.]+) x ([0-9.]+) pts", info, flags=re.MULTILINE)
            if page_match:
                page_count = int(page_match.group(1))
            else:
                errors.append("pdfinfo did not report page count")
            if size_match:
                observed_width_mm = float(size_match.group(1)) * 25.4 / 72
                observed_height_mm = float(size_match.group(2)) * 25.4 / 72
            else:
                errors.append("pdfinfo did not report first-page size")
    expected_width = float(profile.get("page", {}).get("width_mm", 0))
    expected_height = float(profile.get("page", {}).get("height_mm", 0))
    tolerance = float(profile.get("page", {}).get("size_tolerance_mm", 0))
    within_tolerance = (
        abs(observed_width_mm - expected_width) <= tolerance
        and abs(observed_height_mm - expected_height) <= tolerance
    )
    if page_count and not within_tolerance:
        errors.append(
            f"first-page size {observed_width_mm:.2f}x{observed_height_mm:.2f} mm differs from "
            f"profile {expected_width:.2f}x{expected_height:.2f} mm"
        )
    max_pages = profile.get("page", {}).get("max_body_pages")
    if isinstance(max_pages, int) and page_count > max_pages:
        errors.append(f"PDF has {page_count} pages; profile maximum is {max_pages}")

    font_count = 0
    unembedded: list[str] = []
    font_checked = False
    if pdf_path.is_file():
        code, font_output, font_error = command_output(["pdffonts", str(pdf_path)])
        if code == 0:
            font_checked = True
            font_count, unembedded = parse_font_rows(font_output)
            if unembedded and profile.get("typography", {}).get("embedded_fonts_required"):
                severity = profile.get("severity_policy", {}).get("font_embedding", "warning")
                message = f"unembedded fonts: {unembedded}"
                (errors if severity == "error" else warnings).append(message)
        else:
            warnings.append(f"pdffonts could not inspect PDF fonts: {font_error.strip()}")

    cjk_detected = None
    if args.source:
        source_path = resolve_path(args.source, root).resolve()
        try:
            cjk_detected = bool(CJK_RE.search(source_path.read_text(encoding="utf-8")))
        except OSError as exc:
            errors.append(f"cannot read source for CJK scan: {exc}")
    cjk_review = bool(profile.get("typography", {}).get("cjk_render_review_required") and cjk_detected is not False)
    if cjk_review:
        warnings.append("CJK visibility must be confirmed from rendered pages; pdffonts encoding labels are not a verdict")

    pages_rendered = 0
    render_status = "not_run"
    if pdf_path.is_file():
        render_script = Path(__file__).resolve().parent / "render_pdf.py"
        render_command = [
            sys.executable, str(render_script),
            "--project-root", str(root), "--pdf", str(pdf_path),
            "--output-dir", str(render_dir), "--contact-sheet", str(contact_path),
            "--dpi", str(args.render_dpi),
        ]
        rendered = subprocess.run(render_command, text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
        if rendered.returncode == 0:
            render_status = "pass"
            try:
                pages_rendered = int(json.loads(rendered.stdout).get("pages_rendered", 0))
            except (json.JSONDecodeError, TypeError, ValueError):
                errors.append("render_pdf returned an invalid receipt")
            if pages_rendered != page_count:
                errors.append(f"rendered page count {pages_rendered} differs from pdfinfo page count {page_count}")
        else:
            render_status = "fail"
            errors.append(f"render_pdf failed: {rendered.stderr.strip() or rendered.stdout.strip()}")

    report = {
        "schema_version": "1.0",
        "pdf": {"path": rel_path(pdf_path, root), "sha256": sha256_file(pdf_path) if pdf_path.is_file() else "0" * 64},
        "profile": {"path": rel_path(profile_path, root), "sha256": sha256_file(profile_path)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tools": {
            "pdfinfo": shutil.which("pdfinfo") or "missing",
            "pdffonts": shutil.which("pdffonts") or "missing",
            "pdftoppm": shutil.which("pdftoppm") or "missing",
            "python": sys.executable,
        },
        "page_count": page_count,
        "page_size": {
            "observed_width_mm": observed_width_mm,
            "observed_height_mm": observed_height_mm,
            "expected_width_mm": expected_width,
            "expected_height_mm": expected_height,
            "within_tolerance": within_tolerance,
        },
        "fonts": {
            "checked": font_checked,
            "font_count": font_count,
            "unembedded": unembedded,
            "cjk_source_detected": cjk_detected,
            "cjk_render_review_required": cjk_review,
        },
        "render": {
            "status": render_status,
            "dpi": args.render_dpi if render_status != "not_run" else None,
            "pages_rendered": pages_rendered,
            "directory": rel_path(render_dir, root) if render_status == "pass" else None,
            "contact_sheet": rel_path(contact_path, root) if contact_path.is_file() else None,
        },
        "warnings": warnings,
        "errors": errors,
        "formal_ok": not errors,
        "visual_review_required": True,
    }
    try:
        write_json(output_path, report, overwrite=args.force)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": report["formal_ok"], "output": rel_path(output_path, root), "pages": page_count, "warnings": len(warnings)}, ensure_ascii=False))
    return 0 if report["formal_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
