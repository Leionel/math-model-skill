# Method Card: Monte Carlo & Latin Hypercube Simulation (蒙特卡洛与拉丁超立方仿真)

## 1. 解决什么问题
系统包含多维随机变量、非线性传递函数、无法求得解析积分的概率估算、可靠性评定、排队系统仿真与极端风险压力测试。

## 2. 不适合什么问题
- 可以直接求得精确解析解（Closed-form Solution）的低维确定性系统；
- 目标函数需要精确解析导数进行梯度快速优化的连续凸规划问题。

## 3. 最低数据条件
- 各输入随机变量的概率密度函数（PDF / CDF）或经验抽样样本；
- 变量间的相关结构（如 Pearson 相关矩阵或 Copula 函数）；
- 仿真迭代总次数 $N$（建议 $N \ge 10000$ 或拉丁超立方 $N \ge 1000$）。

## 4. 核心数学结构
1. **逆变换抽样法（Inverse Transform Sampling）**：
   \[
   U \sim \text{Uniform}(0, 1) \implies X = F^{-1}(U)
   \]
2. **拉丁超立方抽样（LHS / Latin Hypercube Sampling）**：
   将每个随机变量的累积概率区间 $[0, 1]$ 均匀等分为 $N$ 个区间，在每个区间内各随机抽取一个点，并进行随机排列组合，保证高维样本在边际分布上的均匀分层覆盖。
3. **相关性生成（Cholesky 分解）**：
   若相关矩阵 $\Sigma = L L^T$（$\Sigma$ 必须半正定！），则标准正态独立向量 $Z$ 变换为相关向量 $X = \mu + L Z$。

## 5. 参数来源要求
- 分布类型与参数必须标明拟合方法（如最大似然估计 MLE 或矩估计）并通过 K-S 拟合优度检验（Kolmogorov-Smirnov Test, $p > 0.05$）。

## 6. 推荐 Baseline
- 确定性均值单点代入法（Deterministic Point Estimation）；
- 伪随机独立抽样对比基准。

## 7. 必须验证的东西
- **相关矩阵半正定性（PSD Check）**：$\Sigma$ 的所有特征值 $\lambda_i \ge -10^{-8}$；
- **抽样收敛性检验（Monte Carlo Convergence）**：随抽样次数 $N$ 增加，输出统计量（均值、方差、95% 分位数）的相对变化率 $< 0.5\%$；
- **置信区间报告（Confidence Interval）**：根据大数定律与中心极限定理，报告估计值 $\hat{\theta}$ 的 95% 置信区间 $\hat{\theta} \pm 1.96 \frac{\hat{\sigma}}{\sqrt{N}}$。

## 8. 常见数学错误
- 经验相关矩阵因数据噪声存在轻微负特征值，直接调用 `np.linalg.cholesky` 导致程序崩溃抛出 `LinAlgError`（必须先做 `nearest_psd` 投影）；
- 将蒙特卡洛抽样得到的结果直接宣称为“模型通过了样本外泛化（OOS）验证”（抽样只是对已知分布的数值积分计算，不是真正未知数据的真实外推验证！）。

## 9. 常见代码错误
- 未设置伪随机数种子 `np.random.seed()` 导致每次运行输出数值完全不同；
- 循环中使用低效纯 Python append 导致大样本仿真耗时失控（应全部采用 NumPy 向量化操作）。

## 10. 论文表达规范
- 绘制蒙特卡洛模拟收敛轨迹图（X 轴为仿真步数 $N$，Y 轴为均值与 95% 置信带）；
- 输出指标的经验累积分布函数（ECDF）与核密度估计（KDE）分布图。
## 11. 典型优秀论文机制
- 方差缩减：对偶变量（Antithetic）与控制变量（Control Variates）在同样 $N$ 下压缩置信带；
- 尾部估计用重要抽样（Importance Sampling）而不是盲目加大 $N$。

## 12. 推荐实现入口
numpy 向量化抽样 + `scipy.stats`（分布拟合与 K-S 检验）；收敛轨迹与分位数落盘 `results/` 供冻结。
