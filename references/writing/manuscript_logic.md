# Manuscript Logic: 全文主线与章节任务

> 边界：本文说明**何时**加载整篇论证链、**如何消费** `paper_plan` 与 writer package 生成的视图。它不复述 `editorial_style.md` 的句段规范，也不新增合同字段。

## 何时加载

- 开始任何一节正文前（W1 之后、W2 之前），运行 `harness paper write <section>`。
- 该命令自动编译两个可再生视图（`.harness/views/`，可覆盖，不入真源）：
  - `WRITING_SPINE.md`：中心论点 → 章节顺序 → 每节论证单元 → 跨问承接 → 起草顺序 → 摘要证据预算；
  - `sections/<section>_brief.md`：仅本节的有序论证单元、claim 冻结值、已建立事实、下一节 handoff、must-not-claim。
- 若 `.harness/contracts/paper_plan.json` 不存在，视图被跳过并在 CLI 输出中说明原因——先运行 `harness paper plan --compile`。

## 如何消费

1. **先读 spine 再读 brief。** spine 回答"全文为什么按这个顺序走"；brief 回答"本节必须完成哪些论证动作"。
2. **起草顺序与阅读顺序分离。** spine 的 recommended drafting order 按"决定性结果与验证 → 机理阐释 → 综合收束"排序；摘要永远最后从 Evidence Registry 投影，不从正文复制。
3. **每个论证单元只做一件事。** brief 里每个 unit 的 `rhetorical_role` 是该段唯一的主要研究动作；`prerequisite_unit_ids` 指明它依赖哪些已建立事实。
4. **数字只从 brief 的 claim 冻结值取。** brief 缺数字时回查 writer package；writer package 缺失才允许按 `authoring_context` 的降级顺序查 frozen results，且不得自行重算。

## 何时回退

- 某节 brief 引用的 claim 无冻结值 → 该段必须留空并显式标注 missing，不得用散文补齐。
- 跨问承接（spine 的 handoffs）在草稿中断裂 → 运行 `check_reverse_outline.py`，按错误定位修复顺序，而不是重写整节。

## 不可协商

- 视图是投影：改 `paper_plan.json`（经作者面 Markdown 重新编译）而不是改视图。
- 作者 Markdown（`paper/sections/*/draft.md`）永远不被 `harness paper write` 覆盖；视图只写 `.harness/views/`。
