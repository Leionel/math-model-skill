# Capability benchmark plan (not yet run)

This is a reproducible framework, not a claim that the Harness has benchmarked
model capability. Regression tests and static schema checks do not count as
real benchmark evidence.

## Four task families

| Family | Real-problem archetype | Primary obligations |
|---|---|---|
| optimization | assignment, routing, resource allocation | objective identity, constraints, feasibility, solver gap/globality, sensitivity |
| prediction | small-sample/time-series/forecast-then-optimize | time-aware split, leakage guard, baseline, OOS design, uncertainty |
| evaluation | multi-criteria ranking/decision | unit/scale handling, weight provenance, comparator and robustness |
| mechanism | physics/geometry/dynamics/ODE or network mechanism | dimensional consistency, boundary/conservation, derivation replay, falsification |

Select at least one real released contest problem and its licensed/public data
for each family. Record problem snapshot, data contract, model contract,
implementation receipt, independent validation, frozen results, evidence
registry, paper plan, and final QA receipt. Keep the source problem project
outside this Skill repository and never use `battle/` as an unscoped fixture.

## A0/A1/A2 protocol

Run each family under all three levels with the same declared compute and
human-review budget:

| Level | Scope | Budget (declare before run) | Success standard |
|---|---|---|---|
| A0 | contract + smoke | one fixed wall-clock cap, one seed, one smoke attempt | valid v2 state, receipt captured, no fabricated evidence, smoke obligations pass |
| A1 | full solution + independent validation | same cap class and seed policy across families | selected full receipt, independent obligations PASS, frozen claimable result |
| A2 | evidence-to-paper delivery | same cap class plus fixed human review window | W1/W2/S1 artifact chain current, deterministic QA and required human checkpoints pass |

Use a pre-registered budget manifest containing wall-clock seconds, CPU/memory,
seed policy, retry cap, model/tool versions, and human minutes. Do not tune
the budget per family after observing results. A failed or blocked level is a
valid outcome and must retain failure evidence.

## Artifact evidence and comparison

For every family/level, publish a run receipt index, DAG freshness report,
validation report, frozen result (or diagnostic failure evidence), and Gate
report. Compare only pre-registered metrics: contract completeness, successful
receipt rate, independent validation pass rate, claimable freeze rate,
artifact-lineage completeness, stale-detection rate, and review time. Do not
turn a qualitative paper score into a model-performance claim.

## Completion criteria

The benchmark is complete only when optimization, prediction, evaluation, and
mechanism each have independent A0/A1/A2 runs under the same budget policy and
all raw artifacts and receipts are available for audit. Until then report
`NOT RUN` and list blockers; never call the current regression suite a
capability benchmark.
