# Paper Plan Contract

将 `paper_plan.json` 作为写作前唯一的论证计划；不要把它写成论文初稿或第二份结果数据库。

## 建立顺序

1. 先从 `frozen_results.json` 生成 `evidence_registry.json`。
2. 再检查 registry 中实际存在且 `verification_status=verified` 的 `evidence_id`。
3. 最后建立 requirement → claim → evidence 与 section/figure/table 规划。

结果证据 ID 由注册脚本稳定生成：结果 `R-Q1-01` 对应证据 `E-R-Q1-01`；不要手工创建重复结果证据。

## 最小示例

```json
{
  "schema_version": "1.0",
  "run_id": "run-001",
  "requirements": [
    {"requirement_id": "REQ-Q1", "text": "回答问题一的最优方案和验证结果", "claim_ids": ["C-Q1-01"]}
  ],
  "claims": [
    {
      "claim_id": "C-Q1-01",
      "text": "方案 B 在给定约束下取得最低成本",
      "question_id": "q1",
      "evidence_ids": ["E-R-Q1-01"],
      "section": "results.q1",
      "boundary": "仅适用于冻结数据和给定约束"
    }
  ],
  "sections": [
    {"section_id": "results.q1", "purpose": "回答问题一并解释验证结果", "claim_ids": ["C-Q1-01"]}
  ],
  "abstract_result_ids": ["R-Q1-01"],
  "terminology": [
    {"canonical": "可行域", "forbidden_variants": ["可行区域"]}
  ],
  "figures": [],
  "tables": [],
  "canonical_recommendation": {"text": "采用方案 B", "evidence_ids": ["E-R-Q1-01"]},
  "status": "ready"
}
```

## Gate 规则

- 只让 `ready` 计划进入 W1。
- 为每个赛题子问题至少建立一个 claim；每个 requirement 和 claim 都必须非空。
- 只引用已验证 evidence；不得用 `pending` evidence 支撑论文主张。
- 为“最优、显著、稳健、提升”等表述登记 baseline、指标、统计口径和适用边界。
- 仅把摘要需要出现的权威结果加入 `abstract_result_ids`。
- 将同一推荐方案的唯一文字版本放入 `canonical_recommendation`；若题型不需要推荐，可省略该字段。
