# Authoring Plane

The Authoring Plane makes canonical Harness state readable without creating another truth layer.

## Commands and outputs

| Command | Deterministic outputs | Canonical inputs |
|---|---|---|
| `harness prepare M1` | `MODELING_PLAN.md`, `PROJECT_BRIEF.md` | model contract, manifest, profile, DAG/index |
| `harness prepare W1` | `PAPER_OUTLINE.md`, `APPENDIX_PLAN.md`, `PROJECT_BRIEF.md` | paper plan IR, frozen result reference, runtime state |
| `harness prepare W2` | refreshed `PROJECT_BRIEF.md` with coverage/review/targeted finding | runtime Gate evaluation, DAG freshness, review evidence |
| `harness prepare S1` | `AI_USAGE_LEDGER.md`, disclosure draft, `SUBMISSION_CHECKLIST.md`, staging directories, `PROJECT_BRIEF.md` | profile, AI registry/state, runtime state |

Every projection contains:

```text
Generated projection — factual state remains in Harness contracts/receipts.
```

and a list of source paths with SHA-256. The digest proves which bytes were rendered; it does not prove the source is semantically correct. Editing a projection cannot pass a Gate. Regenerate it after changing the canonical source.

## AI usage tri-state

`run_manifest.ai_usage_state` is one of:

- `unknown`: initial state; S1 must block;
- `none`: allowed only after `harness ai confirm-none` records an explicit human declaration;
- `used`: requires one or more auditable entries. External unobservable uses enter through `harness ai record`; Harness-triggered review backends are recorded automatically as `pending` and must be completed with `harness ai verify`.

The S1 hash binds the state, explicit declaration, and records. Changing `unknown` to `none`, editing the human declaration, or adding/removing a record invalidates a stale S1 report even when the usage list is empty in both cases.

The disclosure renderer uses only the canonical profile and AI registry. It uses `AI工具使用详情` for CUMCM and `Report on Use of AI Tools` for other profiles. It never invents missing prompt, adoption, modification, or verification details.

`--backend-cmd` therefore requires an explicit `--backend-kind`; `ai` additionally requires tool, model, and provider identity, while `non_ai` is not written into the AI registry. The execution receipt is the interaction record, and strict Contest Safety rejects a pending AI record until a human verifies how the report was checked and changed.

## Submission staging

`prepare S1` creates:

```text
submission/
├── staging/
│   ├── support/
│   ├── ai_disclosure/
│   └── official_outputs/
└── final/
```

`staging/` is mutable preparation space. `final/` remains empty until the existing F1 producer freezes a passing package. `prepare` never uploads and always reports `submission_ready: false`.

## Deferred boundaries

This round deliberately does not migrate all internal files into `.harness/`, create a selective-rerun scheduler, add a sensitivity orchestrator, or claim a capability benchmark. Those changes require compatibility and real-battle evidence beyond deterministic authoring projections.
