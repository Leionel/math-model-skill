# Method Card: ARIMA & SARIMAX (自回归差分移动平均与季节时序预测)

## 1. 解决什么问题
具有明显时间依赖、自相关性、线性趋势与固定周期季节性（如日周期、周周期、年周期）的一维或带外生变量的时序预测。

## 2. 不适合什么问题
- 强非线性突变动力系统或混沌系统；
- 样本点极少（$N < 30$）的时序数据；
- 采样间隔不均匀、存在大量随机缺失且无法插补的数据。

## 3. 最低数据条件
- 等时间间隔采样的连续时序序列 $y_1, y_2, \dots, y_T$；
- 明确的时间频率（如小时 `H`、日 `D`、月 `M`）。

## 4. 核心数学结构
$\text{SARIMA}(p, d, q) \times (P, D, Q)_s$：
\[
\Phi_P(B^s) \phi_p(B) (1 - B)^d (1 - B^s)^D y_t = \Theta_Q(B^s) \theta_q(B) \epsilon_t
\]
其中 $B$ 为滞后算子（$B^k y_t = y_{t-k}$），$s$ 为季节周期长度，$\epsilon_t \sim \mathcal{N}(0, \sigma^2)$ 为白噪声序列。

## 5. 参数来源要求
- 差分阶数 $d, D$ 由 ADF 单位根平稳性检验（Augmented Dickey-Fuller Test）确定；
- 阶数 $(p, q, P, Q)$ 结合 ACF/PACF 截尾拖尾特征与 AIC/BIC 信息准则网格搜索确定。

## 6. 推荐 Baseline
- **Seasonal Naive（季节朴素基线）**：$\hat{y}_{t+h} = y_{t+h-s}$；
- **Historical Average / Moving Average**：历史滑动均值基线。

## 7. 必须验证的东西
- **平稳性检验（Stationarity）**：差分后序列 ADF 检验 $p$-value $< 0.05$；
- **残差白噪声检验（Ljung-Box Test）**：拟合残差自相关检验 $p$-value $> 0.05$（证明时序信息已被模型充分提取，残差无自相关残留）；
- **时间切分验证（Time-based Train/Val/Test Split）**：严禁 K-fold 随机交叉验证（会产生未来数据泄漏），必须采用时间顺序切分。

## 8. 常见数学错误
- 过度差分（Over-differencing）引入人工负自相关；
- 忽略非平稳序列直接拟合 ARMA；
- 评估预测精度时只在训练集上汇报，未做独立测试集（Out-of-Sample）评估。

## 9. 常见代码错误
- 预测步长与时间索引未对齐；
- 预测区间置信度计算未随步长 $h$ 扩大而展宽。

## 10. 论文表达规范
- 按 claim 选择证据：平稳性/差分选择可用时域与 ACF/PACF 诊断；残差假设成为结论前提时再给残差诊断；预测性能结论优先给测试期真实值、预测区间与 Baseline 的同口径比较。不要把这些图列成固定配额；
- 指标只报告与任务损失相符且已登记定义的项目，并给出相同切分下的 Baseline；不默认每题都同时需要 MAE、RMSE 和 MAPE。
## 11. 典型优秀论文机制
- 滚动起点验证（Rolling-Origin / Time-Series Cross-Validation）替代单次切分，报告多窗口平均误差；
- ARIMAX 引入外生变量（气温/价格/政策哑变量）解释结构变化，减少纯 AR 项背锅。

## 12. 推荐实现入口
`statsmodels.tsa.arima.model.ARIMA` / `statsmodels.tsa.statespace.SARIMAX`（需自行安装 statsmodels）；ADF/Ljung-Box 用 `statsmodels.tsa.stattools`。
