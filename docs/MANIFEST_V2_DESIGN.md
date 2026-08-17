# Manifest v2 design

Status: v2 contract and runtime boundary implemented. Normal-path Gate consumers
now resolve normalized v2 contracts; v1 remains a read-only compatibility input
through the boundary adapter.

## Boundary and source of truth

`competition_profile.json` is the sole competition-rules contract.  It carries
the contest identity and season/mode, the official rule snapshots and endpoint
references, submission/page/AI/manual-check policy, and template/visual-profile
references.  A YAML file in `competition_profiles/` is only a maintainer seed;
it is not evidence of the current official rules.  A new project may begin as
`status: seed`; migration ambiguity is `status: unresolved`. Neither may be
promoted until verified rule snapshots and endpoints have been completed.

`run_manifest.json` v2 is a control-plane document.  It contains project/run
identity, current stage, one user preset (`sprint`, `research`, or `submission`),
allow-listed overrides, the single `competition_profile_ref`, root references,
and the safety/AI/human decision ledgers.  The v2 field is unique: the
embedded `competition_profile` name is accepted only by the v1 adapter and is
never a v2 alias.  Manifest root refs and the profile ref contain only
`path`, `artifact_id`, and (for the profile ref) `profile_id`; they do not own
digests.  Manifest metadata may retain boundary provenance such as
`normalized_from`, but capabilities are rebuilt from `preset` plus
`profile_overrides` and are not copied there.  It deliberately does not contain:

- an embedded competition profile;
- `commands[]` execution declarations;
- `artifacts[]` identity records;
- flat `gates.*` verdicts; or
- reviewer reports copied from their evidence artifacts.

The v1 schema remains a read-only compatibility branch.  `normalize_manifest`
and `migrate_manifest` are the only boundary functions that turn it into v2;
core consumers should accept normalized v2 only.

## Three-layer execution model

| Layer | Canonical owner | Contract in v2 |
|---|---|---|
| Execution fact | process-captured command receipt | argv, cwd, exit code, time, stdout/stderr and selected I/O digests |
| Projection | `run_index.json` | receipt IDs/paths and selected IDs; no copied argv or command truth |
| Control decision | `run_manifest.control` | pre-declared selection rule and root references |

The index can be deleted and rebuilt from receipts plus the control policy.  A
`projected_from` value records projection provenance; `exit_code`, stage and
timestamps in the index are not execution-fact ownership.  A
legacy command row without a real receipt remains a declaration and is reported
as `unresolved`; it cannot be upgraded to a successful run by copying its exit
code.

## Artifact DAG v2

The existing `artifact_dag.json` is minimally extended rather than replaced by
an `artifact_registry_v2.json`.  Each v2 node owns:

`artifact_id`, `role`, `path`, `producer_id`, `dependencies`, `lifecycle`,
`freshness`, `digest_owner`, and (when risk requires it) one SHA-256 digest.

`mutable` artifacts may evolve while exploratory work is in progress.  A
`frozen` or `submission` artifact is immutable: changing bytes creates a new
version and downstream invalidation; migration never rewrites the old file.
Non-critical cache, debug, status, claim-inventory, and rebuildable projection
artifacts may have no digest.  If an index displays a digest, it is a projection
and must point back to its canonical owner.

Rule snapshots and file refs in `competition_profile.json` likewise carry only
`path`/`artifact_id`.  A snapshot digest, when risk policy requires one, is
owned by the artifact DAG or generated metadata; the manifest and competition
rules contract never become a second digest registry.

The digest algorithm is SHA-256.  A digest proves byte identity only.  It does
not prove leakage safety, objective semantics, mathematical correctness,
statistical units, or a figure's conclusion.  The required order is:

`semantic validation -> artifact accepted -> freeze -> hash binding`.

## Presets and capability resolution

```python
from profiles.normalization import resolve_profile

caps = resolve_profile("research", {"math": "strict"})
assert caps.require_independent_validation
assert caps.require_result_freeze
```

`resolve_profile(preset, overrides)` is the sole resolution entry point.  Gate
code should consume flags such as `require_scope_contract`,
`require_formula_replay`, `require_selected_run_receipt`,
`require_final_pdf_hash`, and `require_submission_chain_hash`, rather than
repeating combinations of old dimensions.  The following invariants are true
for every preset and reject `False` overrides:

`require_contest_safety`, `require_human_checkpoints`,
`require_independent_validation`, `require_result_freeze`, and
`require_submission_immutability`.

`sprint` keeps identity and safety boundaries while avoiding bureaucracy;
`research` is the default evidence-chain profile with selective hashes;
`submission` adds strict math/editorial checks and complete final-chain
immutability.  An override is a narrow capability adjustment, not a fourth
supported preset or a new profile-combination matrix.

## Historical and legacy policy

Migration writes to a separate `migration_v2/` directory by default.  It emits
`migrated`, `inferred`, `unresolved`, `deprecated`, and
`manual_review_required` arrays plus warnings and preserved historical paths.
Profile page-limit conflicts, missing official snapshots, missing receipts,
artifact digest/version conflicts, and ambiguous selected runs are surfaced;
they are never silently guessed.  Legacy `extremum_certificate` remains
checker-readable but is deprecated for new writes; verification obligations
belong in the model contract.

Run:

```text
python scripts/migrate_v1_to_v2.py --project <legacy-project>
```

The command does not overwrite the source manifest or any historical frozen
evidence.  A migration report with `manual_review_required` is not a submission
readiness result.
