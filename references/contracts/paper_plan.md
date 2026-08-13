# Paper Plan Contract

将 `paper_plan.json` 作为写作前唯一的论证计划；不要把它写成论文初稿或第二份结果数据库。Writer 必须先把它编译为只读 package，再开始成文；不能浏览 raw outputs 后自行发明数字、原因、场景或结论强度。

## 建立顺序

1. M1 前可先登记经全文核验的文献 evidence。
2. P2 后把 `frozen_results.json` 合并到同一个 `evidence_registry.json`。
3. 检查 registry 中实际存在且 `verification_status=verified` 的 `evidence_id`。
4. 最后建立 requirement → claim → evidence 与 section/figure/table 规划。

结果证据 ID 由注册脚本稳定生成：结果 `R-Q1-01` 对应证据 `E-R-Q1-01`；不要手工创建重复结果证据。

## 最小示例

```json
{
  "schema_version": "1.2",
  "run_id": "run-001",
  "central_thesis": {
    "text": "在冻结需求和约束下，方案 B 以可验证的可行性取得最低成本。",
    "claim_ids": ["C-Q1-01"],
    "boundary": "不外推至未测试的需求、价格或约束。"
  },
  "requirements": [
    {"requirement_id": "REQ-Q1", "text": "回答问题一的最优方案和验证结果", "claim_ids": ["C-Q1-01"]}
  ],
  "claims": [
    {
      "claim_id": "C-Q1-01",
      "claim_type": "observation",
      "text": "方案 B 在给定约束下取得最低成本",
      "question_id": "q1",
      "evidence_ids": ["E-R-Q1-01"],
      "result_ids": ["R-Q1-01"],
      "section": "results.q1",
      "boundary": "仅适用于冻结数据和给定约束",
      "support_level": "direct",
      "comparison": {"comparator": "同一约束下的候选方案", "metric": "总成本", "direction": "lower_is_better", "scenario": "frozen-base"}
    }
  ],
  "sections": [
    {"section_id": "results.q1", "purpose": "回答问题一并解释验证结果", "claim_ids": ["C-Q1-01"]}
  ],
  "argument_units": [
    {
      "unit_id": "AU-Q1-FORM",
      "section_id": "results.q1",
      "rhetorical_role": "mechanism_derivation",
      "claim_ids": ["C-Q1-01"],
      "evidence_ids": ["E-CITE-Q1-METHOD"],
      "prerequisite_unit_ids": [],
      "expected_reader_judgment": "模型机制、变量和约束与题意一致。",
      "boundary": "固定需求和可加成本。",
      "target_words": 80
    },
    {
      "unit_id": "AU-Q1-RESULT",
      "section_id": "results.q1",
      "rhetorical_role": "result_observation",
      "claim_ids": ["C-Q1-01"],
      "evidence_ids": ["E-R-Q1-01"],
      "prerequisite_unit_ids": [],
      "expected_reader_judgment": "该数值来自可复核的冻结运行。",
      "boundary": "仅适用于 frozen-base。",
      "target_words": 120
    },
    {
      "unit_id": "AU-Q1-VALID",
      "section_id": "results.q1",
      "rhetorical_role": "validation",
      "claim_ids": ["C-Q1-01"],
      "evidence_ids": ["E-R-Q1-01"],
      "prerequisite_unit_ids": ["AU-Q1-RESULT"],
      "expected_reader_judgment": "可行性与目标值已经独立重算。",
      "boundary": "仅验证已声明约束。",
      "target_words": 80
    },
    {
      "unit_id": "AU-Q1-BOUNDARY",
      "section_id": "results.q1",
      "rhetorical_role": "boundary",
      "claim_ids": ["C-Q1-01"],
      "evidence_ids": ["E-R-Q1-01"],
      "prerequisite_unit_ids": ["AU-Q1-VALID"],
      "expected_reader_judgment": "结论不会外推到未测试需求。",
      "boundary": "仅适用于 frozen-base。",
      "target_words": 60
    }
  ],
  "depth_budget": [
    {"question_id": "q1", "target_words": 260, "rationale": "该问承担核心决策，需展示验证与比较。"}
  ],
  "precision_policy": {
    "audit_source": "frozen_display_value",
    "prose_source": "frozen_display_value",
    "table_source": "frozen_display_value",
    "abstract_max_numeric_claims": 3
  },
  "abstract_results": [
    {
      "result_id": "R-Q1-01",
      "priority": "primary",
      "selection_reason": "它直接决定核心建议，且已通过比较与边界验证",
      "claim_ids": ["C-Q1-01"],
      "word_budget": 28
    }
  ],
  "nonresearch_numeric_literals": [
    {"token": "2026", "reason": "赛事年份，不是研究结果"}
  ],
  "terminology": [
    {"canonical": "可行域", "forbidden_variants": ["可行区域"]}
  ],
  "figures": [],
  "tables": [],
  "readiness": {
    "stage": "technical_draft",
    "question_coverage": [
      {
        "question_id": "q1",
        "formulation_unit_ids": ["AU-Q1-FORM"],
        "result_unit_ids": ["AU-Q1-RESULT"],
        "validation_unit_ids": ["AU-Q1-VALID"],
        "interpretation_unit_ids": ["AU-Q1-BOUNDARY"],
        "display_ids": [],
        "display_waiver": "该问只有一个标量结果，公式和正文比单独图表更清楚。"
      }
    ]
  },
  "canonical_recommendation": {"text": "采用方案 B", "evidence_ids": ["E-R-Q1-01"]},
  "status": "ready"
}
```

## Gate 规则

- 只让 `ready` 计划进入 W1。
- 为每个赛题子问题至少建立一个 claim；每个 requirement 和 claim 都必须非空。
- 只引用已验证 evidence；不得用 `pending` evidence 支撑论文主张。
- `central_thesis` 只绑定 1—5 条决定性 claim，并显式说明整体边界；不能把每小问的数字清单伪装成总论点。
- claim 必须标注为 `observation`、`inference` 或 `recommendation`。Observation 必须给出 `result_ids`；Inference/Recommendation 必须给出已经成立的 `precondition_claim_ids`，且不能标为 `direct`。
- 使用“最优、显著、稳健、提升”等比较性强词时，填写 `comparison` 的 comparator、metric、direction 和 scenario；缺少比较合同时降为 observation 或删除强词。
- 每个 `argument_unit` 只能有一个 `rhetorical_role`，同时绑定 claim/evidence、前置单元、期望读者判断、边界和目标篇幅。把 model choice、结果观察、解释和边界混在一个万能段落会被拒绝。
- `depth_budget` 必须覆盖所有承载 claim 的子问题，按难点、风险与决策影响分配篇幅，不能默认四问等长。
- 正式第一版前必须达到 `readiness.stage=technical_draft`；每个子问题分别绑定 formulation、result、validation、interpretation argument units 和至少一个 display，确无必要时写具体 waiver。各单元计划篇幅之和不得低于该问 depth budget。
- 数字只能来自 `precision_policy` 指定的 frozen display source；摘要的权威数字不超过 `abstract_max_numeric_claims`。
- 文献 evidence 必须同时通过 metadata、全文内容和出版状态检查；优秀论文机制卡不属于 evidence。
- 为“最优、显著、稳健、提升”等表述登记 baseline、指标、统计口径和适用边界。
- 仅把摘要需要出现的权威结果加入 `abstract_results[]`，并说明 `selection_reason`、关联 claim 与词数预算；不要只登记 ID 后把所有结果塞进摘要。
- 年份、题号、章节号等非研究数字如会被 claim inventory 扫描，可登记到 `nonresearch_numeric_literals[]` 并写明理由；不能用它放行结果、百分比或参数。
- 将同一推荐方案的唯一文字版本放入 `canonical_recommendation`；若题型不需要推荐，可省略该字段。

## 编译写作包

```powershell
python scripts/claims/compile_writer_package.py `
  --paper-plan paper_plan.json `
  --frozen-results results/frozen_results.json `
  --evidence-registry evidence_registry.json `
  --output reports/writer_package.json `
  --integrity-mode research
```

Writer 只从 package 起草。草稿完成后运行：

```powershell
python scripts/qa/check_writer_package.py `
  --writer-package reports/writer_package.json `
  --draft paper/draft.txt `
  --strict
```

它会阻断 package 外的研究数值，以及只有 observation 却使用因果/解释性语言的草稿。它不替代人工判断机制是否真实成立；这仍是 Semantic Critic 的职责。
