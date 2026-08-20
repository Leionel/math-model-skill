# WP3 implementation and complexity report

Status: the original Manifest-v2 WP3 boundary was verified on 2026-08-17; the
Review Execution Plane addendum was freshly verified on 2026-08-20. This
report does not claim a real-problem capability benchmark. See
[WP3 test report](WP3_TEST_REPORT.md).

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

## Historical Manifest-v2 complexity baseline (2026-08-17, before Review Plane)

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
4. At that baseline, Skill Creator quick validation, metadata validation,
   29-schema parsing,
   CLI packaging boundary, and full unittest results are recorded in the test
   report.
5. Capability benchmark remains incomplete until the four-type A0/A1/A2 plan
   is independently executed under the stated budget and artifact evidence.

---

# Review Execution Plane (P0) — 2026-08-20 verified addendum

Implements `Make Review Executable` per the v4 OSS-scoped prompt. Design:
[REVIEW_EXECUTION_DESIGN.md](REVIEW_EXECUTION_DESIGN.md).

## A. Changed

- Added CLI `harness review` (`scripts/harness.py`) dispatching to the new
  orchestrator `scripts/qa/run_review.py` (QA phase → bundle → reviewer
  routing → validation → DAG registration → summary). Flags: `--json`,
  `--semantic`, `--judge`, `--fresh`, `--recheck`, `--backend-cmd`.
- Added `scripts/qa/review_evidence.py`: the single deterministic
  review-evidence boundary (discovery, schema/mode/verdict contract,
  freshness recompute, bundle boundary, per-preset W2 adjudication).
- Added `schemas/review_report.schema.json` (one schema for both
  perspectives; finding contract with stable ids, severity, locator,
  required fix, status).
- W2 gate (`scripts/v2_gate_runtime.py`) now calls `evaluate_w2_review`
  after deterministic QA; review errors are first-class gate errors.
- `harness status` (`scripts/harness_status.py`) projects a review summary
  (per-perspective verdict/freshness/severity/independence, degraded flag,
  next finding as next action).
- References: added `references/review/judge_lens.md`; updated
  `semantic_critic_rubric.md` (execution contract) and `revision_policy.md`
  (recheck semantics); router links the review branch. SKILL.md W2 section
  and CLI quick start mention `harness review` (+~15 lines).
- Tests: `tests/test_review_execution.py` (prompt §24 A–Q plus degraded/
  foreign-run/gate-integration cases) and `tests/test_review_e2e.py`
  (prompt §23 E2E-A/B/C/D) with a deterministic stub reviewer
  (`tests/fixtures/review_stub/stub_reviewer.py`).

Reliability audit corrections made after rerunning the GLM implementation on
2026-08-20:

- removed a date-dependent test that treated `2026-08-18` as permanently in
  the future;
- hash review inputs before starting the child process, not afterwards;
- bind backend output to the orchestrator-selected perspective/mode/level,
  predeclared receipt ID, exact bundle input, exact report output, and bundle
  working directory;
- require canonical artifact IDs and the minimum artifact-role set for each
  perspective; filter foreign-run history before selecting current evidence;
- block open medium findings unless explicitly accepted with justification;
- reject bundle/report path traversal, detect protected author/control
  mutation, and quarantine invalid backend output outside discoverable W2
  evidence;
- stream phase progress in human mode and use collision-resistant report
  names.

Review execution behavior: deterministic QA runs first and must pass; the
allow-listed bundle is materialized with per-member digests; reviewers run
either in-context (routing instructions with exact output path/contract) or
through the `--backend-cmd` seam via `run_and_record.py --stage review`
(process-captured receipt); reports are validated against schema, mode↔level
mapping, artifact bindings, freshness, and verdict/finding consistency, then
registered as `role=review_report` DAG nodes.

## B. State complexity

- canonical state delta: **0** (manifest gains no review fields; review
  truth lives in generated reports + DAG nodes)
- schema delta: **+1** (`review_report.schema.json`; justified in the design
  doc — no existing schema carries perspective/mode/independence/binding)
- profile dimension delta: **0** (perspectives derive from the preset)
- top-level gate delta: **0** (still M1 P1 P2 W1 W2 S1)

Current absolute counts after this addendum: **30 schemas**, **32 QA Python
scripts**, **205 SKILL.md lines**, **284 README.md lines**, and **388/388**
tests passing. These counts are not capability scores; they make the delta
auditable against the historical table above.

## C. Reuse

Existing deterministic QA runner (dispatched, not reimplemented); existing
`judge_scan` (kept in `check_paper_style.py`, seeded into the bundle);
existing receipt system (`run_and_record.py`, stage `review` was already
legal); existing artifact DAG (new role only); existing digest-owner rules;
existing `harness_status` view pattern; existing rubric/revision references.

## D. Multi-agent / independence

One minimal seam: `--backend-cmd`, executed per perspective with
`MATH_REVIEW_*` env (bundle path, output path, rubric, mode, independence).
No worker SDK, registry, or orchestration graph. `independence_level` comes
from the mode↔level mapping validated against the report; a fresh (L1+)
report additionally requires a bundle whose members hash-match and contain
only allow-listed roles. The receipt proves the supplied bundle, cwd, command,
and output binding; it does not turn an arbitrary local process into an OS
sandbox. Research L0 fallback must set
`degraded_independence: true` or W2 fails; submission requires one current
L1+ report. The E2E suite proves a real backend execution end to end
(receipt + bundle + report + DAG node + gate consumption).

## E. Deferred (not implemented)

P1 (resume/retry/trajectory/context router/generic approvals), P2 (worker
adapters, multi-agent orchestration, capability routing), P3 (skill
benchmark/optimization/registry). Nothing from these lists was implemented.
