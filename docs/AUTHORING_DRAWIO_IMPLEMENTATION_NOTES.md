# Authoring and Draw.io Upgrade — Implementation Notes

Date: 2026-08-21

This historical batch implemented the bounded P0/P1 closure from `math_model_harness_authoring_plane_roadmap_2026-08-20.md` and `drawio_academic_archetype_upgrade_prompt.md`. The 2026-08-22 vNext refactor preserves its Gate and orchestration boundaries while introducing a separate Markdown authoring surface.

## Implemented

- `harness prepare M1|W1|W2|S1` deterministic projections.
- `.harness/views/M1_STATE.md`, `W1_STATE.md`, `W2_STATE.md`, `APPENDIX_PLAN.md`, `PROJECT_BRIEF.md`, `AI_USAGE_LEDGER.md`, and `SUBMISSION_STATE.md` with source SHA-256 provenance and a projection-only notice. They no longer occupy the author's root-document surface.
- AI usage `unknown / none / used`, explicit no-AI confirmation, auditable external-AI records, automatic pending records for Harness-triggered review backends, human verification, and state+records S1/F1 hash binding.
- Profile-driven CUMCM / non-CUMCM disclosure headings without invented content.
- W1 deliverables inside `paper_plan.json`; no separate appendix contract.
- Mutable submission staging directories; no upload, final copy, or readiness claim.
- Five Draw.io academic archetypes plus `custom`, topology-ordered research frameworks, core grouping, composition primitives, non-uniform geometry, compact/no-title paper mode, fail-fast edge preservation, and composition QA warnings.
- PPTX-first concept-figure routing: all user-provided reference slides are inspected, the selected deck is copied once into the figure directory for in-PowerPoint editing, and Draw.io is an explicit fallback rather than the default.
- Archetype/style independence regression tests and five section-16-inspired example specs/native Draw.io outputs.

## Deliberately deferred

- Broad migration of receipts, evidence, results and reports beyond the opt-in four-document v2 control-state relocation into `.harness/state/`.
- Automatic selective rerun and dependency scheduler.
- Sensitivity orchestration as a new execution plane.
- Capability benchmark claims.
- Automatic AI logging for opaque external tools that the Harness cannot observe; those uses still require explicit `harness ai record`.
- Automatic final-paper acceptance or checked-in visual-regression baselines for Draw.io figures. This workstation detects draw.io Desktop 31.1.8 at `D:\Program Files\draw.io\draw.io.exe`; export remains available on demand, while target-size visual review remains a human responsibility.

## Truth boundaries

- `prepare` projections do not pass Gates.
- `.harness/views/PROJECT_BRIEF.md` is regenerated from runtime evaluation and never becomes status truth.
- `paper_plan.json` remains machine IR; `.harness/views/W1_STATE.md` is its deterministic projection. `paper/00_PAPER_PLAN.md` is separate authoring work.
- `submission/staging/` is mutable; only F1 may establish immutable final delivery.
- PPTX staging preserves the source deck and does not manufacture a paper-specific slide, an export, a visual-review receipt, or a Gate result.
- Draw.io archetypes change geometry only. Nodes, edges, roles, source refs, and palette ownership remain in the spec/existing style system.
