# Math Modeling Evidence Harness

面向 CUMCM、MCM/ICM 等数学建模竞赛的本地 Skill/Harness。它把“当届规则—模型—代码—验证—结果—证据—论文—提交”连接成可复核链路，重点降低四类风险：比赛违规、验证占位、关键数字漂移、最终文件与规则不符。

> 当前状态：已有 P0 基础链路、research-first 模型选型门、技术首稿 readiness、分级完整性、真实模板使用检查、实际 LaTeX/PDF QA 和回归测试。CUMCM 已提供从锁定 community snapshot 建立清洗骨架的入口，但它仍不是官方模板；当届 official golden profile、自动选择性重跑和独立能力 benchmark 仍在后续发布门。它是可组合 Harness，不是全自动解题 Agent；模型选择、结论负责和最终提交仍由参赛队完成。

## 架构

```text
Competition Profile / Official Rule Snapshot
╔══════════════ Contest Safety + AI Registry + Human Review ══════════════╗
║ Problem → Research/Candidates → M1 → Coding → P1 → Full/Validation     ║
║ → P2 → Results Freeze                                                   ║
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
- **AI Usage + Human Checkpoints**：在 `run_manifest` 中登记影响交付物的 AI 使用；M1/P2/W2/S1 绑定当前 artifact 做人工确认，只有 submission 模式强制全量哈希。
- **Research-first Model Contract**：先记录中英检索词、大模型知识侦察、外部文献搜索和候选模型比较，再固定变量、公式、参数、实现步骤、验证与失败模式。
- **Validation Obligations**：P2 不再只看验证文件是否存在；由有限比较合同和 measurement snapshot 独立导出 `PASS/FAIL/ERROR`，`{"ok": true}` 不能替代重算。
- **Result Freeze**：禁止覆盖已有冻结文件，绑定模型合同、输入、代码、可重算验证报告与结果哈希；保留失败 run，但只有 `claimable=true` 的 PASS run 可进入论文证据链。
- **Evidence Registry**：一个可增量账本同时承载文献与结果证据；文献身份、全文支持和出版状态分开核验。
- **Argument Plan / Writer Package**：central thesis、claim type、段落研究动作和按风险分配的篇幅在写作前锁定；每问必须覆盖 formulation/result/validation/interpretation，避免第一版只有摘要式结果。
- **Paper Plan / Figure Contract**：requirement → claim → evidence 驱动章节与图表；不硬编码图数。
- **Deterministic QA + Semantic Critic**：机械一致性交给脚本，边界外推和论证强度交给 Critic。
- **Template Usage + Submission Freeze**：正式构建验证实际 `documentclass`、类文件、命令和引擎；W2 与 S1 分离，最终由不可覆盖的 `submission_manifest.json` 固定比赛 profile、规则、文件、截止时间和包哈希。

## 核心 artifact

基础兼容 profile 维护五个核心 JSON。新项目默认使用 `integrity_mode=research`；只有最终提交切换到 `submission` 并强制全量文件哈希。`enhanced_integrity_profile=true` 是额外的题面、数据、实现、呈现与 PDF receipts 检查，不应和哈希模式混为一谈：

| 文件 | 作用 |
|---|---|
| `model_contract.json` | M1 数学、数据与验证合同 |
| `run_manifest.json` | 可变控制面：规则、安全、AI、人审、命令、Gate、Reviewer |
| `frozen_results.json` | P2 可信结果与上游快照 |
| `evidence_registry.json` | 唯一增量证据账本 |
| `paper_plan.json` | W1 claim-evidence、章节、摘要和图表计划 |
| `submission_manifest.json` | F1 最终不可变提交快照 |

增强 profile 另外要求：`problem_snapshot.json`、每个权威数据集的 `data_contract.json`、`implementation_map.json`、`artifact_dag.json`、`presentation_contract.json`、工具生成的 `claim_inventory.json`、`build_receipt.json`、`pdf_visual_qa.json` 与人工/多模态 `visual_review_receipt.json`。详见 [第二轮整合审计](docs/SECOND_ROUND_EDITORIAL_INTEGRATION_AUDIT_2026-08-13.md)。

临时推理、阶段摘要和重复结果报告不需要长期保存。

## 目录

```text
SKILL.md                         Skill 入口与阶段路由
agents/openai.yaml               UI 元数据
schemas/                         核心、增强 integrity、视觉与提交回执 JSON Schema
scripts/validation/              有限比较的独立验证求值器
scripts/freeze_results.py        重算验证后冻结完整 run，并派生 claimable
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
scripts/claims/                  编译只读 writer package
scripts/latex/                   数值宏生成与隔离安全构建
assets/templates/               原创清洗骨架与 Template Contract（不内嵌受限上游 class）
scripts/pdf/                     实际 PDF 检查、逐页渲染与 contact sheet
scripts/figures/                 Figure export 确定性检查
references/visualization/        evidence-driven 科研绘图规则
references/review/               Critic 与有界修订
references/submission/           S1/F1 规则
docs/HARNESS_INTEGRATION_ANALYSIS.md
                                  开源机制审计与整合决策
docs/UPSTREAM_STRENGTHS_REVIEW_2026-08-13.md
                                  用户补充仓库的分层复核与本轮落地映射
tests/test_p0_harness.py          P0 正/负例回归测试
vendor/template_sources.json     模板来源、锁定提交与许可证决策
vendor/clone_templates.ps1       重建本地浅克隆（clone 目录不随 Skill 分发）
```

## 快速开始

### 0. 比赛前离线自检与模板锁定

```powershell
powershell -ExecutionPolicy Bypass -File vendor/clone_templates.ps1
python scripts/doctor.py --offline
```

默认锁定 CUMCMThesis、mcmthesis、Eisvogel 和 SciencePlots。用户指定的三个 Overleaf 页面也逐项登记，但公开 Gallery 项目需要进入登录账户后才能导出 source ZIP，不能冒充 Git clone；manifest 将它们与可验证的兼容仓库明确分开。Scientific Visualization Book 与 Python Graph Gallery 需要显式传 `-IncludeLargeReferences` 才下载；当前已按稀疏路径锁定到指定提交，仅作为本地图形设计参考，整个 `vendor/upstream/` 已被 Git 忽略，禁止随 Skill 分发。所有社区上游都不是当届官方规则。CUMCMThesis 的当前审计快照没有仓库级 LICENSE，因此也禁止随 Skill 分发；具体页面、提交、稀疏路径和许可证见 `vendor/template_sources.json`。

两条可验证论文模板已经实际通过隔离编译并完成全页渲染。兼容测试发现 CUMCM 示例含未嵌入字体，mcmthesis 示例默认采用 Letter 纸；这两个发现会阻止它们未经 visual profile 修补直接成为生产模板。
机器可读结果见 [`docs/TEMPLATE_COMPATIBILITY_AUDIT_2026-08-13.json`](docs/TEMPLATE_COMPATIBILITY_AUDIT_2026-08-13.json)。

CUMCM 新工程不要手写 `ctexart`。从锁定上游复制 class，并套用仓库内的清洗电子版骨架：

```powershell
python scripts/latex/init_cumcm_project.py `
  --destination paper `
  --title "论文题目" `
  --problem C `
  --keywords "关键词一;关键词二;关键词三" `
  --year 2026 --month 9 --day 4
```

这会生成 `paper/main.tex`、`paper/template_contract.json`、匿名 metadata 和正文分片，并实际使用 `cumcmthesis`。community class 只作技术底座；提交前仍须通过当届官方 profile 与最终 PDF QA。

### 1. 建立规则、题面与数据快照

赛前从赛事官网保存当届规则、格式规范、AI 政策和提交说明，登记 URL、抓取时间和 SHA-256。不要把往届规则写成当前规则。

先复制完整的 `run_manifest` 结构，再按当届快照填写 Competition Profile。下面只是 AI/提交差异片段，不能替代完整 schema。

CUMCM 当前可核验的 AI 专项基线仍是 2025 试行规定；2026 赛前规则已要求遵守该专项规定。使用 AI 时需要正文标注、AI 工具参考文献和支撑材料中的详情 PDF；未使用时需要在参考文献后声明：

```json
{
  "ai_disclosure_policy": "required_when_used",
  "ai_disclosure_format": "separate_file",
  "ai_manual_checks": {
    "when_used": [
      "ai_generated_content_marked",
      "ai_tool_in_references",
      "ai_disclosure_in_support"
    ],
    "when_not_used": ["no_ai_declaration_after_references"]
  }
}
```

COMAP 官网会滚动更新赛季。当前规则是一个 PDF、受限主体 25 页，使用 AI 时在主体之后附不计页数的 AI Report：

```json
{
  "support_policy": "prohibited",
  "max_pages": 25,
  "max_pages_excludes_ai_report": true,
  "ai_disclosure_policy": "required_when_used",
  "ai_disclosure_format": "in_paper_section",
  "ai_manual_checks": {
    "when_used": [
      "ai_inline_citations",
      "ai_tool_in_references",
      "ai_report_in_paper",
      "ai_report_position"
    ],
    "when_not_used": []
  }
}
```

每次比赛开始前都重新抓取官方页面；示例只能帮助配置字段，不能作为当届规则证据。

```powershell
python scripts/qa/check_contest_safety.py `
  --manifest run_manifest.json `
  --strict
```

在 M1 前创建并校验 `problem_snapshot.json`、`data_contract.json` 与 `implementation_map.json`：

```powershell
python scripts/qa/check_problem_coverage.py `
  --problem-snapshot problem_snapshot.json `
  --model-contract model_contract.json `
  --paper-plan paper_plan.json `
  --strict

python scripts/qa/check_data_contract.py `
  --data-contract data_contract.json `
  --model-contract model_contract.json `
  --strict

python scripts/qa/check_implementation_map.py `
  --implementation-map implementation_map.json `
  --model-contract model_contract.json `
  --strict

python scripts/qa/check_artifact_dag.py `
  --dag artifact_dag.json `
  --strict
```

### 1.5 先调研并通过 M1，再开始实现

不要从题面直接跳到一个算法名。对每个子问题先做两轮检索：第一轮用大模型知识生成方法族、关键词和待核验假设；第二轮通过 Web Search/OpenAlex/Crossref/CNKI/出版社或官方仓储核验真实文献。把文献写入同一个 `evidence_registry.json`，再在 `model_contract.research_basis` 中比较候选模型并形成详细实施蓝图。详见 [Research-first Model Planning](references/research/model_planning.md)。

```powershell
python scripts/qa/check_modeling_plan.py `
  --model-contract model_contract.json `
  --evidence-registry evidence_registry.json `
  --strict
```

M1 会拒绝：无外部检索、无全文 locator、每问只有一个无豁免候选、没有明确选型标准、选中候选没有映射到模型，或缺公式/参数/实现步骤/输出/验证/失败模式。M1 未通过不得进入 P1。

### 2. 完整验证后冻结结果

先为每项 `validation_obligations[]` 写入带定位器的 measurement snapshot，再由独立求值器生成报告；报告的 verdict 不能手填。FAIL/ERROR 也可冻结用于审计，但不能通过 P2 或写入 Evidence Registry。

```powershell
python scripts/validation/evaluate_obligations.py `
  --model-contract model_contract.json `
  --measurements reports/validation_measurements.json `
  --output reports/full_validation.json
```

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

先检查论文计划是否足以写技术首稿，再编译只读 writer package。正式编译默认要求每个子问题都有建模/推导、结果、验证、解释/边界和图表或豁免；只有本地检查轮廓时才显式使用 `--preview`。

```powershell
python scripts/qa/check_paper_readiness.py `
  --paper-plan paper_plan.json `
  --evidence-registry evidence_registry.json `
  --minimum-stage technical_draft `
  --strict

python scripts/claims/compile_writer_package.py `
  --paper-plan paper_plan.json `
  --frozen-results results/frozen_results.json `
  --evidence-registry evidence_registry.json `
  --output reports/writer_package.json `
  --integrity-mode research
```

随后由 `presentation_contract.json` 生成统一数值宏，再从最终草稿生成 claim inventory；不要在摘要、表格和图注中手填派生百分比。

```powershell
python scripts/latex/generate_values_tex.py `
  --presentation-contract presentation_contract.json `
  --frozen-results results/frozen_results.json `
  --output paper/generated/results.tex `
  --provenance reports/result_provenance.json

python scripts/claims/inventory_claims.py `
  --paper-plan paper_plan.json `
  --frozen-results results/frozen_results.json `
  --draft paper/main.tex `
  --output reports/claim_inventory.json `
  --strict
```

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
  --problem-snapshot problem_snapshot.json `
  --data-contract data_contract.json `
  --implementation-map implementation_map.json `
  --artifact-dag artifact_dag.json `
  --output reports/deterministic_qa.json

python scripts/qa/check_gates.py --manifest run_manifest.json --strict
```

LaTeX 项目可再传 `--tex`、`--bib` 和 `--check-figures`。

需要直接生成正式科研图时，使用 `scripts/figures/plot_templates.py`。它支持 line/interval、comparison、distribution/ECDF、scatter/residual、sensitivity、Pareto、heatmap 与 network，并为每张图记录输入、输出、style、字段和完整参数 hash；PDF 元数据时间戳已移除，完整参数见 [Plot Recipes](references/visualization/plot_recipes.md)。

### 4.1 安全构建与实际 PDF 视觉 QA

```powershell
python scripts/latex/safe_build.py `
  --source-root paper `
  --entrypoint main.tex `
  --engine xelatex `
  --integrity-mode research `
  --template-contract paper/template_contract.json `
  --output submission/solution.pdf `
  --receipt reports/build_receipt.json

python scripts/pdf/check_pdf.py `
  --pdf submission/solution.pdf `
  --profile profiles/visual_profile.json `
  --source paper/main.tex `
  --render-dir reports/rendered_pages `
  --contact-sheet reports/contact_sheet.jpg `
  --output reports/pdf_visual_qa.json
```

`safe_build.py` 的 `dev/research` receipt 只记录路径和模板身份，不强制本地文件哈希；`submission` 才记录 source tree、模板、输出与日志哈希。`check_pdf.py` 只给 formal verdict，并渲染每一页；随后必须按 `visual_review_receipt.schema.json` 由人或多模态逐页确认无裁切、重叠、空白/重复页、中文缺失和不可读图表。`pdffonts` 的 encoding 标签不能单独判断中文显示成功。

### 5. S1/F1

S1 前按以下顺序准备：

1. 停止修改最终 PDF、支撑包和 AI 详情文件；
2. 补齐 `run_manifest.ai_usage[]`，每项通过人工核验；
3. 让 S1 human checkpoint 绑定最终文件哈希，并完成通用及 AI 条件人工检查；
4. 运行比赛专属 S1；通过后才把 report 登记回 manifest。

CUMCM 式“论文 + 支撑包 + AI 详情源文件”示例：

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

这里的 `--ai-disclosure` 用于固定 AI 详情源文件；如果当届规则要求它位于支撑材料中，S1 还必须确认最终 ZIP/RAR 已实际包含该文件。它不表示要额外上传第三个顶层文件。

MCM/ICM 使用 AI、整个 PDF 28 页且末尾 AI Report 为 3 页的示例：

```powershell
python scripts/qa/check_submission.py `
  --run-manifest run_manifest.json `
  --paper submission/0000000.pdf `
  --paper-pages 28 `
  --ai-report-pages 3 `
  --page-count-method pdfinfo `
  --output reports/submission_qa.json
```

`--paper-pages` 始终是整个 PDF 的总页数。只有 profile 设置 `max_pages_excludes_ai_report: true` 时才传 `--ai-report-pages`；未使用 AI 时传 `0`。S1 会记录总页数、AI Report 页数和实际受限页数。

S1 通过后，在 `run_manifest.json` 中完成三项状态更新：

```json
{
  "status": "submission_ready",
  "phase": "submission",
  "gates": {
    "s1": {
      "status": "pass",
      "checked_at": "<ISO-8601>",
      "evidence": ["reports/submission_qa.json"]
    }
  },
  "artifacts": [
    {
      "role": "submission_qa",
      "path": "reports/submission_qa.json",
      "sha256": "<64-hex>"
    }
  ]
}
```

这是字段片段，不要覆盖 manifest 中其他 Gate 和 artifact。

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

S1 report 同时绑定 Competition Profile、submission rules、AI Usage Registry 和 S1 human checkpoint。S1 后新增 AI 使用、修改人工检查或改规则，即使论文文件没变，F1 也会拒绝旧报告；正确做法是重新执行 S1，不要手改报告。

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

Figure Contract 现在要求 message、comparison、visual encoding、selection rule 与 accessibility；`check_figure.py` 检查导出格式、PDF 字体和栅格有效 DPI，`check_pdf.py` 负责最终 PDF 全页渲染。灰度/色觉、视觉强调和可读性仍由 visual review receipt 裁决，不冒充纯自动审美评分。

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

当前 37 个回归测试覆盖：规则/安全策略、人工 checkpoint、验证占位拒绝、`550 MW > 498 MW` 的失败比较、失败 run 冻结但不能注册 evidence、手改 FAIL 为 PASS 的拒绝、P2 对 non-claimable 冻结件的阻断、题面漏答、数据泄漏、公式—代码 hash 漂移、artifact DAG stale、正文未登记数字/因果、Pareto 伪前沿、统一数值宏、LaTeX shell escape/路径穿越、真实构建与 PDF 全页渲染、8 类受控图型、AI 条件披露、ZIP 安全、S1 状态过期与最终包不可覆盖行为。

## 进一步阅读

- [Harness Integration Analysis](docs/HARNESS_INTEGRATION_ANALYSIS.md)
- [Artifact Contracts](references/contracts/artifact_contracts.md)
- [Contest Safety](references/safety/contest_safety.md)
- [Validation Obligations](references/validation/validation_obligations.md)
- [Literature Evidence](references/research/literature_evidence.md)
- [Figure Contract](references/contracts/figure_contract.md)
- [Submission Freeze](references/submission/submission_freeze.md)
