# Failure Card: No-Seed Single-Run Conclusion (无种子单次随机运行下结论)

## 1. 错误形式
含有随机成分的模型（Monte Carlo、GA/SA/PSO、随机划分、Bootstrap、随机仿真）只跑了一次、且未固定随机种子，就把输出当成确定结论写进摘要与冻结结果；复跑一次数值就变。

## 2. 为什么错
- 单次随机运行的输出是分布的一个抽样，不是期望值：Monte Carlo 均值自带 $1/\sqrt{N}$ 级随机误差，GA/SA 的搜索结果对 seed 敏感；
- 不固定 seed → 结果不可复现，论文的每个数字都无法被任何人（包括作者自己三天后）重现；
- 把单次运行的好运气写成"算法性能"，评审复跑即穿帮。

## 3. 最小反例
某随机优化跑 3 个 seed 得到目标值 {100, 137, 121}。论文只报了碰巧最好的 100，称"本算法目标值为 100"。他人复现均值得约 119——"100" 不是算法的属性，是那一次运行的属性。

## 4. Harness 应如何发现与拦截
- `freeze_results.py`：冻结绑定 `--seed` 与可重算命令；随机模型的关键结果作为 metric 落盘时必须同时给出多 seed 的均值与离散度（`statistical_definition` 注明 seed 数）；
- `references/validation/profiles/simulation.md`：`stability` 义务——随机模型 ≥3 seed 重复，报告区间；GA/SA 稳定性见对应方法卡第 7 节；
- `check_modeling_plan.py`：`characteristics` 声明随机/仿真特征时触发相应义务绑定；
- 复现层（Wave 2 方向）：`run_and_record.py` 的 command receipt 记录 argv 与 seed，run_index 防止"只报最好 seed"。

## 5. 论文中如何正确表达
"随机成分统一固定 seed=42 供复现；性能结论基于 5 个独立 seed 的重复实验：目标值 119.3±8.6（均值±标准差，N=5），最优单次 100 对应 seed=7（完整运行记录见附录 run index）。所有报告数字为多 seed 统计量而非单次运行值。"
