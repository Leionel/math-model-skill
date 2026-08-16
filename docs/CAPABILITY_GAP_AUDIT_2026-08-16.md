# 能力缺口审计（第二轮，2026-08-16）：链条闭环缺口

- 审计对象：当前工作区（含 2026-08-15/16 两批未提交改动）。
- 审计方法：验证式——每个缺口先用代码检索/运行证实"确实没有"，再结合上游数模/学术 skill 机制定位缺口来源。区别于《GLOBAL_WORDING_CONSISTENCY_AUDIT_2026-08-16》（表述层），本文只回答一个问题：**哪些防线声称存在、实际断链**。
- 结论先行：**表述层和单点检查器已经很厚，但"检查器之间的焊点"普遍缺失**——工具建好了没有消费者、自由文本没有收据约束、交付物没有符合性检查。共 1 个 P0 级断链、5 个 P1、6 个 P2。

---

## P0：会直接让错误答案进入冻结链的断链

### GAP-01 冻结命令是自由文本，无收据绑定

- **证据**：`scripts/freeze_results.py:176` `--command` 是 `required=True` 的自由字符串，`:247` 原样写入冻结件。`run_and_record.py`（今天新建，能产出带真实 exit code/IO 哈希的 command receipt）**没有任何脚本消费它**。
- **后果**：frozen_results 是整条证据链的数值真源，但它的"这条命令真实运行过且成功"属性只靠人/Agent 声明。battle 里 `--command "python code/run_all.py --seed 42"` 是纯声明——验证报告会被重算（这点很强），但**命令本身从未被验证执行过**。一个从未运行的命令 + 一份手写的 measurement snapshot 依然可以通过 freeze。
- **上游对照**：这正是 XiaoMaColtAI `repro_manifest` 机制的核心（argv 数组 + 真实捕获），Wave 2 规划过，工具今天落地了，**差最后一米**。
- **修法（按 integrity_mode 分级，与规则 9"哈希只是提交完整性约束"对齐）**：`freeze_results.py` 增加 `--command-receipt <receipt.json>`。research 档只验证三件事：receipt 存在、`exit_code==0`（进程捕获、无法手写）、argv 与 `--command` 一致——这是"命令真实运行过"的真值检查，不需要任何哈希比对；只有 `integrity_mode=submission` 才额外核对 receipt 内的输入/输出哈希与冻结件绑定（该档本来就强制全量哈希）。dev 档允许完全省略 receipt（显式降级）。

### GAP-02 资源单调性无 checker（battle 实锤）

- **证据**：2025A battle 中 Q3（3 枚弹，3.63s）劣于其子集问题 Q2（1 枚弹，4.59s）的解，通过全部 19 项验证义务并冻结（详见 `battle/2026-08-16/reports/battle_review_external_agent.md` §2）。目前义务只存在于 `references/validation/profiles/optimization.md`（文档级）。
- **后果**：这是已知、已发生、未被拦截的错误类别；任何"资源增量"型问题（多弹/多机/多阶段预算）都可能复现。
- **修法**：`check_modeling_plan.py` 或 `evaluate_obligations.py` 增加跨问义务类别 `resource_monotonicity`：声明子集关系的两个 run，其目标值必须满足包含序（以 Q3 为第一验收 case，负例已在 battle 报告中）。

---

## P1：明显流程偏差或防线未闭环

### GAP-03 run_index 建好但零消费者（best-seed 防线未闭合）

- **证据**：`run_and_record.py` 产出并追加 run_index（含 selection_policy/selected），但 `check_gates.py`、`freeze_results.py` 均不读取 run_index。
- **后果**：防"只报最优 seed"的关键防线只剩记录、没有执法：P2 gate 不检查"冻结的 run 是否是 run_index 里 selected 的那个、是否符合声明的 selection_policy"。
- **修法**：`check_gates.py` P2 段：若存在 run_index artifact，则要求冻结 run 的 run_id 出现在 runs[] 且 `selected=true`，且 selection_policy 非空。只看 run_id/exit_code/selected 三个字段，不涉及哈希。

### GAP-04 国赛交付物 result*.xlsx 无符合性检查器

- **证据**：`grep -rln "xlsx|openpyxl" scripts/` 仅命中 `eda/auto_eda.py`（读数据用）。三个结果工作簿是**比赛直接提交物**，目前只靠 battle 里手写的 node 脚本 + 人工预览图。
- **后果**：xlsx 单元格与冻结结果脱节、模板列错位、航向角单位错（度/弧度）、逐弹口径写错，都不会被任何 Gate 拦截。
- **上游对照**：MathModelAgent 把"中间结果落盘"当一等公民并有 writing_check；我们对 JSON 链做了，对**官方模板交付物**没做。
- **修法**：新增 `scripts/qa/check_result_workbooks.py`：按模板表头解析三个 xlsx，逐行校验（速度 ∈ [70,140]、投放间隔 ≥1s、起爆点由投放点+弹道公式重算一致、时长列与冻结值一致），strict 模式阻断。

### GAP-05 diagram/rendered 与正文 `\includegraphics` 无绑定

- **证据**：`grep rendered_paths|includegraphics scripts/qa/` 零命中。`check_diagram_spec` 只验证 spec 声明的文件存在；没有任何检查确认论文实际引用的图 = 合同声明的 rendered_paths。
- **后果**：battle 实际发生过——paper_plan 声明 drawio 渲染，正文塞的是 220 DPI 的 AI 位图，全部 QA 通过。illustration 通道（今天）约束了"合同侧"，但"论文侧实际用了哪张图"仍是盲区。
- **修法**：`check_consistency.py --tex` 路径下：提取正文所有 `\includegraphics{...}`，要求每张正式图路径 ∈ 对应 figure 的 `rendered_paths`（或 illustration 的 data_artifacts），未登记图直接 error。

### GAP-06 人工检查点队列不可见（`harness status` 缺失）

- **证据**：battle 四个 checkpoint 全部 `decision=ask` 堆积，Agent 与人都无法一眼看到"链路被哪个人工确认卡住"；check_gates 只在对应 gate 声明 pass 时才检查 checkpoint。
- **后果**：agent-only 运行的真实断点（人机协作面）没有任何工具暴露；也是 roadmap 里优先级最高的体验项。
- **修法**：`scripts/harness_status.py`（薄封装）：输出 gate 状态、blocked 原因、stale artifacts、**pending human checkpoints 清单**、下一步建议命令，`--json` 供 Agent 消费。

### GAP-07 M1 数学执行器（域/索引/量纲）缺失

- **证据**：状态文档"已排期"表 M1 行；`check_derivation_integrity` 已覆盖符号/断链/操作前提，但 domain（`p∈[0,1]`、`λ≥0`）、index（`t+1` 越界、季节边界）、canonical dimension（加减量纲一致、目标量纲统一）均无执行器。
- **说明**：与 post-audit roadmap Sprint 3 一致，此处确认其仍未完成。

### GAP-08 选择性重跑调度器与敏感性编排器缺失

- **证据**：artifact DAG 只检测 stale（`check_artifact_dag.py`），无调度；`check_sensitivity_experiment.py` 只校验回执，不执行 grid。改一个参数全量重跑在 96h 比赛里是真实成本（battle 中 QA 全链约数分钟/次）。
- **说明**：roadmap 2.1A/2.1D 确认未做；优先级在 S0 闭环之后。

---

## P2：一致性/卫生类

| # | 缺口 | 证据 | 说明 |
|---|---|---|---|
| GAP-09 | abstract.txt 与 LaTeX 摘要双源无一致性检查 | `check_consistency.py:456` 把 abstract 当独立文本源扫描；battle 同时存在 `paper/abstract.txt` 与 `sections/abstract.tex`，二者漂移无人管 | 增加"若 --abstract 与 --tex 同给，tex 内 abstract 环境的关键数字/结论句必须与 txt 一致"或规定单一真源 |
| GAP-10 | measurement snapshot 无 schema | `schemas/` 无 measure* 文件；格式只活在 `validation_obligations.md` 示例里 | 新增 `measurement_snapshot.schema.json`，evaluate_obligations 前先验 |
| GAP-11 | 规则新鲜度只查格式不查时效 | `check_contest_safety.py:89/100` 仅 iso8601 校验 retrieved_at，无 TTL/赛季比对 | 增加"retrieved_at 距今 > N 天且 mode=live_contest → warning/error" |
| GAP-12 | 撤稿状态无在线核验 | `check_citations.py` 无 retraction 入口（literature_evidence.md 列为人肉步骤） | `--check-retractions` 走 Crossref RW API，离线跳过 |
| GAP-13 | 图注声明级 vs 实际文本 | caption_claim 是声明字段；正文实际 caption 未被比对 | nature-skills 的 caption 审思路；低频，人工边界即可 |
| GAP-14 | SKILL.md 膨胀 | 重排+新增后约 300 行，与 roadmap 压缩目标 150–200 冲突 | C1 阶段做，注意不压掉不可违反规则 |

## 工程风险（非功能缺口）

- **GAP-15：123 个文件未提交**。08-15/16 两天的全部工作（strict math 批次、审计整改、battle、43 张卡、CI、新工具）都在工作区里，一次误操作即可丢失。建议按语义分批提交（本轮改动态审计文档可在最后一批）。
- **GAP-16：上游新鲜度复核未执行**。9 个 skill 类上游的吸收裁决固定在 2026-08-08 审计快照；文档已加"赛前复核"声明，但尚未实际复核过一轮。

---

## 与上游机制的对照（缺口 ↔ 来源 skill）

| 上游机制 | 来源 | 我们的状态 |
|---|---|---|
| repro_manifest（argv 真实捕获） | math-modeling-skill | 工具已建（run_and_record），**freeze 未消费**（GAP-01） |
| handoff/run 记账 + 稳定 issue ID | mathodology | run_index 已建，**gate 未消费**（GAP-03）；decision memo 仍是纯文字 |
| 中间结果落盘 + writing_check | MathModelAgent | JSON 链已闭环；**xlsx 官方交付物裸奔**（GAP-04） |
| audit_pdf_text / caption 审 | nature-skills | PDF 数字对账今天已做；caption 实文比对未做（GAP-13） |
| citation 撤稿核验 | agent-research-skills | 未做（GAP-12） |
| 题面不变量→可行域双向检查 | post-audit roadmap M3 | 未做（本轮确认，属 roadmap 范畴，暂列观察） |
| status/CLI | Grok 建议 + roadmap E1 | 未做（GAP-06） |

## 建议的最小闭环顺序（按"防线价值/工作量"）

1. **GAP-01** freeze 收据绑定（~半天，闭死数值链根基）
2. **GAP-02** 资源单调性 checker（~半天，battle 负例现成）
3. **GAP-03** run_index 消费进 P2 gate（~2 小时）
4. **GAP-05** includegraphics↔rendered_paths 绑定（~2 小时，防 AI 图冒名复发）
5. **GAP-04** xlsx 符合性检查器（~1 天，国赛交付物）
6. **GAP-06** harness status（~1 天，含 checkpoint 队列）
7. 其余 P2 按顺手顺序；**GAP-15 立即分批提交**。

## 闭环执行记录（2026-08-16，同日完成）

以下缺口已实现并有回归测试（全量 305/305 通过）：

| 缺口 | 落地 | 测试 |
|---|---|---|
| GAP-01 | `freeze_results.py --command-receipt`：research 档验证收据存在 + `exit_code==0` + argv 与 `--command` 一致（无哈希）；`frozen_results.schema.json` 新增可选 `command_receipt` 块；无收据时字段缺省（不写 null） | `test_gap_closures.py::test_freeze_requires_command_receipt_consistency`（argv 不匹配被拒） |
| GAP-02 | 新 `scripts/qa/check_resource_monotonicity.py`：spec 声明 baseline/superset 指标对 + 方向，跨 run 比较，违反即 error | `test_resource_monotonicity_*`（battle Q3 负例 FAIL、等值/更优 PASS） |
| GAP-03 | `check_gates.py` P2 段消费 `run_index`：存在则要求当前 run 被 `selected=true` 且 exit 0；`run_index` 加入 artifact role enum | `test_gate_p2_consumes_run_index`（wiring 无假阳性） |
| GAP-05 | `check_consistency.py`（--paper 为 .tex 时）：递归收集 `\includegraphics`，未登记图 warning（strict 档阻断）、声明的 rendered 全未引用则 warning | illustration 夹具补 includegraphics 后全绿 |
| GAP-04 | 新 `scripts/qa/check_result_workbooks.py`：按官方模板表头匹配 result1/2/3，校验航向角 [0,360]、速度 [70,140]、起爆 z<投放 z、时长列与冻结 display 一致（openpyxl） | （工具就绪；真实 xlsx 校验留 battle 复用） |
| GAP-06 | 新 `scripts/harness_status.py`：gate 状态、首个阻塞门、pending human checkpoints、缺失登记文件、下一步建议；`--json` 供 Agent | `test_status_reports_pending_checkpoint_and_next_action` |

**哈希口径**（按用户裁决）：GAP-01/GAP-03 只比较数值与退出码，不引入本地哈希；哈希核对仍仅在 `integrity_mode=submission` 档（规则 9 既有一致）。

**尚未执行**：GAP-07（M1 域/索引/量纲执行器）、GAP-08（选择性重跑/敏感性编排器）、GAP-12（撤稿在线核验）、GAP-13（caption 实文比对）、GAP-15（分批提交，工作区 123+ 文件）、GAP-16（上游新鲜度复核）——按 roadmap 优先级，先提交再排期。
