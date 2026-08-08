# Validation Obligations

不要用“报告文件存在”代表验证完成。M1 必须按题型声明 `validation_obligations`，P2 冻结时逐项提交 `status=pass` 和可读的 `observed` 证据。

## 题型最低义务

| 题型 | 通常必须覆盖 |
|---|---|
| 优化 | 可行性/约束违反、目标重算、基线；声称全局最优时还需最优性界或 gap |
| 预测/分类/时间序列 | 先划分再拟合预处理、样本外评估、朴素基线、泄漏检查 |
| 评价/排序 | 权重或参数扰动、排序稳定性、尺度与归一化检查 |
| 仿真 | warm-up、重复次数、置信区间、收敛或方差控制 |
| 微分方程/数值计算 | 初边值条件、步长/网格敏感性、数值误差；适用时检查守恒 |
| 统计推断 | 假设检查、效应量/不确定性、多重比较或抽样边界 |

该表是触发器，不是固定清单。只声明会改变结论可信度的义务，避免几十个空检查。

## 报告合同

```json
{
  "ok": true,
  "obligations": [
    {
      "obligation_id": "VAL-FEASIBILITY",
      "status": "pass",
      "observed": "最大约束违反为 0；目标值由独立函数重算一致"
    }
  ]
}
```

冻结脚本会拒绝：`ok!=true`、没有 obligations、未覆盖 M1 声明的义务、出现未声明义务、非 pass 状态或缺少 observed。

机器学习/时间序列任务中，所有会从数据学习参数的预处理都只能在训练数据上 `fit`，再应用到验证/测试数据。参考 scikit-learn 官方的 [Common pitfalls](https://scikit-learn.org/stable/common_pitfalls.html)。
