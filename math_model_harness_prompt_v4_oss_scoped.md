# Math Modeling Harness — OSS-Grounded Review Execution Prompt v4

你现在继续处理：

Repository:
https://github.com/Leionel/math-model-skill

Current branch:
agent/math-modeling-harness

注意：当前工作区已经完成一轮较大的“架构收敛式重构”，但尚未 commit / push。

本 Prompt 基于当前未提交的 Manifest v2 工作区继续修改。

不要：

- 回退 Manifest v2；
- 覆盖当前未提交重构；
- 重新设计整个 Harness；
- 为了参考其他开源项目而引入新的通用 Agent Framework；
- 一次性实现本 Prompt 中列为“Future / Follow-up”的能力；
- commit；
- push。

============================================================
0. 当前已经完成的基础
============================================================

当前未提交工作区已经完成：

- Manifest v2：
  - profile
  - execution fact
  - artifact projection
  - control decision
  已明确单一 ownership。

- 用户运行模式已收敛为：

    sprint
    research
    submission

- Gate 已改为依据：

    real command receipt
    artifact bytes
    artifact DAG freshness
    human checkpoint

  重算真实状态，不再信任 manifest 自报成功。

- Hash / Integrity Policy 已完成：

    result freeze
    submission freeze
    canonical digest owner
    receipt / DAG tamper detection
    final PDF drift detection

- 已建立统一 CLI：

    harness init
    harness status
    harness check
    harness run
    harness validate
    harness freeze
    harness profile
    harness doctor
    harness migrate

- SKILL.md 已从约 307 行降至约 188 行。
- README 已从约 555 行降至约 210 行。
- 国赛 / 美赛优秀论文预留区已明确：

    references/precedents/cumcm/
    references/precedents/mcm-icm/

- Writer 默认只加载抽取后的 pattern cards，
  不把往届论文作为当前 evidence。

- battle/ 不允许修改。

当前测试基线：

    full regression: 352/352
    focused rerun: 47/47
    schemas: 29/29 parse
    Skill Creator: valid
    git diff --check: pass

当前尚未完成：

- 四类真实赛题 A0/A1/A2 capability benchmark
- GitHub Actions online run
- standalone wheel resource packaging

本轮只做：

    P0 — Review Execution Plane

不要把后续 P1/P2/P3 也一起实现。

============================================================
1. 本轮唯一主目标
============================================================

当前 Harness 最大缺口不是模型数量、Skill 数量或 checker 数量。

而是：

    Reviewer / Semantic Critic / Judge Scan
    已存在于 schema / references / Gate 条件中，

但用户运行 Harness 时：

    Reviewer 并没有作为一个明确、可执行、可观察的阶段真正“出现”。

当前问题可以概括为：

    review declarative
    ≠
    review executable

本轮目标：

    Make Review Executable.

即：

    Draft
      ↓
    Deterministic QA
      ↓
    Semantic Critic
      ↓
    Judge Lens
      ↓
    Findings
      ↓
    Targeted Revision
      ↓
    Re-check
      ↓
    W2 PASS

并且用户必须能在：

    harness review
    harness status

中明确看到：

    reviewer 是否执行
    review 当前状态
    unresolved blocker/high
    review 是否 stale
    下一步要修什么

============================================================
2. 本轮参考的 Open-Source 机制
============================================================

本轮参考以下项目，但只借机制。

------------------------------------------------------------
2.1 MetaMath Harness
------------------------------------------------------------

https://github.com/LKQ667/metamath-harness

借：

- low-friction invocation
- preflight
- user-authority mindset
- review UX

不借：

- vendor lock-in
- fixed reviewer count
- fixed paper-length/image-count style
- one-click all-auto final submission

------------------------------------------------------------
2.2 Anthropic Skills / Agent Skills
------------------------------------------------------------

https://github.com/anthropics/skills
https://agentskills.io/specification

借：

- SKILL.md 只做 workflow / routing
- scripts 做 deterministic / repetitive work
- references 按需加载
- assets 独立
- progressive disclosure

本项目继续坚持：

    Root SKILL
        = stage / risk / routing

而不是：

    Root SKILL
        = 所有 Review / Agent / Runtime / Policy 实现细节

本轮禁止因为 Review 增加而重新膨胀 Root SKILL。

------------------------------------------------------------
2.3 Superpowers
------------------------------------------------------------

https://github.com/obra/superpowers

借：

- spec-compliance review 与 quality review 分层
- evidence over claims
- skill behavior should be testable
- review should block on real issues

映射到本项目：

    Semantic Critic
        = research / semantic integrity review

    Judge Lens
        = competition judge / reading-quality review

不要把两个 Reviewer 合并成一个模糊“综合评分”。

------------------------------------------------------------
2.4 Skill Creator / SkillOpt / SkillBenchmark
------------------------------------------------------------

参考：

https://github.com/anthropics/skills
https://github.com/microsoft/SkillOpt
https://github.com/TiesPetersen/SkillBenchmark

本轮只借：

    changes should be behavior-tested

因此：

    Review Execution Plane
    必须由 real E2E 证明 reviewer actually executes。

不要只新增 schema / status 字段。

以下能力属于未来 P3，
本轮不实施：

- skill self-evolution
- held-out skill optimization
- automatic skill mutation
- with-skill / without-skill benchmark framework

------------------------------------------------------------
2.5 LangGraph / Inspect AI
------------------------------------------------------------

参考：

https://github.com/langchain-ai/langgraph
https://github.com/UKGovernmentBEIS/inspect_ai

本轮只借两个原则：

1.

    execution state
    应由 durable artifact / receipt / report 支撑，

    不依赖 Agent 自报。

2.

    human / semantic judgment
    与 deterministic PASS/FAIL
    必须分开。

以下属于 Future P1，
本轮不要实现：

- generic durable workflow engine
- generic retry engine
- generic approval engine
- checkpoint scheduler
- time-travel state machine

------------------------------------------------------------
2.6 OpenHands / Microsoft Agent Framework
------------------------------------------------------------

参考：

https://github.com/OpenHands/OpenHands
https://github.com/microsoft/agent-framework

只借：

    runtime/backend 可替换

以及：

    Multi-Agent is an optional execution topology,
    not a semantic requirement.

本轮可以为 fresh-context review
保留最小 backend seam，

但禁止实现完整：

- Worker SDK
- Agent Registry
- orchestration graph
- distributed agent runtime
- general plugin system

============================================================
3. 最重要的架构原则
============================================================

本轮必须遵循：

    Many possible workers
    One control plane
    One artifact graph
    One evidence truth
    One gate engine

Reviewer 可以由：

- current agent
- fresh-context subagent
- another model
- human

执行。

但是：

    reviewer role
    ≠
    canonical state owner

Reviewer 不得：

- 直接修改 Manifest truth
- 直接 PASS Gate
- 直接修改 frozen results
- 直接修改作者论文并自己验收
- 创建第二套 review registry
- 创建第二套 artifact DAG
- 创建自己的 evidence truth

============================================================
4. 本轮 Scope Boundary
============================================================

本轮必须实现：

P0-A
    harness review

P0-B
    Semantic Critic execution

P0-C
    Judge Lens execution

P0-D
    fresh-context review semantics

P0-E
    review report as generated evidence

P0-F
    review freshness

P0-G
    review visibility in harness status

P0-H
    bounded revision loop integration

P0-I
    W2 gate reads actual review evidence

P0-J
    Review E2E + regression tests

本轮明确不实现：

P1:
    generic resume / retry framework
    trajectory engine
    context-map runtime
    generic approval engine
    clean-process execution overhaul

P2:
    full Worker Adapter
    general multi-agent orchestration
    candidate-generation agents
    adversarial review swarm
    provider capability router

P3:
    skill benchmark
    skill optimization
    SkillOpt-style evolution
    skill registry
    source-grounded auto-skill generation

如果实现过程中发现未来能力确实必要：

    document it

不要顺手实现。

============================================================
5. Typed Invocation：只做 Review 所需最小增量
============================================================

当前 CLI 已经统一。

新增：

    harness review

建议支持：

    harness review
    harness review --json
    harness review --semantic
    harness review --judge
    harness review --fresh
    harness review --recheck

具体参数按现有 CLI 风格最小化。

不要增加：

    harness reviewer
    harness critic
    harness judge
    harness blind-review
    harness review-manager

这种 CLI surface explosion。

------------------------------------------------------------
5.1 Default Behavior
------------------------------------------------------------

默认：

    harness review

根据当前 profile 推导 required review perspectives。

sprint：

    deterministic QA
    + semantic critic

research：

    deterministic QA
    + semantic critic
    + judge lens

submission：

    deterministic QA
    + semantic critic
    + judge lens
    + at least one review with independence_level >= L1_fresh_context

不要恢复：

    3 blind reviewers

作为默认要求。

============================================================
6. Reviewer Independence
============================================================

Reviewer 独立性不要按：

    reviewer_count

定义。

必须区分：

    review_mode
    independence_level

------------------------------------------------------------
6.1 review_mode
------------------------------------------------------------

建议：

    self_critic
    fresh_context
    independent_model
    human

------------------------------------------------------------
6.2 independence_level
------------------------------------------------------------

建议：

    L0_same_context
    L1_fresh_context
    L2_independent_model
    L3_human

定义：

L0_same_context

    当前 Writer / current Agent
    在相同上下文中自审。

L1_fresh_context

    新上下文；
    只读取正式 review bundle；
    不读取 Writer reasoning / previous verdict / revision discussion。

L2_independent_model

    不同 model / reviewer runtime；
    从正式 artifact 独立审阅。

L3_human

    真人审阅。

------------------------------------------------------------
6.3 Profile Requirement
------------------------------------------------------------

sprint：

    L0 allowed

research：

    L1 preferred

若当前 runtime 无法提供 fresh context：

    可以 L0 fallback

但必须：

    显示 degraded independence

不得把：

    self_critic

伪装成：

    fresh_context

submission：

    至少一个 review
    independence_level >= L1

============================================================
7. Fresh Review Information Boundary
============================================================

Fresh review 必须有真实 information boundary。

不能只 prompt：

    “请假装第一次看到。”

Fresh reviewer 默认：

ALLOW:

- problem snapshot
- relevant competition rules
- model contract
- relevant data/model semantic contracts
- frozen results
- evidence registry / verified evidence
- current manuscript / PDF
- necessary figure/table artifacts

DENY BY DEFAULT:

- Writer private reasoning
- old reviewer reasoning
- previous semantic verdict
- previous judge verdict
- revision negotiation
- unrelated drafts
- session logs
- hidden chain-of-thought

Review report 必须能说明：

    reviewed_artifacts
    reviewed_artifact_ids
    review_mode
    independence_level

无需建立复杂 input database。

最小 review bundle manifest 即可，
如果现有 artifact ref 能表达，
优先复用。

============================================================
8. Semantic Critic
============================================================

Semantic Critic 负责：

    research correctness / semantic integrity

不是：

    formatting beautifier

至少检查：

- problem → model alignment
- assumptions
- variable semantics
- statistical entity semantics
- decision-time information set
- objective identity
- constraint semantics
- model contract → implementation consistency
- implementation → result consistency
- validation sufficiency
- leakage
- sensitivity / robustness
- baseline comparison
- unsupported optimality
- “better / improved / optimal” wording
- causal overclaim
- unsupported inference
- conclusion boundary
- claim → evidence binding
- paper → frozen result consistency
- model composition identity
- statistical design consistency where relevant

Semantic Critic 输出：

    findings

不得输出：

    deterministic PASS

来替代 deterministic checker。

============================================================
9. Judge Lens
============================================================

优先复用当前已有：

    judge-scan

升级为：

    Judge Lens

不要建立第二套 judge framework。

Judge Lens 检查：

- 是否完整回答每个小问
- 摘要是否快速暴露：
  - 模型
  - 核心结果
  - 主要结论
- 关键贡献是否容易找到
- 模型复杂度是否有合理收益
- 图表是否降低阅读成本
- 结论是否容易定位
- 创新点是否有 evidence
- 是否存在“工作很多但重点不清”
- 是否存在 competition-review risk
- 阅读顺序是否自然
- 是否有明显评委可见硬伤
- figure/table 与 narrative 是否一致
- abstract 与正文核心结论是否一致

默认：

    issue-only

禁止生成：

- 官方评分
- 国一概率
- 获奖概率
- 虚构 judge score

除非未来有真实评分合同。

============================================================
10. Deterministic QA 与 Semantic Review 的边界
============================================================

必须继续保持：

机器可以确定：

- hash mismatch
- missing artifact
- stale artifact
- formula replay mismatch
- objective recomputation mismatch
- split leakage when formally detectable
- page count
- missing required citation
- PDF numeric mismatch
- frozen result drift

必须：

    deterministic checker
        → PASS / FAIL

语义问题：

- assumption quality
- model suitability
- interpretation
- innovation validity
- causal strength
- judge readability
- model complexity justification

只能：

    finding
    severity
    recommendation
    human judgment

禁止：

    LLM says PASS
        ↓
    deterministic gate PASS

============================================================
11. Review Report Ownership
============================================================

Review report 属于：

    GENERATED_EVIDENCE

不要把完整 review state 塞回 Manifest v2。

建议复用现有 review schema / report structure。

如果现有结构足够：

    schema +0

优先。

可使用类似：

    reports/review/semantic_review.json
    reports/review/judge_review.json
    reports/review/fresh_review.json

但文件数量不是目标。

如果一个 unified review report 更简单，
也可以。

关键是：

    no second canonical review ledger

Manifest v2 最多保存：

    review root/reference
    current accepted review reference

不要复制：

- findings
- issue states
- reviewer narrative
- full verdict history
- duplicate artifact digests

============================================================
12. Finding Contract
============================================================

每个 finding 至少：

    finding_id
    perspective
    severity
    summary
    evidence_locator
    affected_artifact
    affected_claim_id
    required_fix
    confidence
    status

affected_claim_id 可为空。

severity：

    blocker
    high
    medium
    low

status：

    open
    resolved
    accepted_risk
    superseded

------------------------------------------------------------
12.1 Gate Semantics
------------------------------------------------------------

blocker/high open：

    W2 FAIL

medium：

    默认需要：
    - resolve
      or
    - explicitly accept risk

low：

    可作为非阻塞建议。

禁止：

    verdict=pass
    但仍存在 open blocker/high

============================================================
13. Reviewer Mutation Boundary
============================================================

必须保持：

    Writer
      ↓
    Review
      ↓
    Findings
      ↓
    Revision
      ↓
    affected deterministic checks
      ↓
    Review recheck

Reviewer 只能：

    inspect
    identify
    explain
    require fix

Reviewer 不得：

    edit paper
    edit frozen results
    edit model contract
    edit evidence registry
    edit manifest truth
    resolve finding by modifying artifact itself

如果现有代码允许 Reviewer 直接 mutation author artifact：

    fix it

============================================================
14. Bounded Revision
============================================================

复用当前 revision policy。

默认：

    max 2 automatic revision loops

优先自动处理：

    blocker
    high
    conclusion-changing medium

不自动进行无界润色。

要求：

- finding ID 稳定；
- revision 后只重跑受影响 checks；
- paper 改动后旧 review 可能 stale；
- frozen result 被修改必须立即 invalidation；
- blocker/high 未减少时停止自动循环；
- 用户可继续人工处理。

============================================================
15. Review Freshness
============================================================

Review 必须绑定：

    it reviewed which exact artifact version

必须检测：

    paper v1
      ↓
    review PASS
      ↓
    paper modified to v2
      ↓
    old review stale

旧 review 不得继续用于 W2。

Freshness 优先基于现有：

    artifact identity
    artifact DAG
    canonical digest owner

不要：

    每个 review 文件复制一套 digest truth

Review report 只引用：

    artifact_id
    canonical artifact digest/ref
    reviewed_at

Gate 重算 freshness。

============================================================
16. harness status：Review 必须可见
============================================================

用户运行：

    harness status

必须能直接看到：

    Reviewer 是否真正执行
    哪个 perspective 执行
    finding severity
    review freshness
    next action

例如：

    Project: cumcm-2026-A
    Profile: research

    M1   PASS
    P1   PASS
    P2   PASS
    W1   PASS

    W2:
      draft                PASS
      deterministic_qa     PASS
      semantic_review      FAIL
          blocker: 0
          high: 1
          medium: 3
          independence: L1_fresh_context
      judge_review         PASS
      revision             REQUIRED

    S1   BLOCKED

    Next:
      REV-W2-003
      Abstract claims global optimality,
      but current evidence only supports
      superiority over the tested baseline.

对于：

    harness status --json

提供结构化 review summary。

不要要求用户打开 manifest 才知道 review 状态。

============================================================
17. W2 Gate：必须消费真实 Review Evidence
============================================================

W2 不得信任：

    manifest.semantic_review = pass

必须从：

    actual review report
    current artifact binding
    finding states
    freshness

重新计算。

至少满足：

research:

- deterministic QA pass
- semantic review current
- judge review current
- no open blocker/high

submission:

- research requirements
- one current review with independence_level >= L1

如果 review report：

- 缺失
- stale
- artifact mismatch
- verdict 与 finding 冲突

则：

    W2 FAIL

============================================================
18. Review Execution Must Be Observable
============================================================

用户执行：

    harness review

human-readable output 应明确显示：

    [1/3] Running deterministic QA...
    [2/3] Running semantic review...
    [3/3] Running judge review...

完成后：

    Semantic review:
      0 blocker
      1 high
      3 medium

    Judge review:
      0 blocker
      0 high
      2 medium

    W2:
      FAIL

    Next:
      fix REV-W2-003

具体输出格式可以调整。

但必须让用户感知：

    “Reviewer 真实运行了。”

============================================================
19. Optional Multi-Agent Support：本轮只留最小 Seam
============================================================

本轮不要实现 general multi-agent framework。

但是 Review Resolver 可以允许：

    current_context
    fresh_context
    external_reviewer

三类最小 execution path。

如果当前 runtime 支持 subagent：

    fresh_context

可以使用 subagent。

如果不支持：

    research 可以 fallback L0
    submission 要求 human or other L1 path

禁止：

    backend 不支持 subagent
        ↓
    entire Harness unusable

核心原则：

    Multi-Agent optional
    Review semantic mandatory

============================================================
20. No Consensus Theater
============================================================

禁止：

    3/3 reviewers agree
        ↓
    therefore correct

禁止：

    majority vote
    average judge score
    chief reviewer final truth

Multi-Agent 的价值只在：

- different perspective
- fresh context
- independent model
- failure discovery

不是：

    consensus = evidence

事实 Gate 仍依赖：

    deterministic evidence

语义 Gate 依赖：

    explicit findings
    bounded judgment
    human responsibility

============================================================
21. Minimal Authorization Boundary
============================================================

本轮不要实现 generic approval engine。

只需要确保：

    submission profile
    ≠
    auto final freeze

保持：

    ready_to_freeze
      ↓
    explicit human authorization
      ↓
    final freeze

本轮不做：

    approve/reject/modify/escalate generic engine

这个留 Future P1。

============================================================
22. Gate Mutation Policy
============================================================

本轮重点约束 W2。

W2 Review：

ALLOW:

- generated review reports
- generated findings
- review receipts / execution metadata
- review freshness metadata

DENY:

- reviewer editing author artifact
- reviewer editing frozen evidence
- reviewer editing manifest truth
- reviewer overwriting existing frozen result
- reviewer self-resolving issue by mutation

Revision step：

ALLOW:

- author manuscript edits
- paper-plan edits if necessary
- derived presentation edits

DENY:

- silent frozen result change
- silent model identity change
- silent objective change

如果 revision 需要改变：

    model contract
    frozen result
    objective
    critical parameter

则必须：

    invalidate upstream
    leave W2
    return to appropriate earlier Gate

============================================================
23. Review E2E
============================================================

必须增加真实 Review E2E。

不是 mock：

    review = pass

------------------------------------------------------------
23.1 E2E-A: Semantic Finding
------------------------------------------------------------

流程：

    init minimal case
      ↓
    minimal contract
      ↓
    tiny execution
      ↓
    validation
      ↓
    frozen result
      ↓
    minimal manuscript with one intentional semantic overclaim
      ↓
    harness review
      ↓
    semantic finding generated
      ↓
    W2 FAIL

验证：

    reviewer actually executes

------------------------------------------------------------
23.2 E2E-B: Revision / Recheck
------------------------------------------------------------

    previous high finding
      ↓
    revision fixes claim
      ↓
    affected QA
      ↓
    re-review
      ↓
    finding resolved
      ↓
    W2 PASS

------------------------------------------------------------
23.3 E2E-C: Stale Review
------------------------------------------------------------

    paper v1
      ↓
    review PASS
      ↓
    paper changed to v2
      ↓
    old review stale
      ↓
    W2 FAIL

------------------------------------------------------------
23.4 E2E-D: Fresh Review Boundary
------------------------------------------------------------

fresh reviewer receives:

    allowed review bundle

test must verify it does not receive:

- previous verdict
- writer reasoning
- revision discussion

if contaminated:

    independence_level cannot be L1

============================================================
24. Review Tests
============================================================

至少覆盖：

A.

research
无 semantic review report

→ W2 FAIL

B.

semantic review 有 open high

→ W2 FAIL

C.

high resolved
re-review current

→ W2 PASS allowed

D.

review report stale

→ W2 FAIL

E.

sprint

→ Judge Lens 非必须

F.

research

→ Judge Lens 必须

G.

submission

→ 至少 one current review
   independence_level >= L1

H.

self_critic

→ 不得冒充 L1/L2

I.

reviewer modifies frozen artifact

→ integrity invalidation

J.

manifest 手改：

    semantic_review = pass

但无真实 report

→ FAIL

K.

report verdict=pass
但存在 blocker/high open

→ FAIL

L.

report artifact binding mismatch

→ FAIL

M.

fresh reviewer bundle 含 previous verdict

→ independence claim invalid

N.

same-context reviewer 标记 independent_model

→ FAIL

O.

paper changed after pass

→ review stale

P.

harness status

→ exposes review summary

Q.

harness review

→ produces real review artifact

============================================================
25. Skill-Level Testing Principle
============================================================

借鉴 Anthropic Skill Creator、Superpowers、SkillOpt。

本轮不实现 Skill benchmark framework。

但如果本轮需要修改：

    SKILL.md
    semantic_critic_rubric.md
    revision_policy.md
    judge scan instructions

必须至少有：

    observed behavior
    before
    after
    regression

特别是新增 Skill rule 前：

    do not add a rule only because it sounds good

需要回答：

1. 哪个 observed failure 需要它？
2. 现有 instruction 为什么不够？
3. test 如何证明它生效？
4. 是否增加 token/context burden？

核心原则：

    No new Harness mechanism
    without an observed failure
    or measured capability gain.

============================================================
26. Progressive Disclosure
============================================================

不要因为 Review Execution 增加：

    Root SKILL 188 lines
        ↓
    400+ lines

Root SKILL 继续只负责：

- current stage
- profile
- risk routing
- which reference to load
- which CLI action to invoke

Review 细节放：

    references/review/

确定性操作放：

    scripts/

执行行为放：

    harness runtime

============================================================
27. Review Reference Routing
============================================================

建议保持：

references/review/

例如：

    semantic_critic_rubric.md
    revision_policy.md
    judge_lens.md

但不要重复内容。

Semantic Critic 与 Judge Lens 应各有清晰责任。

不要：

    semantic_critic.md
    semantic_reviewer.md
    reviewer.md
    review_policy.md
    review_checklist.md

五个文件重复同一套规则。

============================================================
28. State Complexity Budget
============================================================

本轮目标：

    profile dimension +0
    canonical state +0
    top-level Gate +0

schema：

    preferably +0

如果必须新增 schema：

    必须解释现有 schema 为什么不能表达。

禁止新增：

- review_profile
- critic_profile
- judge_profile
- blind_profile
- review_manifest
- review_registry
- reviewer_state
- worker_registry
- review_artifact_dag
- agent_state

Review finding / receipt：

    GENERATED_EVIDENCE

不是：

    NEW CANONICAL STATE

============================================================
29. CLI Complexity Budget
============================================================

目标只新增：

    harness review

如果现有：

    harness status --verbose

已经能显示详细 review trace，

不要再加：

    harness inspect-review
    harness reviewer-status
    harness judge-status

遵循：

    one obvious command per user intent

============================================================
30. 与现有实现优先复用
============================================================

优先复用：

- Manifest v2
- unified CLI
- profile resolver
- artifact DAG
- receipt system
- deterministic QA
- check_gates
- harness_status
- semantic_critic_rubric.md
- revision_policy.md
- judge-scan
- current hash / integrity policy
- migration support

如果：

judge-scan

可以升级成 Judge Lens：

    extend it

不要新建第二套。

如果现有 review schema 足够：

    reuse it

不要新增。

如果现有 receipt 能表达 review execution：

    reuse / extend minimally

不要新建 parallel receipt architecture。

============================================================
31. Future Roadmap — 本轮只记录，不实现
============================================================

以下能力来自 v3 / OSS 调研，
保留为 follow-up roadmap。

本轮禁止实施。

------------------------------------------------------------
31.1 P1 — Runtime Robustness
------------------------------------------------------------

Future:

- durable resume
- retry preserving failed attempts
- clean-process claimable run
- lightweight trajectory
- Harness Map
- context budget / context router
- generic approval semantics

参考：

- LangGraph
- Inspect AI
- mini-SWE-agent
- Aider

------------------------------------------------------------
31.2 P2 — Optional Multi-Agent
------------------------------------------------------------

Future:

- Worker Contract
- Worker Adapter
- capability-based routing
- fresh reviewer backend
- independent-model backend
- adversarial reviewer
- candidate generation workers

参考：

- Microsoft Agent Framework
- OpenHands
- Superpowers

原则：

    optional topology
    canonical state +0

------------------------------------------------------------
31.3 P3 — Skill Evaluation / Evolution
------------------------------------------------------------

Future:

- with-skill / without-skill paired benchmark
- held-out skill validation
- trigger evaluation
- token/context cost
- false-positive rate
- rejected skill edit history
- optional SkillOpt-style optimization

参考：

- Anthropic skill-creator
- Superpowers writing-skills
- Microsoft SkillOpt
- SkillBenchmark
- SWE-Skills-Bench

任何未来 Skill 拆分必须：

    earn promotion by evaluation

============================================================
32. 本轮输出文档
============================================================

更新：

- docs/REVIEW_EXECUTION_DESIGN.md
- docs/WP3_IMPLEMENTATION_REPORT.md
- docs/WP3_TEST_REPORT.md

不要再建立大量平行文档。

REVIEW_EXECUTION_DESIGN.md 至少说明：

- W2 lifecycle
- Semantic Critic vs Judge Lens
- review_mode
- independence_level
- fresh-context information boundary
- generated evidence ownership
- review freshness
- revision loop
- W2 adjudication
- submission human boundary
- Future P1/P2/P3 explicitly out of scope

============================================================
33. Implementation Report
============================================================

WP3_IMPLEMENTATION_REPORT.md 必须说明：

A. Changed

- changed files
- added CLI
- review execution behavior

B. State Complexity

明确：

    canonical state delta
    schema delta
    profile dimension delta
    top-level Gate delta

C. Reuse

说明复用了哪些：

    existing schema
    existing judge-scan
    existing receipt
    existing DAG
    existing status

D. Multi-Agent

说明：

    是否真正使用 fresh subagent
    如果没有，使用何种 fallback
    independence_level 如何得出

E. Deferred

明确列出：

    P1
    P2
    P3

没有实现。

============================================================
34. Test Report
============================================================

WP3_TEST_REPORT.md 区分：

1. Existing Regression

    previous suite

2. New Review Unit / Integration Tests

3. Review E2E

4. Skill Validation

    if SKILL/reference modified

5. Environment Limitations

不要把：

    schema parse PASS

描述为：

    review capability proven

============================================================
35. Commit 前验收
============================================================

逐项回答：

1.

是否有：

    harness review

2.

它是否真实执行 review，
而不是只改 manifest 状态？

3.

Semantic Critic 是否产生 findings？

4.

Judge Lens 是否真实运行？

5.

research W2 是否要求 current semantic + judge review？

6.

submission 是否要求至少 L1 independence review？

7.

same-context self-critic 是否不会伪装成 independent reviewer？

8.

Reviewer 是否无法直接修改作者 artifact？

9.

paper 修改后旧 review 是否 stale？

10.

W2 是否从真实 report / freshness 重算？

11.

manifest 手改 pass 是否无效？

12.

open blocker/high 是否阻止 W2？

13.

harness status 是否能看到：

- reviewer state
- severity counts
- independence level
- stale/current
- next action

14.

是否没有新增顶层 R1 Gate？

15.

是否仍然：

    M1
    P1
    P2
    W1
    W2
    S1

16.

profile 是否仍只有：

    sprint
    research
    submission

17.

是否没有新增 review profile matrix？

18.

canonical state 是否 +0？

19.

schema 是否尽量 +0？

20.

Root SKILL 是否仍保持精简？

21.

existing regression 是否仍全部通过？

22.

new Review E2E 是否真实证明 reviewer executes？

23.

Future P1/P2/P3 是否没有被顺手实现？

============================================================
36. Anti-Patterns
============================================================

如果出现以下任意行为，
优先删除/收缩。

ANTI-PATTERN 1

    reviewer role
        → reviewer_state.json

ANTI-PATTERN 2

    Semantic Critic
        → one new schema

    Judge Lens
        → another schema

ANTI-PATTERN 3

    review status in manifest
        = source of truth

ANTI-PATTERN 4

    same model changes persona
        → independent reviewer

ANTI-PATTERN 5

    3 reviewers agree
        → correctness

ANTI-PATTERN 6

    Reviewer finds issue
        → Reviewer edits paper
        → Reviewer passes itself

ANTI-PATTERN 7

    paper changed
        → old review remains valid

ANTI-PATTERN 8

    add harness review
        → rebuild workflow engine

ANTI-PATTERN 9

    support fresh context
        → build generic multi-agent SDK

ANTI-PATTERN 10

    reference OSS project
        → copy its entire architecture

ANTI-PATTERN 11

    review feature
        → Root SKILL doubles in size

ANTI-PATTERN 12

    more automation
        → less human responsibility

============================================================
37. Final Architecture Target
============================================================

本轮完成后目标：

                 Typed Invocation
                       ↓
                Profile Resolver
                       ↓
                  Manifest v2
                       ↓
             Single Control Plane
                       ↓
        ┌──────────────┼──────────────┐
        ↓              ↓              ↓
    Contracts      Execution       Evidence
        │              │              │
        └──────── Artifact DAG ────────┘
                       ↓
                Deterministic QA
                       ↓
                 Semantic Critic
                       ↓
                   Judge Lens
                       ↓
              Targeted Revision
                       ↓
                 Review Recheck
                       ↓
                    W2 PASS
                       ↓
                Human Authority
                       ↓
                   S1 / F1

Optional:

                 fresh-context worker
                       ↓
                  review findings

但：

    optional worker
    不拥有 canonical state。

============================================================
38. 产品原则
============================================================

最终仍然是：

    Math Modeling Evidence Harness

不是：

    Multi-Agent Math Modeling Platform

不是：

    General Agent Framework

不是：

    Automated Contest Solver

产品原则：

    少量人工合同
    + 自动生成 evidence
    + 单一 control plane
    + deterministic facts
    + explicit semantic review
    + optional independent reviewer
    + bounded revision
    + human final authority

核心定位：

    算得出
    → 讲得清
    → 证得住
    → 交得稳

============================================================
39. 本轮最终执行顺序
============================================================

严格按：

STEP 1

检查当前未提交 diff。

确认：

    Manifest v2
    profile resolver
    unified CLI
    DAG
    receipt
    existing review schema/rubric

真实存在。

STEP 2

先做 design delta：

    Review Execution only

不要改 Future P1/P2/P3。

STEP 3

实现：

    harness review

STEP 4

接：

    Semantic Critic
    Judge Lens
    optional fresh-context review

STEP 5

实现：

    report binding
    freshness
    W2 recompute

STEP 6

更新：

    harness status

STEP 7

补：

    unit / integration tests

STEP 8

跑：

    real Review E2E

STEP 9

跑全部 existing regression。

STEP 10

更新：

    docs/REVIEW_EXECUTION_DESIGN.md
    docs/WP3_IMPLEMENTATION_REPORT.md
    docs/WP3_TEST_REPORT.md

STEP 11

输出 final report。

仍然：

    DO NOT COMMIT.
    DO NOT PUSH.

============================================================
40. 最终报告格式
============================================================

完成后只输出：

A. Implemented

B. Review Flow

    sprint
    research
    submission

C. Multi-Agent / Independence

D. State Complexity

    canonical state delta
    schema delta
    profile delta
    Gate delta

E. Tests

    previous regression
    new review tests
    E2E
    git diff --check

F. Deferred

    P1
    P2
    P3

G. Remaining Risks

H. Git Status

    no commit
    no push

============================================================
41. 最后约束
============================================================

本轮最重要的不是：

    把 OSS 好机制全部做进去。

而是：

    用 OSS 中已经证明有效的设计原则，
    把当前最明显的缺口
    Review Execution Plane
    做完整、做真实、做可测试。

如果实现过程中出现：

    “顺便可以把 retry 也做了”
    “顺便做个 worker registry”
    “顺便做 generic approval”
    “顺便做 task/solver/scorer”
    “顺便做 skill optimizer”

全部停止。

记录到 Future Roadmap。

不要实现。

本轮成功标准只有一句话：

    当用户运行 Harness 时，
    Reviewer 不再只是 Schema 里的字段，
    而是一个真实执行、产生 evidence、
    可被 status 看见、能阻止错误论文进入 W2 PASS 的流程。

先检查当前未提交 diff。

然后开始。

不要重新架构。

不要回滚。

不要 commit。

不要 push。
