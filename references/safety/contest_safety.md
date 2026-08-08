# Contest Safety and AI Use

在处理赛题之前创建 `competition_profile`，并让它持续约束检索、外部写入、AI 使用和最终提交。它不是一次性 Gate。

## 规则快照

1. 从赛事官网读取当届规则、格式规范、AI 政策和提交说明。
2. 将原始页面或 PDF 保存为本地只读快照，登记 URL、抓取时间和 SHA-256。
3. 把 `official_rule` 与 `local_conservative_policy` 分开。后者可以更严格，不能更宽松。
4. 规则页有冲突、版本不明或无法访问时，标记 `competition_specific` 或 `ask`，不要凭往届经验补结论。

策略强度为：`allow < competition_specific < ask < deny`。有效策略取官方规则与本地策略中更严格者。

`live_contest` 默认要求以下四项为 `deny`：队外真人求助、浏览/讨论当前赛题、公开发布、一般外部写入。向已登记的官方提交端点上传最终文件是唯一可配置例外，必须记录目的并由人确认。

## AI Usage Registry

把每次会影响交付物的 AI 使用登记到 `run_manifest.ai_usage[]`，至少记录工具/模型、时间、阶段、用途、提示与输出摘要、采纳方式、人工修改、交互记录文件及人工核验。

- 不在 manifest 中塞完整长对话；把关键交互存为独立 artifact 并登记哈希。
- `verification.status=verified` 只表示人已核查该项，不表示赛事一定允许；允许性由 Competition Profile 决定。
- AI 声明可从 registry 生成草稿，但必须由人确认后才能进入 S1。

## Human Checkpoints

M1、P2、W2、S1 各保留一个真实人工确认点：

- M1：题意、假设、变量、模型和验证义务；
- P2：代码、验证报告、冻结结果和选择理由；
- W2：主张、引文、图表、AI 内容和结论边界；
- S1：最终文件、匿名性、渲染、页数/大小、附件和 AI 声明。

确认记录必须绑定当前 artifact 哈希。文件变化后旧确认自动失去证明力。

## 已核验的规则入口（2026-08-08）

- CUMCM：[`2026 年参赛规则`](https://www.mcm.edu.cn/html_cn/node/9d8e511fe7a1447b35f53a82c908e2e0.html)、[`2026 年论文格式规范`](https://www.mcm.edu.cn/html_cn/node/4cd596519c9eb9fbd866398f6df0caa3.html)、[`AI 工具使用规定（2025 年试行）`](https://www.mcm.edu.cn/html_cn/node/eebcfb6dc37fd2de9603dc16026fdf01.html)。目前未把无法核验的“2026 AI 新规”当作官方事实。
- COMAP MCM/ICM：[`当届 Contest Rules and Instructions`](https://www.contest.comap.com/undergraduate/contests/mcm/instructions.php) 与其链接的 AI Policy。官网页面会滚动到下一赛季，赛前必须重新快照。

这些链接是 profile 的发现入口，不替代本地规则快照。
