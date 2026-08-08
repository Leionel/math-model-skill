# Submission QA and Final Freeze

W2 只表示内容准备完成；它不等于可提交。

```text
W2 Content Ready
→ S1 competition-specific package QA
→ F1 immutable submission_manifest.json
```

## S1

按照 pinned Competition Profile 检查文件扩展名、字节数、页数范围、附件政策和 AI 声明政策。匿名性、字体/裁切、最终渲染、附件内容完整性等无法可靠从当前 stdlib 脚本判断的项目，必须列入 `required_manual_checks` 并由 S1 human checkpoint 确认。

页数必须同时记录数值和获取方法。`manual_verified` 是明确的人审边界，不应描述成程序自动测量。

## F1

只有以下条件同时满足时才运行 `freeze_submission.py`：

- W2 与 S1 都通过；
- `run_manifest.status=submission_ready`；
- S1 report 为 `ok=true`，且覆盖当前 paper/support/AI disclosure 哈希；
- Competition Profile 哈希仍一致；
- 截止时间与时区已明确。

`submission_manifest.json` 禁止覆盖。论文、附件、AI 声明、规则或截止时间变化时，重新执行 S1，并生成新的 F1 文件；不要修改旧 manifest。
