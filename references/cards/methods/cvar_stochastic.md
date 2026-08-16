# Method Card: Conditional Value at Risk (CVaR / 条件风险价值与随机规划)

## 1. 解决什么问题
在不确定性环境下（如电价剧烈波动、自然灾害、市场需求突变），对冲小概率但损失极大的“尾部极端风险”（Tail Risk），实现期望收益与极端损失控制的最优权衡。

## 2. 不适合什么问题
- 确定性无扰动问题；
- 风险中性决策（此时只需优化均值 $\mathbb{E}[X]$）；
- 样本/情景数极少（$S < 20$）导致尾部无法统计刻画的问题。

## 3. 最低数据条件
- $S$ 个具有代表性的离散扰动情景样本 $\xi_1, \dots, \xi_S$ 及其发生概率 $p_s$（通常 $p_s = 1/S$）；
- 明确的置信水平 $\beta \in (0, 1)$（数模竞赛常取 $\beta = 0.90$ 或 $0.95$）；
- 明确的风险规避偏好系数 $\lambda \ge 0$。

## 4. 核心数学结构 (Rockafellar-Uryasev 线性化)
设决策变量为 $x$，随机损失为 $L(x, \xi)$。
\[
\text{CVaR}_\beta(L(x, \xi)) = \min_{\alpha \in \mathbb{R}} \left\{ \alpha + \frac{1}{1-\beta} \sum_{s=1}^S p_s [L(x, \xi_s) - \alpha]^+ \right\}
\]
引入辅助松弛变量 $u_s \ge 0$，等价重构为线性规划（LP / MILP）：
\[
\min_{x, \alpha, \mathbf{u}} \quad \mathbb{E}[L(x, \xi)] + \lambda \left( \alpha + \frac{1}{(1-\beta)S} \sum_{s=1}^S u_s \right)
\]
\[
\text{s.t.} \quad u_s \ge L(x, \xi_s) - \alpha, \quad u_s \ge 0, \quad \forall s \in \{1, \dots, S\}
\]
\[
\text{物理约束:} \quad A x \le b
\]

## 5. 参数来源要求
- 情景样本 $\xi_s$ 必须标明来源：由历史数据拟合分布生成（`ESTIMATED`）或参数化蒙特卡洛抽样（`DERIVED`）；
- 必须严格区分训练情景集 $\mathcal{S}_{\text{train}}$ 与测试情景集 $\mathcal{S}_{\text{test}}$（记录不同 Seed 与哈希）。

## 6. 推荐 Baseline
- 风险中性期望值模型（Expected Value Baseline, $\lambda = 0$）；
- 最恶劣极端场景模型（Worst-case Robust Optimization, $\beta \to 1$）；
- 历史平均确定性基线（Deterministic Average Model）。

## 7. 必须验证的东西
- **收益/损失极性一致性（Sign Convention）**：若目标是最大化利润 $\Pi(x, \xi)$，则损失定义为 $L(x, \xi) = -\Pi(x, \xi)$；
- **退化检验（Degeneration Test）**：当 $\lambda = 0$ 时，模型结果必须严格等于风险中性最优解；
- **单调性检验（Monotonicity）**：随 $\lambda$ 增大，期望收益下降，尾部最大损失同步下降；
- **样本外回测（OOS Test）**：在未参与优化的独立测试集上评估真实 CVaR 达标率。

## 8. 常见数学错误
- 混淆收益（Profit）与损失（Loss），导致把“最大化左尾期望”写成“最小化左尾期望”，使得优化往更危险的方向移动；
- $\alpha$（即 VaR 阈值）误限制为非负数（当可能存在全局盈利时，$\alpha$ 可为负数，必须设为自由变量 `free variable`）。

## 9. 常见代码错误
- $u_s \ge L(x, \xi_s) - \alpha$ 中的减号写成加号；
- 分母 $(1-\beta)$ 误写为 $\beta$。

## 10. 论文表达规范
- 绘制 Pareto 风险-收益权衡曲线（X 轴为 CVaR 尾部损失，Y 轴为期望收益）；
- 给出不同 $\lambda$ 取值下的调度决策对比，解释风险规避对决策的物理重构意义。
## 11. 典型优秀论文机制
- 场景法两阶段随机规划：第一阶段 here-and-now 决策 + 第二阶段 recourse 校正，CVaR 只约束第一阶段成本尾部分布；
- 对风险权重 $\lambda$ 与置信水平 $eta$ 做网格扫描，输出完整风险-收益前沿并标注推荐工作点。

## 12. 推荐实现入口
场景线性化后按 MILP 求解：`scripts/scaffold/opt_milp.py`；黑箱版对照 `scripts/scaffold/metaheuristics.py`。
