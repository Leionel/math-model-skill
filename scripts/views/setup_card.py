"""Render the single human-facing DSH setup card as a derived view.

The card is a draft-only checklist.  It reads the existing manifest/profile
and capability evaluator, writes only ``.harness/views/SETUP_CARD.md``, and
never dispatches a command or changes Gate state.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path  # noqa: E402
from doctor_core import STAGES, evaluate_capabilities  # noqa: E402
from project_layout import resolve_manifest_path  # noqa: E402


def _read_manifest(root: Path, manifest: str | None) -> tuple[dict[str, Any] | None, Path | None]:
    path = resolve_manifest_path(root, manifest)
    if not path.is_file():
        return None, path
    value = load_structured(path)
    if not isinstance(value, dict):
        raise ValueError("run_manifest must be an object")
    return value, path


def build_setup_card(root: Path, *, manifest: str | None = None, stage: str | None = None) -> dict[str, Any]:
    project_root = root.resolve()
    value, manifest_path = _read_manifest(project_root, manifest)
    profile_path: Path | None = None
    profile: Mapping[str, Any] = {}
    if value:
        raw_ref = value.get("competition_profile_ref")
        raw_profile = raw_ref.get("path") if isinstance(raw_ref, Mapping) else None
        if isinstance(raw_profile, str):
            profile_path = resolve_path(raw_profile, project_root).resolve()
            if profile_path.is_file():
                loaded = load_structured(profile_path)
                if not isinstance(loaded, Mapping):
                    raise ValueError("competition profile must be an object")
                profile = loaded
    capabilities = evaluate_capabilities(
        project_root,
        stage=stage,
        repo_root=Path(__file__).resolve().parents[2],
    )
    control = value.get("control", {}) if isinstance(value, Mapping) else {}
    required_human = control.get("required_human_stages", []) if isinstance(control, Mapping) else []
    if not isinstance(required_human, list):
        required_human = []
    profile_ref = value.get("competition_profile_ref", {}) if isinstance(value, Mapping) else {}
    profile_ref_id = profile_ref.get("profile_id") if isinstance(profile_ref, Mapping) else None
    card: dict[str, Any] = {
        "status": "draft",
        "execution_policy": "draft_only",
        "requires_user_confirmation": True,
        "project_root": str(project_root),
        "run_id": value.get("run_id") if value else None,
        "preset": value.get("preset", "research") if value else "research",
        "profile_id": profile.get("profile_id") or profile_ref_id,
        "stage": stage.upper() if isinstance(stage, str) else None,
        "manifest": rel_path(manifest_path, project_root) if manifest_path and manifest_path.is_file() else None,
        "profile": rel_path(profile_path, project_root) if profile_path and profile_path.is_file() else None,
        "required_human_stages": [str(item) for item in required_human if isinstance(item, str)],
        "ai_usage_state": value.get("ai_usage_state", "unknown") if value else "unknown",
        "capability_stage": capabilities.get("stage"),
        "capability_status": capabilities["stages"].get(capabilities.get("stage"), {}).get("status") if capabilities.get("stage") else None,
        "capability_missing": capabilities["stages"].get(capabilities.get("stage"), {}).get("missing", []) if capabilities.get("stage") else [],
        "planned_actions": [
            "Review the project/profile fields and stage capability report.",
            "Confirm these values before using the card to configure DSH.",
            "After setup, follow the existing Harness Gate and checkpoint policy; this card adds no approval step.",
        ],
        "boundary": "Derived view only; it creates no Gate, receipt, manifest field, or canonical artifact.",
    }
    output = project_root / ".harness" / "views" / "SETUP_CARD.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_setup_card(card), encoding="utf-8")
    card["output"] = rel_path(output, project_root)
    return card


def render_setup_card(card: Mapping[str, Any]) -> str:
    missing = card.get("capability_missing") or []
    lines = [
        "# DSH Setup Card",
        "",
        "> DRAFT ONLY — this card does not execute commands or assert Gate readiness.",
        "> Confirm its values before applying DSH setup; normal workflow commands remain governed by existing Gates.",
        "",
        "## Project binding",
        "",
        f"- project root: `{card.get('project_root')}`",
        f"- run id: `{card.get('run_id') or 'uninitialized'}`",
        f"- preset: `{card.get('preset')}`",
        f"- profile: `{card.get('profile_id') or 'unresolved'}` ({card.get('profile') or 'not found'})",
        f"- manifest: `{card.get('manifest') or 'not found'}`",
        f"- AI usage state: `{card.get('ai_usage_state')}`",
        f"- required human stages: {', '.join(card.get('required_human_stages', [])) or 'none declared'}",
        "",
        "## Capability readout",
        "",
        f"- requested stage: `{card.get('stage') or 'all'}`",
        f"- stage status: `{card.get('capability_status') or 'not selected'}`",
        f"- missing capabilities: {', '.join(str(item) for item in missing) or 'none reported'}",
        "",
        "## Confirmation checklist",
        "",
        "- [ ] The project root and competition profile are correct.",
        "- [ ] The intended stage and its capability requirements are understood.",
        "- [ ] Required human checkpoints and AI-use obligations are assigned.",
        "- [ ] A human has confirmed the setup values shown on this card.",
        "",
        "## Planned actions (not executed)",
        "",
    ]
    lines.extend(f"{index}. {action}" for index, action in enumerate(card.get("planned_actions", []), start=1))
    lines.extend(["", f"_Boundary: {card.get('boundary')}_", ""])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--manifest")
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        card = build_setup_card(Path(args.project_root), manifest=args.manifest, stage=args.stage)
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)]}, ensure_ascii=False))
        return 1
    result = {"ok": True, **card}
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else f"setup card (draft only): {card['output']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
