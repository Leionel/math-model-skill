# Artifact contracts (v2)

This reference defines ownership and minimum I/O. It does not replace the
schemas or checker implementations.

## Three layers

| Layer | Canonical owner | Rule |
|---|---|---|
| execution fact | immutable `command_receipt` | owns argv, cwd, exit code, timestamps, and selected I/O bindings |
| projection | `run_index.json` | stores receipt IDs and selection; never copies command truth |
| control decision | `run_manifest.json` v2 `control` | owns the selection policy, roots, human decisions, safety, and AI ledger |

An old manifest command row is a declaration until a real receipt is present.
Do not promote a copied exit code or a selected flag into execution evidence.

## v2 roots and DAG

`run_manifest.json` contains only `competition_profile_ref`, normalized
`preset`/overrides, canonical root refs, control policy, safety, AI usage, and
human checkpoints. It has no embedded profile, `commands[]`, `artifacts[]`,
flat `gates.*`, or copied reviewer reports.

`competition_profile.json` is standalone. A YAML under `competition_profiles/`
is a maintainer seed; an empty or unverified rule snapshot means
`status: seed`/`unresolved`, never `verified`.

`artifact_dag.json` owns `artifact_id`, role, path, producer, dependencies,
lifecycle, freshness, and a digest only when the risk policy requires it.
Immutable/frozen/submission bytes are versioned and invalidate dependants when
changed. The projector recomputes factual freshness in memory and never writes
the DAG.

## Digest policy

Use SHA-256 only. A given artifact has one digest owner:

- artifact DAG/generated metadata owns rule snapshots and canonical tables/
  figures/evidence when required;
- a command receipt owns selected run I/O;
- `frozen_results.results_sha256` owns its canonical results payload;
- `submission_manifest` owns final package/PDF/source binding at F1.

Indexes and status views may display a projected identity, but cannot become a
second registry. Hash equality is not semantic validation; perform semantic
validation before freeze and hash binding.

## Minimum Gate inputs

| Gate | Minimum artifacts | Result boundary |
|---|---|---|
| M1 | model contract, evidence registry, profile, DAG, human checkpoint | model plan is ready and falsifiable |
| P1 | one successful smoke receipt | smallest real process ran |
| P2 | selected full receipt, freeze receipt, frozen results, independent validation | only PASS + claimable result is evidence |
| W1 | paper plan, verified evidence, current frozen result | claims map to evidence |
| W2 | draft/source, abstract, conclusion, deterministic QA and required review receipts | content ready, not submission ready |
| S1 | verified current profile, PDF/package, submission QA, human checkpoint | current submission contract passes |
| F1 | immutable submission manifest and receipt | final package cannot be overwritten |

Detailed result metric semantics remain in the validation references. Keep
population, units, precision, source key, and validation status attached to the
frozen result; Writer and Registry cannot upgrade `claimable`.

## Historical and generated-file boundary

Migration preserves old frozen files byte-for-byte and writes a separate
`migration_v2/` bundle. `extremum_certificate` remains read-compatible but has
no new writer path. Never edit generated evidence by hand; rerun its producer
and then rerun affected Gates.
