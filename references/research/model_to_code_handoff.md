# Model-to-Code Handoff: 合同到编码任务

> 边界：本文说明 solve 阶段如何从模型合同获得逐模型编码任务、失败时如何回退。它不重复 `model_contract.md` 的字段规则，也不替代 `03_SOLUTION_REPORT.md` 的作者面。

## 何时加载

进入 solve 阶段（M1 通过后、写代码前）：

```powershell
python scripts/harness.py solve --tasks
# -> .harness/views/IMPLEMENTATION_TASKS.md + implementation_tasks.json
```

视图是可再生投影：每个模型一个任务，含公式/约束/验证义务 ID、typed 输入输出、算法、脚手架入口、实现步骤、测试 oracle、smoke 验收与失败回退。

## 如何消费

1. **按任务切片编码**：一个 `IMPL-<model_id>` 任务对应一个可独立验证的实现单元；不要把多模型的公式混进一个脚本再拆。
2. **测试先看 oracle**：任务里的 `test_obligations` 是该模型的验收比较结构（left metric / operator / right / unit）；单元测试直接以它为断言来源。
3. **smoke 覆盖声明**：research/submission preset 下，至少一条成功 smoke 命令通过 `--covers-model`、`--covers-question`、`--covers-contract-item` 把覆盖声明写入该次不可变 receipt 的 `metadata.smoke_coverage`；checker 会对照合同校验。较早的探索 receipt 可保留，但不能替代一条覆盖完整的 receipt。不要把覆盖写进可变 `run_manifest.control`，它不是执行证据。
4. **implementation_map 时序**：`harness solve --compile` 从 `03_SOLUTION_REPORT.md` 编译实现映射；verified 状态在 P2 检查（M1 只验证可编码计划）。

## 失败回退（escalation）

代码运行失败时先区分两类：

- **实现问题**（bug、环境、边界写错）→ 修代码，重跑 receipt；
- **合同问题**（公式、约束、参数来源、数据边界与题意不符）→ 携最小复现（命令 + 堆栈 + 预期 vs 实际）回到 M1 修订 `model_contract.json`。新合同使下游 implementation_map、运行与冻结全部失效，需要新 run。

**禁止**：在代码里静默改数学定义来"让它跑起来"。Coder 无权修改任务视图中的公式与约束语义。

## 边界

- 任务视图不是新真源：修改数学必须回作者面（`02_MODEL_DECISION.md` → `harness model --compile`），不是改视图。
- 视图不含数值结果（那是 P2 之后的事）；它只投影计划。
