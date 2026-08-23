# vNext Human-Visible Workflow — Execution Status

This document records the implementation state on 2026-08-22. It distinguishes
working changes from intentionally unexecuted benchmark work.

## Completed in this batch

| Work package | Delivered evidence |
|---|---|
| WP0 baseline | `BASELINE_BEFORE_VNEXT.md`, isolated branch `refactor/human-visible-workflow` |
| WP1–WP4 human surface | Non-overwriting project templates; `.harness/` directory skeleton; `harness research`, `model`, `solve` façades |
| Markdown → JSON start | Explicit YAML block in `02_MODEL_DECISION.md` compiles to validated `.harness/contracts/model_contract.json`; it updates the manifest root but does not pass M1 |
| WP6 projection split | `prepare` and AI ledger now write under `.harness/views/`; author documents are never overwritten |
| WP7–WP8 section writing/review | `paper plan`, `paper write <section>`, and `paper review <section>` create only local section documents; semantic-critic rubric now includes prose-specific checks without a synthetic score |
| WP9–WP11 figures | 15 attributed MIT reference seeds, visual analysis, 10 local Draw.io variants, 37 inspected user-provided PPTX reference slides, source/downloader/build scripts, figure brief scaffolding, a PPTX-first router, and an explicit Draw.io fallback |
| WP12–WP14 context/UX | `harness context --stage …` lists a bounded context; thin `submit check` dispatches the factual S1 checker; human checkpoints have reader-facing prompts |
| WP5 ownership | `JSON_OWNERSHIP_AUDIT.md` classifies every current schema without deleting one |
| Phase D control-layout slice | Explicit `harness migrate --layout hidden` dry-run/apply move for the four v2 control documents; no receipts, frozen artifacts, evidence, results or author files are rewritten |

## Verification recorded

- `python -m unittest tests.test_human_surface_cli tests.test_harness_cli tests.test_authoring_plane tests.test_drawio_backend -v` — 32 passed, including the Markdown-to-JSON compiler, section-local authoring, projection split, and Draw.io regressions.
- `python -m unittest tests.test_state_layout_migration -v` — 4 passed: dry-run non-mutation, explicit apply, normal hidden-layout CLI paths, ambiguity rejection, and delegated UTF-8 output.
- All five user-provided PPTX decks (37 slides) were rendered and structurally inspected. `python -m unittest tests.test_pptx_router tests.test_human_surface_cli tests.test_drawio_backend tests.test_state_layout_migration tests.test_harness_cli tests.test_authoring_plane -v` — 39 passed, including PPTX catalog selection, writable non-overwriting staging, and explicit Draw.io fallback.
- A disposable v2 project completed `init → migrate --layout hidden → --apply → status → doctor → prepare → run`; the hidden run index retained the relocated policy reference.
- `python -m py_compile scripts/harness.py scripts/human_surface.py scripts/figures/tool_router.py scripts/prepare_project.py` — passed.
- Schema JSON parse check — 30 schemas parsed.
- Visual seed PNG headers/dimensions and local gallery exports were inspected; the generated SVG/PNG outputs are present.
- Reproduced GBK failures for top-level help and delegated projection output have targeted UTF-8 fixes and regression coverage.

## Not completed or not claimable

- Hidden v2 state relocation is opt-in, leaves new `init` flat for compatibility, and intentionally moves only the four control documents—not all receipts, reports or historical artifacts.
- Only `model_contract` has an authoring compiler. Compilers for paper, implementation, data and diagram IR are design targets, not implemented facts.
- `harness solve` captures an actual command only when one is supplied; it does not invent a run, validation, freeze or solution-report content.
- The PPTX route selects a reviewed source slide and stages a writable copy; no paper-specific slide edit, final PPTX/PDF export, or target-size paper acceptance has been claimed in this batch.
- No external paper project, full computation, independent validation, PDF review, competition submission, or F1 freeze was run in this batch.
- No three-CUMCM/two-MCM comparative battle benchmark was run. `CAPABILITY_BENCHMARK_PLAN.md` remains a plan, not evidence of vNext quality.
- The complete baseline discovery suite exceeded its 90-second observation window without output, and the post-change discovery suite exceeded a separate 60-second bounded window without output; both were stopped. Full-discovery state is unknown, not pass.

## Next promotion gates

1. Run the full test suite to completion in a bounded CI environment and resolve or explicitly baseline pre-existing lint violations.
2. Exercise the opt-in migration against a fully populated external project, including current review evidence, before treating the Phase D cleanup as broadly proven.
3. Add the remaining authoring compilers only where a real consumer demonstrates need.
4. Run the specified five-task battle with fixed budgets and retained artifacts before making any quality or efficiency claim.
