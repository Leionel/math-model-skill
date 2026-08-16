# Validation Obligations

不要用“报告文件存在”或手写 `ok=true` 代表验证完成。M1 必须按题型声明可计算的 `validation_obligations`；P2 由独立求值器从测量快照重算 verdict，冻结时不得人工填写通过结论。

## 题型最低义务

| 题型 | 通常必须覆盖 |
|---|---|
| 优化 | 可行性/约束违反、目标重算、基线；声称全局最优时还需最优性界或 gap |
| 预测/分类/时间序列 | 先划分再拟合预处理、样本外评估、朴素基线、泄漏检查 |
| 评价/排序 | 权重或参数扰动、排序稳定性、尺度与归一化检查 |
| 仿真 | warm-up、重复次数、置信区间、收敛或方差控制 |
| 微分方程/数值计算 | 初边值条件、步长/网格敏感性、数值误差；适用时检查守恒 |
| 统计推断 | 假设检查、效应量/不确定性、多重比较或抽样边界 |

该表是触发器，不是固定清单。只声明会改变结论可信度的义务，避免几十个空检查。各模型族的展开规则（按特征追加的义务、常见失败与对应失败卡）见 [profiles/](profiles/)：[optimization](profiles/optimization.md)、[prediction](profiles/prediction.md)、[evaluation_ranking](profiles/evaluation_ranking.md)、[simulation](profiles/simulation.md)。跨问共享资源的问题（如多弹/多机调度）还应验证资源单调性：更多资源下的解不得劣于其子集问题。

## 有限比较合同

每项义务的 `acceptance` 只能使用有限、无表达式执行的比较：左侧测量指标、比较符、右侧字面量或同一测量快照中的指标、单位及可选 tolerance。禁止把自然语言、Python/LaTex 表达式或模型输出的自评文字作为验收条件。

```json
{
  "obligation_id": "VAL-PEAK-LOAD",
  "category": "baseline",
  "method": "在相同场景下比较峰值负荷",
  "acceptance": {
    "left_metric_id": "proposed_peak_mw",
    "operator": "<=",
    "right": {"kind": "metric", "metric_id": "baseline_peak_mw"},
    "unit": "MW"
  },
  "required_stage": "full"
}
```

与之配套的测量快照只记录可定位的数值，不记录 verdict：

```json
{
  "schema_version": "1.0",
  "run_id": "run-001",
  "observations": [
    {
      "obligation_id": "VAL-PEAK-LOAD",
      "metrics": [
        {"metric_id": "proposed_peak_mw", "value": 550, "unit": "MW", "locator": "q3.proposed_peak"},
        {"metric_id": "baseline_peak_mw", "value": 498, "unit": "MW", "locator": "q3.baseline_peak"}
      ]
    }
  ]
}
```

运行独立求值器生成报告：

```powershell
python scripts/validation/evaluate_obligations.py `
  --project-root . `
  --model-contract model_contract.json `
  --measurements reports/validation_measurements.json `
  --output reports/full_validation.json
```

报告含 contract/measurement 的 SHA-256、`operator`、`observed`、`threshold`、`unit`、`locator` 和派生 `PASS`/`FAIL`/`ERROR`。以示例数值会产生 `550 MW <= 498 MW` 的 `FAIL`，而不是被改写为“总体有效”。

## 冻结与可引用性

`freeze_results.py` 会重新读取 measurement snapshot 并重算报告；手改报告中的 `ok`、`verdict` 或 obligation status 会被拒绝。它保留完整的 `PASS`、`FAIL`、`ERROR` run：

- 全部义务 `PASS`：`validation_verdict=PASS`、`claimable=true`，才可通过 P2 并进入 `evidence_registry.json`；
- 任一 `FAIL`：`validation_verdict=FAIL`、`claimable=false`，可审计、不可支撑论文数值 claim；
- 任一 `ERROR`：`validation_verdict=ERROR`、`claimable=false`，可审计、不可支撑论文数值 claim。

原始结果的 `validation_status` 同样由总 verdict 约束为 `passed`、`failed` 或 `error`；不能用一条“已通过”的 raw result 覆盖失败验证。

机器学习/时间序列任务中，所有会从数据学习参数的预处理都只能在训练数据上 `fit`，再应用到验证/测试数据。参考 scikit-learn 官方的 [Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)。
