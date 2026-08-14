# Failure Card: Dominated Points Mislabeled as Pareto Frontier (被支配点集误标为Pareto前沿)

## 1. 错误形式
在多目标优化或多权重扫描实验中，散点图中某点 A 的各项指标（如成本和碳排放）均低于点 B（即点 A 在两个目标上均更优），但作者仍将点 B 连入曲线并冠以“Pareto 前沿”标题。

## 2. 为什么错
- **违反 Pareto 最优定义**：Pareto 前沿（Non-dominated Frontier）上的任意一点，都不应存在另一个可行方案在所有目标上都不弱于它且至少一个目标严格优于它；
- 若点 B 被点 A 严格支配（Dominated），点 B 属于劣解，绝不能进入 Pareto 前沿集合。

## 3. 最小反例
- 方案 1：成本 100 万元，碳排 50 吨；
- 方案 2：成本 120 万元，碳排 60 吨。
显然方案 2 被方案 1 完全支配，任何理性决策者都不会选择方案 2。

## 4. Harness 应如何发现与拦截
- 执行 `scripts/validation/check_pareto.py` 自动化多目标非支配排序筛选；
- 若存在被支配点，禁止使用 `Pareto Frontier` 标题，自动降级为 `Parameter Sweep Trajectory / 候选方案权重扫描轨迹`。

## 5. 论文中如何正确表达
“经过严格非支配排序筛选后，实线标出真实的非支配 Pareto 前沿；空心散点代表被支配的次优解。”
