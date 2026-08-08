---
name: math-modeling-skill-sion
description: 面向 CUMCM、MCM/ICM 等数学建模竞赛的证据驱动 Harness。用于赛题分析、模型合同、代码 smoke/full 实验、结果冻结、证据注册、论文与图表规划、摘要/全文一致性 QA、引用检查和 Reviewer Gate；当用户要求完成或审查数学建模项目、数模论文、建模代码或竞赛交付链时使用。单纯求解一道不涉及竞赛交付的普通数学题时不要使用。
---

# Math Modeling Evidence Harness

按以下单向链执行；不要跳过结果冻结后直接写论文数字：

```text
Problem Analysis
→ model_contract.json → M1
→ Coding → P1 smoke → Full Experiments
→ P2 → frozen_results.json
→ evidence_registry.json
→ paper_plan.json / Figure Contracts → W1
→ Paper Writer
→ Deterministic QA → Semantic Critic → optional Blind Reviewers
→ W2 Release
```

## 核心约束

1. 将 `model_contract.json` 作为 Modeling 与 Coding 的共同输入；缺失变量、单位、约束或验收标准时返回 M1，不让 Coder 猜测。
2. 将关键数字写入 `frozen_results.json`，再注册为 evidence；显式填写单位和适用边界，不默认补 `dimensionless`。
3. 将 claim → evidence 映射只保存在 `paper_plan.json`；不要在 registry 中维护反向 claim 列表。
4. 让图的数量由 requirement → claim → evidence 缺口决定；不设置最低图数。
5. 将可程序化检查交给 `scripts/qa/`；让 Semantic Critic 只检查语义支持、边界外推和结论风险。
6. 在输入、代码、结果、论文或 Reviewer 报告哈希变化后，将受影响 Gate 退回 `pending` 并重检。
7. 默认使用 JSON。只有环境已安装 PyYAML 时才使用人类可读 YAML。

## 执行流程

### 1. 建立 Model Contract 并通过 M1

填写题目要求、输入输出、变量单位与定义域、目标、约束、算法、smoke/full 验收标准、风险和回退方案。先读取 [artifact contracts](references/contracts/artifact_contracts.md) 与 [model contract](references/contracts/model_contract.md)；模型选择需要细化时再读取题型相关 reference。

只在 schema 校验通过且 `status=ready` 后把 M1 标为 `pass`。

### 2. 编码并通过 P1/P2

- P1：只运行一个最小 smoke 路径，验证输入、单位、范围、约束与输出结构。
- P2：分别记录成功的 `stage=full` 和 `stage=freeze` 命令；保存代码、输入与验证日志哈希。
- 不要把原始结果文件当作冻结结果；使用冻结脚本生成新文件，禁止原地覆盖。

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

### 3. 先注册 Evidence，再规划论文

不要预先猜 evidence ID。先执行：

```powershell
python scripts/register_evidence.py `
  --frozen-results results/frozen_results.json `
  --output evidence_registry.json
```

然后读取 [paper plan contract](references/contracts/paper_plan.md)，只使用 registry 中存在且已验证的 evidence 建立 `paper_plan.json`。规划正式图前读取 [figure contract](references/contracts/figure_contract.md) 与 [figure design](references/visualization/figure_design.md)。

### 4. 写作并通过 W1/W2

保持一个 Paper Writer，按需加载 reference：

- 摘要撰写/改写：读取 [abstract guidelines](references/writing/abstract_guidelines.md)，只使用 `abstract_result_ids` 中的冻结结果。
- 全文数字、单位、术语和图表一致性：读取 [consistency guidelines](references/writing/consistency_guidelines.md)。
- 语义审查：读取 [semantic critic rubric](references/review/semantic_critic_rubric.md)。
- 定向修订：读取 [bounded revision policy](references/review/revision_policy.md)。
- Gate 状态：读取 [gate policy](references/workflow/gate_policy.md)。

用统一入口运行并落盘确定性检查；LaTeX 交付时同时传入 `--tex/--bib`，其他格式省略这两个参数：

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
  --tex paper/main.tex `
  --bib paper/references.bib `
  --check-figures `
  --output reports/deterministic_qa.json

python scripts/qa/check_gates.py --manifest run_manifest.json --strict
```

将 Deterministic QA、Semantic Critic 和 Blind Reviewer 回执分别落盘并记录 SHA-256；把生成的 deterministic report 路径与哈希写回 manifest 后再运行 Release Gate。默认使用 `sprint`：确定性 QA + 一个 Semantic Critic；`final_submission` 再加一个 Blind Reviewer；只有明确冲奖时使用 `award_max` 三席盲审。最多执行两轮 targeted revision。

## Release 条件

只在以下条件同时满足时发布：五类 contract 与哈希一致；M1/P1/P2/W1/W2 顺序通过且有 evidence；论文 artifact 已登记；摘要关键数字与单位来自冻结结果；所有 claim 只引用已验证 evidence；Reviewer 报告存在且哈希匹配；没有未关闭 issue。
