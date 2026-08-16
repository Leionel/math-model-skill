# NIPT Batch A–D 验收矩阵（2026-08-15）

> 源审计说明：`Math_Model_Harness_Current_Audit_and_Targeted_Hardening_2026-08-15.md` 为外部输入，未随仓库分发。T-NIPT 编号、失败模式与裁决点以下表为准（自包含），逐项复核不依赖该文档。

本文把 `Math_Model_Harness_Current_Audit_and_Targeted_Hardening_2026-08-15.md` 中的 T-NIPT-01～14 映射到当前 Harness 的真实检查器和回归测试。这里的“已覆盖”只表示：对应失败模式有现有检查器、可复跑的负例回归，以及正式 QA/Gate 的入口；不表示模型本身自动证明正确，也不表示已经完成 Batch E 能力 benchmark。

## 结论

- Batch A（统计单元与泄漏）：T-NIPT-01、02、06 已覆盖。
- Batch B（目标函数完整性）：T-NIPT-03、04、11 已覆盖。
- Batch C（参数与研究设计）：T-NIPT-05、14 已覆盖；T-NIPT-14 现在同时检查合同中的 primary inference 与论文措辞，不允许 Writer 把主推断降格为敏感性分析。
- Batch D（论文与 artifact 完整性）：T-NIPT-07、08、09、12、13 已覆盖。
- T-NIPT-10（Singleton Grouping）属于审计建议的 P1，不混入 A–D，也不在本矩阵中虚报完成。
- Batch E 尚未完成：还需要在 NIPT、物理/几何、统计决策、不确定优化四类真实输入上记录通过率、误报/漏报和运行开销。

## 逐项矩阵

| ID | 批次 | 失败模式 | 当前裁决点 | 精确回归证据 | 旧检查为什么会漏掉 | 状态 |
|---|---|---|---|---|---|---|
| T-NIPT-01 | A | 同一实体的重复测量被拆到 train/test | `check_oos_artifact.py` 按真实 membership 重算 entity overlap | `tests/test_statistical_unit_and_oos.py::test_oos_checker_recomputes_entity_overlap` | 只看声明的 `PASS`、seed 或文件存在性，未重算实体成员关系 | 已覆盖 |
| T-NIPT-02 | A | 首次决策使用未来测量均值 | `check_data_contract.py` 的 derived-feature lineage、decision time 与 feature policy | `tests/test_statistical_unit_and_oos.py::test_future_feature_is_rejected_at_decision_time` | 原数据列有字段名，但没有可裁决的可用时点和 cutoff 语义 | 已覆盖 |
| T-NIPT-03 | B | 平坦目标区间却声称唯一最优 | `check_math_semantics.py` 的 objective diagnostics | `tests/test_objective_semantics.py::test_unique_claim_with_flat_objective_is_rejected` | 只比较最小值，不检查并列候选与 objective spread | 已覆盖 |
| T-NIPT-04 | B | 合同目标与代码实现目标漂移 | `objective_contract`、implementation binding、derivation integrity | `tests/test_objective_semantics.py::test_declared_and_implemented_objective_must_be_equivalent` | 只有一段自然语言 `objective`，没有 declared/implemented 双向语义绑定 | 已覆盖 |
| T-NIPT-05 | C | 高影响 ASSUMED 参数没有敏感性 | `check_modeling_plan.py --require-critical-sensitivity`；正式 M1 strict math Gate 调用它 | `tests/test_nipt_batches_a_d.py::test_t_nipt_05_assumed_high_parameter_must_bind_sensitivity` | 参数计划原来可以停在自由文本，不要求 parameter ID 与 sensitivity artifact 绑定 | 已覆盖 |
| T-NIPT-06 | A | 重复测量使用普通 row CV | `check_data_contract.py` 的 repeated-measure / group-aware validation | `tests/test_statistical_unit_and_oos.py::test_repeated_measure_ml_cannot_use_row_split_as_primary_validation` | CV 方法没有与观测单元绑定，row split 看起来仍像“有验证” | 已覆盖 |
| T-NIPT-07 | D | 论文出现未注册数值阈值 | `check_consistency.py` 严格模式的 frozen/derived numeric registry | `tests/test_p0_harness.py::test_strict_abstract_gate_rejects_unregistered_number` | 仅做人工读稿或把未注册数字当普通 warning，未进入严格 Gate | 已覆盖 |
| T-NIPT-08 | D | comparison 被写成 ensemble | `check_math_semantics.py` 的 model identity/composition check | `tests/test_objective_semantics.py::test_comparison_is_not_an_ensemble_by_label` | 模型名称可被 Writer 改写，合同没有 canonical composition 语义 | 已覆盖 |
| T-NIPT-09 | D | 同一 Pearson claim 的图表来自 v1/v2 两个源 | `check_consistency.py --require-canonical-source` 的 claim→canonical source 一致性 | `tests/test_nipt_batches_a_d.py::test_t_nipt_09_same_claim_cannot_use_two_current_sources` | 只检查每个图/表自身的源存在且 current，没有比较同一 claim 的跨 artifact 源 | 已覆盖 |
| T-NIPT-10 | P1 | singleton grouping 被当成合理分组 | 尚未进入 Batch A–D；应扩展现有分组/诊断契约，默认 warning，声明 actionable grouping 时 fail | 无（不伪造） | 当前 Harness 还没有统一的 grouping diagnostics 与 min group size 语义 | P1 待办 |
| T-NIPT-11 | B | piecewise domain 在 27/28 之间断裂 | `check_math_semantics.py` 的 partition IDs、coverage 与 overlap | `tests/test_objective_semantics.py::test_piecewise_model_requires_domain_coverage` | 分段公式存在不等于整个声明域被覆盖，旧逻辑不检查覆盖与边界 | 已覆盖 |
| T-NIPT-12 | D | BibTeX 含 TODO/占位作者 | `check_citations.py --require-verified-bibliography` | `tests/test_artifact_and_bibliography_guards.py::test_verified_bibliography_bridge_rejects_placeholder_entry` | 只检查 cite key 或 BibTeX 可解析，未检查已验证文献桥和占位内容 | 已覆盖 |
| T-NIPT-13 | D | raw count 被写成 valid count | `frozen_results.result.metric_semantics` + `check_consistency.py` 的句内 population 检查 | `tests/test_nipt_batches_a_d.py::test_t_nipt_13_raw_count_cannot_be_called_valid_count` | 只有数值、单位和统计定义，没有声明 raw/valid population，数字相同就无法裁决语义 | 已覆盖 |
| T-NIPT-14 | C | 普通 OLS p-value 取代合同指定的 primary mixed inference | `check_consistency.py --require-inference-role-consistency`；strict math Gate 自动加入该 flag | `tests/test_nipt_batches_a_d.py::test_t_nipt_14_writer_cannot_reverse_primary_inference_role` | 数据合同可能知道重复测量，但 Writer 的“主要/敏感性”角色反转不在原有文本一致性检查中 | 已覆盖 |

## Batch E 的入口与完成标准

Batch E 不再新增 schema。完成条件是把上述裁决器放到四类真实输入的端到端能力测试（battle test，即带输入快照与运行回执的真实赛题级测试，非单元测试 fixture）中：

1. NIPT：重跑 T-NIPT-01～14，确认每个故障都被拒绝或按声明降级。
2. 物理/几何题：检查单位、边界、守恒/可行性与图表数据谱系。
3. 统计决策题：检查实体/时间单元、决策时点、推断角色与 OOS。
4. 不确定优化题：检查目标语义、相关性/PSD、敏感性绑定与不确定性验证。

每类至少保留：输入快照、运行命令、QA JSON、失败/通过状态、耗时和人工复核边界。只有这些结果完成后，才能说“能力改善”；本地单元测试通过不能替代 Batch E benchmark。

## 当前回归命令

```powershell
python -m unittest tests.test_statistical_unit_and_oos tests.test_objective_semantics tests.test_artifact_and_bibliography_guards tests.test_p0_harness tests.test_nipt_batches_a_d -v
```

如果完整测试集合因本地 Python 环境缺少 `numpy` 而无法加载 `tests.test_enhancements`，应报告为环境限制，不得把未执行的整套 benchmark 写成通过。
