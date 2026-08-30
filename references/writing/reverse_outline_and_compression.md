# Reverse Outline and Compression: 段落回查与正文分配

> 边界：本文定义成稿后的确定性回查动作。它不评判文风，不替代 `editorial_style.md` 的人工编辑判断。

## 何时运行

初稿完成后、提交 semantic review 前：

```powershell
python scripts/qa/check_reverse_outline.py `
  --paper-plan paper_plan.json `
  --writer-package reports/writer_package.json `
  --draft paper/main.tex `
  --outline-report reports/reverse_outline.md
```

## 检查什么

1. **claim-location**：每个 planned claim 至少通过一个锚定的论证单元出现在正文。找不到 → 阻断（该 claim 没写或锚点丢失）。
2. **承接顺序**：`prerequisite_unit_ids` 的锚点必须早于依赖它的锚点；跨 section 的 handoff 反序是硬错误，说明先写了结论再补前提。
3. **重复扫描**：跨锚点块重复出现的长段落（中文 12+ 字 / 英文 8+ 词连续相同）→ warning；同一结论在多处换皮复述是最常见的机器味来源。
4. **逆向提纲**：每个锚点块的主题句 + 词数输出到 `reverse_outline.md`。人工用它检查"删掉这段后读者还能否接受中心论断"。

## 压缩动作（人工裁决）

重复 warning 出现时按优先级处理：

- 同一 claim 在两处出现 → 保留证据更完整的一处，另一处改为一句话引用；
- 机制解释与结果观察混写 → 拆开，各自归位到对应 rhetorical_role 的单元；
- 压缩不得删除改变结论方向的反例或边界声明（`boundary` 字段标注的内容）。

## 边界

- 本检查不读数值来源（`check_writer_package.py` 负责），不查公式映射（`check_math_writing.py` 负责）。
- topic sentence 抽取是确定性的字符串切分，不是语义理解；人工必须读 reverse outline 报告本身。
- 默认由 deterministic QA 以非 strict 模式调用：锚点/顺序错误阻断，重复 warning 留给人工压缩；只有明确希望把所有重复提示都升级为阻断时才单独加 `--strict`。
