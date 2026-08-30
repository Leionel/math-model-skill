# HISTORICAL DESIGN / EXECUTION RECORD
> Do not use this file as current operational instruction.
> Current truth starts from `SKILL.md` and `references/router.md`.

# Math Modeling Harness 下一阶段改造计划
## 从 Evidence Harness 走向 Authoring + Submission Workflow

**适用仓库：** `Leionel/math-model-skill`  
**审查基线：** 2026-08-20，当前 `agent/math-modeling-harness` 分支，最新审查提交 `b9c3d9e`（Implement executable review execution plane）  
**文档定位：** 下一阶段实现计划 / Codex & Claude Code implementation brief  
**核心目标：** 不继续堆叠独立 schema 与 JSON，而是让现有 Evidence / QA / Review 能力真正服务于“建模 → 写作 → 附录/AI说明 → 提交”的正常工作流。

---

# 1. 结论先行

当前 Harness 已经形成较强的：

```text
Evidence Plane
QA Plane
Review Plane
Freeze / Submission Integrity Plane
```

但仍缺少同等成熟的：

```text
Authoring Plane
Human-facing Artifact Plane
Submission Preparation Plane
```

现阶段最主要的问题不再是“检查器不够多”，而是：

> **机器合同已经很强，但用户和执行 Agent 仍然需要直接面对过多 JSON；真正需要人理解、讨论、确认和提交的中间产物没有被一等公民化。**

下一阶段应停止“一个问题新增一个 JSON”的扩张方式，改为：

```text
Human-facing Markdown / LaTeX / Submission Artifacts
                    ↑
       deterministic projection / producer
                    ↑
Existing structured state + evidence contracts
```

即：

> **内部仍然结构化，外部必须文档化。**

---

# 2. 当前三个最高优先级缺口

## 2.1 M1 建模方案没有形成正式文档

当前 M1 已经要求：

- 拆题；
- 文献与外部检索；
- 候选模型比较；
- 假设与 assumption fork；
- 模型选型；
- equation plan；
- parameter provenance；
- implementation steps；
- validation obligations；
- failure modes；
- M1 human checkpoint。

但这些内容目前主要落在：

```text
model_contract.json
```

这对机器 QA 合适，对人机协作不合适。

### 问题

一个真实参赛者、队友或下一轮 Agent 真正需要看到的是：

```text
为什么这么建模？
有哪些备选？
为什么没选另外几个？
关键公式是什么？
哪些假设最危险？
验证如何推翻这个模型？
下一步准备怎么实现？
```

而不是浏览数百行 JSON。

### 改造目标

新增第一等的人类可读 artifact：

```text
MODELING_PLAN.md
```

其内容由 `model_contract.json + verified research evidence` 确定性生成。

推荐结构：

```text
# Modeling Plan

## 1. Problem Decomposition
## 2. Required Outputs by Question
## 3. Data and Scope
## 4. Key Assumptions and Ambiguities
## 5. Candidate Model Comparison
## 6. Selected Modeling Strategy
## 7. Mathematical Formulation
## 8. Parameter and Data Provenance
## 9. Implementation Plan
## 10. Validation / Falsification Plan
## 11. Failure Modes and Fallbacks
## 12. Open Questions
## 13. M1 Approval Checklist
```

### 关键原则

`MODELING_PLAN.md` **不是第二真源**。

必须满足：

```text
model_contract.json
        ↓
deterministic renderer
        ↓
MODELING_PLAN.md
```

禁止反向从 Markdown 手工推断 Gate PASS。

如用户修改 Markdown，应重新同步回 contract 的明确字段，或提示该文档仅为 projection。

---

## 2.2 AI 使用记录与 AI 说明存在“忘记做”的结构性风险

当前 Harness 已有：

- `run_manifest.ai_usage[]`
- Competition Profile 中的 AI disclosure policy；
- S1 AI disclosure QA；
- AI report / support package 检查；
- CUMCM / MCM-ICM 的不同披露要求。

但当前核心风险是：

```text
ai_usage = []
```

同时承担了两种完全不同的含义：

```text
A. 确认未使用 AI
B. 忘记登记 AI 使用
```

这在一个 **本身由 AI Agent 驱动的 Harness** 中风险很高。

### 改造目标 1：AI 使用状态三态化

不要再把空数组等价于“未使用”。

新增或派生：

```text
ai_usage_state:
  unknown
  none
  used
```

规则：

```text
项目初始化        -> unknown
用户/Agent确认未用 -> none
产生任何影响交付物的AI记录 -> used
```

S1 时：

```text
unknown -> BLOCK
none    -> 按“未使用AI”的官方声明路径
used    -> 必须生成披露材料
```

### 改造目标 2：AI Usage Ledger 变为自动积累 artifact

建议内部保持结构化记录，但自动生成：

```text
AI_USAGE_LEDGER.md
```

内容包括：

- 工具 / 模型；
- 日期时间；
- 阶段；
- 用途；
- 关键 prompt 概要；
- 输出概要；
- 采用内容；
- 人工修改；
- 人工核验状态；
- 对应 artifact / section。

### 改造目标 3：AI Disclosure Producer

不要等 S1 时提醒 Agent “请自己写 AI 声明”。

新增 producer：

```text
AI Usage Registry
        +
Competition Profile
        ↓
AI Disclosure Renderer
        ↓
CUMCM:
  AI工具使用详情.md
  AI工具使用详情.pdf / source

MCM/ICM:
  report_on_ai_tools.tex
```

建议 CLI：

```text
harness prepare S1
```

内部完成：

```text
render_ai_disclosure()
render_submission_checklist()
stage_support_materials()
```

而不是新增大量独立命令。

---

## 2.3 JSON Surface 仍然过大

Manifest v2 已正确解决：

> 初始化时不要创建几十个空 JSON。

这一点应保留。

但随着完整比赛执行，项目根目录仍可能出现：

```text
competition_profile.json
run_manifest.json
artifact_dag.json
run_index.json
model_contract.json
evidence_registry.json
paper_plan.json
writer_package.json
frozen_results.json
derived_results.json
diagram_spec.json
validation reports
review reports
receipts
submission reports
submission manifest
...
```

### 核心原则

不要通过合并 contract 来追求“文件数量少”。

应该减少：

> **Public JSON Surface**

而不是减少：

> **Internal Structured State**

### 推荐目录重构

用户可见：

```text
project/
├── MODELING_PLAN.md
├── PAPER_OUTLINE.md
├── PROJECT_BRIEF.md
├── SUBMISSION_CHECKLIST.md
│
├── data/
├── code/
├── figures/
├── paper/
├── appendix/
└── submission/
```

Harness 内部：

```text
project/.harness/
├── state/
│   ├── competition_profile.json
│   ├── run_manifest.json
│   ├── artifact_dag.json
│   └── run_index.json
│
├── contracts/
│   ├── model_contract.json
│   └── paper_plan.json
│
├── evidence/
│   ├── evidence_registry.json
│   ├── frozen_results.json
│   └── derived_results.json
│
├── receipts/
├── review/
├── qa/
├── build/
└── cache/
```

### 兼容策略

第一阶段不要强行迁移所有旧路径。

支持：

```text
legacy flat layout
new hidden-state layout
```

然后由 resolver：

```python
resolve_project_artifact("model_contract")
```

统一寻找。

待新布局稳定后再做正式 migration。

---

# 3. 新增核心能力：Authoring Execution Plane

Review 已经从：

```text
review declarative
```

升级为：

```text
review executable
```

下一阶段要对称地完成：

```text
authoring declarative
        ↓
authoring executable
```

当前主流程：

```text
S0 -> M1 -> P1 -> P2 -> W1 -> W2 -> S1 -> F1
```

保持不变。

但每个关键 Gate 应有一个人类可读的产出层。

---

## 3.1 新的 Human-facing Artifact Plane

建议固定 4 个核心文档：

```text
MODELING_PLAN.md
PAPER_OUTLINE.md
PROJECT_BRIEF.md
SUBMISSION_CHECKLIST.md
```

可选：

```text
AI_USAGE_LEDGER.md
APPENDIX_PLAN.md
```

不要每个 Gate 新建一个 Markdown。

### Artifact 定位

| Artifact | 主要来源 | 用途 |
|---|---|---|
| `MODELING_PLAN.md` | model contract + research evidence | M1 人审与实现前确认 |
| `PAPER_OUTLINE.md` | paper plan + frozen results | Writer / 人类理解论文论证结构 |
| `PROJECT_BRIEF.md` | runtime state 聚合 | Agent 换上下文、长任务恢复 |
| `SUBMISSION_CHECKLIST.md` | competition profile + S1 state | 最后交付清单 |
| `AI_USAGE_LEDGER.md` | ai usage registry | AI 使用累积记录 |
| `APPENDIX_PLAN.md` | paper plan + deliverables plan | 附录/支撑材料规划 |

---

# 4. 新增统一命令：`harness prepare`

不要再增加大量碎片 CLI。

新增：

```text
harness prepare M1
harness prepare W1
harness prepare W2
harness prepare S1
```

---

## 4.1 `harness prepare M1`

输入：

```text
problem snapshot
model_contract
research evidence
competition profile
```

产出：

```text
MODELING_PLAN.md
PROJECT_BRIEF.md
```

检查：

- M1 contract 至少 draft；
- candidate comparison 存在；
- selected model 存在；
- 未解决 assumption fork 明确显示；
- validation plan 显示；
- research evidence 状态显示。

注意：

> prepare 不代表 Gate PASS。

它只是生成供人审的材料。

---

## 4.2 `harness prepare W1`

输入：

```text
model_contract
frozen_results
evidence_registry
paper_plan
```

产出：

```text
PAPER_OUTLINE.md
APPENDIX_PLAN.md
PROJECT_BRIEF.md
```

`PAPER_OUTLINE.md` 推荐：

```text
# Paper Outline

## Central Thesis

## Q1
### Model / Formulation
### Result
### Validation
### Interpretation / Boundary

## Q2
...

## Planned Figures
## Planned Tables
## Planned Appendix
## Abstract Result Budget
## Remaining Evidence Gaps
```

---

## 4.3 `harness prepare W2`

输入：

```text
paper plan
writer package
current paper draft
figure plan
```

产出：

```text
revision checklist
current coverage summary
PROJECT_BRIEF.md
```

如果 review 已存在：

```text
open findings
stale reports
missing sections
figure problems
```

全部汇总到人类可读状态里。

---

## 4.4 `harness prepare S1`

输入：

```text
competition profile
run manifest
AI usage ledger
paper
appendix/support materials
current S1 state
```

产出：

```text
SUBMISSION_CHECKLIST.md
AI disclosure draft
support staging directory
PROJECT_BRIEF.md
```

不得上传。

不得自动声称 submission ready。

---

# 5. 附录与 Supporting Materials 一等公民化

当前 submission 层对：

```text
paper
support
ai_disclosure
```

有较强检查。

但缺少真正的 **Deliverables Planning Model**。

数模中至少应区分：

```text
main_paper
paper_appendix
ai_report
code_appendix
supplementary_tables
official_result_workbook
support_material
submission_package
```

这些不是同一个概念。

---

## 5.1 不建议新建 `appendix_contract.json`

优先扩展现有 `paper_plan` 或 submission planning 结构，例如：

```json
{
  "deliverables": [
    {
      "deliverable_id": "D-PAPER",
      "type": "main_paper",
      "required": true
    },
    {
      "deliverable_id": "D-AI",
      "type": "ai_report",
      "required": "profile_condition"
    },
    {
      "deliverable_id": "D-SUPPORT",
      "type": "support_material",
      "required": "profile_condition"
    }
  ]
}
```

不要引入一个新的平行真源。

---

## 5.2 W1 就规划附录

不要等 S1 才发现：

```text
代码没整理
大表没放
AI 使用详情没写
结果 workbook 没检查
support 文件不知道放哪
```

`PAPER_OUTLINE.md / APPENDIX_PLAN.md` 应提前显示：

```text
Appendix A — Parameter Definitions
Appendix B — Detailed Constraints
Appendix C — Sensitivity Tables
Support — Code / Result Workbook
AI Disclosure — required, draft pending
```

---

# 6. `PROJECT_BRIEF.md`：长上下文与 Agent Handoff 的关键层

这是下一阶段非常重要的体验能力。

当前 Harness 已经有事实状态，但事实散落在多个结构化 artifact 中。

每次 Gate 变化后自动更新：

```text
PROJECT_BRIEF.md
```

推荐结构：

```text
# Project Brief

## Current State
Preset:
Stage:
First blocker:
Last factual successful gate:

## Problem / Competition
Competition:
Question:
Rule snapshot status:

## Current Modeling Decision
Selected models:
Key assumptions:
Open ambiguity:

## Current Results
Selected full run:
Frozen result:
Validation status:

## Failed / Rejected Paths
...

## Paper Status
Outline:
Draft:
Figures:
Appendix:

## AI / Compliance Status
AI usage state:
Disclosure:
Submission profile:

## Review Status
Current reports:
Open blocker/high/medium:

## Human Decisions Pending
...

## Next Action
...
```

---

## 6.1 必须是 projection

`PROJECT_BRIEF.md` 不得成为事实源。

始终：

```text
runtime state
    ↓
brief renderer
    ↓
PROJECT_BRIEF.md
```

如果用户手改 brief：

```text
不会改变 Gate
不会改变 receipt
不会改变 selected run
不会改变 freeze
```

---

# 7. Paper Plan 必须承认自己是 IR

当前 `paper_plan.json` 已经包含：

- thesis；
- requirements；
- claims；
- argument units；
- depth budget；
- figures；
- tables；
- abstract results；
- readiness；
- draft coverage。

它已经不是“给人读的计划”，而是：

> **Paper Intermediate Representation**

因此明确定位：

```text
paper_plan.json = machine IR
PAPER_OUTLINE.md = human projection
writer_package.json = compiler package
paper/*.tex = authored output
```

不要继续试图让 `paper_plan.json` 同时承担人类可读性。

---

# 8. Draw.io Archetype 系统纳入本轮 P1

当前 Diagram Spec 仍以：

```text
kind
layout
style_profile
nodes
edges
panels
```

为核心。

下一轮实现之前已规划的：

```text
archetype
composition grammar
visual primitives
```

固定：

```text
research_framework
computational_pipeline
parallel_integration
method_architecture
iterative_optimization
custom
```

并继续保持：

```text
archetype = topology
style_profile = visual skin
```

该任务放在 P1，不高于 AI disclosure / modeling plan / project brief。

原因：

> 视觉质量重要，但不会像 AI disclosure 遗漏一样直接造成合规风险。

---

# 9. AI Usage 自动登记策略

完全自动捕获“所有大模型交互”在通用 Harness 中未必可靠，因此采用：

```text
automatic where observable
explicit confirmation where not observable
```

---

## 9.1 可自动登记

Harness 自己主动触发的：

```text
review backend
LLM-assisted generation command
AI illustration workflow
AI authoring backend
```

必须由 producer 自动登记。

Agent 不应再额外手工补一次。

---

## 9.2 不可自动观察的外部 AI

例如用户在另一个客户端使用 AI。

必须提供快速入口：

```text
harness ai record
```

但不要要求写完整 JSON。

人类界面可以询问：

```text
Tool/model:
Stage:
Purpose:
What was adopted:
Human verification:
```

内部再写 registry。

---

## 9.3 S1 前强制 resolve

`ai_usage_state=unknown`：

```text
S1 BLOCK
```

CLI 提示：

```text
AI usage status is unresolved.
Confirm one:
1. no AI affected the deliverables
2. AI was used; render/update disclosure
```

---

# 10. Submission Staging

新增：

```text
submission/staging/
```

由 `prepare S1` 生成建议结构，但不自动上传：

```text
submission/
├── staging/
│   ├── paper.pdf
│   ├── support/
│   ├── ai_disclosure/
│   └── official_outputs/
├── SUBMISSION_CHECKLIST.md
└── final/
```

原则：

```text
staging = mutable preparation
final   = only after F1
```

避免“最终文件”和“正在修改的文件”混在一起。

---

# 11. 下一阶段不要做的事

## 11.1 不要继续新增十几个 JSON contract

新增 artifact 前必须回答：

```text
能否扩展已有 contract？
能否成为 derived projection？
是否真的存在新的事实所有权？
```

只有存在新事实所有权时才新增 schema。

---

## 11.2 不要把 Markdown 变成第二套 truth

所有 human-facing 文档：

```text
MODELING_PLAN.md
PAPER_OUTLINE.md
PROJECT_BRIEF.md
SUBMISSION_CHECKLIST.md
AI_USAGE_LEDGER.md
```

都必须注明：

```text
Generated projection — factual state remains in Harness contracts/receipts.
```

---

## 11.3 不要把 `prepare` 变成新的 Gate engine

`prepare`：

```text
生成、汇总、提示
```

`check/validate`：

```text
判定
```

必须保持分离。

---

## 11.4 不要进一步扩大根目录 CLI

优先统一：

```text
harness prepare <stage>
```

而不是：

```text
harness render-model-plan
harness render-paper-plan
harness ai-render
harness appendix-plan
harness submission-stage
...
```

---

# 12. 技术结构建议

推荐模块：

```text
scripts/
├── harness.py
├── prepare/
│   ├── __init__.py
│   ├── prepare_m1.py
│   ├── prepare_w1.py
│   ├── prepare_w2.py
│   ├── prepare_s1.py
│   └── common.py
│
├── render/
│   ├── modeling_plan.py
│   ├── paper_outline.py
│   ├── project_brief.py
│   ├── ai_disclosure.py
│   ├── appendix_plan.py
│   └── submission_checklist.py
```

CLI 只负责 dispatch。

---

# 13. 关键 API

建议：

```python
render_modeling_plan(state) -> str
render_paper_outline(state) -> str
render_project_brief(state) -> str
render_appendix_plan(state) -> str
render_ai_usage_ledger(state) -> str
render_ai_disclosure(state, profile) -> RenderedArtifact
render_submission_checklist(state, profile) -> str
```

Producer 必须尽可能：

```text
deterministic
idempotent
diff-friendly
```

---

# 14. P0 实施计划

## P0-A：Human-facing M1

实现：

```text
MODELING_PLAN.md
harness prepare M1
```

Acceptance：

- 每问展示任务与输出；
- 展示 candidate comparison；
- 展示 selected model；
- 展示关键 assumptions/forks；
- 展示 equation / parameter / implementation plan；
- 展示 validation；
- 显示 unresolved risk；
- 文件重生成稳定；
- 不成为 Gate truth。

---

## P0-B：AI Usage 三态 + Ledger

实现：

```text
unknown / none / used
AI_USAGE_LEDGER.md
```

Acceptance：

- init 默认 unknown；
- unknown 无法进入正式 S1；
- Harness 触发的 AI workflow 自动记录；
- none 必须是显式确认；
- used 可生成 ledger。

---

## P0-C：AI Disclosure Producer

实现：

```text
render_ai_disclosure()
```

Acceptance：

CUMCM profile：

```text
AI工具使用详情
```

MCM/ICM profile：

```text
Report on Use of AI Tools
```

必须来自：

```text
current profile + current AI usage records
```

不得编造未记录 interaction。

---

## P0-D：Deliverables 提前规划

在 W1 加：

```text
appendix/support/AI/official-output plan
```

Acceptance：

S1 前必须能明确知道：

```text
哪些 deliverable required
哪些 ready
哪些 missing
哪些 not applicable
```

---

# 15. P1 实施计划

## P1-A：PROJECT_BRIEF

每次 `prepare` / `status --human` 可重生成。

---

## P1-B：PAPER_OUTLINE

从 paper plan IR 投影。

---

## P1-C：Hidden Internal State

逐步支持：

```text
.harness/
```

同时兼容 legacy flat layout。

---

## P1-D：Submission Staging

不上传，仅 staged copy + checklist。

---

## P1-E：Draw.io Archetype

实现固定 5 套 scientific composition grammar。

---

# 16. P2 实施计划

完成此前仍有实际价值的执行能力：

## 16.1 Domain / Index / Dimension Executor

覆盖：

```text
domain bounds
index boundary
canonical dimension
```

例如：

```text
p ∈ [0,1]
λ >= 0
t+1 不越界
加减项量纲一致
objective unit 一致
```

---

## 16.2 Selective Rerun Scheduler

基于 DAG freshness：

```text
changed artifact
      ↓
affected downstream
      ↓
minimal rerun set
```

先输出 plan，不自动执行。

后续再支持：

```text
harness rerun --affected
```

---

## 16.3 Sensitivity Orchestrator

从已声明 sensitivity obligation：

```text
parameter grid
    ↓
run receipts
    ↓
results
    ↓
semantic validation
```

不能只做 checker。

---

## 16.4 Capability Benchmark

必须独立于 regression tests。

目标：

```text
Harness ON
vs
Harness OFF

same task
same model budget
same token/time budget
blind review
```

测：

```text
model choice quality
numerical correctness
paper quality
contest compliance
time cost
revision count
```

---

# 17. 回归测试设计

## T-AUTH-01

给完整 model contract。

预期：

```text
prepare M1
```

生成包含：

- candidate comparison；
- selected model；
- formula plan；
- validation；
- risks。

---

## T-AUTH-02

model contract 存在 unresolved assumption fork。

预期：

`MODELING_PLAN.md` 必须明确显示 unresolved，不能写成已经确定。

---

## T-AI-01

新项目：

```text
ai_usage_state = unknown
```

S1 阻断。

---

## T-AI-02

显式确认：

```text
none
```

生成“未使用 AI”对应 checklist，而不是伪造 usage ledger。

---

## T-AI-03

已有 AI usage。

生成的 AI disclosure 只能包含 registry 已登记事实。

---

## T-PAPER-01

复杂 paper_plan。

生成 `PAPER_OUTLINE.md`：

- 每问结构正确；
- figure/table/appendix 均列出；
- 无 evidence 的 claim 标为 missing，不自动补写。

---

## T-BRIEF-01

存在：

```text
failed run
frozen selected run
open review blocker
pending human checkpoint
```

`PROJECT_BRIEF.md` 必须全部显示。

---

## T-S1-01

AI disclosure 缺失但 profile requires。

`prepare S1`：

```text
生成 draft
checklist 标 missing human confirmation
```

不得自动 PASS。

---

# 18. CLI 预期体验

用户正常情况下只需要：

```powershell
harness init --project ... --competition cumcm --preset research

harness prepare M1 --project ...
harness check M1 --project ...

harness run ...
harness check P1 ...
...

harness prepare W1 --project ...
harness prepare W2 --project ...
harness review --project ...
harness validate --project ...

harness prepare S1 --project ...
harness check S1 --project ...
```

Agent 不需要主动打开 15 个 JSON。

只有 debug / audit 才直接查看 `.harness/`。

---

# 19. 目标项目体验

升级后，一个新的 Agent 进入项目，首先看到：

```text
PROJECT_BRIEF.md
MODELING_PLAN.md
PAPER_OUTLINE.md
```

而不是：

```text
请先阅读 run_manifest.json
再查 artifact_dag.json
再看 model_contract.json
再找 frozen_results.json
再读 paper_plan.json
```

同时底层证据链完全不牺牲。

---

# 20. 最终架构

```text
                         USER / AGENT
                              │
                              ↓
                 Human-facing Artifact Plane
        ┌────────────────────────────────────────┐
        │ MODELING_PLAN.md                       │
        │ PAPER_OUTLINE.md                       │
        │ PROJECT_BRIEF.md                       │
        │ AI_USAGE_LEDGER.md                     │
        │ APPENDIX_PLAN.md                       │
        │ SUBMISSION_CHECKLIST.md                │
        └────────────────────────────────────────┘
                              ↑
                     deterministic render
                              ↑
                 Authoring Execution Plane
                       harness prepare
                              ↑
        ┌────────────────────────────────────────┐
        │ Existing Evidence / Contract Plane     │
        │ model_contract                         │
        │ paper_plan                             │
        │ evidence_registry                      │
        │ frozen_results                         │
        │ receipts / DAG / manifest              │
        └────────────────────────────────────────┘
                              ↓
                       QA / Review Plane
                              ↓
                    Submission / Freeze Plane
```

---

# 21. 成功标准

这轮升级成功不是“又增加了多少 checker”。

而是达到：

### 对用户

```text
基本不需要直接读 JSON
```

### 对 Agent

```text
进入项目后 1–2 个文档即可恢复上下文
```

### 对建模

```text
M1 必须有真正可讨论的建模方案
```

### 对写作

```text
W1 必须有真正可阅读的论文 Outline
```

### 对 AI 合规

```text
unknown 不再等价于 none
AI disclosure 不再靠最后阶段“想起来”
```

### 对附录 / 提交

```text
W1 提前规划，S1 只做最终装配与核验
```

### 对架构

```text
JSON 仍保留机器契约价值，但退出用户主界面
```

---

# 22. 推荐实施顺序

最终排序：

```text
P0-1  MODELING_PLAN.md
P0-2  AI usage unknown/none/used
P0-3  AI_USAGE_LEDGER + disclosure renderer
P0-4  W1 deliverables / appendix planning
P1-1  PROJECT_BRIEF.md
P1-2  PAPER_OUTLINE.md
P1-3  harness prepare M1/W1/W2/S1
P1-4  .harness hidden internal state
P1-5  submission staging
P1-6  Draw.io archetype system
P2-1  domain/index/dimension executor
P2-2  selective rerun
P2-3  sensitivity orchestration
P2-4  capability benchmark
```

---

# 23. 一句话原则

> **下一阶段不要继续把 Harness 做成“更严的 JSON 审计系统”，而要把已经很强的证据链包装成真正可用的数模研究与写作工作流。**

更具体地说：

> **Machine state stays structured; human work becomes document-first.**
