# integration/dsh — Math Modeling Harness × DeepSeek Harness 接入

依据 `docs/DSH_PLUGIN_INTEGRATION_PLAN_2026-08-22.md`（设想）与
`docs/DSH_PLUGIN_INTEGRATION_WORKPLAN_2026-08-22.md`（本轮实施记录）。

## 当前状态

| 阶段 | 内容 | 状态 |
|---|---|---|
| Phase 0 | 前置决定（零依赖 MCP 子集、project_root 白名单、代码归位、preset id） | ✅ 已定稿，见 workplan §1 |
| Phase 1 | 工作流主轴人设 + checkpoint 问法模板（本目录 preset） | ✅ 模板就绪 |
| Phase 2 | `scripts/mcp_server.py` 读/查 facade + 映射回归测试 | ✅ 已实施（9 工具） |
| Phase 2.5 | TS 薄原生变更适配层 spike（freeze → Deliverables chip） | ⬜ 未开始，验收项未达成前计划 §10 对应项不得标通过 |
| Phase 3 | checkpoint 审批卡 / 进度面板 / Evidence 面板 | ⬜ 未开始 |

## 目录

```
integration/dsh/
├── README.md                  ← 本文件
└── preset/math-modeling/      ← 预设 source of truth（部署即复制）
    ├── agent.cordis.yml
    └── preset.yml
```

## 部署预设

运行时位置是 `%DSH_HOME%\.agent-presets\math-modeling\`（默认即
`C:\Users\<you>\.dsh\.agent-presets\math-modeling\`），不进 Git。

```powershell
$src = "D:/Projects/随便做做/math-modeling-skill-sion/integration/dsh/preset/math-modeling"
$dst = Join-Path $env:DSH_HOME ".agent-presets/math-modeling"   # DSH_HOME 缺省为 ~/.dsh
New-Item -ItemType Directory -Force -Path $dst | Out-Null
Copy-Item -Force (Join-Path $src "*") $dst
```

**复制后必须核对 `agent.cordis.yml` 的 `mcp-math-harness` 行**：

1. `cwd`：指向 math-modeling-skill-sion 仓库根（server 自身目录；业务路径一律显式传参）；
2. `env.MATH_HARNESS_ALLOWED_ROOTS`：允许承载比赛项目的目录白名单，
   `os.pathsep`（Windows 为 `;`）分隔，如
   `"D:/Contests/CUMCM;D:/Contests/MCM"`。**留空 = 所有调用被拒（fail closed）**；
3. `command: python`：确认该名称解析到装有 PyYAML/jsonschema 的解释器
   （harness 运行所需）。

## 会话内验证

1. 新建会话选择 `数模模式 Math Modeling` 预设；
2. 工具清单应出现九个 `mcp__math_harness__*` 工具：
   research_status / research_context / model_status / solve_status /
   paper_status / validate_current_stage / submission_check / doctor / ai_status；
3. 负例：对白名单外路径调用任意工具，应收到
   `rejected: project_root … is outside the allowed roots […]`。

## headless 冒烟（不选预设的回归路径）

`dsh --profile headless` 无法选择 agent 预设；用 `--patch` 叠加层把 MCP 行
`insert` 进 headless 组合。注意 patch 条目是 id 定向补丁，新行必须放在
`insert:` 列表里（裸行会被当作"目标行不存在"而静默忽略）：

```yaml
# smoke-patch.yml
- insert:
    - id: mcp-math-harness
      name: '@deepseek-ai/dsh-mcp-client'
      config:
        serverName: math_harness
        transport: stdio
        command: python
        args: ["scripts/mcp_server.py"]
        cwd: "<仓库根>"
        env:
          MATH_HARNESS_ALLOWED_ROOTS: "<允许根>"
          PYTHONUTF8: "1"
        failOnStartupError: true
```

```powershell
dsh --profile headless --patch smoke-patch.yml "Reply with a single line listing every available tool name that starts with mcp__"
```

已验证（2026-08-22）：九个工具全部注册；Agent 经 MCP 取 doctor/status 并复述
`ok=True yaml=available jsonschema=available`、`first_blocked_gate=m1 pending=4`，
与 CLI 直跑真值一致。

## 回归命令

```powershell
python -m unittest tests.test_mcp_server -v      # facade 映射 + 白名单 + stdio 端到端
python -m unittest discover -s tests -q          # 全量回归
ruff check scripts/mcp_server.py tests/test_mcp_server.py
```

facade 映射表若因 `harness.py` 子命令变更而调整，须同 PR 更新
`tests/test_mcp_server.py::EXPECTED_TOOLS` 与映射断言（AGENTS.md 合约同步要求）。

## 安全红线（与计划 §8 一致）

- 不制造 PASS：工具只透传 exit code 与 JSON，LLM 复述不改变 verdict；
- project_root 白名单 fail closed；越界拒绝并回显原因；
- checkpoint 绑定当前 artifact（人类投影文档路径 + 机器侧 hash 双轨）；
- 本 MCP server 不出网；其包装的 harness 命令访问网络时按既有 contest_safety 规则审查；
- 只改用户根副本，不动 shipped presets 与 host composition。
