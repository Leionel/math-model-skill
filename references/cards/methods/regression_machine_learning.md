# Method Card: Regression & Machine Learning (机器学习与正则化回归)

## 1. 解决什么问题
多变量高维特征拟合、非线性响应面建模、特征重要性筛选、分类判别与预测回归。

## 2. 不适合什么问题
- 强机理微分方程驱动的物理动态系统（纯黑箱模型往往外推崩溃且违背物理守恒）；
- 样本量极小（$N < 20$）且特征数极多的情况（极易过拟合，应优先使用线性模型或岭回归）。

## 3. 最低数据条件
- 特征矩阵 $X \in \mathbb{R}^{N \times P}$，目标向量 $y \in \mathbb{R}^N$；
- 明确的训练集/验证集/测试集划分方案。

## 4. 核心数学结构
1. **Lasso / Elastic Net 正则化**：
   \[
   \min_{\beta} \frac{1}{2N} \|y - X\beta\|_2^2 + \lambda \left( \alpha \|\beta\|_1 + \frac{1-\alpha}{2} \|\beta\|_2^2 \right)
   \]
2. **梯度提升决策树（GBDT / LightGBM）**：
   \[
   \mathcal{L}^{(t)} = \sum_{i=1}^N \left[ g_i f_t(x_i) + \frac{1}{2} h_i f_t^2(x_i) \right] + \Omega(f_t)
   \]

## 5. 参数来源要求
- 超参数（学习率 $\eta$、正则化系数 $\lambda$、树深、叶子数）必须经网格搜索或贝叶斯优化（Optuna）在验证集（Validation Set）上确定，严禁在测试集上调参！

## 6. 推荐 Baseline
- 普通最小二乘线性回归（OLS Linear Baseline）；
- 均值恒等预测模型（Mean Predictor Baseline）。

## 7. 必须验证的东西
- **独立测试集评估（True OOS）**：汇报测试集 RMSE, MAE, $R^2$ 或 Classification AUC/F1；
- **特征共线性诊断**：计算方差膨胀因子（VIF $\le 10$）或特征相关矩阵；
- **残差正态性与同方差性检验**：残差图不应呈现明显漏斗形或弯曲趋势；
- **SHAP 解释力一致性**：特征重要性与物理/经济学常识方向一致。

## 8. 常见数学错误
- 数据标准化/归一化（StandardScaler）在切分数据集之前对全量数据执行（导致数据穿越）；
- 评价指标误用：对不平衡分类问题只汇报 Accuracy（此时必须使用 Precision-Recall AUC 或 F1-score）。

## 9. 常见代码错误
- 未固定 `random_state` / `seed` 导致模型结果不可复现；
- 树模型叶子节点最小样本数设为 1 导致训练集过拟合。

## 10. 论文表达规范
- 汇报特征重要性排序图（Feature Importance / SHAP Summary Plot）；
- 给出训练误差 vs 测试误差学习曲线，证明未出现严重过拟合。
