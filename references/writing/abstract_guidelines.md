# Abstract Guidelines & Editorial Review for Math Modeling

摘要不是结果清单，而是一段可以独立完成“问题—方法—结果—验证—边界—决策含义”闭环的短论证。它应从已经冻结的结果和 `paper_plan.json` 生成，不能由 Writer 浏览 raw output 后临时发明数字、模型名或结论强度。

本文件是写作指导，不是当届官方格式规则。页数、Summary Sheet、字体和栏目以已锁定的 competition profile/template contract 为准；本文件不规定固定句式、固定结果数、固定参考文献数或固定模型评价章节。

## 一、三阶段摘要工作流

### Stage 1：Abstract Draft

先根据 `paper_plan.abstract_results[]`、`required_answer` 和 writer package 写草稿。每个进入摘要的结果应能回到：

- `question_id` 与题目要求的输出；
- 选定模型的 canonical identity；
- `result_id`/`derived_result_id`、单位和比较口径；
- `validation_id` 或独立验证证据；
- 适用边界与未验证范围。

### Stage 2：Fact Backcheck

摘要写完后，逐项回查数字、单位、模型名、比较关系、验证结论和边界。把回查结果记录到 `abstract_results[].fact_check`，并把正文中的摘要片段登记到 `abstract_span`。`passed` 只表示这些字段与已登记证据一致，不表示摘要的表达已经足够好。

### Stage 3：Abstract Final

只在事实回查通过、每个子问题的必要答案可定位、模板/profile 检查通过后定稿。若因篇幅删减方法或数字，应保留能让评委判断答案的最小信息，而不是只留下“采用某模型，结果良好”的空壳句。

## 二、摘要的内容检查

按题目和 `required_answer` 的实际输出检查以下项目：

1. **对象与边界**：研究对象、决策对象和最重要的硬约束是什么？
2. **方法链**：各问分别采用什么模型/算法，方法为什么适配数据与机制？模型名称必须与 `model_contract` 的 canonical identity 一致。
3. **关键答案**：每个需要在摘要回答的子问题是否有可见的量、排序、分类、轨迹、可行方案或建议？结果数目由信息预算和题目需要决定，不设统一配额。
4. **证据与验证**：关键数字来自哪个冻结结果，验证或敏感性结论在哪里？验证不必都塞进摘要，但至少要让读者知道结论经过了什么检查。
5. **边界与含义**：结论适用于哪些数据、场景和假设，不支持什么外推？建议应与 `canonical_recommendation` 保持一致。

数字应带单位和必要的比较口径；比较并非机械要求，只有题目或主张确实涉及相对改进/优劣时才加入相同口径的 baseline。百分比、差值和比例优先引用程序生成的 `derived_result_id`；若项目配置了数值宏，则由宏注入，宏是防漂移工具，不是替代证据链的第二数据库。

## 三、学术用词强度

“显著、最优、稳健、鲁棒、因果、主导因素、广泛适用”等词只能在对应的比较、统计、求解器、敏感性/OOS 或因果设计证据允许时使用。否则改为可观察的事实，例如“在测试范围内保持可行”“当前求解配置下得到的候选方案”“与基线相比降低了 X 个单位”。

检查器可以发现未登记强词和模型身份漂移，但不能自动证明代数正确、因果成立或机制解释真实；这些仍需 W2 数学复核和 Semantic Critic。

## 四、盲读速扫

定稿前做两种不同审阅：

- **30 秒摘要速扫**：只读摘要首句、方法名、关键数字和验证词，确认能复述问题、方法、答案和边界；这是 issue-only 提醒，不生成质量分数。
- **事实回查**：逐数字回到 frozen/derived result，逐模型名回到 model identity，逐验证表述回到 validation artifact；发现冲突就回到 Stage 1/2。

全文还应在渲染后做页面速扫，检查摘要位置、字体、裁切和模板实际加载。不要把静态文本检查当成 PDF 视觉通过。

## 五、比赛模板与语言变体

英文 Summary Sheet、中文摘要或其他语言版本都复用同一份结果与答案合同，只改变表达语言。MCM/ICM 或 CUMCM 的 Summary Sheet 页数、标题、控制号和封面要求必须来自当前 profile/template contract；不能用上一届经验覆盖当届规则，也不能为了“像论文”擅自添加花哨封面。

写作上优先使用具体动词（formulate、estimate、evaluate、validate、compare），但不强迫所有论文采用同一套句式。摘要二次回查的目的是保证事实和逻辑，不是把论文改写成模板化机器文。
