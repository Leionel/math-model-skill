# 参数网格对照面板

- **figure_pattern_id**: FC-LAYOUT-01
- **semantic_type**: comparison / result comparison / small multiples
- **problem_family**: 机理 / mechanism
- **evidence_role**: result comparison
- **data_shape**: time_series
- **chart_family**: multi-panel comparison grid（小倍数）
- **source_id**: 2424371
- **rights_status**: local_study_only
- **layout_grammar**: 行×列网格复制同一图型，每格只变一个参数或一个条件；面板标签放格内角落；所有面板共享纵轴刻度与横轴范围，使视觉比较在相同尺度上成立；阅读顺序从左到右按参数水平递增排列；网格规模控制在一次扫视可容纳的范围。
- **encoding_map**: 参数水平→面板位置（列/行）；情景（机制开/关）→面板内双曲线；时间与种群→各面板共享的轴；结论差异→面板间分离度的变化。
- **required_inputs**: 参数网格×情景组合下的完整时间序列、统一轴范围、面板标签（参数取值）。
- **why_effective**: 小倍数设计把"一个因素如何改变结论"压缩为一次扫视；统一轴消除了单图各自调轴造成的假差异，网格本身即对照实验的视觉化。
- **failure_modes**: 各面板轴范围不同制造假差异；网格超过约 2×4 后信息过载；面板标签缺失或与参数实际取值不符。
- **adaptation_boundary**: 参数连续扫描更适合曲线族而非离散面板；只有单一情景无对照维度时退化为普通多图，不构成小倍数机制。
- **do_not_copy**: 不复制原图的网格规模、面板标题句式与配色分配。
