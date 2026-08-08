# Model Contract

在编码前建立 `model_contract.json`，让 Modeling 与 Coding 对数学定义使用同一权威源。

## 最小示例

```json
{
  "schema_version": "1.0",
  "project_id": "contest-a",
  "run_id": "run-001",
  "unit_system": "SI",
  "questions": [
    {
      "question_id": "q1",
      "task": "在给定需求下最小化总成本",
      "conclusion_type": "numeric optimum and feasible plan",
      "inputs": ["demand"],
      "outputs": ["optimal_cost"]
    }
  ],
  "data_sources": [
    {"data_id": "demand", "path": "data/input.csv", "read_only": true, "sha256": "<64-hex>"}
  ],
  "assumptions": [
    {"assumption_id": "A1", "text": "规划期内需求固定", "basis": "题目给定", "sensitivity_plan": "需求上下浮动 10% 重跑"}
  ],
  "models": [
    {
      "model_id": "M-Q1",
      "question_id": "q1",
      "name": "成本最小化模型",
      "rationale": "直接对应题目目标与约束",
      "variables": [
        {"symbol": "x", "meaning": "生产数量", "unit": "item", "domain": "x >= 0", "role": "decision"}
      ],
      "objective": "minimize total cost",
      "constraints": [
        {"constraint_id": "C1", "expression": "x >= demand", "meaning": "满足需求"}
      ],
      "algorithm": "mixed-integer programming",
      "inputs": ["demand"],
      "outputs": ["optimal_cost"],
      "validation": [
        {"check_id": "V1", "stage": "both", "method": "检查全部约束", "acceptance": "零违反"}
      ],
      "risks": ["需求固定假设"],
      "fallback": "求解超时则使用已验证的可行启发式方案"
    }
  ],
  "terminology": [
    {"canonical": "可行域", "forbidden_variants": ["可行区域"]}
  ],
  "status": "ready"
}
```

## M1 规则

- 明确每个子问题的 conclusion type、输入和输出；不要只写算法名称。
- 为变量填写含义、单位、定义域和角色；无量纲量显式写 `dimensionless`。
- 把约束写成可定位的 `constraint_id + expression + meaning`。
- 为 smoke/full 指定可判断成败的 acceptance；“结果合理”不是验收标准。
- 写明风险和回退方案；模型变化后创建新 run，不能沿用旧 P1/P2 状态。
