# Plot Recipes by Evidence Task

图型由 claim 的比较关系决定，不由“论文至少几张图”决定。

| 证据任务 | 优先图型 | 必须声明 |
|---|---|---|
| 时间变化/预测 | 折线 + 区间带 + 训练/测试分界 | 时间范围、窗口、样本外定义、区间口径 |
| 方案比较 | 点图、排序条形图、small multiples、slope chart（两时点对比）、dumbbell（区间端点对比） | baseline 身份、共同尺度、方向、差值/区间 |
| 分布/异常 | ECDF、直方/密度、箱线/小提琴、beeswarm（小样本逐点） | 样本量、异常值处理、统计定义 |
| 变量关系 | 散点 + 合理拟合/残差 | 相关不等于因果、过绘制处理、置信范围 |
| 参数/敏感性 | 响应曲线、热力图、tornado | 改变量、固定条件、参数范围、失效区 |
| Pareto/多目标 | 目标空间散点 + 非支配标记 | 目标方向、场景、容差、机器重算结果 |
| 空间关系 | 地图、分区/网格 | CRS、比例尺、空间分辨率、缺失区域 |
| 网络/路径 | 网络、路径高亮、流图 | 节点/边含义、布局与权重、是否筛边 |
| 分布沿有序变量 | ridgeline/joyplot（多组密度沿轴堆叠） | 组序依据、带宽、重叠度，组数多时慎用 |

正式图必须在 `paper_plan.figures[]` 声明 `message`、`comparison`、`visual_encoding` 与 `selection_rule`。精确查数优先表格；结构或趋势比较优先图；没有证据增益时使用文字。

更多图型谱系可查本地锁定参考（见 `vendor/template_sources.json`，仅本地使用不随 Skill 分发）：`vendor/upstream/python-graph-gallery/`（按数据关系组织的 100+ 图型配方）、`vendor/upstream/scientific-visualization-book/`（配色、布局与感知规则）。底图瓦片如需在线获取（如 Contextily 类后端），必须先核对当届网络策略与 Contest Safety；优先使用本地 shapefile/geojson，离线或 live-contest 受限时禁止临时抓取 tiles，并声明 CRS 与 attribution。

## 受控模板入口

`scripts/figures/plot_templates.py` 从 tidy CSV/JSON 生成 PDF/PNG/SVG，并写输入、输出、style、字段映射和完整参数 hash receipt。PDF 元数据时间戳被移除；需要记录确定性时间时传 `--source-date-epoch`。当前模板：

- `line`：时间序列、预测和区间带；
- `comparison`：排序点图，适合少量方案的共同尺度比较；
- `distribution`：hist/ECDF；
- `scatter`：关系、预测—观测、残差；
- `sensitivity`：正负效应 tornado/bar；
- `pareto`：机器重算后的非支配点；
- `heatmap`：二维参数/场景网格；
- `network`：可选 NetworkX 的网络/路径结构。

示例：

```powershell
C:\ProgramData\anaconda3\python.exe scripts/figures/plot_templates.py `
  --template line `
  --input reports/forecast_tidy.csv `
  --x time --y prediction --low lower --high upper --group model `
  --title "Out-of-sample forecast" `
  --xlabel "Time" --ylabel "Demand (MW)" `
  --output paper/figures/forecast.pdf `
  --receipt reports/figures/forecast.json
```

模板层不自行挑选行；入图筛选必须在 Figure Contract 的 `selection_rule` 中声明。空间地图需要 CRS、底图来源和可选 GeoPandas，尚未塞进基础运行时；没有地理依赖时应输出准备好的几何/网格数据再绘制，而不是静默猜 CRS。

## 上游参考边界

本地 clone 参考 SciencePlots、Scientific Visualization Book 和 Python Graph Gallery；锁定提交/许可证状态见 `vendor/template_sources.json`。运行时绘图模板不直接复制这些仓库代码，也不依赖 SciencePlots；许可证未审清的仓库保持 distribution blocked。
