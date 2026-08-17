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

# W2 入口复用既有 check_gates -> run_deterministic_qa，不复制 QA 规则
python scripts/harness.py validate --project C:\work\math-q1 --strict

# 结果与提交冻结仍由既有 producer 负责
python scripts/harness.py freeze --project C:\work\math-q1 --kind results `
  --source results.json --output frozen_results.json --run-id <run-id> `
  --model-contract model_contract.json --code model.py --validation validation.json

python scripts/harness.py profile --project C:\work\math-q1 --json
python scripts/harness.py doctor --project C:\work\math-q1 --json
```

对 Agent/CI 使用 `--json`；无 `--json` 时 `status/profile/doctor/init` 给出
人类摘要，底层 checker 仍透明输出机器报告。命令返回码是事实状态，不要
只看最后一行文字。

`check/validate --profile` 是兼容性断言：它只能与 manifest 已绑定的 preset
一致，不能在检查时临时覆盖 Gate policy。正常情况下可省略该参数。

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
计划；W2 是确定性、数学、写作、PDF/视觉检查；S1 是当届规则和提交包；
F1 是不可覆盖交付绑定。详细最低 I/O 见
[Gate policy](references/workflow/gate_policy.md)。

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

不要手写或修改 generated evidence：receipt、index、DAG freshness、frozen
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
