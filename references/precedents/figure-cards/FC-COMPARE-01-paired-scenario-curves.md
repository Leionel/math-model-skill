# 双情景对照时序曲线

- **figure_pattern_id**: FC-COMPARE-01
- **semantic_type**: comparison / result comparison / trend
- **problem_family**: 机理 / mechanism
- **evidence_role**: result comparison
- **data_shape**: time_series
- **chart_family**: paired scenario line chart
- **source_id**: 2400996
- **rights_status**: local_study_only
- **layout_grammar**: 同一坐标系内两条曲线共享时间轴与纵轴刻度，两线分别代表"有/无目标机制"（实验组与对照组）；或左右双面板、面板间仅差一个开关条件；对照差不单独计算画图，靠两线分离度直接读出；图例放曲线稀疏区。
- **encoding_map**: 时间→横轴；种群规模/生物量→纵轴；情景（机制开/关）→颜色深浅或线型；若存在第三个对照维度（如扰动时点）→竖直参考线标记。
- **required_inputs**: 同参数同初值下两情景的完整时间序列、情景标签、共同口径声明（初值与参数一致的证据）。
- **why_effective**: 差异在共享坐标系中直接可见，避免两张图各说各话的口径漂移；评审可一眼验证"改动一个机制带来什么变化"这一核心主张。
- **failure_modes**: 两情景初值或参数不一致导致对照失效；曲线截尾使扰动后的恢复段不可见；双轴或不同纵轴范围放大假差异。
- **adaptation_boundary**: 差异极小或只在瞬态出现时不宜用；情景多于三个时应改为分面小图而非线叠加。
- **do_not_copy**: 不复制原图配色、图例文字、曲线数量与轴范围。
