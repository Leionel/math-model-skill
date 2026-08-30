# 篇幅预算机制重设计方案

> 日期：2026-08-24  
> 背景：用户反馈现行 `depth_budget` + `target_words` 前置字数预算机制"不是很合理，应该是全篇生成后再弄"。  
> 范围：`paper_plan` 合同、`check_paper_readiness`、`check_writer_package`、`validate_contracts`、新增篇幅审计工具。  
> 目标：把"先卡死每段字数再写"改为"先把论证写充分再按总篇幅优化分配"，保持"篇幅向关键困难倾斜"的核心意图但修正其实现时机和度量方式。

> **Historical design note — not current operational policy.** The implemented vNext
> route keeps only `argument_units[].depth_priority` (`core`, `supporting`,
> `compact`) and its rationale; it does not adopt this note's `depth_allocation`,
> `expected_depth`, relative weights, rank checks, or pre-draft word-count Gate.

---

## 1. 现状诊断

### 1.1 当前三层前置字数预算

| 层级 | 字段 | 作用域 | 类型 | 现状约束 |
|---|---|---|---|---|
| 子问题级 | `depth_budget[].target_words` | 每个 question | integer ≥ 80 | Gate 要求必须覆盖所有含 claim 的 question；且 units 字数和 ≥ budget |
| 论证单元级 | `argument_units[].target_words` | 每个 AU | integer ≥ 40 | Schema 必填；由 check_paper_readiness 汇总比对 depth_budget |
| 摘要结果级 | `abstract_results[].word_budget` | 每个摘要结果项 | 8–100 | Schema 必填；目前无硬校验匹配正文字数 |
| 首稿覆盖级 | `draft_coverage.anchors[].minimum_words` | 每个 anchor | ≥ 20 | 传 `--require-first-draft-coverage` 时硬阻断，按 CJK 字符 + 英文词计数 |

### 1.2 为什么不合理（用户反馈 × 工程分析交叉验证）

**① 字数和论证深度不是线性代理关系**

- 80 字可以是高密度的机制推导，也可以是"因此可以看出该方案具有一定的优越性"之类的空洞话术。把 `target_words` 写进 Gate，会激励凑字数而不是写清楚。
- 往届优秀论文中，同一 rhetorical_role 的段落长度差异可达 3×，取决于该 claim 的比较复杂度、反直觉程度和所需机理铺垫——这些在写作前无法精确预测。

**② 前置预算违反真实写作工作流**

- 人类/AI 的自然写作顺序是：先把 claim → evidence → explanation → boundary 四要素写完整，再回头删冗余、合并重复段、补充弱论证。
- 现行机制要求在动笔前就把 AU 精确到 60/80/120 词，等于要求作者先削足适履再走路。结果要么是"写到 80 词就停，论证没说完"，要么是"为凑 120 词加水"。
- `check_paper_readiness` 的 `sum(AU.target_words) >= depth_budget.target_words` 这条 Gate **只检查计划和计划的一致性**，完全不反映真实写作产物的质量——它是元级校验，不是写作质量校验。

**③ 硬 Gate 产生错误激励**

- 当前 schema 中 `target_words` 是必填项。实际使用中用户会倾向于：把所有 AU 的 target_words 都填到刚好满足 sum >= depth_budget 的最小值，这样写作时不容易"超计划"——这和"篇幅向关键困难倾斜"的初衷恰好相反。
- PC-DEPTH-03 的意图是"推导难、决策影响大或验证风险高的部分获得更多公式、图与讨论"，但 `target_words` 的实现把它降格成了"字数更多"，没有区分公式、图、表占用的版面和文字的版面。

**④ 中英文混排与图表使字数预算更不准确**

- 中文按 CJK 字符计数、英文按词计数、公式和图表本身不算字数但占页面。一个 80 词的 formulation AU 如果包含 3 个大公式，实际占页可能是一个 120 词的 observation AU 的 2 倍。
- 赛事的真实限制是**总页数**，不是总词数。字数预算对最终页数的预测误差可达 30–50%。

### 1.3 保留的合理内核

不要把孩子和洗澡水一起倒掉。以下设计意图是正确的，只改实现不改目标：

1. **篇幅必须向关键困难倾斜**：四问等长的流水账论文确实是低质量信号。
2. **每个 AU 必须有预期的展开深度**：不是所有段落都写同样长。
3. **首稿必须覆盖所有必要论证环节**：不能只写结果、不写验证和边界。
4. **摘要的数字预算是对的**：摘要有严格篇幅限制，且摘要数字项是离散选择，可以先做预算。

---

## 2. 重设计：两阶段篇幅治理

新的工作流把篇幅控制拆为 **Plan 阶段（相对权重指引）** 和 **Post-draft 阶段（绝对篇幅审计与重分配）**。只有 Post-draft 阶段才碰硬性字数/页数阈值。

```text
OLD (全部前置):
  paper_plan.depth_budget[].target_words  (绝对字数)
  → argument_units[].target_words         (绝对字数)
  → Gate: sum(AU) >= depth_budget         (计划校验计划)
  → 写作时按字数写                          (削足适履)

NEW (两阶段):
  ┌─ Plan 阶段 ─────────────────────────────────────────┐
  │ paper_plan.depth_allocation[].weight  (相对权重 1-5) │
  │ paper_plan.depth_allocation[].rationale             │
  │ argument_units[].expected_depth       (枚举, 非字数)│
  │   = compact | standard | expanded                    │
  │ → Gate: 权重必须覆盖所有含 claim question            │
  │ → 写作: 按 CEEL 把论证写充分, 不卡字数               │
  └─────────────────────────────────────────────────────┘
                           ↓  全文草稿完成
  ┌─ Post-draft 阶段 ───────────────────────────────────┐
  │ 新工具: audit_paper_length.py                        │
  │   - 按 section / question / AU 统计真实字数/页数     │
  │   - 结合 competition_profile.page_budget 检查超限    │
  │   - 结合 depth_allocation.weight 检查分配合理性      │
  │   - 产出 triage 清单: 哪些段该砍 / 该扩 / 该合并     │
  │ → Gate (W2): 如果超限或分配严重失衡, 阻断进入 W2     │
  │ → 人工/AI 根据 triage 执行压缩或扩充                 │
  │ → 重新 audit, 直到通过                                │
  └─────────────────────────────────────────────────────┘
```

---

## 3. 合同变更 (paper_plan.schema v1.2 → v1.3)

### 3.1 `depth_budget` → `depth_allocation`

**移除字段：**
- `depth_budget[].target_words` (绝对字数)

**新增字段（向后兼容策略见 §5）：**

```jsonc
"depth_allocation": [
  {
    "question_id": "q1",
    "weight": 5,           // 1-5 相对权重, 5=最高优先级篇幅倾斜对象
    "rationale": "该问承担核心决策, 含多情景比较和鲁棒性验证, 需要展开敏感性分析和可行域图示",
    "expected_page_fraction": 0.38,  // 可选, 预期占全文正文页数比例(不含附录)
    "why_not_more": "完整推导进入附录, 正文只保留关键公式和行为检查"  // 可选
  },
  {
    "question_id": "q2",
    "weight": 3,
    "rationale": "该问机制相对直接, 结果主要以表格呈现, 文字只需解释差异来源",
    "expected_page_fraction": 0.24
  }
]
```

**Gate 规则重写：**
- 旧：`depth_budget` 必须覆盖所有承载 claim 的子问题，且 units.target_words 之和 >= budget。
- 新：`depth_allocation` 必须覆盖所有承载 claim 的子问题；`weight` 必须是 1-5 的整数；权重最高的 question 必须是 dependency 图的 sink 或承载 central_thesis 的 claim（即核心决策问），否则给出 warning（不是 hard fail，因为有些题核心问和难问不完全重合）。

### 3.2 `argument_units[].target_words` → `expected_depth`

**移除字段：**
- `argument_units[].target_words` (integer ≥ 40)

**新增字段：**

```jsonc
// 在 argument_unit 中
"expected_depth": "expanded",   // compact | standard | expanded, 默认 standard
```

深度级别的**语义定义**（不是字数定义）：

| 级别 | 语义 | 典型 rhetorical_role | CEEL 要素展开程度 |
|---|---|---|---|
| `compact` | 只给事实，不解释机理。读者已从前置单元理解上下文。 | boundary（当边界直接承接 validation 时）、简单 observation | C+E 完整，E/L 极简或合并到相邻段 |
| `standard` | 包含完整 CEEL，但机理部分只写直接链路，不展开替代解释或反证。 | 多数 mechanism_derivation、result_observation、常规 validation | 完整 CEEL，每要素 1-2 句 |
| `expanded` | 需要展开替代方案比较、反直觉结果的辩护、多情景对比或失效边界的逐一枚举。 | 核心 model_choice、核心 comparison、包含反证的 validation、核心 recommendation | CEEL + alternatives + counterargument；允许拆为 2-3 个物理段落，仍共享同一 unit_id |

**Gate 规则重写：**
- 旧：sum(AU.target_words) >= depth_budget.target_words （硬 fail）
- 新：绑定 high-weight question 的核心 AU（formulation / comparison / validation）不得全部为 `compact`（硬 fail）—— 防止关键问被过度压缩。
- 新：`expected_depth=expanded` 的 AU 的相邻后置单元如果是 boundary / interpretation，可以允许 `compact`（语义检查，不硬 fail）。

### 3.3 `abstract_results[].word_budget` 保留但语义微调

**不删除此字段。** 摘要篇幅极其有限（通常 250–500 词 / 300–700 CJK），且结构紧凑，可以也应该做前置预算。

**语义微调：** 把 `word_budget` 从"必须恰好写这么多词"改为"建议上限"，超过 125% 时给 warning（不硬 fail），因为摘要的超预算通常意味着正文论证安排不当——需要的是重新选择摘要结果项，而不是硬压缩。

### 3.4 `draft_coverage.anchors[].minimum_words` 降级为 warning 默认

**保留字段，** 因为检查"锚点之间有没有写够实质内容"仍是合理的。但：

1. 新增 `--enforce-minimum-words` 开关；**默认**行为：不满足 minimum_words 只产生 warning，不阻断。
2. 新增配套字段 `minimum_sentences` 或 `quality_cues`（可选，未来增强）：比纯字数更可靠的覆盖检查——例如要求出现"比较差值"、"机理词"、"边界词"等 CEEL 要素，而不是数汉字。
3. 字数阈值允许 ±30% 容差（当前是严格小于就报错），因为中英文混排 + 公式使字数波动不可避免。

---

## 4. 新增工具：`audit_paper_length.py`（Post-draft 篇幅审计器）

这是本方案的核心新能力。放在 `scripts/qa/audit_paper_length.py`。

### 4.1 输入

```powershell
python scripts/qa/audit_paper_length.py `
  --paper-plan paper_plan.json `
  --model-contract model_contract.json `
  --competition-profile competition_profiles/cumcm_2026.json `
  --latex-root paper/main.tex `
  --writer-package reports/writer_package.json `
  --output reports/length_audit.json `
  --format (human|json)
```

### 4.2 输出结构 (`length_audit.json`)

```jsonc
{
  "schema_version": "1.0",
  "audit_time": "2026-08-24T10:00:00Z",
  "summary": {
    "total_words": 6420,          // 英文词 + CJK 字符 (不含公式标签和注释)
    "total_body_pages_est": 14.2, // 基于赛事 profile 的版式估算 (正文不含附录摘要结论)
    "abstract_words": 410,
    "conclusion_words": 380,
    "page_budget_limit": 20,      // 来自 competition_profile
    "within_page_budget": true,
    "overall_allocation_score": 7.8  // 0-10, 分配与 depth_allocation.weight 的匹配度
  },
  "by_question": [
    {
      "question_id": "q1",
      "weight": 5,
      "actual_words": 2480,
      "actual_fraction": 0.386,
      "expected_fraction": 0.38,
      "delta_fraction": +0.006,
      "status": "ok",
      "observations": ["comparison AU 略超预期, 但含 2 个情景对比, 合理"]
    },
    {
      "question_id": "q3",
      "weight": 4,
      "actual_words": 1120,
      "actual_fraction": 0.174,
      "expected_fraction": 0.28,
      "delta_fraction": -0.106,
      "status": "underallocated",
      "triage_suggestions": [
        {
          "type": "expand",
          "unit_ids": ["AU-Q3-VALID-02"],
          "reason": "该 validation AU 只写了 62 词, 缺少扰动测试细节",
          "expected_gain_words": 80,
          "priority": "high"
        },
        {
          "type": "expand_with_figure",
          "figure_ids": ["FIG-Q3-SENS"],
          "reason": "敏感性分析目前只有文字描述, 增加 tornado 图可以减少字数同时增强表达",
          "priority": "medium"
        }
      ]
    },
    {
      "question_id": "q2",
      "weight": 3,
      "actual_words": 2040,
      "actual_fraction": 0.318,
      "expected_fraction": 0.24,
      "delta_fraction": +0.078,
      "status": "overallocated",
      "triage_suggestions": [
        {
          "type": "compress",
          "unit_ids": ["AU-Q2-FORM-01"],
          "reason": "公式后行为检查段落重复了前置假设章的内容, 可删除 80-100 词",
          "expected_savings_words": 90,
          "priority": "high",
          "compress_hints": [
            "删除 '如前所述, 我们假设...' 开头的段落, 因为 assumption section 已经声明",
            "合并两个极限检查为一句话: '极限情形下 (α→0, α→1), 目标值分别收敛于 X 和 Y, 与直觉一致'"
          ]
        },
        {
          "type": "move_to_appendix",
          "unit_ids": ["AU-Q2-DERIV-AUX"],
          "reason": "辅助引理的 3 步代数推导不影响核心判断",
          "expected_savings_words": 120,
          "priority": "medium"
        }
      ]
    }
  ],
  "by_unit": [
    // 每个 AU 的实际字数、expected_depth、深度级别匹配度
  ],
  "page_break_estimates": [
    // 基于版式的分页预测, 用于识别"图被挤到下一页只剩半页""结论只剩 3 行"等布局问题
  ],
  "actions_required": [
    // 需要处理的高优先级项汇总
  ],
  "overall_verdict": "pass_with_warnings | fail"
}
```

### 4.3 审计维度

| 维度 | 方法 | 严重级别 |
|---|---|---|
| **总页数超限** | competition_profile.page_budget × 版式估算 (正文词密度 + 图表占位) | 超 10% 以上 = hard fail |
| **总篇幅严重不足** | 低于 page_budget 下限 70% 且没有附录补偿 | warning (可能意味着论证没展开) |
| **权重-篇幅匹配度** | 计算 question_weight × actual_fraction 的秩相关系数 τ；τ < 0 = 高权重问反而篇幅短 = hard fail | τ < 0 hard fail; τ ∈ [0, 0.3] warning |
| **单问超配/低配** | actual_fraction 偏离 expected_fraction 超过 ±15 个百分点 | 低配 >15pp 且 weight ≥ 4 = hard fail; 其他 warning |
| **AU 深度级别匹配** | expected_depth=expanded 的 AU 实际词数低于同 role 的 compact AU 均值 = 反向信号 | warning |
| **摘要预算** | 摘要总词数超过 profile 上限 110% | hard fail |
| **图表-文字平衡** | 某 question 正文词数很少但图表占了 2+ 页 = 可能是图表堆砌 | warning |
| **布局异常** | 预测分页中某 section 只剩 <1/3 页在新页 | info 级, 不 Gate |

### 4.4 Gate 集成

在 `run_deterministic_qa.py --require-length-audit` 中：

1. 必须存在 `reports/length_audit.json` 且其 `audit_time` 晚于 `paper/main.tex` 的 mtime（防止复用旧审计）。
2. `overall_verdict = fail` → Gate FAIL，阻断进入 W2。
3. 如果有 `hard fail` 级别的问题，即使 verdict 侥幸通过，也在 Gate 报告中突出。

---

## 5. 向后兼容与迁移

当前已有 fixture / test 可能引用 v1.2 schema，必须提供平滑迁移。

### 5.1 Schema 双版本共存

- `schema_version: "1.2"` 继续接受 `depth_budget` 和 `target_words`，但 `check_paper_readiness` 对 sum 匹配只产生 **deprecation warning**，不再 hard fail。
- `schema_version: "1.3"` 要求 `depth_allocation` + `expected_depth`，原字段变为可选（读取时忽略）。

### 5.2 自动迁移脚本

新增 `scripts/contracts/migrate_paper_plan_v1_2_to_v1_3.py`：

```text
输入: v1.2 paper_plan.json
输出: v1.3 paper_plan.json (原地备份 .bak)
迁移规则:
  1. depth_budget[].target_words → 归一化为 weight (最大 target_words 映射为 5, 其余按比例取整 1-5)
     rationale 保留; expected_page_fraction = target_words / sum(target_words)
  2. argument_units[].target_words → expected_depth:
     < 60 → compact
     60-119 → standard
     >= 120 → expanded
  3. schema_version 升级为 "1.3"
  4. 在 plan 中写入 migration_note, 提示用户人工复核 weight 的业务合理性
```

### 5.3 测试迁移

- 现有测试中所有 v1.2 fixture：全部运行迁移脚本后回归通过。
- 新增 3 个 v1.3 fixture：
  - `fixtures/paper_plan_v1_3_balanced.json`：分配合理，audit 应 pass
  - `fixtures/paper_plan_v1_3_underallocated.json`：核心问低配，audit 应 fail
  - `fixtures/paper_plan_v1_3_page_overrun.json`：总页数超，audit 应 fail

---

## 6. 受影响文件清单与实施顺序

| 顺序 | 文件 | 改动 |
|---|---|---|
| 1 | `schemas/paper_plan.schema.json` | 新增 v1.3 定义（depth_allocation、expected_depth）；v1.2 字段保持兼容但降级为可选 |
| 2 | `references/contracts/paper_plan.md` | 重写 Gate 规则节；更新最小示例为 v1.3；保留旧规则为 deprecated |
| 3 | `scripts/qa/validate_contracts.py` | depth_budget 检查改为双分支：v1.2 → warning-only；v1.3 → 检查 weight 覆盖和枚举合法性 |
| 4 | `scripts/qa/check_paper_readiness.py` | 删除 sum(AU.target_words) >= depth_budget 硬检查；新增 high-weight question 核心 AU 不得全 compact 检查；新增 deprecation 提示 |
| 5 | `scripts/qa/check_writer_package.py` | minimum_words 默认降级为 warning；新增 ±30% 容差；新增 `--enforce-minimum-words` 开关 |
| 6 | `scripts/qa/audit_paper_length.py` | **新增**：Post-draft 篇幅审计器 (核心) |
| 7 | `scripts/qa/run_deterministic_qa.py` | 新增 `--require-length-audit` 开关；集成审计结果 |
| 8 | `scripts/contracts/migrate_paper_plan_v1_2_to_v1_3.py` | **新增**：自动迁移脚本 |
| 9 | `references/precedents/pattern-cards/PC-DEPTH-03-risk-weighted-depth.md` | 更新机制描述：从"输出 target_words 预算"改为"输出 depth_allocation 权重 + post-draft audit triage" |
| 10 | `tests/` | 新增 v1.3 fixture × 3；audit_paper_length 单元测试 × 8；迁移脚本回归测试 × 2；现有 v1.2 测试全部加 deprecation warning 断言 |

---

## 7. 不变的边界

本方案**不做**以下改动（它们不在用户反馈范围内，且属于正确设计）：

- ✅ 保留 `draft_coverage.anchors` 的**存在性检查**（即每个 anchor 必须在草稿中被定位到），这仍然是防止漏掉论证环节的硬 Gate。只是字数阈值降级。
- ✅ 保留 `abstract_results[].word_budget` 字段和其"摘要数字预算"语义——摘要篇幅确实极短，必须前置规划。
- ✅ 保留 PC-DEPTH-03"篇幅向关键困难倾斜"的核心意图，只是把它从"前置字数预算"兑现为"先写充分、再审计分配、再调整"的闭环。
- ✅ 保留论证结构约束：每个 question 必须有 formulation / result / validation / interpretation 四个角色的 AU——这是研究完整性，与篇幅无关。

---

## 8. 验证计划

完成上述改动后，执行以下验证链路：

```powershell
# 1. Schema 级验证
python -m unittest tests.test_paper_plan_v1_3 -v

# 2. 迁移脚本验证
python scripts/contracts/migrate_paper_plan_v1_2_to_v1_3.py \
  --input tests/fixtures/paper_plan_v1_2_complex.json \
  --output /tmp/migrated.json
python scripts/qa/validate_contracts.py --paper-plan /tmp/migrated.json
# 期望: 0 errors, 迁移合理性 warning = 1

# 3. 篇幅审计功能验证 (正例)
python scripts/qa/audit_paper_length.py \
  --paper-plan tests/fixtures/paper_plan_v1_3_balanced.json \
  --latex-root tests/fixtures/balanced_draft/main.tex \
  --competition-profile competition_profiles/cumcm_2026.json \
  --format json
# 期望: overall_verdict = pass, allocation_score >= 7.0

# 4. 篇幅审计功能验证 (反例: 核心问低配)
python scripts/qa/audit_paper_length.py \
  --paper-plan tests/fixtures/paper_plan_v1_3_underallocated.json \
  --latex-root tests/fixtures/under_draft/main.tex \
  --competition-profile competition_profiles/cumcm_2026.json
# 期望: overall_verdict = fail, by_question.q3.status = underallocated

# 5. 完整回归
python -m unittest discover -s tests -q
# 期望: 全部通过, 与改动前的 376/376 相比仅新增 deprecation warnings
```

---

## 9. 与原用户反馈的映射

用户原话：

> "我觉得篇幅预算这个东西不是很合理，应该是全篇生成后再弄。"

本方案的回应：

| 用户反馈点 | 方案如何体现 |
|---|---|
| 篇幅预算不合理 | 删除 AU.target_words 和 depth_budget.target_words 的硬 Gate；改为相对权重 + 深度枚举，不强制作者卡字数写作 |
| 全篇生成后再处理篇幅 | 新增 audit_paper_length.py 作为 Post-draft 阶段的权威篇幅治理工具；只有这一步才检查硬性字数/页数阈值 |
| (隐含) 不希望写的时候被数字绑住 | Plan 阶段的 depth_allocation 是**业务判断输入**（"这问值得展开"），不是工程约束（"必须写 260 词"）；写作时按 CEEL 把论证写充分，不再需要"写到 120 词就停" |
| (隐含) 优秀论文的篇幅分配是结果，不是前提 | 审计器的 triage_suggestions 给出具体的"砍什么 / 补什么 / 移到哪里"的操作建议，而不是抽象的"字数不够"——这才是人类编辑在改稿时真正会做的事 |

---

## 10. 下一步决策点

在开始编码前，需要用户确认以下 2 个选择：

1. **默认 Gate 严格度**：`audit_paper_length.py` 的 hard fail 阈值是"总页数超 profile 10%"还是"15%"？建议默认 10%，因为赛事规则通常严格执行页数限制。
2. **v1.2 兼容期**：是立即把所有现有 fixture 和生产代码切到 v1.3，还是保留 v1.2 兼容 3 个版本后再移除？建议保留双版本至少到下一次大版本。

确认后即可按 §6 的顺序实施。
