# Consistency Sweep

在 Writer 完成草稿后按以下顺序检查；不要只做语言润色。先用 `compile_writer_package.py` 固定可用 claims、证据、数字和边界；Writer 不得直接从 raw results 或聊天记录增加事实。

1. 数字：摘要关键结果必须列入 `abstract_results[]` 并写选择理由；摘要与结论中的其他数字应能在 frozen results 中解释。
2. 单位与精度：使用 `display_value` 和登记单位；不要在摘要、正文、结论或图表间擅自换算、重舍入。
3. 证据边界：检查“最优、显著、稳健、提升”等词是否超出 evidence 的 `boundary` 和统计定义。
4. 符号与术语：使用 `paper_plan.terminology[].canonical`；清除 forbidden variants。
5. 图表：逐项核对 figure/table ID、caption claim、数据 artifact、正文解释和 paper location。
6. 交叉引用：LaTeX 交付时检查 cite key、label/ref 和图片文件；Word 交付时进行实际渲染与人工交叉引用检查。
7. 复验：任何正文或 artifact 变化后重跑确定性 QA；最终 Release 使用 `--strict`。

结果段按 `Observation → Comparator → Interpretation → Boundary` 组织：只有 package 内有 inference claim 和支持证据时才能写 Interpretation；否则在 Comparator 后直接给 Boundary。不要用“说明/表明”把一个 observation 自动升级为解释或因果。

程序化检查只能发现可编码的不一致。对“该证据是否足以支持该主张”和“边界是否被扩大”的判断交给 Semantic Critic。
