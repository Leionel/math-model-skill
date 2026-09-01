# Research-first Model Planning

M1 的目的不是确认“已经写了一个模型名”，而是确认：为什么这个问题应采用这套机制、哪些替代方案被比较过、证据支持到哪里、代码将如何实现与证伪。P1 前必须完成研究计划，禁止先实现再倒填理由。

## 不同上游的正确角色

- `zhanwen/MathModel`、`personqianduixue/Math_Model`、`HuangCongQing/Algorithms_MathModels`、`datawhalechina/intro-mathmodel`、`QInzhengk/Math-Model-and-Machine-Learning` 等资料/算法仓库用于发现关键词、候选方法、代码接口和往届案例。它们是检索入口，不是本题模型合理性的证据；算法代码能运行也不证明与题意机制匹配。
- `jihe520/MathModelAgent`、`XiaoMaColtAI/math-modeling-skill` 等 Agent/Skill 的阶段拆分、Web Search/RAG、结构化 handoff、HIL 和验收思路用于工作流设计；不照搬“自动生成可提交论文”的宣传目标，也不把多 Agent 数量当质量。
- `nature-skills`、`academic-paper-skills`、`codex-claude-academic-skills` 的 claim-first、strategy-before-writing、section move 和分层 QA 用于论文论证；不照搬 Nature 字体、固定样本数或固定报告数。
- `latexstudio/CUMCMThesis` 只提供 community 排版底座。实际提交仍以当届官方规则/profile 为准，并必须用 Template Contract 证明源码真的加载了该类。

Star 数只说明关注度，不能替代 commit、许可证、内容与任务适配审计。降 AIGC 检测/去痕仓库不进入质量链；目标是提高事实、模型和论证质量，不是规避检测。

## M1 前的强制顺序

1. **拆题与研究问题**：逐个 `question_id` 写清输出、决策对象、机制、数据和风险。建立 `research_questions[]`，每项同时给出中文和英文关键词。
2. **知识侦察**：用大模型已有知识列出方法族、需要核验的假设和可能的反例，登记为 `source=llm_knowledge`。这一步只能产生查询方向，不能登记成已核验文献事实。
3. **外部检索**：按题目范围选择 Web Search、OpenAlex、Crossref、CNKI、出版社或官方仓储等来源，记录 query、语言、时间、候选数和对应 `research_id`。S5 不把查询、数据库或全文数量设为固定配额；来源多样性只有在造成关键 research obligation gap 时才阻断。
4. **真实文献核验**：先核验题名、作者、年份、venue/DOI，再核验正文是否真正支持所需机制；正式选型至少有一条 `full_text + locator + metadata/content/publication verified` citation evidence。S5 另外将 discovery candidate、full-text core 和 excluded item 分开，分别记录纳入/排除理由，并按机制、假设、参数、基线模型选择、验证和失败模式登记 obligation coverage。
5. **候选模型比较**：每个子问题至少比较两个候选；分别写 mechanism fit、assumptions、data requirements、strengths、weaknesses、evidence IDs 和 rejection conditions。确实只有一个可行候选时写 `single_candidate_waiver`，不能留空。
6. **做选择，不做菜单**：`decisions[]` 明确选中候选、比较标准、决定性证据、未解决风险和所有备选。选中候选必须绑定一个实际 `model_id`。
7. **形成可编码蓝图**：`models[].plan_details` 至少写 mechanism、equation plan、parameter plan、三步以上实现步骤、输出 artifact、validation strategy 和 failure modes。同时声明 `characteristics[]`；随机、场景、相关输入、多阶段、时变、多目标和机器学习特征会分别触发 uncertainty、scenario generalization、correlation validity、nonanticipativity、stability、sensitivity 或 out-of-sample/leakage/baseline 义务。不能把随机规划仅标成普通 optimization 来逃过检验。
8. **人审 M1**：人审重点不是语言完整，而是机制是否贴题、数据是否足够、备选是否公平、文献是否支持、数学是否自洽、验证能否推翻结论。`manual_checks` 必须逐项登记 `problem_mechanism_fit`、`candidate_comparison_fairness`、`data_sufficiency`、`mathematical_consistency`、`literature_support_fit`、`validation_can_falsify`，并同时绑定当前 model contract 与 evidence registry。通过后才允许 P1。

## Gate 命令

```powershell
python scripts/qa/check_modeling_plan.py `
  --model-contract model_contract.json `
  --evidence-registry evidence_registry.json `
  --strict
```

该检查会拒绝：只做大模型脑暴而无外部检索、只搜文献而无全文定位、每问只有一个无豁免候选、选型证据未核验、候选未映射到实际模型、或只有模型名称而无公式/参数/实现/验证/失败计划。
