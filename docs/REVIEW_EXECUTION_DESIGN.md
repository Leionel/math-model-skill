# Review Execution Design (P0)

Date: 2026-08-20. Status: implemented; current regression evidence is recorded
in `WP3_TEST_REPORT.md`.
Scope: make review executable — `review declarative → review executable`.
Out of scope: P1 runtime robustness, P2 multi-agent platform, P3 skill
evaluation (see "Explicitly out of scope").

## 1. W2 review lifecycle

```
Draft (W1 outputs: paper/abstract/conclusion + contracts)
  ↓ harness review
[1] Deterministic QA            (existing run_deterministic_qa; must pass first)
[2] Review bundle               (allow-list materialized copy + bundle manifest)
[3] Reviewer execution          (L0 current agent / L1 fresh backend / L2 other model / L3 human)
[4] Review reports              (generated evidence under reports/review/)
[5] Deterministic validation    (schema, mode↔level, binding, freshness, verdict/finding)
[6] DAG registration            (role=review_report; one digest owner)
[7] Targeted revision           (author-side; operator-bounded)
[8] Re-check                    (harness review --recheck + W2 QA rerun)
  ↓
W2 adjudication (from real reports only) → human checkpoint → S1/F1
```

W2 never trusts a manifest review field; the v2 control plane stores none.
The gate, `harness status`, and `harness review` all read review truth through
one module: `scripts/qa/review_evidence.py`.

## 2. Semantic Critic vs Judge Lens

| | Semantic Critic | Judge Lens |
|---|---|---|
| Question | research correctness / semantic integrity | competition-judge reading quality |
| Reference | `references/review/semantic_critic_rubric.md` | `references/review/judge_lens.md` |
| Structural seed | — | deterministic `judge_scan` output inside the bundle |
| Output | findings (never a deterministic PASS) | issue-only findings; no scores, no award probabilities |
| Required | sprint+ | research+ |

Judge Lens extends the existing `judge_scan` structural scan (kept in place in
`check_paper_style.py`); it does not create a second judge framework. The two
perspectives stay separate; there is no blended composite score.

## 3. review_mode and independence_level

```
review_mode         self_critic | fresh_context | independent_model | human
independence_level  L0_same_context | L1_fresh_context | L2_independent_model | L3_human
```

The pair is validated one-to-one (`REVIEW_MODE_LEVEL`); a self_critic claiming
L1/L2 is a contract violation, and vice versa. Preset requirements:

- sprint: semantic critic required; L0 allowed.
- research: semantic + judge required; L1 preferred. A semantic L0 fallback is
  legal only with `degraded_independence: true` (visible in `harness status`).
- submission: research requirements plus at least one current review with
  independence_level ≥ L1; L0 cannot satisfy it.

No reviewer-count semantics; no review profile matrix; the v1
`reviewer.blind_reviewers` count check stays in the read-only v1 path.
The CLI implements backend execution for L0/L1. L2 is an external
independent-model contract and L3 is a manually routed human-report contract;
neither is a built-in provider/worker.

## 4. Fresh-context information boundary

`harness review` materializes an allow-listed bundle at
`reports/review/bundle/<runid>-<ts>/` containing only
problem snapshot, contracts, frozen results, evidence registry, paper plan,
paper/abstract/conclusion, presentation contract, writer package, rules
reference, and the judge-scan structural seed. `bundle_manifest.json` records
role / artifact_id / source_path / path / sha256 per member.

Denied inputs (writer reasoning, previous verdicts, revision negotiation,
session logs, unrelated drafts) are never copied, and validation fails any
L1+ report whose bundle contains a denied or unlisted role. The bundle is the
only reviewer input contract; there is no second input database. Backend
execution starts with this directory as its working directory, and the command
receipt binds that cwd plus the exact bundle input hash and report output hash.

This is a materialized information boundary, **not an OS sandbox**. A local
process with broader filesystem permissions could still attempt to read other
paths. The Harness detects protected author/control artifact mutation and
rejects a non-conforming report, but it cannot prove that an arbitrary command
never read outside the bundle. Therefore `L1_fresh_context` is valid only when
the operator/backend actually supplies a new context; submission-grade hard
isolation remains a future Worker Adapter responsibility.

## 5. Generated evidence ownership

- Reports live under `reports/review/<perspective>-<runid>-<ts>.json` and
  follow `schemas/review_report.schema.json` (the single schema; both
  perspectives share it).
- Validated reports are registered as DAG nodes (`role=review_report`,
  `lifecycle=mutable`, dependencies on the reviewed artifact ids). A
  receipt-produced report keeps the digest only in its command receipt and the
  DAG points to `digest_owner=command_receipt:<receipt_id>`; a manually routed
  report is hashed by the DAG. The manifest gains no fields; there is no
  second review ledger or reviewer state.
- Reviewer execution through a backend goes through `run_and_record.py
  --stage review`, so argv/exit code/timestamps are process-captured receipts.
  L0/L3 executions record mode and time in the report and do not fabricate
  receipts.
- Reviewers may only inspect, identify, explain, and require fixes. The
  orchestrator does not edit author artifacts. It snapshots author/control
  digests around a backend call and blocks the run if the backend mutates them;
  this is detection, not process-level write prevention.
- Backend output that fails its execution contract is moved to
  `reports/review/rejected/`. It remains diagnostic material but is not
  discoverable W2 evidence and cannot permanently outrank a later valid run.

Artifact coverage is deterministic, not left to reviewer discretion. A
Semantic Critic report must bind `model_contract`, `frozen_results`,
`evidence_registry`, and `paper|pdf`; a Judge Lens report must bind
`paper|pdf`, `abstract`, and `conclusion`. Other allow-listed artifacts such as
figures, tables, validation reports, and data contracts are optional inputs.

## 6. Review freshness

A report records the sha256 of each reviewed artifact at review time
(`reviewed_artifacts`). Freshness is recomputed from bytes: current file
digest ≠ recorded digest ⇒ stale ⇒ unusable for W2. Reports only reference
digests; the canonical digest owners (DAG / producer receipts) are not
duplicated. Reports are first filtered by current `run_id`; a foreign run
cannot satisfy or poison the current run. The newest non-superseded report per
perspective is selected by `reviewed_at`; stale history is preserved.

## 7. Revision loop

The current CLI executes **one review pass per invocation**. It does not own an
automatic revision loop. The reference policy asks the operator to cap work at
two passes, keep finding ids stable, stop when blocker/high findings do not
strictly decrease, and write a decision memo. Revision is author-side;
`harness review --recheck` validates already-routed evidence, while the full
W2 gate reruns deterministic QA. Per-finding QA subset selection is not
implemented. Frozen results/model-contract changes trigger upstream
invalidation and leave W2.

## 8. W2 adjudication

`evaluate_w2_review` (in `review_evidence.py`) recomputes, per required
perspective: report exists for this run → schema/mode/verdict contract holds →
bindings current → verdict pass → no open blocker/high/medium → (submission)
one current L1+ review.
Any missing/stale/conflicting evidence is an explicit W2 error. The W2 gate
calls this after deterministic QA; `harness status` projects the same summary
(severity counts, independence level, degraded flag, freshness, next finding,
next action).

## 9. Submission human boundary

Unchanged: submission never auto-freezes. `ready_to_freeze` → explicit human
authorization → final freeze. The review plane adds evidence; it does not add
an approval engine.

## 10. Explicitly out of scope (Future P1/P2/P3)

- P1: durable resume/retry, trajectory engine, context-map runtime, generic
  approval engine, automatic revision-loop/history/decision-memo controller.
- P2: full Worker Adapter, agent registry, orchestration graph, provider
  routing, OS/filesystem sandboxing, adversarial swarms. This round keeps exactly one seam:
  `harness review --backend-cmd` executed through the receipt runner.
- P3: with/without-skill benchmarks, skill optimization, skill registry.

## 11. Complexity deltas

canonical state +0 · schema +1 (review_report, shared by both perspectives) ·
profile dimension +0 · top-level gates +0 (still M1 P1 P2 W1 W2 S1) ·
CLI +1 (`harness review` only) · Root SKILL +~15 lines.

## 12. OSS mechanism cross-check

This design borrows mechanisms, not repository shells:

| Source file | Mechanism retained | Deliberately not copied |
|---|---|---|
| [nature-reviewer/SKILL.md](https://github.com/Yuan1z0825/nature-skills/blob/main/skills/nature-reviewer/SKILL.md) | same immutable packet, independent contexts, stable concern/evidence pointers | fixed three-reviewer topology and Nature-specific scoring axes |
| [mathodology award gates](https://github.com/sweetcornna/mathodology/blob/main/.claude/skills/mathodology-award-gates/SKILL.md) | structured findings, blocking gate, stable IDs, bounded revision policy | full nine-stage award workflow and three-judge aggregation |
| [nature-figure README](https://github.com/Yuan1z0825/nature-skills/blob/main/skills/nature-figure/README.md) and [MathModelAgent 6verity](https://github.com/jihe520/MathModelAgent/blob/main/skills/6verity/SKILL.md) | claim-driven figure contract, source-data mapping, rendered-output QA | fixed figure counts or automatic visual PASS from file existence |
| [backward-traceability](https://github.com/lingzhi227/agent-research-skills/blob/main/skills/backward-traceability/SKILL.md) | claim/number → evidence → artifact locator | a second traceability database parallel to the canonical DAG/registry |

The Review Plane therefore keeps two perspectives, not three blind judges;
uses issue evidence rather than aggregate scores; and treats figure/citation
guidance as references until deterministic checks can verify them.
