# Figure Contract

## 概念流程图/框架图的制作合同

当 `kind=concept` 且 `semantic_type` 为 `methodology_overview`、`data_flow` 或 `model_structure` 时，正式图还应声明 `diagram`：

- `spec_path`：结构化 `diagram_spec.json`，其中每个节点和边都有 `source_refs`；
- `source_format/source_path`：draw.io、SVG、Figma 或 PPTX 的可编辑源；
- `delivery_mode`：默认 `vector_preferred`，可选 `raster_allowed` 或显式例外 `raster_only`；
- `text_policy`：`native_text`、`outlined_text` 或 `raster_text`；位图文字只能配合 `raster_only`；
- `rendered_paths`：实际放入论文或用于构建的 SVG/PDF/PNG；
- `status`：`brief` → `draft` → `rendered` → `reviewed`；只有 `reviewed` 才能作为正式 W2 图稿。

默认不使用 Mermaid 或 Python 绘图脚本作为最终概念图。`raster_only` 必须保留可编辑源，PNG 至少 300 DPI，建议 600 DPI，并经过最终论文尺寸视觉复核。

## AI 生成示意图与框架图择优（illustration 通道）

AI 位图不再是绝对禁区，但只能走受约束的 `illustration` 通道，用于**不直接由数据决定、且对论证重要**的图（机理/场景/原理示意、以及与 draw.io 对比择优的框架图）。硬性条件：

1. **两种用法**：
   - `kind=illustration`：纯概念/机理/场景示意图。不得进入 `methodology_overview`/`data_flow`/`model_structure` 三类结构图职责（那三类仍属 `kind=concept`）。
   - `kind=concept` + `illustration` 块：AI 位图作为框架/流程图的**正式成品**，仅当与可编辑后端（draw.io 等）做过对比择优并保留可编辑源。
2. **`illustration` 块必填**：`generator`（工具/模型）、`prompt_path`（提示词落盘，供审计）、`raster_dpi>=300`、`text_policy=raster_text`、`review_status=reviewed`（人工/多模态视觉复核）。`kind=concept` 时还必须 `backend_comparison`（≥2 个后端且含可编辑源、非空 `selection_reason`，建议附对比记录文件）。
3. **不承载数值结论**：AI 图内不得出现结果数字、公式推导或结论性标注；caption 必须含"示意"类声明（如"概念示意，非按坐标精确绘制，不承载量化结论"）。
4. **AI 使用登记**：生成过程必须记入 `run_manifest.ai_usage[]`（影响交付物）。
5. `check_consistency.py` 在正式 QA 中强制上述全部条件；缺对比记录、DPI<300、未复核或 caption 无声明都会阻断。

画图前先回答“这张图证明什么”，再选图型。它与 `paper_plan.figures[]` 一一对应，不以图数为输入。

W1 对每个 argument unit 生成非阻断的视觉机会扫描：已有 display 时核对其论证作用；定量比较在表格与确定性数据图之间选择；机制、场景或流程只有在纯文字解释成本过高时才考虑可编辑概念图或 `illustration`。扫描必须留下结论，但不因此创建图数配额。

数据图可选登记 `data_shape`、`argument_intent`、`sample_regime` 和 `uncertainty_semantics`，把图型选择约束在“主张 + 数据形态 + 论证意图 + 样本制度”上。复杂图可先登记 `candidate_displays[]`，选定后填写 `selected_display` 和 `selection_reason`；这些字段不是图数配额，也不要求所有图都提供候选列表。`color_profile` 可取 `contest_default`、`colorblind_safe`、`muted` 或 `high_contrast`；发散色图需要语义中心。

## 必填问题

- `figure_id`：在 `paper_plan.figures[]` 中的唯一标识。
- `claim_ids`：对应哪个论文主张？
- `evidence_ids`：使用哪些冻结结果、原始数据或推导？
- `kind`：这是 `data` 结果图还是 `concept` 机理/流程图？
- `audience`：新合同必须标为 `scientific_argument`、`submission_disclosure` 或 `internal_audit`。只有 `scientific_argument` 可进入论文正文；其余两类只能进入各自交付面。
- `purpose`：阅卷者在 5–10 秒内应该看懂什么？
- `why_figure`：如果删除这张图，哪条论证会变弱？
- `message/comparison/visual_encoding/selection_rule`：一句话结论、比较对象、视觉通道和入图筛选规则；防止为了好看挑选样本。
- `data_artifacts`：数据图登记数据/生成脚本，概念图登记可编辑源文件；不得为空。
- `panel_map`：每个 panel 的唯一问题和主次证据是什么？
- `statistical_definition`：数据图写中心、区间、样本/种子/折数和 baseline；概念图显式写 `not_applicable: concept figure`。
- `paper_location/caption_claim`：正文在哪里解释，caption 要说什么结论？
- `accessibility`：灰度/色觉是否可辨，是否使用双轴；双轴必须写明不可替代的理由。
- `qa_status`：`pending`、`passed` 或 `failed`；正式图完成后由 Figure QA 更新。
- `final_size_qa`：可选的最终论文尺寸记录，含目标宽高、预期缩放、最小有效字号、DPI、线宽、marker、可读性、裁切和复核状态；启用严格 Figure Semantics profile 时必须为 `reviewed`。

## 选择原则

- 一个 panel 只承担一个主要问题；可合并的重复图合并。
- 结果图必须由真实冻结结果或明确登记的数据生成；概念图不得冒充实验数据。
- 图的数量由 requirement→claim→evidence 的缺口决定。
- 正式图完成后运行确定性导出检查，并在论文预计尺寸下人工阅读；自动化检查不能代替语义和可读性判断。
- 语义失败卡至少检查：小样本分布过度外推、无序类别连线、均值柱图隐藏分布、无中心发散色图、相关图解释成机制、图没有 primary argument，以及离散网格极值被写成连续最优。只有证据确实被误导时才应 hard fail；其他情况保留为 warning/人工 issue。
