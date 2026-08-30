# Paper Plan IR Contract

作者源是 `paper/00_PAPER_PLAN.md` 的 Paper Director Plan；机器消费者需要时，运行 `harness paper plan --compile` 生成 `.harness/contracts/paper_plan.json`。不要直接维护平行 JSON，也不要把作者 Markdown 或 IR 当作 Gate 事实。

`paper_plan.json` 是可验证的论证 IR，不是论文初稿或第二份结果数据库。Writer 必须先把它编译为只读 package，再开始成文；不能浏览 raw outputs 后自行发明数字、原因、场景或结论强度。

## 建立顺序

1. M1 前可先登记经全文核验的文献 evidence。
2. P2 后把 `frozen_results.json` 合并到同一个 `evidence_registry.json`。
3. 检查 registry 中实际存在且 `verification_status=verified` 的 `evidence_id`。
4. 最后建立 requirement → claim → evidence 与 section/figure/table 规划。

结果证据 ID 由注册脚本稳定生成：结果 `R-Q1-01` 对应证据 `E-R-Q1-01`；不要手工创建重复结果证据。

## 最小示例

```json
{
  "schema_version": "1.3",
  "run_id": "run-001",
  "central_thesis": {
    "text": "在冻结需求和约束下，方案 B 以可验证的可行性取得最低成本。",
    "claim_ids": ["C-Q1-01"],
    "boundary": "不外推至未测试的需求、价格或约束。"
  },
  "requirements": [
    {"requirement_id": "REQ-Q1", "text": "回答问题一的最优方案和验证结果", "claim_ids": ["C-Q1-01"]}
  ],
  "claims": [
    {
      "claim_id": "C-Q1-01",
      "claim_type": "observation",
      "text": "方案 B 在给定约束下取得最低成本",
      "question_id": "q1",
      "evidence_ids": ["E-R-Q1-01"],
      "result_ids": ["R-Q1-01"],
      "section": "results.q1",
      "boundary": "仅适用于冻结数据和给定约束",
      "support_level": "direct",
      "inference_strength": "descriptive",
      "comparison": {"comparator": "同一约束下的候选方案", "metric": "总成本", "direction": "lower_is_better", "scenario": "frozen-base"}
    }
  ],
  "sections": [
    {"section_id": "results.q1", "purpose": "回答问题一并解释验证结果", "claim_ids": ["C-Q1-01"]}
  ],
  "argument_units": [
    {
      "unit_id": "AU-Q1-FORM",
      "section_id": "results.q1",
      "rhetorical_role": "mechanism_derivation",
      "claim_ids": ["C-Q1-01"],
      "evidence_ids": ["E-CITE-Q1-METHOD"],
      "prerequisite_unit_ids": [],
      "model_ids": ["M-Q1"],
      "equation_ids": ["EQ-Q1-OBJ"],
      "constraint_ids": ["C1"],
      "math_locators": ["\\label{eq:EQ-Q1-OBJ}", "\\label{con:C1}"],
      "expected_reader_judgment": "模型机制、变量和约束与题意一致。",
      "boundary": "固定需求和可加成本。",
      "depth_priority": {"level": "core", "rationale": "核心机制必须先让读者看懂。"}
    },
    {
      "unit_id": "AU-Q1-RESULT",
      "section_id": "results.q1",
      "rhetorical_role": "result_observation",
      "claim_ids": ["C-Q1-01"],
      "evidence_ids": ["E-R-Q1-01"],
      "prerequisite_unit_ids": [],
      "result_ids": ["R-Q1-01"],
      "math_locators": ["\\label{harness:AU-Q1-RESULT}"],
      "expected_reader_judgment": "该数值来自可复核的冻结运行。",
      "boundary": "仅适用于 frozen-base。",
      "depth_priority": {"level": "core", "rationale": "核心结果需要与证据和限制一起解释。"}
    },
    {
      "unit_id": "AU-Q1-VALID",
      "section_id": "results.q1",
      "rhetorical_role": "validation",
      "claim_ids": ["C-Q1-01"],
      "evidence_ids": ["E-R-Q1-01"],
      "prerequisite_unit_ids": ["AU-Q1-RESULT"],
      "model_ids": ["M-Q1"],
      "validation_obligation_ids": ["VAL-FEASIBILITY"],
      "math_locators": ["\\label{val:VAL-FEASIBILITY}"],
      "expected_reader_judgment": "可行性与目标值已经独立重算。",
      "boundary": "仅验证已声明约束。",
      "depth_priority": {"level": "supporting", "rationale": "验证支撑结论但不复述求解过程。"}
    },
    {
      "unit_id": "AU-Q1-BOUNDARY",
      "section_id": "results.q1",
      "rhetorical_role": "boundary",
      "claim_ids": ["C-Q1-01"],
      "evidence_ids": ["E-R-Q1-01"],
      "prerequisite_unit_ids": ["AU-Q1-VALID"],
      "math_locators": ["\\label{harness:AU-Q1-BOUNDARY}"],
      "expected_reader_judgment": "结论不会外推到未测试需求。",
      "boundary": "仅适用于 frozen-base。",
      "depth_priority": {"level": "compact", "rationale": "明确边界即可，避免重复主结果。"}
    }
  ],
  "precision_policy": {
    "audit_source": "frozen_display_value",
    "prose_source": "frozen_display_value",
    "table_source": "frozen_display_value",
    "abstract_max_numeric_claims": 3
  },
  "abstract_results": [
    {
      "result_id": "R-Q1-01",
      "priority": "primary",
      "selection_reason": "它直接决定核心建议，且已通过比较与边界验证",
      "claim_ids": ["C-Q1-01"],
      "word_budget": 28
    }
  ],
  "nonresearch_numeric_literals": [
    {"token": "2026", "reason": "赛事年份，不是研究结果"}
  ],
  "terminology": [
    {"canonical": "可行域", "forbidden_variants": ["可行区域"]}
  ],
  "figures": [],
  "tables": [],
  "draft_coverage": {
    "status": "planned",
    "anchors": [
      {"anchor_id": "AU-Q1-FORM", "unit_id": "AU-Q1-FORM", "question_id": "q1", "patterns": ["\\label{harness:AU-Q1-FORM}"]},
      {"anchor_id": "AU-Q1-RESULT", "unit_id": "AU-Q1-RESULT", "question_id": "q1", "patterns": ["\\label{harness:AU-Q1-RESULT}"]},
      {"anchor_id": "AU-Q1-VALID", "unit_id": "AU-Q1-VALID", "question_id": "q1", "patterns": ["\\label{harness:AU-Q1-VALID}"]},
      {"anchor_id": "AU-Q1-BOUNDARY", "unit_id": "AU-Q1-BOUNDARY", "question_id": "q1", "patterns": ["\\label{harness:AU-Q1-BOUNDARY}"]}
    ]
  },
  "readiness": {
    "stage": "technical_draft",
    "question_coverage": [
      {
        "question_id": "q1",
        "formulation_unit_ids": ["AU-Q1-FORM"],
        "result_unit_ids": ["AU-Q1-RESULT"],
        "validation_unit_ids": ["AU-Q1-VALID"],
        "interpretation_unit_ids": ["AU-Q1-BOUNDARY"],
        "display_ids": [],
        "display_waiver": "该问只有一个标量结果，公式和正文比单独图表更清楚。"
      }
    ]
  },
  "canonical_recommendation": {"text": "采用方案 B", "evidence_ids": ["E-R-Q1-01"]},
  "status": "ready"
}
```

## Gate 规则

- 只让 `ready` 计划进入 W1。
- 为每个赛题子问题至少建立一个 claim；每个 requirement 和 claim 都必须非空。
- 只引用已验证 evidence；不得用 `pending` evidence 支撑论文主张。
- `central_thesis` 只绑定 1—5 条决定性 claim，并显式说明整体边界；不能把每小问的数字清单伪装成总论点。
- claim 必须标注为 `observation`、`inference` 或 `recommendation`。Observation 必须给出 `result_ids`；Inference/Recommendation 必须给出已经成立的 `precondition_claim_ids`，且不能标为 `direct`。
- 可选的 `inference_strength` 用 `descriptive`、`associational`、`mechanistic`、`causal` 区分论断强度；Observation 不能声明 mechanistic/causal。`causal` 还必须登记 `causal_design`，不能从普通优化结果直接推出因果。未登记时 Writer 按 observation=descriptive、其他 claim=mechanistic 的保守默认处理。
- 使用“最优、显著、稳健、提升”等比较性强词时，填写 `comparison` 的 comparator、metric、direction 和 scenario；缺少比较合同时降为 observation 或删除强词。
- 每个 `argument_unit` 只能有一个 `rhetorical_role`，同时绑定 claim/evidence、前置单元、期望读者判断、边界和 `depth_priority`。`core`、`supporting`、`compact` 只表达叙事取舍，不是预先分配的字数 Gate；把 model choice、结果观察、解释和边界混在一个万能段落会被拒绝。
- 每个核心 `argument_unit` 还应绑定数学来源：formulation 绑定 `model_ids` 与 `equation_ids`/`constraint_ids`，validation 绑定 `validation_obligation_ids`，result/comparison 绑定 `result_ids` 或 `derived_result_ids`，并填写 `math_locators`。这使 Writer 不能把公式、验证和结果写成无来源的通用话术。
- `prerequisite_unit_ids` 必须形成无环、前向的论证图；推荐顺序是 model/formulation → result/comparison → validation → interpretation/boundary/recommendation。`check_math_writing.py` 会检查依赖环、逆序和首稿定位。
- `scope` 可声明 `question`（恰好一个 ID）、`cross_question`（至少两个 ID）或 `global`（不带 ID）；跨题与全局单元可进入相应问题的 readiness coverage，也不会被误报为未使用。
- `depth_budget` 和各单元 `target_words` 是迁移期可读的 legacy metadata；新的 `schema_version: "1.3"` 作者应省略它们，且任何版本都不再让它们控制当前计划 Gate。
- 正式第一版前必须达到 `readiness.stage=technical_draft`；每个子问题分别绑定 formulation、result、validation、interpretation argument units 和至少一个 display，确无必要时写具体 waiver。此处检查论证覆盖而非计划字数总和。
- `draft_coverage` 为 readiness 使用的每个 argument unit 登记稳定锚点（推荐不可见的 `\\label{harness:...}` 或明确小节标题）。正式 QA 传 `--require-first-draft-coverage` 后，缺锚点会阻断；`minimum_words` 仅在显式 `--enforce-minimum-words` 时成为本地阈值，默认只是审阅提示。
- 数字只能来自 `precision_policy` 指定的 frozen display source；摘要的权威数字不超过 `abstract_max_numeric_claims`。
- 文献 evidence 必须同时通过 metadata、全文内容和出版状态检查；优秀论文机制卡不属于 evidence。
- 为“最优、显著、稳健、提升”等表述登记 baseline、指标、统计口径和适用边界。
- 仅把摘要需要出现的权威结果加入 `abstract_results[]`，并说明 `selection_reason`、关联 claim 与词数预算；不要只登记 ID 后把所有结果塞进摘要。
- 年份、题号、章节号等非研究数字如会被 claim inventory 扫描，可登记到 `nonresearch_numeric_literals[]` 并写明理由；不能用它放行结果、百分比或参数。
- 将同一推荐方案的唯一文字版本放入 `canonical_recommendation`；若题型不需要推荐，可省略该字段。

## 首稿后版式审计

先完成全文和 PDF，再按实际版面审查。不可在前期用按题字数总和、排名或相关系数替代版面与叙事判断。

```powershell
python scripts/qa/audit_paper_length.py `
  --project-root . `
  --paper-plan paper_plan.json `
  --competition-profile competition_profile.json `
  --draft paper/main.tex `
  --pdf build/paper.pdf `
  --output reports/paper_length_audit.json
```

它读取 PDF 实际页数并输出 core/supporting/compact 的审阅提示；没有 PDF 只会标记 `needs_pdf`，不会伪造通过。页面上限来自 verified profile 才可构成硬错误；seed/profile 未验证时仍由人工审查收口。

## 摘要事实回查与逐问答案

摘要采用 Draft → Fact Backcheck → Final：先从 writer package 起草，再把模型身份、决定性数字、单位、比较关系、验证和边界回查到已冻结证据。`abstract_results[]` 可选填写 `question_id`、`method_ids`、`validation_ids`、`abstract_span`、`boundary` 与 `fact_check`；`fact_check.status=passed` 只能由实际回查后登记，不能把“已经写过摘要”当作通过。摘要不要求固定句式、固定数字数量或每个结果都带 baseline。

若 `model_contract.questions[]` 声明了 `required_answer`，W2 应能从官方问题走到 required answer、模型输出、冻结结果，再走到摘要中可定位的答案。运行 `check_consistency.py --require-answer-contract --require-abstract-backcheck` 时，这条链才成为显式阻断；默认模式只报告迁移提示。

## 研究顺序与论文呈现

研究顺序通常是问题 → 调研/文献 → 候选与选型 → 模型 → 代码 → 结果 → 验证；论文呈现顺序通常是问题重述 → 分析/假设 → 符号 → 模型 → 求解 → 结果 → 验证 → 解释/边界。`paper_plan` 只负责把后者编译成可追溯的论证单元，不要求每题使用相同篇幅或单独设置模型评价章节。

`check_paper_readiness.py` 会给出软性 `presentation_completeness` 清单，状态为 `RECOMMENDED`、`MISSING` 或 `NOT_APPLICABLE`；它用于提醒问题分析、假设、符号、逐问结果/解释和验证定位，不会因为缺少经验性章节而替代核心 Gate。

若在 `run_manifest.json` 中显式设置 `"editorial_semantics_profile": "strict"`，`check_gates.py` 会在 W2 从 deterministic QA 的声明输入独立重跑 required answer、摘要 backcheck 和 Figure Semantics；这仍不把 `judge_scan` 的人工 issue 变成自动评分。

## 编译写作包

```powershell
python scripts/claims/compile_writer_package.py `
  --paper-plan paper_plan.json `
  --frozen-results results/frozen_results.json `
  --evidence-registry evidence_registry.json `
  --output reports/writer_package.json `
  --integrity-mode research
```

Writer 只从 package 起草。草稿完成后运行：

```powershell
python scripts/qa/check_writer_package.py `
  --writer-package reports/writer_package.json `
  --draft paper/draft.txt `
  --strict
```

正式首稿还应让确定性 QA 检查计划覆盖是否真的写进正文：

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
  --output reports/deterministic_qa.json
```

`draft_coverage` 只验证 formulation/result/validation/interpretation 是否出现及达到最低内容量，不固定每问字数相同，也不强制每问必须有图。

数学写作正式检查还需运行：

```powershell
python scripts/qa/check_math_writing.py `
  --model-contract model_contract.json `
  --paper-plan paper_plan.json `
  --frozen-results results/frozen_results.json `
  --writer-package reports/writer_package.json `
  --draft paper/main.tex `
  --require-coverage `
  --strict
```

它检查可追溯性和逻辑顺序，不宣称自动证明代数正确。增强 W2 仍需人工勾选公式正确性、方程—约束映射、论证顺序、单位与边界一致性。

它会阻断 package 外的研究数值，以及只有 observation 却使用因果/解释性语言的草稿。它不替代人工判断机制是否真实成立；这仍是 Semantic Critic 的职责。
