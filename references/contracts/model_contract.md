# Model Contract

在编码前建立 `model_contract.json`，让 Modeling 与 Coding 对数学定义使用同一权威源。正式 `research/submission` 运行必须先完成 [Research-first Model Planning](../research/model_planning.md)，不能把模型名和一句 rationale 当作建模计划。

## 最小示例

```json
{
  "schema_version": "1.2",
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
    {
      "data_id": "demand",
      "path": "data/input.csv",
      "read_only": true,
      "sha256": "<submission 模式才必填；dev/research 可省略>",
      "origin": "竞赛附件",
      "license_or_terms": "限本次竞赛使用",
      "transformations": [],
      "quality_checks": ["列类型、缺失值、重复、范围和单位检查"]
    }
  ],
  "assumptions": [
    {"assumption_id": "A1", "text": "规划期内需求固定", "basis": "题目给定", "sensitivity_plan": "需求上下浮动 10% 重跑"}
  ],
  "models": [
    {
      "model_id": "M-Q1",
      "question_id": "q1",
      "name": "成本最小化模型",
      "problem_type": "optimization",
      "characteristics": ["deterministic"],
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
      "validation_obligations": [
        {
          "obligation_id": "VAL-FEASIBILITY",
          "category": "feasibility",
          "method": "独立重算全部约束",
          "acceptance": {
            "left_metric_id": "max_constraint_violation",
            "operator": "<=",
            "right": {"kind": "literal", "value": 0},
            "unit": "item"
          },
          "required_stage": "both"
        }
      ],
      "risks": ["需求固定假设"],
      "fallback": "求解超时则使用已验证的可行启发式方案",
      "plan_details": {
        "selected_candidate_id": "CM-Q1-LP",
        "mechanism": "以需求约束定义可行域，在其中最小化可加成本。",
        "equation_plan": [
          {"equation_id": "EQ-Q1-OBJ", "purpose": "定义目标函数", "expression_or_derivation": "min C(x)", "variables": ["x"], "assumptions": ["成本可加"]}
        ],
        "parameter_plan": [
          {"parameter": "demand", "source_or_estimator": "竞赛附件", "unit": "item", "uncertainty_or_range": "±10%"}
        ],
        "implementation_steps": ["校验输入", "构造并求解模型", "独立重算约束和目标"],
        "output_artifacts": ["results/raw_results.json"],
        "validation_strategy": ["可行性、目标重算和需求敏感性"],
        "failure_modes": ["需求并非固定"]
      }
    }
  ],
  "terminology": [
    {"canonical": "可行域", "forbidden_variants": ["可行区域"]}
  ],
  "status": "ready"
}
```

## M1 规则

- `research_basis` 必须覆盖每个子问题：中英关键词、LLM knowledge 侦察、外部文献搜索、候选模型比较和选型决定；正式选中模型至少绑定一条全文可访问、带 locator、三状态均核验的 citation evidence。
- 每问至少两个候选，或提供具体 `single_candidate_waiver`；候选必须比较机制适配、假设、数据需求、强弱项和淘汰条件，不能只列名称。
- 选中候选必须绑定实际 `model_id`，且 `plan_details` 写清公式/推导、参数来源与范围、至少三步实现、输出、验证和失败模式。
- `problem_type` 之外还要声明 `characteristics`。例如场景随机多阶段模型必须触发 `uncertainty + scenario_generalization + nonanticipativity`，相关输入模拟必须触发 `correlation_validity`；不能只验证“标准差大于零”就声称随机模型可靠。
- 明确每个子问题的 conclusion type、输入和输出；不要只写算法名称。
- 为变量填写含义、单位、定义域和角色；无量纲量显式写 `dimensionless`。
- 把约束写成可定位的 `constraint_id + expression + meaning`。
- 为 smoke/full 指定可判断成败的 acceptance；“结果合理”不是验收标准。
- 按题型声明会改变结论可信度的 `validation_obligations`；每个 `acceptance` 必须是有限的结构化比较，P2 由 measurement snapshot 独立重算，不接受空 `ok=true` 或人工 verdict 报告。
- 数据源必须记录 origin、许可/条款、变换和质量检查；外部数据的来源页面也应固定快照。`dev/research` 不要求处处填写 SHA-256，`submission` 才将最终引用全部哈希化；结果冻结仍可独立保留上游哈希。
- 写明风险和回退方案；模型变化后创建新 run，不能沿用旧 P1/P2 状态。
