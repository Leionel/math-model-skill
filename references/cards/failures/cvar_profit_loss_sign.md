# Failure Card: CVaR Profit vs Loss Sign Convention (CVaR收益/损失符号与方向混淆)

## 1. 错误形式
目标是最大化总利润 $\Pi(x, \xi)$，但作者在公式中直接套用最小化损失的 CVaR 线性化公式，写出：
\[
\max \quad \mathbb{E}[\Pi] - \lambda \left( \alpha + \frac{1}{(1-\beta)S} \sum u_s \right), \quad u_s \ge \Pi_s - \alpha
\]
（符号和不等式方向完全写反！）

## 2. 为什么错
- 原始 Rockafellar-Uryasev 线性化是针对**损失（Loss $L \ge 0$）**推导的，关注损失的**右尾极大值**；
- 若优化对象是**收益/利润（Profit $\Pi$）**，决策者害怕的是利润过低的**左尾极小值（Left Tail）**；
- 若直接将 $\Pi_s$ 套入 $u_s \ge \Pi_s - \alpha$，优化器会错误地惩罚“高利润情景”，反而倾向于选择利润极低甚至全零的荒唐解！

## 3. 最小反例
假设两个投资方案：
- 方案 A：在所有情景下利润均为 100 万元；
- 方案 B：情景 1 利润 100 万元，情景 2 利润 500 万元。
套用错误公式时，方案 B 因情景 2 产生巨大的 $u_2 \ge 500 - \alpha$，导致目标函数扣除巨额惩罚，系统竟然判定恒定 100 万的方案 A 优于有概率赚 500 万的方案 B！

## 4. Harness 应如何发现与拦截
- **CVaR 符号契约检查（`check_modeling_plan.py`）**：强制声明 `optimization_direction`（min/max）、`target_nature`（profit/loss）、`tail_direction`（left/right）；
- 执行极值退化测试：检查高利润方案是否被系统错误惩罚。

## 5. 论文中如何正确表达
“为防范极端低利润风险，定义随机损失 $L(x, \xi) = -\Pi(x, \xi)$；通过最小化损失的 CVaR 等价实现最大化尾部保证利润。”
