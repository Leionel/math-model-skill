# Failure Card: Empirical Correlation Matrix is Not Automatically PSD (经验相关矩阵未验半正定导致分解崩溃)

## 1. 错误形式
作者使用历史多维数据直接调用 `df.corr()` 或手工填补部分相关系数，直接传入 `np.linalg.cholesky(corr_matrix)` 进行多变量随机抽样，程序运行时抛出致命异常：
```text
numpy.linalg.LinAlgError: Matrix is not positive definite
```

## 2. 为什么错
- **缺失数据与成对删除（Pairwise Deletion）**：当不同变量的有效样本周期不完全一致时，分别两两计算相关系数拼凑出的方阵，在数学上不保证是半正定矩阵（Positive Semi-Definite Matrix）；
- **对角线占优破坏**：手工设定或组合多个来源的相关系数可能破坏多维向量内积空间的几何相容性（如 $A$ 与 $B$ 高度正相关，$B$ 与 $C$ 高度正相关，但设定 $A$ 与 $C$ 负相关，在欧氏空间中不存在对应的向量几何）。

## 3. 最小反例
构建矩阵：
\[
\Sigma = \begin{pmatrix} 1.0 & 0.9 & -0.9 \\ 0.9 & 1.0 & 0.9 \\ -0.9 & 0.9 & 1.0 \end{pmatrix}
\]
该矩阵行列式 $\det(\Sigma) = -1.432 < 0$，最小特征值 $\lambda_{\min} = -0.71 < 0$，根本不是合法的协方差矩阵，无法进行概率抽样！

## 4. Harness 应如何发现与拦截
- **Precondition 拦截（`check_modeling_plan.py`）**：在执行 Cholesky 分解前，强制调用特征值分解 `min(eigvals) >= -1e-7` 校验；
- **自动修复引导**：若非半正定，自动执行 Higham 最近半正定矩阵投影算法（Nearest PSD Projection）进行数值平滑。

## 5. 论文中如何正确表达
“由历史观测样本估计得到经验相关系数矩阵后，采用 Higham 算法做最近半正定一致性修正，确保多维正态分布联合抽样的数学合法性。”
