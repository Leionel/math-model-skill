# Method Card: Mixed-Integer Linear Programming (MILP / 混合整数线性规划)

## 1. 解决什么问题
离散决策、设施选址、任务调度、多阶段种植规划、网络流分配、资源受限匹配等确定性组合优化问题。

## 2. 不适合什么问题
- 强非线性动力学过程（如流体、微分方程系统，应采用 ODE 或非线性规划）；
- 目标与约束无法通过线性化或 Big-M 转换的问题；
- 超大规模维数（变量数 > 10^6 且无法分解，此时需配合列生成、Benders 分解或元启发式）。

## 3. 最低数据条件
- 明确的成本/收益单价矩阵；
- 明确的容量/资源上界向量；
- 确定的时间步长与离散集合定义。

## 4. 核心数学结构
\[
\min \quad c^T x + d^T y
\]
\[
\text{s.t.} \quad A x + B y \le b, \quad x \ge 0, \quad y \in \{0, 1\}^m
\]

## 5. 参数来源要求
- 资源上限、单价、固定成本必须标明 `GIVEN`（来自附件/题面）或 `ESTIMATED`（来自历史拟合）；
- Big-M 常数必须有物理紧上界（Tight Upper Bound），严禁随意设置 `M = 10^9` 导致数值病态。

## 6. 推荐 Baseline
- 规则启发式 / 贪心算法（Greedy Heuristic）；
- 现状基准（Current Practice Baseline / 到达即开工）；
- 连续松弛 LP（LP Relaxation）。

## 7. 必须验证的东西
- `variable_domains`：整型/0-1 变量是否严格满足二元/离散约束；
- `feasibility`：所有约束残差（Constraint Violation）$\le 10^{-6}$；
- `solver_status`：求解器返回值必须为 `OPTIMAL` 或明确给出 `actual_gap`；
- `tiny_instance_oracle`：在 3–5 个样本的小规模子集上与穷举枚举/经典解法对比，验证逻辑正确性。

## 8. 常见数学错误
- **伪线性化错误**：$x \cdot y$（两连续变量相乘）误当作线性；
- **Big-M 溢出或失效**：$M$ 取过小导致漏解，或取过大导致数值精度损失；
- **时序状态转移越界**：$t=1$ 时引用 $x_0$ 未设定初始状态，$t=T$ 时引用 $x_{T+1}$ 越界。

## 9. 常见代码错误
- 索引混淆（0-indexed vs 1-indexed）；
- 约束循环添加时遗漏条件过滤；
- 求解器未设置 TimeLimit 导致比赛中死锁。

## 10. 论文表达规范
- 只有求解器报告 `gap <= 1e-4` 且证明无误时才可使用“求得最优解”；未收敛时只能称“当前可行解 / 较优解”；
- 正文必须报告：决策变量数、约束数、求解器耗时、最终 Gap、相比基线的改善百分比。

## 11. 典型优秀论文机制
- 多阶段滚动优化（Rolling Horizon Optimization）；
- 带有逻辑约束的紧凑重构（Tight Formulation & Symmetry Breaking Constraints）。

## 12. 推荐实现入口
`scripts/scaffold/opt_milp.py`
