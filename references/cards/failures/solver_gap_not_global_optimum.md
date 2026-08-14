# Failure Card: Solver Gap Setting is Not Proof of Global Optimality (求解器Gap设置误作已证明全局最优)

## 1. 错误形式
作者在代码中设置 `solver.mipgap = 0.05` 或求解时间耗尽触发 `TimeLimit` 中断退出，在论文摘要和正文中直接声称：“模型已严格证明获得全局最优解”。

## 2. 为什么错
- **提前终止 $\neq$ 证明最优**：当求解器因时间限制或达到 5% 相对容差（MIP Gap）退出时，当前解只是“可行解（Feasible Solution）”或“已证明界内的较优解”，可能与真实理论全局最优解存在达 5% 的客观差距；
- **非凸非线性求解器陷入局部极值**：对于非凸 NLP，常规求解器（如 IPOPT / SLSQP）只保证满足一阶 KKT 条件（局部极值点），并不提供全局最优性证书（Global Optimality Certificate）。

## 3. 最小反例
- 双峰函数 $f(x) = x^4 - 2x^2 + 0.1x$，存在两个局部极小值点 $x \approx -1$ 与 $x \approx 1$；
- 梯度算法从 $x_0 = 2$ 出发收敛到 $x \approx 1$（局部最优，值为 $-0.9$），但真实全局最优在 $x \approx -1$（值为 $-1.1$）；
- 声称找到“全局最优解”直接构成学术事实造假。

## 4. Harness 应如何发现与拦截
- **Optimization Proof Obligation 强制检查**：扫描论文中出现的“全局最优、严格证明最优、绝对最优”等词汇；
- 必须检验求解器回执（Solver Receipt）：`solver_status == "OPTIMAL"` 且 `actual_gap <= 1e-4`；否则禁止使用全局最优表述。

## 5. 论文中如何正确表达
“在设定 180 秒时限内，MILP 求解器获得目标值为 XXX 的高质量可行解，相对最优界差距（Optimality Gap）控制在 0.8% 以内，满足实际工程决策精度要求。”
