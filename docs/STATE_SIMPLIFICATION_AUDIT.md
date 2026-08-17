# State Simplification Audit

审计日期：2026-08-17  
审计分支：`agent/math-modeling-harness`  
审计性质：架构收敛前的只读审计；本文不代表代码、Schema 或迁移已经实现。

## 1. 结论先行

当前问题不是“29 个 Schema 太多”，而是四个事实域的 ownership 没有收口：

1. **Competition Profile 双源且 ontology 不兼容**：`profile_engine.py` 生成的独立 profile 使用 `competition_profile.schema.json`，实际 Safety、Gate、S1、F1 却读取 `run_manifest.competition_profile` 的另一套结构。独立 profile 不是当前消费者的真源。
2. **Command State 三写**：`command_receipt` 已能捕获真实进程事实，`run_index` 又复制 argv/exit code，Gate 仍以人工填写的 `run_manifest.commands[]` 判定 smoke/full/freeze。
3. **Artifact identity/digest 多写**：`run_manifest.artifacts[]`、`artifact_dag.nodes[].inputs/outputs`、`paper_plan.*.data_artifacts/rendered_paths` 和各 evidence 文件都可保存 path/hash；它们能各自通过 Schema，却可指向不同版本。
4. **Profile/Gate 状态是组合式声明，而非单次解析结果**：`integrity_mode × enhanced_integrity_profile × math_correctness_profile × editorial_semantics_profile × reviewer.profile` 有 72 种理论组合；`check_gates.py` 中存在分散的组合判断，Gate 只在 manifest 自报 `pass` 时执行相应阶段检查。

建议的收敛边界是：

- 保留少量有意识维护的合同，不机械合并独立生命周期的 Schema；
- `run_manifest v2` 仅作为 control plane，保存 preset、当前 stage、少量 root reference、安全/人工决策，不复制 profile、command、artifact 或 Gate 结果；
- 独立 `competition_profile.json` 成为唯一比赛规则/提交 profile；
- `command_receipt` 成为执行事实真源，`run_index` 成为可重建 ledger/selection projection；
- 在现有 `artifact_dag` 上最小增强，使其成为 artifact identity、dependency、freshness 的 canonical graph；不新增第二个 registry；
- `sprint | research | submission` 解析成唯一 `ResolvedCapabilities`，所有 Gate 只消费 capability flags；
- Hash 只用于身份、冻结、关键 I/O provenance 和最终提交；每个关键 artifact 只有一个 digest owner，SHA-256 由关键 Gate 重算；Hash 不代表语义正确。

## 2. 审计范围与证据

已完整读取：

- 用户主需求 977 行，SHA-256 `B07A95DC1DA415EB0F8663CF87935A5BF586CBF232AF55238940041EB57B5FA4`；
- 追加的 Hash / Integrity Policy 330 行，SHA-256 `D721D54AB3FD45AE47630902FE2060C8BC9284B4EC7FAD5391CC34114C00CFA6`；
- `README.md`（555 行）、`SKILL.md`（307 行）；
- `docs/MATH_HARNESS_IMPLEMENTATION_STATUS.md`；
- `docs/CAPABILITY_GAP_AUDIT_2026-08-16.md`；
- `references/contracts/artifact_contracts.md`；
- `references/workflow/gate_policy.md`；
- 九个重点 Schema 全文：`run_manifest`、`competition_profile`、`artifact_dag`、`command_receipt`、`run_index`、`model_contract`、`frozen_results`、`evidence_registry`、`paper_plan`；
- `scripts/run_and_record.py`、`scripts/harness_status.py`、`scripts/freeze_results.py`、`scripts/freeze_submission.py` 全文；
- `schemas/` 全量结构、`scripts/qa/` 全量入口/引用关系及高风险消费者实现。

审计期间未直接检查或修改未跟踪的 `battle/` 内容；完整回归中的既有资源单调性测试会按其现有实现读取一个 battle 路径，但未对该目录写入。

## 3. 分类口径

| 分类 | 定义 | 写入规则 |
|---|---|---|
| A. `AUTHORITATIVE_CONTRACT` | 人或 Agent 有意识维护的研究、规则或决策合同 | 允许有审计过的人工编辑；必须有明确 owner；不能混入可重算 PASS |
| B. `GENERATED_EVIDENCE` | 一次真实执行、验证、冻结或人工审阅动作产生的 evidence | 由受控 producer 生成或签认；不可手改 verdict/exit code；immutable evidence 不覆盖 |
| C. `INDEX_OR_PROJECTION` | 可从 A + B 重建的索引、DAG、inventory、status 或 QA summary | 不得成为人工事实源；删除后可重建；默认不要求 Hash |
| D. `LEGACY_OR_REDUNDANT` | ownership 已被其他真源覆盖，或只是为单一错误类型增加的平行状态 | v1 只读兼容；显式迁移和 deprecation；不得继续成为新项目输出 |

“人工审阅 receipt”按生命周期归入 B：它不是研究合同，虽然 verdict 必须由真人/多模态签认。Evidence Registry 是唯一例外的混合账本，文件级归 A，但必须执行 entry-level ownership：文献核验由人维护，result evidence 只能由程序写入。

## 4. Before complexity baseline

| 指标 | 当前值 | 计量说明 |
|---|---:|---|
| Schema 数量 | 29 | `schemas/*.json` |
| QA 脚本 | 30 / 9,795 行 | `scripts/qa/*.py` |
| Schema 中含 digest/hash 定义的文件 | 24 / 29 | 字段名匹配 `sha256|digest|hash` |
| digest/hash 字段定义位置 | 46 | 递归统计 Schema property 定义；不是运行时 artifact 数量 |
| 人工/Agent 直接编写或确认的 schema-backed JSON 类型 | 至少 15 | 12 个常规合同/控制文件 + 3 个条件性人工签认/证书；混合 producer 也计入维护面 |
| 重复 canonical domain | 4 | Competition Profile、Command State、Artifact/digest、Profile/Gate resolution |
| 重复 semantic field family | 至少 25 | profile 至少 9、command 至少 10、artifact/digest 至少 6；名称不同但语义相同也计入 |
| 用户级 profile 维度 | 5 | integrity、enhanced、math、editorial、reviewer |
| profile 理论组合 | 72 | `3 × 2 × 2 × 2 × 3` |
| 推荐 enhanced M1 的 schema-backed JSON | `6 + N` | manifest、model、evidence、problem、implementation、DAG，加 N 个 data contract；N=1 时为 7 |
| README enhanced W2 的路径参数 | 14 | 13 个输入/辅助路径 + output；尚未含所有 strict 条件 artifact |
| `SKILL.md` | 307 行 | 目标为约 150–220 行 |
| `README.md` | 555 行 | 大量底层命令参数暴露给 Agent |
| 新项目需要理解的关键选择 | 至少 7 | competition、mode、integrity、enhanced、math、editorial、reviewer；未计各 require flag |
| 当前回归 | 286 运行，284 成功，2 errors | 2026-08-17 fresh run；不是绿色基线 |
| 独立 capability benchmark | 未完成 | 文档明确 Batch E / 跨题型 benchmark 未执行；regression 不等于 capability proof |

回归的两个 error 必须作为重构前置风险保留：

1. `tests/test_enhancements.py` 导入失败：`ModuleNotFoundError: No module named 'numpy'`；
2. `test_battle_q3_regression_fails_with_worse_superset` 的子进程 stdout reader 以 UTF-8 解码 Windows 输出失败，随后 `result.stdout is None`。

因此不能把历史文档中的 `305/305` 作为当前 checkout 的已验证基线。后续每个工作包应先跑其定向测试，最终修复/隔离环境问题后再报告完整 regression 数量。

## 5. 完整 State / Artifact 分类表

### 5.1 全部 29 个 Schema-backed artifact

| State / Artifact | 分类 | 当前事实源 | 人工编辑 | 程序生成 | 当前 producer | 当前 consumer | 重复/冲突 | Canonical owner 与建议处置 |
|---|---|---|---|---|---|---|---|---|
| `artifact_dag.json` (`artifact_dag.schema.json`) | C | `artifact_dag.nodes[]` | **是（当前）** | 否 | 人/Agent 手写 | `check_artifact_dag.py`、`check_gates.py`、deterministic QA/consistency | 与 manifest artifacts、receipt I/O、paper plan 路径/hash 重复 | **目标 owner：现有 DAG**。v2 由 projector 自动生成；按 artifact_id 记录 identity/dependency/freshness；移除人工 status/digest 维护，不新建 registry |
| `build_receipt.json` (`build_receipt.schema.json`) | B | 实际 LaTeX 子进程与隔离构建 | 否 | 是 | `safe_build.py` | W2 Gate、template/PDF 链 | manifest 再登记 path/hash | receipt 拥有构建事实；artifact 文件身份由 digest policy 指定 owner；不可手改 `ok/exit_code/source_unchanged` |
| `claim_inventory.json` (`claim_inventory.schema.json`) | C | draft + paper plan + frozen/evidence 输入 | 否 | 是 | `inventory_claims.py` / deterministic QA | W2 Gate、Writer QA | 与 paper plan claims 表面相似，但它是“正文扫描结果” | 保留为可重建 projection；不做 canonical claim store；默认不 Hash |
| `command_receipt.json` (`command_receipt.schema.json`) | B | 真实 subprocess | 否 | 是 | `run_and_record.py` | `freeze_results.py`（当前可选）；目标为 P1/P2 Gate、run index projector | 与 `run_manifest.commands[]`、`run_index.runs[].argv/exit_code` 重复 | **执行事实 owner**：argv、cwd、exit、时间、stdout/stderr、seed、关键 I/O；immutable append-only |
| `competition_profile.json` (`competition_profile.schema.json`) | A | 当前独立 profile 与 manifest 内嵌 profile 两套 | 是（YAML/preset） | `profile_engine` 解析 | `profile_engine.py` + 人工补当届规则 | 独立输出几乎无人消费；Safety/S1/F1 消费 manifest 内嵌版本 | **P0 双 ontology**：字段名、规则结构、AI/提交结构不兼容 | **唯一 owner：独立 canonical profile v2**；保留独立 Schema；manifest 只保留 path/profile_id（可选 snapshot binding）；消费者统一 dereference |
| `data_contract.json` (`data_contract.schema.json`) | A | 每个权威数据集一份 | 初稿后人工确认 | 是（初稿） | `profile_generator.py` + 人工确认 | data checker、M1 Gate、strict QA | 与 model contract `data_sources/decision_context` 有边界交叠 | 保留独立生命周期；data contract 拥有列/单位/主键/leakage 语义，model 仅按 data_id 引用；关键 dataset digest 由统一 digest owner 管理 |
| `derived_results.json` (`derived_results.schema.json`) | B | frozen results + derivation spec | 否 | 是 | `derive_results.py` | Writer package、math writing、W1 Gate | paper plan 只应保存 derived_result_id | 保留生成 evidence；不得手算；自身可保存派生 payload identity，其他文件只引用 ID |
| `diagram_spec.json` (`diagram_spec.schema.json`) | A | 每张 concept/flow/framework 图的设计合同 | 是 | 可由 Agent 起草 | Writer/Agent；`generate_drawio.py` 只渲染 | draw.io generator、diagram/figure checker、paper plan | paper plan 又复制 diagram path/rendered paths/status | 保留独立 per-figure contract；paper plan 仅引用 diagram artifact_id；渲染件进入 DAG |
| `evidence_registry.json` (`evidence_registry.schema.json`) | A（混合） | 唯一增量 Evidence Registry | 文献 entry 是 | result entry 是 | 人工 seed/核验 + `register_evidence.py` | modeling plan、contracts、readiness、Writer、W1/W2 | 重复 frozen result IDs 是合法引用；不得复制 claim 反向表 | 保留唯一 registry；文献核验为人工 owner，result evidence 为程序 owner；禁止另建 Claim-Evidence 系统 |
| `extremum_certificate.json` (`extremum_certificate.schema.json`) | D | 人/Agent 填 grid/refinement 后 checker 重算部分字段 | **是（当前）** | 无 in-repo producer | 外部模型流程/人 | extremum checker、deterministic QA | 与 model `verification_obligations`、validation report 重叠；典型“一种错误一个证书” | v1 只读兼容；把 obligation type 与路由放入统一 verification obligation，checker 保留；新项目不再要求独立 certificate Schema |
| `failure_evidence.json` (`failure_evidence.schema.json`) | B | failed frozen run + validation report | 否 | 是 | `compile_failure_evidence.py` | failure checker、P2 failed/blocked Gate | 复制 failure verdict/obligation 摘要，但作为诊断快照有独立生命周期 | 保留；diagnostic-only、不可进入 claim registry；不覆盖失败历史 |
| `figure_qa.json` (`figure_qa.schema.json`) | B | figure artifact + visual profile 的检查执行 | 否 | 是 | `check_figure.py` | figure review/人工审阅 | 与 QA summary 有投影关系 | 保留细粒度 receipt；聚合状态为 C；非 submission-critical 时默认不 Hash |
| `frozen_results.json` (`frozen_results.schema.json`) | B | source result + model snapshot + validation recomputation | 否 | 是 | `freeze_results.py` | evidence registry、paper plan/Writer、W1/W2、submission chain | `command` 自由文本与 receipt 重复；多处复制 input/code/report hash | **结果真源**保留。只接受 selected receipt；冻结后 immutable；新版本新 artifact_id/digest，触发下游 invalidation |
| `implementation_map.json` (`implementation_map.schema.json`) | A | equation/symbol → code/test mapping | 是 | 否 | 人/Agent | implementation checker、M1 Gate、strict QA | 与 model `plan_details` 有引用交叠 | 保留独立代码生命周期；model 拥有数学语义，map 只引用 equation/symbol ID 并拥有实现映射 |
| `model_contract.json` (`model_contract.schema.json`) | A | M1 研究与数学决策 | 是 | 可由 Agent 起草 | Researcher/Modeler/Agent + human M1 | modeling/derivation/scope/formula/data/implementation/validation/Writer/Gates | 与单项 certificate 义务、data/implementation 细节有边界交叠 | **研究决策 owner**；统一 `verification_obligations` 描述/路由放这里，checker 不必合并；不吸收运行证据 |
| `oos_artifact.json` (`oos_artifact.schema.json`) | B | 独立 train/test 场景生成执行 | 不应 | 是（由项目运行） | 模型/OOS 生成程序 | OOS checker、P2 Gate、strict QA | measurement/validation report 引用其结论 | 保留独立 evidence；必须真实计算场景 identity/disjointness，不能手填 PASS |
| `paper_plan.json` (`paper_plan.schema.json`) | A | W1 claim/argument/section/display plan | 是 | 可由 Agent 起草 | Writer planner + human W1 | readiness、Writer package、claim inventory、consistency、math writing、Gates | `data_artifacts`/diagram rendered paths 复制 artifact identity；claim IDs 对 evidence/result 的引用是必要关系 | **claim/argument owner**；所有 artifact path/hash 改为 artifact_id；不拥有 evidence verification 或 result 数值 |
| `pdf_visual_qa.json` (`pdf_visual_qa.schema.json`) | B | 实际 PDF inspect/render | 否 | 是 | `check_pdf.py` | W2 Gate、visual review | manifest 再登记 paper/report hash | 保留 formal/render receipt；submission 时必须绑定最终 PDF artifact_id；普通 research 中不为 summary 递归 Hash |
| `presentation_contract.json` (`presentation_contract.schema.json`) | A | result display/rounding/unit/macro | 是 | 可由 Agent 起草 | W1/Presentation author | presentation checker、`generate_values_tex.py`、strict Gate | paper plan 也保存 display/figure/table 语义 | 保留独立展示生命周期；只引用 frozen result_id/artifact_id，不复制 artifact digest |
| `problem_snapshot.json` (`problem_snapshot.schema.json`) | A | 题面、附件与 requirement matrix | 是/确认 | 可由导入器生成初稿 | Ingestion/Agent + human confirm | coverage checker、M1/W1 Gate | model questions、paper requirements 重复 ID 但关系必要 | 保留；拥有官方题面 identity/requirements，model/paper 只引用 requirement_id；实际题面 digest 由统一 owner |
| `run_index.json` (`run_index.schema.json`) | C（当前混合） | receipts 的 append ledger + selection | 通过 CLI 传 selection policy/selected | 是 | `run_and_record.py` | P2 Gate | 复制 receipt argv/exit；selection policy 藏在 projection 内 | 将 selection policy/selected decision 移入 control contract；index 由 receipts + policy 重建，只保留 receipt/artifact IDs 与投影字段 |
| `run_manifest.json` (`run_manifest.schema.json`) | A（需瘦身） | 当前全能控制面 | **是** | 否 | 人/Agent | Safety、all Gates、status、S1/F1 | 内嵌完整 profile、commands、artifacts、Gate/reviewer states 与各真源重复 | **v2 control owner**只保留 project/run/stage、preset/overrides、root refs、安全/AI/human decisions、selection/revision config；重复字段迁为 D |
| `sensitivity_experiment.json` (`sensitivity_experiment.schema.json`) | B | 每个 grid rerun 的执行结果 | 不应 | 是（由项目运行） | 模型/实验编排 | sensitivity checker、P2 Gate、strict QA | model 只应声明 obligation/experiment_id | 保留独立 evidence；每个点绑定真实 receipt；不为每种 sensitivity 再建新 Schema |
| `submission_manifest.json` (`submission_manifest.schema.json`) | B | 通过 S1 后的最终包冻结 | 否 | 是 | `freeze_submission.py` | submission manifest checker、portal handoff | 当前再冻结完整 embedded profile/run manifest hash | 保留 F1 immutable evidence；v2 绑定 canonical profile artifact_id/version、最终 artifact IDs 与唯一 digests；禁止覆盖 |
| `submission_receipt.json` (`submission_receipt.schema.json`) | B（人工签认） | 官方门户真实提交动作 | 不应事后编辑 | 半人工 | 人执行门户提交，受控记录器待补 | 人工审计/最终交付 | 与 F1 最终文件 identity 有必要绑定 | 保留独立 post-F1 evidence；只能记录真实门户结果，不能预填 accepted；不自动上传 |
| `template_contract.json` (`template_contract.schema.json`) | A | 实际模板身份/入口/命令 | 模板维护者可编辑 | importer/init 生成 | template importer/initializer + maintainer | template usage、safe build、W2 Gate | competition profile 的 `base_template` 只应引用 template_id | 保留独立模板生命周期；canonical competition profile 引用 template_id，不复制模板规则 |
| `validation_report.json` (`validation_report.schema.json`) | B | model obligations + measurement snapshot 的独立重算 | 否 | 是 | `evaluate_obligations.py` | freeze results、P2 Gate | frozen results 保存 report refs/verdict 摘要是冻结证据所需 | 保留；verdict 必须重算；measurement 格式先由 evaluator 内部验证，不因缺 Schema 立即新建 Schema |
| `visual_profile.json` (`visual_profile.schema.json`) | A | 比赛视觉/版式约束 | 是（赛前锁定） | 可由 preset 产生 | profile maintainer | PDF/figure checker | competition profile page/template 字段可能越界 | 保留独立 profile extension；competition profile 只引用 visual_profile_id；明确 page-limit 属比赛 profile、page geometry/typography 属 visual profile |
| `visual_review_receipt.json` (`visual_review_receipt.schema.json`) | B（人工/多模态签认） | 同一 PDF 的逐页视觉审阅 | 不应事后编辑 | 工具可起草 | human/multimodal reviewer | W2 Gate、F1 audit | 与 PDF QA 和 manifest 的 PDF hash 重复 | 保留；只引用 reviewed PDF artifact_id 和 pdf_visual_qa ID；最终 digest 从 canonical owner 重算 |

### 5.2 Schema-less 或 nested state

| State / Artifact | 分类 | 当前 owner/producer | 当前 consumer | 重复与处置 |
|---|---|---|---|---|
| `run_manifest.competition_profile` | D | 人/Agent 内嵌 | Safety、Gate、S1/F1 | v1 adapter 读取；迁移为独立 canonical profile；v2 禁止完整内嵌 |
| `run_manifest.commands[]` | D | 人/Agent | P1/P2 Gate | 删除 v2 写路径；Gate 从 run index dereference receipt 并重算 |
| `run_manifest.artifacts[]` | D | 人/Agent | 所有 Gate/status | 迁移到现有 artifact DAG；v2 manifest 仅保留 DAG root reference |
| `run_manifest.gates.*.status/evidence` | C（当前人工） | 人/Agent 手动更新 | `check_gates.py` 决定是否检查 | 改为 Gate 执行 receipt/status projection；manifest 只保存当前 stage，不相信自报 PASS |
| `run_manifest.reviewer.*.status/report` | B/C 混合 | reviewer + 人工写 status | W2 Gate | reviewer report 是 B；聚合 status 是 C；control 只保存 reviewer policy/preset |
| `run_manifest.safety/events` | A/B | policy 是 A；真实 event 是 B | contest safety | 可继续嵌在 control，但 policy 决策和 event receipt 必须区分，不把 event PASS 当合同 |
| `run_manifest.ai_usage[]` | A/B 签认 ledger | AI interaction + human verification | Safety、S1/F1 | 保留单一 ledger；不另建 AI registry；submission 才绑定最终 disclosure |
| `run_manifest.human_checkpoints[]` | B 签认 ledger | 真人 | Gates、S1/F1、status | 保留不可代签；过期由 artifact invalidation 标记，不靠更新时间猜测 |
| `ResolvedCapabilities` | C | `resolve_profile(profile, overrides)` | 所有 Gate/checker/CLI | 新增为内存或可重建 JSON 输出，不成为人工文件；取代散落 profile if/else |
| `harness status` 输出 | C | `harness_status.py` | 用户/Agent | 当前只看 manifest 且未真正读取 DAG stale；改由 Gate/DAG/receipt 重建；默认不 Hash |
| `writer_package.json` | C | `compile_writer_package.py` | Writer、W2 checks | 只读 projection；可重建；不做第六个 claim/evidence 真源 |
| `deterministic_qa.json` / QA summary | C | `run_deterministic_qa.py` | W2 Gate/status | 可重跑的 projection；submission-critical Gate 重算关键事实，不信任孤立 `ok=true`；默认不递归 Hash |
| `submission_qa.json`（S1 report） | B | `check_submission.py` | `freeze_submission.py` | 保留为最终检查 evidence；绑定 canonical profile、human checkpoint、最终 artifact IDs/digests |
| measurement snapshot | B | 项目 validator/model run | validation evaluator | 当前无 Schema；先在 evaluator 中做严格结构验证，除非证明独立兼容/version lifecycle，否则不新增 Schema |
| raw result / selected model output | B | selected run | freeze results | 在 freeze 前 mutable；接受后产生新 immutable artifact/version；不得原地覆盖 |
| result workbooks / final tables / figures | B | deterministic exporter | checker、paper、submission | research 只 Hash canonical evidence；submission Hash 最终交付链；paper plan 只引用 artifact_id |
| semantic critic / blind review report | B | reviewer | W2 Gate/status | report 是 evidence，汇总状态是 projection；profile 解析只决定要求几个 review，不复制 report identity |

## 6. P0 ownership decisions

### 6.1 Competition Profile

当前独立 Schema 使用 `competition_family/rules.page_limit/ai_disclosure/submission.required_files`；manifest 内嵌 Schema 使用 `competition/mode/official_rules/official_submission_endpoints/submission.max_pages/...`。这不是同一对象的两种序列化，而是两套 ontology。

决定：

- `competition_profile.json v2` 是唯一 canonical representation，并保留独立 Schema；
- v2 至少覆盖 contest identity、season/mode、official rule snapshot artifact IDs、official endpoints、submission/AI/manual-check policy、template/visual profile IDs；
- `profile_engine` 的内置 YAML 是 preset/seed，不等于当届 official profile；项目 init 后必须补齐当前规则 snapshot，不能把 community preset 冒充官方规则；
- `run_manifest v2` 只保存 `{path, profile_id}` 或等价 root reference，不复制 profile 内容；
- `check_contest_safety.py`、`check_gates.py`、`check_submission.py`、`freeze_submission.py`、`check_submission_manifest.py`、`validate_contracts.py` 统一通过 resolver 读取 canonical profile；
- v1 embedded profile 由 adapter 读；`harness migrate` 抽取为独立文件并报告 inferred/unresolved，关键规则不得静默猜测。

### 6.2 Command State

当前 `check_gates.py` 仍用 `run_manifest.commands[]` 的 `stage + exit_code` 判定 P1/P2；`run_index` 仅在注册时可选消费；`freeze_results.py --command-receipt` 也是可选，且没有 `integrity_mode` 参数，当前实现并未兑现“research 要求 receipt、submission 再核关键 I/O hash”的文档口径。

决定：

- receipt 是 argv、exit、time、stdout/stderr、seed、关键 inputs/outputs 的唯一执行真源；
- control 保存 pre-declared selection policy；run index 只从 receipts + policy 生成；
- Gate 不再消费 `run_manifest.commands[]`，而是 `run_index -> receipt` dereference 后检查；
- P1 需要成功 smoke receipt；P2 需要 selected full receipt、freeze receipt、selected frozen run 一致；失败 receipt 永久保留；
- `freeze_results` 接受 receipt ID/path，不再同时要求自由文本 command；v1 `--command` 只在 adapter 中兼容并发 warning；
- research 必须核对 selected run 的关键 I/O SHA-256，submission 对最终链重算；sprint 允许只记录 identity/path/time，显式 freeze 时才产生关键 digest。

### 6.3 Artifact identity / DAG

当前 DAG 有正确的 cycle、producer、digest、stale 检查，但其 Schema 强制每个 input/output/receipt 都带 hash，且 DAG 由人/Agent 编写。这同时违反“projection 可重建”和“Hash critical evidence, not everything”。`harness_status.py` 声称显示 stale artifacts，实际只报告 manifest 已登记但不存在的路径，不读取 DAG status/digest。

决定：

- 最小增强现有 DAG，不新增 `artifact_registry_v2.json`；
- artifact 的 canonical metadata 为 `artifact_id, role, path, producer_id, input_artifact_ids, lifecycle, current/version`，critical 时再有一个 canonical SHA-256 owner；
- DAG 由 contracts、receipts、generated evidence 和 control roots 自动投影；手改 DAG 不能改变事实；
- paper plan、manifest、status、QA summary 只引用 artifact_id；
- stale/current 由 digest/version/dependency 重算，不接受人工 `status=current`；
- mutable artifact 可原地演进但不能进入 frozen truth；immutable artifact 修改必须产生新 version/artifact_id/digest，并 invalidates downstream Gate/F1；历史文件不覆盖。

## 7. Profile convergence

### 7.1 唯一用户路径

| Preset | 必须能力 | Hash 策略 |
|---|---|---|
| `sprint` | contest safety、最小 M1/P1、风险驱动检查、真实 run identity、human boundary | 默认不全量 Hash；显式 freeze 才 Hash 关键 result |
| `research`（默认） | 完整 evidence chain、正式 validation、selected-run enforcement、高风险 math/figure lineage、human checkpoints | Hash authoritative dataset、selected run 关键 I/O、frozen result、canonical paper evidence |
| `submission` | research 全部 + strict math/editorial + current template/PDF/rules/bibliography + S1/F1 immutability | Hash competition profile snapshot、authoritative data、selected receipts、frozen results、canonical tables/figures、最终 source/PDF/package |

`resolve_profile(profile, overrides) -> ResolvedCapabilities` 是唯一解析入口。Gate 只读 capability flags，例如 `require_scope_contract`、`require_formula_replay`、`require_selected_run_receipt`、`require_final_pdf_hash`。高级 override 只允许白名单字段，不能关闭 contest safety、human checkpoints、independent validation、result freeze 或 submission immutability；override 不算新的受支持 preset 组合。

v2 顶层不再平铺 `integrity_mode`、`enhanced_integrity_profile`、`math_correctness_profile`、`editorial_semantics_profile`、`reviewer.profile`。v1 adapter 把旧组合解析成 capability set，并在不等价或冲突时要求 manual review。

## 8. Hash / Integrity ownership policy

### 8.1 单一 digest owner

| Artifact 类别 | Canonical digest owner | 其他文件如何引用 |
|---|---|---|
| official rule snapshot、authoritative dataset、canonical figure/table、frozen artifact 文件身份 | generated artifact metadata / artifact DAG 中该 artifact_id 的唯一记录 | 只引用 artifact_id；不得再写 path + sha256 |
| selected run inputs/outputs | immutable `command_receipt` | run index/DAG 引用 receipt_id 与 artifact_id；投影可展示 digest，但不得作为第二真源 |
| frozen results 内部 canonical results payload | `frozen_results.results_sha256` | Registry/Paper Plan 只引用 result_id/frozen artifact_id |
| final PDF、support/package、submission-relevant source | `submission_manifest` | submission receipt 绑定 F1 artifact_id；关键 Gate 现场重算 SHA-256 |
| rebuildable index/status/claim inventory/intermediate QA | 无默认 digest owner | 从 A+B 重建；只有进入 submission-critical chain 才由最终 manifest 冻结 |

如果一个 projection 为可读性展示 digest，必须标记 `projected_from`，并由生成器复制/重算；消费者仍回到 canonical owner 比较，不能把 projection 当第二真源。

### 8.2 Recompute、生命周期与语义边界

- 算法统一 SHA-256；不引入多算法、Merkle tree、区块链、签名或 content-addressable storage；
- W2 对 frozen/canonical evidence、S1/F1 对最终 PDF/package 实际重算；不相信 `hash_verified=true`；
- sprint 不 Hash cache、临时图、debug、status、claim inventory、普通 reference；
- research 只 Hash 决定正式结果复现与论文主张的对象；
- submission 冻结完整最终交付链；
- Hash mismatch 导致 Gate FAIL 或要求新 freeze；不可通过改 hash 覆盖旧 evidence；
- 正确顺序必须是 `semantic validation -> accept -> freeze -> hash bind`。Hash 只能证明“字节未变”，不能证明 leakage、objective、数学、统计单位或图结论正确。

## 9. Schema expansion rule

新 Schema 必须同时回答：独立生命周期是什么、producer 是谁、consumer 是谁、为何需要独立 compatibility/versioning、为何不能作为现有 obligation。缺一项即不新增。

统一 verification obligation 只统一**描述与路由**，不把现有 checker 合成巨型 checker。候选 type 可覆盖 numeric replay、domain、unit、monotonicity、boundary、conservation、PSD、convexity、tiny oracle、grouped split、objective recompute、sensitivity、OOS。`extremum_certificate` 是首个 v1 deprecation 候选；measurement snapshot 先采用 evaluator 内部结构校验，不因“现在没有 Schema”自动新增 Schema。

## 10. Migration and compatibility gates

1. v1 reader/adapter 与 v2 writer 分开；新项目只写 v2；checker 核心只消费 normalized state。
2. `harness migrate --project <path>` 输出 `migrated / inferred / unresolved / deprecated / manual_review_required`。
3. 抽取 embedded competition profile；关键 official-rule/submission 语义不全时停止，不猜测。
4. 将 manifest commands 对齐到 receipts；没有真实 receipt 的旧 command 标记 unresolved/legacy declaration，不能升级为真实执行。
5. 由 manifest artifacts、existing DAG、receipts 构建 artifact_id；冲突路径/version 必须报告，不自动选 v1/v2/v3。
6. selection policy 从 run index/control 迁移；多个 selected 或缺 policy 必须人工处理。
7. 旧 frozen results/submission manifest 原样保留；迁移只建立引用/adapter，不改历史语义或 digest。
8. v1 deprecation warning 有结束策略；不得永久在每个 checker 内维护两套分支。

最低测试：v1 embedded profile、legacy commands、legacy artifacts、v1->v2 report、profile page-limit 冲突、DAG result_v2 vs legacy result_v1、selected receipt/frozen run 不一致、mutable/immutable invalidation、final PDF drift、sprint 无多余 hash、research 关键 I/O hash、submission 完整链重算。

## 11. 可执行分阶段实现计划（最多三个工作包）

以下工作包按 **WP1 -> WP2 -> WP3** 串行集成。每个包适合由 `gpt-5.6-luna`、`reasoning_effort=max` 执行；每包先读本文和自己拥有的文件，不加载全部 references。`battle/` 不属于任何文件所有权，不得修改。

### WP1 — Contract normalization、profile resolver 与 migration

**依赖**：无。  
**目标**：先定义唯一 state ownership 和 v1/v2 normalization，不碰 Gate 行为。

**文件所有权**：

- 所有 `schemas/*.schema.json`（独占；其他包不得改 Schema）；
- `competition_profiles/*.yaml`；
- `scripts/profiles/profile_engine.py`；
- 新的单一 normalization/profile module 与 migration CLI/script；
- `docs/MANIFEST_V2_DESIGN.md`、`docs/MIGRATION_GUIDE_V1_TO_V2.md`；
- 新增 migration/profile/schema 专属 tests/fixtures。

**实现要点**：

- canonical competition profile v2 + manifest v2 slim refs；
- three presets -> resolved capability flags；
- artifact DAG v2 的 artifact_id/lifecycle/digest-owner contract；
- run index v2 只作 projection，selection policy 归 control；
- legacy `extremum_certificate` deprecation 路径，不删除 checker；
- normalized internal representation，使 WP2 不维护双分支；
- migration report，不猜关键语义，不改 historical frozen evidence。

**测试**：所有 Schema validation；3 presets golden capabilities；unsafe override negative；profile extraction；v1 commands/artifacts conflicts；v1->v2->normalized equivalence；new project only emits v2。

**主要风险**：两个 profile ontology 无法无损映射；Schema `oneOf` 变成永久双复杂度。缓解：adapter 在边界，core 只见 normalized v2；unresolved 立即人工复核。

### WP2 — Receipt/DAG/Gate consumers 与 integrity enforcement

**依赖**：WP1 的 normalized API 与 Schema 固定。  
**目标**：让现有 checker/Gate 改读唯一真源并执行风险分级 Hash；不新增 orchestration。

**文件所有权**：

- `scripts/run_and_record.py`、`scripts/freeze_results.py`、`scripts/freeze_submission.py`；
- `scripts/qa/check_gates.py`、`check_contest_safety.py`、`check_submission.py`、`check_submission_manifest.py`、`validate_contracts.py`、`check_artifact_dag.py`；
- artifact DAG projector（新脚本可建，但不得建第二 registry）；
- receipt/gate/digest/invalidation 专属 tests。

**实现要点**：

- 删除 v2 consumer 对 manifest commands/artifacts/embedded profile 的依赖；
- run index dereference immutable receipts，验证 selected full/freeze/run；失败 runs 保留；
- freeze 不再信自由文本 command；research/submission 强制相应关键 I/O binding；
- DAG 自动生成并重算 producer/dependency/stale；
- per-artifact digest owner，其他文件仅 artifact_id；
- mutable -> immutable versioning 与 downstream invalidation；
- W2/S1/F1 重算 SHA-256，同时继续独立重算 semantic checks；
- v1 只经 WP1 adapter；新路径发 deprecation warning。

**测试**：命令 receipt mismatch、manifest fake success、index copy tampering、artifact version divergence、digest owner duplication、research selected I/O、submission final PDF drift、failure receipt retention、old frozen artifact unchanged。

**主要风险**：`check_gates.py` 1,283 行且现有行为依赖“自报 pass 才检查”，一次修改可能改变大量旧 fixture。缓解：按 M1/P1/P2/W1/W2/S1 分段 golden test；不重写底层 checker；先 adapter 后删除重复读路径。

### WP3 — Thin CLI/status、progressive disclosure 与全量集成

**依赖**：WP1 + WP2。  
**目标**：隐藏路径编排，压缩 Agent 上下文，并完成 release gate；不增加 autonomous Agent。

**文件所有权**：

- `scripts/harness_status.py`、`scripts/qa/run_deterministic_qa.py`、必要的 path-resolution glue；
- 新薄 `harness` CLI（只调用现有脚本）；
- `README.md`、`SKILL.md`、`references/contracts/artifact_contracts.md`、`references/workflow/gate_policy.md` 及按需 router reference；
- CLI/integration/progressive-disclosure tests；最终 test report 与 before/after 表。

**实现要点**：

- `harness init/status/check/run/validate/freeze/profile/doctor/migrate`；human 与 `--json` 输出；
- status 真正从 normalized control、DAG、receipts、Gate receipts 重建 first block、pending human、stale、next action；
- W2 从 14 个路径参数收敛为 project root + stage/profile，底层错误原样暴露；
- `SKILL.md` 150–220 行，只保留 trigger、主链、最低 I/O、不可绕过规则、preset、router、常用 CLI；详细统计/优化/写作/图/引用/模板/提交/视觉规则留在一层 references；
- README 明确 A/B/C/D、不要手写 generated evidence、regression 与 benchmark 边界、Hash 非语义验证；
- 不修改 `battle/`。已有 battle case 仅在命令可证明只读时复验，否则报告未执行，不伪称 benchmark 通过。

**测试**：最小项目 `init -> status -> check M1`；`--json` contract；first blocked Gate；pending checkpoint；stale artifact；CLI 与直接 checker 等价；skill quick validation；fresh full unittest；CI branch trigger；read-only benchmark status。

**主要风险**：CLI 可能形成第二套 Gate orchestration，文档压缩可能丢失 safety。缓解：CLI 只做 resolver/dispatch，Gate policy 仍唯一位于现有 checker + capability resolver；不可绕过规则逐项回归。

## 12. 集成发布门与目标 after 指标

| 指标 | Before | 目标 after / promotion gate |
|---|---:|---|
| Schema 数量 | 29 | 不以减少为 KPI；无新增无独立 lifecycle 的 Schema；`extremum_certificate` 新项目停止生成 |
| 人工维护 JSON | 至少 15 类型 | 正常路径聚焦 control + model + paper + 条件领域合同；所有 receipt/index/status 禁止手写 |
| 重复 canonical domain | 4 | 0；每个 domain 有 owner matrix 与 negative test |
| profile 维度/组合 | 5 / 72 | 3 presets；override 不形成受支持组合矩阵 |
| enhanced M1 JSON | `6 + N` | CLI 只要求 project root + 必要输入；文件可保留但路径自动解析 |
| enhanced W2 path args | 14 | 正常用户 1 个 project root + stage/profile；底层 CLI 保留调试入口 |
| digest/hash definitions | 24 schemas / 46 位置 | 不机械追求字段数；关键 artifact 单一 owner，projection/status 默认无 digest |
| SKILL lines | 307 | 150–220 且 quick validation 通过 |
| regression | 284/286，2 errors | 先解决环境/编码 baseline；所有 existing + migration + SSOT negative + CLI integration 通过 |
| capability benchmark | 未完成 | 仍标记未完成，除非四类真实赛题 A0/A1/A2 同预算独立运行 |

最终 promotion 必须同时满足：

1. profile A=20 与 legacy manifest=25 不可能同时成为真源；canonical profile 决定结果或迁移 FAIL；
2. DAG result_v2 与 legacy manifest result_v1 冲突时，只读取 canonical artifact owner；
3. fake manifest command 无法让 P1/P2 通过；selected run、receipt、frozen result 可闭环；
4. 修改 immutable artifact 会生成新 version/digest 并使相关 Gate pending/fail，旧 evidence 保留；
5. sprint 不产生 integrity bureaucracy，research 保住关键结果 lineage，submission 保住最终 PDF/package immutability；
6. 所有关键 semantic Gate 仍独立重算；Hash match 不提升 semantic verdict；
7. Result Freeze、Evidence Registry、Human Checkpoint、Competition Safety、Strict Math、Submission Freeze 的原安全边界均未下降；
8. 完整 regression 为绿色，benchmark 未跑就明确写未跑。

## 13. Remaining risks

- 当前回归不是绿色基线；不能在重构后把两个既存 error 误归因或静默排除。
- 独立 competition preset 缺少 manifest 内嵌 ontology 所要求的 official snapshots/endpoints/byte limits；迁移需要真实项目输入，不能靠字段 rename 完成。
- artifact DAG 当前要求所有节点 current 且所有 refs 带 hash；转为 risk-based projection 时，必须避免把“无 hash”误判成“无 provenance”。
- command receipt 目前在 declared output 缺失时会在子进程执行后返回而不先写失败 receipt；“失败 run 必须保留”需要定向回归。
- current `run_index` 允许多个 selected rows，且复制 argv/exit；selection policy 的生效语义需要明确测试，而非只检查非空。
- `harness_status.py` 当前不运行 Gate、不读 DAG stale；在新 CLI 完成前不能宣传真实 first blocker/freshness。
- `submission_manifest` 的不可覆盖语义必须维持；不得用 migration 覆盖既有 F1。
- Progressively disclosed references 只能一层路由；不要把所有 cards/references 自动塞回上下文。
