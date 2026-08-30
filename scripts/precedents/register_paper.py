#!/usr/bin/env python3
"""Register one local quarantined paper into a competition precedent index.

The index row records provenance (source URL, rights status), identity
(SHA-256, competition, year, problem), and extraction state.  The paper file
itself stays under `references/precedents/local-sources/` (git-ignored) and is
never copied into the repository or the evidence registry.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file, write_json  # noqa: E402

QUARANTINE_ROOT = "references/precedents/local-sources"
COMPETITIONS = ("CUMCM", "MCM-ICM")
RIGHTS_STATUSES = ("authorized_public_download", "local_study_only", "unknown")
EXTRACTION_STATUSES = ("not_started", "extracted", "verified")


def _normalize_problem(value: str) -> str:
    problem = value.strip().upper()
    for suffix in ("题", "题目", "PROBLEM"):
        problem = problem[: -len(suffix)] if problem.endswith(suffix) else problem
    return problem.strip()


def register_paper(
    root: Path,
    *,
    index_path: str,
    paper_path: str,
    source_url: str,
    rights_status: str,
    problem: str,
    paper_id: str | None = None,
    year: int | None = None,
    award: str | None = None,
    problem_family: str | None = None,
    extraction_status: str = "not_started",
    official_or_authorized: bool = False,
    tags: list[str] | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    if rights_status not in RIGHTS_STATUSES:
        raise ValueError(f"rights_status must be one of {RIGHTS_STATUSES}")
    if rights_status == "authorized_public_download" and not official_or_authorized:
        raise ValueError(
            "authorized_public_download requires explicit official_or_authorized=true; "
            "use local_study_only when authorization has not been established"
        )
    if extraction_status not in EXTRACTION_STATUSES:
        raise ValueError(f"extraction_status must be one of {EXTRACTION_STATUSES}")
    resolved_index = resolve_path(index_path, root).resolve()
    resolved_paper = resolve_path(paper_path, root).resolve()
    if not resolved_paper.is_file():
        raise ValueError(f"paper file does not exist: {paper_path}")
    try:
        paper_relative = resolved_paper.relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError("paper file must stay inside the project root") from exc
    if not paper_relative.startswith(f"{QUARANTINE_ROOT}/"):
        raise ValueError(
            f"paper files must be quarantined under {QUARANTINE_ROOT}/, got {paper_relative}"
        )
    if resolved_paper.suffix.lower() != ".pdf":
        raise ValueError("only PDF papers can be registered in the precedent index")
    digest = sha256_file(resolved_paper)
    index = load_structured(resolved_index) if resolved_index.is_file() else {}
    if not isinstance(index, dict):
        raise ValueError("index must be an object")
    competition = str(index.get("competition") or "").upper()
    if competition not in COMPETITIONS:
        raise ValueError(f"index competition must be one of {COMPETITIONS}, got {competition!r}")
    papers = index.get("papers", [])
    if not isinstance(papers, list):
        raise ValueError("index.papers must be an array")
    for row in papers:
        if not isinstance(row, dict):
            continue
        if row.get("sha256") == digest:
            raise ValueError(f"this file is already registered as {row.get('paper_id')} (same sha256)")
        if paper_id and row.get("paper_id") == paper_id:
            raise ValueError(f"paper_id {paper_id!r} already exists in this index")
    normalized_problem = _normalize_problem(problem)
    stem = resolved_paper.stem
    entry = {
        "paper_id": paper_id or stem,
        "competition": competition,
        "year": year,
        "problem": normalized_problem,
        "award": award,
        "problem_family": problem_family,
        "source_url": source_url,
        "rights_status": rights_status,
        "official_or_authorized": official_or_authorized,
        "local_path": paper_relative,
        "sha256": digest,
        "extraction_status": extraction_status,
        "tags": tags or [],
    }
    if notes:
        entry["notes"] = notes
    papers.append(entry)
    index.update({"schema_version": "1.1", "competition": competition, "papers": papers})
    write_json(resolved_index, index, overwrite=True)
    return {
        "ok": True,
        "index": rel_path(resolved_index, root),
        "registered": entry["paper_id"],
        "sha256": digest,
        "total_papers": len(papers),
        "boundary": "Index rows are metadata only; the paper stays quarantined and never becomes evidence.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--index", required=True, help="index json path, e.g. references/precedents/cumcm/index.json")
    parser.add_argument("--paper", required=True, help="local PDF path under references/precedents/local-sources/")
    parser.add_argument("--source-url", required=True)
    parser.add_argument("--rights-status", required=True, choices=RIGHTS_STATUSES)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--paper-id")
    parser.add_argument("--year", type=int)
    parser.add_argument("--award")
    parser.add_argument("--problem-family", choices=("optimization", "prediction", "evaluation", "simulation", "mechanism", "statistics", "policy"))
    parser.add_argument("--extraction-status", choices=EXTRACTION_STATUSES, default="not_started")
    parser.add_argument("--official-or-authorized", action="store_true")
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--notes")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    try:
        result = register_paper(
            root,
            index_path=args.index,
            paper_path=args.paper,
            source_url=args.source_url,
            rights_status=args.rights_status,
            problem=args.problem,
            paper_id=args.paper_id,
            year=args.year,
            award=args.award,
            problem_family=args.problem_family,
            extraction_status=args.extraction_status,
            official_or_authorized=args.official_or_authorized,
            tags=args.tag,
            notes=args.notes,
        )
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
