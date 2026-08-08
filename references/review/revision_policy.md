# Bounded Targeted Revision

- 默认最多两轮；每轮只处理 blocker/high 和会改变结论的 medium。
- issue 必须有稳定 ID、证据位置、owner、required fix。
- 修订后只重跑受影响的脚本和 Gate，但最终 Release 必须重新聚合状态。
- 若 blocker+high 数量没有严格减少，或冻结结果/输入哈希被意外改变，停止自动循环并输出 decision memo。
- Reviewer 不直接改作者 artifact；作者修改后由 Deterministic QA 和 Critic 复验。
