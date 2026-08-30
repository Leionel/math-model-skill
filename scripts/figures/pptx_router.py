"""Route and safely stage editable PPTX concept-figure references."""

from __future__ import annotations

from collections.abc import Mapping
import shutil
from pathlib import Path
from typing import Any

from _common import rel_path, sha256_file


HARNESS_ROOT = Path(__file__).resolve().parents[2]

PPTX_REFERENCE_CATALOG: tuple[dict[str, Any], ...] = (
    {
        "reference_id": "mcm_sectioned_overview",
        "source_pptx": "assets/pptx_workflow/美赛流程图无敌2025.pptx",
        "source_slide": 1,
        "semantic_family": ("research framework", "methodology overview"),
        "description": "A sectioned, multi-stage overview with separate process regions and an explicit reading order.",
        "edit_guidance": "Keep the major phase bands; simplify unused sections before adding task-specific nodes.",
        "topology": {
            "node_range": (7, 15),
            "depth_range": (3, 5),
            "branching": "medium",
            "feedback": False,
            "parallel_lanes": 3,
        },
        "layout": {"aspect_ratio": "wide", "density": "medium", "reading_order": "left_to_right"},
        "visual_traits": ("section_bands", "explicit_reading_order", "low_saturation"),
        "avoid_when": ("simple_linear_pipeline", "node_count_below_5"),
    },
    {
        "reference_id": "mcm_decision_path",
        "source_pptx": "assets/pptx_workflow/美赛流程图无敌2025.pptx",
        "source_slide": 5,
        "semantic_family": ("decision process", "optimization loop", "validation flow"),
        "description": "A compact decision-and-action path for one conditional branch or feedback point.",
        "edit_guidance": "Use a single decision question and label the pass/fail consequences rather than adding decorative branches.",
        "topology": {
            "node_range": (3, 6),
            "depth_range": (2, 3),
            "branching": "medium",
            "feedback": True,
            "parallel_lanes": 1,
        },
        "layout": {"aspect_ratio": "wide", "density": "low", "reading_order": "left_to_right"},
        "visual_traits": ("decision_gate", "compact_branch", "explicit_feedback"),
        "avoid_when": ("node_count_above_8", "parallel_lanes_above_2"),
    },
    {
        "reference_id": "mcm_model_pipeline",
        "source_pptx": "assets/pptx_workflow/美赛流程图无敌2025.pptx",
        "source_slide": 13,
        "semantic_family": ("algorithm pipeline", "data flow"),
        "description": "A model-pipeline composition with grouped learning stages and directed connections.",
        "edit_guidance": "Retain only evidence-backed inputs, transformations, and outputs.",
        "topology": {
            "node_range": (6, 14),
            "depth_range": (3, 5),
            "branching": "medium",
            "feedback": False,
            "parallel_lanes": 2,
        },
        "layout": {"aspect_ratio": "wide", "density": "medium", "reading_order": "left_to_right"},
        "visual_traits": ("grouped_stages", "directed_connections", "model_pipeline"),
        "avoid_when": ("feedback_required", "node_count_below_4"),
    },
    {
        "reference_id": "paper_framework",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图2.pptx",
        "source_slide": 1,
        "semantic_family": ("research framework",),
        "description": "An all-paper framework using grouped factors, a central mechanism, and downstream outcomes.",
        "edit_guidance": "Use it when one core mechanism explains several evidence groups.",
        "topology": {
            "node_range": (5, 10),
            "depth_range": (3, 4),
            "branching": "medium",
            "feedback": False,
            "parallel_lanes": 3,
        },
        "layout": {"aspect_ratio": "wide", "density": "medium", "reading_order": "left_to_right"},
        "visual_traits": ("dominant_core", "grouped_factors", "downstream_outcomes"),
        "avoid_when": ("simple_linear_pipeline", "feedback_required"),
    },
    {
        "reference_id": "paper_staged_method",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图2.pptx",
        "source_slide": 5,
        "semantic_family": ("workflow", "algorithm pipeline", "methodology overview"),
        "description": "A staged method layout with visible Step labels and an explicit assessment-to-optimization progression.",
        "edit_guidance": "Keep one left-to-right or top-to-bottom reading route; do not turn the slide into a dashboard.",
        "topology": {
            "node_range": (4, 9),
            "depth_range": (3, 4),
            "branching": "low",
            "feedback": False,
            "parallel_lanes": 1,
        },
        "layout": {"aspect_ratio": "wide", "density": "medium", "reading_order": "left_to_right"},
        "visual_traits": ("staged_method", "visible_steps", "single_reading_route"),
        "avoid_when": ("feedback_required", "parallel_lanes_above_2"),
    },
    {
        "reference_id": "paper_model_structure",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图2.pptx",
        "source_slide": 4,
        "semantic_family": ("model architecture", "model structure"),
        "description": "A bounded model-structure layout with inputs, core modules, and task-level outputs.",
        "edit_guidance": "Use for a model whose internal modules must be explained, not for numerical-result plots.",
        "topology": {
            "node_range": (6, 12),
            "depth_range": (3, 4),
            "branching": "medium",
            "feedback": False,
            "parallel_lanes": 2,
        },
        "layout": {"aspect_ratio": "wide", "density": "medium", "reading_order": "left_to_right"},
        "visual_traits": ("bounded_modules", "input_core_output", "model_structure"),
        "avoid_when": ("feedback_required", "simple_linear_pipeline"),
    },
    {
        "reference_id": "quadrant_problem_board",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图6.pptx",
        "source_slide": 1,
        "semantic_family": ("multi-question overview",),
        "description": "A four-question board that separates task blocks while retaining cross-question handoffs.",
        "edit_guidance": "Use only when the paper truly needs a multi-question map; otherwise choose a simpler route.",
        "topology": {
            "node_range": (8, 16),
            "depth_range": (2, 4),
            "branching": "high",
            "feedback": False,
            "parallel_lanes": 4,
        },
        "layout": {"aspect_ratio": "wide", "density": "high", "reading_order": "grid"},
        "visual_traits": ("question_quadrants", "cross_question_handoffs", "board_layout"),
        "avoid_when": ("simple_linear_pipeline", "node_count_below_6"),
    },
    {
        "reference_id": "three_phase_model_board",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图7.pptx",
        "source_slide": 1,
        "semantic_family": ("three-phase overview",),
        "description": "A dense three-phase model board for deterministic mechanisms, stochastic behavior, and sensitivity analysis.",
        "edit_guidance": "Use as a composition source for genuinely multi-phase work and remove any phase that lacks evidence.",
        "topology": {
            "node_range": (9, 18),
            "depth_range": (3, 5),
            "branching": "high",
            "feedback": False,
            "parallel_lanes": 3,
        },
        "layout": {"aspect_ratio": "wide", "density": "high", "reading_order": "left_to_right"},
        "visual_traits": ("three_phase", "dense_model_board", "sensitivity_rail"),
        "avoid_when": ("simple_linear_pipeline", "node_count_below_7"),
    },
)

_SEMANTIC_TO_REFERENCE = {
    "workflow": "paper_staged_method",
    "research framework": "mcm_sectioned_overview",
    "model architecture": "paper_model_structure",
    "algorithm pipeline": "paper_staged_method",
    "optimization loop": "mcm_decision_path",
    "validation flow": "mcm_decision_path",
    "decision process": "mcm_decision_path",
    "methodology overview": "mcm_sectioned_overview",
    "data flow": "mcm_model_pipeline",
    "model structure": "paper_model_structure",
}


_TOPOLOGY_FIELDS = {
    "node_count",
    "dag_depth",
    "branch_count",
    "feedback_edges",
    "parallel_lanes",
    "density",
    "target_aspect_ratio",
    "native_topology_qa",
    "reading_order",
}


def normalize_label(value: str | None) -> str:
    return " ".join((value or "").casefold().replace("_", " ").replace("-", " ").split())


def _normalize_density(value: object) -> str | None:
    if value is None:
        return None
    normalized = normalize_label(str(value))
    if normalized not in {"low", "medium", "high"}:
        raise ValueError("topology density must be low, medium, or high")
    return normalized


def _normalize_aspect_ratio(value: object) -> str | None:
    if value is None:
        return None
    normalized = normalize_label(str(value))
    aliases = {"16:9": "wide", "4:3": "wide", "wide": "wide", "square": "square", "tall": "tall"}
    if normalized not in aliases:
        raise ValueError("topology target_aspect_ratio must be wide, square, or tall")
    return aliases[normalized]


def _normalize_reading_order(value: object) -> str | None:
    if value is None:
        return None
    normalized = normalize_label(str(value))
    aliases = {
        "left to right": "left_to_right",
        "top to bottom": "top_to_bottom",
        "grid": "grid",
    }
    if normalized not in aliases:
        raise ValueError("topology reading_order must be left_to_right, top_to_bottom, or grid")
    return aliases[normalized]


def _nonnegative_integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"topology {field} must be a non-negative integer")
    return value


def normalize_topology(topology: Mapping[str, object] | None = None) -> dict[str, Any]:
    """Validate the brief topology used by both backend and reference selection."""

    if topology is not None and not isinstance(topology, Mapping):
        raise ValueError("topology must be a mapping")
    raw = {} if topology is None else dict(topology)
    unknown = sorted(set(raw) - _TOPOLOGY_FIELDS)
    if unknown:
        raise ValueError(f"unknown topology fields: {', '.join(unknown)}")

    normalized: dict[str, Any] = {
        "node_count": None,
        "dag_depth": None,
        "branch_count": None,
        "feedback_edges": None,
        "parallel_lanes": None,
        "density": None,
        "target_aspect_ratio": None,
        "native_topology_qa": False,
        "reading_order": None,
    }
    for field in ("node_count", "dag_depth", "branch_count", "feedback_edges", "parallel_lanes"):
        if field in raw:
            normalized[field] = _nonnegative_integer(raw[field], field)
    if "density" in raw:
        normalized["density"] = _normalize_density(raw["density"])
    if "target_aspect_ratio" in raw:
        normalized["target_aspect_ratio"] = _normalize_aspect_ratio(raw["target_aspect_ratio"])
    if "reading_order" in raw:
        normalized["reading_order"] = _normalize_reading_order(raw["reading_order"])
    if "native_topology_qa" in raw:
        if not isinstance(raw["native_topology_qa"], bool):
            raise ValueError("topology native_topology_qa must be a boolean")
        normalized["native_topology_qa"] = raw["native_topology_qa"]
    return normalized


def _branching_label(branch_count: int | None) -> str | None:
    if branch_count is None:
        return None
    if branch_count <= 1:
        return "low"
    if branch_count <= 3:
        return "medium"
    return "high"


def _range_score(value: int | None, bounds: tuple[int, int], field: str, reasons: list[str]) -> int:
    if value is None:
        return 0
    lower, upper = bounds
    if lower <= value <= upper:
        reasons.append(f"{field}={value} fits the reference range {lower}-{upper}")
        return 8
    distance = lower - value if value < lower else value - upper
    return -min(distance, 8)


def _avoidance_reasons(reference: Mapping[str, Any], topology: Mapping[str, Any]) -> list[str]:
    rejected: list[str] = []
    avoid_when = set(reference.get("avoid_when", ()))
    node_count = topology["node_count"]
    branch_count = topology["branch_count"]
    feedback_edges = topology["feedback_edges"]
    parallel_lanes = topology["parallel_lanes"]
    is_simple_linear = (
        node_count is not None
        and node_count <= 4
        and (branch_count is None or branch_count <= 1)
        and (feedback_edges is None or feedback_edges == 0)
        and (parallel_lanes is None or parallel_lanes <= 1)
    )
    if "simple_linear_pipeline" in avoid_when and is_simple_linear:
        rejected.append("reference avoids simple linear pipelines")
    if "feedback_required" in avoid_when and feedback_edges is not None and feedback_edges > 0:
        rejected.append("reference avoids feedback loops")
    if "node_count_below_5" in avoid_when and node_count is not None and node_count < 5:
        rejected.append("reference expects at least five nodes")
    if "node_count_below_4" in avoid_when and node_count is not None and node_count < 4:
        rejected.append("reference expects at least four nodes")
    if "node_count_below_6" in avoid_when and node_count is not None and node_count < 6:
        rejected.append("reference expects at least six nodes")
    if "node_count_below_7" in avoid_when and node_count is not None and node_count < 7:
        rejected.append("reference expects at least seven nodes")
    if "node_count_above_8" in avoid_when and node_count is not None and node_count > 8:
        rejected.append("reference is too compact for more than eight nodes")
    if "parallel_lanes_above_2" in avoid_when and parallel_lanes is not None and parallel_lanes > 2:
        rejected.append("reference does not support more than two parallel lanes")
    return rejected


def _score_reference(reference: Mapping[str, Any], semantic_type: str | None, topology: Mapping[str, Any]) -> dict[str, Any]:
    semantic = normalize_label(semantic_type)
    supported_semantics = {normalize_label(item) for item in reference["semantic_family"]}
    topology_metadata = reference["topology"]
    layout_metadata = reference["layout"]
    reasons: list[str] = []
    rejected = _avoidance_reasons(reference, topology)
    score = 0

    if semantic and semantic in supported_semantics:
        score += 40
        reasons.append(f"semantic type '{semantic}' matches the reference family")
    if _SEMANTIC_TO_REFERENCE.get(semantic) == reference["reference_id"]:
        score += 4
        reasons.append("reference is the catalogued primary for this semantic type")

    score += _range_score(topology["node_count"], topology_metadata["node_range"], "node_count", reasons)
    score += _range_score(topology["dag_depth"], topology_metadata["depth_range"], "dag_depth", reasons)

    branching = _branching_label(topology["branch_count"])
    if branching is not None:
        if branching == topology_metadata["branching"]:
            score += 6
            reasons.append(f"branching={branching} matches the reference")
        else:
            score -= 3

    feedback_edges = topology["feedback_edges"]
    if feedback_edges is not None:
        needs_feedback = feedback_edges > 0
        if needs_feedback == topology_metadata["feedback"]:
            score += 9
            reasons.append("feedback requirement matches the reference")
        elif needs_feedback:
            rejected.append("reference has no feedback-loop grammar")
        else:
            score -= 2

    parallel_lanes = topology["parallel_lanes"]
    if parallel_lanes is not None:
        distance = abs(parallel_lanes - topology_metadata["parallel_lanes"])
        if distance == 0:
            score += 6
            reasons.append(f"parallel_lanes={parallel_lanes} matches the reference")
        else:
            score -= min(distance, 4)

    if topology["density"] is not None:
        if topology["density"] == layout_metadata["density"]:
            score += 4
            reasons.append(f"density={topology['density']} matches the reference")
        else:
            score -= 1
    if topology["target_aspect_ratio"] is not None:
        if topology["target_aspect_ratio"] == layout_metadata["aspect_ratio"]:
            score += 4
            reasons.append(f"aspect_ratio={topology['target_aspect_ratio']} matches the reference")
        else:
            score -= 2
    if topology["reading_order"] is not None:
        if topology["reading_order"] == layout_metadata["reading_order"]:
            score += 3
            reasons.append(f"reading_order={topology['reading_order']} matches the reference")
        else:
            score -= 1

    return {
        "reference_id": reference["reference_id"],
        "source_pptx": reference["source_pptx"],
        "source_slide": reference["source_slide"],
        "description": reference["description"],
        "score": score,
        "reasons": reasons or ["No brief topology was supplied; this is a neutral visual candidate."],
        "fit": "rejected" if rejected else "candidate",
        "rejection_reasons": rejected,
    }


def analyze_pptx_references(
    semantic_type: str | None,
    *,
    topology: Mapping[str, object] | None = None,
    limit: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    """Score inspected references and expose compatible alternatives before staging."""

    if limit < 1:
        raise ValueError("reference candidate limit must be positive")
    normalized_topology = normalize_topology(topology)
    scored = [
        (index, _score_reference(reference, semantic_type, normalized_topology))
        for index, reference in enumerate(PPTX_REFERENCE_CATALOG)
    ]
    ranked = sorted(scored, key=lambda item: (item[1]["fit"] == "candidate", item[1]["score"], -item[0]), reverse=True)
    candidates = [candidate for _, candidate in ranked if candidate["fit"] == "candidate"][:limit]
    rejected = [candidate for _, candidate in ranked if candidate["fit"] == "rejected"][:limit]
    return {"candidates": candidates, "rejected": rejected}


def rank_pptx_references(
    semantic_type: str | None,
    *,
    topology: Mapping[str, object] | None = None,
    limit: int = 3,
) -> list[dict[str, Any]]:
    """Return the top compatible PPTX composition candidates, in deterministic order."""

    return analyze_pptx_references(semantic_type, topology=topology, limit=limit)["candidates"]


def _selected_reference(reference: Mapping[str, Any]) -> dict[str, Any]:
    source = HARNESS_ROOT / str(reference["source_pptx"])
    if not source.is_file():
        raise FileNotFoundError(f"PPTX reference is missing: {source}")
    return {
        "reference_id": reference["reference_id"],
        "source_pptx": reference["source_pptx"],
        "source_slide": reference["source_slide"],
        "description": reference["description"],
        "edit_guidance": reference["edit_guidance"],
        "mode": "copy_and_edit_in_pptx",
    }


def select_pptx_reference(
    semantic_type: str | None,
    *,
    reference_id: str | None = None,
    topology: Mapping[str, object] | None = None,
) -> dict[str, Any]:
    """Select the primary inspected source slide while retaining ranked alternatives."""

    indexed = {row["reference_id"]: row for row in PPTX_REFERENCE_CATALOG}
    if reference_id is not None:
        selected = indexed.get(reference_id)
        if selected is None:
            raise ValueError(f"unknown PPTX reference: {reference_id}")
        result = _selected_reference(selected)
        result["selection"] = "explicit_reference"
        return result

    candidates = rank_pptx_references(semantic_type, topology=topology)
    if not candidates:
        raise ValueError("no compatible PPTX reference candidates; choose Draw.io or an explicit PPTX reference")
    selected = indexed[candidates[0]["reference_id"]]
    result = _selected_reference(selected)
    result["selection"] = "ranked_primary"
    result["selection_score"] = candidates[0]["score"]
    result["selection_reasons"] = candidates[0]["reasons"]
    return result


def stage_pptx_reference(root: Path, figure_id: str, reference: dict[str, Any]) -> dict[str, Any]:
    """Copy the selected deck once; never overwrite a user-edited figure deck."""

    source_rel = reference["source_pptx"]
    if not isinstance(source_rel, str):
        raise ValueError("PPTX reference must include source_pptx")
    source = HARNESS_ROOT / source_rel
    if not source.is_file():
        raise FileNotFoundError(f"PPTX reference is missing: {source}")

    figure_root = root / "figures" / figure_id
    target = figure_root / f"{figure_id}.pptx"
    guide = figure_root / "pptx_editing.md"
    figure_root.mkdir(parents=True, exist_ok=True)
    source_sha256 = sha256_file(source)
    created = False
    if not target.exists():
        shutil.copyfile(source, target)
        created = True

    if not guide.exists():
        guide.write_text(
            "\n".join(
                (
                    "# PPTX figure editing",
                    "",
                    "- Source deck: {source}".format(source=source_rel),
                    "- Selected source slide: {slide}".format(slide=reference["source_slide"]),
                    "- Route: {route}".format(route=reference["reference_id"]),
                    "",
                    "Edit the copied deck, never the source under assets/pptx_workflow/.",
                    "Use the selected source slide as the composition starting point; retain only",
                    "evidence-backed nodes, connectors, and labels. Keep connectors behind nodes,",
                    "then render a PDF/SVG/PNG preview and conduct a final-size human review.",
                    "The copy is an editable visual source, not a result, receipt, or Gate fact.",
                    "",
                )
            ),
            encoding="utf-8",
        )

    return {
        "path": rel_path(target, root),
        "created": created,
        "source_pptx": source_rel,
        "source_slide": reference["source_slide"],
        "source_sha256": source_sha256,
        "existing_copy_preserved": target.exists() and not created,
        "editing_guide": rel_path(guide, root),
    }
