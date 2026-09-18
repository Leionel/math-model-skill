# Verifier registry contract

A **verifier declaration** is metadata about a check this harness already ships.
It never replaces the checker's own verdict and it never runs anything: it makes
the check discoverable, gate-bound and repair-oriented so the Gate engine does
not have to grow another hard-coded branch for every new rule.

## Where things live

| Piece | Path |
| --- | --- |
| Declaration contract | `schemas/verifier.schema.json` |
| Loader / validator | `scripts/verifiers/registry.py` (`load_registry`, `registry_for_gate`) |
| Declarations | `scripts/verifiers/declarations/*.yaml` |
| Binding tests | `tests/test_verifier_registry.py` |

## Declaration fields

| Field | Meaning |
| --- | --- |
| `verifier_id` | Stable lowercase id; unique across the set |
| `entrypoint.script` | The repository-relative script that performs the check |
| `consumes` | Canonical inputs the check reads (see vocabulary below) |
| `gates` | Gate runtimes that invoke this check |
| `severity` | `error` (blocks) or `warning` (surfaces only) |
| `deterministic` | Whether the same inputs must yield the same verdict |
| `repair_hint` | One actionable sentence for an agent that has to fix the failure |

`consumes` vocabulary: `ai_ledger`, `artifact_dag`, `competition_profile`,
`derived_results`, `evidence_registry`, `frozen_results`, `implementation_map`,
`model_contract`, `paper`, `receipts`, `review_evidence`, `run_index`,
`run_manifest`, `validation_report`. The schema enum and the registry constant
are checked for equality, so the two cannot drift.

## Loading rules

- The registry is **read-only and deterministic**: it never executes a
  declaration and never writes a projection.
- An invalid declaration set raises `VerifierContractError` carrying **every**
  error, sorted — a broken declaration is never silently dropped from the
  registry.
- An entrypoint script must exist inside the tree being loaded, and a
  declaration cannot claim a gate whose runtime does not invoke that check:
  `tests/test_verifier_registry.py` reads `scripts/v2_gate_runtime.py` and fails
  if `_v2_gate_<gate>` never names the declaring `verifier_id`; the resolved
  script paths are locked by `tests/test_gate_registry_wiring.py`.

## Gate resolution (P1-B pilot)

M1 resolves `unit-consistency` and `artifact-freshness` through
`v2_gate_runtime._v2_registry_entry_scripts` instead of hard-coding
`scripts/qa/check_units.py` / `check_artifact_dag.py`. The resolved absolute
paths are byte-identical to the previously hard-coded argv, so checker
invocation and exit codes are unchanged. Resolution is **fail closed**: a
registry that cannot load, or a missing declaration for a required verifier, is
an M1 error — it never silently skips the check.

The gate order itself lives in one place (`scripts/gate_order.py`); `harness`,
`harness_status`, `check_gates`, `mcp_tools.state` and the registry re-export
the same tuple object.

## Status

This is the **pilot** step of the roadmap's P1-B: M1 is the first gate whose
checker paths come from the registry. Migrating the remaining
`scripts/qa/check_*.py` verifiers onto the registry, and letting the Gate
engine resolve them through `registry_for_gate`, is the step that follows.