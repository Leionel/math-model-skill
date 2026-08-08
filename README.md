# Math Modeling Evidence Harness

一个面向数学建模竞赛（CUMCM、MCM/ICM 等）的证据驱动 Harness。它不替代建模者、程序员或论文作者，而是把“模型—代码—结果—证据—论文—审查”连接成可复核的交付链，降低关键数字漂移、结果被覆盖和论文超出证据边界的风险。

> 当前状态：P0 基础链路已实现并有回归测试。项目仍是可组合的本地 Harness，不是开箱即用的自动建模 Agent，也不承诺替用户选择模型或生成完整论文。

## 核心流程

```text
Problem Analysis
      |
      v
model_contract.json ---- M1 Modeling Gate
      |
      v
Coding ---- P1 Smoke Gate ---- Full Experiments ---- P2 Result Gate
                                                     |
                                                     v
                                             frozen_results.json
                                                     |
                                                     v
                                           evidence_registry.json
                                                     |
                                                     v
                                      paper_plan.json / Figure Contracts
                                                     |
                                                     v
                                           Paper Writer (one writer)
                                                     |
                                                     v
                           Deterministic QA ---- Semantic Critic
                                                     |
                              optional Blind Reviewer(s) ---- W2 Release
```

核心原则是单向追溯：

```text
paper claim -> evidence -> frozen result -> code/input artifact -> raw data
```

关键数字不应只存在于 LLM 上下文或自由文本报告中。

## 主要能力

- **Model Contract**：在 M1 前明确问题、变量、单位、约束、输入输出、验证标准和风险。
- **Result Freeze**：把经过 full experiment 的结果冻结为不可原地覆盖的 `frozen_results.json`，记录单位、适用边界、精度、代码/输入/验证快照。
- **Evidence Registry**：从冻结结果生成可追溯 evidence，避免论文先写数字、事后补证据。
- **Paper Plan**：在 W1 阶段承载 claim-evidence map、章节顺序、摘要候选结果、图表需求和术语约束。
- **Figure Contract**：吸收 [nature-skills 的 claim-first figure 机制](https://github.com/Yuan1z0825/nature-skills)，先写清图要证明什么、使用哪条证据、为什么不可删，再决定图的形式和数量；不硬编码“至少几张图”。
- **Deterministic QA**：程序化检查 contract、数字/单位/术语一致性、摘要 Gate、引用和图表引用等可机械验证内容。
- **Semantic Review**：把语义支持、边界外推、结论风险交给 Critic；Blind Reviewer 只在最终投稿或冲奖模式按需启用。

## 目录

```text
SKILL.md                         Codex skill 入口与执行规则
agents/openai.yaml               Agent 元数据
schemas/                         长期 artifact 的 JSON Schema
scripts/freeze_results.py        结果冻结（禁止覆盖已有输出）
scripts/register_evidence.py     从冻结结果生成 Evidence Registry
scripts/qa/                      contract、consistency、citation、Gate、汇总 QA
references/contracts/             artifact 与 Figure Contract 说明
references/writing/               摘要、全文一致性等按需加载的写作规则
references/visualization/         图设计 reference
references/review/                Critic rubric 与有界修订策略
references/workflow/              Gate 与失败回退规则
docs/HARNESS_INTEGRATION_ANALYSIS.md
                                 外部开源机制的架构审计与整合方案
tests/test_p0_harness.py          P0 回归测试和负例
```

## 快速开始

默认使用 JSON，因此不依赖 PyYAML。先在项目目录准备模型合同、运行输入、代码和验证日志，再冻结结果：

```powershell
python scripts/freeze_results.py `
  --source results/raw_results.json `
  --output results/frozen_results.json `
  --run-id run-001 `
  --command "python code/run_all.py --seed 42" `
  --seed 42 `
  --input data/input.csv `
  --code code/run_all.py `
  --validation reports/full_validation.json
```

然后注册证据：

```powershell
python scripts/register_evidence.py `
  --frozen-results results/frozen_results.json `
  --output evidence_registry.json
```

`paper_plan.json` 只能引用已验证的 evidence 和冻结结果。摘要中的关键数字也必须来自冻结结果；不要在摘要、正文或结论中手写一个未登记的新数字。

## QA 与 Gate

单项检查可独立运行，也可以用统一入口汇总成带输入哈希的报告：

```powershell
python scripts/qa/validate_contracts.py `
  --model-contract model_contract.json `
  --run-manifest run_manifest.json `
  --frozen-results results/frozen_results.json `
  --evidence-registry evidence_registry.json `
  --paper-plan paper_plan.json `
  --strict

python scripts/qa/run_deterministic_qa.py `
  --model-contract model_contract.json `
  --run-manifest run_manifest.json `
  --frozen-results results/frozen_results.json `
  --evidence-registry evidence_registry.json `
  --paper-plan paper_plan.json `
  --abstract paper/abstract.txt `
  --paper paper/main.tex `
  --conclusion paper/conclusion.txt `
  --output reports/deterministic_qa.json

python scripts/qa/check_gates.py --manifest run_manifest.json --strict
```

正式释放前应确认 M1、P1、P2、W1、W2 的状态和各自 evidence 均为当前快照。输入、代码、结果、论文或 Reviewer 报告发生实质变化后，受影响 Gate 应回到 `pending`，而不是手工保留旧的 `pass`。

运行回归测试：

```powershell
python -m unittest discover -s tests -v
```

### 图像 QA 的当前边界

P0 已实现图表合同和轻量确定性检查：图必须绑定 claim/evidence，登记数据或源文件，声明 panel、统计定义、正文位置和 caption；`check_consistency.py` 会检查图表引用、数据 artifact 和相关证据关系。`check_citations.py` 可检查 LaTeX 图片文件引用。

Nature Figure 中更重的三层检查——源码预检、导出 PDF 字体/裁切检查、按论文实际尺寸逐 panel 渲染审查——已记录为 P1 方向，尚未伪装成当前自动能力。最终图仍需要在目标论文尺寸下人工阅读；自动脚本不能替代可读性和论证判断。

## Reviewer 模式

| 模式 | 组成 | 适用场景 |
|---|---|---|
| `sprint` | Deterministic QA + 1 个 Semantic Critic | 普通比赛和快速迭代 |
| `final_submission` | 上述检查 + 1 个 Blind Reviewer | 最终提交前 |
| `award_max` | 冻结成稿后再启用 3 个相互隔离的 Blind Reviewer | 明确冲奖、且仍有返修时间 |

修订默认最多两轮，并且只改动 issue 指向的 artifact；问题没有减少时应停止并记录 decision memo，而不是无限润色。

## 设计边界

- 结果的权威来源是 `frozen_results.json`，不是另一个手工维护的 Markdown 结果报告。
- 长期保存少量高价值 contract；阶段性自由文本、临时推理和重复摘要不应继续膨胀成独立 artifact。
- Writer 保持为一个 Agent，摘要、结果分析、图设计、一致性等内容通过 `references/` 按需加载。
- 图的数量由 claim/evidence coverage 决定，而不是固定张数。
- 程序能可靠验证的内容交给脚本；模型合理性、外推边界和论证强度交给 Semantic Critic。

## 进一步阅读

- [Harness Integration Analysis](docs/HARNESS_INTEGRATION_ANALYSIS.md)：逐仓库分析可抽取机制、重复与冲突、P0/P1/P2 改造优先级。
- [Artifact Contracts](references/contracts/artifact_contracts.md)：长期 artifact、单向依赖和结果字段约定。
- [Gate Policy](references/workflow/gate_policy.md)：Gate 前置关系、失败回退和 Reviewer 强度。
- [Figure Contract](references/contracts/figure_contract.md)：claim-first 的图表契约。
