# Figure Contract

画图前先回答“这张图证明什么”，再选图型。它与 `paper_plan.figures[]` 一一对应，不以图数为输入。

## 必填问题

- `claim_ids`：对应哪个论文主张？
- `evidence_ids`：使用哪些冻结结果、原始数据或推导？
- `kind`：这是 `data` 结果图还是 `concept` 机理/流程图？
- `purpose`：阅卷者在 5–10 秒内应该看懂什么？
- `why_figure`：如果删除这张图，哪条论证会变弱？
- `data_artifacts`：数据图登记数据/生成脚本，概念图登记可编辑源文件；不得为空。
- `panel_map`：每个 panel 的唯一问题和主次证据是什么？
- `statistical_definition`：数据图写中心、区间、样本/种子/折数和 baseline；概念图显式写 `not_applicable: concept figure`。
- `paper_location/caption_claim`：正文在哪里解释，caption 要说什么结论？

## 选择原则

- 一个 panel 只承担一个主要问题；可合并的重复图合并。
- 结果图必须由真实冻结结果或明确登记的数据生成；概念图不得冒充实验数据。
- 图的数量由 requirement→claim→evidence 的缺口决定。
- 正式图完成后运行确定性导出检查，并在论文预计尺寸下人工阅读；自动化检查不能代替语义和可读性判断。
