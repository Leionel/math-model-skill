# 下一阶段执行计划（细化版）：P1/P2 + P0-C 优先，P0-D 紧随

> 基线分支：`refactor/human-visible-workflow`
> 基线 HEAD：`91f99da`（2026-09-17），`harness-ci` 全绿（730 tests，skipped=1 为 vendor 快照条件跳过）
> 顺序决策（2026-09-18）：本轮先做 **P1（架构收敛）+ P2（信任/可复现）+ P0-C（恢复基准）**；
> **P0-D 排在 P0-C 完成之后立即启动（Wave 2），不与 P0-A/P0-B 一起后置**；
> 仅 **P0-A / P0-B 转入【后续安排】专区**，各有触发条件与届时起步点。
> 来源：2026-09-18 路线文档（Evaluation → Recovery → Extensibility）。本计划为该路线的执行级分解，所有仓库触点均于 2026-09-18 复核存在。

**【后续安排】标注约定**：出现在某工作项内部的【后续安排】= 该项本轮不做的子部分、触发条件与去向；出现在专区里的【后续安排】= 整个工作项的延后安排。所有评测/恢复/回归数字只能来自真实 run（AGENTS.md 完整性规则），本计划不预填任何数字。

---

## 0. 执行总览

### 0.1 排期（W1 = 2026-09-21 周一起）

| 周 | 泳道 A：Recovery | 泳道 B：P1 架构收敛 | 泳道 C：P2 信任/复现 | 备注 |
|---|---|---|---|---|
| W1 (09-21) | C0 设计冻结；C1 slim fixture 开工 | P1-F 只读 Runtime API 抽取 | P2-D `docs/THREAT_MODEL.md` | 插入项：D3 constraints-ci.txt |
| W2 (09-28) | C2 fault 套件 F01–F10 | P1-B registry 契约定稿 | — | — |
| W3 (10-05) | C3 恢复执行端（GAP-08）；C4a scripted runner | P1-B 试点 verifier ①（ClaimEvidence） | — | — |
| W4 (10-12) | C5 指标；C6 报告 v1；C4b agent-driven（视供给） | P1-B 试点 ②③（Freshness 含 GAP-16、UnitConsistency） | — | **P0-C 收尾** |
| W5 (10-19) | — | P1-A fork/checkpoint 最小实现 | — | **P0-D 启动（紧接 P0-C）**：D1 matrix、D4 分层 |
| W6 (10-26) | — | P1-E run diff | — | P0-D：D2 Windows 轻量 job、D5 cache |
| W7 (11-02) | — | P1-D regression lab（单任务版） | P2-B permission policy | P0-D 收尾 |
| W8 (11-09) | — | P1-C capability composition | P2-A backend/capsule（Local） | — |
| W9 (11-16) | — | P1-A compare 完善 | P2-C hash chain + checkpoint producer | — |
| W10 (11-23) | 收尾：全量回归、文档、README 措辞边界 | 同左 | 同左 | 里程碑 M2 见 §0.3 |

### 0.2 依赖图

```text
P1-F runtime API ──→ P0-C C3 编排 ──→ C4/C5 指标 ──→ C6 报告 ──→ 【Wave 2】P0-D
P2-D threat model ──→ P2-B permission policy ──→ P2-C attestation
P1-B verifier registry ──→ P1-C capability composition
P1-A checkpoint/fork ──→ P1-E run diff ──→ P1-D bench 呈现
P0-A、P0-B ──→ 【后续安排】专区（触发条件见 §4）
```

### 0.3 里程碑

- **M1（W4 末）**：Recovery Benchmark v1 可运行——≥10 faults 注入→检测→修复→复检全链路真实跑通，报告落盘 `evaluation/results/recovery-v1-<date>/`。
- **M2（W7 末）**：P0-D 完成（matrix + 分层 + Windows 轻量 job + constraints）；P1 试点 verifier 经 registry 驱动 Gate。
- **M3（W9 末）**：fork/diff/bench、backend/reproduce、policy/attestation 全部落地并配回归测试。

### 0.4 全局规则（对每个 PR 生效）

1. 每个行为变化配一个聚焦回归测试；测 CLI 退出码与产物，而非只测返回值（AGENTS.md）。
2. 契约变化同步改 schema + checker + 测试 + reference 文档。
3. 不预填任何 PASS/数字/receipt；`NOT_RUN` 状态如实保留（`evaluation/ablation.py` 的拒绝机制就是范例）。
4. commit 主题短祈使句；PR 说明列出受影响契约/Gate 与测试命令结果。
5. 本轮产出的**工程数字**（recovery、harness 版本回归）与 P0-A 的**能力数字**（A/B/C 对比）严格分开措辞，README 不混用。

---

## 1. Wave 1 主线一：P0-C Agent Recovery Benchmark

**目标**：从"错误被挡住"（`evaluation/redteam.py` 的 blocked/allowed 判定）升级为"挡住之后能修好"的可度量能力。这是 P0 三项中**唯一不依赖 A/B/C 外部评测臂**的项，本轮即可产出真实数字。

### 1.0 现状与真实触点（2026-09-18 复核）

| 件 | 现状 |
|---|---|
| 检测端 | `evaluation/redteam.py`：6 个链式场景（复用 `examples/end_to_end/run_demo.py` 探针：gate 字段伪造、freeze 无执行、下游 stale、reviewer 自荐、unsupported claim、正向链）+ 6 个本地场景（projection 拷贝、receipt 无 attestation、checkpoint 无 attestation、bound artifact 删除、DAG lineage 篡改、AI ledger 无交互）。**仅作用于内置 demo，无任意 project 入口** |
| 恢复端已有件 | `scripts/qa/plan_selective_rerun.py`（`build_rerun_plan(dag, root, changed)`，CLI `--dag --changed --json-output`，默认 `.harness/views/rerun_plan.json`，要求 DAG `schema_version=2.0`）；`scripts/harness_status.py`（gate 状态、first_blocker、pending human checkpoints、next action、`--json`）；`harness execute/freeze`（带 receipt 的真实执行） |
| 恢复端缺口 | **GAP-08：selective rerun 只有计划器、没有执行编排器** |
| 项目形状参照 | `battle/2026-08-17` = 完整 manifest v2 项目（roots：`contracts/model_contract.json`、`evidence_registry.json`、`artifact_dag.json`、`run_index.json`）。battle 目录刻意不入库（AGENTS：竞赛项目隔离），fixture 须抽 slim 版 |
| Agent 可用工具面 | `scripts/mcp_server.py` 只读 facade（`research_status/research_context/model_status/solve_status/paper_status/validate_current_stage/submission_check/doctor/ai_status`）+ `scripts/mcp_tools/` 的 COMPUTED_TOOLS（mutating 标记分离） |

### 1.1 任务分解

- **C0 设计冻结（W1，先于任何实现）**：新增 `docs/RECOVERY_BENCHMARK_DESIGN_2026-09-21.md`——fault 分类 F01–F10（沿路线 §5.1 清单）、注入→检测→修复→复检环、指标定义（含 unnecessary_rerun_ratio 公式）、PASS/FAIL 判定、scripted 与 agent 两种 repairer 的边界。
- **C1 slim v2 fixture（W1–W2）**：`evaluation/recovery/fixtures/base_project/`——从 `battle/2026-08-17` 的**形状**（非内容）抽取：最小 `run_manifest`（schema 2.0）、`contracts/model_contract.json`、`evidence_registry.json`、`artifact_dag.json`、`run_index.json`、1–2 个 frozen result 与对应 receipt。配 schema 校验回归测试；不含任何竞赛原始素材。
- **C2 fault 注入套件（W2）**：`evaluation/recovery/faults/FXX_<slug>/inject.py` + `fault.json`。`fault.json` 声明：`attack_surface`、篡改动作、期望检测点（哪个 gate/checker 必须报）、`minimal_repair_set`（最小必需重跑的 artifact 集）。清单：

  ```text
  F01 model_contract edited          F06 sensitivity run timeout
  F02 upstream artifact hash drift   F07 implementation_map drift
  F03 frozen result deleted          F08 unsupported numerical claim
  F04 receipt/result binding mismatch F09 citation source invalid
  F05 stale review                   F10 wrong parameter provenance
  ```

  每个 fault 一个回归测试：注入后 `harness status` / `harness validate` 必须报 blocker。**若 harness 检不出来，那是发现，记为 gap 回写 P1-B 待办，绝不放宽断言。**
- **C3 恢复执行端（W2–W3，即 GAP-08 落地）**：rerun 编排器——`plan_selective_rerun` 输出 → 逐 artifact 经 `harness execute`/`freeze` 重建 → 复检 gate；repair 每步走 receipt。实现在 `scripts/qa/`（与 planner 同层），经 P1-F 的 runtime API 调用，避免第二套真相。
- **C4a scripted runner（W3）**：`evaluation/recovery/run_recovery.py --repairer scripted`——按 `fault.json` 的 `minimal_repair_set` 机械执行修复。**用途是验证通道与指标计算正确性，不产出能力数字。**
- **C4b agent-driven runner（W4，视外部 agent 供给）**：agent 经 MCP 只读面 + CLI 自主定位并修复。这才是 benchmark 数字来源；供给不稳则如实记 `NOT_RUN`，不阻塞 C4a。
- **C5 指标收集（W4）**：`recovery_success_rate`、`mean_repair_steps`、`mean_tool_calls`、`recovery_wall_time`、`unnecessary_rerun_ratio = (实际重跑数 − 最小必需重跑数) / 实际重跑数`（最小必需 = `fault.json` 声明集）、`wrong_repair_rate`（gate 复检过但全量 `validate` 检出新 violation）、`regression_introduced_rate`。token 成本仅 C4b 有。
- **C6 报告（W4）**：`evaluation/results/recovery-v1-<date>/`——`report.md` + `summary.json` + 每个 fault 的完整轨迹（注入 diff、检测输出、修复步骤 receipts、复检输出）。

### 1.2 DoD 与风险

**DoD**：≥10 faults × scripted 全链路绿（检测+通道+指标自洽）；C4b 的数字可由原始轨迹重推导；报告无任何预填值。
**风险**：外部 agent 供给（C4b 可挂起）；fault 声明的"期望检测点"暴露 harness 盲区（按发现处理，见 C2）。

**【后续安排】**（P0-C 内部）：
- F11+ 扩充 → 触发条件：P0-B 真实 E2E 暴露新故障形态（见 §4.2）。
- 检测端与 P1-B verifier registry 合流（统一检测面）→ Phase 3。
- agent-driven 数字若外部 agent 未就绪 → 状态记 `NOT_RUN`，硬性诚实。

---

## 2. Wave 1 主线二：P1 架构收敛

### 2.1 P1-F Runtime API 渐进抽取（W1 最先，是 P0-C C3 的地基）

- **目标**：`CLI verdict = MCP verdict = API verdict` 单一实现；本轮不改任何行为。
- **做法**：新建 `scripts/runtime/`，先抽纯读三件：`runtime.get_state(root)`（← `scripts/harness_status.py`）、`runtime.check_gate(root, stage)`（← `check`/`validate` 分派）、`runtime.verify_artifact(root, artifact_id)`（← 单 checker）。`scripts/harness.py` 与 `scripts/mcp_server.py` 改为调用同一实现；现有 730 测试锁定 CLI 退出码与 JSON 输出不变。
- **抽取顺序**：get_state → verify_artifact → check_gate → rerun planning（P0-C C3 复用）→ review projection。
- **【后续安排】**：mutation paths 最后抽；不做一次性大重写（路线 §12 原则）。

### 2.2 P1-B Verifier Plugin Architecture（W2–W4）

- **触点**：`scripts/qa/check_gates.py`（Gate 大分支 + `rerun_enhanced_deterministic_qa`）、`scripts/qa/run_deterministic_qa.py`（`PROFILE_FLAG_LEVELS`）、`scripts/qa/check_consistency.py`、`check_math_writing.py`、`check_formula_replay.py`。
- **契约**：`schemas/verifier.schema.json` + `scripts/verifiers/registry.py`——`id / consumes / gates / severity / deterministic / repair_hint()`（YAML 声明，路线 §8 形态）。**契约定稿已完成**：声明经 schema + registry 校验，并由 `tests/test_verifier_registry.py` 绑定到真实 Gate 运行时（`_v2_gate_<gate>` 必须真正调用该入口脚本）；首批两条声明 `artifact-freshness`、`unit-consistency` 服务于 M1。Gate 行为未变，试点迁移为下一步。
- **试点三个，一次迁一个**（W3 ①、W4 ②③）：
  1. `ClaimEvidenceVerifier`（claim↔evidence 绑定）；
  2. `ArtifactFreshnessVerifier`（**吸收 GAP-16 上游新鲜度复检**）；
  3. `UnitConsistencyVerifier`。
  老 CLI 行为保持；每次迁移 = 回归测试 + schema + reference 文档三件套（AGENTS 契约规则）。
- **顺手收敛**：`run_deterministic_qa.PROFILE_FLAG_LEVELS` 与 `check_gates.rerun_enhanced_deterministic_qa` 的镜像陷阱 → 单一常量源（既有维护雷区，迁移 check_gates 时一并处理）。
- **【后续安排】**：其余 checker 批量迁移（试点稳定后）；GAP-13 caption 正文比对、GAP-07 M1 executors → P1-C 之后批次。

### 2.3 P1-A Scientific Fork / Time Travel（W5–W6、W9）

- **触点**：`run_manifest` v2、`battle/2026-08-17` 的 roots 形状、`human_checkpoints`（ask 语义已存在）。
- **命令面**：`harness checkpoint create --name <n>`；`harness fork --from <n> --name <m>`；`harness compare RUN-A RUN-B`。
- **最小实现**：checkpoint = manifest + roots + receipts 的不可变 hash 快照；fork = 新 project root 引用父快照；compare = 只读事实表（assumptions / model contract / parameter provenance / results / sensitivity / claims / evidence coverage / gate outcomes / review findings），**不做"最佳模型"判断**（路线 §7.1）。
- **【后续安排】**：time-travel replay 与后置的 Event Ledger 合流，不在本轮。

### 2.4 P1-E Run Diff（W6）

- `harness diff RUN-A RUN-B`；差异来源 = P1-A checkpoint 快照；输出路线 §11 的领域化 diff 清单（Model/Parameter/RMSE/Claim 状态/Sensitivity 增删等）。
- **【后续安排】**：transcript 级 trajectory diff（后置）。

### 2.5 P1-D Modeling Regression Lab（W7，范围收缩）

- **本轮只做 harness 版本回归**：`harness bench run --task examples/end_to_end --harness-ref <vA>..<vB>`；产出工程指标（gate 失败数、修复步数、重跑比、wall time），回答"新规则是提高系统还是只更严格更慢"。
- 完整 4 任务集与 A/B/C 能力对比**仍属 P0-A【后续安排】**——本轮 regression lab 不产出能力数字（仓库内唯一已提交任务是 `examples/end_to_end`）。
- **【后续安排】**：任务集扩到四 families（P0-A 的 A2 就绪后）；`harness bench` CLI 化完善。

### 2.6 P1-C Capability Composition（W8）

- 依赖 P1-B registry。capability = schemas + verifiers + artifact roles + gate hooks + repair hints + views 的打包；`competition_profiles/*.yaml`（`cumcm.yaml`、`mcm_icm.yaml`、`apmcm.yaml`、`_base_*.yaml`）组合 capability 集（路线 §9 的 CUMCM/MCM 组合式）。
- **【后续安排】**：第二 domain 出现前不抽象 Core/Profile 边界（路线 §19 原则）。

---

## 3. Wave 1 主线三：P2 信任与可复现执行

### 3.1 P2-D 正式 Threat Model（W1，提前——成本最低、被 P2-B/P2-C 引用）

- 新增 `docs/THREAT_MODEL.md`：T1 accidental / T2 careless / T3 adversarial agent / T4 malicious host + 路线 §16 现状表。
- 与 `evaluation/redteam.py` 场景一一对应（`receipt_provenance_is_not_attested`、`human_checkpoint_is_unattested` 已是现成场景）；为 README 使用 reliable/verified/tamper-resistant 划定词边界。
- **【后续安排】**：无——本轮完成并入库。

### 3.2 P2-B Agent Runtime Permission Policy（W7）

- **触点**：`agents/<role>/agent.yaml` 契约（7 角色）、`scripts/agent_contracts/contract.py`（scope checker，CI 已跑 `harness agents check`）、`scripts/mcp_server.py` 的 `MUTATING_TOOLS` / `tool_surface(include_mutating)`（mutating 标记已存在）。
- **做法**：契约 → 编译 → runtime capability policy；MCP facade 层 fail-closed 拒绝越权工具调用；先做**工具级** scope。
- **验收**：越权调用被拒的回归测试；`harness agents check` 增加"contract scope 与 runtime 工具面差集 = 0"断言。
- **【后续安排】**：文件级 read/write scope（路线 §14 的 `modeler: read problem/*`）后置。

### 3.3 P2-A Runtime Backend + Reproduce（W8–W9）

- **触点**：`harness execute`（receipt 捕获）、`harness freeze`。
- **步骤**：Execution Capsule schema（runtime/inputs/randomness/command/environment/outputs，路线 §13.1）→ Backend 接口（`execute / snapshot_environment / collect_outputs / compute_digests / terminate`）→ **LocalBackend 先行** → `harness reproduce <RESULT-ID>`（capsule → 重放 → 输出 digest diff）。
- **【后续安排】**：Docker/Conda/Remote backend（Local 稳定后）。

### 3.4 P2-C Receipt Hash Chain + Human Checkpoint Producer（W9）

- receipt schema（`schemas/`）增加 `previous_receipt_hash`、`execution_host_identity`、可选 signature；如实声明边界：**不能防恶意 host，只提高事后静默改史的检测性**（写入 THREAT_MODEL.md）。
- `harness checkpoint approve <STAGE>` → append-only decision artifact（checkpoint/decision/identity/timestamp/previous/signature）；dashboard 保持只读，approve 只经 producer（路线 §15.2）。
- **【后续安排】**：签名方案（本地密钥管理）后定。

---

## 4. Wave 2：P0-D CI / 复现性第二阶段（**紧接 P0-C 之后，W5–W7**）

> 定位澄清（2026-09-18）：P0-D **不与 P0-A/P0-B 一起后置**。P0-C 于 W4 收尾，P0-D W5 即启动，与泳道 B/C 并行。理由：本轮 P0-C/P1/P2 会新增大量测试与两个新命令族（recovery、fork/diff/bench），CI 分层与 matrix 正好承接；且 TeX 安装步骤已在 `ci.yml` 就绪，扩 matrix 边际成本低。

| 项 | 内容 | 周 |
|---|---|---|
| D1 | Python 3.10 / 3.11 / 3.12 matrix（ubuntu；`requires-python>=3.10` 已声明） | W5 |
| D4 | 测试分层先行：按模块清单拆 unit 与 full 两个 job；PR fast path 不装 TeX | W5 |
| D2 | Windows 轻量 job：非 LaTeX 子集 + import + schema + MCP 路径语义 + UTF-8/路径行为 | W6 |
| D5 | pip cache；TeX/poppler 安装只保留在 full job | W6 |
| D3 | `constraints-ci.txt` + `requirements-dev.txt` 版本界（numpy/pandas/matplotlib/networkx/scipy 各 `>=,<`）——**最小插入项，W1 即可一次小 PR，不等 W5** | W1 |

**【后续安排】**（P0-D 内部）：nightly wheel 全矩阵安装 job、上游最新版 compat job、historical regression job → 触发条件：P1 迁移稳定 / P0-A 任务集就绪（Phase 3）；不提前堆 CI 复杂度。

---

## 5. 【后续安排】专区：P0-A 与 P0-B

> 这两项是唯一整项延后的工作。延后不等于降级：它们回答的是"Harness 是否值得存在"的实证问题，触发条件一到即升为最高优先。

### 5.1 P0-A：A/B/C 实证 Evaluation

- **原目标**：把 `evaluation/PREREGISTRATION.md` 的 `NOT_RUN`（2026-09-17 状态）变为真实、可复现、可重推导的评测结果，回答 B→C 的可靠性与成本。
- **为何本轮延后**：用户决策顺序为架构优先；且 P1-B/P1-F 会改变 gate 行为与调用路径，能力数字应在稳定架构上取，避免跑完即漂移。
- **触发条件（任一即启动）**：
  1. P1-B 试点 verifier 稳定 + P1-F 只读面可用（预计 W4 末具备）；
  2. 用户明确下令启动实证阶段。
- **届时起步点（按序）**：
  1. 修订 `evaluation/PREREGISTRATION.md`：任务集 = `docs/CAPABILITY_BENCHMARK_PLAN.md` 四 families（optimization/prediction/evaluation/mechanism；`examples/end_to_end` 已覆盖 optimization）各出一道 synthetic task；judge 协议、预算（3 重复、40 turns、900 s、温度 0）复核；
  2. 补 3 个 synthetic task（`evaluation/tasks/synthetic/`），每个含独立可复算 ground truth；
  3. 补条件运行器与 `run_log.json` 产出（`evaluation/ablation.py` 的 `score` 已定义其 schema：`reached_stage/wall_clock_seconds/input_tokens/output_tokens/tool_calls`）；
  4. 执行 3 条件 × 4 任务 × 3 重复 = 36 runs；
  5. README capability numbers 只在数字真实存在后出现（仓库既有铁律）。
- **衔接注意**：若 P1 改动过 gate 行为，预注册修订必须记录 harness 版本差异，不得把架构变化静默吸收进条件对比。

### 5.2 P0-B：真实历史数模 E2E

- **原目标**：在真实题目全流程上跑 C 条件，暴露 schema 太重 / author surface 不自然 / gate timing / context 加载 / rerun 可执行性 / human checkpoint 频率 / review 速度等真实瓶颈。
- **触发条件**：P0-A 启动后（共享任务集与运行器）；或用户单独立项。
- **届时素材**（均在库外、刻意未提交，升格基准时抽 slim 版）：
  - `battle/2026-08-16`：2025 CUMCM A 题 agent-only 全程 run + 独立 kernel（Q1 = 1.39198 s；Q2 = 4.5867 s 可复算；**Q3 冻结值 3.635 s 可证次优**——"Q2 最优弹 + 2 枚无害弹"≥ 4.59 s，作为 E2E 的已知校验点）；
  - `battle/2026-08-17`：manifest v2 完整形状参照（P0-C C1 已抽 slim）。
- **届时前置小项**：profile switch（单 root 切 cumcm↔mcm）、GAP-11 `rules_frozen_at` 规则快照 TTL（设计已有、未实现）、GAP-12 `--check-retractions`。
- **battle 遗留 run-level 修复**（Q3 seeded rerun、framework figure 走 illustration lane、ledger 合并）：在 battle root 内补，不污染主线。

---

## 6. 后置探索（不变，仅登记触发条件）

| 项 | 触发条件 |
|---|---|
| Event Ledger（统一事件模型） | replay / fork / trajectory diff / audit timeline 同时需要时才做（路线 §17） |
| Modeling Decision Memory | Memory ≠ Evidence 原则下单独立项；不做通用向量记忆 |
| 第二 Domain Profile（首选 AI-assisted data analysis） | 前四阶段稳定后，用于检验 Core/Profile 抽象 |

---

## 7. 遗留项归位表（按本轮新顺序，2026-09-18 复核）

| 遗留项 | 去向 | 状态依据 |
|---|---|---|
| GAP-08 selective rerun 执行编排 | **P0-C C3（本轮 W2–W3）** | planner 已在 `scripts/qa/plan_selective_rerun.py`，编排器缺 |
| GAP-16 上游新鲜度复检 | **P1-B 试点 ②（本轮 W4）** | grep 未发现实现，路线 §8 freshness verifier 正好承接 |
| `PROFILE_FLAG_LEVELS` 镜像陷阱 | **P1-B 迁移 check_gates 时收敛（本轮）** | `run_deterministic_qa.py:44` 与 `check_gates.py:66` 手工镜像 |
| profile switch、GAP-11 rules TTL、GAP-12 retraction | 【后续安排】P0-B 前置 | grep 复核：`rules_frozen_at`/retraction 均未实现 |
| GAP-13 caption 正文比对 | 【后续安排】P1-B 第二批 或 P0-B | includegraphics 绑定已落地，正文比对未做 |
| GAP-07 M1 domain executors | 【后续安排】P1-C 之后 | 属 capability 执行器层 |
| battle run-level 修复（Q3 等） | 【后续安排】P0-B §5.2 | 见 battle 记录 |
| PDF numeric sweep | 【后续安排】P1-B claim-evidence 增强批次 | 数值↔冻结结果全文对账 |

---

## 8. 本周行动清单（W1 = 2026-09-21 ~ 09-25）

1. **P1-F**：`scripts/runtime/` 只读抽取（`get_state` / `check_gate` / `verify_artifact`），回归锁定 CLI 行为不变 —— **已完成，交接见 §10**。
2. **P2-D**：`docs/THREAT_MODEL.md` 初稿（T1–T4 + 现状表，对齐 redteam 场景）。
3. **P0-C**：C0 设计文档落稿；C1 slim fixture 开工（从 `battle/2026-08-17` 形状抽取）。
4. **P1-B**：`schemas/verifier.schema.json` 契约定稿。
5. **D3 插入项**：`constraints-ci.txt` + `requirements-dev.txt` 版本界（一次小 PR，不等 Wave 2）。

---

## 9. 与既有文档的关系

- `evaluation/PREREGISTRATION.md`：评测协议唯一真源；P0-A 启动时修订，本轮不动其 `NOT_RUN` 状态。
- `docs/CAPABILITY_BENCHMARK_PLAN.md`：任务 families 与预算清单思想，届时并入预注册修订；本轮不被引用出数字。
- 本轮工程数字（recovery v1、harness 版本回归）一律标注为工程回归证据，不与 A/B/C 能力数字混用；README 措辞以 `docs/THREAT_MODEL.md` 为边界。

---

## 10. 交接（2026-09-18，P1-F 已交付）

> 接续 agent 请直接执行 `docs/HANDOFF_PROMPT_2026-09-18.md`：它包含环境与验收命令、不可违反的规则、本会话踩过的坑，以及 P2-C / P0-C / P1-B 试点 / P0-D 的逐项任务块与"不要做什么"。

### 10.1 已交付

- 新增进程内只读面：`scripts/runtime/`（公共面 `__init__.py`，实现 `read_api.py`）——`get_state` / `verify_artifact` / `check_gate`。
- 抽取点放在**持有逻辑的模块**，runtime 不重写任何判定：
  - `harness_status.status_result(root, manifest_raw)`：原 `main()` 的装载与错误分支（退出码 0/1/2 语义原样保留）；
  - `harness_status.artifact_view(root, artifact_id, manifest_raw)`：基于 `_dag_view` 同一投影的单 artifact 判定（不是第二份 artifact 登记表）；
  - `check_gates.v2_gate_result(root, manifest_path, gate, strict)`：原 `main()` 的 v2 分支（含"后面的闸门不得在更早失败后自我报成功"的 break 语义与同一异常封装）。
  - 两处 `main()` 改为委托，行为不变。
- 契约：每个函数返回 `RuntimeView(payload, exit_code)`——`payload` 即 CLI 打印的 JSON，`exit_code` 即 CLI 返回码。
- 回归测试 `tests/test_runtime_api.py`（8 项）：CLI↔API 载荷持平（仅剔除时间戳）、退出码持平、`--strict` 持平、未知闸门拒绝、DAG current/stale 判定与 `harness status` 的 `dag.artifacts` 逐字段一致、未登记 artifact 为负判定、三次读取前后项目文件零变更（只读性）。
- 验证：全量 738 tests OK；`ruff check` 通过；CI 配置未变。

### 10.2 有意未做（下一手接续）

1. **CLI / MCP 的进程内接线未做**。`harness status`、`harness check` 与 MCP façade 仍走原有子进程门面；它们子进程内运行的已是被 runtime 复用的同一函数，因此「CLI verdict = API verdict」成立且已被测试锁住。首个真实进程内消费者应是 **P0-C C3 的恢复编排器**；届时若改动 `harness._dispatch`，必须保留其 `child_env()`/`cwd` 语义，或在 PR 里写明迁移理由。
2. **runtime 覆盖面仍是第一批**：`check_gate` → `verify_artifact` 已就位；`rerun planning`、`review projection`、mutation paths 按路线 §12 的顺序排在后面，不在本批。

### 10.3 接手所需的最小事实

- 入口：`scripts/runtime/__init__.py`（`RuntimeView`、`get_state`、`verify_artifact`、`check_gate`）。
- 新消费者的验收线：任何新的读取都必须通过 CLI↔API 持平测试（`tests/test_runtime_api.py` 的模式），**不得新增第二实现**；若某读取尚无 CLI 对应命令，先在 CLI 侧有行为、再抽 runtime。
- 已知边界：闸门名 runtime 接受任意大小写并归一为小写（CLI 仅接受大写 `M1`）；`artifact_view` / `check_gate` 只走 v2 运行时，v1 manifest 仅 `get_state` 给出降级视图。
- 下一步（与 §2.1 一致）：先接 P0-C C3（恢复编排器），再依次抽 rerun planning → review projection。

### 10.4 交接表更新（2026-09-18，P2-C 已交付）

任务 A（P2-C：Receipt 哈希链 + Human Checkpoint Producer）已完成：

- `schemas/command_receipt.schema.json` 增加可选 `previous_receipt_hash`（run_index 顺序上上一条 receipt 文件字节的 SHA-256）与 `execution_host_identity`（hostname + platform）；v1 receipt 不受影响。
- 生产者 `scripts/run_and_record.py::_run_v2` 写入上述字段；历史链断裂（上一条 receipt 缺失）时拒绝写新 receipt（fail closed）。
- 新增 `run_and_record.py --verify-chain --index <run_index.json>`：按 run_index 顺序重算链，删改/重排/删除历史 receipt 报错（退出码 1）；`--run-id/--stage/--receipt` 改为非 verify 模式下手动校验。
- 新增 `schemas/human_decision.schema.json`（schema 计数守卫 36 → 37）与生产者 `scripts/human_checkpoints.py`；新增 `harness checkpoint approve <STAGE> --role <ROLE> --decision approve|reject`：append-only 决策 artifact（`.harness/human_decisions/`，带全局序号 + `previous_decision_sha256` 决策链）+ 追加 `run_manifest.human_checkpoints` 行（`decision_artifact` + `decision_sha256` 绑定证据）；manifest 仍是控制真相。
- `docs/THREAT_MODEL.md` §5.1/§5.2/§8 改写为"已实现 X，仍未覆盖 Y"；redteam 场景与 DOC-CLAIMS 绑定保持不变（场景仍准确：无签名、无外部见证、身份为自我声明）。
- 回归测试 `tests/test_receipt_chain_and_decisions.py`（9 项）：链串联、完好/篡改/删除三种链校验退出码、approve 追加与决策链、append-only、非法 stage 与非 v2 manifest 拒绝（退出码 2）。
- 验证：目标测试 + 相邻面（doc_claims / checkpoints_and_diff / execution_capsule / agent_policy）+ `ruff check` + `harness agents check` 通过；全量 unittest 见提交记录。
