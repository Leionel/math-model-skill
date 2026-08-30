# HISTORICAL DESIGN / EXECUTION RECORD
> Do not use this file as current operational instruction.
> Current truth starts from `SKILL.md` and `references/router.md`.

# 数学建模 Skill / Harness 修订实施路线图

> 日期：2026-08-12；2026-08-13 基于 2020—2025 MCM/ICM、2020—2024 CUMCM 本地论文库继续修订  
> 输入一：`docs/RESEARCH_INTEGRITY_ARCHITECTURE_AUDIT.md`（研究语义与 C 题现场证据）  
> 输入二：`math-model-skill_audit_roadmap_2026-08-10.md`（通用生产化、LaTeX/PDF 与工程治理）  
> 输入三：用户指定的 Overleaf 社区模板上游；模板文件可从该处取得，但当届官方规则仍是格式验收真源。  
> 输入四：本地历年论文库的分层研读，以及 Harness 生成稿 `C题_evidence_harness/paper/论文.docx` 的段落级对照。  
> 当前代码基线：`6a31b3ba1700f7215466a840929ad4300f516dbe`；工作区另有未提交修改，本方案不把未提交状态误写为已发布能力。  
> 初稿曾是修改方案；2026-08-13 已完成 Wave 1 的最小语义内核实现与 24 项回归验证。其余 wave 仍为待实施计划，不得误读为已发布能力。

## 1. 合并后的最终判断

两份审计并不冲突，关注层次不同：

- 研究完整性审计回答：为什么当前 Harness 会生成“形式完整、语义未闭环”的论文；重点是 contract → code → evaluation → validation → claim → writer。
- 8 月 10 日 roadmap 回答：即使研究链可信，怎样把它做成可初始化、可恢复、可编译、可检查、可冻结的生产型 Skill；重点是 receipts、Gate 失效、LaTeX/PDF、CLI、依赖、安全和 CI。

合并后应把产品目标改为：

> **先成为可信的 modeling research harness，再成为稳定的 PDF delivery harness。**

推荐的真实主链为：

```text
Project / Rules / Data Snapshot
→ Executable Model Contract
→ Recorded Run
→ Independent Evaluation
→ Validation Verdict (PASS/FAIL/ERROR)
→ Append-only Frozen Run
→ Evidence Registry
→ Typed Paper Claims
→ Research Sufficiency Gate
→ Writer-safe Claim Package
→ LaTeX Source + Generated Result Macros
→ PDF Build / Semantic / Visual / Submission QA
→ Immutable Submission Freeze
```

`FAIL` 是合法研究产物，但不是可晋级 claim；自然语言解释、人工 checkpoint、reviewer 或样式 critic 均不能改变机器 verdict。

---

## 2. 对 8 月 10 日 roadmap 的取舍

### 2.1 直接吸收

| 建议 | 决定 | 原因 |
|---|---|---|
| 工具生成 command receipt | 吸收 | 消除手填 `exit_code=0` 和虚假命令历史 |
| 结构化 validation report | 吸收 | 必须包含 operator、observed、threshold、unit、locator 和机器 verdict |
| Gate input digest 与自动失效传播 | 吸收 | 解决旧 review/旧 checkpoint 复用 |
| Evidence 只引用 frozen result ID | 吸收 | 避免 registry 重新读取 mutable raw result |
| Run index 与预先定义选择协议 | 吸收 | 防止挑最好 seed、隐藏失败 run |
| Root confinement、原子写、CAS/锁 | 吸收 | 属于审计链本身的可靠性边界 |
| 版本化赛事 profile、规则 freshness | 吸收 | 赛事规则会变化，不能写死在通用 Skill |
| Generated LaTeX result macros | 吸收 | 解决摘要、正文、表格、结论复制数字漂移 |
| 真实 LaTeX build / PDF QA / submission QA | 吸收 | 正式交付必须检查真实 PDF，而不是手填页数 |
| Schema migration、依赖锁、CI、许可证 | 吸收 | 生产型版本不可缺失 |
| init/status/resume 统一 CLI | 吸收但后置 | 应在核心语义 API 稳定后包装，不先把错误语义产品化 |

### 2.2 吸收但修正

| 原建议 | 修订 |
|---|---|
| 新增多种 JSON 就能形成证据链 | receipt/report 必须由受控工具生成并签出摘要；禁止用户直接编辑 verdict、hash 或 Gate 状态。能嵌入现有 artifact 的字段不另建平行 JSON |
| `freeze_results.py` 只接受全部验证通过 | 改为允许冻结 PASS/FAIL/ERROR 的完整 run；只有 required verdict 全 PASS 才产生 `claimable=true`，避免研究失败消失 |
| 将 baseline、显著性、Pareto、最优性统称 P1 | baseline identity、metric direction、scenario、dominance 和 solver status 是事实语义，属于 P0；只有额外统计功效、更多 robustness 属于 P1 |
| P0-A 先 root confinement/schema，再语义 | 调整为先建立最小的可计算 acceptance 与 FAIL 回归，再补 receipts/append-only/失效传播；否则会得到安全但仍错误的基础设施 |
| PDF 是“唯一论文真源” | 最终 PDF 是唯一提交真源；LaTeX source + generated macros 是唯一写作真源。两者通过 build receipt 绑定，不能只保留 PDF 而丢失生成语义 |
| 前端只支持 LaTeX，DOCX 完全排除 | v0.2 正式 golden path 只保证 LaTeX→PDF；DOCX 标记 legacy/unsupported，不继续扩展，但保留 importer/migration 可能性，不让旧项目立即不可读 |
| 全局禁止未注册 numeric literal | 只禁止 research-value literals；年份、章节号、公式常数、单位换算、文献年份等需有类型化豁免。简单正则全禁会误报 |
| 每个 ASSUMED 参数都做 sensitivity | 改为 risk-based：只有 materially affects required claim 的关键 ASSUMED/POLICY 参数触发 sensitivity/robustness；其他参数只需披露与边界 |
| `p_value` 等字段对所有结果必填 | 用 discriminated result profiles；统计检验只适用于相应模型。确定性优化更关心 feasibility、gap、residual 和 perturbation |
| AI 交互摘要作为核心研究证据 | 只用于合规披露和审计，不作为数学结论 evidence；默认脱敏且不进入提交包，除非赛事要求 |

### 2.3 降级到 P1/P2 或延期

| 项目 | 新优先级 | 理由 |
|---|---|---|
| 两套完整赛事模板同时上线 | P1 release expansion | 先用一个受控 fixture 打通端到端；规则模板建设不能阻塞研究事实内核 |
| 全量 CLI 与一键生命周期 | P1 | 核心 schema/状态机稳定后再封装，避免接口反复破坏 |
| 并发 Agent 文件锁的完整体系 | P1；原子写/CAS 仍 P0 | 单机串行先可信；复杂并发控制可后续增强 |
| 10–20 条 Skill 触发 evals | P1 | 发布前需要，但不应早于 semantic negative tests |
| 论证结构、段落功能与结果解释 | P1 | 这不是润色，而是把可信 claim 组织成研究论证；必须在 Writer 前形成可检查的 argument plan |
| 连接词替换、句式多样化等 micro-guidelines | P2 | 上游 claim package 尚不可信时，单纯增加措辞变化会放大越界，也可能沦为“规避 AI 味”的表面工程 |
| 图表审美、灰度、accessibility | P2；错误图数据仍 P0 | 区分图的证据真实性与视觉质量 |
| 更多 solver/语言/赛事、容器化 | P2 | 等 golden path 稳定后扩展 |

### 2.4 模板来源决策（根据用户补充修订）

#### MCM/ICM 技术底座

- 上游：`https://www.overleaf.com/latex/templates/mei-guo-da-xue-sheng-shu-xue-jian-mo-jing-sai-mcm-slash-icm-lun-wen-mo-ban/tmzfgynjcqfc`
- 页面身份：社区作者“小嗷犬”，CC BY 4.0，页面显示约三年前更新；使用 `mcmthesis` class。
- 决定：可以下载并作为工程底座，不标记为 COMAP 官方模板。
- 必须叠加：当届 COMAP official profile、当届官方 LaTeX Summary Sheet/Control Number 规则、页数与 AI Report 规则、匿名性检查。

#### CUMCM 技术底座

- 首选上游：`https://www.overleaf.com/latex/templates/quan-guo-da-xue-sheng-shu-xue-jian-mo-jing-sai-bian-xie-de-latex/tkpdcwqsphwk`
- 页面身份：`cumcmthesis` 全国大学生数学建模竞赛社区模板，CC BY 4.0，页面显示约四年前更新，内容源自 2021 左右版本。
- 决定：替代辽宁省赛模板，作为全国赛工程底座。
- 辽宁省赛模板 `lnumcmthesis` 只保留为可选 regional profile，不进入 CUMCM golden path。其页面明确称其为辽宁省赛非官方模板，不能改名成全国赛官方模板。
- 必须叠加 2026 CUMCM official profile：电子版去承诺书/编号页、第一页为摘要、无目录、正文页数规则、A4/页边距、匿名性、支撑材料与文件大小规则。

#### 上游与官方规则的关系

```text
Overleaf community source
→ vendor snapshot + upstream hash + license record
→ remove bundled examples/identity/obsolete rule prose
→ season-specific official-rule patch
→ clean build
→ PDF QA against official profile
→ local patched hash
```

`template_manifest.json` 必须同时记录：

- Overleaf URL、抓取日期、页面作者、页面许可证和 upstream archive hash；
- 模板中每个 class/font/image 的单独来源与许可证；
- 删除或修改的旧年份、旧页数、封面、目录、身份字段；
- official rule URLs/hash/season 与本地 patch digest；
- 编译引擎、依赖包、字体解析策略、golden build receipt；
- `status = upstream_unverified | patched | golden_verified`，下载完成不等于可用。

特别限制：CUMCM 模板页面提到从第三方字体站补字体。Overleaf 页面显示的 CC BY 4.0 不能自动视为覆盖其中所有字体文件；下载后先做资产清单和许可证检查。无法确认再分发许可的字体不得提交仓库，改用环境字体或可合法分发的开源字体，并将字体 hash 写入 build receipt。

### 2.5 历年论文研读范围与证据边界

本轮不是把全部 PDF 当成一个无差别“风格库”，而是先盘点、再分层深读：

- MCM/ICM 本地库明确覆盖 2020—2025；对应年份目录共 271 份 PDF，其中包含赛题文件。按年份和题型，从 A/C/F 中各取代表论文，共重点研读 18 篇；可抽取文本的论文检查摘要、完整章节、模型推导、结果解释、验证与 memo/policy 输出。
- CUMCM 本地库覆盖 2020—2024，共 69 篇；当前没有 2025/2026 国赛论文。重点研读 23 篇，覆盖各年份和 A—E 类题。2023 年文本型论文做全文结构抽取；2020—2022、2024 年扫描型论文用关键页与跨页 contact sheet 检查摘要、推导、图表、检验、结论和附录。
- 2024 A242、B196、C038 继续作为前次深读样本，本轮补入 D033、E010；美赛补入 2020—2025 的机制、优化、统计/预测、政策类样本。
- 这些论文是“获奖条件的正样本”，不能据此统计推断某种写法是获奖的充分或必要条件；部分优秀论文同样存在语言生硬、验证不足、代码附录过长和“优缺点”模板化问题，因此只抽取可迁移机制，不照抄表面形式。
- 历年论文不能进入当前项目的科学 `evidence_registry`，也不能证明本题模型正确；只形成带来源 ID 的 pattern cards 和回归样例。

因此，下文所称“稳定机制”指跨年份、跨题型反复出现且与研究可信度直接相关的做法，不表示逐篇论文都具备。

### 2.6 跨年份稳定机制：优秀论文的优势不在模型数量

| 稳定机制 | 论文中的实际表现 | Harness 应生成什么 |
|---|---|---|
| 先确立研究主线，再选择工具 | 2020 MCM A 将温度预测→鱼群迁移→企业收益串成依赖链；2022 MCM A 从生理功率边界→赛道动力学→功率分配优化递进 | `question_dependency_graph`：前问哪些输出成为后问输入、其不确定性如何传播；禁止四问各自独立堆模型 |
| 数学对象从领域机制中长出 | 炉温、波浪能、反潜中概率、定日镜几何、测深覆盖等论文先给物理/几何关系，再形成目标和约束 | 模型选择理由必须包含 domain mechanism、量纲/守恒/边界与被舍弃方案，而不只写“该算法适合” |
| 验证与模型类型匹配 | 预测使用留出集/交叉验证；统计因果使用平行趋势与安慰剂；优化使用可行性、替代算法复核或扰动；仿真使用边界/极端情形 | Research Sufficiency Profile 按模型类型触发义务，不再机械要求所有论文都有同一套 sensitivity/robustness |
| 结果通过比较形成意义 | A092 把优化后指标与问题一方案直接比较；B226 用贪心与模拟退火的误差复核；MCM 样本常把现实路线、额外数据集或朴素方案作为 comparator | 每个核心结果必须声明 comparator、差值/量级、方向、代价与适用范围；没有 comparator 时只能写 observation |
| 允许“不显著、失败或反直觉” | 2024 MCM C 在摘要中明确随机性检验未拒绝原假设，只保留“微弱且不确定”的动量结论，并分析预测失败样本 | `negative_result` 与 `contradicting_evidence` 必须可进入摘要/正文；Writer 不得把 FAIL 改写成“总体有效” |
| 篇幅向关键困难倾斜 | 优秀论文并不平均分配四问篇幅；推导难、决策影响大或验证风险高的部分得到更多公式、图和讨论 | `depth_budget` 按 novelty、risk、dependency 和 decision impact 分配页数，不按“每问一章同长度”生成 |
| 图表参与论证 | 轨迹图、可行域、残差、收敛、敏感性、替代算法误差和情景对比图分别承担不同证据职能 | Figure Contract 新增 `rhetorical_role` 与 `decision_supported`；纯展示图不得被正文称为验证 |
| 输出面向真实决策对象 | MCM memo/policy 类论文把模型结果转成对教练、企业或政策制定者的行动建议；国赛优化题给出可执行参数表与布设方案 | Recommendation 必须绑定前置 claims、资源/约束、实施步骤、风险和触发条件，不能只写“建议加强/提高” |
| 摘要是微型论证，不是模型清单 | 较好的 Summary Sheet 会展示核心冲突、统一思路、关键结果和验证/边界；并非每问都塞模型名和全部数值 | 摘要编译器从 central thesis 和 decisive claims 取材，设置数字预算、模型名预算和至少一个关键边界 |
| 附录服务复现，正文服务判断 | 代码、长表和中间输出进入附录；正文保留公式动机、关键算法、结果与检验 | Writer 先判定“评审需要据此做什么判断”，再决定公式、图、表和附录归属 |

这使产品目标进一步明确：Harness 不应只做 `claim compiler`，还要做 **research argument compiler**。前者防止写错事实，后者防止把正确事实写成没有研究主线的流水账。

### 2.7 Harness 生成稿的内部写作差距

对 `论文.docx` 的问题不能概括成“像 AI”，必须拆成可修复的结构缺陷：

| 当前痕迹 | 为什么显得机械/削弱论文 | 应改成的生成规则 |
|---|---|---|
| 摘要约 506 个非空白字符内出现 14 个数字项，按四问连续报数 | 信息密度高但没有主次；读者记住数字，记不住中心贡献、关键矛盾和证据边界 | 摘要先写 1 个 central thesis；只选择 2—4 个 decisive quantities，其余改为方向性结论或移到正文 |
| 每问普遍采用“建立模型—给公式—报结果—这说明” | 所有段落做同一种修辞动作，没有研究过程中真实的选择、反证、权衡和失败 | 每段声明唯一 `paragraph_role`；同一小节至少区分 model-choice、derivation、result-reading、validation、boundary 中实际需要的角色 |
| “说明”约 11.9 次/万字，而抽取的 2023 国赛样本约 0.9—3.5 次/万字 | 大量“说明/表明”把观察自动升级为解释或因果，形成典型机器式收束 | 结果段按 Observation→Comparator→Interpretation→Boundary 编译；缺少机制证据时禁止生成 Interpretation |
| “显著、关键、真实、严格、可复现、最有效杠杆”等评价词密集 | 评价由作者口头授予，而不是由检验、对照或边界赢得 | evaluative adjective 必须绑定 evidence predicate；未满足时删除形容词，而不是换同义词 |
| 公式前只有模型名，公式后立即进入数值 | 缺少“为什么是这个对象、各项如何作用、极端情况下会怎样”的推理，像把代码说明改写成论文 | 每个核心公式必须有 `motivation → definition → dimensional/behavior check → role in solver` 四项中的适用项；禁止裸公式落地 |
| 图注多为“某指标对比（问题 X）” | 图注只标内容，没有告诉评审图能支持什么、比较口径是什么、哪里不能外推 | claim-bearing caption：对象、场景、指标、主要读数、比较基线和边界；正文不得重复读图，而应解释原因或决策含义 |
| 正文同时出现完整整数和“约百分之四/一点三倍”等刻意改写 | 精度层级混乱，像由一致性规则机械转写；大整数打断阅读 | 建立 `precision_policy`：表格保存审计精度，正文用统一单位和 2—4 个有效数字；语言化数字不能用于绕过 provenance 检查 |
| “模型评价”使用“具有三方面优点：其一、其二、其三”式自评 | 自我表扬不提供新证据，也是竞赛论文常见模板痕迹 | 改为 `what was validated / where it fails / what changes the decision`；删除无法被复核的“创新、合理、广泛适用” |
| 结论基本按原顺序重复摘要和各节结果 | 没有把多个子问题综合成更高层判断，也没有给决策条件 | 结论只保留 thesis、关键 trade-off、适用边界和行动条件；与摘要做语义重复检查，但不追求机械改写 |
| 假设集中列出，后文很少回收 | 假设变成形式章节，没有显示哪条假设影响哪一问、结论对其是否敏感 | 假设必须绑定 model component、affected claim 和 validation/limitation；关键假设在结果段回收 |
| “服务可用性未受损”“低碳调度几乎零成本”等强结论 | 只凭平均时延或近水平前沿不足以支持 SLA/普适因果，语言强度超过证据 | 生成前检查 claim strength、指标覆盖和替代解释；只能写“在冻结窗口和已检查时延约束下未观察到违约”等边界化表述 |

内部写作的真正修复不是随机替换连接词，也不是刻意让句子“更像人”。目标是让每个段落承担不同、必要且可追踪的研究动作；自然度是研究过程真实显露后的副产品。

### 2.8 修订后的优先级结论

基于历年论文对照，原方案对写作的优先级需要再调整：

1. **P0：事实与 verdict 不可伪造。** 保持现有语义内核、运行血缘和 FAIL gate 最高优先。
2. **P1：研究深度与论证架构。** 新增问题依赖图、候选模型取舍、模型型验证、central thesis、段落功能和结果解释规则。没有这一层，P0 只能保证“流水账中的数字没写错”。
3. **P1-delivery：正式交付链。** 在一条赛事 golden path 上把 argument plan 编译成 LaTeX/PDF 并验证。
4. **P2：语言和视觉微调。** 连接词、句长、灰度、字体等只在论证闭环后优化；不得以“降 AI 检测率”为目标。

---

## 3. 修订后的 Gate Architecture

保留现有 M1/P1/P2/W1/W2/S1/F1 对用户可见的阶段名，但内部职责重映射如下。

| 逻辑 Gate | 对应现有阶段 | 权威输入 | 机器输出 | Hard fail / stale 条件 |
|---|---|---|---|---|
| G0 Official & Input Alignment | M1 前半 | competition profile、题面/附件快照、official metrics | alignment report | 规则过期；数据未 hash；主指标/辅助指标未区分；单位未知 |
| G1 Model Semantic Contract | M1 后半 | model contract、parameter provenance、implementation bindings | contract verdict | 决策变量/目标/硬约束/metric definition 不完整；关键假设伪装为 GIVEN |
| G2 Recorded Execution | P1/P2 execution | argv receipt、code/data/config/env/scenario snapshots、raw outputs | run receipt + run index | 命令自填；输入缺失；scenario/evaluator 不绑定；solver error 未记录 |
| G3 Independent Validation | P2 validation | frozen candidate metrics、structured acceptance、independent evaluator | PASS/FAIL/ERROR per obligation | required obligation 非 PASS；解释试图覆盖 verdict；residual 未实测 |
| G4 Append-only Freeze & Evidence | P2 | run receipt、validation、result semantics | immutable frozen run + evidence refs | 原地覆盖；raw evidence；hash/locator 不匹配；旧合同结果被复用 |
| G5 Claim & Argument Semantics | W1 | typed claims、question dependencies、central thesis、argument units、result computations、external evidence | claim verdict + argument plan + writer package | 数字/百分比/baseline/scenario/boundary 不一致；inference 无支持；四问无依赖却伪装成统一主线 |
| G6 Research Sufficiency | W1→Writer | model choice、validation、robustness、limitations、depth budget | sufficiency verdict | 核心 claim 只有结果展示；关键参数风险未测试；FAIL 被隐去；核心困难没有足够解释/验证预算 |
| G7 Paper Build & Semantic QA | W2 | LaTeX source、generated macros、citations、figures、current writer package | build/semantic report | Writer 新增研究事实；undefined refs/cites；PDF 文本与 claim package 漂移 |
| G8 PDF & Submission QA | S1 | current PDF、rule profile、AI disclosure、support package | PDF/submission report | 页数/匿名/字体/文本层/文件 hash/附件不合规 |
| G9 Immutable Delivery | F1 | 当前 G0–G8 digests | submission manifest | 任一 Gate stale；任一 artifact 字节变化；目标已存在 |

关键规则：

1. G0–G5 必须在 Writer 前 hard fail。
2. G6 对 exploratory/draft 可报告不足但继续研究；对 final paper 必须 pass。
3. G7/G8 只负责论文和交付，不得把 G0–G6 的 FAIL 改写为 PASS。
4. 每个 Gate 的 `pass` 都是 `(gate_id, input_digest, evaluator_version)` 上的判定，不是永久布尔值。
5. 人工 checkpoint 只能批准建模取舍或规则冲突，不能手改计算出的 verdict。
6. G5 必须先由人确认 central thesis、问题依赖和少量核心 claims（通常 3—5 个，可由题型 profile 调整）；Writer 只能实现已批准的 argument plan，不能在成文时临时发明研究主线。

---

## 4. 最小数据模型：只新增必要 artifact

### 4.1 保留并强化三个权威合同

#### `model_contract.json`

增加：

- `official_metrics[]`：metric ID、方向、单位、aggregation、官方/辅助标记；
- `parameters[]`：value/unit/type/source/derivation/materiality；
- `scenarios[]`：base snapshot、transforms、solver/evaluator required refs；
- `question_dependencies[]`：上游结果、下游用途、传播量、传播方式和失效条件；
- `implementation_bindings[]`：contract item → function/test/check ID；
- `validation_obligations[]`：结构化 expression，不再以 prose acceptance 为权威；
- `candidate_models[]`、selection rationale、known boundary（P1 字段，可分阶段填充）。

#### `frozen_results.json`

改为“frozen run”，允许失败：

- run/receipt/data/code/config/environment/scenario/evaluator digests；
- result kind、metric ID、value/unit/aggregation/boundary；
- baseline/comparator/direction/computation；
- solver status/objective/gap/residual/violations；
- obligation verdicts：PASS/FAIL/ERROR/NOT_RUN；
- `claimable` 由工具派生；
- append-only 路径 `runs/<run_id>/frozen_results.json`，禁止覆盖。

#### `paper_plan.json`

增加：

- `claim_type = observation | inference | recommendation`；
- Observation 使用 `result_ref` 或受限 computation AST；
- Inference 记录 supporting/contradicting evidence、support level、alternative explanation；
- Recommendation 记录前置 claim 和适用边界；
- `prohibited_wording`、confidence、limitations；
- figures/tables 绑定 result/scenario/data/build receipt。
- `central_thesis`、`argument_units[]` 与 `depth_budget[]`：每个单元记录 rhetorical role、claim/evidence、必要前置、预期读者判断、边界和目标篇幅；这些字段属于现有 `paper_plan.json`，不再新增一份平行“写作大纲数据库”。
- `precision_policy`：审计精度、表格精度、正文显示精度和允许的单位换算；禁止用中文数字或近义表达绕开 result provenance。

### 4.2 只新增四类不可替代 artifact

1. `command_receipt.json`：由 runner 自动生成，记录真实进程与 IO 摘要。
2. `validation_report.json`：由 evaluator 自动生成，记录结构化计算和 verdict。
3. `run_index.json`：登记所有运行、selection policy、selected run；失败运行不可删除。
4. `build/pdf/submission reports`：只在正式交付链启用。

Gate history 可放在现有 `run_manifest.json` 的 append-only events 中，不再另建一个“GateEvidence.json”。参数、claim、figure、depth 不各建独立 JSON。

---

## 5. 实施波次与文件级修改

## Wave 0 — 基线锁定与兼容边界（0.5–1 天）

目标：在不碰用户未提交修改的前提下，确定实现基线。

- 记录当前 commit、dirty patch digest 和现有 21 个测试结果。
- 把 `docs/RESEARCH_INTEGRITY_ARCHITECTURE_AUDIT.md` 中的 C 题反例固化为 fixtures，不引用外部 C 题目录作为长期测试依赖。
- 决定 schema v2 迁移策略：旧 v1/v1.1 只读；迁移后标记 `needs_human_review`，禁止猜测缺失语义。
- 明确 v0.2 正式输出为 LaTeX→PDF，DOCX 为 legacy，不在本轮增强。

出口：基线测试可重跑；旧 artifact 不会被静默升级成“已验证”。

**实施状态（2026-08-13）：完成基线记录；原有 21 项测试已通过。保留用户工作区中与本波次无关的未提交修改。**

## Wave 1 — 可计算的研究语义内核（P0，最高优先，3–5 天）

先写 negative tests，再改 schema/scripts。

### 文件

- `schemas/model_contract.schema.json`
- `schemas/frozen_results.schema.json`
- `schemas/paper_plan.schema.json`
- 新增 `schemas/validation_report.schema.json`
- 新增 `scripts/validation/evaluate_obligations.py`
- 修改 `scripts/freeze_results.py`
- 修改 `scripts/qa/validate_contracts.py`
- 修改 `scripts/qa/check_consistency.py`
- 修改 `scripts/qa/check_gates.py`

### 必须首先通过的固定反例

1. `498 → 550 MW` 对 `candidate <= baseline` 必须 FAIL。
2. carbon `+1.9%` 对 nonincrease 必须 FAIL。
3. `observed="解释合理"` 不得改变 FAIL。
4. C7/C8 文本数字与 result 不一致必须 FAIL。
5. flat-price solver/evaluator input hash 不一致必须 FAIL。
6. migration denominator、violation-hour 口径与实现不一致必须 FAIL。
7. `claimable=true` 不可手填，只能由 required obligation verdict 派生。

### 设计限制

- acceptance 使用有限 comparator DSL/AST，不执行任意表达式或 `eval`。
- 统计、优化、预测使用 discriminated profiles；不强迫所有结果具有 `p_value`。
- freeze 允许保存失败实验，但 claim gate 只消费 claimable results。

出口：**当前 C 题必须在 Writer 前被正确阻断，且 FAIL 可以完整冻结。**

**实施状态（2026-08-13）：核心闭环完成，范围严格限定为有限 comparator DSL、measurement snapshot、独立 `evaluate_obligations.py`、`validation_report` schema、freeze 重算、`claimable` 派生、Registry/P2/W1 阻断及跨契约复算。写作与交付侧已补最小 argument-plan/writer-package、题面/数据/实现追溯、claim inventory、统一数值宏、artifact DAG stale 检测、安全 LaTeX 构建、真实 PDF 全页渲染与受控绘图库。37 个回归测试覆盖关键正反例。carbon、C7/C8、flat-price、migration 反例、自动选择性重跑、正式赛事 golden template 和独立能力 benchmark 仍待后续扩展。**

## Wave 2 — 运行身份、不可变性与 Gate 失效（P0，3–5 天）

### 文件

- 新增 `schemas/command_receipt.schema.json`
- 新增 `schemas/run_index.schema.json`
- 新增 `scripts/run_and_record.py`
- 新增 `scripts/reconcile_gates.py`
- 修改 `schemas/run_manifest.schema.json`
- 修改 `scripts/register_evidence.py`
- 修改 `scripts/_common.py`
- 新增 `scripts/migrate_contracts.py`

### 行为

- runner 以 argv 数组执行，自动捕获 cwd、exit code、时间、stdout/stderr、输入输出 hash、env/solver/seed。
- frozen run 路径含 run ID；写入采用原子创建且目标存在即拒绝。
- evidence 只能以 JSON Pointer 引用 frozen result；取消原位 `--force`。
- Gate 根据 input digest 自动 stale，并向下游传播；review 绑定全部被审 artifact digest。
- run index 记录全部候选/失败/调参/最终 run 和 selection policy。
- project-root confinement 默认开启；外部数据必须在只读白名单内；输出永远留在项目根。

出口：修改 raw、合同、代码、场景、evaluator、paper plan 或 PDF 中任一项，都能使正确的下游 Gate stale；手填 exit code 或复制旧 review 不能通过。

## Wave 3 — Claim / Argument compiler 与 Writer sandbox（P0/P1，4–6 天）

### 文件

- 修改 `SKILL.md`：把 central thesis / question dependency / argument plan 的读取与人工确认放入 W1→Writer 必经路径
- 修改 `schemas/paper_plan.schema.json`
- 修改 `references/contracts/paper_plan.md`
- 修改 `references/review/semantic_critic_rubric.md`
- 修改 `references/writing/consistency_guidelines.md`
- 修改 `references/writing/abstract_guidelines.md`
- 新增 `references/writing/paragraph_realization.md`
- 新增 `scripts/claims/compile_claims.py`
- 新增 `scripts/claims/compile_argument_plan.py`
- 新增 `scripts/claims/check_writer_output.py`
- 新增 `scripts/qa/check_rhetorical_patterns.py`
- 修改 `scripts/qa/check_consistency.py`

### 行为

- 先从 paper plan 编译只读 writer package，而不是让 Writer 浏览全部 raw artifact 后自行判断。
- 先确认 `central_thesis` 和 `question_dependencies`，再按 risk/novelty/decision impact 分配 `depth_budget`；禁止默认按题号平均铺陈。
- argument unit 的有限角色为：`problem_tension | model_choice | mechanism_derivation | parameter_evidence | result_observation | comparison | validation | interpretation | boundary | recommendation`。每个单元只能有一个主角色，可引用多个 claim，但不能把 observation 与未经支持的 causal interpretation 合并。
- 量化 observation 由 result refs/computation 生成自然语言 slots。
- Writer 可以改句法，不能改 claim type、strength、number、baseline、scenario、causal status 或 boundary。
- 对 research numeric literals 做 provenance 检查；非研究数字使用类型化豁免。
- “证明、显著、主要原因、最优、零成本、最重要”等强词按 support level 解锁。
- 核心公式执行“动机—定义—行为/量纲检查—求解作用”合同；按模型类型选择适用项，不要求对教科书公式机械写满四句。
- 结果段优先采用 Observation→Comparator→Interpretation→Boundary；没有机制或排他性证据时省略 Interpretation，不用“说明/表明”强行收束。
- 摘要从 central thesis 和 decisive claims 编译，默认只容纳 2—4 个决定性数值；数字预算可由赛事/题型 profile 调整，不能作为一刀切字数规则。
- caption 必须说明场景、指标、比较和可支持结论；正文负责解释而不是逐项复述坐标。
- deterministic rhetoric check 只检查高风险模式：连续段落同构开头、无证据评价词、异常数字密度、摘要/结论近复制、同一收束词过密、裸公式和空泛自评。它产生 warning/high issue，不以“AI 检测分数”作为目标或 Gate。
- 发现新 inference/causal explanation 时返回 W1，而不是自动补写。

出口：论文生成器不能复现“验证集择优但代码没调参”“时移但代码未决策”“服务未受损但没有 SLA result”等越界；也不能在事实正确时退化成四问等长、公式落地、数字堆叠和“这说明”式流水账。

## Wave 4 — Research Sufficiency Profiles（P1，3–5 天）

### 文件

- 强化 `references/validation/validation_obligations.md`
- 新增 `references/validation/profiles/{optimization,prediction,evaluation-ranking,simulation,stochastic,ode-pde,causal-inference,network-spatial,decision-policy}.md`
- 强化 `references/contracts/model_contract.md`
- 强化 `references/contracts/figure_contract.md`
- 强化 `references/research/precedent_policy.md`
- 新增 `references/precedents/pattern-cards/schema.md` 与少量脱敏机制卡 fixtures（不提交原论文全文）
- 修改 semantic critic

### 原则

- 不是每问机械要求 baseline+sensitivity+robustness 全套。
- 根据 claim、模型类型、参数 materiality 和 failure risk 触发义务。
- 核心问至少形成 Model → Independent Validation → Boundary/Robustness 的链。
- 预测优先检查时间/组别泄漏、样本外误差、基线和残差；优化优先检查可行性、约束余量、solver status/gap、替代算法或扰动；统计因果优先检查识别假设、平行趋势/安慰剂/稳健标准误；机理/仿真优先检查守恒、量纲、极端情形、校准和跨情景行为。
- 多问依赖链必须执行 uncertainty propagation 或至少给出 signed boundary audit；上游未通过的输出不能被下游当作 GIVEN。
- 对复杂模型要求 nested/simple comparator 或 component ablation，理由是证明新增复杂度改变了结论，不是追求算法数量。
- ASSUMED/POLICY 参数只有对 required claim 影响 material 时才强制 sensitivity。
- 图先声明可支持/可驳回的 claim；纯展示图不冒充 validation。
- pattern card 不保存可复用段落，只保存 `problem_family / trigger / mechanism / dependency_shape / validation_signature / rhetorical_moves / failure_modes / do_not_copy / source_ids`。Writer 只能加载 mechanism 与 rhetorical roles，不能检索原文句子进行拼贴。

出口：final paper 的每个核心 inference 均有 comparison、ablation、robustness 或明确低置信边界；失败结果不会被隐藏。

## Wave 5 — LaTeX/PDF 正式交付链（P0-delivery，4–7 天）

研究语义稳定后再接交付层。

### Golden path 顺序

1. **先打通 CUMCM 2026 electronic**：下载用户指定的 `cumcmthesis` Overleaf 模板，建立 vendor snapshot；删除旧年份/旧规则示例和身份内容；用 2026 官方格式 profile 打补丁并验证 `withoutpreface` 电子版路径。
2. **再打通 MCM/ICM 2027**：下载用户指定的 `mcmthesis` Overleaf 模板；把当届 COMAP 官方 Summary Sheet 作为第一页面源，社区模板只负责正文样式；验证 25 页 solution 与后置 AI Report 的分段计数。
3. 辽宁 `lnumcmthesis` 不进入这两个 golden paths，只能在未来作为 `regional/liaoning` profile 独立支持。

两套模板可以现在确定上游，但实现仍按一个 golden path 完成后再接第二个，避免同时维护两套未经真实 PDF 验证的补丁。

### 文件

- 新增 `scripts/latex/generate_values_tex.py`
- 新增 `scripts/latex/build_latex.py`
- 新增 `scripts/latex/check_latex_log.py`
- 新增 `scripts/pdf/check_pdf.py`
- 新增 `scripts/pdf/render_pdf.py`
- 新增 build/pdf QA schemas
- 修改 `scripts/qa/check_submission.py`
- 修改 `scripts/freeze_submission.py`
- 版本化 `assets/competition-profiles/` 与 `assets/templates/`

建议目录：

```text
assets/templates/
  cumcm/2026/electronic/
    vendor/overleaf-tkpdcwqsphwk/
    patches/
    template_manifest.json
  mcm-icm/2027/
    vendor/overleaf-tmzfgynjcqfc/
    official-summary-sheet/
    patches/
    template_manifest.json
```

### 真源规则

- LaTeX source + generated macros 是写作源；宏文件不可手改。
- PDF 是唯一提交 artifact；build receipt 绑定 source、template、engine、font、macro、figure、bib 和 PDF hash。
- QA 读取真实 PDF：页数、尺寸、字体嵌入、缺字、文本层、匿名性、metadata、文件大小、裁切/空白页。
- citation QA 建立 claim → evidence → bib key → inline location 闭环，并读取 `.log/.blg`。
- 模板源文件中的年份、队号、学校、作者、示例 QR/宣传图片、旧页数说明必须被静态扫描；任何残留使 build fail。
- CUMCM profile 检查电子版第一页是摘要且不含承诺书/编号页；MCM/ICM profile 检查第一面是当届 Summary Sheet。

出口：一个 golden project 可从空 build 目录生成可抽取文本的真实 PDF；PDF hash 与 S1/F1 全链绑定；伪造页数无效。

## Wave 6 — CLI、初始化、恢复和发布工程（P1，3–5 天）

- `init/status/run/validate/freeze-results/build/qa/freeze-submission/resume` 统一 CLI。
- 项目 skeleton 自动生成稳定 ID、目录与下一步命令，用户不手填 Gate/hash。
- `pyproject.toml`、lock file、LICENSE、THIRD_PARTY_NOTICES、CI。
- Windows/Linux 最小兼容；失败从最早 stale Gate 恢复。
- README 5 分钟 quickstart，明确 implemented / experimental / planned。
- 触发 evals 和第二赛事 golden project。

出口：新用户无需直接编辑 manifest/Gate，即可走完一条 golden path；旧 schema 可显式迁移或被安全拒绝。

## Wave 7 — 语言实现与视觉质量（P2，持续）

- P1 的 argument plan 已在 Wave 3 完成；本波只处理不改变论证的语言与视觉实现。
- 检查摘要—结论重复、连续同构句式、过强结论、空泛优缺点、未定义指代与精度层级混乱。
- 不做同义词随机替换，不为了降低任何 AI 检测分数改写；优先让模型选择、失败结果和边界自然进入文字。
- 图表灰度/色觉/字号/DPI/单位/样本量和最终尺寸 QA。
- 不新增 Writer/Reviewer Agent；先提升现有 writer package 与 critic 的输入质量。

---

## 6. 发布切片，而不是一次性大重构

### v0.2-alpha — Semantic Kernel

包含 Wave 0–1。

发布门：

- Q3 FAIL、C7/C8 stale claim、scenario drift 三类反例全部被拦截；
- 失败 run 可冻结；
- 现有 21 个测试继续通过或有明确 v2 migration replacement；
- alpha 发布记录仍不得宣称正式 PDF；当前开发分支已新增真实构建/PDF QA，但只有 rc 的当届 golden path 通过后才可把赛事模板称为正式可交付。

### v0.2-beta — Traceable Runs

包含 Wave 2–3。

发布门：

- 真实 receipts、append-only freeze、Gate stale propagation、run selection、writer boundary 通过负向测试；
- 用户无法通过手改 `ok=true`、`exit_code=0`、claim text 或 review status 晋级。
- central thesis、问题依赖、argument units 与 depth budget 可由 paper plan 编译，并能阻止四问等长流水账、裸公式和无证据“说明/表明”。

### v0.2-rc — One Golden Delivery Path

包含 Wave 4–5。

发布门：

- 一个真实赛事 profile + 一个真实 LaTeX/PDF golden project 全链通过；
- semantic gate 和 PDF gate 相互独立；
- PDF 合规但 semantic FAIL 的项目仍不能 F1。

### v0.2 — Usable Product

包含 Wave 6，并至少支持第二个 golden profile 或明确标为 experimental。

发布门：

- CLI/init/resume 可用；
- migration、依赖、许可证、CI 完成；
- README 能让新用户无需手改 JSON 跑通；
- 能力清单不把 planned 写成 implemented。

---

## 7. 必须先写的回归测试

### 7.1 第一组：研究语义负例（最先）

1. `validation_failure_cannot_become_pass`
2. `q3_peak_550_gt_498_is_fail`
3. `q3_carbon_positive_delta_is_fail`
4. `observed_comment_does_not_affect_verdict`
5. `contract_declared_variable_must_be_exercised_or_removed`
6. `hard_constraint_fallback_cannot_relax_without_new_contract`
7. `solver_and_evaluator_scenario_hashes_must_match`
8. `official_power_mapping_must_be_consumed`
9. `metric_denominator_and_aggregation_match_definition`
10. `failed_run_is_frozen_but_not_claimable`

### 7.2 第二组：Claim / Writer 负例

11. `claim_percentage_recomputes_from_bound_results`
12. `stale_C7_C8_numbers_fail`
13. `inference_requires_support_or_low_confidence_boundary`
14. `writer_cannot_add_calibration_fact`
15. `writer_cannot_add_scenario_or_causal_explanation`
16. `writer_cannot_raise_claim_strength`
17. `research_numeric_literal_requires_provenance`
18. `nonresearch_numeric_literal_uses_typed_exemption`

### 7.3 第三组：论证与内部写作负例

19. `central_thesis_requires_decisive_claims_and_boundaries`
20. `downstream_question_cannot_consume_failed_upstream_result`
21. `question_dependency_propagates_scenario_and_uncertainty`
22. `depth_budget_is_risk_weighted_not_equal_by_question`
23. `result_observation_cannot_imply_cause_without_support`
24. `abstract_decisive_number_budget_warns_on_inventory_dump`
25. `core_formula_requires_motivation_and_behavior_or_dimension_check`
26. `caption_states_comparator_metric_and_boundary`
27. `unsupported_evaluative_adjective_is_removed_or_fails`
28. `conclusion_must_synthesize_not_duplicate_abstract`

这些检查不能只靠字符串正则给最终 verdict：19—23 属于结构化 hard gate；24—28 由结构化字段与文本 lint 联合产生 warning/high issue，再由 W2 人审裁决。这样既能拦截高风险模板痕迹，又不把优秀写作压成新的固定模板。

### 7.4 第四组：血缘与篡改

29. `receipt_exit_code_is_process_captured`
30. `raw_mutation_invalidates_freeze_and_downstream_gates`
31. `review_input_digest_must_match_current_artifacts`
32. `frozen_run_is_append_only`
33. `registry_cannot_reference_mutable_raw_result`
34. `run_selection_policy_prevents_best_seed_only_reporting`
35. `external_data_read_allowed_but_external_output_denied`
36. `schema_migration_never_invents_missing_semantics`

### 7.5 第五组：真实交付

37. `latex_values_are_generated_from_claimable_results`
38. `undefined_citation_or_reference_fails_build`
39. `bibliography_without_inline_citation_fails_strict`
40. `pdf_page_count_is_tool_derived`
41. `missing_cjk_glyph_or_unembedded_required_font_fails`
42. `pdf_hash_must_match_submission_report`
43. `semantic_fail_blocks_F1_even_when_pdf_qa_passes`
44. `paper_change_stales_review_S1_and_F1`
45. `cumcm_electronic_first_page_is_abstract_without_identity_pages`
46. `cumcm_template_contains_no_legacy_20_page_rule_or_old_year`
47. `mcm_first_page_uses_current_official_summary_sheet`
48. `template_asset_license_manifest_covers_every_bundled_font_and_image`
49. `community_template_hash_and_local_patch_digest_are_recorded`

---

## 8. Definition of Done

只有同时满足以下条件，Harness 才能回答“当前项目已完成”：

1. 当届规则 profile 可追溯、未过 freshness TTL，冲突已明确决议；
2. 官方输入、代码、配置、环境、场景和 evaluator 均有当前 digest；
3. model contract 的变量、目标、硬约束、参数和 metric semantics 已绑定实现/测试；
4. required validation 由独立工具计算，FAIL/ERROR 不被备注覆盖；
5. 选中的 run 符合预先定义的 selection policy，失败 runs 保留；
6. frozen run append-only，evidence 只引用 frozen locator；
7. paper plan 的 Observation/Inference/Recommendation 均通过语义 Gate；
8. central thesis、问题依赖和核心 claims 已由人确认，关键上游结果的失败/不确定性已传播到下游；
9. final 模式下 Research Sufficiency 通过，验证义务与模型类型匹配，核心复杂度有简单 comparator 或充分理由；
10. argument units 和 depth budget 覆盖每个必要研究动作，没有把四问机械等分；
11. Writer 输出没有新增研究数字、机制、因果或强度，公式、结果段、图注和结论均满足对应角色合同；
12. 摘要只保留 decisive claims，结果精度符合统一 policy，结论不是摘要的近复制；
13. LaTeX clean build、citation/reference log、PDF semantic/visual/submission QA 对当前 build 通过；
14. Reviewer、S1、F1 均绑定当前全部上游 digest；
15. submission manifest 以不可覆盖方式创建。

任何一项失败时，系统应报告：首个失败 Gate、机器观测、阈值/期望、受影响 claims、需要重跑的最早阶段和下一条安全命令。不得用“总体合理”代替未完成状态。

---

## 9. 当前最推荐的第一批实际修改

如果继续编码，不应先建模板或 CLI。第一批 P0 原定的 8 项中，已完成第 1、2、3、7（仅 validation/claimable 闸门部分）和第 8；同时提前完成了 Wave 3 的最小 argument-plan/writer-package 边界。其余条目仍是下一迭代工作：

1. 为 validation obligation 定义有限 comparator schema；**已完成。**
2. 实现独立 `evaluate_obligations.py`；**已完成。**
3. 让 frozen schema 支持 FAIL/ERROR 并派生 `claimable`；**已完成。**
4. 把 Q3 `498→550` 和 carbon `+1.9%` 做成固定负向 fixture；**前者已完成，carbon 待补。**
5. 在 consistency 中重算 claim 数字、百分比、baseline、scenario 和 boundary；
6. 把 C7/C8 陈旧数字做成固定负向 fixture；
7. Gate 在 required FAIL/unknown 或 input digest stale 时阻断 W1/W2；**P2/W1 claimable 阻断与 DAG stale 检测已完成；自动调度受影响节点重跑仍待 Wave 2。**
8. 禁止 `freeze_results.py` 信任报告自填 status。**已完成。**

本轮已让 Harness 具备最小的 `FAIL remains FAIL`、可检测运行血缘漂移和实际 PDF 交付检查能力；尚不表示它已拥有自动选择性重跑、当届赛事 golden template 或完整端到端能力 benchmark。

紧随其后的第二批 P1 不应直接写长文，而应先实现 6 个“研究深度生成”能力：

1. 在 model contract 中加入问题依赖与上游失效传播；
2. 为主要模型族实现差异化 validation profiles 和简单 comparator 规则；
3. 在 paper plan 中加入 central thesis、argument units、depth budget 与 precision policy；
4. 编译只读 writer package，明确每个段落的角色、claim、evidence、边界和允许措辞；
5. 增加摘要数字预算、结果段 observation/inference 分离、公式落地和 claim-bearing caption 检查；
6. 用本轮历年论文机制卡和当前 C 题生成稿建立回归 fixtures，验证“事实正确但流水账式论文”会被 W2 拦截。

然后再做 receipts、append-only、正式 Writer realization 和 PDF 链。这样修订后的顺序是：**先不写错 → 再能形成研究论证 → 最后稳定交付。**

---

## 10. 最终推荐

8 月 10 日 roadmap 的总体方向应保留，但版本目标需要从：

> “可信证据链 + 两套模板 + PDF QA + 一键生命周期”

修订为：

> **v0.2：可计算研究语义内核 + 不可伪造运行血缘 + Research Argument Compiler + Writer 事实边界 + 一条真实 LaTeX/PDF golden path。**

两套模板、完整 CLI 和语言微调放在这个核心闭环之后。v0.2 的第一价值不是“能更快写完论文”，而是：它会先指出哪些模型、结果和主张还不能成立，再把成立的部分组织成有主线、有取舍、有验证、有边界的研究论证。只有这样，论文的“AI味”才会从生成机制上下降，而不是被同义词替换暂时遮住。
