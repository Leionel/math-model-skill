#!/usr/bin/env python3
"""Check pinned contest rules, conservative policy, AI records, and human review."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR.parent))

from _common import load_structured, rel_path, resolve_path, sha256_file  # noqa: E402
from runtime_state import RuntimeStateError, load_runtime_state  # noqa: E402


POLICY_RANK = {"allow": 0, "competition_specific": 1, "ask": 2, "deny": 3}
POLICY_ACTIONS = (
    "interactive_human_help",
    "current_problem_discussion",
    "public_posting",
    "external_write",
    "static_reference_search",
    "ai_tool_use",
)
LIVE_DENY = {"interactive_human_help", "current_problem_discussion", "public_posting", "external_write"}


def _check_v2_safety(manifest_path: Path, root: Path, *, strict: bool) -> tuple[dict[str, Any], int]:
    errors: list[str] = []
    warnings: list[str] = []
    try:
        state = load_runtime_state(manifest_path, project_root=root, allow_legacy=False)
    except (OSError, ValueError, TypeError, RuntimeStateError) as exc:
        report = {"ok": False, "manifest": rel_path(manifest_path, root), "errors": [str(exc)], "warnings": []}
        return report, 1
    profile = state.profile
    rules = profile.get("official_rules", [])
    if profile.get("status") != "verified":
        warnings.append("canonical competition profile is not verified; S1/submission promotion remains blocked")
    if not isinstance(rules, list) or not rules:
        errors.append("canonical competition profile requires at least one official rule snapshot")
        rules = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f"official_rules[{index}] must be an object")
            continue
        snapshot = rule.get("snapshot")
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("path"), str):
            errors.append(f"official_rules[{index}].snapshot must reference a local path")
        elif not resolve_path(snapshot["path"], root).resolve().is_file():
            errors.append(f"official_rules[{index}].snapshot does not exist: {snapshot['path']}")
        if not isinstance(rule.get("rule_id"), str) or not rule.get("rule_id"):
            errors.append(f"official_rules[{index}].rule_id must be non-empty")
        if not isinstance(rule.get("url"), str) or not rule.get("url", "").startswith("https://"):
            errors.append(f"official_rules[{index}].url must be an https URL")
    endpoints = profile.get("official_submission_endpoints", [])
    if not isinstance(endpoints, list) or not endpoints:
        errors.append("canonical competition profile requires official_submission_endpoints")

    safety = state.manifest.get("safety")
    if not isinstance(safety, dict):
        errors.append("safety must be an object")
        safety = {}
    official = safety.get("official_rule") if isinstance(safety.get("official_rule"), dict) else {}
    local = safety.get("local_conservative_policy") if isinstance(safety.get("local_conservative_policy"), dict) else {}
    effective: dict[str, str] = {}
    for action in POLICY_ACTIONS:
        official_value, local_value = official.get(action), local.get(action)
        if official_value not in POLICY_RANK:
            errors.append(f"safety.official_rule.{action} is invalid")
            continue
        if local_value not in POLICY_RANK:
            errors.append(f"safety.local_conservative_policy.{action} is invalid")
            continue
        if POLICY_RANK[local_value] < POLICY_RANK[official_value]:
            errors.append(f"local policy relaxes official rule for {action}: {official_value} -> {local_value}")
        effective[action] = max((official_value, local_value), key=POLICY_RANK.__getitem__)
    mode = profile.get("competition", {}).get("mode") if isinstance(profile.get("competition"), dict) else None
    if mode == "live_contest":
        for action in sorted(LIVE_DENY):
            if effective.get(action) != "deny":
                errors.append(f"live_contest requires effective {action}=deny")

    events = safety.get("events", [])
    if not isinstance(events, list):
        errors.append("safety.events must be an array")
        events = []
    event_ids: list[str] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"safety.events[{index}] must be an object")
            continue
        event_ids.append(str(event.get("event_id", "")))
        if event.get("decision") != "executed":
            continue
        action = event.get("action")
        policy = effective.get(action)
        official_submission = action == "external_write" and event.get("purpose") == "official_submission" and event.get("human_confirmed") is True and isinstance(event.get("target"), str) and any(matches_endpoint(event["target"], endpoint) for endpoint in endpoints)
        if policy in {"deny", "ask", "competition_specific"} and not official_submission:
            errors.append(f"executed safety event {event.get('event_id')} is not permitted by effective {action}={policy}")
    if len(event_ids) != len(set(event_ids)) or any(not value for value in event_ids):
        errors.append("safety event_id values must be distinct and non-empty")

    usage_rows = state.manifest.get("ai_usage", [])
    if not isinstance(usage_rows, list):
        errors.append("ai_usage must be an array")
        usage_rows = []
    if effective.get("ai_tool_use") == "deny" and usage_rows:
        errors.append("ai_usage is non-empty while effective ai_tool_use=deny")
    for index, usage in enumerate(usage_rows):
        if not isinstance(usage, dict):
            errors.append(f"ai_usage[{index}] must be an object")
            continue
        ref = usage.get("interaction_record")
        if isinstance(ref, dict) and isinstance(ref.get("path"), str) and not resolve_path(ref["path"], root).resolve().is_file():
            errors.append(f"ai_usage[{index}].interaction_record does not exist")
        verification = usage.get("verification")
        if not isinstance(verification, dict) or verification.get("status") != "verified":
            (errors if strict else warnings).append(f"ai_usage[{index}] has not completed human verification")
    checkpoints = state.manifest.get("human_checkpoints", [])
    if not isinstance(checkpoints, list):
        errors.append("human_checkpoints must be an array")
        checkpoints = []
    checkpoint_ids = [str(row.get("checkpoint_id", "")) for row in checkpoints if isinstance(row, dict)]
    if len(checkpoint_ids) != len(set(checkpoint_ids)) or any(not value for value in checkpoint_ids):
        errors.append("checkpoint_id values must be distinct and non-empty")
    report = {
        "ok": not errors and (not strict or not warnings),
        "manifest": rel_path(manifest_path, root),
        "competition_profile": profile.get("profile_id"),
        "profile_status": profile.get("status"),
        "mode": mode,
        "effective_policy": effective,
        "checked_rules": len(rules),
        "checked_ai_usage": len(usage_rows),
        "errors": errors,
        "warnings": warnings,
    }
    return report, 0 if report["ok"] else 1


def matches_endpoint(target: str, endpoint: str) -> bool:
    target_url = urlsplit(target)
    endpoint_url = urlsplit(endpoint)
    if (target_url.scheme, target_url.netloc) != (endpoint_url.scheme, endpoint_url.netloc):
        return False
    prefix = endpoint_url.path.rstrip("/")
    return not prefix or target_url.path == prefix or target_url.path.startswith(prefix + "/")


def iso8601(value: Any, owner: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not value:
        errors.append(f"{owner} must be a non-empty ISO-8601 string")
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{owner} must be ISO-8601")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    manifest_path = resolve_path(args.manifest, root).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        manifest = load_structured(manifest_path)
    except (OSError, ValueError, TypeError) as exc:
        print(json.dumps({"ok": False, "errors": [str(exc)], "warnings": []}, ensure_ascii=False, indent=2))
        return 1
    if not isinstance(manifest, dict):
        manifest = {}
        errors.append("run_manifest must be an object")
    if manifest.get("schema_version") == "2.0":
        report, code = _check_v2_safety(manifest_path, root, strict=args.strict)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return code

    def verify_ref(owner: str, ref: Any) -> None:
        if not isinstance(ref, dict):
            errors.append(f"{owner} must be a file reference")
            return
        raw_path = ref.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            errors.append(f"{owner}.path must be non-empty")
            return
        path = resolve_path(raw_path, root).resolve()
        if not path.is_file():
            errors.append(f"{owner} does not exist: {raw_path}")
        elif ref.get("sha256") != sha256_file(path):
            errors.append(f"{owner} sha256 drift: {raw_path}")

    profile = manifest.get("competition_profile")
    if not isinstance(profile, dict):
        errors.append("competition_profile must be an object")
        profile = {}
    iso8601(profile.get("retrieved_at"), "competition_profile.retrieved_at", errors)
    rules = profile.get("official_rules", [])
    if not isinstance(rules, list) or not rules:
        errors.append("competition_profile requires at least one official rule snapshot")
        rules = []
    rule_ids: list[str] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            errors.append(f"official_rules[{index}] must be an object")
            continue
        rule_ids.append(str(rule.get("rule_id", "")))
        iso8601(rule.get("retrieved_at"), f"official_rules[{index}].retrieved_at", errors)
        verify_ref(f"official_rules[{index}].snapshot", rule.get("snapshot"))
    if len(rule_ids) != len(set(rule_ids)) or any(not value for value in rule_ids):
        errors.append("official rule_id values must be distinct and non-empty")

    safety = manifest.get("safety")
    if not isinstance(safety, dict):
        errors.append("safety must be an object")
        safety = {}
    official = safety.get("official_rule") if isinstance(safety.get("official_rule"), dict) else {}
    local = safety.get("local_conservative_policy") if isinstance(safety.get("local_conservative_policy"), dict) else {}
    effective: dict[str, str] = {}
    for action in POLICY_ACTIONS:
        official_value = official.get(action)
        local_value = local.get(action)
        if official_value not in POLICY_RANK:
            errors.append(f"safety.official_rule.{action} is invalid")
            continue
        if local_value not in POLICY_RANK:
            errors.append(f"safety.local_conservative_policy.{action} is invalid")
            continue
        if POLICY_RANK[local_value] < POLICY_RANK[official_value]:
            errors.append(f"local policy relaxes official rule for {action}: {official_value} -> {local_value}")
        effective[action] = max((official_value, local_value), key=POLICY_RANK.__getitem__)

    if profile.get("mode") == "live_contest":
        for action in sorted(LIVE_DENY):
            if effective.get(action) != "deny":
                errors.append(f"live_contest requires effective {action}=deny")

    endpoints = profile.get("official_submission_endpoints", [])
    if not isinstance(endpoints, list):
        endpoints = []
    events = safety.get("events", [])
    if not isinstance(events, list):
        errors.append("safety.events must be an array")
        events = []
    event_ids: list[str] = []
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            errors.append(f"safety.events[{index}] must be an object")
            continue
        event_ids.append(str(event.get("event_id", "")))
        iso8601(event.get("recorded_at"), f"safety.events[{index}].recorded_at", errors)
        if event.get("decision") != "executed":
            continue
        action = event.get("action")
        policy = effective.get(action)
        official_submission = (
            action == "external_write"
            and event.get("purpose") == "official_submission"
            and event.get("human_confirmed") is True
            and isinstance(event.get("target"), str)
            and any(matches_endpoint(event["target"], endpoint) for endpoint in endpoints)
        )
        if policy in {"deny", "ask", "competition_specific"} and not official_submission:
            errors.append(f"executed safety event {event.get('event_id')} is not permitted by effective {action}={policy}")
    if len(event_ids) != len(set(event_ids)) or any(not value for value in event_ids):
        errors.append("safety event_id values must be distinct and non-empty")

    usage_rows = manifest.get("ai_usage", [])
    if not isinstance(usage_rows, list):
        errors.append("ai_usage must be an array")
        usage_rows = []
    if effective.get("ai_tool_use") == "deny" and usage_rows:
        errors.append("ai_usage is non-empty while effective ai_tool_use=deny")
    usage_ids: list[str] = []
    for index, usage in enumerate(usage_rows):
        if not isinstance(usage, dict):
            errors.append(f"ai_usage[{index}] must be an object")
            continue
        usage_ids.append(str(usage.get("usage_id", "")))
        iso8601(usage.get("used_at"), f"ai_usage[{index}].used_at", errors)
        verify_ref(f"ai_usage[{index}].interaction_record", usage.get("interaction_record"))
        verification = usage.get("verification")
        if not isinstance(verification, dict) or verification.get("status") != "verified":
            message = f"ai_usage[{index}] has not completed human verification"
            (errors if args.strict else warnings).append(message)
        elif verification:
            iso8601(verification.get("checked_at"), f"ai_usage[{index}].verification.checked_at", errors)
    if len(usage_ids) != len(set(usage_ids)) or any(not value for value in usage_ids):
        errors.append("AI usage_id values must be distinct and non-empty")

    checkpoints = manifest.get("human_checkpoints", [])
    if not isinstance(checkpoints, list):
        errors.append("human_checkpoints must be an array")
        checkpoints = []
    checkpoint_ids: list[str] = []
    for index, checkpoint in enumerate(checkpoints):
        if not isinstance(checkpoint, dict):
            errors.append(f"human_checkpoints[{index}] must be an object")
            continue
        checkpoint_ids.append(str(checkpoint.get("checkpoint_id", "")))
        iso8601(checkpoint.get("checked_at"), f"human_checkpoints[{index}].checked_at", errors)
        for artifact_index, ref in enumerate(checkpoint.get("artifacts", [])):
            verify_ref(f"human_checkpoints[{index}].artifacts[{artifact_index}]", ref)
    if len(checkpoint_ids) != len(set(checkpoint_ids)) or any(not value for value in checkpoint_ids):
        errors.append("checkpoint_id values must be distinct and non-empty")

    modeling_ai = any(
        isinstance(usage, dict) and usage.get("stage") == "modeling"
        for usage in usage_rows
    )
    if modeling_ai:
        m1_checkpoint = next(
            (
                row for row in checkpoints
                if isinstance(row, dict) and row.get("stage") == "m1" and row.get("decision") == "pass"
            ),
            None,
        )
        m1_manual = set(m1_checkpoint.get("manual_checks", [])) if m1_checkpoint else set()
        if "team_led_core_modeling" not in m1_manual:
            warnings.append(
                "AI was used during modeling; add 'team_led_core_modeling' to the M1 human checkpoint "
                "manual_checks to confirm core modeling was team-led per competition AI policy"
            )

    ok = not errors and (not args.strict or not warnings)
    print(json.dumps({
        "ok": ok,
        "manifest": rel_path(manifest_path, root),
        "competition_profile": profile.get("profile_id"),
        "mode": profile.get("mode"),
        "effective_policy": effective,
        "checked_rules": len(rules),
        "checked_ai_usage": len(usage_rows),
        "errors": errors,
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
