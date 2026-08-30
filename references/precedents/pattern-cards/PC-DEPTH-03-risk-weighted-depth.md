# 篇幅向关键困难倾斜（Risk-Weighted Depth）

- **card_id**: PC-DEPTH-03
- **problem_family**: 全题型
- **trigger**: 开始分配各子问题篇幅、或发现四问章节几乎等长时。
- **mechanism**: 推导难、决策影响大或验证风险高的部分获得更多公式、图与讨论；简单问保持紧凑。往届高分论文普遍非线性分配篇幅，避免"每问一章同长度"的流水账结构。
- **dependency_shape**: 依赖 Paper Director Plan 的问题依赖和每个 argument unit 的 `depth_priority`（`core` / `supporting` / `compact`）理由；先指导论证展开，再在真实 PDF 完成后用 length audit 输出压缩、扩充或移附录的 triage。
- **validation_signature**: 无直接义务；`check_paper_readiness` 的 readiness 覆盖检查防止简单问被砍掉必要环节。
- **rhetorical_moves**: 每问仍保持 模型→结果→验证→边界 闭环，只是深度不同。
- **failure_modes**: 简单问写满凑数挤占关键问；关键问只给结果不给推导。
- **do_not_copy**: 不照搬某届论文的章节比例。
- **source_ids**: roadmap-2025-survey（§2.6"篇幅向关键困难倾斜"）
