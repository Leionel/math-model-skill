---
name: math-modeling-skill-sion
description: 面向 CUMCM、MCM/ICM 等数学建模竞赛的证据与合规驱动 Harness。用于赛题分析、当届规则快照、模型/数据/验证合同、代码 smoke/full 实验、结果冻结、真实文献核验、Evidence Registry、论文与 Figure Contract、AI 使用记录、一致性 QA、Reviewer、比赛专属提交检查和最终冻结；当用户要求完成、审查或交付数学建模竞赛项目、数模论文或建模代码时使用。普通数学题且不涉及建模竞赛交付链时不要使用。
---

# Math Modeling Evidence Harness

先确认当前比赛允许做什么，再保证模型、结果和论文可追溯。Contest Safety 持续包围整条链，不是开场后即可遗忘的一次检查。

```text
Competition Profile / Rule Snapshot
╔════════════════ Contest Safety / AI / Human Review ════════════════╗
║ Problem → M1 → Code → P1 → Full + Validation → P2 → Result Freeze ║
║ → Evidence → Paper Plan / Figures → W1 → Writer → QA/Critic → W2  ║
╚═════════════════════════════════════════════════════════════════════╝
→ S1 Submission QA → F1 Immutable Submission Freeze
```

## 不可违反的规则

1. 分开记录 `official_rule` 与 `local_conservative_policy`；本地策略只能更严格。
2. `live_contest` 中拒绝被策略禁止的队外求助、当前赛题浏览/讨论、公开发布和外部写入。只有带人工确认的官方提交端点可作为上传例外。
3. M1 前声明数据来源、许可/条款、变换、质量检查和题型触发的验证义务；Coder 不得自行补关键数学口径。
4. 只冻结逐项通过 validation obligations 的结果。关键数字必须进入 `frozen_results.json`，不能只留在聊天或 Markdown。
5. 只用一个增量 `evidence_registry.json`。文献 metadata、全文支持和出版状态分别核验；优秀论文不作为科学证据。
6. claim → evidence 只在 `paper_plan.json` 中维护；图数由 evidence coverage 决定，不设最低张数。
7. 保持一个 Paper Writer，按任务加载 micro-guidelines；不要拆 Abstract/Result/Figure 等 Agent。
8. W2 表示内容就绪；S1 表示当届提交包合规；F1 由不可覆盖的 `submission_manifest.json` 表示。
9. 输入、规则、代码、结果、论文或报告哈希变化后，将受影响 Gate 退回 `pending` 并重检。

## 0. 固定比赛规则与安全边界

读取 [Contest Safety](references/safety/contest_safety.md)。从官方页面保存当届规则快照并登记 SHA-256；规则不明时使用 `ask`/`competition_specific`，不要引用往届规则替代。

先运行：

```powershell
python scripts/qa/check_contest_safety.py `
  --manifest run_manifest.json `
  --strict
```

影响交付物的 AI 使用登记到 `run_manifest.ai_usage[]`，关键交互放独立文件并记录哈希。M1、P2、W2、S1 必须有绑定当前 artifact 的人工 checkpoint。

## 1. M1：模型、数据与验证合同

读取 [Artifact Contracts](references/contracts/artifact_contracts.md)、[Model Contract](references/contracts/model_contract.md) 和 [Validation Obligations](references/validation/validation_obligations.md)。文献用于假设、方法或外部事实时，再读取 [Literature Evidence](references/research/literature_evidence.md)。

只在 schema 通过、`model_contract.status=ready`、M1 人工确认完成后通过 M1。

## 2. P1/P2：编码、完整实验与结果冻结

- P1：一个最小 smoke 路径，检查输入、单位、范围、约束与输出结构。
- Full：运行模型合同声明的所有必要验证，不用 `{"ok": true}` 占位。
- P2：完整命令成功、验证义务逐项 pass、人工核验后冻结；源文件与冻结文件必须不同。

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

## 3. Evidence、论文策略与图表

文献证据可在 M1 前用 seed 初始化；P2 后把冻结结果合并到同一 registry：

```powershell
python scripts/register_evidence.py `
  --seed evidence_registry.seed.json `
  --frozen-results results/frozen_results.json `
  --output evidence_registry.json
```

建立 `paper_plan.json` 前读取 [Paper Plan](references/contracts/paper_plan.md)。设计正式图时读取 [Figure Contract](references/contracts/figure_contract.md) 与 [Figure Design](references/visualization/figure_design.md)。只有 registry 中 `verified` 的 evidence 能支撑 claim。

往届论文只在赛前按 [Outstanding Paper Quarantine](references/research/precedent_policy.md) 提炼机制卡；Writer 默认不加载全文。

## 4. W1/W2：单 Writer、确定性 QA 与语义审查

- 摘要：读取 [Abstract Guidelines](references/writing/abstract_guidelines.md)。
- 全文一致性：读取 [Consistency Sweep](references/writing/consistency_guidelines.md)。
- 语义审查：读取 [Semantic Critic Rubric](references/review/semantic_critic_rubric.md)。
- 定向返修：读取 [Bounded Revision](references/review/revision_policy.md)。

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

默认 `sprint` 只用确定性 QA + 一个 Semantic Critic；最终成稿可加一个 Blind Reviewer；仅冲奖且有返修余量时使用三席。最多两轮 targeted revision。

## 5. S1/F1：比赛专属提交与最终冻结

读取 [Submission Freeze](references/submission/submission_freeze.md)。先由人完成 profile 中的 `required_manual_checks`，再运行 S1：

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

把 S1 report 的路径和哈希写回 manifest，将 S1 设为 pass、状态设为 `submission_ready`，最后运行 `freeze_submission.py`。F1 文件禁止覆盖；任何最终文件变化都必须重新做 S1/F1。
