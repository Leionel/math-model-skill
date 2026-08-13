# Semantic Critic Rubric

Semantic Critic 是证据-aware 的二元审查者，不负责奖项打分，也不重复做文件存在性或哈希检查。

## 检查面

1. 题目每个子问题是否有明确 conclusion type。
2. model_contract 的假设、变量、单位、目标和约束是否兑现到代码和结果。
3. 每个关键 claim 是否有足够的 evidence，且 evidence 的边界没有被扩大。
4. 比较/提升/最优等表述是否明确 baseline、指标和统计口径。
5. Figure Contract 是否真正支撑 claim，是否存在装饰性或重复图。
6. 摘要、正文、结论和推荐方案是否引用同一批冻结结果。
7. 结论是否承认敏感性、稳健性、数据范围和其他限制。
8. central thesis 是否只综合少量 decisive claim，而不是按题号堆数字；argument units 是否区分 model choice、结果观察、比较、验证、解释与边界。
9. Observation 是否被误写为因果解释；Inference/Recommendation 是否有支持、替代解释和前置 claim；强评价词是否与 comparison contract 一致。

## 回执格式

```json
{
  "phase": "W2",
  "loop": 0,
  "verdict": "fail",
  "issues": [
    {
      "id": "W2-1",
      "severity": "high",
      "summary": "摘要中的成本没有对应 evidence_id",
      "artifact": "paper_plan.json",
      "required_fix": "登记 R-Q1-01 并重跑一致性检查",
      "owner": "paper-writer"
    }
  ],
  "evidence_checked": ["C-Q1-01", "E-R-Q1-01"]
}
```

将报告单独落盘并记录 SHA-256；只有 `verdict=pass` 且没有 blocker/high issue 时，才把 manifest 中的 `semantic_critic.status` 设为 `pass`。

严重度：`blocker` 影响正确性/规则/复现安全；`high` 很可能改变结论可信度；`medium` 应在本轮修复或明确接受；`low` 只影响润色。
