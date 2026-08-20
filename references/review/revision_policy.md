# Bounded Targeted Revision

- 建议由操作者限制为最多两轮；当前 CLI 每次只执行一轮 review，不实现自动
  loop controller。每轮只处理 blocker/high 和会改变结论的 medium。
- finding 必须有稳定 ID、证据位置、owner、required fix；修订前后同一问题的
  finding_id 不变，状态流转为 resolved / accepted_risk / superseded。
- 修订后重跑受影响检查：`harness review --recheck` 只重新校验/登记既有报告
  的绑定与 freshness；随后必须单独运行 `harness validate --strict` 执行完整
  W2 deterministic QA（当前不支持按 finding 选择 QA 子集）。论文已修改时，
  旧报告会 stale，不能靠 `--recheck` 重新变为 current，必须重新审查。
- 论文改动后旧 review 立即 stale（reviewed_artifacts digest 不再匹配），
  不得继续用于 W2；必须重新审查产出新报告。
- 若 blocker+high 数量没有严格减少，或冻结结果/输入哈希被意外改变，操作者
  必须停止下一轮并输出 decision memo；当前 Harness 只提供证据与 Gate，不会
  自动生成或执行该 memo。
- Reviewer 不直接改作者 artifact；作者修改后由 Deterministic QA 和 Critic
  复验。Reviewer 的修改面只有 review report 本身。
- 若修订需要触碰 model contract、frozen result、objective 或关键参数，
  上游 invalidation 生效，退出 W2 回到相应更早的 Gate。
