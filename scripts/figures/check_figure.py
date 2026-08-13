#!/usr/bin/env python3
"""Run deterministic figure export checks; semantic/readability review remains manual."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path, sha256_file, write_json  # noqa: E402
from qa.validate_contracts import _validate_document  # noqa: E402


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def png_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as handle:
        header = handle.read(24)
    if len(header) >= 24 and header[:8] == PNG_SIGNATURE and header[12:16] == b"IHDR":
        return int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")
    return None


def pdf_page_points(path: Path) -> tuple[float, float] | None:
    result = subprocess.run(["pdfinfo", str(path)], text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
    if result.returncode != 0:
        return None
    match = re.search(r"^Page size:\s+([0-9.]+) x ([0-9.]+) pts", result.stdout, flags=re.MULTILINE)
    return (float(match.group(1)), float(match.group(2))) if match else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--figure-id", required=True)
    parser.add_argument("--figure", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--target-width-inch", type=float)
    parser.add_argument("--output", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    figure_path = resolve_path(args.figure, root).resolve()
    profile_path = resolve_path(args.profile, root).resolve()
    output_path = resolve_path(args.output, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    profile, schema_errors, _ = _validate_document(
        profile_path, Path(__file__).resolve().parents[2] / "schemas" / "visual_profile.schema.json"
    )
    errors.extend(f"visual_profile schema: {message}" for message in schema_errors)
    if not isinstance(profile, dict):
        profile = {}
    if not figure_path.is_file():
        errors.append(f"figure does not exist: {args.figure}")
    suffix = figure_path.suffix.lower()
    width_px = height_px = None
    effective_dpi = None
    page_box_ok = None
    font_status = "not_applicable"
    if not errors and suffix == ".png":
        size = png_size(figure_path)
        if size is None:
            errors.append("PNG header is invalid or unsupported")
        else:
            width_px, height_px = size
            if args.target_width_inch:
                effective_dpi = width_px / args.target_width_inch
                minimum = profile.get("figures", {}).get("raster_min_dpi")
                if isinstance(minimum, (int, float)) and effective_dpi < minimum:
                    severity = profile.get("severity_policy", {}).get("low_resolution", "warning")
                    message = f"effective DPI {effective_dpi:.1f} is below profile minimum {minimum}"
                    (errors if severity == "error" else warnings).append(message)
    elif not errors and suffix == ".pdf":
        points = pdf_page_points(figure_path)
        page_box_ok = points is not None and points[0] > 0 and points[1] > 0
        if not page_box_ok:
            errors.append("cannot read PDF figure page box")
        fonts = subprocess.run(["pdffonts", str(figure_path)], text=True, capture_output=True, encoding="utf-8", errors="replace", check=False)
        if fonts.returncode == 0:
            font_status = "pass"
            for line in fonts.stdout.splitlines()[2:]:
                parts = line.split()
                if len(parts) >= 6 and parts[-5].lower() == "no":
                    font_status = "fail"
                    break
            if font_status == "fail":
                severity = profile.get("severity_policy", {}).get("font_embedding", "warning")
                (errors if severity == "error" else warnings).append("PDF figure contains unembedded font(s)")
        else:
            font_status = "not_available"
            warnings.append("pdffonts could not inspect the PDF figure")
    elif not errors and suffix not in {".svg", ".eps"}:
        warnings.append(f"no deterministic size/font parser for {suffix or 'unknown format'}")

    if profile.get("figures", {}).get("grayscale_review_required"):
        warnings.append("grayscale distinguishability requires final-size visual review")
    if profile.get("figures", {}).get("colorblind_review_required"):
        warnings.append("color-vision accessibility requires visual review")

    report = {
        "schema_version": "1.0",
        "figure_id": args.figure_id,
        "artifact": {"path": rel_path(figure_path, root), "sha256": sha256_file(figure_path) if figure_path.is_file() else "0" * 64},
        "profile": {"path": rel_path(profile_path, root), "sha256": sha256_file(profile_path)},
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "automated": {
            "format": suffix.lstrip(".") or "unknown",
            "width_px": width_px,
            "height_px": height_px,
            "effective_dpi": effective_dpi,
            "page_box_ok": page_box_ok,
            "font_scan_status": font_status,
            "warnings": warnings,
            "errors": errors,
        },
        "manual_review_required": True,
        "ok": not errors,
    }
    try:
        write_json(output_path, report, overwrite=args.force)
    except (OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({"ok": report["ok"], "output": rel_path(output_path, root), "warnings": len(warnings)}, ensure_ascii=False))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
