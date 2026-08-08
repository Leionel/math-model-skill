# Artifact Contracts

解题阶段长期保存五个 contract；只有最终提交阶段再增加第六个不可变 manifest。代码、数据、验证日志、图和论文是被合同引用的实际 artifact，不再为每个阶段另写重复总结文件。

```text
competition_profile (embedded in run_manifest)
          ↓
model_contract.json → run_manifest.json
          ↓                  ↓
frozen_results.json → evidence_registry.json → paper_plan.json
                                                ↓
                              submission_manifest.json (F1 only)
```

- `model_contract.json`：M1 的题意、数据、模型和验证义务。数学口径变化后创建新 run。
- `run_manifest.json`：可变控制面；记录规则快照、安全策略、AI 使用、人审、命令、artifact、Gate 与 Reviewer，不存长篇内容。
- `frozen_results.json`：P2 的不可覆盖结果快照；绑定 model contract、代码、输入、验证报告和逐项义务。
- `evidence_registry.json`：唯一的增量证据账本；可先登记文献，再合并冻结结果。它不维护 claim 反向列表。
- `paper_plan.json`：W1 的 requirement/claim/evidence、章节、摘要结果和图表合同。
- `submission_manifest.json`：F1 才生成；冻结比赛 profile、规则、最终论文、附件、AI 声明、S1 report、截止时间与包哈希。

Competition Profile 嵌入 run manifest，避免新增一个常驻顶层 JSON；AI 使用也放 `run_manifest.ai_usage[]`。规则原文、交互记录和报告仍是独立 artifact，通过路径与 SHA-256 引用。

## 结果字段

```json
{
  "result_id": "R-Q1-01",
  "question_id": "q1",
  "name": "optimal_cost",
  "value": 123.45,
  "unit": "CNY",
  "precision": 2,
  "display_value": "123.45",
  "statistical_definition": "independently recomputed objective",
  "boundary": "仅适用于冻结需求与给定约束",
  "source_artifact": "results/q1.json",
  "source_key": "optimal_cost",
  "validation_status": "passed"
}
```

单位必须显式填写；无量纲量写 `dimensionless`。显示值必须等于 `value + precision` 的 ROUND_HALF_UP 结果，Writer 不得自行换算或重新舍入。
