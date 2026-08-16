# Validation Profile：预测/分类/时间序列类

触发：`problem_type` 为 prediction / classification / time_series，或特征含 `machine_learning`。

## 最低义务

1. **先划分后拟合**：一切从数据学习参数的预处理只在训练折 fit（`leakage`）。
2. **样本外评估**：独立测试场景/时间；训练集内交叉验证不得称 OOS（`out_of_sample`，需 `oos_artifact`）。
3. **朴素基线**：均值/上期值/线性外推等 comparator（`baseline`）。
4. **重复测量**：观测单元为实体而非行时，分组切分；主验证不得用 row CV（T-NIPT-06）。

## 按特征追加

- `time_series`：时间边界声明、滚动/留出窗口口径、未来特征在决策时点的可用性（T-NIPT-02）。
- 概率输出：值域 [0,1] 与校准检查。
- 区间预测：区间口径（置信/预测）与覆盖率。

## 常见失败

`leakage_future_data`、`monte_carlo_not_oos`、把 RMSE 下降写成因果结论。
