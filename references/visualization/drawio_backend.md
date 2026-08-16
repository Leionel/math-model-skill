# Native draw.io 后端

本后端借鉴 draw.io 官方 XML/style reference 和 `github/awesome-copilot` 的 draw.io generator skill，但不把上游 skill 当作论文事实来源，也不直接复制其模板。它只负责把已经通过 Figure Contract 的 `diagram_spec.json` 编译成可编辑的 native `.drawio` 文件。

## 后端边界

```text
paper_plan + diagram_spec
        ↓
generate_drawio.py
        ↓
native mxGraph XML (.drawio)
        ↓
check_diagram_spec.py
        ↓
draw.io Desktop CLI / app.diagrams.net
        ↓
SVG / PDF / PNG preview
```

生成器只做确定性的版式工作：节点分层、面板边界、正交连接、语义色、字体、文字换行和 source_refs 标签。它不替 Writer 选择模型、不补充结果数字，也不判断模型语义是否正确。

## 已固定的 decent 默认值

- A4 横向比例附近的宽画布，标题、唯一 message 和主体图分层；
- `left_to_right` 默认用 DAG 层级布局，`top_to_bottom`、`grid` 可显式选择；
- 节点间保留 76 px 横向间距、66 px 纵向间距；核心节点使用较粗边框和加粗文字；
- input/task/model/validation/decision/result 使用低饱和语义色，白底，禁用阴影和玻璃渐变；
- 边默认使用 `orthogonalEdgeStyle`，feedback/comparison 使用虚线，不用大面积弧线和交叉装饰；
- 中文默认 `Microsoft YaHei`，可在 spec 中指定 `font_family`；英文模板可以切换为 Arial；
- 每个 XML 都保留 `id=0` 根容器和 `id=1` 默认层，节点和边使用稳定顺序 ID；
- 节点/边保留 `harness-node`、`harness-edge` 和 `source-refs` tags，便于回溯但不把内部 ID展示给读者。

## 默认配色预设

在 `diagram_spec.json` 中设置 `style_profile`。支持下划线名称及等价的连字符别名（例如 `academic_minimal` 与 `academic-minimal`）；未知名称会直接报错，避免悄悄换色。同一篇论文建议只使用一套。

| 预设 | 视觉定位 | 适合 |
|---|---|---|
| `academic_minimal` | Navy + Teal，白底、低饱和 | 默认；数模论文总览图和任务流程图 |
| `academic_navy_teal` | 更沉稳的深蓝 + 青绿 | 复杂模型框架、英文 MCM/ICM 图 |
| `okabe_ito` | 蓝/橙/绿，色觉友好 | 需要灰度/色觉可辨识的正式图 |
| `forest_gold` | 森林绿 + 金色 | 资源、环境、农业、能源类题目 |
| `slate_violet` | 石板蓝 + 紫色 | 统计、评价、机器学习模型结构 |
| `navy_coral` | 深蓝 + 珊瑚橙 | 需要突出核心机制或对照任务 |
| `minimal_gray_blue` | 灰阶 + 单一蓝色强调 | 版面严格、黑白打印风险高的模板 |

这些预设都遵循“白底为主、最多三种语义色、颜色不替代文字/箭头”的规则。`okabe_ito` 是默认的可访问性参考，但不把任何单一配色当成自动通过；最终仍需灰度和色觉人工检查。

## 运行

```powershell
python scripts/figures/generate_drawio.py --list-style-profiles

python scripts/figures/generate_drawio.py `
  --project-root . `
  --spec paper/figures/FIG-01/diagram_spec.json `
  --output paper/figures/FIG-01/FIG-01.drawio `
  --force

python scripts/figures/check_diagram_spec.py `
  --project-root . `
  --spec paper/figures/FIG-01/diagram_spec.json `
  --strict
```

如果安装了 draw.io Desktop，可继续导出：

```powershell
python scripts/figures/generate_drawio.py `
  --project-root . `
  --spec paper/figures/FIG-01/diagram_spec.json `
  --output paper/figures/FIG-01/FIG-01.drawio `
  --export-format svg `
  --export-output paper/figures/FIG-01/FIG-01.drawio.svg `
  --force
```

需要正式论文常用的 PDF 矢量输出时，把 `--export-format svg` 换为 `--export-format pdf`（生成器同样支持 `png`）。

没有 Desktop CLI 时，生成器仍然交付 `.drawio`；在 `app.diagrams.net` 打开后手动导出。导出 PNG 时，必须把 `raster_only`、`raster_text` 和 `raster_dpi` 写入 spec，并用 `check_figure.py` 检查最终尺寸的有效 DPI。

## 不做的事

- 不用 Mermaid 转成概念图；
- 不用 matplotlib/Python 绘制最终图形；Python 这里只生成 native draw.io XML；
- 不从自然语言自动捏造节点、箭头、公式或结果；没有 `source_refs` 的节点会被检查器阻断；
- AI 图像模型的位图不经 [Figure Contract](../contracts/figure_contract.md) 的 `illustration` 通道（对比择优 + ≥300 DPI + 人工复核 + caption 声明）不得作为正式图；draw.io 可编辑源在此通道中仍须保留。
