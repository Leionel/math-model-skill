# Figure Contract

## 概念流程图/框架图的制作合同

当 `kind=concept` 且 `semantic_type` 为 `methodology_overview`、`data_flow` 或 `model_structure` 时，正式图还应声明 `diagram`：

- `spec_path`：结构化 `diagram_spec.json`，其中每个节点和边都有 `source_refs`；
- `source_format/source_path`：draw.io、SVG、Figma 或 PPTX 的可编辑源；
- `delivery_mode`：默认 `vector_preferred`，可选 `raster_allowed` 或显式例外 `raster_only`；
- `text_policy`：`native_text`、`outlined_text` 或 `raster_text`；位图文字只能配合 `raster_only`；
- `rendered_paths`：实际放入论文或用于构建的 SVG/PDF/PNG；
- `status`：`brief` → `draft` → `rendered` → `reviewed`；只有 `reviewed` 才能作为正式 W2 图稿。

默认不使用 Mermaid 或 Python 绘图脚本作为最终概念图。AI 可以辅助生成节点、边和布局草案，但不能凭空生成公式、中文标签、结果数值或模型步骤。`raster_only` 必须保留可编辑源，PNG 至少 300 DPI，建议 600 DPI，并经过最终论文尺寸视觉复核。

画图前先回答“这张图证明什么”，再选图型。它与 `paper_plan.figures[]` 一一对应，不以图数为输入。

## 必填问题

- `figure_id`：在 `paper_plan.figures[]` 中的唯一标识。
- `claim_ids`：对应哪个论文主张？
- `evidence_ids`：使用哪些冻结结果、原始数据或推导？
- `kind`：这是 `data` 结果图还是 `concept` 机理/流程图？
- `purpose`：阅卷者在 5–10 秒内应该看懂什么？
- `why_figure`：如果删除这张图，哪条论证会变弱？
- `message/comparison/visual_encoding/selection_rule`：一句话结论、比较对象、视觉通道和入图筛选规则；防止为了好看挑选样本。
- `data_artifacts`：数据图登记数据/生成脚本，概念图登记可编辑源文件；不得为空。
- `panel_map`：每个 panel 的唯一问题和主次证据是什么？
- `statistical_definition`：数据图写中心、区间、样本/种子/折数和 baseline；概念图显式写 `not_applicable: concept figure`。
- `paper_location/caption_claim`：正文在哪里解释，caption 要说什么结论？
- `accessibility`：灰度/色觉是否可辨，是否使用双轴；双轴必须写明不可替代的理由。
- `qa_status`：`pending`、`passed` 或 `failed`；正式图完成后由 Figure QA 更新。

## 选择原则

- 一个 panel 只承担一个主要问题；可合并的重复图合并。
- 结果图必须由真实冻结结果或明确登记的数据生成；概念图不得冒充实验数据。
- 图的数量由 requirement→claim→evidence 的缺口决定。
- 正式图完成后运行确定性导出检查，并在论文预计尺寸下人工阅读；自动化检查不能代替语义和可读性判断。
