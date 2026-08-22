"""Public WP1 facade for profile normalization and non-destructive migration.

Capability resolution and artifact projections live in focused sibling modules;
this file owns the v1 boundary, canonical competition profile extraction, and
the v2 control-plane writer.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

try:
    from .artifact_projection import (
        build_artifact_dag_v2, invalidate_downstream, normalize_run_index,
        sha256_file, sha256_json, validate_artifact_dag_ownership,
    )
    from .capabilities import (
        PRESETS, ResolvedCapabilities, UnsafeOverrideError, resolve_profile, resolve_profile_from_legacy,
    )
except ImportError:  # direct ``scripts/profiles`` path imports used by existing tests
    from artifact_projection import (  # type: ignore
        build_artifact_dag_v2, invalidate_downstream, normalize_run_index,
        sha256_file, sha256_json, validate_artifact_dag_ownership,
    )
    from capabilities import (  # type: ignore
        PRESETS, ResolvedCapabilities, UnsafeOverrideError, resolve_profile, resolve_profile_from_legacy,
    )

V2 = "2.0"
_PHASE_TO_STAGE = {name: name for name in ("analysis", "coding", "results", "evidence", "paper", "review", "submission")}


class NormalizationError(ValueError):
    """The v1 boundary cannot safely establish a required v2 fact."""


def _dedupe(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _strip_digest_fields(value: Any) -> tuple[Any, bool]:
    """Remove digest fields from legacy profile references, reporting whether any were present."""

    removed = False
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if str(key) in {"sha256", "digest", "digest_algorithm", "digest_owner"}:
                removed = True
                continue
            cleaned, child_removed = _strip_digest_fields(item)
            result[str(key)] = cleaned
            removed = removed or child_removed
        return result, removed
    if isinstance(value, list):
        result_list: list[Any] = []
        for item in value:
            cleaned, child_removed = _strip_digest_fields(item)
            result_list.append(cleaned)
            removed = removed or child_removed
        return result_list, removed
    return copy.deepcopy(value), False


def canonicalize_competition_profile(
    legacy_profile: Mapping[str, Any], *, profile_id: str | None = None, mode: str = "pre_contest",
    official_rules: Iterable[Mapping[str, Any]] | None = None, official_submission_endpoints: Iterable[str] | None = None,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """Extract one standalone v2 profile and explicitly report missing facts."""

    if not isinstance(legacy_profile, Mapping):
        raise NormalizationError("competition profile must be an object")
    if legacy_profile.get("schema_version") == V2:
        _, has_rule_digest = _strip_digest_fields(legacy_profile.get("official_rules", []))
        if has_rule_digest:
            raise NormalizationError("v2 competition_profile rule snapshots cannot own digests; register them in artifact_dag/generated metadata")
        return copy.deepcopy(dict(legacy_profile)), {"inferred": [], "unresolved": [], "manual_review_required": []}

    notes = {"inferred": [], "unresolved": [], "manual_review_required": []}
    rules = legacy_profile.get("rules") if isinstance(legacy_profile.get("rules"), Mapping) else {}
    ai = legacy_profile.get("ai_disclosure") if isinstance(legacy_profile.get("ai_disclosure"), Mapping) else {}
    old_submission = legacy_profile.get("submission") if isinstance(legacy_profile.get("submission"), Mapping) else {}
    family = str(legacy_profile.get("competition_family") or legacy_profile.get("competition") or "custom")
    name = str(legacy_profile.get("competition_name") or family)
    season = legacy_profile.get("season")
    if season is None:
        season = "unknown"
        notes["inferred"].append("competition.season=unknown from missing legacy season")
    mode_value = mode if mode in ("pre_contest", "live_contest", "post_contest", "custom") else "custom"
    if mode_value == "custom":
        notes["inferred"].append("competition.mode=custom from unsupported legacy mode")

    page_sources: list[tuple[str, Any]] = []
    if rules.get("page_limit") is not None:
        page_sources.append(("legacy rules.page_limit", rules.get("page_limit")))
    if old_submission.get("max_pages") is not None:
        page_sources.append(("legacy submission.max_pages", old_submission.get("max_pages")))
    max_pages = page_sources[0][1] if page_sources else None
    if max_pages is None:
        notes["unresolved"].append("submission.max_pages is missing from legacy profile")
        notes["manual_review_required"].append("confirm official page limit")
    else:
        notes["inferred"].append(f"submission.max_pages={max_pages} inherited from {page_sources[0][0]}; not an official verified fact")
        notes["unresolved"].append("submission.max_pages is not verified by an official rule snapshot")
        notes["manual_review_required"].append("confirm official page limit")
    if len({str(value) for _, value in page_sources}) > 1:
        notes["unresolved"].append("submission.max_pages has conflicting legacy sources")
        notes["manual_review_required"].append("resolve legacy page-limit sources against the official rule snapshot")
    try:
        max_pages = int(max_pages) if max_pages is not None else None
    except (TypeError, ValueError):
        max_pages = None
        notes["unresolved"].append("submission.max_pages is not an integer")
        notes["manual_review_required"].append("confirm official page limit")

    raw_ai_policy = ai.get("policy")
    ai_policy = str(raw_ai_policy or "required_when_used")
    if raw_ai_policy is None:
        notes["inferred"].append("submission.ai_disclosure_policy=required_when_used from missing legacy policy")
        notes["unresolved"].append("submission.ai_disclosure_policy is missing from legacy profile")
        notes["manual_review_required"].append("confirm official AI disclosure policy")
    elif ai_policy not in ("prohibited", "optional", "required_when_used", "required_always"):
        notes["unresolved"].append(f"submission.ai_disclosure_policy is unsupported: {ai_policy}")
        notes["manual_review_required"].append("confirm official AI disclosure policy")
        ai_policy = "required_when_used"
    else:
        notes["inferred"].append(f"submission.ai_disclosure_policy={ai_policy} carried from legacy seed; not an official verified fact")
        notes["unresolved"].append("submission.ai_disclosure_policy is not verified by an official rule snapshot")
        notes["manual_review_required"].append("confirm official AI disclosure policy")
    raw_ai_format = ai.get("format")
    ai_format_map = {"support_material_pdf": "separate_file", "in_paper_section": "in_paper_section", "separate_file": "separate_file", "both": "both"}
    ai_format = ai_format_map.get(str(raw_ai_format or "none"), "none")
    if raw_ai_format is None or (ai_format == "none" and str(raw_ai_format) not in ("none", "")):
        notes["inferred"].append("submission.ai_disclosure_format=none from missing or unsupported legacy format")
        notes["unresolved"].append("submission.ai_disclosure_format is missing or unsupported")
        notes["manual_review_required"].append("confirm official AI disclosure format")
    else:
        notes["inferred"].append(f"submission.ai_disclosure_format={ai_format} carried from legacy seed; not an official verified fact")
        notes["unresolved"].append("submission.ai_disclosure_format is not verified by an official rule snapshot")
        notes["manual_review_required"].append("confirm official AI disclosure format")

    checks = ai.get("manual_checks") if isinstance(ai.get("manual_checks"), Mapping) else {}
    when_used, when_not_used = _dedupe(checks.get("when_used", [])), _dedupe(checks.get("when_not_used", []))
    required_checks = _dedupe([*when_used, *when_not_used])
    if not required_checks:
        required_checks = ["human_profile_review"]
        notes["inferred"].append("submission.required_manual_checks=human_profile_review")

    support_zip = old_submission.get("support_zip") if isinstance(old_submission.get("support_zip"), Mapping) else {}
    required_files = old_submission.get("required_files") if isinstance(old_submission.get("required_files"), list) else []
    cleaned_required_files, required_file_digest_removed = _strip_digest_fields(required_files)
    if required_file_digest_removed:
        notes["inferred"].append("legacy required-file digests were not copied into the profile contract")
        notes["unresolved"].append("legacy required-file digest ownership must be registered in artifact_dag/generated metadata")
        notes["manual_review_required"].append("bind required-file digests under their artifact DAG owners")
    support_roles = {str(row.get("role")) for row in required_files if isinstance(row, Mapping)}
    raw_support_policy = support_zip.get("policy")
    support_policy = str(raw_support_policy or "")
    if support_policy not in ("prohibited", "optional", "required"):
        support_policy = "required" if "support" in support_roles else "optional"
        notes["inferred"].append(f"submission.support_policy={support_policy} from legacy support fields")
    else:
        notes["inferred"].append(f"submission.support_policy={support_policy} carried from legacy seed; not an official verified fact")
    notes["unresolved"].append("submission.support_policy is not verified by an official rule snapshot")
    notes["manual_review_required"].append("confirm official support-material policy")

    max_support_bytes = None
    if support_zip.get("max_size_mb") is not None:
        try:
            max_support_bytes = int(float(support_zip["max_size_mb"]) * 1024 * 1024)
            notes["inferred"].append(f"submission.max_support_bytes={max_support_bytes} carried from legacy seed; not an official verified fact")
            notes["unresolved"].append("submission.max_support_bytes is not verified by an official rule snapshot")
            notes["manual_review_required"].append("confirm official maximum support bytes")
        except (TypeError, ValueError):
            notes["unresolved"].append("submission.max_support_bytes is not numeric")
            notes["manual_review_required"].append("confirm official maximum support bytes")

    raw_max_paper_bytes = legacy_profile.get("max_paper_bytes", old_submission.get("max_paper_bytes"))
    max_paper_bytes: int | None = None
    if raw_max_paper_bytes is None:
        notes["unresolved"].append("submission.max_paper_bytes is missing from legacy profile")
        notes["manual_review_required"].append("confirm official maximum paper bytes")
    else:
        try:
            max_paper_bytes = int(raw_max_paper_bytes)
            if max_paper_bytes < 1:
                raise ValueError
            notes["inferred"].append(f"submission.max_paper_bytes={max_paper_bytes} carried from legacy profile; not an official verified fact")
            notes["unresolved"].append("submission.max_paper_bytes is not verified by an official rule snapshot")
            notes["manual_review_required"].append("confirm official maximum paper bytes")
        except (TypeError, ValueError):
            notes["unresolved"].append("submission.max_paper_bytes is not a positive integer")
            notes["manual_review_required"].append("confirm official maximum paper bytes")

    page_count_scope = rules.get("page_count_scope") or old_submission.get("page_count_scope")
    if not page_count_scope:
        page_count_scope = "paper_body"
        notes["inferred"].append("submission.page_count_scope=paper_body from missing legacy scope")
        notes["unresolved"].append("submission.page_count_scope is missing from legacy profile")
        notes["manual_review_required"].append("confirm official page-count scope")
    else:
        notes["inferred"].append(f"submission.page_count_scope={page_count_scope} carried from legacy seed; not an official verified fact")
        notes["unresolved"].append("submission.page_count_scope is not verified by an official rule snapshot")
        notes["manual_review_required"].append("confirm official page-count scope")
    max_pages_excludes_ai_report = rules.get("max_pages_excludes_ai_report", old_submission.get("max_pages_excludes_ai_report", False))
    if "max_pages_excludes_ai_report" not in rules and "max_pages_excludes_ai_report" not in old_submission:
        notes["inferred"].append("submission.max_pages_excludes_ai_report=false from missing legacy rule")
        notes["unresolved"].append("submission.max_pages_excludes_ai_report is missing from legacy profile")
        notes["manual_review_required"].append("confirm whether the AI report counts toward the page limit")
    else:
        notes["inferred"].append(f"submission.max_pages_excludes_ai_report={bool(max_pages_excludes_ai_report)} carried from legacy seed; not an official verified fact")
        notes["unresolved"].append("submission.max_pages_excludes_ai_report is not verified by an official rule snapshot")
        notes["manual_review_required"].append("confirm whether the AI report counts toward the page limit")

    rules_list_raw = [copy.deepcopy(dict(row)) for row in (official_rules or legacy_profile.get("official_rules") or []) if isinstance(row, Mapping)]
    rules_list: list[dict[str, Any]] = []
    digest_removed = False
    for row in rules_list_raw:
        cleaned, row_removed = _strip_digest_fields(row)
        rules_list.append(cleaned)
        digest_removed = digest_removed or row_removed
    if digest_removed:
        notes["inferred"].append("legacy rule snapshot digests were not copied into the profile contract")
        notes["unresolved"].append("legacy rule snapshot digest ownership must be registered in artifact_dag/generated metadata")
        notes["manual_review_required"].append("bind rule snapshot digest under the artifact DAG owner")

    endpoints = _dedupe(official_submission_endpoints or legacy_profile.get("official_submission_endpoints") or [])
    if not rules_list:
        notes["unresolved"].append("official_rules snapshot refs are absent")
        notes["manual_review_required"].append("attach and verify official rule snapshot")
    if not endpoints:
        notes["unresolved"].append("official_submission_endpoints are absent")
        notes["manual_review_required"].append("confirm official submission endpoint")

    profile = {
        "schema_version": V2,
        "profile_id": str(profile_id or legacy_profile.get("profile_id") or family),
        "status": "verified" if not notes["unresolved"] else "unresolved",
        "competition": {"family": family, "name": name, "season": str(season), "mode": mode_value, "language": str(legacy_profile.get("language") or "unknown")},
        "official_rules": rules_list,
        "official_submission_endpoints": endpoints,
        "submission": {
            "paper_extensions": [".pdf"],
            "max_paper_bytes": max_paper_bytes,
            "max_pages": max_pages,
            "max_pages_excludes_ai_report": bool(max_pages_excludes_ai_report),
            "page_count_scope": str(page_count_scope),
            "support_policy": support_policy,
            "max_support_bytes": max_support_bytes,
            "ai_disclosure_policy": ai_policy,
            "ai_disclosure_format": ai_format,
            "ai_manual_checks": {"when_used": when_used, "when_not_used": when_not_used},
            "required_manual_checks": required_checks,
            "required_files": cleaned_required_files,
        },
        "template_id": str(legacy_profile.get("base_template") or "unresolved-template"),
        "visual_profile_id": None,
        "metadata": {"source": "legacy_profile_seed_or_embedded", "source_schema_version": str(legacy_profile.get("schema_version") or "v1_legacy")},
    }
    return profile, notes


def _legacy_artifact_path(manifest: Mapping[str, Any], role: str) -> str | None:
    rows = manifest.get("artifacts")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if isinstance(row, Mapping) and row.get("role") == role and isinstance(row.get("path"), str):
            return str(row["path"])
    return None


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(value) if isinstance(value, Mapping) else None


def _page_candidates(profile: Mapping[str, Any], manifest: Mapping[str, Any]) -> list[tuple[str, Any]]:
    rules = profile.get("rules") if isinstance(profile.get("rules"), Mapping) else {}
    submission = profile.get("submission") if isinstance(profile.get("submission"), Mapping) else {}
    values = [("profile.rules.page_limit", rules.get("page_limit")), ("profile.submission.max_pages", submission.get("max_pages")), ("manifest.page_limit", manifest.get("page_limit"))]
    top_submission = manifest.get("submission")
    if isinstance(top_submission, Mapping):
        values.append(("manifest.submission.max_pages", top_submission.get("max_pages")))
    return [(source, value) for source, value in values if value is not None]


def _initial_report() -> dict[str, Any]:
    return {"schema_version": V2, "status": "migrated", "migrated": [], "inferred": [], "unresolved": [], "deprecated": [], "manual_review_required": [], "warnings": [], "historical_evidence_preserved": []}


def _normalize_internal(
    manifest: Mapping[str, Any], *, project_root: Path | None = None, profile_path: str = "competition_profile.json",
    legacy_dag: Mapping[str, Any] | None = None, legacy_index: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
    report = _initial_report()
    if not isinstance(manifest, Mapping):
        raise NormalizationError("run_manifest must be an object")
    if manifest.get("schema_version") == V2:
        forbidden = [key for key in ("commands", "artifacts", "gates", "reviewer") if key in manifest]
        if "competition_profile" in manifest:
            forbidden.append("competition_profile (v1 embedded field is adapter-only)")
        if forbidden:
            raise NormalizationError(f"v2 run_manifest contains forbidden duplicated state: {', '.join(forbidden)}")
        profile_ref = manifest.get("competition_profile_ref")
        if not isinstance(profile_ref, Mapping) or not isinstance(profile_ref.get("path"), str) or not isinstance(profile_ref.get("profile_id"), str):
            raise NormalizationError("v2 run_manifest requires competition_profile_ref.path and competition_profile_ref.profile_id")
        if any(key not in {"path", "artifact_id", "profile_id"} for key in profile_ref):
            raise NormalizationError("v2 competition_profile_ref may contain only path, artifact_id, and profile_id; digest ownership belongs to artifact_dag")
        roots = manifest.get("roots")
        if not isinstance(roots, Mapping):
            raise NormalizationError("v2 run_manifest roots must be an object")
        for name, ref in roots.items():
            if not isinstance(ref, Mapping):
                raise NormalizationError(f"v2 run_manifest root ref must be an object: roots.{name}")
            if any(key not in {"path", "artifact_id"} for key in ref):
                raise NormalizationError(f"v2 run_manifest root ref cannot own a digest: roots.{name}")
        metadata = manifest.get("metadata")
        if isinstance(metadata, Mapping) and "capabilities" in metadata:
            raise NormalizationError("v2 run_manifest.metadata cannot store ResolvedCapabilities; rebuild from preset and profile_overrides")
        return copy.deepcopy(dict(manifest)), report, {}, None, None
    if not str(manifest.get("schema_version", "")).startswith("1."):
        raise NormalizationError(f"unsupported run_manifest schema_version: {manifest.get('schema_version')!r}")
    embedded = manifest.get("competition_profile") if isinstance(manifest.get("competition_profile"), Mapping) else {}
    if not embedded:
        report["unresolved"].append("run_manifest.competition_profile is absent or not an object")
        report["manual_review_required"].append("supply standalone competition_profile.json")
    candidates = _page_candidates(embedded, manifest)
    if len({str(value) for _, value in candidates}) > 1:
        report["unresolved"].append(f"conflicting page limits at {', '.join(source for source, _ in candidates)}")
        report["manual_review_required"].append("resolve profile page-limit conflict before any submission Gate")
    profile, profile_notes = canonicalize_competition_profile(embedded, profile_id=str(embedded.get("profile_id") or "legacy-profile"), mode="pre_contest")
    for key in ("inferred", "unresolved", "manual_review_required"):
        report[key].extend(profile_notes[key])
    caps, inferred = resolve_profile_from_legacy(manifest)
    report["inferred"].extend(inferred)
    index_v2, index_notes = normalize_run_index(legacy_index)
    for key in ("inferred", "unresolved", "manual_review_required"):
        report[key].extend(index_notes[key])
    dag_v2, dag_conflicts = build_artifact_dag_v2(manifest, legacy_dag=legacy_dag, project_root=project_root)
    report["unresolved"].extend(dag_conflicts)
    if dag_conflicts:
        report["manual_review_required"].append("resolve artifact path/version conflicts before selecting a canonical artifact")
    if isinstance(legacy_index, Mapping) and legacy_index.get("schema_version") != V2:
        report["migrated"].append("run_index converted to receipt/selection projection")
    if isinstance(legacy_dag, Mapping) and legacy_dag.get("schema_version") != V2:
        report["migrated"].append("artifact_dag converted to v2 identity/dependency/lifecycle projection")
    for index, row in enumerate(manifest.get("commands", []) if isinstance(manifest.get("commands"), list) else []):
        receipt_path = row.get("receipt_path") if isinstance(row, Mapping) else None
        if not isinstance(receipt_path, str) or not receipt_path:
            report["unresolved"].append(f"legacy command[{index}] has no immutable command receipt")
            report["manual_review_required"].append(f"register real receipt for legacy command[{index}]")
        elif project_root:
            receipt_file = (project_root / receipt_path).resolve() if not Path(receipt_path).is_absolute() else Path(receipt_path)
            if not receipt_file.is_file():
                report["unresolved"].append(f"legacy command[{index}] receipt does not exist: {receipt_path}")
                report["manual_review_required"].append(f"verify execution receipt for legacy command[{index}]")
    frozen_path = _legacy_artifact_path(manifest, "frozen_results")
    if frozen_path and project_root:
        frozen_file = (project_root / frozen_path).resolve() if not Path(frozen_path).is_absolute() else Path(frozen_path).resolve()
        if not frozen_file.is_file():
            report["unresolved"].append(f"historical frozen_results artifact does not exist: {frozen_path}")
            report["manual_review_required"].append("locate the historical frozen result before migration")
        elif isinstance(index_v2, Mapping):
            frozen_value = _load_json(frozen_file)
            if frozen_value is None:
                report["unresolved"].append(f"historical frozen_results artifact is not a JSON object: {frozen_path}")
                report["manual_review_required"].append("verify historical frozen result without rewriting it")
            selected_ids = index_v2.get("selection", {}).get("selected_receipt_ids", []) if isinstance(index_v2.get("selection"), Mapping) else []
            selected_run_ids = {row.get("run_id") for row in index_v2.get("receipts", []) if isinstance(row, Mapping) and row.get("receipt_id") in selected_ids}
            if frozen_value and frozen_value.get("run_id") and selected_run_ids and frozen_value["run_id"] not in selected_run_ids:
                report["unresolved"].append(f"frozen_results.run_id={frozen_value['run_id']} does not match selected receipt run_ids={sorted(selected_run_ids)}")
                report["manual_review_required"].append("select the receipt that produced the frozen result or create a new freeze")
    for index, row in enumerate(manifest.get("artifacts", []) if isinstance(manifest.get("artifacts"), list) else []):
        if isinstance(row, Mapping) and str(row.get("role", "")).startswith("extremum_certificate"):
            report["deprecated"].append(f"legacy artifact role {row.get('role')} remains read-compatible but has no v2 writer path")
        if isinstance(row, Mapping) and row.get("role") in {"frozen_results", "submission_manifest", "submission_receipt"} and isinstance(row.get("path"), str):
            report["historical_evidence_preserved"].append(str(row["path"]))
    report["deprecated"].append("run_manifest v1 embedded profile/commands/artifacts/gates are read-only compatibility fields")
    report["warnings"].extend(["v1 migration never upgrades a declaration into a real execution receipt", "v1 migration never overwrites frozen historical evidence"])
    if isinstance(index_v2, Mapping):
        legacy_policy = legacy_index.get("selection_policy") if isinstance(legacy_index, Mapping) else None
        rule = str(legacy_policy) if legacy_policy else "manual review required: selection policy unavailable"
    else:
        rule = "manual review required: selection policy unavailable"
    if caps.preset == "submission":
        human_stages = ["m1", "p2", "w1", "w2", "s1", "f1"]
    elif caps.preset == "research":
        human_stages = ["m1", "p2", "w1", "w2"]
    else:
        human_stages = ["m1", "p2"]
    roots: dict[str, Any] = {"artifact_dag": {"path": _legacy_artifact_path(manifest, "artifact_dag") or "artifact_dag.json"}, "run_index": {"path": _legacy_artifact_path(manifest, "run_index") or "run_index.json"}}
    model = manifest.get("model_contract")
    if isinstance(model, Mapping) and isinstance(model.get("path"), str):
        roots["model_contract"] = {"path": str(model["path"])}
        if isinstance(model.get("artifact_id"), str):
            roots["model_contract"]["artifact_id"] = model["artifact_id"]
    normalized = {
        "schema_version": V2, "project_id": str(manifest.get("project_id") or "migrated-project"), "run_id": str(manifest.get("run_id") or "migrated-run"),
        "status": str(manifest.get("status") or "active"), "stage": _PHASE_TO_STAGE.get(str(manifest.get("phase")), "analysis"),
        "preset": caps.preset, "profile_overrides": copy.deepcopy(dict(caps.overrides)),
        "competition_profile_ref": {"path": profile_path.replace("\\", "/"), "profile_id": profile["profile_id"]}, "roots": roots,
        "control": {"selection_policy": {"owner": "run_manifest.control", "rule": rule, "version": V2}, "required_human_stages": human_stages, "historical_evidence_policy": "preserve"},
        "safety": copy.deepcopy(manifest.get("safety") if isinstance(manifest.get("safety"), Mapping) else {}),
        "ai_usage_state": "used" if isinstance(manifest.get("ai_usage"), list) and manifest.get("ai_usage") else "unknown",
        "ai_usage": copy.deepcopy(manifest.get("ai_usage") if isinstance(manifest.get("ai_usage"), list) else []),
        "human_checkpoints": copy.deepcopy(manifest.get("human_checkpoints") if isinstance(manifest.get("human_checkpoints"), list) else []),
        "metadata": {"normalized_from": str(manifest.get("schema_version")), "normalization_boundary": "v1_adapter"},
    }
    report["migrated"].extend(["embedded competition_profile extracted to standalone competition_profile.json", "run_manifest reduced to v2 control-plane roots and decisions", "legacy profile dimensions resolved to one preset/capability set"])
    if report["unresolved"] or report["manual_review_required"]:
        report["status"] = "manual_review_required"
    return normalized, report, profile, dag_v2, index_v2


def normalize_manifest(manifest: Mapping[str, Any], *, project_root: Path | None = None, profile_path: str = "competition_profile.json", legacy_dag: Mapping[str, Any] | None = None, legacy_index: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return _normalize_internal(manifest, project_root=project_root, profile_path=profile_path, legacy_dag=legacy_dag, legacy_index=legacy_index)[0]


def migrate_manifest(manifest: Mapping[str, Any], *, project_root: Path | None = None, profile_path: str = "competition_profile.json", legacy_dag: Mapping[str, Any] | None = None, legacy_index: Mapping[str, Any] | None = None) -> dict[str, Any]:
    normalized, report, profile, dag, index = _normalize_internal(manifest, project_root=project_root, profile_path=profile_path, legacy_dag=legacy_dag, legacy_index=legacy_index)
    return {"manifest": normalized, "competition_profile": profile, "artifact_dag": dag, "run_index": index, "report": report}


def migrate_project(project_root: str | Path, *, manifest_path: str | Path | None = None, output_dir: str | Path | None = None, write: bool = True) -> dict[str, Any]:
    """Write v2 files to a separate directory; never overwrite source evidence."""

    root = Path(project_root).resolve()
    raw_manifest = manifest_path or "run_manifest.json"
    source = (root / raw_manifest).resolve() if not Path(raw_manifest).is_absolute() else Path(raw_manifest).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"run_manifest not found: {source}")
    manifest = _load_json(source)
    if manifest is None:
        raise NormalizationError("run_manifest root must be a JSON object")
    dag_path = root / (_legacy_artifact_path(manifest, "artifact_dag") or "artifact_dag.json")
    index_path = root / (_legacy_artifact_path(manifest, "run_index") or "run_index.json")
    bundle = migrate_manifest(manifest, project_root=root, legacy_dag=_load_json(dag_path), legacy_index=_load_json(index_path))
    if not bundle.get("competition_profile"):
        ref = manifest.get("competition_profile_ref") if isinstance(manifest.get("competition_profile_ref"), Mapping) else {}
        path_value = ref.get("path") if isinstance(ref, Mapping) else None
        if isinstance(path_value, str):
            candidate = (root / path_value).resolve() if not Path(path_value).is_absolute() else Path(path_value).resolve()
            loaded = _load_json(candidate)
            if loaded and loaded.get("schema_version") == V2:
                bundle["competition_profile"] = loaded
            else:
                bundle["report"]["unresolved"].append("v2 competition_profile reference does not resolve to a v2 profile")
                bundle["report"]["manual_review_required"].append("provide the standalone v2 competition_profile.json")
    destination = Path(output_dir).resolve() if output_dir is not None else root / "migration_v2"
    if destination == root:
        raise ValueError("migration output must be separate from the source project root")
    if bundle["report"]["unresolved"] or bundle["report"]["manual_review_required"]:
        bundle["report"]["status"] = "manual_review_required"
    outputs: dict[str, str] = {}
    if write:
        destination.mkdir(parents=True, exist_ok=True)
        def write_document(name: str, value: Any) -> None:
            path = destination / name
            path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            outputs[name] = str(path)
        if bundle.get("competition_profile"):
            write_document("competition_profile.json", bundle["competition_profile"])
        write_document("run_manifest.json", bundle["manifest"])
        if bundle["artifact_dag"] is not None:
            write_document("artifact_dag.json", bundle["artifact_dag"])
        if bundle["run_index"] is not None:
            write_document("run_index.json", bundle["run_index"])
        write_document("migration_report.json", bundle["report"])
    bundle["output_paths"] = outputs
    return bundle


def load_normalized_manifest(path: str | Path, *, project_root: Path | None = None) -> dict[str, Any]:
    manifest_path = Path(path)
    value = _load_json(manifest_path)
    if value is None:
        raise NormalizationError(f"manifest must be a JSON object: {manifest_path}")
    return normalize_manifest(value, project_root=project_root or manifest_path.parent)


__all__ = [
    "NormalizationError", "UnsafeOverrideError", "ResolvedCapabilities", "PRESETS", "resolve_profile", "resolve_profile_from_legacy",
    "canonicalize_competition_profile", "normalize_manifest", "migrate_manifest", "migrate_project", "load_normalized_manifest",
    "build_artifact_dag_v2", "normalize_run_index", "invalidate_downstream", "validate_artifact_dag_ownership", "sha256_file", "sha256_json",
]
