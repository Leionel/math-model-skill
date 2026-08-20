# v1 to v2 migration guide

This guide covers the WP1 compatibility boundary.  Migration is explicit and
non-destructive: old documents remain readable and frozen evidence remains
byte-for-byte untouched.  New project writers must emit v2 only.

## What changes

| v1 field/source | v2 destination | Migration rule |
|---|---|---|
| `run_manifest.competition_profile` (v1 only) | `competition_profile.json` + `competition_profile_ref` | Extract the embedded profile; missing official snapshots/endpoints and critical submission rules are unresolved. |
| `run_manifest.commands[]` | `command_receipt` references and `run_index.receipts[]` | A declaration without a real receipt stays unresolved; copied exit codes are not execution facts. |
| `run_manifest.artifacts[]` and legacy DAG | existing `artifact_dag.json` v2 projection | Build stable artifact IDs and report path/digest/version conflicts. |
| `run_index.selection_policy` | `run_manifest.control.selection_policy` | The v2 index stores only a policy reference and selected receipt IDs. |
| five legacy profile dimensions | `preset` + `profile_overrides` | Resolve once to `ResolvedCapabilities`; ambiguous combinations require review. |
| `run_manifest.reviewer.*` (incl. `blind_reviewers`) | not migrated | Mark deprecated. Reviewer-count semantics stay v1-only; after migration run `harness review` to produce real reports under `reports/review/`. No v1 review status is mapped or auto-passed. |
| `extremum_certificate` | legacy checker compatibility | Mark deprecated; do not create a new certificate writer path. |

The v2 manifest has only the unique `competition_profile_ref`; it has no
embedded profile alias, command list, artifact registry, flat gate results, or
copied reviewer state.  The canonical roots are referenced by path/artifact ID
only and never carry SHA-256.  Rule-snapshot refs in
`competition_profile.json` use the same path/artifact-ID-only form; digest
ownership belongs to the artifact DAG/generated metadata.

## Run the migration

From the repository root:

```powershell
python scripts/migrate_v1_to_v2.py --project C:\path\to\legacy-project
```

The default output is `C:\path\to\legacy-project\migration_v2`.  To use an
explicit destination and machine-readable output:

```powershell
python scripts/migrate_v1_to_v2.py `
  --project C:\path\to\legacy-project `
  --output-dir C:\path\to\migration-v2 `
  --json
```

`--no-write` performs the same read-only analysis and prints the bundle without
creating files.  Writing into the source project root is rejected.  The output
contains, when available:

```text
competition_profile.json
run_manifest.json
artifact_dag.json
run_index.json
migration_report.json
```

## Read the report before promotion

`migration_report.json` always includes these arrays:

- `migrated`: transformations performed by the adapter;
- `inferred`: low-risk defaults explicitly inferred from legacy fields;
- `unresolved`: facts that v1 did not establish;
- `deprecated`: read-compatible legacy paths with no v2 writer;
- `manual_review_required`: decisions a human must make before a formal Gate.

It also records warnings and paths of historical frozen evidence preserved by
the operation.  Treat `status: manual_review_required` as blocked for research
or submission promotion.  Do not fix an unresolved page limit by editing the
report; update the standalone profile from an authoritative rule snapshot and
rerun the migration/validation boundary.

The adapter does not invent `submission.max_paper_bytes`.  A missing value is
nullable and is reported as unresolved/manual review.  Legacy page limits,
support policy, AI disclosure policy/format, and page-count scope are explicitly
marked inferred until an authoritative rule snapshot verifies them; seed values
must not be presented as official facts.

## Required manual checks

1. Attach a real official rule snapshot and verify its URL, retrieval time and
   artifact reference.  A contest profile seed is not an official snapshot.
2. Resolve any page-limit disagreement between embedded profile, top-level
   manifest fields, and submission policy.  The adapter never chooses a winner.
3. Register immutable command receipts for old command declarations.  The
   legacy `command`, `exit_code`, or `selected` fields cannot serve as a receipt.
4. Resolve artifact path/version/digest collisions between the old manifest,
   DAG, receipts and frozen results.  Do not replace an old frozen file in
   place; create a new artifact version and invalidate downstream projections.
5. Confirm exactly one selected receipt under the policy owned by
   `run_manifest.control`.  Multiple selected rows or no policy are blocked.
6. Review the deprecation warning for any `extremum_certificate`; keep its
   checker for old evidence but route new obligations through the model
   contract.

## Programmatic boundary API

```python
from profiles.normalization import (
    load_normalized_manifest,
    migrate_manifest,
    resolve_profile,
)

caps = resolve_profile("submission")
normalized = load_normalized_manifest("run_manifest.json")
bundle = migrate_manifest(legacy_manifest, project_root=project_root)
```

`normalize_manifest` and `load_normalized_manifest` return only the v2 control
representation.  `migrate_manifest` additionally returns the canonical profile,
DAG/index projections and report.  Downstream core code should consume the
normalized v2 result; it should not grow a second v1/v2 branch.

## Historical evidence guarantee

Migration never rewrites `frozen_results`, `submission_manifest`,
`submission_receipt`, or any other historical artifact.  A changed immutable
artifact requires a new version, digest and downstream invalidation.  A matching
SHA-256 is an identity check, not a semantic validation verdict.
