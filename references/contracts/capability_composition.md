# Capability composition contract

A **capability** is a composable bundle: the verifiers, schemas, artifact roles
and gates one modeling concern needs. A competition profile composes capability
ids; the loader expands `requires` transitively and reports the concrete
resources a project actually carries. It never restates another capability's
content and never replaces a verifier's own verdict.

## Where things live

| Piece | Path |
| --- | --- |
| Declaration contract | `schemas/capability.schema.json` |
| Loader / resolver | `scripts/capability_composition/composition.py` |
| Capability declarations | `scripts/capability_composition/declarations/*.yaml` |
| Profile → capability mapping | `scripts/capability_composition/compositions.yaml` |
| Binding tests | `tests/test_capability_composition.py` |

The package is deliberately **not** named `capabilities`: `profile_engine`
imports its sibling `capabilities` module by bare name, and a same-named package
under `scripts/` would shadow it for callers that put `scripts/` on `sys.path`
first.

## Fields

| Field | Meaning |
| --- | --- |
| `capability_id` | Stable lowercase id; unique across the set |
| `verifiers` | Verifier registry ids this capability carries |
| `schemas` | `schemas/*.schema.json` files the capability owns |
| `artifact_roles` | Run-manifest artifact roles it produces or consumes |
| `gates` | Gates the capability participates in |
| `requires` | Other capabilities it builds on (expanded transitively) |

## Fail-closed cross-checks

- A bundled verifier must exist in the verifier registry **and serve at least
  one of the capability's gates** — a capability cannot carry a check it never
  gates.
- A named schema must exist under `schemas/`; a `requires` target must exist;
  a `requires` cycle is an error.
- Every key in `compositions.yaml` must be a `profile_id` that a real
  competition profile declares, so renaming a profile fails the composition
  instead of silently keeping a stale mapping.
- Errors are collected and sorted; a broken set never degrades into a quietly
  smaller composition.

## Inspecting a project

```text
harness profile --compose --json                          # the project's resolved profile
harness profile --compose --profile-id mcm_icm --json      # a named profile
```

## Status

This is the roadmap's P1-C composition step. The profile → capability mapping
lives here because `schemas/competition_profile.schema.json` is a closed
contract; folding a `capabilities` list into that schema (and into the profile
seeds) is the follow-up. Capability declarations currently stay within the two
verifiers the registry declares, so the composition is real but small.