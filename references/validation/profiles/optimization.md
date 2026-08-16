# Validation Profile：优化类（LP/MILP/NLP/启发式）

触发：`problem_type` 为 optimization 或目标含 min/max 决策变量。

## 最低义务

1. **可行性**：独立重算全部约束违反（`category=feasibility`）；不允许用求解器 status 代替。
2. **目标重算**：把求解器返回的决策变量代入目标独立重算并一致（`objective_recomputation`）。
3. **基线**：至少一个 comparator（贪心/朴素/现实方案），同口径比较（`baseline`）。
4. **最优性措辞**：只有存在 gap/bound/精确小实例 oracle 证据时才能写"全局最优"；启发式结果写"当前搜索下的最好可行方案"（`optimality_bound`）。

## 按特征追加

- `metaheuristic`：多种子稳定性（≥3 seeds 的分布，非单次收敛曲线）；收敛轨迹只作辅助证据。
- `nonconvex`：替代算法复核或扰动检查；多起点防局部解；可声明 `extremum_certificate`（网格+连续精化，拒绝自报 global）。
- `milp`：gap 记录、松弛界对比；Big-M 合理性（见 failures/unrealistic_big_m）。
- `multiobjective`：机器重算非支配排序后才能称 Pareto（`check_pareto.py`）。
- 资源单调性：更多资源（弹数/机数/预算）下的解应不差于其子集问题——跨问对比时必须验证（防止"3 枚弹劣于 1 枚弹"类矛盾冻结）。

## 常见失败

`solver_gap_not_global_optimum`、`unrealistic_big_m`、`dominated_pareto_mislabel`、平坦目标区误称唯一最优（T-NIPT-03/04/11）。
