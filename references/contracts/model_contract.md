# Model Contract

在编码前建立 `model_contract.json`，让 Modeling 与 Coding 对数学定义使用同一权威源。正式 `research/submission` 运行必须先完成 [Research-first Model Planning](../research/model_planning.md)，不能把模型名和一句 rationale 当作建模计划。

## 最小示例

```json
{
  "schema_version": "1.3",
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
  "assumption_forks": [
    {
      "fork_id": "AF-01",
      "phrase": "消纳比例",
      "question_id": "q1",
      "interpretations": [
        {"id": "A", "meaning": "历史统计平均，仅描述基准状态", "mathematical_effect": "仅作描述统计量，不进入约束"},
        {"id": "B", "meaning": "逐时物理硬上限", "mathematical_effect": "R_t <= rho * R_available_t 成为硬约束"}
      ],
      "checks": ["题面措辞", "附件语义", "单位一致性", "对后续问题的边际影响", "sanity check"],
      "selected": "A",
      "selection_reason": "题面无逐时上限措辞，附件无线路容量字段；采用 B 会人为压制全部优化时段"
    }
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
          {
            "equation_id": "EQ-Q1-OBJ",
            "purpose": "定义目标函数",
            "expression_or_derivation": "min C(x)",
            "variables": ["x"],
            "assumptions": ["成本可加"],
            "equation_type": "objective",
            "math_risk": "medium",
            "inputs": ["x"],
            "outputs": ["cost"],
            "symbols": ["x"],
            "domains": {"x": "x >= 0"},
            "preconditions": ["成本项单位一致"],
            "unit_signature": "CNY",
            "verification": {
              "symbol_check": "PASS",
              "domain_check": "PASS",
              "unit_check": "PASS",
              "boundary_check": "UNVERIFIED",
              "property_test_refs": [],
              "semantic_test_refs": []
            }
          }
        ],
        "parameter_plan": [
          {
            "parameter": "demand",
            "provenance": {"type": "GIVEN", "source_locator": "竞赛附件 input.csv demand 列"},
            "unit": "item",
            "uncertainty_or_range": "±10%"
          }
        ],
        "implementation_steps": ["校验输入", "构造并求解模型", "独立重算约束和目标"],
        "output_artifacts": ["results/raw_results.json"],
        "validation_strategy": ["可行性、目标重算和需求敏感性"],
        "failure_modes": ["需求并非固定"],
        "derivation_graph": {
          "nodes": [
            {"id": "EQ-Q1-OBJ", "equation_id": "EQ-Q1-OBJ", "type": "objective", "inputs": ["x"], "outputs": ["cost"]}
          ],
          "edges": [],
          "source_node_ids": ["EQ-Q1-OBJ"],
          "terminal_node_ids": ["EQ-Q1-OBJ"]
        }
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
- `searches[]` 的外部检索在 `--formal` M1 中还必须有 `evidence_ids`，且候选数不能为零；只写“搜过”或只保留一个 URL 不构成研究根据。
- 每问至少两个候选，或提供具体 `single_candidate_waiver`；候选必须比较机制适配、假设、数据需求、强弱项和淘汰条件，不能只列名称。
- 选中候选必须绑定实际 `model_id`，且 `plan_details` 写清公式/推导、参数来源与范围、至少三步实现、输出、验证和失败模式。
- 关键公式应补充 `equation_type`、`math_risk`、`symbols`、`domains`、`unit_signature`、`preconditions` 和 `verification`；公式之间通过 `plan_details.derivation_graph` 记录中间量、输入、输出和目标终点。只写公式字符串不算推导链。
- `problem_type` 之外还要声明 `characteristics`。例如场景随机多阶段模型必须触发 `uncertainty + scenario_generalization + nonanticipativity`，相关输入模拟必须触发 `correlation_validity`；不能只验证“标准差大于零”就声称随机模型可靠。
- 明确每个子问题的 conclusion type、输入和输出；不要只写算法名称。
- `models[].inputs` 中的每个输入都必须在 `plan_details.parameter_plan[]` 出现，并使用 typed provenance；不能只在数据源列表里声明一次就算完成参数解释。
- 为变量填写含义、单位、定义域和角色；无量纲量显式写 `dimensionless`。
- 把约束写成可定位的 `constraint_id + expression + meaning`。
- 为 smoke/full 指定可判断成败的 acceptance；“结果合理”不是验收标准。
- 按题型声明会改变结论可信度的 `validation_obligations`；每个 `acceptance` 必须是有限的结构化比较，P2 由 measurement snapshot 独立重算，不接受空 `ok=true` 或人工 verdict 报告。
- `sensitivity` 义务必须声明 `artifact_role=sensitivity_experiment`；`out_of_sample` 义务必须声明 `artifact_role=oos_artifact`。P2 要求对应 artifact 绑定当前 `run_id` 并通过语义检查，不能只把“敏感性分析/OOS”写在 validation 文本里。
- 数据源必须记录 origin、许可/条款、变换和质量检查；外部数据的来源页面也应固定快照。`dev/research` 不要求处处填写 SHA-256，`submission` 才将最终引用全部哈希化；结果冻结仍可独立保留上游哈希。
- 写明风险和回退方案；模型变化后创建新 run，不能沿用旧 P1/P2 状态。

### Equation Contract 与 Derivation DAG

公式风险分三级：`low` 只要求符号/定义域/单位合同，`medium` 还要有边界或数值 sanity check，`high` 还要声明操作前提，并绑定 symbolic、property、tiny-oracle、semantic test 或独立人工复核中的适用项。检查状态使用 `PASS`、`FAIL`、`UNVERIFIED`、`NOT_APPLICABLE`；`UNVERIFIED` 不能在正式 W2 被当作 PASS。

`scripts/qa/check_derivation_integrity.py --require-metadata --strict` 会检查：

- 公式符号是否在变量、参数或输入中登记；
- 中间量是否有上游来源，推导图是否有环或不可达节点；
- 公式是否孤立、机制是否没有进入 objective/terminal；
- Cholesky、inverse、log、sqrt、CVaR 等操作是否写出完整关键前提；空的 `verification` 对象不再算作有验证。

它是结构和前提检查，不是万能证明器；代数等价性、题意适配和结论合理性仍需 W2 独立审阅。

## Assumption Fork（题意歧义预检）

遇到会决定后续所有问题的歧义措辞（"可视为""允许""消纳比例""损耗""满意度""最大能力""近似认为"、附件中含义不明的比例/容量等），必须在 `assumption_forks` 中登记，而不是直接选一个解释往下做：

- 每个 fork 至少给出两种 `interpretations`，各写清 `meaning` 和 `mathematical_effect`（它会如何改变模型）。
- `checks` 至少列出用题面、附件、单位一致性和下游边际影响做的判别检查。
- 两种结局只能取其一：选定则写 `selected` + `selection_reason`；无法判断则写 `unresolved_risk`，并把它同步进选型决策的 `unresolved_risks` 或 `research_basis.unresolved_questions`，不允许静默吞掉。自动拆题器输出的是 pending candidate seeds，不得直接当作选定解释。
- `check_modeling_plan.py --formal` 是 L1 完整性/证据链门槛：会拒绝零候选搜索、未绑定 evidence 的外部检索、未点名选中候选的理由和没有风险处置的决策；它不替代队员对机制合理性的判断。
- 历史统计平均值不能自动升级为逐时硬约束；没有题面或附件依据时这是默认错误方向。

## Typed Parameter Provenance

`parameter_plan` 不再接受自由文本来源。每个参数必须声明六类之一，并补齐该类义务字段：

| type | 适用 | 强制字段 |
| --- | --- | --- |
| `GIVEN` | 题面/附件直接给定 | `source_locator` |
| `DERIVED` | 由其他量推导 | `derivation_chain` + `source_variables` |
| `ESTIMATED` | 由样本估计 | `estimator` + `sample_scope` + `uncertainty` |
| `CALIBRATED` | 拟合/标定得到 | `calibration_data` + `calibration_objective` + `independent_validation` |
| `ASSUMED` | 无依据假设 | `reason` + `range` + `sensitivity` |
| `POLICY` | 官方规则/政策 | `official_source` + `rule_snapshot` |

## Model Identity

凡模型名称或目标涉及风险度量（CVaR、mean-variance 等），必须填写 `identity`：

- `canonical_name` / `mathematical_class` / `objective_form` 锁定"这个模型在数学上到底是什么"；论文、摘要、代码注释只能使用 `canonical_name`。
- `forbidden_aliases` 列出禁止出现的近似名称（例如合同是 Mean-CVaR 时禁止写 Mean-Variance）；确定性 QA 会扫描摘要与正文。
- `defining_equations` 引用 `equation_plan` 中真正定义该模型的公式 id，把名称绑定到公式而不是绑定到措辞。

涉及 CVaR 的模型还必须填写 `risk_semantics`（`random_variable`=profit/loss、`tail`=upper/lower、`confidence_level`、`objective_direction`）；涉及相关输入的模型必须填写 `correlation_spec`（来源、样本范围、维度、最小特征值、对称/有界/PSD 检查）。有限数学语义检查见 [Math Semantic Checks](../validation/math_semantic_checks.md)。
