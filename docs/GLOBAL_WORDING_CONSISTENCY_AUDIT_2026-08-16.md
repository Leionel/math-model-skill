# HISTORICAL DESIGN / EXECUTION RECORD
> Do not use this file as current operational instruction.
> Current truth starts from `SKILL.md` and `references/router.md`.

# 全局表述、术语与声明一致性审计（2026-08-16）

- 审计对象：`math-modeling-skill-sion`（Math Modeling Evidence Harness），工作区当前状态（含未提交修改，分支 `agent/math-modeling-harness`）。
- 审计方式：只读。覆盖 `SKILL.md`、`README.md`、`docs/` 全部 Markdown、`references/` 全部契约/规范、`schemas/` 的 title/description/enum/required、`scripts/` 的 docstring 与 CLI 参数、`tests/` 的测试名与断言、`competition_profiles/`、`assets/templates/`、`agents/openai.yaml`、`vendor/template_sources.json`、`.workbuddy/memory/`。`vendor/upstream/` 为第三方上游，仅在核对融合声明时引用。
- 交叉核对方法：每条能力/状态声明都对照（a）实现文件是否存在、（b）是否接入 `check_gates.py` / `run_deterministic_qa.py` 主流程、（c）默认档位是否启用、（d）是否有对应回归测试、（e）是否有真实运行证据。
- 本审计未修改任何既有文件；本文档为新增文件。

---

## 1. 总体结论

**全局表述水平整体较高，属于"自我边界意识很强"的项目**：绝大多数能力声明都配有明确的 non-claims（如 `docs/MATH_HARNESS_IMPLEMENTATION_STATUS.md:220-227` "当前不承诺的能力"、`SKILL.md:59` "它们不能自动证明代数等价性"、`references/workflow/math_correctness_profile.md:47-51`），静态检查没有被写成正确性保证，"测试通过"没有被写成端到端可用（`docs/NIPT_BATCH_A_D_ACCEPTANCE_2026-08-15.md:42` "本地单元测试通过不能替代 Batch E benchmark"），W2/S1/F1 的语义分层（内容就绪 ≠ 可提交 ≠ 已提交）在 `SKILL.md:72`、`references/submission/submission_freeze.md:5-7`、`gate_policy.md:26-27` 三处保持一致。文档与实现的一致性水平在 90% 以上：抽查的全部 CLI 参数、全部 NIPT 引用的测试名、strict math profile、模板兼容审计数据均能在代码/测试中找到对应物。

**但仍存在 2 个 P0、5 个 P1 问题**，集中在三类：

1. **少数入口指令与代码默认值/真实能力冲突**（最重要）：
   - `SKILL.md:37` 声称 S1 阶段"自动代码与 PDF 匿名脱敏"，但 `scripts/` 中不存在任何匿名化脚本，且 `references/submission/submission_freeze.md:17` 明确规定匿名性属于无法自动判断、必须人工确认的项目——入口文档与提交规范互相矛盾，且方向是把人工义务写成自动能力。
   - `SKILL.md:73`/`README.md:51` 写"新项目默认 `integrity_mode=research`"，但 `schemas/run_manifest.schema.json:22` 的 default 是 `"dev"`，`scripts/qa/check_gates.py:293` 缺省回退也是 `dev`。而 formal M1（research-first 证据链检查，`check_gates.py:559,597`）只在 `research/submission/strict_math` 下运行——省略该字段的 Agent 实际运行在弱得多的 dev 档，却以为自己在正式研究链上。

2. **"已实现"粒度不一致造成的能力误判**：`MATH_HARNESS_IMPLEMENTATION_STATUS.md` 的"已实现能力"表中，公式回放（:43）、展示值安全（:44）、源码—PDF 一致性（:46）三行没有写明"仅显式档位/传参才启用"，而同表其他行（:45、:65、:69）写了。真实默认行为是 `run_deterministic_qa.py:237-240` 在未传 `--require-formula-replay` 时对公式回放 `--skip-if-absent`（未声明即跳过）——读者会以为数值默认被回放复核过。

3. **历史文档缺 superseded 标注 + 引用断链**：`RESEARCH_INTEGRITY_ARCHITECTURE_AUDIT.md`（2026-08-08 NO-GO 审计）描述的"freeze 信任 ok=true、Gate 放行失败 run"已被修复，但文档无任何"已过时/已被修复"横幅；`NIPT_BATCH_A_D_ACCEPTANCE_2026-08-15.md:3` 引用的源审计文件 `Math_Model_Harness_Current_Audit_and_Targeted_Hardening_2026-08-15.md` 不在仓库中；`README.md:495` 两个相对链接缺 `docs/` 前缀。

**是否存在系统性过度承诺：否。** 绝对化词语（保证/确保/完全/自动/production-ready/end-to-end/submission-ready）经全文检索，绝大多数出现在 non-claims 或"解锁条件表"中（如 `editorial_style.md:33-45` 强词解锁表）。孤立的例外见问题清单 P0-1（"自动…脱敏"）、P2-9（"保证…可追溯"）、P2-14（提案文档"确保…完备"）。

**最容易误导 Agent 的三处问题：**
1. `SKILL.md:37`"自动代码与 PDF 匿名脱敏"——导致跳过人工匿名检查并声称已完成（P0-1）。
2. `SKILL.md:73` vs `run_manifest.schema.json:22` 默认档位冲突——导致静默降级到 dev、绕过 formal M1（P0-2）。
3. 状态表 `MATH_HARNESS_IMPLEMENTATION_STATUS.md:43/44/46` 缺"显式启用"限定——导致 Agent 以为公式数值回放/展示值复核/源码—PDF 一致性默认执行，形成虚假的数值可信度（P1-3）。

---

## 2. 核心术语表

| 术语 | 当前用法 | 冲突位置 | 建议定义 | 建议统一写法 |
|------|----------|----------|----------|--------------|
| Gate（门） | M1/P1/P2/W1/W2/S1/F1 七个决策点；状态 `pending/pass/fail/blocked`（`run_manifest.schema.json` `$defs.gate`） | 无实质冲突；但"谁写入 status、何时写入"无文档说明（见 P1-4） | 对当前 artifact 集的阶段性判定；`pass` 仅对当前哈希/证据有效（`gate_policy.md:29` 已有此句） | 保留 Gate；在 gate_policy 增加"status 由执行者在 checker 返回 ok 后写回 manifest；check_gates 负责复验"一句 |
| QA | `run_deterministic_qa.py` 输出的确定性检查集合；check 标签如 `contracts/contest_safety/consistency/citations`（`check_gates.py:430-460`） | 无冲突 | 保留 | |
| review / audit / Critic | review=人对 artifact 的审阅（human checkpoint、visual review）；audit=一次性对照审计文档（docs/ 下多份）；Semantic Critic=证据 aware 的二元审查（`semantic_critic_rubric.md:3`） | "audit" 既指历史审计文档又指 vendor 许可审计（`template_sources.json` 的 `audited_at`），语义可分 | 文档级"审计"统一加日期后缀（现状已如此）；运行时只用 review/critic | 保留 |
| implemented / 已实现 | 状态表标记："当前仓库有脚本/Schema/测试支持，可以在项目目录中运行"（`MATH_HARNESS_IMPLEMENTATION_STATUS.md:30`） | 同表内部分行未区分"默认启用"与"显式档位启用"（P1-3） | "已实现 = 有代码 + 有测试 + 可运行"；是否默认阻断须另行标注 | 每行"当前作用"列补"默认启用 / 显式 strict / 显式 flag"三选一标记 |
| 本轮新增 | 状态表标记（`:31`），锚点是文档头部"更新时间：2026-08-15"（`:3`） | 多轮迭代后"本轮"会漂移；NIPT 文档又引入"已覆盖"（`:3`）、"P1 待办"（`:27`）两个表外标记 | 按日期批次命名 | 用 "Batch 2026-08-15" 类日期批次名替代"本轮" |
| 已覆盖（NIPT） | "有现有检查器、可复跑的负例回归，以及正式 QA/Gate 的入口；不表示模型自动证明正确，不表示 Batch E 完成"（`NIPT_...md:3`） | 定义仅存在于该文档，未进入状态表词汇表 | 定义本身良好 | 将该定义并入状态文档词汇表 |
| validated | `data_contract.status=validated`（schema enum `draft/validated/failed/superseded`） | 与 `implementation_map.status=verified`、`problem_snapshot.status=confirmed` 并存——同类"人审通过"用了三个词 | 人审通过类状态按 artifact 各自保留，但需集中词汇表声明三者等价层级 | 集中 glossary（见第 7 节） |
| verified | 至少 4 种语义：文献三重核验（`evidence_registry.verification_status=verified`）、模板实际使用验证（`template_contract.status=verified`）、实现映射验证（`implementation_map.status=verified`）、派生特征血缘验证（`derived_feature_lineage.status=verified`） | 无集中定义；`template_contract` 的 `verified` 不要求附构建回执（assets 模板即预置 verified，见 P2-10） | 每种 verified 都应能指到证据；模板 verified 应要求引用 build/PDF 回执路径 | schema 增加字段说明或 evidence 指针 |
| passed / PASS | `pass` 用于 Gate/figure qa；`PASS/FAIL/ERROR` 大写专用于验证义务 verdict（`validation_report/frozen_results` schema） | 无冲突，大小写约定清晰 | 保留 | |
| claimable | 由冻结件派生："只有独立重算后逐项 PASS 的 claimable=true 结果可进入 Evidence Registry"（`SKILL.md:68`；`validation_obligations.md:71-73`） | 无冲突，测试锁定（`test_p0_harness.py:483,501`） | 保留 | |
| submission-ready | `run_manifest.status=submission_ready`，仅表示 S1 通过（`check_gates.py:1217-1223` 校验） | 无冲突；`submission_freeze.md:5` 明确"F1 只证明本地最终包不可变，不证明门户已接受" | 保留 | |
| content_ready | `run_manifest.status=content_ready` = W2 通过 = 内容就绪 ≠ 可提交 | 无冲突 | 保留 | |
| frozen | 结果冻结（append-only、可含 FAIL）与 manifest 状态 `frozen` 两处使用 | "冻结 ≠ 结果合理"已在 `SKILL.md:68`、`validation_obligations.md:69-73` 说明 | 保留 | |
| reproducible / 可复现 | `editorial_style.md:45` 将"完全可复现"列为需证据解锁的强词 | 无冲突（处理正确） | 保留 | |
| integrity_mode | `dev/research/submission` 三档，控制哈希强度 | **文档默认值（research）与 schema 默认值（dev）冲突**（P0-2） | 统一默认值并写明各档触发的 Gate 差异 | 见 P0-2 修复建议 |
| enhanced_integrity_profile / math_correctness_profile / editorial_semantics_profile | 三个独立 opt-in 开关，均为 default off/baseline（schema `:21-23`） | `README.md:51` 已警告"不应和哈希模式混为一谈"；三者差异需读者拼装多文档 | 保留三开关，但建议在 run_manifest schema 增加字段 description | 见第 7 节 |
| template fork | "只复制 main.tex 和 .cls"被多处明确否定（`README.md:140`、`SKILL.md:240`、`template_adapter.md:5`） | 无冲突 | 保留 | |
| artifact / evidence / claim | 命名一致：claim 只在 paper_plan 维护（`SKILL.md:70`）；evidence 唯一 registry（`:69`） | 无冲突 | 保留 | |
| battle test | 仅 `NIPT_...md:35` 出现，未定义 | 孤例英文术语 | 若保留，定义为"真实输入的端到端能力测试（Batch E）" | 或改写为中文"真实战场测试（Batch E）"并定义 |
| mandatory / recommended / optional | 文档用 必须/应/建议/可选/可以/显式；无 MUST/SHOULD/MAY 形式化分级 | 强制程度依赖语气词，个别地方粒度不一致（P1-3） | 引入 MUST/SHOULD/MAY 分级（见第 7 节） | |

**易混状态对照（用户清单逐项核验）：**

| 状态对 | 项目现状 |
|--------|----------|
| 文件存在 ≠ 功能已实现 | 已明确（`SKILL.md:74`"模板文件在目录里不等于用了模板"；有 `check_template_usage.py` + `test_template_usage_rejects_declared_template_that_is_not_used`） |
| 已实现 ≠ 已接入主流程 | **部分明确**：strict-math 系列已接入 `check_gates.py`，但状态表未标"默认不启用"（P1-3） |
| 已接入 ≠ 已验证 | 明确（Gate 从声明输入独立重跑，`check_gates.py:62-220`；`test_math_profile_gate.py:15`） |
| 单元测试通过 ≠ 端到端验证 | 明确（`NIPT_...md:42`） |
| Gate PASS ≠ 数学结论正确 | 明确（`MATH_..._STATUS.md:24`；`math_correctness_profile.md:47-49`） |
| PDF 编译成功 ≠ 论文质量合格 | 明确（三层视觉 QA，`visual_review.md:3-9`；`figure_design.md:87`） |
| 研究草稿完成 ≠ 可以提交 | 明确（W2/S1/F1 分层） |
| 结果冻结 ≠ 结果合理 | 明确（FAIL 可冻结、不可 claimable） |
| 文献已列出 ≠ 文献支持方法 | 明确（`literature_evidence.md:3-14` 三步核验；`model_planning.md:19`） |
| Agent 声称完成 ≠ 有运行证据 | **baseline 档有残留缺口**（P1-4）：仅 enhanced/strict 档有独立重跑；baseline 的 deterministic 报告与 reviewer 状态本质仍是 manifest 声明性输入，文档未明示这一边界 |

---

## 3. 表述问题清单

严重度定义：P0 = 可能导致错误执行、绕过 Gate、伪造结果或错误提交；P1 = 明显流程偏差或能力误判；P2 = 术语、风格、可读性或轻微一致性问题。

### P0

| # | 严重度 | 文件及行号 | 原文 | 问题类型 | 为什么有问题 | 建议改写 |
|---|--------|------------|------|----------|--------------|----------|
| P0-1 | P0 | `SKILL.md:37` | "S1/F1 …必做动作：自动代码与 PDF 匿名脱敏、AI 使用报告生成、支撑包整理与当届提交检查" | 过度承诺 + 与规范文档冲突（把人工义务写成自动能力） | ① `scripts/` 全目录无任何匿名化/脱敏实现（grep `anonym\|匿名` 于 `scripts/**/*.py` 为 0 命中）；② `references/submission/submission_freeze.md:17` 明确规定"匿名性、字体/裁切、最终渲染……无法可靠从当前 stdlib 脚本判断的项目，必须列入 `required_manual_checks` 并由 S1 human checkpoint 确认"；③ `_base_cumcm.yaml` 的 `anonymous_rules` 只是 profile 配置，无执行脚本。Agent 依入口文档会认为存在自动脱敏工具，从而跳过人工匿名核验并声称已完成——匿名性是提交合规红线，可能直接导致含身份信息的错误提交 | "必做动作"改为："整理支撑包；按 profile 逐项完成人工检查（匿名性、AI 标注等属 `required_manual_checks`，无法自动判定）；从 `ai_usage[]` 生成 AI 使用报告草稿并经人工确认；运行当届提交检查" |
| P0-2 | P0 | `SKILL.md:73`（另见 `README.md:51`）vs `schemas/run_manifest.schema.json:22`、`scripts/qa/check_gates.py:293` | SKILL："新项目默认 `research`，提交前升级为 `submission`"；schema：`"integrity_mode": {..., "default": "dev"}`；check_gates：`manifest.get("integrity_mode", "dev")` | 文档与代码默认值冲突（静默降级、绕过主质量门） | formal M1（research-first 证据链检查 `--formal --strict`）只在 `research/submission/strict_math` 下运行（`check_gates.py:559,596-597`）。Agent 按 SKILL 指引省略该字段（以为默认就是 research），实际落入 dev：formal M1、research/submission 专属人工检查（`:559-575`）、W1 registry 绑定（`:884`）等全部不生效，且没有任何报错提示 | 二选一并全仓统一：要么把 schema/代码默认改为 `research`（推荐，与文档意图一致），要么把 SKILL/README 改为"必须显式写 `integrity_mode`；未写时系统按 `dev` 处理（不触发 formal M1）"。同时建议 `check_gates.py` 对 status≠dev 而 integrity_mode 缺失的情况输出 warning |

### P1

| # | 严重度 | 文件及行号 | 原文 | 问题类型 | 为什么有问题 | 建议改写 |
|---|--------|------------|------|----------|--------------|----------|
| P1-1 | P1 | `SKILL.md:186` vs `references/visualization/diagram_workflow.md:7`、`references/contracts/figure_contract.md:9`、`schemas/diagram_spec.schema.json`（`source_format` enum） | SKILL："总览图、任务流程图和模型框架图必须先生成结构化 `diagram_spec.json`，再通过 `generate_drawio.py` 生成 native `.drawio`"；diagram_workflow："Figma、PowerPoint 或其他矢量编辑器可以作为人工绘制后端，但必须保留等价的可编辑源文件"；figure_contract/schema：`source_format` 合法值含 `svg/figma/pptx` | 同一约束三处强度不同（MUST 冲突） | 入口文档最严格且未提替代路径，契约文档与 schema 允许 draw.io 以外的可编辑矢量后端。Agent 只读 SKILL 会把合法的 Figma/PPT 源判为违规而返工，或误以为 `check_diagram_spec.py` 只接受 `.drawio` | SKILL 改为："必须先写结构化 `diagram_spec.json`，默认经 `generate_drawio.py` 生成 native `.drawio`；如使用 Figma/PPT 等其他可编辑矢量后端，须在 spec 中声明 `source_format` 并保留等价可编辑源（见 Diagram Workflow）。无论后端，均不得以 Mermaid/Python 成品或 AI 位图作为最终图" |
| P1-2 | P1 | `docs/NIPT_BATCH_A_D_ACCEPTANCE_2026-08-15.md:3` | "本文把 `Math_Model_Harness_Current_Audit_and_Targeted_Hardening_2026-08-15.md` 中的 T-NIPT-01～14 映射到……" | 引用不存在的文件（验收依据不可追溯） | 该文件不在仓库任何位置（全盘 `find` 无命中）。T-NIPT 编号、Batch A–E 划分、"旧检查为什么会漏掉"的原始裁决均无法复核；矩阵中"已覆盖"结论失去了可审计的源头 | ① 将源审计文档提交进仓库（docs/），或 ② 在本文头部注明"源审计为外部输入，编号定义以本文表格为准"，并把每个 T-NIPT 的失败模式描述补全为自包含 |
| P1-3 | P1 | `docs/MATH_HARNESS_IMPLEMENTATION_STATUS.md:43`（另涉 :44、:46，对照 :45、:65、:69） | ":43 结构化公式回放（本轮新增）……对声明的标量公式执行安全数值回放……"；未标明启用条件 | 强制程度标注不一致（能力误判） | 真实默认行为：`run_deterministic_qa.py:237-240` 未传 `--require-formula-replay` 时以 `--skip-if-absent` 运行（未声明回放案例即跳过）；pdf 数学一致性需 `--require-pdf-math-consistency --pdf`（`:150`）；展示值安全需提供 presentation contract（`:274`）。同表 :45 行写了"可选正式模式"、:65/:69 行写了"默认……显式 profile 才阻断"，而这三行没写。Agent 会认为公式数值在默认 QA 中已被回放复核、PDF 与源码一致性默认受查——形成没有发生过的数值可信度 | 三行"当前作用"列统一补注："默认 skip-if-absent；`math_correctness_profile=strict` 或显式 `--require-*` 才阻断" |
| P1-4 | P1 | `references/workflow/gate_policy.md:31`（对照 `SKILL.md:234`、`artifact_contracts.md:24`） | "增强 profile 的 W2 Gate 会从 deterministic QA 报告声明的输入重建一次临时 QA；……重算失败不能通过手改 `ok=true` 绕过" | 关键边界只写了正面（隐含 baseline 档可被手写报告通过但未明示） | 所有"不能手改 ok=true 通过"的表述都限定在 enhanced/strict 档（`check_gates.py:62-220` 的重跑仅由 `enhanced_integrity_profile/strict_math/editorial_semantics` 触发，`:604,1092`）。baseline 档 W2 只校验 manifest 声明的 reviewer 状态 + 报告文件内容（`verify_review`，`check_gates.py:430-460`）——一个手工编写、含必需 check 标签与 `ok=true` 的 JSON 报告在 baseline 档可通过。读者（Agent 或人）易把"防手改"理解为全档位属性，从而过度信任 baseline W2 | 在 gate_policy 增加一段："baseline 档的 deterministic 报告与 reviewer 状态是声明性输入，check_gates 只做存在性/哈希/标签校验；防手改的独立重跑仅存在于 enhanced/strict 档。正式研究链建议开启 enhanced 或 strict profile" |
| P1-5 | P1 | `docs/RESEARCH_INTEGRITY_ARCHITECTURE_AUDIT.md:4`（另 :24、:30、:54-57） | "审计结论：**NO-GO——当前产物可以作为自动建模与成文原型，但不能标记为'研究链已验证'的竞赛终稿**"；:30 "Validation 接受自报状态，不重算 acceptance"；:56 "check_gates.py --strict M1/P1/P2/W1/W2 全部 pass"（指当时放行了失败 run） | 旧文档与当前实现不一致且未标 superseded | 该审计描述的缺陷（freeze 信任 `ok=true`、Gate 放行 `498→550` 反例）已由 `evaluate_obligations.py`、freeze 重算与回归测试修复（`tests/test_p0_harness.py:442,483`；`validation_obligations.md:65-75`）。但文档只有"审计日期：2026-08-08"，无任何"结论已过时/对应 P0 已修复"横幅；且其中引用的 `build_paper.py/collect_results.py/refresh_q4.py/conform_contracts.py` 均不在本仓库（属外部生成运行目录）。新 Agent 可能：① 把 NO-GO 当作现状；② 找不到被引用脚本；③ 把"Gate 全 pass"的旧输出当作当前 Gate 不可信或可欺骗的证据 | 文档头部加横幅："历史审计快照（2026-08-08）。其中 P0 研究语义缺陷已在 Wave 1（见 REVISED_IMPLEMENTATION_ROADMAP）修复并有回归测试；引用的运行目录脚本不在本仓库。"同类处理建议适用于 `HARNESS_INTEGRATION_ANALYSIS.md`（其 :3 已有部分说明，可再明确） |

### P2

| # | 严重度 | 文件及行号 | 原文 | 问题类型 | 为什么有问题 | 建议改写 |
|---|--------|------------|------|----------|--------------|----------|
| P2-1 | P2 | `README.md:51` 对照 :53-61 表格、"references/contracts/artifact_contracts.md:26" | "基础兼容 profile 维护五个核心 JSON"紧接列出 6 行表格（含 `submission_manifest.json`） | 计数与清单不符 | artifact_contracts.md:26 的准确表述是"五个核心 contract……只有最终提交阶段再增加不可变 manifest"。README 表格把 F1 产物并进"五个"标题下，读者会数出 6 个 | 表格拆分：前 5 行标"核心 artifact"，`submission_manifest.json` 单独标"F1 阶段追加" |
| P2-2 | P2 | `README.md:495`（对照 :96-105、:507） | "见 [开源机制整合审计](HARNESS_INTEGRATION_ANALYSIS.md) 和 [上游长处复核](UPSTREAM_STRENGTHS_REVIEW_2026-08-13.md)" | 相对链接断链 + 同文件内路径写法不一致 | 两文件实际位于 `docs/`；同文件 96-105 行与 507 行都正确使用了 `docs/` 前缀。Agent 按链接找文件会失败 | 补 `docs/` 前缀 |
| P2-3 | P2 | `.workbuddy/memory/2026-08-13.md:3` | "依据 `math_model_skill_private_competition_roadmap.md` 完成 Phase A P0 全部六项" | 引用不存在的文件（低影响） | 该 roadmap 不在仓库；memory 文件的"全部六项"无从核对 | 在 memory 中注明来源为外部会话，或提交该 roadmap |
| P2-4 | P2 | `docs/MATH_HARNESS_IMPLEMENTATION_STATUS.md:245-257` | "## Strict math correctness profile (implemented this round)"（整节英文） | 语言体系混杂 + 同一规则三处维护 | 该规则同时存在于本节、`gate_policy.md:49-62`、`math_correctness_profile.md` 全文；三处中两处英文一处中文，未来更新易漂移 | 状态文档保留一行中文摘要 + 链接到 `math_correctness_profile.md` 作为唯一权威描述 |
| P2-5 | P2 | `docs/NIPT_BATCH_A_D_ACCEPTANCE_2026-08-15.md:35`；`MATH_..._STATUS.md:31` | "四类真实 battle test"；"本轮新增" | 未定义术语 / 相对时间词 | "battle test" 全仓孤例、无定义；"本轮"锚点依赖文档更新日期 | battle test → "真实输入端到端测试（Batch E）"并定义；"本轮新增" → "Batch 2026-08-15 新增" |
| P2-6 | P2 | `SKILL.md:198`、`README.md:284` | "先运行 `check_paper_readiness.py` 和 `compile_writer_package.py`……只有显式 `--preview` 才允许生成不完整预览包" | 参数归属不明 | `--preview` 只存在于 `compile_writer_package.py`（`compile_writer_package.py:36-39`）；两句都把两个脚本并列后再提 `--preview`，Agent 可能对 readiness 脚本传该参数（报错，良性但费时） | 明确写"compile_writer_package.py 的 --preview" |
| P2-7 | P2 | `SKILL.md:35` | W1 最低产出含"可编译 writer package" | 用词不准 | writer package 是 JSON 写作输入，不是可编译物；"可编译"易被理解为 LaTeX 构建 | 改为"通过 readiness 的 writer package（JSON）" |
| P2-8 | P2 | `SKILL.md:8` | "先确认当前比赛允许做什么，再保证模型、结果和论文可追溯" | 目标写成保证 | 追溯由机制+人工共同保证，单句"保证"弱化了人工边界（同文 :24 等处边界表述良好，此处不协调） | "再使模型、结果和论文可追溯（机制见各 Gate；人工确认点见 Contest Safety）" |
| P2-9 | P2 | `schemas/run_manifest.schema.json:21-23` | `math_correctness_profile/editorial_semantics_profile/enhanced_integrity_profile` 仅有 enum/default，无 description | Schema 字段说明缺失 | 三个档位开关是全局强制语义的核心，schema 层无说明；新人只能从散落文档拼装含义与联动后果 | 为三个字段补 description（各一句话 + 指向 references/workflow/ 对应文档） |
| P2-10 | P2 | `assets/templates/*/template_contract.json`（`status: "verified"`）对照 `schemas/template_contract.schema.json` | 两个随库模板合同直接以 `status: "verified"` 分发 | 状态标签缺证据链 | `verified` 无需附带构建/PDF 回执即可声明；`check_template_usage.py:45` 在 research/submission 档只检查该枚举值。随库模板的 verified 依据（隔离编译记录）未以机器可读方式随合同保存（compat audit JSON 只覆盖上游 demo，不含这两个骨架） | 合同增加 `verification` 字段（build receipt 路径 + PDF hash），或 notes 中注明验证日期与命令；schema 为 `verified` 增加"须能指向回执"的说明 |
| P2-11 | P2 | `docs/MATH_MODELING_SKILL_ENHANCEMENT_PROPOSAL.md:154` | "通过校验工具……确保公式符号与参数来源完备" | 提案语气强于检查器实际能力 | checker 只能强制"已声明的输入"具备 typed provenance，无法确保"完备"（未列出的输入不在检查范围）。该文档头部 :9 已有边界声明，此句与之不协调 | "确保……完备"→"强制已声明模型输入具备 typed provenance，并对缺失来源报错" |
| P2-12 | P2 | `docs/SECOND_ROUND_EDITORIAL_INTEGRITY_AUDIT_2026-08-13.md:37` | "本轮扩展为 37 个回归测试" | 过时数字（有日期锚点，属可接受的历史快照） | 当前 18 个测试文件共 148 个测试函数；README:503 已声明"以实际 unittest 输出为准"，故仅建议 | 历史审计文档统一加"数字为当时快照"脚注，或头部加 superseded 提示 |
| P2-13 | P2 | `README.md:479-494` 致谢表 | 表中未列 SciencePlots（vendor 已锁定并用于绘图样式参考，`README.md:122`、`template_sources.json`） | 致谢清单不完整 | 用户要求核对"acknowledgement 中对开源项目融合程度的描述"；SciencePlots 的融合定位（样式参考、运行时不依赖，`plot_recipes.md:48`）应与 vendor 记录一致 | 致谢表补一行 SciencePlots：吸收样式设计参考；运行时使用自有轻量 style，不强依赖 |
| P2-14 | P2 | `docs/MATH_MODELING_SKILL_ENHANCEMENT_PROPOSAL.md:123`（mermaid） | "触发有界返修编排 (最多 2-3 轮……)" 对照 `scripts/reflexion/runner.py:30`（默认 `max_rounds=3`） | 区间数字与实现默认值并存 | 提案文档允许 2-3，实现默认 3；SKILL.md:33/134 与 `_base_cumcm.yaml`（`max_refl_rounds: 3`）一致为 3。提案为设计文档，影响小 | 统一写 3，或注明"上限可配置，默认 3" |
| P2-15 | P2 | `SKILL.md:31`（S0 行）对照 `README.md:208`、`artifact_contracts.md:10` | S0 最低产出写单个 `data_contract.json`；enhanced profile 要求"每个权威数据集一份 data_contract" | 同名产物单复数歧义 | `profile_generator.py` 默认输出单个 `data_contract.json`；多数据集项目需每集一份并逐一过 `check_data_contract.py`。S0 行未提示单复数差异 | S0 行补注："每个权威数据集一份；auto-eda 生成的初始契约 status 为 draft，M1 前需人工确认" |
| P2-16 | P2 | `references/visualization/figure_design.md:72` | "当前 P0 不声称自动完成 Nature Figure 的源码预检、导出 PDF 字体/裁切和逐 panel 最终尺寸审查；这些属于 P1" | 与现状部分不符（低估） | `check_figure.py` 现已实现导出格式、PDF 字体嵌入（pdffonts，`check_figure.py:110-120`）与 `--require-final-size` 合同检查（`:46-47,132`）；README:467 与 `visual_review.md:11` 均按现状描述。"逐 panel 人工可读性"确仍是人工，但整句会让 Agent 以为字体/尺寸检查未实现而跳过 | 拆分表述："导出格式、字体嵌入与最终尺寸合同检查已由 `check_figure.py` 自动执行；逐 panel 语义与可读性仍需人工（P1）" |

---

## 4. 能力声明证据表

| 声明 | 文件位置 | 实现证据 | 测试/运行证据 | 判定 | 建议表述 |
|------|----------|----------|---------------|------|----------|
| "当前 Harness 已经能约束一条可审计的交付链" | `MATH_..._STATUS.md:9` | `check_gates.py` 全链校验 + 25 个 schema + 全套脚本 | `tests/` 148 个测试函数 | 证据充分，表述准确 | 保留 |
| "Strict math correctness profile … is wired into check_gates.py" | `MATH_..._STATUS.md:245-253` | `check_gates.py:50-59,127-156`（strict 触发 scope/replay/presentation/pdf 一致性重跑） | `tests/test_math_profile_gate.py:15`；`tests/test_scope_consistency.py`；`tests/test_formula_replay.py` | 证据充分，表述准确 | 保留（建议中文化并单源化，见 P2-4） |
| "T-NIPT-01…09、11–14 已映射到现有检查器并有精确负例" | `NIPT_...md:7-10,16-31` | 各 check_* 脚本存在 | 矩阵引用的 14 个测试名逐一核实全部存在（如 `test_oos_checker_recomputes_entity_overlap` 等） | 基本准确，但需限定范围：源审计文档缺失（P1-2） | 补自包含定义或提交源审计 |
| "两条可验证论文模板已经实际通过隔离编译并完成全页渲染……发现未嵌入字体/Letter 纸" | `README.md:124` | `docs/TEMPLATE_COMPATIBILITY_AUDIT_2026-08-13.json`（exit_code 0、12/11 页全渲染、`formal_ok:false`、缺陷如实记录） | 同 JSON 即运行回执 | 证据充分，表述准确（含诚实披露） | 保留 |
| "Enhanced W2 独立重算……重算不为 ok=true 时阻断" | `MATH_..._STATUS.md:64` | `check_gates.py:62-220` | `test_p0_harness.py`（enhanced 系列） | 证据充分，表述准确 | 保留，并按 P1-4 补 baseline 边界说明 |
| "自动代码与 PDF 匿名脱敏" | `SKILL.md:37` | **未找到证据**（无脚本；`check_submission.py` 无匿名逻辑） | 无 | 与代码冲突 / 表述过强 | 按 P0-1 改写 |
| "新项目默认 integrity_mode=research" | `SKILL.md:73`、`README.md:51` | **与代码冲突**：schema default=dev（`run_manifest.schema.json:22`）、`check_gates.py:293` 回退 dev | 无（默认值无测试锁定） | 与代码冲突 | 按 P0-2 统一 |
| "拆题器只产候选、不替代 M1……不再自动选择解释 A" | `MATH_..._STATUS.md:63` | `scripts/ideation/problem_decomposer.py:86` | `tests/test_enhancements.py:322` | 证据充分，表述准确 | 保留 |
| "生成器已提供七套默认配色" | `MATH_..._STATUS.md:76` | `generate_drawio.py` + `drawio_backend.md:38-47`（恰 7 个预设） | `tests/test_drawio_backend.py:52,59` | 证据充分，表述准确 | 保留 |
| "W2 表示内容就绪；S1 表示当届提交包合规；F1 由不可覆盖 manifest 表示" | `SKILL.md:72`；`gate_policy.md:26-27`；`submission_freeze.md:5-7` | `check_gates.py:1217-1223`；`freeze_submission.py`（禁止覆盖） | `test_p0_harness.py:634` | 证据充分，表述准确 | 保留 |
| "CUMCM 当前可核验的 AI 专项基线仍是 2025 试行规定" | `contest_safety.md:37`、`README.md:162` | 带核验日期（2026-08-08）的规则入口清单（`:57`） | 本地规则快照（人工） | 基本准确，但需限定范围：有时效性，赛前必须重抓（文档已自声明） | 保留 |
| "本轮扩展为 37 个回归测试" | `SECOND_ROUND_...md:37` | 历史（2026-08-13）快照；现为 148 个测试函数 | README:503 已声明以实际输出为准 | 已经过时（有日期锚点，可接受） | 加历史快照脚注 |
| "Harness 不自动上传，也不能把 submission_receipt 预填为 accepted" | `submission_freeze.md:5` | 无上传脚本；schema `portal_status` 由人工登记 | — | 证据充分，表述准确 | 保留 |
| "它不表示把上游仓库整体复制进本项目"（融合边界） | `README.md:481` | `vendor/template_sources.json`（逐源 license/distribution 记录） | doctor/clone 脚本 | 证据充分，表述准确 | 保留（补 SciencePlots 行，P2-13） |

---

## 5. 全局冲突表

| 主题 | 文件 A 表述 | 文件 B 表述 | 当前实现 | 应采用的表述 |
|------|-------------|-------------|----------|--------------|
| 匿名脱敏执行方式 | `SKILL.md:37`"自动代码与 PDF 匿名脱敏" | `submission_freeze.md:17`"匿名性……必须列入 required_manual_checks 并由 S1 human checkpoint 确认" | 无自动实现；S1 人工检查 | 以 submission_freeze 为准（人工义务），修订 SKILL |
| integrity_mode 默认值 | `SKILL.md:73`/`README.md:51`"新项目默认 research" | `run_manifest.schema.json:22` default=dev；`check_gates.py:293` 回退 dev | dev | 建议改实现默认为 research（或在文档中要求显式声明并说明 dev 回退后果） |
| 概念图可编辑后端 | `SKILL.md:186`"必须……通过 generate_drawio.py 生成 native .drawio" | `diagram_workflow.md:7`/`figure_contract.md:9`/schema：drawio、SVG、Figma、PPTX 均合法 | `check_diagram_spec.py` 按 spec 的 source_format 校验 | 以契约/schema 为准：默认 drawio 后端，其他可编辑矢量源需声明并保留源 |
| 图表自动检查能力 | `figure_design.md:72`"PDF 字体/裁切和逐 panel 最终尺寸审查……属于 P1" | `README.md:467`/`visual_review.md:11`"check_figure.py 检查导出格式、PDF 字体和栅格有效 DPI……final_size_qa" | `check_figure.py` 已含字体嵌入与 final-size 合同检查 | 以现状为准，修订 figure_design（P2-16） |
| 核心 artifact 数量 | `README.md:51`"五个核心 JSON"+6 行表 | `artifact_contracts.md:26`"五个核心 contract……提交阶段再增加不可变 manifest" | 后者 | 以 artifact_contracts 为准 |
| "防手改 ok=true"适用档位 | `SKILL.md:234`/`gate_policy.md:31`（限定"增强 profile"） | 无文件声称 baseline 同样防手改（缺的是显式否定） | 重跑仅 enhanced/strict 触发 | 补 baseline 声明性边界（P1-4） |
| 公式回放默认行为 | `MATH_..._STATUS.md:43`（未提启用条件） | `math_correctness_profile.md:22-36`（列为 strict 启用项） | `run_deterministic_qa.py:237-240` 默认 skip-if-absent | 以实现为准：标注默认跳过 |
| strict profile 规则文本位置 | `MATH_..._STATUS.md:245-257`（英文） | `gate_policy.md:49-62`（英文）+ `math_correctness_profile.md`（英文全文） | 一致（当前无内容冲突） | 单源化到 math_correctness_profile.md，其余摘要+链接 |
| "本轮"批次语义 | `MATH_..._STATUS.md:31` | `NIPT_...md:3`（"已覆盖"另一套词汇） | 各自定义 | 统一词汇表（第 7 节） |
| 测试数量 | `SECOND_ROUND_...md:37`"37 个" | `README.md:503`"以实际 unittest 输出为准" | 148 个测试函数 | 以 README 的活口径为准，历史文档加快照注 |

**流程顺序**（S0→M1→P1→P2→W1→W2→S1→F1）、**项目目标定位**（"可组合 Harness，不是全自动解题 Agent"，`README.md:5`）、**数学正确性边界**（结构/追溯检查 ≠ 代数证明，多处一致）、**文献边界**（metadata/全文/出版状态三重核验，摘要≠原文证据）、**模板机制**（社区/用户模板 ≠ 官方模板，多处一致）、**哈希定位**（提交完整性约束，非本地必做，多处一致）经交叉比对**未发现冲突**，是本项目表述质量最好的部分。

---

## 6. Agent 误解风险

以下按"新 Agent 只读入口文档"的视角列出可能误解，每条含导致误解的原文与后果。

| # | 可能的错误理解 | 导致误解的原文 | 可能产生的后果 | 应增加的明确指令 |
|---|----------------|----------------|----------------|------------------|
| 1 | 匿名脱敏由工具自动完成，无需人工核验 | `SKILL.md:37`"自动代码与 PDF 匿名脱敏" | 跳过 required_manual_checks 中的匿名项，含队号/校名的 PDF 进入提交 | S1 行改为人工义务清单，并指向 `submission_freeze.md:17` |
| 2 | 不写 integrity_mode 也在正式研究链上 | `SKILL.md:73`"新项目默认 research" vs schema default dev | 静默落入 dev：formal M1 不运行，research-first 门被绕过 | 要求显式声明该字段；或改默认值（P0-2） |
| 3 | 默认 QA 已对公式数值做回放复核 | `MATH_..._STATUS.md:43`（未标 skip-if-absent） | 未声明 replay case 的公式被当作"已验证数字" | 状态表补默认行为标注（P1-3） |
| 4 | baseline 档的 ok=true 报告不可伪造 | `SKILL.md:234`/`gate_policy.md:31`（只写增强档重跑） | Agent 手写或复用旧报告通过 W2 而无重算 | gate_policy 补 baseline 声明性边界（P1-4） |
| 5 | 概念图只能用 generate_drawio 产物，Figma/PPT 源不合规 | `SKILL.md:186` | 合法可编辑源被拒绝、重复返工；或误判 check_diagram_spec 只认 .drawio | SKILL 补替代后端一句（P1-1） |
| 6 | NO-GO 审计描述的是当前 Harness 行为 | `RESEARCH_INTEGRITY_ARCHITECTURE_AUDIT.md:4,30,56` | 错误地不信任已修复的 Gate，或模仿"用解释覆盖 verdict"的旧反例 | 加 superseded 横幅（P1-5） |
| 7 | T-NIPT 编号有可追溯的源审计 | `NIPT_...md:3` | 复述"已覆盖"时无法提供出处；Batch E 设计失去输入 | 提交源文档或自包含化（P1-2） |
| 8 | 字体/最终尺寸自动检查尚未实现，不必运行 | `figure_design.md:72` | 跳过 `check_figure.py --require-final-size`，图 QA 缺层 | 按 P2-16 拆分表述 |
| 9 | `--preview` 可用于 readiness 脚本 | `SKILL.md:198`/`README.md:284`（两脚本并列后提 --preview） | 传错参数报错（良性）；或误以为 preview 包能交给正式 Writer（SKILL 已明确禁止，风险低） | 指明归属 compile_writer_package.py |
| 10 | 按 README 尾部链接找不到整合审计文档 | `README.md:495`（缺 docs/ 前缀） | 致谢/决策依据追溯中断 | 修链接（P2-2） |
| 11 | "五个核心 JSON"即仓库只需维护五个文件 | `README.md:51`+6 行表 | 把 submission_manifest 当常规 artifact 随手创建 | 拆表并注明 F1-only（P2-1） |
| 12 | 一份 data_contract.json 就满足 M1 | `SKILL.md:31`（S0 行单数） | 多数据集项目漏建契约，enhanced M1 被 check_gates 拒绝（会被拦住，但浪费一轮） | S0 行补"每个权威数据集一份"（P2-15） |

**关于用户列举的其余典型误解的核验结论**：未发现会导致"没有调研就建模"（`SKILL.md:67` M1 规则 3 强制研究优先）、"计划未评审就编码"（`check_gates.py:557-558` M1 人审硬性）、"数学审查失败仍写作"（W2 依赖链 + FAIL 不可 claimable）、"把测试 fixture 当真实实验"（fixture 与 artifact 分离，Gate 校验 run_id/哈希）、"只复制 main.tex 冒充完整模板"（多处明确禁止且有 `test_template_usage_rejects_declared_template_that_is_not_used`）、"生成很短的第一版论文"（`draft_coverage` 最低字数锚点 + `test_first_draft_coverage_rejects_a_short_argument_span`）、"用 Mermaid 冒充正式框架图"（SKILL/figure_contract/drawio_backend 三处禁止）、"把编译成功当允许提交"（W2≠S1≠F1 分层）的表述缺陷。防"自填 PASS"在 enhanced/strict 档有独立重跑兜底，唯 baseline 档有第 4 条所述边界。

---

## 7. 建议的统一词典和写作规则

以下为可直接放入项目文档的规范草案（本审计不修改任何文件）。

### 7.1 统一状态词（对齐现有 schema，新增两个项目层词汇）

| 状态词 | 定义 | 已有使用处（保持不变） |
|--------|------|------------------------|
| `planned` | 已列入计划/路线图，未实现 | roadmap "已排期"；`sensitivity_experiment.status=planned` |
| `scaffolded` | 仅有 Schema/接口/脚手架，无端到端运行证据 | （新增，供状态表使用） |
| `implemented` | 有功能代码且可通过 CLI 运行 | 状态表"已实现" |
| `integrated` | 已接入 `check_gates.py`/`run_deterministic_qa.py` 主流程（须注明默认档位：default-on / strict-only / flag-only） | （新增维度，修复 P1-3） |
| `tested` | 有自动化回归测试（负例优先） | NIPT 矩阵"精确回归证据"列 |
| `validated` | 在真实比赛/真实数据项目中有可复核运行证据（QA JSON + run_id） | `data_contract.status`；Batch E 完成后方可用于能力层 |
| `submission-ready` | 通过指定比赛 profile 的 S1 并完成 F1 冻结 | `run_manifest.status=submission_ready` |

### 7.2 统一强制词

- **MUST/必须**：不满足即由 checker 报 error、Gate 无法 pass（须能指到对应检查器与测试）。
- **SHOULD/应**：默认执行；跳过必须在 manifest/决策记录中留 `skip_with_reason`。
- **MAY/可**：可选能力或等价替代路径（如替代矢量后端）。
- 禁止裸用"自动"修饰无脚本支撑的动作；"自动"仅用于存在可执行入口的检查/生成。

### 7.3 统一证据词（区分声明与核验层级）

| 词 | 含义 |
|----|------|
| `declared` | 仅在合同/manifest 中声明，未经检查 |
| `generated` | 由受控工具产出（receipt/report） |
| `checked` | 通过确定性脚本校验（ok=true） |
| `reviewed` | 通过人工/多模态审阅（visual review、Critic） |
| `verified` | 通过独立重算/重跑（enhanced/strict 重跑、evaluate_obligations、formula replay）或文献三重核验——不同 domain 的 verified 必须能指到各自证据 |
| `reproduced` | 从声明的输入在本地重建出一致结果 |
| `frozen` | 进入 append-only/不可覆盖交付物（本身不代表内容正确） |

### 7.4 完成声明格式

所有"已完成 X"的声明（状态表、提交信息、验收文档）须同时写明五项：

1. 完成了什么（组件/命令名）；
2. 接入到哪里（哪个 Gate、默认档位还是显式档位）；
3. 在什么条件下有效（profile/flag/前置 artifact）；
4. 用什么测试验证（测试文件::测试名）；
5. 尚有什么限制（对应 non-claims）。

### 7.5 其他写作规则

- 历史审计/提案文档头部必须有"快照日期 + 是否被后续工作取代"横幅；路线图中的计划一律用将来时/计划语，不用完成时。
- 所有文档内相对链接在提交前校验一次目标存在（可加入 doctor 或 CI 的轻量检查）。
- 中英文混排文档中，规则性内容（profile 定义、Gate 规则）单源化到 references/，其余位置只留摘要+链接。
- 涉及比赛规则的事实（页数、AI 政策）必须带"核验日期 + 快照来源"，禁止无日期断言（现状已基本做到，作为规则固化）。

---

## 8. 最小修订顺序

按"会改变实际执行行为的入口指令优先"排序：

1. **P0-1**：修订 `SKILL.md:37` S1/F1 行——去掉"自动匿名脱敏"，改写为人工检查义务（入口指令，直接影响提交合规执行）。
2. **P0-2**：统一 `integrity_mode` 默认值（改 schema/代码默认为 research，或在 SKILL/README 强制显式声明并说明 dev 回退会跳过 formal M1）。
3. **P1-3**：为状态表公式回放/展示值安全/源码—PDF 一致性三行补"默认 skip / 显式档位才阻断"标注（能力与完成状态的失真声明）。
4. **P1-4**：在 `gate_policy.md` 增加 baseline 档"QA 报告为声明性输入、防手改仅限 enhanced/strict"边界说明。
5. **P1-1**：调和 SKILL 与 diagram_workflow 的概念图后端表述（MUST 冲突）。
6. **P1-2 / P1-5**：补 NIPT 源审计文档或自包含化；为 2026-08-08 历史审计加 superseded 横幅（不同文档间冲突与断链）。
7. **P2 批次**：术语统一（verified 词汇表、"本轮"→日期批次、battle test 定义）、README 五/六计数、断链修复、`--preview` 归属、schema 字段 description、template_contract verified 证据链、figure_design:72 现状化等文字性修订。

---

---

## 附录 B（2026-08-16 补充）：对第二份"全量文档表述与易用性审查"的逐条复核

输入：外部审查《数学建模 Skill/Harness 全量文档表述与易用性审查及优化指南》（S-01～S-06、README 三项、references 五组、docs 三项）。以下每条均按仓库现状重新取证。判定取值：**成立 / 部分成立 / 不成立 / 已实现 / 建议有风险**。优先级沿用本审计第 3 节的 P0/P1/P2 口径（以是否改变执行行为分级，与该审查的"P0=坏链与英文段落"口径不同）。

### B.1 复核总表

| 对方编号 | 断言 | 复核证据 | 判定 | 本审计处置 |
|---|---|---|---|---|
| S-01 | SKILL.md:39-61 在阶段总表后、M1/P1/P2 之前插入"W2 的数学—写作最低合同"，破坏线性顺序 | 标题在 `SKILL.md:39`，其后 63 行才是"不可违反的规则"、76 行起才是阶段 0/1/2 | 成立 | P2（结构）。可移至 `## 4`；若保留原位，应加一句"此处为前置声明，执行见第 4 节" |
| S-02 | 章节编号与 Gate 代码错位（第 3 节实为 W1 产物、第 4 节混合 W1/W2） | `SKILL.md:162`"## 3. Evidence、论文策略与图表"（产出 paper_plan=W1）；`:190`"## 4. W1/W2：单 Writer…"（含 W1 readiness） | 成立 | P2。建议 `## 3. W1 …`、`## 4. W2 …` 一一对应 |
| S-03 | `run_deterministic_qa` 示例堆 20 个参数，其后 `:236` 又说"迁移期间可先不启用" | `SKILL.md:200-223` 与 `:236` 属实；且与本审计 P1-3（状态表缺启用条件）同根 | 成立 | P2（可读性），与 P1-3 合并处理：按 Baseline/Strict 拆两个代码块 |
| S-04 | 单项脚本（check_derivation_integrity）与聚合入口（--require-derivation-integrity）关系未说明 | `SKILL.md:43-57` vs `:213`；无任何一处解释"单项调试 vs 阶段聚合" | 成立 | P2。补一句关系说明 |
| S-05 | 长难句（SKILL.md:67、:186） | 实测 `:67` 单行 337 字符、`:186` 单行 989 字符 | 成立 | P2。拆为条件子条目 |
| S-06 | 缺 Minimal Happy Path | SKILL.md 全文无极简正向流程；README:107 起有 quickstart 但入口文档没有 | 成立（判断类） | P2。开篇加 5 步速查表价值明确 |
| README-1 | `README.md:495` 坏链 | 属实（同文件 :96-105、:507 用了 docs/ 前缀） | 成立 | 即本审计 P2-2 |
| README-2 | `:249-267` 两个代码块之间无过渡句 | 属实（`evaluate_obligations` 块后仅空行即 `freeze_results` 块） | 成立 | P2。加一句"验证求值产出后，冻结完整 run：" |
| README-3 | Quickstart 法律/许可细节过重（:107-155） | 属实；但这些内容是 `template_sources.json` 决策的人读版，**不可删除** | 部分成立 | P2。移至附录/折叠段，保留原文与链接 |
| R-3.1a | model_contract.md 超长 JSON 示例（约 140 行）挤占全文 | 示例位于 `:7-143`（约 62% 篇幅） | 部分成立 | P2。保留完整可复制示例有独立价值；建议前部加字段速查表、示例后移 |
| R-3.1b | artifact_contracts.md 增强表缺"生成脚本/校验脚本"两列 | 表格仅 Artifact/Gate/作用（`:7-18`） | 成立 | P2。低成本低风险，可做 |
| R-3.2a | gate_policy.md:49-62 英文块割裂 | 属实 | 成立 | 即本审计 P2-4（单源化到 math_correctness_profile.md） |
| R-3.2b | 状态表末尾英文段 | 属实（`MATH_..._STATUS.md:245-257`） | 成立 | 即本审计 P2-4 |
| R-3.2c | contest_safety.md 未说明"本地调用大模型 API 是否允许" | 属实且**比对方定性更严重**：`contest_safety.md` 与 `check_contest_safety.py` 全文无 API/LLM 处理；live_contest 默认 deny"一般外部写入"，而向云端 LLM 端点发送当前赛题数据是否算"外部写入"未定义——这直接决定本 Skill 自身在 live contest 的主执行模式是否合规 | **成立（升级为新 P1-6）** | 但对方的建议文案**有风险**，见 B.2 |
| R-3.3 | cumcm_empirical_style / editorial_style 软建议用"必须/一律"易被当硬 Gate | cumcm_empirical_style.md **不成立**：:3、:13、:33-40（Not Mandatory）、:44 已有完整边界声明，对方引用的"一律"出现在 Not-Mandatory 清单内（:39）。editorial_style.md **部分成立**：:35/:51/:61 等确用"严禁/禁止"，但其边界声明只在文末 :93-95；且实测 `check_paper_style.py` 仅"强词标记"为 error（:142），三线表/单位置表头等排版规则**无任何脚本强制** | 部分成立（仅 editorial_style） | P2。editorial_style.md 顶部加边界框，并逐条标注"脚本强制（error）/lint warning/仅人工" |
| R-3.4 | diagram 文档缺 .drawio→PDF 具体命令 | **说法过重**：`drawio_backend.md:66-79` 已有具体导出命令；`generate_drawio.py:531` 支持 `--export-format svg/pdf/png`。缺口仅是示例用了 svg、未给 pdf 变体 | 部分成立 | P2。补一行 `--export-format pdf` 示例即可；不建议另引入裸 `drawio --export` 双入口（与 generate_drawio 包装重复，制造两个入口） |
| R-3.5 | cards/ 结构杂乱、纯段落、缺检查器关联 | **基本不成立**：三类卡各有统一模板（failures 全部为"错误形式/为什么错/最小反例/Harness 应如何发现与拦截/论文中如何正确表达"五段，如 `cvar_profit_loss_sign.md`、`solver_gap_not_global_optimum.md`；methods 统一 11 段编号；problems 统一 4 段编号），无"纯段落"卡。检查器链接方面：failures 10 张中 5 张含 `check_*` 引用（其余 5 张对应 check_math_semantics 文本级检查，可补）；methods/problems 卡本就不承担拦截职责 | 不成立（主体） | 可选增强：为其余 5 张 failure 卡补"对应检查器"行；不必推行对方模板 |
| D-1 | HARNESS_INTEGRATION_ANALYSIS.md 加早期记录 WARNING 横幅 | 文档 :3 已有部分说明（"第 2～3 节保留最初的逐仓机制裁决…"），但未指向现行真源 | 部分成立 | 与本审计 P1-5 一并处理：加"历史快照 + 以状态表为准"横幅 |
| D-2 | ENHANCEMENT_PROPOSAL.md 加 NOTE 横幅 | **已实现**：该文档 `:9` 已有"文档边界：本文是演进方案与设计记录，不是功能已完成证明……以 MATH_HARNESS_IMPLEMENTATION_STATUS.md 为准" | 已实现 | 无需修改（可选：格式化为 alert 块） |
| D-3 | SECOND_ROUND 加"已合并至主状态表"TIP | 加指向横幅合理；但"已合并"这一断言本身未经验证（其中"尚未声称完成"清单与状态表"已排期"是否逐项对应需核对） | 部分成立 | P2。措辞用"本文为 2026-08-13 快照；当前状态以 MATH_HARNESS_IMPLEMENTATION_STATUS.md 为准"，不要写"已合并" |

### B.2 需要单独说明的两点

**① R-3.2c 的观察成立，但其建议文案会引入新的合规错误。**
对方建议写"通过官方/本地受控端点调用大模型 API 属于允许的参赛辅助"。这句话以文档形式制造了一条全局许可，与本项目"官方规则与本地保守策略分离、规则不明用 `ask`"的架构（`contest_safety.md:9-14`）冲突：CUMCM 2025 试行规定要求"核心建模独立完成"+披露，COMAP 要求 AI Report，两者都不是无条件允许；且 live_contest 默认 `deny 一般外部写入`（`:14`）本就可能覆盖"把当届题面发给云端端点"。正确修法是补一条**判定规则**而非许可：

> 调用大模型 API 属于 AI 使用：必须登记 `run_manifest.ai_usage[]` 并按当届 AI 政策披露；向外部端点发送当前赛题数据在 `live_contest` 下默认按"外部写入"策略处理（deny/ask 由当届 profile 决定，官方端点例外需人工确认）；规则不明时用 `ask`，不得默认允许。

**② 对方清单不含真正会改变执行行为的问题。**
该审查把坏链与英文段落列为"P0"，按本审计口径这些是 P2（不影响 Gate 与执行行为）；而两个行为级 P0——`SKILL.md:37`"自动匿名脱敏"无实现（本审计 P0-1）与 `integrity_mode` 文档默认 research vs schema 默认 dev（本审计 P0-2）——以及 P1-3/P1-4（档位启用条件、baseline 声明性边界）均不在其清单内。**若只按对方清单整改，实际执行风险不会下降**；两份清单应按本审计第 8 节顺序合并执行：先 P0-1/P0-2 与新增 P1-6，再做对方的结构性/可读性改进。

### B.3 合并后的补充修订顺序（在第 8 节之后追加）

9. **P1-6（新增）**：contest_safety.md 补"AI API 调用 = AI 使用 + 外部端点数据外发按外部写入策略判定"规则（按 B.2① 文案，勿采用对方许可式表述）。
10. P2 批次追加：SKILL.md 结构重排（S-01/S-02/S-03/S-04/S-05/S-06）、README 过渡句与 quickstart 减负（法律内容移动不删除）、model_contract 字段速查表、artifact_contracts 工具列、editorial_style 顶部边界框、drawio_backend 补 pdf 导出示例、docs 历史文档横幅（D-1/D-3，D-2 已实现）。

---

## 附录 C（2026-08-16）：整改记录

本附录记录按第 8 节 + 附录 B.3 顺序实际执行的修订。所有修改均通过全量回归测试验证（见 C.3）。

### C.1 已执行的修订

**P0（行为级）**

1. **P0-1** `SKILL.md` S1/F1 行：删除"自动代码与 PDF 匿名脱敏"，改为"`required_manual_checks` 逐项人工确认（明确不存在自动匿名化脚本）+ AI 报告草稿经人工确认"。
2. **P0-2** integrity_mode 默认值统一为 `research`：
   - `schemas/run_manifest.schema.json`：`integrity_mode` default `dev`→`research`；
   - `scripts/qa/check_gates.py`（原 :293）与 `scripts/qa/validate_contracts.py`（原 :178）的缺失回退值 `dev`→`research`（字段本身为 schema 必填，回退仅在文档已报 schema error 时生效）；
   - `SKILL.md` 规则 9 补注："必填字段，缺失会被 schema 校验拒绝，不会静默回退"；
   - `README.md` 核心 artifact 段同步补注。

**P1（能力/边界级）**

3. **P1-1** `SKILL.md` 第 3 节图件段：改为"默认经 `generate_drawio.py`；也可使用 Figma/PowerPoint 等其他可编辑矢量后端（声明 `source_format` 并保留等价可编辑源）"，与 diagram_workflow/figure_contract/schema 对齐。
4. **P1-2** `NIPT_BATCH_A_D_ACCEPTANCE_2026-08-15.md` 头部加"源审计说明"：源文档为外部输入未随仓库分发，矩阵自包含、复核不依赖该文档。
5. **P1-3** `MATH_HARNESS_IMPLEMENTATION_STATUS.md` 状态表：作用域（默认仅已声明时检查）、公式回放（默认 skip-if-absent）、展示值安全（仅提供 presentation contract 时运行）、源码—PDF 一致性（仅 strict 档 + `--pdf` 输入时执行）四行补默认行为标注。
6. **P1-4** `references/workflow/gate_policy.md` 补 baseline 边界段："baseline 档 QA 报告与 reviewer 状态是声明性输入，防手改的独立重跑仅存在于 enhanced/strict 档；正式研究链建议开启增强或 strict 档。"
7. **P1-5** 历史文档横幅：`RESEARCH_INTEGRITY_ARCHITECTURE_AUDIT.md`（NO-GO 快照 + 已修复范围 + 引用脚本不在本仓库）、`HARNESS_INTEGRATION_ANALYSIS.md`（历史整合审计、状态以状态表为准）。
8. **P1-6** `references/safety/contest_safety.md` 补 AI API 判定规则："调用大模型 API 属于 AI 使用须登记；向外部端点发送当届题面数据在 live_contest 按'外部写入'策略处理（默认 deny，profile 显式允许或已登记官方端点例外才放行）；规则不明用 ask，不得默认允许。"（采用附录 B.2① 的判定式文案，未采用对方审查的许可式表述）

**P2（结构/可读性/术语）**

9. `SKILL.md` 结构重排（对方审查 S-01~S-06 全部落地）：
   - 新增"最短路径速查"5 步节；
   - "W2 的数学—写作最低合同"从阶段表后移入第 4 节；
   - 章节改名 `## 3. W1：…`、`## 4. W2：…`；readiness/writer package 段归位第 3 节末（"W1 收尾"）；
   - `run_deterministic_qa` 命令拆为 Baseline 标准命令 + 增强档注释式参数清单，并补"单项脚本=独立调试，聚合入口=阶段验收"关系说明（S-04）；
   - 规则 3 与第 3 节 989 字符长段拆为条件子条目（S-05）；
   - `--preview` 归属 `compile_writer_package.py`（P2-6）、"可编译 writer package"→"只读 writer package（JSON）"（P2-7）、"保证可追溯"→"使可追溯"（P2-8）、S0 行 data_contract 补"每个权威数据集一份"（P2-15）。
10. `README.md`：五个核心 JSON 表格拆分（manifest 单列为 F1 追加项，P2-1）；:495 坏链补 `docs/` 前缀（P2-2）；evaluate/freeze 两代码块间加过渡句；quickstart 许可证段前加"可先跳过"提示；:284 `--preview` 归属；致谢表补 SciencePlots 行（P2-13）。
11. `gate_policy.md` 与状态表末尾的英文 Strict profile 段中文化并单源化到 `references/workflow/math_correctness_profile.md`（P2-4）。
12. 状态标记表"本轮新增"锚定为"2026-08-15 更新批次"；battle test 补定义为"带输入快照与运行回执的真实赛题级测试，非单元测试 fixture"（P2-5）。
13. `figure_design.md` 图表自动检查描述现状化（check_figure.py 已查字体/DPI/最终尺寸合同；逐 panel 人工复核仍属 P1）（P2-16）；`drawio_backend.md` 补 `--export-format pdf` 一句（对方 R-3.4）。
14. `editorial_style.md` 顶部加边界声明框（SHOULD 级指导；机器强制仅强词 error，其余 warning/人工）（对方 R-3.3 成立部分）。
15. `model_contract.md` 前部加顶层字段速查表（对方 R-3.1a）；`artifact_contracts.md` 增强 artifact 表补"生成来源/校验入口"两列（R-3.1b）。
16. `run_manifest.schema.json` 三个 profile 字段 + `integrity_mode` 补 description（P2-9）；`template_contract.schema.json` `status` 补"verified 只证明身份一致，不等于当届格式合规"定义；两份 assets 模板合同 notes 同步补该边界（P2-10）。
17. `MATH_MODELING_SKILL_ENHANCEMENT_PROPOSAL.md`："确保…完备"改为"强制已声明输入具备 typed provenance（未列入合同的不在检查范围）"（P2-11）；mermaid"最多 2-3 轮"→"最多 3 轮"与 runner 默认一致（P2-14）。
18. `SECOND_ROUND_...md` 加快照说明横幅（D-3，措辞用"当前状态以状态表为准"，未写未经验证的"已合并"）。

### C.2 整改中顺带修复的存量测试问题（非本审计清单项，已定位根因并修复）

1. `scripts/eda/auto_eda.py` 多重共线性检查：新版 pandas（copy-on-write）下 `corr().values` 只读导致 `np.fill_diagonal` 抛 `ValueError: underlying array is read-only`，`test_auto_eda_detection_and_metrics`、`test_data_contract_generator` 两个测试 ERROR。修复：`np.array(corr_matrix, copy=True)` 后在副本上归零并读取。
2. `tests/test_enhancements.py::test_editable_diagram_spec_supports_vector_and_raster_delivery`：fixture 手写的 `.drawio` 缺少 native 结构必需的 `mxCell id=0` 根容器与 `id=1 parent=0` 默认层，被加固后的 `check_diagram_spec` 正确拒绝。修复：fixture 补全 native 结构（检查器语义不变）。

两项修复后 `tests.test_enhancements` 20/20 通过。

### C.3 验证

- 全量 `python -m unittest discover -s tests`：176 个测试全部通过（含 gate/schema/模板/NIPT/strict profile 全部模块）。
- 修改过的 JSON schema 与模板合同均通过 `json.load` 解析；修改过的 Python 脚本通过 `py_compile`。
- 未采纳项：对方审查 R-3.5（cards 结构统一模板，复核判定基本不成立）、D-2（提案文档横幅，已存在）、contest_safety 许可式文案（以判定式规则替代，见第 8 项）。

### 附：本次审计核实过的一致性基线（无问题项，供后续审计对照）

- `SKILL.md` 全部命令行示例的脚本路径与参数（`check_derivation_integrity --require-metadata --strict`、`check_math_writing --require-coverage`、`run_deterministic_qa` 的 9 个 `--require-*`、`check_gates --strict`、`check_submission` 的页数/AI 参数、`check_paper_readiness --minimum-stage technical_draft`、`compile_writer_package --preview`、`generate_values_tex --provenance`、`plot_templates`、`check_diagram_spec --require-reviewed`、`generate_drawio --list-style-profiles`、`doctor --offline`、`problem_decomposer`、`run_bounded_reflexion(..., repair_callback=...)`、max_rounds=3）与 `scripts/` 实现逐一核对一致。
- `vendor/clone_templates.ps1`、`requirements-dev.txt` 存在；`vendor/template_sources.json` 的许可/分发记录与 README/SECOND_ROUND 表述一致。
- `TEMPLATE_COMPATIBILITY_AUDIT_2026-08-13.json` 与 README:124 的模板编译声明逐字段一致（含 formal_ok=false 的诚实披露）。
- NIPT 矩阵引用的 14 个测试名全部存在；`tests/` 共 18 文件 148 个测试函数，命名语义与文档声明一致。
- `agents/openai.yaml` 的 UI 描述与实际能力相符，无过度承诺。
- `competition_profiles/*.yaml` 的状态标签、AI 基线与 `contest_safety.md` 一致（含 2025 试行 AI 规定的时效性声明）。
