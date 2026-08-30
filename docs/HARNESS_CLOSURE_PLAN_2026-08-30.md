# Harness 收敛实施计划（审查与上游调研修订版）

> 审计日期：2026-08-31
>
> 状态：待确认的实施计划；本轮只改本文档，不改 Harness
>
> 基线分支：`refactor/human-visible-workflow`
>
> 实施记录预留：`docs/implementation-notes/HARNESS_CLOSURE_2026-08-30.md`

## 1. 目标与边界

下一轮修改不再扩充 Agent 数量，而是让现有 Harness 在真实比赛中更轻、更自然、更可靠：

1. 作者笔记不再被大段 YAML 淹没。
2. 文献调研从“找到一篇真论文即可”升级为“关键研究义务有覆盖或明确缺口”。
3. Writer 先组织论证，再组织段落，不再机械填合同。
4. 正文、公式和图中不出现 `ANCHOR-*`、`LOC-*`、`\audit{}` 等内部痕迹。
5. 安装包不携带本地优秀论文、截图或本机路径。

本计划坚持：

- 不新增顶层 Gate；增强现有 M1、W1、W2、Submission QA。
- 不新增章节 Agent、Figure Agent 或三席常驻 Reviewer。
- 不新增核心 JSON 真源；优先扩展现有合同或生成派生视图。
- 不把篇数、图数、查询数和模型数写成通用硬指标。
- 语法残缺、论证跳跃等语义问题交给 Critic；确定性检查只阻断可客观证明的错误。

## 2. 审查后的事实基线

| 判断 | 证据 | 结论 |
|---|---|---|
| 作者 Markdown 仍嵌入机器合同 | `scripts/human_surface.py:112,183,245,301,418` | 真实缺口，需分层 |
| 论文上下文偏重 | `authoring_context()` 的 `paper:<section>` 路由一次声明多份输入 | 真实缺口，需最小化默认上下文 |
| Writer 有论证投影 | `scripts/views/writing_spine.py` 已生成 Writing Spine、Section Brief 和 evidence allocation | 旧计划“尚未建立”已过时；只能增强，不能重建 |
| Model→Code 有任务投影 | `scripts/views/implementation_tasks.py` 已含实现任务与 coding protocol | 旧计划“缺少 handoff”已过时；应做真实题验证 |
| 文献真实性已有下限 | `scripts/qa/check_modeling_plan.py:269-292` 要求全文、locator 和三态核验 | 可靠性已有，完备性仍不足 |
| 正文标识检查不完整 | `scripts/qa/check_writer_package.py:24` 只直接识别 ANCHOR/LOC 两类前缀 | 真实缺口 |
| Figure Contract 无受众类型 | `schemas/paper_plan.schema.json` 的 figure contract 没有 `audience` | 真实缺口 |
| 打包存在泄漏风险 | `pyproject.toml` 发现 `references*`，package-data 包含 PDF/PNG | 发布前必须修 |
| 规则重复加载没有机器指纹 | `status/context` 无 `ruleset_id` | 体验缺口，但不应引入“跳过安全检查”开关 |
| Cards 并非全部孤立 | coding protocols、validation references、precedent selectors 已消费其中一部分 | 不做“43 张卡全部接线”的伪目标 |

旧文档中的“128 个未决条目”“补 `.gitattributes` 后才能开始”“所有测试在缺本机解释器时 skip”等判断已失效或不合理。2026-08-31 复核时只有未跟踪的 `.qoder/` 与本文档；`.qoder/` 属用户工作，不在本计划中删除。测试应使用 `sys.executable`，解析失败应报错，不应用 skip 掩盖可移植性问题。

## 3. 上游机制调研：借什么，不借什么

本轮读取了具体 SKILL、reference、agent 和脚本，而不是只看 README。下表的“借用”均需改写成本仓库已有合同、视图或 QA 规则。

| 来源与具体文件 | 值得借用 | 明确不借 | 落点 |
|---|---|---|---|
| Nature Skills：[paragraph-flow.md](https://github.com/Yuan1z0825/nature-skills/blob/205ed18839181b0fe67323c7e42077a0807d8b03/skills/nature-writing/references/paragraph-flow.md)、[main-text-discipline.md](https://github.com/Yuan1z0825/nature-skills/blob/205ed18839181b0fe67323c7e42077a0807d8b03/skills/nature-shared/core/main-text-discipline.md) | 单段单消息；topic sentence→section thesis 的反向纲要；正文/图注/附录的结果分配；修订后删除检查 | 把审稿表逐项写进正文；新增一套论文真源 | 增强现有 Writing Spine 和 `manuscript_logic.md` |
| Research Writing Skill @ `7ed6377f0efb`：[SKILL.md](https://github.com/zLanqing/codex-claude-academic-skills/blob/7ed6377f0efb/research-writing-skill/SKILL.md)、`brainstorming_guide.md`、`rhetorical_moves.md`、`figure_synthesis_guide.md` | 写作前先定 problem→gap→method→evidence→contribution→limitation；Claim→Evidence→若失败怎么办；引言承诺必须由结果兑现；先定义图要证明什么 | 30 多问的固定问卷；计算机科学会议专用结构；每段写计划注释 | Writer micro-guideline、Section Brief、Figure opportunity scan |
| Academic Paper Strategist @ `c325557646e9`：[strategist/SKILL.md](https://github.com/lishix520/academic-paper-skills/blob/c325557646e9/strategist/SKILL.md)、[gap_analysis.py](https://github.com/lishix520/academic-paper-skills/blob/c325557646e9/strategist/scripts/gap_analysis.py) | 从论证流生成提纲；用 reviewer 视角检查 gap 是否有证据 | 固定 35–50 篇、每 gap 3 条证据、固定分数和字数配额 | M1 research obligations；W1 strategy check |
| Agent Research Skills @ `9e6c085d65e3`：[review-workflow.md](https://github.com/lingzhi227/agent-research-skills/blob/9e6c085d65e3/skills/literature-review/references/review-workflow.md) | `SUMMARY → FULL_TEXT → ADD_PAPER` 的发现、全文核验、纳入分离 | 把“5–10 篇”或最大尝试次数变成通用 Gate | 扩展现有 `research_basis`，不新建 literature artifact |
| 同仓库：[backward-traceability/SKILL.md](https://github.com/lingzhi227/agent-research-skills/blob/9e6c085d65e3/skills/backward-traceability/SKILL.md) | 每个关键数字应回溯到 evidence→result artifact→code→raw data 的目标 | 在正文插入 `\hypertarget`、`\hyperlink` 和可见数字 ID；这正是当前不自然标识的来源之一 | 保留 Evidence Registry/sidecar 追踪，正文只留正常引用 |
| 同仓库：[paper-revision/SKILL.md](https://github.com/lingzhi227/agent-research-skills/blob/9e6c085d65e3/skills/paper-revision/SKILL.md)、[experiment-design/SKILL.md](https://github.com/lingzhi227/agent-research-skills/blob/9e6c085d65e3/skills/experiment-design/SKILL.md) | finding→受影响章节→动作→新证据/实验→复查；实验先最小可运行，再逐步扩展；记录“若失败意味着什么” | 新 Revision Agent；固定数据集数、seed 数和实验套餐 | 从 review report 派生 targeted revision packet；增强现有 validation obligations |
| 同仓库：[self-review/SKILL.md](https://github.com/lingzhi227/agent-research-skills/blob/9e6c085d65e3/skills/self-review/SKILL.md)、[paper-writing-section/SKILL.md](https://github.com/lingzhi227/agent-research-skills/blob/9e6c085d65e3/skills/paper-writing-section/SKILL.md) | 正确性 pass 后再做冗余/过渡 pass | 三 persona 加权打分；每段保留 `% Plan:` 脚手架 | 一个 semantic critic；反向纲要为派生视图 |
| XiaoMa Math Modeling Skill @ `5a85fe34ca1d`：[论文手/SKILL.md](https://github.com/XiaoMaColtAI/math-modeling-skill/blob/5a85fe34ca1d/references/roles/%E8%AE%BA%E6%96%87%E6%89%8B/SKILL.md)、[figure contract](https://github.com/XiaoMaColtAI/math-modeling-skill/blob/5a85fe34ca1d/tools/figure/static/core/contract.md) | 图是视觉论证；每 panel 只承担独特证据；先写核心结论、数据来源和导出契约 | “至少 8 张”“每类至少 3 张”、按章节拆 Agent | 扩展 Figure Contract；数量由 evidence coverage 决定 |
| Mathodology @ `11cdfd7cca66`：[award-gates/SKILL.md](https://github.com/sweetcornna/mathodology/blob/11cdfd7cca66/.claude/skills/mathodology-award-gates/SKILL.md)、[critic agent](https://github.com/sweetcornna/mathodology/blob/11cdfd7cca66/.claude/agents/mathodology-critic.md)、`lint_run.py`、`pdf_qa.sh` | stable finding ID；有限修订预算；最终 PDF 的页数、匿名、空白页、图表渲染检查；只修目标问题 | 常规运行的三 Blind Judge、0–100 分、奖项阈值、每阶段一份 YAML handoff | Review report、bounded revision、Submission QA |
| MathModelAgent：[coder.py](https://github.com/jihe520/MathModelAgent/blob/83d8783187a2d29dda1b046cb667009cc50c8203/backend/app/core/prompts/coder.py)；MetaMath：[preflight.js](https://github.com/LKQ667/metamath-harness/blob/1eb7a702ee6814cf73856544700fa8b48acd4218/plugins/dsh-mathmodel/src/preflight.js) | modeler→coder 可执行交接；阶段敏感 capability/evidence scope | 再造一套 Coder Agent、handoff artifact 或 runtime broker | 验证已有 Implementation Tasks、doctor 和 review scope，不重复实现 |

结论：当前最欠缺的不是更多角色，而是**结果如何被分配为一条完整论证、研究何时算覆盖充分、以及内部追踪如何不污染读者界面**。

## 4. 目标架构与 Gate 取舍

```text
Contest Profile / Safety
        ↓
Problem Analysis → M1 Modeling & Research Readiness
        ↓
Implementation Tasks → Coding → P1 Smoke
        ↓
Full Experiments → P2 Result Integrity
        ↓
Frozen Results → Evidence Registry
        ↓
Figure Contracts + Claim–Evidence Map
        ↓
Writing Spine / Section Briefs → W1 Paper Strategy
        ↓
One Paper Writer + on-demand micro-guidelines
        ↓
Whole-paper integration
        ↓
W2 Deterministic QA → Semantic Critic
        ↘ targeted revision（有限轮次）↗
        ↓
Competition-specific Submission QA → Final Freeze
```

Gate 不合并，职责收紧：

- **M1**：模型选择、研究义务和验证义务是否足以开工。
- **P1**：最小执行链是否真的运行；不评价完整结果。
- **P2**：完整实验、复现收据和冻结结果是否可信。
- **W1**：Claim–Evidence、图表和整篇论证是否已规划；不新增独立 Paper Strategy Gate。
- **W2**：确定性一致性和当前 review finding 是否关闭；Deterministic QA 是 W2 的实现，不是另一个 Gate。
- **Submission QA**：比赛特定的 PDF、匿名、页数、AI 声明和交付清单；与 W2 不合并。

常规比赛只运行一个 Semantic Critic。冲奖终稿可额外启用**一个**无历史上下文的 blind reviewer；只有在对评审方差做实验时才考虑多席，不把三席作为默认流程。

## 5. Artifact Contract 收敛

长期保存的核心事实仍限于现有主链：

| Artifact | 必要性 |
|---|---|
| `run_manifest` / competition profile snapshot | 比赛规则、运行状态和 AI usage 的审计入口 |
| `model_contract`（含 `research_basis`） | 模型、假设、候选选择、研究与验证义务 |
| `frozen_results` | 关键数值的唯一冻结版本 |
| `evidence_registry` | claim 到结果、代码、数据和文献的可核验映射 |
| `paper_plan` | 论文论证、Claim–Evidence、Figure/Table Contract |
| `submission_manifest` | 最终交付物、hash 和比赛特定检查结果 |

以下均不得升级为新的核心 artifact：

- `.harness/authoring/*.yaml`：可编辑的机器 authoring source。
- 一个隐藏 compile index：记录 source/output hash、schema ID 和 compiler version，用于发现 stale；可重建，不是事实真源。
- `IMPLEMENTATION_TASKS.md`、`WRITING_SPINE.md`、Section Brief、Setup Card、failure summary、targeted revision packet：全部为派生视图。
- 检索 scratch、段落草稿、Critic 内部推理：临时信息。

作者 Markdown、authoring YAML、compiled JSON 的关系为：

```text
人类决策笔记（Markdown）
        + 明确机器字段（.harness/authoring/*.yaml）
        ↓ compile + schema validation
权威运行合同（.harness/contracts/*.json）
```

## 6. 可执行纵向切片

### S0：真实赛题基线追踪（Competition P0）

**结果**：先用一份保留原貌的往届赛题项目跑当前流程，记录真实阻力，避免继续按静态审计猜问题。

**执行**：

1. 选择一个包含文献、模型、代码、图和完整论文的往届题；优秀论文只作赛前 pattern 参考，不作科学证据。
2. 跟踪 `model_contract → IMPLEMENTATION_TASKS → smoke → full → frozen_results → evidence_registry → WRITING_SPINE → paper → W2`。
3. 在实施记录中记录：人工补规则次数、默认上下文文件数、作者 Markdown 中机器载荷占比、检索覆盖缺口、内部标识命中、无法解释的 Gate、从 review 到修复的轮次。
4. 对建模与编码单独记录：Coder 是否需要自行发明公式/参数/边界条件，Implementation Tasks 是否能直接运行，smoke 是否覆盖最危险假设，full run、选择性重跑、敏感性和 paper-code conformance 是否有断点。
5. 保存原 PDF/文本作为 before 样本，不反向修改基线。

**验收**：每个后续切片至少对应一个已观察故障或明确合同风险。若某项只有“可能有用”而无证据，移出 P0。

### S1：发布安全与路径可移植（Release P0，独立执行）

**结果**：wheel 只含运行必需资源，在另一 Python 环境中可启动。

**主要文件**：

- `pyproject.toml`
- `scripts/qa/check_package_resources.py`
- `tests/test_package_resources.py`
- `integration/dsh/plugin/lib/index.js`
- `integration/dsh/native/checkpoint.host.js`
- `integration/dsh/preset/math-modeling/agent.cordis.yml`
- `tests/test_editorial_integrity.py`

**改动**：

1. 用显式运行资源 allowlist 替代 `references*` + 全类型 package-data 泛收集。
2. 明确 deny `references/precedents/local-sources/**`、本地论文、截图、临时产物和绝对本机路径。
3. 资源检查器验证“应有 sentinel 存在 + 禁止模式不存在”，不再要求磁盘上所有 reference 都进 wheel。
4. DSH 入口按环境变量、插件位置或已安装 entry point 解析 Harness；Python 测试使用 `sys.executable`。
5. 构建真实 wheel，解包检查后在干净临时目录运行 `harness --help` 与最小 `doctor`。

**验收**：

```powershell
python -m pip wheel . --no-deps -w dist-test
python -m unittest tests.test_package_resources tests.test_editorial_integrity -v
ruff check scripts/qa/check_package_resources.py tests/test_package_resources.py tests/test_editorial_integrity.py
```

STOP：若排除规则使 schema、profile、必要 reference 或 assets 缺失，不用 fallback 静默继续，先修正发布清单。

### S2：干净的作者工作面（Competition P0）

**结果**：新项目的五类作者 Markdown 不再嵌入大段 JSON/YAML。

**主要文件**：

- `scripts/human_surface.py`
- authoring plane 相关 schema/迁移逻辑
- `tests/test_human_surface_cli.py`
- README/SKILL 的 authoring 说明

**改动**：

1. 新项目将结构化输入写入 `.harness/authoring/*.yaml`；作者 Markdown 只保留目标、理由、假设、未决问题和下一步。
2. compiled JSON 继续是 Gate 消费的运行真源；禁止手改 JSON。
3. 增加一个隐藏、可重建的 compile index，记录 source path/hash、output path/hash、schema ID 和 compiler version；不写时间戳，避免无意义 diff。
4. 迁移期双读：旧项目可读取嵌入 block；执行显式 migrate 后写出 YAML 并移除 block；新 `init` 不再生成嵌入 block。
5. 对 authoring source 缺失、schema 不合法或 hash stale 给出一条直接的修复命令，不生成平行副本。

**验收**：

- 新 init 的作者 Markdown 中 `Machine contract source` 与 fenced contract 为 0。
- 迁移运行两次幂等；迁移前后的 compiled JSON 语义一致。
- 人工编辑 YAML 后旧 JSON 必须被识别为 stale。
- 不新增顶层 md/json 文件。

### S3：读者界面完整性（Competition P0）

**结果**：内部定位继续可审计，但不进入可见正文、公式、图或最终 PDF。

**主要文件**：

- `scripts/qa/check_writer_package.py`
- `scripts/qa/check_paper_style.py`
- `schemas/paper_plan.schema.json`
- Figure binding / rendered PDF QA
- `tests/test_writer_patterns.py`、figure/PDF QA tests

**改动**：

1. 以当前 project 的 claim/unit/locator 注册表为准检查精确 ID，并硬失败 `ANCHOR-*`、`LOC-*`、注册过的内部 ID、`\audit{...}` 调用及定义。
2. TeX 注释、不可见 label 和 sidecar 可保留 locator；可见源和 PDF 抽取文本不得出现。
3. 不用宽泛的 `R-*` 或“Harness/Gate”等普通词硬拦正文，避免误伤正常数学符号和必要 AI 声明。
4. Figure Contract 增加可选 `audience: scientific_argument | submission_disclosure | internal_audit`。新项目必须生成；旧合同 W1 告警；进入 W2 正文的图必须完成分类。
5. W1 主动扫描每个 argument unit 的视觉机会：定量比较优先代码图/表；难以用文字讲清的机制、场景或流程才创建 conceptual illustration contract，并由现有 tool router 选择 Draw.io/PPTX 或 Agent 原生生图能力，无需用户再次提醒。
6. 原生生图只用于非定量解释图，不承载精确数值、比例或未经核验的科学结构；每张图仍需声明要证明什么、使用什么证据、为什么用图及对应 claim。
7. `internal_audit` 图进入 reader-facing body 时硬失败；图数仍由 claim/evidence coverage 决定。
8. 最终 PDF 的页数、匿名、空白页、重复 caption 和可见标识由确定性 QA 检查。残句、过渡和“像不像人”只进入 Semantic Critic，不用脆弱正则升级为 Gate。

**验收**：golden TeX/PDF 覆盖“宏吞词”“内部 ID 可见”“注释 locator 合法”“internal_audit 图误入正文”“正常数学 R 符号不误报”五类用例；真实题 W1 必须输出视觉机会扫描结论，即使结论是“无需概念图”。

### S4：Argument-first Writer 与有限修订（Competition P0）

**结果**：复用现有 Writing Spine，让每一节推进整篇论证，而不是按问题重复“建模—结果—验证—解释”模板。

**主要文件**：

- `scripts/views/writing_spine.py`
- `scripts/claims/compile_writer_package.py`
- `scripts/human_surface.py::authoring_context`
- `references/router.md`
- 现有 `references/writing/*.md`
- review report/targeted revision 的派生视图

**改动**：

1. 保留现有 Writing Spine、Section Brief 和 evidence allocation；补充 Nature 式 result allocation 与反向纲要，不创建第二套 outline。
2. 默认 Writer context 只加载：Writing Spine、当前 Section Brief、当前草稿和一份任务相关 micro-guideline。合同、冻结结果和其他 reference 通过明确 locator 按需读取。
3. 删除 writer package 中每问固定四段的结构命令；每个 argument unit 声明其目的、前提、证据、解释、边界和与下一单元的关系。
4. `canonical_recommendation` 只约束决策内容、数值和证据，不要求整句逐字复制。
5. router 接通现有 `manuscript_logic.md`、`abstract_guidelines.md`、`consistency_guidelines.md`、`cumcm_empirical_style.md`；不再新建重复 reference。
6. 全文完成后生成派生 reverse outline：段落主张→section thesis→central thesis；无法映射的段落删除、移位或补证据。
7. 从 review finding 派生 `finding → section → action → required evidence/experiment → recheck` 修订包。正常流程一轮，冲奖终稿最多两轮；finding 数量未下降时停止并交给人判断。

**验收**：

- 同一结果不会在摘要、结果、结论中以不同数字或不同决策出现。
- 每个正文段落可映射到一个 argument unit；不能映射的段落有明确处理。
- 摘要所有关键结果来自 Evidence Registry。
- Semantic Critic 能逐项回答：中心论点是否清楚、段落是否推进、承诺是否兑现、证据是否解释、边界是否适当。
- 不用 n-gram 差异充当“自然写作”的确定性证明。

STOP：若实现方案需要 Abstract/Result/Conclusion 等新 Agent，或把 Critic 的主观分数写成 Gate，退回本切片重新设计。

### S5：覆盖驱动的文献调研（Competition P0）

**结果**：保留现有真实性 Gate，补上研究范围、纳入理由和停止依据。

**主要文件**：

- `schemas/model_contract.schema.json`
- `scripts/qa/check_modeling_plan.py`
- `scripts/human_surface.py` 的 research compiler
- 相应 modeling-plan/human-surface tests

**改动**：

1. 在既有 `research_basis` 内区分 discovery candidate、full-text verified core 和 excluded item；不建新的 evidence JSON。
2. 按题目需要声明 research obligations：机制、假设、参数、基线/模型选择、验证、失败模式。每项状态为 `covered | gap | waived | not_applicable`，并给出 evidence IDs 或理由。
3. 每条纳入/排除记录保留原因；综述、原始方法、应用研究标注角色，避免把综述当作原始证据。
4. ready 状态必须有 stop reason：覆盖已满足、边际新增信息很低，或带风险说明的赛时 time-box/waiver。
5. 查询与来源多样性只在造成关键 obligation gap 时阻断；否则是告警。禁止固定“3 个查询、2 个库、2 篇全文”等通用配额。
6. 往届优秀论文继续隔离为 precedent pattern，只能回答“怎样组织”，不能支持科学 claim、参数或模型有效性。

**验收**：

- metadata verified 但 content 未核验的论文不能支持 claim。
- 只有一篇真实论文但关键 obligation 未覆盖时，M1 不能伪装 ready。
- 小众题在合理 time-box 后可用明确 gap/waiver 继续，不制造文献。
- schema 对旧项目可读；新项目与迁移后项目执行新义务。

### S6：规则指纹与公共操作面（P1）

**结果**：上游 Agent 能判断规则是否变化，不必每轮无条件重读全部 SKILL。

**改动**：

1. 运行时计算 `ruleset_id`，输入为规范化后的 `SKILL.md`、schemas、competition profiles、policy/contract/writing 核心 references。
2. 排除 precedents、cards、local-sources、generated views 和运行产物；不把自 hash 写进 SKILL frontmatter。
3. `status --json`、`context --json` 返回 `ruleset_id` 与命中范围。上游缓存 id 相同可复用规则理解；Gate 和 contract freshness 仍照常检查。
4. 不增加 `--skip-rules-reload`；该开关会把上游记忆状态错误地变成 Harness 真相。
5. README 主流程只讲 `init → status → prepare → execute → check → submit` 六类动作；旧命令保留在 advanced/compat 附录，不做破坏性删除。

**验收**：核心规则变化时 id 必变，precedent/local source 变化时 id 不变；两个干净 checkout 产生相同 id。

### S7：真实赛题闭环复验（P0 收尾）

**依赖**：S2–S5；S1 独立验收，S6 可后置。

1. 用 S0 同一赛题重新跑完整链，禁止复用旧 Gate PASS、receipt、frozen results 或 review。
2. 比较 before/after：规则重载次数、作者笔记机器载荷、文献 obligation coverage、正文标识、Writer 默认上下文、review 修订轮次和最终可读性。
3. 重新执行模型合同→Implementation Tasks→smoke→full→sensitivity/replay，确认当前建模与编码机制在真实题中可用；只有复验暴露具体缺口时，才新开 modeling/coding 计划。
4. 由一名未参与写作的人只看最终 PDF，检查中心论点、结果解释、图表必要性和人类可读性；不提供 Harness 日志以免锚定。

**完成条件**：确定性 QA 全绿；无内部痕迹；所有 headline claim 可追溯；关键 research obligation 无伪覆盖；盲读者能复述模型选择、主要结论、证据和限制。一次通过只能证明该 archetype，可在 P1 再选不同题型验证泛化。

## 7. Reviewer 职责与修订预算

| 层 | 只负责 | 不负责 |
|---|---|---|
| Deterministic QA | schema、hash、数字/单位、引用状态、可见内部 ID、图绑定、PDF/提交规则 | 文章是否优美、创新性分数、段落是否像人 |
| Semantic Critic | 论证跳跃、解释不足、承诺未兑现、边界失衡、图是否必要、paper-code 语义一致 | 重新计算 hash、伪造 Gate PASS、用主观判断替代格式检查 |
| Optional Blind Reviewer | 冲奖终稿的独立读者体验与最大弱点 | 常规每阶段审查、三席常驻打分 |

所有 finding 使用稳定 ID。修订只针对未关闭 finding，并保留“不要回退”的已正确内容；正常一轮、冲奖最多两轮。达到预算或 blocker/high 数量不下降时停止，生成面向人的决策摘要，不无限自循环。

## 8. 优先级

### 下一次比赛前必须完成

1. S0 真实赛题基线。
2. S2 + S3：作者/读者界面清理。
3. S4：Argument-first Writer。
4. S5：文献 obligation coverage。
5. S7：同题闭环复验。

### 下一次公开发布前必须完成

- S1：wheel 资源白名单与路径可移植。

### 实战验证后加入

- S6：ruleset id 与 README 公共操作面收敛。
- 第二种题型的闭环 benchmark。
- 冲奖模式下一个 blind reviewer。

### 未来平台化再考虑

- 异步 MCP 执行与进度流。
- 多模型 reviewer 方差实验。
- 远程 provider/runtime broker。

## 9. 全局验证与实施纪律

每个切片一个 scoped commit；先跑相关测试，再跑全量：

```powershell
python -m unittest discover -s tests -q
python scripts/harness.py --help
ruff check <CHANGED_PYTHON_FILES> <RELATED_TEST_FILES>
git diff --check
```

只有完整执行后才能记录“全量通过”。历史的 411/411、受影响链 111/111 或本轮早先的 268 项结果不能替代新工作树的复验。

实施期间满足任一条件即 STOP 并回到计划：

- 为一个切片新增顶层 Agent、顶层 Gate 或核心 artifact。
- 用固定论文数、模型数、图数或评分阈值替代 coverage。
- 把 locator、review ID 或 planning 注释写入 reader-facing 内容。
- schema 变化没有兼容读取、迁移和回归测试。
- 确定性 QA 开始裁决“像不像人”等语义问题。
- 为通过测试添加未经复现的 fallback、skip 或重复校验。

## 10. 计划审查结论

| 维度 | 旧计划 | 本次修订 |
|---|---:|---:|
| 事实准确性 | 2/5 | 4.8/5 |
| 范围收敛 | 2/5 | 4.8/5 |
| 可执行性 | 3/5 | 4.5/5 |
| 可测试性 | 3/5 | 4.6/5 |
| 上游依据 | 2/5 | 4.8/5 |

修订后的核心变化是：

- 把已经存在的 Writing Spine、Implementation Tasks 和 cards 消费路径从“待实现”中删除。
- 把真实赛题 before/after tracer 提到第一位，而不是功能改完再找案例证明。
- 把正文标识、authoring 分层、Writer 逻辑和文献覆盖拆成可独立验收的纵向切片。
- 采纳 Nature、Research Writing、Mathodology 等项目的机制，同时明确拒绝固定配额、可见 trace marker、三席常驻 Reviewer 和阶段 YAML 膨胀。
- 将 release packaging 单列为安全泳道，避免它挤占下一次比赛的写作改进，但要求公开发布前完成。

仍需在 S0 启动时确定唯一的基线赛题与只读 before 副本；这是实施输入，不影响架构取舍。各切片的精确函数级任务在开始该切片时写入实施记录，避免计划阶段提前制造一组很快过时的 ticket 文档。

在开始实施前，只需确认按 S0→S2/S3→S4→S5→S7 的比赛主线推进；S1 可并行，S6 后置。
