# Math Modeling Evidence Harness — Architecture Review & Workflow-Gap Analysis

verified_against: 2026-08-29@working-tree

> **Snapshot scope.** This is the pre-remediation architecture review. Use `HANDOFF_2026-08-28.md` for later implementation status; the gap verdicts below are preserved as review inputs, not rewritten as current-state claims.

- **Date:** 2026-08-28
- **Skills:** `system-modeler` + `risk-quality-reviewer` (via `explore` router), foundations `graphviz`
- **Scope:** Current-state architecture & design review; comparison against excellent comparable skills; gap analysis over the full mathematical-modeling workflow.
- **Evidence basis:** README/SKILL/agents; full file inventory; `references/router.md`; prior maintainer audits in `docs/`; verbatim comparables in `references/precedents/local-sources/upstream_refs/`; runtime code read with file:line citations.
- **Diagrams (on disk, DOT sources):** `system-context.dot`, `architecture-layers.dot`, `gate-chain.dot`, `gap-map.dot`

---

## 1. Architecture verdict (current state)

This is a **mature, integrity-first evidence harness**, not a modeling solver. Its core design is unusually disciplined and, in several dimensions, ahead of every comparable skill inspected.

**The distinctive architecture** (see `architecture-layers.dot`):

- **Separation of Harness repo vs competition project root.** The system (scripts/schemas/references/assets) never stores contest artifacts; everything writes to a separate project root. This is a hard, well-enforced boundary (`scripts/harness.py`, `project_layout.py`).
- **Three-layer ownership** with one digest owner per artifact:
  - *execution fact* = `command_receipt` (process-captured, immutable, SHA-256 of inputs hashed **before** spawn — `run_and_record.py:206-212`);
  - *projection* = `run_index` (append-only, never copies `exit_code`);
  - *control* = `run_manifest` (preset, roots, policy, human stages, `ai_usage_state`).
- **Non-bypassability by re-derivation, not storage.** v2 stores *no* gate status; every gate report is regenerated from receipts/hashes/DAG at check time (`check_gates.py:259-278`; `v2_gate_runtime.py:_v2_gate`). The gate chain `S0→M1→P1→P2→W1→W2→S1→F1` is ordered by fact-dependency (W1 needs P2's frozen artifact; S1 needs the submission preset set only at `init`).
- **Authoring plane vs machine projection.** Human `00_*.md` Markdown is the editable source; explicit `--compile` turns fenced-YAML into schema-validated IR; `.harness/views/*.md` are SHA-256-headered read-only projections that never pass a gate (`human_surface.py`, `prepare_project.py`).
- **Preset/capability system** with `SAFE_INVARIANTS` that cannot be disabled (`capabilities.py:11-17`, forced re-enabled at `:172-173`).
- **Progressive knowledge routing** via `references/router.md` (method/problem/failure cards, contracts, validation profiles, writing/figure/precedent refs) loaded one branch at a time.

**Honest caveat on the integrity model:** nothing is cryptographically signed; files are hand-editable. The guarantee is that gates *recompute everything at check time*. This is a deliberate, documented design choice, not an accident — but it is a real boundary worth stating.

**Complexity hotspots (confirmed in code):**
- `check_gates.py main()` ~1100 lines (229-1365), a god-function carrying both v2 dispatch and the entire legacy v1 checker.
- `v2_gate_runtime._v2_gate` ~460-line if/elif monolith (453-915).
- Duplicated v1/v2 writers (`run_and_record.py`, `freeze_submission.py` repeats F1 logic twice) and dual import blocks.
- Every `status`/`prepare` re-evaluates all six gates (heavy recomputation).

---

## 2. Comparison vs excellent comparable skills/harnesses

Comparables inspected (verbatim under `references/precedents/local-sources/upstream_refs/`): **MathModelAgent**, **math-modeling-skill** (jianmo/biancheng), **math-paper-cn**, **nature-figure**, **nature-polishing**, **nature-shared**, **nature-writing**, **_shared excellent-paper**.

**The "strength bar" the comparables set:**
1. **Stage-decomposed agent roles with explicit handoff artifacts** (JSON plans, task tables, fixed files) — MathModelAgent modeler→coder, math-modeling-skill 建模手/编程手.
2. **Deep, operational domain heuristics** — model decision trees + high-score combos, leakage/encoding/large-CSV coding protocols, a 9-point solver-robustness checklist, a semantically rich chart ontology with policy exceptions, Nature argument/paragraph patterns.
3. **Increasingly machine-verifiable figure QA** — nature-figure collision/alignment audits with blocking exit codes.
4. **Anti-fabrication ethics** — flag-don't-invent, provenance bundles, no-copy policies.

**What this harness adds beyond all of them (genuine strengths):**
- **End-to-end machine-enforced evidence gating across ALL stages** (schema contracts + exit codes + frozen results), not just figure audits or prose discipline.
- **Contest-compliance machinery** (CUMCM/MCM-ICM/APMCM profile verification, AI disclosure, submission packaging/hashing, F1 immutability) — no comparable has this.
- **A unified reproducibility chain** binding data→code→results→figures→paper under one CLI, vs conventions scattered across four separate skill families.
- Reviewer **independence levels** and a real **review plane**; `integrity_mode` tiering.

**What the comparables still do better (feeds the gap list below):** model→code handoff & coding protocols (MathModelAgent coder, mms-skill), solver-robustness checklist, rendered figure QA (nature-figure), evidence-allocation/result-interpretation discipline for writing (nature-shared), and role-based agent decomposition.

---

## 3. Gap analysis — full math-modeling workflow

Coverage verdict per stage (green=strong, amber=partial, red=gap). Evidence in parentheses. See `gap-map.dot`.

| # | Workflow stage | Verdict | What's missing |
|---|---|---|---|
| 1 | Problem understanding / decomposition / ambiguity | 🔴 weak | `ideation/problem_decomposer.py` exists but ENHANCEMENT_PROPOSAL 痛点2: "赛题拆解/算法发现偏弱（静态校验）". No active ≥2-interpretation ambiguity exploration like MathModelAgent. Contract has `assumption_forks` but it's declarative, not a workflow. |
| 2 | Literature / precedent research | 🟡 registered, not integrated | **Verified populated:** `cumcm/index.json` has 6 papers, `mcm-icm/index.json` 4, all SHA-256-verified with `extraction_status: extracted`, and `select_reference_cards.py` is unit-tested. **Gap:** selection is NOT a `harness` subcommand nor any gate step — it is manual-only, so a live contest team must remember to run it. Upstream freshness re-review (GAP-16) still open. |
| 3 | Data / EDA / data contract | 🟢 covered | `auto_eda.py`, `data_contract` schema. Lighter operational protocols than MathModelAgent coder (encoding/leakage/large-CSV) but structurally sound. |
| 4 | Model selection & design | 🟢 strong | Claimed strength; METAMATH: "建模底座明显强于所审上游". 17 method + 11 problem + 16 failure cards, typed `model_contract`. |
| 5 | Model implementation / coding / solving | 🟡 projection exists; protocols + validation missing | **Verified wired:** `harness solve --tasks` projects `model_contract`→per-model implementation tasks (equations/constraints/typed params/test-obligation oracles/smoke acceptance/steps/escalation) via `views/implementation_tasks.py` (`harness.py:627,635,1076`). **Residual gaps:** no *operational* coding/solving protocols (leakage prevention, encoding fallbacks, solver-robustness checklist) that comparables inject; thin `scaffold/`; unvalidated on a real problem. METAMATH "模型合同未投影成编码任务" is stale. |
| 6 | Validation / sensitivity / robustness | 🟡 partial infra, weak execution | Strong artifacts (`validation_obligations`, profiles, `sensitivity_experiment`, `oos_artifact`, `extremum_certificate`, `failure_evidence`) **but** GAP-08 "选择性重跑/敏感性编排缺失" and **no math executors** (GAP-07; STATUS M0–M4: algebra/unit/index/dimension/SymPy equivalence — scheduled only). |
| 7 | Results analysis / interpretation | 🟡 partial | `derive_results` exists, but no evidence-allocation/result-interpretation discipline comparable to nature-shared's 8-class allocation table. |
| 8 | Writing / paper composition | 🟡 spine exists; needs validation + allocation discipline | **Verified wired:** `harness paper write <section>` compiles `paper_plan`→`WRITING_SPINE.md` (thesis, ordered sections, argument units, cross-question handoffs, drafting order, abstract budget) + per-section Writer Briefs (claims, frozen values, established facts, must-not-claim) via `views/writing_spine.py` (`harness.py:45,736-750`). **Residual gaps:** not validated on a real paper (METAMATH §9); no nature-shared-style result-allocation discipline; ENHANCEMENT_PROPOSAL 痛点4 (空洞化/符号漂移) unaddressed. METAMATH "未投影成章节级写作任务" is stale. |
| 9 | Figures / visualization | 🟡 strong routing, weak rendered QA | Strong contract/routing (`figure_contract`, `tool_router`, `pptx_router`, drawio, illustration). But METAMATH §3.2: no Figure Reference Card visual library; no rendered collision/alignment QA (nature-figure has it); GAP-05 (`\includegraphics` binding) & GAP-13 (caption compare). |
| 10 | Review / QA | 🟢 strong | Review plane, semantic critic, judge lens, independence levels, `--fresh`. Minor: METAMATH §3.3 "独立性不等于可观察性" (missing `evidence_scope` observability). |
| 11 | Compliance / packaging / submission | 🟢 strong & distinctive | Contest safety, profile verification, AI disclosure tri-state, submission freeze/F1. Leads all comparables. |
| 12 | Iteration / revision / orchestration | 🟡 partial | `reflexion/` exists; selective-rerun orchestration missing; revision loops are manual. |

### Cross-cutting META gaps (the headline findings)

- **A. Capability benchmark NEVER RUN — the single biggest honest gap.** `CAPABILITY_BENCHMARK_PLAN.md` is explicit: until 4 task families × A0/A1/A2 with pre-registered budgets exist, report `NOT RUN`. BASELINE/VNEXT: "No external paper project, full computation, independent validation, PDF review, competition submission, or F1 freeze was run." **All current evidence is regression/schema correctness, not real-contest capability.** Regression tests ≠ generalization.
- **B. Cognitive load / "合同丰富，交接贫弱".** ~30 schemas, 15+ manual JSON contracts; ENHANCEMENT_PROPOSAL 痛点1 "为了填契约而填契约". The harness optimizes integrity at the cost of authoring ergonomics and inter-stage handoff.
- **C. Broken welds — tools without consumers.** CAPABILITY_GAP_AUDIT thesis: "检查器之间的焊点普遍缺失——工具建好了没有消费者". `run_index` had zero consumers (GAP-03); free text lacked receipt constraint (GAP-01, since closed); 123 files uncommitted (GAP-15).
- **D. Math executors absent.** No algebra/unit/index/dimension symbolic verification (GAP-07; STATUS M0–M4). High-risk math correctness still depends on independent human W2 review — a designed boundary, but a coverage hole vs "full workflow".
- **E. State-ownership multi-write + code debt.** STATE_SIMPLIFICATION_AUDIT: competition profile dual-source with incompatible ontology, command state triple-write, 72 theoretical profile combos. Plus the god-functions/v1-v2 duplication in §1. Regression baseline not green (2 errors; full-discovery state "unknown, not pass").
- **F. No distributable packaging.** README admits no wheel; editable checkout only. Blocks reuse/distribution.

---

## 4. Prioritized remediation direction

Ordered by blast radius × evidence:

1. **Run the capability benchmark (Meta-A).** Even 1–2 of the 12 planned runs on real past problems converts "NOT RUN" into evidence and de-risks every other claim. This is the highest-leverage action.
2. **Enrich + validate the model→code handoff (#5).** The `solve --tasks` projection exists; add operational coding/solving protocols (leakage/encoding/solver-robustness) borrowed from MathModelAgent coder / mms-skill, deepen `scaffold/`, and validate on a real problem. Also resolve the M1 "已验证实现映射" stage-inversion.
3. **Enrich + validate the writing handoff (#8).** The writing spine + section briefs exist; add result-allocation discipline (nature-shared), then validate on a real paper to close 空洞化/符号漂移.
4. **Integrate precedent selection into the workflow (#2).** The index is already populated and the selector tested — expose `select_reference_cards` as a `harness` subcommand / research-stage step so it is consumed during a live project, and do the upstream freshness re-review (GAP-16).
5. **Add selective-rerun/sensitivity orchestration (#6, GAP-08)** and begin the math executors (Meta-D), starting with units/dimension (cheapest, highest catch-rate).
6. **Pay down state/code debt (Meta-E):** collapse command-state triple-write, reconcile profile dual-source, split `check_gates.py`/`_v2_gate` monoliths, remove v1 duplication once migration is complete.
7. **Add rendered figure QA + Figure Reference Cards (#9).**
8. **Reduce cognitive load (Meta-B):** template/derive boilerplate contracts; only surface what each gate actually consumes.

---

## 5. Caveats & unknowns

- The DOT diagrams are pre-remediation review snapshots, evidence-backed to the files cited at review time. They are not the post-remediation source of truth; render state remains unverified (Graphviz was not installed during the review).
- "Comparables do X better" is based on the stored upstream_refs snapshots, which may lag their live upstreams (freshness re-review itself is an open gap).
- Gap verdicts for #6/#7/#8/#9 are "partial", not "absent" — infrastructure exists; the shortfall is execution/orchestration/handoff, which is what the maintainer audits also conclude.
- This review did not re-run the test suite; the "baseline not green (2 errors)" figure is quoted from STATE_SIMPLIFICATION_AUDIT and should be re-verified before acting on Meta-E.
- **Doc/state drift found during verification (3 instances):** METAMATH_HARNESS_LEARNING_ANALYSIS (dated 2026-08-28) claims the precedent indexes are empty, that `model_contract` is not projected to coding tasks, and that `paper_plan` is not projected to section writing tasks. All three are contradicted by current code: the indexes are populated & hash-verified, `harness solve --tasks` (`views/implementation_tasks.py`) and `harness paper write` (`views/writing_spine.py`) both exist and are wired in `harness.py`. A "latest" design doc does not match the tree — a clear living-architecture / doc-reconciliation gap (see recommendation R9).
