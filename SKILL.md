---
name: math-modeling-skill-sion
description: 面向 CUMCM、MCM/ICM、APMCM 等数学建模竞赛的证据与合规 Harness。用于新建或迁移比赛项目、题意与模型选型、数据/验证合同、真实运行、结果冻结、证据追溯、技术写作、确定性 QA、提交检查与不可变交付；普通数学题且不涉及竞赛交付链时不要使用。
---

# Math Modeling Evidence Harness

## Trigger and scope

Use this skill when a user asks to build, audit, migrate, run, validate, write,
or submit a mathematical-modeling competition project. Start from the project
root and use the thin `harness` CLI; keep the paper project separate from the
Harness repository.

Do not use it for a one-off textbook solution, an informal plot, or a generic
Python experiment with no evidence or competition-delivery obligations.

## Core principles

1. Treat `competition_profile.json` as the only competition-rules contract.
2. Treat receipts as execution facts, the run index as a rebuildable
   projection, and the normalized manifest as the control plane.
3. Resolve exactly one preset: `sprint`, `research`, or `submission`.
   Overrides are allow-listed capability adjustments, not new presets.
4. Keep Contest Safety, independent validation, human checkpoints, result
   freeze, and submission immutability non-bypassable.
5. Never hand-write gate PASS values, receipts, hashes, freshness, claim
   inventories, or validation verdicts. A reviewer/human may create a new
   schema-valid review report; operators must not rewrite an existing report
   to manufacture PASS.
6. Preserve failed runs and failure evidence. A failed run is evidence, not a
   reason to delete a counterexample.
7. Hashes prove byte identity only. They do not prove leakage safety, objective
   semantics, mathematical correctness, units, statistics, or figure claims.
8. Use the order `semantic validation -> accept -> freeze -> hash binding`.
9. Stop on missing inputs, `FAIL`, `ERROR`, unresolved official rules, or a
   pending human decision. Do not promote a plan, demo, or regression as a
   benchmark result.

## Normal path

```text
harness init -> S0 -> M1 -> P1 -> P2 -> W1 -> W2 -> S1 -> F1
```

Only advance after the current Gate has a factual report and its required
human checkpoint. A later status value in a stale manifest cannot override an
earlier factual failure.

### S0 — scope and safety

Resolve a standalone competition-profile seed and inspect the current rule
snapshot, endpoints, AI policy, page scope, and human checks. A maintainer
seed is `status: seed` or `unresolved`; it is not an official verified rule.
Keep official rules separate from a stricter local policy.

Minimum I/O: project root, `competition_profile.json`, `run_manifest.json`,
`artifact_dag.json`, and `run_index.json`.

### M1 — model and validation contract

Record the problem mechanism, data boundary, at least two candidate models (or
a documented reason for an exception), assumptions, typed parameter
provenance, formulas, implementation map, and falsifiable validation duties.
Use `assumption_forks` for ambiguous question semantics and declare objective
and risk semantics before coding.

Minimum I/O: ready `model_contract.json`, evidence registry, current profile,
M1 human checkpoint, and a current DAG. In `research`/`submission`, formal
literature linkage and scope checks are required.

### P1 — smoke execution

Run the smallest real process through `run_and_record.py`. The receipt must be
process-captured, tied to this run, and successful; copied command text or an
exit code in a projection is not a receipt.

Minimum I/O: one successful smoke receipt and the v2 run-index projection.

### P2 — full run, independent validation, and result freeze

Run the selected full computation and an independent evaluator. Recompute each
declared obligation, including sensitivity/OOS/failure evidence when triggered.
Freeze the result only after semantic validation. Only `status: frozen`,
`validation_verdict: PASS`, and `claimable: true` results may enter evidence.

Minimum I/O: exactly one selected full receipt, one successful freeze receipt,
one frozen-results artifact, required input/output bindings, and P2 human
checkpoint.

### W1 — evidence and paper plan

Build one incremental evidence registry and a paper plan mapping each claim to
verified evidence. Keep result definitions, population, units, and rounding
consistent. Do not fill missing evidence with prose.

Minimum I/O: ready `paper_plan.json`, verified evidence references, current
frozen result, and W1 human checkpoint.

### W2 — deterministic content QA

Generate the writer package and draft, then run deterministic QA, mathematical
semantic checks, consistency checks, template/build checks, PDF checks, and
visual review required by the resolved capabilities. Semantic Critic and
human review are separate from mechanical QA.

Review is executable, not declarative: run `harness review` after the draft.
It runs deterministic QA, materializes the allow-listed review bundle, and
routes the required perspectives (sprint: semantic critic; research:
semantic + judge; submission: research set plus one review with
independence_level >= L1). Reports land under `reports/review/` as generated
evidence; W2 recomputes verdict, artifact binding, and freshness from those
reports — never from manifest self-reports. Open blocker/high/medium findings
block W2 unless a medium finding is explicitly accepted with justification;
a paper change makes the old review stale. `--fresh` binds the bundle, child
working directory, receipt, and report, but is not an OS sandbox: submission
still needs a genuinely separate context/model. Load the review references
via the router before acting as a reviewer.

Minimum I/O: paper source/draft, abstract, conclusion, deterministic QA report,
current review reports, current evidence chain, and W2 human checkpoint.
`research` requires the full evidence chain; `submission` additionally
requires strict math/editorial and current template/bibliography evidence.

### S1 — current submission checks

Check the current verified profile, page scope, support package, AI disclosure,
required manual checks, and final PDF. A seed profile cannot pass submission.
The Harness never uploads on a user's behalf.

Minimum I/O: verified profile, current PDF/support/disclosure artifacts, S1
report, and S1 human checkpoint.

### F1 — immutable delivery

Freeze the submission package and bind the final source/PDF/package identities
in the submission manifest. Any changed immutable input requires a new version,
new digest binding, downstream invalidation, and rerun of affected Gates.

Minimum I/O: immutable submission manifest and receipt. F1 is not a mutable
`run_manifest.gates` flag.

## Presets

| Preset | Use | Integrity posture |
|---|---|---|
| `sprint` | fast exploratory/model smoke work | identity boundaries; explicit result freeze |
| `research` | default formal research run | selected-run lineage, independent validation, selective critical hashes |
| `submission` | current contest delivery | strict math/editorial checks and final-chain immutability |

Never disable Contest Safety, human checkpoints, independent validation,
result freeze, or submission immutability with an override.

## CLI quick start

```powershell
python scripts/harness.py init --project C:\work\q1 --competition cumcm --preset research
python scripts/harness.py status --project C:\work\q1
python scripts/harness.py check M1 --project C:\work\q1 --profile research --json
python scripts/harness.py run --project C:\work\q1 --stage smoke -- python model.py
python scripts/harness.py review --project C:\work\q1 --json
python scripts/harness.py review --project C:\work\q1 --recheck --json
python scripts/harness.py validate --project C:\work\q1 --strict
python scripts/harness.py freeze --project C:\work\q1 --kind results --source results.json --output frozen_results.json --run-id run-1 --model-contract model_contract.json --code model.py --validation validation.json
python scripts/harness.py profile --project C:\work\q1 --json
python scripts/harness.py doctor --project C:\work\q1 --json
python scripts/harness.py migrate --project C:\work\legacy --json
```

Use `--json` for agent consumption. Underlying checkers retain their stdout,
stderr, and exit code. Use their script-level flags only for debugging; the
normal path should require one project root plus stage/preset.

## Progressive disclosure

Read only the relevant router entry before a specialized task:

- [reference router](references/router.md) for contracts, Gate policy,
  validation, writing, figures, literature, and submission details;
- [artifact contracts](references/contracts/artifact_contracts.md) for
  ownership, result semantics, and generated artifact boundaries;
- [Gate policy](references/workflow/gate_policy.md) for Gate-specific checks.

Detailed statistics, optimization, prediction, mechanism, writing, figure,
citation, template, and contest-submission rules stay in the existing
one-level routed references. Do not load all cards into the active context.

## Migration and safety reminders

Run `harness migrate --project <legacy-root>` to a separate `migration_v2/`
directory. Read `migrated`, `inferred`, `unresolved`, `deprecated`, and
`manual_review_required` before promotion. Migration never rewrites historical
frozen evidence and never upgrades a legacy command declaration to a receipt.

Status is read-only and a v1 status is explicitly deprecated. A DAG freshness
projection is evidence for the next action, not permission to rewrite the DAG.
Regression tests prove stated code paths; they are not capability benchmarks.

For release work, report commands actually run, exit codes, artifact paths,
uncovered risks, and whether any real benchmark was run. Quarantine previous
national-contest papers under `references/precedents/cumcm/` and MCM/ICM papers
under `references/precedents/mcm-icm/`, register their provenance in the local
indexes, and extract reusable mechanisms into `pattern-cards/` before Writer
use. Raw precedent papers are not current evidence and must not silently enter
a new project.
