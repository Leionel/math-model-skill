---
name: math-modeling-skill-sion
description: 面向 CUMCM、MCM/ICM 等数学建模竞赛的证据与合规驱动 Harness。用于赛题分析、当届规则快照、模型/数据/验证合同、代码 smoke/full 实验、结果冻结、真实文献核验、Evidence Registry、论文与 Figure Contract、AI 使用记录、一致性 QA、Reviewer、比赛专属提交检查和最终冻结；当用户要求完成、审查或交付数学建模竞赛项目、数模论文或建模代码时使用。普通数学题且不涉及建模竞赛交付链时不要使用。
---

# Math Modeling Evidence Harness

先确认当前比赛允许做什么，再保证模型、结果和论文可追溯。Contest Safety 持续包围整条链，不是开场后即可遗忘的一次检查。

```text
Competition Profile / Rule Snapshot
╔════════════════ Contest Safety / AI / Human Review ════════════════╗
║ Problem → Research + Candidate Comparison → M1 → Code → P1       ║
║ → Full + Validation → P2 → Result Freeze                          ║
║ → Evidence → Paper Plan / Figures → W1 → Writer → QA/Critic → W2  ║
╚═════════════════════════════════════════════════════════════════════╝
→ S1 Submission QA → F1 Immutable Submission Freeze
```

## 不可违反的规则

1. 分开记录 `official_rule` 与 `local_conservative_policy`；本地策略只能更严格。
2. `live_contest` 中拒绝被策略禁止的队外求助、当前赛题浏览/讨论、公开发布和外部写入。只有带人工确认的官方提交端点可作为上传例外。
3. M1 前先研究、后选型：对每个子问题记录中英关键词、大模型知识侦察、外部文献搜索、至少两个候选模型（或明确豁免）、机制/假设/数据需求/优缺点/淘汰条件比较和全文定位证据；再写公式、参数、实现步骤、输出、验证与失败模式。Coder 不得自行补关键数学口径。
4. 冻结完整 run（PASS/FAIL/ERROR）以保留反例；只有独立重算后逐项 PASS 的 `claimable=true` 结果可进入 Evidence Registry。关键数字必须进入 `frozen_results.json`，不能只留在聊天或 Markdown。
5. 只用一个增量 `evidence_registry.json`。文献 metadata、全文支持和出版状态分别核验；优秀论文不作为科学证据。
6. claim → evidence 只在 `paper_plan.json` 中维护；摘要结果必须说明选择原因；图数由 evidence coverage 决定，不设最低张数。
7. 保持一个 Paper Writer，按任务加载 micro-guidelines；不要拆 Abstract/Result/Figure 等 Agent。
8. W2 表示内容就绪；S1 表示当届提交包合规；F1 由不可覆盖的 `submission_manifest.json` 表示。
9. `integrity_mode=dev` 用于本地探索，`research` 用于正式研究链，`submission` 才强制所有最终引用哈希。不要在本地每一步机械制造哈希；但冻结结果和最终提交仍保持不可变。新项目默认 `research`，提交前升级为 `submission`。
10. `research/submission` 的论文构建必须有已验证 `template_contract`，并由源码检查证明实际 `\documentclass`、类文件、命令和引擎与合同一致；“模板文件在目录里”不等于用了模板。

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

读取 [Research-first Model Planning](references/research/model_planning.md)、[Artifact Contracts](references/contracts/artifact_contracts.md)、[Model Contract](references/contracts/model_contract.md)、[Validation Obligations](references/validation/validation_obligations.md) 和 [Literature Evidence](references/research/literature_evidence.md)。先校验 problem snapshot 与 data contract，再用大模型知识形成检索方向、通过网络/学术索引核验真实文献，比较候选模型并写出详细 implementation blueprint；选型结论成立后再建立 implementation map。

```powershell
python scripts/qa/check_modeling_plan.py `
  --model-contract model_contract.json `
  --evidence-registry evidence_registry.json `
  --strict
```

只在 schema 通过、研究—候选—证据—选型—实施链完整、`model_contract.status=ready`、M1 人工确认完成后通过 M1。P1 前不得先写实现再倒填计划。

## 2. P1/P2：编码、完整实验与结果冻结

- P1：一个最小 smoke 路径，检查输入、单位、范围、约束与输出结构。
- Full：输出 measurement snapshot，并用 `scripts/validation/evaluate_obligations.py` 运行模型合同声明的有限比较；不用 `{"ok": true}` 或人工 verdict 占位。
- P2：完整命令成功、独立重算的验证义务逐项 PASS、`claimable=true`、人工核验后才可通过；FAIL/ERROR run 仍应冻结以便审计，但不能作为论文 evidence。源文件与冻结文件必须不同。

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

建立 `paper_plan.json` 前读取 [Paper Plan](references/contracts/paper_plan.md)。先让人确认 central thesis、claim type、argument units 与 risk-weighted depth budget；每个子问题必须明确 formulation、result、validation、interpretation 和 display/waiver，达到 `readiness.stage=technical_draft` 后才编译正式 writer package。Writer 不得浏览 raw outputs 后自行添加研究事实。设计正式图时读取 [Figure Contract](references/contracts/figure_contract.md)、[Figure Design](references/visualization/figure_design.md) 与 [Plot Recipes](references/visualization/plot_recipes.md)。只有 registry 中 `verified` 的 evidence 能支撑 claim。

往届论文只在赛前按 [Outstanding Paper Quarantine](references/research/precedent_policy.md) 提炼机制卡；Writer 默认不加载全文。

## 4. W1/W2：单 Writer、确定性 QA 与语义审查

- 摘要：读取 [Abstract Guidelines](references/writing/abstract_guidelines.md)。
- 全文一致性：读取 [Consistency Sweep](references/writing/consistency_guidelines.md)。
- 语义审查：读取 [Semantic Critic Rubric](references/review/semantic_critic_rubric.md)。
- 定向返修：读取 [Bounded Revision](references/review/revision_policy.md)。

先运行 `scripts/qa/check_paper_readiness.py` 和 `scripts/claims/compile_writer_package.py`；只有显式 `--preview` 才允许生成不完整预览包，不能把它交给正式 Writer。Writer 完成后运行 `scripts/qa/check_writer_package.py --strict` 与 `scripts/claims/inventory_claims.py --strict`；前者约束只读 package，后者扫描最终正文里未登记数字、比较、因果、最优性和外部事实，不以“规避 AI 检测”为目标。编辑阶段读取 [Editorial Style](references/writing/editorial_style.md)。

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

CUMCM 工程先用 `scripts/latex/init_cumcm_project.py` 从锁定的本地 community snapshot 建立清洗后的电子版骨架；它不会把社区模板冒充官方模板。LaTeX 交付使用 `scripts/latex/safe_build.py --integrity-mode research --template-contract ...`，禁止 shell escape、在隔离副本构建并写入模板身份；随后运行 `scripts/pdf/check_pdf.py` 全页渲染，并按 [Visual Review](references/visualization/visual_review.md) 生成 review receipt。社区模板只作技术底座，当届官方 profile 仍是格式真源。

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

MCM/ICM 的 AI report 位于受限主体之后时，加 `--ai-report-pages` 并在 profile 中设 `max_pages_excludes_ai_report: true`。CUMCM 当前可核验基线使用支撑材料中的 AI 详情 PDF，不能推断成顶层独立上传文件；按 [Contest Safety](references/safety/contest_safety.md) 和 [Submission Freeze](references/submission/submission_freeze.md) 建立当届 profile。

把 S1 report 的路径和哈希写回 manifest，将 S1 设为 pass、状态设为 `submission_ready`，最后运行 `freeze_submission.py`。F1 文件禁止覆盖；最终文件、submission rules、AI Usage Registry 或 S1 checkpoint 任一变化，都必须重新做 S1/F1。

冻结后可随时复验最终文件未漂移：

```powershell
python scripts/qa/check_submission_manifest.py `
  --submission-manifest submission_manifest.json
```
