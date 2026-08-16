# 结果靠比较产生意义（Comparator Required）

- **card_id**: PC-CLAIM-02
- **problem_family**: 全题型
- **trigger**: 任何"方案 X 更好/降低了/提升了"类结论出现之前。
- **mechanism**: 核心结果必须声明 comparator（基线方案、替代算法、现实参照或朴素规则）、共同口径、差值/区间与代价；没有 comparator 时只能写 observation。往届优秀论文几乎都把优化结果与问题一的方案、贪心解或现实做法直接对比，使数字"有参照系"。
- **dependency_shape**: 依赖合同中的 baseline 声明与 `validation_obligations` 的 baseline 类别；输出支撑 `paper_plan.claims[].comparison`。
- **validation_signature**: baseline 类义务；`check_consistency` 对比较性强词要求 comparison 合同。
- **rhetorical_moves**: Observation → Comparator → (有机制证据时) Interpretation → Boundary。
- **failure_modes**: 只报优化后指标不报基线；基线口径与优化口径不一致；把不同场景的结果当同一比较。
- **do_not_copy**: 不复制具体对比表格样式或固定差值表述。
- **source_ids**: roadmap-2025-survey（§2.6"结果通过比较形成意义"）
