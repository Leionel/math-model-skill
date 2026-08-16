# Pattern Card Schema（机制卡格式）

机制卡从合法获得的往届论文/教程中**只提炼可迁移机制**，不保存原文段落、公式结果或固定句式。卡片可提交到 Git；来源论文全文留在 `references/precedents/{cumcm,mcm-icm}/` 本地（不入 Git）。

每张卡一个文件，字段固定：

```markdown
# <机制名>

- **card_id**: PC-<域>-<序号>（如 PC-VALID-03）
- **problem_family**: 优化 / 预测 / 评价 / 仿真 / 机理 …
- **trigger**: 什么题面特征应想起这个机制（一两句，可检验）
- **mechanism**: 机制本身怎么工作（不抄原文，用自己的话）
- **dependency_shape**: 该机制通常依赖哪些上游输出、对下游提供什么
- **validation_signature**: 与该机制匹配的验证义务（对应 validation profile 的条目）
- **rhetorical_moves**: 论文里通常需要哪几类论证动作（如 模型选择→结果→边界）
- **failure_modes**: 常见翻车点（可链接 `references/cards/failures/` 同名机制）
- **do_not_copy**: 明确不许照搬的内容（句式、图数、参数、结构）
- **source_ids**: 来源论文 ID（指向 precedents index.json），或 "roadmap-2025-survey"（来自历年论文研读纪要）
```

规则：

1. 机制卡不是 evidence，不能进 `evidence_registry` 支撑事实主张（见 Outstanding Paper Quarantine）。
2. Writer 默认只加载 mechanism / rhetorical_moves / failure_modes 三类内容。
3. 每张卡必须能追溯到 source_ids；无来源的"经验"不入卡。
