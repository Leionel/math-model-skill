# Validation Profile：评价/排序类（AHP/TOPSIS/熵权/综合评价）

触发：`problem_type` 为 evaluation / ranking。

## 最低义务

1. **权重扰动**：权重或参数扰动下排序稳定性（`sensitivity`，需逐格重跑回执）。
2. **尺度与归一化**：归一化方法、方向处理声明；无量纲量写 dimensionless（`scale_check`）。
3. **基线**：与简单加权/单一指标排序比较（`baseline`）。

## 按特征追加

- 主观权重（AHP 类）：一致性比率检查；主观/客观权重组合方式声明。
- 分组评价：组间可比性与同口径声明。
- 相关输入：`correlation_spec`（PSD/最小特征值），见 `correlation_matrix_not_automatically_psd`。

## 常见失败

权重来路不明（ASSUMED 未做敏感性）、不同归一化口径混排、"TOPSIS 贴近度"当物理量解释。
