# Math Modeling Evidence Harness

这是一个证据、验证与竞赛合规 Harness。正常使用只需要一个 paper project
root、一个比赛 seed/competition 和一个 preset；底层脚本仍保留为 debug
appendix。Harness 不替用户猜题、伪造结果、上传比赛门户或把测试当成奖项
能力证明。

## 5–10 分钟上手

在仓库根目录运行：

```powershell
python scripts/harness.py init `
  --project C:\work\math-q1 `
  --competition cumcm `
  --preset research

python scripts/harness.py status --project C:\work\math-q1
python scripts/harness.py check M1 --project C:\work\math-q1 --profile research --json
```

如果希望使用短命令，在本地 checkout 做 editable 安装：

```powershell
python -m pip install -r requirements-dev.txt
python -m pip install --no-deps -e .
harness --help
```

当前 `harness` console entry 支持本地 editable checkout；尚未承诺把 schemas、
references、assets 和模板打入可独立分发的 wheel。发布型 wheel 属未来平台化
范围，不能用一次 `pip install .` 的成功替代资源完整性验证。

`init` 只写 v2 的四个最小文件：`competition_profile.json`、
`run_manifest.json`、`artifact_dag.json`、`run_index.json`。它不创建几十个
空 JSON，也不生成不存在的 model、result、paper 或 receipt。新项目会停在
M1，直到用户提供真实题面、数据边界、模型合同、验证计划和人工确认。

继续执行时，使用同一个 project root：

```powershell
# 真正运行并捕获 receipt；命令的 stdout/stderr/exit code 保留
python scripts/harness.py run --project C:\work\math-q1 --stage smoke -- python model.py

# 无 backend 时只生成 bundle 与人工路由说明；报告写好后用 --recheck 导入
python scripts/harness.py review --project C:\work\math-q1 --json
python scripts/harness.py review --project C:\work\math-q1 --recheck --json

# 实际 fresh reviewer：子进程从 bundle 目录启动，执行事实写入 receipt
python scripts/harness.py review --project C:\work\math-q1 --fresh `
  --backend-cmd "python C:\tools\reviewer.py" --json

# review evidence current 后，再跑完整 W2 Gate（复用既有 deterministic QA）
python scripts/harness.py validate --project C:\work\math-q1 --strict

# 结果与提交冻结仍由既有 producer 负责
python scripts/harness.py freeze --project C:\work\math-q1 --kind results `
  --source results.json --output frozen_results.json --run-id <run-id> `
  --model-contract model_contract.json --code model.py --validation validation.json

python scripts/harness.py profile --project C:\work\math-q1 --json
python scripts/harness.py doctor --project C:\work\math-q1 --json
```

对 Agent/CI 使用 `--json`；无 `--json` 时 review 会在 stderr 流式显示阶段
进度，其他命令给出人类摘要。命令返回码是事实状态：无 backend 的 review
会在等待人工报告时返回非零，这是 pending，不是已完成。`--fresh` 证明的是
bundle、工作目录、receipt 与报告的绑定；它不是 OS 级沙箱。submission 使用
者仍须把 backend 放在真正的新上下文/独立模型中运行。

`check/validate --profile` 是兼容性断言：它只能与 manifest 已绑定的 preset
一致，不能在检查时临时覆盖 Gate policy。正常情况下可省略该参数。

## 给指挥 Agent 的可复制 Prompt

先替换开头 5 个变量，再把整段交给 Codex、Claude 或其他执行 Agent。Harness
目录与比赛项目目录必须分开；同一上下文里的作者自审只能标为 L0，不能冒充
fresh reviewer。

```text
你要使用现有 Math Modeling Evidence Harness 完成一次证据约束的数模任务。

固定参数：
- HARNESS_ROOT = D:\Projects\随便做做\math-modeling-skill-sion
- PROJECT_ROOT = D:\Competitions\当前赛题
- COMPETITION = cumcm            # 可改为 mcm_icm / apmcm
- PRESET = research              # sprint / research / submission
- INPUTS = 题面、附件数据及用户给定参考资料的绝对路径

执行规则：
1. 先完整读取 HARNESS_ROOT\SKILL.md，再从 references\router.md 只加载当前
   Gate 需要的 reference；不要一次性加载所有材料。
2. 所有 Harness 命令从 HARNESS_ROOT 执行，所有比赛 artifact 写入
   PROJECT_ROOT。不要把论文项目写进 Harness 仓库，也不要修改 HARNESS_ROOT
   的代码、schema 或测试。
3. 首先运行：
   python scripts\harness.py doctor --project PROJECT_ROOT --offline --json
   python scripts\harness.py status --project PROJECT_ROOT --json
   若项目尚未初始化，才运行：
   python scripts\harness.py init --project PROJECT_ROOT --competition COMPETITION --preset PRESET
4. 严格按 S0 -> M1 -> P1 -> P2 -> W1 -> W2 -> S1 -> F1 推进。每次先读
   status 的 first blocker，只修当前 blocker；不得通过手改 manifest、receipt、
   hash、DAG freshness、review verdict 或 Gate 状态来跳关。
5. 遇到缺失题面/数据、官方规则未确认、命令 FAIL/ERROR、pending human
   checkpoint、哈希漂移或证据不足，立即停止下游阶段并报告。不得编造数据、
   文献、运行结果、最优性、因果解释、获奖概率或测试通过状态。
6. 所有模型/代码结论必须走真实运行与 receipt；关键数字必须能从 paper claim
   反向追到 evidence_registry -> frozen_results -> receipt/code -> raw data。
   frozen artifact 如需改变，回到上游 Gate 生成新版本，不得原地改写。
7. W2 的 review 命令会先运行 deterministic QA；只有 QA 通过才 dispatch reviewer：
   - 同上下文自审：运行 harness review 获取 routing instructions，按
     review_report.schema.json 产出 L0 报告，再运行 --recheck；不得声称独立。
   - 真正 fresh review：只有在独立新上下文/模型 backend 已提供时，才运行
     python scripts\harness.py review --project PROJECT_ROOT --fresh
       --backend-cmd "<独立 reviewer 命令>" --json
   `--fresh` 绑定 bundle/cwd/receipt/report，但不是 OS 沙箱。submission 至少
   需要一个 current L1+ 或人工 L3 报告。open blocker/high/medium 未解决时
   不得通过 W2；论文改动后旧报告 stale，必须重新审查。
8. review evidence current 后，运行：
   python scripts\harness.py validate --project PROJECT_ROOT --strict
   然后再次运行 status。没有用户明确授权时，不 commit、不 push、不上传，
   也不执行 Final Freeze。

最终汇报必须包含：
- 当前 preset、stage、first blocker、各 Gate 的事实状态；
- 实际执行的完整命令及 exit code；
- 新增/更新 artifact 的绝对路径；
- receipt ID、selected run、frozen result、review report 与关键 hash；
- 已通过的检查、未通过/未运行的检查、人工待办和剩余风险；
- 明确区分“研究草稿完成”“W2 通过”“submission ready”“F1 已冻结”，
  不得把前一种状态宣传成后一种。
```

## 目录与三层模型

```text
project-root/
├── competition_profile.json   # 独立比赛规则合同（seed/unresolved/verified）
├── run_manifest.json           # v2 control plane：preset、roots、policy、人审/安全
├── artifact_dag.json           # artifact_id、依赖、生命周期、现场 freshness
├── run_index.json              # 可重建 projection：receipt IDs 与 selection
├── receipts/                   # 真实进程生成；不要手写
├── model_contract.json         # M1 后由项目产生
├── frozen_results.json         # P2 freeze 后由 producer 产生
└── paper/                      # W1/W2 论文项目，可与 Harness 分离
```

三层 ownership 固定如下：

| 层 | 真源 | 不能做什么 |
|---|---|---|
| execution fact | `command_receipt` | 不能用 manifest command/复制 exit code 代替 |
| projection | `run_index` | 不能复制 argv、变成执行真源或第二 digest registry |
| control decision | `run_manifest.control` | 不能写平铺 Gate PASS 或内嵌比赛 profile |

### 主链与 Gate

```text
S0 -> M1 -> P1 -> P2 -> W1 -> W2 -> S1 -> F1
```

每个 Gate 只推进一个决策。M1 是可编码且可证伪的模型/验证计划；P1 是
最小真实 smoke；P2 是 full + 独立重算 + freeze；W1 是 claim/evidence
计划；W2 是确定性、数学、写作、PDF/视觉检查加上真实执行的 review plane
（`harness review` 产出 `reports/review/` 下的 generated evidence；open
blocker/high/medium 阻断 W2，除非 medium 被有理由地接受；论文改动使旧
review stale）；S1 是当届规则和提交包；
F1 是不可覆盖交付绑定。详细最低 I/O 见
[Gate policy](references/workflow/gate_policy.md) 与
[Review Execution Design](docs/REVIEW_EXECUTION_DESIGN.md)。

## 三个 preset

| preset | 用途 | 哈希/检查姿态 |
|---|---|---|
| `sprint` | 快速探索与最小 smoke | 保留身份、安全、人审、独立验证和显式结果 freeze；避免全量哈希 |
| `research` | 默认正式研究链 | selected run、独立验证、完整 evidence chain、关键 I/O 选择性哈希 |
| `submission` | 当前比赛交付 | strict math/editorial、current template/bibliography、最终 source/PDF/package 不可变 |

override 只能是 allow-list capability adjustment，不能关闭 Contest Safety、
human checkpoint、independent validation、result freeze 或 submission
immutability，也不会形成第四种 preset。

## Profile 与比赛规则

`competition_profiles/*.yaml` 是维护者 seed，不是官方规则证据。`harness
init` 产生 standalone profile，明确为 `status: seed`；它没有 verified
official snapshot 时，S1/submission 必须阻塞。请附上真实官方快照、URL、
retrieval time、endpoint 和 page/AI/support/manual-check 语义，再走验证。

不要把上一届 profile、博客、聊天内容或本地保守策略冒充当届官方规则。
local policy 可以更严格，但必须和 official rule 分开记录。

## v1 migration

迁移是显式且非破坏性的：

```powershell
python scripts/harness.py migrate --project C:\work\legacy --json
```

默认输出 `C:\work\legacy\migration_v2\`，不覆盖源 manifest、旧
`frozen_results`、`submission_manifest` 或历史 receipts。读取报告中的
`migrated`、`inferred`、`unresolved`、`deprecated`、
`manual_review_required`；出现 unresolved/manual review 时不能宣传研究或
提交 ready。旧 command declaration 没有真实 receipt 时仍是 unresolved。

原始入口仍可用于 debug：

```powershell
python scripts/migrate_v1_to_v2.py --project C:\work\legacy --no-write --json
```

## Hash policy 与 generated evidence

只使用 SHA-256，并让每个 artifact 只有一个 digest owner：DAG/metadata、
command receipt、`frozen_results.results_sha256` 或最终 submission manifest。
Status/index 可以展示 projection，但不能成为第二真源。

哈希只证明字节身份，不证明 leakage、objective semantics、数学正确性、
统计单位、因果关系或图的结论。正确顺序是：

```text
semantic validation -> accept -> freeze -> hash binding
```

操作者不要编辑或伪造既有 generated evidence：receipt、index、DAG freshness、frozen
results、QA report、claim inventory、submission manifest 都必须重跑 producer。
改动 immutable artifact 时保留旧版本，生成新版本并让 downstream Gate
pending/fail。

## Migration/benchmark 边界

回归测试只说明代码路径、契约和负向防护仍工作；它不是 capability benchmark，
也不是数学模型已在真实赛题上泛化。当前 capability benchmark 计划保留在
[CAPABILITY_BENCHMARK_PLAN](docs/CAPABILITY_BENCHMARK_PLAN.md)，没有四类真实赛题
在 A0/A1/A2 同预算独立运行与 artifact 证据时，必须写“未完成”，不能写
“已验证”。

往届论文已经预留隔离区：国赛放入 `references/precedents/cumcm/`，
美赛放入 `references/precedents/mcm-icm/`，并在各自 `index.json` 登记来源、
哈希、权利说明和处理状态。赛前只把可迁移的方法选择、验证结构、写作组织和
Figure Contract 抽成 `references/precedents/pattern-cards/`；比赛时 Writer
默认只加载机制卡，不长期挂载论文原文。往届论文不自动进入当前
evidence registry、claim inventory 或 capability benchmark。完整规则见
[`precedent_policy.md`](references/research/precedent_policy.md)。

## Troubleshooting

| 现象 | 处理 |
|---|---|
| `status` 显示 M1 blocked | 先补真实 profile snapshot、model/evidence contract，再确认 M1 checkpoint；不要改 manifest.gates |
| profile 是 `seed`/`unresolved` | 它不是官方规则；绑定可核验快照后重新验证 |
| selected receipt 缺失或多个 | 按 control selection policy 重建 index；不要复制 `exit_code` |
| DAG stale/immutable drift | 检查实际文件与 producer receipt，生成新 version 并重跑下游 Gate |
| migrate 有 manual review | 阅读报告并由人解决 page limit、receipt、profile、artifact collision；不要手改报告为 pass |
| CLI 报缺依赖 | `python scripts/harness.py doctor --json`；安装 `requirements-dev.txt`，然后重跑原命令 |
| `validate` 失败 | 保存 checker 原始 stdout/stderr 和 exit code；先修 Gate 指向的 artifact，不要在论文中掩盖 |

## Debug appendix

正常入口不需要记住底层 14 个路径参数。只在定位问题时直接运行既有脚本：

```powershell
python scripts/doctor.py --offline --project-root C:\work\math-q1
python scripts/qa/check_gates.py --manifest run_manifest.json --project-root C:\work\math-q1 --gate M1 --strict
python scripts/qa/run_deterministic_qa.py --manifest run_manifest.json --project-root C:\work\math-q1 --output reports/deterministic_qa.json --force
python scripts/qa/check_artifact_dag.py --dag artifact_dag.json --project-root C:\work\math-q1 --strict
```

底层脚本是现有 checker/producer 的调试接口；CLI 不复制 Gate policy，也不
通过“看起来成功”覆盖它们的失败。更多合同、验证、写作、图、文献和提交
细节从[reference router](references/router.md)按需读取。

## Development checks

```powershell
python -m unittest discover -s tests -v
python -c "import json; from pathlib import Path; [json.loads(p.read_text(encoding='utf-8')) for p in Path('schemas').glob('*.schema.json')]"
python C:\Users\Administrator\.codex\skills\.system\skill-creator\scripts\quick_validate.py .
```

这些命令的结果必须如实报告；没有跑过的完整回归、真实 benchmark、PDF
视觉审查或比赛提交，不得写成已完成。
