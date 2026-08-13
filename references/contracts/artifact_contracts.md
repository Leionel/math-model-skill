# Artifact Contracts

## Enhanced Integrity Profile

新项目应在 `run_manifest.json` 设置 `enhanced_integrity_profile=true`。该 profile 不另建一套 Gate，而是在现有 M1/W1/W2 增加以下不可替代 artifact：

| Artifact | Gate | 作用 |
|---|---|---|
| `problem_snapshot.json` | M1 | 题面/附件 hash、选题依据与逐 requirement 交付追踪 |
| `data_contract.json`（每个权威数据集一份） | M1 | 列类型、单位、范围、主键、缺失、时间和泄漏语义 |
| `implementation_map.json` | M1 | equation/symbol → contract item → code symbol → passing test |
| `artifact_dag.json` | M1 | 输入/输出/命令/receipt 依赖图与 stale 传播真源 |
| `presentation_contract.json` | W1 | 结果宏、舍入、单位、百分比与出现位置唯一真源 |
| `claim_inventory.json` | W2 | 扫描正文中 plan 外数字与研究强词；由工具生成 |
| `build_receipt.json` | W2 | 隔离 LaTeX build、禁 shell escape、源码前后 tree hash |
| `pdf_visual_qa.json` | W2 | 实际 PDF 页数/纸张/字体/全页渲染 receipt |
| `visual_review_receipt.json` | W2 | 最终尺寸人工/多模态逐页审查，绑定同一 PDF/hash |

默认 false 只用于 schema 1.1 项目的显式迁移窗口，不能据此声称已通过增强研究完整性门槛。

M1 Gate 会调用语义检查器重新验证每份 data contract、implementation map 与 artifact DAG；W1 再把 problem snapshot 与最终 paper plan 做逐 requirement 闭环。DAG 检查能够发现输入/输出 hash 漂移、上游 digest 漂移、重复 producer、cycle 与非 current 节点；它目前负责阻断 stale，不负责自动调度重跑。

基础兼容 profile 长期保存五个核心 contract；enhanced profile 只为无法嵌入权威对象的题面、数据语义、实现映射和机器/人工 receipts 增件。只有最终提交阶段再增加不可变 manifest。代码、数据、验证日志、图和论文是被合同引用的实际 artifact，不为每个阶段另写重复总结文件。

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
- `frozen_results.json`：P2 的不可覆盖结果快照；绑定 model contract、代码、输入、可重算验证报告和逐项义务；可保留失败 run，但只有 `claimable=true` 的 PASS run 可进入 evidence。
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
  "validation_status": "passed",
  "claimable": true
}
```

单位必须显式填写；无量纲量写 `dimensionless`。显示值必须等于 `value + precision` 的 ROUND_HALF_UP 结果，Writer 不得自行换算或重新舍入。`validation_status` 由总验证结论派生（`passed`/`failed`/`error`），`claimable` 必须等于冻结件的 `claimable`，不能由 Writer 或 Registry 自行提升。
