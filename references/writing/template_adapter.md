# 完整用户 LaTeX 模板适配

## 目标

用户给出 Overleaf source ZIP 或本地模板目录时，不能只复制 `main.tex` 和 `.cls`。必须保留模板的 preamble、文献样式、字体、图件、数据文件和辅助宏；Harness 只替换示例正文，并把保留资产登记到模板合同。

## 导入

```powershell
python scripts/latex/import_user_template.py `
  --project-root . `
  --template-root "C:\Users\Administrator\Desktop\美赛模板" `
  --destination paper_en `
  --template-id mcm-user-template-2026 `
  --competition-profile mcm_icm `
  --family mcm_icm `
  --title "Paper title" `
  --problem A `
  --control-number 2600000 `
  --keywords "keyword 1, keyword 2"
```

国赛模板把 `--family` 换为 `cumcm`，并按题面填写标题、题号与关键词。入口文件不叫 `main.tex` 时，显式增加 `--entrypoint relative/path/to/template.tex`，不要让 Agent 猜测多个候选文件。

导入后保留原始 `\documentclass` 与 preamble，在 `\begin{document}` 后以 `\input{harness/body.tex}` 替换演示正文。模板题名、题号和控制号使用 `harness/metadata.tex` 提供的宏；MCM/ICM 的 AI report 通过 `\AImatter` 进入不计正文页数的部分。

## 身份与验收

导入会生成 `template_contract.json`：

- `required_files` 记录被复制的 `.cls/.sty/.bib/.bst`、图件、字体和数据资产；
- `template_snapshot.asset_hashes` 约束这些保留资产不能被静默替换；
- 新导入默认是 `status: draft`，不能因为“能编译”就冒充当届官方模板；
- 先以 `safe_build.py --integrity-mode dev` 做隔离编译，再用当届 profile 运行 `check_pdf.py` 并完成人工 visual review；只有这些证据齐全时，才允许以显式 `--template-status verified` 创建用于正式构建的干净导入副本。

`safe_build.py` 会把 `.ttf/.otf/.ttc/.otc`、BibLaTeX 样式、TikZ/PGF、图件和表格数据一并带入隔离副本。提交前仍须执行 `check_template_usage.py`、`check_pdf.py` 和当前比赛 profile 的页面/匿名/AI 使用检查。

## 不自动做的事

- 不把 community 模板或用户下载的 Overleaf ZIP 宣称为官方 golden template；
- 不猜测复杂 demo 正文中隐含的研究事实；正文由 writer package 写入 `sections/`；
- 不改写用户模板的类文件、字体或参考文献资产；资产漂移会被模板合同检查报错；
- 不绕过当前规则、PDF 渲染与人工视觉审查直接把 `draft` 模板用于正式构建。
