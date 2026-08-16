# Numeric correctness safeguards

The Harness separates three different claims that are often conflated in a generated paper:

1. a displayed number is rounded safely;
2. a declared formula reproduces a numeric value by back-substitution;
3. a solver actually explored the relevant domain and refined a candidate.

None of these alone proves a global optimum.

## Formula replay

Declare scalar cases under `model_contract.models[].plan_details.equation_plan[].verification.numeric_replay[]`. Each case contains an explicit right-hand-side expression, substitutions, expected value, unit, source locator, and its own absolute/relative tolerance. Optional `paper_section_markers`, `paper_tokens`, and `forbidden_tokens` connect the case to the final draft.

```powershell
python scripts/qa/check_formula_replay.py `
  --model-contract model_contract.json `
  --paper paper/main.tex `
  --require-formula-replay `
  --strict
```

The evaluator is a whitelist interpreter for scalar arithmetic and basic functions. It never executes arbitrary Python. This is a numeric replay of the declared equation, not a solver rerun.

## Direction-safe display values

For a result that is a lower or upper feasible bound, extend its presentation entry with:

- `safe_side: lower_bound` and `rounding: floor`, or
- `safe_side: upper_bound` and `rounding: ceil`,
- a `feasibility_recheck` that substitutes the displayed value back into the constraint.

Run:

```powershell
python scripts/qa/check_presentation_safety.py `
  --presentation-contract presentation_contract.json `
  --frozen-results results/frozen_results.json `
  --strict
```

The check uses decimal rounding and a per-entry tolerance. `half_up` is not accepted as a safe-side policy. The displayed value is re-evaluated after rounding, so a directionally safe-looking display cannot pass if it violates the declared constraint.

## Grid plus continuous refinement

`extremum_certificate.schema.json` records a grid receipt, its best point/value, a bounded continuous refinement interval and candidate, and the source artifacts for both runs. Validate it with:

```powershell
python scripts/qa/check_extremum_certificate.py `
  --certificate results/extremum_certificate.json `
  --project-root . `
  --run-id run-001 `
  --strict
```

The checker verifies that the grid best is real, the refinement interval contains that candidate, the refined value is not worse than the grid value, and both source receipts exist. It deliberately rejects `claim_level: global`; global optimality needs an independent mathematical certificate and W2 review rather than a denser grid or a self-attested flag.
