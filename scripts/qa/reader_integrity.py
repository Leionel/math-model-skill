"""Shared checks for keeping internal authoring metadata out of reader output.

The Harness needs locator metadata to remain usable in source files and
sidecars, but that metadata must not become part of the manuscript.  This
module deliberately recognizes only exact identifiers registered by the
current paper plan/writer package.  It does not treat ordinary words or an
unregistered ``R-*`` token as an internal marker.
"""

from __future__ import annotations

import re
import shutil
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


INTERNAL_PREFIX_RE = re.compile(r"\b(?:ANCHOR|LOC)-[A-Za-z0-9][A-Za-z0-9_.-]*\b")
AUDIT_COMMAND_RE = re.compile(r"\\audit\b")
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)
_TEX_COMMENT_RE = re.compile(r"(?<!\\)%[^\r\n]*")
_INVISIBLE_SINGLE_ARG_RE = re.compile(
    r"\\(?:label|ref|pageref|eqref|autoref|cref|Cref|cite[a-zA-Z]*|index|glossary)"
    r"\s*(?:\[[^\]]*\]\s*)*\{[^{}]*\}"
)
_INVISIBLE_LINK_RE = re.compile(
    r"\\(?:hypertarget|hyperlink)\s*\{[^{}]*\}\s*\{([^{}]*)\}"
)
_INVISIBLE_GRAPHICS_RE = re.compile(
    r"\\includegraphics(?:\[[^\]]*\])?\s*\{[^{}]*\}"
)
_ID_LIKE_RE = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]*\Z")
_LOCATOR_COMMAND_RE = re.compile(r"^\\(?:label|hypertarget)\s*\{([^{}]+)\}\s*\Z")


def strip_tex_comments(text: str) -> str:
    """Remove TeX comments while preserving escaped percent signs."""

    return _TEX_COMMENT_RE.sub("", text)


def reader_visible_source(text: str) -> str:
    """Return the portion of TeX/Markdown that can reach reader-facing text.

    ``label``, cross-reference keys, citation keys, graphics paths and the
    first argument of hyperlink targets are source-side metadata.  They are
    removed before exact marker matching, while the visible hyperlink label
    is retained.  This is a visibility filter, not a TeX parser; the final
    PDF scan remains the authoritative rendered check.
    """

    visible = _HTML_COMMENT_RE.sub("", strip_tex_comments(text))
    visible = _INVISIBLE_LINK_RE.sub(lambda match: match.group(1), visible)
    visible = _INVISIBLE_SINGLE_ARG_RE.sub("", visible)
    visible = _INVISIBLE_GRAPHICS_RE.sub("", visible)
    return visible


def noncomment_source(text: str) -> str:
    """Remove comments while retaining commands hidden in TeX metadata."""

    return _HTML_COMMENT_RE.sub("", strip_tex_comments(text))


def contains_token(text: str, token: str) -> bool:
    """Match an exact registered identifier, not a prefix of another token."""

    if not token:
        return False
    return re.search(
        rf"(?<![A-Za-z0-9_-]){re.escape(token)}(?![A-Za-z0-9_-])",
        text,
        flags=re.IGNORECASE,
    ) is not None


def _locator_ids(value: Any) -> set[str]:
    if not isinstance(value, str):
        return set()
    raw = value.strip()
    match = _LOCATOR_COMMAND_RE.fullmatch(raw)
    if match:
        raw = match.group(1).strip()
    if not _ID_LIKE_RE.fullmatch(raw):
        return set()
    identifiers = {raw}
    # ``eq:EQ-Q1`` and ``harness:AU-Q1`` are common locator namespaces.  The
    # namespace itself is not a reader marker, but the registered suffix is.
    if ":" in raw:
        suffix = raw.rsplit(":", 1)[-1]
        if _ID_LIKE_RE.fullmatch(suffix):
            identifiers.add(suffix)
    return identifiers


def collect_registered_internal_ids(*documents: Mapping[str, Any] | None) -> set[str]:
    """Collect exact claim/unit/anchor/locator IDs from current documents.

    Result IDs are intentionally not collected merely because they have an
    ``R-*`` shape.  A result token is only considered internal when an author
    explicitly registered it as a mathematical locator in the current plan.
    """

    identifiers: set[str] = set()
    for document in documents:
        if not isinstance(document, Mapping):
            continue
        for row in document.get("claims", []):
            if isinstance(row, Mapping) and isinstance(row.get("claim_id"), str):
                identifiers.add(row["claim_id"])
        for row in document.get("argument_units", []):
            if not isinstance(row, Mapping):
                continue
            for field in ("unit_id", "anchor_id"):
                if isinstance(row.get(field), str):
                    identifiers.add(row[field])
            for locator in row.get("math_locators", []):
                identifiers.update(_locator_ids(locator))
    return {value for value in identifiers if value}


def exposed_identifiers(text: str, registered_ids: Iterable[str] = ()) -> list[str]:
    """Return exact internal markers exposed by reader-facing text."""

    visible = reader_visible_source(text)
    exposed = set(INTERNAL_PREFIX_RE.findall(visible))
    exposed.update(
        identifier
        for identifier in registered_ids
        if contains_token(visible, identifier)
    )
    return sorted(exposed, key=str.casefold)


def source_issues(text: str, registered_ids: Iterable[str] = ()) -> list[str]:
    """Return deterministic source-level reader-integrity errors."""

    issues: list[str] = []
    markers = exposed_identifiers(text, registered_ids)
    if markers:
        issues.append("reader-facing source exposes internal marker(s): " + ", ".join(markers))
    if AUDIT_COMMAND_RE.search(noncomment_source(text)):
        issues.append("source contains forbidden \\audit command or definition outside comments")
    return issues


def extract_pdf_text(pdf_path: Path) -> tuple[str, str | None]:
    """Extract PDF text with the same tool used by PDF math QA."""

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


def _path_variants(raw: str) -> set[str]:
    normalized = raw.replace("\\", "/").casefold()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    variants = {normalized}
    if Path(normalized).suffix in {".png", ".pdf", ".jpg", ".jpeg", ".eps", ".svg"}:
        variants.add(normalized.rsplit(".", 1)[0])
    return variants


def paths_match(left: str, right: str) -> bool:
    """Match a project-relative graphics path with an extension-tolerant suffix."""

    return any(
        a == b or a.endswith("/" + b) or b.endswith("/" + a)
        for a in _path_variants(left)
        for b in _path_variants(right)
    )


def included_graphics_paths(source: str) -> list[str]:
    """Extract graphics paths from raw TeX without treating comments as use."""

    return [
        match.group(1).strip()
        for match in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\s*\{([^{}]+)\}", strip_tex_comments(source))
    ]


def figure_is_reader_used(figure: Mapping[str, Any], source: str) -> bool:
    """Determine whether a planned figure is referenced by reader-facing source."""

    visible = reader_visible_source(source)
    figure_id = figure.get("figure_id")
    if isinstance(figure_id, str) and contains_token(visible, figure_id):
        return True
    candidates: list[str] = [
        artifact
        for artifact in figure.get("data_artifacts", [])
        if isinstance(artifact, str)
    ]
    diagram = figure.get("diagram")
    if isinstance(diagram, Mapping):
        candidates.extend(
            path
            for path in diagram.get("rendered_paths", [])
            if isinstance(path, str)
        )
    return any(
        paths_match(included, candidate)
        for included in included_graphics_paths(source)
        for candidate in candidates
    )


def evaluate_figure_reader_bindings(
    paper_plan: Mapping[str, Any],
    source: str,
) -> tuple[list[str], dict[str, Any]]:
    """Require audience classification only for figures used in the body."""

    errors: list[str] = []
    details: dict[str, Any] = {"figures": {}}
    for figure in paper_plan.get("figures", []):
        if not isinstance(figure, Mapping):
            continue
        figure_id = str(figure.get("figure_id", "figure"))
        used = figure_is_reader_used(figure, source)
        audience = figure.get("audience")
        row = {"used_in_reader_body": used, "audience": audience}
        details["figures"][figure_id] = row
        if not used:
            continue
        if audience not in {"scientific_argument", "submission_disclosure", "internal_audit"}:
            errors.append(
                f"figure {figure_id} is used in reader-facing body but has no audience classification"
            )
        elif audience != "scientific_argument":
            errors.append(
                f"figure {figure_id} has audience={audience} and cannot enter reader-facing body"
            )
    return errors, details


def visual_opportunity_scan(paper_plan: Mapping[str, Any]) -> dict[str, Any]:
    """Derive a non-blocking visual review row for every argument unit.

    This does not decide that a figure must exist.  It exposes where a human or
    Writer should choose between prose, table, deterministic data figure, or a
    conceptual illustration before drafting.
    """

    displays = [
        row
        for key in ("figures", "tables")
        for row in paper_plan.get(key, [])
        if isinstance(row, Mapping)
    ]
    quantitative_roles = {"result_observation", "comparison", "validation"}
    conceptual_roles = {"problem_tension", "model_choice", "mechanism_derivation"}
    rows: list[dict[str, Any]] = []
    for unit in paper_plan.get("argument_units", []):
        if not isinstance(unit, Mapping):
            continue
        claim_ids = {
            value for value in unit.get("claim_ids", []) if isinstance(value, str)
        }
        bound = [
            str(display.get("figure_id") or display.get("table_id"))
            for display in displays
            if claim_ids.intersection(
                value for value in display.get("claim_ids", []) if isinstance(value, str)
            )
        ]
        role = unit.get("rhetorical_role")
        if bound:
            status = "covered"
            recommendation = "use the planned display only if it advances this argument"
        elif role in quantitative_roles:
            status = "review_required"
            recommendation = "compare a table with a deterministic data figure"
        elif role in conceptual_roles:
            status = "review_required"
            recommendation = "decide whether prose, an editable diagram, or a non-quantitative illustration explains the mechanism best"
        else:
            status = "no_default_visual_need"
            recommendation = "keep prose unless a figure materially reduces explanation cost"
        rows.append({
            "unit_id": unit.get("unit_id"),
            "rhetorical_role": role,
            "status": status,
            "bound_display_ids": sorted(bound),
            "recommendation": recommendation,
        })
    return {
        "rows": rows,
        "review_required": sum(row["status"] == "review_required" for row in rows),
        "rule": "Figure count follows argument/evidence coverage; this scan does not impose a quota.",
    }
