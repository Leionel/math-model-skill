# Review Execution Plane（P0）改进实施方案

> 历史规划快照：本文包含实施前拟议项，不代表当前已实现能力。2026-08-20
> 可靠性复核后的事实边界以 [REVIEW_EXECUTION_DESIGN.md](REVIEW_EXECUTION_DESIGN.md)
> 和 [WP3_TEST_REPORT.md](WP3_TEST_REPORT.md) 为准；其中自动 revision loop、
> OS sandbox、finding-history 单调性与 decision memo 仍未实现。

日期：2026-08-17
依据：`math_model_harness_prompt_v4_oss_scoped.md`（v4 OSS-Grounded Review Execution Prompt）
范围：仅 P0 — Review Execution Plane。不实现 P1/P2/P3，不 commit，不 push。

---

## 0. 文档定位

本文档是 v4 prompt 的**实施前设计蓝图**（design delta），基于当前未提交的 Manifest v2 工作区的真实代码现状，给出 `harness review` 及其配套机制的详细改进方案。实施完成后，本文档的结论应沉淀为：

- `docs/REVIEW_EXECUTION_DESIGN.md`（正式设计文档）
- `docs/WP3_IMPLEMENTATION_REPORT.md`
- `docs/WP3_TEST_REPORT.md`

本轮唯一主目标：

```
Make Review Executable
review declarative → review executable
```

即：Reviewer 从 schema / references / Gate 条件中的"字段"，变成一个**真实执行、产生 evidence、可被 status 看见、能阻止错误论文进入 W2 PASS** 的流程。

---

## 1. 现状盘点（基于代码证据）

### 1.1 已完成的基础（与 prompt §0 一致，确认存在）

| 基础 | 证据位置 |
|---|---|
| Manifest v2（profile / execution fact / artifact projection / control decision 单一 ownership） | [runtime_state.py](../scripts/runtime_state.py)、[MANIFEST_V2_DESIGN.md](MANIFEST_V2_DESIGN.md) |
| 三 preset 收敛（sprint/research/submission） | [capabilities.py](../scripts/profiles/capabilities.py) `PRESETS`、[harness.py](../scripts/harness.py) `PRESETS` |
| Gate 依据真实 receipt / artifact bytes / DAG freshness / human checkpoint 重算 | [v2_gate_runtime.py](../scripts/v2_gate_runtime.py) `_v2_gate` |
| Hash / Integrity Policy（freeze 绑定、canonical digest owner、DAG 漂移检测） | [v2_gate_runtime.py](../scripts/v2_gate_runtime.py) `_v2_require_dag_digests`、[freeze_results.py](../scripts/freeze_results.py) |
| 统一 CLI：init/status/check/run/validate/freeze/profile/doctor/migrate | [harness.py](../scripts/harness.py) `build_parser` |
| `harness run --stage review` 已是合法 receipt stage | [harness.py](../scripts/harness.py#L481) stage choices 含 `review` |
| Semantic Critic rubric（含回执 JSON 格式示例） | [semantic_critic_rubric.md](../references/review/semantic_critic_rubric.md) |
| Revision policy（bounded 2 轮、finding 稳定 ID、Reviewer 不改作者 artifact） | [revision_policy.md](../references/review/revision_policy.md) |
| judge-scan（结构化启发式扫描，issue-only、不打分） | [check_paper_style.py](../scripts/qa/check_paper_style.py#L28) `judge_scan()`，经 `run_deterministic_qa --judge-scan` 触发 |
| precedents 隔离、battle/ 不可改、SKILL.md ~188 行 | 目录结构确认 |

### 1.2 核心缺口（review declarative ≠ review executable）

| # | 缺口 | 代码证据 | 对应 P0 |
|---|---|---|---|
| G1 | **没有 `harness review` 命令**。用户没有任何入口触发 review 流程 | [harness.py](../scripts/harness.py) `build_parser` 无 review 子命令 | P0-A |
| G2 | **v2 W2 Gate 完全不消费 review evidence**。W2 只做 DAG freshness、frozen hash 复算、deterministic QA、contracts、checkpoint、safety——一个 v2 项目可以在没有任何 semantic/judge review 的情况下通过 W2 | [v2_gate_runtime.py](../scripts/v2_gate_runtime.py#L639-L777) `elif gate == "w2"` 全分支无 review 读取 | P0-I |
| G3 | **Semantic Critic 只有 rubric，没有执行器**。无 schema、无报告校验、无 artifact 绑定、无 freshness，且未接入 v2 Gate | [semantic_critic_rubric.md](../references/review/semantic_critic_rubric.md) 仅为 markdown；schemas/ 无对应 schema | P0-B/E |
| G4 | **judge-scan 是确定性启发式 warning，不是 Judge Lens**。issue 无 finding contract（无 severity 分级契约/required_fix/status）、无 artifact 绑定、仅并入 warnings | [check_paper_style.py](../scripts/qa/check_paper_style.py#L194) `warnings.extend(...)` | P0-C |
| G5 | **无 review_mode / independence_level 模型**。v1 遗留路径按 `reviewer.profile`（sprint/final_submission/award_max）+ blind reviewer **数量**定义独立性，正是 v4 明令禁止的语义 | [check_gates.py](../scripts/qa/check_gates.py#L1264-L1274) `required_blind` 计数逻辑（仅 v1 路径） | P0-D |
| G6 | **无 fresh-context information boundary**。不存在 review bundle / allow-deny 清单，fresh review 无从建立也无法验证 | 全仓无 bundle 相关实现 | P0-D |
| G7 | **review report 不是 generated evidence**。无落盘约定、无 DAG 注册、无 receipt 绑定 | schemas/ 29 个 schema 中无 review report schema（[visual_review_receipt.schema.json](../schemas/visual_review_receipt.schema.json) 为最近似先例但面向 visual review） | P0-E |
| G8 | **无 review freshness 机制**。paper 修改后旧 review 仍会被视为有效（v1 `verify_review` 只校验报告文件自身 hash，不校验被审 artifact 是否变化） | [check_gates.py](../scripts/qa/check_gates.py#L485-L576) | P0-F |
| G9 | **status 不可见 review**。`_v2_status` 只投影 gates/checkpoints/receipts/DAG/next_action | [harness_status.py](../scripts/harness_status.py#L198-L243) | P0-G |
| G10 | **bounded revision 无实现**。revision_policy.md 无代码承载；v1 仅校验 `revision.loop/cap` 数值范围 | [check_gates.py](../scripts/qa/check_gates.py#L1296-L1308) | P0-H |
| G11 | **无 review E2E / 测试**。无任何测试证明 reviewer 真实执行 | tests/ 无 review 执行测试 | P0-J |

### 1.3 结论

现有实现的 review 语义分散在三处且互不连通：v1 manifest 的 `reviewer.*` 自报字段（legacy）、`run_deterministic_qa --judge-scan` 的启发式 warning、两份 markdown policy。**缺的不是规则，而是执行面（Execution Plane）**：一个把 Draft → Deterministic QA → Semantic Critic → Judge Lens → Findings → Revision → Recheck → W2 PASS 串起来、且每一步留下可验证 evidence 的运行通道。

---

## 2. 架构原则与红线

必须持续满足（prompt §3 / §36）：

```
Many possible workers
One control plane
One artifact graph
One evidence truth
One gate engine
```

- reviewer role ≠ canonical state owner。Reviewer 不得改 Manifest truth、不得直接 PASS Gate、不得改 frozen results、不得改作者论文并自我验收、不得创建第二套 review registry / artifact DAG / evidence truth。
- deterministic checker → PASS/FAIL；语义问题 → finding + severity + recommendation + human judgment。**禁止 LLM says PASS → deterministic gate PASS**。
- 不做 consensus theater：无 majority vote、无平均分、无 chief reviewer。
- Multi-Agent optional，Review semantic mandatory：backend 不支持 subagent 时 harness 必须仍可用（L0 fallback + 显式 degraded 标记）。
- Root SKILL.md 保持精简（目标 ≤ ~200 行），review 细节进 `references/review/`，确定性操作进 `scripts/`。

反模式对照（实施中每完成一个 P0 项即自查）：reviewer_state.json（禁止）、每个 perspective 一个新 schema（禁止）、manifest review status 作为 truth（禁止）、same model 换 persona 冒充 independent（禁止）、reviewer 改论文后自我通过（禁止）、paper 变更后旧 review 仍有效（禁止）。

---

## 3. 总体设计

### 3.1 W2 Review Lifecycle（目标状态）

```
Draft (paper/abstract/conclusion, W1 产物)
   ↓
[1] Deterministic QA            ← 复用 run_deterministic_qa.py（机器可判定部分）
   ↓
[2] Review Bundle 构建           ← 新增：allow 清单物化为 reports/review/bundle/<ts>/
   ↓
[3] Semantic Critic             ← 执行者: current agent(L0) / subagent(L1) / 他模型(L2) / 人(L3)
   ↓
[4] Judge Lens                  ← 复用升级 judge_scan 结构化结果 + agent 阅读评审
   ↓
[5] Review Report(s)            ← GENERATED_EVIDENCE, 落盘 reports/review/ + DAG 注册
   ↓
[6] Report 确定性校验            ← schema / 绑定 / freshness / verdict-finding 一致性 / independence 一致性
   ↓
[7] Findings → Targeted Revision（bounded ≤2 轮，作者侧执行）
   ↓
[8] Re-check（受影响 QA + review recheck）
   ↓
W2 PASS（Gate 从真实 report + freshness 重算，绝不读 manifest 自报）
```

### 3.2 组件与数据流

```
harness review (thin CLI, 复用 _dispatch 模式)
        ↓
scripts/qa/run_review.py        ← 新增：唯一 review 编排器
  ├─ Phase 1  dispatch run_deterministic_qa.py          （复用）
  ├─ Phase 2  build review bundle（allow-list 物化拷贝 + bundle manifest）
  ├─ Phase 3  执行 perspectives：
  │     L0 self_critic   → 输出 agent 路由指令（rubric 路径 + 报告落盘路径）
  │     L1 fresh_context → 产出 task package；有 backend 命令时经
  │                         run_and_record.py --stage review 真实执行并捕获 receipt
  │     L2/L3            → 同一 seam，外部产出报告
  ├─ Phase 4  校验报告（schemas/review_report.schema.json + 绑定/一致性规则）
  ├─ Phase 5  报告落盘 reports/review/ + 追加 artifact DAG 节点(role=review_report)
  └─ Phase 6  输出 human-readable 摘要（severity 计数 + W2 预判 + next finding）

v2_gate_runtime._v2_gate("w2")   ← 修改：新增 _v2_review_evidence() 消费真实报告
harness_status._v2_status        ← 修改：新增 _review_view() 投影
```

关键点：`run_review.py` 是**确定性编排器与校验器**，本身不做语义判断。语义判断由 reviewer（agent/subagent/他模型/人）依据 rubric 完成，但 reviewer 产出的报告必须通过 run_review/Gate 的确定性校验才能成为有效 evidence。

### 3.3 复用映射表（prompt §30）

| 需求 | 复用 | 增量 |
|---|---|---|
| 触发入口 | [harness.py](../scripts/harness.py) thin-dispatch 模式 | `review` 子命令（~40 行） |
| 确定性 QA | [run_deterministic_qa.py](../scripts/qa/run_deterministic_qa.py) | 0（直接 dispatch） |
| Judge 结构扫描 | [check_paper_style.py](../scripts/qa/check_paper_style.py) `judge_scan()` | 输出从 warnings 升级为 bundle 内结构化输入（函数本身少改） |
| Critic 规则 | [semantic_critic_rubric.md](../references/review/semantic_critic_rubric.md) | 增补 independence/binding 字段说明 |
| Revision 规则 | [revision_policy.md](../references/review/revision_policy.md) | 增补 recheck 语义 |
| 执行 receipt | [run_and_record.py](../scripts/run_and_record.py)（stage=review 已合法） | 0 |
| Artifact 注册 | artifact DAG（role 机制 + digest owner 规则） | 新 role：`review_report` |
| Freshness | canonical digest owner + DAG projector | 报告仅引用 artifact_id/digest，Gate 重算 |
| Gate 消费 | [v2_gate_runtime.py](../scripts/v2_gate_runtime.py) `_v2_run_checker`/`_v2_require_dag_digests` 模式 | `_v2_review_evidence()` |
| Status 投影 | [harness_status.py](../scripts/harness_status.py) 视图函数模式 | `_review_view()` |
| 报告先例 | [visual_review_receipt.schema.json](../schemas/visual_review_receipt.schema.json)（issues/severity/status 契约风格） | 新 schema 1 个（见 §5.5 论证） |

---

## 4. 详细设计

### 4.1 P0-A — `harness review` CLI

新增子命令（唯一的 CLI surface 增量，prompt §29）：

```
harness review                     # 按 preset 推导 required perspectives
harness review --json              # 机器可读输出
harness review --semantic          # 仅 semantic critic
harness review --judge             # 仅 judge lens
harness review --fresh             # 强制 fresh-context（L1）路径
harness review --recheck           # 不重跑 reviewer，仅重校验已有报告
                                   # （freshness/verdict/finding 一致性）
```

实现要点：

- [harness.py](../scripts/harness.py) 新增 `_review(args)`，与 `_check`/`_validate` 同构：resolve root/manifest → dispatch `scripts/qa/run_review.py`，子进程 stdout/stderr/exit code 透传，CLI 不解释 review 结果。
- 参数仅 `--project/--manifest/--json` + 上述 5 个 flag，遵循 one obvious command per user intent。
- **不新增** `harness reviewer/critic/judge/blind-review/review-manager`。

默认 perspective 推导（prompt §5.1）：

| preset | 默认执行 |
|---|---|
| sprint | deterministic QA + semantic critic（L0 allowed） |
| research | deterministic QA + semantic critic + judge lens（L1 preferred，L0 fallback 须显式 degraded） |
| submission | research 全部 + 至少一个 independence_level ≥ L1 的 review |

### 4.2 P0-B — Semantic Critic 执行

职责边界（rubric 已定义，不重复建规则）：research correctness / semantic integrity；**不是** formatting beautifier；**不得**输出 deterministic PASS 替代 checker。

执行路径：

1. `run_review.py` 将 allow-list 输入（problem snapshot、model contract、frozen results、evidence registry、paper/abstract/conclusion、presentation contract、judge_scan 结构化结果等）物化进 bundle；
2. 按 review_mode 分派：
   - `self_critic`（L0）：CLI 输出路由指令——当前 agent 加载 [semantic_critic_rubric.md](../references/review/semantic_critic_rubric.md)，读 bundle，将报告写到约定路径 `reports/review/semantic-<runid>-<ts>.json`；
   - `fresh_context`（L1）：生成 task package（bundle 路径 + rubric 路径 + 输出路径 + 输出 schema），由 subagent/backend 执行；
   - `independent_model`（L2）/`human`（L3）：同一 task package seam，外部产出。
3. 报告落盘后由 Phase 4 确定性校验（见 §4.5/§4.6）。

检查面以 rubric 现有 9 条为基础，映射 prompt §8 最低检查项（problem→model alignment、assumptions、variable semantics、decision-time information set、objective identity、constraint semantics、implementation consistency、validation sufficiency、leakage、sensitivity、baseline comparison、unsupported optimality、causal overclaim、conclusion boundary、claim→evidence binding、paper→frozen result consistency 等）——**只增补 rubric 文本中缺失的条目，不新建文件**。

### 4.3 P0-C — Judge Lens 执行（升级 judge-scan，不建第二套）

现状：`judge_scan()` 是确定性结构启发式（摘要 decisive number 可见性、model identity 可见性、validation 可发现性、figure placement），结果仅并入 warnings。

升级方案：

1. **保留** `judge_scan()` 确定性部分原位不动（它是 Judge Lens 的结构化输入，不是 Judge Lens 本身）；
2. `run_review.py` 将 `judge_scan` 结构化输出（issues + manual_checks_required）放入 review bundle，作为 Judge Lens 的 pre-seed candidate findings；
3. Judge Lens reviewer（agent/subagent/人）依据新 reference `references/review/judge_lens.md`（prompt §9 的 12 项检查面：小问完整回答、摘要快速暴露模型/核心结果/主要结论、关键贡献可发现、复杂度收益、图表降阅读成本、结论可定位、创新点有 evidence、"工作多重点不清"风险、评委可见硬伤、figure-narrative 一致、abstract-正文一致）产出 findings；
4. 默认 issue-only：**禁止**官方评分/国一概率/获奖概率/虚构 judge score（无真实评分合同前）。

`references/review/` 最终只保留 3 个文件：`semantic_critic_rubric.md`、`judge_lens.md`、`revision_policy.md`（prompt §27，不出现 reviewer.md/review_policy.md 等重复文件）。

### 4.4 P0-D — Fresh Review 信息边界与独立性

#### 4.4.1 review_mode / independence_level（prompt §6）

```
review_mode:         self_critic | fresh_context | independent_model | human
independence_level:  L0_same_context | L1_fresh_context | L2_independent_model | L3_human
```

合法映射（校验规则，Gate 与 run_review 共用）：

| review_mode | 允许的 independence_level |
|---|---|
| self_critic | 仅 L0_same_context |
| fresh_context | 仅 L1_fresh_context |
| independent_model | 仅 L2_independent_model |
| human | 仅 L3_human |

规则：`self_critic` 声称 L1/L2 → 校验失败（测试 N）；same-context 标记 independent_model → FAIL。research 下 L0 fallback 合法但报告必须带 `degraded_independence: true` 且 status 中可见 "degraded independence"；submission 不接受 L0 满足独立性要求。

#### 4.4.2 Review Bundle（物理边界，不靠 prompt 承诺）

fresh review 的 information boundary 通过**物化拷贝**实现，而非"请假装第一次看到"：

```
reports/review/bundle/<runid>-<ts>/
  bundle_manifest.json      # artifact_id / role / path / sha256 / copied_at
  problem_snapshot.json     # ALLOW
  rules_ref.md              # ALLOW（relevant competition rules 引用）
  model_contract.json       # ALLOW
  frozen_results.json       # ALLOW
  evidence_registry.json    # ALLOW（verified evidence）
  paper/ abstract/ conclusion/   # ALLOW（当前 manuscript）
  figures/…                 # ALLOW（必要图表）
  judge_scan_structural.json     # ALLOW（结构化输入）
```

DENY BY DEFAULT（即**不拷贝**进 bundle，天然不可见）：writer private reasoning、旧 reviewer reasoning、previous semantic/judge verdict、revision negotiation、unrelated drafts、session logs、hidden chain-of-thought。

- bundle_manifest.json 即 prompt §7 的"最小 review bundle manifest"，字段复用现有 artifact ref 风格（path + sha256 + artifact_id）；
- fresh 报告必须引用其消费的 bundle（`bundle_ref`），校验时验证 bundle 内容不含 deny 类产物（按路径约定检查 reports/、writer_package 的 reasoning 字段等可机械识别项）——含 previous verdict → independence 声明无效（测试 M）；
- 现有 artifact ref 能表达的字段一律复用，不建 input database。

#### 4.4.3 执行 backend 最小 seam（prompt §19）

Review Resolver 仅三类执行路径：`current_context` / `fresh_context` / `external_reviewer`。

- 当前 runtime 支持 subagent → L1 用 subagent；
- 不支持 → research 可 L0 fallback（显式 degraded），submission 要求 human 或其他 L1 路径；
- 为测试与未来 P2 worker 保留唯一 seam：`run_review.py --backend-cmd "<command>"`，backend 命令经 `run_and_record.py --stage review` 执行并捕获 process receipt。**不实现** Worker SDK / Agent Registry / orchestration graph / general plugin system。

### 4.5 P0-E — Review Report 作为 GENERATED_EVIDENCE

#### 4.5.1 Schema 增量：+1（统一 review_report.schema.json）

论证（prompt §28 要求解释为何现有 schema 不能表达）：

- 现有 29 个 schema 中，唯一带 issues/severity/status 契约的是 [visual_review_receipt.schema.json](../schemas/visual_review_receipt.schema.json)，但其绑定对象是 pdf_visual_qa/paper 的视觉审查，无 perspective、无 review_mode/independence_level、无 reviewed_artifacts 多 artifact 绑定、无 bundle_ref，扩展它反而制造视觉/语义混杂；
- run_manifest v1 的 `reviewer` 是自由 object（[run_manifest.schema.json](../schemas/run_manifest.schema.json#L157)），是自报状态而非 generated evidence；
- semantic_critic_rubric.md 中的回执示例缺少 finding contract 必需字段（evidence_locator/affected_artifact/affected_claim_id/confidence/status）与独立性字段。

因此新增**一个统一 schema**（所有 perspective 共用，anti-pattern 2 禁止每 perspective 一个）：

```json
{
  "schema_version": "1.0",
  "report_id": "REV-<runid>-<seq>",
  "run_id": "...", "project_id": "...",
  "perspective": "semantic_critic | judge_lens",
  "review_mode": "self_critic | fresh_context | independent_model | human",
  "independence_level": "L0_same_context | L1_fresh_context | L2_independent_model | L3_human",
  "degraded_independence": false,
  "reviewed_at": "<ISO-8601>",
  "reviewed_artifacts": [
    {"artifact_id": "...", "role": "paper", "path": "paper/main.tex", "sha256": "<review 时 digest>"}
  ],
  "bundle_ref": {"path": "reports/review/bundle/.../bundle_manifest.json", "sha256": "..."},  // L1+ 必填
  "execution_receipt_ref": {"receipt_id": "...", "path": "..."},                              // 有 backend 时必填
  "findings": [
    {
      "finding_id": "REV-W2-003",
      "perspective": "semantic_critic",
      "severity": "blocker | high | medium | low",
      "summary": "...",
      "evidence_locator": "paper/main.tex#abstract / frozen_results.results[2]",
      "affected_artifact": "paper/main.tex",
      "affected_claim_id": null,
      "required_fix": "...",
      "confidence": "low | medium | high",
      "status": "open | resolved | accepted_risk | superseded"
    }
  ],
  "verdict": "pass | fail",
  "superseded_by": null
}
```

#### 4.5.2 落盘与注册

- 路径约定：`reports/review/semantic-<runid>-<ts>.json`、`reports/review/judge-<runid>-<ts>.json`（文件数不是目标，统一目录便于发现；一个 unified report 的取舍在实施时若更简单可收敛为单文件，但**不建第二 canonical review ledger**）；
- 每份有效报告追加为 artifact DAG 节点：`role=review_report`、`producer_id=harness.review`、`dependencies=[被审 artifact_id 列表]`、`digest_owner=artifact_dag`、`lifecycle=generated_evidence`；
- 执行事实：reviewer 经 backend 执行时由既有 command receipt（stage=review）拥有 argv/exit_code/时间戳；无 backend（L0/L3）时报告自身的 execution metadata 记录 mode 与 reviewed_at，**不伪造 receipt**；
- **Manifest v2 增量：0**。不加 `review` 字段、不加 reviewer_state；发现渠道 = DAG role（首选）+ `reports/review/` 约定目录（兼容）。Manifest 最多可选增加 `roots.review_reports` 引用（prompt §11 允许的 "review root/reference"），仅在实施中发现 DAG 发现不足时启用。

### 4.6 P0-F — Review Freshness

机制（prompt §15：报告只引用，Gate 重算）：

1. 报告在 `reviewed_artifacts` 中记录被审 artifact 的 `artifact_id + sha256`（review 时刻值）——这是**引用**，不是第二套 digest truth；
2. Gate/`--recheck` 重算：取被审 artifact 的**当前 canonical digest**（`digest_owner=artifact_dag` 节点或 producer receipt，复用 `_v2_require_dag_digests` 的解析逻辑）；
3. 当前 digest ≠ 报告记录 digest → `stale` → 该报告不得用于 W2（测试 O）；
4. 旧报告被新报告取代：新报告落盘时将同 perspective 旧报告标记 `superseded_by`（同目录文件内字段更新，属 generated evidence 自身演化，非 manifest truth 变更）。

paper v1 → review PASS → paper v2 的场景由上述规则天然覆盖；frozen result 被修改则触发既有 DAG invalidation + 本规则双重失效。

### 4.7 P0-G — harness status 可见性

[harness_status.py](../scripts/harness_status.py) 新增 `_review_view(state)`，与 Gate 用**同一套**报告发现/校验逻辑（抽公共函数，避免两套判断）：

`harness status`（human）新增块：

```
W2:
  deterministic_qa     PASS
  semantic_review      FAIL
      blocker: 0  high: 1  medium: 3
      independence: L1_fresh_context
      freshness: current
  judge_review         PASS
      freshness: current
  revision             REQUIRED

Next:
  REV-W2-003 — Abstract claims global optimality, but current evidence
  only supports superiority over the tested baseline.
```

`--json` 输出结构化 review summary：per-perspective {executed, severity_counts, independence_level, degraded, freshness, verdict}、open blocker/high 列表、next_finding。不要求用户打开 manifest。

### 4.8 P0-H — Bounded Revision Loop

复用 [revision_policy.md](../references/review/revision_policy.md) 规则，实现为**报告历史的确定性推导**（不加 canonical state）：

- 上限：最多 2 轮自动修订；自动处理优先级 blocker > high > conclusion-changing medium；不做无界润色；
- finding ID 稳定：同 perspective 修订前后报告重校验时，未解决的 finding 必须沿用原 finding_id（run_review 校验：新报告中找不到旧 open blocker/high 的同 ID 或显式 resolved/superseded 状态 → 报错）；
- 修订后只重跑受影响检查：`harness review --recheck` = 重校验报告绑定/freshness + 重跑受影响 deterministic QA 子集（最小实现：重跑 W2 deterministic QA，因当前 QA runner 不支持子集选择——记录该限制）；
- 停止条件：一轮修订后 blocker+high 未严格减少 → 输出 decision memo（报告摘要），停止自动循环，交还用户（SKILL 路由指引）；
- frozen result / model contract / objective 被修订触碰 → 既有 DAG invalidation 生效，W2 退出回到相应更早 Gate（prompt §22）；
- 修订是**作者侧**动作：Reviewer 只 inspect/identify/explain/require fix；代码层面 run_review.py 不存在任何写 paper/frozen/model contract 的路径（mutation boundary 由代码结构保证）。

### 4.9 P0-I — W2 Gate 消费真实 Review Evidence

修改 [v2_gate_runtime.py](../scripts/v2_gate_runtime.py) `_v2_gate("w2")`，在 deterministic QA 之后新增 `_v2_review_evidence(state, capabilities, evidence, errors)`：

**输入发现**：DAG role=`review_report` 节点（+ 兼容 `reports/review/` 目录扫描，仅读）。

**逐报告确定性校验**（任何一条失败 → 该报告无效）：

1. schema 校验（review_report.schema.json）；
2. 绑定校验：`reviewed_artifacts` 中每个 artifact 存在且 digest 与 review 时记录一致（ freshness，§4.6）；
3. verdict/finding 一致性：`verdict=pass` 但存在 open blocker/high → FAIL（测试 K）；
4. independence 一致性：mode↔level 映射合法（§4.4.1）；L1+ 报告必须有合法 bundle_ref 且 bundle 无污染（测试 M/N）；
5. finding 状态：open blocker/high 存在 → W2 FAIL；open medium 需 resolved 或 accepted_risk（accepted_risk 须有 justifier 记录）。

**Preset 要求重算**（不信任任何自报）：

| preset | W2 review 条件 |
|---|---|
| sprint | ≥1 份 current semantic_critic 报告（L0 可） |
| research | semantic + judge 各 ≥1 份 current；semantic 允许 L0 fallback 但须 degraded 标记（warning + status 可见，不 FAIL） |
| submission | research 条件 + ≥1 份 current 报告 independence_level ≥ L1 |

报告缺失/stale/artifact mismatch/verdict 冲突 → W2 FAIL（测试 A/D/L）。同时保持既有 v1 路径行为不变（v1 legacy 项目不迁移则不受影响）。

**显式清理**：v2 路径下，[check_gates.py](../scripts/qa/check_gates.py) v1 分支的 `reviewer.blind_reviewers` 数量语义**不进入 v2**；v1→v2 迁移时 `reviewer.*` 标记 deprecated，不映射、不自动 pass（见 §6）。

### 4.10 P0-J — 测试计划

#### 4.10.1 单元/集成测试（prompt §24 A–Q 全覆盖）

新增 `tests/test_review_execution.py`：

| 用例 | 验证 | 手段 |
|---|---|---|
| A | research 无 semantic 报告 → W2 FAIL | 构造 v2 fixture 项目，跑 `_v2_gate("w2")` |
| B | semantic 有 open high → W2 FAIL | 报告 fixture |
| C | high resolved + re-review current → W2 允许 PASS | 报告状态流转 |
| D | 报告 stale → W2 FAIL | 修改 paper 后 recheck |
| E | sprint 不强制 Judge Lens | preset 推导 |
| F | research 强制 Judge Lens | 同上 |
| G | submission 需 ≥1 份 L1+ current | independence 校验 |
| H | self_critic 不得冒充 L1/L2 | mode↔level 映射校验失败 |
| I | reviewer 改 frozen artifact → integrity invalidation | 触发既有 digest 漂移检测 |
| J | 手改 manifest semantic_review=pass 但无真实报告 → FAIL（v2 根本不读该字段，测试固化此语义） | 手改 manifest |
| K | verdict=pass 但有 open blocker/high → FAIL | 一致性校验 |
| L | artifact binding mismatch → FAIL | 报告绑定错误 digest |
| M | fresh bundle 含 previous verdict → independence 无效 | bundle 污染检测 |
| N | same-context 标记 independent_model → FAIL | 同 H 的反面 |
| O | paper 变更后旧 review stale | 同 D |
| P | status 暴露 review summary | `_review_view` 断言 |
| Q | review 产出真实 review artifact | DAG 节点 + 文件存在 |

#### 4.10.2 E2E（prompt §23，real，非 mock pass）

新增 `tests/test_review_e2e.py`，用**确定性 stub reviewer**（tests fixture 脚本）经 `--backend-cmd` seam + `run_and_record --stage review` 真实执行——验证的是 Execution Plane（receipt、报告 artifact、DAG 注册、Gate 消费），不是 LLM 评审质量（后者按 §25 以 observed behavior 记录）：

- **E2E-A Semantic Finding**：init 最小 case → 最小 contract → tiny execution → validation → freeze → 含一处故意 semantic overclaim 的手稿 → `harness review` → stub critic 产出含该 finding 的报告 → W2 FAIL；
- **E2E-B Revision/Recheck**：修复 claim → 受影响 QA → recheck → finding resolved → W2 PASS；
- **E2E-C Stale Review**：paper v1 → review PASS → paper v2 → 旧 review stale → W2 FAIL；
- **E2E-D Fresh Boundary**：验证 fresh reviewer 收到的 bundle 仅含 allow 集合，不含 previous verdict/writer reasoning/revision discussion；污染 → independence_level 不能为 L1。

#### 4.10.3 回归

- 既有 352 用例全量回归必须通过；`harness review` 不改变任何既有 Gate 语义（W2 v2 路径新增的是"以前缺失的必要条件"，需同步更新受影响的既有 fixture：为现有 W2 测试项目补最小合法 review 报告 fixture）；
- schemas 29+1 全部 parse；Skill Creator 校验仍 valid；`git diff --check` pass。

#### 4.10.4 Skill 级验证（§25）

修改 SKILL.md / rubric / revision_policy / judge_lens 时，逐条记录：observed failure → before → after → regression；新增规则前回答四问（哪个 observed failure 需要它/现有 instruction 为何不够/test 如何证明/token 负担）。**No new mechanism without an observed failure.**

---

## 5. State / Schema / CLI 复杂度预算核对

| 维度 | 目标 | 本方案 |
|---|---|---|
| profile dimension | +0 | 达成（perspective 由 preset 直接推导，无新 capability 维度、无 review profile matrix） |
| canonical state | +0 | 达成（manifest 不加字段；报告为 GENERATED_EVIDENCE；revision 状态由报告历史推导） |
| top-level Gate | +0 | 达成（仍为 M1/P1/P2/W1/W2/S1；review 是 W2 的输入证据，不是新 Gate） |
| schema | preferably +0 | **+1**（review_report.schema.json，论证见 §4.5.1；禁项 review_manifest/review_registry/reviewer_state/worker_registry 等均不新增） |
| CLI | 仅 `harness review` | 达成（无 inspect-review/reviewer-status 等衍生命令；详细 trace 由 `status --json` 承载） |
| Root SKILL.md | ≤ ~200 行 | 计划净增 ~10–15 行（review 路由 + CLI 一行 + reference 链接） |

---

## 6. 迁移与兼容

1. **v1 项目**：legacy check_gates 路径保持现状（含 `reviewer.*` 校验），不做语义升级——v1 的 blind reviewer 数量语义止步于 v1；
2. **v1→v2 迁移**（[migrate_v1_to_v2.py](../scripts/migrate_v1_to_v2.py)）：`reviewer.*` 标记 `deprecated`，提示迁移后需重新执行 `harness review`；不映射 blind_reviewers、不自动生成 independence 声明；
3. **存量 v2 项目**（无 review 报告）：`harness check W2` 将因缺少 review evidence 而 FAIL——这是**预期行为**（review 从可选变必需），在 MIGRATION_GUIDE 与 README 中显式说明补跑 `harness review` 的路径；
4. README / MIGRATION_GUIDE_V1_TO_V2 增补 review 章节（少量段落，不建平行文档）。

---

## 7. SKILL.md 与 references 增量

- [SKILL.md](../SKILL.md)：W2 小节补 2–3 句（review 是 W2 必需输入 + `harness review` 一行）；CLI quick start 补 1 行；progressive disclosure 链接补 review router 条目。合计 ~10–15 行；
- [router.md](../references/router.md)：新增 review 条目指向 3 个文件；
- `references/review/judge_lens.md`：新建（§4.3 的 12 项检查面 + issue-only 边界）；
- `semantic_critic_rubric.md` / `revision_policy.md`：增补字段说明与 recheck 语义，不重复 judge_lens 内容。

---

## 8. 实施顺序（严格遵循 prompt §39）

| STEP | 内容 | 产出/验收 |
|---|---|---|
| 1 | 检查未提交 diff，确认 Manifest v2 / profile resolver / CLI / DAG / receipt / rubric 真实存在 | 本文档 §1.1 已核对；实施时复核 DAG 节点追加的既有写入口径 |
| 2 | Design delta 定稿 | 本文档 → 沉淀为 docs/REVIEW_EXECUTION_DESIGN.md 骨架 |
| 3 | 实现 `harness review`（CLI + run_review.py Phase 1/5/6 最小闭环） | P0-A |
| 4 | 接 Semantic Critic / Judge Lens / fresh bundle（Phase 2/3） | P0-B/C/D |
| 5 | 报告绑定 / freshness / W2 重算（Phase 4 + `_v2_review_evidence`） | P0-E/F/I |
| 6 | 更新 harness status | P0-G |
| 7 | 单元/集成测试 A–Q | P0-J 部分 |
| 8 | 真实 Review E2E A–D | P0-J 部分 |
| 9 | 全量既有回归 + schemas + Skill Creator + git diff --check | §4.10.3 |
| 10 | 更新三份文档 | REVIEW_EXECUTION_DESIGN / WP3_IMPLEMENTATION_REPORT / WP3_TEST_REPORT |
| 11 | Final report（§40 格式） | **不 commit、不 push** |

---

## 9. 验收清单（commit 前逐项回答，prompt §35）

1. 有 `harness review`？→ §4.1
2. 真实执行 review 而非只改 manifest 状态？→ §3.2/§4.10.2（v2 路径不读 manifest review 字段）
3. Semantic Critic 产生 findings？→ §4.2/§4.5.1 finding contract
4. Judge Lens 真实运行？→ §4.3（judge_scan 结构化输入 + lens 评审）
5. research W2 要求 current semantic + judge？→ §4.9 表
6. submission 要求 ≥L1 independence？→ §4.9 表
7. self-critic 不伪装 independent？→ §4.4.1 映射校验（测试 H/N）
8. Reviewer 无法直接修改作者 artifact？→ §4.8（run_review 无作者 artifact 写路径）
9. paper 修改后旧 review stale？→ §4.6（测试 D/O）
10. W2 从真实 report/freshness 重算？→ §4.9
11. manifest 手改 pass 无效？→ §4.9（测试 J）
12. open blocker/high 阻止 W2？→ §4.9（测试 B/K）
13. status 可见 reviewer state/severity/independence/stale/next？→ §4.7（测试 P）
14. 无新增顶层 R1 Gate？→ §5
15. 仍为 M1/P1/P2/W1/W2/S1？→ §5
16. preset 仍只有三个？→ §5
17. 无 review profile matrix？→ §5
18. canonical state +0？→ §5
19. schema 尽量 +0（实际 +1 已论证）？→ §4.5.1
20. Root SKILL 仍精简？→ §7
21. existing regression 全过？→ §4.10.3
22. Review E2E 证明 reviewer executes？→ §4.10.2
23. Future P1/P2/P3 未顺手实现？→ §10

---

## 10. 明确不做（Deferred）

| 优先级 | 内容 | 备注 |
|---|---|---|
| P1 | generic resume/retry framework、trajectory engine、context-map runtime、generic approval engine、clean-process overhaul | 记录需求即可 |
| P2 | full Worker Adapter、general multi-agent orchestration、candidate-generation agents、adversarial review swarm、provider capability router | 本轮只留 `--backend-cmd` 单 seam |
| P3 | skill benchmark、skill optimization、SkillOpt-style evolution、skill registry、source-grounded auto-skill generation | 包括 with/without-skill benchmark |

实施中若发现"顺便可以做 X"：**停止，记入本文档 §10 或 Future Roadmap，不实现**。

---

## 11. 风险与开放问题

1. **DAG 节点追加口径**：当前 scripts/ 中 DAG 节点主要由 init 创建、projector 只读投影；实施 STEP 1 需确认 review_report 节点追加的规范写入口径（直接 append artifact_dag.json vs 复用 projection 工具），原则是不破坏 digest owner 单一性；
2. **QA 子集重跑**：run_deterministic_qa 不支持按 finding 影响面选择子集，本轮 `--recheck` 采用整跑 W2 QA 并在 WP3 报告记录该限制（不做 generic retry engine）；
3. **bundle 污染检测的机械化边界**：previous verdict/writer reasoning 的识别依赖路径与字段约定（reports/review/、writer_package.reasoning 等），无法覆盖任意自由文本——测试 M 覆盖约定路径，WP3 报告如实声明检测边界；
4. **存量 v2 项目 W2 语义收紧**：无 review 报告的存量项目 W2 将 FAIL（预期），需在 README/迁移指南显著说明，避免误判为回归 bug；
5. **E2E 中 LLM 评审质量**：E2E 用 stub reviewer 证明 Execution Plane；真实评审质量属 Skill-level 行为，按 §25 以 observed behavior 记录，不得将 schema parse PASS 表述为 review capability proven。

---

## 12. 成功标准

当用户运行 Harness 时，Reviewer 不再只是 Schema 里的字段，而是一个：

- 真实执行（receipt + 报告 artifact + DAG 节点）
- 产生 evidence（finding contract 完整、绑定被审版本）
- 可被 status 看见（severity/independence/freshness/next action）
- 能阻止错误论文进入 W2 PASS（open blocker/high → FAIL；paper 变更 → stale → FAIL）

的流程。产品定位不变：**Math Modeling Evidence Harness**——算得出 → 讲得清 → 证得住 → 交得稳。
