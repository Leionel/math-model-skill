#!/usr/bin/env python3
"""Thin user-facing CLI for the math-modeling evidence Harness.

The CLI resolves a project root, resolves one capability preset, and dispatches
to the existing receipts, checkers, freeze, and migration scripts. It does
not implement Gate policy or create a second orchestration engine.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))

from _common import child_env, exclusive_path_lock, load_structured, rel_path, resolve_ai_usage_state, resolve_path, sha256_file, write_json_atomic  # noqa: E402
from figures.tool_router import route_figure  # noqa: E402
from figures.pptx_router import stage_pptx_reference  # noqa: E402
from figures.illustration_execution import build_image_generation_request, collect_illustration_output  # noqa: E402
from human_surface import (  # noqa: E402
    authoring_context,
    compile_figure_diagram_spec,
    compile_model_contract,
    compile_paper_plan,
    compile_research_basis,
    compile_solution_implementation_map,
    ensure_figure_brief,
    ensure_human_surface,
    ensure_section,
)
from profiles.normalization import canonicalize_competition_profile, resolve_profile  # noqa: E402
from runtime_state import RuntimeStateError, load_runtime_state  # noqa: E402
from project_layout import StateLayoutError, active_state_layout, existing_control_paths, resolve_manifest_path  # noqa: E402
from state_layout_migration import migrate_flat_control_state_to_hidden  # noqa: E402
from views.implementation_tasks import compile_implementation_tasks  # noqa: E402
from views.writing_spine import compile_section_brief, compile_writing_spine  # noqa: E402
from views.setup_card import build_setup_card  # noqa: E402
from precedents.select_reference_cards import select_cards  # noqa: E402
from qa.plan_selective_rerun import plan_selective_rerun  # noqa: E402
from doctor_core import STAGES as DOCTOR_STAGES, evaluate_capabilities  # noqa: E402


GATE_ORDER = ("m1", "p1", "p2", "w1", "w2", "s1")
PRESETS = ("sprint", "research", "submission")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def _configure_utf8_output() -> None:
    """Keep Chinese CLI help usable in legacy Windows console code pages."""

    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def _emit(value: Any, *, machine: bool, human: str | None = None) -> None:
    if machine:
        print(json.dumps(value, ensure_ascii=False))
    elif human is not None:
        print(human)
    elif isinstance(value, Mapping) and value.get("status") == "error":
        print(_json(value), end="")
    else:
        print(_json(value), end="")


def _project(args: argparse.Namespace) -> Path:
    raw = getattr(args, "project", None) or getattr(args, "project_root", None) or "."
    return Path(raw).resolve()


def _manifest_path(root: Path, raw: str | None = None) -> Path:
    return resolve_manifest_path(root, raw)


def _parse_overrides(values: list[str] | None) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    for raw in values or []:
        if "=" not in raw:
            raise ValueError(f"override must be KEY=VALUE, got {raw!r}")
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError("override key must not be empty")
        if value.lower() in {"true", "false"}:
            parsed: Any = value.lower() == "true"
        else:
            parsed = value
        overrides[key] = parsed
    return overrides


def _deep_merge(base: Mapping[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)  # type: ignore[arg-type]
        else:
            merged[key] = value
    return merged


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ImportError:  # pragma: no cover - CI installs the declared dependency
        # Keep the new-project entry point usable in a minimal Python install.
        # The repository ships three small, reviewed maintainer seeds; their
        # fallback is intentionally data-only and still marked ``seed`` below.
        builtin: dict[str, dict[str, Any]] = {
            "_base_cumcm.yaml": {
                "competition_family": "cumcm", "language": "zh-CN", "default_engine": "xelatex",
                "base_template": "cumcm-2026-electronic", "rules": {"page_limit": 25, "page_count_scope": "paper_body"},
                "ai_disclosure": {"policy": "required_when_used", "format": "support_material_pdf", "manual_checks": {"when_used": ["ai_generated_content_marked", "ai_tool_in_references", "ai_disclosure_in_support"], "when_not_used": ["no_ai_declaration_after_references"]}},
                "submission": {"required_files": [{"role": "paper", "format": "pdf"}], "support_zip": {"policy": "required"}},
            },
            "_base_mcm_icm.yaml": {
                "competition_family": "mcm_icm", "language": "en-US", "default_engine": "pdflatex",
                "base_template": "mcm-icm-2026", "rules": {"page_limit": 25, "page_count_scope": "paper_body", "max_pages_excludes_ai_report": True},
                "ai_disclosure": {"policy": "required_when_used", "format": "in_paper_section", "manual_checks": {"when_used": ["ai_inline_citations", "ai_tool_in_references", "ai_report_in_paper", "ai_report_position"], "when_not_used": []}},
                "submission": {"required_files": [{"role": "paper", "format": "pdf"}], "support_zip": {"policy": "prohibited"}},
            },
            "cumcm.yaml": {"profile_id": "cumcm-2026-electronic", "competition_name": "2026年全国大学生数学建模竞赛", "season": "2026", "overrides": {"rules": {"page_limit": 25}}, "inherits": "_base_cumcm"},
            "mcm_icm.yaml": {"profile_id": "mcm_icm", "competition_name": "2026 Mathematical Contest in Modeling (MCM/ICM)", "season": "2026", "overrides": {"rules": {"page_limit": 25}}, "inherits": "_base_mcm_icm"},
            "apmcm.yaml": {"profile_id": "apmcm", "competition_name": "亚太地区大学生数学建模竞赛 (APMCM)", "season": "2026", "overrides": {"language": "en-US", "rules": {"page_limit": 25}, "ai_disclosure": {"policy": "required_when_used", "format": "in_paper_section"}}, "inherits": "_base_cumcm"},
        }
        key = path.name
        if key not in builtin:
            raise RuntimeError("init requires PyYAML for custom YAML seeds; install requirements-dev.txt")
        value = builtin[key]
        inherited = value.get("inherits")
        if isinstance(inherited, str):
            parent = (path.parent / inherited).with_suffix(path.suffix)
            value = _deep_merge(_load_yaml(parent), value)
        overrides = value.get("overrides")
        if isinstance(overrides, Mapping):
            value = _deep_merge(value, overrides)
            value.pop("overrides", None)
        return value
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError(f"competition seed must be a YAML object: {path}")
    inherited = value.get("inherits")
    if isinstance(inherited, str):
        parent = (path.parent / inherited).resolve()
        if parent.suffix.lower() not in {".yaml", ".yml"}:
            parent = parent.with_suffix(path.suffix)
        if not parent.is_file():
            raise FileNotFoundError(f"competition seed inherits missing file: {parent}")
        parent_value = _load_yaml(parent)
        value = _deep_merge(parent_value, value)
    overrides = value.get("overrides")
    if isinstance(overrides, Mapping):
        value = _deep_merge(value, overrides)
        value.pop("overrides", None)
    return dict(value)


def _seed_path(selector: str) -> Path | None:
    candidate = Path(selector)
    if candidate.is_file():
        return candidate.resolve()
    for name in (selector, selector.lower(), selector.replace("-", "_")):
        for suffix in (".yaml", ".yml"):
            path = REPO_ROOT / "competition_profiles" / f"{name}{suffix}"
            if path.is_file() and not path.name.startswith("_"):
                return path.resolve()
    return None


def _competition_seed(selector: str) -> tuple[dict[str, Any], str]:
    path = _seed_path(selector)
    if path is not None:
        seed = _load_yaml(path)
        return seed, rel_path(path, REPO_ROOT)
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", selector).strip("-") or "custom"
    return {
        "profile_id": safe,
        "competition_family": safe,
        "competition_name": selector,
        "season": "unknown",
        "language": "unknown",
        "base_template": "unresolved-template",
        "rules": {},
        "ai_disclosure": {},
        "submission": {},
    }, "inline seed"


def _init_profile(selector: str) -> tuple[dict[str, Any], str]:
    legacy_seed, source = _competition_seed(selector)
    profile, notes = canonicalize_competition_profile(legacy_seed, mode="pre_contest")
    # A maintainer YAML is a starting point, never an official rule snapshot.
    # Keep this explicit even when a seed happens to contain page limits.
    profile["status"] = "seed"
    metadata = profile.setdefault("metadata", {})
    if isinstance(metadata, dict):
        metadata.update({"source": "maintainer_seed", "seed_source": source, "official_verified": False})
        if notes.get("unresolved"):
            metadata["unresolved_count"] = len(notes["unresolved"])
    return profile, source


def _init(args: argparse.Namespace) -> int:
    root = _project(args)
    try:
        active_state_layout(root)
    except StateLayoutError as exc:
        raise ValueError(f"project has an incomplete Harness state layout: {exc}") from exc
    if root.exists() and any(root.iterdir()) and not args.force:
        existing = [
            rel_path(path, root)
            for paths in existing_control_paths(root).values()
            for path in paths
        ]
        if existing:
            raise ValueError(f"project already contains Harness state ({', '.join(existing)}); use a new root or --force")
    root.mkdir(parents=True, exist_ok=True)
    profile, source = _init_profile(args.competition)
    overrides = _parse_overrides(args.override)
    # Resolve now so invalid/unsafe overrides fail before any file is written.
    resolve_profile(args.preset, overrides)
    project_name = re.sub(r"[^A-Za-z0-9_.-]+", "-", root.name).strip("-") or "math-project"
    project_id = f"{project_name}-{uuid.uuid4().hex[:8]}"
    run_id = f"run-{uuid.uuid4().hex[:12]}"
    profile_id = str(profile["profile_id"])
    now = datetime.now(timezone.utc).isoformat()
    manifest = {
        "schema_version": "2.0",
        "project_id": project_id,
        "run_id": run_id,
        "status": "active",
        "stage": "analysis",
        "preset": args.preset,
        "profile_overrides": overrides,
        "competition_profile_ref": {"path": "competition_profile.json", "profile_id": profile_id},
        "roots": {
            "artifact_dag": {"path": "artifact_dag.json"},
            "run_index": {"path": "run_index.json"},
        },
        "control": {
            "selection_policy": {
                "owner": "run_manifest.control",
                "rule": "select exactly one successful full receipt after independent validation",
                "version": "2.0",
            },
            "required_human_stages": ["m1", "p2"] if args.preset == "sprint" else (["m1", "p2", "w1", "w2"] if args.preset == "research" else ["m1", "p2", "w1", "w2", "s1", "f1"]),
            "historical_evidence_policy": "preserve",
        },
        "safety": {"contest_safety": "required"},
        "ai_usage_state": "unknown",
        "ai_usage": [],
        "human_checkpoints": [],
    }
    dag = {
        "schema_version": "2.0",
        "run_id": run_id,
        "projection": "artifact_identity_dependency",
        "generated_at": now,
        "nodes": [{
            "artifact_id": f"PROFILE-{re.sub(r'[^A-Za-z0-9]+', '-', profile_id).upper()}",
            "role": "competition_profile",
            "path": "competition_profile.json",
            "producer_id": "harness.init",
            "dependencies": [],
            "lifecycle": "mutable",
            "freshness": "current",
            "critical": False,
            "version": "1",
            "created_at": now,
            "digest_owner": "artifact_dag",
            "metadata": {"status": "seed", "official_verified": False},
        }],
    }
    index = {
        "schema_version": "2.0",
        "projection": "receipt_selection",
        "run_id_scope": run_id,
        "receipts": [],
        "selection": {
            "policy_ref": {"owner": "run_manifest.control", "path": "run_manifest.json#/control/selection_policy", "version": "2.0"},
            "selected_receipt_ids": [],
        },
    }
    outputs = {
        "competition_profile.json": profile,
        "run_manifest.json": manifest,
        "artifact_dag.json": dag,
        "run_index.json": index,
    }
    for name, value in outputs.items():
        path = root / name
        if path.exists() and not args.force:
            raise ValueError(f"refusing to overwrite existing file: {path}")
        path.write_text(_json(value), encoding="utf-8")
    human_surface = ensure_human_surface(root)
    result = {"ok": True, "schema_version": "2.0", "project_root": str(root), "preset": args.preset, "competition": args.competition, "profile_status": "seed", "profile_source": source, "files": sorted(outputs), "human_surface": human_surface}
    _emit(result, machine=args.json, human=f"initialized v2 project at {root}\npreset: {args.preset}\ncompetition profile: seed ({source})\nfiles: {', '.join(sorted(outputs))}")
    return 0


def _dispatch(command: list[str], root: Path) -> int:
    # Keep child stdout/stderr and exit code transparent: the CLI is not a
    # wrapper around Gate policy and does not reinterpret checker results.
    return subprocess.run(command, cwd=str(root), env=child_env(), check=False).returncode


def _check(args: argparse.Namespace, gate: str | None = None) -> int:
    root = _project(args)
    manifest = _manifest_path(root, args.manifest)
    requested_preset = getattr(args, "requested_preset", None)
    if requested_preset is not None:
        value = load_structured(manifest)
        if not isinstance(value, Mapping):
            raise ValueError("run manifest must be an object")
        actual_preset = value.get("preset") if value.get("schema_version") == "2.0" else value.get("integrity_mode")
        if actual_preset != requested_preset:
            raise ValueError(
                f"--profile {requested_preset} conflicts with the manifest-owned preset {actual_preset!r}; "
                "do not override Gate policy at check time"
            )
    selected = (gate or args.gate).lower()
    command = [sys.executable, str(SCRIPT_DIR / "qa" / "check_gates.py"), "--manifest", str(manifest), "--project-root", str(root), "--gate", selected]
    if args.strict:
        command.append("--strict")
    return _dispatch(command, root)


def _validate(args: argparse.Namespace) -> int:
    # The existing v2 W2 gate dispatches run_deterministic_qa.py with the
    # canonical roots and capability flags. No QA rules are copied here.
    return _check(args, gate="w2")


def _review(args: argparse.Namespace) -> int:
    root = _project(args)
    manifest = _manifest_path(root, args.manifest)
    command = [sys.executable, str(SCRIPT_DIR / "qa" / "run_review.py"), "--manifest", str(manifest), "--project-root", str(root)]
    for flag in ("semantic", "judge", "fresh", "recheck", "json"):
        if getattr(args, flag, False):
            command.append(f"--{flag}")
    if args.backend_cmd:
        command.extend(["--backend-cmd", args.backend_cmd])
        if not args.backend_kind:
            raise ValueError("--backend-cmd requires --backend-kind=ai or --backend-kind=non_ai")
        command.extend(["--backend-kind", args.backend_kind])
        missing = [name for name in ("ai_tool_name", "ai_model", "ai_provider") if not getattr(args, name)]
        if args.backend_kind == "ai" and missing:
            raise ValueError("--backend-cmd requires --ai-tool-name, --ai-model, and --ai-provider")
        if args.backend_kind == "ai":
            command.extend([
                "--ai-tool-name", args.ai_tool_name,
                "--ai-model", args.ai_model,
                "--ai-provider", args.ai_provider,
            ])
    return _dispatch(command, root)


def _run(args: argparse.Namespace) -> int:
    root = _project(args)
    manifest = _manifest_path(root, args.manifest)
    manifest_value = load_structured(manifest) if manifest.is_file() else None
    state = None
    if isinstance(manifest_value, Mapping) and manifest_value.get("schema_version") == "2.0":
        state = load_runtime_state(manifest, project_root=root, allow_legacy=False)
    if args.run_id is None:
        args.run_id = manifest_value.get("run_id") if isinstance(manifest_value, Mapping) else None
        if not isinstance(args.run_id, str) or not args.run_id:
            raise ValueError("run requires --run-id when run_manifest.json is absent")
    receipt = args.receipt or f"receipts/{args.stage}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}.json"
    if args.index:
        index = args.index
    elif state is not None:
        index_path = state.root_path("run_index", required=True)
        assert index_path is not None
        index = rel_path(index_path, root)
    else:
        index = "run_index.json"
    command = [sys.executable, str(SCRIPT_DIR / "run_and_record.py"), "--run-id", args.run_id, "--stage", args.stage, "--receipt", receipt, "--index", index, "--project-root", str(root)]
    if state is not None:
        command[2:2] = ["--manifest", str(manifest)]
    else:
        command[2:2] = ["--v2", "--integrity-mode", args.preset]
    if args.selected:
        command.append("--selected")
    if args.freeze:
        command.append("--freeze")
    if args.seed is not None:
        command.extend(["--seed", str(args.seed)])
    for path in args.input:
        command.extend(["--input", path])
    for path in args.output_artifact:
        command.extend(["--output-artifact", path])
    for value in getattr(args, "covers_model", []):
        command.extend(["--covers-model", value])
    for value in getattr(args, "covers_question", []):
        command.extend(["--covers-question", value])
    for value in getattr(args, "covers_contract_item", []):
        command.extend(["--covers-contract-item", value])
    command.append("--")
    command.extend(args.command)
    return _dispatch(command, root)


def _freeze(args: argparse.Namespace) -> int:
    root = _project(args)
    if args.kind == "submission":
        required = (args.run_manifest, args.s1_report, args.paper, args.deadline, args.timezone, args.output)
        if any(value is None for value in required):
            raise ValueError("submission freeze requires --run-manifest, --s1-report, --paper, --deadline, --timezone, and --output")
        command = [sys.executable, str(SCRIPT_DIR / "freeze_submission.py"), "--run-manifest", args.run_manifest, "--s1-report", args.s1_report, "--paper", args.paper, "--deadline", args.deadline, "--timezone", args.timezone, "--output", args.output, "--project-root", str(root)]
        for path in args.support:
            command.extend(["--support", path])
        if args.ai_disclosure:
            command.extend(["--ai-disclosure", args.ai_disclosure])
    else:
        required = (args.source, args.output, args.run_id, args.model_contract)
        if any(value is None for value in required) or not args.code or not args.validation:
            raise ValueError("result freeze requires --source, --output, --run-id, --model-contract, --code, and --validation")
        command = [sys.executable, str(SCRIPT_DIR / "freeze_results.py"), "--source", args.source, "--output", args.output, "--run-id", args.run_id, "--model-contract", args.model_contract, "--project-root", str(root)]
        for path in args.code:
            command.extend(["--code", path])
        for path in args.validation:
            command.extend(["--validation", path])
        for path in args.input:
            command.extend(["--input", path])
        for key in ("manifest", "receipt", "selected_receipt", "freeze_receipt", "run_index", "command"):
            value = getattr(args, key, None)
            if value:
                command.extend([f"--{key.replace('_', '-')}", value])
        if args.integrity_mode:
            command.extend(["--integrity-mode", args.integrity_mode])
    return _dispatch(command, root)


def _write_manifest_atomic(path: Path, value: Mapping[str, Any]) -> None:
    write_json_atomic(path, value)


def _refresh_ai_ledger(root: Path, manifest_path: Path) -> str:
    from prepare_project import refresh_ai_ledger

    state = load_runtime_state(manifest_path, project_root=root, allow_legacy=False)
    ledger_path, _ = refresh_ai_ledger(state)
    return rel_path(ledger_path, root)


def _ai(args: argparse.Namespace) -> int:
    root = _project(args)
    manifest_path = _manifest_path(root, args.manifest)
    action = args.ai_action
    if action == "status":
        state = load_runtime_state(manifest_path, project_root=root, allow_legacy=False)
        manifest = dict(state.manifest)
        rows = manifest.get("ai_usage", [])
        if not isinstance(rows, list):
            raise ValueError("run_manifest.ai_usage must be an array")
        result = {
            "ok": True,
            "ai_usage_state": resolve_ai_usage_state(manifest),
            "record_count": len(rows),
            "declared": "ai_usage_state" in manifest,
            "declaration": manifest.get("ai_usage_declaration"),
        }
        _emit(result, machine=args.json, human=f"AI usage: {result['ai_usage_state']} ({len(rows)} records)")
        return 0
    with exclusive_path_lock(manifest_path):
        state = load_runtime_state(manifest_path, project_root=root, allow_legacy=False)
        manifest = dict(state.manifest)
        rows = manifest.get("ai_usage", [])
        if not isinstance(rows, list):
            raise ValueError("run_manifest.ai_usage must be an array")
        if action == "verify":
            matched = [index for index, row in enumerate(rows) if isinstance(row, Mapping) and row.get("usage_id") == args.usage_id]
            if not matched:
                raise ValueError(f"unknown AI usage_id: {args.usage_id}")
            index = matched[0]
            updated = dict(rows[index])
            updated["human_changes"] = args.human_changes
            updated["verification"] = {
                "status": "verified",
                "checked_by_role": args.checked_by_role,
                "method": args.verification_method,
                "checked_at": args.checked_at or datetime.now(timezone.utc).isoformat(),
            }
            manifest["ai_usage"] = [*rows[:index], updated, *rows[index + 1:]]
            manifest["ai_usage_state"] = "used"
            manifest.pop("ai_usage_declaration", None)
            _write_manifest_atomic(manifest_path, manifest)
            result = {
                "ok": True, "ai_usage_state": "used", "usage_id": args.usage_id,
                "verification_status": "verified", "manifest": rel_path(manifest_path, root),
                "ledger": _refresh_ai_ledger(root, manifest_path),
            }
            _emit(result, machine=args.json, human=f"verified AI use {args.usage_id}")
            return 0
        if action == "confirm-none":
            if rows:
                raise ValueError("cannot declare no AI use while ai_usage contains records")
            now = args.confirmed_at or datetime.now(timezone.utc).isoformat()
            manifest["ai_usage_state"] = "none"
            manifest["ai_usage_declaration"] = {
                "status": "none",
                "confirmed_by": args.confirmed_by,
                "confirmed_at": now,
                "reason": args.reason,
            }
            _write_manifest_atomic(manifest_path, manifest)
            result = {"ok": True, "ai_usage_state": "none", "manifest": rel_path(manifest_path, root), "ledger": _refresh_ai_ledger(root, manifest_path)}
            _emit(result, machine=args.json, human="AI usage explicitly declared: none")
            return 0
        record_path = resolve_path(args.interaction_record, root).resolve()
        if not record_path.is_file():
            raise ValueError(f"interaction record does not exist: {record_path}")
        try:
            record_path.relative_to(root)
        except ValueError as exc:
            raise ValueError("interaction record must be inside the project root for portable audit evidence") from exc
        used_at = args.used_at or datetime.now(timezone.utc).isoformat()
        checked_at = args.checked_at or datetime.now(timezone.utc).isoformat()
        usage_id = args.usage_id or f"AI-{uuid.uuid4().hex[:12].upper()}"
        if any(isinstance(row, Mapping) and row.get("usage_id") == usage_id for row in rows):
            raise ValueError(f"duplicate AI usage_id: {usage_id}")
        record = {
            "usage_id": usage_id,
            "tool_name": args.tool_name,
            "model": args.model,
            "provider": args.provider,
            "used_at": used_at,
            "stage": args.stage,
            "purpose": args.purpose,
            "prompt_summary": args.prompt_summary,
            "output_use": args.output_use,
            "human_changes": args.human_changes,
            "interaction_record": {"path": rel_path(record_path, root), "sha256": sha256_file(record_path)},
            "verification": {
                "status": "verified",
                "checked_by_role": args.checked_by_role,
                "method": args.verification_method,
                "checked_at": checked_at,
            },
        }
        manifest["ai_usage"] = [*rows, record]
        manifest["ai_usage_state"] = "used"
        manifest.pop("ai_usage_declaration", None)
        _write_manifest_atomic(manifest_path, manifest)
        result = {"ok": True, "ai_usage_state": "used", "usage_id": usage_id, "record_count": len(rows) + 1, "manifest": rel_path(manifest_path, root), "ledger": _refresh_ai_ledger(root, manifest_path)}
    _emit(result, machine=args.json, human=f"recorded AI use {usage_id}; total records: {len(rows) + 1}")
    return 0


def _prepare(args: argparse.Namespace) -> int:
    root = _project(args)
    manifest = _manifest_path(root, args.manifest)
    return _dispatch([sys.executable, str(SCRIPT_DIR / "prepare_project.py"), args.stage, "--project-root", str(root), "--manifest", str(manifest)], root)


def _research(args: argparse.Namespace) -> int:
    root = _project(args)
    if args.compile:
        result = compile_research_basis(
            root,
            source=args.source,
            output=args.output,
            model_schema_path=REPO_ROOT / "schemas" / "model_contract.schema.json",
        )
        _emit(result, machine=args.json, human=f"research basis IR compiled: {result['output']}")
        return 0
    surface = ensure_human_surface(root)
    result = {
        "ok": True,
        "human_surface": surface,
        "read": "00_PROJECT_BRIEF.md",
        "authoring_target": "01_RESEARCH_NOTES.md",
        "checkpoint": {
            "message": "Research notes are ready to author. Review problem interpretation, candidate coverage, rejected methods, and unresolved questions before model selection.",
            "gate": "none",
        },
        "compile_hint": "When a machine consumer needs a structured research basis, add the explicit YAML source block and run `harness research --compile`.",
    }
    _emit(result, machine=args.json, human="research authoring surface ready\nread: 00_PROJECT_BRIEF.md\nwrite: 01_RESEARCH_NOTES.md")
    return 0


def _precedents(args: argparse.Namespace) -> int:
    result = select_cards(
        competition=args.competition,
        problem_family=args.problem_family,
        evidence_role=args.evidence_role,
        data_shape=args.data_shape,
        semantic_type=args.semantic_type,
        card_kind=args.card_kind,
        limit=args.limit,
    )
    lines = [
        f"selected {len(result['selected'])}/{result['available']} {result['card_kind']} card(s)",
    ]
    lines.extend(
        f"- {row.get('card_id')}: {row.get('title')} ({row.get('path')})"
        for row in result["selected"]
    )
    if result.get("competition_index_last_reviewed"):
        lines.append(f"competition index last reviewed: {result['competition_index_last_reviewed']}")
    lines.append(result["note"])
    _emit(result, machine=args.json, human="\n".join(lines))
    return 0


def _model(args: argparse.Namespace) -> int:
    if args.research_source and not args.compile:
        raise ValueError("--research-source requires --compile")
    root = _project(args)
    if args.compile:
        result = compile_model_contract(
            root,
            source=args.source,
            output=args.output,
            schema_path=REPO_ROOT / "schemas" / "model_contract.schema.json",
            manifest_path=_manifest_path(root),
            research_source=args.research_source,
        )
    else:
        result = {
            "ok": True,
            "human_surface": ensure_human_surface(root),
            "read": "01_RESEARCH_NOTES.md",
            "authoring_target": "02_MODEL_DECISION.md",
            "checkpoint": {
                "message": "Model selection ready for review. Check candidate coverage, selected-model rationale, inter-question dependencies, and the validation plan.",
                "actions": ["continue", "revise", "research-more"],
                "gate": "m1",
            },
            "compile_hint": "When a machine consumer needs the decision, add the explicit YAML source block and run `harness model --compile`.",
        }
    _emit(result, machine=args.json, human="model authoring surface ready\nread: 01_RESEARCH_NOTES.md\nwrite: 02_MODEL_DECISION.md")
    return 0


def _solve(args: argparse.Namespace) -> int:
    root = _project(args)
    ensure_human_surface(root)
    if args.rerun_plan:
        if args.compile or args.command or args.tasks:
            raise ValueError("--rerun-plan cannot be combined with --tasks, --compile, or a receipt-captured command")
        if args.output:
            raise ValueError("--rerun-plan writes to .harness/views/RERUN_PLAN.md and cannot take --output")
        result = plan_selective_rerun(root, dag=args.dag, changed=args.changed)
        affected = len(result.get("affected_artifact_ids", []))
        pending = ", ".join(result.get("pending_gates", {})) or "none"
        human = (
            f"rerun plan projected: {affected} affected artifact(s), gates to re-evaluate: {pending}\n"
            f"view: {result.get('markdown')}\n"
            "projection only — no command was executed"
        )
        _emit(result, machine=args.json, human=human)
        return 0 if result.get("ok") else 1
    if args.tasks:
        if args.compile or args.command:
            raise ValueError("--tasks cannot be combined with --compile or a receipt-captured command")
        if args.output:
            raise ValueError("--tasks writes to .harness/views/IMPLEMENTATION_TASKS.md and cannot take --output")
        result = compile_implementation_tasks(
            root,
            model_contract=args.model_contract,
        )
        _emit(result, machine=args.json, human=f"implementation task view compiled: {result['tasks']} tasks\nview: {result['markdown']}")
        return 0
    if args.compile:
        if args.command:
            raise ValueError("--compile cannot be combined with a receipt-captured command")
        result = compile_solution_implementation_map(
            root,
            source=args.source,
            output=args.output,
            schema_path=REPO_ROOT / "schemas" / "implementation_map.schema.json",
            manifest_path=_manifest_path(root, args.manifest),
        )
        _emit(result, machine=args.json, human=f"implementation-map IR compiled: {result['output']}")
        return 0
    if not args.command:
        result = {
            "ok": True,
            "execution_started": False,
            "read": "02_MODEL_DECISION.md",
            "authoring_target": "03_SOLUTION_REPORT.md",
            "next_action": "Run a real command after `--`; the existing receipt producer and validation Gate remain authoritative.",
        }
        _emit(result, machine=args.json, human="solve surface ready; no computation was run\nread: 02_MODEL_DECISION.md\nupdate after a real receipt: 03_SOLUTION_REPORT.md")
        return 0
    run_args = argparse.Namespace(
        project=str(root), manifest=args.manifest, run_id=args.run_id, stage=args.execution_stage,
        receipt=args.receipt, index=args.index, preset=args.preset, selected=args.selected,
        freeze=False, seed=args.seed, input=args.input, output_artifact=args.output_artifact,
        covers_model=args.covers_model, covers_question=args.covers_question,
        covers_contract_item=args.covers_contract_item,
        command=args.command,
    )
    return _run(run_args)


def _paper(args: argparse.Namespace) -> int:
    root = _project(args)
    if args.paper_action == "plan":
        if args.compile:
            result = compile_paper_plan(
                root,
                source=args.source,
                output=args.output,
                schema_path=REPO_ROOT / "schemas" / "paper_plan.schema.json",
                manifest_path=_manifest_path(root),
            )
            human = f"paper-plan IR compiled: {result['output']}"
        else:
            result = {
                "ok": True,
                "human_surface": ensure_human_surface(root),
                "authoring_target": "paper/00_PAPER_PLAN.md",
                "compile_hint": "When a machine consumer needs the plan, add the explicit YAML source block and run `harness paper plan --compile`.",
            }
            human = "Paper Director Plan surface ready\nwrite: paper/00_PAPER_PLAN.md"
    else:
        section_action = getattr(args, "paper_section_action", args.paper_action)
        section = ensure_section(root, args.section, role=getattr(args, "role", None))
        action = "semantic review" if section_action == "review" else "draft"
        writer_view = _section_writer_view(root, section["section"])
        result = {
            "ok": True,
            "section": section,
            "action": action,
            "writer_view": writer_view,
            "context": authoring_context(root, f"paper:{section['section']}"),
            "boundary": "Only this section was scaffolded; no other section, result, or Gate state was changed.",
        }
        human = f"paper {section_action} surface ready\nsection: {section['section']}\npath: {section['path']}"
        if writer_view.get("brief"):
            human += f"\nwriter brief: {writer_view['brief']}"
        if writer_view.get("why_skipped"):
            human += f"\nwriter brief skipped: {writer_view['why_skipped']}"
    _emit(result, machine=args.json, human=human)
    return 0


def _section_writer_view(root: Path, section_id: str) -> dict[str, Any]:
    """Compile the section-scoped Writer Brief view when a compiled plan exists.

    The view is a regenerable projection under `.harness/views/`; it never
    touches author Markdown under `paper/` and never becomes a truth source.
    """

    plan_path = root / ".harness" / "contracts" / "paper_plan.json"
    package_path = root / ".harness" / "reports" / "writer_package.json"
    if not plan_path.is_file():
        return {"brief": None, "why_skipped": "no compiled paper_plan.json; run `harness paper plan --compile` first"}
    try:
        result = compile_section_brief(
            root,
            paper_plan=str(plan_path),
            section_id=section_id,
            writer_package=str(package_path) if package_path.is_file() else None,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        return {"brief": None, "why_skipped": f"section brief compilation failed: {exc}"}
    spine = None
    try:
        spine = compile_writing_spine(
            root,
            paper_plan=str(plan_path),
            writer_package=str(package_path) if package_path.is_file() else None,
        )
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        spine = None  # the section brief is the load-bearing view; spine is additive
    return {
        "brief": result["markdown"],
        "json": result["json"],
        "units": result["units"],
        "writer_package_used": package_path.is_file(),
        "spine": spine["markdown"] if spine else None,
    }


def _figure(args: argparse.Namespace) -> int:
    root = _project(args)
    if args.compile:
        if args.prepare_pptx:
            raise ValueError("--compile cannot be combined with --prepare-pptx")
        result = {
            "ok": True,
            "diagram_spec": compile_figure_diagram_spec(
                root,
                args.figure_id,
                source=args.source,
                output=args.output,
                schema_path=REPO_ROOT / "schemas" / "diagram_spec.schema.json",
            ),
        }
        _emit(result, machine=args.json, human=f"diagram-spec IR compiled: {result['diagram_spec']['output']}")
        return 0
    brief = ensure_figure_brief(root, args.figure_id)
    topology = {
        key: getattr(args, key)
        for key in ("node_count", "dag_depth", "branch_count", "feedback_edges", "parallel_lanes", "density", "target_aspect_ratio", "reading_order")
        if getattr(args, key) is not None
    }
    if args.native_topology_qa:
        topology["native_topology_qa"] = True
    route = route_figure(
        args.kind,
        args.semantic_type,
        args.fallback_reason,
        diagram_backend=args.diagram_backend,
        pptx_reference=args.pptx_reference,
        topology=topology or None,
    )
    if args.request_illustration or args.collect_illustration:
        if args.prepare_pptx:
            raise ValueError("illustration execution cannot be combined with --prepare-pptx")
        result = _run_illustration_protocol(args, root, brief, route)
        _emit(result, machine=args.json, human=_illustration_human(result))
        return 0 if result.get("ok") else 1
    staged = None
    if args.prepare_pptx:
        if route["default_tool"] != "pptx_template":
            raise ValueError("--prepare-pptx requires a diagram routed to PPTX")
        staged = stage_pptx_reference(root, args.figure_id, route["reference"])
    result = {
        "ok": True,
        "brief": brief,
        "route": route,
        "boundary": "The router creates no visual claim and does not replace Figure Contract, source evidence, or final-size review.",
    }
    if staged is not None:
        result["pptx_editable_copy"] = staged
    human = f"figure brief ready: {brief['path']}\nroute: {route['default_tool']}"
    if staged is not None:
        human += f"\npptx copy: {staged['path']}"
    _emit(result, machine=args.json, human=human)
    return 0


def _run_illustration_protocol(args: argparse.Namespace, root: Path, brief: dict[str, Any], route: dict[str, Any]) -> dict[str, Any]:
    """Request or collect a native image generation for an illustration figure."""

    figure_id = args.figure_id
    brief_path = Path(brief["path"]) / "brief.md"
    request_path = root / ".harness" / "views" / "figures" / f"{figure_id}_image_generation_request.json"
    if args.request_illustration and args.collect_illustration:
        raise ValueError("choose either --request-illustration or --collect-illustration, not both")
    if args.request_illustration:
        request = build_image_generation_request(
            figure_id=figure_id,
            brief_path=brief_path,
            root=root,
            route=route,
            capability=args.capability,
            ai_policy=args.ai_policy,
        )
        if request.get("ok"):
            request_path.parent.mkdir(parents=True, exist_ok=True)
            write_json_atomic(request_path, request)
            request["request_path"] = rel_path(request_path, root)
        return request
    collected = collect_illustration_output(
        figure_id=figure_id,
        generated_path=resolve_path(args.collect_illustration, root).resolve(),
        root=root,
        request_path=request_path,
    )
    if collected.get("ok"):
        record_path = root / "figures" / figure_id / "illustration.json"
        record_path.parent.mkdir(parents=True, exist_ok=True)
        write_json_atomic(record_path, collected)
        collected["record_path"] = rel_path(record_path, root)
        collected["next_actions"] = [
            "run scientific, visual, and final-size review before treating the figure as formal",
            "register the generator in run_manifest.ai_usage (harness ai record) and run `harness ai verify` before strict promotion",
        ]
    return collected


def _illustration_human(result: dict[str, Any]) -> str:
    status = result.get("status")
    lines = [f"illustration protocol: {status}"]
    if result.get("request_path"):
        lines.append(f"request: {result['request_path']}")
        lines.append("call the native image-generation tool with the recorded prompt, then collect the output with --collect-illustration")
    if result.get("record_path"):
        lines.append(f"record: {result['record_path']}")
        lines.append("review pending; do not promote to W2 before review_status=reviewed")
    if result.get("message"):
        lines.append(str(result["message"]))
    if result.get("prompt") and status == "requested":
        lines.append("--- prompt ---")
        lines.append(str(result["prompt"]))
    return "\n".join(lines)


def _context(args: argparse.Namespace) -> int:
    root = _project(args)
    ensure_human_surface(root)
    result = authoring_context(root, args.stage)
    _emit(result, machine=args.json, human="context plan generated; inspect the listed files before starting the stage")
    return 0


def _submit_check(args: argparse.Namespace) -> int:
    check_args = argparse.Namespace(
        project=args.project,
        manifest=args.manifest,
        requested_preset=None,
        gate="S1",
        strict=args.strict,
    )
    return _check(check_args, gate="s1")


def _submit_receipt(args: argparse.Namespace) -> int:
    root = _project(args)
    command = [
        sys.executable,
        str(SCRIPT_DIR / "qa" / "check_submission_receipt.py"),
        "--receipt",
        args.receipt,
        "--project-root",
        str(root),
    ]
    return _dispatch(command, root)


def _profile(args: argparse.Namespace) -> int:
    root = _project(args)
    manifest = _manifest_path(root, args.manifest)
    overrides = _parse_overrides(args.override)
    if manifest.is_file():
        state = load_runtime_state(manifest, project_root=root, allow_legacy=False)
        capabilities = state.capabilities
        profile = {"path": rel_path(state.profile_path, root), "profile_id": state.profile.get("profile_id"), "status": state.profile.get("status"), "competition": state.profile.get("competition")}
        preset = state.preset
    else:
        preset = args.preset
        capabilities = resolve_profile(preset, overrides)
        profile = {"path": None, "profile_id": None, "status": "unresolved", "competition": None}
    result = {"ok": True, "preset": preset, "capabilities": capabilities.to_dict(), "profile": profile}
    _emit(result, machine=args.json, human=f"preset: {preset}\nprofile: {profile.get('profile_id') or 'unresolved'} ({profile.get('status')})\ncapabilities: {', '.join(key for key, value in capabilities.capabilities.items() if value)}")
    return 0


def _doctor(args: argparse.Namespace) -> int:
    root = _project(args)
    report = evaluate_capabilities(root, stage=args.stage, repo_root=REPO_ROOT)
    errors = list(report["errors"])
    warnings = list(report["warnings"])
    layout: str | None
    try:
        layout = active_state_layout(root)
        manifest = _manifest_path(root)
    except StateLayoutError as exc:
        layout = None
        manifest = None
        errors.append(f"project state layout cannot be resolved: {exc}")
    if manifest is not None and manifest.is_file():
        try:
            value = load_structured(manifest)
            if not isinstance(value, Mapping):
                errors.append("project run_manifest is not an object")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"project run_manifest cannot be read: {exc}")
    report["state_layout"] = layout
    report["errors"] = errors
    report["warnings"] = warnings
    report["ok"] = not errors
    _emit(report, machine=args.json, human=f"doctor: {'OK' if report['ok'] else 'BLOCKED'}\npython: {sys.version.split()[0]}\nschemas: {report['schema_count']}\nstage: {args.stage or 'all'}\noptional warnings: {len(warnings)}")
    return 0 if report["ok"] else 1


def _setup(args: argparse.Namespace) -> int:
    root = _project(args)
    card = build_setup_card(root, manifest=args.manifest, stage=args.stage)
    result = {"ok": True, **card}
    _emit(
        result,
        machine=args.json,
        human=f"setup card (draft only): {card['output']}\nconfirmation required: {card['requires_user_confirmation']}",
    )
    return 0


def _add_common(parser: argparse.ArgumentParser, *, machine: bool = True) -> None:
    parser.add_argument("--project", default=".", help="project root")
    if machine:
        parser.add_argument("--json", action="store_true", help="machine-readable output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="harness", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="create a new v2 project")
    _add_common(init)
    init.add_argument("--competition", required=True, help="competition seed name or YAML path")
    init.add_argument("--preset", choices=PRESETS, default="research")
    init.add_argument("--override", action="append", default=[])
    init.add_argument("--force", action="store_true")
    init.set_defaults(handler=_init)

    status = sub.add_parser("status", help="read-only factual status")
    _add_common(status)
    status.add_argument("--manifest", default=None)
    status.set_defaults(handler=lambda args: _status(args))

    check = sub.add_parser("check", help="run one existing Gate checker")
    _add_common(check)
    check.add_argument("gate", choices=tuple(name.upper() for name in GATE_ORDER))
    check.add_argument("--manifest", default=None)
    check.add_argument(
        "--profile",
        dest="requested_preset",
        choices=PRESETS,
        help="compatibility alias that asserts (but never overrides) the manifest-owned preset",
    )
    check.add_argument("--strict", action="store_true")
    check.set_defaults(handler=_check)

    validate = sub.add_parser("validate", help="run existing deterministic W2 QA through check_gates")
    _add_common(validate)
    validate.add_argument("--manifest", default=None)
    validate.add_argument(
        "--profile",
        dest="requested_preset",
        choices=PRESETS,
        help="assert the manifest-owned preset before W2 validation",
    )
    validate.add_argument("--strict", action="store_true")
    validate.set_defaults(handler=_validate)

    review = sub.add_parser("review", help="execute the review plane: deterministic QA, bundle, semantic critic, judge lens")
    _add_common(review)
    review.add_argument("--manifest", default=None)
    review.add_argument("--semantic", action="store_true", help="run only the semantic critic perspective")
    review.add_argument("--judge", action="store_true", help="run only the judge lens perspective")
    review.add_argument("--fresh", action="store_true", help="require fresh-context (L1) execution via --backend-cmd")
    review.add_argument("--recheck", action="store_true", help="revalidate existing review reports without executing reviewers")
    review.add_argument("--backend-cmd", help="reviewer backend command executed per perspective with MATH_REVIEW_* env")
    review.add_argument("--backend-kind", choices=("ai", "non_ai"), help="declare whether the backend invokes AI; never infer this from a command string")
    review.add_argument("--ai-tool-name", help="AI tool identity for automatic backend usage logging")
    review.add_argument("--ai-model", help="AI model identity for automatic backend usage logging")
    review.add_argument("--ai-provider", help="AI provider identity for automatic backend usage logging")
    review.set_defaults(handler=_review)

    run = sub.add_parser("run", help="capture a v2 command receipt")
    _add_common(run)
    run.add_argument("--manifest", default=None)
    run.add_argument("--stage", required=True, choices=("safety", "smoke", "full", "freeze", "evidence", "qa", "review", "submission"))
    run.add_argument("--run-id")
    run.add_argument("--receipt")
    run.add_argument("--index")
    run.add_argument("--preset", choices=PRESETS, default="research")
    run.add_argument("--selected", action="store_true")
    run.add_argument("--freeze", action="store_true")
    run.add_argument("--seed", type=int)
    run.add_argument("--input", action="append", default=[])
    run.add_argument("--output-artifact", action="append", default=[])
    run.add_argument("--covers-model", action="append", default=[], help="model id exercised by a smoke command")
    run.add_argument("--covers-question", action="append", default=[], help="question id exercised by a smoke command")
    run.add_argument("--covers-contract-item", action="append", default=[], help="equation, constraint, or validation-obligation id exercised by a smoke command")
    run.add_argument("command", nargs=argparse.REMAINDER, help="command after --")
    run.set_defaults(handler=_run)

    freeze = sub.add_parser("freeze", help="dispatch existing result/submission freeze")
    _add_common(freeze)
    freeze.add_argument("--kind", choices=("results", "submission"), default="results")
    freeze.add_argument("--source")
    freeze.add_argument("--output")
    freeze.add_argument("--run-id")
    freeze.add_argument("--model-contract")
    freeze.add_argument("--code", action="append", default=[])
    freeze.add_argument("--validation", action="append", default=[])
    freeze.add_argument("--input", action="append", default=[])
    freeze.add_argument("--manifest")
    freeze.add_argument("--receipt")
    freeze.add_argument("--selected-receipt")
    freeze.add_argument("--freeze-receipt")
    freeze.add_argument("--run-index")
    freeze.add_argument("--command")
    freeze.add_argument("--integrity-mode", choices=PRESETS)
    freeze.add_argument("--run-manifest")
    freeze.add_argument("--s1-report")
    freeze.add_argument("--paper")
    freeze.add_argument("--support", action="append", default=[])
    freeze.add_argument("--ai-disclosure")
    freeze.add_argument("--deadline")
    freeze.add_argument("--timezone")
    freeze.set_defaults(handler=_freeze)

    prepare = sub.add_parser("prepare", help="render deterministic human-facing projections without changing Gate truth")
    _add_common(prepare)
    prepare.add_argument("stage", choices=("M1", "W1", "W2", "S1"))
    prepare.add_argument("--manifest", default=None)
    prepare.set_defaults(handler=_prepare)

    research = sub.add_parser("research", help="prepare the human-authored research surface; it does not run a Gate")
    _add_common(research)
    research.add_argument("--compile", action="store_true", help="compile the explicit research-basis YAML block to JSON IR")
    research.add_argument("--source", help="research Markdown source; defaults to 01_RESEARCH_NOTES.md")
    research.add_argument("--output", help="compiled JSON path; defaults to .harness/contracts/research_basis.json")
    research.set_defaults(handler=_research)

    model = sub.add_parser("model", help="prepare model-decision authoring or compile its explicit YAML contract source")
    _add_common(model)
    model.add_argument("--compile", action="store_true", help="compile the explicit machine-contract YAML block to JSON IR")
    model.add_argument("--source", help="model decision Markdown source; defaults to 02_MODEL_DECISION.md")
    model.add_argument("--research-source", help="optional research-notes Markdown source to compile into model_contract.research_basis")
    model.add_argument("--output", help="compiled JSON path; defaults to .harness/contracts/model_contract.json")
    model.set_defaults(handler=_model)

    solve = sub.add_parser("solve", help="prepare solve authoring or dispatch one real receipt-captured command")
    solve.add_argument("--tasks", action="store_true", help="compile the per-model implementation task view from the model contract")
    solve.add_argument("--rerun-plan", action="store_true", help="project the minimal rerun set and pending gates after a change; never executes anything")
    solve.add_argument("--dag", help="artifact DAG path for --rerun-plan; defaults to the active control layout")
    solve.add_argument("--changed", action="append", default=[], help="artifact_id or path treated as changed for --rerun-plan; repeatable")
    solve.add_argument("--model-contract", default=".harness/contracts/model_contract.json", help="model contract source for --tasks")
    solve.add_argument("--compile", action="store_true", help="compile the explicit implementation-map YAML block to JSON IR")
    solve.add_argument("--source", help="solution-report Markdown source; defaults to 03_SOLUTION_REPORT.md")
    solve.add_argument("--output", help="compiled JSON path; defaults to .harness/contracts/implementation_map.json")
    _add_common(solve)
    solve.add_argument("--manifest", default=None)
    solve.add_argument("--stage", dest="execution_stage", choices=("smoke", "full"), default="smoke")
    solve.add_argument("--run-id")
    solve.add_argument("--receipt")
    solve.add_argument("--index")
    solve.add_argument("--preset", choices=PRESETS, default="research")
    solve.add_argument("--selected", action="store_true")
    solve.add_argument("--seed", type=int)
    solve.add_argument("--input", action="append", default=[])
    solve.add_argument("--output-artifact", action="append", default=[])
    solve.add_argument("--covers-model", action="append", default=[], help="model id exercised by a smoke command")
    solve.add_argument("--covers-question", action="append", default=[], help="question id exercised by a smoke command")
    solve.add_argument("--covers-contract-item", action="append", default=[], help="equation, constraint, or validation-obligation id exercised by a smoke command")
    solve.add_argument("command", nargs=argparse.REMAINDER, help="real command after --")
    solve.set_defaults(handler=_solve)

    paper = sub.add_parser("paper", help="section-local paper authoring façades")
    paper_sub = paper.add_subparsers(dest="paper_action", required=True)
    paper_plan = paper_sub.add_parser("plan", help="create paper/00_PAPER_PLAN.md when absent")
    _add_common(paper_plan)
    paper_plan.add_argument("--compile", action="store_true", help="compile the explicit Paper Director Plan YAML block to JSON IR")
    paper_plan.add_argument("--source", help="paper-plan Markdown source; defaults to paper/00_PAPER_PLAN.md")
    paper_plan.add_argument("--output", help="compiled JSON path; defaults to .harness/contracts/paper_plan.json")
    paper_plan.set_defaults(handler=_paper)

    paper_section = paper_sub.add_parser("section", help="create a flexible section-local authoring surface")
    paper_section_sub = paper_section.add_subparsers(dest="paper_section_action", required=True)
    paper_section_create = paper_section_sub.add_parser("create", help="scaffold one freely named section")
    _add_common(paper_section_create)
    paper_section_create.add_argument("section")
    paper_section_create.add_argument("--role", help="soft section role for the author brief; it does not change Gate policy")
    paper_section_create.set_defaults(handler=_paper)
    for action, help_text in (("write", "scaffold exactly one section for drafting"), ("review", "scaffold exactly one section for semantic review")):
        section = paper_sub.add_parser(action, help=help_text)
        _add_common(section)
        section.add_argument("section")
        section.add_argument("--role", help="soft section role for the author brief; it does not change Gate policy")
        section.set_defaults(handler=_paper)

    figure = sub.add_parser("figure", help="create a figure brief and route it to the appropriate tool family")
    _add_common(figure)
    figure.add_argument("figure_id")
    figure.add_argument("--compile", action="store_true", help="compile the explicit diagram-spec YAML block when a structured diagram producer needs it")
    figure.add_argument("--source", help="figure brief Markdown source; defaults to figures/<figure-id>/brief.md")
    figure.add_argument("--output", help="compiled JSON path; defaults to .harness/contracts/figures/<figure-id>_diagram_spec.json")
    figure.add_argument("--kind", choices=("auto", "data", "diagram", "illustration"), default="auto")
    figure.add_argument("--semantic-type")
    figure.add_argument("--diagram-backend", choices=("auto", "pptx", "drawio"), default="auto")
    figure.add_argument("--pptx-reference", help="use one inspected PPTX reference id")
    figure.add_argument("--node-count", type=int, help="declared diagram node count for backend/reference selection")
    figure.add_argument("--dag-depth", type=int, help="declared longest acyclic path depth")
    figure.add_argument("--branch-count", type=int, help="declared decision/branch count")
    figure.add_argument("--feedback-edges", type=int, help="declared feedback edge count")
    figure.add_argument("--parallel-lanes", type=int, help="declared parallel lane count")
    figure.add_argument("--density", choices=("low", "medium", "high"), help="declared visual density")
    figure.add_argument("--target-aspect-ratio", choices=("wide", "square", "tall", "16:9", "4:3"))
    figure.add_argument("--reading-order", choices=("left_to_right", "top_to_bottom", "grid"))
    figure.add_argument("--native-topology-qa", action="store_true", help="require native topology QA and route to Draw.io")
    figure.add_argument("--prepare-pptx", action="store_true", help="copy the selected PPTX reference into the figure directory without overwriting an existing copy")
    figure.add_argument("--fallback-reason", help="record why the explicit Draw.io fallback is needed")
    figure.add_argument("--request-illustration", action="store_true", help="emit a provider-neutral image-generation request for an illustration-routed figure (the agent then calls its native tool)")
    figure.add_argument("--collect-illustration", metavar="PATH", help="register the generated raster file back into the figure directory with hash and review obligations")
    figure.add_argument("--capability", choices=("available", "missing", "unknown"), default="unknown", help="whether the current environment exposes a native image-generation tool")
    figure.add_argument("--ai-policy", choices=("allowed", "forbidden", "unknown"), default="unknown", help="current competition-profile stance on generated imagery")
    figure.set_defaults(handler=_figure)

    context = sub.add_parser("context", help="show the minimal stage-local context plan")
    _add_common(context)
    context.add_argument("--stage", required=True, help="research, model, solve, or paper:<section>")
    context.set_defaults(handler=_context)

    precedents = sub.add_parser("precedents", help="consume quarantined precedent knowledge through cards only")
    precedents_sub = precedents.add_subparsers(dest="precedents_action", required=True)
    precedents_select = precedents_sub.add_parser(
        "select",
        help="select pattern or figure cards by competition, problem family, or evidence role; full papers stay quarantined",
    )
    _add_common(precedents_select)
    precedents_select.add_argument("--competition", choices=("CUMCM", "MCM-ICM"))
    precedents_select.add_argument("--problem-family")
    precedents_select.add_argument("--evidence-role")
    precedents_select.add_argument("--data-shape")
    precedents_select.add_argument("--semantic-type")
    precedents_select.add_argument("--card-kind", choices=("pattern", "figure"), default="pattern")
    precedents_select.add_argument("--limit", type=int, default=3)
    precedents_select.set_defaults(handler=_precedents)

    submit = sub.add_parser("submit", help="thin submission-facing façade")
    submit_sub = submit.add_subparsers(dest="submit_action", required=True)
    submit_check = submit_sub.add_parser("check", help="dispatch the existing factual S1 checker")
    _add_common(submit_check)
    submit_check.add_argument("--manifest", default=None)
    submit_check.add_argument("--strict", action="store_true")
    submit_check.set_defaults(handler=_submit_check)

    submit_receipt = submit_sub.add_parser(
        "receipt",
        help="verify a human portal receipt against the immutable F1 package",
    )
    _add_common(submit_receipt)
    submit_receipt.add_argument("--receipt", required=True)
    submit_receipt.set_defaults(handler=_submit_receipt)

    ai = sub.add_parser("ai", help="declare or record AI usage in the v2 control manifest")
    ai_sub = ai.add_subparsers(dest="ai_action", required=True)

    ai_status = ai_sub.add_parser("status", help="show the current tri-state AI declaration")
    _add_common(ai_status)
    ai_status.add_argument("--manifest", default=None)
    ai_status.set_defaults(handler=_ai)

    ai_none = ai_sub.add_parser("confirm-none", help="explicitly confirm that no AI tool was used")
    _add_common(ai_none)
    ai_none.add_argument("--manifest", default=None)
    ai_none.add_argument("--confirmed-by", required=True)
    ai_none.add_argument("--reason", required=True)
    ai_none.add_argument("--confirmed-at")
    ai_none.set_defaults(handler=_ai)

    ai_record = ai_sub.add_parser("record", help="append one externally auditable AI-use record")
    _add_common(ai_record)
    ai_record.add_argument("--manifest", default=None)
    ai_record.add_argument("--usage-id")
    ai_record.add_argument("--tool-name", required=True)
    ai_record.add_argument("--model", required=True)
    ai_record.add_argument("--provider", required=True)
    ai_record.add_argument("--stage", required=True, choices=("analysis", "modeling", "coding", "experiments", "writing", "review", "submission", "other"))
    ai_record.add_argument("--purpose", required=True)
    ai_record.add_argument("--prompt-summary", required=True)
    ai_record.add_argument("--output-use", required=True)
    ai_record.add_argument("--human-changes", required=True)
    ai_record.add_argument("--interaction-record", required=True)
    ai_record.add_argument("--checked-by-role", required=True)
    ai_record.add_argument("--verification-method", required=True)
    ai_record.add_argument("--used-at")
    ai_record.add_argument("--checked-at")
    ai_record.set_defaults(handler=_ai)

    ai_verify = ai_sub.add_parser("verify", help="complete human verification for an automatically logged AI use")
    _add_common(ai_verify)
    ai_verify.add_argument("--manifest", default=None)
    ai_verify.add_argument("--usage-id", required=True)
    ai_verify.add_argument("--checked-by-role", required=True)
    ai_verify.add_argument("--verification-method", required=True)
    ai_verify.add_argument("--human-changes", required=True)
    ai_verify.add_argument("--checked-at")
    ai_verify.set_defaults(handler=_ai)

    profile = sub.add_parser("profile", help="show preset capabilities and profile status")
    _add_common(profile)
    profile.add_argument("--manifest", default=None)
    profile.add_argument("--preset", choices=PRESETS, default="research")
    profile.add_argument("--override", action="append", default=[])
    profile.set_defaults(handler=_profile)

    doctor = sub.add_parser("doctor", help="check Python, optional dependencies, schemas, and critical files")
    _add_common(doctor)
    doctor.add_argument("--offline", action="store_true", help="reserved compatibility flag; does not download anything")
    doctor.add_argument("--stage", choices=DOCTOR_STAGES, help="report only the capabilities required by one workflow stage")
    doctor.set_defaults(handler=_doctor)

    setup = sub.add_parser("setup", help="render one draft-only DSH setup card")
    _add_common(setup)
    setup.add_argument("--manifest", default=None)
    setup.add_argument("--stage", choices=DOCTOR_STAGES, help="stage to include in the capability readout")
    setup.set_defaults(handler=_setup)

    migrate = sub.add_parser("migrate", help="dispatch the non-destructive v1 to v2 migration")
    _add_common(migrate)
    migrate.add_argument("--manifest")
    migrate.add_argument("--output-dir")
    migrate.add_argument("--no-write", action="store_true")
    migrate.set_defaults(handler=_migrate)
    migrate.add_argument("--layout", choices=("hidden",), help="plan or apply a v2 control-state relocation into .harness/state")
    migrate.add_argument("--apply", action="store_true", help="apply --layout hidden after inspecting its default dry-run report")
    return parser


def _status(args: argparse.Namespace) -> int:
    root = _project(args)
    manifest = _manifest_path(root, args.manifest)
    command = [sys.executable, str(SCRIPT_DIR / "harness_status.py"), "--manifest", str(manifest), "--project-root", str(root)]
    if args.json:
        command.append("--json")
    return _dispatch(command, root)


def _migrate(args: argparse.Namespace) -> int:
    root = _project(args)
    if args.layout:
        if args.manifest or args.output_dir or args.no_write:
            raise ValueError("--layout hidden cannot be combined with v1 migration flags")
        report = migrate_flat_control_state_to_hidden(root, apply=args.apply)
        human = "hidden control-state migration applied" if args.apply else "hidden control-state migration plan ready; rerun with --apply to move state"
        _emit(report, machine=args.json, human=human)
        return 0
    if args.apply:
        raise ValueError("--apply requires --layout hidden")
    command = [sys.executable, str(SCRIPT_DIR / "migrate_v1_to_v2.py"), "--project", str(root)]
    if args.manifest:
        command.extend(["--manifest", args.manifest])
    if args.output_dir:
        command.extend(["--output-dir", args.output_dir])
    if args.no_write:
        command.append("--no-write")
    if args.json:
        command.append("--json")
    return _dispatch(command, root)


def main(argv: list[str] | None = None) -> int:
    _configure_utf8_output()
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.handler(args))
    except (OSError, ValueError, TypeError, RuntimeStateError, json.JSONDecodeError, RuntimeError) as exc:
        payload = {"ok": False, "status": "error", "errors": [str(exc)]}
        _emit(payload, machine=bool(getattr(args, "json", False)))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
