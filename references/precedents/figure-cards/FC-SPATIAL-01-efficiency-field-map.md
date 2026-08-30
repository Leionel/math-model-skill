# 空间指标分布云图

- **figure_pattern_id**: FC-SPATIAL-01
- **semantic_type**: heatmap / map / data distribution
- **problem_family**: 优化 / optimization
- **evidence_role**: mechanism
- **data_shape**: other
- **chart_family**: spatial field / heatmap
- **source_id**: A127
- **rights_status**: local_study_only
- **layout_grammar**: 在场地平面坐标上把每个空间单元（每面镜/每网格点）的指标值渲染为颜色场，叠加场地边界与关键结构物（塔位、测线）标记；色带单独置于图侧并标数值范围；需要局部细节时补一个内圈放大子图；同一论文内多问的分布图共用色带范围以便跨问对比。
- **encoding_map**: 平面坐标→图面位置；指标值（效率/深度/密度）→单端渐变色；结构物与边界→线符号；数值范围→侧边色带。
- **required_inputs**: 各空间单元的指标值、场地边界、结构物位置、统一的色带范围。
- **why_effective**: 空间异质性一眼可见（如由内向外递减的梯度），直接支撑"遮挡/余弦损失主导"类机制解释；统一色带还使不同问的分布图可横向比较。
- **failure_modes**: 色带范围截断夸大梯度；彩虹 colormap 使顺序不可读；采样点过密糊成色块无结构；省略结构物标记使梯度失去参照。
- **adaptation_boundary**: 指标与空间位置无关时禁用；单元数量极少时用标注散点即可，不值得整幅云图。
- **do_not_copy**: 不复制原图的色带取值、标记样式、子图布置与图幅尺寸。
