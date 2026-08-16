# Failure Card: Small-Sample Overfitting (小样本深度模型过拟合)

## 1. 错误形式
样本只有 8–15 期（或几十行截面数据），作者直接训练 LSTM/Transformer/XGBoost 并报告训练集 RMSE 极小，然后据此"预测/分类"出高精度结论；论文只展示拟合曲线，不做任何样本外检验。

## 2. 为什么错
- 参数量 >> 样本量时，模型可以记忆全部样本，训练误差对外推能力几乎没有信息量；
- 小样本下"验证集"也小，随机波动就能造成巨大误差估计方差；
- 时间序列里相邻点强相关，随机切分交叉验证会泄漏时间结构（历史拟合未来）。

## 3. 最小反例
10 期数据 $y = 2t + \epsilon$。线性拟合留出末 2 期误差 ≈ 噪声量级；而 4 层 LSTM 在训练点上误差≈0，外推第 11 期却可能给出完全离谱值（记忆了噪声拐点）。按训练误差选模型会选 LSTM，按留出误差必须选线性。

## 4. Harness 应如何发现与拦截
- `check_oos_artifact.py`：声称样本外/泛化必须绑定真实留出的 `oos_artifact`（独立场景身份 + 泄漏检查）；
- `check_data_contract.py`：重复测量/时序数据禁止 row 随机切分当主验证（`--require-statistical-design`）；
- `check_consistency.py --require-abstract-backcheck`：摘要中"精度 X%"须能回到冻结的留出指标；
- 人工边界（M1）：样本量 < 20 时选深度模型须给出对比 Baseline（朴素/线性/ARIMA）的留出误差证据，否则 `candidate_comparison_fairness` 不通过。参考 `problems/small_sample_forecasting`。

## 5. 论文中如何正确表达
"在样本量 $n=12$ 的约束下，我们对比了线性趋势、GM(1,1) 与 LSTM 的留一/末两期留出误差（表 X）；LSTM 训练误差最低但留出误差最高，故不采用。最终预测给出区间而非点值，并声明结论假设历史结构延续。"
