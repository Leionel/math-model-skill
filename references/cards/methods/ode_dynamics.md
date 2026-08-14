# Method Card: Ordinary Differential Equations Dynamics (ODE / 常微分方程动力学)

## 1. 解决什么问题
连续时间演化系统、种群竞争捕食模型（Lotka-Volterra）、流行病传播（SIR/SEIR/SEIR-Q）、物理运动轨迹、热力传导与化学反应动力学。

## 2. 不适合什么问题
- 纯离散组合优化决策（如排班、路线组合，应采用 MILP）；
- 缺乏机理公式且数据维度极高的高维静态回归问题。

## 3. 最低数据条件
- 系统状态变量初始值 $y(0) = y_0$；
- 状态转移速率参数（如感染率 $\beta$、康复率 $\gamma$、出生率、死亡率）；
- 仿真时间跨度 $[t_0, t_{\text{end}}]$。

## 4. 核心数学结构
\[
\frac{d \mathbf{y}}{dt} = \mathbf{f}(t, \mathbf{y}, \boldsymbol{\theta}), \quad \mathbf{y}(t_0) = \mathbf{y}_0
\]
质量/守恒律约束（如 SIR 守恒 $S(t) + I(t) + R(t) = N$）。

## 5. 参数来源要求
- 物理常量必须注明 `GIVEN` 或文献来源；
- 速率参数由历史数据拟合时必须注明 `CALIBRATED` 并给出拟合目标函数（如最小化残差平方和 $L_2$ 范数）及置信区间。

## 6. 推荐 Baseline
- 静态趋势外推（如指数增长模型或逻辑斯蒂单变量拟合）；
- 无干预基础模型（Uncontrolled Baseline）。

## 7. 必须验证的东西
- **守恒律检验（Conservation Law）**：例如种群总数/能量总和在时间步进中守恒误差 $< 10^{-4}$；
- **数值积分收敛性（Numerical Stability）**：RK45 vs 刚性求解器（Radau/BDF）步长敏感性检验；
- **退化测试（Degeneration Test）**：当关键参数取 0 或极限值时（如 $\beta = 0$ 感染率归零），系统应退化为确定常数或无传播状态。

## 8. 常见数学错误
- 状态导数单位与状态变量单位不匹配（如漏乘时间单位系数）；
- 忽略状态变量的非负物理边界（出现 $S(t) < 0$ 的非物理负数）；
- 参数辨识时直接用差分近似微分却未进行误差控制。

## 9. 常见代码错误
- `scipy.integrate.solve_ivp` 中时间跨度 `t_span=(0, T)` 与评估点 `t_eval` 格式混淆；
- 参数解包顺序与导数函数定义不一致。

## 10. 论文表达规范
- 必须明确给出微分方程状态定义、参数物理意义及守恒律推导；
- 给出相空间轨迹图（Phase Plane Portrait）或时域演化包络线。

## 11. 推荐实现入口
`scripts/scaffold/ode_system.py`
