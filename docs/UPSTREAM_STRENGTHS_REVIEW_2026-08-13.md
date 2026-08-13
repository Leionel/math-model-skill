# 上游仓库取长补短复核（2026-08-13）

本轮不是按 Star 拼装功能，而是按“资料发现—模型决策—实现验证—论证写作—模板交付”分层。资源仓库、Agent、写作 Skill 和模板解决的是不同问题，不能相互冒充。

## 1. 数学建模资源与 Agent

| 上游 | 实际长处 | 吸收方式 | 不照搬的部分 |
|---|---|---|---|
| [zhanwen/MathModel](https://github.com/zhanwen/MathModel) | 历年题目/优秀论文、算法、教材、LaTeX 模板和思维导图的综合索引 | 作为 `local_method_library`/precedent discovery，帮助形成中英关键词、候选模型和案例检索方向 | 资料存在不等于本题方法合理；往届论文不作本题科学 evidence |
| [personqianduixue/Math_Model](https://github.com/personqianduixue/Math_Model) | 大体量比赛、模板、书籍和 MATLAB 算法资料库 | 只按需检索，不整库注入上下文；候选必须回到原始文献/题面验证 | 无许可证或来源不清的材料不再分发，不把 8GB 资料库变成默认 RAG 噪声 |
| [HuangCongQing/Algorithms_MathModels](https://github.com/HuangCongQing/Algorithms_MathModels) | MATLAB 算法实现示例 | 用于实现接口和 smoke 原型；算法进入正式链前必须写适配假设和独立验证 | 示例代码能跑不等于模型选择成立 |
| [datawhalechina/intro-mathmodel](https://github.com/datawhalechina/intro-mathmodel) | 结构化建模教程和方法解释 | 用于理解方法族、变量/目标/约束结构与教学型参考 | 教程不是最新研究或本题数据证据 |
| [jihe520/MathModelAgent](https://github.com/jihe520/MathModelAgent) | 分阶段技能、Web Search、RAG、结构化中间结果、HIL、有限重试/回退、模板匹配与多步验收 | 吸收“搜索 + 知识库只产候选”“关键节点人审”“阶段输出可校验”；本仓库落实为 research M1、Gate 和 bounded revision | 不以“一小时自动获奖论文”为质量承诺；不默认多 Agent、多 LLM、危险权限或在线服务 |
| [XiaoMaColtAI/math-modeling-skill](https://github.com/XiaoMaColtAI/math-modeling-skill) | Model Contract、三角色主链、P1/P2、复现工具 | 保留短链和合同，但把 M1 升级为有研究证据的候选比较 | 固定图数、默认双格式和到处哈希不作为本地默认 |
| [latexstudio/CUMCMThesis](https://github.com/latexstudio/CUMCMThesis) | `cumcmthesis` 社区文档类与完整样例 | 锁定 commit，本地初始化时复制 class；用原创清洗骨架、Template Contract 和当届 profile 叠加 | 不冒充官方模板；不复制旧年份、队号、学校、宣传图或旧规则说明；许可证不清时不随 Harness 分发 class |

其余综合笔记仓库（如 QInzhengk、ravenxrz、Lanrzip）归入同一“方法发现层”：只有在锁定 commit、来源和许可证后才可进入本地索引，不新增平行事实源。

## 2. 学术研究与写作 Skills

| 上游 | 实际长处 | 吸收方式 | 不照搬的部分 |
|---|---|---|---|
| [Yuan1z0825/nature-skills](https://github.com/Yuan1z0825/nature-skills) | claim-first Figure Contract、证据层级、源码/导出/渲染分层 QA | 合并进唯一 `paper_plan.figures[]` 和 PDF visual review | Nature 的固定期刊规格不直接套数模竞赛 |
| [zLanqing/codex-claude-academic-skills](https://github.com/zLanqing/codex-claude-academic-skills) | outline before prose；主张绑定证据；方法写变量/单位/假设；实验写数据/参数/指标/baseline/uncertainty；结果按 claim→evidence→explanation→limitation | 落成 `paper_plan.readiness` 和 formal writer package gate | 不拆多个 Writer，不让修辞规则改变研究事实 |
| [lishix520/academic-paper-skills](https://github.com/lishix520/academic-paper-skills) | 写作前 strategy、贡献/论证顺序和 reviewer 视角 | 合并到 W1 `paper_plan`，不另造七份报告 | 固定样本数、文献数和报告数不适合限时竞赛 |
| [LeonChaoX/qinyan-academic-skills](https://github.com/LeonChaoX/qinyan-academic-skills) | 大型可搜索技能目录、按领域/单 skill 安装、更新检查 | 借鉴“按任务路由和最小加载”，不把 181 个技能全部放进上下文 | 聚合数量不是质量；安装脚本和第三方来源必须逐项审计 |
| 论文精读/X-ray 类 skill | 问题—方法—公式—证据—局限的拆解顺序 | 可用于文献全文核验和 precedent pattern card | LLM 的论文摘要不能替代原文 locator |
| 科研配图生成类 skill | 图前规划、可编辑产物、布局与可读性规则 | 概念图可用；数据图仍必须由冻结数据确定性生成，并走 Figure Contract | 生成图不能冒充实验数据或自动通过统计 QA |

`AcademicForge` 等注册表/精选集合可以用于后续能力发现，但在没有逐文件审计前不进入运行时。医学专用 skill 只在赛题确属医学且完成领域安全审查后加载。

## 3. 明确排除

- AIGC detector rewriter、降重/去痕工具不进入 Harness。它们优化检测器表面分数，不提高模型、数据、证据或论证质量，还可能改变技术含义。
- Star、README 宣传、在线 demo 和“可直接提交”不是质量证据。
- 不把资源库自动选出的“最热门算法”直接交给 Coder；必须通过 `check_modeling_plan.py`。
- 不把模板目录存在、PDF 能编译或肉眼相似当作“用了模板”；必须通过 `check_template_usage.py` 并绑定 build receipt。

## 4. 本轮落地映射

| 上游长处 | 本地落点 |
|---|---|
| Web Search/RAG + 文献核验 | `model_contract.research_basis`、`evidence_registry`、`check_modeling_plan.py` |
| 候选模型决策树/结构化 handoff | `candidate_models[]`、`decisions[]`、`models[].characteristics`、`models[].plan_details` 与特征触发验证 |
| strategy/outline before prose | `paper_plan.readiness`、`check_paper_readiness.py`、正式 `compile_writer_package.py` |
| claim-first figure | 既有 `paper_plan.figures[]` 与 visual QA |
| 模板自动匹配且真实使用 | `template_contract.schema.json`、`init_cumcm_project.py`、`check_template_usage.py`、`safe_build.py` |
| 本地轻量、提交强冻结 | `integrity_mode=dev/research/submission`；只在 submission 强制全量哈希 |
