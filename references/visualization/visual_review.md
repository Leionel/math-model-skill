# Visual Review Protocol

视觉 QA 分三层，结论不得互相替代：

1. **Semantic QA（hard）**：图表数据、baseline、方向、统计定义、caption 与 claim/evidence 一致。
2. **Formal QA（profile-driven）**：页数/纸张、字体嵌入、图像分辨率、构建成功和文件哈希。
3. **Perceptual QA（human/multimodal receipt）**：最终尺寸下的裁切、重叠、空白/重复页、CJK 可见性、图表可读性和视觉误导。

`pdffonts` 的 encoding 标签不能独立证明中文已经正确显示；必须查看渲染页。页面密度、留白与“美观”默认只产生 warning；只有官方 profile 违规、不可读、裁切或误导才是 hard error。

W2 enhanced profile 的顺序：

```text
safe_build.py → check_pdf.py（全页渲染 + contact sheet）
→ 人工/多模态逐页检查 → visual_review_receipt.json
```

图 QA 的自动部分运行 `scripts/figures/check_figure.py`；灰度、色觉、语义强调和双轴误导仍需人工判断。
