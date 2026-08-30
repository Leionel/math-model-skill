"""Black-box Draw.io -> PDF -> rendered-page delivery-chain check.

This check records the environment and validates only that the delivery tools
can transform a real ``.drawio`` source into a PDF and a page image.  A pass
does not assert model correctness, paper correctness, or visual quality.
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, resolve_path  # noqa: E402
from figures.generate_drawio import _find_drawio_cli  # noqa: E402
from redaction import redact_text  # noqa: E402


def _version(executable: str | None) -> str | None:
    if not executable:
        return None
    for flag in ("--version", "-version"):
        try:
            result = subprocess.run(
                [executable, flag], text=True, capture_output=True, encoding="utf-8",
                errors="replace", check=False, timeout=5,
            )
        except (OSError, subprocess.TimeoutExpired):
            continue
        if result.returncode == 0:
            output = redact_text(result.stdout or result.stderr)
            return next((line.strip() for line in output.splitlines() if line.strip()), None)
    return None


def _run(argv: list[str], *, timeout: float = 120) -> dict[str, Any]:
    try:
        result = subprocess.run(
            argv, text=True, capture_output=True, encoding="utf-8", errors="replace",
            check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "exit_code": None, "stdout": redact_text(exc.stdout or ""), "stderr": "command timed out"}
    except OSError as exc:
        return {"ok": False, "exit_code": None, "stdout": "", "stderr": redact_text(str(exc))}
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": redact_text(result.stdout or ""),
        "stderr": redact_text(result.stderr or ""),
    }


def _resolve_executable(raw: str | None, discovered: str | None = None) -> str | None:
    if raw:
        located = shutil.which(raw)
        if located:
            return located
        candidate = Path(raw).resolve()
        return str(candidate) if candidate.is_file() else None
    return discovered


def check_delivery(
    root: Path,
    source: str,
    *,
    output_dir: str = ".harness/qa/drawio",
    drawio: str | None = None,
    pdfinfo: str | None = None,
    pdftoppm: str | None = None,
) -> tuple[dict[str, Any], int]:
    project_root = root.resolve()
    source_path = resolve_path(source, project_root).resolve()
    destination = resolve_path(output_dir, project_root).resolve()
    drawio_path = _resolve_executable(drawio, _find_drawio_cli())
    pdfinfo_path = _resolve_executable(pdfinfo, shutil.which("pdfinfo"))
    pdftoppm_path = _resolve_executable(pdftoppm, shutil.which("pdftoppm"))
    environment = {
        "platform": platform.platform(),
        "python": sys.version.split()[0],
        "drawio": {"path": drawio_path, "version": _version(drawio_path)},
        "pdfinfo": {"path": pdfinfo_path, "version": _version(pdfinfo_path)},
        "pdftoppm": {"path": pdftoppm_path, "version": _version(pdftoppm_path)},
    }
    report: dict[str, Any] = {
        "ok": False,
        "status": "blocked",
        "scope": "delivery_chain_only",
        "claim_boundary": "This check does not prove model, paper, semantic, or visual correctness.",
        "source": source,
        "environment": environment,
        "steps": {},
        "errors": [],
    }
    try:
        source_path.relative_to(project_root)
        destination.relative_to(project_root)
    except ValueError:
        report["status"] = "failed"
        report["errors"].append("source and output_dir must remain inside the project root")
        return report, 1
    report["source"] = rel_path(source_path, project_root)
    if not source_path.is_file():
        report["errors"].append(f"drawio source does not exist: {source}")
    elif source_path.suffix.lower() != ".drawio":
        report["errors"].append("source must be a .drawio file")
    if report["errors"]:
        report["status"] = "failed"
        return report, 1
    if not drawio_path:
        report["errors"].append("Draw.io Desktop executable was not found")
    if not pdfinfo_path:
        report["errors"].append("pdfinfo was not found")
    if not pdftoppm_path:
        report["errors"].append("pdftoppm was not found")
    if report["errors"]:
        report["status"] = "not_available"
        return report, 3

    destination.mkdir(parents=True, exist_ok=True)
    run_dir = Path(tempfile.mkdtemp(prefix=f"{source_path.stem}-", dir=destination))
    report["output_dir"] = rel_path(run_dir, project_root)
    pdf_path = run_dir / f"{source_path.stem}.pdf"
    preview_prefix = run_dir / f"{source_path.stem}-page-1"
    preview_path = preview_prefix.with_suffix(".png")
    export_argv = [drawio_path, "-x", "-f", "pdf", "-e", "-b", "10", "-o", str(pdf_path), str(source_path)]
    export = _run(export_argv)
    export["output"] = rel_path(pdf_path, project_root)
    report["steps"]["drawio_export_pdf"] = export
    if not export["ok"] or not pdf_path.is_file():
        report["status"] = "failed"
        report["errors"].append("Draw.io PDF export failed or produced no PDF")
        return report, 1

    info = _run([pdfinfo_path, str(pdf_path)])
    info["input"] = rel_path(pdf_path, project_root)
    report["steps"]["pdf_inspection"] = info
    if not info["ok"]:
        report["status"] = "failed"
        report["errors"].append("pdfinfo could not inspect the exported PDF")
        return report, 1

    render = _run([pdftoppm_path, "-f", "1", "-singlefile", "-png", str(pdf_path), str(preview_prefix)])
    render["output"] = rel_path(preview_path, project_root)
    report["steps"]["render_page_png"] = render
    if not render["ok"] or not preview_path.is_file():
        report["status"] = "failed"
        report["errors"].append("pdftoppm could not render the exported PDF page")
        return report, 1
    report["ok"] = True
    report["status"] = "passed"
    return report, 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--source", required=True, help=".drawio source, relative to project root")
    parser.add_argument("--output-dir", default=".harness/qa/drawio")
    parser.add_argument("--drawio")
    parser.add_argument("--pdfinfo")
    parser.add_argument("--pdftoppm")
    args = parser.parse_args(argv)
    try:
        report, code = check_delivery(
            Path(args.project_root), args.source, output_dir=args.output_dir,
            drawio=args.drawio, pdfinfo=args.pdfinfo, pdftoppm=args.pdftoppm,
        )
    except (OSError, ValueError, TypeError) as exc:
        report, code = {"ok": False, "status": "failed", "scope": "delivery_chain_only", "errors": [str(exc)]}, 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
