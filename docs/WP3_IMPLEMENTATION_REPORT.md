# WP3 implementation and complexity report

Status: implementation delivered and regression-verified on 2026-08-17. This
report records the thin boundary added by WP3; it does not claim a real-problem
capability benchmark. See [WP3 test report](WP3_TEST_REPORT.md).

## Scope delivered

- `scripts/harness.py` resolves project roots/presets and dispatches existing
  checkers, receipt runner, freeze scripts, and migration CLI.
- `scripts/harness_status.py` projects normalized control, real receipts, DAG
  freshness, and factual Gate errors without writing files or becoming a
  digest registry; v1 is marked deprecated.
- `run_deterministic_qa.py --manifest` resolves v2 canonical roots while
  retaining the existing checker implementation and flags.
- `init` emits only a v2 standalone seed profile, slim manifest, minimal DAG,
  and run-index projection.
- README/SKILL/reference router describe the v2 normal path and leave detailed
  validation/writing/figure/literature/submission material one hop away.

## Complexity before / observed after

| Measure | Before (audit baseline) | Observed v2 normal path |
|---|---:|---:|
| Schema count | 29 | 29; no new error-specific Schema |
| QA scripts | 30 | 30; the CLI dispatches rather than adding a second QA tree |
| schema-backed JSON types that a human/Agent may maintain | at least 15 | four core contract families plus only triggered domain contracts; receipts/index/status are producer-owned |
| files emitted by a new project | legacy guidance exposed many optional/empty artifacts | 4 v2 files; 2 control/profile documents plus 2 rebuildable DAG/index projections |
| duplicated canonical domains | 4 | 0 in the v2 path; v1 duplication remains inside the read-only adapter |
| duplicated semantic field families | at least 25 | removed from v2 manifest; it has no embedded profile, command list, artifact registry, flat Gate verdicts, or copied capabilities |
| supported profile dimensions / combinations | 5 / 72 | 3 presets; allow-listed overrides do not create a supported combination matrix |
| typical M1 durable files | `6 + N` | still `6 + N`; evidence was not deleted, but the user supplies one project root and the CLI resolves paths |
| normal W2 path arguments | 14 | one project root plus optional `--strict/--profile` assertion; debug scripts remain available |
| SKILL.md / README lines | 307 / 555 | 188 / 210 |
| required up-front user choices | at least 7 | 2: competition seed and preset; official-rule resolution and human checkpoints remain explicit later decisions |
| regression | 284 / 286 with 2 errors | 352 / 352 in the final aggregate run |
| capability benchmark | not run | not run; only an executable A0/A1/A2 plan exists |

The comparison is interface/maintenance complexity, not model quality or
runtime performance. Existing WP1/WP2 schemas, producers, and checkers remain
the canonical implementation.

## Promotion gates

1. `init -> status -> check M1` is JSON-readable and factually blocked on the
   missing M1 contract/human checkpoint.
2. A fake manifest Gate status cannot change the first factual blocker.
3. Receipt selection, stale DAG artifacts, pending human checkpoints, and CLI
   versus direct checker exit codes are covered by integration tests.
4. Skill Creator quick validation, metadata validation, 29-schema parsing,
   CLI packaging boundary, and full unittest results are recorded in the test
   report.
5. Capability benchmark remains incomplete until the four-type A0/A1/A2 plan
   is independently executed under the stated budget and artifact evidence.
