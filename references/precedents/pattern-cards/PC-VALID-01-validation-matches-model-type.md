# 验证与模型类型匹配（Validation Matches Model Type）

- **card_id**: PC-VALID-01
- **problem_family**: 全题型
- **trigger**: 任何为模型选择验证方式的时刻；尤其当想给所有模型套同一套"sensitivity + robustness"模板时。
- **mechanism**: 验证义务由 claim 类型与模型类型触发：预测用留出集/泄漏检查/朴素基线；优化用可行性重算/约束余量/替代算法或扰动复核；统计因果用识别假设与安慰剂；仿真用 warm-up、重复次数与方差控制。往届高分论文的共性是"验证与机制同构"，不是验证项目多。
- **dependency_shape**: 依赖模型合同声明的 `problem_type` 与 `characteristics`；输出为 `validation_obligations[]` 的类别选择。
- **validation_signature**: 对应 Harness 的 `REQUIRED_VALIDATION_CATEGORIES` 触发表与 `references/validation/profiles/`。
- **rhetorical_moves**: 模型→验证设计理由→结果→"验证覆盖了什么/没覆盖什么"的边界。
- **failure_modes**: 把 Monte Carlo 重复叫 OOS；把求解器成功当最优性；所有题共用一套敏感性模板。
- **do_not_copy**: 不照搬任何一届论文的验证章节结构或固定表格。
- **source_ids**: roadmap-2025-survey（2020—2025 MCM/ICM、2020—2024 CUMCM 研读纪要，见 REVISED_IMPLEMENTATION_ROADMAP_2026-08-12.md §2.6）
