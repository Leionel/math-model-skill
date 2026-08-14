# Problem Pattern Card: Uncertainty & Stochastic Optimization (不确定性与随机/鲁棒规划)

## 1. 典型业务结构
系统输入参数（如未来市场电价、自然灾害概率、订单需求波动、风光发电量）存在不可忽视的不确定性，决策者需要在“期望收益”与“尾部风险控制”之间做出权衡。

## 2. 常见比赛翻车陷阱
- **CVaR 符号体系混淆**：未声明随机变量代表 Profit（收益，关注左尾极小值）还是 Loss（损失，关注右尾极大值），导致优化方向和约束符号彻底写反；
- **伪 Out-of-Sample（Fake OOS）**：在训练情景上调参并直接在该情景集上汇报泛化指标，未做真正独立的情景抽样隔离；
- **相关矩阵非半正定（Non-PSD）**：通过历史样本经验估计相关系数矩阵时，未做半正定校验或最近半正定投影（Nearest PSD），导致 Cholesky 分解报错或多维高斯抽样崩溃；
- **历史平均值直接当作硬约束**：如将“历史平均消纳率 20%”误写成每小时最大消纳上限 $R_t \le 0.2 \cdot R^{\text{avail}}_t$。

## 3. 标准推荐实战流水线
1. **明确不确定性源头与分布形态**：正态、对数正态、经验经验分布或有界不确定集合；
2. **多情景生成与独立隔离**：
   - 训练情景集 $\mathcal{S}_{\text{train}}$（用于模型求解）；
   - 测试情景集 $\mathcal{S}_{\text{test}}$（真正独立随机抽样，用于 OOS 验证，记录不同 Seed 与 SHA）；
3. **风险度量公式显式化**：
   \[
   \min_{x, \alpha, u_s} \quad \mathbb{E}[C(x, \xi)] + \lambda \left( \alpha + \frac{1}{(1-\beta)S} \sum_{s=1}^S u_s \right)
   \]
   \[
   \text{s.t.} \quad u_s \ge C(x, \xi_s) - \alpha, \quad u_s \ge 0
   \]
4. **退化检验（Degeneration Check）**：
   - 当风险厌恶系数 $\lambda = 0$ 时，模型必须严格退化为“风险中性期望成本最小化”；
   - 当不确定性方差 $\sigma^2 = 0$ 时，模型必须严格退化为确定性 MILP。

## 4. 论文表达规范
- 明确汇报：置信水平 $\beta$（如 0.95）、情景数 $S$、风险权重 $\lambda$、样本内外表现差（OOS Performance Gap）；
- 绘制 Pareto 风险-收益前沿曲线，标明当前推荐工作点。
