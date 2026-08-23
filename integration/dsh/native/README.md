# integration/dsh/native — 原生工具适配层（Phase 2.5 / 3 实施记录）

状态：**动态 Cordis 插件形态已在会话内验证**；持久化部署（profile 插件）待做。
本文是机制结论 + 源码归位，供后续 TS 化或直接复用。

## 已验证的机制事实（2026-08-22 实测）

1. **Deliverables 折叠按渲染意图，不按工具名**
   `dsh-client-ui-deliverables/lib/client.js producedPaths()`：`card === "diff"` 或
   `card === "generic" && kind === "edit"` 的 **call view** 的 `locations[].path`
   在成功 `tool/result` 时折叠进本 turn 的 Deliverables；isError 结果跳过。
   locations 只存在于 call view（result view 无此字段）。

2. **动态原生工具可带 presentCall**
   `harness.defineTool` / `ctx.tools.register` 接受
   `presentCall(args) → {card,title,kind?,diffs?,locations?}`；
   host 端 apiproxy 在 `tool/call` 事件时重新调用 presenter 并随事件持久化，
   客户端据此渲染卡片与 Deliverables chip。实测 `harness_freeze_results`
   以 `{card:'generic', kind:'edit', locations:[{path: output}]}` 成功产出 chip。

3. **composer 是开放接管链**
   `conversation.composer` chain 按 `priority` 升序选举（最低者胜），
   shipped 的 question 选择器占默认 priority 0。注册 `priority: -100` +
   `select` 认领 `intent.kind === 'contest-checkpoint'` 即可在不改动 shipped
   代码的前提下渲染专属决策卡。host 对未知 intent kind 只校验
   `approve ∈ options` 且 `detail` 存在（`BAD_INTENT`），kind 本身不设白名单。

4. **白名单基准是会话 cwd**
   `exec.agent.session.header.cwd` 才是会话工作区；`sandboxPolicy.workspaceRoot`
   是进程主目录（本部署为 `C:\Users\Administrator`），不能用作业务路径基准。

5. **面板座位是 `conversation.input.dock`**
   该槽位可承载常驻面板（本实现：进度 / Evidence 双 tab + 20s 轮询），
   无需重建 Web 产物；`conversation.chat.turnTail` 是 conversationEvents
   注册而非 slots 座位，动态 client 插件不依赖它。

## Phase 3 交付（2026-08-23 完善）

| 计划项 | 实现 | 验证 |
|---|---|---|
| P0 checkpoint 审批卡 | `checkpoint.host.js` 的 `contest_checkpoint` + `checkpoint.client.js` 的 composer 接管卡；approve 语义骑标签（`approved: decision === approve`），与选项顺序无关 | 会话内验证（前轮）；host 正/负例见 `verify-host.js` |
| P1 阶段进度面板 | `checkpoint.client.js` PanelsDock「进度」tab：六 Gate 行（✓/●/○ + 状态），点击展开 Human artifact（投影文档 + 在案/缺失）/ Machine status（evidence_keys）/ Outstanding issues（errors、warnings、待确认 checkpoint、陈旧产物、w2 审查意见）；数据来自 `mm-progress`（`harness status --json` 只读投影） | `verify-host.js` 全量断言通过 |
| P2 Evidence 面板 | PanelsDock「Evidence」tab：条目计数（verified/pending/rejected）+ 可展开条目（supports/boundary/result_ids/artifacts sha256/citation）；数据来自 `mm-evidence`（`evidence_registry.json` 只读投影） | `verify-host.js` 正/负例通过 |

Phase 3 验收对照（计划 §10）：
- [x] checkpoint 审批卡 approve 标签语义不依赖选项顺序；
- [x] 进度面板展示六 Gate 状态并可展开 Human artifact / Machine status / Outstanding issues；
- [x] Evidence 面板展示证据注册表条目与验证状态；
- [x] 全部为只读投影，verdict/回执由 CLI 内独立求值器产生，无编造 PASS。

## 源码

| 文件 | 对应动态插件 | 内容 |
|---|---|---|
| `checkpoint.host.js` | mmchk-4/pkg-5（Phase 3 合并包） | `contest_checkpoint`（intent 化 ask、文档 sha256 绑定、阶段选项）+ `harness_freeze_results`（**已并入本包**，调用时记录 project_root）+ `mm-progress`（全量 gate 载荷 + 人类文档存在性）+ `mm-evidence`（evidence_registry 投影） |
| `checkpoint.client.js` | 同上 | composer 接管链渲染 checkpoint 决策卡（priority -100）+ `conversation.input.dock` 的进度/Evidence 双 tab 面板 |
| `freeze.tool.host.js` | （存档） | Phase 2.5 独立 spike 的历史记录；**已被 checkpoint.host.js 取代，勿再挂载**（避免重复注册工具） |
| `verify-host.js` | — | 无 Cordis 端到端验证：stub `subprocess` 后真实跑 `harness status`/python 探针，断言 mm-progress/mm-evidence 投影 |
| `smoke-render.js` | — | 渲染路径冒烟：stub React（mini hooks）+ host.call，走通进度/Evidence/决策卡/空态/错误态五条渲染路径，23 项断言（含展开态详情） |
| `../plugin/`（`package.json` + `lib/index.js` + `cordis.patch.yml` + `verify-static.cjs`） | — | **静态 host 插件 `mm-phase3`**（重启持久）：`contest_checkpoint` + `harness_freeze_results` 经 `ctx.tools.register` 注册（canonical ToolDefinition，零依赖）；`verify-static.cjs` 为无 Cordis 验证脚本 |

共同安全契约：
- project_root / human_doc 必须位于 `exec.agent.session.header.cwd` 内，
  规范化后大小写不敏感比较，越界拒绝并回显原因；
- 工具只是执行者：PASS 由 CLI 内独立求值器产生，原样透传 exit code 与 JSON；
- 失败调用 throw（isError），不产生 Deliverables chip；
- RPC 也是只读投影：`mm-progress`/`mm-evidence` 只读 `status --json` 与
  `evidence_registry.json`，不写任何文件、不计算 verdict。

## 会话内验证记录

- 正例冻结：exit 0，stdout JSON `{status:"frozen", validation_verdict:"PASS", claimable:true}`
  原样返回；`frozen_by_tool.json` 落盘并成为本 turn Deliverables chip。
- 负例重复冻结：CLI 拒绝覆盖（exit 1），工具失败并附验证器输出，无 chip。
- 白名单越界：`rejected: project_root … is outside this session workspace …`。

## 验证命令（无 Cordis，可重复）

```powershell
# 1) 语法检查
node --check integration/dsh/native/checkpoint.host.js
node --check integration/dsh/native/checkpoint.client.js

# 2) host 端到端（fixture 已存在于 tmp/phase3-fixture；evidence 正/负例）
node integration/dsh/native/verify-host.js tmp/phase3-fixture                # evidence 缺失负例
node integration/dsh/native/verify-host.js tmp/phase3-fixture --seed-evidence  # 正例

# 3) client 渲染冒烟（进度 / Evidence / 决策卡 / 空态 / 错误态，23 项断言）
node integration/dsh/native/smoke-render.js
```

fixture 重建（若 tmp/phase3-fixture 被删）：`harness init --project tmp/phase3-fixture
--competition cumcm --preset research --json`，并写入四份人类投影文档
（`01_RESEARCH_NOTES.md` / `02_MODEL_DECISION.md` / `03_SOLUTION_REPORT.md` /
`paper/00_PAPER_PLAN.md`）；`--seed-evidence` 用例需先写入 schema 合法的
`evidence_registry.json`（参考 `schemas/evidence_registry.schema.json`）。

## 持久化部署（2026-08-23 混合方案已实施）

机制结论：`harness.*`（defineTool/registerTool/handle）与 `host.call`↔`harness.handle`
RPC 通道都是**动态沙箱专属**；静态 profile 插件的工具注册走 `ctx.tools.register`
（canonical ToolDefinition，支持 `presentCall`/`presentResult`），client↔host 通信
只能走 api-remotes 网关（能力集构建期写死，挂新能力需改 shipped 代码，违背
"不改 shipped"原则）。因此采用**混合**：

1. **静态插件 `mm-phase3`**（`../plugin/`）：两个工具经 `ctx.tools.register` 注册，
   重启后依然可用。安装：`dsh plugin --profile web add ./integration/dsh/plugin`
   （已装：profile bundles 含 `mm-phase3`）；激活需重启 `dsh web`。
2. **面板保持会话级动态插件**：`checkpoint.client.js` 的进度/Evidence 面板与
   `mm-progress`/`mm-evidence` RPC 走动态沙箱，进程存活期间可用；重启后由
   cordis 会话按 `cordis_define`/`cordis_run` 重新挂载（或后续轮次把面板数据源
   改为静态可用的通道）。

**挂载注意**：host 侧工具（`contest_checkpoint` / `harness_freeze_results`）由静态
`mm-phase3` 注册，**勿再**用动态 `checkpoint.host.js` 重复注册同名工具（会冲突）；
`freeze.tool.host.js` 已存档为空。动态侧只挂 `checkpoint.client.js`（面板）。
