# 实验凭证：失败、敏感性与 OOS

这些 artifact 用来证明实验确实发生过；它们不是把一段论文措辞包装成结果。只有通过语义检查、绑定当前 `run_id`，并在 P2 manifest 中登记的凭证，才能进入主 Gate。

## 1. 敏感性实验

当模型合同中的 `validation_obligations[].category` 为 `sensitivity` 时，必须同时写：

```json
{
  "artifact_role": "sensitivity_experiment",
  "experiment_id": "SENS-Q1-LAMBDA",
  "run_id": "run-001",
  "question_id": "q1",
  "status": "completed",
  "parameter": "lambda",
  "baseline": 0.5,
  "grid": [0.2, 0.5, 0.8, 1.0],
  "rerun_policy": "full_reoptimization",
  "metrics": [
    {"metric_id": "profit", "unit": "CNY", "definition": "objective value"},
    {"metric_id": "solution_similarity", "unit": "probability", "definition": "share of matching decisions", "similarity_definition": "1 - normalized L1 distance"}
  ],
  "results_artifact": {"path": "results/sensitivity_q1.json"},
  "runs": [
    {"grid_value": 0.2, "status": "PASS", "artifact": {"path": "results/sens_020.json"}},
    {"grid_value": 0.5, "status": "PASS", "artifact": {"path": "results/sens_050.json"}},
    {"grid_value": 0.8, "status": "PASS", "artifact": {"path": "results/sens_080.json"}},
    {"grid_value": 1.0, "status": "PASS", "artifact": {"path": "results/sens_100.json"}}
  ],
  "generated_at": "2026-08-13T00:00:00Z"
}
```

检查器会拒绝缺少某个 grid 重跑回执、只有一个 grid 点、没有 similarity 定义或结果文件不存在的实验。`baseline` 不强制必须出现在 grid 中，但正式结论应明确说明基线如何比较。无需为本地每个结果文件机械填写 SHA-256；`submission` 模式的最终包仍按全局完整性策略处理。

```powershell
python scripts/qa/check_sensitivity_experiment.py `
  --experiment results/sensitivity_experiment.json `
  --run-id run-001 `
  --strict
```

论文只能写 artifact 中真实存在的参数、指标和比较。没有 artifact 时只能写“计划做敏感性分析”，不能写“模型稳定”。

## 2. 真正的 OOS

Monte Carlo、同一场景集上的重复模拟或训练集内交叉验证不能自动叫 OOS。`oos_artifact.json` 至少要保存训练/测试场景的来源、seed、场景数和 64 位场景集身份摘要，并由生成程序确认：

```json
{
  "status": "verified",
  "split_rule": "按年份切分；测试年份未参与参数估计",
  "train_scenarios": [{"seed": 101, "hash": "...64 hex...", "count": 240, "source": "results/train_scenarios.json"}],
  "test_scenarios": [{"seed": 202, "hash": "...64 hex...", "count": 120, "source": "results/test_scenarios.json"}],
  "disjoint_check": "PASS",
  "leakage_check": "PASS",
  "metrics_artifact": {"path": "results/oos_metrics.json"}
}
```

检查命令：

```powershell
python scripts/qa/check_oos_artifact.py `
  --artifact results/oos_artifact.json `
  --run-id run-001 `
  --strict
```

若没有独立测试场景，Writer 只能使用“scenario test”“stress test”等准确表述，不得升级为 `out-of-sample validation`。

## 3. 失败证据

FAIL/ERROR run 仍应冻结，便于解释边界和模型迭代；但它不能进入 `evidence_registry`，也不能支撑 PASS 数值结论。编译诊断 artifact：

```powershell
python scripts/validation/compile_failure_evidence.py `
  --frozen-results results/failed_frozen_results.json `
  --model-contract model_contract.json `
  --output results/failure_evidence.json

python scripts/qa/check_failure_evidence.py `
  --artifact results/failure_evidence.json `
  --frozen-results results/failed_frozen_results.json `
  --run-id run-001 `
  --strict
```

该 artifact 的 `status` 固定为 `diagnostic`，每条诊断 claim 固定 `claimable=false`。它可以支持“预注册条件未通过”“峰值超过约束”等失败描述，但不能支持“方案满足全部目标”。

## 4. 主流程接入

在 `model_contract` 中用 `artifact_role` 把义务和凭证类型绑定；在 `run_manifest.artifacts[]` 登记对应角色。P2 会按角色检查 `sensitivity_experiment` / `oos_artifact`；FAIL/ERROR run 则要求 `failure_evidence`。因此新增实验不会停留在孤立 JSON 文件中。
