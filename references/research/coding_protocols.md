# Coding Protocols: 操作性编码协议（防泄漏 / 读入回退 / 求解器鲁棒）

> 边界：本文给出 solve 阶段"怎么写代码才稳"的操作性协议（协议编号 `CP-*`），被
> `harness solve --tasks` 投影到每个实现任务的「鲁棒性检查清单」里。它不重复
> `model_contract.md` 的字段规则，也不替代 [model_to_code_handoff.md](model_to_code_handoff.md)
> 的任务切片与失败升级流程；协议触发失败证据如何处置，仍走那里的 escalation 路由。

## 何时加载

进入 solve 阶段、开始写实现代码之前。实现任务视图（`.harness/views/IMPLEMENTATION_TASKS.md`）
会按 `problem_type` / `characteristics` 列出本任务适用的协议 ID；拿不准时回到本文查全文。

## 1. 防泄漏协议（预测/时序类必读）

- **CP-LEAK-01 只在训练集上 `fit`。** 标准化、编码器、插值器、填充器、PCA 等一切从数据
  学习的预处理，先划分后拟合：`fit` 只用训练段，测试段只允许 `transform`。预测类特征
  构造使用 `shift(1)` 或更远的滞后，禁止用同期或未来列直接入特征。
  （对应失败卡 [imputation_leakage](../cards/failures/imputation_leakage.md)）
- **CP-LEAK-02 时序严禁未来数据。** 禁止双向滤波/中心移动平均、全局标准化
  （`StandardScaler().fit(全量)`）、随机 K-fold 切分时间序列；切分必须按时间边界单调，
  滚动统计只回看历史，填充只允许前向（`ffill`）或仅历史窗口。
  （对应失败卡 [leakage_future_data](../cards/failures/leakage_future_data.md)）

## 2. 编码与读入回退协议

- **CP-DATA-01 多编码回退。** 读入文本/CSV 按 `utf-8 → gbk/gb18030 → latin-1` 顺序尝试，
  记录最终生效编码；解析错误先抽 10 行坏样本定位，再决定回退编码，而不是静默
  `errors="ignore"`。
- **CP-DATA-02 大文件分块与降类型。** `>1GB` 的 CSV 分块读取（`chunksize`），进内存前
  降类型（`int64→int32`、`float64→float32`、高基数类别列先计数再决定是否 category）；
  分块聚合结果要与抽样全量核对一次量级。
- **CP-DATA-03 缺失值策略要登记。** 缺失比例、推断的缺失机制（MCAR/MAR/MNAR）、所选
  填充方法与"只用训练期统计量"的保证，写进数据决策（作者面），不允许代码里随手
  `fillna(0)` 不留痕。

## 3. 求解器与数值鲁棒清单（9 点）

1. **CP-NUM-01 防溢出：** 概率/指数运算使用稳定实现（log-sum-exp、`scipy.special.expit`、
   对数域运算），禁止对大量级数值直接 `exp` 求和。
2. **CP-NUM-02 病态矩阵：** 求逆/解线性系统前估计条件数；`cond > 1e7` 时改用 `pinv` 或
   正则化（岭/截断 SVD），并在报告中登记处理动作。
3. **CP-SOLVE-01 超时退化：** 求解前约定退化路径（缩减规模、放松容差、换启发式），
   超时触发时按路径执行并登记退化前后的目标值对比，不允许无限等待或静默截断。
4. **CP-RAND-01 多种子：** 随机成分（Monte Carlo、GA/SA/PSO、随机划分、Bootstrap）
   ≥3 个固定 seed 重复，报告均值±离散度；所有 seed 随命令登记进 receipt。
   （对应失败卡 [no_seed_single_run](../cards/failures/no_seed_single_run.md)）
5. **CP-UNIT-01 量纲与上下界：** 求解前后各做一次 sanity 检查——输入输出量纲一致、
   变量落在合同声明的上下界内、结果量级与题意吻合（元/万元/百万元不混用）。
   （对应失败卡 [unit_value_scale_drift](../cards/failures/unit_value_scale_drift.md)）
6. **CP-SOLVE-02 Big-M 不失真：** 逻辑/分段线性化的 M 必须有紧上界推导式并写入参数计划
   （`DERIVED` provenance）；`M > 1e5` 触发人工质询。宁可用紧 M 的指示约束重构，
   不用 `1e9` 级别的松弛常数。
   （对应失败卡 [unrealistic_big_m](../cards/failures/unrealistic_big_m.md)）
7. **CP-SOLVE-03 对偶/间隙要报告：** 优化结果必须记录求解器状态与 gap/收敛回执；
   提前终止、达到容差或非凸局部解，一律不得表述为"全局最优"，只能写"gap ≤ x% 的
   可行解"。
   （对应失败卡 [solver_gap_not_global_optimum](../cards/failures/solver_gap_not_global_optimum.md)）
8. **CP-OUT-01 输出拦截：** 结果落盘前检查 NaN/inf 与量级异常；发现异常先查根因
   （边界、初值、数据），不得静默丢弃或替换。
9. **CP-EVID-01 失败留证：** 运行失败时保存命令、堆栈、预期 vs 实际；先区分实现问题
   （修代码重跑）与合同问题（携最小复现回 M1），禁止在代码里静默改数学让它跑通。

## 4. 协议 → 任务视图的映射

`harness solve --tasks` 按以下规则把协议注入每个 `IMPL-*` 任务：

- **基础集（所有任务）：** CP-DATA-01、CP-DATA-03、CP-UNIT-01、CP-OUT-01、CP-EVID-01。
- **按 `problem_type` 追加：** `prediction` / `classification` / `statistical_inference`
  追加 CP-LEAK-01；`time_series` 追加 CP-LEAK-01 + CP-LEAK-02；
  `optimization` 追加 CP-NUM-02、CP-SOLVE-01、CP-SOLVE-02、CP-SOLVE-03；
  `simulation` 追加 CP-RAND-01；`differential_equation` 追加 CP-NUM-01。
- **按 `characteristics` 追加：** `stochastic` → CP-RAND-01；
  `machine_learning` → CP-LEAK-01；`time_dependent` → CP-LEAK-02。

清单是"这题容易踩的坑"的起点，不是上限：任务实现中发现的新风险按
[model_to_code_handoff.md](model_to_code_handoff.md) 的失败分类处置。

## 边界

- 协议不新增契约或 Gate；它们是编码操作规范，违反后果体现在复现失败与评审扣分。
- 协议文本变更需同步更新 `scripts/views/implementation_tasks.py` 中的映射表与相关测试。
