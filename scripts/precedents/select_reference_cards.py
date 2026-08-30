#!/usr/bin/env python3
"""Select a small set of reference cards by competition, problem family, or role.

Reads pattern cards and figure cards (Markdown files with fixed fields) and
returns only the matched card summaries.  It never returns local paper file
paths to the writer — full texts stay quarantined and are gated by the
competition profile and live-contest policy.

Selection order is claim/evidence -> evidence_role/problem_family -> card;
never pick a card because it looks good and then hunt for data.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
HARNESS_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(HARNESS_ROOT / "scripts"))

CARD_FIELD_RE = re.compile(r"^-\s+\*\*(\w+)\*\*:\s*(.+?)\s*$", flags=re.MULTILINE)


def _normalise_label(value: str) -> str:
    return " ".join(value.casefold().replace("_", " ").replace("-", " ").split())


def _split_labels(value: str) -> set[str]:
    return {_normalise_label(row) for row in re.split(r"[/,、]", value) if row.strip()}


def _parse_card(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    fields = dict(CARD_FIELD_RE.findall(text))
    title = path.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip()
    return {"title": title, "path": path.relative_to(HARNESS_ROOT).as_posix(), **fields}


def _competition_source_ids(competition: str) -> tuple[set[str], str | None]:
    folder = "cumcm" if competition == "CUMCM" else "mcm-icm"
    index_path = HARNESS_ROOT / "references" / "precedents" / folder / "index.json"
    value = json.loads(index_path.read_text(encoding="utf-8"))
    papers = value.get("papers", []) if isinstance(value, dict) else []
    last_reviewed = value.get("last_reviewed") if isinstance(value, dict) else None
    ids = {
        str(row["paper_id"])
        for row in papers
        if isinstance(row, dict) and isinstance(row.get("paper_id"), str)
    }
    if not isinstance(last_reviewed, str):
        last_reviewed = None
    return ids, last_reviewed


def _card_source_ids(card: dict[str, str]) -> set[str]:
    raw = card.get("source_ids") or card.get("source_id") or ""
    return {row.strip() for row in re.split(r"[,，、]", raw) if row.strip()}


def select_cards(
    *,
    competition: str | None = None,
    problem_family: str | None = None,
    evidence_role: str | None = None,
    data_shape: str | None = None,
    semantic_type: str | None = None,
    card_kind: str = "pattern",
    limit: int = 3,
) -> dict[str, Any]:
    if card_kind == "pattern":
        card_dir = HARNESS_ROOT / "references" / "precedents" / "pattern-cards"
    elif card_kind == "figure":
        card_dir = HARNESS_ROOT / "references" / "precedents" / "figure-cards"
    else:
        raise ValueError("card_kind must be pattern or figure")
    cards = [
        _parse_card(path)
        for path in sorted(card_dir.glob("*.md"))
        if path.name != "schema.md"
    ]
    allowed_source_ids, index_last_reviewed = (
        _competition_source_ids(competition) if competition else (None, None)
    )
    selected = []
    for card in cards:
        if allowed_source_ids is not None and not (_card_source_ids(card) & allowed_source_ids):
            continue
        family = card.get("problem_family", "")
        families = _split_labels(family)
        if problem_family and _normalise_label(problem_family) not in families:
            continue
        if evidence_role and evidence_role.casefold() not in card.get("evidence_role", "").casefold():
            continue
        if data_shape and data_shape.casefold() not in card.get("data_shape", "").casefold():
            continue
        if semantic_type and _normalise_label(semantic_type) not in _split_labels(card.get("semantic_type", "")):
            continue
        selected.append(card)
    id_key = "figure_pattern_id" if card_kind == "figure" else "card_id"
    return {
        "ok": True,
        "card_kind": card_kind,
        "filters": {
            "competition": competition,
            "problem_family": problem_family,
            "evidence_role": evidence_role,
            "data_shape": data_shape,
            "semantic_type": semantic_type,
        },
        "competition_index_last_reviewed": index_last_reviewed,
        "selected": [
            {
                "card_id": card.get(id_key),
                "title": card["title"],
                "path": card["path"],
                "mechanism": card.get("mechanism"),
                "rhetorical_moves": card.get("rhetorical_moves"),
                "data_shape": card.get("data_shape"),
                "semantic_type": card.get("semantic_type"),
                "chart_family": card.get("chart_family"),
                "failure_modes": card.get("failure_modes"),
                "do_not_copy": card.get("do_not_copy"),
                "source_ids": card.get("source_ids") or card.get("source_id"),
            }
            for card in selected[:limit]
        ],
        "available": len(cards),
        "note": "Cards carry mechanisms only, never paper text or evidence; full papers stay quarantined.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--competition", choices=("CUMCM", "MCM-ICM"))
    parser.add_argument("--problem-family")
    parser.add_argument("--evidence-role")
    parser.add_argument("--data-shape")
    parser.add_argument("--semantic-type")
    parser.add_argument("--card-kind", choices=("pattern", "figure"), default="pattern")
    parser.add_argument("--limit", type=int, default=3)
    args = parser.parse_args()
    try:
        result = select_cards(
            competition=args.competition,
            problem_family=args.problem_family,
            evidence_role=args.evidence_role,
            data_shape=args.data_shape,
            semantic_type=args.semantic_type,
            card_kind=args.card_kind,
            limit=args.limit,
        )
    except (OSError, ValueError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
