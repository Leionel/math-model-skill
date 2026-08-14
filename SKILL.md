---
name: math-modeling-skill-sion
description: 面向 CUMCM、MCM/ICM 等数学建模竞赛的证据与合规驱动 Harness。用于赛题分析、当届规则快照、模型/数据/验证合同、代码 smoke/full 实验、结果冻结、真实文献核验、Evidence Registry、论文与 Figure Contract、AI 使用记录、一致性 QA、Reviewer、比赛专属提交检查和最终冻结；当用户要求完成、审查或交付数学建模竞赛项目、数模论文或建模代码时使用。普通数学题且不涉及建模竞赛交付链时不要使用。
---

# Math Modeling Evidence Harness

先确认当前比赛允许做什么，再保证模型、结果和论文可追溯。Contest Safety 持续包围整条链，不是开场后即可遗忘的一次检查。

```mermaid
flowchart LR
    A["题目与当届规则"] --> B["研究与候选比较"]
    B --> M1["M1 模型/数据/验证合同"]
    M1 --> P1["P1 Smoke"]
    P1 --> P2["P2 Full + 独立验证"]
    P2 --> F["结果冻结"]
    F --> W1["W1 Evidence + Paper Plan"]
    W1 --> W2["W2 Writer + 数学/逻辑 QA"]
    W2 --> S1["S1 提交包 QA"]
    S1 --> F1["F1 不可变提交冻结"]
    P2 -. "失败/不可主张" .-> P1
    W2 -. "数学/证据问题" .-> W1
```

## 执行协议：每一轮只推进一个 Gate

先判断当前项目属于 `dev`、`research` 还是 `submission`，再按下面顺序执行。没有前一 Gate 的通过证据，不得跳到下一阶段；发现问题时退回产生问题的 artifact，而不是在论文里用措辞掩盖。

| 阶段 | 进入条件 | 必做动作 | 最低产出 | 未通过时退回 |
|---|---|---|---|---|
| S0/EDA | 赛题附件已导入 | 解析比赛画像 (`profile_engine.py`)，运行自动化数据体检 (`auto_eda.py`) 并生成数据契约 | `active_profile.json`、`data_contract.json` | Data Ingestion |
| M1 | 规则 profile 和数据已锁定 | 风险驱动拆解题意、文献检索与候选模型比较（主模型+Baseline+必要Alternative）；记录假设分叉、参数 provenance、公式、实现与验证义务 | `model_contract.json`、`evidence_registry.json`、M1 checkpoint | Research / Model Contract |
| P1 | M1 通过 | 增量原型编码，使用 `scripts/reflexion/runner.py` 跑最小 smoke；失败先分类，只有显式返修回调才进入有界返修（最多3轮，严禁放松约束） | 1 个成功 smoke receipt | Coding / Model Contract |
| P2 | P1 通过 | Full run、独立求值器重算每项 obligation、敏感性/OOS/失败证据按需生成，再冻结结果 | `frozen_results.json`，`PASS + claimable=true` 才可写论文 | Coding / Validation |
| W1 | P2 有可主张结果 | 建立全局论文蓝图与统一符号/数值宏 (`results.tex`)；安排每题 CEEL 论证结构、数据证据图和可编辑矢量流程/框架图 | `paper_plan.json`、`results.tex`、diagram spec、readiness、可编译 writer package | Evidence / Results / Paper Plan |
| W2 | W1 readiness 通过 | 渐进式分节生成并逐题局部冻结；运行数学引用、推导图、数字、因果强度、逻辑顺序和 PDF QA；执行独立人工数学复核与单一语义 Critic | 首稿、`deterministic_qa.json`、critic、build/visual receipt | Writer / Model / Validation |
| S1/F1 | W2 内容通过且 profile 完整 | 自动代码与 PDF 匿名脱敏、AI 使用报告生成、支撑包整理与当届提交检查；最后生成不可覆盖 manifest | S1 report、`submission_manifest.json` | Submission Builder → W2 |

### W2 的数学—写作最低合同

每个核心论证单元在 `paper_plan.argument_units[]` 中声明 `model_ids`、`equation_ids`、`constraint_ids`、`validation_obligation_ids`、`result_ids`/`derived_result_ids` 和 `math_locators`。正式首稿运行：

```powershell
python scripts/qa/check_derivation_integrity.py `
  --model-contract model_contract.json `
  --require-metadata `
  --strict

python scripts/qa/check_math_writing.py `
  --model-contract model_contract.json `
  --paper-plan paper_plan.json `
  --frozen-results results/frozen_results.json `
  --writer-package reports/writer_package.json `
  --draft paper/main.tex `
  --require-coverage `
  --strict
```

前一个脚本检查 Equation Contract 和 derivation DAG；后一个脚本检查数学引用、结果绑定和写作顺序。它们不能自动证明代数等价性，所以增强 W2 的人工 checkpoint 还必须包含 `math_formula_correctness`、`equation_constraint_mapping`、`argument_logic_order` 和 `units_and_boundary_consistency`。

完整状态表和后续 M0–M4 路线见 [Math Harness Implementation Status](docs/MATH_HARNESS_IMPLEMENTATION_STATUS.md)。

## 不可违反的规则

1. 分开记录 `official_rule` 与 `local_conservative_policy`；本地策略只能更严格。
2. `live_contest` 中拒绝被策略禁止的队外求助、当前赛题浏览/讨论、公开发布和外部写入。只有带人工确认的官方提交端点可作为上传例外。
3. M1 前先研究、后选型：对每个子问题记录中英关键词、大模型知识侦察、外部文献搜索、至少两个候选模型（或明确豁免）、机制/假设/数据需求/优缺点/淘汰条件比较和全文定位证据；再写公式、参数、实现步骤、输出、验证与失败模式。Coder 不得自行补关键数学口径。题意歧义必须走 `assumption_forks`（至少两种解释、判别检查、选定理由或 unresolved_risk）；参数来源必须 typed provenance（GIVEN/DERIVED/ESTIMATED/CALIBRATED/ASSUMED/POLICY）；风险度量模型必须声明 `identity` 与 `risk_semantics`，相关输入必须声明 `correlation_spec`。
4. 冻结完整 run（PASS/FAIL/ERROR）以保留反例；只有独立重算后逐项 PASS 的 `claimable=true` 结果可进入 Evidence Registry。关键数字必须进入 `frozen_results.json`，不能只留在聊天或 Markdown。
5. 只用一个增量 `evidence_registry.json`。文献 metadata、全文支持和出版状态分别核验；优秀论文不作为科学证据。
6. claim → evidence 只在 `paper_plan.json` 中维护；摘要结果必须说明选择原因；图数由 evidence coverage 决定，不设最低张数。
7. 保持一个 Paper Writer，按任务加载 micro-guidelines；不要拆 Abstract/Result/Figure 等 Agent。
8. W2 表示内容就绪；S1 表示当届提交包合规；F1 由不可覆盖的 `submission_manifest.json` 表示。
9. `integrity_mode=dev` 用于本地探索，`research` 用于正式研究链，`submission` 才强制所有最终引用哈希。不要在本地每一步机械制造哈希；新加入的敏感性、OOS、失败诊断 artifact 在 dev/research 可只登记路径，冻结结果、OOS 场景身份和最终提交仍保持必要的不可变/独立性证据。新项目默认 `research`，提交前升级为 `submission`。哈希是提交完整性约束，不是数学正确性检查，也不是本地探索的工作量指标。
10. `research/submission` 的论文构建必须有已验证 `template_contract`，并由源码检查证明实际 `\documentclass`、类文件、命令和引擎与合同一致；“模板文件在目录里”不等于用了模板。

## 0. 比赛画像与前置 Auto-EDA

首先根据参加的比赛解析 Competition Profile 并运行自动化数据探索：

```powershell
# 1. 解析比赛画像（如 cumcm 或 mcm_icm）
python scripts/profiles/profile_engine.py `
  --profile cumcm `
  --validate `
  --output profiles/active_profile.json

# 2. 运行自动化数据探索 (Auto-EDA) 并生成数据画像契约
python scripts/eda/auto_eda.py data/ `
  --target target_column `
  --split-key entity_id `
  --output-md reports/eda_summary.md

python scripts/eda/profile_generator.py data/input.csv `
  --target target_column `
  --split-key entity_id `
  --output data_contract.json
```

如果尚未明确 target、分组键或时间边界，省略相应参数；生成的 `leakage_policy.status` 必须保持 `not_run`，不能把自动画像当作泄漏通过。`profile_generator.py` 仍会保留数据源 SHA-256 作为输入身份，但本地探索不要求为每个中间 receipt 机械生成哈希。

读取 [Contest Safety](references/safety/contest_safety.md)。从官方页面保存当届规则快照并登记 SHA-256；规则不明时使用 `ask`/`competition_specific`，不要引用往届规则替代。

运行安全与合规检查：

```powershell
python scripts/qa/check_contest_safety.py `
  --manifest run_manifest.json `
  --strict
```

影响交付物的 AI 使用登记到 `run_manifest.ai_usage[]`；`dev/research` 可登记交互记录路径、用途和人工核验，不要求为每条本地交互生成哈希，`submission` 或比赛规则明确要求时再绑定哈希。M1、P2、W2、S1 必须有绑定当前 artifact 的人工 checkpoint。

## 1. M1：模型、数据与验证合同

读取 [Research-first Model Planning](references/research/model_planning.md)、[Artifact Contracts](references/contracts/artifact_contracts.md)、[Model Contract](references/contracts/model_contract.md)、[Validation Obligations](references/validation/validation_obligations.md) 和 [Literature Evidence](references/research/literature_evidence.md)。先校验 problem snapshot 与 data contract，再用大模型知识形成检索方向、通过网络/学术索引核验真实文献，比较候选模型并写出详细 implementation blueprint；选型结论成立后再建立 implementation map。

```powershell
python scripts/qa/check_modeling_plan.py `
  --model-contract model_contract.json `
  --evidence-registry evidence_registry.json `
  --strict
```

在 `research/submission` 模式追加 `--formal --strict`；`check_gates.py` 对 M1 会自动这样调用。该模式会要求外部搜索绑定已核验 evidence、搜索确实返回候选、决策理由点名选中候选，并在已声明增强数学元数据时把 Equation Contract/推导完整性作为结构性阻断；它仍不是“模型语义正确”的自动证明，最终仍需 M1 人审。

`check_modeling_plan.py` 内置有限数学语义检查（CVaR 方向、PSD/Cholesky、identity 等），并要求每个模型输入都有 typed parameter provenance；`sensitivity` / `out_of_sample` 义务必须绑定对应实验 artifact。完整规则见 [Model Contract](references/contracts/model_contract.md) 和 [Experiment Artifacts](references/validation/experiment_artifacts.md)。有论文文本后再运行 `scripts/qa/check_math_semantics.py` 扫描 identity 漂移、全局最优措辞和单位/量级漂移，细则见 [Math Semantic Checks](references/validation/math_semantic_checks.md)。

只在 schema 通过、研究—候选—证据—选型—实施链完整、`model_contract.status=ready`、M1 人工确认完成后通过 M1。P1 前不得先写实现再倒填计划。

## 2. P1/P2：增量编码、有界诊断/返修与结果冻结

- P1：增量原型编码，使用 `scripts/reflexion/runner.py` 跑最小 smoke；可调用 `scripts/scaffold/`（LP/MILP、ODE、GA/PSO、Evaluation Metrics）标准脚手架。Runner 默认只诊断；需要编排返修时由上层显式提供 `run_bounded_reflexion(..., repair_callback=...)`，最多 3 轮，严禁擅自放松约束。
- Full：输出 measurement snapshot，并用 `scripts/validation/evaluate_obligations.py` 运行模型合同声明的有限比较；不用 `{"ok": true}` 或人工 verdict 占位。
- P2：完整命令成功、独立重算的验证义务逐项 PASS、`claimable=true`、人工核验后才可通过；FAIL/ERROR run 仍应冻结以便审计，但不能作为论文 evidence。源文件与冻结文件必须不同。
- 若合同声明 `sensitivity` 或 `out_of_sample`，P2 同时要求 `sensitivity_experiment` / `oos_artifact` 通过语义检查；FAIL/ERROR run 需编译 `failure_evidence`，它只支持 diagnostic claim，不能进入 Evidence Registry。

增量有界执行与结果冻结命令：

```powershell
# 1. 增量执行并捕获诊断；失败后必须由人或受控编排器提供返修
python scripts/reflexion/runner.py code/subproblem_1.py `
  --timeout 120 `
  --round 1 `
  --max-rounds 3 `
  --output reports/execution_receipt.json

# 2. 独立验证并冻结结果
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

论文需要的增长率、相对下降、比例、百分点、均值/标准差等二次指标一律由程序从冻结结果计算，Writer 只能引用 `derived_result_id`，不得自己算：

```powershell
python scripts/derive_results.py `
  --frozen-results results/frozen_results.json `
  --spec derived_spec.json `
  --output results/derived_results.json
```

派生结果默认按 `research` 模式只登记冻结结果路径；需要最终提交完整绑定时显式追加 `--integrity-mode submission`。如果本地已有 hash，检查器会校验它，但不会要求本地探索机械生成 hash。

实验与失败凭证的检查命令见 [Experiment Artifacts](references/validation/experiment_artifacts.md)。

建立 `paper_plan.json` 前读取 [Paper Plan](references/contracts/paper_plan.md)。先让人确认 central thesis、claim type、argument units 与 risk-weighted depth budget；每个子问题必须明确 formulation、result、validation、interpretation 和 display/waiver，达到 `readiness.stage=technical_draft` 后才编译正式 writer package。Writer 不得浏览 raw outputs 后自行添加研究事实。设计正式图时读取 [Figure Contract](references/contracts/figure_contract.md)、[Figure Design](references/visualization/figure_design.md)、[Diagram Workflow](references/visualization/diagram_workflow.md)、[Native draw.io Backend](references/visualization/drawio_backend.md) 与 [Plot Recipes](references/visualization/plot_recipes.md)。数据证据图可以由确定性绘图库生成；总览图、任务流程图和模型框架图必须先生成结构化 `diagram_spec.json`，再通过 `generate_drawio.py` 生成 native `.drawio`，不能用 Mermaid 或 Python 绘图脚本作为最终成品。只有 registry 中 `verified` 的 evidence 能支撑 claim。

往届论文只在赛前按 [Outstanding Paper Quarantine](references/research/precedent_policy.md) 提炼机制卡；Writer 默认不加载全文。

## 4. W1/W2：单 Writer、确定性 QA 与语义审查

- 摘要：读取 [Abstract Guidelines](references/writing/abstract_guidelines.md)。
- 全文一致性：读取 [Consistency Sweep](references/writing/consistency_guidelines.md)。
- 语义审查：读取 [Semantic Critic Rubric](references/review/semantic_critic_rubric.md)。
- 定向返修：读取 [Bounded Revision](references/review/revision_policy.md)。

先运行 `scripts/qa/check_paper_readiness.py` 和 `scripts/claims/compile_writer_package.py`；只有显式 `--preview` 才允许生成不完整预览包，不能把它交给正式 Writer。Writer 完成后运行 `scripts/qa/check_writer_package.py --strict` 与 `scripts/claims/inventory_claims.py --strict`；前者约束只读 package，后者扫描最终正文里未登记数字、比较、因果、最优性和外部事实，不以“规避 AI 检测”为目标。正式流程图/框架图还要运行 `scripts/figures/check_diagram_spec.py --strict --require-reviewed`；默认优先 SVG/PDF，确有兼容性原因时可声明 `raster_only + raster_text`，但必须保留可编辑源并达到至少 300 DPI。编辑阶段读取 [Editorial Style](references/writing/editorial_style.md)。

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
  --writer-package reports/writer_package.json `
  --require-first-draft-coverage `
  --require-math-writing-coverage `
  --require-derivation-integrity `
  --output reports/deterministic_qa.json

python scripts/qa/check_gates.py --manifest run_manifest.json --strict
```

默认 `sprint` 只用确定性 QA + 一个 Semantic Critic；最终成稿可加一个 Blind Reviewer；仅冲奖且有返修余量时使用三席。最多两轮 targeted revision。增强 profile 的 `check_gates.py` 会从 deterministic report 的声明输入重建一次临时 QA，不覆盖原报告；重算失败不能靠手改 `ok=true` 通过。

CUMCM 工程先用 `scripts/latex/init_cumcm_project.py` 从锁定的本地 community snapshot 建立清洗后的电子版骨架；它不会把社区模板冒充官方模板。用户提供 Overleaf source ZIP 或完整本地模板目录时，改读 [完整用户 LaTeX 模板适配](references/writing/template_adapter.md)，运行 `scripts/latex/import_user_template.py`：必须复制完整可编译资产并只替换 demo 正文，不能只 fork `main.tex` 和 `.cls`。导入合同默认 `draft`，先做隔离编译、当届 profile PDF QA 与人工视觉审查，再用于正式构建。LaTeX 交付使用 `scripts/latex/safe_build.py --integrity-mode research --template-contract ...`，禁止 shell escape、在隔离副本构建并写入模板身份；随后运行 `scripts/pdf/check_pdf.py` 全页渲染，并按 [Visual Review](references/visualization/visual_review.md) 生成 review receipt。社区模板只作技术底座，当届官方 profile 仍是格式真源。

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
