# Validation Profile：仿真/随机类（Monte Carlo、排队、随机规划）

触发：`characteristics` 含 uncertainty / scenario_generalization 或模型含随机输入。

## 最低义务

1. **重复次数与方差**：重复运行的置信区间或方差控制（`stability`）；单次运行不得作结论。
2. **随机种子**：固定并登记；claimable 结果必须可重放（freeze 绑定 seed）。
3. **warm-up**（稳态系统）：预热期剔除声明。
4. **基线/解析对照**：存在解析解或极限情形时必须对照（`baseline`）。

## 按特征追加

- `correlated_inputs`：`correlation_spec` 与 PSD 检查；Cholesky 要求 PD。
- 场景随机规划：`nonanticipativity`（决策不依赖未实现场景）。
- `out_of_sample`：独立场景集 + `oos_artifact`（场景身份摘要防复用）。
- 尾部风险（CVaR 类）：`risk_semantics` 完整声明（`cvar_profit_loss_sign`）。

## 常见失败

`monte_carlo_not_oos`、场景集复用当 OOS、收敛曲线替代稳定性证据。
