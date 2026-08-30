#!/usr/bin/env python3
"""Provider-neutral execution protocol for illustration-class figures.

The harness never calls an image API and never hard-codes one vendor.  It
builds a typed `image_generation_request` record (a derived view), the agent
calls whatever native image-generation tool its environment exposes, and the
harness collects the artifact back with its hash and review obligations.

Routes allowed: only `kind=illustration` figures.  Data figures, diagram
topologies that need editable sources, and profiles that forbid generated
imagery are rejected with an actionable status instead of a silent fallback.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import rel_path, sha256_file  # noqa: E402

MIN_RASTER_DPI = 300

_HEADING_RE = re.compile(r"^##\s+(.+?)\s*$", flags=re.MULTILINE)


def _brief_sections(brief_text: str) -> dict[str, str]:
    """Split a figure brief into heading -> body chunks (best effort, deterministic)."""

    chunks: dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(brief_text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(brief_text)
        chunks[match.group(1).strip().lower()] = brief_text[match.end():end].strip()
    return chunks


def build_generation_prompt(brief_text: str, figure_id: str) -> str:
    """Compose the generation prompt from the approved brief, not from memory."""

    sections = _brief_sections(brief_text)
    required = ("purpose", "main message", "reader should understand", "required elements", "required relations", "primary reading order", "must not include")
    missing = [key for key in required if key not in sections or not sections[key]]
    if missing:
        raise ValueError(f"figure brief for {figure_id} is incomplete for generation: missing sections {missing}")
    prompt_lines = [
        f"Scientific concept illustration '{figure_id}' for a math-modeling competition paper.",
        f"Purpose: {sections['purpose']}",
        f"Main message: {sections['main message']}",
        f"Reader should understand: {sections['reader should understand']}",
        f"Required elements: {sections['required elements']}",
        f"Required relations: {sections['required relations']}",
        f"Reading order: {sections['primary reading order']}",
        f"Must not include: {sections['must not include']}",
        "Constraints: no numeric results, no equations, no fabricated axis labels, no logos or watermarks; clean vector-like flat style readable at print size.",
    ]
    return "\n".join(prompt_lines)


def build_image_generation_request(
    *,
    figure_id: str,
    brief_path: Path,
    root: Path,
    route: dict[str, Any],
    capability: str,
    ai_policy: str,
) -> dict[str, Any]:
    """Build the provider-neutral request record for an illustration figure."""

    if route.get("machine_kind") != "illustration" or route.get("default_tool") != "image_generation":
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "route_rejected",
            "message": (
                f"figure routed to {route.get('default_tool')!r}; only illustration routes may request generation. "
                "Data figures must be plotted deterministically; editable diagrams must use a PPTX/Draw.io backend."
            ),
        }
    brief_text = brief_path.read_text(encoding="utf-8") if brief_path.is_file() else ""
    if not brief_text:
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "missing_brief",
            "message": f"figure brief does not exist: {brief_path}",
        }
    if ai_policy == "forbidden":
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "forbidden_by_profile",
            "message": "the current competition profile forbids generated imagery for this figure",
        }
    if ai_policy != "allowed":
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "policy_unresolved",
            "message": "generated imagery requires an explicit allowed policy for the current competition",
        }
    try:
        prompt = build_generation_prompt(brief_text, figure_id)
    except ValueError as exc:
        return {"ok": False, "figure_id": figure_id, "status": "incomplete_brief", "message": str(exc)}
    if capability == "unknown":
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "unknown_capability",
            "message": "the current agent environment has not confirmed a native image-generation capability",
        }
    status = "requested" if capability == "available" else "missing"
    request = {
        "schema_version": "1.0",
        "figure_id": figure_id,
        "kind": "illustration",
        "status": status,
        "prompt": prompt,
        "parameters": {
            "raster_dpi": MIN_RASTER_DPI,
            "text_policy": "raster_text",
            "style": "flat scientific concept illustration",
        },
        "negative_constraints": [
            "no numeric results or quantitative claims",
            "no equations or formula-like glyphs",
            "no fabricated labels, captions, or axes",
            "no logos, watermarks, or competition branding",
        ],
        "required_outputs": [
            "generated raster file (png/jpg) at >= 300 DPI effective resolution",
            "generation record (generator name, prompt path, date)",
            "scientific + visual + final-size human review before formal use",
        ],
        "ai_usage_obligation": "register the generator in run_manifest.ai_usage and run `harness ai verify` before strict promotion",
        "authority_note": "Provider-neutral request record only; the harness itself never calls an image API.",
    }
    return {"ok": True, **request}


def collect_illustration_output(
    *,
    figure_id: str,
    generated_path: Path,
    root: Path,
    request_path: Path,
) -> dict[str, Any]:
    """Register a generated illustration artifact back into the figure directory."""

    if not request_path.is_file():
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "missing_request",
            "message": "collect requires the matching executable image-generation request",
        }
    try:
        request = json.loads(request_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "invalid_request",
            "message": f"cannot read image-generation request: {exc}",
        }
    if not isinstance(request, dict) or request.get("figure_id") != figure_id or request.get("kind") != "illustration":
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "request_mismatch",
            "message": "image-generation request is not bound to this illustration figure",
        }
    if request.get("ok") is not True or request.get("status") != "requested":
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "request_not_executable",
            "message": "only a request with ok=true and status=requested may collect generated output",
        }

    if not generated_path.is_file():
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "missing_artifact",
            "message": f"generated illustration does not exist: {generated_path}",
        }
    if generated_path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "unsupported_artifact",
            "message": f"generated illustration must be a raster png/jpg, got {generated_path.suffix!r}",
        }
    try:
        generated_path.resolve().relative_to(root.resolve())
    except ValueError:
        return {
            "ok": False,
            "figure_id": figure_id,
            "status": "path_escape",
            "message": "generated illustration must stay inside the project root",
        }
    digest = sha256_file(generated_path)
    record = {
        "schema_version": "1.0",
        "figure_id": figure_id,
        "kind": "illustration",
        "generated": {
            "path": rel_path(generated_path.resolve(), root.resolve()),
            "sha256": digest,
        },
        "request_path": rel_path(request_path.resolve(), root.resolve()),
        "review_status": "pending",
        "review_requirements": [
            "scientific review: entities and relations match the approved brief; nothing invented",
            "visual review: legibility, grayscale safety, no stray text artifacts",
            "final-size review: effective DPI and print dimensions before paper placement",
        ],
        "promotion_rule": "review_status must become reviewed before the figure may enter W2 as a formal illustration",
    }
    return {"ok": True, **record}
