# Baseline Before vNext

Captured on 2026-08-22 before the Human Visible Workflow refactor on branch `refactor/human-visible-workflow`.

| Item | Observed baseline |
|---|---|
| Commit | `fd94bea Improve modeling workflow and validation coverage` |
| Python | `3.14.5` (`C:\Python314\python.exe`) |
| JSON schemas | 30 parse successfully |
| Initial state | `competition_profile.json`, `run_manifest.json`, `artifact_dag.json`, `run_index.json` |
| Agent-authored structured documents in a normal formal flow | `model_contract.json`, `evidence_registry.json`, `paper_plan.json`, and, for formal diagrams, `diagram_spec.json` |
| Current generated Markdown | `MODELING_PLAN.md`, `PAPER_OUTLINE.md`, `PROJECT_BRIEF.md`, `APPENDIX_PLAN.md`, `AI_USAGE_LEDGER.md`, `SUBMISSION_CHECKLIST.md` at the project root |
| Figure path | Data plots use deterministic Python; formal diagrams use `diagram_spec.json` → native Draw.io; no reference gallery is present |
| Paper path | `paper_plan.json`/writer package → draft; review is executable through `harness review` |

## Checks actually run

```powershell
python --version
python -m unittest discover -s tests -q
ruff check scripts tests
python -c "import json; from pathlib import Path; paths=sorted(Path('schemas').glob('*.schema.json')); [json.loads(p.read_text(encoding='utf-8')) for p in paths]; print(f'schema_count={len(paths)}')"
```

- Schema parsing passed with `schema_count=30`.
- `ruff check scripts tests` failed before this refactor with 21 violations in existing files, including unused imports/locals and same-line statements outside this batch.
- Full discovery produced no result within a 90-second observation window and was stopped to avoid an unbounded baseline job. It is therefore **not** recorded as pass or fail.
- No complete external demo project was available in this repository. Its full-run file count is intentionally unmeasured rather than invented.

## Baseline boundary

This record establishes the pre-refactor facts only. It does not claim a clean suite, a capability benchmark, a complete paper run, or submission readiness.
