# Literature Evidence Contract

文献发现、身份核验和内容核验是三个步骤。OpenAlex、Crossref 或搜索引擎只能帮助发现和核对 metadata；DOI 存在不等于原文支持某条 claim。

## 覆盖驱动的研究记录

`model_contract.research_basis` 在需要正式 M1 研究时还应把来源分到三个状态：

- `discovery_candidates`：检索得到、尚未完成全文核验的候选；它们不能支持科学 claim。
- `full_text_core`：已纳入当前研究范围的全文核心来源；每项写 `inclusion_reason`，并绑定完整三态核验的 citation evidence。
- `excluded_items`：审过但不纳入本题论证的来源；每项写 `exclusion_reason`。

每项都声明 `source_role`（例如 `review`、`original_method`、
`application_research` 或 `precedent_pattern`）。综述可以帮助定位方法与研究脉络，
但不能被默认为原始方法证据；往届优秀论文的 `precedent_pattern` 只说明组织方式，
不能支持本题的科学 claim、参数或模型有效性。

同时按本题需要登记 `research_obligations`：机制、假设、参数、基线/模型选择、
验证和失败模式等义务可标为 `covered`、`gap`、`waived` 或 `not_applicable`。
每项还要显式声明 `critical`；`covered` 应绑定 evidence ID 或给出可核查理由，其余状态必须说明理由。查询数量、
数据库数量和全文数量不是通用门槛；只有关键义务仍为 `gap` 时才阻断 M1。`ready` 的
研究记录必须给出 `stop_reason`，说明覆盖已满足、边际新增信息很低，或带剩余风险的
赛时 time-box/waiver。

## 登记流程

1. 用关键词和权威索引发现候选文献。
2. 通过 DOI、出版方或官方仓储核对题名、作者、年份与版本。
3. 阅读可访问全文，在 `locator` 记录页码、章节、定理、表或图；只读摘要时不能把 `content_verified` 设为 true。
4. 检查撤稿、勘误或版本状态，例如 Crossref 的 Retraction Watch 数据。
5. 在唯一的 `evidence_registry` 中新增 `type=citation` 记录；不要另建 Literature Registry。
6. 只让 `metadata_verified=true`、`content_verified=true`、`publication_status_checked=true` 且 `access_level=full_text` 的引文作为已验证 claim evidence。

`supports` 写原文真正能支持的命题，`boundary` 写不能外推到哪里。不要保存长段原文，也不要让 citation evidence 证明本队计算出来的数值。

全文获取优先开放获取渠道（arXiv、出版社 OA 页、机构仓储镜像）；被反爬或付费墙阻挡时，诚实地把该条降级为 abstract 级（`content_verified=false`），并改用其他可全文核验的来源满足 formal M1 的全文门槛——不得把摘要页当全文，也不得因一条被挡就放宽三状态核验。

Crossref 官方说明其检索数据主要是成员提交的 metadata，并非全文：[Metadata Retrieval](https://www.crossref.org/documentation/retrieve-metadata/)。撤稿状态入口：[Retraction Watch](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/)。
