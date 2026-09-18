# 交接 Prompt（2026-09-18）：给接续 agent 的执行指令

> 本文件是一份**可直接执行**的交接说明。接手者请从分支 `refactor/human-visible-workflow` 的最新提交开始；下面的每个「任务块」都可以单独派给一个 agent 执行，按顺序或并行皆可（任务之间无代码依赖，除特别注明外）。

## 0. 环境与验收命令

```bash
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
python -m unittest discover -s tests -q      # 全量 ~11 分钟；必须全绿
ruff check <每个改动的 .py 文件>
python scripts/harness.py agents check        # 契约/MCP 面交叉校验，必须 ok
```

CI（`.github/workflows/ci.yml`，Ubuntu + Python 3.11）跑的就是这些 + schema 解析 + red-team + SKILL.md 体检。**提交前至少跑一次全量**。

## 1. 不可违反的规则（违反即返工）

1. **一个功能一个 commit**，主题用短祈使句；功能完成即提交，最后统一 push。
2. **每个行为变化配一个聚焦回归测试**；测 CLI 退出码与产物，而非只测 helper 返回值。
3. **不得制造 Gate PASS、receipt、hash、review 独立性或任何预填数字**。评测/复现数字只能来自真实 run；没有就跑成 `NOT_RUN` 并如实写。
4. **不得削弱或跳过测试**。环境相关断言必须真的检查环境（例如"有 latexmk 才跑编译"），不许改成无条件 skip。
5. 改契约要**同步**改 schema + checker + 测试 + `references/` 文档（AGENTS.md 规定）。
6. 已有约定：CLI 里 handler 抛异常 → 退出码 **2** + `{"ok": false, "status": "error"}`；判定失败（verify/validate/compare 不通过）→ 退出码 **1**。
7. 新增 `schemas/*.schema.json` 时必须同步更新 `tests/test_wp1_contracts.py` 的 schema 计数守卫（当前 36）。

## 2. 本会话踩过的坑（省时间用）

- **`PYTHONWARNINGS` 带点号的类别在 Python 3.13+ 会被静默忽略**（"invalid module name"）。要升级警告必须在进程内 `warnings.simplefilter("error", <category>)`。
- **Windows 短路径名（`ADMINI~1`）与长路径不一致**：比较/改写路径前先 `.resolve()`；否则包含判断会失败、根路径改写会漏（见 `scripts/runtime/backend.py` 对两种拼写的处理）。
- **`scripts/` 下不要新建名为 `capabilities` 的包**：`scripts/profiles/profile_engine.py` 会裸导入同名的兄弟模块，新包会把它遮蔽（现有包因此命名 `capability_composition`）。
- **registry/loader 的默认路径必须跟随 `repo_root`**，否则测试无法用临时树校验（P1-B/P1-C 已按此实现，新 loader 照做）。
- **demo 的 receipt 性质**：`freeze` 产物内嵌 run root（跨根不可字节复现，复现功能会如实报 mismatch）；`smoke` receipt 不绑定产物摘要（复现只到退出码级）。写与复现相关的测试前先看 `tests/test_execution_capsule.py` 的既有断言。
- 命令行闸门名：CLI 只接受大写（`M1`）；`runtime.check_gate` 接受任意大小写。

## 3. 任务块

### 任务 A（优先级最高）：P2-C —— Receipt 哈希链 + Human Checkpoint Producer

**目标**：把 `docs/THREAT_MODEL.md` §5.1/§5.2 两个已知缺口变成"可检测"，而不是依旧无防护。

**要求**
1. receipt 增加 `previous_receipt_hash`（上一条 receipt 的 sha256，按 run_index 顺序）与 `execution_host_identity`（hostname + platform）；`schemas/command_receipt.schema.json` 增加这两个**可选**字段（保持向后兼容，现有 receipt 不失效）。
2. 写入点在 receipt 的生产者（`scripts/run_and_record.py` 一侧，先 grep 出真正写 receipt 的位置），并用回归测试锁定：连续两条 receipt 的 `previous_receipt_hash` 串联正确；删改历史 receipt 后链校验能报错。
3. 新增 `harness checkpoint approve <STAGE> --role <ROLE> --decision approve|reject`：写 append-only 决策 artifact（`checkpoint/decision/identity/timestamp/previous`）**并**追加 `run_manifest.human_checkpoints` 记录（manifest 仍是控制真相，artifact 只是证据）。禁止在 dashboard 侧实现审批。
4. 在 `docs/THREAT_MODEL.md` 更新 §5/§8：把"关闭路径"改写成"已实现 X，仍未覆盖 Y（宿主自愿作恶）"。
5. 测试：链式校验、approve 产生决策记录、身份写入、append-only（重复 approve 追加而非覆盖）、`harness checkpoint approve` 的退出码。

**不要**：不要声称可防恶意宿主；不要把 `decided_by` 说成"已验证身份"。

### 任务 B：P0-C C0/C1 —— Recovery Benchmark 设计与 slim fixture

**目标**：为 `harness status` 报出 blocker 之后"能否修回来"建立可度量基线（路线 §5）。

**要求**
1. 先写 `docs/RECOVERY_BENCHMARK_DESIGN_2026-09-21.md`：F01–F10 故障清单、注入→检测→修复→复检环、指标定义（含 `unnecessary_rerun_ratio`）、PASS/FAIL 判定。
2. 建 `evaluation/recovery/fixtures/`：一个**最小 v2 项目**（从 `battle/2026-08-17` 的**形状**抽取，不含竞赛原文；battle 目录不入库）。用现有 `examples/end_to_end/run_demo.py` 的产物形状做参照，配 schema 校验测试。
3. 起 `evaluation/recovery/faults/F0X_*/inject.py` + `fault.json`（声明攻击面、篡改动作、期望检测点、`minimal_repair_set`）；每个故障配一个回归测试：**注入后 `harness status` / `harness validate` 必须报出 blocker**。检不出来就是发现——记为 gap 回写 `docs/`，**不要**放宽断言。
4. 恢复执行端（GAP-08）：把 `scripts/qa/plan_selective_rerun.py` 的计划落成可执行编排（逐产物经 `harness execute`/`freeze` 重建 → 复检 gate），repair 每步留 receipt。经 `scripts/runtime/` 调用，不要另起第二实现。

**不要**：不要在 C4b（agent 驱动）没跑之前写任何 recovery 数字；C4a 的 scripted repairer 只用于验证通道。

### 任务 C：P1-B 试点 —— 让 M1 经 verifier registry 解析 checker

**背景**：`scripts/verifiers/registry.py` 已能加载声明，且 `tests/test_verifier_registry.py` 会读取 `scripts/v2_gate_runtime.py` 的 `_v2_gate_<gate>` 源文本、断言声明的入口脚本真被调用。现在要把 Gate 从"硬编码脚本路径"改为"经 registry 取入口"。

**要求**
1. 先把 `GATE_ORDER` 收敛为单一来源（现存三处镜像：`scripts/harness.py`、`scripts/harness_status.py`、`scripts/qa/check_gates.py`），消除镜像陷阱（同类陷阱还有 `run_deterministic_qa.PROFILE_FLAG_LEVELS` 与 `check_gates.rerun_enhanced_deterministic_qa`）。
2. 再让 `_v2_gate_m1` 通过 registry 解析 `check_units.py` / `check_artifact_dag.py` 的路径，**argv 与退出码保持逐字节不变**（由现有测试锁定）。
3. 注意循环导入：`verifiers.registry` 目前导入 `check_gates`，而 `check_gates → v2_gate_runtime`；若 Gate 运行时反向导入 registry 会成环——先解掉这一依赖再接线。
4. 加回归测试：registry 缺失/坏声明时 Gate 的行为（fail-closed 还是保持现状，需明确定义并测）。

### 任务 D：P0-D —— CI 第二阶段（低预算，可随时插入）

1. Python 3.10/3.11/3.12 matrix（Ubuntu；`requires-python>=3.10` 已声明）。
2. 测试分层：按模块清单拆 unit 与 full 两个 job，PR fast path 不装 TeX。
3. `constraints-ci.txt` + `requirements-dev.txt` 版本界（numpy/pandas/matplotlib/networkx/scipy）。
4. Windows 轻量 job：非 LaTeX 子集 + import + schema + MCP 路径语义。
5. 【后续安排】nightly wheel 全矩阵、上游最新版 compat job——等 P0-A 后再做。

### 任务 E（【后续安排】，触发条件未到就别动）：P0-A / P0-B

- **触发条件**：P1-B 试点稳定 + `scripts/runtime/` 只读面可用（现已具备）；或用户明确下令。
- 第一步永远是**修订 `evaluation/PREREGISTRATION.md`**（任务集 = `docs/CAPABILITY_BENCHMARK_PLAN.md` 四 families、judge 协议、预算复核），再补 3 个 synthetic task，最后才跑 3 条件 × 4 任务 × 3 重复 = 36 runs。README 的 capability 数字只在那之后出现。
- P0-B 历史 E2E：`battle/2026-08-16`（2025 CUMCM A，agent-only；Q1 = 1.39198 s、Q2 = 4.5867 s、Q3 冻结值 3.635 s 可证次优，"Q2 最优弹 + 2 枚无害弹" ≥ 4.59 s 是现成校验点）与 `battle/2026-08-17`（v2 形状）都不入库，升格基准时抽 slim 版。

## 4. 已完成（不要重做）

| 项 | 提交 |
| --- | --- |
| P1-F runtime 只读面（get_state / verify_artifact / check_gate，CLI↔API 持平测试） | `04808f9` |
| 计划文档交接章节 | `64842a6` |
| P2-D 威胁模型 + DOC-CLAIMS 机器校验 | `c4e35e7` |
| P1-B verifier registry 契约（schema + registry + 两条真实声明） | `80b034a` |
| P1-A/P1-E 分支：checkpoint / fork / diff / compare | `2651a6b` |
| P1-D `harness bench`（harness 版本回归，ref 路径已验证） | `261b602` |
| P1-C capability composition（`harness profile --compose`） | `7f7f0f4` |
| P2-B agent 权限策略（`--agent-role`，MCP 边界强制） | `9a8e255` |
| P2-A execution capsule + `harness reproduce`（隔离副本内复现） | `e7b5e6d` |

完成任何一项后，请更新 `docs/EXECUTION_PLAN_2026-09-18.md` 的 §10 交接表，并保持 `tests/test_wp1_contracts.py` 的 schema 计数守卫同步。
