# Agent contracts

Seven reasoning roles sit above the deterministic Harness. This document says
what a contract is, what it is checked against, and what it explicitly is not.

```text
agents/<role>/agent.yaml   ──┐
                             ├─▶ harness agents check ──▶ PASS / FAIL (exit 1)
schemas/agent_contract       │      ▲
  .schema.json               │      │ reads live ground truth
                             ▼      │
                     CLI parser · schemas/ · Gate tuple ·
                     artifact-role vocabulary · SAFE_INVARIANTS
```

## The roles

| Role | Owns stage | Writes artifacts | Why it is separate |
| --- | --- | --- | --- |
| `orchestrator` | dispatch only | **nothing** | chooses the next move from the recomputed first blocker |
| `problem_analyst` | S0 | `problem_snapshot`, `data_contract` | turns a statement into a checkable scope |
| `modeler` | M1 | `model_contract` | makes the model falsifiable before code exists |
| `experimenter` | P1, P2 | receipt, `frozen_results`, `evidence_registry`, `validation_report`, `implementation_map` | only a captured process may become a number |
| `writer` | W1 | `paper_plan`, paper/abstract/conclusion/sections, `figure`, `table` | prose is bound to evidence, not the reverse |
| `reviewer` | W2 | `review_report` | judges from outside the author's context |
| `compliance` | S1, F1 | nothing (producers write) | rules and AI disclosure are adjudicated against verified snapshots |

## Contract fields

```yaml
schema_version, name, role, purpose
stages:               [S0 | M1 | … | F1]
inputs:               [free strings — what must already exist]
allowed_tools:        [harness CLI path | mcp:<tool>]
allowed_artifacts:    {read: [role], write: [role]}
forbidden_actions:    [>= 5 entries, including the mandatory floor]
outputs:              [{name, schema, persists}]
preconditions:        [what must be true before this role acts]
postconditions:       [what must be true after it claims to be done]
failure_conditions:   [when it must stop and hand back a blocker]
references:           [repo-relative paths it must load]
```

## What the checker verifies

Every rule below is a real rejection with a regression test in
`tests/test_agent_contracts.py` (24 cases).

1. **Schema validity** against `schemas/agent_contract.schema.json`.
2. **No invented capability.** Every `allowed_tools` entry must exist in the
   live argparse tree (`harness` command paths, discovered by walking
   `build_parser()`'s subparsers) or in the MCP server's registry. A contract
   naming `summon_gpu_cluster` or `mcp:fabricate_result` fails.
3. **No orphan schema.** A persisting output must name a file in `schemas/`; a
   non-persisting output must name `null`. The orchestrator's dispatch decision
   is the one non-persisting output, because there is no agent-plan artifact.
4. **Real artifact roles.** Read and write roles must come from the Harness's own
   vocabulary (`_ROLE_GATES` ∪ `BUNDLE_ALLOW_ROLES` ∪ generated-evidence roles).
5. **Control plane is off-limits.** No contract may write `run_manifest`,
   `competition_profile`, `artifact_dag` or `run_index`. That is precisely where a
   forged Gate PASS would live.
6. **Mandatory prohibition floor.** Derived from code, not from taste: each name
   in `profiles/capabilities.py:SAFE_INVARIANTS` maps to a required prohibition —
   `weaken_contest_safety`, `self_approve_human_checkpoint`,
   `self_validate_as_independent`, `promote_unfrozen_result`,
   `rewrite_frozen_artifact` — plus the three fabrication prohibitions
   (`forge_gate_status`, `forge_receipt_or_hash`, `forge_review_verdict`).
   Adding a safety invariant without a matching prohibition fails the check.
7. **Orchestrator holds no truth-mutating command.** The mutating set is derived
   from `TRUTH_MUTATING_LEAVES` (`init`, `execute`, `run`, `freeze`, `review`,
   `migrate`, `ai record|verify|confirm-none`, `authoring migrate`,
   `submit receipt`) plus any command **group** that can reach one — granting
   `ai` grants `ai record`. The orchestrator also writes nothing.
8. **Reviewer isolation.** The reviewer must act through `review` or
   `mcp:request_review`, may hold no other truth-mutating command, and may not
   write any author-plane role.
9. **Human-only declarations stay human.** No contract may hold
   `ai confirm-none`: SKILL.md principle 12 makes "no AI was used" a human
   declaration, and an agent holding it could launder an unrecorded model call.
10. **Unambiguous ownership.** Each artifact role has at most one writer; each
    stage has exactly one non-orchestrator owner; all eight stages are covered.
11. **References exist.** Every listed `references` path must be a file in this
    repository, so a contract cannot point at guidance that was deleted.
12. **The mutating list cannot rot.** If a mutating command is renamed or
    removed, `stale_truth_mutating_names()` fails the run rather than silently
    widening what an agent may hold.

## What a contract is not

**It is not enforcement at runtime.** A contract describes scope; the Harness
enforces outcomes. An agent that ignores `forbidden_actions` still cannot pass a
Gate, because no writable Gate field exists in v2 control state, and it still
cannot produce a claimable number, because `freeze` refuses without a receipt.

The enforcement gap this layer does **not** close: nothing here stops a host
from *running* a CLI command a contract forbids. Cross-checking an actual
transcript against the contract would be a runtime policy engine — a different
component, and one that should be measured before it is built.

```bash
harness agents check          # human-readable
harness agents check --json   # machine-readable; exit 1 on any violation
```

Output is scope, verdicts and the ground-truth counts it checked against. It
grants no authority, executes no model, and writes no project state.
