# 预测曲线与分量分解

- **figure_pattern_id**: FC-PRED-01
- **semantic_type**: forecast / uncertainty / trend
- **problem_family**: 预测 / prediction
- **evidence_role**: uncertainty
- **data_shape**: uncertainty_interval
- **chart_family**: line + band
- **source_id**: C235
- **rights_status**: local_study_only
- **layout_grammar**: 历史窗口与预测窗口在同一时间轴上相接：历史段画观测点或实线，预测段画预测中线加置信带；可分解模型另配分量小面板（趋势/周期/外生项）置于主图下方并排，分量面板与主图共享时间轴；预测起点用竖线标记以划分两段。
- **encoding_map**: 时间→横轴；销量/价格→纵轴；历史 vs 预测→线型（点/实线）；不确定性→带面积宽度；模型分量→独立小面板。
- **required_inputs**: 历史观测序列、预测序列、区间宽度（由残差或模型给出）、各分量序列（若做分解面板）。
- **why_effective**: 观测与预测同轴才可比，区间宽度直接传达可信度；分量小图支撑"模型捕捉了哪些规律"的可解释性主张，把黑箱预测变成可审计的分解。
- **failure_modes**: 只画预测不画历史段；无区间仍声称可信；分量面板与主图时间轴不对齐；预测段长度远超模型支持范围却不声明。
- **adaptation_boundary**: 无重复结构、无区间输出的黑箱预测不适用分量面板；非时序的优化结果不适用本图型。
- **do_not_copy**: 不照搬原图的分面数量、带宽样式、颜色与面板标题句式。
