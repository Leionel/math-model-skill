# Gate policy

The executable source is `scripts/qa/check_gates.py` plus the normalized
capability resolver. This page is the concise decision contract for agents.

## Order and stopping rule

```text
S0 -> M1 -> P1 -> P2 -> W1 -> W2 -> S1 -> F1
```

Run one Gate at a time. Stop on the first factual failure, missing input,
`FAIL`, `ERROR`, stale artifact, or unresolved human checkpoint. A later
manifest status cannot make an earlier Gate pass.

## Gate minimums

| Gate | Factual checks | Required human boundary |
|---|---|---|
| M1 | profile/rule boundary, ready model contract, evidence linkage, validation obligations, current DAG | mechanism fit, candidate fairness, data sufficiency, mathematical consistency, literature fit, falsifiability |
| P1 | process-captured successful smoke receipt for this run | confirm smoke scope if profile requires it |
| P2 | exactly one selected successful full receipt, independent validation, freeze receipt, frozen result binding | confirm selected result and frozen artifact |
| W1 | ready paper plan, verified evidence, claim-to-evidence continuity | confirm evidence and paper scope |
| W2 | deterministic QA rerun as required, math/logic/figure/PDF checks, current source/build | independent mathematical and writing review |
| S1 | current verified competition profile, page/support/AI/manual checks, submission QA | final human checklist and decision |
| F1 | immutable submission manifest and package/PDF/source identity | no automatic portal upload; preserve submission receipt |

`sprint` keeps safety and identity while minimizing extra hashes. `research`
requires the formal evidence chain and selected-run bindings. `submission`
adds strict math/editorial/template/bibliography checks and final-chain
immutability. Overrides cannot disable safety, human checkpoints, independent
validation, result freeze, or submission immutability.

## Safety and evidence rules

- Keep official rules distinct from a local conservative policy.
- Do not use an unverified seed as current official rules.
- Keep failed runs and diagnostic failure evidence; never rewrite a frozen file.
- `run_index.json` and status are projections, not digest owners.
- Recompute semantic checks independently; SHA-256 only proves bytes unchanged.
- Changes to immutable inputs create a new version, stale dependants, and
  pending affected Gates.
- A regression test proves a stated implementation path. It is not a capability
  benchmark, a mathematical proof, or evidence of generalization.

## W2 and review boundary

Deterministic QA, mathematical semantic checks, visual review, Semantic Critic,
and human review have separate verdicts. A successful checker does not prove
the paper's reasoning or scientific claims. Enhanced/strict profiles rerun QA
from declared inputs; hand-editing an old `ok=true` report is never a repair.

See [math correctness](../validation/math_correctness_profile.md), [validation
obligations](../validation/validation_obligations.md), and [submission freeze](../submission/submission_freeze.md) when the task enters those branches.
