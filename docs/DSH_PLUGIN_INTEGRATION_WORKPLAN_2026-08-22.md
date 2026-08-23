# DSH 插件接入 · 具体工作方案（2026-08-22）

依据：`docs/DSH_PLUGIN_INTEGRATION_PLAN_2026-08-22.md`（v2 设想）。本文把该设想落成可执行任务清单，并记录 Phase 0 的最终决定与实施证据；Phase 3 完善记录见 §3.5。状态标记：**[已完成]** / **[本轮实施]** / **[待后续轮次]**。

## 1. Phase 0 前置决定（定稿）

| 决定点 | 结论 | 理由 |
|---|---|---|
| MCP Python SDK | **不引入官方 `mcp` 包**；在 `scripts/mcp_server.py` 内自实现最小 stdio 子集（initialize / tools/list / tools/call，换行分隔 JSON-RPC 2.0） | facade 只桥接读/查工具，协议面小且由回归测试锁定；避免为 9 个只读工具引入 pydantic 级依赖链；`requirements-dev.txt` 保持精简。若未来需要 resources/prompts 再评估独立 extra |
| `project_root` 安全规则（P0） | 所有工具显式接收 `project_root`；服务端 `Path.resolve()` 规范化后校验其位于 `MATH_HARNESS_ALLOWED_ROOTS`（`os.pathsep` 分隔）白名单内；**变量缺失或为空 = 全部拒绝**（fail closed）；Windows 下用 `os.path.normcase` 比较；所有 subprocess 显式 `cwd=project_root` 且强制 UTF-8（`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`、stdio 字节层显式编解码）；白名单外拒绝时回显原因 | 计划 §7 Phase 0 / §8.2；禁止假定 server cwd == 项目根；多项目并行不串项目 |
| 判定语义 | 工具结果按"是否执行成功"分两层：子进程跑起来 → `isError=false`，原样返回 exit code + stdout/stderr（structuredContent 携带）；参数非法/越界/超时/spawn 失败 → `isError=true` + 文本原因。**Gate FAIL 是合法结论，不是执行错误** | 计划 §8.1 不制造 PASS、不语义转述 |
| 超时 | 服务端单次调用上限 55s（低于 dsh-mcp-client 默认 60s），长构建按计划走 DSH background job，不经 MCP 同步通道 | 计划 §9 风险表第 1 条 |
| preset id | `math-modeling` | 计划 §7 Phase 0 |
| 代码归位 | 全在本仓库：`scripts/mcp_server.py`、`tests/test_mcp_server.py`、`integration/dsh/preset/math-modeling/`、`integration/dsh/README.md`、`integration/dsh/native/`（Phase 2.5/3 原生适配层 + 验证脚本）；同步更新 AGENTS.md Project Structure | 计划 §11 |
| facade 清单 | 对照 `harness.py --help` 实测核对（见 §2 表） | 计划 §4 |

## 2. facade 映射表（回归测试锁定）

统一注入：`python scripts/harness.py <argv> --project <project_root> --json`。

| MCP 工具 | harness 子命令 argv 额外部分 | 参数 schema 要点 |
|---|---|---|
| `research_status` | `status` | — |
| `research_context` | `context --stage <stage>` | stage: string（research / model / solve / paper:<section>） |
| `model_status` | `model` | — |
| `solve_status` | `solve` | — |
| `paper_status` | `paper plan` | — |
| `validate_current_stage` | `check <gate>`（+ `--strict` 可选） | gate 枚举 M1/P1/P2/W1/W2/S1，必填 |
| `submission_check` | `submit check`（+ `--strict` 可选） | — |
| `doctor` | `doctor --offline` | — |
| `ai_status` | `ai status` | — |

Internal checkers（单 Gate 透传之外的原始 QA 输出等）本阶段不暴露；如需 debug 第二 serverName，另开行再评估。

## 3. 任务分解

### 本轮实施
1. [已完成] `scripts/mcp_server.py`：零依赖最小 MCP stdio server + 白名单校验 + UTF-8 强制。
2. [已完成] `tests/test_mcp_server.py`：
   - facade 映射表回归——每个工具构造的 argv 能被真实 `harness.build_parser()` 解析；
   - `project_root` 白名单正/负例（含空表全拒、normcase 大小写、嵌套路径）；
   - stdio 端到端：initialize → tools/list 与映射表一致 → tools/call(status) 返回 exit_code=0 且 JSON 可解析 → Gate FAIL 原样透传（exit_code=1、isError=false）→ 越界路径被拒并回显原因。
3. [已完成] `integration/dsh/preset/math-modeling/`（`agent.cordis.yml` + `preset.yml`）：以 shipped `standard` 为基线的工作流主轴人设 + `mcp-math-harness` 行（stdio、`failOnStartupError: true`、`MATH_HARNESS_ALLOWED_ROOTS` 经 env 注入）。MCP client 只注册工具不发布 service，无需 isolate realm。
4. [已完成] `integration/dsh/README.md`：部署步骤、必改项、验证清单对照计划 §10，含 headless 冒烟的 `--patch insert:` 配方。
5. [已完成] AGENTS.md Project Structure 补充 `integration/dsh/`。
6. [已完成] 验证证据（2026-08-22 实测）：
   - `python -m unittest tests.test_mcp_server`：17 项全绿；
   - `python -m unittest discover -s tests -q`：442 项全绿；
   - `ruff check scripts/mcp_server.py tests/test_mcp_server.py`：通过；
   - 预设已部署到 `%DSH_HOME%\.agent-presets\math-modeling\`（部署副本白名单置为仓库父目录 `D:/Projects/随便做做`，可按需收紧）；
   - 挂载验证：动态探针插件经 `agentPresets.standingKeyFor('math-modeling')` 真实组装预设子树，无任何拒绝诊断（组合合法、MCP 行通过 dsh-mcp-client schema 校验）；
   - headless 冒烟：经 `--patch` 叠加层挂载同一 MCP 行后，真实 DSH 会话工具清单出现全部九个 `mcp__math_harness__*`；Agent 调用 doctor/status 并复述 `ok=True yaml=available jsonschema=available`、`first_blocked_gate=m1 pending_checkpoints=4`，与 CLI 直跑真值逐字段一致——无编造 PASS。计划 §10 的"headless 冒烟"与"`project_root` 白名单外路径被拒（负例测试）"达成；"preset 挂载验证"以 standingKeyFor + 会话工具清单双重确认。

### 实测发现（补充到计划 §6 机制事实）
- `dsh --patch` 叠加层的条目是 **id 定向补丁**（`@deepseek-ai/cordis-plugin-include` 的 `PatchOptions`）：插入新行必须写 `- insert: [...]`；裸行会被当作"目标行不存在"静默忽略（仅 Loader warning）。预设文件本身不受影响——`agent.cordis.yml` 用的是完整行形状。
- headless profile 不支持选择 agent 预设；免 UI 的冒烟路径是 `--patch` 叠加层（配方见 `integration/dsh/README.md`）。

### 待后续轮次
- **Phase 1** 会话级验证：真实会话选择 math-modeling 预设走 model 阶段 checkpoint（问答卡渲染、答案落会话日志）——需要人工开一个会话确认。
- **Phase 2.5 spike**（原生变更适配层）：已做并在会话内验证（`integration/dsh/native/freeze.tool.host.js` 存档，工具已并入 Phase 3 合并包）。
- **Phase 3 窗口**：见下节（2026-08-23 已完善 P0/P1/P2，动态插件路线）。
- 收紧部署副本白名单：当前为 `D:/Projects/随便做做`（仓库父目录），用户可改为实际比赛项目目录。
- 持久化部署路线决定：profile 插件 vs 保持会话级动态插件（见 `integration/dsh/native/README.md`）。

## 3.5 Phase 3 完善记录（2026-08-23）

沿用已验证的动态 Cordis 插件架构（无需重建 Web 产物），Phase 3 三个交付全部落地：

- **P0 checkpoint 审批卡**（完成，前轮会话内验证）：`contest_checkpoint` 工具 + composer 接管卡；approve 语义骑标签（`approved: decision === approve`），与选项顺序无关——满足计划 §10 验收项。
- **P1 阶段进度面板**（完成）：`conversation.input.dock` 常驻面板「进度」tab，六 Gate 行（✓/●/○ + 状态），点击展开 Human artifact（投影文档 + 在案/缺失）/ Machine status（evidence_keys）/ Outstanding issues（errors、warnings、待确认 checkpoint、陈旧产物、w2 审查意见）。数据来自 `mm-progress` RPC（`harness status --json` 只读投影）。
- **P2 Evidence 面板**（完成）：同面板「Evidence」tab，`mm-evidence` RPC 只读投影 `evidence_registry.json`，展示计数（verified/pending/rejected）与可展开条目（supports/boundary/result_ids/artifacts sha256/citation）。

实现归位：`integration/dsh/native/checkpoint.host.js`（合并包：`contest_checkpoint` + `harness_freeze_results` + `mm-progress` + `mm-evidence`）、`checkpoint.client.js`（决策卡 + 双 tab 面板）、`verify-host.js`（无 Cordis 端到端验证脚本）。`freeze.tool.host.js` 转为存档（避免重复注册）。

验证证据（2026-08-23 实测）：`node integration/dsh/native/verify-host.js tmp/phase3-fixture [--seed-evidence]` 全量断言通过——mm-progress 六 Gate 载荷、m1 blocked/first_blocked、人类文档在案映射、pending/next_action/receipts、白名单越界拒绝、mm-evidence 正例（verified 计数/artifact sha256/supports/boundary）与缺失负例；`node --check` 三份 JS 全通过；`node integration/dsh/native/smoke-render.js` 渲染冒烟 23 项断言全通过（进度/Evidence 双 tab、展开态 Human artifact / Machine status / Outstanding issues、决策卡、空态/错误态文案）。面板真实会话渲染需人工确认（同 Phase 1）。

**挂载注意**：Phase 3 host 侧工具（`contest_checkpoint` / `harness_freeze_results`）由静态 `mm-phase3` 注册；动态 `checkpoint.host.js` 勿再挂载（避免同名工具冲突），`freeze.tool.host.js` 已存档为空；动态侧只挂 `checkpoint.client.js`（面板）。

**持久化部署（2026-08-23 混合方案，已实施）**：机制核查确认 `harness.*`/`host.call` 为动态沙箱专属，静态 profile 插件无法携带面板 RPC（api-remotes 网关能力集构建期写死）。落地混合——静态插件 `integration/dsh/plugin/`（`mm-phase3`，两个工具经 `ctx.tools.register` 注册，canonical ToolDefinition 零依赖；`dsh plugin --profile web add` 已安装进 web profile bundles）＋ 面板保持会话级动态插件；激活需重启 `dsh web`。静态插件验证：`node integration/dsh/plugin/verify-static.cjs tmp/phase3-fixture` 13 项断言通过。详见 `integration/dsh/native/README.md`。

## 4. 验证命令备忘

```powershell
python -m unittest tests.test_mcp_server -v
python -m unittest discover -s tests -q
ruff check scripts/mcp_server.py tests/test_mcp_server.py
# 部署后（另一机器需先改 cwd 与 MATH_HARNESS_ALLOWED_ROOTS）：
# 新会话选择 math-modeling 预设 → 工具清单应出现 mcp__math_harness__* 九项
```
