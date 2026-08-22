# 流程图与框架图工作流

论文中的总览图、任务流程图和模型框架图不使用 Mermaid 或 Python 绘图脚本作为最终成品。它们采用“结构化图稿 + 可编辑源文件 + 导出物 + 版面复核”的流程。

## 推荐后端

默认使用 draw.io/diagrams.net 作为可编辑源文件，保存 `.drawio` 或 `.xml`；正式交付优先导出 SVG/PDF。draw.io 的源文件包含完整图形结构，SVG/PDF 也可以选择嵌入源数据，便于后续编辑。Figma、PowerPoint 或其他矢量编辑器可以作为人工绘制后端，但必须保留等价的可编辑源文件。

最终论文不直接使用未经约束的 AI 生成位图。AI 可以帮助生成 `diagram_spec.json` 的节点、边、分区和布局建议；AI 位图要成为正式图，必须走 [Figure Contract](figure_contract.md) 的 `illustration` 通道：`kind=illustration` 的概念/机理示意，或 `kind=concept` 附 `illustration` 块的后端对比择优（此时可编辑源仍必须保留）。模型、公式、结果数字和中文标签必须来自已登记的题面、model contract、frozen results 或 evidence registry。

## 两种交付模式

| 模式 | 适用场景 | 最低要求 |
|---|---|---|
| `vector_preferred` | 默认正式论文图 | 可编辑源 + SVG/PDF/EMF；原生文字或转曲文字；最终版面复核 |
| `raster_allowed` | 同时保留矢量和位图，兼容 Word/模板预览 | 可编辑源 + 至少一个矢量输出；位图仅作为兼容输出 |
| `raster_only` | 某些模板只接受位图，或复杂字体在目标环境中无法稳定嵌入 | 仍必须保留可编辑源；`text_policy=raster_text`；PNG 至少 300 DPI，建议 600 DPI；最终尺寸人工检查 |

`raster_only` 是显式例外，不是降低质量门槛的快捷方式。位图的文字无法由普通 PDF 文本检查器可靠恢复，因此必须同时检查原始源文件和最终 PDF 页面。

## W1/W2 运行顺序

1. Writer 根据 `paper_plan` 和 Figure Contract 生成 `diagram_spec.json`，先确定唯一 message、节点/边、模型与结果引用，再分别选择 composition `archetype` 与颜色 `style_profile`。两者不得耦合。
2. 人工确认拓扑：总览图回答“题目—任务—模型—验证—输出”如何串联；关键任务图回答一个任务内部的输入、处理、模型、验证和结果，不把所有内容塞进一张图。
3. 优先用仓库的 [Native draw.io Backend](drawio_backend.md) 从 `diagram_spec.json` 生成初始 `.drawio`，再在 draw.io/Figma/PowerPoint 中人工微调；不要让图像生成模型直接承担公式、中文和数值的排版。
4. 导出 SVG/PDF，或在有明确兼容理由时导出高 DPI PNG；运行 `check_diagram_spec.py --strict`，再运行 `check_figure.py` 和整篇 PDF 视觉检查。
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

该检查器能阻断未知节点、断开的边、空标签、遗漏占位符、缺少来源、没有可编辑源和低 DPI 栅格例外，并提示 card wall、PPT title banner、overview overload 与 weak hierarchy；它不能代替人判断图是否真正帮助读者理解模型。
