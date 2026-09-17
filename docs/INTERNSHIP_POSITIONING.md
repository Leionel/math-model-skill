# Internship positioning

Written so that every sentence can be pointed at code or a test. If a claim is
not backed today, it says so here instead of in a footnote.

## One line

A deterministic control plane that makes multi-agent output verifiable: gates
that recompute, receipts for real processes, hash-driven staleness across an
artifact DAG, an evidence-bound review plane, and an MCP interface plus a
read-only console on top.

## Three core contributions

### 1. Facts are never granted by an agent, a prompt, or a view

- v2 control state **forbids** a `gates` key (`profiles/normalization.py:313`,
  `qa/validate_contracts.py:202`), so there is no field to hand-write a PASS
  into; every verdict is recomputed from files at read time
  (`v2_gate_runtime.py:951`).
- `frozen_results.claimable` is derived from `validation_verdict == "PASS"` and
  supplying it explicitly is an error (`freeze_results.py:101`), and a v2 freeze
  without a selected successful full receipt raises (`freeze_results.py:185`).
- The console refuses all `POST` traffic with the producer command to use
  instead (`dashboard/server.py`), and a test proves serving cannot mutate the
  project tree.

Measured, not asserted: `evaluation/redteam.py` runs 12 scripted-adversary
scenarios and reports per-class blocked counts.

### 2. Provenance and freshness are one recomputable graph

- Receipts capture argv, cwd, exit code, timestamps and — depending on preset —
  input/output digests, hashing inputs *before* the child starts
  (`run_and_record.py:214`).
- `review_freshness` rehashes every bound artifact and cross-checks the DAG
  node digest (`qa/review_evidence.py:412`); W2 refuses a stale review, and L1+
  reports additionally fail closed if the report file itself drifted from its
  receipt (`review_evidence.py:716`).
- One real defect found and fixed while building this: a drifted artifact whose
  lifecycle is `mutable` but which declares a digest was silently absent from
  the selective-rerun seed set, so the plan reported "no change" while its
  dependents were already stale (`qa/plan_selective_rerun.py:135`). Review
  reports are now registered as `immutable` generated evidence rather than
  `mutable` (`qa/run_review.py:750`). Three regression tests.

### 3. The agent layer is machine-checked, and its limits are published

- Seven role contracts in `agents/*/agent.yaml` against a JSON Schema, verified
  by `harness agents check` — which discovers the command surface from the live
  argparse tree and the tool surface from the live MCP registry, so a contract
  cannot name a capability that was removed. 24 tests assert the rejections
  (invented tool, control-plane write, dropped prohibition, orchestrator holding
  a mutating command, reviewer writing the author plane, duplicate stage or
  artifact ownership, `ai confirm-none` as an agent tool).
- 13 read-only MCP tools + 1 opt-in mutating tool behind
  `MATH_HARNESS_ALLOW_REVIEW_TOOL`. The reviewer command is configured
  server-side; an agent-supplied argv would be RCE wearing a tool name.
- **`register_artifact` deliberately does not exist.** Minting ids, hashes and
  timestamps on request is a receipt-forgery endpoint. `docs/MCP_ARCHITECTURE.md`
  states this and lists the producer commands that actually create provenance.
- Two gaps are recorded as `expected: allowed` scenarios in the suite, so the
  eval fails if the README ever overclaims: receipt `argv` is not attested, and a
  `human_checkpoints` entry carries no identity.

## Agent engineering skills mapped

| Skill | Where it shows |
| --- | --- |
| Multi-agent orchestration | Orchestrator contract with no write authority; one owner per stage; dispatch bounded by the recomputed first blocker |
| Tool design and agent-computer interface | `scripts/mcp_server.py` + `scripts/mcp_tools/`; per-call `project_root`, fail-closed allowlist, verdict passthrough, output redaction |
| Context management | Stage-local context plan (`harness context`), allow-listed review bundle with a deny list, progressive disclosure through `references/router.md`, ruleset fingerprint as a cache hint only |
| Grounding and verification | Claim → evidence → claimable frozen result → selected receipt → code/input digests |
| Failure recovery | Failed runs preserved as evidence (`SKILL.md` principle 6); rerun planning that names affected artifacts and pending Gates; quarantined rejected review outputs |
| Human-in-the-loop | Three-state AI declaration, pending→verified review records, per-Gate checkpoints |
| Evaluation | Red-team reliability suite with honest gap accounting; pre-registered A/B/C ablation that reports `NOT_RUN` |
| Architecture boundaries | Contract layer vs deterministic plane; the repo's own "no new Gate or agent role to look complete" guardrail |

## Reliability mechanisms

Gate recomputation on read · no writable Gate field · immutable receipts that
refuse overwrite · single digest owner per artifact · hash-driven freshness with
transitive staleness · semantic validation before accept before freeze ·
evidence scope that cannot self-upgrade beyond bound artifacts · independence
levels bound by the orchestrator · preset capability floors with five
non-bypassable safety invariants · submission guard that re-verifies every final
artifact hash · redaction on every MCP response.

## Evaluation design

Reliability is measured as a **property of the harness under attack**, which is
what can be measured honestly without burning model budget: scripted adversaries,
deterministic verdicts, runs in CI with no API key. Capability ablation
(A single-prompt / B multi-agent / C multi-agent + harness) is specified,
budgeted and metric-frozen in `evaluation/PREREGISTRATION.md`, and
`evaluation/ablation.py` returns `NOT_RUN` until three conditions are executed
against four tasks at three repeats each.

The intended conclusion is not "multi-agent wins". It is that role decomposition
buys capability and the deterministic layer buys auditability, and only the
second one is what makes an agent system deployable.

## Difference from a typical multi-agent demo

| Typical demo | Here |
| --- | --- |
| Agents negotiate a verdict | A verdict is recomputed from files; agents propose, code adjudicates |
| "Passed" is a string in memory | v2 has no field that could hold it |
| Tool list is documentation | Tool names are validated against the live CLI and MCP registries |
| Metrics are self-reported by the model | Metrics are exit codes under scripted attacks |
| Green tests imply capability | 729 tests are stated as code-path evidence; benchmark says `NOT RUN` |
| Everything is allowed by default | Roots, mutating tools and AI backends are denied unless configured |

## Positions this is aimed at

Agent Engineer Intern · Applied AI Intern · LLM Application Engineer ·
AI Platform / Agent Platform Intern.

The transferable claim is domain-independent: the same Gate/receipt/DAG/
freshness/review machinery governs any long-running agent workflow that produces
artifacts someone must trust — research pipelines, data analysis, compliance
document generation.

## Resume bullets

Use only the wording the repository can support.

- Designed and shipped a deterministic control plane for multi-agent workflows:
  6 recomputed Gates over 8 stages across ~36k LOC of Python, where control state
  structurally cannot store an agent-authored PASS.
- Built an artifact DAG with hash-driven freshness and process-captured
  execution receipts, so an edited upstream silently invalidates downstream
  review and a result with no receipt cannot become claimable.
- Added a machine-checked agent contract layer (7 roles, JSON Schema + validator)
  that rejects any contract naming a tool, artifact role, schema or Gate absent
  from the live CLI/MCP surface — 24 regression tests.
- Implemented an MCP access layer (13 read-only tools, fail-closed root
  allowlist, one env-gated mutating tool) and a read-only observability console
  sharing the same tool calls; the console refuses all writes by design.
- Wrote a red-team reliability evaluation (12 adversarial scenarios, 9 classes)
  that reports both what it blocks and the two boundaries it does not, and
  pre-registered an A/B/C harness-ablation study that remains honestly `NOT_RUN`.

## What is not done

Say these if asked, not after being caught:

- The A/B/C ablation has not been run; no capability number exists.
- No runtime policy engine enforces a contract against a live transcript; the
  contract layer checks scope, the Gate layer enforces outcomes.
- Reviewer independence is bound by configuration and honest operation, not by
  an OS sandbox; L2/L3 have no distinct execution path.
- Receipts and human checkpoints have no external trust anchor, so both are
  forgeable by anyone who can write project files — recorded as eval scenarios.
- The three extra tasks required by the ablation budget do not exist yet.
