# Math Modeling Evidence Harness

面向 CUMCM、MCM/ICM 等数学建模竞赛的本地 Skill/Harness。它把“当届规则—模型—代码—验证—结果—证据—论文—提交”连接成可复核链路，重点降低四类风险：比赛违规、验证占位、关键数字漂移、最终文件与规则不符。

> 当前状态：P0 链路已实现并有回归测试。它是可组合 Harness，不是全自动解题 Agent；模型选择、结论负责和最终提交仍由参赛队完成。

## 架构

```text
Competition Profile / Official Rule Snapshot
╔══════════════ Contest Safety + AI Registry + Human Review ══════════════╗
║ Problem → M1 → Coding → P1 → Full/Validation → P2 → Results Freeze     ║
║ → Evidence Registry → Paper Plan/Figures → W1 → Writer → QA/Critic → W2║
╚═════════════════════════════════════════════════════════════════════════╝
→ S1 Competition-specific Submission QA
→ F1 Immutable submission_manifest.json
```

两条追溯链并行存在：

```text
paper claim → evidence → frozen result → code/input → raw data
contest action → effective policy → official rule snapshot
```

## P0 能力

- **Contest Safety**：固定当届官方规则快照；区分官方规则与本地保守策略；检查 live contest 的队外求助、赛题讨论、公开发布、外部写入与 AI 使用。
- **AI Usage + Human Checkpoints**：在 `run_manifest` 中登记影响交付物的 AI 使用；M1/P2/W2/S1 绑定当前 artifact 哈希做人工确认。
- **Model/Data Contract**：记录题意、变量、单位、约束、数据来源/许可/变换/质量和题型触发的验证义务。
- **Validation Obligations**：P2 不再只看验证文件是否存在；`{"ok": true}` 没有逐项 obligation 回执时无法冻结。
- **Result Freeze**：禁止覆盖已有冻结文件，绑定模型合同、输入、代码、验证报告与结果哈希。
- **Evidence Registry**：一个可增量账本同时承载文献与结果证据；文献身份、全文支持和出版状态分开核验。
- **Paper Plan / Figure Contract**：requirement → claim → evidence 驱动章节与图表；不硬编码图数。
- **Deterministic QA + Semantic Critic**：机械一致性交给脚本，边界外推和论证强度交给 Critic。
- **Submission Freeze**：W2 与 S1 分离，最终由不可覆盖的 `submission_manifest.json` 固定比赛 profile、规则、文件、截止时间和包哈希。

## 核心 artifact

解题阶段只维护五个核心 JSON；最终提交再增加一个：

| 文件 | 作用 |
|---|---|
| `model_contract.json` | M1 数学、数据与验证合同 |
| `run_manifest.json` | 可变控制面：规则、安全、AI、人审、命令、Gate、Reviewer |
| `frozen_results.json` | P2 可信结果与上游快照 |
| `evidence_registry.json` | 唯一增量证据账本 |
| `paper_plan.json` | W1 claim-evidence、章节、摘要和图表计划 |
| `submission_manifest.json` | F1 最终不可变提交快照 |

临时推理、阶段摘要和重复结果报告不需要长期保存。

## 目录

```text
SKILL.md                         Skill 入口与阶段路由
agents/openai.yaml               UI 元数据
schemas/                         6 个 JSON Schema
scripts/freeze_results.py        逐项验证后冻结结果
scripts/register_evidence.py     初始化/合并唯一 Evidence Registry
scripts/freeze_submission.py     生成 F1 不可变提交 manifest
scripts/qa/                      Safety、合同、一致性、引用、Gate、S1 QA
references/safety/               规则快照、网络/外写、AI 与人审政策
references/validation/           题型触发的验证义务
references/research/             文献真实性与优秀论文隔离规则
references/precedents/cumcm/     国赛优秀论文本地预留区 + index
references/precedents/mcm-icm/   美赛优秀论文本地预留区 + index
references/precedents/pattern-cards/
                                  可提交到 Git 的机制卡
references/contracts/            核心 artifact 与 Figure Contract
references/writing/              Writer 按需加载的摘要/一致性规则
references/visualization/        evidence-driven 科研绘图规则
references/review/               Critic 与有界修订
references/submission/           S1/F1 规则
docs/HARNESS_INTEGRATION_ANALYSIS.md
                                  开源机制审计与整合决策
tests/test_p0_harness.py          P0 正/负例回归测试
```

## 快速开始

### 1. 建立规则快照与运行清单

赛前从赛事官网保存当届规则、格式规范、AI 政策和提交说明，登记 URL、抓取时间和 SHA-256。不要把往届规则写成当前规则。

```powershell
python scripts/qa/check_contest_safety.py `
  --manifest run_manifest.json `
  --strict
```

### 2. 完整验证后冻结结果

验证报告必须包含与 `model_contract.models[].validation_obligations[]` 一一对应的通过记录及 `observed` 证据。

```powershell
python scripts/freeze_results.py `
  --source results/raw_results.json `
  --output results/frozen_results.json `
  --run-id run-001 `
  --model-contract model_contract.json `
  --command "python code/run_all.py --seed 42" `
  --seed 42 `
  --input data/input.csv `
  --code code/run_all.py `
  --validation reports/full_validation.json
```

### 3. 合并证据

M1 前可以先用 seed 建立文献 evidence；P2 后合并冻结结果。输出已存在时应写新文件，确认后再使用 `--force` 替换。

```powershell
python scripts/register_evidence.py `
  --seed evidence_registry.seed.json `
  --frozen-results results/frozen_results.json `
  --output evidence_registry.json
```

`type=citation` 且要标为 verified 时，必须满足：metadata 已核验、读过全文并记录 locator、检查过撤稿/勘误状态。Crossref/OpenAlex metadata 本身不能证明 claim。

### 4. W2 确定性 QA

```powershell
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

LaTeX 项目可再传 `--tex`、`--bib` 和 `--check-figures`。

### 5. S1/F1

S1 前由人完成 Competition Profile 中列出的匿名性、最终渲染、页数、附件内容等人工检查。

```powershell
python scripts/qa/check_submission.py `
  --run-manifest run_manifest.json `
  --paper submission/solution.pdf `
  --paper-pages 25 `
  --page-count-method pdfinfo `
  --support submission/support.zip `
  --ai-disclosure submission/AI_use_report.pdf `
  --output reports/submission_qa.json
```

将 S1 report 登记回 manifest 并把状态设为 `submission_ready` 后：

```powershell
python scripts/freeze_submission.py `
  --run-manifest run_manifest.json `
  --s1-report reports/submission_qa.json `
  --paper submission/solution.pdf `
  --support submission/support.zip `
  --ai-disclosure submission/AI_use_report.pdf `
  --deadline "2026-09-01T20:00:00+08:00" `
  --timezone "Asia/Hong_Kong" `
  --output submission_manifest.json
```

F1 文件不可覆盖。最终文件发生变化时，重新执行 S1/F1。

冻结后可随时复验最终文件未漂移：

```powershell
python scripts/qa/check_submission_manifest.py `
  --submission-manifest submission_manifest.json
```

## 优秀论文预留区

国赛与美赛目录已经预留，但论文文件不会提交到 Git：

- `references/precedents/cumcm/`
- `references/precedents/mcm-icm/`

把合法获得的论文放到本地，并在各自 `index.json` 记录赛事、年份、题号、奖项、官方来源、哈希和用途。先提炼成 `pattern-cards/` 机制卡，再供 Writer 赛前参考；不要复制原文，也不要把优秀论文当成科学 evidence。详见 [Outstanding Paper Quarantine](references/research/precedent_policy.md)。

## Figure / Reviewer 边界

Figure Contract 吸收了 nature-skills 的 claim-first、panel map、统计定义和最终尺寸人工检查思想。P0 已检查 claim/evidence/data artifact/引用关系；源码预检、导出 PDF 字体/裁切和逐 panel 渲染审查仍是 P1，不冒充已实现能力。

Reviewer 默认不堆 Agent：

| 模式 | 组成 |
|---|---|
| `sprint` | Deterministic QA + 1 Semantic Critic |
| `final_submission` | 上述检查 + 1 Blind Reviewer |
| `award_max` | 冻结成稿后按需使用 3 个隔离盲席 |

修订最多两轮，只处理稳定 issue ID 指向的问题；blocker/high 不下降时停止并写 decision memo。

## 验证

```powershell
python -m unittest discover -s tests -v
```

当前测试覆盖：规则/安全策略、人工 checkpoint、验证占位拒绝、文献全文核验、摘要未登记数字、S1 人工检查、最终包冻结和不可覆盖行为。

## 进一步阅读

- [Harness Integration Analysis](docs/HARNESS_INTEGRATION_ANALYSIS.md)
- [Artifact Contracts](references/contracts/artifact_contracts.md)
- [Contest Safety](references/safety/contest_safety.md)
- [Validation Obligations](references/validation/validation_obligations.md)
- [Literature Evidence](references/research/literature_evidence.md)
- [Figure Contract](references/contracts/figure_contract.md)
- [Submission Freeze](references/submission/submission_freeze.md)
