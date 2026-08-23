# DSH 插件接入计划（Math Modeling Harness × DeepSeek Harness）

状态：**设想/计划，未实施**。v2（2026-08-22）：吸收外部评审后修订——MCP 定位收缩为读/查通道、新增薄原生变更适配层（Phase 2.5）、Agent-facing 两级工具 API、checkpoint 以人类投影文档为主位、`project_root` 显式校验升为 P0、预设人设改用工作流主轴、明确代码归位于本仓库。所有"已有能力"均指对 DeepSeek Harness（DSH）随部署包与本仓库当前代码的实测阅读结论；所有"待建"项均未落地。

## 1. 目标与非目标

**目标**：让 DSH 会话中的 Agent 以结构化工具和窗口使用本仓库的检查链，使 DSH 成为 Math Modeling Harness 的**交互工作台**，而不只是能调 checker 的 Web UI：

1. 读/查操作经 MCP 以高层 facade 工具暴露（状态、阶段上下文、各 Gate 结论）；
2. 变更类操作（冻结、提交打包等）走薄原生工具适配层，产物进入 Web Deliverables；
3. 人工 checkpoint 获得结构化确认卡：主位展示人类投影文档（`02_MODEL_DECISION.md` 等），机器证据（JSON/hash/PASS）退居次要位；
4. 一个"数模模式" Agent Preset 把上述能力与人设固化，用户认知主轴采用 `research → model → solve → paper → review → submit` 工作流。

**非目标**：

- 不把任何 Gate 的 PASS 判定交给 LLM；DSH 只做执行面与呈现面，真相源仍是 JSON contract。
- 不改动 DSH shipped files（shipped presets、host composition）；全部通过用户根目录、profile patch 与外挂插件实现。
- 不在本仓库内实现全自动解题 Agent；模型选型、结论负责与提交仍由参赛队完成。

## 2. 总体分层

```text
┌────────────────────────────────────────────────────────┐
│ DSH 交互层（数模模式 Preset）                            │
│ 进度呈现 / Checkpoint 卡 / Human MD / Deliverables      │
└───────────────────────┬────────────────────────────────┘
                        │ 高层 facade 工具（MCP 只读 + 薄原生变更）
┌───────────────────────▼────────────────────────────────┐
│ Harness 工作流层（已落地：harness.py 子命令 + 人类投影）   │
│ research / model / solve / paper / review / submit      │
│ 00_PROJECT_BRIEF · 01_RESEARCH_NOTES ·                  │
│ 02_MODEL_DECISION · 03_SOLUTION_REPORT                  │
└───────────────────────┬────────────────────────────────┘
                        │ subprocess / 既有入口
┌───────────────────────▼────────────────────────────────┐
│ Evidence & Integrity Core（不改动语义）                   │
│ receipts / validation / frozen results / safety /       │
│ evidence registry / submission manifest                 │
└────────────────────────────────────────────────────────┘
```

本机事实（2026-08-22 实测）：

- `%DSH_HOME%` = `C:\Users\Administrator\.dsh`；`.agent-presets\` 尚不存在，首次 `copy()` 时由 roster 创建；
- 内置 preset：`standard`（全量基线）、`code`/PTC、`minimal`、`cordis`/创造模式；预设创作 copy-only，shipped 预设禁改；
- 本仓库 `harness.py` 已提供阶段级子命令（`status`/`context`/`research`/`model`/`solve`/`paper`/`review`/`submit` 等）、`prepare`（渲染确定性人类投影而不改 Gate truth）、`human_surface.py` 内置四份人类文档模板——v2 的 facade 与 checkpoint 设计直接以它们为载体。

## 3. 接入路径（v2 分工）

| 操作类别 | 通道 | 理由 |
|---|---|---|
| 读 / 查 / 校验（status、context、check 结论、doctor、AI 声明状态、S1 复验） | **MCP**（`mcp__math_harness__*`） | 结构化 JSON 回执即可，无需富呈现；官方桥接自带重连/超时/HMR |
| 变更且产出交付物（freeze、submission 打包、工程初始化、构建） | **薄原生 TS 工具适配层**（Phase 2.5 spike 起步） | Deliverables 词汇表依赖工具自声明的 render intent + `locations`；`dsh-mcp-client` 不生成这些，MCP 变更调用不会自动变成可点击交付物 |
| 大面板（进度、Evidence 视图） | client plugin 键位槽位（Phase 3） | 需 TS 工程 + Web 产物重建 |
| 人设 / 技能 / 工作流主轴 | Agent Preset（YAML 组装） | 纯配置 |

关键机制事实（决定上述分工）：Deliverables 行由"成功变更调用的 follow-along locations"折叠，识别依据是渲染意图（diff 卡或 `kind: edit` 泛型卡），不是工具名，也不是"产生了文件"；仅在收尾消息 inline code 提及而未经变更工具落盘的文件不进词汇表。推论：**变更操作走 MCP 不产生 Deliverables 呈现，要走原生适配层**。不走原生层的代价仅是呈现缺失（文件仍在 workspace，完整性不受影响），因此这是 UX 投资决策，按 Phase 2.5 spike 验证收益后再扩展规模。

MCP 桥接行（放进 preset；每会话独立 stdio 实例）：

```yaml
- id: mcp-math-harness
  name: '@deepseek-ai/dsh-mcp-client'
  config:
    serverName: math_harness          # 工具名前缀 mcp__math_harness__*
    transport: stdio
    command: python
    args: ["scripts/mcp_server.py"]
    cwd: "D:/Projects/随便做做/math-modeling-skill-sion"   # 仅 server 自身目录；业务路径一律显式传参
    failOnStartupError: true
```

若挂载审计报该行发布了 process-global service，则按 realm 规则包进 `isolate` 组；`standingKeyFor` 挂载验证是最终判据。

## 4. 两级工具 API（防止 checker 泛滥）

不把"Harness CLI 全部 MCP 化"当目标，只把"高层 intent"MCP 化：

```text
Agent-facing facade（默认可见，schema 常驻成本可控）
├─ research_status / research_context      ← harness.py status / context（阶段本地上下文计划）
├─ model_status                            ← model 子命令读取面
├─ solve_status                            ← solve 子命令读取面
├─ paper_status                            ← paper / review 读取面
├─ validate_current_stage                  ← validate / check（当前阶段 Gate 结论）
├─ submission_check                        ← submit check（S1 事实检查）
└─ doctor / ai_status                      ← doctor / ai status

Internal checkers（debug/repair 模式才暴露：第二个 serverName 或开关）
└─ 单个 Gate checker 透传（check <gate>）、原始 QA 输出等
```

映射以 `harness.py --help` 实际旗标为准（实施时逐条核对）；facade 返回值保持检查器原样输出（exit code + JSON），不做语义转述。

## 5. 全流程 × 窗口 × 人工物

| 工作流阶段（用户认知主轴） | 机器侧 Gate | 人工确认卡主位（Human MD） | 次要位（机器证据） | 呈现窗口 |
|---|---|---|---|---|
| 题意/调研 research | Contest Safety、规则快照 | `01_RESEARCH_NOTES.md` | safety check JSON | 工具卡 |
| 模型选型 model | M1 | `02_MODEL_DECISION.md` | `model_contract` hash + PASS | checkpoint 卡 |
| 求解 solve | P1→Full→P2 | `03_SOLUTION_REPORT.md` | 冻结 run 回执、claimable | checkpoint 卡 + Jobs |
| 论文 paper | W1→W2 | 分节草稿 / Paper Plan 投影 | readiness/QA 报告 | Plan review 卡 + Trajectory |
| 审查 review | W2 QA + Critic | 修订 decision memo | deterministic_qa.json | Trajectory |
| 提交 submit | S1/F1 | 提交清单投影 | submission_qa / F1 manifest | checkpoint 卡 |

Checkpoint 问法原则：**人类推理可见，机器状态退后台**。示例（model 阶段）：

> ### 本轮模型选择
> 主模型：XGBoost；Baseline：ARIMA；选择原因：（摘要自 `02_MODEL_DECISION.md`）
>
> *机器校验：PASS · Artifact: model_contract@a829bc1*
>
> [接受并进入求解] [需修改] [继续调研]

## 6. 依赖的 DSH 关键机制

1. **presentation intent**：`ask_user_question` 请求声明意图时渲染专属卡片；内置仅 `plan-review`（approve 标签由意图命名，裁决不依赖选项顺序）。Phase 3 的 checkpoint 卡即仿此新增意图。
2. **Deliverables / mutation render intent**：见 §3 关键机制事实。原生适配层工具须声明 diff 或 `kind: edit` 渲染并携带 locations。
3. **键位槽位**：浏览器半区插件向命名槽位注册条目（已证实 `conversation.chat.turnTail`、`conversation.composer`）。Phase 3 面板走此路；client-plugin 改动仅在 dev watcher 运行时热重载，否则需重建 Web 产物并刷新验证。
4. **headless**：`dsh --profile headless "<task>"` 一次性执行、exit code 表成败。后续 Python 执行面接 LLM Critic/Writer（`run_and_record --backend-cmd` seam）可用它做受控后端，receipt 照常入 DAG。

## 7. 分阶段实施

### Phase 0：前置决定（半天）

- MCP Python SDK 依赖归置（requirements-dev 或独立 extra）；
- **`project_root` 安全规则定稿（P0）**：所有工具显式接收 `project_root`，服务端 canonicalize 后校验其位于允许的 workspace roots 白名单内；禁止假定 server cwd == 项目根；所有 subprocess 显式 `cwd=project_root`。多项目并行（两个比赛窗口）不得串项目；
- **代码归位定稿**：见 §11——全部在本仓库内，不新开项目；
- preset id 定为 `math-modeling`；facade 工具清单对照 `harness.py --help` 核对定稿。

### Phase 1：零前端约定（1 天）

- preset 人设采用工作流主轴（research→model→solve→paper→review→submit），gate id 仅作机器侧引用；
- 固化 §5 checkpoint 问法模板与"MD 主位 / 证据次位"排版；要求 Agent 收尾消息用 inline code 引用产物路径；
- 验证：真实会话走一遍 model 阶段 checkpoint，确认问答卡渲染与答案落会话日志。

### Phase 2：MCP 读/查通道（2–3 天）

- 交付物：`scripts/mcp_server.py`（§4 facade 清单 + `project_root` 白名单校验 + 显式 UTF-8）、preset 中的 MCP 行、映射表回归测试；
- 明确不在本阶段承诺任何 Deliverables 呈现（那是 Phase 2.5 的验收项）；
- 验证：`dsh --profile headless` 冒烟（Agent 经 MCP 调 status/doctor 并复述 JSON 字段）；`project_root` 越界负例被拒。

### Phase 2.5：薄原生变更适配层 spike（3–5 天，按收益决定续做规模）

- 先做 **1 个工具**：包装 `freeze` 的 result 冻结分支，声明 edit-kind 渲染 + locations，验证产物 chip 进入 Deliverables 且可点击打开；
- spike 通过后再扩展到 submission 打包、工程初始化；始终遵守"工具只是执行者，verdict 由独立求值器产生"；
- 验证：真实会话执行冻结，Deliverables 行出现冻结文件 chip 并可打开。

### Phase 3：专属窗口（按需）

优先级：**P0 checkpoint 审批卡**（新增 presentation intent，主位 MD + 次要机器证据）→ **P1 阶段进度面板**（题意✓ 调研✓ 选型✓ 求解● 论文○…，点开显示 Human artifact / Machine status / Outstanding issues）→ P2 Evidence 面板。前置：TS client plugin 工程 + Web 产物重建流程。

## 8. 完整性与安全约束

1. **不制造 PASS**：工具原样返回 exit code 与 JSON；LLM 说 PASS 不得折算 deterministic PASS（与 `math_model_harness_prompt_v4_oss_scoped.md` 红线一致）。
2. **project_root 隔离（P0）**：见 Phase 0；白名单外路径一律拒绝并回显原因。
3. **checkpoint 纪律**：确认绑定当前 artifact（人类投影文档路径 + 机器侧 hash 双轨）；确认动作可从会话日志复现；问法原则见 §5。
4. **live contest 外写策略**：云端 LLM API 调用属 AI 使用，须登记 `run_manifest.ai_usage[]`；`live_contest` 下向外部端点发送当届题面按"外部写入"默认 deny，规则不明用 ask（`references/safety/contest_safety.md` 既有判定规则继续适用）。本地 stdio MCP server 不出网，但其包装的命令若访问网络仍按原策略审查。
5. **预设卫生**：只改用户根副本；`cordis` 预设损坏会禁用创造模式本身；不因 preset 放宽 sandbox/approval 边界。
6. **编码**：Windows 下 MCP stdio 通道与子进程输出显式 UTF-8，避免 GBK 乱码进入回执。

## 9. 风险与开放问题

| 风险 | 影响 | 缓解 |
|---|---|---|
| MCP server 生命周期（stdio 子进程随会话起停） | 长构建被会话结束打断 | 长任务走 DSH background job 而非 MCP 同步调用；Phase 2 验证项 |
| DSH 为 developer preview，存在 breaking changes；workspace-scoped MCP 有社区 RFC 讨论 | 机制细节漂移 | 文档记录实测版本行为；接入前后重验 §6 各机制；坚持只经用户根/profile patch/外挂插件接入 |
| 固定 cwd 导致多项目串扰 | 结果污染、违规外发 | `project_root` 白名单（P0）；必要时每项目独立 serverName |
| 工具 schema token 成本（每请求常驻） | 上下文占用 | 两级 API（§4）；facade 收敛数量，debug 工具按需启用 |
| 自定义窗口需重建 Web 产物 | 迭代慢 | 推迟至 Phase 3；Phase 1/2 不依赖 |
| 变更类工具被绕过人审语境调用 | 完整性 | 默认少暴露；暴露则工具内校验 manifest/Gate 前置状态 |

## 10. 验证清单

- [ ] Phase 1：model 阶段 checkpoint 问答卡在真实会话渲染，答案入会话日志，MD 主位排版生效；
- [ ] Phase 2：headless 冒烟——Agent 经 MCP facade 取 status/doctor JSON 并复述关键字段；
- [ ] Phase 2：`project_root` 白名单外路径被拒（负例测试）；
- [ ] Phase 2.5：freeze spike 产物 chip 出现在 Deliverables 且点击可打开（未做原生适配层前，此项不得标记通过）；
- [ ] Phase 2.5：preset 挂载验证通过（`standingKeyFor` 或新会话工具清单核对）；
- [ ] Phase 3：checkpoint 审批卡 approve 标签语义不依赖选项顺序；
- [ ] 回归：`python -m unittest discover -s tests -q` 全绿；facade 映射表变更有配套测试。

## 11. 代码归位

**全部在本仓库内实施，不新开项目。** 归属判断依据是耦合度而非语言差异：

| 组件 | 位置 | 理由 |
|---|---|---|
| `scripts/mcp_server.py` | 本仓库 `scripts/` | 包装的是本仓库 `harness.py` facade；CLI 子命令每次变更，MCP 映射表须同 PR 跟进（AGENTS.md 要求 schema/checker/tests/docs 同步更新），分仓库即跨仓同步 |
| facade 映射回归测试 | 本仓库 `tests/` | 必须随 `python -m unittest discover` 一起跑，同仓才有保证 |
| preset 模板 | 本仓库 `integration/dsh/preset/` | 运行时位置 `%DSH_HOME%\.agent-presets\math-modeling\` 不进 Git；source of truth 进版本控制，部署即复制 |
| TS 原生适配层 / client plugin | 本仓库 `integration/dsh/` | 工具链不同（pnpm/esbuild vs pip/ruff），子目录即可隔离：ruff 只扫 `scripts/`、`tests/`，Python 侧不受污染 |

拆出独立仓库的触发条件（当前均不成立）：TS 插件需要 npm 公开发布；插件需包装不止本 harness；CI 需求冲突到无法共存。另注意 AGENTS.md "contest projects 单独 project root" 指**比赛项目**不进本仓库；DSH 集成属 harness 工具链，恰属此处。若引入 `integration/dsh/`，同步更新 AGENTS.md 的 Project Structure 一节。
