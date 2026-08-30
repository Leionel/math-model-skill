# Illustration Execution: 原生生图触发、边界与回收

> 边界：本文定义 illustration 类图的执行协议。它不复制任何图像生成工具手册，不硬编码图片 API；路由分类见 `tool_router.py`，合同义务见 `figure_contract.md`。

## 主动触发规则

**当且仅当**以下三个条件同时成立时，直接调用当前环境暴露的原生 image generation 工具，不等用户提醒：

1. 该图已完成 Figure Contract 且路由判定为 `illustration`（physical mechanism / system concept / scenario / energy flow concept）；
2. 当前环境暴露原生生图能力（`--capability available`）；
3. competition profile 允许生成式图像（`--ai-policy allowed`）。

触发源是**已批准的 Figure Contract**，不是用户的自然语言提醒。

## 永不生成

- data/result 图：必须确定性绘图（`python_plotting` 路由）；
- 公式密集或承载数值的结构图：走 editable backend（PPTX / Draw.io）；
- 没有完整合同的装饰性可选图；
- live-contest 中 profile 禁止生成图像的情况。

## 执行协议

```powershell
# 1. 生成 provider-neutral 请求记录（harness 永远不调用图片 API）
python scripts/harness.py figure FIG-02 --kind illustration --semantic-type "physical mechanism" `
  --request-illustration --capability available --ai-policy allowed
#    -> .harness/views/figures/FIG-02_image_generation_request.json（含完整 prompt）

# 2. Agent 用当前环境原生工具按 prompt 生成图像

# 3. 回收：登记路径 + SHA-256 + 复核义务
python scripts/harness.py figure FIG-02 --collect-illustration figures/FIG-02/generated.png
#    -> figures/FIG-02/illustration.json（review_status: pending）
```

prompt 由已批准的 figure brief 组合生成（Purpose / Main message / Required elements / Required relations / Reading order / Must not include）；brief 缺节时请求被拒绝并说明缺什么。

## 回收后的义务

- `review_status: pending` → 人工科学复核（实体与关系与 brief 一致、无捏造）+ 视觉复核（可读、灰度安全）+ 最终尺寸复核（有效 DPI ≥ 300）后才能作为正式图进入 W2；
- 登记到 `run_manifest.ai_usage`（`harness ai record`）并在 S1 前运行 `harness ai verify`；
- 未完成 provenance / AI usage / review 的图不得晋升正式图，不得出现在 paper_plan 的 figures[] 正式条目中。

## 能力缺失与规则冲突

- 原生工具缺失：`--capability missing` → 输出事实状态与可执行 prompt，不假装已生成；
- profile 禁止：`--ai-policy forbidden` → 输出 `forbidden_by_profile` 状态并停止；
- 未显式确认能力或规则时保持默认 `unknown`，分别输出 `unknown_capability` / `policy_unresolved` 并停止；
- 回收必须读取同一 `figure_id` 的 `ok=true,status=requested` 请求记录；缺失、错配或未获许可的请求不能登记成正式生成物；
- 两者都不是失败重试的理由，而是向用户报告的事实边界。
