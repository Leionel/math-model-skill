# Figure Reference Card Schema（图形表达机制卡格式）

图形卡从权利清晰的论文图例或科研图例中提炼**可迁移的视觉表达机制**，不保存原图、不复制像素与配色参数。卡片可提交到 Git；来源论文全文留在 `references/precedents/local-sources/`（不入 Git）。原图缩略图只有在权利允许时才入 `figures/` 本地目录，否则卡片只保留来源定位与自行描述。

每张卡一个文件，字段固定：

```markdown
# <图形机制名>

- **figure_pattern_id**: FC-<域>-<序号>（如 FC-COMPARE-01）
- **semantic_type**: 与 Figure Contract / `harness figure --semantic-type` 对齐的一个或多个语义标签，以 `/` 分隔
- **problem_family**: 优化 / 预测 / 评价 / 仿真 / 机理 …
- **evidence_role**: 该图承担的证据职能（result comparison / sensitivity / mechanism / uncertainty / process …）
- **data_shape**: distribution / ordered_categories / time_series / continuous_relationship / grid_search / network / uncertainty_interval / other
- **chart_family**: 具体图型家族（tornado / pareto scatter / line+band / heatmap / phase portrait …）
- **source_id**: 来源论文 ID（指向 precedents index.json）或公开图例来源
- **rights_status**: authorized_public_download | local_study_only | unknown
- **layout_grammar**: 版面机制——面板划分、阅读路径、主次层级（用文字描述，不含具体坐标）
- **encoding_map**: 编码机制——什么数据维度映射到什么视觉通道，颜色语义中心
- **required_inputs**: 复用该机制需要的最小数据输入
- **why_effective**: 为什么该表达对这种论证有效
- **failure_modes**: 常见翻车点（截断轴、双轴滥用、色盲不可辨、密度过载）
- **adaptation_boundary**: 什么数据形态/论证角色下不该用
- **do_not_copy**: 明确不许照搬的内容（配色数值、具体标签文字、图幅尺寸、原图结构）
```

规则：

1. 选择顺序必须是 `claim/evidence → evidence_role/data_shape → reference card`；禁止先挑一张好看的图再寻找数据。
2. 图型最终由 Figure Contract 的 evidence role、data shape 和 comparison 决定；图形卡只提供表达机制参考，不构成图数配额或审美禁令。
3. 图形卡不是 evidence，不能进入 `evidence_registry`；`source_id` 仅供追溯。
4. Writer/Figure Author 默认只接触卡片；全文读取受 competition profile 与 live-contest policy 控制。
