# Threat Model：Math Modeling Evidence Harness

verified_against: 64842a6@2026-09-18

> 定位：本文件是仓库**唯一的威胁模型与措辞边界来源**。README、SKILL、评测报告、PR 描述与简历行在使用 reliable / verified / tamper-resistant 一类词时，必须落在 §6 的允许范围内。
> 机器校验：§4 的每一次判定都由 CI 中的 red-team 步骤重放；§7 给出与本文件绑定的 `docs/DOC_CLAIMS.json` 声明。

## 0. 目的

回答两个问题：

1. 谁会以什么方式试图让一个**未经证据支撑的状态**被接受？
2. 系统当前能挡住什么、挡不住什么？

不回答：数学/模型正确性（Gate 只能建立契约内可建立的部分）、获奖概率、宿主自愿作恶时的代码完整性。

## 1. 信任边界

- **信任**：本仓库的代码与 schema；操作系统与 Python 运行时；人类 checkpoint 的真实性由组织流程保证（技术层面不绑定身份，见 §5.2）。
- **不信任**：Agent 的输出与自述。Agent 可写的 manifest/receipt/DAG 字段一律视为**声明**，Gate 判定由证据重算（`scripts/v2_gate_runtime.py`、`scripts/qa/check_gates.py`）。
- **边界外**：对 Harness 代码本身拥有写权限的人（见 T4）。

## 2. 资产（Assets）

| 资产 | 载体 | 谁可能改动 |
| --- | --- | --- |
| 控制真相 | `run_manifest.json`（v2）、`competition_profile.json` | Agent、人类 |
| 执行证据 | `receipts/`（真相）、`run_index.json`（投影） | 执行器写入；Agent 可改文件 |
| 谱系与新鲜度 | `artifact_dag.json` + artifact 文件本体 | Agent |
| 结论 | `frozen_results.json`、evidence registry | Agent |
| 审阅 | review 证据、`human_checkpoints` | Agent、人类 |
| 使用声明 | AI ledger | Agent |

## 3. 威胁主体

| 编号 | 主体 | 典型行为 |
| --- | --- | --- |
| T1 | 失误的 Agent | 顺序错误、漏证据、把未执行的事情写成已执行 |
| T2 | 粗心 / 幻觉的 Agent | 编造数字、把无证据 claim 写进论文、自称独立 review |
| T3 | 对抗性 Agent | 直接改 gate 字段、伪造 receipt、篡改 DAG、删除不利证据 |
| T4 | 恶意宿主 / 仓库所有者 | 改写 Harness 自身；事后静默重写历史 receipt 与 checkpoint |

## 4. 现状表（机器证据）

结果取自 `evaluation/redteam.py` 的场景判定；`blocked` = 攻击被拒绝，`inert` = 攻击面不存在（该字段从不被读取），`allowed` = 已知缺口（§5）。

| 威胁 | 攻击尝试 | 机器证据 | 结果 | 残余风险 |
| --- | --- | --- | --- | --- |
| T1/T2 | 把 manifest 的 gate 字段直接写成 pass | `examples/end_to_end/run_demo.py::probe_gate_field_is_inert` | blocked | 无：**a forged gate field cannot flip a verdict**，判定由证据重算 |
| T1/T2 | 冻结结果但没有真实执行 receipt | `examples/end_to_end/run_demo.py::probe_freeze_needs_execution` | blocked | 无 |
| T1/T2 | 上游改动后下游仍当作 current | `examples/end_to_end/run_demo.py::probe_downstream_goes_stale` | blocked | 无 |
| T2 | reviewer 自称 independent | `examples/end_to_end/run_demo.py::probe_reviewer_cannot_self_promote` | blocked | 无 |
| T2 | 图/claim 没有绑定证据 | `examples/end_to_end/run_demo.py::probe_unsupported_claim_is_blocked` | blocked | 无 |
| T3 | 把 `run_index` 投影里每行的 `exit_code` 改成 0 | `evaluation/redteam.py::scenario_projection_copy_is_inert` | inert | 无：**a forged run_index projection is inert**，P1 从 `receipts/` 重算 |
| T3 | 删除被审阅的 paper 后重新 validate | `evaluation/redteam.py::scenario_bound_artifact_deleted` | blocked | 无 |
| T3 | 篡改 DAG lineage | `evaluation/redteam.py::scenario_dag_lineage_tampering` | blocked | 无 |
| T3 | AI ledger 写入一条没有交互的记录 | `evaluation/redteam.py::scenario_ai_ledger_entry_without_interaction` | blocked | 无 |
| T3 | 字节一致地改写 receipt 的 `argv`（所有摘要仍合法） | `evaluation/redteam.py::scenario_receipt_provenance_is_not_attested` | **allowed** | 见 §5.1 |
| T3 | 删掉 W1 checkpoint，再以任意角色名重新加入 | `evaluation/redteam.py::scenario_human_checkpoint_is_unattested` | **allowed** | 见 §5.2 |
| 正向 | 正常链路的可追溯性 | `examples/end_to_end/run_demo.py::positive_checks` | verified | — |

## 5. 已知缺口（不得声称已覆盖）

### 5.1 receipt provenance is not externally attested

字节一致地改写 receipt（摘要、路径绑定全部仍然合法）会被接受。receipt 证明的是"字节相同"，不是"哪个进程跑的"。
证据：`evaluation/redteam.py::scenario_receipt_provenance_is_not_attested`（`expect="allowed"`，即**有意**记录的已知缺口）。
关闭路径：P2-C 的 `previous_receipt_hash` + `execution_host_identity` + 可选签名——只提高**事后静默改史**的可检测性，不防恶意宿主。

### 5.2 human checkpoint identity is not attested

丢掉 W1 checkpoint 会让 W1 失败（缺证据 → fail closed），但再以任意角色名重新加入即可通过；`decided_by` 是自由文本。
证据：`evaluation/redteam.py::scenario_human_checkpoint_is_unattested`（`expect="allowed"`）。
关闭路径：P2-C 的 `harness checkpoint approve` producer（append-only 决策 artifact + identity + previous 指针）。

### 5.3 宿主自愿作恶

改写 `scripts/`、`schemas/` 或 CI 定义之后，"重算"得到的也是被改过的真相。这是信任边界之外：任何本地校验都无法自证。

## 6. 措辞边界（README / SKILL / 报告 / PR / 简历）

**允许**：

- "fail-closed gate recomputation"（Gate 判定由证据重算，不由声明决定）
- "digest-bound artifact lineage and freshness"
- "unsupported claims and stale downstream artifacts are blocked / detected"
- "read-only status projections"（`harness status`、dashboard）

**必须限定或禁止**：

- ✗ "tamper-proof" / "tamper-resistant receipts"：仅当同一句说明 §5.1 的字节一致伪造会被接受时才允许。
- ✗ "verified human approval" / "human-verified"：身份未绑定；只能说 "a recorded human checkpoint decision exists"。
- ✗ 任何 "proves the model/agent ran"：receipt 证明字节，不证明进程。
- ✗ 用"回归测试通过"或"demo 跑通"代替能力基准；A/B/C 数字只在 `evaluation/PREREGISTRATION.md` 修订并真实执行后出现。
- ✗ 把本文件的存在表述为"安全问题已解决"。

以上同时受 `AGENTS.md` 完整性规则约束：不得制造 Gate PASS、receipt、hash、review 独立性或冻结结果。

## 7. 本文件的机器校验

`docs/DOC_CLAIMS.json` 中与本文档绑定的声明，由 `python scripts/qa/check_doc_claims.py --repo-root .` 校验（`tests/test_doc_claims.py` 在 CI 中执行）：

| claim | 本文档断言 | 机器检查 |
| --- | --- | --- |
| DOC-CLAIM-013 | receipt provenance 未被外部 attest | `evaluation/redteam.py` 含 `def scenario_receipt_provenance_is_not_attested` |
| DOC-CLAIM-014 | human checkpoint 身份未绑定 | `evaluation/redteam.py` 含 `def scenario_human_checkpoint_is_unattested` |
| DOC-CLAIM-015 | run_index 投影伪造无效 | `evaluation/redteam.py` 含 `def scenario_projection_copy_is_inert` |
| DOC-CLAIM-016 | gate 字段伪造不能改变判定 | `examples/end_to_end/run_demo.py` 含 `def probe_gate_field_is_inert` |
| DOC-CLAIM-017 | §4 判定每次 CI 重放 | `.github/workflows/ci.yml` 含 `evaluation/redteam.py` |

## 8. 不在范围内

- 模型/求解的数学正确性（Gate 只建立契约内的部分）。
- P2-A 引入外部执行后端后的容器/主机隔离强度。
- 多用户权限模型（P2-B 落地后回填 §3 的 T3 一行）。

## 变更记录

- 2026-09-18 初版：T1–T4、§4 现状表、§5 两个已知缺口、§6 措辞边界。P2-B / P2-C 落地后必须同步更新 §5 与 §8。