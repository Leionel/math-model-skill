# 流程图与框架图工作流

论文中的总览图、任务流程图和模型框架图不使用 Mermaid 或 Python 绘图脚本作为最终成品。它们采用“结构化图稿 + 可编辑源文件 + 导出物 + 版面复核”的流程。

## 先判图型，再选后端

每张图先在 Figure Brief 中分类为 `data`、`diagram` 或 `illustration`。`data`/结果图只能由真实数据的确定性绘图生成；`illustration` 走 Figure Contract 的插图通道；只有 `diagram` 进入本页的可编辑流程。未声明或不认识的语义类型保持 `unresolved` 并停止，不得以任意 PPTX 或 Draw.io 模板悄悄兜底。

对 `diagram`，选择器依据已声明的语义类型、节点数、DAG 深度、分支数、反馈边、并行 lane、密度、目标长宽比和是否需要 native topology QA，给出 2–3 个已检查的候选构图及其不适配理由。候选是供作者挑选的视觉起点，不是自动替换内容的模板。

路由结果还会按同一个 `semantic_type` 返回 `figure_reference_cards`。卡片来自 `references/precedents/figure-cards/`，只说明可迁移的布局/编码机制；它不提供当前题证据，也不授权复制来源图的像素、配色或文字。选择顺序固定为 `claim/evidence → semantic_type/evidence_role/data_shape → card`。

- 简单流程、方法总览、有限分组的框架图：默认走 PPTX。先从 [`assets/pptx_workflow`](../../assets/pptx_workflow/README.md) 的已检查页面中挑选候选，一次性复制源 deck 到项目图目录，再在 PowerPoint 中修改。
- 复杂 DAG、显式反馈、多重交叉关系，或确实需要原生 XML/拓扑检查：才选择 [Native draw.io Backend](drawio_backend.md)。它是可验证的备选后端，而不是默认。
- 人工调整过的连接线、箭头位置和层级属于作者编辑；后续操作不得按模板自动重排或覆盖它们。

无论后端，正式交付优先 SVG/PDF；PPTX、Draw.io 或其他矢量编辑器均须保留相应的可编辑源文件。

最终论文不直接使用未经约束的 AI 生成位图。AI 可以帮助生成 `diagram_spec.json` 的节点、边、分区和布局建议；AI 位图要成为正式图，必须走 [Figure Contract](figure_contract.md) 的 `illustration` 通道：`kind=illustration` 的概念/机理示意，或 `kind=concept` 附 `illustration` 块的后端对比择优（此时可编辑源仍必须保留）。模型、公式、结果数字和中文标签必须来自已登记的题面、model contract、frozen results 或 evidence registry。

## 两种交付模式

| 模式 | 适用场景 | 最低要求 |
|---|---|---|
| `vector_preferred` | 默认正式论文图 | 可编辑源 + SVG/PDF/EMF；原生文字或转曲文字；最终版面复核 |
| `raster_allowed` | 同时保留矢量和位图，兼容 Word/模板预览 | 可编辑源 + 至少一个矢量输出；位图仅作为兼容输出 |
| `raster_only` | 某些模板只接受位图，或复杂字体在目标环境中无法稳定嵌入 | 仍必须保留可编辑源；`text_policy=raster_text`；PNG 至少 300 DPI，建议 600 DPI；最终尺寸人工检查 |

`raster_only` 是显式例外，不是降低质量门槛的快捷方式。位图的文字无法由普通 PDF 文本检查器可靠恢复，因此必须同时检查原始源文件和最终 PDF 页面。

## W1/W2 运行顺序

1. Writer 根据 `paper_plan` 和 Figure Contract 建立 Figure Brief：先确定唯一 message、节点/边、模型与结果引用，再分类为 `data`、`diagram` 或 `illustration`。`diagram` 才填写可观测的拓扑元数据；不要用视觉偏好冒充论证事实。
2. 选择器返回候选后，人工确认阅读顺序：总览图回答“题目—任务—模型—验证—输出”如何串联；关键任务图只回答一个任务的输入、处理、模型、验证和结果，不把所有内容塞进一张图。
3. 简单构图复制并编辑选中的 PPTX 页面；复杂拓扑则从 `diagram_spec.json` 生成初始 `.drawio`。不要让图像生成模型承担公式、中文和数值的排版，也不要在后续自动化中覆盖人工微调的箭头与层级。
4. 导出 SVG/PDF，或在有明确兼容理由时导出高 DPI PNG；Draw.io 路由额外运行 `check_diagram_spec.py --strict`。两条路线都需要 `check_figure.py` 和整篇 PDF 视觉检查。
5. W2 人工确认箭头方向、节点含义、文字可读性、灰度/色觉可辨识性、图注边界和正文引用；图稿状态才能从 `rendered` 变为 `reviewed`。

## 设计边界

- 总览图通常 5–9 个一级节点；关键任务图只保留能改变读者判断的节点。
- 优先从 `research_framework`、`computational_pipeline`、`parallel_integration`、`method_architecture`、`iterative_optimization` 选择一种主阅读语法；只有确有特殊拓扑才用 `custom`。参考样例是 visual regression，不是固定 XML 换字模板。
- 论文模式使用 `title_mode=none` 或 `compact`；`banner` 只用于确有需要的海报、PPT 或 standalone infographic，并接受 `PPT_TITLE_BANNER_RISK` 提示。
- 一个 panel 只承担一个主要问题；不要把概念流程、实验结果和敏感性结论混成没有层级的彩色拼贴。
- 节点文字优先使用短语，公式保留真实 LaTeX/数学文本；禁止用 `...`、`etc.` 隐去关键步骤。
- 使用 2–3 个语义色和白底，颜色用于区分任务/模型/结果，不用颜色代替箭头和文字。
- 结果数字只能来自冻结结果或派生结果；概念框架图不得伪装成数据证据图。
- 正文必须引用图，并在 caption 中说明图能支持的结论边界；图数仍由 claim/evidence coverage 决定。

## 结构化图稿

`schemas/diagram_spec.schema.json` 规定节点、边、source_refs、布局、风格和交付模式。检查命令：

```powershell
python scripts/figures/check_diagram_spec.py `
  --project-root . `
  --spec paper/figures/FIG-01/diagram_spec.json `
  --strict `
  --require-reviewed
```

生成 native draw.io 源文件：

```powershell
python scripts/figures/generate_drawio.py `
  --project-root . `
  --spec paper/figures/FIG-01/diagram_spec.json `
  --output paper/figures/FIG-01/FIG-01.drawio `
  --force
```

该检查器能阻断未知节点、断开的边、空标签、遗漏占位符、缺少来源、没有可编辑源和低 DPI 栅格例外。对 native Draw.io 源，它还要求每个 spec node 唯一反查到 `harness-node`，并检查节点碰撞、画布越界、低于 spec 的字号以及 `left_to_right` / `top_to_bottom` 主边方向；报告保留稳定错误码。它仍不能代替人判断视觉层级、文字是否拥挤、颜色语义或图是否真正帮助读者理解模型。
