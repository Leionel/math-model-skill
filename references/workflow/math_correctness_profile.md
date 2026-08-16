# Strict math correctness profile

`run_manifest.json` may opt into the mathematical correctness profile with:

```json
{
  "math_correctness_profile": "strict"
}
```

The default is `baseline`, so existing development runs are not silently
reinterpreted as migrated runs. This profile is intentionally a Gate policy,
not a claim that a checker has proved every theorem or model assumption.

## What strict enables

At M1, the Harness runs the formal research-first modeling-plan check and
requires a ready `scope_contract`. Question-specific parameters, units, time
origins, coordinate frames, and event definitions must be bound to the model
and checked in the marked paper sections.

At W1/W2, the run must provide a ready `presentation_contract`, a
`writer_package`, and a deterministic QA report with the following passing
checks:

- `scope_consistency`
- `formula_replay`
- `derivation_integrity`
- `math_writing`
- `presentation_safety`
- `pdf_math_consistency`

The report must also declare `pdf` and `pdf_source` inputs. The Gate reruns
deterministic QA from those declared inputs; it does not trust a manually
edited `ok=true` report. Formula replay cases are evaluated by the safe scalar
interpreter, and argument units must bind their declared replay cases.

If a sensitivity experiment is declared, strict QA requires execution
receipts with successful exit codes and unique artifacts. If figure lineage,
extremum certificates, or other optional math artifacts are declared, the
same rerun includes their semantic checks. An extremum checker may validate a
grid plus bounded continuous refinement, but it will not accept a bare
`global` claim as a proof.

## What strict does not automate

It does not establish that the selected model is substantively appropriate,
that a cited theorem applies to the problem, or that a numerical solver found
a global optimum. Those remain explicit M1/W2 human checks. The checker also
does not require SHA-256 for ordinary local consistency checks; immutable
submission packaging retains hash requirements in `integrity_mode=submission`.

## Recommended promotion path

1. Keep a local run on `baseline` while migrating the model contract and
   paper plan.
2. Add `scope_contract`, numeric replay cases, and `replay_case_ids` to the
   argument units; generate and verify the real presentation/PDF artifacts.
3. Add `"math_correctness_profile": "strict"` and run the full M1/W1/W2 Gate.
4. Treat any strict failure as a migration or evidence issue, not as a reason
   to weaken the profile or delete the intermediate artifact.
