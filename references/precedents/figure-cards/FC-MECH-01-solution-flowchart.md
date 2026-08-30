# 求解流程机制图

- **figure_pattern_id**: FC-MECH-01
- **semantic_type**: workflow / model flow / methodology overview / algorithm pipeline
- **problem_family**: 全题型
- **evidence_role**: mechanism
- **data_shape**: other
- **chart_family**: flowchart / pipeline diagram
- **source_id**: A092
- **rights_status**: local_study_only
- **layout_grammar**: 当求解过程存在读者难以从文字恢复的分支、反馈或模块依赖时，用流程图表达真实拓扑。框形区分计算与判断，箭头表示数据或控制关系；模块标签应能回到正文中的实现说明，但不要求每个子问题都画图，也不要求图与小节机械一一对应。
- **encoding_map**: 步骤类型→框形状（起止/计算/算法/判断）；数据流向→箭头；与正文对应关系→框内标签文字。
- **required_inputs**: 求解步骤序列、每步的输入输出物名称、分支条件。
- **why_effective**: 在读者进入公式推导之前先给整问骨架，降低迷路率；"框与正文小节对应"的机制同时承诺图不是装饰、每个框有落点。
- **failure_modes**: 流程图与正文实际步骤不一致；框内文字过细变成复述正文；纯线性链没有分支却硬画菱形；一图塞超过十个框。
- **adaptation_boundary**: 纯解析推导、无迭代无分支的问题不需要流程图；篇幅紧张时与建模思路图合并为一张总图。
- **do_not_copy**: 不复制原图的框样式、配色、步骤数量与分支写法。
