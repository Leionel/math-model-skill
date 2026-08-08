# Literature Evidence Contract

文献发现、身份核验和内容核验是三个步骤。OpenAlex、Crossref 或搜索引擎只能帮助发现和核对 metadata；DOI 存在不等于原文支持某条 claim。

## 登记流程

1. 用关键词和权威索引发现候选文献。
2. 通过 DOI、出版方或官方仓储核对题名、作者、年份与版本。
3. 阅读可访问全文，在 `locator` 记录页码、章节、定理、表或图；只读摘要时不能把 `content_verified` 设为 true。
4. 检查撤稿、勘误或版本状态，例如 Crossref 的 Retraction Watch 数据。
5. 在唯一的 `evidence_registry` 中新增 `type=citation` 记录；不要另建 Literature Registry。
6. 只让 `metadata_verified=true`、`content_verified=true`、`publication_status_checked=true` 且 `access_level=full_text` 的引文作为已验证 claim evidence。

`supports` 写原文真正能支持的命题，`boundary` 写不能外推到哪里。不要保存长段原文，也不要让 citation evidence 证明本队计算出来的数值。

Crossref 官方说明其检索数据主要是成员提交的 metadata，并非全文：[Metadata Retrieval](https://www.crossref.org/documentation/retrieve-metadata/)。撤稿状态入口：[Retraction Watch](https://www.crossref.org/documentation/retrieve-metadata/retraction-watch/)。
