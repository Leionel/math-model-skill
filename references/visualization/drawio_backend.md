# Native draw.io 后端

本后端借鉴 draw.io 官方 XML/style reference，并按升级文档第 16 节吸收 `ai-jiaqian/drawio-figure-replicator` 的 research framework / model pipeline / central container / meaningful loop 构图机制，以及 `QIANJINYDX/research-drawio-skill` 的单一阅读顺序、学术层级、紧凑标签、语义分组、正交连线和 paper-scale QA。它不把上游项目当作论文事实来源，不复制外部 XML，不保留软件平台语义，也不形成运行时依赖或第二套 palette。

## 后端边界

```text
paper_plan + diagram_spec
        ↓
archetype resolver
        ↓
composition grammar + primitive planner
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

生成器只做确定性的版式工作：archetype-specific geometry、primitive 尺寸、面板边界、正交连接、语义色、字体、文字换行和 source_refs 标签。它不增加或删除节点/边，不替 Writer 选择模型、不补充结果数字，也不判断模型语义是否正确。

## 构图 archetype

`archetype` 与 `style_profile` 完全解耦：前者只负责结构和 geometry，后者只负责既有角色配色。旧 spec 没有 `archetype` 时按 `kind` 做兼容映射，并以 `research_framework` 为保守 fallback。

| archetype | 结构语法 | 典型场景 |
|---|---|---|
| `research_framework` | input band → core model chain → validation rail → output | 论文 Figure 1 总框架 |
| `computational_pipeline` | 连续执行层级，核心模型放大，辅助节点同层堆叠 | 数据处理、预测、优化流水线 |
| `parallel_integration` | 多输入/模型 lane → topology-derived merge hub → output | 多源数据或多模型融合 |
| `method_architecture` | 中心 hero core，前驱/约束/目标输入，输出与验证分层 | 算法或优化模型内部结构 |
| `iterative_optimization` | 主链 + spec 明确声明的 feedback edge | ALNS、迭代求解、校准循环 |
| `custom` | 非统一尺寸的 DAG layout | 已有明确特殊拓扑 |

节点可选 `primitive` 只作显式覆盖；默认 `auto` 会从 role、emphasis、archetype 和 DAG 入度/出度推断。构图 fixtures 和回归样例见 [`assets/drawio/archetypes`](../../assets/drawio/archetypes/README.md)。它们是 example/layout reference/QA benchmark，不是“复制 `.drawio` 后换字”。

## 已固定的 academic 默认值

- paper-first 白底宽画布，不沿用 16:9 concept board；复杂拓扑允许扩宽，但必须在最终栏宽/页宽导出后人工检查，不能仅凭 native XML 宣称可读；论文图默认不用大标题 banner；`title_mode=compact` 只保留小型 caption strip，`none` 完全省略图内标题；
- hero block、band、validation rail、output、annotation 使用不同尺寸；长标签只做一次有界扩容，不能无限长成文字卡片；
- module 内、module 间和 tier 间使用不同 gutter；核心节点使用较粗边框和加粗文字；
- input/task/model/validation/decision/result 使用低饱和语义色，白底，禁用阴影和玻璃渐变；
- 边默认使用 `orthogonalEdgeStyle`，feedback/comparison 使用虚线，不用大面积弧线和交叉装饰；
- 中文默认 `Microsoft YaHei`，可在 spec 中指定 `font_family`；英文模板可以切换为 Arial；
- 每个 XML 都保留 `id=0` 根容器和 `id=1` 默认层，节点和边使用稳定顺序 ID；
- 节点/边保留 `harness-node`、`harness-edge`、`relation:*` 和 `source-refs` tags，便于回溯但不把内部 ID 展示给读者；未知边端点会 fail-fast，不能静默丢边。

Composition QA 额外给出 warning（不替代人工判断）：`CARD_WALL_RISK`、`PPT_TITLE_BANNER_RISK`、`OVERVIEW_OVERLOADED`、`WEAK_HIERARCHY`。`check_diagram_spec.py` 的 warning 不能自动升级为 Gate PASS；最终仍要在论文实际缩放尺寸检查阅读顺序、层级、箭头和文字密度。

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
python scripts/figures/generate_drawio.py --list-style-profiles --list-archetypes

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

示例 spec 的关键字段：

```json
{
  "kind": "overview",
  "archetype": "research_framework",
  "title_mode": "none",
  "style_profile": "academic_minimal"
}
```

生成器会依次查找 `DRAWIO_CLI`、PATH 中的 `drawio` / `diagrams.net`、常规 Windows 安装目录，以及本机常见的 `D:\Program Files\draw.io\draw.io.exe`。非标准位置可显式指定：

```powershell
$env:DRAWIO_CLI = 'D:\Program Files\draw.io\draw.io.exe'
```

找到 draw.io Desktop 后，可继续导出：

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

仍无法发现 Desktop CLI 时，生成器会交付 `.drawio`；可在 `app.diagrams.net` 打开后手动导出。导出 PNG 时，必须把 `raster_only`、`raster_text` 和 `raster_dpi` 写入 spec，并用 `check_figure.py` 检查最终尺寸的有效 DPI。

## 不做的事

- 不用 Mermaid 转成概念图；
- 不用 matplotlib/Python 绘制最终图形；Python 这里只生成 native draw.io XML；
- 不从自然语言自动捏造节点、箭头、公式或结果；没有 `source_refs` 的节点会被检查器阻断；
- AI 图像模型的位图不经 [Figure Contract](../contracts/figure_contract.md) 的 `illustration` 通道（对比择优 + ≥300 DPI + 人工复核 + caption 声明）不得作为正式图；draw.io 可编辑源在此通道中仍须保留。
