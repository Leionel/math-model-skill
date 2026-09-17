# End-to-end demo

One synthetic problem, the full chain, and six concrete bypass attempts.

```bash
python examples/end_to_end/run_demo.py --out tmp/demo-run
```

The command is idempotent in one direction only: `--out` must be absent or
empty, because a demo that could overwrite a previous run would not be evidence
of anything. The run leaves the project in place so you can inspect every
artifact with `harness status`.

## What the chain actually does

| Stage | What happens | Who is accountable |
| --- | --- | --- |
| S0 | `harness init`, then the operator binds a rule snapshot | problem_analyst |
| M1 | model contract with two candidates, typed parameter provenance and validation obligations; operator checkpoint | modeler |
| P1 | one real smoke process captured as a receipt | experimenter |
| P2 | full run, obligation recomputation, freeze bound to the selected receipt, evidence registration | experimenter |
| W1 | paper plan whose claims bind claimable evidence | writer |
| W2 | deterministic QA, then a fresh-context reviewer executed from an allow-listed bundle; the observable AI call is logged and human-verified | reviewer |

The solver in [`model.py`](model.py) is deliberately tiny and uses only the
standard library: three products each served by one of three capacitated
depots, minimized by enumeration. Both the feasibility check and the objective
recomputation come from a genuinely different summation order, so "independent
validation" is not a label.

Input data lives in [`input.json`](input.json); the statement it satisfies is
[`problem.md`](problem.md). Both are synthetic. The competition profile the
driver writes is likewise synthetic and says so — a real contest run must bind
the organizer's page, and a maintainer seed profile can never pass submission.

## The probe table

Each of the first five rows performs a real attack against a copy of the
finished project; the last row re-derives the chain from bytes on disk. Every
verdict is the Harness's own exit code and error list:

| Attempted bypass | Mechanism that refuses it |
| --- | --- |
| hand-write `gates.m1.status = "pass"` | v2 control state forbids a `gates` key at all |
| freeze the same numbers from a free-text command | P2 requires `frozen_results.command` to name the selected receipt |
| append one sentence to the reviewed paper | review freshness recomputes every bound digest |
| reviewer backend declares itself L2 | independence level is bound by the orchestrator, not the report |
| add an unevidenced figure to the abstract | deterministic QA consistency refuses the number |
| recompute the chain | frozen result → receipt id → argv/cwd/exit → pinned snapshot digests |

The driver exits non-zero if any row stops holding, so this directory doubles as
a CI sentinel. `evaluation/redteam.py` reuses the same fixture for a wider
scenario matrix, including the two things the Harness does **not** enforce
today.
