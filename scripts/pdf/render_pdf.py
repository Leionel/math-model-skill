#!/usr/bin/env python3
"""Render every PDF page and create a contact sheet for visual review."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path  # noqa: E402


def make_contact_sheet(pages: list[Path], output: Path, columns: int) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError as exc:
        raise RuntimeError("Pillow is required for contact sheets; use the bundled Codex Python runtime") from exc
    opened = [Image.open(path).convert("RGB") for path in pages]
    thumb_width = 280
    thumbnails = []
    for index, page in enumerate(opened, start=1):
        height = round(page.height * thumb_width / page.width)
        thumb = page.resize((thumb_width, height))
        canvas = Image.new("RGB", (thumb_width, height + 28), "white")
        canvas.paste(thumb, (0, 28))
        ImageDraw.Draw(canvas).text((8, 6), f"Page {index}", fill="black")
        thumbnails.append(canvas)
    rows = (len(thumbnails) + columns - 1) // columns
    cell_height = max(image.height for image in thumbnails)
    sheet = Image.new("RGB", (columns * thumb_width, rows * cell_height), "#dddddd")
    for index, thumb in enumerate(thumbnails):
        x = (index % columns) * thumb_width
        y = (index // columns) * cell_height
        sheet.paste(thumb, (x, y))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=88)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--contact-sheet", required=True)
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    pdf_path = resolve_path(args.pdf, root).resolve()
    output_dir = resolve_path(args.output_dir, root).resolve()
    contact_path = resolve_path(args.contact_sheet, root).resolve()
    if not pdf_path.is_file():
        print(f"ERROR: PDF does not exist: {pdf_path}", file=sys.stderr)
        return 1
    if args.dpi < 72 or args.dpi > 600 or args.columns < 1 or args.columns > 10:
        print("ERROR: dpi must be 72..600 and columns must be 1..10", file=sys.stderr)
        return 2
    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / "page"
    result = subprocess.run(
        ["pdftoppm", "-png", "-r", str(args.dpi), str(pdf_path), str(prefix)],
        text=True, capture_output=True, encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        print(f"ERROR: pdftoppm failed: {result.stderr}", file=sys.stderr)
        return 1
    pages = sorted(output_dir.glob("page-*.png"))
    if not pages:
        print("ERROR: pdftoppm produced no pages", file=sys.stderr)
        return 1
    try:
        make_contact_sheet(pages, contact_path, args.columns)
    except (OSError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps({
        "ok": True,
        "pdf": rel_path(pdf_path, root),
        "dpi": args.dpi,
        "pages_rendered": len(pages),
        "output_dir": rel_path(output_dir, root),
        "contact_sheet": rel_path(contact_path, root),
        "runtime": os.path.realpath(sys.executable),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
