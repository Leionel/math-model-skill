# Artifact Contracts

长期保存五类 contract。代码、数据、验证日志、图片和论文仍是实际 artifact，由 contract 通过路径与 SHA-256 引用；不要再维护内容重复的阶段摘要。

## 单向权威链

```text
model_contract.json
  → run_manifest.json
  → frozen_results.json
  → evidence_registry.json
  → paper_plan.json
```

- `model_contract.json`：M1 前建立；模型、变量、单位、约束或验证口径变化后创建新 run，并使下游 Gate 失效。
- `run_manifest.json`：记录命令、artifact 哈希、Gate、Reviewer 报告和修订循环；不存大段自由文本。
- `frozen_results.json`：P2 后生成；禁止原地覆盖，必须同时冻结代码与验证日志。
- `evidence_registry.json`：只登记可追溯 evidence，不重复保存 claim 归属；claim → evidence 映射只存在于 paper plan。
- `paper_plan.json`：W1 前建立；只引用 registry 中已验证的 evidence 和 frozen results 中已有的 result。

默认使用 JSON，保证当前无 PyYAML 环境也能直接运行。`load_structured` 仍兼容已安装 PyYAML 的环境，但 YAML 不是 P0 的必需依赖。

## 结果记录

每个关键结果至少包含：

```json
{
  "result_id": "R-Q1-01",
  "question_id": "q1",
  "name": "optimal_cost",
  "value": 123.45,
  "unit": "CNY",
  "precision": 2,
  "display_value": "123.45",
  "statistical_definition": "exact solver objective value",
  "boundary": "仅适用于冻结需求与给定约束",
  "source_artifact": "results/q1.json",
  "source_key": "optimal_cost",
  "validation_status": "passed"
}
```

必须显式填写单位；无量纲量写 `dimensionless`。不得让冻结脚本猜测单位。显示值必须与 `value + precision` 的 ROUND_HALF_UP 结果一致。
