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
该矩阵行列式 $\det(\Sigma) = 1 + 2(0.9)(-0.9)(0.9) - 3(0.9^2) = -2.888 < 0$，特征值为 $\{1.9,\ 1.9,\ -0.8\}$，最小特征值 $\lambda_{\min} = -0.8 < 0$，根本不是合法的协方差矩阵，无法进行概率抽样！

## 4. Harness 应如何发现与拦截
- **合同强制声明（`check_modeling_plan.py` + `check_math_semantics.py`）**：`characteristics` 含 `correlated_inputs` 时必须声明 `correlation_spec`（来源、样本范围、维度、最小特征值），且 `psd_verified=true` 才能通过；任何公式/算法提到 Cholesky 时要求 `min_eigenvalue > 0`（PD，不只是 PSD）；
- **修复指引（非自动改写）**：检测到非正定时，建模者应改用成对协方差完全观测、或 Higham 最近半正定投影后再抽样，并把修正前后的最小特征值写进 `correlation_spec`；Harness 不代替用户改矩阵。

## 5. 论文中如何正确表达
“由历史观测样本估计得到经验相关系数矩阵后，采用 Higham 算法做最近半正定一致性修正，确保多维正态分布联合抽样的数学合法性。”
