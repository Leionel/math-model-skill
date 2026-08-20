#!/usr/bin/env python3
"""Thin user-facing CLI for the math-modeling evidence Harness.

The CLI resolves a project root, resolves one capability preset, and dispatches
to the existing receipts, checkers, freeze, and migration scripts. It does
not implement Gate policy or create a second orchestration engine.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
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

from _common import load_structured, rel_path, resolve_path  # noqa: E402
from profiles.normalization import canonicalize_competition_profile, resolve_profile  # noqa: E402
from runtime_state import RuntimeStateError, load_runtime_state  # noqa: E402

GATE_ORDER = ("m1", "p1", "p2", "w1", "w2", "s1")
PRESETS = ("sprint", "research", "submission")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


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
    return resolve_path(raw or "run_manifest.json", root).resolve()


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
    if root.exists() and any(root.iterdir()) and not args.force:
        existing = [path.name for path in root.iterdir() if path.name in {"run_manifest.json", "competition_profile.json", "artifact_dag.json", "run_index.json"}]
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
    result = {"ok": True, "schema_version": "2.0", "project_root": str(root), "preset": args.preset, "competition": args.competition, "profile_status": "seed", "profile_source": source, "files": sorted(outputs)}
    _emit(result, machine=args.json, human=f"initialized v2 project at {root}\npreset: {args.preset}\ncompetition profile: seed ({source})\nfiles: {', '.join(sorted(outputs))}")
    return 0


def _dispatch(command: list[str], root: Path) -> int:
    # Keep child stdout/stderr and exit code transparent: the CLI is not a
    # wrapper around Gate policy and does not reinterpret checker results.
    return subprocess.run(command, cwd=str(root), check=False).returncode


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
    return _dispatch(command, root)


def _run(args: argparse.Namespace) -> int:
    root = _project(args)
    manifest = _manifest_path(root, args.manifest)
    if args.run_id is None:
        if manifest.is_file():
            value = load_structured(manifest)
            args.run_id = value.get("run_id") if isinstance(value, Mapping) else None
        if not isinstance(args.run_id, str) or not args.run_id:
            raise ValueError("run requires --run-id when run_manifest.json is absent")
    receipt = args.receipt or f"receipts/{args.stage}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:6]}.json"
    index = args.index or "run_index.json"
    command = [sys.executable, str(SCRIPT_DIR / "run_and_record.py"), "--run-id", args.run_id, "--stage", args.stage, "--receipt", receipt, "--index", index, "--project-root", str(root)]
    if manifest.is_file() and load_structured(manifest).get("schema_version") == "2.0":
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
    errors: list[str] = []
    warnings: list[str] = []
    dependencies: dict[str, dict[str, Any]] = {}
    for name in ("yaml", "jsonschema", "numpy", "pandas", "scipy", "matplotlib"):
        try:
            module = importlib.import_module(name)
            dependencies[name] = {"available": True, "version": getattr(module, "__version__", None)}
        except Exception as exc:  # optional dependencies must not hide core readiness
            dependencies[name] = {"available": False, "error": str(exc)}
            if name in {"yaml", "jsonschema"}:
                errors.append(f"required Python dependency missing: {name}")
            else:
                warnings.append(f"optional Python dependency missing: {name}")
    schemas: list[str] = []
    schema_dir = REPO_ROOT / "schemas"
    for path in sorted(schema_dir.glob("*.schema.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(value, Mapping):
                raise ValueError("schema root is not an object")
            schemas.append(path.name)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"schema parse failed: {path.name}: {exc}")
    critical = ["scripts/harness.py", "scripts/harness_status.py", "scripts/run_and_record.py", "scripts/qa/check_gates.py", "scripts/qa/run_deterministic_qa.py"]
    missing = [item for item in critical if not (REPO_ROOT / item).is_file()]
    errors.extend(f"critical file missing: {item}" for item in missing)
    manifest = root / "run_manifest.json"
    if manifest.is_file():
        try:
            value = load_structured(manifest)
            if not isinstance(value, Mapping):
                errors.append("project run_manifest is not an object")
        except (OSError, ValueError, TypeError) as exc:
            errors.append(f"project run_manifest cannot be read: {exc}")
    report = {"ok": not errors, "project_root": str(root), "python": {"path": sys.executable, "version": sys.version.split()[0]}, "dependencies": dependencies, "schema_count": len(schemas), "schemas": schemas, "critical_files": {"checked": critical, "missing": missing}, "warnings": warnings, "errors": errors}
    _emit(report, machine=args.json, human=f"doctor: {'OK' if report['ok'] else 'BLOCKED'}\npython: {sys.version.split()[0]}\nschemas: {len(schemas)}\noptional warnings: {len(warnings)}")
    return 0 if report["ok"] else 1


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

    profile = sub.add_parser("profile", help="show preset capabilities and profile status")
    _add_common(profile)
    profile.add_argument("--manifest", default=None)
    profile.add_argument("--preset", choices=PRESETS, default="research")
    profile.add_argument("--override", action="append", default=[])
    profile.set_defaults(handler=_profile)

    doctor = sub.add_parser("doctor", help="check Python, optional dependencies, schemas, and critical files")
    _add_common(doctor)
    doctor.add_argument("--offline", action="store_true", help="reserved compatibility flag; does not download anything")
    doctor.set_defaults(handler=_doctor)

    migrate = sub.add_parser("migrate", help="dispatch the non-destructive v1 to v2 migration")
    _add_common(migrate)
    migrate.add_argument("--manifest")
    migrate.add_argument("--output-dir")
    migrate.add_argument("--no-write", action="store_true")
    migrate.set_defaults(handler=_migrate)
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
