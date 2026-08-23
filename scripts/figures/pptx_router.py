"""Route and safely stage editable PPTX concept-figure references."""

from __future__ import annotations

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
        "semantic_types": ("research framework", "methodology overview"),
        "description": "A sectioned, multi-stage overview with separate process regions and an explicit reading order.",
        "edit_guidance": "Keep the major phase bands; simplify unused sections before adding task-specific nodes.",
    },
    {
        "reference_id": "mcm_decision_path",
        "source_pptx": "assets/pptx_workflow/美赛流程图无敌2025.pptx",
        "source_slide": 5,
        "semantic_types": ("decision process", "optimization loop", "validation flow"),
        "description": "A compact decision-and-action path for one conditional branch or feedback point.",
        "edit_guidance": "Use a single decision question and label the pass/fail consequences rather than adding decorative branches.",
    },
    {
        "reference_id": "mcm_model_pipeline",
        "source_pptx": "assets/pptx_workflow/美赛流程图无敌2025.pptx",
        "source_slide": 13,
        "semantic_types": ("algorithm pipeline", "data flow"),
        "description": "A model-pipeline composition with grouped learning stages and directed connections.",
        "edit_guidance": "Retain only evidence-backed inputs, transformations, and outputs.",
    },
    {
        "reference_id": "paper_framework",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图2.pptx",
        "source_slide": 1,
        "semantic_types": ("research framework",),
        "description": "An all-paper framework using grouped factors, a central mechanism, and downstream outcomes.",
        "edit_guidance": "Use it when one core mechanism explains several evidence groups.",
    },
    {
        "reference_id": "paper_staged_method",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图2.pptx",
        "source_slide": 5,
        "semantic_types": ("workflow", "algorithm pipeline", "methodology overview"),
        "description": "A staged method layout with visible Step labels and an explicit assessment-to-optimization progression.",
        "edit_guidance": "Keep one left-to-right or top-to-bottom reading route; do not turn the slide into a dashboard.",
    },
    {
        "reference_id": "paper_model_structure",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图2.pptx",
        "source_slide": 4,
        "semantic_types": ("model architecture", "model structure"),
        "description": "A bounded model-structure layout with inputs, core modules, and task-level outputs.",
        "edit_guidance": "Use for a model whose internal modules must be explained, not for numerical-result plots.",
    },
    {
        "reference_id": "quadrant_problem_board",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图6.pptx",
        "source_slide": 1,
        "semantic_types": ("multi-question overview",),
        "description": "A four-question board that separates task blocks while retaining cross-question handoffs.",
        "edit_guidance": "Use only when the paper truly needs a multi-question map; otherwise choose a simpler route.",
    },
    {
        "reference_id": "three_phase_model_board",
        "source_pptx": "assets/pptx_workflow/数学建模论文流程图7.pptx",
        "source_slide": 1,
        "semantic_types": ("three-phase overview",),
        "description": "A dense three-phase model board for deterministic mechanisms, stochastic behavior, and sensitivity analysis.",
        "edit_guidance": "Use as a composition source for genuinely multi-phase work and remove any phase that lacks evidence.",
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


def _normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().replace("_", " ").replace("-", " ").split())


def select_pptx_reference(semantic_type: str | None, *, reference_id: str | None = None) -> dict[str, Any]:
    """Select one inspected source slide without creating or editing a deck."""

    indexed = {row["reference_id"]: row for row in PPTX_REFERENCE_CATALOG}
    selected_id = reference_id or _SEMANTIC_TO_REFERENCE.get(_normalize(semantic_type), "mcm_sectioned_overview")
    selected = indexed.get(selected_id)
    if selected is None:
        raise ValueError(f"unknown PPTX reference: {selected_id}")
    source = HARNESS_ROOT / str(selected["source_pptx"])
    if not source.is_file():
        raise FileNotFoundError(f"PPTX reference is missing: {source}")
    return {
        "reference_id": selected["reference_id"],
        "source_pptx": selected["source_pptx"],
        "source_slide": selected["source_slide"],
        "description": selected["description"],
        "edit_guidance": selected["edit_guidance"],
        "mode": "copy_and_edit_in_pptx",
    }


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
