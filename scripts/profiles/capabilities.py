"""Single user-facing preset resolver for the v2 capability contract."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

V2 = "2.0"
PRESETS = ("sprint", "research", "submission")
SAFE_INVARIANTS = (
    "require_contest_safety",
    "require_human_checkpoints",
    "require_independent_validation",
    "require_result_freeze",
    "require_submission_immutability",
)


class UnsafeOverrideError(ValueError):
    """A caller tried to turn off a non-bypassable safety boundary."""


@dataclass(frozen=True)
class ResolvedCapabilities:
    """Rebuildable in-memory capability set; never a second source file."""

    preset: str
    capabilities: Mapping[str, bool]
    hash_policy: Mapping[str, Any]
    overrides: Mapping[str, Any]

    def __getitem__(self, key: str) -> Any:
        if key in self.capabilities:
            return self.capabilities[key]
        if key in self.hash_policy:
            return self.hash_policy[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        return self.capabilities.get(key, self.hash_policy.get(key, default))

    def __getattr__(self, key: str) -> Any:
        if key in self.capabilities:
            return self.capabilities[key]
        raise AttributeError(key)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": V2,
            "preset": self.preset,
            "capabilities": dict(self.capabilities),
            "hash_policy": copy.deepcopy(dict(self.hash_policy)),
            "overrides": copy.deepcopy(dict(self.overrides)),
            "safety_invariants": list(SAFE_INVARIANTS),
        }


def _base() -> dict[str, bool]:
    return {
        "require_contest_safety": True,
        "require_human_checkpoints": True,
        "require_independent_validation": True,
        "require_result_freeze": True,
        "require_submission_immutability": True,
        "require_real_run_identity": True,
        "require_risk_based_checks": True,
        "require_scope_contract": False,
        "require_formula_replay": False,
        "require_selected_run_receipt": False,
        "require_selected_io_hash": False,
        "require_authoritative_data_hash": False,
        "require_frozen_result_hash": False,
        "require_canonical_paper_evidence_hash": False,
        "require_final_pdf_hash": False,
        "require_submission_chain_hash": False,
        "require_full_evidence_chain": False,
        "require_figure_result_lineage": False,
        "require_strict_math": False,
        "require_strict_editorial": False,
        "require_current_template": False,
        "require_verified_bibliography": False,
        "submission_freeze_boundary": False,
    }


def _preset(preset: str) -> tuple[dict[str, bool], dict[str, Any]]:
    caps = _base()
    if preset == "sprint":
        policy = {"mode": "identity_only", "algorithm": "sha256", "required_artifact_classes": ["explicit_freeze_result"]}
    elif preset == "research":
        caps.update({
            "require_scope_contract": True, "require_formula_replay": True,
            "require_selected_run_receipt": True, "require_selected_io_hash": True,
            "require_authoritative_data_hash": True, "require_frozen_result_hash": True,
            "require_canonical_paper_evidence_hash": True, "require_full_evidence_chain": True,
            "require_figure_result_lineage": True,
        })
        policy = {"mode": "selective", "algorithm": "sha256", "required_artifact_classes": [
            "authoritative_dataset", "selected_run_input", "selected_run_output", "frozen_results", "canonical_paper_evidence",
        ]}
    elif preset == "submission":
        caps.update({
            "require_scope_contract": True, "require_formula_replay": True,
            "require_selected_run_receipt": True, "require_selected_io_hash": True,
            "require_authoritative_data_hash": True, "require_frozen_result_hash": True,
            "require_canonical_paper_evidence_hash": True, "require_final_pdf_hash": True,
            "require_submission_chain_hash": True, "require_full_evidence_chain": True,
            "require_figure_result_lineage": True, "require_strict_math": True,
            "require_strict_editorial": True, "require_current_template": True,
            "require_verified_bibliography": True, "submission_freeze_boundary": True,
        })
        policy = {"mode": "full_final_chain", "algorithm": "sha256", "required_artifact_classes": [
            "competition_profile_snapshot", "authoritative_dataset", "selected_execution_receipt",
            "frozen_results", "canonical_table", "canonical_figure", "paper_source", "final_pdf", "submission_package",
        ]}
    else:
        raise ValueError(f"unknown profile preset: {preset!r}; expected one of {PRESETS}")
    return caps, policy


def _set(caps: dict[str, bool], key: str, value: Any) -> None:
    if key not in caps:
        raise ValueError(f"unsupported profile override: {key}")
    if not isinstance(value, bool):
        raise ValueError(f"capability override {key} must be boolean")
    if key in SAFE_INVARIANTS and value is False:
        raise UnsafeOverrideError(f"cannot disable safety invariant {key}")
    caps[key] = value


def resolve_profile(preset: str = "research", overrides: Mapping[str, Any] | None = None) -> ResolvedCapabilities:
    """Resolve one preset; overrides are narrow capability adjustments only."""

    if preset not in PRESETS:
        raise ValueError(f"profile preset must be one of {PRESETS}, got {preset!r}")
    if overrides is None:
        overrides = {}
    if not isinstance(overrides, Mapping):
        raise TypeError("profile overrides must be a mapping")
    caps, policy = _preset(preset)
    applied: dict[str, Any] = {}
    aliases = {
        "safety": "require_contest_safety", "require_safety": "require_contest_safety",
        "human_checkpoints": "require_human_checkpoints", "independent_validation": "require_independent_validation",
        "result_freeze": "require_result_freeze", "submission_immutability": "require_submission_immutability",
    }
    for raw_key, value in overrides.items():
        key = str(raw_key)
        if key in aliases:
            _set(caps, aliases[key], value)
        elif key in ("math", "math_correctness_profile"):
            if value not in ("baseline", "strict"):
                raise ValueError("math override must be 'baseline' or 'strict'")
            _set(caps, "require_strict_math", value == "strict")
            if value == "strict":
                _set(caps, "require_formula_replay", True)
        elif key in ("editorial", "editorial_semantics_profile"):
            if value not in ("baseline", "strict"):
                raise ValueError("editorial override must be 'baseline' or 'strict'")
            _set(caps, "require_strict_editorial", value == "strict")
        elif key in ("hash", "hash_policy"):
            if value not in ("identity_only", "selective", "full_final_chain"):
                raise ValueError("hash_policy override must be identity_only, selective, or full_final_chain")
            policy = dict(policy)
            policy["mode"] = value
        elif key in caps:
            _set(caps, key, value)
        else:
            raise ValueError(f"unsupported profile override: {key}")
        applied[key] = value
    for invariant in SAFE_INVARIANTS:
        caps[invariant] = True
    return ResolvedCapabilities(preset, caps, policy, applied)


def resolve_profile_from_legacy(manifest: Mapping[str, Any]) -> tuple[ResolvedCapabilities, list[str]]:
    """Resolve v1's independent profile dimensions at the compatibility edge."""

    inferred: list[str] = []
    mode = manifest.get("integrity_mode")
    if mode == "dev":
        preset = "sprint"
    elif mode == "submission":
        preset = "submission"
    elif mode in (None, "research"):
        preset = "research"
        if mode is None:
            inferred.append("preset=research from missing legacy integrity_mode")
    else:
        raise ValueError(f"unsupported legacy integrity_mode: {mode!r}")
    reviewer = manifest.get("reviewer")
    if isinstance(reviewer, Mapping) and reviewer.get("profile") in ("final_submission", "award_max"):
        if preset != "submission":
            inferred.append("preset=submission from legacy reviewer.profile")
        preset = "submission"
    overrides: dict[str, Any] = {}
    for source, target in (("math_correctness_profile", "math"), ("editorial_semantics_profile", "editorial")):
        if manifest.get(source) in ("baseline", "strict"):
            overrides[target] = manifest[source]
    if manifest.get("enhanced_integrity_profile") is True:
        inferred.append("enhanced_integrity_profile folded into research evidence capabilities")
        if preset == "sprint":
            preset = "research"
    return resolve_profile(preset, overrides), inferred


__all__ = ["V2", "PRESETS", "SAFE_INVARIANTS", "UnsafeOverrideError", "ResolvedCapabilities", "resolve_profile", "resolve_profile_from_legacy"]
