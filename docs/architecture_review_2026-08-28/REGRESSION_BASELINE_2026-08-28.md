# R6 状态/代码债：绿色基线与收口记录（2026-08-28）

verified_against: 2026-08-29@working-tree

> 本文记录 2026-08-28 的历史对拍数字；最新工作树测试结果见 `HANDOFF_2026-08-28.md`，不要把 564 项基线解释为 R1 真实赛题能力基准。

本文是第三阶段 R6 的如实记录：先跑绿、再收口、再拆分。所有数字来自真实运行，未经修饰。

## 1. 回归基线（双跑对拍）

| 时点 | 命令 | 结果 | 用时 |
|---|---|---|---|
| `_v2_gate` 拆分前 | `python -m unittest discover -s tests -q` | Ran 564 tests — **OK** | 524.2s |
| `_v2_gate` 拆分后 | 同上 | Ran 564 tests — **OK** | 526.6s |

拆分前后同为 564 项全绿，作为"拆分未改变行为"的对拍证据。

对照历史：`docs/STATE_SIMPLIFICATION_AUDIT.md`（2026-08-17）记录的基线是 286 运行 / 2 errors（numpy 导入失败 + Windows UTF-8 解码）。当前套件已增长到 564 项，且本次运行未复现这两个环境错误——但那次错误的根因（环境缺 numpy、控制台编码）并未被代码修复，只是本次环境恰好具备依赖、且相关测试路径未触发；在干净环境（无 numpy）仍可能复现导入类错误，这点如实保留为环境风险而非已修复项。

## 2. 已确认的收口事实（代码证据）

以下不是"计划"，是当前代码里已经成立的约束：

1. **v2 manifest 禁止重复状态。** `scripts/profiles/normalization.py:311-336`：v2 `run_manifest` 含 `commands/artifacts/gates/reviewer/内嵌 competition_profile` 等字段直接抛 `NormalizationError`；必须用 `competition_profile_ref.{path,profile_id}` 指向独立 canonical profile；`roots.*` 只许引用不许携带 digest（digest ownership 归 artifact_dag）。
2. **Gate 不再信任自报状态。** v2 各 Gate 由 `scripts/v2_gate_runtime.py` 从事实重推：receipt、roots/DAG、checkpoint、capabilities；manifest 里没有任何可手填的 `gates.*.status`。
3. **执行事实归 receipt。** `run_and_record.py` 产出 immutable receipt；run_index 是 receipts+selection policy 的投影；P2 要求 selected full receipt 与 frozen run 一致。
4. **能力解析单一入口。** `resolve_profile(profile, overrides)` 产出 ResolvedCapabilities，preset 只有 sprint/research/submission 三档；Gate 只消费 capability flags。

## 3. 已完成的拆分

`scripts/v2_gate_runtime.py` 中的单体 `_v2_gate`（约 600 行、六段门内逻辑全在一个函数里）拆为：

- 六个门函数 `_v2_gate_m1/p1/p2/w1/w2/s1`，正文逐行搬迁、只改缩进与两个闭包提升；
- 两个闭包提升为模块级 `_v2_checkpoint_required` / `_v2_run_safety_checker`；
- `_V2_GATE_BRANCHES` 分发表 + 薄壳 `_v2_gate`。

度量（ast 统计）：文件 960 行，最大函数 `_v2_gate_w2` 151 行，其余均 ≤122 行。无行为变化（见第 1 节双跑）。

## 4. 如实保留的遗留项

1. **`scripts/qa/check_gates.py` 的 `main()` 仍有 1155 行。** 它是 v1+v2 双体制：v2 请求在入口处分发给 `v2_gate_runtime`，剩余是 v1 遗留路径。继续拆分的正确顺序是"迁移完成→双跑对拍→切流→删 v1"，而不是在 v1 还有真实用户时把尸体切块。本次只做了安全的部分（v2 runtime），v1 拆分留待迁移决策。
2. **v1 deprecation warning 未加。** 曾计划对 v1 manifest 输出弃用警告，但 v1 严格模式判定是 `ok = not errors and (not strict or not warnings)`——无条件 warning 会让所有 strict v1 Gate 直接失败。这需要先定弃用语义（哪一档降级为 warning、何时转 error），属于策略决定而非代码工作。
3. **环境类回归风险未根除**（见第 1 节末段）。

## 5. 第三阶段（R5+R6）变更面

新增：`scripts/qa/check_units.py`、`scripts/qa/plan_selective_rerun.py`、`scripts/run_sensitivity_sweep.py` 及三个测试文件（`test_unit_checks.py`、`test_selective_rerun.py`、`test_sensitivity_sweep.py`）。
修改：`schemas/model_contract.schema.json`（unit_balance/output_unit）、`scripts/qa/run_deterministic_qa.py`、`scripts/qa/check_gates.py`（v1 M1/P2 接线）、`scripts/v2_gate_runtime.py`（units 接线 + 拆分）、`scripts/harness.py`（`solve --rerun-plan`）、`tests/test_p0_harness.py`。

全部变更文件 `ruff check` 通过；`python -m unittest discover -s tests -q` 564/564 OK。
