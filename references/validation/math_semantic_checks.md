# Math Semantic Checks（有限数学语义检查）

不做通用自动证明，只检查比赛中高频且致命的错误。确定性脚本：

```powershell
python scripts/qa/check_math_semantics.py `
  --model-contract model_contract.json `
  --frozen-results results/frozen_results.json `
  --abstract paper/abstract.txt `
  --paper paper/main.tex `
  --conclusion paper/conclusion.txt `
  --strict
```

合同级检查在 M1 由 `check_modeling_plan.py` 一并执行；文本级检查需要摘要/正文，在 W2 前后执行。

## 检查清单

### 1. Assumption Fork 完整性

- `selected` 必须是已声明的 interpretation id，且必须附 `selection_reason`；
- 未选定的 fork 必须写 `unresolved_risk`，并同步出现在 `research_basis.unresolved_questions` 或该问决策的 `unresolved_risks` 中——不允许静默丢弃歧义。

### 2. Model Identity 漂移

- 模型名/目标/算法涉及风险度量族（CVaR、mean-variance 等）时必须声明 `identity`；
- 摘要、正文、结论中出现 `identity.forbidden_aliases` 即 FAIL（例：合同是 Mean-CVaR，摘要写 Mean-Variance）。

### 3. CVaR 语义

模型文本提到 CVaR 时必须声明 `risk_semantics`：

- `random_variable` 是 profit 还是 loss；
- `tail` 是 upper 还是 lower；
- `confidence_level` 严格在 (0, 1)；
- 方向约定：loss+upper ⇒ `minimize`；profit+lower ⇒ `maximize`；loss+lower / profit+upper 属于非常规组合，直接 FAIL。

### 4. 相关矩阵与 Cholesky

- `characteristics` 含 `correlated_inputs` 必须声明 `correlation_spec`：来源、样本范围、维度、最小特征值，且 `in_unit_interval`/`symmetric`/`psd_verified` 均为 true；
- 任何公式或算法提到 Cholesky，`min_eigenvalue` 必须严格大于 0（PD，不只是 PSD）。

### 5. 全局最优性语言

摘要/正文/结论出现"全局最优 / global optimum"等措辞时，合同中必须至少有一条 validation obligation 的 method 或指标记录 gap / bound / optimal 证据，否则 FAIL。solver 设置了 gap 容差不等于已证明全局最优。

### 6. 结果值域

- unit 为 `probability` 的冻结结果必须在 [0, 1]；
- unit 为 `correlation` 的冻结结果必须在 [-1, 1]。

### 7. Unit / Scale 漂移

冻结结果声明了 `display_label`/`display_unit`（如"百万元"）后，摘要/正文/结论中同一 `display_value` 紧邻出现其他货币量级词（元/万元/亿元等）即 FAIL。同一数字的 canonical value、展示值与量纲必须来自同一份冻结语义。

### 8. 论断强度

`paper_plan.claims[].inference_strength` 用来防止 Writer 把观察自动改写成机制或因果：

- `descriptive`：只描述冻结结果；
- `associational`：有比较或共同变化，但不宣称机制；
- `mechanistic`：必须有机制推导、组成/边际分析或消融等支持；
- `causal`：默认不从普通优化结果推出，除非 claim 额外登记了 `causal_design` 因果研究设计。

Observation 不能标成 `mechanistic` 或 `causal`。没有登记时，Writer package 采用保守默认：observation 为 descriptive，inference/recommendation 为 mechanistic，并保留原边界。

## 对应失败卡

这些检查与 `references/cards/failures/` 的失败模式一一对应（CVaR 符号、PSD、伪 OOS、单位漂移、全局最优过度声明等）。每次真实比赛踩坑后：先在这里加确定性检查或失败卡，再加 regression test。
