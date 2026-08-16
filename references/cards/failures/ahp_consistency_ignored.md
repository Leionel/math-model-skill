# Failure Card: AHP Consistency Ignored (一致性不达标仍使用 AHP)

## 1. 错误形式
构造判断矩阵后不算（或算完不报）一致性比率 CR，直接取最大特征向量当权重；或 CR = 0.35 明显超标仍继续使用；或 n=2（两指标）也算 CR——两阶矩阵天然完全一致，报告它是凑格式。

## 2. 为什么错
- CR > 0.10 说明两两比较自相矛盾（A>B, B>C 却 C>A），导出的权重是矛盾判断的代数平均，没有决策含义（Saaty 阈值 CR ≤ 0.10，见 [SpiceLogic AHP CR](https://spicelogic.com/docs/ahpsoftware/intro/ahp-consistency-ratio-transitivity-rule-388)、[Esri 文档](https://doc.esri.com/en/arcgis-pro/latest/tool-reference/analysis/calculate-the-consistency-ratio.html)）；
- 小矩阵应更严：3×3 建议 CR ≤ 0.05、4×4 ≤ 0.08；
- 一致性不达标的标准处置是**修订判断**（回到专家/题面依据），不是换软件重算。

## 3. 最小反例
三指标判断矩阵 $A \succ B, B \succ C$ 但 $C \succ A$（循环）。任何权重都无法同时满足三组比较；特征向量法会强行给出一组数字，读者可以构造另一组合法判断得到完全不同的排序——权重不可复现。

## 4. Harness 应如何发现与拦截
- 模型合同：AHP 权重参数标 `CALIBRATED`，`calibration_data` 中必须含判断矩阵与 $\lambda_{max}$、CI、CR、所用 RI 表（Saaty：n=3→0.58, 4→0.90, 5→1.12, 6→1.24）；
- `check_modeling_plan.py`：`--require-critical-sensitivity` 把高影响主观权重绑到敏感性实验（权重扰动下排序稳定性）；
- `references/validation/profiles/evaluation_ranking.md`：主观权重的最低义务（CR 检查 + 权重扰动 + 排序稳定）；
- 人工边界（W2）：论文中"CR=0.xx 通过一致性检验"必须能回到合同登记的数值。参考 `methods/ahp_analytic_hierarchy`、`problems/comprehensive_evaluation`。

## 5. 论文中如何正确表达
"判断矩阵 $\lambda_{max}=5.21$，CI=0.053，查 Saaty RI(n=5)=1.12 得 CR=0.047 ≤ 0.10，通过一致性检验。权重在 ±10% 扰动下（逐格重跑，见敏感性回执）Top3 排序保持稳定；权重来源为专家组两两比较（登记于附件 X）。"
