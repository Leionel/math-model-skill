# P0 Gate Policy

## 状态

每个 Gate 使用 `pending | pass | fail | blocked`。`pass` 只表示当前输入快照通过；输入、代码、冻结结果或论文发生实质变化后，状态必须回到 `pending`。

## 前置关系

```text
M1 → P1 → P2 → W1(Paper Strategy) → W2(Release)
```

- M1 需要 `model_contract.status=ready`，且文件哈希与 manifest 一致。
- P1 需要 M1 通过，并且恰有一个成功的 `stage=smoke` command。
- P2 需要 P1 通过，`stage=full` 与 `stage=freeze` 分别成功，并且冻结文件含代码与验证日志快照。
- W1 需要 P2 通过、`paper_plan.status=ready`，且每个必要 claim 只引用已验证 evidence。
- W2 需要已哈希的论文、Deterministic QA 报告和 Semantic Critic 报告；若启用 Blind Reviewer，还需要独立 reviewer ID 与报告哈希。

## 失败处理

- M1 失败：返回 Modeling，不能由 Coder 猜测修复数学合同。
- P1/P2 失败：返回 Coding；禁止先写论文再补结果。
- W1 失败：返回 Evidence/Results 或重新规划 claim；不能用空泛句子绕过缺口。
- W2 失败：只处理 issue 指向的 artifact，最多两轮；问题未减少时输出 decision memo。

每个 `pass` Gate 必须在 `evidence` 中登记本次检查使用的 artifact/report；不能只手工改状态字符串。

## Reviewer 分档

- 默认：确定性 QA + 1 个 Semantic Critic。
- Final Submission：再加 1 个 Blind Reviewer。
- Award-Max：冻结成稿后才启用 3 个隔离盲席；不把竞赛阈值写死在通用 Harness。
